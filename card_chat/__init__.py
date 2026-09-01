import json
import os
import re
import subprocess
import time

from aqt import mw, gui_hooks
from aqt.qt import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextBrowser,
    QTextEdit,
    QPushButton,
    QLabel,
    QShortcut,
    QKeySequence,
    QDialog,
    QComboBox,
    Qt,
)
from aqt.utils import tooltip

DEFAULTS = {
    # toggles / focuses the panel
    "shortcut": "Ctrl+Shift+C",
    "mnemonic_shortcut": "Ctrl+Shift+M",
    "quiz_shortcut": "Ctrl+Shift+Q",
    "vignette_shortcut": "Ctrl+Shift+V",
    "teachback_shortcut": "Ctrl+Shift+T",
    "boss_shortcut": "Ctrl+Shift+B",
    # leave empty to auto-detect; set to full path if claude lives elsewhere
    "claude_path": "",
    # leave empty for the CLI's default model
    "model": "",
    "timeout_seconds": 120,
    # open the panel automatically when Anki starts
    "open_on_start": True,
}

CLAUDE_CANDIDATES = [
    os.path.expanduser("~/.local/bin/claude"),
    os.path.expanduser("~/.claude/local/claude"),
    "/opt/homebrew/bin/claude",
    "/usr/local/bin/claude",
    os.path.expanduser("~/.npm-global/bin/claude"),
]


def get_config():
    cfg = dict(DEFAULTS)
    stored = mw.addonManager.getConfig(__name__) or {}
    cfg.update({k: v for k, v in stored.items() if v not in (None, "")})
    return cfg


def find_claude(cfg):
    if cfg.get("claude_path"):
        return cfg["claude_path"]
    for p in CLAUDE_CANDIDATES:
        if os.path.exists(p):
            return p
    return None


def run_claude(cfg, prompt):
    claude = find_claude(cfg)
    if not claude:
        return (
            "Could not find the claude CLI — set claude_path in the addon "
            "config."
        )
    cmd = [claude, "-p", prompt]
    if cfg.get("model"):
        cmd += ["--model", cfg["model"]]
    env = dict(os.environ)
    env["PATH"] = (
        os.path.expanduser("~/.local/bin")
        + ":" + env.get("PATH", "")
        + ":/usr/local/bin:/opt/homebrew/bin"
    )
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=cfg.get("timeout_seconds", 120),
        env=env,
        cwd=os.path.expanduser("~"),
    )
    out = result.stdout.strip()
    if "Not logged in" in out or "Not logged in" in result.stderr:
        return (
            "The claude CLI isn't logged in yet. Open Terminal, run "
            "'claude', then type /login and sign in. Only needed once."
        )
    if not out and result.stderr.strip():
        return "Error from claude: %s" % result.stderr.strip()[:500]
    return out or "(empty response)"


def strip_html(text):
    text = re.sub(r"\[sound:[^\]]+\]", "", text)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.S)
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.S)
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"</div>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def note_context(note):
    fields = []
    for name, value in note.items():
        value = strip_html(value)
        if value:
            fields.append("%s: %s" % (name, value))
    return "\n".join(fields)


def answer_shown():
    try:
        return mw.reviewer.state == "answer"
    except Exception:
        return False


def current_card_context():
    """Returns (context, label, revealed). On the question side, only the
    rendered question is included so the answer can't leak into the chat."""
    if mw.state != "review" or mw.reviewer.card is None:
        return None, None, False
    card = mw.reviewer.card
    label = strip_html(card.question())[:60]
    return note_context(card.note()), label, answer_shown()


