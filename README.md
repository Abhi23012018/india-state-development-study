# India State Development, Education, and Population Correlation Study

A reproducible, production-oriented cross-sectional analysis of how education,
population concentration, and economic output vary across Indian states and union
territories. The project downloads real public data, harmonizes state names,
validates the merged table, estimates correlations and an OLS model, and exports
publication-ready graphics.

No synthetic or randomly generated observations are used.

## Repository layout

```text
.
├── data/
│   ├── raw/                    # Download cache (gitignored)
│   └── processed/              # Analysis-ready CSV (gitignored)
├── notebooks/                  # Exploration guidance
├── outputs/                    # Tables, model summary, and PNG figures
├── src/
│   ├── data_pipeline.py        # Download, validation, harmonization, merge
│   ├── analytics.py            # Pearson/Spearman and robust OLS
│   ├── visualization.py        # Heatmap and population bubble regression plot
│   └── map_visualization.py    # Interactive Census 2011 state choropleth
├── tests/
│   ├── test_pipeline.py
│   └── test_analytics.py
├── .gitignore
├── README.md
└── requirements.txt
```

## Real data sources

The analysis uses a common 2011/2011–12 reference period to reduce temporal
mismatch. Each remote file is cached locally after its first download.

| Measure | Period | Upstream provenance | Reproducible file used |
|---|---:|---|---|
| Population, literacy rate, area, density | Census 2011 | Office of the Registrar General & Census Commissioner, India | [Public Census CSV mirror](https://gist.github.com/NeeharikaGali/34a6bd81a0bbea3917c028179dbee34a) |
| Per-capita income (per-capita NSDP) | 2011–12 | Reserve Bank of India state statistics | [Public RBI-derived CSV mirror](https://github.com/sahuvaibhav/Looker-Custom-Maps-Tutorial/blob/master/RBI%20DATA%20states_wise_population_Income.csv) |
| GSDP at current prices (INR crore) | 2011–12 | MoSPI/RBI state domestic product table | [Public GSDP CSV mirror](https://github.com/pdp19/GDP_Analysis/blob/master/Data_1A_for%20all%20state.csv) |

The Census 2011 Primary Census Abstract is documented by the [Census of India](https://censusindia.gov.in/nada/index.php/catalog/6191). Mirrors are used because they are direct, keyless CSV downloads suitable for automated builds. For archival-grade work, pin mirror commit SHAs or preserve downloaded files with checksums in an external data registry.

### Metric definitions

- **State GSDP**: gross state domestic product at current prices, INR crore.
- **Per Capita Income**: source-reported per-capita NSDP, INR. It is a net-income measure and is the OLS outcome.
- **Per Capita GSDP**: derived as `GSDP crore × 10,000,000 / Census population`. It is gross output per Census resident and is not treated as interchangeable with per-capita NSDP.
- **Population Density**: Census residents per square kilometre.

## Installation

Python 3.10+ is recommended.

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Run the project

From the repository root:

```bash
python -m src.data_pipeline
python -m src.analytics
python -m src.visualization
python -m src.map_visualization
pytest -q
```

Use `python -m src.data_pipeline --refresh` to redownload all sources. Without
`--refresh`, the raw cache makes reruns independent of network availability.

Generated artifacts:

- `data/processed/india_state_development.csv`
- `outputs/correlation_pearson.csv`
- `outputs/correlation_spearman.csv`
- `outputs/ols_summary.txt` and `outputs/ols_coefficients.csv`
- `outputs/correlation_heatmap.png`
- `outputs/literacy_income_bubble.png`
- `outputs/india_state_choropleth.html`
- `outputs/india_state_choropleth.png` when Kaleido/Chrome is available

## Interactive India state map

Open [the generated interactive choropleth](outputs/india_state_choropleth.html)
to switch among Census 2011 literacy, population density, total population, and
2011–12 per-capita income. Hovering a state reports its name and the selected
metric. The map is responsive and retains a neutral base layer so territories
without a matched project observation remain visible rather than disappearing.

Generate it from the repository root:

```bash
python -m src.data_pipeline
python -m src.map_visualization
```

`src/map_visualization.py` reads only
`data/processed/india_state_development.csv`; it does not generate or substitute
synthetic indicator values. The script downloads and caches the versioned
[Census 2011 state GeoJSON](https://github.com/saketlab/censusindia/blob/master/inst/extdata/india-census-2011-states.geojson)
from the MIT-licensed [`saketlab/censusindia`](https://github.com/saketlab/censusindia)
repository. That project documents the boundaries as collated through BharatViz
from Jolad & Singh's digitised Census collection and
[`ramSeraph/indian_admin_boundaries`](https://github.com/ramSeraph/indian_admin_boundaries).
The original Census indicators remain attributed to the Office of the Registrar
General & Census Commissioner, India.

State labels are canonicalized before joining, including Orissa/Odisha,
Pondicherry/Puducherry, NCT of Delhi/Delhi, Jammu & Kashmir/Jammu and Kashmir,
and Andaman `&`/`and` Nicobar Islands. The geometry contains all 35 Census 2011
states and union territories. The processed table currently supplies 32 matches;
Dadra & Nagar Haveli, Daman & Diu, and Lakshadweep are displayed as no-data areas.

### Boundary limitations

The map deliberately uses 2011 administrative definitions. Andhra Pradesh is
shown undivided, and Jammu & Kashmir includes the area now administered as
Ladakh. Telangana (formed in 2014) and Ladakh (formed in 2019) are not fabricated
as independent 2011 observations. This makes the map historically consistent
with the project's population and literacy measures, but unsuitable as a map of
current administrative units.

Static PNG export is best-effort because Plotly uses Kaleido and may require a
compatible Chrome installation. Failure to export PNG does not prevent the
standalone interactive HTML from being created.

## Data engineering behavior

State names are normalized before one-to-one joins, including Delhi/NCT of Delhi,
Orissa/Odisha, Pondicherry/Puducherry, Jammu & Kashmir/Jammu and Kashmir, and
Andaman `&`/`and` Nicobar Islands. The pipeline selects the exact 2011–12 GSDP
row, coerces Indian comma-grouped numbers, checks ranges and positivity, rejects
duplicate canonical states, and fails if fewer than 20 states/UTs survive.

Missing historical values are filled within state by forward-fill when a panel is
available, followed by a cross-state median fallback. Every affected output row
records column names in `Imputed Fields`; imputation is never silent.

## Statistical analysis

`src/analytics.py` produces Pearson correlations (linear association) and
Spearman correlations (rank-monotonic association) for:

- State GSDP
- Per Capita Income
- Literacy Rate
- Population Density

The model is:

```text
Per Capita Income = β₀ + β₁ Literacy Rate + β₂ Population Density + ε
```

It is estimated with Statsmodels OLS and HC3 heteroskedasticity-robust standard
errors. Coefficients describe conditional cross-state associations, not causal
effects.

## Findings and interpretation

On the 32-state/UT merged cross-section produced by the pinned inputs:

- Per-capita income has a positive association with literacy (Pearson **0.589**;
  Spearman **0.628**).
- Its relationship with density is stronger under Pearson (**0.486**) than
  Spearman (**0.171**), consistent with influence from compact, high-income urban
  UTs such as Delhi and Chandigarh.
- The two-predictor OLS has an unadjusted **R² of 0.456**. Point estimates are
  approximately **INR 2,369** per one-percentage-point increase in literacy and
  **INR 5.69** per additional resident/km², conditional on the other predictor.
  Use `outputs/ols_summary.txt` for HC3 robust uncertainty and p-values.
- Total GSDP and per-capita income have almost no cross-sectional linear
  relationship here (Pearson **−0.029**), illustrating the difference between
  aggregate economic scale and average income.
- West Bengal's source GSDP cell is unavailable and is median-imputed; the output
  records this in `Imputed Fields`, so GSDP correlations should be sensitivity-tested.
- Large bubbles are populous states, so the chart makes clear that the regression
  is state-weighted, not population-weighted.

Do not present p-values as proof that education or density causes income. The
small cross-section omits capital formation, urbanization, industrial structure,
health, governance, and spatial dependence. Administrative boundaries also
changed after 2011 (notably Andhra Pradesh/Telangana and Jammu & Kashmir/Ladakh),
so this repository retains source-era labels and reports the reference period.

## Reproducibility and quality checks

- Source URLs are centralized in `src/data_pipeline.py`.
- Raw downloads are cached; logs include SHA-256 checksums.
- Merge cardinality is validated as one-to-one.
- Unit tests cover name harmonization, year selection, auditable imputation,
  correlations, and regression design.
- Plots use a non-interactive backend for CI/headless execution.

## License and data terms

Project code may be reused under the repository's chosen software license. Source
data remains subject to its publishers' terms. Government datasets are cited to
their originating agencies; the GitHub mirrors are redistribution conveniences,
not new data authorities.
