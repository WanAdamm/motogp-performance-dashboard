[CmdletBinding()]
param(
    [string]$DataRoot = "data",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$year = 2025
# Official 2025 event codes in calendar order.
$events = @(
    "THA", "ARG", "AME", "QAT", "SPA", "FRA", "GBR", "ARA", "ITA", "NED", "GER",
    "CZE", "AUT", "HUN", "CAT", "RSM", "JPN", "INA", "AUS", "MAL", "POR", "VAL"
)
$sessions = @("FP1", "FP2", "PR", "Q1", "Q2", "WUP", "SPR", "RAC")
$artifacts = @("laps.parquet", "runs.parquet", "partials.parquet", "session.json")

if (-not $DryRun) {
    & uv sync
    if ($LASTEXITCODE -ne 0) {
        throw "uv sync failed with exit code $LASTEXITCODE"
    }
}

$processedCount = 0
$skippedCount = 0
$unavailableCount = 0
$failures = @()

foreach ($event in $events) {
    foreach ($session in $sessions) {
        $arguments = @(
            "run", "motogp-analytics", "ingest",
            "--year", $year,
            "--event", $event,
            "--session", $session,
            "--data-root", $DataRoot
        )

        if ($DryRun) {
            "uv $($arguments -join ' ')"
            continue
        }

        $rawPdf = Join-Path $DataRoot "raw\$year\$event\$session\Analysis.pdf"
        $processed = Join-Path $DataRoot "processed\year=$year\event=$event\session=$session"
        $complete = Test-Path -LiteralPath $rawPdf
        foreach ($artifact in $artifacts) {
            if (-not (Test-Path -LiteralPath (Join-Path $processed $artifact))) {
                $complete = $false
                break
            }
        }
        if ($complete) {
            Write-Host "[SKIP] $event/$session is complete"
            $skippedCount++
            continue
        }

        $ErrorActionPreference = "Continue"
        $output = & uv @arguments 2>&1
        $exitCode = $LASTEXITCODE
        $ErrorActionPreference = "Stop"
        if ($exitCode -eq 0) {
            Write-Host "[OK]   $event/$session"
            $processedCount++
            continue
        }

        $message = $output -join [Environment]::NewLine
        if ($message -match "404 Not Found") {
            Write-Host "[MISS] $event/$session is unavailable"
            $unavailableCount++
            continue
        }

        Write-Warning "[FAIL] $event/$session"
        $output | ForEach-Object { Write-Warning "  $_" }
        $failures += "$event/$session"
    }
}

if ($DryRun) {
    Write-Host "Planned $($events.Count * $sessions.Count) sessions."
    return
}

Write-Host "Processed: $processedCount; complete: $skippedCount; unavailable: $unavailableCount; failed: $($failures.Count)"
if ($failures.Count -gt 0) {
    throw "Failed sessions: $($failures -join ', ')"
}
