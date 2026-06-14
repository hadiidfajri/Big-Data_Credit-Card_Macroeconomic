# Panduan Detail Menyusun Dashboard — Power BI & Tableau
### Tugas Besar Big Data · Credit-Card Default (Taiwan 2005)
*Langkah klik-demi-klik untuk membangun setiap zona di kedua tools.*

> Membangun **desain yang sama** di dua tool: **Tableau → warehouse ETL (`bigdata_etl`)**,
> **Power BI → warehouse ELT (`bigdata_elt`)**. Keduanya membaca tabel `kpi_*`. Acuan desain:
> `DASHBOARD_SPEC.md`. Preview hasil akhir: `docs/DASHBOARD_PREVIEW.pdf`.

---

## 0. Sumber data (4 tabel KPI)
| Tabel | Kolom | Dipakai di zona |
|---|---|---|
| `kpi_overall` | `default_rate`, `total_clients` | A (kartu) |
| `kpi_corr_default_macro` | `corr_fx`, `corr_reer`, `corr_reserves` | A (kartu) + D (anotasi) |
| `kpi_default_by_demographic` | `dimension`, `category`, `clients`, `default_rate` | B (bar) |
| `kpi_monthly_default_vs_macro` | `date_key`, `month_name`, `default_rate`, `exchange_rate_twd_usd`, `real_broad_eer`, `total_reserves` | C (tren) + D (scatter) |

---

## 1. Menghubungkan data

### 1A. Tableau (ke ETL `bigdata_etl`)
1. Buka Tableau → **Connect → To a Server → Other Databases (ODBC)** (atau Cloudera Hive bila ada).
2. Pilih **DSN** Hive yang sudah dikonfigurasi (Host `localhost`, Port `10000`, DB `bigdata_etl`,
   HiveServer2, Mechanism **User Name** `hive`, Thrift Transport **Binary**, SSL **off**). Detail:
   `dashboard/HIVE_ODBC_CONNECTION.md`.
3. Di **Data Source**, seret tabel `kpi_overall`, `kpi_default_by_demographic`,
   `kpi_monthly_default_vs_macro`, `kpi_corr_default_macro` (sebagai sumber terpisah / tanpa join).
4. **Tanpa ODBC?** Connect → **Text file** dan pilih `dashboard/exports/bigdata_etl__*.csv`
   (hasil `python dashboard/export_kpis_csv.py`).

### 1B. Power BI (ke ELT `bigdata_elt`)
1. **Get Data → ODBC →** pilih DSN (Database `bigdata_elt`) → **Connect**.
2. Di **Navigator**, centang keempat tabel `kpi_*` → **Load** (bukan Transform, data sudah siap).
3. **Tanpa ODBC?** **Get Data → Text/CSV** dan pilih `dashboard/exports/bigdata_elt__*.csv`.
4. Cek tipe kolom di **Model view**: `default_rate`/macro = **Decimal**, `total_clients`/`clients` =
   **Whole number**, `date_key` = **Whole number**, `month_name`/`dimension`/`category` = **Text**.

> Untuk **mengurutkan bulan** (Apr→Sep), buat kolom urut dari `date_key`:
> Power BI: di tabel `kpi_monthly_default_vs_macro`, *Sort by column* → `month_name` **Sort by**
> `date_key`. Tableau: klik kanan field `month_name` → **Sort** → *by field* `date_key` (Ascending).

---

## 2. ZONA A — Kartu KPI

### 2A. Tableau (4 sheet kartu)
1. **Sheet baru** → namai `KPI Overall`.
2. Seret measure **`default_rate`** ke **Text** (kotak Marks). Klik kanan di Marks → **Format** →
   angka → **Percentage**, 2 desimal → tampil `22,12%`. Perbesar font (Marks → Text → ukuran 28).
3. Sheet baru `KPI Clients`: seret **`total_clients`** ke Text → format **Number (standard)** ribuan.
4. Sheet baru `KPI Corr`: dari `kpi_corr_default_macro` seret **`corr_fx`** (atau ketiga corr) ke
   Text, 2 desimal.
5. (Opsional) beri judul tiap sheet via **Title** (double-click area judul).

