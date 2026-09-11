## Rebalance Subjects

Tools → Rebalance Subjects…  Study a big unit in a burst and FSRS schedules it
back at you in a burst. Months later that one subject is 150 cards a day while
everything else is 40.

Tick the subjects that are burying you — **Select all** and **Deselect all**
are there for doing the whole collection — choose how many days to spread them
over, and their cards are moved onto the quietest days in that window, so the
daily total flattens instead of spiking.

Two rules keep it honest:

- **No card is ever moved earlier.** Pulling reviews forward would add work,
  which is the opposite of the point.
- **No card is delayed past its own interval.** A card on a three-day interval
  can move three days, not thirty. Delay a card far past its interval and you
  are not rescheduling it, you are forgetting it. Untick
  `cap_delay_at_interval` to let the load flatten further at that cost.

Settings:

- `days`: the window to spread across. Rewritten each run.
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
