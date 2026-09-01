# Install Card Chat — instructions for an AI assistant

**How to use this file:** download it, then hand it to Claude (or another coding
assistant with file access) and say *"follow this file to install Card Chat for
me."* Everything below is addressed to the assistant.

---

## Assistant: read this first

You are installing **Card Chat**, an Anki add-on that opens a Claude
conversation about the flashcard currently on screen. Work through the phases in
order. Do not skip the verification phase — a silently broken install looks
exactly like a working one until the user is mid-study.

Tell the user what you're doing as you go, and stop and ask if anything
contradicts what this file predicts.

---

## Phase 1 — Check the prerequisites

Card Chat is a thin wrapper around the **Claude Code CLI**. It shells out to a
`claude` binary; it does not use an API key of its own.

**1a. Is the `claude` CLI installed?**

```bash
which claude && claude --version
```

If that fails, the user needs Claude Code. Do not install it silently — tell
them what it is and let them decide. The usual route is:

```bash
npm install -g @anthropic-ai/claude-code
```

which requires Node.js. Anthropic's native installer also works.

**Important:** the add-on does **not** search `PATH`. It only checks these five
locations, in order:

1. `~/.local/bin/claude`
2. `~/.claude/local/claude`
3. `/opt/homebrew/bin/claude`
4. `/usr/local/bin/claude`
5. `~/.npm-global/bin/claude`

So `which claude` succeeding is not sufficient. Compare the real path against
that list. If it lives anywhere else, note it — you will set `claude_path` in
Phase 4.

**1b. Is the CLI authenticated?** The add-on cannot log in for the user. Ask them
to run `claude` in a terminal and complete `/login` if they never have. This
needs a Claude subscription or API credit.

**1c. Which Anki?** Requires Anki 2.1.x with Qt6, and the `Cloze` note type must
exist if they want the practice-question importer. Check the version in
*Anki → About*.

## Phase 2 — Tell the user what leaves their computer

Do this before installing, not after. Card Chat sends, to Anthropic, via the
CLI:

- The **full contents of the card being studied** — every field, including the
  answer, even while the question side is showing.
- For the *Boss Battle* and *Find my confusions* features, **excerpts from up to
  20 cards the user has recently failed**, pulled from their review history.

For most people studying public decks this is unremarkable. Anyone with personal
notes, patient details, or otherwise sensitive material in their cards should
know before they install, not after. Get their acknowledgement.

## Phase 3 — Install the add-on

Locate the add-ons folder:

| OS | Path |
|---|---|
| macOS | `~/Library/Application Support/Anki2/addons21` |
| Windows | `%APPDATA%\Anki2\addons21` |
| Linux | `~/.local/share/Anki2/addons21` |

**Close Anki first.** Anki rewrites add-on state on quit and will clobber
changes made while it is running.

Copy the `card_chat` folder from this repository into `addons21`, keeping the
folder name exactly `card_chat`:

```bash
git clone https://github.com/SashaLawrence13/anki-addons.git
cp -r anki-addons/card_chat "$HOME/Library/Application Support/Anki2/addons21/card_chat"
```

Confirm `addons21/card_chat/` now contains `__init__.py`, `manifest.json`, and
`config.json`. Verify the code parses before launching Anki:

```bash
python3 -m py_compile "$HOME/Library/Application Support/Anki2/addons21/card_chat/__init__.py"
```

## Phase 4 — Configure, only if needed

Defaults are fine when the CLI sits in one of the five known paths. Otherwise
edit `card_chat/config.json` and set the full binary path:

```json
{
  "shortcut": "Ctrl+Shift+C",
  "claude_path": "/full/path/to/claude",
  "model": "",
  "timeout_seconds": 120,
  "open_on_start": true
}
```

- `claude_path` — empty means auto-detect. Set it when auto-detection can't work.
- `model` — empty uses the CLI's default. A value is passed through as `--model`.
- `timeout_seconds` — per-message ceiling. Raise it on a slow connection.
- `open_on_start` — whether the panel opens with Anki.

Do **not** put an API key here. There is no field for one and the add-on never
reads one; authentication belongs to the CLI.

## Phase 5 — Verify it actually works

Have the user start Anki and check, in order:

1. A **Claude** panel is docked in the main window (unless `open_on_start` was
   set to false).
2. <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>C</kbd> toggles and focuses it.
3. Open a card, type a question, press Enter. A real answer should come back
   within the timeout.
4. The Tools menu lists *Claude: Import practice question…* and
   *Claude: Find my confusions*.

If the panel appears but every message errors, the failure is almost always
Phase 1, not the add-on. Map the message:

| Message | Cause | Fix |
|---|---|---|
| `Could not find the claude CLI — set claude_path in the addon config.` | Binary is outside the five search paths | Set `claude_path` (Phase 4) |
| A prompt to run `claude` then `/login` | CLI installed but not authenticated | User runs `claude` and `/login` |
| `Error from claude: …` | The CLI itself failed | Run the same command in a terminal to see the real error |
| Nothing happens, then a timeout | Slow model or no network | Raise `timeout_seconds`; check connectivity |

## Phase 6 — Tell the user these two things

**The five extra shortcuts in the config do nothing.** `mnemonic_shortcut`,
`quiz_shortcut`, `vignette_shortcut`, `teachback_shortcut` and `boss_shortcut`
are declared in the code's defaults but never registered with Qt. Those features
work — as **buttons in the panel**, not as hotkeys. Don't let the user waste
time debugging a keypress that was never wired up.

**"Save last answer to card" edits the note.** It writes into the first field it
finds named `Extra`, `Lecture Notes`, `Additional Resources`, or `Back Extra` —
and if the note has none of those, it writes into **the note's last field**,
whatever that happens to be. On an unfamiliar note type, check what the last
field is before using that button.

---

## If the user wants it gone

Close Anki, delete the `card_chat` folder from `addons21`, reopen. Nothing else
is touched — the add-on stores no state outside its own folder. Any text already
saved into cards via "Save last answer" stays, since those are ordinary note
edits.
