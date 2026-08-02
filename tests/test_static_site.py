from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).parents[1]
SITE = ROOT / "site"


class LocalReferenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del tag
        for name, value in attrs:
            if name in {"href", "src"} and value:
                self.references.append(value)


def test_static_site_is_self_contained() -> None:
    index = SITE / "index.html"
    parser = LocalReferenceParser()
    parser.feed(index.read_text(encoding="utf-8"))

    local_references = [
        reference.split("#", 1)[0]
        for reference in parser.references
        if not reference.startswith(("#", "http://", "https://", "mailto:"))
    ]
    assert local_references
    assert all((SITE / reference).is_file() for reference in local_references)


def test_static_site_contains_only_reviewed_publication_files() -> None:
    files = [path for path in SITE.rglob("*") if path.is_file()]
    assert {path.suffix for path in files if path.name != ".nojekyll"} <= {
        ".css",
        ".html",
        ".svg",
    }

    published_text = "\n".join(
        path.read_text(encoding="utf-8") for path in files if path.suffix in {".html", ".css"}
    ).lower()
    assert "source_path" not in published_text
    assert "source_sha256" not in published_text
    assert "lap_time_seconds" not in published_text
    assert "parquet" not in published_text


def test_static_site_preserves_snapshot_scope_and_attribution() -> None:
    page = (SITE / "index.html").read_text(encoding="utf-8")
    assert "2025 Spanish Sprint" in page
    assert "Derived analysis only" in page
    assert "CC BY-SA 4.0" in page
    assert all(section in page for section in ('id="pace"', 'id="sectors"', 'id="quality"'))
