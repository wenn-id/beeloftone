"""M02 (#44) — master unit usaha, lokasi, pihak, employee, dan pemetaan lokasi.

Cakupan: integritas migrasi dari DB lama, idempotensi master, nama lokasi sama di
unit berbeda, aturan nonaktif pada transaksi baru, relasi employee stabil lewat
ID, dan pemetaan lokasi teks -> identitas storage (deterministik/ambigu/eksplisit).
"""
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from beeloft.api import create_app
from beeloft.store import Store, DomainError
import test_production


class BusinessMastersTest(test_production.ProductionTest):
    def setUp(self):
        super().setUp()
        self.unit = self.post('/api/business-units',
                              {'code': 'JKT', 'name': 'Jakarta', 'reason': 'Unit pertama'})
        self.unit2 = self.post('/api/business-units',
                               {'code': 'BDG', 'name': 'Bandung', 'reason': 'Unit kedua'})

    def storage(self, code='GDG-A', name='Gudang A', unit=None, **options):
        return self.post('/api/storages', {'code': code, 'name': name, 'kind': 'warehouse',
                                           'business_unit_id': (unit or self.unit)['id'],
                                           'reason': 'Lokasi demo'}, **options)

    # --- migrasi & integritas ------------------------------------------

    def _plain(self):
        """Koneksi tanpa row_factory untuk PRAGMA; WAL di-checkpoint dulu supaya
        file sampingan -wal/-shm tidak mengunci folder sementara di Windows."""
        db = sqlite3.connect(self.path)
        db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        db.row_factory = None
        return db

    def test_migration_from_55_is_additive_and_idempotent(self):
        with closing(self._plain()) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 59)
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])
        # Membangun ulang Store pada DB yang sudah termigrasi tidak boleh mengubah
        # skema maupun user_version (jalur migrasi dijaga idempoten).
        Store(self.path)
        with closing(self._plain()) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 59)
            # Kolom additive yang dicek ulang tidak menduplikasi.
            cols = {row[1] for row in db.execute('PRAGMA table_info(suppliers)')}
            self.assertIn('active', cols)
            emp = {row[1] for row in db.execute('PRAGMA table_info(workforce_employee_events)')}
            self.assertIn('position_id', emp)
            self.assertIn('business_unit_id', emp)

    def test_migration_rewinds_and_reapplies_cleanly(self):
        # Test lain membangun skema lengkap lalu memutar balik user_version untuk
        # mensimulasikan DB lama; runner harus bisa migrasi ulang tanpa error.
        with closing(self._plain()) as db:
            db.execute('PRAGMA user_version=54')
            db.commit()
        Store(self.path)
        with closing(self._plain()) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 59)
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    # --- master dasar ----------------------------------------------------

    def test_master_create_history_and_stale_revision_guard(self):
        for path, body, label in (
                ('/api/business-units', {'code': 'SMG', 'name': 'Semarang', 'reason': 'u'}, 'unit'),
                ('/api/customers', {'code': 'C-1', 'name': 'Toko Sumber', 'contact': 'Budi',
                                    'address': 'Jl. Mawar', 'reason': 'u'}, 'customer'),
                ('/api/positions', {'code': 'JAHIT', 'name': 'Penjahit', 'reason': 'u'}, 'position'),
                ('/api/payment-methods', {'code': 'TUNAI', 'name': 'Tunai', 'kind': 'cash',
                                          'reason': 'u'}, 'payment method')):
            created = self.post(path, body)
            self.assertEqual((created['code'], created['revision'], created['active']),
                             (body['code'], 1, True), label)
            history = self.client.get(f"{path}/{created['id']}/history").json()
            self.assertEqual(len(history['items']), 1, label)

    def test_master_change_is_versioned_and_no_change_rejected(self):
        changed = self.post(f"/api/business-units/{self.unit['id']}/changes",
                            {'expected_revision': 1, 'name': 'Jakarta Raya', 'active': True,
                             'reason': 'Rename'})
        self.assertEqual((changed['revision'], changed['name']), (2, 'Jakarta Raya'))
        history = self.client.get(f"/api/business-units/{self.unit['id']}/history").json()
        self.assertEqual([row['revision'] for row in history['items']], [2, 1])
        # Revisi basi ditolak.
        self.post(f"/api/business-units/{self.unit['id']}/changes",
                  {'expected_revision': 1, 'name': 'Jakarta', 'active': True,
                   'reason': 'stale'}, status=409)
        # Tanpa perubahan ditolak.
        self.post(f"/api/business-units/{self.unit['id']}/changes",
                  {'expected_revision': 2, 'name': 'Jakarta Raya', 'active': True,
                   'reason': 'no-op'}, status=422)

    def test_master_deactivation_keeps_history_readable(self):
        storage = self.storage()
        deactivated = self.post(f"/api/storages/{storage['id']}/changes",
                                {'expected_revision': 1, 'name': 'Gudang A', 'kind': 'warehouse',
                                 'active': False, 'reason': 'Pindah gudang'})
        self.assertFalse(deactivated['active'])
        # Identitas tetap ada; history terbaca.
        one = self.client.get(f"/api/storages/{storage['id']}").json()
        self.assertEqual((one['code'], one['active']), ('GDG-A', False))
        history = self.client.get(f"/api/storages/{storage['id']}/history").json()
        self.assertEqual([row['active'] for row in history['items']], [False, True])
        # Daftar aktif hanya memunculkan yang aktif; status=all memunculkan semua.
        active = self.client.get('/api/storages?status=active').json()
        self.assertEqual(active['total'], 0)
        all_rows = self.client.get('/api/storages?status=all').json()
        self.assertEqual(all_rows['total'], 1)

    def test_unit_with_active_storage_cannot_be_deactivated(self):
        self.storage()
        self.post(f"/api/business-units/{self.unit['id']}/changes",
                  {'expected_revision': 1, 'name': 'Jakarta', 'active': False,
                   'reason': 'nonaktif'}, status=409)

    # --- nama lokasi sama di unit berbeda --------------------------------

    def test_same_storage_name_in_different_units_is_distinguishable(self):
        a = self.storage(name='Gudang Pusat', code='GP-A', unit=self.unit)
        b = self.storage(name='Gudang Pusat', code='GP-B', unit=self.unit2)
        self.assertNotEqual(a['id'], b['id'])
        self.assertEqual((a['unit_code'], b['unit_code']), ('JKT', 'BDG'))
        self.assertNotEqual(a['label'], b['label'])
        # Nama sama dalam satu unit ditolak.
        self.post('/api/storages', {'code': 'GP-C', 'name': 'Gudang Pusat', 'kind': 'warehouse',
                                    'business_unit_id': self.unit['id'],
                                    'reason': 'dup'}, status=409)
        # Filter per unit.
        rows = self.client.get(f"/api/storages?business_unit_id={self.unit2['id']}").json()
        self.assertEqual([row['code'] for row in rows['items']], ['GP-B'])

    def test_inactive_unit_cannot_receive_new_storage(self):
        self.post(f"/api/business-units/{self.unit2['id']}/changes",
                  {'expected_revision': 1, 'name': 'Bandung', 'active': False,
                   'reason': 'tutup unit'})
        self.post('/api/storages', {'code': 'X', 'name': 'Gudang X', 'kind': 'warehouse',
                                    'business_unit_id': self.unit2['id'],
                                    'reason': 'lokasi di unit nonaktif'}, status=422)

    # --- pihak: supplier & customer --------------------------------------

    def test_supplier_identity_immutable_but_active_toggle(self):
        supplier = self.post('/api/suppliers', {'code': 'S-1', 'name': 'Toko Kain',
                                                'contact': '', 'address': '', 'reason': 'u'})
        self.assertTrue(supplier['active'])
        deactivated = self.post(f"/api/suppliers/{supplier['id']}/changes",
                                {'active': False, 'reason': 'Pindah supplier'})
        self.assertFalse(deactivated['active'])
        # No-op ditolak.
        self.post(f"/api/suppliers/{supplier['id']}/changes",
                  {'active': False, 'reason': 'lagi'}, status=422)
        with closing(sqlite3.connect(self.path)) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE suppliers SET name='Lain' WHERE id=?", (supplier['id'],))

    # --- employee: ID stabil + relasi ------------------------------------

    def employee(self, code='EMP-1', name='Sari', department='Produksi', **options):
        body = {'code': code, 'name': name, 'department': department, 'reason': 'u'}
        body.update({k: options.pop(k) for k in ('position_id', 'business_unit_id') if k in options})
        return self.post('/api/workforce/employees', body, **options)

    def test_employee_links_position_and_unit_and_legacy_id(self):
        position = self.post('/api/positions', {'code': 'JAHIT', 'name': 'Penjahit', 'reason': 'u'})
        employee = self.employee(position_id=position['id'], business_unit_id=self.unit['id'])
        self.assertEqual((employee['position_code'], employee['business_unit_code']),
                         ('JAHIT', 'JKT'))
        # Legacy ID stabil untuk relasi payroll/HR lama.
        legacy = self.post(f"/api/workforce/employees/{employee['id']}/legacy-ids",
                           {'legacy_id': 'HR-9001', 'source_system': 'mekari',
                            'reason': 'ID payroll lama'})
        self.assertEqual(legacy['legacy_id'], 'HR-9001')
        listed = self.client.get(
            f"/api/workforce/employees/{employee['id']}/legacy-ids").json()
        self.assertEqual([row['legacy_id'] for row in listed], ['HR-9001'])
        # Legacy ID unik per sistem sumber.
        self.post(f"/api/workforce/employees/{employee['id']}/legacy-ids",
                  {'legacy_id': 'HR-9001', 'source_system': 'mekari',
                   'reason': 'dup'}, status=409)

    def test_inactive_position_rejected_on_new_employee(self):
        position = self.post('/api/positions', {'code': 'QC', 'name': 'QC', 'reason': 'u'})
        self.post(f"/api/positions/{position['id']}/changes",
                  {'expected_revision': 1, 'name': 'QC', 'active': False, 'reason': 'hapus jabatan'})
        self.employee(position_id=position['id'], status=422)

    def test_position_is_not_department(self):
        # Jabatan dan departemen adalah dua hal terpisah; tidak ada penyamaan otomatis.
        position = self.post('/api/positions', {'code': 'JAHIT', 'name': 'Penjahit', 'reason': 'u'})
        employee = self.employee(department='Produksi', position_id=position['id'])
        self.assertEqual((employee['department'], employee['position_name']), ('Produksi', 'Penjahit'))

    # --- transaksi: aturan nonaktif ---------------------------------------

    def material_receipt(self, storage_id=None, location='Gudang A', **options):
        suffix = str(uuid4())[:6]
        material = self.post('/api/materials', {'code': 'KAIN-' + suffix,
                                                'name': 'Katun', 'unit': 'm'})
        body = {'material_id': material['id'], 'reference': 'RC-' + suffix,
                'supplier': 'Toko Kain', 'location': location, 'received_date': '2026-09-01',
                'quantity': '5', 'reason': 'penerimaan'}
        if storage_id:
            body['storage_id'] = storage_id
        return self.post('/api/material-batches', body, **options)

    def test_receipt_links_storage_and_records_explicit_mapping(self):
        storage = self.storage()
        batch = self.material_receipt(storage_id=storage['id'])
        self.assertEqual(batch['storage']['code'], 'GDG-A')
        self.assertEqual(batch['storage']['match_status'], 'confirmed')
        # Teks lokasi yang tidak cocok ditolak.
        self.material_receipt(storage_id=storage['id'], location='Rak X', status=422)

    def test_inactive_storage_rejected_on_new_receipt(self):
        storage = self.storage()
        self.post(f"/api/storages/{storage['id']}/changes",
                  {'expected_revision': 1, 'name': 'Gudang A', 'kind': 'warehouse',
                   'active': False, 'reason': 'nonaktif'})
        self.material_receipt(storage_id=storage['id'], status=422)

    # --- pemetaan lokasi ---------------------------------------------------

    def seed_location_rows(self):
        """Dua batch dengan teks lokasi yang sama di unit yang berbeda -> ambigu."""
        storage_jkt = self.storage(name='Gudang Sama', code='GS-A', unit=self.unit)
        storage_bdg = self.storage(name='Gudang Sama', code='GS-B', unit=self.unit2)
        a = self.material_receipt(location='Gudang Sama')
        b = self.material_receipt(location='Gudang Sama')
        return storage_jkt, storage_bdg, a, b

    def test_recompute_marks_ambiguous_for_same_name_across_units(self):
        storage_jkt, storage_bdg, batch_a, batch_b = self.seed_location_rows()
        stats = self.post('/api/storage-location-mappings/recompute', {}, key='recompute-1')
        self.assertEqual((stats['ambiguous'], stats['rows']), (2, 2))
        ambiguous = self.client.get('/api/storage-location-mappings?match_status=ambiguous').json()
        self.assertEqual(len(ambiguous), 2)
        # Unit pemilik tidak ditebak: tidak ada storage_id yang terisi otomatis.
        self.assertTrue(all(row['storage_id'] is None for row in ambiguous))

    def test_explicit_mapping_resolves_ambiguous_without_touching_rows(self):
        storage_jkt, storage_bdg, batch_a, batch_b = self.seed_location_rows()
        self.post('/api/storage-location-mappings/recompute', {}, key='recompute-2')
        ambiguous = self.client.get(
            '/api/storage-location-mappings?match_status=ambiguous').json()
        target = ambiguous[0]
        mapped = self.post(f"/api/storage-location-mappings/{target['id']}/mappings",
                           {'storage_id': storage_jkt['id'], 'reason': 'Pemetaan admin'})
        self.assertEqual((mapped['match_status'], mapped['match_basis']), ('confirmed', 'explicit'))
        # Recompute berikutnya mempertahankan pemetaan eksplisit.
        stats = self.post('/api/storage-location-mappings/recompute', {}, key='recompute-3')
        self.assertEqual(stats['preserved'], 1)
        # Teks transaksi tidak berubah.
        again = self.client.get(f"/api/material-batches/{batch_a['id']}").json()
        self.assertEqual(again['location'], 'Gudang Sama')

    def test_unique_active_name_auto_confirms(self):
        storage = self.storage(name='Gudang Unik', code='GU', unit=self.unit)
        batch = self.material_receipt(location='Gudang Unik')
        stats = self.post('/api/storage-location-mappings/recompute', {}, key='recompute-4')
        self.assertEqual((stats['confirmed'], stats['ambiguous']), (1, 0))
        refreshed = self.client.get(f"/api/material-batches/{batch['id']}").json()
        self.assertEqual(refreshed['storage']['code'], 'GU')

    def test_pending_when_no_storage_matches(self):
        batch = self.material_receipt(location='Gudang Tak Terdaftar')
        stats = self.post('/api/storage-location-mappings/recompute', {}, key='recompute-5')
        self.assertEqual((stats['pending'], stats['confirmed']), (1, 0))
        pending = self.client.get('/api/storage-location-mappings?match_status=pending').json()
        self.assertEqual(len(pending), 1)

    # --- izin ---------------------------------------------------------------

    def test_only_admin_can_create_and_change_masters(self):
        self.post('/api/business-units', {'code': 'NOPE', 'name': 'Nope', 'reason': 'u'},
                  api_key=self.operator['api_key'], status=403)
        self.post(f"/api/business-units/{self.unit['id']}/changes",
                  {'expected_revision': 1, 'name': 'Jakarta', 'active': True, 'reason': 'u'},
                  api_key=self.viewer['api_key'], status=403)
        # Viewer tetap bisa membaca.
        response = self.client.get('/api/business-units',
                                   headers={'X-API-Key': self.viewer['api_key']})
        self.assertEqual(response.status_code, 200)

    def test_recompute_is_admin_only(self):
        self.post('/api/storage-location-mappings/recompute', {},
                  api_key=self.operator['api_key'], status=403)


if __name__ == '__main__':
    unittest.main()
