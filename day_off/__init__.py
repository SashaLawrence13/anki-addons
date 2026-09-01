"""Take a Day Off — slide the whole review schedule forward, intervals intact.

Adds Tools > Take a Day Off…  Every scheduled card's due date moves by the number
of days you pick. Interval, ease factor and FSRS memory state are left exactly as
they were, so nothing is punished for the skipped day and no card comes back
looking overdue.

The entire schedule slides together rather than just today's cards, which is the
point: shifting only what is due today would hand you a double pile tomorrow.

A forced backup is taken first, and the shift is exactly reversible — run it again
with a negative number to pull everything back.
"""

from __future__ import annotations

from dataclasses import dataclass

from anki.collection import Collection
from aqt import mw
from aqt.operations import QueryOp
from aqt.qt import *
from aqt.utils import askUser, qconnect, showInfo, tooltip

ADDON_NAME = "Take a Day Off"

# Queues whose `due` column holds a day number, so adding N shifts by N days.
# 2 = review, 3 = day learning (a learning card already waiting for tomorrow).
DAY_QUEUES = (2, 3)

# Queue 1 is intraday learning, where `due` is a unix timestamp instead.
INTRADAY_QUEUE = 1
SECONDS_PER_DAY = 86400

# Cards per backend write. Keeps the progress bar honest without a round trip
# per card.
CHUNK = 500

DEFAULTS = {
    "default_days": 1,
    "include_intraday_learning": False,
    "backup_first": True,
}


def get_config() -> dict:
    conf = dict(DEFAULTS)
    user = mw.addonManager.getConfig(__name__) or {}
    conf.update({k: v for k, v in user.items() if k in DEFAULTS})
    return conf


# Counting
######################################################################


def count_scheduled(col: Collection) -> tuple[int, int]:
    """Cards the shift would touch: (day-scheduled, intraday learning)."""
    scheduled = col.db.scalar(
        "select count() from cards where queue in (2, 3)"
    ) or 0
    intraday = col.db.scalar(
        "select count() from cards where queue = ?", INTRADAY_QUEUE
    ) or 0
    return scheduled, intraday


# The shift itself
######################################################################


@dataclass
class Result:
    shifted: int = 0
    intraday: int = 0
    backed_up: bool = False


def write_cards(col: Collection, cards: list) -> None:
    if hasattr(col, "update_cards"):
        col.update_cards(cards)
    else:  # pragma: no cover - older API
        for card in cards:
            col.update_card(card)


def shift_ids(col: Collection, ids: list[int], delta: int, progress) -> None:
    for start in range(0, len(ids), CHUNK):
        cards = [col.get_card(cid) for cid in ids[start : start + CHUNK]]
        for card in cards:
            card.due += delta
            # A card sitting in a filtered deck keeps its real due date in
            # `odue`; move that too so it returns to the right day.
            if card.odid and card.odue:
                card.odue += delta
        write_cards(col, cards)
        progress(len(cards))


def take_day_off(col: Collection, days: int, conf: dict) -> Result:
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

    scheduled_ids = col.db.list("select id from cards where queue in (2, 3)")
    intraday_ids = (
        col.db.list("select id from cards where queue = ?", INTRADAY_QUEUE)
        if conf["include_intraday_learning"]
        else []
    )

    total = len(scheduled_ids) + len(intraday_ids)
    done = 0

    def progress(n: int) -> None:
        nonlocal done
        done += n

        def update() -> None:
            mw.progress.update(
                label=f"Moving due dates… {done:,} / {total:,}",
                value=done,
                max=total,
            )

        mw.taskman.run_on_main(update)

    # One undo entry for the whole sweep, so Ctrl/Cmd+Z takes back all of it.
    undo_pos = None
    try:
        undo_pos = col.add_custom_undo_entry(f"{ADDON_NAME} ({days:+d} days)")
    except AttributeError:  # pragma: no cover - older API
        pass

    shift_ids(col, scheduled_ids, days, progress)
    shift_ids(col, intraday_ids, days * SECONDS_PER_DAY, progress)

    if undo_pos is not None:
        col.merge_undo_entries(undo_pos)

    result.shifted = len(scheduled_ids)
    result.intraday = len(intraday_ids)
    return result


# Interface
######################################################################


def on_done(result: Result, days: int) -> None:
    mw.reset()

    moved = result.shifted + result.intraday
    direction = "later" if days > 0 else "earlier"
    lines = [
        f"Moved {moved:,} cards {abs(days)} day{'s' if abs(days) != 1 else ''} "
        f"{direction}.",
        "",
        "Intervals, ease and FSRS memory state are unchanged.",
    ]
    if result.backed_up:
        lines.append("A backup was taken before the change.")
    lines.append(
        f"To put it back, run {ADDON_NAME} again with {-days:+d}."
    )
    showInfo("\n".join(lines), title=ADDON_NAME)


def run() -> None:
    conf = get_config()
    scheduled, intraday = count_scheduled(mw.col)

    if not scheduled and not intraday:
        showInfo("Nothing is scheduled, so there is nothing to move.")
        return

    days, ok = QInputDialog.getInt(
        mw,
        ADDON_NAME,
        "Push every scheduled card forward by how many days?\n\n"
        "Intervals and FSRS memory state stay exactly as they are —\n"
        "only the dates move. Use a negative number to pull them back.",
        conf["default_days"],
        -365,
        365,
        1,
    )
    if not ok or days == 0:
        return

    counted = scheduled + (intraday if conf["include_intraday_learning"] else 0)
    direction = "later" if days > 0 else "earlier"
    if not askUser(
        f"Move {counted:,} scheduled cards {abs(days)} day"
        f"{'s' if abs(days) != 1 else ''} {direction}?\n\n"
        "New and suspended cards are left alone. Nothing is marked late and no "
        "interval changes — the whole schedule just slides.\n\n"
        f"A backup is taken first, and running this again with {-days:+d} "
        "puts it back.",
        title=ADDON_NAME,
    ):
        return

    QueryOp(
        parent=mw,
        op=lambda col: take_day_off(col, days, conf),
        success=lambda result: on_done(result, days),
    ).with_progress("Taking a day off…").run_in_background()


action = QAction(f"{ADDON_NAME}…", mw)
qconnect(action.triggered, run)
mw.form.menuTools.addAction(action)
