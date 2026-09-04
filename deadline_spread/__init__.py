"""Spread to a Deadline — clear a backlog by fanning it out over the days you have left.

Adds Tools > Spread to a Deadline…  Pick a date, and every card that is due or
overdue right now is redistributed evenly across the days between today and that
date, most-overdue first, so the pile is gone and everything comes up before the
deadline.

Only the backlog moves. Cards already scheduled for a future day stay where they
are — which is why the confirmation shows the *combined* daily load: the spread
backlog plus the reviews those days were already going to bring. A backlog
spread that ignored them would promise 140 cards a day and deliver 500.

Intervals, ease and FSRS memory state are never touched; only due dates change.
A forced backup is taken first, and the whole redistribution is one undo step.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from anki.collection import Collection
from anki.utils import ids2str
from aqt import mw
from aqt.operations import QueryOp
from aqt.qt import *
from aqt.utils import askUser, qconnect, showInfo

ADDON_NAME = "Spread to a Deadline"

# Queues whose `due` column holds a day number. 2 = review, 3 = day learning.
# Negative queues (suspended, buried) are excluded by construction.
DAY_QUEUES = (2, 3)

# Cards per backend write.
CHUNK = 500

DEFAULTS = {
    "default_days_ahead": 14,
    "deck": "",
    "backup_first": True,
}


def get_config() -> dict:
    conf = dict(DEFAULTS)
    user = mw.addonManager.getConfig(__name__) or {}
    conf.update({k: v for k, v in user.items() if k in DEFAULTS})
    return conf


def save_config(conf: dict) -> None:
    """Remember the deck and window, so the next run opens where you left off."""
    mw.addonManager.writeConfig(__name__, conf)


def daily_review_limit(col: Collection, deck_name: str) -> int | None:
    """The deck preset's reviews/day cap.

    Anki hides anything past this, so a plan that exceeds it quietly fails to
    deliver the cards it just scheduled. Returns None when it can't be read, or
    for the whole collection, where per-deck presets make one number meaningless.
    """
    if not deck_name:
        return None
    try:
        did = col.decks.id_for_name(deck_name)
        if did is None:
            return None
        return col.decks.config_dict_for_deck_id(did)["rev"]["perDay"]
    except Exception:
        return None


# Scope
######################################################################


def deck_ids_for(col: Collection, deck_name: str) -> list[int]:
    """Deck plus its children, or [] meaning the whole collection."""
    if not deck_name:
        return []
    did = col.decks.id_for_name(deck_name)
    if did is None:
        return []
    return list(col.decks.deck_and_child_ids(did))


def deck_sql(deck_ids: list[int]) -> str:
    if not deck_ids:
        return ""
    ids = ids2str(deck_ids)
    # A card sitting in a filtered deck has the filtered deck in `did` and its
    # home deck in `odid`, so match either.
    return f" and (did in {ids} or odid in {ids})"


# Planning
######################################################################


@dataclass
class Plan:
    targets: dict[int, int] = field(default_factory=dict)  # card id -> due day
    days: int = 0
    backlog: int = 0
    spread_per_day: list[int] = field(default_factory=list)
    existing_per_day: list[int] = field(default_factory=list)

    @property
    def combined_per_day(self) -> list[int]:
        return [a + b for a, b in zip(self.spread_per_day, self.existing_per_day)]


def build_plan(col: Collection, deck_ids: list[int], days: int) -> Plan:
    """Fan the backlog out evenly across `days`, most overdue first."""
    today = col.sched.today
    where = deck_sql(deck_ids)

    # The backlog: due today or earlier. Ordered by how overdue it already is,
    # so Anki's own sense of priority survives the redistribution.
    rows = col.db.all(
        f"select id from cards where queue in {DAY_QUEUES} and due <= ?{where}"
        " order by due asc, id asc",
        today,
    )
    ids = [r[0] for r in rows]

    plan = Plan(days=days, backlog=len(ids))
    plan.spread_per_day = [0] * days
    if not ids:
        plan.existing_per_day = [0] * days
        return plan

    for i, cid in enumerate(ids):
        offset = (i * days) // len(ids)
        plan.targets[cid] = today + offset
        plan.spread_per_day[offset] += 1

    # What those same days were already going to bring, so the confirmation
    # can quote a load the user will actually experience.
    existing = dict(
        col.db.all(
            f"select due, count() from cards where queue in {DAY_QUEUES}"
            f" and due > ? and due < ?{where} group by due",
            today,
            today + days,
        )
    )
    plan.existing_per_day = [existing.get(today + d, 0) for d in range(days)]
    return plan


# The redistribution
######################################################################


@dataclass
class Result:
    moved: int = 0
    backed_up: bool = False


def write_cards(col: Collection, cards: list) -> None:
    if hasattr(col, "update_cards"):
        col.update_cards(cards)
    else:  # pragma: no cover - older API
        for card in cards:
            col.update_card(card)


def merge_undo(col: Collection, undo_pos):
    """Fold the work so far into our single undo entry.

    Anki's undo queue only holds a few dozen operations. A large shift writes
    in many batches, which would evict the custom entry before the end and make
    the final merge fail with "target undo op not found" — after every card had
    already moved. Merging as we go keeps the queue short, and a failure here
    costs tidy undo grouping, never the work itself.
    """
    if undo_pos is None:
        return None
    try:
        col.merge_undo_entries(undo_pos)
        return undo_pos
    except Exception:
        return None


def apply_plan(col: Collection, plan: Plan, conf: dict) -> Result:
    result = Result()

    if conf["backup_first"]:
        mw.taskman.run_on_main(
            lambda: mw.progress.update(label="Backing up collection…")
        )
        result.backed_up = col.create_backup(
            backup_folder=mw.pm.backupFolder(),
            force=True,
            wait_for_completion=True,
        )

    ids = list(plan.targets)
    total = len(ids)
    done = 0

    undo_pos = None
    try:
        undo_pos = col.add_custom_undo_entry(ADDON_NAME)
    except AttributeError:  # pragma: no cover - older API
        pass

    for start in range(0, total, CHUNK):
        cards = [col.get_card(cid) for cid in ids[start : start + CHUNK]]
        for card in cards:
            target = plan.targets[card.id]
            card.due = target
            # Keep the home-deck due date in step for filtered-deck cards.
            if card.odid and card.odue:
                card.odue = target
        write_cards(col, cards)
        undo_pos = merge_undo(col, undo_pos)
        done += len(cards)

        def update(done: int = done) -> None:
            mw.progress.update(
                label=f"Spreading cards… {done:,} / {total:,}",
                value=done,
                max=total,
            )

        mw.taskman.run_on_main(update)

    merge_undo(col, undo_pos)

    result.moved = total
    return result


# Interface
######################################################################


class DeadlineDialog(QDialog):
    """Date picker plus an optional deck scope."""

    def __init__(self, parent, decks: list[str], conf: dict) -> None:
        super().__init__(parent)
        self.setWindowTitle(ADDON_NAME)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Spread everything you are behind on across the days\n"
                "between today and a date, so it is all done before then."
            )
        )

        form = QFormLayout()
        self.date = QDateEdit(QDate.currentDate().addDays(conf["default_days_ahead"]))
        self.date.setCalendarPopup(True)
        self.date.setMinimumDate(QDate.currentDate().addDays(1))
        form.addRow("Everything due before:", self.date)

        self.deck = QComboBox()
        self.deck.addItem("Whole collection")
        self.deck.addItems(decks)
        if conf["deck"] in decks:
            self.deck.setCurrentText(conf["deck"])
        form.addRow("Deck:", self.deck)
        layout.addLayout(form)

        layout.addWidget(
            QLabel(
                "Only cards you are already behind on move. Intervals and FSRS\n"
                "memory state are left alone — only due dates change."
            )
        )

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        qconnect(buttons.accepted, self.accept)
        qconnect(buttons.rejected, self.reject)
        layout.addWidget(buttons)

    def values(self) -> tuple[QDate, str]:
        deck = "" if self.deck.currentIndex() == 0 else self.deck.currentText()
        return self.date.date(), deck


def describe(plan: Plan, deadline: QDate, limit: int | None = None) -> str:
    combined = plan.combined_per_day
    per_day = plan.backlog / plan.days
    already = sum(plan.existing_per_day)

    lines = [
        f"Spread {plan.backlog:,} cards you are behind on across "
        f"{plan.days} day{'s' if plan.days != 1 else ''}, so everything is due "
        f"before {deadline.toString('MMM d')}?",
        "",
        f"That is about {per_day:,.0f} backlog cards a day.",
    ]
    if already:
        lines += [
            f"Those days already hold {already:,} scheduled reviews, so your "
            f"real load runs {min(combined):,}–{max(combined):,} cards a day.",
        ]
    else:
        lines.append("Nothing else is scheduled in that window.")

    if limit and max(combined) > limit:
        lines += [
            "",
            f"Heads up: this deck's review limit is {limit:,} a day, so on the "
            "busiest days you would not be shown everything scheduled. Pick a "
            "later date, or raise the limit in the deck options.",
        ]

    lines += [
        "",
        "Cards already scheduled for a future day are left where they are. "
        "New and suspended cards are untouched, and no interval, ease or FSRS "
        "value changes — only due dates move.",
        "",
        "A backup is taken first, and Ctrl/Cmd+Z undoes the whole thing.",
    ]
    return "\n".join(lines)


def on_done(result: Result, plan: Plan, deadline: QDate) -> None:
    mw.reset()
    combined = plan.combined_per_day
    lines = [
        f"Spread {result.moved:,} cards across {plan.days} "
        f"day{'s' if plan.days != 1 else ''}.",
        "",
        f"Nothing is now due after {deadline.toString('MMM d')}, and your "
        f"daily load runs {min(combined):,}–{max(combined):,} cards.",
        "",
        "Intervals, ease and FSRS memory state are unchanged.",
    ]
    if result.backed_up:
        lines.append("A backup was taken before the change.")
    lines.append("Ctrl/Cmd+Z undoes the whole redistribution.")
    showInfo("\n".join(lines), title=ADDON_NAME)


def run() -> None:
    if mw.state == "review":
        showInfo(
            "Close the reviewer first — this moves the cards it is drawing from.",
            title=ADDON_NAME,
        )
        return

    conf = get_config()
    decks = sorted(d.name for d in mw.col.decks.all_names_and_ids())

    dialog = DeadlineDialog(mw, decks, conf)
    if not dialog.exec():
        return
    deadline, deck_name = dialog.values()

    days = QDate.currentDate().daysTo(deadline)
    if days < 1:
        showInfo("Pick a date at least one day from now.", title=ADDON_NAME)
        return

    conf["deck"] = deck_name
    conf["default_days_ahead"] = days
    save_config(conf)

    deck_ids = deck_ids_for(mw.col, deck_name)
    plan = build_plan(mw.col, deck_ids, days)

    if not plan.backlog:
        where = f' in "{deck_name}"' if deck_name else ""
        showInfo(
            f"Nothing{where} is due or overdue, so there is no backlog to "
            "spread.\n\nThis only moves cards you are already behind on — to "
            "pull future cards forward as well, that is a different job.",
            title=ADDON_NAME,
        )
        return

    limit = daily_review_limit(mw.col, deck_name)
    if not askUser(describe(plan, deadline, limit), title=ADDON_NAME):
        return

    QueryOp(
        parent=mw,
        op=lambda col: apply_plan(col, plan, conf),
        success=lambda result: on_done(result, plan, deadline),
    ).with_progress("Spreading the backlog…").run_in_background()


action = QAction(f"{ADDON_NAME}…", mw)
qconnect(action.triggered, run)
mw.form.menuTools.addAction(action)
