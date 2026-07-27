# MotoGP Performance Analytics Platform

## MVP Status

The MVP implements the complete local workflow:

```text
MotoGP analysis PDF
    → coordinate-aware parsing
    → schema and timing validation
    → lap classification
    → Parquet storage
    → DuckDB analytics
    → Streamlit dashboard
```

PyMuPDF reads the embedded words and their coordinates. The parser preserves rider, run,
tyre, lap, sector, speed, cancellation, pit, and partial-row data without relying on the
PDF's unreliable linear text order.

### Quick Start

Requirements: Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```powershell
uv sync
uv run motogp-analytics ingest --year 2025 --event SPA --session SPR
uv run streamlit run dashboard/app.py
```

Pass `--pdf "path/to/Analysis.pdf"` to ingest an already downloaded document instead.

The dashboard discovers every session under `data/processed/`. Generated datasets are
ignored by Git because the source documents contain a Dorna reproduction restriction.

Dashboard guide: [How to use and interpret each view](docs/dashboard-usage.md).

Portfolio case study: [Where Marc Márquez built the 2025 Spanish Sprint win](docs/spa-2025-sprint-case-study.md).

Inspect a session from the terminal:

```powershell
uv run motogp-analytics summary "data/processed/year=2025/event=SPA/session=SPR" --scope clean
```

Run verification:

```powershell
uv run ruff check .
uv run ruff format --check src dashboard tests
uv run pytest
```

Run one focused parser test:

```powershell
uv run pytest tests/test_mvp.py -k race
```

### Sample Data Note

`SPA` is the event code for Spain/Jerez. The supplied `SPA 2025 FP1.pdf` is byte-identical
to `SPA 2025 RAC.pdf` and identifies itself internally as Race data. The ingestion command
therefore rejects it as a session mismatch instead of silently storing Race laps as FP1.

## High-Level Project Plan

## 1. Project Summary

The **MotoGP Performance Analytics Platform** is an end-to-end data analytics portfolio project that transforms official MotoGP timing PDFs into structured, analysis-ready datasets and interactive performance insights.

Official MotoGP timing documents contain detailed lap-level information, including lap times, sector times, speeds, rider information, tyre data, and session results. However, the information is distributed primarily through PDF documents, making large-scale comparison and analysis difficult.

This project will automate the process of:

**Data Acquisition → PDF Extraction → Data Cleaning → Validation → Analysis → Visualization → Insight Generation**

The primary goal is to demonstrate practical skills relevant to **Data Analyst positions**, while also showing supporting knowledge in data engineering, statistics, and dashboard development.

---

## 2. Core Portfolio Objective

The project should demonstrate the ability to take messy real-world data and turn it into meaningful analytical insights.

The final product should answer questions such as:

- Which rider had the strongest underlying pace?
- Which rider was the most consistent?
- Where did riders gain or lose time across sectors?
- How did pace change throughout a Sprint or Grand Prix?
- Which riders maintained their pace best late in the race?
- How close did riders come to their theoretical best lap?
- How did rider performance develop throughout a race weekend?
- How did constructors perform across different circuits?
- What patterns can be identified across multiple races and sessions?

The project should prioritize **interpretation and analytical storytelling**, rather than simply displaying timing data.

---

# 3. Data Source

The main source will be official MotoGP session analysis PDFs.

General URL structure:

```text
https://resources.motogp.com/files/results/{year}/{event}/MotoGP/{session}/Analysis.pdf
```

Example:

```text
https://resources.motogp.com/files/results/2025/ARG/MotoGP/SPR/Analysis.pdf
```

Expected session codes:

```text
FP1
FP2
PR
Q1
Q2
WUP
SPR
RAC
```

Because the URL follows a predictable structure, the data collection process can be automated across events, sessions, and seasons.

---

# 4. High-Level Architecture

```text
Official MotoGP Timing PDF
            │
            ▼
    Data Acquisition
            │
            ▼
      PDF Extraction
            │
            ▼
       Data Parsing
            │
            ▼
      Data Validation
            │
            ▼
 Cleaning & Transformation
            │
            ▼
   Structured Dataset
      │           │
      ▼           ▼
    Parquet     DuckDB
      │           │
      └─────┬─────┘
            ▼
     Analytics Layer
            │
            ▼
 Interactive Dashboard
            │
            ▼
 Analytical Insights
```

---

# 5. Data Acquisition Layer

The first component will generate and retrieve MotoGP timing documents automatically.

Example interface:

```python
get_session(
    year=2025,
    event="ARG",
    session="SPR"
)
```

Responsibilities:

- Generate the correct MotoGP results URL
- Check whether the requested document exists
- Download the session PDF
- Store raw source documents
- Record event, season, and session metadata
- Prevent unnecessary duplicate downloads

This creates a reusable ingestion pipeline instead of relying on manual downloads.

---

# 6. PDF-to-Structured-Data Pipeline

The PDF parser will transform MotoGP timing documents into a standardized lap-level dataset.

Example schema:

| Field | Description |
|---|---|
| year | Championship year |
| event | Grand Prix/event |
| session | Session type |
| rider | Rider name |
| rider_number | Race number |
| team | Team |
| constructor | Manufacturer |
| position | Session position |
| run | Tyre/setup run number |
| lap | Lap number |
| lap_time_seconds | Lap time in seconds |
| t1 | Sector 1 time |
| t2 | Sector 2 time |
| t3 | Sector 3 time |
| t4 | Sector 4 time |
| speed | Recorded speed |
| classification | Derived clean-lap classification |
| is_fastest | Rider-fastest-lap flag |

Tyre compounds and their starting age are stored once per rider/run in `runs.parquet`, not
duplicated onto every lap.

Lap times should be stored numerically.

Example:

```text
1'37.706 → 97.706 seconds
```

Formatting back into traditional motorsport timing notation should only happen in the presentation layer.

---

# 7. Data Validation and Quality Control

PDF extraction can create missing, duplicated, or incorrectly aligned values. Therefore, validation will be treated as a core part of the project.

Validation checks may include:

### Sector Sum Check

```text
T1 + T2 + T3 + T4 ≈ Lap Time
```

### Duplicate Check

Ensure each combination of:

```text
Year + Event + Session + Rider Number + Lap
```

is unique.

### Missing-Value Checks

Flag missing:

- Lap times
- Sector times
- Speed
- Rider metadata
- Tyre information

### Session-Level Checks

Track:

- Riders detected
- Laps detected
- Valid laps
- Sector completeness
- Missing values
- Parsing warnings

A future version may assign each imported session a **Data Quality Score**.

---

# 8. Lap Cleaning and Classification

Raw lap averages can be misleading because sessions include laps that are not representative of normal performance.

Examples include:

- Opening laps
- Outlaps
- Inlaps
- Pit-lane laps
- Invalidated laps
- Extremely slow laps
- Incident-affected laps

Each lap should therefore receive a classification.

Possible classes:

```text
OPENING_LAP
OUTLAP
CLEAN
SLOW
PIT_IN
INVALID
```

Fastest is an independent `is_fastest` flag rather than a mutually exclusive class.

The analytics layer should allow users to compare:

```text
Raw Pace
vs.
Clean Pace
```

This cleaning methodology should be documented clearly because it directly affects analytical conclusions.

---

# 9. Core Analytical Features

## 9.1 Rider Pace Analysis

Calculate:

- Mean clean lap time
- Median clean lap time
- Fastest lap
- Interquartile range
- Standard deviation
- Number of clean laps

Primary visualization:

**Rider Pace Boxplot**

This allows both outright pace and consistency to be assessed.

---

## 9.2 Pace Consistency

Analyze how repeatable each rider's performance is.

Potential measures:

```text
Standard Deviation
Interquartile Range
Coefficient of Variation
```

A normalized **Consistency Score** may later be created for easier comparison between riders.

---

## 9.3 Lap-Time Evolution

Plot lap time against race lap.

Possible views:

- Absolute lap time
- Delta to session leader
- Delta to rider median
- Rolling average
- Early-race vs late-race pace

This can reveal:

- Stable race pace
- Gradual pace deterioration
- Improving performance
- Abnormal laps
- Different race-management patterns

---

## 9.4 Sector Performance

Analyze T1, T2, T3, and T4 independently.

Metrics:

- Best sector
- Median sector
- Average sector
- Delta to session-best sector
- Sector contribution to overall lap deficit

Primary visualization:

**Sector Performance Heatmap**

This should help explain *where* a rider is gaining or losing lap time.

---

## 9.5 Theoretical Best Lap

Calculate:

```text
Theoretical Best =
Best T1 + Best T2 + Best T3 + Best T4
```

Then compare against the rider's actual fastest lap.

Derived metric:

```text
Potential Lost =
Actual Fastest Lap - Theoretical Best
```

This provides another perspective on lap execution and performance potential.

---

# 10. Sprint and Grand Prix Analysis