class ChatInput(QTextEdit):
    """Multi-line input: Enter sends (and never reaches the reviewer),
    Shift+Enter inserts a newline."""

    def __init__(self, on_send):
        super().__init__()
        self.on_send = on_send
        self.setPlaceholderText("Ask about this card…  (Enter to send)")
        self.setFixedHeight(70)
        self.setStyleSheet("QTextEdit { font-size: 14px; padding: 6px; }")

    def keyPressEvent(self, event):
        try:
            enter_keys = (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            shift = Qt.KeyboardModifier.ShiftModifier
        except AttributeError:
            enter_keys = (Qt.Key_Return, Qt.Key_Enter)
            shift = Qt.ShiftModifier
        if event.key() in enter_keys and not (event.modifiers() & shift):
            event.accept()
            self.on_send()
            return
        super().keyPressEvent(event)


class ChatPanel(QDockWidget):
    def __init__(self):
        super().__init__("Claude", mw)
        self.cfg = get_config()
        self.history = []
        self.busy = False
        self.setObjectName("card_chat_dock")

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(4, 4, 4, 4)

        self.card_label = QLabel("No card open")
        self.card_label.setWordWrap(True)
        self.card_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.card_label)

        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(True)
        layout.addWidget(self.view)

        self.input = ChatInput(self.send)
        layout.addWidget(self.input)

        def make_btn(label, fn, height=32):
            b = QPushButton(label)
            b.setMinimumHeight(height)
            b.clicked.connect(fn)
            return b

        row = QHBoxLayout()
        self.btn = make_btn("Send", self.send)
        row.addWidget(self.btn, 2)
        row.addWidget(make_btn("Clear", self.clear_chat), 1)
        layout.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(make_btn("\U0001f9e0 Mnemonic", lambda: ask_mnemonic()))
        row2.addWidget(make_btn("❓ Quiz me", lambda: ask_quiz()))
        row2.addWidget(make_btn("\U0001fa7a Vignette", lambda: ask_vignette()))
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(make_btn("\U0001f393 Teach it", lambda: ask_teachback()))
        row3.addWidget(make_btn("⚔️ Boss battle", lambda: boss_battle()))
        row3.addWidget(
            make_btn("\U0001f500 Confusions", lambda: find_confusions())
        )
        layout.addLayout(row3)

        save = make_btn(
            "\U0001f4be Save last answer to card", self.save_last, height=28
        )
        layout.addWidget(save)

        self.setWidget(body)
        try:
            area = Qt.DockWidgetArea.RightDockWidgetArea
        except AttributeError:
            area = Qt.RightDockWidgetArea
        mw.addDockWidget(area, self)

    def update_card_label(self):
        ctx, label, revealed = current_card_context()
        if ctx is None:
            self.card_label.setText("No card open — context off")
        elif revealed:
            self.card_label.setText("Card: %s…" % label)
        else:
            self.card_label.setText("Card: %s… (answer hidden)" % label)

    def clear_chat(self):
        self.history = []
        self.view.clear()

    def send(self):
        q = self.input.toPlainText().strip()
        if not q:
            return
        self.input.clear()
        self.send_text(q)

    def send_text(self, q, display=None, include_card=True):
        if self.busy:
            tooltip("Claude is still thinking — one moment")
            return
        self.busy = True
        self.btn.setEnabled(False)
        self.view.append("<p><b>You:</b> %s</p>" % (display or q))
        self.view.append("<p><i>thinking…</i></p>")

        prompt = self.build_prompt(q, include_card=include_card)

        def work():
            return run_claude(self.cfg, prompt)

        def done(fut):
            self.busy = False
            self.btn.setEnabled(True)
            try:
                answer = fut.result()
            except Exception as e:
                answer = "Error: %s" % e
            self.history.append((display or q, answer))
            del self.history[:-12]
            self.render_all()
            self.input.setFocus()

        mw.taskman.run_in_background(work, done)

    def add_exchange(self, label, answer):
        """Insert a completed exchange (used by auto-explain)."""
        self.history.append((label, answer))
        del self.history[:-12]
        self.render_all()

    def render_all(self):
        self.view.clear()
        for q, a in self.history:
            self.view.append("<p><b>You:</b> %s</p>" % q)
            self.view.append(
                "<p><b>Claude:</b><br>%s</p><hr>" % a.replace("\n", "<br>")
            )
        sb = self.view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def build_prompt(self, question, include_card=True):
        ctx, _, revealed = current_card_context()
        if not include_card:
            ctx = None
        parts = ["You are helping a medical student studying with Anki.\n"]
        if ctx and revealed:
            parts.append(
                "They are currently looking at this flashcard:\n---\n%s\n---\n\n"
                % ctx
            )
        elif ctx:
            parts.append(
                "They are looking at the QUESTION side of this flashcard. "
                "You can see the full card below, INCLUDING the answer — "
                "but the student cannot see the answer yet:\n---\n%s\n---\n\n"
                "CRITICAL: the student has not answered yet. Do NOT reveal, "
                "state, or strongly hint at the answer (including the cloze "
                "contents or anything from the Extra field that gives it "
                "away). Use your knowledge of the answer to give smart, "
                "targeted hints and clarifications that guide them toward "
                "it. Only give the answer outright if they explicitly ask "
                "you to just tell them.\n\n" % ctx
            )
        else:
            parts.append("(No card is open right now.)\n\n")
        if self.history:
            parts.append("Conversation so far:\n")
            for q, a in self.history:
                parts.append("Student: %s\nYou: %s\n" % (q, a))
        parts.append(
            "\nStudent's question: %s\n\n"
            "Answer concisely and accurately for board-exam-level study. "
            "Plain text only, no markdown formatting." % question
        )
        return "".join(parts)

    def save_last(self):
        if not self.history:
            tooltip("Nothing to save yet")
            return
        if mw.state != "review" or mw.reviewer.card is None:
            tooltip("Open a card first")
            return
        note = mw.reviewer.card.note()
        target = None
        for cand in ("Extra", "Lecture Notes", "Additional Resources",
                     "Back Extra"):
            if cand in note:
                target = cand
                break
        if target is None:
            target = list(note.keys())[-1]
        answer = self.history[-1][1]
        note[target] += (
            "<br><br><div style='border-left:3px solid #7c4dff;"
            "padding-left:8px'><b>Claude:</b><br>%s</div>"
            % answer.replace("\n", "<br>")
        )
        mw.col.update_note(note)
        tooltip("Saved to field: %s" % target)


