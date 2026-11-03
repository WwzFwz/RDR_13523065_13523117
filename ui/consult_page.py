"""Halaman konsultasi: input kasus -> kesimpulan -> konfirmasi pakar -> rule baru."""

from __future__ import annotations

import streamlit as st

from rdr import Condition, RDRError, ValidationError, save_domain, separates
from rdr.models import CATEGORICAL_OPS, NUMERIC_OPS

from . import state
from .tree_view import show_tree
from .widgets import (
    build_attribute, case_table, justification, new_attribute_fields, show_errors, value_input,
)


def render(expert_mode: bool) -> None:
    domain, kb = state.domain(), state.kb()
    fid = domain.folder.name

    with st.form(f"case_form_{fid}"):
        st.subheader("Data konsumen")
        cols = st.columns(min(3, len(domain.attributes)))
        raw = {}
        for i, attr in enumerate(domain.attributes):
            with cols[i % len(cols)]:
                raw[attr.name] = value_input(attr, key=f"in_{fid}_{attr.name}")
        submitted = st.form_submit_button("Cari rekomendasi", type="primary")

    if submitted:
        try:
            state.start_consult(domain.validate_case(raw))
        except ValidationError as e:
            show_errors(e.errors)
            return

    session = state.consult()
    if not session:
        st.caption(f"Isi semua atribut lalu tekan **Cari rekomendasi**. "
                   f"Default domain ini: *{domain.default_conclusion}*.")
        return

    case = session["case"]
    result = kb.infer(case)
    st.divider()
    st.markdown(f"### Rekomendasi: **{result.conclusion}**")
    st.caption(f"Diberikan oleh {result.last_true.id}: `{result.last_true.rule_text()}`")
    with st.expander("Justifikasi: jalur penelusuran", expanded=True):
        justification(result)
    with st.expander("Posisi kasus pada tree", expanded=False):
        show_tree(kb, result, "consult_tree")

    if not expert_mode:
        return

    stage = session["stage"]
    if stage == "done":
        st.success(session["message"])
        if st.button("Konsultasi kasus baru"):
            state.reset_consult()
            st.rerun()
        return

    if stage == "result":
        st.markdown("**Apakah pakar setuju dengan rekomendasi ini?**")
        c1, c2, _ = st.columns([1, 1, 4])
        if c1.button("Setuju", type="primary"):
            state.set_stage("done", f"Rekomendasi **{result.conclusion}** diberikan ke konsumen.")
            st.rerun()
        if c2.button("Tidak setuju"):
            state.set_stage("disagree")
            st.rerun()
        return

    render_correction(case, result)


def render_correction(case, result) -> None:
    domain, kb = state.domain(), state.kb()
    st.markdown("#### Koreksi pakar")

    options = [c for c in kb.conclusions() if c.lower() != result.conclusion.lower()]
    choice = st.selectbox("Kesimpulan yang benar", options, index=None, accept_new_options=True,
                          placeholder="Pilih kesimpulan yang ada atau ketik yang baru",
                          key="correct_conclusion")
    if st.button("Batal"):
        state.reset_consult()
        st.rerun()
    if not choice or not choice.strip():
        return
    conclusion = kb.canonical_conclusion(choice)
    if conclusion.lower() == result.conclusion.lower():
        st.info("Kesimpulan sama dengan rekomendasi sistem, jadi dianggap setuju. Tidak ada rule baru.")
        return

    corner = result.cornerstone
    cid = result.last_true.id
    st.markdown(f"Kesimpulan **{result.conclusion}** ({cid}) akan dianulir oleh rule baru.")
    if corner is None:
        st.caption(f"{cid} adalah rule default tanpa cornerstone, sehingga semua kondisi kasus "
                   "baru boleh dipilih.")
    else:
        st.caption(f"Kondisi harus dipenuhi kasus baru **dan tidak dipenuhi** cornerstone {cid}.")
    case_table(domain, case, corner, cid)

    diff = kb.difference_list(case, domain)
    if not diff:
        render_conflict(case, cid)
        return

    chosen = st.multiselect("Pilih kondisi dari difference list (digabung dengan AND)", diff,
                            format_func=str, placeholder="Pilih minimal satu kondisi",
                            key="chosen_conds")
    custom_condition_editor(case, corner)
    chosen = list(dict.fromkeys(chosen + state.custom_conds()))
    if not chosen:
        return

    side = "trueChild" if result.last_result else "falseChild"
    cond_text = " AND ".join(str(c) for c in chosen)
    st.code(f"IF {cond_text} THEN {conclusion}", language=None)
    st.caption(f"Akan ditempel sebagai {result.last_eval.id}.{side}, pengecualian dari {cid}.")
    if st.button("Tambah rule", type="primary"):
        try:
            node = kb.add_rule(case, conclusion, chosen)
        except RDRError as e:
            st.error(str(e))
            return
        state.persist()
        state.set_stage("done", f"Rule **{node.id}** ditambahkan: `{node.rule_text()}`. "
                                f"Rekomendasi untuk konsumen: **{node.conclusion}**.")
        st.rerun()


