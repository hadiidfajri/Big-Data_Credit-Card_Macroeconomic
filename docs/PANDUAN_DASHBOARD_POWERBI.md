# Panduan Dashboard — POWER BI (Detail, klik-demi-klik)
### Tugas Besar Big Data · Credit-Card Default (Taiwan 2005) · jalur **ELT** (`bigdata_elt`)

> Power BI membaca warehouse **ELT** (`bigdata_elt`) via Hive ODBC. Dashboard memakai 4 tabel
> `kpi_*`. Acuan desain: `DASHBOARD_SPEC.md`. Preview hasil: `docs/DASHBOARD_PREVIEW.pdf`.
> (Versi Tableau ada di `docs/PANDUAN_DASHBOARD_DETAIL.pdf`.)

---

## 1. Prasyarat — siapkan server dulu
1. Stack Hive hidup, dan **matikan layanan yang tidak perlu** agar HiveServer2 lega (kunci kestabilan):
   ```powershell
   docker compose stop spark-master spark-worker kafka kafka-ui
   docker compose up -d --force-recreate hiveserver2   # sesi bersih
   docker compose ps   # cukup: postgres + hive-metastore + hiveserver2
   ```
2. **Hive ODBC driver 64-bit** (Cloudera/Microsoft) terpasang.
3. DSN ODBC sudah dikonfigurasi: Host `localhost`, Port `10000`, Database **`bigdata_elt`**,
   Hive Server Type **HiveServer2**, Mechanism **User Name** user `hive`, **Thrift Transport =
   Binary**, **SSL = OFF** → **Test → SUCCESS**. (Detail: `dashboard/HIVE_ODBC_CONNECTION.md`.)

## 2. Tabel sumber (4 KPI)
| Tabel | Kolom |
|---|---|
| `kpi_overall` | `default_rate`, `total_clients` |
| `kpi_default_by_demographic` | `dimension`, `category`, `clients`, `default_rate` |
| `kpi_monthly_default_vs_macro` | `date_key`, `month_name`, `default_rate`, `exchange_rate_twd_usd`, `real_broad_eer`, `total_reserves` |
| `kpi_corr_default_macro` | `corr_fx`, `corr_reer`, `corr_reserves` |

---

## 3. Menghubungkan data — pilih SATU cara

### Cara A — ODBC **Import** (paling stabil, disarankan)
1. **Home → Get Data → More… → ODBC → Connect**.
2. Pilih **DSN** Anda → **OK**.
3. Saat ditanya **Import / DirectQuery → pilih `Import`**.
4. Di **Navigator**, buka database `bigdata_elt`, **centang hanya 4 tabel `kpi_*`** → **Load**.
   *(Jangan tarik `elt_fact_monthly`/`elt_client_trends` 900k baris.)*

### Cara B — ODBC **DirectQuery** (jika diminta query live)
1. Get Data → ODBC → DSN → **DirectQuery** → centang **hanya `kpi_*`** → Load.
2. **WAJIB setel agar handle tidak gugur** (`Invalid OperationHandle`):
   - **File → Options and settings → Options → DirectQuery →**
     **"Maximum connections per data source" = 1** (query berurutan, tidak berebut).
   - **Options → Data Load →** hilangkan centang **"Allow data previews to download in the
     background"**.
   - DSN → Configure → Advanced: **Rows Fetched Per Block = 10000**, **Use Native Query** ON.
3. Jangan jalankan Spark/Kafka selama dashboard aktif (lihat §1).

### Cara C — CSV (fallback tanpa ODBC, sudah disiapkan)
File ada di `dashboard/exports/`:
1. **Get Data → Text/CSV** → pilih `bigdata_elt__kpi_overall.csv`,
   `bigdata_elt__kpi_default_by_demographic.csv`, `bigdata_elt__kpi_monthly_default_vs_macro.csv`,
   `bigdata_elt__kpi_corr_default_macro.csv` → **Load** (ulangi per file).
> Regenerasi CSV: `python dashboard/export_kpis_csv.py` (atau lihat perintah beeline di guide).

---

## 4. Siapkan model & tipe data
1. **Model view** (ikon kiri) → cek tipe tiap kolom:
   `default_rate` / `corr_*` / kolom makro = **Decimal number**; `total_clients`/`clients`/`date_key`
   = **Whole number**; `dimension`/`category`/`month_name` = **Text**.
2. **Urutkan bulan Apr→Sep:** klik tabel `kpi_monthly_default_vs_macro` → pilih kolom `month_name` →
   **Column tools → Sort by column → `date_key`**.
