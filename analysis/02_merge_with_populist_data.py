from populism_project.parties import write_party_mapping

if __name__ == "__main__":
    mapping, exceptions = write_party_mapping()
    print(
        f"Wrote {len(mapping):,} ESS party-code rows and "
        f"{len(exceptions):,} documented exceptions"
    )
