#!/usr/bin/env python3
"""
Das Perfekte Dinner – Namenssuche
═══════════════════════════════════════════════════════════
Durchsucht ALLE Episoden des Episodenguides auf fernsehserien.de
nach Namen und gibt die gefundenen Episoden samt zugehöriger Woche aus.

Verwendung:
    python3 dinner_suche.py Anna
    python3 dinner_suche.py Anna Thomas Sabine
    python3 dinner_suche.py "Ann-Katrin" Kevin Wibke

Optionen:
    --fresh   Cache loeschen und Seite neu laden

Beim ersten Aufruf werden ALLE Staffelseiten geladen (~22 Requests)
und als JSON-Cache gespeichert. Folgeaufrufe sind sofort schnell.
═══════════════════════════════════════════════════════════
"""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

# Hauptseite zum Ermitteln der Staffel-URLs und Serien-ID
BASE_URL = "https://www.fernsehserien.de"
GUIDE_URL = BASE_URL + "/das-perfekte-dinner/episodenguide"
CACHE_FILE = Path("cache/dinner_episoden.json")
CACHE_VERSION = 3  # erhöhen wenn sich woche_key-Logik ändert

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "de-DE,de;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": GUIDE_URL,
}

# ──────────────────────────────────────────────────────────
# HTTP
# ──────────────────────────────────────────────────────────


def get(url: str, retries: int = 3) -> str:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            print(f"     HTTP {e.code} bei {url}")
            if e.code in (429, 503):
                wait = 5 * (attempt + 1)
                print(f"     Warte {wait}s …")
                time.sleep(wait)
            else:
                raise
        except Exception:
            if attempt < retries - 1:
                time.sleep(2)
            else:
                raise
    raise RuntimeError(f"Zu viele Fehlversuche: {url}")


# ──────────────────────────────────────────────────────────
# HTML-Parsing
# ──────────────────────────────────────────────────────────


def extract_ort(title: str) -> str:
    """
    Extrahiert den Ort aus einem Episodentitel.

    Formate:
      "Tag 1: Anna, Berlin"                    → "Berlin"
      "Tag 1: Onur aus Frankfurt"               → "Frankfurt"
      "Das Weihnachtsmenü, Tag 1: Stefanie"     → ""  (kein Ort)
      "Wunschmenü: Tag 1: Melanie, Rhein-..."   → "Rhein-..."
    """
    # Ort nach Komma/Slash — aber nur wenn der Kandidat kein Tag-Titel ist
    ort_m = re.search(r"[,/]\s*(.+)$", title)
    if ort_m:
        kandidat = ort_m.group(1).strip()
        if not re.match(r"(?i)tag\s*\d|woche|profi|menu|menü", kandidat):
            return re.sub(r"^\((.+)\)$", r"\1", kandidat)
    # Fallback: "aus ORT" am Titelende
    ort_m = re.search(r"\baus\s+(\S.+)$", title, re.IGNORECASE)
    if ort_m:
        return ort_m.group(1).strip()
    return ""


def parse_episodes_from_html(html: str) -> list[dict]:
    """
    Extrahiert Episoden aus einer Staffelseite.

    Echte HTML-Struktur (ermittelt per Diagnose):
      <section itemprop="episode" ...>
        <a href="/das-perfekte-dinner/folgen/213-tag-1-iris-489352">
          <span itemprop="name">Tag 1: Iris</span>
        </a>
        <div itemprop="episodeNumber" content="213">Folge 213</div>
        <ea-angabe-datum>Mo. 01.01.2007</ea-angabe-datum>
      </section>
    """
    episodes = []
    seen = set()

    # Jeden <section itemprop="episode">...</section> Block einzeln verarbeiten
    section_pattern = re.compile(
        r'<section\s[^>]*itemprop="episode"[^>]*>([\s\S]*?)</section>', re.DOTALL
    )

    for sec in section_pattern.finditer(html):
        block = sec.group(1)

        # URL-Pfad und Slug
        url_m = re.search(
            r'href="(/das-perfekte-dinner/folgen/(\d+(?:[ab]?)-[^"]+))"', block
        )
        if not url_m:
            continue
        url_path = url_m.group(1)
        slug = url_m.group(2)

        # Folgennummer
        folge_m = re.match(r"^(\d+(?:[ab]?))", slug)
        folge_nr = folge_m.group(1) if folge_m else "?"

        # Titel aus <span itemprop="name">
        title_m = re.search(
            r'<span\s[^>]*itemprop="name"[^>]*>([\s\S]*?)</span>', block
        )
        if not title_m:
            continue
        title = re.sub(r"<[^>]+>", "", title_m.group(1)).strip()
        if not title:
            continue

        # Datum aus <ea-angabe-datum>Mo. 01.01.2007</ea-angabe-datum>
        datum_m = re.search(
            r"<ea-angabe-datum>[^<]*?(\d{2}\.\d{2}\.\d{4})</ea-angabe-datum>", block
        )
        if not datum_m:
            # Fallback: irgendein Datum im Block
            datum_m = re.search(r"(\d{2}\.\d{2}\.\d{4})", block)
        if not datum_m:
            continue
        datum = datum_m.group(1)

        key = (folge_nr, datum)
        if key in seen:
            continue
        seen.add(key)

        jahr = datum.split(".")[-1]
        ort = extract_ort(title)

        # woche_key wird später in assign_week_keys() gesetzt
        episodes.append(
            {
                "folge": folge_nr,
                "titel": title,
                "datum": datum,
                "url": BASE_URL + url_path,
                "jahr": jahr,
                "ort": ort,
                "woche_key": "",  # wird unten befüllt
            }
        )

    return episodes


