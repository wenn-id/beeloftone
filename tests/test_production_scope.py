"""Agregat order terpilih untuk jawaban fokus: seluruh populasi, bukan satu halaman.

`production_board()` menyajikan ringkasan global supaya KPI board tidak bergerak ketika daftar
difilter. `production_scope()` adalah kebalikannya dan dipakai jawaban fokus investigasi AI: angka
yang hanya mencakup order yang dipilih, dihitung atas seluruh populasi yang cocok. Modul ini
mengunci dua sisi sekaligus - agregat terpilih yang benar terhadap oracle Python, dan kontrak KPI
board yang tidak berubah.

Nilai harapan tidak pernah diambil dari fungsi agregat yang diuji: setiap baris order dihitung
ulang dari saldo tahapnya dengan aritmetika Python biasa.
"""

from unittest import TestCase

import test_board_filters as board_tests


class ProductionScopeTest(TestCase):
    setUp = board_tests.BoardFilterTest.setUp
    post = board_tests.BoardFilterTest.post
    order = board_tests.BoardFilterTest.order
    move = board_tests.BoardFilterTest.move

    def scope(self, **params):
        return self.app.state.store.production_scope(**params)

    def board(self, **params):
        return self.app.state.store.production_board(**params)

    def oracle(self, rows):
        """Hitung ulang agregat dari baris order yang dikembalikan daftar board."""
        expected = {'orders': len(rows), 'active': 0, 'overdue': 0, 'closed': 0,
                    'in_progress': 0, 'rework': 0}
        for row in rows:
            pending = row['target_quantity'] - row['totals']['warehouse'] - row['totals']['reject']
            if pending > 0:
                expected['active'] += 1
                expected['overdue'] += row['overdue']
            else:
                expected['closed'] += 1
            expected['in_progress'] += sum(row['totals'][stage] for stage in
                                           ('cutting', 'sewing', 'finishing', 'qc', 'rework'))
            expected['rework'] += row['totals']['rework']
        return expected

    def mixed_population(self):
        """Tiga order dengan tenggat, PIC, dan tahap yang berbeda."""
        first = self.order(reference='SCOPE-A', qty=100, due_date='2026-01-01')
        second = self.order(reference='SCOPE-B', qty=80, owner_id=self.admin['id'], due_date='2026-12-31')
        third = self.order(reference='SCOPE-C', qty=60, due_date='2026-12-31')
        self.move(first['lines'][0]['id'], 'planned', 'cutting', 100)
        self.move(second['lines'][0]['id'], 'planned', 'cutting', 80)
        self.move(second['lines'][0]['id'], 'cutting', 'sewing', 30)
        return first, second, third

    def test_selected_aggregate_matches_the_board_population_for_every_filter(self):
        self.mixed_population()
        filters = ({}, {'status': 'active'}, {'status': 'overdue'}, {'status': 'blocked'},
                   {'status': 'closed'}, {'stage': 'cutting'}, {'stage': 'sewing'},
                   {'owner_id': self.admin['id']}, {'query': 'SCOPE-B'}, {'query': 'scope'},
                   {'query': 'TIDAK-ADA'})
        for params in filters:
            selection = self.board(**params)
            # Populasi kecil: satu halaman memang memuat seluruh hasil, jadi oracle dan daftar
            # menunjuk populasi yang sama persis.
            self.assertEqual(selection['total'], len(selection['orders']), params)
            scope = self.scope(**params)
            self.assertEqual(scope['total'], selection['total'], params)
            self.assertEqual(scope['summary'], self.oracle(selection['orders']), params)

    def test_board_kpi_stays_global_while_the_selected_aggregate_narrows(self):
        self.mixed_population()
        global_board = self.board()
        self.assertEqual(global_board['summary'],
                         {'orders': 3, 'active': 3, 'overdue': 1, 'closed': 0,
                          'in_progress': 180, 'rework': 0})
        for params in ({'query': 'SCOPE-B'}, {'owner_id': self.admin['id']},
                       {'status': 'overdue'}, {'stage': 'sewing'}):
            filtered = self.board(**params)
            self.assertEqual(filtered['summary'], global_board['summary'], params)
            self.assertNotEqual(self.scope(**params)['summary'], global_board['summary'], params)
        self.assertEqual(self.scope(query='SCOPE-B')['summary'],
                         {'orders': 1, 'active': 1, 'overdue': 0, 'closed': 0,
                          'in_progress': 80, 'rework': 0})

    def test_scope_counts_only_issues_of_the_selected_orders(self):
        first = self.order(reference='SCOPE-ISSUE-A')
        second = self.order(reference='SCOPE-ISSUE-B')
        self.post('/api/issues', dict(line_id=first['lines'][0]['id'], stage='cutting',
            owner_id=self.operator['id'], description='Kain sobek'))
        resolved = self.post('/api/issues', dict(line_id=second['lines'][0]['id'], stage='cutting',
            owner_id=self.operator['id'], description='Jarum patah'))
        self.post('/api/issues/' + resolved['id'] + '/resolve', {'resolution': 'Jarum diganti'})
        self.assertEqual(self.board()['open_issues'], 1)
        self.assertEqual(self.scope()['open_issues'], 1)
        self.assertEqual(self.scope(query='SCOPE-ISSUE-A')['open_issues'], 1)
        self.assertEqual(self.scope(query='SCOPE-ISSUE-B')['open_issues'], 0)
        self.assertEqual(self.scope(query='TIDAK-ADA')['open_issues'], 0)

    def test_empty_population_is_reported_as_zero_not_as_the_global_board(self):
        self.order(reference='SCOPE-ONLY')
        self.assertEqual(self.board(query='TIDAK-ADA')['summary']['active'], 1)
        self.assertEqual(self.scope(query='TIDAK-ADA'),
                         {'summary': {'orders': 0, 'active': 0, 'overdue': 0, 'closed': 0,
                                      'in_progress': 0, 'rework': 0}, 'total': 0, 'open_issues': 0})
