"""Halaman domain: lihat schema, ubah default, tambah atribut; plus halaman buat domain baru."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import json
from typing import Optional

from rdr import (
    Domain, KnowledgeBase, ValidationError, create_domain, format_value, save_domain, save_kb,
)

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


def render_new_domain() -> None:
    """Halaman tersendiri, dibuka dari tombol di sidebar."""
    st.subheader("Buat domain baru")
    st.caption("Domain baru selalu dimulai dari satu rule: `IF true THEN <default>`.")
    if st.button("Batal", key="cancel_new_domain"):
        st.session_state.pop("creating_domain", None)
        st.rerun()
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
        submitted = st.form_submit_button("Buat domain", type="primary")

    with st.form("import_domain_form"):
        st.markdown("**Atau impor dari file** (hasil unduhan / isi folder domain lain)")
        st.caption("`kb.json` opsional; tanpa file ini domain dimulai dari `IF true THEN <default>`.")
        domain_file = st.file_uploader("domain.json", type="json", key="import_domain_file")
        kb_file = st.file_uploader("kb.json (opsional)", type="json", key="import_kb_file")
        imported = st.form_submit_button("Impor domain")

    try:
        if submitted:
            folder = create_domain(state.domains_dir(),
                                   domain_from_table(name, default, table.to_dict("records")))
        elif imported:
            if domain_file is None:
                raise ValidationError(["Upload domain.json terlebih dahulu"])
            domain, kb = domain_from_files(domain_file.getvalue(),
                                           kb_file.getvalue() if kb_file else None)
            folder = create_domain(state.domains_dir(), domain)
            if kb:
                save_kb(kb, domain)
        else:
            return
    except ValidationError as e:
        show_errors(e.errors)
        return
    state.use_domain(folder)
    st.session_state.pending_domain = str(folder)
    st.session_state.pop("creating_domain", None)
    st.rerun()


def domain_from_files(domain_bytes: bytes,
                      kb_bytes: Optional[bytes]) -> tuple[Domain, Optional[KnowledgeBase]]:
    """Baca domain.json (+ kb.json) hasil upload; tolak sebelum ada yang ditulis ke disk."""
    try:
        domain = Domain.from_dict(json.loads(domain_bytes))
    except (ValueError, TypeError, AttributeError, KeyError) as e:
        errors = e.errors if isinstance(e, ValidationError) else [f"domain.json tidak valid: {e}"]
        raise ValidationError(errors)
    if kb_bytes is None:
        return domain, None
    try:
        kb = KnowledgeBase.from_dict(json.loads(kb_bytes))
    except (ValueError, TypeError, AttributeError, KeyError) as e:
        raise ValidationError([f"kb.json tidak valid: {e}"])

    names = {a.name for a in domain.attributes}
    errors = [f"Rule {n.id} memakai atribut '{c.attr}' yang tidak ada di domain.json"
              for n in kb.nodes() for c in n.conditions if c.attr not in names]
    if kb.root.conditions:
        errors.append("Root (R0) harus tanpa kondisi: IF true THEN <default>")
    ids = [n.id for n in kb.nodes()]
    if len(ids) != len(set(ids)):
        errors.append("kb.json memuat id rule yang sama lebih dari sekali")
    if errors:
        raise ValidationError(errors)
    kb.root.conclusion = domain.default_conclusion
    errors = [f"Cornerstone {i.node.id} kini menghasilkan {i.got}, bukan rule-nya sendiri"
              for i in kb.verify()]
    if errors:
        raise ValidationError(errors)
    # Jaga agar rule berikutnya tidak memakai id yang sudah ada.
    kb.next_id = max([kb.next_id] + [int(i[1:]) + 1 for i in ids if i[1:].isdigit()])
    return domain, kb


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