def to_days(datum: str) -> int:
    """Datum TT.MM.JJJJ → Tage seit Epoche (für Abstandsberechnung)."""
    d, m, y = datum.split(".")
    # grobe Tagesanzahl reicht für ±7-Tage-Vergleich
    return int(y) * 365 + int(m) * 30 + int(d)


def assign_week_keys(episodes: list[dict]) -> None:
    """
    Weist jeder Episode einen woche_key zu.

    Alle Episoden werden nach Datum sortiert und in Gruppen von max. 6 Tagen
    Abstand eingeteilt. Der woche_key ist das Datum der ersten Episode der
    Gruppe, optional ergänzt um den Ort — so werden mehrere Besuche in
    derselben Stadt im selben Jahr korrekt als separate Wochen erkannt.
    Läuft in-place.
    """
    sorted_eps = sorted(episodes, key=lambda e: to_days(e["datum"]))

    group_start = None
    group_key = None

    for ep in sorted_eps:
        d = to_days(ep["datum"])
        if group_start is None or d - group_start > 5:
            group_start = d
            suffix = f"_{ep['ort']}" if ep["ort"] else ""
            group_key = f"{ep['datum']}{suffix}"
        ep["woche_key"] = group_key


def find_staffel_urls(html: str) -> list[str]:
    """
    Konstruiert alle Staffel-URLs direkt.

    Die Hauptseite zeigt im Staffel-Slider nur die letzten ~5 Staffeln als Links.
    Ältere Staffeln sind nur als Anker (#0, #1, …) verlinkt, nicht als href.
    Daher: Serien-ID aus den vorhandenen Links extrahieren, Staffelanzahl aus
    den Jahres-Ankern im Navigationsbereich zählen, URLs dann selbst bauen.
    """
    # Serien-ID aus einem der sichtbaren Staffel-Links holen
    serien_id_m = re.search(r"/episodenguide/\d+/(\d+)", html)
    if not serien_id_m:
        print("   WARNUNG: Serien-ID nicht gefunden, verwende Fallback 21260")
        serien_id = "21260"
    else:
        serien_id = serien_id_m.group(1)

    # Staffelanzahl: Jahres-Anker im Nav zählen → [2005](#0) [2006](#1) …
    # Jeder Anker entspricht einer Staffel (Index 0-basiert, Staffel 1-basiert)
    jahr_anker = re.findall(r"\[\d{4}\]\(#\d+\)", html)
    n_staffeln = len(jahr_anker)
    if n_staffeln == 0:
        # Fallback: höchste Staffelnummer aus sichtbaren Links
        nummern = re.findall(r"/episodenguide/(\d+)/" + serien_id, html)
        n_staffeln = max(int(x) for x in nummern) if nummern else 22

    base_path = re.search(r"(/[^/]+/episodenguide)/", html)
    serie_path = (
        base_path.group(1) if base_path else "/das-perfekte-dinner/episodenguide"
    )

    urls = [
        f"{BASE_URL}{serie_path}/{staffel}/{serien_id}"
        for staffel in range(1, n_staffeln + 1)
    ]
    return urls


# ──────────────────────────────────────────────────────────
# Vollständiges Laden aller Staffeln
# ──────────────────────────────────────────────────────────


