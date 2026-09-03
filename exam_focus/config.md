## Exam Focus

Tools → Exam Focus…  Tick the subjects your exam covers, and everything *else*
is pushed back, so the day before a cardiology exam you sit down to cardiology
and nothing else. The rest of the collection is waiting, untouched, the day
after.

Take a Day Off clears the day completely; this clears everything except what
you're being tested on.

- `days`: how far to push everything else. Rewritten each run to whatever you
  last chose. A negative number undoes a previous shift.
- `tag_prefixes`: the tag hierarchies subjects are read from — the same shape
  Topic Stats and Weak Topic Drill use, so "Cardiology" means the same thing
  everywhere. Set to `[]` to treat each top-level tag as a subject.
- `backup_first`: force a collection backup before moving anything. Leave it on.

Only due dates move. Intervals, ease and FSRS memory state are never touched,
so nothing is treated as late and no card is rescheduled as though you answered
it. New and suspended cards are untouched — new cards have no due date to miss.

A card sitting in a filtered deck keeps its position there; its home-deck date
moves instead, so it stays available until the filtered deck is emptied.

The whole shift is one undo step — Ctrl/Cmd+Z puts everything back.
