# 2025 Spanish Sprint: Where Marc Márquez Built the Win

## Question

Marc Márquez beat Alex Márquez by 1.001 seconds over 12 laps. Was the result driven by a
single peak lap, or by a repeatable pace advantage?

## Method

- Source: official 2025 Spanish Grand Prix Sprint chronological analysis.
- Clean pace: laps 2-12, excluding the opening lap and any cancelled, incomplete, pit, or
  anomalously slow laps.
- Sector comparison: median sector time across clean laps.
- Early phase: mean matched-lap delta over laps 2-6.
- Late phase: mean matched-lap delta over laps 8-12. Positive delta means Marc was slower.

## Evidence

| Metric | Marc Márquez | Alex Márquez | Advantage |
|---|---:|---:|---:|
| Fastest clean lap | 1'36.665 | 1'36.683 | Marc, 0.018 s |
| Median clean pace | 1'37.309 | 1'37.411 | Marc, 0.102 s |
| Mean clean pace | 1'37.291 | 1'37.338 | Marc, 0.047 s |
| Pace IQR | 0.622 s | 0.294 s | Alex, 0.328 s tighter |
| Theoretical best | 1'36.504 | 1'36.566 | Marc, 0.062 s |
| Potential lost | 0.161 s | 0.117 s | Alex, 0.044 s less |

Marc's median sector advantage was concentrated in T1 and T3:

| Sector | Marc median | Alex median | Marc minus Alex |
|---|---:|---:|---:|
| T1 | 24.259 s | 24.355 s | -0.096 s |
| T2 | 14.248 s | 14.218 s | +0.030 s |
| T3 | 28.957 s | 29.083 s | -0.126 s |
| T4 | 29.822 s | 29.716 s | +0.106 s |

The race shape matters as much as the session-wide averages:

- Marc gained 0.480 seconds on the opening lap.
- Across laps 2-6, Marc averaged 0.149 seconds per lap faster.
- Across laps 8-12, Marc averaged 0.074 seconds per lap slower.
- The cumulative 12-lap timing difference was 1.001 seconds in Marc's favor.

## Finding

The win was not explained by a materially better single lap: the fastest-lap difference was
only 0.018 seconds, and Alex produced the tighter pace distribution. Marc instead combined
an opening-lap gain with a clear early-Sprint advantage, especially through T1 and T3. Alex
was marginally faster late in the Sprint, but not by enough to recover the deficit.

This analysis describes the observed timing pattern. The PDF does not establish whether the
late change came from tyres, fuel, traffic, rider management, or another cause.

## Reproduce

```powershell
uv run motogp-analytics ingest --year 2025 --event SPA --session SPR --pdf "SPA 2025/SPA 2025 SPR.pdf"
uv run motogp-analytics summary "data/processed/year=2025/event=SPA/session=SPR" --scope clean
uv run streamlit run dashboard/app.py
```
