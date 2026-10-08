"""Build a repository-owned SVG from GitHub's actual contribution calendar."""

import argparse
from datetime import date, timedelta
from html import escape
import json
import math
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

QUERY = """query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}"""


def fetch_calendar(login):
    response = subprocess.run(
        ["gh", "api", "graphql", "--input", "-"],
        input=json.dumps({"query": QUERY, "variables": {"login": login}}),
        text=True, capture_output=True, timeout=60, check=True,
    )
    payload = json.loads(response.stdout)
    if payload.get("errors"):
        raise ValueError("GitHub returned GraphQL errors")
    return payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def recent_days(calendar):
    counts = {}
    for week in calendar["weeks"]:
        for day in week["contributionDays"]:
            day_date = date.fromisoformat(day["date"])
            count = day["contributionCount"]
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError("Invalid contribution count")
            if day_date in counts:
                raise ValueError("Duplicate calendar date")
            counts[day_date] = count
    if not counts:
        raise ValueError("Empty contribution calendar")
    end = max(counts)
    days = [(end - timedelta(days=offset), counts.get(end - timedelta(days=offset)))
            for offset in range(29, -1, -1)]
    if any(count is None for _, count in days):
        raise ValueError("Incomplete 30-day contribution calendar")
    return days


def render(login, days):
    left, right, top, bottom = 68, 1060, 112, 274
    total = sum(count for _, count in days)
    active = sum(count > 0 for _, count in days)
    ceiling = max(10, math.ceil(max(count for _, count in days) / 10) * 10)
    points = [(left + i * (right-left)/29, bottom-count*(bottom-top)/ceiling)
              for i, (_, count) in enumerate(days)]
    coordinates = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    area = f"{left},{bottom} {coordinates} {right},{bottom}"
    parts = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="350" viewBox="0 0 1100 350" role="img" aria-labelledby="title description">
<title id="title">{escape(login)} — recent GitHub activity</title>
<desc id="description">Daily GitHub contributions from {days[0][0]} through {days[-1][0]}. {total} contributions across {active} active days. Counts come from GitHub's contribution calendar.</desc>
<rect x="1" y="1" width="1098" height="348" rx="16" fill="#0d1117" stroke="#30363d"/>
<g font-family="Segoe UI, Arial, sans-serif">
<text x="32" y="40" font-size="23" font-weight="700" fill="#e6edf3">Recent GitHub activity</text>
<text x="32" y="67" font-size="14" fill="#9da7b3">Daily contributions · {days[0][0]} to {days[-1][0]}</text>
<text x="1060" y="40" text-anchor="end" font-size="23" font-weight="700" fill="#3fb950">{total:,}</text>
<text x="1060" y="67" text-anchor="end" font-size="14" fill="#9da7b3">contributions · {active}/30 active days</text>''']
    for fraction in (0, 0.25, 0.5, 0.75, 1):
        y = bottom - fraction*(bottom-top)
        parts.append(f'<line x1="{left}" y1="{y}" x2="{right}" y2="{y}" stroke="#21262d"/>')
        parts.append(f'<text x="54" y="{y+5}" text-anchor="end" font-size="12" fill="#9da7b3">{ceiling*fraction:g}</text>')
    parts.append(f'<polygon points="{area}" fill="#238636" opacity="0.16"/>')
    parts.append(f'<polyline points="{coordinates}" fill="none" stroke="#3fb950" stroke-width="3" stroke-linejoin="round"/>')
    for (day, count), (x, y) in zip(days, points):
        parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3" fill="#e6edf3"><title>{day}: {count} contributions</title></circle>')
    for i in (0, 7, 14, 21, 29):
        parts.append(f'<text x="{points[i][0]:.2f}" y="299" text-anchor="middle" font-size="12" fill="#9da7b3">{days[i][0].strftime("%b %d")}</text>')
    parts.append('<text x="32" y="331" font-size="12" fill="#9da7b3">Source: GitHub contribution calendar · refreshed daily · includes today’s partial activity</text></g></svg>\n')
    svg = "\n".join(parts)
    ET.fromstring(svg)
    return svg


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user", default="RamiNoodle733")
    parser.add_argument("--input", type=Path, help="Optional calendar JSON for offline verification")
    parser.add_argument("--output", type=Path, default=Path("assets/activity-graph.svg"))
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", args.user):
        parser.error("Invalid GitHub username")
    calendar = json.loads(args.input.read_text(encoding="utf-8")) if args.input else fetch_calendar(args.user)
    days = recent_days(calendar)
    svg = render(args.user, days)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists() and args.output.read_text(encoding="utf-8") == svg:
        print("Contribution graph unchanged")
        return
    temporary = args.output.with_suffix(".tmp")
    temporary.write_text(svg, encoding="utf-8", newline="\n")
    temporary.replace(args.output)
    print(f"Updated contribution graph: {days[0][0]} to {days[-1][0]}")


if __name__ == "__main__":
    main()
