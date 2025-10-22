from dataclasses import dataclass
import math


@dataclass
class Tag:
    WochenID: int
    FolgenID: int
    Datum: str
    Ort: str | None

    K1: int | None
    K2: int | None
    K3: int | None
    K4: int | None
    K5: int | None

    Summe: int | None

    Mikkel: int | None
    Andi: int | None
    Chat: int | None

    Person: str
    Bemerkung: str

    @classmethod
    def from_dataframe(cls, row) -> "Tag":
        data = row.to_dict()

        # rename columns
        data["Mikkel"] = data.pop("M")
        data["Andi"] = data.pop("A")
        data["Chat"] = data.pop("C")

        # floats to int
        for k, v in data.items():
            if isinstance(v, float):
                if math.isnan(v):
                    data[k] = None
                else:
                    data[k] = int(v)

        return cls(**data)
