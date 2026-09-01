"""Temporary diagnostic: log a stack trace whenever Anki's progress
dialog machinery is invoked, so we can see who triggers 'Processing...'."""

import os
import time
import traceback

from aqt.progress import ProgressManager

LOG = os.path.join(os.path.dirname(__file__), "user_files", "progress_log.txt")


def _log(kind, label):
    try:
        with open(LOG, "a") as f:
            f.write(
                "\n=== %s  %s  label=%r\n"
                % (time.strftime("%H:%M:%S"), kind, label)
            )
            f.write("".join(traceback.format_stack(limit=14)))
    except Exception:
        pass


_orig_start = ProgressManager.start


def patched_start(self, *args, **kwargs):
    _log("start", kwargs.get("label"))
    return _orig_start(self, *args, **kwargs)


ProgressManager.start = patched_start

if hasattr(ProgressManager, "_showWin"):
    _orig_show = ProgressManager._showWin

    def patched_show(self, *args, **kwargs):
        _log("showWin", None)
        return _orig_show(self, *args, **kwargs)

    ProgressManager._showWin = patched_show
