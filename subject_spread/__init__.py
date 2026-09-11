"""Rebalance Subjects — thin out a unit that is burying you.

Study a big unit in a burst and FSRS schedules it back at you in a burst. Months
later that one subject is 150 cards a day while everything else is 40.

Adds Tools > Rebalance Subjects…  Tick the subjects to thin out, choose how many
days to spread them over, and their cards are moved onto the quietest days in
that window — so the daily total flattens instead of spiking.

Two rules keep it honest:

  * No card is ever moved earlier than it is now. Pulling reviews forward would
    add work, which is the opposite of the point.
  * No card is delayed by more than its own current interval. A card on a
    three-day interval can move three days, not thirty. Delay a card far past
    its interval and you are not rescheduling it, you are forgetting it.

Intervals, ease and FSRS memory state are never modified — only due dates move.
A backup is taken first and the whole run is one undo step.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from anki.collection import Collection
from aqt import mw
from aqt.operations import QueryOp
from aqt.qt import *
from aqt.utils import askUser, qconnect, showInfo

ADDON_NAME = "Rebalance Subjects"

# Queues whose due column holds a day number. 2 = review, 3 = day learning.
DAY_QUEUES = (2, 3)

CHUNK = 500

DEFAULTS = {
    "days": 30,
    "cap_delay_at_interval": True,
    "tag_prefixes": ["#AK_Step2_v12::#Bootcamp", "#AK_Step1_v12::#Bootcamp"],
    "backup_first": True,
}


def get_config() -> dict:
    conf = dict(DEFAULTS)
    user = mw.addonManager.getConfig(__name__) or {}
    conf.update({k: v for k, v in user.items() if k in DEFAULTS})
    return conf


def save_config(conf: dict) -> None:
    mw.addonManager.writeConfig(__name__, conf)


# Subjects
######################################################################


def clean_segment(seg: str) -> str:
    seg = seg.lstrip("#").replace("_", " ")
    return re.sub(r"^\d+\s*", "", seg)


def subjects(conf: dict) -> dict[str, set[str]]:
    """Display name -> the raw tag bases that feed it.

    Grouped one level below the configured prefixes, which is the subject
    level. Matches Exam Focus and Topic Stats, so a subject means the same
    thing everywhere.
    """
    prefixes = conf.get("tag_prefixes") or []
    found: dict[str, set[str]] = {}

    for tag in mw.col.tags.all():
        if prefixes:
            for prefix in prefixes:
                if tag == prefix or tag.startswith(prefix + "::"):
                    rest = tag[len(prefix) :].lstrip(":")
                    if not rest:
                        break
                    raw = rest.split("::")[0]
                    found.setdefault(clean_segment(raw), set()).add(
                        f"{prefix}::{raw}"
                    )
                    break
        else:
            top = tag.split("::")[0]
            found.setdefault(clean_segment(top), set()).add(top)

    return found


def cards_in(bases: set[str]) -> set[int]:
    if not bases:
        return set()
    terms = []
    for base in sorted(bases):
        safe = base.replace('"', '\\"')
        terms.append(f'"tag:{safe}"')
        terms.append(f'"tag:{safe}::*"')
    return set(mw.col.find_cards(" OR ".join(terms)))


# Planning
######################################################################


@dataclass
class Plan:
    targets: dict[int, int] = field(default_factory=dict)
    start: int = 0
    days: int = 0
    moving: int = 0
    before: list[int] = field(default_factory=list)
    after: list[int] = field(default_factory=list)
    max_delay: int = 0
    capped: int = 0
    # Cards the interval rule refuses to drag as far as the window.
    unreachable: int = 0
    # Cards due before the window that get scheduled into it.
    pulled_in: int = 0


def build_plan(
    col: Collection, chosen: set[int], start: int, end: int, conf: dict
) -> Plan:
    """Fit the chosen subjects' cards into the window, flattest-first.

    `start` and `end` are absolute Anki day numbers, inclusive.
    """
    today = col.sched.today
    days = end - start + 1
    cap = bool(conf.get("cap_delay_at_interval", True))

    rows = col.db.all(
        f"select id, due, ivl, odid, odue from cards where queue in {DAY_QUEUES}"
    )

    plan = Plan(start=start, days=days)
    fixed = [0] * days
    before = [0] * days
    ranges = []

    for cid, due, ivl, odid, odue in rows:
        # A card in a filtered deck keeps its position in `due`; the real date
        # it returns to lives in `odue`.
        eff = odue if odid else due
        if eff is None:
            continue
        slot = eff - start
        inside = 0 <= slot < days

        if cid not in chosen:
            if inside:
                before[slot] += 1
                fixed[slot] += 1
            continue

        # Already past the window: nothing to do with it.
        if eff > end:
            continue

        # Never earlier than it is now, never before the window, never in the
        # past; and never past its own interval when the cap is on.
        lo = max(eff, start, today)
        hi = min(end, eff + max(ivl, 1)) if cap else end

        if hi < lo:
            # The interval rule won't stretch this card as far as the window,
            # so it stays where it is and counts as load we cannot move.
            plan.unreachable += 1
            if inside:
                before[slot] += 1
                fixed[slot] += 1
            continue

        if inside:
            before[slot] += 1
        else:
            plan.pulled_in += 1
        if hi < end:
            plan.capped += 1
        ranges.append((cid, eff, lo - start, hi - start))

    plan.before = before
    plan.moving = len(ranges)
    if not ranges:
        plan.after = list(before)
        return plan

    # Least flexible first. Placing the cards with the narrowest choice while
    # the calendar is still empty leaves the roomy ones to fill whatever gaps
    # remain; going in due order instead lets late cards pile against the end
    # of the window, which on a whole-collection rebalance is the difference
    # between a flat 220 a day and a wall of 468 on the final day.
    ranges.sort(key=lambda row: (row[3] - row[2], row[2], row[0]))

    load = list(fixed)
    for cid, eff, lo, hi in ranges:
        # The quietest day it is allowed to land on; ties go to the earliest.
        best = min(range(lo, hi + 1), key=lambda d: (load[d], d))
        load[best] += 1
        target = start + best
        plan.targets[cid] = target
        plan.max_delay = max(plan.max_delay, target - eff)

    plan.after = load
    return plan


# Applying
######################################################################


@dataclass
class Result:
    moved: int = 0
    unchanged: int = 0
    in_filtered: int = 0
    backed_up: bool = False


def merge_undo(col: Collection, undo_pos):
    """Fold the work so far into our single undo entry.

    Anki's undo queue only holds a few dozen operations, and a large
    redistribution writes in many batches. Merging as we go keeps the queue
    short; a failure here costs tidy undo grouping, never the work itself.
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

    undo_pos = None
    try:
        undo_pos = col.add_custom_undo_entry(ADDON_NAME)
    except AttributeError:  # pragma: no cover - older API
        pass

    ids = list(plan.targets)
    total = len(ids)
    done = 0

    for start in range(0, total, CHUNK):
        cards = [col.get_card(cid) for cid in ids[start : start + CHUNK]]
        touched = []
        for card in cards:
            target = plan.targets[card.id]
            if card.odid:
                if card.odue == target:
                    result.unchanged += 1
                    continue
                card.odue = target
                result.in_filtered += 1
            else:
                if card.due == target:
                    result.unchanged += 1
                    continue
                card.due = target
            touched.append(card)

        if touched:
            if hasattr(col, "update_cards"):
                col.update_cards(touched)
            else:  # pragma: no cover - older API
                for card in touched:
                    col.update_card(card)
            result.moved += len(touched)
        undo_pos = merge_undo(col, undo_pos)
        done += len(cards)

        def update(done: int = done) -> None:
            mw.progress.update(
                label=f"Rebalancing… {done:,} / {total:,}",
                value=done,
                max=total,
            )

        mw.taskman.run_on_main(update)

    return result


