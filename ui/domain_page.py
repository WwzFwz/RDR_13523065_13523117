"""Halaman domain: lihat schema, ubah default, tambah atribut, buat domain baru."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from rdr import Domain, ValidationError, create_domain, format_value, save_domain

from . import state
from .widgets import build_attribute, new_attribute_fields, parse_values, show_errors


def render() -> None:
    domain = state.domain()
    st.subheader(f"Domain aktif: {domain.name}")
    st.caption(f"Folder: `domains/{domain.folder.name}/`")
    rows = [{
        "Atribut": a.name,
        "Tipe": a.type,
        "Nilai": ", ".join(a.values) if a.values else ("bebas" if not a.is_numeric else "—"),
        "Rentang": "—" if not a.is_numeric else
        f"{format_value(a.min) if a.min is not None else '-∞'} … "
        f"{format_value(a.max) if a.max is not None else '∞'}",
        "Satuan": a.unit or "",
    } for a in domain.attributes]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    c1, c2 = st.columns(2)
    with c1, st.form("default_form"):
        st.markdown("**Ubah default conclusion**")
        st.caption("Aman dilakukan kapan saja karena root tidak punya cornerstone.")
        new_default = st.text_input("Default", value=domain.default_conclusion)
        if st.form_submit_button("Simpan default") and new_default.strip():
            domain.default_conclusion = " ".join(new_default.split())
            state.kb().root.conclusion = domain.default_conclusion
            save_domain(domain)
            state.persist()
            st.rerun()
    with c2, st.form("add_attr_form", clear_on_submit=True):
        st.markdown("**Tambah atribut**")
        st.caption("Cornerstone lama tidak punya nilai atribut ini (kondisinya dianggap FALSE).")
        fields = new_attribute_fields("addattr")
        if st.form_submit_button("Tambah atribut"):
            try:
                domain.add_attribute(build_attribute(fields))
            except ValidationError as e:
                show_errors(e.errors)
            else:
                save_domain(domain)
                state.reset_consult()
                st.rerun()

    st.divider()
    render_new_domain()


def render_new_domain() -> None:
    st.subheader("Buat domain baru")
    st.caption("Domain baru selalu dimulai dari satu rule: `IF true THEN <default>`.")
    with st.form("new_domain_form"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Nama domain", placeholder="mis. Rekomendasi Skincare",
                             key="new_domain_name")
        default = c2.text_input("Default conclusion", placeholder="mis. Pelembap Umum",
                                key="new_domain_default")
        st.markdown("Atribut (tambah baris dengan tombol **+** di tabel):")
        table = st.data_editor(
            pd.DataFrame([{"nama": "", "tipe": "numeric", "nilai": "", "min": None, "max": None,
                           "satuan": ""}]),
            num_rows="dynamic", hide_index=True, width="stretch", key="new_domain_attrs",
            column_config={
                "nama": st.column_config.TextColumn("Nama", required=True),
                "tipe": st.column_config.SelectboxColumn("Tipe", options=["numeric", "categorical"],
                                                         required=True),
                "nilai": st.column_config.TextColumn("Nilai kategorikal (pisah koma)"),
                "min": st.column_config.NumberColumn("Min"),
                "max": st.column_config.NumberColumn("Max"),
                "satuan": st.column_config.TextColumn("Satuan"),
            },
        )
        if not st.form_submit_button("Buat domain", type="primary"):
            return

    try:
        folder = create_domain(state.domains_dir(),
                               domain_from_table(name, default, table.to_dict("records")))
    except ValidationError as e:
        show_errors(e.errors)
        return
    state.use_domain(folder)
    st.session_state.pending_domain = str(folder)
    st.rerun()


def domain_from_table(name: str, default: str, records: list[dict]) -> Domain:
    """Ubah isi form + tabel atribut menjadi Domain (baris tanpa nama diabaikan)."""
    attrs = {}
    for rec in records:
        attr_name = str(rec.get("nama") or "").strip()
        if not attr_name:
            continue
        cfg = {"type": rec.get("tipe") or "numeric"}
        if cfg["type"] == "categorical" and parse_values(rec.get("nilai")):
            cfg["values"] = parse_values(rec.get("nilai"))
        for key in ("min", "max"):
            if cfg["type"] == "numeric" and pd.notna(rec.get(key)):
                cfg[key] = float(rec[key])
        if cfg["type"] == "numeric" and str(rec.get("satuan") or "").strip():
            cfg["unit"] = str(rec["satuan"]).strip()
        attrs[attr_name] = cfg
    return Domain.from_dict({"name": name, "default_conclusion": default, "attributes": attrs})
