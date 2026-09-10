"""Render public GitHub contribution counts without an external image service.

Run from the repository root: python3 scripts/update_contributions.py
Only replace the existing SVG after fetching and validating all 31 days.
"""

import math
import re
from datetime import date, timedelta
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen


class Contributions(HTMLParser):
    def __init__(self):
        super().__init__()
        self.dates = {}
        self.counts = {}
        self.target = None
        self.text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "td" and "data-date" in attrs:
            self.dates[attrs["id"]] = date.fromisoformat(attrs["data-date"])
        if tag == "tool-tip":
            self.target = attrs.get("for")
            self.text = []

    def handle_data(self, data):
        if self.target:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag == "tool-tip" and self.target:
            match = re.match(r"^(No|[\d,]+) contributions? on\b", "".join(self.text).strip())
            if match:
                self.counts[self.target] = int(match[1].replace(",", "")) if match[1] != "No" else 0
            self.target = None


def parse_days(html):
    parser = Contributions()
    parser.feed(html)
    if not parser.dates:
        raise ValueError("GitHub returned no contribution calendar; keeping previous SVG")
    # Use the calendar's last day, which reflects GitHub's date boundary.
    end = max(parser.dates.values())
    days = {day: parser.counts[key] for key, day in parser.dates.items() if key in parser.counts}
    expected = [end - timedelta(days=i) for i in reversed(range(31))]
    if any(day not in days for day in expected):
        raise ValueError("Incomplete contribution counts; keeping previous SVG")
    return [(day, days[day]) for day in expected]


def render(days):
    top = max(4, math.ceil(max(count for _, count in days) / 4) * 4)
    points = [(60 + i * 30, 270 - count / top * 170) for i, (_, count) in enumerate(days)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    title = "Contribution Activity"
    subtitle = f"{days[0][0]:%b %d} – {days[-1][0]:%b %d, %Y} · {sum(n for _, n in days):,} contributions"
    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="340" viewBox="0 0 1000 340" role="img" aria-labelledby="title desc">',
        f'<title id="title">{title}</title>',
        f'<desc id="desc">{escape(subtitle)}. Daily counts from the public GitHub contribution calendar.</desc>',
        '<rect width="1000" height="340" rx="8" fill="#1a1b27"/>',
        '<g font-family="Segoe UI, Arial, sans-serif">',
        f'<text x="35" y="40" fill="#70a5fd" font-size="23" font-weight="600">{title}</text>',
        f'<text x="35" y="66" fill="#a9b1d6" font-size="14">{escape(subtitle)}</text>',
    ]
    for tick in range(5):
        y = 270 - tick * 42.5
        svg += [
            f'<path d="M60 {y} H960" stroke="#303448"/>',
            f'<text x="48" y="{y + 5}" text-anchor="end" fill="#a9b1d6" font-size="12">{top * tick // 4}</text>',
        ]
    svg += [
        f'<polygon points="60,270 {line} 960,270" fill="#70a5fd" opacity="0.12"/>',
        f'<polyline points="{line}" fill="none" stroke="#70a5fd" stroke-width="2.5" stroke-linejoin="round"/>',
    ]
    for i, ((day, count), (x, y)) in enumerate(zip(days, points)):
        svg.append(f'<circle cx="{x}" cy="{y:.1f}" r="3" fill="#bf91f3"><title>{day}: {count} contributions</title></circle>')
        if i % 5 == 0:
            svg.append(f'<text x="{x}" y="294" text-anchor="middle" fill="#a9b1d6" font-size="12">{day:%b %d}</text>')
    svg.append('<text x="960" y="322" text-anchor="end" fill="#a9b1d6" font-size="11">Source: GitHub public contribution calendar</text>')
    return "\n".join(svg + ["</g>", "</svg>", ""])


if __name__ == "__main__":
    request = Request("https://github.com/users/WengYuehTing/contributions", headers={"User-Agent": "profile-contribution-chart", "Accept-Language": "en-US"})
    with urlopen(request, timeout=30) as response:
        days = parse_days(response.read().decode("utf-8"))
    output = Path(__file__).resolve().parents[1] / "assets/contributions.svg"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(days), encoding="utf-8")
    print(f"Updated {output.name}: {days[0][0]} to {days[-1][0]}")
