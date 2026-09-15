from datetime import datetime, timedelta, timezone
from unittest import TestCase

import test_production


class PayrollPaymentReconciliationTest(TestCase):
    setUp=test_production.ProductionTest.setUp
    post=test_production.ProductionTest.post

    def period(self,external_id,status='reviewing',**changes):
        row={'external_payroll_id':external_id,'period_start':'2026-09-01','period_end':'2026-09-30',
             'status':status,'currency':'IDR','employee_count':42,'gross_pay':'1000000.00',
             'employee_deductions':'100000.00','employer_contributions':'150000.00',
             'payment_date':'2026-09-30' if status=='paid' else None,
             'updated_at':'2026-09-15T04:00:00+00:00'}
        row.update(changes);return row

    def snapshot(self,periods):
        finished=datetime.now(timezone.utc).replace(microsecond=0)
        return self.post('/api/integrations/mekari/payroll-snapshots',{
            'started_at':(finished-timedelta(seconds=5)).isoformat(),
            'finished_at':finished.isoformat(),'snapshot_at':finished.isoformat(),
            'external_cursor':'payroll-payment','reason':'Rekonsiliasi pembayaran payroll',
            'periods':periods})

    def approve(self,period):
        request=self.post('/api/integrations/mekari/payroll-periods/'+period['id']+'/approval-requests',
            {'reason':'Payroll siap dibayar'},api_key=self.operator['api_key'])
        return self.post('/api/payroll-approval-requests/'+request['id']+'/decisions',
            {'status':'approved','expected_revision':request['revision'],
             'reason':'Nominal payroll disetujui'})

    def report(self,query=''):
        response=self.client.get('/api/payroll-payment-reconciliation'+query)
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def test_tracks_approved_batch_until_mekari_reports_payment(self):
        source=self.snapshot([self.period('payroll-paid')])['periods'][0]
        approved=self.approve(source)
        waiting=self.report()
        self.assertEqual(waiting['summary'],{'approved_batches':1,'awaiting_payment':1,
            'paid':0,'exceptions':0,'expected_net_pay':'900000.00','paid_net_pay':'0.00'})
        self.assertEqual((waiting['items'][0]['approval_request_id'],waiting['items'][0]['payment_status'],
                          waiting['items'][0]['source_status']),
                         (approved['id'],'awaiting_payment','reviewing'))

        self.snapshot([self.period('payroll-paid','approved',
            updated_at='2026-09-16T04:00:00+00:00')])
        self.assertEqual(self.report('?status=awaiting_payment')['items'][0]['source_status'],'approved')
        self.snapshot([self.period('payroll-paid','paid',
            updated_at='2026-09-30T04:00:00+00:00')])
        paid=self.report('?status=paid')
        self.assertEqual((paid['items'][0]['payment_status'],paid['items'][0]['payment_date'],
                          paid['summary']['paid_net_pay']),('paid','2026-09-30','900000.00'))
        self.assertEqual(self.report('?status=exception')['items'],[])

    def test_flags_missing_changed_and_cancelled_sources(self):
        original=self.snapshot([self.period('payroll-changed'),self.period('payroll-missing',
            period_start='2026-08-01',period_end='2026-08-31'),self.period('payroll-cancelled',
            period_start='2026-07-01',period_end='2026-07-31')])['periods']
        for source in original:self.approve(source)
        self.snapshot([self.period('payroll-changed',gross_pay='1200000.00'),
            self.period('payroll-cancelled','cancelled',period_start='2026-07-01',period_end='2026-07-31')])
        report=self.report('?status=exception')
        reasons={item['external_payroll_id']:item['exception_reason'] for item in report['items']}
        self.assertEqual(reasons,{'payroll-changed':'financial_mismatch',
            'payroll-missing':'source_missing','payroll-cancelled':'source_cancelled'})
        changed=next(item for item in report['items'] if item['external_payroll_id']=='payroll-changed')
        self.assertEqual(changed['changed_fields'],['gross_pay'])
        self.assertEqual(report['summary']['exceptions'],3)

    def test_latest_nonapproved_request_supersedes_old_approval_and_filters(self):
        source=self.snapshot([self.period('payroll-search-a'),self.period('payroll-search-b',
            period_start='2026-08-01',period_end='2026-08-31')])['periods']
        for period in source:self.approve(period)
        report=self.report('?q=SEARCH&limit=1&offset=1')
        self.assertEqual((report['total'],len(report['items'])),(2,1))
        latest=self.snapshot([self.period('payroll-search-a'),self.period('payroll-search-b',
            period_start='2026-08-01',period_end='2026-08-31')])['periods'][0]
        request=self.post('/api/integrations/mekari/payroll-periods/'+latest['id']+'/approval-requests',
            {'reason':'Pengajuan terbaru'},api_key=self.operator['api_key'])
        self.post('/api/payroll-approval-requests/'+request['id']+'/decisions',
            {'status':'rejected','expected_revision':request['revision'],'reason':'Tidak dilanjutkan'})
        self.assertEqual(self.report('?q=payroll-search-a')['items'],[])
        viewer=self.client.get('/api/payroll-payment-reconciliation',
            headers={'X-API-Key':self.viewer['api_key']})
        self.assertEqual(viewer.status_code,200)
        self.assertEqual(self.client.get('/api/payroll-payment-reconciliation?status=bad').status_code,422)
        self.assertEqual(self.client.get('/api/payroll-payment-reconciliation?q='+'x'*161).status_code,422)
