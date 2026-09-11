# Anki add-ons

A handful of small Anki add-ons written for a medical-school-scale collection
(tens of thousands of cards, AnKing decks, FSRS). They're personal tools, shared
in case they're useful — no AnkiWeb listing, no support promises.

Built and used against **Anki 25.07** on macOS with Qt6.

## Never used GitHub? Let any AI assistant install these for you

Download **[INSTALL_WITH_AI.md](INSTALL_WITH_AI.md)**, hand it to Claude, ChatGPT,
Gemini, Copilot or Cursor, and say *"install these Anki add-ons for me."* It walks the assistant
through picking which ones you want, finding your add-ons folder on any OS,
downloading without git or a GitHub account, installing, and checking each one
actually loaded. If your assistant can't run
commands, it walks you through it by hand instead. No terminal needed, no
GitHub account, no git.

Right-click → Save As on
[this link](https://raw.githubusercontent.com/SashaLawrence13/anki-addons/main/INSTALL_WITH_AI.md),
or paste that URL into any assistant that can browse, and ask it to follow the file.

| Add-on | What it's for |
|---|---|
| [Card Chat](#card-chat) | Ask Claude about the card you're looking at, without leaving Anki |
| [Take a Day Off](#take-a-day-off) | Slide your whole schedule forward so time off costs nothing |
| [Exam Focus](#exam-focus) | Keep one subject due and push every other subject back |
| [Rebalance Subjects](#rebalance-subjects) | Thin out a unit that is burying you, across a window you choose |
| [Image Blur Control](#image-blur-control) | Unblur images a deck ships blurred, without editing note types |
| [Weak Topic Drill](#weak-topic-drill) | NBME-style questions on whatever you're failing today |
| [Spread to a Deadline](#spread-to-a-deadline) | Fan a backlog out evenly over the days before a deadline |
| [Study Companion](#study-companion) | Real study time, XP, streaks and a finish-time estimate in the toolbar |
| [Auto-Answer Good](#auto-answer-good) | Bulk-answer "Good" through the real scheduler |
| [Topic Stats](#topic-stats) | Your strongest and weakest topics on the deck screen |
| [Suspend New & Learning](#suspend-new--learning) | Suspend a deck's new and learning cards in one pass |
| [One-Key Sync](#one-key-sync) | Sync on a single keypress |
| [Progress Debug](#progress-debug) | A throwaway diagnostic — read the warning before installing |

## Installing them yourself

Close Anki first, copy the add-on's folder into your add-ons directory, then
reopen Anki. Keep the folder name exactly as it appears here.

| OS | Add-ons folder |
|---|---|
| macOS | `~/Library/Application Support/Anki2/addons21` |
| Windows | `%APPDATA%\Anki2\addons21` |
| Linux | `~/.local/share/Anki2/addons21` |

```bash
git clone https://github.com/SashaLawrence13/anki-addons.git
cp -r anki-addons/card_chat "$HOME/Library/Application Support/Anki2/addons21/card_chat"
```

Or build an installable package and double-click it:

```bash
./build.sh day_off      # one add-on, or omit the name to build them all
```

Settings live in *Tools → Add-ons → (select) → Config*.

---

## Card Chat

Docks a **Claude** panel in the Anki window that knows which card you're on. Ask
it anything about the card; it also has one-press buttons for a mnemonic, a quiz,
a clinical vignette, a teach-it-back drill, a "boss battle" built from cards
you've recently failed, and a pass that hunts for concepts you keep confusing.
There's a practice-question importer that turns a pasted question into cloze
cards, and a Browser right-click action that critiques card quality.

On the question side it sends the answer but instructs the model to withhold it
and give hints instead, so asking for help doesn't spoil the card.

**Requires the [Claude Code CLI](https://claude.com/claude-code)** — the add-on
shells out to a `claude` binary and has no API key of its own. Install it, run
`claude` once and `/login`, and the add-on finds it automatically in the usual
locations (otherwise set `claude_path`).

> **Privacy:** this add-on sends the full contents of the card you're studying —
> and, for Boss Battle and Confusions, excerpts of cards you've recently failed —
> to Anthropic through the CLI. Fine for public decks; think twice if your cards
> contain personal or patient information.

**Shortcut:** <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>C</kbd> toggles the panel.
The other five `*_shortcut` keys in the config are declared but never registered
— those features are buttons only.

**Full setup guide:** [`card_chat/INSTALL_WITH_AI.md`](card_chat/INSTALL_WITH_AI.md)
is written to be handed to Claude. Download it, give it to your assistant, and
say "follow this file to install Card Chat for me."

## Take a Day Off

Adds **Tools → Take a Day Off…**  Pick a number of days and your entire review
schedule slides forward by exactly that much — intervals, ease factors and FSRS
memory state untouched, so nothing is treated as late.

The point is that it moves *every* scheduled card, not just the ones due now.
Postponing only today's queue empties today and hands you a double pile
tomorrow; this preserves the shape of the schedule and simply starts it later.
On a 20,013-card collection, a 7-day shift:

| | today | +1 | +2 | +3 | +4 | +5 | +6 | +7 | +8 | +9 | +10 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **before** | 22 | 513 | 642 | 466 | 415 | 394 | 346 | 315 | 286 | 253 | 226 |
| **after** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 22 | 513 | 642 | 466 |

New cards are deliberately left alone — they have no due date to miss. Backs up
the collection first, lands as a single undo step, and is exactly reversible by
re-running with a negative number.

Details and caveats: [`day_off/README.md`](day_off/README.md).

## Spread to a Deadline

The opposite of Take a Day Off. Adds **Tools → Spread to a Deadline…**  Pick a
deck and a date, and everything you're already behind on is fanned out evenly
across the days between now and then — most overdue first — so the backlog is
gone before the deadline instead of sitting in one pile on today.

The part that makes it honest: cards already scheduled inside that window stay
where they are, so the confirmation quotes the **combined** daily load — the
spread backlog plus the reviews those days were always going to bring. A tool
that reported only the backlog would promise 8 cards a day and hand you 532.

If a deck is selected, it also checks the plan against that deck's reviews/day
limit and warns when the busiest days would exceed it, since Anki would
otherwise hide the overflow and you'd never see the cards you just scheduled.

Only due dates move: intervals, ease and FSRS memory state are untouched, so
nothing is rescheduled as though you'd answered it. New and suspended cards are
left alone, and cards sitting in filtered decks keep their home-deck due date in
step. Takes a backup first, and the whole redistribution is a single undo step.

## Exam Focus

Cardiology exam tomorrow? Tick **Cardiology**, and every *other* subject is
pushed back a day. Tomorrow you sit down to cardiology and nothing else, and the
rest of the collection is waiting untouched the day after.

Take a Day Off clears the day completely; this clears everything except what
you're being tested on. Tick several subjects if the exam covers several.

Subjects are read from your tag hierarchy — on a real AnKing collection that's
22 of them, Cardiology through Surgery — and grouped exactly the way Topic Stats
groups them, so a subject means the same thing across all these add-ons. Not on
AnKing? Set `tag_prefixes` to `[]` and each top-level tag becomes a subject.

Anki's deck screen adds three things together, so a clean exam day means
handling all three. Review cards move by date. Learning cards hold a timestamp
instead, so they move in seconds. New cards have no due date at all — the only
way to stop Anki offering them is to suspend them, so it does, recording exactly
which ones; **Tools → Exam Focus: Release Held Cards** puts back precisely those
and never touches cards you suspended yourself. Only new cards carrying your
subject tags are eligible, so an unrelated deck is never disturbed, and a
tickbox turns the whole behaviour off per run.

On a real collection that's the difference between 989 cards waiting tomorrow
and 107, all of them cardiology.

Only due dates move: intervals, ease and FSRS memory state are untouched. Cards
in filtered decks keep their place there and have their home-deck date moved
instead. Best run after you finish today's reviews — cards move by date, so
anything still sitting on today would land on tomorrow. Backs up first, one undo
step, and a negative number puts it back.

## Rebalance Subjects

Study a big unit in a burst and FSRS schedules it back at you in a burst. Months
later cardiology is 150 cards a day while you're trying to learn pulmonology.

**Tools → Rebalance Subjects…** Tick the subjects that are burying you —
**Select all** and **Deselect all** are there for doing the whole collection —
pick a window, and their cards move onto the quietest days inside it.

Two rules keep it honest. **No card is ever moved earlier**, because pulling
reviews forward adds work, which is the opposite of the point. And **no card is
delayed past its own interval** — a card on a three-day interval moves three
days, not thirty. Delay a card far past its interval and you aren't
rescheduling it, you're forgetting it.

On a real collection, spreading cardiology over 30 days:

| | +1 | +2 | +3 | +4 | +5 | +6 | +7 |
|---|---|---|---|---|---|---|---|
| **before** | 552 | 501 | 403 | 366 | 363 | 356 | 342 |
| **after** | 405 | 358 | 295 | 294 | 294 | 294 | 289 |

Those totals include every other subject, which stays exactly where it is — so
it's the load you'll actually meet, not just the part being moved.

Cards are placed least-flexible-first: the ones with the narrowest choice of day
go while the calendar is still empty. Ordering by due date instead lets late
cards pile against the end of the window — on a whole-collection rebalance
that's the difference between a flat 220 a day and a wall of 468 on the final
day.

Only due dates move; intervals, ease and FSRS memory state are untouched. Backs
up first, one undo step.

## Image Blur Control

Some shared decks ship images with `class="blur"` baked into the note, and the
note type's styling turns that into a permanent smear. Editing the note type
works right up until the deck syncs and overwrites it.

This overrides the styling from outside instead, so nothing in your collection
is modified and a deck update can't undo it. Four modes — **off** (just show
them), **hover** (reveal while pointing), **click** (click to reveal, click to
hide), and **keep** (leave the deck's blurring alone). Cycle them mid-review
with <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>U</kbd>, or pick one in
**Tools → Image Blur Control…**

## Weak Topic Drill

**Tools → Drill My Weak Topics…** reads your review log, works out which topics
you've actually been failing — today by default — and asks Claude for NBME-style
single-best-answer vignettes on exactly those, then quizzes you on them with
per-question explanations.

Vignettes are written to test reasoning, with distractors chosen as the mistakes
someone who half-knows the topic would make. If today's history is too thin to
rank anything it widens to a week and says so.

**Requires the [Claude Code CLI](https://claude.com/claude-code)**, the same
binary Card Chat uses. It sends topic *names* and accuracy percentages — not
your cards. Nothing is written to your collection.

## Study Companion

A toolbar readout of **real** study time — an app-wide event filter tracks actual
keyboard and mouse activity, so time only accrues while you're reviewing and not
idle, which is a very different number from Anki's card count. Adds XP, levels, a
daily streak, a progress bar with an estimated finish time, confetti when you
level up or clear the day's queue, and a recap dialog when you close Anki. Syncs
automatically once you've been idle a while.

Click the toolbar item for today's recap. Stats persist in the add-on's
`user_files/stats.json`.

Two config keys the shipped `config.json` doesn't list but the code does read:
`review_auto_sync_idle_seconds` (a floor while reviewing, so a long think on a
hard card can't trigger a sync) and `min_minutes_between_auto_syncs` (default 15,
because controller input is invisible to the idle monitor). It also writes a
`debug_log.txt` every 30 seconds — leftover instrumentation, harmless but noisy.

## Auto-Answer Good

Bulk-answers "Good" on whatever you select — a deck or the whole collection,
optionally including new and learning cards. It goes through the real scheduler
rather than editing the database, so every card gets a genuine revlog entry and
normal FSRS/SM-2 scheduling, exactly as if you'd pressed 3 by hand. Learning
cards need several passes to clear their steps, so it sweeps up to 20 times.

Forces a collection backup before it starts, and Escape stops it mid-run.

**Tools → Auto-Answer "Good"…** Obviously this fabricates review history —
it's for digging out of a hole, not for studying.

## Topic Stats

Adds a **Topic performance** table to the deck screen: your strongest and
weakest topics over a configurable window, by accuracy, with review counts.
Topics come from your tag hierarchy — it strips a prefix and groups by the first
couple of `::` segments, so `#AK_Step2_v12::#Bootcamp::Medicine::01_Cardiology`
becomes `Medicine › Cardiology`.

Defaults target the AnKing Step 1 / Step 2 v12 tag trees. **With any other
tagging scheme you must set `tag_prefixes` yourself**, or set it to `[]` to rank
raw leaf tags — otherwise nothing renders. Nothing renders below two qualifying
topics either, so give it some history first.

## Suspend New & Learning

Pick a deck, optionally give a tag to skip (wildcards allowed, e.g.
`*Bootcamp*`), and it suspends every unsuspended new and learning card in it. The
exact search string is shown in the confirmation so you can see what you're
about to do. Reversible: select the cards in the Browser and press
<kbd>Ctrl/Cmd</kbd>+<kbd>J</kbd>.

**Tools → Suspend New & Learning…**  Qt6 only — no Qt5 fallback.

## One-Key Sync

Binds a key to Anki's normal sync. Twenty-five lines. Default
<kbd>Ctrl</kbd>+<kbd>S</kbd>, changeable in the config to any key sequence —
though single-key bindings like `0` will collide with the reviewer's answer
buttons, so pick something with a modifier.

## Progress Debug

> **Not really an add-on.** It's a diagnostic that monkeypatches Anki's internal
> `ProgressManager` to log a stack trace every time a progress dialog appears —
> written to find what was flashing "Processing…" during reviews. It has no UI,
> no config, and no off switch.

Install it only if you're chasing that same bug, and delete it once you're done.
It appends to `user_files/progress_log.txt` forever without rotating; that file
reached 16 MB and 200,000 lines in ordinary use. Those logs contain absolute
file paths from your home directory, so don't paste one publicly without
skimming it first.

---

## Notes on the repo

`user_files/` and `meta.json` are gitignored on purpose. `meta.json` is
Anki-generated and holds *your* settings rather than the defaults, and
`user_files/` is where these add-ons keep real study data and logs. If you fork
this, keep both ignored.

MIT licensed. Built with [Claude Code](https://claude.com/claude-code).
