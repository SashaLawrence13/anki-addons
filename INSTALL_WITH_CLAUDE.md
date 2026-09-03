# Install these Anki add-ons — instructions for an AI assistant

**If you're a person reading this:** download this file and drag it into Claude
(or any coding assistant that can run commands on your computer), then say
*"install these Anki add-ons for me."* You don't need a GitHub account, you
don't need to know what git is, and you don't need to touch a terminal — the
assistant does all of it. Everything below this line is written for the
assistant.

---

## Assistant: read this before doing anything

You are installing add-ons from `https://github.com/SashaLawrence13/anki-addons`
onto this person's computer.

Ground rules:

1. **Assume they have never used GitHub or git.** Never tell them to "just clone
   the repo" or ask them to make an account. Phase 3 has a no-git path — use it
   whenever git isn't already installed. Do not install git for them.
2. **Anki must be closed before you copy anything.** Anki rewrites add-on state
   when it quits and will overwrite what you just installed. Check, and ask them
   to quit it if it's open.
3. **Don't install all nine by default.** Ask first (Phase 1). One of them is a
   debugging tool nobody should install casually, and two need setup or specific
   decks to do anything at all.
4. **Verify before you declare success** (Phase 5 and 6). A broken add-on looks
   exactly like a working one until Anki is restarted.
5. Tell them what you're doing as you go, in plain language.

## Phase 0 — the catalogue

| Folder | Name | What it does | Needs |
|---|---|---|---|
| `day_off` | Take a Day Off | Slides your whole review schedule forward N days so time off doesn't create a catch-up pile | — |
| `deadline_spread` | Spread to a Deadline | Fans an existing backlog evenly across the days before a date, so it's cleared by then | — |
| `study_companion` | Study Companion | Toolbar readout of real study time, XP, streak, finish-time estimate; auto-syncs when idle | — |
| `auto_good` | Auto-Answer Good | Bulk-answers "Good" through the real scheduler, to dig out of a hole | — |
| `suspend_new_learn` | Suspend New & Learning | Suspends a deck's new and learning cards in one pass | Qt6 |
| `one_key_sync` | One-Key Sync | Sync on a single keypress | — |
| `topic_stats` | Topic Stats | Best/worst topics table on the deck screen | Tag hierarchy; **needs config** unless they use AnKing Step 1/2 v12 |
| `card_chat` | Card Chat (Claude) | A Claude panel that knows the card you're on: hints, mnemonics, quizzes, vignettes | **Claude Code CLI** |
| `progress_debug` | Progress Debug | Diagnostic only — logs a stack trace every time Anki shows a progress dialog | **Don't install** unless debugging |

## Phase 1 — ask which ones they want

Show them the table above in your own words and let them choose. Guidance:

- **Good default set for most people:** `day_off`, `deadline_spread`,
  `study_companion`, `one_key_sync`.
- **`card_chat`** only if they have (or will install) the Claude Code CLI, and
  only after they've read the privacy note in Phase 7. It sends card contents
  off-device.
- **`topic_stats`** does nothing visible unless its `tag_prefixes` setting
  matches their tag scheme. Only suggest it if they use AnKing decks or are
  willing to configure it.
- **`auto_good`** fabricates review history. Fine as a rescue tool, bad as a
  habit. Say so.
- **`progress_debug`** — actively talk them out of this one unless they are
  chasing a specific bug. It writes an unbounded log file forever.

## Phase 2 — check Anki, and close it

Find out which Anki they have (*Anki → About*, or the app version). These need
**Anki 2.1.50 or newer**; they were built against 25.07. `suspend_new_learn`
additionally requires a Qt6 build (any recent Anki is Qt6).

Confirm Anki is not running:

```bash
pgrep -x Anki && echo "RUNNING — ask them to quit Anki" || echo "not running"
```

Windows: check Task Manager for `anki.exe`, or just ask them.

The add-ons folder:

| OS | Path |
|---|---|
| macOS | `~/Library/Application Support/Anki2/addons21` |
| Windows | `%APPDATA%\Anki2\addons21` |
| Linux | `~/.local/share/Anki2/addons21` |

If that folder doesn't exist, Anki has probably never been run on this machine.
Have them open Anki once, then quit it, then continue.

## Phase 3 — get the files

**Route A — git is already installed** (check with `git --version`):

```bash
cd /tmp
git clone https://github.com/SashaLawrence13/anki-addons.git
```

**Route B — no git.** This is the normal case for someone who has never used
GitHub. Download the zip directly; no account, no git, no signup:

macOS / Linux:

```bash
cd /tmp
curl -L -o anki-addons.zip https://github.com/SashaLawrence13/anki-addons/archive/refs/heads/main.zip
unzip -q anki-addons.zip     # creates anki-addons-main/
```

Windows PowerShell:

