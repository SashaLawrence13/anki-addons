import json
import os
import time

from aqt import mw, gui_hooks
from aqt.qt import (
    QObject,
    QEvent,
    QTimer,
    QDialog,
    QVBoxLayout,
    QLabel,
    QPushButton,
    Qt,
)

ADDON_DIR = os.path.dirname(__file__)
STATS_PATH = os.path.join(ADDON_DIR, "user_files", "stats.json")

DEFAULTS = {
    # seconds of no keyboard/mouse input before the study timer pauses
    "idle_pause_seconds": 60,
    # seconds of no input before an automatic sync fires (e.g. 30, 60, 90)
    "auto_sync_idle_seconds": 300,
    # while reviewing, wait at least this long — thinking pauses on a hard
    # card must not trigger a sync (and its Processing dialog) mid-session
    "review_auto_sync_idle_seconds": 300,
    # show the recap dialog when closing Anki (auto-dismisses)
    "show_recap_on_close": True,
    "recap_auto_close_seconds": 6,
}


def get_config():
    cfg = dict(DEFAULTS)
    stored = mw.addonManager.getConfig(__name__) or {}
    cfg.update({k: v for k, v in stored.items() if v is not None})
    return cfg


def today_key():
    # respect Anki's day rollover (usually 4am) so late-night reviews
    # count toward the same study day
    try:
        cutoff = mw.col.sched.day_cutoff
        return time.strftime("%Y-%m-%d", time.localtime(cutoff - 86400))
    except Exception:
        return time.strftime("%Y-%m-%d")


class Stats:
    def __init__(self):
        self.data = {}
        self.load()

    def load(self):
        try:
            with open(STATS_PATH, "r") as f:
                self.data = json.load(f)
        except Exception:
            self.data = {}

    def save(self):
        try:
            os.makedirs(os.path.dirname(STATS_PATH), exist_ok=True)
            with open(STATS_PATH, "w") as f:
                json.dump(self.data, f)
        except Exception:
            pass

    def day(self):
        key = today_key()
        if key not in self.data:
            self.data[key] = {"active_seconds": 0, "cards": 0}
        return self.data[key]

    def total_xp(self):
        return self.data.get("_total_xp", 0)

    def add_xp(self, amount):
        self.data["_total_xp"] = self.total_xp() + amount
        day = self.day()
        day["xp"] = day.get("xp", 0) + amount


def level_info(xp):
    """Returns (level, xp_into_level, xp_needed_for_next)."""
    level = 1
    need = 500
    while xp >= need:
        xp -= need
        level += 1
        need = 500 + 250 * (level - 1)
    return level, xp, need


CONFETTI_JS = """
(function(){
var c=document.createElement('canvas');
c.style.cssText='position:fixed;left:0;top:0;width:100vw;height:100vh;pointer-events:none;z-index:9999';
c.width=innerWidth;c.height=innerHeight;document.body.appendChild(c);
var x=c.getContext('2d');var P=[];
for(var i=0;i<160;i++)P.push({x:Math.random()*c.width,y:-20-Math.random()*c.height/2,
s:5+Math.random()*7,v:2+Math.random()*4,a:Math.random()*6.28,r:0.05+Math.random()*0.12,
col:'hsl('+Math.floor(Math.random()*360)+',90%,60%)'});
var t=0;var iv=setInterval(function(){t++;x.clearRect(0,0,c.width,c.height);
P.forEach(function(p){p.y+=p.v;p.a+=p.r;x.save();x.translate(p.x,p.y);x.rotate(p.a);
x.fillStyle=p.col;x.fillRect(-p.s/2,-p.s/2,p.s,p.s*0.6);x.restore();});
if(t>280){clearInterval(iv);c.remove();}},16);})();
"""


class ActivityMonitor(QObject):
    """App-wide event filter: any key press or mouse activity counts as activity."""

    WATCHED = None

    def __init__(self):
        super().__init__()
        et = QEvent.Type
        self.WATCHED = {
            et.KeyPress,
            et.MouseButtonPress,
            et.MouseMove,
            et.Wheel,
            et.TouchBegin,
        }
        self.last_activity = time.time()
        self._last_mouse_pos = None
        self.recent_resets = []

    def _record(self, source):
        self.last_activity = time.time()
        self.recent_resets.append((self.last_activity, source))
        del self.recent_resets[:-50]

    def eventFilter(self, obj, event):
        if event.type() not in self.WATCHED:
            return False
        # Qt can synthesize MouseMove events when content redraws under a
        # parked cursor — only count moves where the cursor actually moved
        if event.type() == QEvent.Type.MouseMove:
            try:
                pos = event.globalPosition()
                pos = (round(pos.x()), round(pos.y()))
            except AttributeError:
                p = event.globalPos()
                pos = (p.x(), p.y())
            if pos == self._last_mouse_pos:
                return False
            self._last_mouse_pos = pos
        self._record(
            "%s on %s" % (str(event.type()), type(obj).__name__)
        )
        return False

    def touch(self, *args, **kwargs):
        self._record("hook")

    def idle_seconds(self):
        return time.time() - self.last_activity


