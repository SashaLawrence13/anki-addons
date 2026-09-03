# Anki add-ons — a guide for AI assistants

**If you're a person reading this:** save this file, hand it to an AI assistant
(Claude, ChatGPT, Gemini, Copilot, Cursor — any of them), and say *"install
these Anki add-ons for me."* You don't need a GitHub account, you don't need to
know what git is, and if your assistant can't run commands on your computer it
will walk you through it by hand instead. Everything below is written for the
assistant.

Repository: `https://github.com/SashaLawrence13/anki-addons`

---

## Assistant: start here

Your job is to get some or all of these Anki add-ons onto this person's
computer, and to help them understand what they picked.

**First, work out which kind of assistant you are**, because the route differs:

- **You can run shell commands** (Claude Code, Cursor, a terminal-connected
  agent) → use **Route A** in Phase 3. Do the work yourself.
- **You can't run commands** (ChatGPT or Gemini in a browser, most chat-only
  assistants) → use **Route B** in Phase 3. Read the steps out one at a time,
  wait for them to confirm each, and never assume a step worked.

Ground rules either way:

1. **Assume they have never used GitHub.** Never say "just clone the repo."
   Never ask them to make an account or install git. Route B needs neither.
2. **Anki must be fully quit before any file is copied.** Anki rewrites add-on
   state when it exits and will silently overwrite what you just installed.
3. **Don't install all twelve.** Ask first (Phase 1). One is a debugging tool
   nobody should install casually; three need extra setup to do anything.
4. **Verify before declaring success** (Phase 5). A broken add-on is
   indistinguishable from a working one until Anki restarts.
5. Explain what you're doing in plain language. They are studying medicine, not
   software.

## Phase 0 — what's in the repository

| Folder | Name | What it does | Needs |
|---|---|---|---|
| `day_off` | Take a Day Off | Slides the whole review schedule forward N days, so time off doesn't create a catch-up pile | — |
| `deadline_spread` | Spread to a Deadline | Fans an existing backlog evenly across the days before a date | — |
| `exam_focus` | Exam Focus | Keeps the subjects your exam covers due and pushes every other subject back | Tags |
| `study_companion` | Study Companion | Toolbar readout of real study time, XP, streak, finish estimate; auto-syncs when idle | — |
| `blur_toggle` | Image Blur Control | Unblurs images that a shared deck ships blurred, without editing note types | — |
| `auto_good` | Auto-Answer Good | Bulk-answers "Good" through the real scheduler, to dig out of a hole | — |
| `suspend_new_learn` | Suspend New & Learning | Suspends a deck's new and learning cards in one pass | Qt6 |
| `one_key_sync` | One-Key Sync | Sync on a single keypress | — |
| `topic_stats` | Topic Stats | Best/worst topics table on the deck screen | Tags; **needs config** off AnKing |
| `nbme_drill` | Weak Topic Drill | Generates NBME-style questions on whatever you're failing today, and quizzes you | **Claude Code CLI** |
| `card_chat` | Card Chat (Claude) | A Claude panel that knows the card you're on: hints, mnemonics, quizzes, vignettes | **Claude Code CLI** |
| `progress_debug` | Progress Debug | Diagnostic only — logs a stack trace on every Anki progress dialog | **Don't install** |

Repository layout, so you can find things:

```
anki-addons/
├── README.md              human-readable descriptions of every add-on
├── INSTALL_WITH_AI.md     this file
├── LICENSE                MIT
├── build.sh               packages an add-on as .ankiaddon (see Phase 3B)
└── <addon folder>/
    ├── __init__.py        the add-on itself; one file each
    ├── manifest.json      the display name Anki shows
    ├── config.json        default settings
    ├── config.md          what each setting means — read this to answer
    │                      "what does X do?" questions
    └── README.md          only day_off has one, with extra detail
```

Settings are edited in Anki at *Tools → Add-ons → select → Config*, never by
hand-editing `config.json` after installation. A `meta.json` appears in each
folder once Anki loads it; that is the user's own settings and is not in the
repository by design.

