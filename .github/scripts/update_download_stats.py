#!/usr/bin/env python3
"""Fetch Home Assistant analytics data and write a readable download stats report."""
from __future__ import annotations

import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ANALYTICS_URL = "https://analytics.home-assistant.io/custom_integrations.json"
DOMAIN = "hcu_integration"
OUTPUT_PATH = Path(".docs/downloads/download_stats.md")
HISTORY_PATH = Path(".docs/downloads/history.json")
CHART_PATH = Path(".docs/downloads/chart.svg")
MAX_HISTORY = 90  # keep enough runs around for the chart's rolling window
KEEP_FILES = {OUTPUT_PATH.name, HISTORY_PATH.name, CHART_PATH.name}


def fetch_analytics() -> dict:
    request = urllib.request.Request(
        ANALYTICS_URL, headers={"User-Agent": "homematicip-hcu-download-stats/1.0"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def version_key(version: str) -> tuple:
    match = re.match(r"^(\d+(?:\.\d+)*)(?:-(.+))?$", version)
    if not match:
        return ((), False, version)
    release = tuple(int(part) for part in match.group(1).split("."))
    pre_release = match.group(2)
    return (release, pre_release is None, pre_release or "")


def render(stats: dict) -> str:
    total = stats.get("total", 0)
    versions = stats.get("versions", {})
    sorted_versions = sorted(
        versions.items(), key=lambda item: version_key(item[0]), reverse=True
    )

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "# Download-Statistik",
        "",
        f"Stand: {timestamp}",
        "",
        f"**Gesamtanzahl Installationen: {total}**",
        "",
        "![Download-Statistik Verlauf](chart.svg)",
        "",
        "| Version | Installationen |",
        "| --- | --- |",
    ]
    for version, count in sorted_versions:
        lines.append(f"| {version} | {count} |")
    lines.append("")

    return "\n".join(lines), timestamp


def update_history(timestamp: str, stats: dict) -> None:
    """Append this run's totals to the rolling history the chart is built from."""
    history = []
    if HISTORY_PATH.exists():
        try:
            history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            history = []

    history.append(
        {
            "timestamp": f"{timestamp}",
            "total": stats.get("total", 0),
            "versions": stats.get("versions", {}),
        }
    )
    history = history[-MAX_HISTORY:]

    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    data = fetch_analytics()
    stats = data.get(DOMAIN, {"total": 0, "versions": {}})

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    for existing in OUTPUT_PATH.parent.glob("*"):
        if existing.is_file() and existing.name not in KEEP_FILES:
            existing.unlink()

    markdown, timestamp = render(stats)
    OUTPUT_PATH.write_text(markdown, encoding="utf-8")
    update_history(timestamp, stats)


if __name__ == "__main__":
    main()
