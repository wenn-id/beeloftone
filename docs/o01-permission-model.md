# O01 (#45) — Izin per fungsi & pemisahan tugas

Status: implementasi. Dibangun di atas auth existing (`/api/session`, `X-API-Key`, SSO OIDC).
Tidak ada sistem login/identitas kedua.

## Katalog izin

Sembilan izin kanonikal di `beeloft/permissions.py` (`PERMISSIONS`):

- `read_operational` — baca data operasional
- `create_transaction` — buat/ubah transaksi
- `approve_transaction` — setujui pengajuan
- `record_payment` — eksekusi pembayaran
- `post_ledger` — posting buku besar
- `export_data` — ekspor data/CSV
- `view_salary` — rincian gaji & payroll
- `view_margin_profit` — margin & laba
- `manage_access` — kelola akses pengguna

`view_salary` dan `view_margin_profit` **terpisah**: tidak ada preset yang memegang keduanya
kecuali `owner` (demo saja). `record_payment` juga terpisah dari `approve_transaction` —
status `approved` tidak memberi hak bayar.

## Skema (migrasi `user_version` 58, `beeloft/permissions.sql`)

- `user_permissions(user_id, permission, granted_by, granted_at)` — izin granular, `CHECK` ke katalog.
- `user_business_units(user_id, business_unit_id, ...)` — cakupan unit, FK ke `business_units` (#44).
- `user_access_profiles(user_id, all_units, preset, no_self_approval, updated_by, updated_at)`.
- `user_access_events(...)` — audit append-only setiap mutasi akses (termasuk `disable_user`).
- `orders.business_unit_id` ditambahkan untuk penandaan unit pada order.

Migrasi menulis baris izin eksplisit untuk seluruh user existing senilai akses pra-O01
(`LEGACY_COMPATIBILITY_PERMISSIONS`). Migrasi tidak pernah menebak kebijakan baru dan tidak
mencabut jalur administrasi yang sah. Pengetatan dilakukan eksplisit lewat preset atau
`set_user_permissions`, dan setiap perubahan tercatat.

## Preset demo

`DEMO_PRESET_VERSION = "O01-DEMO-20260928-1"`. Preset adalah **konfigurasi demo berversi**,
bukan klaim struktur jabatan atau kebijakan resmi Beeloft.

| preset | gaji | margin | bayar | kelola akses | cakupan |
|---|---|---|---|---|---|
| `owner` | ya | ya | ya | ya | semua unit |
| `operational_admin` | tidak | tidak | tidak | ya | semua unit |
| `hr_payroll` | ya | tidak | tidak | tidak | semua unit |
| `finance` | tidak | ya | ya | tidak | semua unit |
| `production_operator` | tidak | tidak | tidak | tidak | per unit |
| `management_viewer` | tidak | ya | tidak | tidak | semua unit |
| `auditor_viewer` | tidak | tidak | tidak | tidak | semua unit |

`owner` all-access hanya untuk demo. Akses gaji tidak diberikan otomatis ke admin operasional,
dan tidak digabung dengan akses margin.

## Enforcement

Server-side, bukan sekadar menyembunyikan tombol:

- `require_permission(actor, permission)` di route handler `beeloft/api.py`.
- `require_unit_access(actor, unit_id)` — pengguna ber-cakupan terbatas tidak bisa menembus
  dengan mengganti ID atau memanggil endpoint langsung. Record legacy tanpa unit
  (`unit_id IS NULL`) **ditolak** untuk pengguna ber-cakupan terbatas, bukan diloloskan.
- `check_self_approval(actor, creator_id)` — identitas pembuat dibaca dari server
  (`created_by`/`actor_id` tersimpan), bukan dari payload.
- Izin dibaca ulang setiap request via `Store._user_access`, jadi pencabutan berlaku pada
  request berikutnya walau session browser masih aktif.
- Eskalasi via payload ditolak: `POST /api/users` menolak `permissions`/`business_units`/
  `all_units` di body (HTTP 422); perubahan akses hanya lewat endpoint audited.

Route yang sudah digate: `/api/users*` (`manage_access`), `/api/integrations/mekari/payroll-summary`,
`/api/payroll-payment-reconciliation`, `/api/payroll-accounting-reconciliation` (`view_salary`),
`/api/orders/{id}/contribution-margin` (`view_margin_profit`), `/api/activity.csv` (`export_data`).

## Endpoint akses

- `GET /api/permissions` — katalog + versi preset
- `GET /api/presets` — preset demo + disclaimer
- `POST /api/users` — provisioning (opsional `preset`)
- `GET /api/users`, `GET /api/users/{id}`
- `PUT /api/users/{id}/permissions|preset|units`
- `GET /api/users/{id}/access-events` — audit mutasi akses
- `POST /api/users/{id}/disable` — self-disable ditolak (409)

Semua butuh `manage_access`.

## Belum tercakup (jujur)

- Gate UI di `beeloft/static/app.mjs` belum ada helper `has_permission`; enforcement saat ini
  murni server-side. Endpoint tetap aman tanpa gate UI.
- `require_unit_access` tersedia dan teruji sebagai unit, tapi belum dipasang pada setiap route
  operasional; `orders.business_unit_id` baru disiapkan. Jangan klaim seluruh endpoint sudah
  ter-scope per unit.
- Modul akuntansi/jasa milik agent lain (#46/#48) tidak disentuh.
