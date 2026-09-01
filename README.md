# Anki add-ons

A handful of small Anki add-ons written for a medical-school-scale collection
(tens of thousands of cards, AnKing decks, FSRS). They're personal tools, shared
in case they're useful — no AnkiWeb listing, no support promises.

Built and used against **Anki 25.07** on macOS with Qt6.

| Add-on | What it's for |
|---|---|
| [Card Chat](#card-chat) | Ask Claude about the card you're looking at, without leaving Anki |
| [Study Companion](#study-companion) | Real study time, XP, streaks and a finish-time estimate in the toolbar |
| [Auto-Answer Good](#auto-answer-good) | Bulk-answer "Good" through the real scheduler |
| [Topic Stats](#topic-stats) | Your strongest and weakest topics on the deck screen |
| [Suspend New & Learning](#suspend-new--learning) | Suspend a deck's new and learning cards in one pass |
| [One-Key Sync](#one-key-sync) | Sync on a single keypress |
| [Progress Debug](#progress-debug) | A throwaway diagnostic — read the warning before installing |

Also see **[Take a Day Off](https://github.com/SashaLawrence13/anki-day-off)**, in
its own repository: it slides your entire review schedule forward so time away
doesn't create a catch-up pile.

## Installing any of these

Close Anki, copy the add-on's folder into your add-ons directory, reopen Anki.
Keep the folder name exactly as it appears here.

| OS | Add-ons folder |
|---|---|
| macOS | `~/Library/Application Support/Anki2/addons21` |
| Windows | `%APPDATA%\Anki2\addons21` |
| Linux | `~/.local/share/Anki2/addons21` |

```bash
git clone https://github.com/SashaLawrence13/anki-addons.git
cp -r anki-addons/card_chat "$HOME/Library/Application Support/Anki2/addons21/card_chat"
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

**Full setup guide:** [`card_chat/INSTALL_WITH_CLAUDE.md`](card_chat/INSTALL_WITH_CLAUDE.md)
is written to be handed to Claude. Download it, give it to your assistant, and
say "follow this file to install Card Chat for me."

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
