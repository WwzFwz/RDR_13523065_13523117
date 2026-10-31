import pytest

from rdr import Condition, Node


@pytest.mark.parametrize("op,value,expected", [
    (">", 30, True), (">", 40, False),
    (">=", 40, True), (">=", 41, False),
    ("<", 50, True), ("<", 40, False),
    ("<=", 40, True), ("<=", 39, False),
])
def test_numeric_condition(op, value, expected):
    assert Condition("umur", op, value).evaluate({"umur": 40.0}) is expected


def test_categorical_condition():
    case = {"risiko": "tinggi"}
    assert Condition("risiko", "==", "tinggi").evaluate(case)
    assert not Condition("risiko", "==", "rendah").evaluate(case)
    assert Condition("risiko", "!=", "rendah").evaluate(case)


def test_missing_attribute_is_false():
    # Termasuk "!=": atribut yang tidak ada tidak dianggap memenuhi apa pun.
    assert not Condition("umur", ">", 1).evaluate({})
    assert not Condition("status", "!=", "x").evaluate({"umur": 3})
    assert not Condition("umur", ">", 1).evaluate(None)


def test_unknown_operator_rejected():
    with pytest.raises(ValueError):
        Condition("umur", "=>", 1)


def test_root_always_true_and_str():
    root = Node("R0", [], "Default")
    assert root.satisfied_by({}) and root.satisfied_by({"a": 1})
    assert root.rule_text() == "IF true THEN Default"
    assert str(Condition("gaji", ">=", 40.0)) == "gaji >= 40"
    assert str(Condition("gaji", ">=", 2.5)) == "gaji >= 2.5"


def test_node_roundtrip():
    n = Node("R1", [Condition("a", "==", "x"), Condition("b", ">", 2.0)], "Y", {"a": "x", "b": 3.0})
    n.true_child = Node("R2", [Condition("b", ">=", 5.0)], "Z", {"a": "x", "b": 5.0})
    back = Node.from_dict(n.to_dict())
    assert back.to_dict() == n.to_dict()
