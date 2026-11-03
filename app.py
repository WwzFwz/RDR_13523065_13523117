"""Sistem pakar rekomendasi berbasis Ripple Down Rules.

Jalankan:  streamlit run app.py
"""

from pathlib import Path

import streamlit as st

from rdr import load_domain
from rdr.schema import list_domains
from ui import batch_page, consult_page, domain_page, kb_page, state

st.set_page_config(page_title="Sistem Pakar RDR", layout="wide")
# Sembunyikan "Press Enter to submit form" bawaan Streamlit yang menimpa placeholder input.
st.html("<style>[data-testid='InputInstructions'] { display: none; }</style>")

folders = list_domains(state.domains_dir())
if not folders:
    st.error(f"Belum ada domain. Buat folder berisi domain.json di `{state.domains_dir()}`.")
    st.stop()

# Domain yang baru dibuat langsung dipilih di sidebar.
pending = st.session_state.pop("pending_domain", None)
if pending:
    st.session_state.domain_select = pending

with st.sidebar:
    st.title("Sistem Pakar RDR")
    names = {str(f): load_domain(f).name for f in folders}
    selected = st.selectbox("Domain", list(names), format_func=names.get, key="domain_select",
                            on_change=lambda: st.session_state.pop("creating_domain", None))
    state.use_domain(Path(selected))
    if st.button("➕ Buat domain baru", width="stretch"):
        st.session_state.creating_domain = True

    expert_mode = st.toggle("Mode pakar", value=True,
                            help="Aktif: pakar mengonfirmasi rekomendasi dan dapat menambah rule. "
                                 "Nonaktif: mode konsumen, hanya menampilkan rekomendasi.")
    st.divider()
    kb = state.kb()
    st.metric("Jumlah rule", sum(1 for _ in kb.nodes()))
    st.caption(f"Default: {state.domain().default_conclusion}")
    st.caption(f"KB: `domains/{state.domain().folder.name}/kb.json`")

if st.session_state.get("creating_domain"):
    tab, = st.tabs(["Buat Domain Baru"])
    with tab:
        domain_page.render_new_domain()
    st.stop()

st.header(state.domain().name)
tabs = st.tabs(["Konsultasi", "Tree & Rule", "Uji Batch (CSV)", "Domain & Atribut"])
with tabs[0]:
    consult_page.render(expert_mode)
with tabs[1]:
    kb_page.render()
with tabs[2]:
    batch_page.render()
with tabs[3]:
    domain_page.render()
