import pandas as pd

from .config import ANALYSIS_BASE, PROCESSED

AUDIT_COLUMNS = [
    "respondent_key",
    "cntry",
    "source_dataset",
    "mode",
    "stratum",
    "psu",
    "stratum",
    "psu",
    "vote_status",
    "outcome_status",
    "analysis_eligible",
    "ess_variable",
    "ess_party_code",
    "ess_party_label",
    "partyfacts_id",
    "name_english",
    "populist_party_name",
    "voted_populist",
    "voted_borderline",
    "classification_source",
    "response_status",
    "alliance_status",
    "manual_relationship",
    "manual_target_partyfacts_id",
    "manual_target_party",
    "manual_evidence",
    "election_date",
    "dweight",
    "pspwght",
    "pweight",
    "anweight",
]


def load_outcome_audit() -> tuple[pd.DataFrame, pd.DataFrame]:
    data = pd.read_csv(ANALYSIS_BASE, low_memory=False, usecols=AUDIT_COLUMNS)
    countries = pd.read_csv(PROCESSED / "ess10_outcome_by_country.csv")
    return data, countries
