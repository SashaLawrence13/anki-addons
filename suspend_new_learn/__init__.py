"""
Suspend New & Learning
----------------------
Adds a Tools menu item that suspends every new and learning card
in a deck you pick, with an optional tag to exclude.

Tested against Anki 23.10+ (Qt6).
"""

from aqt import mw
from aqt.qt import QAction, QInputDialog, QLineEdit
from aqt.utils import showInfo, askUser


def _deck_names():
    return sorted(d.name for d in mw.col.decks.all_names_and_ids())


def suspend_new_and_learning():
    decks = _deck_names()
    if not decks:
        showInfo("No decks found.")
        return

    deck, ok = QInputDialog.getItem(
        mw, "Suspend New & Learning", "Deck:", decks, 0, False
    )
    if not ok:
        return

    exclude, ok = QInputDialog.getText(
        mw,
        "Exclude tag (optional)",
        "Skip cards with this tag.\nWildcards allowed, e.g. *Bootcamp*\nLeave blank to skip nothing.",
        QLineEdit.EchoMode.Normal,
        "",
    )
    if not ok:
        return

    query = f'deck:"{deck}" (is:new OR is:learn) -is:suspended'
    if exclude.strip():
        query += f' -tag:{exclude.strip()}'

    ids = mw.col.find_cards(query)
    if not ids:
        showInfo(f"Nothing to suspend.\n\nSearch used:\n{query}")
        return

    if not askUser(
        f"Suspend {len(ids)} cards in '{deck}'?\n\n"
        f"Search used:\n{query}\n\n"
        "This is reversible — select the cards in Browse and press Ctrl/Cmd+J."
    ):
        return

    mw.col.sched.suspend_cards(ids)
    mw.reset()
    showInfo(f"Suspended {len(ids)} cards.")


action = QAction("Suspend New && Learning...", mw)
action.triggered.connect(suspend_new_and_learning)
mw.form.menuTools.addAction(action)
