"""
Detect cluster of ratings.
"""

import json
import argparse


def cluster(ratings):
    """
    Split all ratings into clusters.

    A cluster consists of all ratings where the pairwise difference in times is < 100.
    """
    # time of first rating
    global_time = int(min(ratings))

    clusters = []
    current_cluster = dict()

    for time, text in ratings.items():
        time = int(time)

        if time - global_time > 100:
            clusters.append(current_cluster)
            current_cluster = dict()

        current_cluster[time] = text
        global_time = time

    clusters.append(current_cluster)

    return clusters


def split(text: str, seps: list[str] = ["-", "/", " bis "]) -> list[str]:
    """
    Split a text by multiple seperators.

    Python's default split() only supports a single seperator.
    """
    for sep in seps:
        if sep in text:
            return text.split(sep)


def cluster_average(cluster):
    """
    Calculate the average rating of a cluster.

    If a rating is range, the first value is taken.
    """
    ratings = []
    for rating in cluster.values():
        if rating.isdecimal():
            ratings.append(int(rating))
        else:
            rating = split(rating)
            ratings.append(int(rating[0]))

    return sum(ratings) / len(ratings)


def describe(cluster):
    """Describe the cluster."""

    print(f"Cluster between {min(cluster)} and {max(cluster)}")
    print(f"Cluster length {max(cluster) - min(cluster)}")
    print(f"Number of ratings {len(cluster)}")
    print(f"Values: {cluster.values()}")

    avg = cluster_average(cluster)
    print(f"Average: {avg}")
    print(f"Rounded: {round(avg)}")

    print()


def is_valid_cluster(cluster):
    """A cluster is valid if it has more than one entry."""
    return len(cluster) > 1


if __name__ == "__main__":
    # Argument parser
    parser = argparse.ArgumentParser()
    parser.add_argument("file")
    # parser.add_argument("-o", "--outfile")
    args = parser.parse_args()

    # Open file
    with open(args.file, mode="r") as file:
        ratings = json.load(file)

    clusters = cluster(ratings)

    for cluster in clusters:
        # if is_valid_cluster(cluster):
        describe(cluster)
