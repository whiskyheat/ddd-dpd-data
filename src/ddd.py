from dataclasses import dataclass


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

    summe: int | None

    mikkel: int | None
    andi: int | None
    chat: int | None

    person: str
    bemerkung: str
