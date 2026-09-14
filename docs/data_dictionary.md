# Table A–C data dictionary

## Authorized H2b extension on 2026-09-11

The primary H2a operationalization remains the single `viepol` item. H2b separately
examines whether `wpestop` and `votedir` add explanatory information without treating
the three variables as a homogeneous scale. The original H1–H2a outputs are preserved.

| Output field | Source | Valid values/range | Declared missing codes | Cleaning rule | Interpretation |
|---|---|---|---|---|---|
| `respondent_key` | `cntry`, `idno` | Unique text | None | `ESS10-{cntry}-{idno}` | Cross-file respondent identifier. |
| `source_dataset` | file name | `ESS10e03_3`, `ESS10SCe03_2` | None | Added during import. | ESS respondent release of origin. |
| `mode` / `mode_raw` | ESS `mode` | Codebook categories | Codebook-specific | Cleaned value plus unchanged raw value. | Interview/data-collection mode. |
| `psu` / `psu_raw` | ESS `psu` | Positive survey-design identifier within country | Codebook-specific | Preserve raw and cleaned numeric value; no cross-country pooling of identifiers. | Primary sampling unit used as the within-country cluster for Stage 9A uncertainty. |
| `stratum` / `stratum_raw` | ESS `stratum` | Survey stratum identifier within country | Codebook-specific | Preserve raw and cleaned value for design audit. | Sampling stratum audited in Stage 9A; the implemented estimator clusters by PSU but does not perform full stratified Taylor linearization. |
| `dweight`, `pspwght`, `pweight`, `anweight` (and `_raw`) | ESS weights | Positive numeric where observed | Codebook-specific | Preserve raw; recode only declared special values. | Design, post-stratification, population and analysis weights. ESS recommends `anweight` by default for later analysis. |
| `vote` / `vote_raw` | ESS `vote` | 1 yes, 2 no, 3 ineligible | 7 refusal, 8 don't know, 9 no answer | Recode declared missing categories to null. | Participation in the referenced national election. |
| `vote_status` | `vote_raw` | `voted`, `non_voter`, `ineligible`, `refusal`, `dont_know`, `no_answer` | None | Map all six raw categories explicitly. | Voting eligibility/response status; non-voters are not non-populist voters. |
| `party_slot_{1..3}_variable` | applicable `prtv*` column | ESS variable name | Null if no slot | Preserve country-applicable party dimensions. | Source variable for a party response. |
| `party_slot_{1..3}_raw_code` | applicable `prtv*` value | Codebook values | Raw special codes retained | No recoding in slot. | Original response code for later reviewed crosswalk join. |
| Trust, efficacy, `viepol`, `wpestop`, `votedir`, and provisional-control fields (plus `_raw`) | Exact-named ESS variable | Per HTML codebook | Per HTML codebook | Preserve raw; replace only that variable's declared special codes. | Inputs retained for later measurement decisions; no composite is constructed. The trust fields preserve distinct domains. `viepol` captures people-over-elite representational priority; `wpestop` indicates unrestricted popular sovereignty but has an abstract wording caveat; `votedir` captures direct-democracy orientation. |

## Table B: `ess10_party_mapping.csv`

