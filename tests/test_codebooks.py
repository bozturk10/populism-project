from populism_project.codebooks import parse_codebook, party_variables
from populism_project.config import ESS_CODEBOOKS


def test_party_code_extraction_and_special_missing_codes():
    main = parse_codebook(ESS_CODEBOOKS["ESS10e03_3"])
    assert main["vote"].missing_codes == frozenset({7, 8, 9})
    assert main["prtvtdgr"].values[5] == "Ελληνική Λύση"
    assert {"prtvclt1", "prtvclt2", "prtvclt3"} <= party_variables(main).keys()


def test_germany_has_two_party_variables():
    self_completion = party_variables(parse_codebook(ESS_CODEBOOKS["ESS10SCe03_2"]))
    assert {"prtvfde1", "prtvfde2"} <= self_completion.keys()
