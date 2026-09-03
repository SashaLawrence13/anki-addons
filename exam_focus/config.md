## Exam Focus

Tools → Exam Focus…  Tick the subjects your exam covers; everything else is
cleared off tomorrow. One button, and tomorrow is your exam subject only.

Take a Day Off clears the day completely; this clears everything except what
you're being tested on.

Anki's deck screen adds three different things together, so a clean exam day
means dealing with all three:

- **Review cards** move by date — pushed back `days`.
- **Learning cards** store a timestamp rather than a day number, so they're
  moved in seconds by the same amount.
- **New cards have no due date at all.** The only way to stop Anki offering
  them tomorrow is to suspend them, so Exam Focus does, and records exactly
  which ones. Tools → Exam Focus: Release Held Cards puts back precisely those
  and nothing else — it will never touch cards you suspended deliberately.
  Only new cards **inside the subject taxonomy** are ever held: a deck that
  carries none of your subject tags — a language deck, guitar practice, your
  school's own deck — is nobody's exam subject and is left alone. The
  confirmation always states the exact number, and a tickbox in the dialog
  turns it off for a single run.

Settings:

- `days`: how far to push everything else. Rewritten each run. A negative
  number undoes a previous shift.
- `hold_other_new`: suspend other subjects' new cards. Turn this off if you'd
  rather keep meeting new cards from everywhere.
- `include_learning`: move other subjects' learning cards too.
- `tag_prefixes`: the tag hierarchies subjects are read from — the same shape
  Topic Stats and Weak Topic Drill use. Set to `[]` to treat each top-level tag
  as a subject.
- `backup_first`: force a collection backup first. Leave it on.

Only due dates move. Intervals, ease and FSRS memory state are never touched,
so nothing is treated as late and no card is rescheduled as though you answered
it.

Best run **after you finish today's reviews**. Cards move by date, so anything
still sitting on today gets pushed onto tomorrow — the day you're trying to
clear.

A card in a filtered deck keeps its position there; its home-deck date moves
instead. The whole shift is one undo step.