3. **Hindari penjumlahan salah:** untuk `default_rate`/`corr_*`, di pane **Data** klik kolomnya →
   **Column tools → Summarization = Average** (atau **Don't summarize**), bukan Sum.

---

## 5. Membangun 4 zona (visual per zona)

### Zona A — Kartu KPI (visual **Card**)
1. Pane **Visualizations → Card**. Tarik **`kpi_overall[default_rate]`** ke **Fields**.
2. **Format (ikon kuas) → Callout value → Value decimal places = 2**. Agar tampil persen: di pane
   Data pilih `default_rate` → **Column tools → Format = Percentage, 2 desimal** (hasil **22,12%**).
3. Card kedua: **`kpi_overall[total_clients]`** → Format ribuan → **150.000**.
4. Card ketiga–kelima: **`corr_fx`**, **`corr_reer`**, **`corr_reserves`** (2 desimal → **0,00**).
5. Tiap Card: **Format → General → Title** beri judul ("Overall Default Rate", dst).

### Zona B — Default rate per demografi (**Clustered bar chart** + slicer)
1. Visual **Clustered bar chart**. **Y-axis = `kpi_default_by_demographic[category]`**,
   **X-axis = `default_rate`** (set **Average**).
2. Tambah **Slicer** terpisah: field **`dimension`** → Format slicer → **Single select** ON.
   Memilih `sex`/`education`/`marriage`/`age_band` akan memfilter bar.
3. **Garis referensi overall:** pilih bar chart → **Analytics pane → Average line / Constant line**
   = `0.2212` → beri label "overall".
4. **Data labels** ON. Urut: "…" (More options) → **Sort axis → default_rate → Descending**.

### Zona C — Tren bulanan Apr–Sep 2005 (**Line chart**, sumbu ganda)
1. Visual **Line chart**. **X-axis = `kpi_monthly_default_vs_macro[month_name]`** (sudah sort by
   `date_key`).
2. **Y-axis = `default_rate`** (Average).
3. **Secondary y-axis:** tarik **`exchange_rate_twd_usd`** ke **Secondary y-axis** (atau pakai
   *Line and clustered column chart* → kolom = makro, garis = default_rate).
4. **Format → Y-Axis → Secondary** aktif; beri warna garis berbeda (merah=default, biru=kurs).
5. (Pilih makro) buat **Field parameter**: **Modeling → New parameter → Fields** berisi
   `exchange_rate_twd_usd`, `real_broad_eer`, `total_reserves` → jadikan **Slicer** pemilih indikator.

### Zona D — Default vs makro (**Scatter chart**, korelasi ≈ 0)
1. Visual **Scatter chart**. **X Axis = `exchange_rate_twd_usd`** (Average),
   **Y Axis = `default_rate`** (Average), **Values = `month_name`** (agar 1 titik per bulan).
2. **Analytics pane → Trend line** ON.
3. Tambah **Card** kecil `corr_fx` di dekatnya sebagai anotasi korelasi.
> Titik akan mendatar → **korelasi ≈ 0,00** (temuan jujur: label default per-klien konstan tiap
> bulan — keterbatasan grain, report §10).

---

## 6. Filter interaktif (wajib §8)
Tambah **Slicer** di kanvas (otomatis memfilter semua visual sehalaman):
- **`dimension`** (Single select) → zona B.
- **Indikator makro** (Field parameter) → zona C & D.
- **`month_name`** (rentang/checklist) → zona C & D.
- Atur cakupan via **Format → Edit interactions** bila perlu membatasi visual yang terpengaruh.

---

## 7. Menyusun & merapikan halaman
1. Susun: 4–5 **Card** sejajar di atas; **bar** (kiri) & **line** (kanan) di tengah; **scatter** +
   **slicer** di bawah. Atur posisi/ukuran dengan drag.
2. Tambah **Text box** judul: "Credit-Card Default Risk Taiwan 2005 — ELT (Power BI)".
3. **View → Themes** untuk warna konsisten (samakan dengan versi Tableau agar screenshot sebanding).

## 8. Simpan & ekspor (untuk report §8–§9)
- **File → Save As →** `dashboard/powerbi_elt_dashboard.pbix`.
- Screenshot: **File → Export → PDF**, atau **Win+Shift+S** → simpan
  `dashboard/screenshots/powerbi_elt_dashboard.png`.
- Verifikasi angka: **overall ≈ 0,2212**, **total clients 150.000** — harus sama dengan Tableau
  (ETL). Kecocokan = bukti konsistensi ETL vs ELT (report §9).

---

## 9. Troubleshooting (kasus nyata di proyek ini)
| Gejala | Sebab | Solusi |
|---|---|---|
| `Invalid OperationHandle … EXECUTE_STATEMENT` / "Failed to save modifications" | DirectQuery: query paralel berebut handle / sesi HS2 di-recycle | **Max connections per data source = 1**; matikan background preview; muat **hanya `kpi_*`**; **Refresh** setelah HS2 di-recreate; atau pakai **Import** / CSV |
| "Unexpected response received from server" | DSN transport salah | DSN: **Thrift Transport = Binary**, **SSL = OFF**, Mechanism **User Name** `hive` |
| Query lambat / HS2 berat | Spark/Kafka ikut jalan / tarik tabel 900k | `docker compose stop spark-master spark-worker kafka kafka-ui`; jangan DirectQuery tabel fakta |
| Nilai ke-jumlah (mis. default_rate aneh besar) | agregasi Sum | set **Summarization = Average** |
| Bulan tak urut | belum sort | `month_name` **Sort by column** `date_key` |
| Tetap gagal ODBC | driver/timeout | **Cara C — CSV** di `dashboard/exports/` (pasti jalan) |

---

## 10. Ringkas urutan
1. `docker compose stop spark-master spark-worker kafka kafka-ui` + recreate HS2 →
2. Get Data → ODBC (**Import**, DB `bigdata_elt`) → centang **kpi_** → Load →
3. set tipe & Average, sort bulan →
4. bangun zona A–D →
5. tambah slicer →
6. rapikan + Save `.pbix` + screenshot →
7. cek overall 0,2212 == Tableau.
