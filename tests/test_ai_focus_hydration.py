"""Regresi P3: metadata focus tidak boleh membayar hidrasi seluruh detail order.

`_focus()` dijalankan sebelum dispatch intent. Sebelumnya fungsi itu memanggil `store.orders()`,
yang menghidrasi setiap order lewat `_order()`: revision, lines, balances per line, dan hitungan
kendala terbuka. Biayanya tumbuh sekitar lima statement per order, padahal jawaban approval hanya
memakai agregat dan contoh approval, dan pencocokan focus sendiri hanya memakai kolom identitas.

Pengukuran di sini memakai statement yang benar-benar dieksekusi SQLite, bukan teks sumbernya.
Oracle biaya hidrasinya independen: dibaca langsung dari `store.orders()` atas populasi yang sama,
sehingga angka "sekitar lima per order" tidak pernah dipatok sebagai konstanta di dalam tes.
"""

from beeloft.brain import investigate
import test_approval_aggregates
import test_production


QUESTION = 'approval persetujuan'
# Tabel yang hanya tersentuh kalau detail order benar-benar dihidrasi.
ORDER_DETAIL_TABLES = ('balances', 'order_lines', 'order_changes')


class FocusHydrationFixture(test_approval_aggregates.ApprovalFixture):
    def payload(self, question=QUESTION, **changes):
        return dict(question=question, as_of='2026-11-15', window_days=14, lead_time_days=180,
                    review_period_days=180, safety_stock_days=90, batch_multiple=12) | changes

    def investigate(self, question=QUESTION, **changes):
        return investigate(self.app.state.store, self.payload(question, **changes))

    def executed_sql(self, run):
        """Rekam setiap statement yang benar-benar dieksekusi SQLite selama `run()`."""
        store = self.app.state.store
        statements, original = [], store.connect

        def connect():
            db = original()
            db.set_trace_callback(statements.append)
            return db

        store.connect = connect
        try:
            run()
        finally:
            store.connect = original
        return [' '.join(sql.split()) for sql in statements]

    def reads(self, statements):
        """Statement yang membaca tabel, tanpa BEGIN/COMMIT."""
        return [sql for sql in statements if 'FROM' in sql.upper()]

    def seed_orders(self, count, product=None, due_date='2026-12-31', prefix='FOCUS'):
        product = product or self.product
        return [self.post('/api/orders', {'reference': '%s-%04d' % (prefix, self.next_index()),
                                          'title': 'Batch hidrasi',
                                          'owner_id': self.operator['id'], 'due_date': due_date,
                                          'lines': [{'product_id': product['id'], 'quantity': 1}]})
                for _ in range(count)]


class ApprovalPathHydrationTest(FocusHydrationFixture):
    def test_approval_cost_stays_flat_while_the_order_population_grows(self):
        store = self.app.state.store
        self.seed_marketing(3, amount_minor=1_000_00)

        self.seed_orders(20)
        small = self.reads(self.executed_sql(lambda: self.investigate()))
        self.seed_orders(100)
        large = self.reads(self.executed_sql(lambda: self.investigate()))

        self.assertTrue(small)
        self.assertEqual(len(small), len(large))
        self.assertEqual(small, large)

        # Oracle independen: hidrasi populasi yang sama masih berbiaya sekitar lima statement per
        # order. Itulah biaya yang dulu ikut dibayar jalur approval dan sekarang tidak lagi.
        hydration = self.reads(self.executed_sql(lambda: store.orders(1_000_000_000, 0)))
        identities = self.reads(self.executed_sql(lambda: store.order_identities(1_000_000_000, 0)))
        self.assertEqual(len(store.order_identities(1_000_000_000, 0)), 120)
        self.assertGreaterEqual(len(hydration), 5 * 120)
        self.assertEqual(len(identities), 1)
        self.assertGreater(len(hydration) - len(identities), len(large))

    def test_approval_path_never_touches_order_detail_tables(self):
        self.seed_marketing(2, amount_minor=2_500_00)
        self.seed_orders(5)
        statements = self.executed_sql(lambda: self.investigate())
        for sql in statements:
            for table in ORDER_DETAIL_TABLES:
                self.assertNotIn(table, sql.lower(), sql)

    def test_approval_answer_aggregates_and_evidence_stay_correct(self):
        self.seed_marketing(12, amount_minor=1_000_00)
        self.seed_workforce(4, kind='leave')
        self.seed_orders(30)
        truth = self.oracle()
        report = self.investigate()
        self.assertEqual((truth['total'], truth['amount']), (16, '12000.00'))
        self.assertEqual(report['intent'], 'approvals')
        self.assertEqual(report['answer'], 'Ada 16 item menunggu keputusan dengan total nominal '
                                           'tercatat Rp12000.00.')
        facts = {row['label']: row['value'] for row in report['facts']}
        self.assertEqual((facts['Approval tertunda'], facts['Nominal tertunda']), (16, '12000.00'))
        self.assertEqual((facts['Approval marketing budget'], facts['Approval workforce leave']),
                         (12, 4))
        evidence = report['evidence']['approvals']
        self.assertEqual(evidence['summary']['total'], 16)
        self.assertEqual((evidence['sample_size'], evidence['truncated']), (10, True))
        self.assertEqual(len(report['findings']), 10)
        # Kontrak metadata focus tetap ada meskipun tidak ada entity yang cocok.
        self.assertEqual(report['focus'], {'products': [], 'orders': []})

    def test_focus_metadata_contract_is_unchanged(self):
        order = self.seed_orders(3)[1]
        report = self.investigate('Cek produksi %s untuk SKU %s' % (order['reference'],
                                                                    self.product['sku']))
        self.assertEqual(report['focus']['orders'],
                         [{'id': order['id'], 'reference': order['reference'],
                           'title': order['title']}])
        self.assertEqual(report['focus']['products'],
                         [{'id': self.product['id'], 'sku': self.product['sku'],
                           'name': self.product['name']}])


