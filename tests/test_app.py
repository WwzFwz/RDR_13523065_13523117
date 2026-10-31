"""Smoke test UI Streamlit (headless) dengan folder domain sementara.

KB awal diisi skenario C1–C8 supaya kesimpulan yang dipakai sudah ada di pilihan
(AppTest belum bisa mengetik opsi baru pada selectbox accept_new_options).
"""

import json
import shutil
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from rdr import Condition, KnowledgeBase, load_domain, save_kb
from scripts.demo_scenario import run
from ui.domain_page import domain_from_table

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def app(tmp_path, monkeypatch):
    shutil.copytree(ROOT / "domains" / "keuangan", tmp_path / "keuangan",
                    ignore=shutil.ignore_patterns("kb*.json"))
    domain = load_domain(tmp_path / "keuangan")
    save_kb(run(KnowledgeBase(domain.default_conclusion), domain, verbose=False), domain)
    monkeypatch.setenv("RDR_DOMAINS_DIR", str(tmp_path))
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30)
    at.run()
    assert not at.exception
    return at, tmp_path / "keuangan"


def button(at, label):
    return next(b for b in at.button if b.label == label)


def submit_case(at, umur, gaji, risiko, status):
    at.number_input(key="in_keuangan_umur").set_value(umur)
    at.number_input(key="in_keuangan_gaji").set_value(gaji)
    at.selectbox(key="in_keuangan_risiko").select(risiko)
    at.selectbox(key="in_keuangan_status").select(status)
    button(at, "Cari rekomendasi").click().run()
    assert not at.exception


def disagree(at, conclusion):
    button(at, "Tidak setuju").click().run()
    at.selectbox(key="correct_conclusion").select(conclusion).run()
    assert not at.exception


def markdown_text(at):
    return "\n".join(m.value for m in at.markdown)


def test_add_rule_through_ui(app):
    at, folder = app
    # R0(T) -> R1(F) -> R2(F) -> null : default, lastEval = R2 (FALSE)
    submit_case(at, 70.0, 10.0, "rendah", "pensiun")
    assert "Rekomendasi: **Tabungan Reguler**" in markdown_text(at)

    disagree(at, "Deposito")
    ms = at.multiselect(key="chosen_conds")
    assert "status == pensiun" in ms.options
    ms.set_value([Condition("status", "==", "pensiun")]).run()
    assert any("R2.falseChild" in c.value for c in at.caption)
    button(at, "Tambah rule").click().run()
    assert not at.exception
    assert "Rekomendasi: **Deposito**" in markdown_text(at)

    kb = json.loads((folder / "kb.json").read_text(encoding="utf-8"))
    r6 = kb["root"]["true_child"]["false_child"]["false_child"]
    assert (r6["id"], r6["conclusion"], r6["exception_of"]) == ("R6", "Deposito", "R0")


def test_conflict_when_difference_list_empty(app):
    at, _ = app
    submit_case(at, 30.0, 15.0, "tinggi", "pekerja")  # identik dengan cornerstone R1
    disagree(at, "Obligasi")
    assert any("Conflict" in w.value for w in at.warning)


def test_agree_flow(app):
    at, _ = app
    submit_case(at, 65.0, 2.0, "tinggi", "pensiun")
    assert "Rekomendasi: **Deposito**" in markdown_text(at)
    button(at, "Setuju").click().run()
    assert any("diberikan ke konsumen" in s.value for s in at.success)


def test_invalid_input_shows_errors(app):
    at, _ = app
    button(at, "Cari rekomendasi").click().run()
    assert at.error and "wajib diisi" in at.error[0].value


def test_new_domain_requires_attributes(app):
    at, _ = app
    at.text_input(key="new_domain_name").set_value("Rekomendasi Skincare")
    at.text_input(key="new_domain_default").set_value("Pelembap Umum")
    button(at, "Buat domain").click().run()
    assert any("minimal satu atribut" in e.value for e in at.error)


def test_domain_from_table():
    d = domain_from_table("Rekomendasi Skincare", "Pelembap Umum", [
        {"nama": "jenis_kulit", "tipe": "categorical", "nilai": "kering, berminyak, kering"},
        {"nama": "umur", "tipe": "numeric", "min": 12, "max": float("nan"), "satuan": "tahun"},
        {"nama": "", "tipe": "numeric"},
    ])
    assert d.to_dict()["attributes"] == {
        "jenis_kulit": {"type": "categorical", "values": ["kering", "berminyak"]},
        "umur": {"type": "numeric", "min": 12.0, "unit": "tahun"},
    }