| Output field | Source | Cleaning rule | Interpretation |
|---|---|---|---|
| `ess_id` / `first_ess_id` | Party Facts ESS linkage | Preserve published values. | ESS party identifiers and harmonized party identity. |
| `partyfacts_id` | Party Facts ESS linkage and PopuList 4.0 | Numeric identifier; join only on nonmissing values, validate cardinality, and record reviewed source-identity conflicts as manual rules. | Primary identity bridge between ESS and PopuList; not a score or classification. |
| `parlgov_id` | PopuList 4.0 | Preserve when available. | Supporting ParlGov database identifier; not a score or classification. |
| `cntry`, `ess_variable`, `ess_party_code`, `ess_party_label` | ESS codebook | Preserve exact code-level values. | Unique ESS response-category key and label. |
| `respondent_count` | Table A | Count exact raw responses. | Shows whether a codebook category occurs in Round 10. |
| `response_status` | ESS codebook and Party Facts `technical` | Party, missing, other, independent candidate, or invalid. | Separates party choices from non-party answers. |
| PopuList classification fields | PopuList 4.0 | Join through `partyfacts_id`; apply documented historical validity at the referenced election. | External party classifications used in the later voting outcome. |
| `final_populist` | PopuList validity at `election_date` plus manual rules | 1 firm; 0 identified non-firm; null excluded/unresolved. | Primary party classification. An unlisted zero is an operational assumption, not a PopuList score. |
| `final_borderline` | PopuList validity plus manual rules | 0/1 | Election-valid borderline flag for sensitivity analysis. |
| `classification_source` | Derived | Identifier, unlisted, manual identity, manual alliance, outside coverage, or response status. | Audit trail for the final value. |
| `manual_relationship`, `manual_target_*`, `alliance_status`, `manual_evidence` | `data/manual/*.csv` | Preserve rule-table values. | Makes reviewed exceptions reproducible and inspectable. |
| `include_primary` | `final_populist` | Boolean | Whether the category can enter the primary binary outcome. |

`ess10_party_exceptions.csv` is the review subset: manual decisions, excluded rows,
and unused codebook categories lacking a Party Facts identifier. The complete mapping
remains the authoritative Table B.

## Table C: `ess10_analysis_base.csv`

| Output field | Source/rule | Interpretation |
|---|---|---|
| `ess_variable`, `ess_party_code` | Table A party slots | Selected party response. Germany uses `prtvfde2`; Lithuania uses its first routed non-99 response; other countries use slot 1. |
| Party identity and provenance fields | Table B | Auditable party mapping attached to the respondent. |
| `voted_populist` | `final_populist`, only when `vote_status == voted` | Binary primary outcome; null outside the classifiable-voter sample. |
| `voted_borderline` | `final_borderline`, only for reported voters | Sensitivity flag; null for non-voters. |
| `outcome_status` | Voting, coverage, party-response and classification rules | Mutually exclusive reason for inclusion or exclusion. |
| `analysis_eligible` | Reported voter with nonmissing `voted_populist` | Membership in the primary outcome sample. |

`ess10_outcome_by_country.csv` reports classifiable and populist-voter counts by
country. `ess10_outcome_flow.md` records sequential exclusions and final statuses.

## Stage 4 constructed fields and model rules

The following fields are constructed in `analysis/04_measurement_diagnostics.py` for
diagnostics and sample definition. They do not overwrite Table C.

| Field/rule | Source | Coding | Role |
|---|---|---|---|
| `distrust_prl`, `distrust_plt`, `distrust_prt` | `trstprl`, `trstplt`, `trstprt` | `10 - source`; range 0–10, higher is more distrust | Item-level H1 diagnostics. |
| `distrust_index_three` | Three distrust items | Arithmetic mean only when all three are observed | Primary H1 predictor. |
| `distrust_index_two_plus` | Three distrust items | Arithmetic mean when at least two are observed | Stage 7 sensitivity only. |
| `age_decades_50` | `agea` | `(agea - 50) / 10`; modelled linearly | Primary control; coefficients are per decade around age 50. |
| `gndr` | Cleaned ESS field | Categorical; 1 male reference, 2 female | Primary control. The binary source coding is retained and its limitation must be reported. |
| `eisced_model` | `eisced` | Categories 1–7; category 4 reference; valid but unharmonized code 55 set missing for modelling | Primary education control without imposing equal distances between levels. |
| `polintr` | Cleaned ESS field | Categorical 1–4; category 4 “not at all interested” reference | Expanded-model control only. |
| `mode` | Cleaned ESS field | Categorical 1–4; category 1 CAPI reference | Descriptive characteristic; one sensitivity model adds it as a control. |
| Primary country sample | Country outcome cells | At least 30 classifiable voters in both outcome groups | Excludes CY, GB, LT, and PT from primary country-fixed-effect models. |
| Primary weight | `anweight` | Positive supplied value; no rescaling in Stage 4 | Used in primary estimates; the final specification is repeated once unweighted. |
| Missing-data rule | Model variables | Model-specific complete cases | No imputation; exact H1/H2 sample sizes are reported separately. |

