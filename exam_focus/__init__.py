"""Exam Focus — keep one subject due, push everything else back.

Take a Day Off clears tomorrow completely. This clears everything *except* the
subject you are being examined on, so the day before a cardiology exam you sit
down to cardiology and nothing else, and the rest of the collection is waiting
untouched the day after.

Subjects come from your tag hierarchy, grouped the same way Topic Stats groups
them, so "Cardiology" means the same thing in both.

Only due dates move. Intervals, ease and FSRS memory state are never touched, so
nothing is treated as late and nothing is rescheduled as though you answered it.
A backup is taken first and the whole shift is one undo step.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

import json
import os

from anki.collection import Collection
from aqt import mw
from aqt.operations import QueryOp
from aqt.qt import *
from aqt.utils import askUser, qconnect, showInfo

ADDON_NAME = "Exam Focus"

# Queues whose `due` column holds a day number. 2 = review, 3 = day learning.
DAY_QUEUES = (2, 3)

CHUNK = 500

DEFAULTS = {
    "days": 1,
    # A pure exam day means new and learning cards from other subjects have to
    # be held back too, or Anki still serves them tomorrow.
    "hold_other_new": True,
    "include_learning": True,
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
    level: "Cardiology", "Pulmonology", and so on.
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
            # No prefixes configured: treat each top-level tag as a subject.
            top = tag.split("::")[0]
            found.setdefault(clean_segment(top), set()).add(top)

    return found


def cards_in(bases: set[str]) -> set[int]:
    """Every card whose note carries one of these tags, or a child of it."""
    if not bases:
        return set()
    terms = []
    for base in sorted(bases):
        safe = base.replace('"', '\\"')
        terms.append(f'"tag:{safe}"')
        terms.append(f'"tag:{safe}::*"')
    return set(mw.col.find_cards(" OR ".join(terms)))


# The shift
######################################################################


@dataclass
class Result:
    moved: int = 0
    learning: int = 0
    held_new: int = 0
    kept: int = 0
    in_filtered: int = 0
    backed_up: bool = False


def held_file() -> str:
    folder = os.path.join(os.path.dirname(__file__), "user_files")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "held_new.json")


def load_held() -> list[int]:
    try:
        with open(held_file()) as handle:
            return json.load(handle).get("card_ids", [])
    except Exception:
        return []


def save_held(card_ids: list[int]) -> None:
    with open(held_file(), "w") as handle:
        json.dump({"card_ids": card_ids, "saved": time.time()}, handle)


def plan_shift(col: Collection, keep: set[int], conf: dict):
    """The three groups that have to move for a clean exam day.

    Reviews move by date. Intraday learning cards store a timestamp instead, so
    they move in seconds. New cards have no date at all — the only way to stop
    Anki serving them tomorrow is to suspend them, so we do, and remember which
    ones so they can be released afterwards.
    """
    reviews = [
        cid
        for cid in col.db.list(f"select id from cards where queue in {DAY_QUEUES}")
        if cid not in keep
    ]
    learning = []
    if conf.get("include_learning", True):
        learning = [
            cid
            for cid in col.db.list("select id from cards where queue = 1")
            if cid not in keep
        ]
    new = []
    if conf.get("hold_other_new", True):
        # Only cards inside the subject taxonomy. An unrelated deck — guitar
        # practice, a language deck — is nobody's exam subject and is left be.
        in_subjects = tagged_cards(conf)
        new = [
            cid
            for cid in col.db.list("select id from cards where queue = 0")
            if cid not in keep and (not in_subjects or cid in in_subjects)
        ]
    return reviews, learning, new


def tagged_cards(conf: dict) -> set[int]:
    """Every card whose note sits anywhere under the configured prefixes."""
    prefixes = conf.get("tag_prefixes") or []
    if not prefixes:
        return set()
    terms = []
    for prefix in prefixes:
        safe = prefix.replace('"', '\\"')
        terms.append(f'"tag:{safe}::*"')
    return set(mw.col.find_cards(" OR ".join(terms)))


def apply_shift(
    col: Collection,
    reviews: list[int],
    learning: list[int],
    new: list[int],
    days: int,
    conf: dict,
) -> Result:
    result = Result(kept=0)
    ids = reviews

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

    total = len(ids)
    done = 0
    for start in range(0, total, CHUNK):
        cards = [col.get_card(cid) for cid in ids[start : start + CHUNK]]
        for card in cards:
            if card.odid:
                # Sitting in a filtered deck: `due` is its position there, and
                # `odue` is the real date it goes back to. Move that instead.
                if card.odue:
                    card.odue += days
                    result.in_filtered += 1
            else:
                card.due += days
        if hasattr(col, "update_cards"):
            col.update_cards(cards)
        else:  # pragma: no cover - older API
            for card in cards:
                col.update_card(card)
        done += len(cards)

        def update(done: int = done) -> None:
            mw.progress.update(
                label=f"Moving cards… {done:,} / {total:,}",
                value=done,
                max=total,
            )

        mw.taskman.run_on_main(update)

    # Learning cards keep a unix timestamp in `due`, not a day number.
    for start in range(0, len(learning), CHUNK):
        cards = [col.get_card(cid) for cid in learning[start : start + CHUNK]]
        for card in cards:
            card.due += days * 86400
        if hasattr(col, "update_cards"):
            col.update_cards(cards)
        else:  # pragma: no cover - older API
            for card in cards:
                col.update_card(card)
    result.learning = len(learning)

    # New cards have no due date to move, so holding them back means
    # suspending them. Remember exactly which, so releasing them later can't
    # touch the thousands the user suspended deliberately.
    if new:
        col.sched.suspend_cards(new)
        save_held(list(new))
        result.held_new = len(new)

    if undo_pos is not None:
        col.merge_undo_entries(undo_pos)

    result.moved = total
    return result


def release_held() -> None:
    """Unsuspend exactly the new cards this add-on suspended."""
    card_ids = load_held()
    if not card_ids:
        showInfo(
            "No held cards to release.\n\nThis only unsuspends new cards that "
            "Exam Focus suspended itself — it will never touch cards you "
            "suspended deliberately.",
            title=ADDON_NAME,
        )
        return
    still = [
        cid
        for cid in card_ids
        if col_queue(cid) == -1
    ]
    mw.col.sched.unsuspend_cards(still)
    save_held([])
    mw.reset()
    showInfo(
        f"Released {len(still):,} new cards back into rotation.",
        title=ADDON_NAME,
    )


def col_queue(card_id: int) -> int | None:
    return mw.col.db.scalar("select queue from cards where id = ?", card_id)


# Interface
######################################################################


class ExamFocusDialog(QDialog):
    def __init__(self, parent, names: list[str], conf: dict) -> None:
        super().__init__(parent)
        self.setWindowTitle(ADDON_NAME)
        self.resize(420, 520)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Keep these subjects due, and push everything else back.\n"
                "Tick more than one if the exam covers more than one."
            )
        )

        self.list = QListWidget()
        for name in names:
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.list.addItem(item)
        layout.addWidget(self.list, 1)

        self.hold_new = QCheckBox(
            "Also hold back other subjects' new cards"
        )
        self.hold_new.setChecked(bool(conf.get("hold_other_new", True)))
        self.hold_new.setToolTip(
            "New cards have no due date, so the only way to keep them out of "
            "tomorrow is to suspend them. Exam Focus remembers which ones and "
            "can release exactly those afterwards.\n\nUntick if your new "
            "cards are already held back by a deck limit."
        )
        layout.addWidget(self.hold_new)

        form = QFormLayout()
        self.days = QSpinBox()
        self.days.setRange(-30, 30)
        self.days.setValue(int(conf["days"]))
        self.days.setSuffix(" days")
        form.addRow("Push everything else back by:", self.days)
        layout.addLayout(form)

        layout.addWidget(
            QLabel(
                "Only due dates move — intervals, ease and FSRS memory\n"
                "state are left alone. A negative number undoes a shift."
            )
        )

        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        qconnect(box.accepted, self.accept)
        qconnect(box.rejected, self.reject)
        layout.addWidget(box)

    def chosen(self) -> list[str]:
        return [
            self.list.item(i).text()
            for i in range(self.list.count())
            if self.list.item(i).checkState() == Qt.CheckState.Checked
        ]


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
            "No subjects found in your tags.\n\nThis groups subjects from a "
            "tag hierarchy. If you don't use AnKing decks, set tag_prefixes "
            "to [] in this add-on's config and it will treat each top-level "
            "tag as a subject.",
            title=ADDON_NAME,
        )
        return

    dialog = ExamFocusDialog(mw, sorted(found), conf)
    if not dialog.exec():
        return

    picked = dialog.chosen()
    days = dialog.days.value()
    if not picked:
        showInfo("Pick at least one subject to keep.", title=ADDON_NAME)
        return
    if days == 0:
        showInfo("Zero days would move nothing.", title=ADDON_NAME)
        return

    conf["days"] = days
    conf["hold_other_new"] = dialog.hold_new.isChecked()
    save_config(conf)

    bases: set[str] = set()
    for name in picked:
        bases |= found[name]
    keep = cards_in(bases)
    reviews, learning, new = plan_shift(mw.col, keep, conf)

    if not (reviews or learning or new):
        showInfo("Nothing to move.", title=ADDON_NAME)
        return
    ids = reviews

    kept_scheduled = len(
        keep
        & set(mw.col.db.list(f"select id from cards where queue in {DAY_QUEUES}"))
    )
    direction = "back" if days > 0 else "forward"
    subject_list = ", ".join(picked)

    plural = "s" if abs(days) != 1 else ""
    detail = [
        f"Keep {subject_list} exactly where it is — {kept_scheduled:,} "
        "scheduled cards — and clear everything else off tomorrow?",
        "",
        f"· {len(reviews):,} review cards pushed {direction} {abs(days)} "
        f"day{plural}",
    ]
    if learning:
        detail.append(f"· {len(learning):,} learning cards pushed with them")
    if new:
        detail.append(
            f"· {len(new):,} new cards from other subjects held back "
            "(suspended, and released with one menu click afterwards)"
        )
    detail += [
        "",
        "Only due dates move. Intervals, ease and FSRS memory state are left "
        "alone.",
        "",
        "A backup is taken first, and Ctrl/Cmd+Z undoes the whole thing in "
        "one step.",
    ]
    if not askUser(
        "\n".join(detail),
        defaultno=True,
        title=ADDON_NAME,
    ):
        return

    def done(result: Result) -> None:
        mw.reset()
        lines = [
            f"Moved {result.moved:,} review cards {direction} by {abs(days)} "
            f"day{'s' if abs(days) != 1 else ''}.",
        ]
        if result.learning:
            lines.append(f"Moved {result.learning:,} learning cards with them.")
        if result.held_new:
            lines.append(
                f"Held back {result.held_new:,} new cards from other subjects "
                "— release them with Tools → Exam Focus: Release Held Cards."
            )
        lines += [
            "",
            f"{subject_list} stayed put — {kept_scheduled:,} cards still due "
            "on their original days.",
        ]
        if result.in_filtered:
            lines.append(
                f"\n{result.in_filtered:,} of those sit in a filtered deck, so "
                "their home-deck date moved instead; they stay available in "
                "the filtered deck until it is emptied."
            )
        lines += ["", "Ctrl/Cmd+Z undoes the whole shift."]
        showInfo("\n".join(lines), title=ADDON_NAME)

    QueryOp(
        parent=mw,
        op=lambda col: apply_shift(col, reviews, learning, new, days, conf),
        success=done,
    ).with_progress("Clearing the decks…").run_in_background()


action = QAction(f"{ADDON_NAME}…", mw)
qconnect(action.triggered, run)
mw.form.menuTools.addAction(action)

release_action = QAction(f"{ADDON_NAME}: Release Held Cards", mw)
qconnect(release_action.triggered, release_held)
mw.form.menuTools.addAction(release_action)