def custom_condition_editor(case, corner) -> None:
    """Kondisi dengan threshold/nilai sendiri; tetap harus memisahkan kasus dari cornerstone."""
    domain = state.domain()
    with st.expander("Kondisi kustom (misalnya mengubah threshold numerik)"):
        c1, c2, c3 = st.columns([2, 1, 2])
        attr = domain.attribute(c1.selectbox("Atribut", [a.name for a in domain.attributes],
                                             key="custom_attr"))
        op = c2.selectbox("Operator", NUMERIC_OPS if attr.is_numeric else CATEGORICAL_OPS,
                          key=f"custom_op_{attr.name}")
        with c3:
            value = value_input(attr, key=f"custom_val_{attr.name}", value=case.get(attr.name))
        if st.button("Tambahkan kondisi kustom"):
            if value is None:
                st.error("Isi nilainya terlebih dahulu")
            else:
                cond = Condition(attr.name, op, float(value) if attr.is_numeric else value)
                if separates(cond, case, corner):
                    if cond not in state.custom_conds():
                        state.custom_conds().append(cond)
                else:
                    st.error(f"`{cond}` harus TRUE untuk kasus baru dan FALSE untuk cornerstone")
        for i, cond in enumerate(state.custom_conds()):
            k1, k2 = st.columns([5, 1])
            k1.markdown(f"- `{cond}` (ikut dipakai)")
            if k2.button("Hapus", key=f"del_custom_{i}"):
                state.custom_conds().pop(i)
                st.rerun()


def render_conflict(case, cid) -> None:
    domain = state.domain()
    st.warning(
        f"**Conflict:** tidak ada kondisi yang membedakan kasus ini dari cornerstone {cid} "
        "(difference list kosong). Rule lama tidak diubah. Pilihannya: batalkan koreksi, "
        "atau tambahkan atribut baru yang membedakan kedua kasus."
    )
    with st.form("conflict_attr_form"):
        st.markdown("**Tambah atribut baru**")
        fields = new_attribute_fields("conflict")
        raw_value = st.text_input("Nilai atribut ini untuk kasus sekarang")
        st.caption("Cornerstone lama tidak memiliki nilai atribut ini, sehingga kondisinya "
                   "dianggap FALSE untuk cornerstone tersebut.")
        if st.form_submit_button("Tambah atribut"):
            try:
                attr = build_attribute(fields)
                attr.check()
                value = attr.parse(raw_value)
                domain.add_attribute(attr)
            except ValidationError as e:
                show_errors(e.errors)
                return
            except ValueError as e:
                show_errors([str(e)])
                return
            save_domain(domain)
            case[attr.name] = value
            st.rerun()