### 2B. Power BI (visual **Card**)
1. Panel **Visualizations → Card**. Tarik **`default_rate`** ke *Fields*. Di **Format → Callout
   value → Display units = None, Value decimal places = 2**; ubah jadi persen via *Measure tools →
   Format → Percentage* atau buat measure `Default % = AVERAGE(kpi_overall[default_rate])` lalu
   format Percentage.
2. Card kedua: **`total_clients`** (Format → ribuan).
3. Card ketiga–kelima: **`corr_fx`**, **`corr_reer`**, **`corr_reserves`** (2 desimal).
4. Beri judul Card (Format → General → Title) mis. "Overall Default Rate".

> **Catatan agregasi:** karena tabel KPI sudah ringkas, set agregasi ke **Average/Min** (bukan Sum)
> agar nilai tidak terjumlah. Tableau: klik kanan measure → Measure → Average. Power BI: *Don't
> summarize* atau Average.

---

## 3. ZONA B — Default rate per demografi (bar + garis referensi)

### 3A. Tableau
1. Sheet baru `Default by Demographic`. Seret **`category`** ke **Columns**, **`default_rate`** ke
   **Rows** (set ke **Average**).
2. Seret **`dimension`** ke **Filters** → centang satu nilai (mis. `sex`); atau seret `dimension`
   ke **Pages**/**Filter** + tampilkan kontrol filter (klik kanan → **Show Filter**).
3. **Garis referensi**: klik kanan sumbu `default_rate` → **Add Reference Line** → Value =
   *Average of default_rate* atau konstanta `0.2212` → label "overall".
4. Urutkan bar **descending** (toolbar Sort). Beri label nilai (Marks → Label → aktifkan).

### 3B. Power BI
1. Visual **Clustered bar chart**. **Y-axis = `category`**, **X-axis = `default_rate`**
   (agregasi **Average**).
2. Tambah **Slicer** terpisah: field **`dimension`** → atur **Single select**. Slicer ini memfilter
   bar saat dipilih (sex/education/marriage/age_band).
3. **Garis referensi**: **Analytics pane → Constant line / Average line** = 0,2212, beri label.
4. **Data labels** ON (Format → Data labels). Urutkan: "…" → **Sort axis → default_rate → Desc**.

---

## 4. ZONA C — Tren bulanan Apr–Sep 2005 (dual-axis)

### 4A. Tableau
1. Sheet baru `Monthly Trend`. Seret **`month_name`** ke **Columns** (pastikan sort by `date_key`).
2. Seret **`default_rate`** ke **Rows** (Average) → muncul garis pertama.
3. Seret indikator makro mis. **`exchange_rate_twd_usd`** ke **Rows** lagi (di sebelahnya) →
   dua sumbu.
4. Klik kanan sumbu makro (kedua) → **Dual Axis**. Karena skala beda, **jangan** Synchronize Axis.
5. Marks: set tipe **Line** untuk keduanya, warna berbeda; aktifkan **Tooltip**.
6. (Filter makro) buat **parameter** "Pilih Makro" (FX/REER/Reserves) + *calculated field* `CASE
   [Pilih Makro] WHEN 'FX' THEN [exchange_rate_twd_usd] …` lalu pakai field itu di Rows agar bisa
   diganti interaktif.

### 4B. Power BI
1. Visual **Line chart** (atau **Line and clustered column**). **X-axis = `month_name`**
   (urut by `date_key`).
2. **Y-axis = `default_rate`** (Average). **Secondary values / secondary y-axis =
   `exchange_rate_twd_usd`** (Average).
3. Aktifkan sumbu sekunder (Format → Y-Axis → **Secondary**). Beri warna garis berbeda.
4. (Filter makro) cara mudah: sediakan **3 line** opsional via *field parameter* (Modeling → New
   parameter → Fields) berisi FX/REER/Reserves, lalu jadikan slicer pemilih indikator.

---

## 5. ZONA D — Default vs makro (scatter, korelasi ≈ 0)

### 5A. Tableau
1. Sheet baru `Default vs Macro`. Seret **`exchange_rate_twd_usd`** ke **Columns** (Average),
   **`default_rate`** ke **Rows** (Average).
2. Seret **`month_name`** (atau `date_key`) ke **Detail** (Marks) → 1 titik per bulan.
3. Marks type = **Circle**. **Analytics → Trend Line** → Linear.
4. Tambah anotasi nilai korelasi (dari `kpi_corr_default_macro`) via **Annotate → Area** atau caption.

### 5B. Power BI
1. Visual **Scatter chart**. **X Axis = `exchange_rate_twd_usd`** (Average), **Y Axis =
   `default_rate`** (Average), **Values/Details = `month_name`** (agar 1 titik/bulan, bukan 1 titik
   tergabung).
2. **Analytics pane → Trend line** ON.
3. Tambah **Card** kecil `corr_fx` di dekatnya sebagai anotasi korelasi.

> **Insight zona D:** titik akan **mendatar** (default rate konstan 0,2212) → korelasi ≈ 0. Ini
> temuan jujur (keterbatasan grain label per-klien, report §10) — tetap ditampilkan sebagai bukti.

---

## 6. Filter interaktif (wajib §8)
| Filter | Tableau | Power BI |
|---|---|---|
| Dimensi demografi | `dimension` → **Show Filter** (single value) | **Slicer** `dimension` (single select) |
| Indikator makro | **Parameter** + calculated field | **Field parameter** / slicer |
| Rentang bulan | filter `date_key`/`month_name` (range) | **Slicer** `month_name` (atau date range) |

Pasang filter sebagai **floating** di dashboard agar memengaruhi beberapa zona sekaligus (di Power BI
slicer otomatis memfilter semua visual di halaman).

---

## 7. Menyusun jadi SATU dashboard

### 7A. Tableau
1. Tab bawah → **New Dashboard**. Set ukuran (mis. 1366×768 atau Automatic).
2. Seret tiap **sheet** (KPI Overall/Clients/Corr di atas; Demographic, Trend, Scatter di bawah)
   ke kanvas, atur tata letak (gunakan **Horizontal/Vertical** containers).
3. Seret kontrol **filter**/**parameter** ke kanvas. Atur **Use as Filter** agar klik bar memfilter
   zona lain (ikon corong di pojok sheet).