# Interface
######################################################################


class RebalanceDialog(QDialog):
    def __init__(self, parent, names: list[str], conf: dict) -> None:
        super().__init__(parent)
        self.setWindowTitle(ADDON_NAME)
        self.resize(440, 560)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Tick the subjects that are burying you. Their cards get\n"
                "moved onto the quietest days in the window below, so the\n"
                "daily total flattens out."
            )
        )

        buttons = QHBoxLayout()
        select_all = QPushButton("Select all")
        clear_all = QPushButton("Deselect all")
        qconnect(select_all.clicked, lambda: self.set_all(True))
        qconnect(clear_all.clicked, lambda: self.set_all(False))
        buttons.addWidget(select_all)
        buttons.addWidget(clear_all)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.list = QListWidget()
        for name in names:
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.list.addItem(item)
        layout.addWidget(self.list, 1)

        form = QFormLayout()
        today = QDate.currentDate()
        self.start = QDateEdit(today)
        self.start.setCalendarPopup(True)
        self.start.setMinimumDate(today)
        qconnect(self.start.dateChanged, self.on_start_changed)
        form.addRow("Spread from:", self.start)

        self.end = QDateEdit(today.addDays(max(int(conf["days"]), 2) - 1))
        self.end.setCalendarPopup(True)
        self.end.setMinimumDate(today.addDays(1))
        qconnect(self.end.dateChanged, self.update_span)
        form.addRow("through:", self.end)

        self.span = QLabel()
        form.addRow("", self.span)
        layout.addLayout(form)

        presets = QHBoxLayout()
        for label, length in (("2 weeks", 14), ("1 month", 30), ("3 months", 90)):
            button = QPushButton(label)
            qconnect(
                button.clicked,
                lambda _=False, n=length: self.set_span(n),
            )
            presets.addWidget(button)
        presets.addStretch(1)
        layout.addLayout(presets)

        self.cap = QCheckBox("Never delay a card past its own interval")
        self.cap.setChecked(bool(conf.get("cap_delay_at_interval", True)))
        self.cap.setToolTip(
            "A card on a three-day interval can move three days, not thirty.\n"
            "Unticking lets the load flatten further, at the cost of pushing\n"
            "short-interval cards well past when you would have forgotten them."
        )
        layout.addWidget(self.cap)

        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        qconnect(box.accepted, self.accept)
        qconnect(box.rejected, self.reject)
        layout.addWidget(box)

        self.update_span()

    def set_all(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(self.list.count()):
            self.list.item(i).setCheckState(state)

    def set_span(self, length: int) -> None:
        """A preset counts from the chosen start, not from today."""
        self.end.setDate(self.start.date().addDays(length - 1))

    def on_start_changed(self) -> None:
        start = self.start.date()
        self.end.setMinimumDate(start.addDays(1))
        if self.end.date() <= start:
            self.end.setDate(start.addDays(1))
        self.update_span()

    def update_span(self) -> None:
        days = self.start.date().daysTo(self.end.date()) + 1
        start = self.start.date()
        note = ""
        if start > QDate.currentDate():
            note = "  ·  starts in the future, so cards due before then move into it"
        self.span.setText(f"{days} days{note}")

    def window(self) -> tuple[QDate, QDate]:
        return self.start.date(), self.end.date()

    def chosen(self) -> list[str]:
        return [
            self.list.item(i).text()
            for i in range(self.list.count())
            if self.list.item(i).checkState() == Qt.CheckState.Checked
        ]


def profile(values: list[int], width: int = 10) -> str:
    """A short day-by-day sample, since a peak alone hides the shape."""
    return "  ".join(f"{v:,}" for v in values[:width])


def describe(plan: Plan, picked: list[str], start: QDate, end: QDate) -> str:
    before_peak = max(plan.before) if plan.before else 0
    after_peak = max(plan.after) if plan.after else 0

    lines = [
        f"Rebalance {plan.moving:,} cards from {', '.join(picked)} across "
        f"{start.toString('MMM d')} – {end.toString('MMM d')} "
        f"({plan.days} days)?",
        "",
        f"Busiest day now:        {before_peak:,} cards",
        f"Busiest day afterwards: {after_peak:,} cards",
        "",
        f"Daily totals from {start.toString('MMM d')}:",
        f"  now:   {profile(plan.before)}",
        f"  after: {profile(plan.after)}",
        "",
        "These totals include every other subject, which stays exactly where "
        "it is — so this is the load you will actually meet, not just the "
        "part being moved.",
    ]
    if plan.pulled_in:
        lines.append(
            f"\n{plan.pulled_in:,} cards due before "
            f"{start.toString('MMM d')} are scheduled into the window."
        )
    if plan.unreachable:
        lines.append(
            f"{plan.unreachable:,} cards stay where they are: reaching the "
            "window would delay them past their own interval."
        )
    if plan.max_delay:
        lines.append(
            f"\nNo card moves earlier. The largest delay is "
            f"{plan.max_delay} days."
        )
    lines += [
        "",
        "Intervals, ease and FSRS memory state are untouched — only due dates "
        "move. A backup is taken first, and Ctrl/Cmd+Z undoes the whole run.",
    ]
    return "\n".join(lines)


def run() -> None:
    if mw.state == "review":
        showInfo(
            "Close the reviewer first — this moves the cards it is drawing "
            "from.",
            title=ADDON_NAME,
        )
        return

    conf = get_config()
    found = subjects(conf)
    if not found:
        showInfo(
            "No subjects found in your tags.\n\nThis reads subjects from a tag "
            "hierarchy. If you don't use AnKing decks, set tag_prefixes to [] "
            "in this add-on's config and each top-level tag becomes a subject.",
            title=ADDON_NAME,
        )
        return

    dialog = RebalanceDialog(mw, sorted(found), conf)
    if not dialog.exec():
        return

    picked = dialog.chosen()
    start_date, end_date = dialog.window()
    conf["days"] = start_date.daysTo(end_date) + 1
    conf["cap_delay_at_interval"] = dialog.cap.isChecked()
    save_config(conf)

    # Anki counts days from the collection's creation, so translate the chosen
    # calendar dates into that numbering.
    now = QDate.currentDate()
    today = mw.col.sched.today
    start_day = today + now.daysTo(start_date)
    end_day = today + now.daysTo(end_date)

    if not picked:
        showInfo("Pick at least one subject.", title=ADDON_NAME)
        return

    bases: set[str] = set()
    for name in picked:
        bases |= found[name]
    chosen = cards_in(bases)

    plan = build_plan(mw.col, chosen, start_day, end_day, conf)
    if not plan.moving:
        extra = ""
        if plan.unreachable:
            extra = (
                f"\n\n{plan.unreachable:,} cards could only reach that window "
                "by being delayed past their own interval, so they were left "
                "alone. A window closer to today would take them."
            )
        showInfo(
            f"Nothing from {', '.join(picked)} can move into "
            f"{start_date.toString('MMM d')} – {end_date.toString('MMM d')}."
            + extra,
            title=ADDON_NAME,
        )
        return

    if not askUser(
        describe(plan, picked, start_date, end_date),
        defaultno=True,
        title=ADDON_NAME,
    ):
        return

    def done(result: Result) -> None:
        mw.reset()
        lines = [
            f"Moved {result.moved:,} cards.",
        ]
        if result.unchanged:
            lines.append(
                f"{result.unchanged:,} were already on the best day and were "
                "left alone."
            )
        lines += [
            "",
            f"Busiest day is now {max(plan.after):,} cards, down from "
            f"{max(plan.before):,}.",
            "",
            "Intervals and FSRS memory state are unchanged.",
        ]
        if result.in_filtered:
            lines.append(
                f"\n{result.in_filtered:,} cards sit in a filtered deck, so "
                "their home-deck date moved instead."
            )
        lines.append("\nCtrl/Cmd+Z undoes the whole rebalance.")
        showInfo("\n".join(lines), title=ADDON_NAME)

    QueryOp(
        parent=mw,
        op=lambda col: apply_plan(col, plan, conf),
        success=done,
    ).with_progress("Rebalancing subjects…").run_in_background()


action = QAction(f"{ADDON_NAME}…", mw)
qconnect(action.triggered, run)
mw.form.menuTools.addAction(action)
