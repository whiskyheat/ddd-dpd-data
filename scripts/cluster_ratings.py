"""
Gruppiert Ratings (Output von extract_ratings.py) in Cluster
anhand von Zeitlücken und speichert jeden Cluster als eigene JSON-Datei.

Usage:
    python cluster_ratings.py ratings.json
    cat ratings.json | python cluster_ratings.py
"""

import argparse
import json
import re
import sys
from statistics import median_high


def cluster(ratings: dict, gap: int = 60) -> list[dict]:
    """
    Teilt ratings anhand von Zeitlücken in Cluster auf.
    Eine neue Gruppe beginnt, wenn der Abstand zum vorherigen
    Eintrag größer als `gap` Sekunden ist.
    """
    sorted_items = sorted(ratings.items(), key=lambda x: int(x[0]))
    clusters = []
    current = {}
    last = None

    for time, text in sorted_items:
        if last is not None and int(time) - int(last) > gap:
            clusters.append(current)
            current = {}
        current[time] = text
        last = time

    if current:
        clusters.append(current)

    return clusters


def median_of_cluster(ratings):
    values = []
    for value in ratings.values():
        values.append(int(re.split(r"[/\-]", value)[0]))

    return median_high(values)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file", nargs="?", help="Input JSON (default: stdin)")
    parser.add_argument(
        "-o",
        "--outprefix",
        default=None,
        help="Prefix für Ausgabedateien (default: stdout)",
    )
    parser.add_argument(
        "--gap",
        type=int,
        default=60,
        help="Mindestlücke in Sekunden zwischen Clustern (default: 60)",
    )
    parser.add_argument(
        "--min-entries",
        type=int,
        default=3,
        help="Minimale Anzahl Einträge pro Cluster (default: 3)",
    )
    args = parser.parse_args()

    if args.file:
        with open(args.file) as f:
            ratings = json.load(f)
    else:
        ratings = json.load(sys.stdin)

    clusters = [c for c in cluster(ratings, gap=args.gap) if len(c) >= args.min_entries]

    for i, c in enumerate(clusters, start=1):
        if args.outprefix:
            outfile = f"{args.outprefix}_{i}.json"
            with open(outfile, "w") as f:
                json.dump(c, f, indent=4)
            print(f"Cluster {i}: {len(c)} Einträge → {outfile}", file=sys.stderr)
        else:
            sys.stdout.write(json.dumps(c, indent=4) + "\n")
            print(f"Cluster median: {median_of_cluster(c)}")
