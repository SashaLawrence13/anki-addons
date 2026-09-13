"""One-by-One Reveal — drive AnKing's cloze one-by-one from a key or a controller.

AnKing's Overhaul note type can reveal a card's clozes one at a time, with
"Reveal Next" and "Toggle All" buttons and its own in-card shortcuts (N and ,).
Those shortcuts are DOM listeners living inside the card's webview, which has
two consequences people run into:

  * Add-ons that reveal "hints" (Hint Hotkeys and friends) do nothing here.
    They target `.hint` elements; cloze one-by-one has none.
  * A controller mapper that simulates a keypress does nothing either. Contanki
    sends a synthetic Qt key event to the focused widget; that never reaches the
    page as a DOM keydown, and never triggers a QShortcut either, because Qt's
    shortcut map only listens to real key events.

So this doesn't pretend to type. It calls the card's own reveal function
directly, and registers it with Contanki as a real action, so a controller
button runs the same code the on-screen button does.
"""

from __future__ import annotations

import importlib

from aqt import gui_hooks, mw
from aqt.qt import *
from aqt.utils import tooltip

ADDON_NAME = "One-by-One Reveal"

# Contanki's package is its add-on id.
CONTANKI = "1898790263"

DEFAULTS = {
    "shortcut_reveal_next": "Y",
    "shortcut_reveal_all": "Shift+Y",
    "register_with_contanki": True,
    "quiet": True,
}


def get_config() -> dict:
    conf = dict(DEFAULTS)
    user = mw.addonManager.getConfig(__name__) or {}
    conf.update({k: v for k, v in user.items() if k in DEFAULTS})
    return conf


# The reveal itself
######################################################################

# Click the card's own button when it is present — that is exactly what the
# user's mouse would do — and fall back to the global the button calls.
JS = """
(function () {
    var b = document.getElementById('%(button)s');
    if (b) { b.click(); return true; }
    try {
        if (typeof %(func)s === 'function') { %(func)s(); return true; }
    } catch (e) {}
    return false;
})()
"""

NEXT_JS = JS % {"button": "button-reveal-next", "func": "revealNextCloze"}
ALL_JS = JS % {"button": "button-toggle-all", "func": "toggleAllCloze"}


def run_js(script: str, label: str) -> None:
    if mw.state != "review" or not mw.reviewer or not mw.reviewer.web:
        return
    conf = get_config()

    def handled(ok) -> None:
        if not ok and not conf["quiet"]:
            tooltip(f"{label}: this card has no one-by-one content.")

    try:
        mw.reviewer.web.evalWithCallback(script, handled)
    except Exception:
        # Older webview API, or the page is mid-navigation.
        try:
            mw.reviewer.web.eval(script)
        except Exception:
            pass


def reveal_next() -> None:
    run_js(NEXT_JS, "Reveal Next")


def reveal_all() -> None:
    run_js(ALL_JS, "Toggle All")


# Wiring
######################################################################


def add_shortcuts(state, shortcuts: list) -> None:
    if state != "review":
        return
    conf = get_config()
    if conf["shortcut_reveal_next"]:
        shortcuts.append((conf["shortcut_reveal_next"], reveal_next))
    if conf["shortcut_reveal_all"]:
        shortcuts.append((conf["shortcut_reveal_all"], reveal_all))


def register_with_contanki() -> None:
    """Add real actions to Contanki, so a button runs code instead of typing.

    Contanki looks its actions up at press time in a module-level dict, so
    inserting into it is enough; the names match what the profile already
    binds. Wrapped tightly — a Contanki update must never break Anki's start-up.
    """
    if not get_config()["register_with_contanki"]:
        return
    try:
        actions = importlib.import_module(f"{CONTANKI}.actions")
    except Exception:
        return  # Contanki isn't installed; keyboard shortcuts still work.
    try:
        actions.button_actions["Reveal Next"] = reveal_next
        actions.button_actions["Reveal All Hints"] = reveal_all
        actions.button_actions["Toggle All Cloze"] = reveal_all
    except Exception:
        pass


gui_hooks.state_shortcuts_will_change.append(add_shortcuts)
gui_hooks.main_window_did_init.append(register_with_contanki)
