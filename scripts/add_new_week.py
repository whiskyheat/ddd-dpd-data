import argparse
import csv
import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from scripts.cluster_ratings import cluster, median_of_cluster
from scripts.dinner_search import (
    extract_name_age,
    group_by_week,
    load_all_episodes,
    search,
)
from scripts.extract_ratings import extract_comments, is_rating
from scripts.parse_week import CSV_FIELDNAMES, get_next_wochen_id

EXPECTED_EPISODES_PER_WEEK = 5

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-s",
        "--streams",
        required=True,
        nargs="+",
        help="Liste der Streams der Woche",
    )
    parser.add_argument(
        "-p",
        "--personen",
        required=True,
        nargs="+",
        help="Liste meherer Personen, die in der Woche gekocht haben",
    )
    parser.add_argument("--clear-cache", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")

    return parser.parse_args()


def _url_to_streamid(urlstring: str) -> int:
    url = urlsplit(urlstring)
    id = url.path.split("/")[2]
    return int(id)


def _parse_streamids(streams: list[str]) -> list[int]:
    streamids = []
    for stream in streams:
        if stream.isdecimal():
            streamids.append(int(stream))
        else:
            streamids.append(_url_to_streamid(stream))

    return sorted(streamids)


def _date_from_rating_filename(path: Path) -> str:
    raw = path.stem.split("_")[2]
    return datetime.strptime(raw, "%Y-%m-%d").strftime("%d.%m.%Y")


def finde_woche(personen: list[str]):
    episodes = load_all_episodes()
    matching_keys = search(personen, episodes)

    if len(matching_keys) != 1:
        raise ValueError(f"Erwartete genau eine Woche, gefunden: {len(matching_keys)}")

    weeks = group_by_week(episodes)
    return weeks.get(matching_keys[0])


def finde_streams(streams: list[str]):
    streamids = _parse_streamids(streams)

    alle_streams = subprocess.check_output(
        ["twitch-dl", "videos", "dasdilettantischeduett", "--json", "--all"],
    )
    alle_streams = json.loads(alle_streams)["videos"]

    gefundene = [s for s in alle_streams if int(s["id"]) in streamids]
    if len(gefundene) != len(streamids):
        raise ValueError(f"Nicht alle Streams gefunden: {streamids}")

    return gefundene


def clear_cache():
    for file in Path("cache").glob("chat_*.json"):
        file.unlink()


def download_chat(streamid: str, streamdate: str) -> Path:
    file = Path(f"cache/chat_raw_{streamid}_{streamdate}.json")

    if not file.exists():
        subprocess.check_output(
            [
                "twitch-dl",
                "chat",
                "json",
                streamid,
                "-o",
                file,
            ],
        )

    return file


def filter_and_cluster_chat(file: Path, streamdate: str):
    with open(file, mode="r") as f:
        raw_chat = json.load(f)

    comments = extract_comments(raw_chat)
    ratings = {time: text for time, text in comments.items() if is_rating(text)}

    clusters = [c for c in cluster(ratings, gap=60) if len(c) >= 3]
    log.info(clusters)

    for idx, cl in enumerate(clusters):
        file_filtered = Path(f"cache/chat_ratings_{streamdate}_{idx}.json")
        if not file_filtered.exists():
            with open(file_filtered, mode="w") as out:
                json.dump(cl, out, indent=4)


def write_csv(woche, rating_files: list[Path]) -> None:
    bewertungen_file = Path("data/bewertungen.csv")

    wochen_id = get_next_wochen_id(bewertungen_file)
    with open(bewertungen_file, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)

        for tag, ratings_path in zip(woche, rating_files, strict=True):
            row = {field: "" for field in CSV_FIELDNAMES}

            row["WochenID"] = wochen_id
            row["FolgenID"] = tag["folge"]
            row["Ausstrahlung"] = tag["datum"]
            row["Reaction"] = _date_from_rating_filename(ratings_path)
            row["Ort"] = tag["ort"]

            name, alter = extract_name_age(tag["titel"])
            row["Person"] = name
            row["Alter"] = alter

            with open(ratings_path, mode="r") as json_f:
                data = json.load(json_f)
                row["C"] = median_of_cluster(data)

            print(row)

            writer.writerow(row)


if __name__ == "__main__":
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.clear_cache:
        clear_cache()

    log.info("Suche Woche")
    try:
        woche = finde_woche(args.personen)
    except ValueError as e:
        log.error(e)
        sys.exit(1)
    log.info("Woche gefunden")

    log.info("Suche Streams")
    try:
        streams = finde_streams(args.streams)
    except ValueError as e:
        log.error(e)
        sys.exit(1)
    log.info("Streams gefunden\n")

    for stream in streams:
        streamid = stream["id"]
        streamdate = stream["createdAt"][:10]
        log.info("%s %s", streamid, streamdate)

        file = download_chat(streamid, streamdate)
        filter_and_cluster_chat(file, streamdate)

    rating_files = sorted(Path("cache").glob("chat_ratings_*.json"))
    if len(rating_files) != EXPECTED_EPISODES_PER_WEEK:
        log.warning(
            "Es wurden Ratings zu %d Folgen gefunden, erwartet wurden %d.",
            len(rating_files),
            EXPECTED_EPISODES_PER_WEEK,
        )

    write_csv(woche, rating_files)


# TODO move files to chats/

# TODO open twitch stream at fitting position to get ratings