## Phase 1 — ask which ones they want

Describe the table above in your own words and let them choose. Guidance:

- **Good default set:** `day_off`, `deadline_spread`, `study_companion`,
  `one_key_sync`.
- **`blur_toggle`** if they use AnKing or any deck that ships blurred images.
- **`exam_focus`** for anyone with subject-tagged decks and real exams.
- **`card_chat` and `nbme_drill`** need the Claude Code CLI. Only suggest them
  if the person already uses Claude Code or is happy to install it. Mention the
  privacy note in Phase 6 *before* they choose, not after.
- **`topic_stats`** shows nothing unless its `tag_prefixes` matches their tags.
  Only worth it for AnKing users or people willing to configure it.
- **`auto_good`** fabricates review history. A rescue tool, not a habit.
- **`progress_debug`** — talk them out of it unless they're chasing a specific
  bug. It writes an unbounded log file forever.

## Phase 2 — check Anki, and quit it

These need **Anki 2.1.50 or newer** (built against 25.07). Version is in
*Anki → About*.

The add-ons folder:

| OS | Path |
|---|---|
| macOS | `~/Library/Application Support/Anki2/addons21` |
| Windows | `%APPDATA%\Anki2\addons21` |
| Linux | `~/.local/share/Anki2/addons21` |

**The reliable way to find it on any OS, with no typing:** open Anki →
*Tools → Add-ons* → click **View Files**. That opens the add-ons folder in
Finder or Explorer. Then quit Anki, leaving the window open. Use this for
Route B.

Confirm Anki is closed (`pgrep -x Anki` on macOS, Task Manager on Windows, or
just ask).

## Phase 3 — get the files, then install

### Route A — you can run commands

```bash
cd /tmp
curl -L -o anki-addons.zip https://github.com/SashaLawrence13/anki-addons/archive/refs/heads/main.zip
unzip -q anki-addons.zip      # creates anki-addons-main/
```

Windows PowerShell:

```powershell
cd $env:TEMP
Invoke-WebRequest -Uri "https://github.com/SashaLawrence13/anki-addons/archive/refs/heads/main.zip" -OutFile "anki-addons.zip"
Expand-Archive -Path "anki-addons.zip" -DestinationPath . -Force
```

Then copy each chosen folder in, **keeping the folder name exactly** — the name
is the add-on's identity, and renaming it orphans its settings:

```bash
DEST="$HOME/Library/Application Support/Anki2/addons21"
SRC="/tmp/anki-addons-main"
for a in day_off deadline_spread study_companion; do
  cp -r "$SRC/$a" "$DEST/$a"
done
```

```powershell
$dest = "$env:APPDATA\Anki2\addons21"
$src  = "$env:TEMP\anki-addons-main"
foreach ($a in @("day_off","deadline_spread","study_companion")) {
  Copy-Item -Recurse -Force "$src\$a" "$dest\$a"
}
```

If a folder is already there, they already have that add-on — ask before
overwriting, since it discards their settings.

### Route B — you cannot run commands

Walk them through this, one step at a time, confirming each:

1. Open this link in a browser — it downloads a zip immediately, no account, no
   sign-in:
   `https://github.com/SashaLawrence13/anki-addons/archive/refs/heads/main.zip`
2. Find the download and unzip it (double-click on macOS; right-click →
   *Extract All* on Windows). They get a folder called **anki-addons-main**.
3. In Anki: *Tools → Add-ons → View Files*. A folder called **addons21** opens.
4. **Quit Anki completely**, leaving that folder window open.
5. From **anki-addons-main**, drag the folders they chose — e.g. `day_off` —
   into **addons21**. Folders only, not the loose files like `README.md`.
6. Reopen Anki.

Tell them the folder names must not be renamed, and that they should copy the
folder itself rather than its contents.

## Phase 4 — verify the files (Route A only)

Each installed folder needs `__init__.py` and `manifest.json`. Check the code
parses:

