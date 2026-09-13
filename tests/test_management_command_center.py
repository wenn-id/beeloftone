from datetime import datetime, timedelta, timezone
from unittest import TestCase

import test_production as production_tests


class ManagementCommandCenterTest(TestCase):
    setUp = production_tests.ProductionTest.setUp
    post = production_tests.ProductionTest.post
    order = production_tests.ProductionTest.order

    def sync_window(self):
        finished = datetime.now(timezone.utc).replace(microsecond=0)
        return {
            "started_at": (finished - timedelta(minutes=2)).isoformat(),
            "finished_at": finished.isoformat(),
            "snapshot_at": finished.isoformat(),
        }

    def test_empty_command_center_is_honest_about_missing_sources(self):
        report = self.client.get('/api/command-center').json()
        self.assertEqual(report['production'], {
            'active_orders': 0, 'overdue_orders': 0, 'in_progress_quantity': 0,
            'rework_quantity': 0, 'open_issues': 0,
        })
        self.assertEqual(report['approvals']['pending_count'], 0)
        self.assertIsNone(report['sales']['snapshot_at'])
        self.assertIsNone(report['finance']['current'])
        self.assertEqual(report['integrations']['attention_count'], 8)
        self.assertEqual({row['id'] for row in report['attention']},
                         {'integration-jubelio', 'integration-mekari'})

    def test_combines_operational_decisions_and_vendor_snapshots(self):
        order = self.order(qty=12, reference='CMD-OVERDUE')
        self.post('/api/issues', {
            'line_id': order['lines'][0]['id'], 'stage': 'sewing',
            'description': 'Mesin perlu diperiksa', 'owner_id': self.operator['id'],
        }, api_key=self.operator['api_key'])
        material = self.post('/api/materials', {'code': 'CMD-CLOTH', 'name': 'Kain command', 'unit': 'm'})
        self.post('/api/purchase-requests', {
            'reference': 'PR-CMD-001', 'order_id': order['id'], 'required_date': '2026-10-01',
            'estimated_value': '1250000.50', 'reason': 'Menutup kebutuhan produksi',
            'lines': [{'material_id': material['id'], 'quantity': '10.000'}],
        }, api_key=self.operator['api_key'])

        window = self.sync_window()
        self.post('/api/integrations/jubelio/order-snapshots', {
            **window, 'external_cursor': 'orders-command', 'reason': 'Snapshot command center',
            'orders': [],
        })
        self.post('/api/integrations/mekari/finance-snapshots', {
            **window, 'external_cursor': 'finance-command', 'reason': 'Snapshot command center',
            'periods': [{
                'source_report_id': 'finance-command-2026-08', 'period_start': '2026-08-01',
                'period_end': '2026-08-31', 'currency': 'IDR', 'gross_revenue': '5000000',
                'sales_returns': '250000', 'cost_of_goods_sold': '2000000',
                'operating_expenses': '1000000', 'other_income': '100000',
                'other_expenses': '50000', 'cash_balance': '3000000',
                'receivables_balance': '750000', 'payables_balance': '500000',
            }],
        })
        self.post('/api/integrations/mekari/payable-snapshots', {
            **window, 'as_of': '2026-09-13', 'external_cursor': 'payables-command',
            'reason': 'Snapshot command center', 'payables': [{
                'external_payable_id': 'payable-command', 'reference': 'INV-CMD-PAY',
                'external_supplier_id': 'supplier-command', 'supplier_name': 'Supplier Command',
                'invoice_date': '2026-08-01', 'due_date': '2026-09-01', 'status': 'open',
                'currency': 'IDR', 'original_amount': '800000', 'paid_amount': '0',
                'updated_at': '2026-09-13T10:00:00+07:00',
            }],
        })
        self.post('/api/integrations/mekari/receivable-snapshots', {
            **window, 'as_of': '2026-09-13', 'external_cursor': 'receivables-command',
            'reason': 'Snapshot command center', 'receivables': [{
                'external_receivable_id': 'receivable-command', 'reference': 'INV-CMD-REC',
                'external_customer_id': 'customer-command', 'customer_name': 'Customer Command',
                'invoice_date': '2026-08-01', 'due_date': '2026-09-01', 'status': 'open',
                'currency': 'IDR', 'original_amount': '900000', 'received_amount': '0',
                'updated_at': '2026-09-13T10:00:00+07:00',
            }],
        })

        report = self.client.get('/api/command-center').json()
        self.assertEqual((report['production']['active_orders'], report['production']['overdue_orders'],
                          report['production']['open_issues']), (1, 1, 1))
        self.assertEqual((report['approvals']['pending_count'], report['approvals']['pending_amount']),
                         (1, '1250000.50'))
        self.assertEqual(report['finance']['current']['net_profit'], '1800000.00')
        self.assertEqual(report['finance']['payables']['overdue_amount'], '800000.00')
        self.assertEqual(report['finance']['receivables']['overdue_amount'], '900000.00')
        attention = {row['id']: row for row in report['attention']}
        self.assertEqual(attention['production-overdue']['priority'], 'critical')
        self.assertEqual(attention['approvals-pending']['action'], 'approvals')
        self.assertEqual(attention['payables-overdue']['action'], 'mekari_payables')
        self.assertEqual(report['status']['critical_count'], 3)

    def test_all_active_roles_can_read_but_anonymous_cannot(self):
        for account in (self.admin, self.operator, self.viewer):
            response = self.client.get('/api/command-center',
                                       headers={'X-API-Key': account['api_key']})
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/api/command-center', headers={'X-API-Key': 'invalid'}).status_code, 401)
