import re
import time

from aqt import mw, gui_hooks

DEFAULTS = {
    # how many days of review history to analyze
    "window_days": 30,
    # a topic needs at least this many reviews in the window to be ranked
    "min_reviews": 30,
    # how many best/worst topics to show
    "show_count": 5,
    # tag hierarchies to rank, grouped by the segments after each prefix;
    # empty list = rank all leaf tags (old behavior)
    "tag_prefixes": [
        "#AK_Step2_v12::#Bootcamp",
        "#AK_Step1_v12::#Bootcamp",
    ],
    # how many tag segments after the prefix form one topic
    # (2 = "Medicine > 01_Cardiology")
    "group_levels": 2,
}

_cache = {"time": 0, "html": ""}


def get_config():
    cfg = dict(DEFAULTS)
    stored = mw.addonManager.getConfig(__name__) or {}
    cfg.update({k: v for k, v in stored.items() if v is not None})
    return cfg


def leaf_name(tag):
    return tag.split("::")[-1].replace("_", " ").lstrip("#")


def clean_segment(seg):
    seg = seg.lstrip("#").replace("_", " ")
    # drop ordering numbers like "01 Cardiology" -> "Cardiology"
    return re.sub(r"^\d+\s*", "", seg)


def group_key(tag, prefixes, levels):
    """Map a tag to its broader topic group, or None if outside the
    configured hierarchies."""
    for prefix in prefixes:
        if tag == prefix or tag.startswith(prefix + "::"):
            rest = tag[len(prefix):].lstrip(":")
            if not rest:
                return None
            segs = rest.split("::")[:levels]
            return " › ".join(clean_segment(s) for s in segs)
    return None


def compute_topic_stats(cfg):
    cutoff_ms = int((time.time() - cfg["window_days"] * 86400) * 1000)
    rows = mw.col.db.all(
        "select n.tags, "
        "sum(case when r.ease = 1 then 1 else 0 end), count(*) "
        "from revlog r "
        "join cards c on r.cid = c.id "
        "join notes n on c.nid = n.id "
        "where r.id > ? and r.type != 4 "
        "group by n.id",
        cutoff_ms,
    )

    prefixes = cfg.get("tag_prefixes") or []
    levels = cfg.get("group_levels", 2)
    per_group = {}
    all_tags = set()
    for tags_str, fails, total in rows:
        seen_groups = set()
        for tag in tags_str.split():
            all_tags.add(tag)
            if prefixes:
                g = group_key(tag, prefixes, levels)
            else:
                g = tag
            # a note can carry several tags in the same group — count once
            if g is None or g in seen_groups:
                continue
            seen_groups.add(g)
            f, t = per_group.get(g, (0, 0))
            per_group[g] = (f + fails, t + total)

    results = []
    for g, (fails, total) in per_group.items():
        if total < cfg["min_reviews"]:
            continue
        if not prefixes:
            # leaf-tag mode: skip parents that duplicate their children
            is_leaf = not any(
                other != g and other.startswith(g + "::") for other in all_tags
            )
            if not is_leaf:
                continue
        accuracy = 100.0 * (1 - fails / total)
        results.append((accuracy, total, g))

    results.sort(reverse=True)
    return results


def bar(pct, color):
    return (
        '<span style="display:inline-block;width:90px;height:9px;'
        'background:#8883;border-radius:5px;vertical-align:middle;'
        'margin-right:6px"><span style="display:block;width:%d%%;'
        'height:9px;background:%s;border-radius:5px"></span></span>'
        % (int(pct), color)
    )


def row_html(accuracy, total, tag, color):
    return (
        '<tr><td style="text-align:left;padding:1px 8px 1px 0">%s</td>'
        '<td style="white-space:nowrap">%s<b>%.0f%%</b> '
        '<span style="color:gray;font-size:11px">(%d revs)</span></td></tr>'
        % (leaf_name(tag), bar(accuracy, color), accuracy, total)
    )


def build_html(cfg):
    results = compute_topic_stats(cfg)
    if len(results) < 2:
        return ""

    n = cfg["show_count"]
    best = results[:n]
    worst = list(reversed(results[-n:]))
    # avoid overlap when few topics qualify
    best_tags = {t for _, _, t in best}
    worst = [r for r in worst if r[2] not in best_tags]

    total_revs = sum(t for _, t, _ in results)
    overall_correct = sum(a * t / 100 for a, t, _ in results)
    overall = 100 * overall_correct / total_revs if total_revs else 0

    html = [
        '<div style="margin-top:1.5em;text-align:center">',
        '<h3 style="margin-bottom:2px">Topic performance '
        '<span style="font-weight:normal;color:gray;font-size:12px">'
        "last %d days · %.0f%% overall</span></h3>" % (cfg["window_days"], overall),
        '<table style="margin:0 auto;border-spacing:0 2px">',
        '<tr><td colspan="2" style="text-align:left;color:#4caf50">'
        "<b>Strongest</b></td></tr>",
    ]
    for a, t, tag in best:
        html.append(row_html(a, t, tag, "#4caf50"))
    if worst:
        html.append(
            '<tr><td colspan="2" style="text-align:left;color:#e53935;'
            'padding-top:6px"><b>Needs work</b></td></tr>'
        )
        for a, t, tag in worst:
            html.append(row_html(a, t, tag, "#e53935"))
    html.append("</table></div>")
    return "".join(html)


def on_deck_browser(deck_browser, content):
    cfg = get_config()
    now = time.time()
    if now - _cache["time"] > 300:
        try:
            _cache["html"] = build_html(cfg)
        except Exception:
            _cache["html"] = ""
        _cache["time"] = now
    content.stats += _cache["html"]


gui_hooks.deck_browser_will_render_content.append(on_deck_browser)
