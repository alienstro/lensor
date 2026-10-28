"""Load CUAD v1 and split it into the demo set and the evaluation set.

Confirmed layout of CUADv1.json (SQuAD style, read on 2026-10-26):
  {"version": "aok_v1.0", "data": [510 contracts]}
  contract: {"title": str, "paragraphs": [one item]}
  paragraph: {"context": full contract text, "qas": [41 items]}
  qa: {"id": "<title>__<Category Name>", "question": str, "is_impossible": bool,
       "answers": [{"text": str, "answer_start": int}]}
The category names in the ids use title case, for example "Cap On Liability".
"""

import json
import random
from dataclasses import dataclass, field
from pathlib import Path

from lensor.clauses import CLAUSE_TYPES, canonical_clause_type


@dataclass(frozen=True)
class CuadContract:
    title: str
    text: str
    # Lawyer label spans for the 10 clause types. An empty list means "no such clause".
    labels: dict[str, list[tuple[int, int]]] = field(default_factory=dict)


def load_cuad(json_path: Path) -> list[CuadContract]:
    raw = json.loads(Path(json_path).read_text(encoding="utf-8"))
    contracts = []
    for item in raw["data"]:
        paragraph = item["paragraphs"][0]
        text = paragraph["context"]
        labels: dict[str, list[tuple[int, int]]] = {name: [] for name in CLAUSE_TYPES}
        for qa in paragraph["qas"]:
            clause_type = canonical_clause_type(qa["id"].rsplit("__", 1)[-1])
            if clause_type is None:
                continue
            spans = {(a["answer_start"], a["answer_start"] + len(a["text"])) for a in qa["answers"]}
            labels[clause_type] = sorted(spans)
        contracts.append(CuadContract(title=item["title"], text=text, labels=labels))
    return contracts


def split_demo_eval(
    contracts: list[CuadContract], n_demo: int = 50, n_eval: int = 50, seed: int = 42
) -> tuple[list[CuadContract], list[CuadContract]]:
    """Pick two sets with no shared contract. The result does not depend on the input order."""
    if n_demo + n_eval > len(contracts):
        raise ValueError("Not enough contracts for the two sets")
    ordered = sorted(contracts, key=lambda c: c.title)
    random.Random(seed).shuffle(ordered)
    return ordered[:n_demo], ordered[n_demo : n_demo + n_eval]
