#!/usr/bin/env python3
"""Turn the newest snapshot in data/ into readable CSVs."""

import csv
import gzip
import json
import pathlib
import sys

DATA = pathlib.Path(__file__).resolve().parent / "data"

POS = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}

COLUMNS = [
    "web_name", "team", "pos", "price", "owned_pct", "total_points",
    "form", "minutes", "starts", "goals_scored", "assists",
    "expected_goals", "expected_assists", "expected_goal_involvements",
    "expected_goals_conceded", "defensive_contribution",
    "transfers_in_event", "transfers_out_event", "net_transfers_event",
    "cost_change_event", "status", "chance_of_playing_next_round",
]


def newest_snapshot() -> pathlib.Path:
    files = sorted(DATA.glob("*.json.gz"))
    if not files:
        print("no snapshots found in data/", file=sys.stderr)
        sys.exit(1)
    return files[-1]


def main() -> int:
    src = newest_snapshot()
    with gzip.open(src, "rt", encoding="utf-8") as fh:
        snap = json.load(fh)

    teams = {t["id"]: t["short_name"] for t in snap["teams"]}

    rows = []
    for e in snap["elements"]:
        tin = e.get("transfers_in_event", 0) or 0
        tout = e.get("transfers_out_event", 0) or 0
        rows.append({
            "web_name": e["web_name"],
            "team": teams.get(e["team"], "?"),
            "pos": POS.get(e["element_type"], "?"),
            "price": e["now_cost"] / 10,
            "owned_pct": e.get("selected_by_percent"),
            "total_points": e.get("total_points"),
            "form": e.get("form"),
            "minutes": e.get("minutes"),
            "starts": e.get("starts"),
            "goals_scored": e.get("goals_scored"),
            "assists": e.get("assists"),
            "expected_goals": e.get("expected_goals"),
            "expected_assists": e.get("expected_assists"),
            "expected_goal_involvements": e.get("expected_goal_involvements"),
            "expected_goals_conceded": e.get("expected_goals_conceded"),
            "defensive_contribution": e.get("defensive_contribution"),
            "transfers_in_event": tin,
            "transfers_out_event": tout,
            "net_transfers_event": tin - tout,
            "cost_change_event": (e.get("cost_change_event") or 0) / 10,
            "status": e.get("status"),
            "chance_of_playing_next_round": e.get("chance_of_playing_next_round"),
        })

    rows.sort(key=lambda r: float(r["owned_pct"] or 0), reverse=True)

    stamp = src.name.split(".")[0]
    for out in (DATA / "latest.csv", DATA / f"{stamp}.csv"):
        with out.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=COLUMNS)
            w.writeheader()
            w.writerows(rows)

    print(f"wrote latest.csv and {stamp}.csv from {src.name} ({len(rows)} players)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
