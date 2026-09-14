# Raw data and documentation

Third-party source data are not distributed through this repository. Download them
from the sources below and place them at the expected local paths. Analysis scripts
must not modify them in place; cleaned and joined outputs belong in `data/processed/`.

| Local path | Source and purpose |
|---|---|
| `ESS_R10/ESS10e03_3/` | [ESS Round 10 integrated file, edition 3.3](https://ess.sikt.no/en/study/172ac431-2a06-41df-9dab-c1fd8f3877e7); respondent CSV and supplied HTML codebook. |
| `ESS_R10/ESS10SCe03_2/` | ESS Round 10 self-completion file, edition 3.2; respondent CSV and supplied HTML codebook from the ESS Data Portal. |
| `populist_4_0.csv` | [PopuList 4.0](https://popu-list.org/); party classifications used to classify ESS party choices. |
| `PartyFacts/essprt-all.csv` | [Party Facts ESS linkage](https://github.com/hdigital/partyfactsdata/tree/main/import/essprtv); bridges ESS party codes to PopuList through `partyfacts_id`. |
| `ParlGov/parlgov-stable.db` | [ParlGov 2024 stable release](https://doi.org/10.7910/DVN/2VZ5ZC); used only for the exploratory government-context analysis. |

The local `ESS_R10/` directory contains the Round 10 integrated and
self-completion respondent files with their HTML codebooks. These large/raw
materials are ignored by Git. Their sources and checksums are recorded in
`documentation_manifest.md`.

The local `PartyFacts/` directory contains the published ESS–Party Facts linkage used
to bridge ESS party codes to PopuList through `partyfacts_id`. It is also ignored by Git
and inventoried in the documentation manifest.

The local `ParlGov/` directory contains the ParlGov 2024 stable SQLite release
used only for the exploratory government-context analysis. It is ignored by Git;
the release DOI is recorded in the documentation manifest.

All of these paths are ignored by Git. Do not commit source microdata, third-party
classification files, downloaded documentation, or other redistributed source data.
