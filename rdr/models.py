"""Struktur data dasar RDR: Case, Condition, dan Node."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator, Optional

# Case = satu kasus konsumen, berupa pemetaan nama atribut -> nilai.
# Nilai numerik disimpan sebagai float, nilai kategorikal sebagai str.
Case = dict[str, Any]

NUMERIC_OPS = (">", ">=", "<", "<=")
CATEGORICAL_OPS = ("==", "!=")
OPERATORS = NUMERIC_OPS + CATEGORICAL_OPS


def format_value(value: Any) -> str:
    """Tampilkan 60.0 sebagai '60', tetapi 2.5 tetap '2.5'."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


@dataclass(frozen=True)
class Condition:
    """Satu kondisi atomik: <atribut> <operator> <nilai>."""

    attr: str
    op: str
    value: Any

    def __post_init__(self) -> None:
        if self.op not in OPERATORS:
            raise ValueError(f"Operator tidak dikenal: {self.op!r}")

    def evaluate(self, case: Optional[Case]) -> bool:
        """Atribut yang tidak ada pada kasus selalu membuat kondisi FALSE."""
        if case is None or case.get(self.attr) is None:
            return False
        v = case[self.attr]
        if self.op == "==":
            return v == self.value
        if self.op == "!=":
            return v != self.value
        try:
            v, target = float(v), float(self.value)
        except (TypeError, ValueError):
            return False
        if self.op == ">":
            return v > target
        if self.op == ">=":
            return v >= target
        if self.op == "<":
            return v < target
        return v <= target

    def __str__(self) -> str:
        return f"{self.attr} {self.op} {format_value(self.value)}"

    def to_dict(self) -> dict:
        return {"attr": self.attr, "op": self.op, "value": self.value}

    @classmethod
    def from_dict(cls, d: dict) -> "Condition":
        return cls(d["attr"], d["op"], d["value"])


@dataclass
class Node:
    """Node pada binary tree RDR.

    true_child  (anak kanan) = pengecualian, dikunjungi jika kondisi TRUE.
    false_child (anak kiri)  = alternatif, dikunjungi jika kondisi FALSE.
    Root memiliki conditions kosong sehingga selalu TRUE.
    """

    id: str
    conditions: list[Condition]
    conclusion: str
    cornerstone: Optional[Case] = None
    true_child: Optional["Node"] = None
    false_child: Optional["Node"] = None
    parent_id: Optional[str] = None
    branch: Optional[bool] = None  # True jika node ini true_child dari parent-nya
    exception_of: Optional[str] = None  # id node yang kesimpulannya dianulir

    def satisfied_by(self, case: Optional[Case]) -> bool:
        return all(c.evaluate(case) for c in self.conditions)

    def rule_text(self) -> str:
        cond = " AND ".join(str(c) for c in self.conditions) or "true"
        return f"IF {cond} THEN {self.conclusion}"

    def walk(self) -> Iterator["Node"]:
        """Preorder: node, lalu true_child, lalu false_child."""
        yield self
        if self.true_child:
            yield from self.true_child.walk()
        if self.false_child:
            yield from self.false_child.walk()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "conditions": [c.to_dict() for c in self.conditions],
            "conclusion": self.conclusion,
            "cornerstone": self.cornerstone,
            "parent_id": self.parent_id,
            "branch": self.branch,
            "exception_of": self.exception_of,
            "true_child": self.true_child.to_dict() if self.true_child else None,
            "false_child": self.false_child.to_dict() if self.false_child else None,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Node":
        return cls(
            id=d["id"],
            conditions=[Condition.from_dict(c) for c in d.get("conditions", [])],
            conclusion=d["conclusion"],
            cornerstone=d.get("cornerstone"),
            parent_id=d.get("parent_id"),
            branch=d.get("branch"),
            exception_of=d.get("exception_of"),
            true_child=cls.from_dict(d["true_child"]) if d.get("true_child") else None,
            false_child=cls.from_dict(d["false_child"]) if d.get("false_child") else None,
        )
