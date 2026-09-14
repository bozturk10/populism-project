# Documentation manifest

Downloaded or inventoried on 2026-08-22. Source files are stored locally and ignored
by Git; this manifest records their provenance for reproducibility.

## European Social Survey Round 10

| Local file | Purpose | Official source | SHA-256 |
|---|---|---|---|
| `ESS_R10/docs/ess10_country_documentation_e03_0.pdf` | Country fieldwork, sampling, questionnaires, elections, and national deviations; edition 3.0 | [ESS data storage](https://stessrelpubprodwe.blob.core.windows.net/data/round10/survey/ESS10_country_documentation_report_e03_0.pdf) | `072634bea305611c54a558897a42dad97212f3e1e566090bd1e8c9b4240249b7` |
| `ESS_R10/docs/ess10_source_questionnaire.pdf` | Round 10 source questionnaire and routing | [ESS ERIC](https://www.europeansocialsurvey.org/sites/default/files/2023-06/ESS-Round-10-Source-Questionnaire_FINAL_A.pdf) | `ee6c967d2efbc47e0541c8ebc4ff01a6a156bea0028398aac4610ecd55abb67c` |
| `ESS_R10/docs/ess_weighting_guide_1_1.pdf` | Selection and use of ESS weights and sample-design variables | [ESS ERIC](https://www.europeansocialsurvey.org/sites/default/files/2023-06/ESS_weighting_data_1_1.pdf) | `d1d958814ad6376a7e3a19f89e265c8f8069c1e43deb35a397bda2bdb6469560` |
| `ESS_R10/docs/ess10_quality_report.pdf` | Round 10 sampling, fieldwork, mode, and data-quality assessment | [ESS ERIC](https://www.europeansocialsurvey.org/sites/default/files/2024-09/ESS10_Quality_Report.pdf) | `f6d497cbd67e17a51a391cb6661eb3915d0096359e6c4f3e6eb81981ae429871` |
| `ESS_R10/docs/ess10_note_on_data_modes_e01_0.pdf` | Differences and comparability cautions for interviewer and self-completion modes | [ESS data storage](https://stessrelpubprodwe.blob.core.windows.net/data/round10/methods/ESS10_note_on_data_modes_e01_0.pdf) | `f7d9a78a5fcbc017f96e8acacb24deef8770a082efb2ef1040bdffa48b43f9d4` |

The exact-edition HTML codebooks distributed with `ESS10e03_3` and `ESS10SCe03_2`
remain the primary machine-readable references for variable labels, valid values, and
missing codes.

## PopuList

| Local file | Purpose | Source | SHA-256 |
|---|---|---|---|
| `PopuList/docs/popuList_4_0_static_table.pdf` | Static presentation of PopuList 4.0 classifications | [PopuList](https://popu-list.github.io/Visualizations/table/table.pdf) | `e88700932ef6b77266547b30331392887719e9026a23e9fa5c9d03cba5d7076b` |
| `PopuList/docs/popuList_EIQCC_methods_article.pdf` | EIQCC methodology article supplied for the project | [DOI: 10.1017/S0007123423000431](https://doi.org/10.1017/S0007123423000431) | `adac5ddb4568c489368923732ba890b84f704555db8053927b8520dd7bdd9411` |

Download the classification data from PopuList and save it locally as
`data/raw/populist_4_0.csv`; the file is intentionally not committed.

## Party Facts ESS linkage

Downloaded on 2026-08-22 from Party Facts Data commit
`61e04e83a4eff4e285bdb724cc11cc8bdf4beb16`.

| Local file | Purpose | Source | SHA-256 |
|---|---|---|---|
| `PartyFacts/essprt-all.csv` | Code-level ESS Round 1–11 party links | [Party Facts Data](https://github.com/hdigital/partyfactsdata/blob/main/import/essprtv/essprt-all.csv) | `98988e7e0cbc7123535b16c81ab515b50c1e63372d6ef01bf35315c27d811da8` |
| `PartyFacts/essprtv.csv` | Harmonized ESS voted-party identities | [Party Facts Data](https://github.com/hdigital/partyfactsdata/blob/main/import/essprtv/essprtv.csv) | `74b8912c9a4707dd3439b2e7859e46319b178ebab0599222cc02532cd6221577` |
| `PartyFacts/readme.md` | Upstream linkage documentation and citations | [Party Facts Data](https://github.com/hdigital/partyfactsdata/blob/main/import/essprtv/readme.md) | `5dfc43288c8fd1efdebc74e4a2142ddb7e855e668f9d668b46206fe32b49bab9` |
# Additional contextual source

- ParlGov 2024 stable V1, DOI `10.7910/DVN/2VZ5ZC`: cabinet, cabinet-party,
  election, party, and country tables used by the exploratory Stage 9B government
  context. The pipeline downloads the required release directly from the documented
  source and validates the expected file structure before use.
