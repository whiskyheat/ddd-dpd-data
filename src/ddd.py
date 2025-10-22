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

    @property
    def gesamtbewertung(self):
        kandidaten = [self.K1, self.K2, self.K3, self.K4, self.K5]

        return self._wertung(kandidaten)

    @property
    def bolwertung(self):
        bols = [self.Mikkel, self.Andi, self.Chat]

        return self._wertung(bols)

    def _wertung(self, cols: list) -> int:
        cols = list(filter(None, cols))

        punkte = (sum(cols) / len(cols)) * 4
        punkte = round(punkte)

        return punkte

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
