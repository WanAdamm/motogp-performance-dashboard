from __future__ import annotations

from base64 import b64decode
from xml.etree import ElementTree

from dashboard.circuits import CIRCUITS, circuit_image_uri

EVENT_CODES = {
    "AME",
    "ARA",
    "ARG",
    "AUS",
    "AUT",
    "CAT",
    "CZE",
    "FRA",
    "GBR",
    "GER",
    "HUN",
    "INA",
    "ITA",
    "JPN",
    "MAL",
    "NED",
    "POR",
    "QAT",
    "RSM",
    "SPA",
    "THA",
    "VAL",
}


def test_circuit_artwork_covers_configured_events() -> None:
    assert set(CIRCUITS) == EVENT_CODES

    for event_code, circuit in CIRCUITS.items():
        uri = circuit_image_uri(event_code, "#123456", "#abcdef")
        assert uri is not None
        svg = b64decode(uri.partition(",")[2]).decode()
        ElementTree.fromstring(svg)
        assert "#123456" in svg
        assert "#abcdef" in svg
        assert circuit.source_url in svg


def test_unknown_circuit_has_no_artwork() -> None:
    assert circuit_image_uri("UNKNOWN", "#123456", "#abcdef") is None