class MarginSelectionTest(FocusHydrationFixture):
    """Pemilihan order untuk margin sekarang bekerja atas id, bukan order yang sudah dihidrasi."""

    detail = test_production.ProductionTest.detail

    def hydrated_selection(self, focus):
        """Oracle: logika lama, memfilter order yang sudah dihidrasi di Python."""
        orders = self.app.state.store.orders(1_000_000_000, 0)
        if focus['orders']:
            wanted = {row['id'] for row in focus['orders']}
            selected = [row for row in orders if row['id'] in wanted]
        elif focus['products']:
            wanted = {row['id'] for row in focus['products']}
            selected = [row for row in orders
                        if any(line['product_id'] in wanted for line in row['lines'])]
        else:
            selected = orders
        return [row['id'] for row in selected[:100]]

    def assert_margin_selection_matches_oracle(self, question):
        report = self.investigate(question)
        self.assertEqual(report['intent'], 'margin')
        reported = [row['order_id'] for row in report['evidence']['contribution_margins']]
        self.assertEqual(reported, self.hydrated_selection(report['focus']))
        return report

    def mixed_population(self):
        """Dua produk dan tanggal jatuh tempo yang tidak searah dengan urutan pembuatan."""
        other = self.post('/api/products', {'sku': 'VEGA-RED-L', 'name': 'Vega Red',
                                            'size': 'L', 'color': 'Red'})
        for index, due in enumerate(('2026-12-31', '2026-03-01', '2026-07-15')):
            self.seed_orders(1, due_date=due, prefix='LUNA-%d' % index)
            self.seed_orders(1, product=other, due_date=due, prefix='VEGA-%d' % index)
        return other

    def test_selection_matches_the_hydrated_oracle_for_every_focus(self):
        other = self.mixed_population()
        self.assert_margin_selection_matches_oracle('Bagaimana margin kontribusi bisnis saat ini?')
        focused = self.assert_margin_selection_matches_oracle(
            'Bagaimana margin kontribusi untuk %s?' % other['sku'])
        self.assertEqual(len(focused['evidence']['contribution_margins']), 3)
        self.assertEqual(focused['focus']['products'][0]['sku'], other['sku'])

    def test_product_focus_selection_keeps_the_due_date_ordering(self):
        other = self.mixed_population()
        report = self.investigate('Bagaimana margin kontribusi untuk %s?' % other['sku'])
        reported = [row['order_reference'] for row in report['evidence']['contribution_margins']]
        due_dates = [self.detail({'id': row['order_id']})['due_date']
                     for row in report['evidence']['contribution_margins']]
        self.assertEqual(due_dates, sorted(due_dates))
        self.assertEqual(len(set(reported)), 3)

    def test_order_focus_reports_only_that_order(self):
        self.mixed_population()
        order = self.app.state.store.order_identities(1_000_000_000, 0)[0]
        report = self.assert_margin_selection_matches_oracle(
            'Tolong investigasi margin %s' % order['reference'])
        self.assertEqual([row['order_id'] for row in report['evidence']['contribution_margins']],
                         [order['id']])
        self.assertFalse(report['evidence']['truncated'])


class IdentityReadTest(FocusHydrationFixture):
    def test_identity_reads_agree_with_the_hydrated_listing(self):
        store = self.app.state.store
        self.seed_orders(4, due_date='2026-05-05')
        self.seed_orders(3, due_date='2026-02-02')
        hydrated = store.orders(1_000_000_000, 0)
        identities = store.order_identities(1_000_000_000, 0)
        self.assertEqual([{'id': row['id'], 'reference': row['reference'], 'title': row['title']}
                          for row in hydrated], identities)
        self.assertEqual([dict(row) for row in store.product_identities(1_000_000_000, 0)],
                         [{'id': row['id'], 'sku': row['sku'], 'name': row['name']}
                          for row in store.products(1_000_000_000, 0)])
        # Paginasi identitas mengikuti urutan yang sama dengan daftar yang dihidrasi.
        self.assertEqual(store.order_identities(2, 1), identities[1:3])

    def test_product_selection_covers_orders_without_hydrating_them(self):
        store = self.app.state.store
        other = self.post('/api/products', {'sku': 'NOVA-GREEN-S', 'name': 'Nova Green',
                                            'size': 'S', 'color': 'Green'})
        self.seed_orders(3)
        wanted = self.seed_orders(2, product=other)
        selected = store.order_ids_for_products([other['id']])
        self.assertEqual(sorted(selected), sorted(row['id'] for row in wanted))
        self.assertEqual(store.order_ids_for_products([]), [])
        self.assertEqual(store.order_ids_for_products(['missing']), [])
        # Id yang berulang tidak menduplikasi hasil.
        self.assertEqual(store.order_ids_for_products([other['id'], other['id']]), selected)
        statements = self.reads(self.executed_sql(
            lambda: store.order_ids_for_products([other['id']])))
        self.assertEqual(len(statements), 1)
        for sql in statements:
            self.assertNotIn('balances', sql.lower())


class AuthenticatedEndpointTest(FocusHydrationFixture):
    def test_endpoint_answer_is_identical_to_the_direct_call(self):
        self.seed_marketing(5, amount_minor=1_000_00)
        self.seed_orders(8)
        response = self.client.post('/api/ai/investigate', json=self.payload())
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), self.investigate())
