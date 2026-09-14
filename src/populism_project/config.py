from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
MANUAL = ROOT / "data" / "manual"

ESS_SOURCES = {
    "ESS10e03_3": RAW / "ESS_R10" / "ESS10e03_3" / "ESS10e03_3.csv",
    "ESS10SCe03_2": RAW / "ESS_R10" / "ESS10SCe03_2" / "ESS10SCe03_2.csv",
}
ESS_CODEBOOKS = {
    name: path.with_name(f"{name} codebook.html") for name, path in ESS_SOURCES.items()
}
POPULIST = RAW / "populist_4_0.csv"
PARTYFACTS_ESS_ALL = RAW / "PartyFacts" / "essprt-all.csv"
PARTY_OVERRIDES = MANUAL / "party_overrides.csv"
ALLIANCE_RULES = MANUAL / "alliance_rules.csv"
RESPONDENT_BASE = PROCESSED / "ess10_respondent_base.csv"
PARTY_MAPPING = PROCESSED / "ess10_party_mapping.csv"
ANALYSIS_BASE = PROCESSED / "ess10_analysis_base.csv"