## Sprint

Focus on:

- Clean pace
- Consistency
- Short-term pace evolution
- Early vs late Sprint performance
- Rider-to-rider deltas

## Grand Prix

Add:

- Longer-term pace trends
- Race-phase comparison
- Late-race performance
- Greater variation in tyre and race management

Possible race phases:

```text
Opening
Early Race
Mid Race
Late Race
```

---

# 11. Observed Pace Trend

A simple regression model can estimate how lap times change as a race progresses.

Conceptually:

```text
Lap Time = Baseline Pace + Pace Trend × Lap Number
```

This should initially be labelled **Observed Pace Trend**, not automatically "tyre degradation."

Changes in lap time may also result from:

- Fuel load
- Traffic
- Rider management
- Track evolution
- Mistakes
- Incidents
- Changing conditions

The project should clearly separate **measured patterns** from **possible explanations**.

---

# 12. Rider Head-to-Head Comparison

Allow two riders to be compared directly.

Example metrics:

| Metric | Rider A | Rider B |
|---|---:|---:|
| Fastest Lap | | |
| Median Pace | | |
| Mean Pace | | |
| Consistency | | |
| Best T1 | | |
| Best T2 | | |
| Best T3 | | |
| Best T4 | | |
| Theoretical Best | | |
| Top Speed | | |
| Early-Race Pace | | |
| Late-Race Pace | | |

Additional chart:

**Lap-by-Lap Time Delta**

This provides an intuitive view of exactly where one rider gained or lost time relative to another.

---

# 13. Weekend Progression Analysis

Once multiple sessions are available, performance can be analyzed across an entire race weekend.

```text
FP1
 ↓
Practice
 ↓
Qualifying
 ↓
Sprint
 ↓
Race
```

Potential insights:

- Practice-to-qualifying improvement
- Qualifying vs race pace
- Sprint vs Grand Prix performance
- Sector improvement throughout the weekend
- Rider adaptation to the circuit

This extends the project from isolated-session analysis into longitudinal analytics.

---

# 14. Constructor Analysis

Aggregate rider performance by manufacturer:

```text
Ducati
KTM
Aprilia
Yamaha
Honda
```

Potential comparisons:

- Median pace
- Sector performance
- Speed distribution
- Pace consistency
- Circuit-specific performance

With enough historical data, the project could identify recurring constructor strengths across different circuit types.

---

# 15. Advanced Race Simulation

Race simulation should be treated as an advanced project phase rather than part of the first MVP.

Possible inputs:

- Baseline clean pace
- Lap-time variance
- Observed pace trend
- Starting position
- Race length
- Simplified traffic assumptions

Monte Carlo simulation could estimate:

- Expected finishing position
- Expected race time
- Probability of finishing ahead of another rider
- Range of potential race outcomes

The simulation should be presented as a **statistical scenario model**, not as a deterministic prediction engine.

---

# 16. Dashboard Design

Potential navigation:

```text
Overview
Pace
Lap Evolution
Sectors
Head-to-Head
Weekend Analysis
Constructors
Simulation
Data Quality
```

Potential overview KPIs:

```text
Fastest Rider
Best Median Pace
Most Consistent Rider
Best Theoretical Lap
Highest Top Speed
Largest Late-Race Pace Drop
```

The dashboard should prioritize a small number of useful visualizations and clear findings over chart quantity.

---

# 17. Technology Stack

| Layer | MVP technology |
|---|---|
| Runtime and environment | Python 3.12, uv |
| Acquisition and extraction | httpx, PyMuPDF word coordinates |
| Processing and validation | pandas, Pandera |
| Analytical storage | Parquet, DuckDB |
| Visualization and dashboard | Plotly, Streamlit |
| Verification | pytest, Ruff |

The dataset is small enough that pandas is preferable to adding Polars. Parquet is the
canonical store and DuckDB queries it directly, so the MVP does not need CSV duplication,
a persistent database server, an API, or a separate frontend.

---

# 18. Development Roadmap

## Phase 1 — Data Pipeline MVP

Build:

- MotoGP URL generator
- PDF downloader
- PDF parser
- Time conversion
- Normalized dataset
- Validation checks
- Parquet export

### Deliverable

A reliable structured dataset generated automatically from a selected MotoGP session.

---

## Phase 2 — Core Analytics

Build:

- Clean-lap filtering
- Pace summary statistics
- Pace boxplots
- Lap-time evolution
- Sector comparison
- Consistency analysis
- Theoretical best lap

