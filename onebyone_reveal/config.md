## One-by-One Reveal

Reveals AnKing cloze one-by-one cards from a keyboard shortcut or a controller
button, by calling the card's own reveal function directly.

The card template already has its own in-card shortcuts — **N** to reveal next,
**,** to toggle all — and those keep working. This exists because those are DOM
listeners inside the card's webview, so two things that look like they should
work, don't:

- Hint-revealing add-ons target `.hint` elements. Cloze one-by-one has none, so
  they do nothing on these cards no matter which key you bind.
- Controller mappers that simulate a keypress send a synthetic Qt event to the
  focused widget. That never becomes a DOM keydown, and never triggers a
  QShortcut either, since Qt's shortcut map only listens to real key events.

So a button press here runs the same function the on-screen button runs.

- `shortcut_reveal_next`: default `Y`. Set `""` to register none.
- `shortcut_reveal_all`: default `Shift+Y`.
- `register_with_contanki`: adds **Reveal Next**, **Reveal All Hints** and
  **Toggle All Cloze** to Contanki's action list, so a controller button can be
  bound to them like any built-in action. Harmless if Contanki isn't installed.
- `quiet`: when `false`, shows a tooltip on cards that have no one-by-one
  content, instead of silently doing nothing. Useful for confirming a binding
  fires at all.

Only affects notes whose **One by one** field is filled — the rest are untouched.
