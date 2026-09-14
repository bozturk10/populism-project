from populism_project.outcomes import write_analysis_base

if __name__ == "__main__":
    data, countries = write_analysis_base()
    print(
        f"Wrote Table C: {len(data):,} respondents, "
        f"{int(data['analysis_eligible'].sum()):,} classifiable voters, "
        f"{len(countries)} countries"
    )
