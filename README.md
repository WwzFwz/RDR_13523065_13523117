# Sistem Pakar Rekomendasi Berbasis Ripple Down Rules (RDR)

Implementasi *Single Classification Ripple Down Rules* (SCRDR) untuk membantu pakar memberi
rekomendasi kepada konsumen. Knowledge base dimulai dari satu rule `IF true THEN <default>`,
lalu bertambah setiap kali pakar tidak setuju dengan kesimpulan sistem.

- Engine generik: domain, default, dan atribut (numerik/kategorikal) dibaca dari file config.
- Binary tree: anak kanan = *true-child* (pengecualian), anak kiri = *false-child*.
- Kondisi rule baru dipilih pakar dari *difference list* (dipenuhi kasus baru, tidak dipenuhi
  cornerstone rule yang dianulir).
- Antarmuka web lokal (Streamlit): konsultasi, justifikasi, visualisasi tree, uji batch CSV,
  pembuatan domain baru.
- Mode terminal (CLI) dengan opsi merekam sesi ke file txt.

## Instalasi

Butuh Python 3.10 atau lebih baru.

```bash
pip install -r requirements.txt
```

## Menjalankan aplikasi

```bash
streamlit run app.py
```

Browser akan terbuka di `http://localhost:8501`.

| Tab | Fungsi |
|---|---|
| Konsultasi | Input data konsumen, lihat rekomendasi dan jalur penelusuran. Dalam mode pakar: setuju/tidak setuju, beri kesimpulan yang benar, pilih kondisi, tambah rule. |
| Tree & Rule | Visualisasi binary tree, daftar rule beserta cornerstone, verifikasi KB, unduh `kb.json`, reset KB. |
| Uji Batch (CSV) | Jalankan inferensi untuk banyak kasus sekaligus (tanpa menambah rule). |
| Domain & Atribut | Lihat schema, ubah default, tambah atribut. |

Toggle **Mode pakar** di sidebar: aktif berarti pakar dapat mengoreksi dan menambah rule;
nonaktif berarti mode konsumen yang hanya menampilkan rekomendasi.

## Mode terminal (CLI)

Alternatif tanpa browser, dengan alur yang sama (konsultasi, koreksi pakar, difference list,
conflict, tree ASCII, daftar rule, verifikasi, tambah atribut, buat domain):

```bash
python cli.py --domain keuangan
```

```bash
python cli.py --domain keuangan --consumer
```

```bash
python cli.py --domain keuangan --log docs/sesi.txt
```

Perintah pertama menjalankan mode pakar. Perintah kedua menjalankan mode konsumen (hanya
rekomendasi). Perintah ketiga juga merekam seluruh sesi (prompt dan jawaban) ke file txt.
Contoh rekaman: [docs/contoh_sesi_cli.txt](docs/contoh_sesi_cli.txt). Tanpa `--domain`,
CLI menampilkan daftar domain dan opsi membuat domain baru.

## Domain

Setiap domain adalah satu folder di `domains/`:

```text
domains/
├── keuangan/
│   ├── domain.json   # ditulis manusia: default + atribut
│   └── kb.json       # ditulis sistem: tree rule + cornerstone
└── laptop/
    └── domain.json   # belum ada kb.json -> mulai dari IF true THEN default
```

Format `domain.json` (atribut boleh ditulis singkat `"nama": "numeric"`):

```json
{
  "name": "Rekomendasi Produk Keuangan",
  "default_conclusion": "Tabungan Reguler",
  "attributes": {
    "umur":   {"type": "numeric", "min": 17, "max": 100, "unit": "tahun"},
    "gaji":   {"type": "numeric", "min": 0, "unit": "juta/bulan"},
    "risiko": {"type": "categorical", "values": ["rendah", "sedang", "tinggi"]},
    "status": "categorical"
  }
}
```

- `values` pada atribut kategorikal bersifat opsional; tanpa `values`, nilainya bebas diketik.
- `min`, `max`, `unit` pada atribut numerik bersifat opsional.

**Membuat domain baru:** lewat tombol *➕ Buat domain baru* di sidebar (membuka halaman tersendiri: isi form, atau impor
`domain.json` + `kb.json` opsional hasil unduhan; file divalidasi dan `verify()` harus lolos), atau
buat folder baru di `domains/` berisi `domain.json`.

**Menambah atribut:** lewat tab *Domain & Atribut*, atau saat terjadi conflict (difference
list kosong) di halaman konsultasi. Cornerstone lama tidak memiliki nilai atribut baru, sehingga
kondisi pada atribut tersebut dianggap FALSE untuk cornerstone lama.

**Reset KB:** tombol *Reset KB* di tab *Tree & Rule* (file lama di-backup sebagai
`kb.<waktu>.bak.json`), atau hapus `kb.json`.

## Skenario demo

`scripts/demo_scenario.py` berisi 9 kasus (C1–C9) yang membangun tree contoh pada domain
keuangan, termasuk satu kasus conflict.

```bash
python -m scripts.demo_scenario
```

```bash
python -m scripts.demo_scenario --save
```

Perintah kedua menyimpan hasilnya ke `domains/keuangan/kb.json` (menimpa KB yang ada).

## Pengujian

```bash
python -m pytest
```

Test mencakup evaluasi kondisi, difference list, inferensi, penempatan node, validasi, simpan/muat
KB, skenario C1–C9 beserta cek regresi cornerstone, dan smoke test UI Streamlit.

## Struktur kode

```text
app.py               entry point Streamlit
cli.py               mode terminal
rdr/                 engine (tidak bergantung pada UI)
  models.py          Condition, Node
  engine.py          KnowledgeBase: infer(), add_rule(), verify()
  difference.py      kandidat kondisi dan difference list
  schema.py          Domain, Attribute, validasi kasus, load/save domain.json
  storage.py         load/save/reset kb.json
ui/                  halaman Streamlit
scripts/             skenario demo
tests/               pytest
docs/laporan/        laporan (LaTeX)
```

## Asumsi terhadap spesifikasi

1. Satu rule boleh berisi beberapa kondisi yang digabung dengan AND; semua kondisi wajib berasal
   dari difference list (dipenuhi kasus baru, tidak dipenuhi cornerstone).
2. Operator numerik: `>`, `>=`, `<`, `<=`. Operator kategorikal: `==`, `!=`.
3. Kandidat numerik relatif terhadap cornerstone: jika nilai kasus baru `v` > nilai cornerstone
   `c`, kandidatnya `attr > c` (paling umum) dan `attr >= v` (paling spesifik); berlaku
   sebaliknya untuk `v < c`. Pakar boleh memasukkan threshold sendiri selama tetap memisahkan
   kasus baru dari cornerstone.
4. Root tidak memiliki cornerstone, sehingga rule yang menganulir default boleh memakai kondisi
   apa pun dari kasus baru.
5. Node baru ditempel pada node terakhir yang dievaluasi (sebagai true-child jika kondisinya
   TRUE, false-child jika FALSE). Difference list dihitung terhadap cornerstone node terakhir
   yang bernilai TRUE (pemberi kesimpulan).
6. Jika difference list kosong, rule lama tidak diubah. Pakar dapat membatalkan koreksi atau
   menambah atribut baru.
7. Semua atribut wajib diisi saat konsultasi.
8. Jika pakar memberi kesimpulan yang sama dengan sistem, dianggap setuju.
