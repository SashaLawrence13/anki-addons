"""Auto-Good — answer "Good" on cards in bulk.

Adds Tools > Auto-Answer "Good"…  Pick a deck and a scope, and every matching
card gets the same treatment it would get if you sat there pressing 3/spacebar:
a real revlog entry, real scheduling, FSRS/SM-2 updated normally.

A forced backup is taken before anything is answered.
"""

from __future__ import annotations

from typing import Any

from anki.collection import Collection, SearchNode
from anki.scheduler.v3 import CardAnswer
from aqt import mw
from aqt.operations import QueryOp
from aqt.qt import *
from aqt.utils import askUser, qconnect, showInfo, showWarning, tooltip

ADDON_NAME = 'Auto-Answer "Good"'

# A learning card answered Good moves to its next step, so clearing a deck that
# uses multi-step learning takes more than one sweep. Bounded so a misbehaving
# preset can't spin forever.
MAX_PASSES = 20

# How often to repaint the progress dialog, in cards.
PROGRESS_EVERY = 20

DEFAULTS = {
    "deck": "",
    "include_new": False,
    "include_learning": False,
    "limit": 0,
}


# Search building
######################################################################


def build_search(
    col: Collection,
    deck_id: int | None,
    include_new: bool,
    include_learning: bool,
) -> str:
    """Search string for the cards to answer."""
    scope = ["is:due"]
    if include_new:
        scope.append("is:new")
    if include_learning:
        # Intraday learning/relearning cards whose next step is later today.
        scope.append("is:learn")

    terms = ["(" + " OR ".join(scope) + ")", "-is:suspended", "-is:buried"]
    if deck_id is not None:
        terms.append(
            col.build_search_string(SearchNode(deck=col.decks.name(deck_id)))
        )
    return " AND ".join(terms)


# The work
######################################################################


class Result:
    def __init__(self) -> None:
        self.answered = 0
        self.failed = 0
        self.cancelled = False
        self.hit_limit = False
        self.backed_up = False


def answer_good(
    col: Collection,
    search: str,
    limit: int,
) -> Result:
    """Answer Good on everything matching `search`. Runs off the main thread."""
    result = Result()

    def progress(done: int, total: int) -> None:
        def update() -> None:
            mw.progress.update(
                label=f"Answering Good… {done} / {total}\n(press Escape to stop)",
                value=done,
                max=total,
            )

        mw.taskman.run_on_main(update)

    mw.taskman.run_on_main(
        lambda: mw.progress.update(label="Backing up collection…")
    )
    result.backed_up = col.create_backup(
        backup_folder=mw.pm.backupFolder(),
        force=True,
        wait_for_completion=True,
    )

    for _ in range(MAX_PASSES):
        card_ids = col.find_cards(search)
        if not card_ids:
            break

        answered_this_pass = 0
        total = len(card_ids)
        for i, card_id in enumerate(card_ids):
            if mw.progress.want_cancel():
                result.cancelled = True
                return result
            if limit and result.answered >= limit:
                result.hit_limit = True
                return result

            try:
                card = col.get_card(card_id)
                # Same states the reviewer would show on the answer buttons.
                states = col._backend.get_scheduling_states(card_id)
                card.start_timer()
                col.sched.answer_card(
                    col.sched.build_answer(
                        card=card, states=states, rating=CardAnswer.GOOD
                    )
                )
            except Exception:
                # A card can go missing mid-run (sync, another window, leech
                # suspension). Skip it rather than losing the whole batch.
                result.failed += 1
                continue

            result.answered += 1
            answered_this_pass += 1
            if i % PROGRESS_EVERY == 0:
                progress(i + 1, total)

        if answered_this_pass == 0:
            break

    return result


def report(result: Result) -> None:
    mw.reset()

    if not result.answered:
        tooltip("Nothing to answer.", parent=mw)
        return

    lines = [f"Answered Good on {result.answered} card(s)."]
    if result.cancelled:
        lines.append("Stopped early — cards already answered were kept.")
    if result.hit_limit:
        lines.append("Stopped at the card limit you set.")
    if result.failed:
        lines.append(f"{result.failed} card(s) were skipped due to errors.")
    if result.backed_up:
        lines.append("")
        lines.append(
            "A backup was made first. To roll this back, close the profile and "
            "use File > Switch Profile > Open Backup."
        )
    showInfo("\n".join(lines), parent=mw, title=ADDON_NAME)


