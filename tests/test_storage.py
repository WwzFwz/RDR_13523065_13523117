import json

import pytest

from rdr import (
    Attribute, Condition, Domain, ValidationError, create_domain, list_domains,
    load_domain, load_kb, reset_kb, save_kb,
)


def test_validate_case(domain):
    case = domain.validate_case({"umur": "30", "gaji": "2,5", "risiko": "TINGGI", "status": " pekerja "})
    assert case == {"umur": 30.0, "gaji": 2.5, "risiko": "tinggi", "status": "pekerja"}


def test_validate_case_collects_errors(domain):
    with pytest.raises(ValidationError) as e:
        domain.validate_case({"umur": "banyak", "gaji": "", "risiko": "ekstrem", "status": "x"})
    assert len(e.value.errors) == 3  # status bebas (tanpa daftar values)
    with pytest.raises(ValidationError):
        domain.validate_case({"umur": 5, "gaji": 1, "risiko": "rendah", "status": "x"})  # < min


def test_domain_config_errors():
    with pytest.raises(ValidationError):
        Domain.from_dict({"name": "X", "default_conclusion": "", "attributes": {"a": "numeric"}})
    with pytest.raises(ValidationError):
        Domain.from_dict({"name": "X", "default_conclusion": "Y", "attributes": {"a": "teks"}})
    with pytest.raises(ValidationError):
        Domain.from_dict({"name": "X", "default_conclusion": "Y", "attributes": {}})


def test_create_list_and_reload_domain(tmp_path, domain):
    folder = create_domain(tmp_path, domain)
    assert folder.name == "uji" and list_domains(tmp_path) == [folder]
    again = load_domain(folder)
    assert again.to_dict() == domain.to_dict()
    with pytest.raises(ValidationError):
        create_domain(tmp_path, domain)


def test_shorthand_attribute_written_back(tmp_path, domain):
    folder = create_domain(tmp_path, domain)
    data = json.loads((folder / "domain.json").read_text(encoding="utf-8"))
    assert data["attributes"]["gaji"] == "numeric"


def test_kb_save_load_reset(tmp_path, domain):
    create_domain(tmp_path, domain)
    kb = load_kb(domain)
    assert kb.root.true_child is None  # belum ada kb.json -> t -> default
    case = domain.validate_case({"umur": 30, "gaji": 15, "risiko": "tinggi", "status": "pekerja"})
    kb.add_rule(case, "Saham", [Condition("risiko", "==", "tinggi")])
    save_kb(kb, domain)

    loaded = load_kb(domain)
    assert loaded.infer(case).conclusion == "Saham" and loaded.next_id == 2

    fresh = reset_kb(domain)
    assert fresh.root.true_child is None
    assert not (domain.folder / "kb.json").exists()
    assert list(domain.folder.glob("kb.*.bak.json"))


def test_default_follows_domain_file(tmp_path, domain):
    create_domain(tmp_path, domain)
    save_kb(load_kb(domain), domain)
    domain.default_conclusion = "Konsultasi Lanjut"
    assert load_kb(domain).root.conclusion == "Konsultasi Lanjut"


def test_add_attribute(domain):
    domain.add_attribute(Attribute("tanggungan", "numeric"))
    with pytest.raises(ValidationError):
        domain.add_attribute(Attribute("tanggungan", "numeric"))
    with pytest.raises(ValidationError):
        domain.add_attribute(Attribute("kota", "categorical", min=1))
