#!/usr/bin/env python3
"""
Capture a dated, gzipped snapshot of the FPL API.

The per-gameweek fields (transfers_in_event, transfers_out_event,
event_points, cost_change_event) reset at each deadline and cannot be
recovered later. That is the whole point of running this on a schedule.

Usage:
    python fpl_snapshot.py                # capture, label phase automatically
    python fpl_snapshot.py --expect pre   # exit 2 if this is not a pre-deadline run
    python fpl_snapshot.py --expect mid   # exit 2 if this is not a mid-week run
"""

import argparse
import datetime as dt
import gzip
import json
import pathlib
import sys
import urllib.error
import urllib.request

BASE = "https://fantasy.premierleague.com/api"
OUTDIR = pathlib.Path(__file__).resolve().parent / "data"
HEADERS = {"User-Agent": "fpl-snapshot/1.0 (personal research use)"}

# A run within this many hours of the next deadline counts as "pre".
PRE_WINDOW_HOURS = 36


def get(path: str):
    req = urllib.request.Request(f"{BASE}/{path}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def parse_utc(ts: str) -> dt.datetime:
    return dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))


def next_event(events, now):
    """The next gameweek by deadline. is_next is authoritative when present."""
    flagged = next((e for e in events if e.get("is_next")), None)
    if flagged:
        return flagged
    future = [e for e in events if parse_utc(e["deadline_time"]) > now]
    return min(future, key=lambda e: parse_utc(e["deadline_time"])) if future else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--expect", choices=["pre", "mid"], default=None)
    args = ap.parse_args()

    now = dt.datetime.now(dt.timezone.utc)

    try:
        bootstrap = get("bootstrap-static/")
        fixtures = get("fixtures/")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        print(f"FETCH FAILED: {exc}", file=sys.stderr)
        return 1

    events = bootstrap["events"]
    nxt = next_event(events, now)

    if nxt is None:
        gw, deadline, hours = 0, None, None
        phase = "offseason"
    else:
        gw = nxt["id"]
        deadline = nxt["deadline_time"]
        hours = (parse_utc(deadline) - now).total_seconds() / 3600
        phase = "pre" if hours <= PRE_WINDOW_HOURS else "mid"

    payload = {
        "captured_utc": now.isoformat(),
        "next_gw": gw,
        "deadline_utc": deadline,
        "hours_to_deadline": round(hours, 2) if hours is not None else None,
        "phase": phase,
        "teams": bootstrap["teams"],
        "element_types": bootstrap["element_types"],
        "events": events,
        "elements": bootstrap["elements"],
        "fixtures": fixtures,
    }

    OUTDIR.mkdir(parents=True, exist_ok=True)
    name = f"{now:%Y-%m-%d}_gw{gw:02d}_{phase}.json.gz"
    path = OUTDIR / name
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        json.dump(payload, fh, separators=(",", ":"))

    size_mb = path.stat().st_size / 1_000_000
    hrs = f"{hours:.1f}h" if hours is not None else "n/a"
    print(f"wrote {name} ({size_mb:.1f} MB) | next GW{gw} in {hrs} | phase={phase}")

    if args.expect and args.expect != phase:
        print(
            f"GUARDRAIL: expected a '{args.expect}' run but this is '{phase}'. "
            "Most likely a catch-up run fired late. Snapshot kept and labelled "
            "correctly, but check the schedule.",
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
