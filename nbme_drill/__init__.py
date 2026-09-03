"""Weak Topic Drill — NBME-style questions on whatever you're worst at today.

Adds Tools > Drill My Weak Topics…  It reads your review log, works out which
topics you have been failing, and asks Claude for board-style single-best-answer
vignettes on exactly those, then quizzes you on them.

Topics are grouped the same way Topic Stats groups them, so the two agree about
what "Medicine › Cardiology" means.

Nothing is written to your collection: this reads your review history and shows
questions. Requires the Claude Code CLI, the same one Card Chat uses.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass

from aqt import mw
from aqt.operations import QueryOp
from aqt.qt import *
from aqt.utils import qconnect, showInfo, showWarning

ADDON_NAME = "Weak Topic Drill"

CLAUDE_CANDIDATES = [
    os.path.expanduser("~/.local/bin/claude"),
    os.path.expanduser("~/.claude/local/claude"),
    "/opt/homebrew/bin/claude",
    "/usr/local/bin/claude",
    os.path.expanduser("~/.npm-global/bin/claude"),
]

DEFAULTS = {
    # "today" by default — the topics you struggled with in this session
    "window_days": 1,
    # a topic needs this many reviews in the window before it can be ranked
    "min_reviews": 10,
    # how many weak topics to build questions from
    "topic_count": 3,
    # how many questions to ask for
    "question_count": 5,
    # same shape as Topic Stats; [] ranks raw leaf tags
    "tag_prefixes": ["#AK_Step2_v12::#Bootcamp", "#AK_Step1_v12::#Bootcamp"],
    "group_levels": 2,
    "claude_path": "",
    "model": "",
    "timeout_seconds": 180,
}

# If today is too thin to rank anything, widen to this before giving up.
FALLBACK_DAYS = 7


def get_config() -> dict:
    conf = dict(DEFAULTS)
    user = mw.addonManager.getConfig(__name__) or {}
    conf.update({k: v for k, v in user.items() if k in DEFAULTS})
    return conf


# Finding the weak topics
######################################################################


def clean_segment(seg: str) -> str:
    seg = seg.lstrip("#").replace("_", " ")
    return re.sub(r"^\d+\s*", "", seg)


def group_key(tag: str, prefixes: list[str], levels: int) -> str | None:
    for prefix in prefixes:
        if tag == prefix or tag.startswith(prefix + "::"):
            rest = tag[len(prefix) :].lstrip(":")
            if not rest:
                return None
            segs = rest.split("::")[:levels]
            return " › ".join(clean_segment(s) for s in segs)
    return None


@dataclass
class Topic:
    name: str
    fails: int
    total: int

    @property
    def accuracy(self) -> float:
        return 100.0 * (self.total - self.fails) / self.total if self.total else 0.0


def weak_topics(conf: dict, days: int) -> list[Topic]:
    """Topics ranked worst-first over the last `days` of reviews."""
    cutoff_ms = int((time.time() - days * 86400) * 1000)
    rows = mw.col.db.all(
        "select n.tags, sum(case when r.ease = 1 then 1 else 0 end), count(*) "
        "from revlog r "
        "join cards c on r.cid = c.id "
        "join notes n on c.nid = n.id "
        "where r.id > ? and r.type != 4 "
        "group by n.id",
        cutoff_ms,
    )

    prefixes = conf.get("tag_prefixes") or []
    levels = conf.get("group_levels", 2)
    per_group: dict[str, list[int]] = {}
    for tags_str, fails, total in rows:
        seen = set()
        for tag in tags_str.split():
            key = group_key(tag, prefixes, levels) if prefixes else tag
            # a note carrying several tags in one group counts once
            if key is None or key in seen:
                continue
            seen.add(key)
            bucket = per_group.setdefault(key, [0, 0])
            bucket[0] += fails
            bucket[1] += total

    topics = [
        Topic(name, fails, total)
        for name, (fails, total) in per_group.items()
        if total >= conf["min_reviews"] and fails
    ]
    topics.sort(key=lambda t: (t.accuracy, -t.total))
    return topics


# Asking Claude
######################################################################


def find_claude(conf: dict) -> str | None:
    if conf.get("claude_path"):
        return conf["claude_path"]
    for path in CLAUDE_CANDIDATES:
        if os.path.exists(path):
            return path
    return None


def build_prompt(topics: list[Topic], count: int) -> str:
    lines = [
        "You are writing practice questions for a medical student, in the "
        "style of an NBME/USMLE Step exam item.",
        "",
        "Their weakest topics right now, with recent accuracy:",
    ]
    for topic in topics:
        lines.append(
            f"- {topic.name}: {topic.accuracy:.0f}% correct "
            f"over {topic.total} reviews"
        )
    lines += [
        "",
        f"Write {count} single-best-answer questions spread across those "
        "topics, weighted toward the weakest.",
        "",
        "Each must be a clinical vignette in NBME style: a patient stem with "
        "the relevant history, vitals, exam and labs, then a question. Five "
        "options labelled A-E, exactly one correct, with the wrong options "
        "being plausible mistakes a student who half-knows the topic would "
        "make. Test reasoning, not recall of a single fact.",
        "",
        "Return ONLY a JSON array, no prose and no code fences. Each element:",
        '{"topic": "...", "vignette": "...", "options": ["A. ...", "B. ...", '
        '"C. ...", "D. ...", "E. ..."], "answer": "C", "explanation": "why '
        'the answer is right and why the tempting wrong ones are wrong"}',
    ]
    return "\n".join(lines)


def run_claude(conf: dict, prompt: str) -> str:
    claude = find_claude(conf)
    if not claude:
        raise RuntimeError(
            "Could not find the claude CLI.\n\nInstall Claude Code, or set "
            "claude_path in this add-on's config to the full path of the "
            "binary."
        )
    cmd = [claude, "-p", prompt]
    if conf.get("model"):
        cmd += ["--model", conf["model"]]
    env = dict(os.environ)
    env["PATH"] = (
        os.path.expanduser("~/.local/bin")
        + ":"
        + env.get("PATH", "")
        + ":/usr/local/bin:/opt/homebrew/bin"
    )
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=conf.get("timeout_seconds", 180),
        env=env,
        cwd=os.path.expanduser("~"),
    )
    out = result.stdout.strip()
    if "Not logged in" in out or "Not logged in" in result.stderr:
        raise RuntimeError(
            "The claude CLI isn't logged in yet. Open a terminal, run "
            "'claude', then type /login. Only needed once."
        )
    if not out:
        raise RuntimeError(
            "claude returned nothing.\n\n" + result.stderr.strip()[:500]
        )
    return out


def parse_questions(raw: str) -> list[dict]:
    """Pull the JSON array out of the reply, fences or stray prose included."""
    text = raw.strip()
    if "```" in text:
        text = re.sub(r"^```[a-zA-Z]*\n?|```$", "", text, flags=re.M).strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        raise ValueError("no JSON array in the reply")
    data = json.loads(text[start : end + 1])
    return [
        q
        for q in data
        if isinstance(q, dict) and q.get("vignette") and q.get("options")
    ]


# The quiz
######################################################################


class QuizDialog(QDialog):
    def __init__(self, parent, questions: list[dict], topics: list[Topic], days: int):
        super().__init__(parent)
        self.questions = questions
        self.index = 0
        self.correct = 0
        self.answered = False

        self.setWindowTitle(ADDON_NAME)
        self.resize(760, 620)
        layout = QVBoxLayout(self)

        span = "today" if days <= 1 else f"the last {days} days"
        self.header = QLabel(
            f"Weakest over {span}: "
            + ", ".join(f"{t.name} ({t.accuracy:.0f}%)" for t in topics)
        )
        self.header.setWordWrap(True)
        layout.addWidget(self.header)

        self.progress = QLabel()
        layout.addWidget(self.progress)

        self.stem = QTextBrowser()
        layout.addWidget(self.stem, 1)

        self.option_box = QVBoxLayout()
        layout.addLayout(self.option_box)
        self.option_buttons: list[QPushButton] = []

        self.feedback = QTextBrowser()
        self.feedback.setMaximumHeight(190)
        self.feedback.hide()
        layout.addWidget(self.feedback)

        row = QHBoxLayout()
        row.addStretch(1)
        self.next_button = QPushButton("Next")
        self.next_button.setEnabled(False)
        qconnect(self.next_button.clicked, self.next_question)
        row.addWidget(self.next_button)
        close = QPushButton("Close")
        qconnect(close.clicked, self.reject)
        row.addWidget(close)
        layout.addLayout(row)

        self.show_question()

    def clear_options(self) -> None:
        for button in self.option_buttons:
            self.option_box.removeWidget(button)
            button.deleteLater()
        self.option_buttons = []

    def show_question(self) -> None:
        question = self.questions[self.index]
        self.answered = False
        self.feedback.hide()
        self.next_button.setEnabled(False)
        self.progress.setText(
            f"Question {self.index + 1} of {len(self.questions)}"
            f"   ·   {question.get('topic', '')}"
        )
        self.stem.setPlainText(question["vignette"])

        self.clear_options()
        for option in question["options"]:
            button = QPushButton(option)
            button.setStyleSheet("text-align: left; padding: 6px;")
            qconnect(
                button.clicked,
                lambda _=False, text=option: self.choose(text),
            )
            self.option_box.addWidget(button)
            self.option_buttons.append(button)

    def choose(self, text: str) -> None:
        if self.answered:
            return
        self.answered = True
        question = self.questions[self.index]
        # the model answers with a letter; match it against the option label
        letter = str(question.get("answer", "")).strip()[:1].upper()
        picked = text.strip()[:1].upper()
        right = picked == letter

        if right:
            self.correct += 1

        for button in self.option_buttons:
            label = button.text().strip()[:1].upper()
            if label == letter:
                button.setStyleSheet(
                    "text-align: left; padding: 6px; font-weight: bold;"
                )
            button.setEnabled(False)

        verdict = "Correct." if right else f"Not quite — the answer is {letter}."
        self.feedback.setPlainText(
            f"{verdict}\n\n{question.get('explanation', '')}"
        )
        self.feedback.show()
        self.next_button.setEnabled(True)
        if self.index == len(self.questions) - 1:
            self.next_button.setText("Finish")

    def next_question(self) -> None:
        if self.index == len(self.questions) - 1:
            showInfo(
                f"{self.correct} of {len(self.questions)} correct.",
                title=ADDON_NAME,
            )
            self.accept()
            return
        self.index += 1
        self.show_question()


# Entry point
######################################################################


def run() -> None:
    conf = get_config()

    days = conf["window_days"]
    topics = weak_topics(conf, days)
    if not topics and days < FALLBACK_DAYS:
        days = FALLBACK_DAYS
        topics = weak_topics(conf, days)

    if not topics:
        showInfo(
            "Not enough review history to find a weak topic yet.\n\n"
            "Either nothing has been failed recently, or no topic has hit "
            f"{conf['min_reviews']} reviews in the window. Lower min_reviews "
            "or raise window_days in this add-on's config.\n\n"
            "If you don't use AnKing decks, set tag_prefixes to [] so it "
            "ranks your own tags.",
            title=ADDON_NAME,
        )
        return

    chosen = topics[: conf["topic_count"]]
    prompt = build_prompt(chosen, conf["question_count"])

    def op(_col) -> list[dict]:
        return parse_questions(run_claude(conf, prompt))

    def done(questions: list[dict]) -> None:
        if not questions:
            showWarning(
                "Claude replied, but no usable questions came back. "
                "Try again — models occasionally wander off the requested "
                "format.",
                title=ADDON_NAME,
            )
            return
        QuizDialog(mw, questions, chosen, days).exec()

    def failed(exc: Exception) -> None:
        showWarning(str(exc), title=ADDON_NAME)

    QueryOp(parent=mw, op=op, success=done).failure(failed).with_progress(
        "Writing questions on your weak topics…"
    ).run_in_background()


action = QAction("Drill My Weak Topics…", mw)
qconnect(action.triggered, run)
mw.form.menuTools.addAction(action)
