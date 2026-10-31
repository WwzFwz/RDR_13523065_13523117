import pytest

from rdr import Condition, KnowledgeBase, RDRError

C = Condition
A = {"umur": 30.0, "gaji": 15.0, "risiko": "tinggi", "status": "pekerja"}
B = {"umur": 25.0, "gaji": 8.0, "risiko": "sedang", "status": "pekerja"}
D = {"umur": 60.0, "gaji": 20.0, "risiko": "tinggi", "status": "pensiun"}


@pytest.fixture
def kb():
    return KnowledgeBase("Tabungan Reguler")


def test_initial_kb_returns_default(kb):
    res = kb.infer(A)
    assert res.conclusion == "Tabungan Reguler"
    assert res.last_true is kb.root and res.last_eval is kb.root and res.last_result
    assert [(s.node.id, s.result) for s in res.path] == [("R0", True)]


def test_first_rule_becomes_true_child_of_root(kb):
    r1 = kb.add_rule(A, "Saham", [C("risiko", "==", "tinggi")])
    assert kb.root.true_child is r1 and kb.root.false_child is None
    assert (r1.parent_id, r1.branch, r1.exception_of) == ("R0", True, "R0")
    assert r1.cornerstone == A and r1.cornerstone is not A
    assert kb.infer(A).conclusion == "Saham"


def test_rule_attached_on_false_branch_is_exception_of_last_true(kb):
    r1 = kb.add_rule(A, "Saham", [C("risiko", "==", "tinggi")])
    r2 = kb.add_rule(B, "Reksadana", [C("risiko", "==", "sedang")])
    assert r1.false_child is r2
    assert (r2.parent_id, r2.branch, r2.exception_of) == ("R1", False, "R0")


def test_exception_compares_against_last_true_cornerstone(kb):
    kb.add_rule(A, "Saham", [C("risiko", "==", "tinggi")])
    # risiko == tinggi juga dipenuhi cornerstone R1 (A) -> ditolak.
    with pytest.raises(RDRError, match="cornerstone R1"):
        kb.add_rule(D, "Deposito", [C("risiko", "==", "tinggi")])
    r3 = kb.add_rule(D, "Deposito", [C("status", "==", "pensiun")])
    assert kb.find("R1").true_child is r3
    assert kb.infer(A).conclusion == "Saham"
    assert kb.infer(D).conclusion == "Deposito"


def test_condition_must_hold_for_new_case(kb):
    with pytest.raises(RDRError, match="tidak dipenuhi"):
        kb.add_rule(A, "Saham", [C("risiko", "==", "rendah")])


def test_same_conclusion_or_empty_rejected(kb):
    with pytest.raises(RDRError, match="sama"):
        kb.add_rule(A, " tabungan  reguler ", [C("risiko", "==", "tinggi")])
    with pytest.raises(RDRError, match="minimal satu"):
        kb.add_rule(A, "Saham", [])
    with pytest.raises(RDRError, match="kosong"):
        kb.add_rule(A, "   ", [C("risiko", "==", "tinggi")])
    assert kb.root.true_child is None and kb.next_id == 1


def test_conjunction_of_conditions(kb):
    r = kb.add_rule(D, "Deposito", [C("umur", ">=", 60.0), C("status", "==", "pensiun")])
    assert r.rule_text() == "IF umur >= 60 AND status == pensiun THEN Deposito"
    assert kb.infer({**D, "status": "pekerja"}).conclusion == "Tabungan Reguler"


def test_conclusion_spelling_follows_existing(kb):
    kb.add_rule(A, "Saham", [C("risiko", "==", "tinggi")])
    r = kb.add_rule(B, "  saham ", [C("risiko", "==", "sedang")])
    assert r.conclusion == "Saham"
    assert kb.conclusions() == ["Saham", "Tabungan Reguler"]


def test_verify_detects_broken_cornerstone(kb):
    r1 = kb.add_rule(A, "Saham", [C("risiko", "==", "tinggi")])
    assert kb.verify() == []
    # Rusak tree secara manual (tidak mungkin terjadi lewat add_rule).
    r1.conditions = [C("risiko", "==", "rendah")]
    issues = kb.verify()
    assert [i.node.id for i in issues] == ["R1"]


def test_kb_dict_roundtrip(kb):
    kb.add_rule(A, "Saham", [C("risiko", "==", "tinggi")])
    kb.add_rule(D, "Deposito", [C("status", "==", "pensiun")])
    back = KnowledgeBase.from_dict(kb.to_dict())
    assert back.to_dict() == kb.to_dict()
    assert back.infer(D).conclusion == "Deposito"