class StudyCompanion:
    def __init__(self):
        self.cfg = get_config()
        self.stats = Stats()
        self.monitor = ActivityMonitor()
        mw.app.installEventFilter(self.monitor)

        self.synced_this_idle = False
        self.last_auto_sync = None
        self.last_save = time.time()
        self.answer_times = []
        self.streak = None
        self.last_streak_calc = 0
        # refreshed once per card (on question show) — never polled from the
        # 1s timer, which would contend with the answer operation and make
        # Anki flash its Processing dialog on slow answers
        self.cached_remaining = None

        self.timer = QTimer(mw)
        self.timer.timeout.connect(self.tick)
        self.timer.start(1000)

        gui_hooks.reviewer_did_answer_card.append(self.on_answer)
        gui_hooks.top_toolbar_did_init_links.append(self.on_toolbar)
        gui_hooks.profile_will_close.append(self.on_close)

        # clicks inside the card area happen in a Chromium child widget the
        # app-level filter can miss — treat reviewer events as activity too
        gui_hooks.reviewer_did_show_question.append(self.on_question_shown)
        gui_hooks.reviewer_did_show_answer.append(
            lambda *a: self.monitor._record("show_answer")
        )
        gui_hooks.state_did_change.append(
            lambda *a: self.monitor._record("state_change")
        )
        gui_hooks.webview_did_receive_js_message.append(self.on_js_message)

        self._filtered_proxies = set()

    def watch_webview(self):
        """Install the activity filter on the web view's real input widget."""
        try:
            proxy = mw.web.focusProxy()
            if proxy is not None and id(proxy) not in self._filtered_proxies:
                proxy.installEventFilter(self.monitor)
                self._filtered_proxies.add(id(proxy))
        except Exception:
            pass

    # only messages caused by a real user action — Anki's webviews also send
    # internal housekeeping messages that must NOT reset the idle clock
    USER_JS_PREFIXES = (
        "ans",
        "ease",
        "showAnswer",
        "typeans",
        "flag",
        "mark",
        "bury",
        "suspend",
        "play:",
    )

    def on_js_message(self, handled, message, context):
        if isinstance(message, str) and message.startswith(self.USER_JS_PREFIXES):
            self.monitor._record("js:%s" % message[:40])
        return handled

    # ---- time tracking ----

    def tick(self):
        if mw is None or mw.col is None:
            return

        self.watch_webview()
        idle = self.monitor.idle_seconds()

        if mw.state == "review" and idle < self.cfg["idle_pause_seconds"]:
            self.stats.day()["active_seconds"] += 1

        self.update_toolbar()
        self.maybe_auto_sync(idle)

        if time.time() - self.last_save > 30:
            self.stats.save()
            self.last_save = time.time()
            self.dump_debug()

        if time.time() - self.last_streak_calc > 1800:
            self.last_streak_calc = time.time()
            self.streak = self.compute_streak()

    def dump_debug(self):
        try:
            path = os.path.join(ADDON_DIR, "user_files", "debug_log.txt")
            with open(path, "w") as f:
                f.write("last 50 idle-clock resets (newest last):\n")
                for ts, source in self.monitor.recent_resets:
                    f.write(
                        "%s  %s\n"
                        % (time.strftime("%H:%M:%S", time.localtime(ts)), source)
                    )
        except Exception:
            pass

    def on_question_shown(self, card):
        self.monitor._record("show_question")
        # ask the scheduler AFTER the answer operation chain has fully
        # finished — querying inside it pushes slow answers over Anki's
        # progress-dialog threshold, flashing "Processing..."
        QTimer.singleShot(900, self.refresh_remaining)

    def refresh_remaining(self):
        if mw.state == "review":
            self.cached_remaining = self.remaining_due()

    def on_answer(self, reviewer, card, ease):
        self.stats.day()["cards"] += 1
        self.answer_times.append(time.time())
        del self.answer_times[:-200]
        self.award_xp(ease)
        QTimer.singleShot(400, self.maybe_confetti)

    # ---- xp / levels ----

    def award_xp(self, ease):
        before = level_info(self.stats.total_xp())[0]
        xp = 10 if ease == 1 else 15
        if self.streak:
            xp = int(xp * (1 + min(self.streak, 30) * 0.01))
        self.stats.add_xp(xp)
        after = level_info(self.stats.total_xp())[0]
        if after > before:
            from aqt.utils import tooltip

            tooltip("\U0001f389 Level %d!" % after, period=3000)
            try:
                mw.web.eval(CONFETTI_JS)
            except Exception:
                pass

    # ---- confetti on zero ----

    def maybe_confetti(self):
        day = self.stats.day()
        if day.get("confetti_done"):
            return
        # only check once review has ended (finishing the deck exits review);
        # querying the scheduler mid-review races the answer operation
        if mw.state == "review":
            return
        try:
            remaining = sum(mw.col.sched.counts())
        except Exception:
            remaining = None
        if remaining == 0 and day["cards"] > 0:
            day["confetti_done"] = True
            try:
                mw.web.eval(CONFETTI_JS)
            except Exception:
                pass

    # ---- streak / pace / progress ----

    def compute_streak(self):
        """Consecutive days (per Anki's rollover) with at least one review."""
        try:
            roll = mw.col.get_config("rollover", 4)
            days = set(
                mw.col.db.list(
                    "select distinct strftime('%%Y-%%m-%%d', "
                    "datetime(id/1000 - %d, 'unixepoch', 'localtime')) "
                    "from revlog" % (roll * 3600)
                )
            )
            import datetime as dt

            d = dt.datetime.fromtimestamp(time.time() - roll * 3600).date()
            streak = 0
            if d.isoformat() not in days:
                d -= dt.timedelta(days=1)
            while d.isoformat() in days:
                streak += 1
                d -= dt.timedelta(days=1)
            return streak
        except Exception:
            return None

    def remaining_due(self):
        """Cards left in the currently selected deck, or None."""
        if mw.state != "review":
            return None
        try:
            counts = mw.col.sched.counts(mw.reviewer.card)
        except TypeError:
            try:
                counts = mw.col.sched.counts()
            except Exception:
                return None
        except Exception:
            return None
        return sum(counts)

    def eta_text(self, remaining):
        """Time left at the answer rate of the last 15 min, plus finish time."""
        if not remaining:
            return None
        now = time.time()
        recent = [t for t in self.answer_times if now - t < 900]
        if len(recent) < 5 or now - recent[0] < 60:
            return None
        rate = len(recent) / (now - recent[0])  # cards per second
        if rate <= 0:
            return None
        left = remaining / rate
        if left >= 3600:
            dur = "%dh%02dm" % (left // 3600, (left % 3600) // 60)
        else:
            dur = "%dm" % max(1, left // 60)
        finish = time.strftime("%-I:%M%p", time.localtime(now + left)).lower()
        return "%s left, done %s" % (dur, finish)

    # ---- auto sync ----

    def sync_threshold(self):
        # accept old configs that used minutes
        if "auto_sync_idle_minutes" in self.cfg:
            base = self.cfg["auto_sync_idle_minutes"] * 60
        else:
            base = self.cfg["auto_sync_idle_seconds"]
        if mw.state == "review":
            return max(base, self.cfg.get("review_auto_sync_idle_seconds", 300))
        return base

    def maybe_auto_sync(self, idle):
        threshold = self.sync_threshold()
        if idle < threshold:
            self.synced_this_idle = False
            return
        if self.synced_this_idle:
            return
        # controller input (e.g. Contanki) is invisible to the idle monitor,
        # so cap how often idle-detection mistakes can fire a sync
        gap = self.cfg.get("min_minutes_between_auto_syncs", 15) * 60
        if self.last_auto_sync and time.time() - self.last_auto_sync < gap:
            return
        if mw.state not in ("deckBrowser", "overview", "review"):
            return
        self.synced_this_idle = True
        self.last_auto_sync = time.time()
        self.stats.save()
        try:
            mw.onSync()
        except Exception:
            pass

    # ---- toolbar ----

    def on_toolbar(self, links, toolbar):
        links.append(
            toolbar.create_link(
                "study_companion",
                self.toolbar_text(),
                self.show_recap,
                tip="Study Companion — click for today's recap",
                id="study-companion",
            )
        )

    def toolbar_text(self):
        day = self.stats.day()
        mins = day["active_seconds"] // 60
        if mins >= 60:
            t = "%dh%02dm" % (mins // 60, mins % 60)
        else:
            t = "%dm" % mins
        base = "%s · %d cards" % (t, day["cards"])

        idle = self.monitor.idle_seconds()
        if self.synced_this_idle and self.last_auto_sync:
            base += " · synced %s" % time.strftime(
                "%-I:%M%p", time.localtime(self.last_auto_sync)
            ).lower()
        elif idle >= 10:
            remaining = int(self.sync_threshold() - idle)
            if remaining > 0:
                base += " · sync in %d:%02d" % (remaining // 60, remaining % 60)
        return base

    def toolbar_html(self):
        parts = [self.toolbar_text()]
        level, _, _ = level_info(self.stats.total_xp())
        parts.append("Lv%d" % level)
        if self.streak:
            parts.append("\U0001f525%d" % self.streak)

        remaining = self.cached_remaining if mw.state == "review" else None
        if remaining is not None:
            done = self.stats.day()["cards"]
            total = done + remaining
            if total > 0 and remaining > 0:
                pct = int(100 * done / total)
                bar = (
                    '<span style="display:inline-block;width:56px;height:8px;'
                    'background:#8884;border-radius:4px;vertical-align:middle">'
                    '<span style="display:block;width:%d%%;height:8px;'
                    'background:#4caf50;border-radius:4px"></span></span> %d left'
                    % (pct, remaining)
                )
                parts.append(bar)
                eta = self.eta_text(remaining)
                if eta:
                    parts.append(eta)
            elif remaining == 0:
                parts.append("\u2705 done!")
        return " · ".join(parts)

    def update_toolbar(self):
        html = self.toolbar_html().replace("'", "\\'").replace("\n", " ")
        try:
            mw.toolbar.web.eval(
                "var e=document.getElementById('study-companion');"
                "if(e){e.innerHTML='%s';}" % html
            )
        except Exception:
            pass

    # ---- recap ----

    def anki_counted_seconds(self):
        """Time as Anki's own stats count it (per-card answer time, capped)."""
        try:
            cutoff_ms = (mw.col.sched.day_cutoff - 86400) * 1000
            return (
                mw.col.db.scalar(
                    "select sum(time)/1000 from revlog where id > ?", cutoff_ms
                )
                or 0
            )
        except Exception:
            return 0

    def show_recap(self, on_close=False):
        day = self.stats.day()
        active_min = day["active_seconds"] / 60
        anki_min = self.anki_counted_seconds() / 60

        dlg = QDialog(mw)
        dlg.setWindowTitle("Today's Recap")
        layout = QVBoxLayout(dlg)

        level, into, need = level_info(self.stats.total_xp())
        xp_line = (
            "<p><b>Level %d</b> · +%d XP today · %d/%d to next level</p>"
            % (level, day.get("xp", 0), into, need)
        )
        streak_line = xp_line
        if self.streak:
            streak_line += (
                "<p>\U0001f525 <b>%d day streak</b></p>" % self.streak
            )
        label = QLabel(
            "<h3>Today</h3>"
            "<p><b>%d cards</b> answered</p>"
            "<p><b>%.0f min</b> real study time<br>"
            "<span style='color:gray'>(%.0f min by Anki's per-card count)</span></p>"
            "%s" % (day["cards"], active_min, anki_min, streak_line)
        )
        try:
            label.setTextFormat(Qt.TextFormat.RichText)
        except AttributeError:
            label.setTextFormat(Qt.RichText)
        layout.addWidget(label)

        btn = QPushButton("Close")
        btn.clicked.connect(dlg.accept)
        btn.setDefault(True)
        layout.addWidget(btn)

        if on_close:
            secs = self.cfg["recap_auto_close_seconds"]
            countdown = QLabel("Closing in %d s… (Enter to dismiss)" % secs)
            layout.addWidget(countdown)
            state = {"left": secs}

            def step():
                state["left"] -= 1
                if state["left"] <= 0:
                    dlg.accept()
                else:
                    countdown.setText(
                        "Closing in %d s… (Enter to dismiss)" % state["left"]
                    )

            t = QTimer(dlg)
            t.timeout.connect(step)
            t.start(1000)

        dlg.exec()

    def on_close(self):
        self.stats.save()
        if self.cfg["show_recap_on_close"] and self.stats.day()["cards"] > 0:
            try:
                self.show_recap(on_close=True)
            except Exception:
                pass


companion = None


def init():
    global companion
    if companion is None:
        companion = StudyCompanion()
        mw.toolbar.draw()


gui_hooks.profile_did_open.append(init)
