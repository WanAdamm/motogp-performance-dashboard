"""Circuit metadata and locally bundled hero artwork."""

from __future__ import annotations

from base64 import b64encode
from functools import cache
from pathlib import Path
from typing import NamedTuple


class Circuit(NamedTuple):
    country: str
    venue: str
    source_url: str
    credit: str
    license_name: str
    license_url: str


CIRCUITS = {
    "THA": Circuit(
        "Thailand",
        "Buriram",
        "https://commons.wikimedia.org/wiki/File:Buriram_circuit_map.svg",
        "Gpmat",
        "CC BY-SA 3.0",
        "https://creativecommons.org/licenses/by-sa/3.0/",
    ),
    "ARG": Circuit(
        "Argentina",
        "Termas de Rio Hondo",
        "https://commons.wikimedia.org/wiki/File:Termas_de_R%C3%ADo_Hondo.svg",
        "Gustavo Girardelli and OpenStreetMap contributors",
        "CC BY-SA 4.0",
        "https://creativecommons.org/licenses/by-sa/4.0/",
    ),
    "AME": Circuit(
        "USA",
        "COTA",
        "https://commons.wikimedia.org/wiki/"
        "File:F1_circuits_2014-2018_-_Circuit_of_the_Americas_(version_2).svg",
        "Firkin",
        "CC0 1.0",
        "https://creativecommons.org/publicdomain/zero/1.0/",
    ),
    "QAT": Circuit(
        "Qatar",
        "Lusail",
        "https://commons.wikimedia.org/wiki/File:Lusail_International_Circuit_2023.svg",
        "Will Pittenger and Gpmat",
        "CC BY-SA 3.0",
        "https://creativecommons.org/licenses/by-sa/3.0/",
    ),
    "SPA": Circuit(
        "Spain",
        "Jerez",
        "https://commons.wikimedia.org/wiki/File:Circuito_de_Jerez_v2.svg",
        "Will Pittenger, Uppsalo, and Gpmat",
        "CC BY-SA 4.0",
        "https://creativecommons.org/licenses/by-sa/4.0/",
    ),
    "FRA": Circuit(
        "France",
        "Le Mans",
        "https://commons.wikimedia.org/wiki/File:Bugatti_Circuit.svg",
        "Will Pittenger",
        "CC BY-SA 3.0",
        "https://creativecommons.org/licenses/by-sa/3.0/",
    ),
    "GBR": Circuit(
        "Great Britain",
        "Silverstone",
        "https://commons.wikimedia.org/wiki/File:Silverstone_Circuit_moto_intl_pits.svg",
        "Astradaen and Gpmat",
        "CC BY-SA 3.0",
        "https://creativecommons.org/licenses/by-sa/3.0/",
    ),
    "ARA": Circuit(
        "Spain",
        "MotorLand Aragon",
        "https://commons.wikimedia.org/wiki/File:Motorland_Arag%C3%B3n_FIM.svg",
        "Willtron",
        "CC BY-SA 3.0",
        "https://creativecommons.org/licenses/by-sa/3.0/",
    ),
    "ITA": Circuit(
        "Italy",
        "Mugello",
        "https://commons.wikimedia.org/wiki/File:Mugello_Racing_Circuit_track_map.svg",
        "Will Pittenger",
        "CC BY-SA 3.0",
        "https://creativecommons.org/licenses/by-sa/3.0/",
    ),
    "NED": Circuit(
        "Netherlands",
        "Assen",
        "https://commons.wikimedia.org/wiki/File:TT_Circuit_Assen_moto.svg",
        "Will Pittenger and Gpmat",
        "CC BY-SA 3.0",
        "https://creativecommons.org/licenses/by-sa/3.0/",
    ),
    "GER": Circuit(
        "Germany",
        "Sachsenring",
        "https://commons.wikimedia.org/wiki/File:Sachsenring.svg",
        "Will Pittenger and OpenStreetMap contributors",
        "CC BY-SA 2.0",
        "https://creativecommons.org/licenses/by-sa/2.0/",
    ),
    "CZE": Circuit(
        "Czechia",
        "Brno",
        "https://commons.wikimedia.org/wiki/File:Brno_(formerly_Masaryk%C5%AFv_okruh).svg",
        "Will Pittenger",
        "CC BY-SA 3.0",
        "https://creativecommons.org/licenses/by-sa/3.0/",
    ),
    "AUT": Circuit(
        "Austria",
        "Red Bull Ring",
        "https://commons.wikimedia.org/wiki/File:Red_Bull_Ring_moto_2022.svg",
        "Pitlane02 and contributors",
        "CC BY-SA 3.0",
        "https://creativecommons.org/licenses/by-sa/3.0/",
    ),
    "HUN": Circuit(
        "Hungary",
        "Balaton Park",
        "https://commons.wikimedia.org/wiki/"
        "File:Balaton_Park_Circuit_layout_(motorcycle_racing).svg",
        "VulcanSphere",
        "CC BY-SA 4.0",
        "https://creativecommons.org/licenses/by-sa/4.0/",
    ),
    "CAT": Circuit(
        "Spain",
        "Barcelona-Catalunya",
        "https://commons.wikimedia.org/wiki/File:Circuit_de_Catalunya_moto_2021.svg",
        "Will Pittenger and contributors",
        "CC BY-SA 3.0",
        "https://creativecommons.org/licenses/by-sa/3.0/",
    ),
    "RSM": Circuit(
        "San Marino",
        "Misano",
        "https://commons.wikimedia.org/wiki/File:Misano_World_Circuit.svg",
        "Will Pittenger",
        "CC BY-SA 3.0",
        "https://creativecommons.org/licenses/by-sa/3.0/",
    ),
    "JPN": Circuit(
        "Japan",
        "Motegi",
        "https://commons.wikimedia.org/wiki/File:Twin_Ring_Motegi_road_course_map.svg",
        "Spyder_Monkey",
        "Public domain",
        "https://commons.wikimedia.org/wiki/File:Twin_Ring_Motegi_road_course_map.svg",
    ),
    "INA": Circuit(
        "Indonesia",
        "Mandalika",
        "https://commons.wikimedia.org/wiki/File:Mandalika_International_Street_Circuit.svg",
        "Alex9089 and VulcanSphere",
        "CC BY-SA 4.0",
        "https://creativecommons.org/licenses/by-sa/4.0/",
    ),
    "AUS": Circuit(
        "Australia",
        "Phillip Island",
        "https://commons.wikimedia.org/wiki/File:Phillip_Island_Grand_Prix_Circuit_v2022.svg",
        "Will Pittenger, Uppsalo, and Gpmat",
        "CC BY-SA 3.0",
        "https://creativecommons.org/licenses/by-sa/3.0/",
    ),
    "MAL": Circuit(
        "Malaysia",
        "Sepang",
        "https://commons.wikimedia.org/wiki/File:Circuit_Sepang_1999.svg",
        "AlexJ",
        "CC0 1.0",
        "https://creativecommons.org/publicdomain/zero/1.0/",
    ),
    "POR": Circuit(
        "Portugal",
        "Portimao",
        "https://commons.wikimedia.org/wiki/File:Aut%C3%B3dromo_do_Algarve_moto.svg",
        "Sentoan and Gpmat",
        "CC BY-SA 4.0",
        "https://creativecommons.org/licenses/by-sa/4.0/",
    ),
    "VAL": Circuit(
        "Spain",
        "Ricardo Tormo",
        "https://commons.wikimedia.org/wiki/File:Valencia_(Ricardo_Tormo)_track_map.svg",
        "Will Pittenger",
        "CC BY-SA 3.0",
        "https://creativecommons.org/licenses/by-sa/3.0/",
    ),
}

_ASSET_ROOT = Path(__file__).parent / "assets" / "circuits"


@cache
def circuit_image_uri(event_code: str, graphite: str, cobalt: str) -> str | None:
    """Return selected circuit artwork as a theme-colored SVG data URI."""

    if event_code not in CIRCUITS:
        return None
    svg = (_ASSET_ROOT / f"{event_code}.svg").read_text(encoding="utf-8")
    svg = svg.replace("#000000", graphite).replace("#1457d9", cobalt)
    return "data:image/svg+xml;base64," + b64encode(svg.encode()).decode()
