"""Skenario demo C1–C9 untuk domain keuangan.

Dipakai oleh test (tests/test_scenario.py) dan untuk mengisi KB demo:

    python -m scripts.demo_scenario            # cetak jalannya skenario
    python -m scripts.demo_scenario --save     # simpan hasilnya ke domains/keuangan/kb.json
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from rdr import Condition, KnowledgeBase, load_domain, save_kb

DOMAIN_DIR = Path(__file__).resolve().parent.parent / "domains" / "keuangan"


@dataclass
class ScenarioCase:
    id: str
    case: dict
    expert: Optional[str]  # None = pakar setuju
    chosen: tuple[Condition, ...] = ()


SCENARIO = [
    ScenarioCase("C1", {"umur": 20, "gaji": 2, "risiko": "rendah", "status": "pelajar"}, None),
    ScenarioCase("C2", {"umur": 30, "gaji": 15, "risiko": "tinggi", "status": "pekerja"}, "Saham",
                 (Condition("risiko", "==", "tinggi"),)),
    ScenarioCase("C3", {"umur": 25, "gaji": 8, "risiko": "sedang", "status": "pekerja"}, "Reksadana",
                 (Condition("risiko", "==", "sedang"),)),
    ScenarioCase("C4", {"umur": 60, "gaji": 20, "risiko": "tinggi", "status": "pensiun"}, "Deposito",
                 (Condition("status", "==", "pensiun"),)),
    ScenarioCase("C5", {"umur": 35, "gaji": 25, "risiko": "tinggi", "status": "pekerja"}, None),
    ScenarioCase("C6", {"umur": 22, "gaji": 3, "risiko": "tinggi", "status": "pelajar"}, "Reksadana",
                 (Condition("gaji", "<=", 3.0),)),
    ScenarioCase("C7", {"umur": 65, "gaji": 2, "risiko": "tinggi", "status": "pensiun"}, None),
    ScenarioCase("C8", {"umur": 50, "gaji": 40, "risiko": "sedang", "status": "pekerja"}, "Obligasi",
                 (Condition("gaji", ">=", 40.0),)),
    # C9 identik dengan C2 tetapi pakar meminta kesimpulan lain -> difference list kosong.
    ScenarioCase("C9", {"umur": 30, "gaji": 15, "risiko": "tinggi", "status": "pekerja"}, "Obligasi"),
]


def path_text(res) -> str:
    return " → ".join(f"{s.node.id}({'T' if s.result else 'F'})" for s in res.path) + " → null"


def run(kb: KnowledgeBase, domain, verbose: bool = True) -> KnowledgeBase:
    for sc in SCENARIO:
        case = domain.validate_case(sc.case)
        res = kb.infer(case)
        line = (f"{sc.id}: {path_text(res)} | output={res.conclusion} | "
                f"lastTrue={res.last_true.id} lastEval={res.last_eval.id}({'T' if res.last_result else 'F'})")
        if sc.expert is None or sc.expert == res.conclusion:
            line += " | pakar setuju"
        else:
            diff = kb.difference_list(case, domain)
            line += f" | pakar: {sc.expert} | diff={[str(c) for c in diff]}"
            if not diff:
                line += " | CONFLICT (difference list kosong)"
            else:
                node = kb.add_rule(case, sc.expert, list(sc.chosen))
                side = "trueChild" if node.branch else "falseChild"
                line += f" | {node.id}: {node.rule_text()} ditempel di {node.parent_id}.{side}"
        if verbose:
            print(line)
    return kb


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", action="store_true", help="simpan KB hasil skenario ke kb.json")
    args = ap.parse_args()
    domain = load_domain(DOMAIN_DIR)
    kb = run(KnowledgeBase(domain.default_conclusion), domain)
    print()
    print(kb.ascii_tree())
    print("verify:", kb.verify() or "semua cornerstone konsisten")
    if args.save:
        print("disimpan ke", save_kb(kb, domain))
