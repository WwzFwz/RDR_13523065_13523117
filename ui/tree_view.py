"""Visualisasi tree RDR sebagai DOT (dirender Streamlit di browser, tanpa binary Graphviz).

Anak kiri = false-child (merah, F), anak kanan = true-child (hijau, T).
Cabang yang kosong diisi node tak terlihat supaya posisi kiri/kanan tetap konsisten.
"""

from __future__ import annotations

from typing import Optional

from rdr import InferenceResult, KnowledgeBase

TRUE_COLOR = "#2e7d32"
FALSE_COLOR = "#c62828"


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def to_dot(kb: KnowledgeBase, result: Optional[InferenceResult] = None) -> str:
    visited = {s.node.id: s.result for s in result.path} if result else {}
    fired = result.last_true.id if result else None

    lines = [
        "digraph RDR {",
        '  graph [ordering=out, nodesep=0.4, ranksep=0.45, bgcolor="transparent"];',
        '  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11, '
        'fillcolor="#f5f5f5", color="#9e9e9e"];',
        '  edge [fontname="Helvetica", fontsize=10, arrowsize=0.7];',
    ]
    for n in kb.nodes():
        cond = " AND\\n".join(_esc(str(c)) for c in n.conditions) or "true"
        label = f"{n.id}\\n{cond}\\n→ {_esc(n.conclusion)}"
        attrs = [f'label="{label}"']
        if n.id == fired:
            attrs += ['fillcolor="#c8e6c9"', f'color="{TRUE_COLOR}"', "penwidth=2.5"]
        elif n.id in visited:
            attrs += ['fillcolor="#fff8e1"', 'color="#f9a825"', "penwidth=2"]
        lines.append(f'  {n.id} [{", ".join(attrs)}];')

    for n in kb.nodes():
        if not (n.true_child or n.false_child):
            continue
        # Urutan deklarasi edge = urutan kiri -> kanan (ordering=out).
        for child, is_true in ((n.false_child, False), (n.true_child, True)):
            if child is None:
                ghost = f"{n.id}_{'T' if is_true else 'F'}_ghost"
                lines.append(f'  {ghost} [style=invis, label="", width=0.3];')
                lines.append(f"  {n.id} -> {ghost} [style=invis];")
                continue
            color = TRUE_COLOR if is_true else FALSE_COLOR
            taken = visited.get(n.id) is is_true and child.id in visited
            lines.append(
                f'  {n.id} -> {child.id} [label="{"T" if is_true else "F"}", color="{color}", '
                f'fontcolor="{color}", penwidth={3 if taken else 1.2}];'
            )
    lines.append("}")
    return "\n".join(lines)
