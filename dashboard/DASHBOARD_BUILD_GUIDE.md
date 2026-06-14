# Panduan Membangun Dashboard — Tableau (ETL) & Power BI (ELT)
# Dashboard Build Guide — Tableau (ETL) & Power BI (ELT)
### Tugas Besar Big Data · Credit-Card Default (Taiwan 2005)

> **ID:** Panduan langkah-demi-langkah membangun **desain dashboard yang sama** di dua tools dari
> tabel `kpi_*`. Spesifikasi desain lengkap ada di [DASHBOARD_SPEC.md](DASHBOARD_SPEC.md);
> koneksi ODBC di [HIVE_ODBC_CONNECTION.md](HIVE_ODBC_CONNECTION.md).
> **EN:** step-by-step to build the **same dashboard** in both tools from the `kpi_*` tables.

---

## 0. Prasyarat / Prerequisites
1. Pipeline sudah dijalankan → tabel `kpi_*` ada di **`bigdata_etl`** (untuk Tableau) dan
   **`bigdata_elt`** (untuk Power BI). Verifikasi:
   ```bash
   docker compose exec hiveserver2 beeline -u "jdbc:hive2://localhost:10000" \
     -e "SHOW TABLES IN bigdata_etl LIKE 'kpi_*'; SHOW TABLES IN bigdata_elt LIKE 'kpi_*';"
   ```
2. **HiveServer2** punya RAM cukup (matikan spark-worker/kafka dulu — lihat `docs/CARA_MENJALANKAN.pdf` §6).
3. **Tableau Desktop** + **Power BI Desktop** + **Hive ODBC driver 64-bit** terpasang.

## Tabel sumber / Source tables (sama di kedua DB)
| Tabel | Kolom |
|---|---|
| `kpi_overall` | `default_rate`, `total_clients` |
| `kpi_default_by_demographic` | `dimension`, `category`, `clients`, `default_rate` |
| `kpi_monthly_default_vs_macro` | `date_key`, `month_name`, `default_rate`, `exchange_rate_twd_usd`, `real_broad_eer`, `total_reserves` |
| `kpi_corr_default_macro` | `corr_fx`, `corr_reer`, `corr_reserves` |

---

## A. Koneksi data / Connect the data

### Opsi 1 — Hive ODBC (utama / primary)
- **Tableau:** Connect → *More…* → **Other Databases (ODBC)** → pilih DSN Hive →
  Database **`bigdata_etl`** → seret tabel `kpi_*` ke kanvas.
- **Power BI:** Get Data → **ODBC** → pilih DSN → Database **`bigdata_elt`** → centang `kpi_*` → **Load**.
- Setelan DSN (perbaikan error *"Unexpected response received from server"*): Host `localhost`,
  Port `10000`, HiveServer2, Mechanism **User Name** user `hive`, **Thrift Transport = Binary**,
  **SSL = OFF** → Test = SUCCESS. (Detail: [HIVE_ODBC_CONNECTION.md](HIVE_ODBC_CONNECTION.md).)

### Opsi 2 — CSV (fallback tanpa ODBC)
```bash
python dashboard/export_kpis_csv.py          # -> dashboard/exports/<db>__<tabel>.csv
```
Lalu **Tableau:** Connect → *Text file*; **Power BI:** Get Data → *Text/CSV*. Untuk Tableau pakai
file `bigdata_etl__*.csv`, untuk Power BI pakai `bigdata_elt__*.csv`.

---

## B. Membangun 4 zona / Build the 4 zones
Bangun **identik** di kedua tools (nama field, warna, tata letak sama agar screenshot sebanding).

### Zona A — Kartu KPI / KPI cards  *(dari `kpi_overall` + `kpi_corr_default_macro`)*
- **Overall Default Rate**: kartu besar `default_rate` (format persen). *(≈ 0,2212)*
- **Total Clients**: kartu `total_clients`. *(150.000)*
- 3 kartu kecil korelasi: `corr_fx`, `corr_reer`, `corr_reserves`.
- **Tableau:** drag measure → *Text/Label*, format Number→Percentage. **Power BI:** visual **Card**.

### Zona B — Default per demografi (distribusi & perbandingan)  *(`kpi_default_by_demographic`)*
- **Bar chart**: sumbu = `category`, nilai = `default_rate`, **difilter `dimension`**
  (sex / education / marriage / age_band).
- Tambah **reference line** di nilai overall default rate.
- **Tableau:** `category` ke Columns, `default_rate` ke Rows, `dimension` ke Filter + Pages.
  **Power BI:** *Clustered bar chart*; `dimension` jadi *Slicer*.

### Zona C — Tren waktu Apr–Sep 2005  *(`kpi_monthly_default_vs_macro`)*
- **Line dual-axis:** `default_rate` vs indikator makro terpilih
  (`exchange_rate_twd_usd` / `real_broad_eer` / `total_reserves`) sepanjang `month_name`.
- Urutkan pakai `date_key` agar bulan terbaca Apr→Sep.
- **Tableau:** dua measure di Rows → *Dual Axis* → *Synchronize*? (jangan—skala beda, biarkan ganda).
  **Power BI:** *Line and clustered column* atau *Line chart* dengan secondary axis.

### Zona D — Default vs makro (hubungan)  *(`kpi_monthly_default_vs_macro`)*
- **Scatter:** x = indikator makro, y = `default_rate`, 1 titik/bulan, + trend line.
- Anotasi nilai korelasi dari `kpi_corr_default_macro`.
- **Catatan jujur:** korelasi ≈ 0 (keterbatasan grain label — lihat report §10); tetap tampilkan
  sebagai bukti analisis.

### Filter interaktif / Interactive filters (wajib)
- Selector **dimensi demografi** → Zona B.
- Selector **indikator makro** (FX / real broad EER / reserves) → Zona C & D.
- **Rentang bulan** (Apr–Sep 2005) → Zona C & D.

---

## C. Ambil screenshot / Capture screenshots
Setelah dashboard jadi di **kedua** tools, ekspor PNG ke `dashboard/screenshots/` dengan nama:
| File | Isi |
|---|---|
| `tableau_etl_dashboard.png` | dashboard penuh Tableau (sumber ETL) |
| `powerbi_elt_dashboard.png` | dashboard penuh Power BI (sumber ELT) |
| `tableau_zone_*.png` / `powerbi_zone_*.png` | (opsional) per-zona untuk report |

- **Tableau:** Worksheet/Dashboard → *Export → Image* (atau Dashboard → *Export PDF*).
- **Power BI:** *File → Export → PDF*, atau screenshot OS (Win+Shift+S) untuk PNG.
- Simpan juga file dashboard: `dashboard/tableau_etl_dashboard.twbx` & `dashboard/powerbi_elt_dashboard.pbix`.

## D. Verifikasi & untuk report
- Angka KPI di Tableau (ETL) dan Power BI (ELT) **harus cocok** (overall ≈ 0,2212; 150.000 clients) —
  ini bukti konsistensi ETL vs ELT.
- Masukkan kedua screenshot ke **report §8** dan perbandingan berdampingan ke **report §9** (bonus).
