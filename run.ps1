$ErrorActionPreference = "Stop"

uv sync

$session = "data/processed/year=2025/event=SPA/session=SPR/laps.parquet"
if (-not (Test-Path -LiteralPath $session)) {
    $ingest = @("run", "motogp-analytics", "ingest", "--year", "2025", "--event", "SPA", "--session", "SPR")
    $pdf = "SPA 2025/SPA 2025 SPR.pdf"
    if (Test-Path -LiteralPath $pdf) {
        $ingest += @("--pdf", $pdf)
    }
    & uv @ingest
}

uv run streamlit run dashboard/app.py