### Deliverable

A complete analytical report for a single MotoGP session.

---

## Phase 3 — Interactive Dashboard

Build:

- Season selector
- Event selector
- Session selector
- Rider filtering
- Interactive charts
- Head-to-head comparison
- KPI cards
- Data-quality indicators

### Deliverable

A public-facing interactive MotoGP analytics dashboard.

---

## Phase 4 — Multi-Session Analytics

Build:

- Weekend progression
- Rider historical trends
- Constructor comparison
- Cross-event analysis
- Historical analytical database

### Deliverable

A longitudinal MotoGP performance analytics platform.

---

## Phase 5 — Advanced Analytics

Explore:

- Pace-trend modelling
- Automated race-phase detection
- Rider similarity analysis
- Constructor performance profiles
- Sprint simulation
- Grand Prix simulation

### Deliverable

An advanced statistical analysis and modelling layer.

---

# 19. Data Analyst Skills Demonstrated

This project should be positioned around the following competencies.

## Data Cleaning

- Missing-value handling
- Outlier identification
- Data-type conversion
- Validation rules
- Data-quality assessment

## Exploratory Data Analysis

- Distribution analysis
- Trend analysis
- Comparative analysis
- Segment analysis
- Pattern identification

## Statistical Analysis

- Descriptive statistics
- Variability
- Regression
- Normalization
- Simulation

## SQL and Data Modelling

- Structured analytical datasets
- Relational modelling
- Aggregations
- Window functions
- Historical comparisons

## Data Visualization

- Boxplots
- Line charts
- Heatmaps
- KPI dashboards
- Comparative visualizations

## Analytical Communication

The project should demonstrate the complete workflow:

```text
Raw Data
   ↓
Clean Data
   ↓
Analysis
   ↓
Finding
   ↓
Interpretation
   ↓
Insight
```

The strongest portfolio version will explain **why a pattern matters**, rather than only reporting the number.

---

# 20. Portfolio Positioning

Avoid describing the project primarily as:

> MotoGP PDF-to-CSV Converter

That describes only the ingestion component.

A stronger positioning is:

> **MotoGP Performance Analytics Platform** — An end-to-end analytics project that transforms official MotoGP timing documents into structured lap-level datasets and applies statistical analysis and interactive visualization to evaluate rider pace, consistency, sector performance, race evolution, and weekend progression.

---

# 21. Example Resume Bullet

> Developed an end-to-end MotoGP performance analytics pipeline in Python that extracted and normalized lap- and sector-level timing data from official race documents, implemented data-quality and clean-lap filtering logic, and built interactive analyses for rider pace, consistency, sector deltas, and race progression.

A stronger quantified version can be written once the completed project has measurable figures such as:

- Number of seasons processed
- Number of sessions
- Number of races
- Number of lap records
- Parsing accuracy
- Number of dashboard views

---

# 22. Recommended Portfolio Deliverables

The finished GitHub repository should ideally include:

```text
README.md
│
├── Clear problem statement
├── Architecture diagram
├── Data dictionary
├── Data-cleaning methodology
├── Example analytical findings
├── Dashboard screenshots
└── Instructions for reproducing the project

data/
src/
notebooks/
dashboard/
tests/
docs/
```

A separate case-study section should demonstrate at least one complete analysis such as:

> **2025 Argentina Sprint — Why Marc Márquez Beat Alex Márquez Despite Similar Peak Pace**

The analysis should move from raw timing data to statistical evidence, visualization, and a concise conclusion.

That type of case study will make the project significantly stronger for Data Analyst applications than presenting the dashboard alone.

---

# 23. MVP Success Criteria

The first portfolio-ready version should be able to:

1. Retrieve a selected official MotoGP session automatically.
2. Convert the timing PDF into structured lap-level data.
3. Validate important extracted fields.
4. Identify representative and abnormal laps.
5. Compare rider pace distributions.
6. Measure rider consistency.
7. Compare sector performance.
8. Calculate theoretical best laps.
9. Visualize lap-time evolution.
10. Produce at least one clear analytical case study.

Advanced simulations and predictive modelling can be added later.

The priority is to first build a **credible, reproducible, and explainable analytics workflow**.

---

# 24. Final Project Goal

The final project should show that the analyst can:

> **Take an inconvenient real-world data source, engineer it into a trustworthy dataset, use statistics to identify performance patterns, and communicate those patterns through effective visualizations and evidence-based insights.**

That is the core value of the project for a Data Analyst portfolio.
