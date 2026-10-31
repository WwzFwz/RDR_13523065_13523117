"""Session state bersama: domain aktif, knowledge base, dan sesi konsultasi."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import streamlit as st

from rdr import Domain, KnowledgeBase, load_domain, load_kb, save_kb


def domains_dir() -> Path:
    """Folder domain; RDR_DOMAINS_DIR memungkinkan test UI memakai folder sementara."""
    return Path(os.environ.get("RDR_DOMAINS_DIR")
                or Path(__file__).resolve().parent.parent / "domains")


def use_domain(folder: Path) -> None:
    """Muat domain + KB ke session state (sekali per pergantian domain)."""
    if st.session_state.get("domain_folder") == str(folder):
        return
    domain = load_domain(folder)
    st.session_state.domain_folder = str(folder)
    st.session_state.domain = domain
    st.session_state.kb = load_kb(domain)
    reset_consult()


def domain() -> Domain:
    return st.session_state.domain


def kb() -> KnowledgeBase:
    return st.session_state.kb


def set_kb(new_kb: KnowledgeBase) -> None:
    st.session_state.kb = new_kb


def persist() -> None:
    save_kb(kb(), domain())


# ---------- sesi konsultasi ----------
# consult = {"case": Case, "stage": "result" | "disagree" | "done", "message": str}

def consult() -> Optional[dict]:
    return st.session_state.get("consult")


def start_consult(case: dict) -> None:
    st.session_state.consult = {"case": case, "stage": "result", "message": None}
    st.session_state.custom_conds = []


def set_stage(stage: str, message: Optional[str] = None) -> None:
    st.session_state.consult["stage"] = stage
    st.session_state.consult["message"] = message


def reset_consult() -> None:
    st.session_state.consult = None
    st.session_state.custom_conds = []


def custom_conds() -> list:
    return st.session_state.setdefault("custom_conds", [])