# Dialog
######################################################################


class AutoGoodDialog(QDialog):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.conf: dict[str, Any] = {
            **DEFAULTS,
            **(mw.addonManager.getConfig(__name__) or {}),
        }
        self.setWindowTitle(ADDON_NAME)
        self._build()
        self._refresh_count()

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.deck_combo = QComboBox()
        self.deck_combo.addItem("Whole collection", None)
        for deck in sorted(
            mw.col.decks.all_names_and_ids(), key=lambda d: d.name.lower()
        ):
            self.deck_combo.addItem(deck.name, deck.id)
        saved = self.deck_combo.findText(self.conf["deck"])
        self.deck_combo.setCurrentIndex(saved if saved != -1 else 0)
        form.addRow("Deck:", self.deck_combo)

        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(0, 100_000)
        self.limit_spin.setSpecialValueText("No limit")
        self.limit_spin.setValue(int(self.conf["limit"]))
        form.addRow("Stop after:", self.limit_spin)

        layout.addLayout(form)

        self.new_check = QCheckBox("Also answer new (unseen) cards")
        self.new_check.setChecked(bool(self.conf["include_new"]))
        self.new_check.setToolTip(
            "Off by default. This ignores your daily new-card limit and will "
            "introduce every new card in the deck at once."
        )
        layout.addWidget(self.new_check)

        self.learning_check = QCheckBox(
            "Also answer learning cards due later today"
        )
        self.learning_check.setChecked(bool(self.conf["include_learning"]))
        self.learning_check.setToolTip(
            "Burns through remaining learning steps so the deck reads zero, "
            "instead of leaving cards to come back in 10 minutes."
        )
        layout.addWidget(self.learning_check)

        self.count_label = QLabel()
        self.count_label.setWordWrap(True)
        layout.addWidget(self.count_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Answer Good")
        qconnect(buttons.accepted, self.accept)
        qconnect(buttons.rejected, self.reject)
        layout.addWidget(buttons)

        qconnect(self.deck_combo.currentIndexChanged, self._refresh_count)
        qconnect(self.new_check.stateChanged, self._refresh_count)
        qconnect(self.learning_check.stateChanged, self._refresh_count)

    def search(self) -> str:
        return build_search(
            mw.col,
            self.deck_combo.currentData(),
            self.new_check.isChecked(),
            self.learning_check.isChecked(),
        )

    def _refresh_count(self, *_args: Any) -> None:
        try:
            count = len(mw.col.find_cards(self.search()))
        except Exception as exc:
            self.count_label.setText(f"Could not count cards: {exc}")
            return
        self.count_label.setText(
            f"<b>{count}</b> card(s) match right now."
            if count
            else "No cards match right now."
        )

    def accept(self) -> None:
        search = self.search()
        count = len(mw.col.find_cards(search))
        if not count:
            tooltip("Nothing to answer.", parent=self)
            return

        mw.addonManager.writeConfig(
            __name__,
            {
                "deck": self.deck_combo.currentText(),
                "include_new": self.new_check.isChecked(),
                "include_learning": self.learning_check.isChecked(),
                "limit": self.limit_spin.value(),
            },
        )

        limit = self.limit_spin.value()
        affected = min(count, limit) if limit else count
        if not askUser(
            f"Answer Good on {affected} card(s)?\n\n"
            "This writes real review history and changes their scheduling, "
            "the same as answering them by hand. A backup is taken first.",
            parent=self,
            defaultno=True,
            title=ADDON_NAME,
        ):
            return

        super().accept()

        QueryOp(
            parent=mw,
            op=lambda col: answer_good(col, search, limit),
            success=report,
        ).with_progress("Answering Good…").run_in_background()


def show_dialog() -> None:
    if mw.col is None:
        showWarning("Open a collection first.")
        return
    if mw.state == "review":
        showWarning(
            "Close the reviewer first — the current card is mid-answer.",
            parent=mw,
        )
        return
    AutoGoodDialog(mw).exec()


action = QAction(f"{ADDON_NAME}…", mw)
qconnect(action.triggered, show_dialog)
mw.form.menuTools.addAction(action)