4. Beri **judul** dashboard.

### 7B. Power BI
1. Di satu **Page (Report view)**, susun semua visual (4 card di atas, bar & line di tengah,
   scatter di bawah) dengan drag & resize.
2. Tambahkan **Slicer** (`dimension`, `month_name`, indikator makro). Slicer memfilter semua visual
   se-halaman secara default.
3. **Format → Edit interactions** bila ingin mengatur visual mana yang terpengaruh slicer/klik.
4. Tambah **Text box** judul.

---

## 8. Ekspor screenshot & file (untuk report §8–§9)
Simpan ke `dashboard/screenshots/` dengan nama yang dipakai laporan:
- `tableau_etl_dashboard.png` — **Tableau → Worksheet/Dashboard → Export → Image**.
- `powerbi_elt_dashboard.png` — **Power BI → File → Export → PDF**, atau **Win+Shift+S** untuk PNG.
- Simpan file sumber: `dashboard/tableau_etl_dashboard.twbx`, `dashboard/powerbi_elt_dashboard.pbix`.

**Verifikasi:** angka KPI Tableau (ETL) **harus sama** dengan Power BI (ELT) — overall ≈ 0,2212,
total clients 150.000. Kecocokan ini = bukti konsistensi ETL vs ELT (report §9).

---

## 9. Tips & jebakan umum
- **Nilai terjumlah salah** → set agregasi **Average** (bukan Sum) untuk `default_rate`/corr/macro.
- **Bulan tidak urut** → atur *Sort by* `date_key` (lihat §1).
- **Dual-axis skala campur** → jangan Synchronize (skala default vs kurs berbeda jauh).
- **Scatter cuma 1 titik** → tambahkan `month_name`/`date_key` ke Detail (Tableau) / Details (Power BI).
- **ODBC error "Unexpected response"** → Thrift Transport **Binary** + SSL **off** (lihat
  `HIVE_ODBC_CONNECTION.md`); atau pakai fallback CSV.
