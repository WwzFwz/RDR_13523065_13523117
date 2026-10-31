"""Simpan / muat knowledge base (kb.json) per folder domain."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from .engine import KnowledgeBase
from .schema import Domain

KB_FILE = "kb.json"


def kb_path(domain: Domain) -> Path:
    return Path(domain.folder) / KB_FILE


def load_kb(domain: Domain) -> KnowledgeBase:
    """Muat kb.json; jika belum ada, mulai dari satu rule: t -> default."""
    path = kb_path(domain)
    if not path.exists():
        return KnowledgeBase(domain.default_conclusion)
    with open(path, encoding="utf-8") as f:
        kb = KnowledgeBase.from_dict(json.load(f))
    # Root tidak punya cornerstone, jadi default boleh mengikuti domain.json.
    kb.root.conclusion = domain.default_conclusion
    return kb


def save_kb(kb: KnowledgeBase, domain: Domain) -> Path:
    path = kb_path(domain)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"domain": domain.name, **kb.to_dict()}
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)
    return path


def reset_kb(domain: Domain) -> KnowledgeBase:
    """Backup kb.json lama (kb.<timestamp>.bak.json) lalu mulai dari t -> default."""
    path = kb_path(domain)
    if path.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.move(path, path.with_name(f"kb.{stamp}.bak.json"))
    return KnowledgeBase(domain.default_conclusion)