panel = None


def ensure_panel(focus=True):
    global panel
    if panel is None:
        panel = ChatPanel()
    if not panel.isVisible():
        panel.show()
    panel.update_card_label()
    if focus:
        panel.input.setFocus()
    return panel


def toggle_panel():
    global panel
    if panel is None or not panel.isVisible():
        ensure_panel()
    elif not panel.input.hasFocus():
        # visible but focus is elsewhere (e.g. the card) — jump into the box
        panel.input.setFocus()
    else:
        panel.hide()


# ---- mnemonic & quiz hotkeys ----

def ask_mnemonic():
    if mw.state != "review" or mw.reviewer.card is None:
        tooltip("Open a card first")
        return
    if not answer_shown():
        tooltip("Flip the card first — a mnemonic needs the answer")
        return
    p = ensure_panel(focus=False)
    p.send_text(
        "Give me a short, genuinely memorable mnemonic or a vivid, absurd "
        "visual scene (Sketchy-style) for the key fact on this card. "
        "Keep it under 80 words.",
        display="[mnemonic for this card]",
    )


def ask_quiz():
    if mw.state != "review" or mw.reviewer.card is None:
        tooltip("Open a card first")
        return
    p = ensure_panel()
    p.send_text(
        "Quiz me deeper on this card's topic: ask me ONE board-style "
        "follow-up question (next-step management, mechanism, or a classic "
        "vignette twist). Wait for my answer, then grade it and ask the "
        "next one. Start now with question 1 only.",
        display="[quiz me on this card]",
    )


def ask_vignette():
    if mw.state != "review" or mw.reviewer.card is None:
        tooltip("Open a card first")
        return
    p = ensure_panel()
    p.send_text(
        "Turn the fact this card tests into ONE full USMLE Step 2-style "
        "clinical vignette MCQ: a realistic patient stem (demographics, "
        "history, vitals, labs where relevant) and five answer choices A-E "
        "with plausible distractors. Present ONLY the question and choices, "
        "then wait for my answer. After I answer, grade me and briefly "
        "explain why each wrong choice is wrong. Do not reveal the correct "
        "answer before I answer.",
        display="[vignette from this card]",
    )


def ask_teachback():
    if mw.state != "review" or mw.reviewer.card is None:
        tooltip("Open a card first")
        return
    p = ensure_panel()
    p.send_text(
        "Feynman mode: ask me to explain this card's core concept back to "
        "you in my own words, as if teaching a junior student. After I "
        "reply, grade me STRICTLY: point out anything wrong, anything "
        "important I omitted, and any vague hand-waving where I clearly "
        "don't understand the mechanism. Then have me re-explain just the "
        "weak parts. Start now by telling me what to explain.",
        display="[teach it back]",
    )


def todays_failed_notes(limit=10):
    try:
        cutoff_ms = (mw.col.sched.day_cutoff - 86400) * 1000
        nids = mw.col.db.list(
            "select distinct n.id from revlog r "
            "join cards c on r.cid = c.id "
            "join notes n on c.nid = n.id "
            "where r.id > ? and r.ease = 1 "
            "order by r.id desc limit ?",
            cutoff_ms,
            limit,
        )
        return [mw.col.get_note(nid) for nid in nids]
    except Exception:
        return []


