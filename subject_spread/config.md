## Rebalance Subjects

Tools → Rebalance Subjects…  Study a big unit in a burst and FSRS schedules it
back at you in a burst. Months later that one subject is 150 cards a day while
everything else is 40.

Tick the subjects that are burying you — **Select all** and **Deselect all**
are there for doing the whole collection — pick the date range to spread them
over, and their cards are moved onto the quietest days inside it, so the daily
total flattens instead of spiking.

The range is two dates, not just a length, so the window can start later than
today: *"put cardiology into October, once this unit is done."* Buttons for
2 weeks, 1 month and 3 months set the end date from whatever start you chose.
When a window starts in the future, cards due before it are scheduled into it,
and the confirmation says how many.

Two rules keep it honest:

- **No card is ever moved earlier.** Pulling reviews forward would add work,
  which is the opposite of the point.
- **No card is delayed past its own interval.** A card on a three-day interval
  can move three days, not thirty. Delay a card far past its interval and you
  are not rescheduling it, you are forgetting it. Untick
  `cap_delay_at_interval` to let the load flatten further at that cost.

This second rule is why a distant window may not take everything: a card whose
interval cannot stretch that far is left exactly where it is, and the
confirmation counts them for you.

Settings:

- `days`: how long the default window is when the dialog opens. Rewritten
  each run to the length you last used; the start always defaults to today.
- `cap_delay_at_interval`: the interval rule above. Leave it on.
- `tag_prefixes`: the tag hierarchies subjects are read from — the same shape
  Exam Focus and Topic Stats use, so a subject means the same thing
  everywhere. Set to `[]` to treat each top-level tag as a subject.
- `backup_first`: force a collection backup first. Leave it on.

The confirmation quotes the **combined** daily load — every other subject
included, since those cards stay exactly where they are. That is the load you
will actually meet, not just the part being moved.

Cards are placed least-flexible-first: the ones with the narrowest choice of
day get picked while the calendar is still empty. Going in due order instead
lets late cards pile against the end of the window.

Only due dates move. Intervals, ease and FSRS memory state are never touched.
New and suspended cards are left alone. A card in a filtered deck keeps its
position there and has its home-deck date moved instead. The whole run is one
undo step.
