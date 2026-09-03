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
from dataclasses import dataclass

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
    kept: int = 0
    in_filtered: int = 0
    backed_up: bool = False


def plan_shift(col: Collection, keep: set[int]) -> list[int]:
    """Every date-scheduled card except the ones we're keeping."""
    everything = col.db.list(
        f"select id from cards where queue in {DAY_QUEUES}"
    )
    return [cid for cid in everything if cid not in keep]


def apply_shift(col: Collection, ids: list[int], days: int, conf: dict) -> Result:
    result = Result(kept=0)

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

    if undo_pos is not None:
        col.merge_undo_entries(undo_pos)

    result.moved = total
    return result


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
    save_config(conf)

    bases: set[str] = set()
    for name in picked:
        bases |= found[name]
    keep = cards_in(bases)
    ids = plan_shift(mw.col, keep)

    if not ids:
        showInfo("Nothing to move.", title=ADDON_NAME)
        return

    kept_scheduled = len(
        keep
        & set(mw.col.db.list(f"select id from cards where queue in {DAY_QUEUES}"))
    )
    direction = "back" if days > 0 else "forward"
    subject_list = ", ".join(picked)

    if not askUser(
        f"Keep {subject_list} exactly where it is — {kept_scheduled:,} "
        f"scheduled cards — and push the other {len(ids):,} "
        f"{direction} by {abs(days)} day{'s' if abs(days) != 1 else ''}?\n\n"
        "Only due dates move. Intervals, ease and FSRS memory state are left "
        "alone.\n\nA backup is taken first, and Ctrl/Cmd+Z undoes the whole "
        "thing in one step.",
        defaultno=True,
        title=ADDON_NAME,
    ):
        return

    def done(result: Result) -> None:
        mw.reset()
        lines = [
            f"Moved {result.moved:,} cards {direction} by {abs(days)} "
            f"day{'s' if abs(days) != 1 else ''}.",
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
        op=lambda col: apply_shift(col, ids, days, conf),
        success=done,
    ).with_progress("Clearing the decks…").run_in_background()


action = QAction(f"{ADDON_NAME}…", mw)
qconnect(action.triggered, run)
mw.form.menuTools.addAction(action)
