"""Skenario C1–C9 (sama dengan tabel di laporan)."""

from rdr import KnowledgeBase, load_domain
from scripts.demo_scenario import DOMAIN_DIR, SCENARIO, run


def build():
    domain = load_domain(DOMAIN_DIR)
    return run(KnowledgeBase(domain.default_conclusion), domain, verbose=False), domain


def test_final_tree_shape():
    kb, _ = build()
    r = {n.id: n for n in kb.nodes()}
    assert set(r) == {"R0", "R1", "R2", "R3", "R4", "R5"}
    assert r["R0"].true_child is r["R1"] and r["R0"].false_child is None
    assert r["R1"].true_child is r["R3"] and r["R1"].false_child is r["R2"]
    assert r["R3"].false_child is r["R4"] and r["R3"].true_child is None
    assert r["R2"].true_child is r["R5"]
    assert {i: r[i].exception_of for i in r if i != "R0"} == {
        "R1": "R0", "R2": "R0", "R3": "R1", "R4": "R1", "R5": "R2",
    }


def test_final_outputs_for_every_case():
    kb, domain = build()
    expected = {
        "C1": "Tabungan Reguler", "C2": "Saham", "C3": "Reksadana", "C4": "Deposito",
        "C5": "Saham", "C6": "Reksadana", "C7": "Deposito", "C8": "Obligasi", "C9": "Saham",
    }
    for sc in SCENARIO:
        assert kb.infer(domain.validate_case(sc.case)).conclusion == expected[sc.id], sc.id


def test_c7_order_matters():
    # gaji <= 3 benar untuk C7, tetapi R3 (TRUE) membuat R4 tidak pernah dicek.
    kb, domain = build()
    res = kb.infer(domain.validate_case(SCENARIO[6].case))
    assert [s.node.id for s in res.path] == ["R0", "R1", "R3"]


def test_c9_conflict_empty_difference():
    kb, domain = build()
    c9 = domain.validate_case(SCENARIO[8].case)
    assert kb.difference_list(c9, domain) == []


def test_no_regression():
    kb, _ = build()
    assert kb.verify() == []
