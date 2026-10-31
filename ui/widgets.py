"""Widget yang dipakai lebih dari satu halaman."""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd
import streamlit as st

from rdr import NUMERIC, Attribute, Case, Domain, InferenceResult, format_value


def attr_label(attr: Attribute) -> str:
    return f"{attr.name} ({attr.unit})" if attr.unit else attr.name


def value_input(attr: Attribute, key: str, value: Any = None) -> Any:
    """Input satu nilai atribut sesuai tipenya; None berarti belum diisi."""
    label = attr_label(attr)
    if attr.is_numeric:
        as_float = lambda x: None if x is None else float(x)  # noqa: E731 (tipe harus seragam)
        return st.number_input(label, min_value=as_float(attr.min), max_value=as_float(attr.max),
                               value=as_float(value), step=1.0, format="%g",
                               placeholder="angka", key=key)
    if attr.values:
        index = attr.values.index(value) if value in attr.values else None
        return st.selectbox(label, attr.values, index=index, placeholder="Pilih…", key=key)
    return st.text_input(label, value=value or "", placeholder="teks", key=key) or None


def parse_values(text: str) -> Optional[list[str]]:
    vals = [v.strip() for v in (text or "").split(",") if v.strip()]
    return list(dict.fromkeys(vals)) or None


def new_attribute_fields(key: str) -> dict:
    """Field untuk mendefinisikan atribut baru (dipakai di dalam st.form)."""
    c1, c2 = st.columns(2)
    name = c1.text_input("Nama atribut", key=f"{key}_name").strip()
    type_ = c2.selectbox("Tipe", ["numeric", "categorical"], key=f"{key}_type")
    values = st.text_input("Daftar nilai (kategorikal, pisahkan koma; kosongkan = bebas)",
                           key=f"{key}_values")
    unit = st.text_input("Satuan (opsional, numerik)", key=f"{key}_unit").strip()
    return {"name": name, "type": type_, "values": values, "unit": unit}


def build_attribute(fields: dict) -> Attribute:
    numeric = fields["type"] == NUMERIC
    return Attribute(
        name=fields["name"],
        type=fields["type"],
        values=None if numeric else parse_values(fields["values"]),
        unit=(fields["unit"] or None) if numeric else None,
    )


def show_errors(errors: list[str]) -> None:
    st.error("\n".join(f"- {e}" for e in errors))


def case_table(domain: Domain, case: Case, cornerstone: Optional[Case], corner_id: str) -> None:
    rows = []
    for attr in domain.attributes:
        new = case.get(attr.name)
        old = cornerstone.get(attr.name) if cornerstone else None
        rows.append({
            "Atribut": attr.name,
            "Kasus baru": "—" if new is None else format_value(new),
            f"Cornerstone {corner_id}": "—" if old is None else format_value(old),
            "Berbeda": "ya" if cornerstone is not None and new != old else "",
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def justification(result: InferenceResult) -> None:
    rows = [{
        "Langkah": i + 1,
        "Node": s.node.id,
        "Rule": s.node.rule_text(),
        "Hasil": "TRUE → anak kanan" if s.result else "FALSE → anak kiri",
    } for i, s in enumerate(result.path)]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