```powershell
cd $env:TEMP
Invoke-WebRequest -Uri "https://github.com/SashaLawrence13/anki-addons/archive/refs/heads/main.zip" -OutFile "anki-addons.zip"
Expand-Archive -Path "anki-addons.zip" -DestinationPath . -Force
```

Note the folder is `anki-addons-main` on Route B and `anki-addons` on Route A.
Use whichever you actually created in the next phase.

## Phase 4 — install the chosen add-ons

Copy each chosen folder into `addons21`, **keeping the folder name exactly**.
The folder name is the add-on's identity; renaming it breaks its settings.

macOS example, installing three:

```bash
DEST="$HOME/Library/Application Support/Anki2/addons21"
SRC="/tmp/anki-addons-main"        # or /tmp/anki-addons via Route A
for a in day_off deadline_spread study_companion; do
  cp -r "$SRC/$a" "$DEST/$a"
done
```

Windows PowerShell:

```powershell
$dest = "$env:APPDATA\Anki2\addons21"
$src  = "$env:TEMP\anki-addons-main"
foreach ($a in @("day_off","deadline_spread","study_companion")) {
  Copy-Item -Recurse -Force "$src\$a" "$dest\$a"
}
```

If a folder already exists there, they already have that add-on — ask before
overwriting, since it would discard their settings.

## Phase 5 — verify the files before starting Anki

Each installed folder should contain `__init__.py` and `manifest.json` (most
also have `config.json` and `config.md`). Check the code parses:

```bash
python3 -m py_compile "$DEST/day_off/__init__.py" && echo OK
```

A `SyntaxError` here means the download was truncated — redo Phase 3. If
`python3` isn't available, skip this check; it's a nicety, not a requirement
(Anki ships its own Python).

Clean up the temporary download afterwards.

## Phase 6 — start Anki and confirm each one actually loaded

Have them open Anki. First check *Tools → Add-ons* — every add-on they chose
should be listed **by name**, not by folder name, with no error dialog on
startup. Then confirm each one individually:

| Add-on | Where it shows up |
|---|---|
| Take a Day Off | Tools → Take a Day Off… |
| Spread to a Deadline | Tools → Spread to a Deadline… |
| Auto-Answer Good | Tools → Auto-Answer "Good"… |
| Suspend New & Learning | Tools → Suspend New & Learning… |
| Study Companion | A live stats item in the top toolbar |
| Topic Stats | A "Topic performance" table on the deck screen |
| One-Key Sync | Ctrl+S starts a sync |
| Card Chat | A docked "Claude" panel; Ctrl+Shift+C toggles it |
| Progress Debug | Nothing visible — it only writes a log |

If an add-on shows as a **number** instead of its name, it was installed from
AnkiWeb rather than from here. If it shows as its folder name, its
`manifest.json` didn't copy — redo Phase 4 for that one.

If Anki shows an error on startup, open *Tools → Add-ons*, select the add-on,
and read the error. Report it to them verbatim rather than guessing.

## Phase 7 — configure the ones that need it

Settings live at *Tools → Add-ons → (select it) → Config*.

**Card Chat** needs the Claude Code CLI installed and logged in — it shells out
to a `claude` binary and has no API key of its own. It only looks in five
specific locations and **does not search PATH**, so if their binary lives
elsewhere they must set `claude_path` to the full path. Full walkthrough:
`card_chat/INSTALL_WITH_CLAUDE.md` in the same repository — read it before
installing that one.

> Tell them plainly: Card Chat sends the full contents of the card being
> studied, and excerpts of recently-failed cards, to Anthropic via the CLI.
> Fine for public decks; their call if their cards contain personal or patient
> information.

**Topic Stats** shows nothing until `tag_prefixes` matches their tags. Set it to
`[]` to rank raw leaf tags, or give it their own hierarchy. It also stays hidden
until at least two topics have enough reviews.

**Study Companion** syncs automatically after idle. If that's unwanted, raise
`auto_sync_idle_seconds` a long way.

**One-Key Sync** defaults to Ctrl+S. Warn them off single-key bindings like
`0` — those collide with the reviewer's answer buttons.

## Uninstalling

*Tools → Add-ons → select → Delete*, or quit Anki and delete the folder from
`addons21`. Nothing is left behind outside each add-on's own folder.

## If something goes wrong

- **Add-on missing after restart** — wrong folder (must be `addons21`, not
  `addons`), or the folder was renamed, or Anki was open during the copy.
- **"Anki cannot start because an add-on is broken"** — hold **Shift** while
  launching Anki to start with add-ons disabled, then delete the offending
  folder.
- **Older Anki (below 2.1.50)** — these use modern scheduler APIs and will not
  work. Updating Anki is the fix.

Don't invent fixes beyond this. If the error isn't covered here, show them the
exact message and point them at the repository's issues page.
