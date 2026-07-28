"""Remote PDF acquisition and local raw-file caching."""

from __future__ import annotations

import os
from pathlib import Path

import httpx

from ._contracts import _event_code, _session_code


def analysis_url(year: int, event: str, session: str) -> str:
    session = _session_code(session)
    event = _event_code(event)
    return (
        f"https://resources.motogp.com/files/results/{year}/{event}/MotoGP/{session}/Analysis.pdf"
    )


def download_pdf(
    year: int,
    event: str,
    session: str,
    data_root: Path = Path("data"),
    *,
    force: bool = False,
) -> Path:
    """Download one official analysis PDF unless a cached copy already exists."""

    session = _session_code(session)
    event = _event_code(event)
    target = data_root / "raw" / str(year) / event / session / "Analysis.pdf"
    if target.exists() and not force:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        response = client.get(analysis_url(year, event, session))
        response.raise_for_status()
    if not response.content.startswith(b"%PDF"):
        raise ValueError("Downloaded response is not a PDF")
    temporary = target.with_suffix(".pdf.tmp")
    temporary.write_bytes(response.content)
    os.replace(temporary, target)
    return target
