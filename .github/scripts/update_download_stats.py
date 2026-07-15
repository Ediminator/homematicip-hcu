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
        "| Version | Installationen |",
        "| --- | --- |",
    ]
    for version, count in sorted_versions:
        lines.append(f"| {version} | {count} |")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    data = fetch_analytics()
    stats = data.get(DOMAIN, {"total": 0, "versions": {}})

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    for existing in OUTPUT_PATH.parent.glob("*"):
        if existing != OUTPUT_PATH:
            existing.unlink()

    OUTPUT_PATH.write_text(render(stats), encoding="utf-8")


if __name__ == "__main__":
    main()
