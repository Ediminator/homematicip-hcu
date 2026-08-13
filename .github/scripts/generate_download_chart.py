#!/usr/bin/env python3
"""Render a static SVG trend chart from the download-stats history.

Reads the accumulated history written by update_download_stats.py and draws
two charts (total installations over time, version mix over time) covering
the most recent runs. The output is a single self-contained SVG embedded in
download_stats.md, so it renders directly when browsing the repo on GitHub -
no extra hosting required.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

HISTORY_PATH = Path(".docs/downloads/history.json")
OUTPUT_PATH = Path(".docs/downloads/chart.svg")
WINDOW = 20  # number of most recent history entries to plot
TOP_N_VERSIONS = 6  # versions charted individually; the rest fold into "Sonstige"

# Categorical palette (validated for CVD-safety, see dataviz skill), light mode only.
SLOT_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
OTHER_COLOR = "#898781"

SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"


def version_key(version: str) -> tuple:
    match = re.match(r"^(\d+(?:\.\d+)*)(?:-(.+))?$", version)
    if not match:
        return ((), False, version)
    release = tuple(int(part) for part in match.group(1).split("."))
    pre_release = match.group(2)
    return (release, pre_release is None, pre_release or "")


def nice_ticks(vmin: float, vmax: float, count: int = 4) -> tuple[float, float, list[float]]:
    """Round (vmin, vmax) out to a human-friendly axis with ~count ticks."""
    if vmax <= vmin:
        vmax = vmin + 1
    raw_step = (vmax - vmin) / max(count - 1, 1)
    magnitude = 10 ** math.floor(math.log10(raw_step)) if raw_step > 0 else 1
    residual = raw_step / magnitude
    if residual > 5:
        step = 10 * magnitude
    elif residual > 2:
        step = 5 * magnitude
    elif residual > 1:
        step = 2 * magnitude
    else:
        step = magnitude
    nice_min = math.floor(vmin / step) * step
    nice_max = math.ceil(vmax / step) * step
    ticks = []
    v = nice_min
    while v <= nice_max + 1e-9:
        ticks.append(round(v))
        v += step
    return nice_min, nice_max, ticks


def short_date(timestamp: str) -> str:
    # timestamps look like "2026-08-13T06:09 UTC" or "2026-08-13 06:09 UTC"
    day_part = timestamp.replace("T", " ").split(" ")[0]
    _, month, day = day_part.split("-")
    return f"{day}.{month}."


def esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_svg(rows: list[dict]) -> str:
    n = len(rows)
    parts: list[str] = []

    def add(s: str) -> None:
        parts.append(s)

    # ---------- pick versions to chart individually ----------
    max_by_version: dict[str, int] = {}
    for row in rows:
        for version, count in row["versions"].items():
            max_by_version[version] = max(max_by_version.get(version, 0), count)
    ranked = sorted(max_by_version.items(), key=lambda item: item[1], reverse=True)
    top_versions = [name for name, _ in ranked[:TOP_N_VERSIONS]]
    color_by_version = {name: SLOT_COLORS[i % len(SLOT_COLORS)] for i, name in enumerate(top_versions)}
    has_other = len(ranked) > len(top_versions) or any(
        row["total"] - sum(row["versions"].get(v, 0) for v in top_versions) > 0 for row in rows
    )
    # stack bottom -> top: oldest-to-newest by semantic version, "Sonstige" as the base
    stack_order = sorted(top_versions, key=version_key)
    if has_other:
        stack_order = ["Sonstige"] + stack_order
    legend_order = list(reversed(stack_order))  # newest / most prominent first

    totals = [row["total"] for row in rows]
    dates = [short_date(row["timestamp"]) for row in rows]
    last = rows[-1]

    # ================= shared geometry =================
    W = 760
    ML, MR = 46, 16

    def xpos(i: int, plot_left: float, plot_w: float) -> float:
        if n <= 1:
            return plot_left + plot_w / 2
        return plot_left + (i / (n - 1)) * plot_w

    add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} 660" '
        f'font-family="system-ui, -apple-system, Segoe UI, sans-serif">')
    add(f'<rect x="0" y="0" width="{W}" height="660" fill="{SURFACE}" />')

    # ================= CHART 1: total installations =================
    CH1_TOP, CH1_TITLE_H, CH1_MT, CH1_MB = 8, 34, 8, 34
    plot1_top = CH1_TOP + CH1_TITLE_H + CH1_MT
    plot1_h = 220
    plot1_bottom = plot1_top + plot1_h
    plot1_w = W - ML - MR

    add(f'<text x="{ML}" y="{CH1_TOP + 16}" font-size="14" font-weight="650" fill="{INK_PRIMARY}">'
        f'Gesamtinstallationen &#252;ber Zeit</text>')
    add(f'<text x="{ML}" y="{CH1_TOP + 30}" font-size="11" fill="{INK_SECONDARY}">'
        f'Summe aller Versionen je Lauf &#183; {esc(dates[0])} &#8211; {esc(dates[-1])}</text>')

    vmin, vmax, ticks = nice_ticks(min(totals), max(totals), 4)

    def y1(v: float) -> float:
        return plot1_bottom - ((v - vmin) / (vmax - vmin)) * plot1_h

    for t in ticks:
        ty = y1(t)
        add(f'<line x1="{ML}" x2="{W - MR}" y1="{ty:.1f}" y2="{ty:.1f}" stroke="{GRID}" stroke-width="1" />')
        add(f'<text x="{ML - 8}" y="{ty + 3:.1f}" font-size="10.5" fill="{INK_MUTED}" text-anchor="end">{t:,.0f}</text>'.replace(",", "."))

    step = max(1, round(n / 8))
    for i, d in enumerate(dates):
        if i % step != 0 and i != n - 1:
            continue
        tx = xpos(i, ML, plot1_w)
        add(f'<text x="{tx:.1f}" y="{plot1_bottom + 16}" font-size="10.5" fill="{INK_MUTED}" text-anchor="middle">{esc(d)}</text>')

    pts = [(xpos(i, ML, plot1_w), y1(t)) for i, t in enumerate(totals)]
    area_d = f"M {pts[0][0]:.1f},{y1(vmin):.1f} " + " ".join(f"L {x:.1f},{y:.1f}" for x, y in pts) + f" L {pts[-1][0]:.1f},{y1(vmin):.1f} Z"
    add(f'<path d="{area_d}" fill="{SLOT_COLORS[0]}" opacity="0.10" stroke="none" />')
    line_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    add(f'<path d="{line_d}" fill="none" stroke="{SLOT_COLORS[0]}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />')
    for i, (px, py) in enumerate(pts):
        if i != 0 and i != n - 1:
            continue
        add(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="{SLOT_COLORS[0]}" stroke="{SURFACE}" stroke-width="2">'
            f'<title>{esc(dates[i])}: {totals[i]}</title></circle>')
    add(f'<text x="{pts[-1][0]:.1f}" y="{pts[-1][1] - 12:.1f}" font-size="13" font-weight="650" fill="{INK_PRIMARY}" text-anchor="end">{last["total"]:,.0f}</text>'.replace(",", "."))
    add(f'<text x="{pts[0][0]:.1f}" y="{pts[0][1] - 12:.1f}" font-size="11" fill="{INK_SECONDARY}" text-anchor="start">{rows[0]["total"]:,.0f}</text>'.replace(",", "."))

    # ================= CHART 2: version mix =================
    CH2_TOP = plot1_bottom + 30
    CH2_TITLE_H, CH2_MT, CH2_MB = 34, 8, 34
    LEGEND_H = 26
    plot2_top = CH2_TOP + CH2_TITLE_H + CH2_MT
    plot2_h = 220
    plot2_bottom = plot2_top + plot2_h
    plot2_w = W - ML - MR

    add(f'<text x="{ML}" y="{CH2_TOP + 16}" font-size="14" font-weight="650" fill="{INK_PRIMARY}">'
        f'Versionsverteilung &#252;ber Zeit</text>')
    other_note = " + Sonstige" if has_other else ""
    add(f'<text x="{ML}" y="{CH2_TOP + 30}" font-size="11" fill="{INK_SECONDARY}">'
        f'Top {len(top_versions)} Versionen{esc(other_note)}, gestapelt</text>')

    _, vmax2, ticks2 = nice_ticks(0, max(totals), 4)

    def y2(v: float) -> float:
        return plot2_bottom - (v / vmax2) * plot2_h

    for t in ticks2:
        ty = y2(t)
        add(f'<line x1="{ML}" x2="{W - MR}" y1="{ty:.1f}" y2="{ty:.1f}" stroke="{GRID}" stroke-width="1" />')
        add(f'<text x="{ML - 8}" y="{ty + 3:.1f}" font-size="10.5" fill="{INK_MUTED}" text-anchor="end">{t:,.0f}</text>'.replace(",", "."))

    for i, d in enumerate(dates):
        if i % step != 0 and i != n - 1:
            continue
        tx = xpos(i, ML, plot2_w)
        add(f'<text x="{tx:.1f}" y="{plot2_bottom + 16}" font-size="10.5" fill="{INK_MUTED}" text-anchor="middle">{esc(d)}</text>')

    cum = []
    for row in rows:
        acc = 0.0
        layer = {}
        for name in stack_order:
            v = row["versions"].get(name, 0) if name != "Sonstige" else (
                row["total"] - sum(row["versions"].get(t, 0) for t in top_versions)
            )
            layer[name] = (acc, acc + v)
            acc += v
        cum.append(layer)

    color_of = {**color_by_version, "Sonstige": OTHER_COLOR}
    for name in stack_order:
        top_line = [(xpos(i, ML, plot2_w), y2(cum[i][name][1])) for i in range(n)]
        bot_line = [(xpos(i, ML, plot2_w), y2(cum[i][name][0])) for i in range(n)][::-1]
        d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in top_line) + " L " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in bot_line) + " Z"
        add(f'<path d="{d}" fill="{color_of[name]}" stroke="none"><title>{esc(name)}</title></path>')
        top_stroke = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in top_line)
        add(f'<path d="{top_stroke}" fill="none" stroke="{SURFACE}" stroke-width="2" />')

    # direct end-labels for bands wide enough to hold text
    for name in stack_order:
        seg = cum[-1][name]
        if seg[1] - seg[0] < 16:
            continue
        mid_y = y2((seg[0] + seg[1]) / 2)
        lx = xpos(n - 1, ML, plot2_w) - 6
        add(f'<text x="{lx:.1f}" y="{mid_y + 4:.1f}" font-size="11" font-weight="650" fill="#ffffff" text-anchor="end">{esc(name)}</text>')

    # legend, newest-first, with current value
    lx0 = ML
    ly = plot2_bottom + 40
    add(f'<line x1="{ML}" x2="{W - MR}" y1="{plot2_bottom:.1f}" y2="{plot2_bottom:.1f}" stroke="{BASELINE}" stroke-width="1" />')
    cx = lx0
    row_h = 18
    max_w = W - MR
    for name in legend_order:
        value = last["versions"].get(name, 0) if name != "Sonstige" else (
            last["total"] - sum(last["versions"].get(t, 0) for t in top_versions)
        )
        label = f"{name} ({value:,.0f})".replace(",", ".")
        est_w = 16 + 6.2 * len(label) + 18
        if cx + est_w > max_w:
            cx = lx0
            ly += row_h
        add(f'<line x1="{cx:.1f}" x2="{cx + 14:.1f}" y1="{ly - 4:.1f}" y2="{ly - 4:.1f}" stroke="{color_of[name]}" stroke-width="3" stroke-linecap="round" />')
        add(f'<text x="{cx + 20:.1f}" y="{ly:.1f}" font-size="11.5" fill="{INK_SECONDARY}">{esc(label)}</text>')
        cx += est_w

    total_h = ly + 24
    add("</svg>")
    svg = "\n".join(parts)
    svg = svg.replace('viewBox="0 0 760 660"', f'viewBox="0 0 {W} {total_h:.0f}"')
    svg = svg.replace('height="660"', f'height="{total_h:.0f}"')
    return svg


def main() -> None:
    if not HISTORY_PATH.exists():
        return
    history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    if not history:
        return
    rows = history[-WINDOW:]
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(build_svg(rows), encoding="utf-8")


if __name__ == "__main__":
    main()
