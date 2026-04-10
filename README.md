# Trump Administration Legal Tracker

A unified dashboard combining two datasets to track the Trump administration's legal exposure:

1. **Structural Litigation Tracker** — 637 federal dockets (427 distinct legal battles) challenging executive actions, enriched via [CourtListener](https://www.courtlistener.com/)
2. **Habeas Non-Compliance Tracker** — 368 documented instances of the federal government violating court orders in immigration habeas cases, sourced from [Lawfare](https://www.lawfaremedia.org/)

The key analytical question: **20 federal judges appear in both datasets** — simultaneously handling major structural constitutional challenges *and* finding the government in non-compliance with individual court orders.

![Screenshot](https://img.shields.io/badge/status-live-brightgreen)

## Key Findings

- Non-compliance is **bipartisan** — judges appointed by presidents of both parties have documented government violations
- The District of Minnesota accounts for a disproportionate share of non-compliance cases
- "Failure to Timely Release" and "Failure to Return Property" are the most common violation types; "Removal/Deportation Despite Order" is the most severe
- 24 cases involve multiple simultaneous violation types

## Architecture

Static site (HTML + CSS + D3.js) with a Python data pipeline:

```
data/                        # Raw data sources
  mega_list.json               # Lawfare non-compliance dataset (Google Sheets export)
  litigation_tracker.db        # SQLite DB with cases/parties/attorneys
  litigation_analysis.json     # Pre-computed litigation stats
  judges_crossref.json         # Normalized judges with appointer data
  fjc_judges.csv               # FJC Biographical Directory of Federal Judges

analysis/                    # Data pipeline (Python)
  normalize_judges.py          # Judge name normalization + cross-referencing
  enrich_appointers.py         # Appointing president lookup via CourtListener API + FJC
  build_unified_data.py        # Merges both datasets → site/data.json

site/                        # Static frontend
  index.html                   # Unified layout with section switcher
  styles.css                   # Dark theme, responsive
  app.js                       # All chart rendering (D3.js v7)
  data.json                    # Combined dataset (~3 MB)
```

## Sections & Visualizations

### Litigation Tracker
| Tab | Contents |
|-----|----------|
| Overview | Stat cards, dockets by executive action, dockets by court, filing timeline (monthly / cumulative) |
| Judges | Cases by appointing president, top judges by docket count, injunction vs. dismissal scatter plot |
| Attorneys | Top organizations/firms, top plaintiff-side and defendant-side (DOJ) attorneys |
| Executive Actions | Status breakdown (stacked bars) by executive action |
| Case Explorer | Full-text search, status/court filters, all dockets vs. battles toggle |

### Non-Compliance
| Tab | Contents |
|-----|----------|
| Overview | Stat cards, violations by type (severity-ordered), cases by jurisdiction, appointing president |
| Judge Overlap | Stacked bar chart of 20 judges in both datasets, click-to-detail panel, all judges by caseload |
| Violation Patterns | Violation co-occurrence matrix, violations-by-jurisdiction heatmap |
| Timeline | Non-compliance cases over time |
| Case Explorer | Full-text search, jurisdiction/violation type/appointer filters |

## Running Locally

Serve the `site/` directory with any static file server:

```bash
python3 -m http.server 8502 --directory site
```

Then open [http://localhost:8502](http://localhost:8502).

## Rebuilding the Data

If the source data changes, re-run the pipeline:

```bash
# 1. Normalize judge names and cross-reference datasets
python3 analysis/normalize_judges.py

# 2. Enrich judges with appointing president (requires CourtListener API)
python3 analysis/enrich_appointers.py

# 3. Build unified data.json for the frontend
python3 analysis/build_unified_data.py
```

Steps 1–2 are only needed if the judge data changes. Step 3 rebuilds `site/data.json` from all sources.

## Data Sources

- [Lawfare Institute](https://www.lawfaremedia.org/) — Habeas non-compliance dataset
- [CourtListener RECAP Archive](https://www.courtlistener.com/) — Docket data, judge biographical data
- [Federal Judicial Center](https://www.fjc.gov/) — Biographical Directory of Federal Judges

## License

Data is sourced from the organizations listed above. Code is provided as-is for research and journalism purposes.
