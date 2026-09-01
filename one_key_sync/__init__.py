from aqt import mw
from aqt.qt import QShortcut, QKeySequence, Qt

DEFAULT_SHORTCUT = "Ctrl+S"


def sync_now():
    if mw is None or mw.col is None:
        return
    mw.onSync()


def setup():
    config = mw.addonManager.getConfig(__name__) or {}
    keys = config.get("shortcut", DEFAULT_SHORTCUT)

    shortcut = QShortcut(QKeySequence(keys), mw)
    context = getattr(getattr(Qt, "ShortcutContext", Qt), "ApplicationShortcut", None)
    if context is None:
        context = Qt.ApplicationShortcut
    shortcut.setContext(context)
    shortcut.activated.connect(sync_now)


setup()
