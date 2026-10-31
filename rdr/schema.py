"""Schema domain: default conclusion dan daftar atribut (numerik / kategorikal).

Format domain.json (bentuk singkat dan bentuk lengkap boleh dicampur):

    {
      "name": "Rekomendasi Produk Keuangan",
      "default_conclusion": "Tabungan Reguler",
      "attributes": {
        "umur":   "numeric",
        "gaji":   {"type": "numeric", "min": 0, "unit": "juta/bulan"},
        "risiko": {"type": "categorical", "values": ["rendah", "sedang", "tinggi"]},
        "status": "categorical"
      }
    }
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .models import Case

NUMERIC = "numeric"
CATEGORICAL = "categorical"
TYPES = (NUMERIC, CATEGORICAL)
DOMAIN_FILE = "domain.json"


class ValidationError(ValueError):
    """Input kasus atau schema tidak valid. `errors` berisi semua pesan."""

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


@dataclass
class Attribute:
    name: str
    type: str
    values: Optional[list[str]] = None  # hanya kategorikal; None = bebas
    min: Optional[float] = None  # hanya numerik
    max: Optional[float] = None
    unit: Optional[str] = None

    @property
    def is_numeric(self) -> bool:
        return self.type == NUMERIC

    def to_dict(self) -> dict | str:
        d: dict[str, Any] = {"type": self.type}
        for key in ("values", "min", "max", "unit"):
            if getattr(self, key) not in (None, []):
                d[key] = getattr(self, key)
        return d if len(d) > 1 else self.type

    @classmethod
    def from_config(cls, name: str, cfg: dict | str) -> "Attribute":
        if isinstance(cfg, str):
            cfg = {"type": cfg}
        attr = cls(
            name=name,
            type=cfg.get("type", ""),
            values=list(cfg["values"]) if cfg.get("values") else None,
            min=cfg.get("min"),
            max=cfg.get("max"),
            unit=cfg.get("unit"),
        )
        attr.check()
        return attr

    def check(self) -> None:
        errors = []
        if not self.name or not self.name.strip():
            errors.append("Nama atribut tidak boleh kosong")
        if self.type not in TYPES:
            errors.append(f"Tipe atribut '{self.name}' harus numeric atau categorical")
        if self.type == NUMERIC and self.values:
            errors.append(f"Atribut numerik '{self.name}' tidak boleh punya daftar values")
        if self.type == CATEGORICAL and (self.min is not None or self.max is not None):
            errors.append(f"Atribut kategorikal '{self.name}' tidak boleh punya min/max")
        if self.min is not None and self.max is not None and self.min > self.max:
            errors.append(f"min > max pada atribut '{self.name}'")
        if errors:
            raise ValidationError(errors)

    def parse(self, raw: Any) -> Any:
        """Ubah input mentah (str/angka) jadi nilai bertipe; ValueError jika gagal."""
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            raise ValueError(f"'{self.name}' wajib diisi")
        if self.is_numeric:
            try:
                v = float(str(raw).replace(",", ".")) if isinstance(raw, str) else float(raw)
            except ValueError:
                raise ValueError(f"'{self.name}' harus berupa angka (diterima: {raw!r})")
            if self.min is not None and v < self.min:
                raise ValueError(f"'{self.name}' minimal {self.min}")
            if self.max is not None and v > self.max:
                raise ValueError(f"'{self.name}' maksimal {self.max}")
            return v
        v = str(raw).strip()
        if self.values is not None:
            match = next((x for x in self.values if x.lower() == v.lower()), None)
            if match is None:
                raise ValueError(f"'{self.name}' harus salah satu dari {self.values}")
            return match
        return v


@dataclass
class Domain:
    name: str
    default_conclusion: str
    attributes: list[Attribute] = field(default_factory=list)
    folder: Optional[Path] = None

    def attribute(self, name: str) -> Attribute:
        for a in self.attributes:
            if a.name == name:
                return a
        raise KeyError(name)

    def has_attribute(self, name: str) -> bool:
        return any(a.name == name for a in self.attributes)

    def add_attribute(self, attr: Attribute) -> None:
        attr.check()
        if self.has_attribute(attr.name):
            raise ValidationError([f"Atribut '{attr.name}' sudah ada"])
        self.attributes.append(attr)

    def validate_case(self, raw: dict[str, Any]) -> Case:
        """Semua atribut wajib diisi. Mengembalikan Case dengan nilai bertipe."""
        case: Case = {}
        errors = []
        for attr in self.attributes:
            try:
                case[attr.name] = attr.parse(raw.get(attr.name))
            except ValueError as e:
                errors.append(str(e))
        if errors:
            raise ValidationError(errors)
        return case

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "default_conclusion": self.default_conclusion,
            "attributes": {a.name: a.to_dict() for a in self.attributes},
        }

    @classmethod
    def from_dict(cls, d: dict, folder: Optional[Path] = None) -> "Domain":
        errors = []
        if not str(d.get("name", "")).strip():
            errors.append("Nama domain tidak boleh kosong")
        if not str(d.get("default_conclusion", "")).strip():
            errors.append("default_conclusion tidak boleh kosong")
        if not d.get("attributes"):
            errors.append("Domain harus punya minimal satu atribut")
        if errors:
            raise ValidationError(errors)
        attrs = [Attribute.from_config(n, c) for n, c in d["attributes"].items()]
        return cls(d["name"].strip(), d["default_conclusion"].strip(), attrs, folder)


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug or "domain"


def load_domain(folder: str | os.PathLike) -> Domain:
    folder = Path(folder)
    with open(folder / DOMAIN_FILE, encoding="utf-8") as f:
        return Domain.from_dict(json.load(f), folder)


def save_domain(domain: Domain, folder: Optional[str | os.PathLike] = None) -> Path:
    folder = Path(folder or domain.folder)
    folder.mkdir(parents=True, exist_ok=True)
    tmp = folder / (DOMAIN_FILE + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(domain.to_dict(), f, indent=2, ensure_ascii=False)
    os.replace(tmp, folder / DOMAIN_FILE)
    domain.folder = folder
    return folder


def list_domains(base_dir: str | os.PathLike) -> list[Path]:
    base = Path(base_dir)
    if not base.exists():
        return []
    return sorted(p for p in base.iterdir() if (p / DOMAIN_FILE).is_file())


def create_domain(base_dir: str | os.PathLike, domain: Domain) -> Path:
    """Simpan domain baru di base_dir/<slug>; gagal jika folder sudah dipakai."""
    folder = Path(base_dir) / slugify(domain.name)
    if (folder / DOMAIN_FILE).exists():
        raise ValidationError([f"Domain dengan folder '{folder.name}' sudah ada"])
    return save_domain(domain, folder)
