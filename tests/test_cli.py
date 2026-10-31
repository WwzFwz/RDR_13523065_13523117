"""Mode terminal dengan input yang di-script."""

import shutil
from pathlib import Path

import pytest

import cli
from rdr import load_domain, load_kb

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def domains(tmp_path, monkeypatch):
    shutil.copytree(ROOT / "domains" / "keuangan", tmp_path / "keuangan",
                    ignore=shutil.ignore_patterns("kb*.json"))
    monkeypatch.setattr(cli, "DOMAINS_DIR", tmp_path)
    return tmp_path


def run_cli(monkeypatch, answers, argv):
    it = iter(answers)
    monkeypatch.setattr("builtins.input", lambda prompt="": next(it))
    cli.main(argv)


def test_add_rule_then_resolve_conflict_with_new_attribute(domains, monkeypatch):
    log = domains / "sesi.txt"
    run_cli(monkeypatch, [
        "1", "30", "15", "tinggi", "pekerja",   # konsultasi -> default
        "n", "Saham", "5", "y",                 # koreksi: risiko == tinggi
        "1", "30", "15", "tinggi", "pekerja",   # kasus identik -> Saham
        "n", "Obligasi",                        # difference list kosong
        "y", "tanggungan", "1", "", "2",        # tambah atribut numerik, nilai 2
        "1", "y",                               # tanggungan >= 2
        "2", "0",                               # tampilkan tree, keluar
    ], ["--domain", "keuangan", "--log", str(log)])

    domain = load_domain(domains / "keuangan")
    kb = load_kb(domain)
    assert [n.rule_text() for n in kb.nodes()] == [
        "IF true THEN Tabungan Reguler",
        "IF risiko == tinggi THEN Saham",
        "IF tanggungan >= 2 THEN Obligasi",
    ]
    assert domain.has_attribute("tanggungan")
    text = log.read_text(encoding="utf-8")
    assert "REKOMENDASI: Tabungan Reguler" in text and "CONFLICT" in text
    assert "R2 ditambahkan" in text and "└─T─► R1" in text


def test_consumer_mode_never_asks_expert(domains, monkeypatch, capsys):
    run_cli(monkeypatch, ["1", "20", "2", "rendah", "pelajar", "0"],
            ["--domain", "keuangan", "--consumer"])
    out = capsys.readouterr().out
    assert "REKOMENDASI: Tabungan Reguler" in out and "Pakar setuju" not in out


def test_invalid_input_is_asked_again(domains, monkeypatch, capsys):
    run_cli(monkeypatch, ["1", "abc", "30", "15", "ekstrem", "tinggi", "pekerja", "y", "0"],
            ["--domain", "keuangan"])
    out = capsys.readouterr().out
    assert "harus berupa angka" in out and "harus salah satu dari" in out


def test_create_domain_wizard(domains, monkeypatch):
    run_cli(monkeypatch, [
        "2",                                     # pilih "Buat domain baru"
        "Rekomendasi Skincare", "Pelembap Umum",
        "jenis_kulit", "2", "kering, berminyak",
        "umur", "1", "tahun",
        "",                                      # selesai atribut
        "0",
    ], [])
    d = load_domain(domains / "rekomendasi_skincare")
    assert d.default_conclusion == "Pelembap Umum"
    assert [a.name for a in d.attributes] == ["jenis_kulit", "umur"]
