# Dashboard Usage Guide

The dashboard compares MotoGP rider pace, consistency, sectors, lap evolution, and data
quality from processed timing-analysis PDFs.

## Start the Dashboard

From the repository root on Windows:

```powershell
.\run.ps1
```

The launcher syncs dependencies, ingests the 2025 Spain Sprint when processed data is
missing, and starts Streamlit. Open the URL printed in the terminal, normally
`http://localhost:8501`.

To start it manually:

```powershell
uv sync
uv run streamlit run dashboard/app.py
```

Stop the server with `Ctrl+C` in the terminal.

## Add a Session

Ingest a local PDF before opening or refreshing the dashboard:

```powershell
uv run motogp-analytics ingest --year 2025 --event SPA --session RAC --pdf "SPA 2025/SPA 2025 RAC.pdf"
```

Omit `--pdf` to download the document from the official results URL:

```powershell
uv run motogp-analytics ingest --year 2025 --event SPA --session SPR
```

Supported session codes are `FP1`, `FP2`, `PR`, `Q1`, `Q2`, `WUP`, `SPR`, and `RAC`.
Processed sessions appear automatically when all required artifacts exist under:

```text
data/processed/year=<year>/event=<event>/session=<session>/
```

The supplied `SPA 2025 FP1.pdf` is actually Race data and is correctly rejected as a
session mismatch.

## Sidebar Controls

### Session

Selects the championship year, event, and session to analyze. The label format is:

```text
2025 / SPA / SPR
```

### Pace View

- **clean**: excludes opening laps, outlaps, pit crossings, cancelled laps, incomplete
  timing, and anomalously slow laps. Use this view for performance conclusions.
- **raw**: includes every numbered lap with a lap time. Use it to audit how filtering
  changes the result.

Sector potential always uses complete, officially valid timing observations, even when the
pace view is `raw`. This prevents pit or cancelled sectors from creating impossible
theoretical laps.

## Summary Cards

| Card | Meaning |
|---|---|
| Fastest lap | Lowest lap time in the selected pace view |
| Best median | Lowest rider median; the main repeatable-pace benchmark |
| Tightest IQR | Smallest middle-50% lap-time range among riders with at least three laps |
| Top speed | Highest recorded speed in the selected pace view |

`Unavailable` means the selected data does not contain enough observations for that metric.

## Pace Distribution

### Repeatable Pace Window

Each horizontal box represents a rider's lap-time distribution.

- Further left means faster lap times.
- A narrower box means more repeatable pace.
- Rider order follows median pace, not finishing position.
- Colors identify constructors.

Hover over a box to inspect values. Use this chart to compare pace and consistency together;
do not rank riders from one isolated lap.

### Lap-Time Evolution

Use **Riders on trace** to add or remove riders. The chart plots lap time against lap number.
Practice runs are drawn as separate line segments so unrelated tyre or setup runs are not
joined.

Look for sustained changes rather than one-lap spikes. The chart shows an observed pace
trend; it does not by itself prove tyre degradation, fuel effects, traffic, or rider
management.

## Sector Map

### Median Sector Deficit

Each cell shows:

```text
rider median sector - best rider median sector
```

- `+0.000` is the session benchmark for that sector.
- Larger positive values indicate more time lost.
- Compare columns to identify where a rider's overall deficit originates.

### Theoretical Best Table

| Column | Meaning |
|---|---|
| Fastest | Fastest complete, officially valid reference lap |
| Theoretical best | Best valid T1 + best valid T2 + best valid T3 + best valid T4 |
| Potential lost | Fastest valid lap minus theoretical best |

The theoretical best combines sectors from different laps. It represents demonstrated
sector potential, not a lap the rider necessarily could have assembled in practice.

## Head-to-Head

Choose two riders to compare their lap count, fastest lap, median, IQR, theoretical best,
potential lost, and top speed.

The lap-delta chart calculates:

```text
Rider A lap time - Rider B lap time
```

- Negative: Rider A was faster.
- Positive: Rider B was faster.
- Only matching lap numbers in the selected pace view are compared.

## Data Quality

This tab should be checked before interpreting performance.

| Indicator | Meaning |
|---|---|
| Riders | Rider blocks detected in the PDF |
| Numbered laps | Parsed rows with a lap number and lap time |
| Valid laps | Full laps without cancellation markers |
| Sector completeness | Available T1-T4 cells divided by expected sector cells |

The reconciliation table compares detected runs, laps, full laps, and valid laps against
the counts printed in each rider's PDF header. Parser warnings identify mismatches or missing
tyre metadata. The source SHA-256 identifies the exact input document, and the sector
tolerance records the allowed rounding difference between sector sum and lap time.

## Chart Controls

Plotly charts support these interactions:

- Hover to inspect exact values.
- Drag to zoom into a region.
- Double-click to reset the axes.
- Use the toolbar camera button to save an image locally.

## Troubleshooting

### No timing feed

No complete processed session was found. Run an ingestion command, then reload the page.

### No clean laps are available

The session has no laps that pass the clean classification. Switch to `raw` to inspect the
source timing and review the Data Quality tab.

### Session mismatch

The requested session does not match the title inside the PDF. Check the session code and
source file; do not rename or force the document through validation.

### Processed data is outside `data/`

Set the data root before starting Streamlit:

```powershell
$env:MOTOGP_DATA_ROOT = "D:\motogp-data"
uv run streamlit run dashboard/app.py
```

### Port 8501 is already in use

Start Streamlit on another port:

```powershell
uv run streamlit run dashboard/app.py --server.port 8502
```

## Publication Note

The source PDFs contain a Dorna notice restricting reproduction, storage, and transmission.
Before publishing, confirm permission and prefer derived findings, charts, and methodology
over distributing complete extracted timing records.
