# P01: kontrak resolver tarif dan snapshot

Dipublikasikan lebih awal untuk konsumen downstream: **P03** [#52](https://github.com/wenn-id/beeloftone/issues/52)
(job karyawan dan realisasi), **H01** [#55](https://github.com/wenn-id/beeloftone/issues/55) (payroll native)
dan **I01** [#53](https://github.com/wenn-id/beeloftone/issues/53) (costing/valuasi). Bentuk shape di bawah
adalah kontrak stabil; implementasi P01 mengikuti ini dan konsumen diharapkan menyimpan persis shape ini.

Syarat P01 [#48](https://github.com/wenn-id/beeloftone/issues/48): tarif diberi versi dengan tanggal berlaku,
pemilihan tarif eksplisit (tidak ada fallback diam-diam ke tarif terbaru/nol/menit standar), dan transaksi
yang sudah disahkan tidak dihitung ulang saat master/tarif berubah. P01 **tidak** membuat charge payroll,
slip gaji atau posting jurnal; P01 hanya menyediakan resolver, snapshot, dan histori.

## Aturan pemilihan tarif

Scope tarif pada schema 58 adalah **jenis pekerjaan** (`service_work_types`). Scope product/employee
menunggu D04; lihat `docs/f01-owner-decisions.md` D04.

1. Tanggal acuan adalah **tanggal pengerjaan** (business date ISO `YYYY-MM-DD`, zona `Asia/Jakarta`).
   DEMO_ASSUMPTION (D04 belum final): tanggal acuan = tanggal realisasi/pekerjaan, bukan tanggal kirim
   atau tanggal approval. Interval efektif adalah setengah-terbuka `[effective_from, effective_to)`;
   `effective_to` NULL berarti terbuka.
2. Kandidat = `service_rate_events` untuk work type itu yang `active=1` dan intervalnya mencakup tanggal
   acuan: `effective_from <= date AND (effective_to IS NULL OR date < effective_to)`.
3. Tepat satu kandidat → terpilih. **Nol kandidat → error 422 eksplisit**, bukan tarif terbaru, bukan nol:
   - ada revision nonaktif yang mencakup tanggal → `tarif <kode> nonaktif pada tanggal <date>`;
   - tidak ada sama sekali → `tarif <kode> tidak ditemukan pada tanggal <date>`.
4. **Dua kandidat atau lebih → error 409 eksplisit** (interval tumpang tindih). Overlap dicegah juga saat
   menyimpan revisi baru: di antara revisi aktif yang ada, interval baru tidak boleh berpotongan.
5. Nominal disimpan **satu kali** sebagai `amount_minor` (integer minor, 100 minor = 1 IDR) plus
   `rate_basis` authoritative ('lusin' atau 'pcs'). Nilai lawan (per pcs / per lusin) **selalu derived**:
   `Fraction` eksak, plus nilai 2dp ROUND_HALF_UP yang jelas ditandai display-only. Mengirim nominal
   pcs dan lusin sekaligus ditolak; konsumen tidak boleh menyimpan dua angka bebas.
6. Aritmatika upah memakai `beeloft.contracts.wage_for_realization` (rasional eksak sampai pembulatan
   akhir). Basis perhitungan selalu `rate_per_lusin_minor` (integer eksak):
   basis 'lusin' → `amount_minor`; basis 'pcs' → `amount_minor * 12`.

## Shape `Store.resolve_service_rate(work_type_id, effective_date, policy=DEMO_POLICY)`

Dipanggil resolver; `snapshot_service_rate()` adalah alias yang selalu membekukan bentuk ini plus
`snapshot_at`. Semua field immutable kecuali dinyatakan.

```jsonc
{
  "work_type_id": "…uuid…",
  "work_type_code": "DEMO-JAHIT",          // immutable
  "work_type_name": "Jahit",               // nama saat ini, hanya label
  "rate_revision": "DEMO-JAHIT#2",         // ref immutable: "<kode>#<revision>"
  "rate_revision_number": 2,               // immutable
  "rate_basis": "lusin",                   // basis authoritative nominal tersimpan
  "amount_minor": 1440000,                 // nominal pada rate_basis (minor)
  "currency": "IDR",
  "effective_from": "2026-09-16",          // immutable
  "effective_to": null,                    // immutable; null = terbuka
  "active": true,                          // status revision terpilih
  "rate_per_lusin_minor": 1440000,         // derived eksak; basis perhitungan upah
  "rate_per_lusin_money": "14400.00",      // derived display 2dp
  "rate_per_pcs_exact": "12000",           // derived: Fraction string minor per pcs
  "rate_per_pcs_money": "1200.00",         // derived display 2dp ROUND_HALF_UP (display only)
  "calculation_policy_ref": "DEMO-20260928-1",
  "effective_date": "2026-09-16",          // tanggal acuan yang dipakai memilih
  "timezone": "Asia/Jakarta",              // DEMO_ASSUMPTION: zona tanggal bisnis
  "source_table": "service_rate_events"
}
```

## Shape `Store.resolve_product_services(product_id, effective_date, policy=DEMO_POLICY)`

Menerapkan resolver per SKU: ambil penerapan template terbaru untuk SKU (`service_template_applications`),
lalu resolve tarif tiap komponen pekerjaan pada tanggal acuan.

```jsonc
{
  "product_id": "…uuid…",
  "sku": "DEMO-LUNA-BLUE-M",
  "template_id": "…uuid…",
  "template_code": "DEMO-TPL-JAHIT",
  "template_revision": 1,                  // versi template saat diterapkan (immutable)
  "applied_at": "2026-09-27T…Z",
  "applied_by": "Admin Demo",
  "services": [ /* resolve_service_rate shape per work type */ ],
  "calculation_policy_ref": "DEMO-20260928-1",
  "effective_date": "2026-09-16",
  "timezone": "Asia/Jakarta"
}
```

Jika salah satu komponen tidak punya tarif valid pada tanggal acuan, seluruh resolve gagal 422/409 dengan
daftar work type bermasalah — tidak pernah mengembalikan tarif parsial atau nominal nol.

## Shape `Store.preview_service_wage(work_type_id, pcs, effective_date, policy=DEMO_POLICY)`

Preview demo: gabungan snapshot di atas plus `beeloft.contracts.wage_for_realization` (pcs, lusin_exact,
wage_minor, rounding_*). Tidak ada charge, tidak ada payroll, tidak ada posting. Hasil ini adalah bentuk
yang akan dikonsumsi P03/H01 saat finalisasi charge.

## Kewajiban downstream (P03/H01/I01)

Saat transaksi difinalisasi, konsumen **menyimpan snapshot** pilihan tarif: minimal
`rate_revision`, `rate_revision_number`, `rate_basis`, `amount_minor`, `rate_per_lusin_minor`,
`currency`, `effective_from`, `effective_to`, `template_revision`, `calculation_policy_ref`, dan
tanggal acuan. Field `rate_revision` + `rate_per_lusin_minor` inilah yang membuat histori tidak
dihitung ulang: perhitungan ulang selalu memakai snapshot sendiri, bukan resolve terhadap master terbaru.

Perubahan master setelah finalisasi (tarif baru, template nonaktif, work type nonaktif):
- memblokir pemakaian baru sesuai aturan di atas;
- **tidak** menghapus histori penerapan (`service_template_applications` append-only);
- **tidak** membatalkan snapshot transaksi lama;
- **tidak** menghitung ulang pekerjaan yang berjalan.

## Pemisahan kapasitas

`production_routing_standard_events.minutes_per_unit` tetap menjadi input kapasitas tersendiri dan
**bukan** tarif upah: mengubah menit tidak mengubah tarif, mengubah tarif tidak mengubah menit.
Lihat `docs/p01-template-rate-readiness.md` dan kontrak F02.

## Izin (baseline teknis; D17 belum final)

Baca work type/kelompok/template/tarif/histori: semua role terautentikasi. Tulis (create/change/rate/
apply): `admin` saja, ditegakkan di `Store._write`. Integrasi permission per-fungsi [#45](https://github.com/wenn-id/beeloftone/issues/45)
menunggu merge; P01 memakai gate role existing.
