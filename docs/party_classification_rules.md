# Primary party-classification rules

| ESS response at the referenced election | Primary value | Sensitivity handling |
|---|---:|---|
| Firm PopuList party | 1 | — |
| Identified party absent from PopuList in a covered country | 0 | Treat as an operational assumption |
| PopuList borderline party | 0 | Reclassify using `final_borderline` |
| Homogeneous alliance | 0 or 1 | Use the common component classification |
| Mixed or unresolved alliance | Exclude | Report separately if needed |
| Other, independent, invalid, or missing response | Exclude | — |
| Country outside PopuList coverage | Exclude | — |

Identity and alliance exceptions are applied from the two CSV rule tables in
`data/manual/`. They record the ESS key, decision, relationship or alliance type,
and evidence; the processing code contains no case-specific party names.
