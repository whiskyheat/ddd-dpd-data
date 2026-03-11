"""
Extract comments representing ratings from a twitch chat.
"""

import argparse
import json
import sys


def extract_comments(raw_chat: dict) -> dict[int, str]:
    """
    Given the original chat json file as dict,
    extract time and text for every chat message and drop everything else.
    """
    filtered = dict()
    comments = raw_chat["comments"]

    for comment in comments:
        time = comment["contentOffsetSeconds"]
        try:
            text = comment["message"]["fragments"][0]["text"]
        except (IndexError, KeyError):
            continue
        filtered[time] = text

    return filtered


def _split_rating(text: str, seps: list[str] = ["-", "/", " bis "]) -> list[str]:
    """Split a text by multiple separators."""
    for sep in seps:
        if sep in text:
            return text.split(sep)
    raise ValueError("cannot split text")


def is_rating(comment: str) -> bool:
    """
    Check if a comment is a rating.

    A comment is a rating if it is
    - a single number between 1 and 10,
    - a range like "5-6" or "5 bis 6",
    - out of ten, like "5/10".
    """
    try:
        parts = _split_rating(comment) if not comment.isdecimal() else [comment]
    except ValueError:
        return False

    return all(
        part.strip().isdecimal() and 1 <= int(part.strip()) <= 10 for part in parts
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", help="Twitch-Chat JSON-Datei")
    parser.add_argument("-o", "--outfile", help="Ausgabedatei (default: stdout)")
    args = parser.parse_args()

    with open(args.file, mode="r") as f:
        raw_chat = json.load(f)

    comments = extract_comments(raw_chat)
    ratings = {time: text for time, text in comments.items() if is_rating(text)}

    if args.outfile:
        with open(args.outfile, mode="w") as out:
            json.dump(ratings, out, indent=4)
    else:
        json.dump(comments, sys.stdout, indent=4)
