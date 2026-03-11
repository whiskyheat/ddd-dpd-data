"""
Parst die Ausgabe der Dinner-Suche und schreibt die Folgen in die CSV-Datei.

Usage:
    python woche_parsen.py < ausgabe.txt
"""

import argparse
import csv
import os
import re
import sys
from pathlib import Path

CSV_PATH = "data/bewertungen.csv"

CSV_FIELDNAMES = [
    "WochenID",
    "FolgenID",
    "Ausstrahlung",
    "Reaction",
    "Ort",
    "K1",
    "K2",
    "K3",
    "K4",
    "K5",
    "Summe",
    "M",
    "A",
    "C",
    "Bolwertung",
    "Person",
    "Geschlecht",
    "Alter",
    "Schlafrock?",
    "YT-Link",
]

FOLGE_PATTERN = re.compile(
    r"\s*\[\*\]\s+Folge\s+(\d+)\s+(\d{2}\.\d{2}\.\d{4})\s+(?:\((\d+)\)\s+)?(\S+)"
)
ORT_PATTERN = re.compile(r">>\s+(\S+)")


def parse_output(text: str) -> list[dict]:
    ort = None
    folgen = []

    ort_match = ORT_PATTERN.search(text)
    if ort_match:
        ort = ort_match.group(1)

    for line in text.splitlines():
        match = FOLGE_PATTERN.match(line)
        if match:
            folgen.append(
                {
                    "FolgenID": match.group(1),
                    "Ausstrahlung": match.group(2),
                    "Alter": match.group(3) or "",
                    "Person": match.group(4),
                    "Ort": ort,
                }
            )

    return folgen


def get_next_wochen_id(csv_path: str | Path) -> int:
    if not os.path.exists(csv_path):
        return 1
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    ids = [int(r["WochenID"]) for r in rows if r.get("WochenID", "").isdigit()]
    return max(ids) + 1 if ids else 1


def append_to_csv(csv_path: str, folgen: list[dict], wochen_id: int) -> None:
    file_exists = os.path.exists(csv_path)
    with open(csv_path, "a+", newline="", encoding="utf-8") as f:
        # Sicherstellen dass die Datei mit newline endet
        f.seek(0, 2)  # ans Ende springen
        if f.tell() > 0:
            f.seek(f.tell() - 1)
            last_char = f.read(1)
            if last_char != "\n":
                f.write("\n")
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        for folge in folgen:
            row = {field: "" for field in CSV_FIELDNAMES}
            row["WochenID"] = wochen_id
            row["FolgenID"] = folge["FolgenID"]
            row["Ausstrahlung"] = folge["Ausstrahlung"]
            row["Ort"] = folge["Ort"]
            row["Person"] = folge["Person"]
            row["Alter"] = folge["Alter"]
            writer.writerow(row)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", nargs="?", help="Eingabedatei (default: stdin)")
    args = parser.parse_args()

    if args.file:
        with open(args.file) as f:
            text = f.read()
    else:
        text = sys.stdin.read()

    folgen = parse_output(text)

    if not folgen:
        print("Keine Folgen gefunden.", file=sys.stderr)
        sys.exit(1)

    wochen_id = get_next_wochen_id(CSV_PATH)
    append_to_csv(CSV_PATH, folgen, wochen_id)
    print(f"WochenID {wochen_id}: {len(folgen)} Folgen hinzugefügt.")
