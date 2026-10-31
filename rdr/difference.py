"""Pembangkitan kandidat kondisi dan difference list.

Difference list = kondisi yang TRUE untuk kasus baru dan FALSE untuk
cornerstone dari node yang kesimpulannya akan dianulir.
"""

from __future__ import annotations

from typing import Optional

from .models import Case, Condition
from .schema import Domain


def generate_candidates(case: Case, cornerstone: Optional[Case], domain: Domain) -> list[Condition]:
    """Kandidat kondisi dari nilai-nilai kasus baru.

    Numerik, kasus baru v vs cornerstone c:
      - tanpa pembanding (root / atribut tidak ada di cornerstone): `attr >= v` dan `attr <= v`
      - v > c: `attr > c` (paling umum) dan `attr >= v` (paling spesifik)
      - v < c: `attr < c` (paling umum) dan `attr <= v` (paling spesifik)
      - v == c: tidak ada kandidat
    Kategorikal: `attr == v`, ditambah `attr != c` jika c ada dan berbeda.
    """
    candidates: list[Condition] = []
    for attr in domain.attributes:
        v = case.get(attr.name)
        if v is None:
            continue
        c = cornerstone.get(attr.name) if cornerstone else None
        if attr.is_numeric:
            if c is None:
                candidates += [Condition(attr.name, ">=", v), Condition(attr.name, "<=", v)]
            elif v > c:
                candidates += [Condition(attr.name, ">", c), Condition(attr.name, ">=", v)]
            elif v < c:
                candidates += [Condition(attr.name, "<", c), Condition(attr.name, "<=", v)]
        else:
            candidates.append(Condition(attr.name, "==", v))
            if c is not None and c != v:
                candidates.append(Condition(attr.name, "!=", c))
    return candidates


def separates(cond: Condition, case: Case, cornerstone: Optional[Case]) -> bool:
    """True jika kondisi dipenuhi kasus baru dan tidak dipenuhi cornerstone."""
    return cond.evaluate(case) and not cond.evaluate(cornerstone)


def difference_list(case: Case, cornerstone: Optional[Case], domain: Domain) -> list[Condition]:
    seen: set[Condition] = set()
    result = []
    for cond in generate_candidates(case, cornerstone, domain):
        if cond not in seen and separates(cond, case, cornerstone):
            seen.add(cond)
            result.append(cond)
    return result