`viepol` remains on its cleaned 0–10 source scale as the primary H2 indicator.
`wpestop` remains on its cleaned 0–10 source scale as a separate Stage 7 sensitivity
indicator. `votedir` is retained on its cleaned 0–10 source scale: 0 means that direct
referendum decision-making is not at all important for democracy and 10 means it is
extremely important. Its ESS special codes 77 (refusal), 88 (don't know), and 99
(no answer) are missing; the `_raw` field is unchanged. H2b enters all three items
separately and never averages them.

## H2b outputs and estimands

The H2b common sample requires the primary H1–H2a variables plus observed `wpestop`
and `votedir`. The base H2a specification is refitted on that same sample before the
extended model adds both variables, so the nested comparison is not confounded by
sample change. The primary incremental test is a two-parameter Wald F test with 2 and
22 degrees of freedom. Conventional AIC/BIC are not reported for the weighted GEE;
same-sample weighted Brier score and log loss are descriptive fit measures. Files
`data/processed/votedir_cleaning_by_country.csv` and
`data/processed/h2b_complete_case_keys.csv` audit cleaning and membership; detailed
tables are prefixed `outputs/tables/h2b_`.

## Stage 6 model estimands and outputs

Stage 6 does not add fields to the respondent-level processed data. It constructs
model-specific complete-case samples in memory and writes report-facing summaries.

| Output/estimand | Definition | Interpretation |
|---|---|---|
| Log-odds coefficient | Weighted logistic GEE coefficient with country fixed intercepts | Conditional association on the log-odds scale; country-clustered robust uncertainty is reported with 22 df. |
| Odds ratio | Exponentiated log-odds coefficient | Multiplicative change in conditional odds for a one-point increase; not a risk ratio. |
| Average marginal effect | Weighted average of `beta * p * (1 - p)` over the model sample | Average probability-point change associated with a one-point increase in a continuous focal predictor. |
| Standardized predicted probability | Set one focal score to a common value for every model observation, predict, then average using `anweight` | Model-based descriptive standardization over the observed covariate distribution; not an intervention effect. |
| Country influence | Change in the primary M2 focal coefficient after omitting one country and refitting | Composition diagnostic only; it is not used to select countries. |

M1 is the adjusted H1 model with political distrust, demographic controls, and country
indicators. M2 is the adjusted H2a model and adds `viepol`. M3 is the common-sample H2b
extension and adds `wpestop` and `votedir`. S1 adds political interest as a sensitivity
check, and S1-U repeats S1 without `anweight`.

## Stage 9 exploratory outputs and contextual fields

Stage 9A fits the M2 specification separately in each of the 23 primary countries,
using `anweight` and `psu` clusters. `stage9_country_effects.csv` reports coefficients,
odds ratios, average marginal effects, raw p-values, within-hypothesis Benjamini-Hochberg
q-values, intervals, sample sizes, and fixed descriptive evidence categories. The
random-effects synthesis uses country log-odds estimates; empirical-Bayes values are a
secondary display and do not replace the unpooled estimates.

| Field/output | Source/rule | Interpretation |
|---|---|---|
| `populist_in_pre_election_government` | ParlGov 2024 stable cabinet and cabinet-party tables joined by published identifiers | Country context: at least one election-active PopuList party participated in the last partisan cabinet governing immediately before the referenced election. |
| `partisan_cabinet_id` / `partisan_cabinet_name` | ParlGov cabinet data | If the immediate cabinet is caretaker, use the most recent preceding non-caretaker cabinet for the substantive context and retain the immediate cabinet in the audit. |
| `government_status` | Party crosswalk plus cabinet membership | `incumbent_populist`, `opposition_populist`, `non_populist`, or `unresolved`; derived from the same party choice as the outcome and therefore not entered as an ordinary respondent-level control. |
| Stage 9B vote-type summaries | M2 complete cases and `anweight` | Descriptive weighted means and cells only; sparse/structurally empty categories prevented a defensible weighted multinomial model. |

The contextual source provenance and SHA-256 checksums are recorded in
the source documentation linked in `data/raw/documentation_manifest.md`. Party links use published Party Facts/ParlGov identifiers;
unresolved categories are retained explicitly rather than repaired by name matching.
