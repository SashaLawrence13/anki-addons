"""Image Blur Control — decide for yourself whether blurred images stay blurred.

Some shared decks ship images with class="blur" baked into the note itself, and
the note type's styling turns that into a permanent 15px smear. Editing the note
type works until the deck syncs and overwrites it.

This injects a CSS override into the reviewer instead, so nothing in your
collection is modified and a deck update can't undo it. Four modes:

    off    every blurred image is simply shown
    hover  blurred until you point at it
    click  blurred until you click it, click again to re-blur
    keep   leave the deck's own blurring alone

Tools > Image Blur Mode…, or cycle the modes with a hotkey mid-review.
"""

from __future__ import annotations

from aqt import gui_hooks, mw
from aqt.qt import *
from aqt.reviewer import Reviewer
from aqt.utils import qconnect, tooltip
from aqt.webview import WebContent

ADDON_NAME = "Image Blur Control"

MODES = ["off", "hover", "click", "keep"]

MODE_LABELS = {
    "off": "Off — always show blurred images",
    "hover": "Hover — reveal while pointing at it",
    "click": "Click — click to reveal, click again to hide",
    "keep": "Keep — leave the deck's own blurring alone",
}

DEFAULTS = {
    "mode": "off",
    "shortcut": "Ctrl+Shift+U",
    "blur_radius": 15,
}


def get_config() -> dict:
    conf = dict(DEFAULTS)
    user = mw.addonManager.getConfig(__name__) or {}
    conf.update({k: v for k, v in user.items() if k in DEFAULTS})
    if conf["mode"] not in MODES:
        conf["mode"] = DEFAULTS["mode"]
    return conf


def save_config(conf: dict) -> None:
    mw.addonManager.writeConfig(__name__, conf)


# Injection
######################################################################


def style_for(radius: int) -> str:
    # Every rule is scoped to a class on <html>, so switching modes is one
    # className change rather than a re-render. The reveal rules carry an extra
    # class each, which outranks the base blur at equal !important weight.
    return f"""
<style id="ao-blur-style">
.blur {{ transition: filter .12s ease; }}
html.ao-off .blur {{ filter: none !important; }}
html.ao-hover .blur {{ filter: blur({radius}px) !important; }}
html.ao-hover .blur:hover {{ filter: none !important; }}
html.ao-click .blur {{ filter: blur({radius}px) !important; cursor: pointer; }}
html.ao-click .blur.ao-shown {{ filter: none !important; }}
</style>
"""


SCRIPT = """
<script>
window.aoBlurApply = function (mode) {
    var c = document.documentElement.classList;
    c.remove('ao-off', 'ao-hover', 'ao-click');
    if (mode !== 'keep') { c.add('ao-' + mode); }
    // a re-blur should forget what was already revealed
    document.querySelectorAll('.blur.ao-shown').forEach(function (el) {
        el.classList.remove('ao-shown');
    });
};
if (!window.aoBlurInit) {
    window.aoBlurInit = true;
    document.addEventListener('click', function (e) {
        if (!document.documentElement.classList.contains('ao-click')) return;
        var el = e.target;
        if (el && el.classList && el.classList.contains('blur')) {
            el.classList.toggle('ao-shown');
        }
    }, true);
}
</script>
"""


def on_webview_will_set_content(web_content: WebContent, context) -> None:
    if not isinstance(context, Reviewer):
        return
    conf = get_config()
    web_content.head += style_for(int(conf["blur_radius"]))
    web_content.body += SCRIPT


def apply_mode(mode: str | None = None) -> None:
    """Push the current mode into the reviewer, if one is on screen."""
    if mode is None:
        mode = get_config()["mode"]
    if mw.state == "review" and mw.reviewer and mw.reviewer.web:
        mw.reviewer.web.eval(f"window.aoBlurApply && window.aoBlurApply('{mode}');")


def on_card_shown(*args) -> None:
    apply_mode()


# Interface
######################################################################


def cycle_mode() -> None:
    conf = get_config()
    conf["mode"] = MODES[(MODES.index(conf["mode"]) + 1) % len(MODES)]
    save_config(conf)
    apply_mode(conf["mode"])
    tooltip(f"Image blur: {MODE_LABELS[conf['mode']]}", period=1500)


class BlurModeDialog(QDialog):
    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.conf = get_config()
        self.setWindowTitle(ADDON_NAME)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "How should images that a deck ships blurred be shown?\n"
                "Nothing in your collection is edited — this only overrides\n"
                "the styling, so a deck update can't undo it."
            )
        )

        self.buttons: dict[str, QRadioButton] = {}
        group = QButtonGroup(self)
        for mode in MODES:
            radio = QRadioButton(MODE_LABELS[mode])
            radio.setChecked(mode == self.conf["mode"])
            group.addButton(radio)
            layout.addWidget(radio)
            self.buttons[mode] = radio

        layout.addWidget(
            QLabel(f"\nHotkey to cycle these: {self.conf['shortcut']}")
        )

        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        qconnect(box.accepted, self.accept)
        qconnect(box.rejected, self.reject)
        layout.addWidget(box)

    def chosen(self) -> str:
        for mode, radio in self.buttons.items():
            if radio.isChecked():
                return mode
        return DEFAULTS["mode"]


def open_dialog() -> None:
    dialog = BlurModeDialog(mw)
    if not dialog.exec():
        return
    conf = get_config()
    conf["mode"] = dialog.chosen()
    save_config(conf)
    apply_mode(conf["mode"])
    tooltip(f"Image blur: {MODE_LABELS[conf['mode']]}")


def setup() -> None:
    gui_hooks.webview_will_set_content.append(on_webview_will_set_content)
    gui_hooks.reviewer_did_show_question.append(on_card_shown)
    gui_hooks.reviewer_did_show_answer.append(on_card_shown)

    action = QAction(f"{ADDON_NAME}…", mw)
    qconnect(action.triggered, open_dialog)
    mw.form.menuTools.addAction(action)

    conf = get_config()
    if conf["shortcut"]:
        shortcut = QShortcut(QKeySequence(conf["shortcut"]), mw)
        try:
            shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        except AttributeError:  # pragma: no cover - Qt5
            shortcut.setContext(Qt.ApplicationShortcut)
        qconnect(shortcut.activated, cycle_mode)


setup()
