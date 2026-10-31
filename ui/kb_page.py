"""Halaman knowledge base: tree, daftar rule, verifikasi, ekspor, reset."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from rdr import format_value, reset_kb

from . import state
from .tree_view import to_dot


def render() -> None:
    domain, kb = state.domain(), state.kb()
    nodes = list(kb.nodes())

    c1, c2, c3 = st.columns(3)
    c1.metric("Jumlah rule", len(nodes))
    c2.metric("Kesimpulan unik", len(kb.conclusions()))
    c3.metric("Default", domain.default_conclusion)

    session = state.consult()
    result = kb.infer(session["case"]) if session else None
    st.subheader("Binary tree")
    st.caption("Anak kiri = **F** (false-child), anak kanan = **T** (true-child / pengecualian)."
               + (" Jalur kasus terakhir disorot; hijau = node pemberi kesimpulan." if result else ""))
    st.graphviz_chart(to_dot(kb, result), width="stretch")
    with st.expander("Tree dalam bentuk teks"):
        st.code(kb.ascii_tree(), language=None)

    st.subheader("Daftar rule")
    rows = []
    for n in nodes:
        rows.append({
            "ID": n.id,
            "Rule": n.rule_text(),
            "Posisi": "root" if n.parent_id is None
            else f"{n.parent_id}.{'trueChild' if n.branch else 'falseChild'}",
            "Pengecualian dari": n.exception_of or "—",
            "Cornerstone": "—" if n.cornerstone is None
            else ", ".join(f"{k}={format_value(v)}" for k, v in n.cornerstone.items()),
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Verifikasi KB (jalankan ulang semua cornerstone)"):
            issues = kb.verify()
            if issues:
                for i in issues:
                    st.error(f"{i.node.id}: cornerstone sekarang menghasilkan {i.got}, "
                             f"seharusnya {i.node.conclusion}")
            else:
                checked = sum(1 for n in nodes if n.cornerstone is not None)
                st.success(f"{checked} cornerstone diuji ulang, semuanya tetap mendapat "
                           "kesimpulan rule-nya sendiri.")
    with c2:
        st.download_button("Unduh kb.json",
                           json.dumps({"domain": domain.name, **kb.to_dict()}, indent=2,
                                      ensure_ascii=False),
                           file_name=f"kb_{domain.folder.name}.json", mime="application/json")

    with st.expander("Reset knowledge base"):
        st.write("KB kembali ke satu rule `IF true THEN default`. File lama di-backup sebagai "
                 "`kb.<waktu>.bak.json`.")
        sure = st.checkbox("Saya yakin ingin mereset KB")
        if st.button("Reset KB", disabled=not sure):
            state.set_kb(reset_kb(domain))
            state.reset_consult()
            st.rerun()
