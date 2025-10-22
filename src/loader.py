import pandas as pd

from ddd import Tag


def load_data(as_df: bool = False):
    data = pd.read_csv("../data/bewertungen.csv")

    # convert to objects
    if not as_df:
        data = [Tag.from_dataframe(row) for _, row in data.iterrows()]

    return data