def boss_battle():
    notes = todays_failed_notes()
    if not notes:
        tooltip("No failed cards today — no boss to fight!")
        return
    p = ensure_panel()
    blocks = []
    for i, note in enumerate(notes):
        blocks.append("CARD %d:\n%s" % (i + 1, note_context(note)[:1200]))
    p.send_text(
        "BOSS BATTLE. Below are the %d cards I FAILED today. Quiz me on "
        "each one as a fresh board-style question (short vignette or "
        "direct question — vary it), ONE at a time. Wait for my answer, "
        "grade it, give a one-line explanation, then move to the next. "
        "Keep score. After the last card, give me my final score out of %d "
        "and a verdict: did I beat the boss? Start with question 1 now.\n\n"
        "%s" % (len(notes), len(notes), "\n\n".join(blocks)),
        display="[boss battle: today's %d failed cards]" % len(notes),
        include_card=False,
    )


def find_confusions():
    cfg = get_config()
    try:
        cutoff_ms = int((time.time() - 14 * 86400) * 1000)
        rows = mw.col.db.all(
            "select n.id, count(*) as fails from revlog r "
            "join cards c on r.cid = c.id "
            "join notes n on c.nid = n.id "
            "where r.id > ? and r.ease = 1 "
            "group by n.id having fails >= 2 "
            "order by fails desc limit 20",
            cutoff_ms,
        )
    except Exception as e:
        tooltip("Query failed: %s" % e)
        return
    if len(rows) < 4:
        tooltip("Not enough repeatedly-failed cards to analyze — nice work")
        return

    blocks = []
    for i, (nid, fails) in enumerate(rows):
        note = mw.col.get_note(nid)
        blocks.append(
            "CARD %d (failed %dx):\n%s"
            % (i + 1, fails, note_context(note)[:1000])
        )
    prompt = (
        "These are the Anki cards a medical student has repeatedly failed "
        "in the last 2 weeks. Identify which ones they are likely "
        "CONFUSING WITH EACH OTHER — lookalike drugs, similar syndromes, "
        "parallel facts (list the card numbers in each confusable "
        "group). For each group, give a compact plain-text "
        "compare-and-contrast (aligned columns) highlighting exactly the "
        "distinguishing features, plus one memory hook to keep them "
        "apart. Ignore cards that aren't confusable with anything here.\n\n"
        "%s" % "\n\n".join(blocks)
    )

    dlg = QDialog(mw)
    dlg.setWindowTitle("Claude — your confusions")
    dlg.resize(680, 560)
    lay = QVBoxLayout(dlg)
    view = QTextBrowser()
    view.setHtml(
        "<i>Analyzing your %d most-failed cards…</i>" % len(rows)
    )
    lay.addWidget(view)
    dlg.show()

    def work():
        return run_claude(cfg, prompt)

    def done(fut):
        try:
            answer = fut.result()
        except Exception as e:
            answer = "Error: %s" % e
        view.setHtml(
            "<pre style='white-space:pre-wrap;font-family:Menlo,monospace;"
            "font-size:12px'>%s</pre>" % answer
        )

    mw.taskman.run_in_background(work, done)


# ---- practice-question importer ----

class ImportDialog(QDialog):
    def __init__(self):
        super().__init__(mw)
        self.cfg = get_config()
        self.setWindowTitle("Import practice question with Claude")
        self.resize(600, 480)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            "Paste a practice-question explanation (UWorld-style). "
            "Claude will turn it into 1-3 cloze cards."
        ))
        self.text = QTextEdit()
        layout.addWidget(self.text)

        row = QHBoxLayout()
        row.addWidget(QLabel("Deck:"))
        self.deck = QComboBox()
        for d in sorted(mw.col.decks.all_names_and_ids(),
                        key=lambda x: x.name):
            self.deck.addItem(d.name, d.id)
        row.addWidget(self.deck, 1)
        layout.addLayout(row)

        self.status = QLabel("")
        layout.addWidget(self.status)

        self.go = QPushButton("Create cards")
        self.go.clicked.connect(self.run)
        layout.addWidget(self.go)

    def run(self):
        src = self.text.toPlainText().strip()
        if not src:
            return
        self.go.setEnabled(False)
        self.status.setText("Asking Claude…")
        deck_id = self.deck.currentData()

        prompt = (
            "Convert this practice-question explanation into 1-3 Anki cloze "
            "cards for a medical student. Each card should test ONE "
            "high-yield fact using {{c1::...}} cloze syntax (use c2, c3 for "
            "additional deletions on the same card only when they belong "
            "together).\n\nReturn ONLY a JSON array, no other text:\n"
            '[{"text": "cloze sentence", "extra": "1-line explanation"}]\n\n'
            "Explanation:\n---\n%s\n---" % src
        )

        def work():
            return run_claude(self.cfg, prompt)

        def done(fut):
            try:
                raw = fut.result()
            except Exception as e:
                self.status.setText("Error: %s" % e)
                self.go.setEnabled(True)
                return
            try:
                cards = self.parse(raw)
                n = self.create(cards, deck_id)
                self.status.setText("Created %d cards ✓" % n)
                self.text.clear()
                mw.reset()
            except Exception as e:
                self.status.setText("Could not parse Claude's reply: %s" % e)
            self.go.setEnabled(True)

        mw.taskman.run_in_background(work, done)

    def parse(self, raw):
        raw = re.sub(r"```(json)?", "", raw)
        start, end = raw.find("["), raw.rfind("]")
        if start == -1 or end == -1:
            raise ValueError("no JSON array found")
        cards = json.loads(raw[start:end + 1])
        good = []
        for c in cards:
            if isinstance(c, dict) and "{{c1::" in c.get("text", ""):
                good.append(c)
        if not good:
            raise ValueError("no valid cloze cards in reply")
        return good

    def create(self, cards, deck_id):
        model = mw.col.models.by_name("Cloze")
        if model is None:
            raise ValueError("no Cloze note type found")
        n = 0
        for c in cards:
            note = mw.col.new_note(model)
            note["Text"] = c["text"]
            if "Back Extra" in note:
                note["Back Extra"] = c.get("extra", "")
            note.tags.append("claude-import")
            mw.col.add_note(note, deck_id)
            n += 1
        return n


