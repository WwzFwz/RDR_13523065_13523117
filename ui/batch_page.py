"""Uji banyak kasus sekaligus dari CSV (hanya inferensi, tanpa menambah rule)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from rdr import ValidationError

from . import state


def render() -> None:
    domain, kb = state.domain(), state.kb()
    names = [a.name for a in domain.attributes]
    st.write("Unggah CSV dengan kolom: " + ", ".join(f"`{n}`" for n in names)
             + ". Kolom `id` dan `expected` opsional.")
    st.download_button("Unduh template CSV", ",".join(["id", *names, "expected"]) + "\n",
                       file_name=f"template_{domain.folder.name}.csv", mime="text/csv")

    file = st.file_uploader("File CSV", type="csv")
    if not file:
        return
    df = pd.read_csv(file, dtype=str, keep_default_na=False)
    missing = [n for n in names if n not in df.columns]
    if missing:
        st.error(f"Kolom berikut tidak ada di CSV: {missing}")
        return

    rows = []
    for i, rec in df.iterrows():
        out = {"id": rec.get("id") or i + 1}
        try:
            res = kb.infer(domain.validate_case({n: rec[n] for n in names}))
            out.update({
                "kesimpulan": res.conclusion,
                "rule": res.last_true.id,
                "jalur": " → ".join(f"{s.node.id}({'T' if s.result else 'F'})" for s in res.path),
            })
            if rec.get("expected"):
                out["sesuai"] = "ya" if rec["expected"].strip().lower() == res.conclusion.lower() else "tidak"
        except ValidationError as e:
            out["error"] = "; ".join(e.errors)
        rows.append(out)

    result = pd.DataFrame(rows)
    if "sesuai" in result:
        ok = (result["sesuai"] == "ya").sum()
        st.metric("Sesuai expected", f"{ok}/{result['sesuai'].notna().sum()}")
    st.dataframe(result, hide_index=True, width="stretch")
    st.download_button("Unduh hasil", result.to_csv(index=False),
                       file_name=f"hasil_{domain.folder.name}.csv", mime="text/csv")
