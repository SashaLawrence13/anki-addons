# Take a Day Off

An Anki add-on for taking time off without paying for it later.

Adds **Tools → Take a Day Off…**  Pick a number of days, and your entire review
schedule slides forward by exactly that much. Intervals, ease factors and FSRS
memory state are left untouched, so nothing is treated as late and no card is
punished for the days you skipped.

## The problem it solves

Most "postpone" tools move only the cards that are due right now. That empties
today and quietly hands you a double pile tomorrow, because tomorrow's own cards
are still tomorrow's.

This add-on moves *every* scheduled card. The shape of your schedule is
preserved perfectly — it just starts later.

Cards arriving each day, before and after a 7-day shift on a 20,013-card
collection:

| | today | +1 | +2 | +3 | +4 | +5 | +6 | +7 | +8 | +9 | +10 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **before** | 22 | 513 | 642 | 466 | 415 | 394 | 346 | 315 | 286 | 253 | 226 |
| **after** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 22 | 513 | 642 | 466 |

The week is empty, and day 7 picks up the exact sequence that used to start
today. No catch-up hump, no compression, same total.

## What it does and doesn't touch

- **Review and day-learning cards** move by the number of days you choose.
- **Intraday learning cards** move too, so a week away leaves nothing waiting.
  Turn this off in the config if you'd rather they greet you on your return.
- **New cards** are deliberately left alone. They have no due date to miss —
  they're governed by your daily new limit, so you simply introduce none while
  you're away and resume your normal allotment when you're back.
- **Suspended cards** are left alone. They aren't shown either way.
- **Intervals, ease and FSRS memory state are never modified.** Only dates move.

One honest caveat: your stored intervals don't change, but when you eventually
review a delayed card, FSRS sees the extra elapsed days and computes its *next*
interval from that. That's FSRS working correctly — and it's far gentler than
letting thousands of cards go genuinely overdue.

## Safety

- A forced collection backup is taken before anything changes.
- The whole sweep is one undo step, so <kbd>Ctrl/Cmd</kbd>+<kbd>Z</kbd> takes
  back every card at once.
- It's exactly reversible: run it again with a negative number to pull the
  schedule back where it was.

## Install

**From source:**

```bash
git clone https://github.com/SashaLawrence13/anki-addons.git
cp -r anki-addons/day_off "$HOME/Library/Application Support/Anki2/addons21/day_off"
```

Then restart Anki. (On Windows the add-ons folder is
`%APPDATA%\Anki2\addons21`.)

**As a package:** run `./build.sh day_off` from the repository root to produce
`day_off.ankiaddon`, then double-click it, or use
*Tools → Add-ons → Install from file*.

## Configuration

*Tools → Add-ons → Take a Day Off → Config*

| Key | Default | Meaning |
|---|---|---|
| `default_days` | `1` | The number the dialog opens on. |
| `include_intraday_learning` | `true` | Also move cards partway through today's learning steps. |
| `backup_first` | `true` | Force a collection backup before the shift. Leave this on. |

## Requirements

Anki 25.x (built and tested against 25.07.5). Uses the modern
`CollectionOp`/`update_cards` backend API, so it needs 2.1.45 or newer.

## License

MIT
