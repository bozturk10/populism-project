from collections.abc import Mapping

import pandas as pd

from .codebooks import Variable, parse_codebook, party_variables
from .config import ESS_CODEBOOKS, ESS_SOURCES, PROCESSED

CORE = [
    "essround",
    "edition",
    "proddate",
    "idno",
    "cntry",
    "mode",
    "stratum",
    "psu",
    "stratum",
    "psu",
    "dweight",
    "pspwght",
    "pweight",
    "anweight",
    "vote",
    "ppltrst",
    "trstprl",
    "trstlgl",
    "trstplc",
    "trstplt",
    "trstprt",
    "trstep",
    "trstun",
    "trstsci",
    "psppsgva",
    "psppipla",
    "viepol",
    "wpestop",
    "votedir",
    "polintr",
    "lrscale",
    "hincfel",
    "gincdif",
    "stfgov",
    "stfdem",
    "agea",
    "gndr",
    "edulvlb",
    "eisced",
    "eduyrs",
    "mainact",
]


def recode(series: pd.Series, variable: Variable) -> pd.Series:
    return series.mask(series.isin(variable.missing_codes))


def vote_status(series: pd.Series) -> pd.Series:
    return series.map(
        {
            1: "voted",
            2: "non_voter",
            3: "ineligible",
            7: "refusal",
            8: "dont_know",
            9: "no_answer",
        }
    ).astype("string")


def construct_key(frame: pd.DataFrame) -> pd.Series:
    return "ESS10-" + frame["cntry"].astype(str) + "-" + frame["idno"].astype(str)


def build_respondent_base(
    sources: Mapping[str, object] = ESS_SOURCES,
) -> pd.DataFrame:
    frames = []
    for source, path in sources.items():
        codebook = parse_codebook(ESS_CODEBOOKS[source])
        header = pd.read_csv(path, nrows=0).columns
        parties = list(party_variables(codebook))
        columns = [x for x in CORE + parties if x in header]
        raw = pd.read_csv(path, usecols=columns, low_memory=False)
        output = {"respondent_key": construct_key(raw), "source_dataset": source}
        for name in columns:
            output[f"{name}_raw"] = raw[name]
            output[name] = (
                recode(raw[name], codebook[name]) if name in codebook else raw[name]
            )
        out = pd.DataFrame(output)
        out["vote_status"] = vote_status(raw["vote"])
        for slot in range(3):
            out[f"party_slot_{slot + 1}_variable"] = pd.NA
            out[f"party_slot_{slot + 1}_raw_code"] = pd.NA
        for country, indexes in raw.groupby("cntry").groups.items():
            active = [p for p in parties if raw.loc[indexes, p].notna().any()]
            for slot, name in enumerate(active[:3], 1):
                out.loc[indexes, f"party_slot_{slot}_variable"] = name
                out.loc[indexes, f"party_slot_{slot}_raw_code"] = raw.loc[indexes, name]
        frames.append(out)
    result = pd.concat(frames, ignore_index=True, sort=False)
    return result


def validate_respondent_base(frame: pd.DataFrame) -> None:
    assert len(frame) == 59_685
    assert frame["cntry"].nunique() == 31
    assert frame["respondent_key"].is_unique
    assert frame.groupby("source_dataset").size().to_dict() == {
        "ESS10SCe03_2": 22_074,
        "ESS10e03_3": 37_611,
    }
    for weight in ["dweight", "pspwght", "pweight", "anweight"]:
        assert pd.api.types.is_numeric_dtype(frame[weight])
        assert frame[weight].dropna().gt(0).all()


def write_respondent_base() -> pd.DataFrame:
    frame = build_respondent_base()
    validate_respondent_base(frame)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    frame.to_csv(PROCESSED / "ess10_respondent_base.csv", index=False)
    return frame
