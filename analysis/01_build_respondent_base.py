from populism_project.respondents import write_respondent_base

if __name__ == "__main__":
    data = write_respondent_base()
    print(
        f"Wrote Table A: {len(data):,} respondents, {data['cntry'].nunique()} countries"
    )