```bash
python3 -m py_compile "$DEST/day_off/__init__.py" && echo OK
```

A `SyntaxError` means a truncated download — redo Phase 3. If `python3` isn't
present, skip it; Anki ships its own Python. Delete the temporary download when
done.

## Phase 5 — restart Anki and confirm each one loaded

*Tools → Add-ons* should list each chosen add-on **by name**, with no startup
error. Then check them individually:

| Add-on | Where it appears |
|---|---|
| Take a Day Off | Tools → Take a Day Off… |
| Spread to a Deadline | Tools → Spread to a Deadline… |
| Auto-Answer Good | Tools → Auto-Answer "Good"… |
| Suspend New & Learning | Tools → Suspend New & Learning… |
| Image Blur Control | Tools → Image Blur Control… |
| Exam Focus | Tools → Exam Focus… |
| Weak Topic Drill | Tools → Drill My Weak Topics… |
| Study Companion | A live stats item in the top toolbar |
| Topic Stats | A "Topic performance" table on the deck screen |
| One-Key Sync | Ctrl+S starts a sync |
| Card Chat | A docked "Claude" panel; Ctrl+Shift+C toggles it |
| Progress Debug | Nothing visible — it only writes a log |

Two failure signatures worth knowing:

- Listed by **folder name** instead of its proper name → `manifest.json` didn't
  copy. Redo Phase 3 for that add-on.
- Listed as a **number** → that one came from AnkiWeb, not from here.

If Anki shows an error on startup, open *Tools → Add-ons*, select the add-on,
and read the message. Report it to them verbatim rather than guessing.

## Phase 6 — configure what needs it

**Card Chat and Weak Topic Drill** both shell out to a `claude` binary and have
no API key of their own. The person needs Claude Code installed
(`npm install -g @anthropic-ai/claude-code`, or Anthropic's native installer)
and needs to have run `claude` once and done `/login`. Neither add-on searches
`PATH` — they check five fixed locations — so if the binary lives elsewhere, set
`claude_path` to its full path in the config. Card Chat has a much longer
walkthrough at `card_chat/INSTALL_WITH_CLAUDE.md` in this repository.

> Say this plainly before they install either: **Card Chat** sends the full
> contents of the card being studied, and excerpts of recently-failed cards, to
> Anthropic through the CLI. **Weak Topic Drill** sends only topic names and
> accuracy percentages, not cards. Fine for public decks; their call if their
> cards hold personal or patient information.

**Topic Stats, Weak Topic Drill and Exam Focus** all read subjects from a tag
hierarchy and ship defaults aimed at AnKing Step 1/Step 2 v12. For any other tagging scheme,
set `tag_prefixes` to `[]` to rank raw tags, or supply their own prefixes.

**Image Blur Control** defaults to `off`, meaning blurred images are simply
shown. `hover` is the better choice for studying in public.

**Study Companion** auto-syncs after idle; raise `auto_sync_idle_seconds` to
stop that. **One-Key Sync** defaults to Ctrl+S — warn against single-key
bindings like `0`, which collide with the reviewer's answer buttons.

## Answering questions about an add-on

Read that add-on's `config.md` first — every setting is documented there, with
the reasoning. `README.md` at the repository root has a prose description of
each one. The code is a single `__init__.py` per add-on and is meant to be
readable; if they ask what something really does, read it rather than guessing.

## Uninstalling

*Tools → Add-ons → select → Delete*, or quit Anki and delete the folder from
`addons21`. Nothing is stored outside each add-on's own folder.

## If it goes wrong

- **Add-on missing after restart** — wrong folder (`addons21`, not `addons`),
  folder renamed, or Anki was open during the copy.
- **"Anki cannot start because an add-on is broken"** — hold **Shift** while
  launching Anki to start with add-ons disabled, then delete the offending
  folder.
- **Anki older than 2.1.50** — these use modern scheduler APIs and won't load.
  Updating Anki is the fix.

Don't invent fixes beyond these. If the error isn't covered, show them the exact
message and point them at the repository's issues page.
