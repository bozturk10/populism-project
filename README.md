# Populist-party voting in Europe

Reproducible Python analysis of political distrust, people-centred democratic
preferences, and populist-party voting using European Social Survey Round 10,
Party Facts, PopuList 4.0, and ParlGov 2024.

The project evaluates three expectations:

- H1: political distrust is positively associated with populist-party voting;
- H2a: preference for ordinary people's views to prevail over political elites
  is positively associated with populist-party voting;
- H2b: broader popular-sovereignty and direct-democracy indicators add
  information beyond the narrower people-over-elite indicator.

## Reproduce the analysis

Install [uv](https://docs.astral.sh/uv/) and create the locked environment:

```sh
uv sync --locked
```
## Required data

The analysis uses:

- European Social Survey Round 10 integrated file, edition 3.3;
- European Social Survey Round 10 self-completion file, edition 3.2;
- ESS-Party Facts bridge, version 0.1;
- PopuList 4.0;
- ParlGov 2024 stable release.

ESS files require registration and manual download from the
[ESS Data Portal](https://ess.sikt.no/en/study/172ac431-2a06-41df-9dab-c1fd8f3877e7).
Exact filenames, local paths, and sources are listed in
[`data/raw/README.md`](data/raw/README.md) and
[`data/raw/documentation_manifest.md`](data/raw/documentation_manifest.md).


Run the workflow from the repository root:

```sh
uv run python analysis/01_build_respondent_base.py
uv run python analysis/02_merge_with_populist_data.py
uv run python analysis/03_build_analysis_base.py
uv run python analysis/04_measurement_diagnostics.py
uv run python analysis/05_descriptive_comparisons.py
uv run python analysis/06_fit_models.py
uv run python analysis/09_country_heterogeneity.py
uv run python analysis/09b_government_context.py
uv run python analysis/10_h2b_incremental.py
uv run python analysis/11_hypothesis_model_map.py
uv run pytest
uv run ruff check .
```

The scripts create analysis-ready data under `data/processed/` and refresh the
tables, figures, and readable reports under `outputs/`.



## Authors

Antonia Bouton, Elif Ezgi Aksulu, and Berk Yoztyurk.
