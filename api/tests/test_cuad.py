from pathlib import Path

from lensor.clauses import CLAUSE_TYPES
from lensor.ingest.cuad import CuadContract, load_cuad, split_demo_eval

MINI = Path(__file__).parent / "fixtures" / "cuad_mini.json"


def test_load_cuad_maps_labels_to_spans() -> None:
    contracts = load_cuad(MINI)

    assert [c.title for c in contracts] == ["ACME-SUPPLY AGREEMENT", "BETA-LICENSE AGREEMENT"]
    acme, beta = contracts
    assert set(acme.labels) == set(CLAUSE_TYPES)
    assert acme.labels["Renewal Term"] == [(18, 53)]
    assert acme.labels["Governing Law"] == [(72, 104)]
    assert acme.labels["Cap on Liability"] == []
    assert "Document Name" not in acme.labels
    # "Cap On Liability" in the CUAD id maps to "Cap on Liability".
    assert beta.labels["Cap on Liability"] == [(9, 42), (78, 111)]
    for spans in beta.labels.values():
        for start, end in spans:
            assert 0 <= start < end <= len(beta.text)


def make(n: int) -> list[CuadContract]:
    return [CuadContract(title=f"C{i:03d}", text="x", labels={}) for i in range(n)]


def test_split_is_disjoint_and_stable() -> None:
    contracts = make(300)

    demo, evaluation = split_demo_eval(contracts)
    again_demo, again_eval = split_demo_eval(list(reversed(contracts)))

    assert (len(demo), len(evaluation)) == (50, 50)
    assert not {c.title for c in demo} & {c.title for c in evaluation}
    assert [c.title for c in demo] == [c.title for c in again_demo]
    assert [c.title for c in evaluation] == [c.title for c in again_eval]
