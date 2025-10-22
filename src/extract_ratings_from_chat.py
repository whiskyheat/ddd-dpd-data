"""
Extract comments representing ratings from a twitch chat.
"""

import json
import argparse


def extract_comments(raw_chat: dict) -> dict:
    """
    Given the original chat json file as dict,
    extract time and text for every chat message and drop everything else.

    The orginal chat json file can be downloaded using the `twitch-dl` utility.
    It contains a lot of metadata unnecessary for our porpuses.
    """
    filtered = dict()
    comments = raw_chat["comments"]

    for comment in comments:
        # get time
        time = comment["contentOffsetSeconds"]

        # get comment text
        # sometimes there is no text, ignore them
        try:
            text = comment["message"]["fragments"][0]["text"]
        except IndexError:
            # print(comment)
            continue

        # add to dict
        filtered[time] = text

    return filtered


def split(text: str, seps: list[str] = ["-", "/", " bis "]) -> list[str]:
    """
    Split a text by multiple seperators.

    Python's default split() only supports a single seperator.
    """
    for sep in seps:
        if sep in text:
            return text.split(sep)


def is_rating(comment: str) -> bool:
    """
    Check if a comment is a rating.

    A comment is a rating if it is
    - a single number between "0" and "10",
    - a range like "5-6" or "5 bis 10",
    - out of ten, like "5/10".
    """

    if comment.isdecimal():
        decomposed = [comment]
    else:
        decomposed = split(comment)
        if decomposed is None:
            return False

    # check that everything is an integer between 0 and 10
    return all([c.isdecimal() and 0 <= int(c) <= 10 for c in decomposed])


def outfile_name() -> str:
    """Name the output file."""

    if args.outfile:
        # name of outputfile is given as argument
        outfile = args.outfile
    else:
        # check if a number is in the input name
        for part in args.file.split("_"):
            if part.isdecimal():
                number = part
                outfile = f"chat_ratings_{number}.json"
                break
        else:
            raise ValueError("No outfile given and no number in input file.")
    return outfile


if __name__ == "__main__":
    # Argument parser
    parser = argparse.ArgumentParser()
    parser.add_argument("file")
    parser.add_argument("-o", "--outfile")
    args = parser.parse_args()

    # Open file
    with open(args.file, mode="r") as raw_json:
        raw_chat = json.load(raw_json)

    # extract comments
    comments = extract_comments(raw_chat)

    # filer comments
    comments = {time: text for time, text in comments.items() if is_rating(text)}

    # save
    with open(outfile_name(), mode="w") as out:
        json.dump(comments, out, indent=4)
