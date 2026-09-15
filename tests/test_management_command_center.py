from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import patch

import test_production_quality_insights as quality_tests
import test_production_capacity as capacity_tests


class ManagementCommandCenterTest(TestCase):
    setUp = quality_tests.ProductionQualityInsightsTest.setUp
    post = quality_tests.ProductionQualityInsightsTest.post
    order = quality_tests.ProductionQualityInsightsTest.order
    material = quality_tests.ProductionQualityInsightsTest.material
    receipt = quality_tests.ProductionQualityInsightsTest.receipt
    issue = quality_tests.ProductionQualityInsightsTest.issue
    setup_stock = quality_tests.ProductionQualityInsightsTest.setup_stock
    prepare = quality_tests.ProductionQualityInsightsTest.prepare
    cut = quality_tests.ProductionQualityInsightsTest.cut
    create_bundle = quality_tests.ProductionQualityInsightsTest.create_bundle
    setup_bundle = quality_tests.ProductionQualityInsightsTest.setup_bundle
    setup_quality = quality_tests.ProductionQualityInsightsTest.setup_quality
    move = capacity_tests.ProductionCapacityTest.move
    center = capacity_tests.ProductionCapacityTest.center
    standard = capacity_tests.ProductionCapacityTest.standard

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
        self.assertEqual((report['quality']['inspected_quantity'],
                          report['quality']['first_pass_yield_percent'],
                          report['quality']['attention_groups']), (0, '0.00', 0))
        self.assertEqual((report['capacity']['work_centers'],
                          report['capacity']['attention_work_centers'],
                          report['capacity']['coverage_gaps']), (0, 0, 0))
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

    def test_vendor_quality_alert_uses_active_final_qc_and_opens_analysis(self):
        self.setup_quality()
        with patch('beeloft.command_center.datetime') as clock:
            clock.now.return_value = datetime(2026, 10, 16, 5, tzinfo=timezone.utc)
            report = self.client.get('/api/command-center').json()
        self.assertEqual(report['quality'], {
            'as_of': '2026-10-16', 'period_start': '2026-09-17',
            'inspected_quantity': 10, 'first_pass_yield_percent': '70.00',
            'nonconforming_rate_percent': '30.00', 'rework_rate_percent': '20.00',
            'reject_rate_percent': '10.00', 'groups': 2, 'attention_groups': 1,
        })
        alert = next(row for row in report['attention'] if row['id'] == 'production-quality')
        self.assertEqual((alert['priority'], alert['kind'], alert['action'], alert['action_label']),
                         ('warning', 'quality', 'production_quality', 'Buka analisis kualitas'))
        self.assertEqual(alert['title'], 'Kualitas Vendor <B> (vendor makloon) perlu perhatian')
        self.assertEqual(alert['detail'],
                         'Rework + reject 60.00% dari 5 pcs; naik 60.00 poin dari periode sebelumnya.')

    def test_capacity_risk_and_coverage_alerts_use_fourteen_day_plan(self):
        with patch('beeloft.store.now', return_value='2026-10-01T02:00:00+00:00'):
            self.order(30, reference='CMD-CAPACITY', title='Target kapasitas',
                       due_date='2026-10-09')

        def command_center():
            with patch('beeloft.command_center.datetime') as clock:
                clock.now.return_value = datetime(2026, 10, 5, 5, tzinfo=timezone.utc)
                return self.client.get('/api/command-center').json()

        missing = command_center()
        self.assertFalse(missing['capacity']['capacity_complete'])
        self.assertEqual((missing['capacity']['coverage_gaps'],
                          missing['capacity']['missing_standard_quantity']), (4, 120))
        coverage = next(row for row in missing['attention']
                        if row['id'] == 'production-capacity-coverage')
        self.assertEqual((coverage['priority'], coverage['action'], coverage['action_label']),
                         ('warning', 'production_capacity', 'Lengkapi standar kapasitas'))

        centers = {stage: self.center('CMD-'+stage.upper(), stage,
                    10 if stage == 'sewing' else 480)
                   for stage in ('cutting', 'sewing', 'finishing', 'qc')}
        for stage, minutes in {'cutting': '1', 'sewing': '10',
                               'finishing': '1', 'qc': '1'}.items():
            self.standard(stage, centers[stage], minutes)
        report = command_center()
        self.assertEqual(report['capacity'], {
            'as_of': '2026-10-05', 'horizon_end': '2026-10-18',
            'capacity_complete': True, 'required_minutes': '390.000',
            'available_minutes': 14500, 'work_centers': 4,
            'attention_work_centers': 1, 'overloaded_work_centers': 1,
            'deadline_risk_work_centers': 0, 'near_capacity_work_centers': 0,
            'at_risk_orders': 1, 'coverage_gaps': 0, 'missing_standard_quantity': 0,
        })
        alert = next(row for row in report['attention']
                     if row['id'] == 'production-capacity-risk')
        self.assertEqual((alert['priority'], alert['kind'], alert['action'], alert['action_label']),
                         ('critical', 'capacity', 'production_capacity', 'Buka rencana kapasitas'))
        self.assertEqual(alert['detail'],
                         '1 work center overload dan 0 berisiko deadline; '
                         '1 order tidak cukup kapasitas sebelum target.')
        self.assertNotIn('production-capacity-coverage',
                         {row['id'] for row in report['attention']})

    def test_all_active_roles_can_read_but_anonymous_cannot(self):
        for account in (self.admin, self.operator, self.viewer):
            response = self.client.get('/api/command-center',
                                       headers={'X-API-Key': account['api_key']})
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/api/command-center', headers={'X-API-Key': 'invalid'}).status_code, 401)
