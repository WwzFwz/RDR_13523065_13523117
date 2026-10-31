"""Mode terminal sistem pakar RDR.

    python cli.py                         # pilih domain dari daftar
    python cli.py --domain keuangan       # langsung ke domain tertentu
    python cli.py --consumer              # mode konsumen (tanpa menambah rule)
    python cli.py --log sesi.txt          # rekam seluruh sesi (prompt + jawaban) ke file
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable, Optional, TextIO

from rdr import (
    Attribute, Condition, Domain, KnowledgeBase, RDRError, ValidationError, create_domain,
    format_value, list_domains, load_domain, load_kb, reset_kb, save_domain, save_kb, separates,
)
from rdr.models import CATEGORICAL_OPS, NUMERIC_OPS

DOMAINS_DIR = Path(__file__).resolve().parent / "domains"


class Console:
    """print/input yang sekaligus menulis ke file log (jika ada)."""

    def __init__(self, log: Optional[TextIO] = None, read: Optional[Callable[[str], str]] = None):
        self.log = log
        self.read = read or (lambda prompt: input(prompt))

    def out(self, text: str = "") -> None:
        print(text)
        if self.log:
            self.log.write(text + "\n")
            self.log.flush()

    def ask(self, prompt: str) -> str:
        answer = self.read(prompt).strip()
        if self.log:
            self.log.write(f"{prompt}{answer}\n")
            self.log.flush()
        return answer

    def yes(self, prompt: str) -> bool:
        while True:
            a = self.ask(f"{prompt} [y/n]: ").lower()
            if a in ("y", "ya", "n", "t", "tidak"):
                return a in ("y", "ya")

    def choose(self, prompt: str, n: int, allow_empty: bool = False) -> Optional[int]:
        """Pilih satu nomor 1..n; None jika kosong dan diizinkan."""
        while True:
            a = self.ask(prompt)
            if not a and allow_empty:
                return None
            if a.isdigit() and 1 <= int(a) <= n:
                return int(a) - 1
            self.out(f"  Masukkan nomor 1-{n}.")

    def table(self, headers: list[str], rows: list[list[str]]) -> None:
        widths = [max(len(str(x)) for x in col) for col in zip(headers, *rows)]
        line = lambda r: "  " + " | ".join(str(x).ljust(w) for x, w in zip(r, widths))  # noqa: E731
        self.out(line(headers))
        self.out("  " + "-+-".join("-" * w for w in widths))
        for r in rows:
            self.out(line(r))


class App:
    def __init__(self, io: Console, domain: Domain, consumer: bool = False):
        self.io = io
        self.consumer = consumer
        self.set_domain(domain)

    def set_domain(self, domain: Domain) -> None:
        self.domain = domain
        self.kb: KnowledgeBase = load_kb(domain)

    # ---------- menu ----------

    def run(self) -> None:
        actions = [
            ("Konsultasi kasus baru", self.consult),
            ("Tampilkan tree", self.show_tree),
            ("Tampilkan daftar rule", self.show_rules),
        ]
        if not self.consumer:
            actions += [
                ("Verifikasi KB (uji ulang semua cornerstone)", self.verify),
                ("Tambah atribut", self.add_attribute),
                ("Ganti / buat domain", self.switch_domain),
                ("Reset KB", self.reset),
            ]
        while True:
            self.io.out()
            self.io.out(f"=== {self.domain.name} | {sum(1 for _ in self.kb.nodes())} rule | "
                        f"mode {'konsumen' if self.consumer else 'pakar'} ===")
            for i, (label, _) in enumerate(actions, 1):
                self.io.out(f"  {i}. {label}")
            self.io.out("  0. Keluar")
            a = self.io.ask("Pilih menu: ")
            if a == "0":
                return
            if a.isdigit() and 1 <= int(a) <= len(actions):
                actions[int(a) - 1][1]()

    # ---------- konsultasi ----------

    def read_value(self, attr: Attribute):
        hint = []
        if attr.is_numeric:
            hint.append("angka")
            if attr.min is not None or attr.max is not None:
                lo = format_value(attr.min) if attr.min is not None else "-inf"
                hi = format_value(attr.max) if attr.max is not None else "inf"
                hint.append(f"{lo}..{hi}")
            if attr.unit:
                hint.append(attr.unit)
        elif attr.values:
            hint.append("/".join(attr.values))
        else:
            hint.append("teks")
        while True:
            try:
                return attr.parse(self.io.ask(f"  {attr.name} ({', '.join(hint)}): "))
            except ValueError as e:
                self.io.out(f"  ! {e}")

    def consult(self) -> None:
        self.io.out("\nData konsumen:")
        case = {attr.name: self.read_value(attr) for attr in self.domain.attributes}
        res = self.kb.infer(case)
        self.io.out("\nJalur penelusuran:")
        for s in res.path:
            self.io.out(f"  {s.node.id}: {s.node.rule_text():<50} -> "
                        f"{'TRUE (ke anak kanan)' if s.result else 'FALSE (ke anak kiri)'}")
        self.io.out(f"\nREKOMENDASI: {res.conclusion}   (dari {res.last_true.id})")
        if self.consumer or self.io.yes("Pakar setuju?"):
            self.io.out(f"Rekomendasi '{res.conclusion}' diberikan ke konsumen.")
            return
        self.correct(case)

    def ask_conclusion(self, current: str) -> Optional[str]:
        options = [c for c in self.kb.conclusions() if c.lower() != current.lower()]
        self.io.out("Kesimpulan yang benar (ketik nomor atau teks baru, kosong = batal):")
        for i, c in enumerate(options, 1):
            self.io.out(f"  {i}. {c}")
        a = self.io.ask("> ")
        if not a:
            return None
        if a.isdigit() and 1 <= int(a) <= len(options):
            return options[int(a) - 1]
        return self.kb.canonical_conclusion(a)

    def correct(self, case: dict) -> None:
        res = self.kb.infer(case)
        conclusion = self.ask_conclusion(res.conclusion)
        if conclusion is None:
            self.io.out("Koreksi dibatalkan.")
            return
        if conclusion.lower() == res.conclusion.lower():
            self.io.out("Kesimpulan sama dengan sistem, dianggap setuju.")
            return

        while True:
            res = self.kb.infer(case)
            corner, cid = res.cornerstone, res.last_true.id
            self.io.out(f"\nKesimpulan '{res.conclusion}' ({cid}) akan dianulir.")
            if corner is None:
                self.io.out(f"{cid} tidak punya cornerstone: semua kondisi kasus baru boleh dipilih.")
            self.io.table(["Atribut", "Kasus baru", f"Cornerstone {cid}"], [
                [a.name, format_value(case[a.name]) if a.name in case else "-",
                 format_value(corner[a.name]) if corner and a.name in corner else "-"]
                for a in self.domain.attributes
            ])
            diff = self.kb.difference_list(case, self.domain)
            if diff:
                break
            self.io.out(f"\nCONFLICT: tidak ada kondisi yang membedakan kasus ini dari cornerstone {cid}.")
            if not self.io.yes("Tambah atribut baru untuk membedakannya?"):
                self.io.out("Koreksi dibatalkan, rule lama tidak diubah.")
                return
            attr = self.add_attribute()
            if attr is None:
                return
            self.io.out(f"Nilai '{attr.name}' untuk kasus ini:")
            case[attr.name] = self.read_value(attr)

        chosen = self.pick_conditions(diff, case, corner)
        if not chosen:
            self.io.out("Koreksi dibatalkan.")
            return
        try:
            node = self.kb.add_rule(case, conclusion, chosen)
        except RDRError as e:
            self.io.out(f"! {e}")
            return
        save_kb(self.kb, self.domain)
        side = "trueChild" if node.branch else "falseChild"
        self.io.out(f"\nRule {node.id} ditambahkan: {node.rule_text()}")
        self.io.out(f"Ditempel di {node.parent_id}.{side}, pengecualian dari {node.exception_of}.")
        self.io.out(f"Rekomendasi untuk konsumen: {node.conclusion}")

    def pick_conditions(self, diff: list[Condition], case: dict, corner) -> list[Condition]:
        self.io.out("\nDifference list:")
        for i, c in enumerate(diff, 1):
            self.io.out(f"  {i}. {c}")
        self.io.out("Pilih nomor (pisahkan koma, digabung AND), 'k' = kondisi kustom, kosong = batal.")
        chosen: list[Condition] = []
        while True:
            a = self.io.ask("> ").lower()
            if not a:
                return chosen
            if a == "k":
                cond = self.custom_condition(case, corner)
                if cond and cond not in chosen:
                    chosen.append(cond)
            else:
                nums = [x.strip() for x in a.split(",") if x.strip()]
                if not all(x.isdigit() and 1 <= int(x) <= len(diff) for x in nums):
                    self.io.out(f"  ! Masukkan nomor 1-{len(diff)}.")
                    continue
                chosen += [c for c in (diff[int(x) - 1] for x in nums) if c not in chosen]
            self.io.out("  Kondisi: " + " AND ".join(str(c) for c in chosen))
            if self.io.yes("  Sudah cukup?"):
                return chosen

    def custom_condition(self, case: dict, corner) -> Optional[Condition]:
        names = [a.name for a in self.domain.attributes]
        for i, n in enumerate(names, 1):
            self.io.out(f"  {i}. {n}")
        attr = self.domain.attributes[self.io.choose("  Atribut: ", len(names))]
        ops = NUMERIC_OPS if attr.is_numeric else CATEGORICAL_OPS
        while (op := self.io.ask(f"  Operator ({' '.join(ops)}): ")) not in ops:
            pass
        cond = Condition(attr.name, op, self.read_value(attr))
        if not separates(cond, case, corner):
            self.io.out(f"  ! '{cond}' harus TRUE untuk kasus baru dan FALSE untuk cornerstone.")
            return None
        return cond

    # ---------- knowledge base ----------

    def show_tree(self) -> None:
        self.io.out("\n(T = anak kanan / true-child, F = anak kiri / false-child)")
        self.io.out(self.kb.ascii_tree())

    def show_rules(self) -> None:
        rows = []
        for n in self.kb.nodes():
            pos = "root" if n.parent_id is None else f"{n.parent_id}.{'T' if n.branch else 'F'}"
            corner = "-" if n.cornerstone is None else ", ".join(
                f"{k}={format_value(v)}" for k, v in n.cornerstone.items())
            rows.append([n.id, n.rule_text(), pos, n.exception_of or "-", corner])
        self.io.table(["ID", "Rule", "Posisi", "Pengecualian dari", "Cornerstone"], rows)

    def verify(self) -> None:
        issues = self.kb.verify()
        if not issues:
            self.io.out("Semua cornerstone tetap mendapat kesimpulan rule-nya sendiri.")
        for i in issues:
            self.io.out(f"! {i.node.id}: cornerstone menghasilkan {i.got}, seharusnya {i.node.conclusion}")

    def reset(self) -> None:
        if self.io.yes("Yakin reset KB ke IF true THEN default? (file lama di-backup)"):
            self.kb = reset_kb(self.domain)
            self.io.out("KB direset.")

    # ---------- domain ----------

    def add_attribute(self) -> Optional[Attribute]:
        attr = read_attribute(self.io)
        if attr is None:
            return None
        try:
            self.domain.add_attribute(attr)
        except ValidationError as e:
            self.io.out("! " + "; ".join(e.errors))
            return None
        save_domain(self.domain)
        self.io.out(f"Atribut '{attr.name}' ditambahkan. Cornerstone lama tidak punya nilai atribut ini.")
        return attr

    def switch_domain(self) -> None:
        folder = pick_domain(self.io, allow_new=True)
        if folder:
            self.set_domain(load_domain(folder))


def read_attribute(io: Console) -> Optional[Attribute]:
    name = io.ask("  Nama atribut (kosong = selesai/batal): ")
    if not name:
        return None
    if io.ask("  Tipe [1=numeric, 2=categorical]: ") != "2":
        return Attribute(name, "numeric", unit=io.ask("  Satuan (opsional): ") or None)
    vals = [v.strip() for v in io.ask("  Daftar nilai, pisahkan koma (kosong = bebas): ").split(",")]
    return Attribute(name, "categorical", values=list(dict.fromkeys(v for v in vals if v)) or None)


def create_domain_wizard(io: Console) -> Optional[Path]:
    name = io.ask("Nama domain: ")
    default = io.ask("Default conclusion: ")
    attrs: dict = {}
    io.out("Atribut (kosongkan nama untuk selesai):")
    while attr := read_attribute(io):
        attrs[attr.name] = attr.to_dict()
    try:
        return create_domain(DOMAINS_DIR, Domain.from_dict(
            {"name": name, "default_conclusion": default, "attributes": attrs}))
    except ValidationError as e:
        io.out("! " + "; ".join(e.errors))
        return None


def pick_domain(io: Console, allow_new: bool = True) -> Optional[Path]:
    folders = list_domains(DOMAINS_DIR)
    io.out("\nDomain tersedia:")
    for i, f in enumerate(folders, 1):
        io.out(f"  {i}. {load_domain(f).name}  ({f.name})")
    if allow_new:
        io.out(f"  {len(folders) + 1}. Buat domain baru")
    idx = io.choose("Pilih domain: ", len(folders) + (1 if allow_new else 0))
    if idx == len(folders):
        return create_domain_wizard(io)
    return folders[idx]


def main(argv: Optional[list[str]] = None) -> None:
    ap = argparse.ArgumentParser(description="Sistem pakar RDR (mode terminal)")
    ap.add_argument("--domain", help="nama folder domain di domains/")
    ap.add_argument("--consumer", action="store_true", help="mode konsumen (tanpa menambah rule)")
    ap.add_argument("--log", help="rekam sesi ke file txt")
    args = ap.parse_args(argv)
    # Console Windows (cp1252) tidak bisa menampilkan karakter garis tree.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    log = open(args.log, "a", encoding="utf-8") if args.log else None
    io = Console(log)
    try:
        folder = DOMAINS_DIR / args.domain if args.domain else pick_domain(io)
        if folder is None:
            return
        app = App(io, load_domain(folder), consumer=args.consumer)
        app.run()
    except (EOFError, KeyboardInterrupt):
        io.out("\nKeluar.")
    finally:
        if log:
            log.close()


if __name__ == "__main__":
    main()
