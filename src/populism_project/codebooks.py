from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class Variable:
    name: str
    label: str
    question: str
    values: dict[int, str]
    missing_codes: frozenset[int]


def parse_codebook(path: Path) -> dict[str, Variable]:
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    result = {}
    for heading in soup.select("h3[id]"):
        blocks = [
            node for node in heading.find_next_siblings() if getattr(node, "name", None)
        ]
        blocks = blocks[
            : next((i for i, x in enumerate(blocks) if x.name == "h3"), len(blocks))
        ]
        texts = [x.get_text(" ", strip=True) for x in blocks]
        label = texts[0] if texts else ""
        table = next((x for x in blocks if x.name == "div" and x.find("table")), None)
        question_parts = [x for x in texts[1:] if not x.startswith("Value Category")]
        values: dict[int, str] = {}
        missing = set()
        if table:
            for row in table.select("tr"):
                cells = [c.get_text(" ", strip=True) for c in row.select("th,td")]
                if len(cells) < 2:
                    continue
                try:
                    code = int(float(cells[0]))
                except ValueError:
                    continue
                values[code] = cells[1].removesuffix("*").strip()
                if "*" in cells[1] or any("Missing value" in c for c in cells[2:]):
                    missing.add(code)
        result[heading["id"]] = Variable(
            heading["id"], label, " ".join(question_parts), values, frozenset(missing)
        )
    return result


def party_variables(variables: dict[str, Variable]) -> dict[str, Variable]:
    return {
        name: var
        for name, var in variables.items()
        if name.startswith("prtv") and "Party voted for" in var.label
    }
