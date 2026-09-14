# Analysis workflow

Run the numbered scripts from the repository root with `uv run`. Generated data
are written to `data/processed/`; reports, figures, and tables are written to
`outputs/`.

| Step | Script | Purpose |
|---|---|---|
| 1 | `01_build_respondent_base.py` | Harmonize the two ESS Round 10 respondent releases. |
| 2 | `02_merge_with_populist_data.py` | Link ESS party choices to Party Facts and PopuList. |
| 3 | `03_build_analysis_base.py` | Construct the analysis-ready respondent file. |
| 4 | `04_measurement_diagnostics.py` | Audit missingness, reliability, distributions, and model samples. |
| 5 | `05_descriptive_comparisons.py` | Produce weighted descriptive comparisons. |
| 6 | `06_fit_models.py` | Fit the primary H1 and H2a models. |
| 9A | `09_country_heterogeneity.py` | Estimate exploratory country-specific associations. |
| 9B | `09b_government_context.py` | Examine exploratory pre-election government context. |
| 10 | `10_h2b_incremental.py` | Fit the H2b nested and same-sample indicator comparisons. |
| 11 | `11_hypothesis_model_map.py` | Generate the compact hypothesis-to-model figure. |
| 12 | `12_export_report_visuals.py` | Collect report figures and render report tables as high-resolution PNG files. |
| 13 | `13_update_manuscript_visuals.py` | Replace manuscript images and normalize figure and appendix captions. |

The non-consecutive labels preserve identifiers used in existing output files
and manuscript notes. The workflow intentionally excludes old notebooks,
temporary reports, and robustness scripts that are not part of the reported
seminar-paper analysis.

## Verification

```sh
uv run pytest
uv run ruff check .
```