def load_staffel(serie_path: str, serien_id: str, staffel_nr: int) -> list[dict]:
    """
    Lädt alle Episoden einer Staffel – iteriert über alle Unterseiten.
    Jede Staffelseite zeigt 25 Episoden; weitere unter /episodenguide/N/ID/2 usw.
    Stoppt wenn eine Unterseite 0 neue Episoden liefert oder einen 404 wirft.
    """
    all_eps: dict[str, dict] = {}
    seite = 1

    while True:
        if seite == 1:
            url = f"{BASE_URL}{serie_path}/{staffel_nr}/{serien_id}"
        else:
            url = f"{BASE_URL}{serie_path}/{staffel_nr}/{serien_id}/{seite}"

        try:
            html = get(url)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                break  # keine weitere Seite
            raise

        eps = parse_episodes_from_html(html)
        if not eps:
            break  # leere Seite → fertig

        neu = 0
        for ep in eps:
            if ep["folge"] not in all_eps:
                all_eps[ep["folge"]] = ep
                neu += 1

        if neu == 0:
            break  # Seite brachte nichts Neues → fertig

        seite += 1
        time.sleep(0.3)

    return list(all_eps.values())


def load_all_episodes(force_fresh: bool = False) -> list[dict]:
    """
    Lädt alle Episoden – aus Cache oder frisch von allen Staffel-Unterseiten.
    """
    if not force_fresh and CACHE_FILE.exists():
        cached = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        # Cache-Format: entweder plain list (v1) oder {"version":N, "episodes":[...]}
        if isinstance(cached, dict):
            version = cached.get("version", 1)
            data = cached.get("episodes", [])
        else:
            version = 1
            data = cached
        if version < CACHE_VERSION:
            print(f"   Cache veraltet (v{version} < v{CACHE_VERSION}), baue neu …")
        else:
            print(f"   Cache gefunden: {CACHE_FILE}")
            # ort + woche_key immer frisch berechnen (nicht aus Cache lesen)
            for ep in data:
                ep["ort"] = extract_ort(ep["titel"])
                ep["woche_key"] = ""
            assign_week_keys(data)
            print(f"   {len(data)} Episoden aus Cache geladen.")
            return data

    # 1. Hauptseite laden → Staffelanzahl + Serien-ID ermitteln
    print("   Lade Hauptseite …")
    try:
        main_html = get(GUIDE_URL)
    except Exception as e:
        print(f"\n   FEHLER: {e}")
        print("\n   Die Seite ist nicht erreichbar.")
        print("   Loesung: Fuehre das Skript einmalig mit Internetzugang aus.")
        sys.exit(1)

    staffel_urls = find_staffel_urls(main_html)
    if not staffel_urls:
        print("   WARNUNG: Keine Staffel-URLs gefunden.")
        sys.exit(1)

    # Serien-ID und Pfad aus einer bekannten URL extrahieren
    sample_m = re.search(r"(/[^/]+/episodenguide)/(\d+)/(\d+)", staffel_urls[0])
    serie_path = sample_m.group(1)
    serien_id = sample_m.group(3)
    n_staffeln = len(staffel_urls)
    print(f"   {n_staffeln} Staffeln gefunden (Serien-ID: {serien_id}).")

    all_episodes: dict[str, dict] = {}

    # 2. Jede Staffel Seite für Seite laden
    for staffel_nr in range(1, n_staffeln + 1):
        print(f"   Staffel {staffel_nr:>3} … ", end="", flush=True)
        try:
            eps = load_staffel(serie_path, serien_id, staffel_nr)
            neu = 0
            for ep in eps:
                if ep["folge"] not in all_episodes:
                    all_episodes[ep["folge"]] = ep
                    neu += 1
                else:
                    all_episodes[ep["folge"]].update(ep)
            print(f"{len(eps):>4} Episoden ({neu} neu)")
        except Exception as e:
            print(f"FEHLER: {e}")
        time.sleep(0.3)

    episodes = list(all_episodes.values())

    # Sortiere nach Folgennummer
    def folge_sort_key(ep):
        m = re.match(r"^(\d+)([ab]?)$", ep["folge"])
        return (int(m.group(1)), m.group(2)) if m else (0, "")

    episodes.sort(key=folge_sort_key)

    # Wochen-Schlüssel zuweisen
    assign_week_keys(episodes)

    # Cache speichern
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(
        json.dumps(
            {"version": CACHE_VERSION, "episodes": episodes},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\n   Gesamt: {len(episodes)} Episoden. Cache gespeichert: {CACHE_FILE}")
    return episodes


# ──────────────────────────────────────────────────────────
# Suche & Ausgabe
# ──────────────────────────────────────────────────────────


def search(names: list[str], episodes: list[dict]) -> list[str]:
    """
    Gibt alle woche_keys zurück, in denen ALLE gesuchten Namen vorkommen.
    Ein Name gilt als gefunden wenn er im Titel irgendeiner Episode der Woche steckt.
    """
    names_lower = [n.lower() for n in names]

    weeks: dict[str, list[dict]] = defaultdict(list)
    for ep in episodes:
        weeks[ep["woche_key"]].append(ep)

    matching = []
    for woche_key, week_eps in weeks.items():
        alle_titel = " ".join(ep["titel"].lower() for ep in week_eps)
        if all(name in alle_titel for name in names_lower):
            matching.append(woche_key)
    return matching


def group_by_week(episodes: list[dict]) -> dict:
    weeks = defaultdict(list)
    for ep in episodes:
        weeks[ep["woche_key"]].append(ep)
    return weeks


def extract_name_age(titel: str) -> tuple:
    """Gibt (Name, Alter) zurück. Alter ist '' wenn nicht angegeben."""
    m = re.search(r"(?:\d+\.\s*Tag|\bTag\s*\d+)[^:]*:\s*(.+)$", titel, re.IGNORECASE)
    raw = m.group(1).strip() if m else titel
    alter_m = re.search(r"\((\d+)\)", raw)
    alter = alter_m.group(1) if alter_m else ""
    name = re.sub(r"\s*\(\d+\)", "", raw)
    name = re.sub(r"\s*[,/]\s*.+$", "", name)
    name = re.sub(r"\s+aus\s+\S.*$", "", name, flags=re.IGNORECASE)
    return name.strip(), alter


def extract_name(titel: str) -> str:
    return extract_name_age(titel)[0]


def date_sort_key(ep: dict) -> tuple:
    d, mo, y = ep["datum"].split(".")
    m = re.match(r"^(\d+)([ab]?)$", ep["folge"])
    folge_int = int(m.group(1)) if m else 0
    return (y, mo, d, folge_int)


def print_week(week_eps: list[dict], hit_folgen: set[str]):
    week_eps = sorted(week_eps, key=date_sort_key)
    # Ort aus der ersten Episode mit bekanntem Ort, sonst "unbekannt"
    ort = next((ep["ort"] for ep in week_eps if ep["ort"]), "unbekannt")
    jahr = week_eps[0]["jahr"]
    datum_von = week_eps[0]["datum"]
    datum_bis = week_eps[-1]["datum"]
    print(f"  >> {ort}  ({datum_von} – {datum_bis})")
    print("  " + "─" * 54)
    for ep in week_eps:
        marker = "  [*]" if ep["folge"] in hit_folgen else "   - "
        name, alter = extract_name_age(ep["titel"])
        alter_str = f"({alter})" if alter else "     "
        print(f"{marker} Folge {ep['folge']:>5}  {ep['datum']}  {alter_str}  {name}")
    print()


# ──────────────────────────────────────────────────────────
# main
# ──────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Das Perfekte Dinner – Namenssuche",
        epilog="Beim ersten Aufruf werden alle Staffelseiten geladen (~22 Requests) "
        "und als JSON-Cache gespeichert. Folgeaufrufe sind sofort schnell.",
    )
    parser.add_argument(
        "namen",
        nargs="+",
        metavar="NAME",
        help="Ein oder mehrere Namen (max. 5)",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Cache löschen und Seite neu laden",
    )
    args = parser.parse_args()

    names = args.namen[:5]
    if len(args.namen) > 5:
        print("   Hinweis: Nur die ersten 5 Namen werden beruecksichtigt.\n")

    print("\n  Das Perfekte Dinner – Namenssuche")
    print(f"  Suchbegriffe: {', '.join(names)}\n")

    episodes = load_all_episodes(force_fresh=args.fresh)

    if not episodes:
        print("   Keine Episoden geladen.")
        sys.exit(1)

    matching_keys = search(names, episodes)

    if not matching_keys:
        print(
            f"\n  Keine Woche gefunden in der alle Namen vorkommen: {', '.join(names)}\n"
        )
        sys.exit(0)

    weeks = group_by_week(episodes)
    names_lower = [n.lower() for n in names]

    # hit_folgen: Episoden deren Titel einen der gesuchten Namen enthält
    hit_folgen = {
        ep["folge"]
        for ep in episodes
        if ep["woche_key"] in matching_keys
        and any(n in ep["titel"].lower() for n in names_lower)
    }

    # Wochen chronologisch sortieren
    def woche_sort_key(wk):
        eps = weeks.get(wk, [])
        return min(date_sort_key(ep) for ep in eps) if eps else ("", "", "", 0)

    matching_keys.sort(key=woche_sort_key)

    print(f"\n  {len(matching_keys)} Woche(n) mit allen Namen ({', '.join(names)}):")
    print("=" * 60)
    print()

    for wk in matching_keys:
        print_week(weeks.get(wk, []), hit_folgen)

    print("=" * 60)
    print("  [*] = gesuchter Name  |  - = gleiche Woche\n")


if __name__ == "__main__":
    main()
