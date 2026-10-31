"""Inferensi dan akuisisi pengetahuan Single Classification RDR."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Iterator, Optional

from .difference import difference_list
from .models import Case, Condition, Node
from .schema import Domain


class RDRError(ValueError):
    """Rule baru ditolak (kondisi tidak valid, kesimpulan sama, dst.)."""


@dataclass
class Step:
    node: Node
    result: bool


@dataclass
class InferenceResult:
    conclusion: str
    last_true: Node  # node pemberi kesimpulan
    last_eval: Node  # node terakhir yang dievaluasi (tempat node baru ditempel)
    last_result: bool  # hasil evaluasi last_eval
    path: list[Step] = field(default_factory=list)

    @property
    def cornerstone(self) -> Optional[Case]:
        return self.last_true.cornerstone


@dataclass
class VerifyIssue:
    node: Node
    got: str


def normalize_conclusion(text: str) -> str:
    return " ".join(text.split())


class KnowledgeBase:
    def __init__(self, default_conclusion: str, root: Optional[Node] = None, next_id: int = 1):
        self.root = root or Node("R0", [], normalize_conclusion(default_conclusion))
        self.next_id = next_id

    # ---------- inferensi ----------

    def infer(self, case: Case) -> InferenceResult:
        node: Optional[Node] = self.root
        last_true = last_eval = self.root
        last_result = True
        path: list[Step] = []
        while node is not None:
            last_eval = node
            if node.satisfied_by(case):
                last_true, last_result = node, True
                path.append(Step(node, True))
                node = node.true_child
            else:
                last_result = False
                path.append(Step(node, False))
                node = node.false_child
        return InferenceResult(last_true.conclusion, last_true, last_eval, last_result, path)

    # ---------- akuisisi pengetahuan ----------

    def difference_list(self, case: Case, domain: Domain) -> list[Condition]:
        return difference_list(case, self.infer(case).cornerstone, domain)

    def add_rule(self, case: Case, conclusion: str, conditions: list[Condition]) -> Node:
        """Tambah rule pengecualian bagi kesimpulan yang diberikan sistem untuk `case`.

        Setiap kondisi harus TRUE untuk kasus baru dan FALSE untuk cornerstone
        node pemberi kesimpulan (sesuai spesifikasi: dipilih dari difference list).
        """
        conclusion = self.canonical_conclusion(conclusion)
        if not conclusion:
            raise RDRError("Kesimpulan baru tidak boleh kosong")
        if not conditions:
            raise RDRError("Pilih minimal satu kondisi")
        res = self.infer(case)
        if conclusion.lower() == res.conclusion.lower():
            raise RDRError(f"Kesimpulan '{conclusion}' sama dengan kesimpulan sistem")
        for cond in conditions:
            if not cond.evaluate(case):
                raise RDRError(f"Kondisi '{cond}' tidak dipenuhi oleh kasus baru")
            if cond.evaluate(res.cornerstone):
                raise RDRError(
                    f"Kondisi '{cond}' juga dipenuhi cornerstone {res.last_true.id}, "
                    "sehingga cornerstone tersebut ikut teranulir"
                )

        node = Node(
            id=f"R{self.next_id}",
            conditions=list(dict.fromkeys(conditions)),
            conclusion=conclusion,
            cornerstone=copy.deepcopy(case),
            parent_id=res.last_eval.id,
            branch=res.last_result,
            exception_of=res.last_true.id,
        )
        if res.last_result:
            res.last_eval.true_child = node
        else:
            res.last_eval.false_child = node
        self.next_id += 1
        return node

    # ---------- utilitas ----------

    def nodes(self) -> Iterator[Node]:
        return self.root.walk()

    def find(self, node_id: str) -> Optional[Node]:
        return next((n for n in self.nodes() if n.id == node_id), None)

    def canonical_conclusion(self, text: str) -> str:
        """Samakan ejaan dengan kesimpulan yang sudah ada ('saham ' -> 'Saham')."""
        text = normalize_conclusion(text)
        return next((c for c in self.conclusions() if c.lower() == text.lower()), text)

    def conclusions(self) -> list[str]:
        return sorted({n.conclusion for n in self.nodes()}, key=str.lower)

    def verify(self) -> list[VerifyIssue]:
        """Jalankan ulang semua cornerstone; harus tetap berakhir di node-nya sendiri."""
        issues = []
        for node in self.nodes():
            if node.cornerstone is None:
                continue
            res = self.infer(node.cornerstone)
            if res.last_true is not node:
                issues.append(VerifyIssue(node, f"{res.conclusion} ({res.last_true.id})"))
        return issues

    def ascii_tree(self) -> str:
        lines = [f"{self.root.id} [{self._cond_text(self.root)}] -> {self.root.conclusion}"]

        def rec(node: Node, prefix: str) -> None:
            children = [(c, label) for c, label in ((node.true_child, "T"), (node.false_child, "F")) if c]
            for i, (child, label) in enumerate(children):
                last = i == len(children) - 1
                lines.append(
                    f"{prefix}{'└' if last else '├'}─{label}─► {child.id} "
                    f"[{self._cond_text(child)}] -> {child.conclusion}"
                )
                rec(child, prefix + ("      " if last else "│     "))

        rec(self.root, "")
        return "\n".join(lines)

    @staticmethod
    def _cond_text(node: Node) -> str:
        return " AND ".join(str(c) for c in node.conditions) or "true"

    def to_dict(self) -> dict:
        return {"next_id": self.next_id, "root": self.root.to_dict()}

    @classmethod
    def from_dict(cls, d: dict) -> "KnowledgeBase":
        root = Node.from_dict(d["root"])
        return cls(root.conclusion, root, d.get("next_id", 1))