import_dialog = None


def open_importer():
    global import_dialog
    import_dialog = ImportDialog()
    import_dialog.show()


# ---- card quality checker (browser) ----

def on_browser_menu(browser, menu):
    action = menu.addAction("Check card quality with Claude")
    action.triggered.connect(lambda: check_quality(browser))


def check_quality(browser):
    try:
        nids = browser.selected_notes()
    except AttributeError:
        nids = browser.selectedNotes()
    if not nids:
        tooltip("Select some cards first")
        return
    if len(nids) > 15:
        tooltip("Checking the first 15 of %d selected" % len(nids))
        nids = nids[:15]

    cfg = get_config()
    blocks = []
    for i, nid in enumerate(nids):
        note = mw.col.get_note(nid)
        blocks.append("CARD %d:\n%s" % (i + 1, note_context(note)[:1500]))
    prompt = (
        "Review these Anki cards for a medical student. For each card flag "
        "any of: ambiguous wording, testing multiple facts at once, "
        "outdated/incorrect medicine, or a cloze that can be guessed "
        "without knowing the fact. Suggest a rewrite when flagged; say "
        "'OK' if the card is fine. Be concise.\n\n%s" % "\n\n".join(blocks)
    )

    dlg = QDialog(mw)
    dlg.setWindowTitle("Claude card quality check")
    dlg.resize(640, 520)
    lay = QVBoxLayout(dlg)
    view = QTextBrowser()
    view.setHtml("<i>Reviewing %d cards…</i>" % len(nids))
    lay.addWidget(view)
    dlg.show()

    def work():
        return run_claude(cfg, prompt)

    def done(fut):
        try:
            answer = fut.result()
        except Exception as e:
            answer = "Error: %s" % e
        view.setHtml(answer.replace("\n", "<br>"))

    mw.taskman.run_in_background(work, done)


# ---- setup ----

def on_card_shown(card):
    if panel is not None and panel.isVisible():
        panel.update_card_label()


def on_state_change(new_state, old_state):
    if panel is not None and panel.isVisible():
        panel.update_card_label()


def make_shortcut(keys, fn):
    sc = QShortcut(QKeySequence(keys), mw)
    try:
        sc.setContext(Qt.ShortcutContext.ApplicationShortcut)
    except AttributeError:
        sc.setContext(Qt.ApplicationShortcut)
    sc.activated.connect(fn)


def setup():
    cfg = get_config()
    make_shortcut(cfg["shortcut"], toggle_panel)

    gui_hooks.reviewer_did_show_question.append(on_card_shown)
    gui_hooks.reviewer_did_show_answer.append(on_card_shown)
    gui_hooks.state_did_change.append(on_state_change)
    gui_hooks.browser_will_show_context_menu.append(on_browser_menu)

    menu_action = mw.form.menuTools.addAction(
        "Claude: Import practice question…"
    )
    menu_action.triggered.connect(open_importer)

    conf_action = mw.form.menuTools.addAction("Claude: Find my confusions")
    conf_action.triggered.connect(find_confusions)

    if cfg.get("open_on_start"):
        ensure_panel(focus=False)


gui_hooks.main_window_did_init.append(setup)
