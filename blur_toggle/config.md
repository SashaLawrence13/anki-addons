## Image Blur Control

Some shared decks — AnKing's especially — ship images with `class="blur"` in the
note itself, which the note type's styling turns into a permanent smear. Editing
the note type works until the deck syncs and overwrites your change. This
overrides the styling from outside instead, so nothing in your collection is
modified and a deck update cannot undo it.

- `mode`: one of
  - `off` — always show blurred images (the default)
  - `hover` — blurred until you point at it
  - `click` — blurred until you click it; click again to re-blur
  - `keep` — leave the deck's own blurring alone
- `shortcut`: cycles the four modes mid-review. Default `Ctrl+Shift+U`. Set to
  `""` to register no hotkey.
- `blur_radius`: pixels of blur used by `hover` and `click`. Only affects those
  two modes; `keep` uses whatever the deck specified.

Also available at Tools → Image Blur Control…

Worth knowing: `off` means anything a deck chose to blur is now visible on
screen, which is the entire point, but it is worth a thought about where you
study. `hover` is the polite middle ground in a library.
