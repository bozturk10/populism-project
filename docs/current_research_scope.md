# Current research scope and source hierarchy

## Purpose

This document reconciles the professor-approved email proposal, the final
research plan, subsequent group discussion,
and the implemented Round 10 pipeline. It prevents superseded alternatives from
silently returning to the main analysis.

## Source hierarchy

1. The professor-approved email proposal and reply define the substantive scope.
2. Explicit later decisions recorded in `docs/methods_decision_log.md` define the
   implemented operationalization.
3. `plans/analysis-plan.md` and `plans/stage-4-task.md` define current execution.
4. The Concise Research Plan DOCX is a historical planning document. It contains
   useful candidate variables and cautions but also broader alternatives that are not
   current commitments.

## Course and scope guidance from Professor Theocharis

- Empirical survey analysis is permitted; the assignment does not require a full-scale
  empirical study.
- ESS Round 10 combined with PopuList fits the course and proposed question.
- The central theoretical contribution should distinguish institutional distrust from
  specifically populist people-centred and anti-elite attitudes. Low institutional
  trust is not itself populism.
- H1 and H2 work well together because H2 asks whether the more explicitly
  people-centred and anti-elite preference contributes information beyond distrust.
- The interaction idea was discussed but is excluded from the final scope to keep the
  paper proportionate.
- Operationalization must remain close to the concepts.

## Current main question

How is distrust in representative political institutions associated with electoral
support for populist parties, and does the importance attached to ordinary people's
views prevailing over political elites contribute additional information beyond
political distrust?

On 2026-09-11 the owner considered, then withdrew before implementation, an extension
of H2 to the broader three-item People-Centrism measure. The final scope retains the
narrow, item-matched H2 using `viepol` alone.

The unit of analysis is the individual ESS Round 10 respondent. Country is context and
must be handled in the model; the study estimates associations, not causal effects.

## Current primary hypotheses

**H1 Institutional distrust:** Greater distrust in representative political
institutions and actors (`trstprl`, `trstplt`, `trstprt`) is associated with a higher
probability of voting for a populist party.

H1 is stated as an individual-level association across the Round 10 analysis sample.
It is not a hypothesis about country differences. The model will account for country
context so the pooled association is not driven only by stable between-country
differences.

**H2 People's representational priority over elites:** Greater importance attached to
ordinary people's views prevailing over those of political elites (`viepol`) is
associated with a higher probability of voting for a populist party, after accounting
for political distrust.

The preferred Turkish working label is **halkın elitlere karşı temsili önceliği**. ESS
places `viepol` under Anti-Elitism; the paper uses the item-specific label above to
avoid implying that this single item measures every aspect of anti-elitism or the
broader People-Centrism construct.

There is no H3 or interaction hypothesis in the current project.

## Implemented operationalization

- Outcome: `voted_populist`, defined among reported voters with a classifiable party
  choice using the documented ESS–Party Facts–PopuList bridge.
- H1 predictor: reverse-coded trust in parliament (`trstprl`), politicians (`trstplt`),
  and political parties (`trstprt`), combined only after the Stage 4 measurement gate.
- H2 predictor: `viepol` (ordinary people's views should prevail over political elites).
- Sensitivity only: `wpestop` (the will of the people cannot be stopped), kept separate
  because its wording is more ambiguous.
- Adjustment candidates: age (`agea`), gender (`gndr`), and education (`eisced`) as a
  limited demographic set; political interest (`polintr`) in a separate expanded model.
  `mainact` is excluded in its current form.

## Out of the current main scope

The following appeared in the historical DOCX but are not current primary commitments:

- extending the analysis to ESS Rounds 9 and 11;
- making external political efficacy (`psppsgva`, `psppipla`) a primary hypothesis;
- left- versus right-populist party-family multinomial models;
- an interaction between institutional distrust and people-centred anti-elite
  preference;
- redistribution, immigration, social-media, abstention, and social-connectedness
  extensions;
- treating `lrscale`, government satisfaction, economic insecurity, or a large control
  battery as default adjustments.

These may be mentioned as future work or reinstated only by an explicit group decision.

## Considered and rejected measurement extension

Dolci and Melli (2025) validate a broader three-item People-Centrism dimension using
`votedir`, `viepol`, and `wpestop`. The project considered adopting this broader
operationalization, but decided not to expand H2. The three items are not interchangeable
expressions of the same unambiguous content, so combining them would broaden the target
beyond the specific people-over-elite preference stated in H2. External political
efficacy and the earlier interaction also remain outside the main scope.

The theoretical discussion should compare this later grouping with the ESS module's own
conceptual taxonomy: ESS places `votedir` in its Direct Democracy model, `viepol` under
Anti-Elitism, and `wpestop` under Unrestricted Popular Sovereignty. The ESS pretest
trail further shows that explicit court and rule formulations for unrestricted popular
sovereignty created comprehension, face-validity, nonresponse, and cross-national
portability problems. The final `wpestop` wording removed the institutional constraint
and was not itself cognitively validated in the cited development report. The report
must discuss the resulting possibility of democratic-sovereignty as well as illiberal-
majoritarian interpretations. Treat Dolci and Melli's CFA evidence as evidence of
statistical structure, not by itself as proof that each indicator exclusively measures
People-Centrism. This evidence supports the narrow `viepol` operationalization and
should be reported as a construct-validity decision, not as a claim that Dolci and
Melli's broader measure is generally invalid.

## Interpretation discipline

- “Controlling for age” means comparing otherwise model-similar respondents while
  holding measured age constant; it does not show that age itself causes the outcome.
- Country indicators help prevent stable between-country differences from being
  mistaken for an individual-level relationship. They do not explain why countries
  differ.
- Do not claim that a country has higher distrust because of its age composition without
  a separate country-composition analysis.
- Report the unadjusted relationship and staged adjustments so readers can see what the
  controls change.
- Keep the paper concise: H1-H2 are the required empirical core; optional analyses must
  earn their space.
- Missing-data diagnostics remain proportional to a seminar paper: report variable and
  final model-sample loss, but do not add country-by-outcome missingness modelling unless
  a material problem appears.
- The analysis covers 23 countries with at least 30 classifiable voters in both
  outcome groups. This is a stability rule for the analytical sample, not a
  significance threshold.
