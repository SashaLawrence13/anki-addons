## Spread to a Deadline

Tools → Spread to a Deadline…  Pick a date and a deck; everything you are
already behind on is fanned out evenly across the days between now and then,
most overdue first, so the backlog is gone before the deadline.

Only due dates move. Intervals, ease and FSRS memory state are untouched, so no
card is rescheduled as though you had answered it.

- `default_days_ahead`: how far ahead the date box opens. Rewritten each run to
  whatever you last chose.
- `deck`: the deck the dialog opens on, including its subdecks. Rewritten each
  run; `""` means the whole collection.
- `backup_first`: force a collection backup before redistributing. Leave this
  on — it costs a second and it is the thing that saves you.

Cards already scheduled for a future day stay where they are, which is why the
confirmation quotes a *combined* daily load: the spread backlog plus the reviews
those days were already going to bring. New and suspended cards are untouched —
new cards have no due date to miss.

When a deck is selected, the confirmation also checks the plan against that
deck's reviews/day limit and warns if the busiest days would exceed it, since
Anki would otherwise hide the overflow and you would never see the cards you
just scheduled.

The whole run is one undo step — Ctrl/Cmd+Z puts every card back.
