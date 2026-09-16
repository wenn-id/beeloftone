from datetime import datetime, timedelta, timezone
from unittest import TestCase

import test_production as production_tests


class JubelioMarketplacePerformanceTest(TestCase):
    """Marketplace business performance derived from the latest Jubelio order snapshot batch."""

    setUp = production_tests.ProductionTest.setUp
    post = production_tests.ProductionTest.post

    def map_product(self, product=None, external_id='item-42', external_sku='JUB-LUNA-M'):
        product = product or self.product
        return self.post(f"/api/products/{product['id']}/external-mappings/jubelio", {
            'expected_revision': 0, 'action': 'mapped', 'external_id': external_id,
            'external_sku': external_sku, 'reason': 'Mapping untuk performa marketplace'})

    def second_product(self):
        product = self.post('/api/products', {'sku': 'NOVA-RED-L', 'name': 'Nova Red',
                                              'size': 'L', 'color': 'Red'})
        self.map_product(product, external_id='item-77', external_sku='JUB-NOVA-L')
        return product

    def order(self, **changes):
        record = {'external_order_id': 'order-42', 'external_order_reference': 'JUB-ORDER-0042',
                  'marketplace': 'Shopee', 'status': 'completed', 'ordered_at': '2026-09-13T09:00:00+07:00',
                  'lines': [{'external_id': 'item-42', 'external_sku': 'JUB-LUNA-M', 'quantity': 2,
                             'gross_revenue': '240000'}]}
        record.update(changes)
        return record

    def line(self, external_id='item-42', external_sku='JUB-LUNA-M', quantity=2, gross_revenue='240000'):
        return {'external_id': external_id, 'external_sku': external_sku,
                'quantity': quantity, 'gross_revenue': gross_revenue}

    def body(self, orders, **changes):
        finished = datetime.now(timezone.utc).replace(microsecond=0)
        body = {'started_at': (finished - timedelta(minutes=2)).isoformat(),
                'finished_at': finished.isoformat(), 'snapshot_at': finished.isoformat(),
                'external_cursor': 'orders-page-1', 'reason': 'Snapshot order untuk performa marketplace',
                'orders': orders}
        body.update(changes)
        return body

    def returns_body(self, records, **changes):
        finished = datetime.now(timezone.utc).replace(microsecond=0)
        body = {'started_at': (finished - timedelta(minutes=2)).isoformat(),
                'finished_at': finished.isoformat(), 'snapshot_at': finished.isoformat(),
                'external_cursor': 'returns-page-1', 'reason': 'Snapshot retur untuk performa marketplace',
                'returns': records}
        body.update(changes)
        return body

    def refund(self, **changes):
        record = {'external_return_id': 'return-42', 'external_return_reference': 'JUB-RETURN-0042',
                  'external_order_id': 'order-42', 'external_order_reference': 'JUB-ORDER-0042',
                  'marketplace': 'Shopee', 'status': 'refunded', 'updated_at': '2026-09-13T11:00:00+07:00',
                  'refund_amount': '40000',
                  'lines': [{'external_id': 'item-42', 'external_sku': 'JUB-LUNA-M', 'quantity': 1}]}
        record.update(changes)
        return record

    def performance(self):
        return self.app.state.store.jubelio_marketplace_performance()

    def test_empty_data_reports_zeroes_without_dividing_by_zero(self):
        report = self.performance()
        self.assertEqual((report['snapshot_at'], report['return_snapshot_at'], report['period_start'],
                          report['period_end'], report['trend_start'], report['trend_end']),
                         (None, None, None, None, None, None))
        self.assertEqual((report['marketplaces'], report['products'], report['daily']), ([], [], []))
        self.assertEqual(report['summary']['average_order_value'], '0.00')
        self.assertEqual((report['summary']['gross_revenue'], report['summary']['net_revenue'],
                          report['summary']['refund_amount']), ('0.00', '0.00', '0.00'))
        self.assertEqual((report['summary']['orders'], report['summary']['completed_orders'],
                          report['summary']['units'], report['summary']['marketplaces']), (0, 0, 0, 0))

    def test_average_order_value_ignores_orders_that_never_completed(self):
        self.map_product()
        # Only the completed order contributes revenue, units, and the AOV denominator.
        self.post('/api/integrations/jubelio/order-snapshots', self.body([
            self.order(),
            self.order(external_order_id='pending-1', external_order_reference='PENDING-1',
                       status='pending', lines=[self.line(quantity=9, gross_revenue='900000')]),
            self.order(external_order_id='cancelled-1', external_order_reference='CANCELLED-1',
                       status='cancelled', lines=[self.line(quantity=4, gross_revenue='500000')]),
        ]))
        summary = self.performance()['summary']
        self.assertEqual((summary['orders'], summary['completed_orders']), (3, 1))
        self.assertEqual((summary['pending'], summary['cancelled'], summary['completed']), (1, 1, 1))
        self.assertEqual((summary['units'], summary['gross_revenue']), (2, '240000.00'))
        self.assertEqual(summary['average_order_value'], '240000.00')

    def test_average_order_value_is_zero_when_no_order_completed(self):
        self.map_product()
        self.post('/api/integrations/jubelio/order-snapshots', self.body([
            self.order(status='pending'),
        ]))
        summary = self.performance()['summary']
        self.assertEqual((summary['orders'], summary['completed_orders']), (1, 0))
        self.assertEqual((summary['gross_revenue'], summary['average_order_value']), ('0.00', '0.00'))
        self.assertEqual(self.performance()['daily'], [])

    def test_marketplace_names_group_case_insensitively(self):
        self.map_product()
        self.post('/api/integrations/jubelio/order-snapshots', self.body([
            self.order(marketplace='Shopee'),
            self.order(external_order_id='order-43', external_order_reference='JUB-ORDER-0043',
                       marketplace='shopee', lines=[self.line(gross_revenue='60000')]),
            self.order(external_order_id='order-44', external_order_reference='JUB-ORDER-0044',
                       marketplace='  SHOPEE  ', lines=[self.line(gross_revenue='100000')]),
            self.order(external_order_id='order-45', external_order_reference='JUB-ORDER-0045',
                       marketplace='Tokopedia', lines=[self.line(gross_revenue='50000')]),
        ]))
        report = self.performance()
        self.assertEqual([row['key'] for row in report['marketplaces']], ['shopee', 'tokopedia'])
        shopee = report['marketplaces'][0]
        # Three spellings collapse into one channel and the most common original label is reported.
        self.assertEqual((shopee['marketplace'], shopee['orders'], shopee['completed_orders']),
                         ('Shopee', 3, 3))
        self.assertEqual((shopee['units'], shopee['gross_revenue']), (6, '400000.00'))
        self.assertEqual(report['summary']['marketplaces'], 2)

    def test_channel_rows_expose_aov_contribution_and_status_counts(self):
        self.map_product()
        self.post('/api/integrations/jubelio/order-snapshots', self.body([
            self.order(lines=[self.line(gross_revenue='300000')]),
            self.order(external_order_id='order-43', external_order_reference='JUB-ORDER-0043',
                       lines=[self.line(gross_revenue='100000')]),
            self.order(external_order_id='order-44', external_order_reference='JUB-ORDER-0044',
                       marketplace='Tokopedia', status='processing',
                       lines=[self.line(gross_revenue='90000')]),
            self.order(external_order_id='order-45', external_order_reference='JUB-ORDER-0045',
                       marketplace='Tokopedia', lines=[self.line(gross_revenue='100000')]),
        ]))
        report = self.performance()
        shopee, tokopedia = report['marketplaces']
        self.assertEqual((shopee['marketplace'], shopee['gross_revenue'], shopee['average_order_value']),
                         ('Shopee', '400000.00', '200000.00'))
        self.assertEqual(shopee['contribution_percent'], '80.00')
        self.assertEqual((tokopedia['gross_revenue'], tokopedia['average_order_value'],
                          tokopedia['contribution_percent']), ('100000.00', '100000.00', '20.00'))
        self.assertEqual((tokopedia['orders'], tokopedia['completed'], tokopedia['processing'],
                          tokopedia['pending'], tokopedia['cancelled']), (2, 1, 1, 0, 0))
        # Channels are ordered by completed gross sales so the biggest contributor leads.
        self.assertGreater(float(shopee['gross_revenue']), float(tokopedia['gross_revenue']))

    def test_daily_series_groups_completed_orders_by_jakarta_order_date(self):
        self.map_product()
        self.post('/api/integrations/jubelio/order-snapshots', self.body([
            self.order(ordered_at='2026-09-13T09:00:00+07:00', lines=[self.line(gross_revenue='100000')]),
            self.order(external_order_id='order-43', external_order_reference='JUB-ORDER-0043',
                       ordered_at='2026-09-13T21:00:00+07:00', lines=[self.line(gross_revenue='50000')]),
            self.order(external_order_id='order-44', external_order_reference='JUB-ORDER-0044',
                       ordered_at='2026-09-15T08:00:00+07:00', lines=[self.line(gross_revenue='70000')]),
            # 2026-09-16T01:00+07:00 is still 2026-09-15 in UTC; Jakarta is the business day.
            self.order(external_order_id='order-45', external_order_reference='JUB-ORDER-0045',
                       ordered_at='2026-09-16T01:00:00+07:00', lines=[self.line(gross_revenue='30000')]),
            self.order(external_order_id='order-46', external_order_reference='JUB-ORDER-0046',
                       status='cancelled', ordered_at='2026-09-17T09:00:00+07:00',
                       lines=[self.line(gross_revenue='999000')]),
        ]))
        report = self.performance()
        self.assertEqual([(row['date'], row['orders'], row['gross_revenue']) for row in report['daily']], [
            ('2026-09-13', 2, '150000.00'),
            ('2026-09-15', 1, '70000.00'),
            ('2026-09-16', 1, '30000.00'),
        ])
        # period_* covers every accepted order in the batch, including the cancelled one...
        self.assertEqual((report['period_start'], report['period_end']), ('2026-09-13', '2026-09-17'))
        # ...while trend_* covers only the completed-sales series the chart actually plots.
        self.assertEqual((report['trend_start'], report['trend_end']), ('2026-09-13', '2026-09-16'))

    def test_top_products_aggregate_by_sku_and_sort_by_units(self):
        self.map_product()
        other = self.second_product()
        self.post('/api/integrations/jubelio/order-snapshots', self.body([
            self.order(lines=[self.line(quantity=2, gross_revenue='200000'),
                              self.line('item-77', 'JUB-NOVA-L', 5, '150000')]),
            self.order(external_order_id='order-43', external_order_reference='JUB-ORDER-0043',
                       lines=[self.line('item-77', 'JUB-NOVA-L', 3, '90000')]),
            self.order(external_order_id='order-44', external_order_reference='JUB-ORDER-0044',
                       status='cancelled', lines=[self.line(quantity=50, gross_revenue='900000')]),
        ]))
        products = self.performance()['products']
        self.assertEqual([(row['sku'], row['units'], row['orders'], row['gross_revenue']) for row in products], [
            ('NOVA-RED-L', 8, 2, '240000.00'),
            ('LUNA-BLUE-M', 2, 1, '200000.00'),
        ])
        self.assertEqual((products[0]['product_id'], products[0]['product_name']), (other['id'], 'Nova Red'))
        self.assertEqual((products[1]['color'], products[1]['size']), ('Blue', 'M'))

    def test_only_latest_batch_is_read_so_repeated_orders_never_double_count(self):
        self.map_product()
        first = self.body([self.order(lines=[self.line(gross_revenue='240000')])])
        self.post('/api/integrations/jubelio/order-snapshots', first, key='batch-one')
        self.assertEqual(self.performance()['summary']['gross_revenue'], '240000.00')
        # The connector re-sends the same order in a later batch and adds one more.
        self.post('/api/integrations/jubelio/order-snapshots', self.body([
            self.order(lines=[self.line(gross_revenue='240000')]),
            self.order(external_order_id='order-99', external_order_reference='JUB-ORDER-0099',
                       lines=[self.line(gross_revenue='60000')]),
        ], external_cursor='orders-page-2'), key='batch-two')
        report = self.performance()
        self.assertEqual((report['summary']['orders'], report['summary']['completed_orders']), (2, 2))
        self.assertEqual(report['summary']['gross_revenue'], '300000.00')
        self.assertEqual(report['summary']['units'], 4)
        # A third batch that drops the recurring order shrinks the figures instead of accumulating.
        self.post('/api/integrations/jubelio/order-snapshots', self.body([
            self.order(external_order_id='order-99', external_order_reference='JUB-ORDER-0099',
                       lines=[self.line(gross_revenue='60000')]),
        ], external_cursor='orders-page-3'), key='batch-three')
        self.assertEqual(self.performance()['summary']['gross_revenue'], '60000.00')

    def test_net_sales_only_subtracts_refunds_matched_to_orders_in_this_batch(self):
        self.map_product()
        self.post('/api/integrations/jubelio/order-snapshots', self.body([
            self.order(lines=[self.line(gross_revenue='240000')]),
            self.order(external_order_id='order-43', external_order_reference='JUB-ORDER-0043',
                       marketplace='Tokopedia', lines=[self.line(gross_revenue='100000')]),
        ]))
        self.post('/api/integrations/jubelio/return-snapshots', self.returns_body([
            self.refund(refund_amount='40000'),
            # Refund for an order that is not in the current order batch: reported, never netted off.
            self.refund(external_return_id='return-77', external_return_reference='JUB-RETURN-0077',
                        external_order_id='order-gone', external_order_reference='JUB-ORDER-GONE',
                        refund_amount='500000'),
            # A received-but-not-refunded return carries no money and must not change net sales.
            self.refund(external_return_id='return-88', external_return_reference='JUB-RETURN-0088',
                        external_order_id='order-43', external_order_reference='JUB-ORDER-0043',
                        status='received', refund_amount='0'),
        ]))
        report = self.performance()
        summary = report['summary']
        self.assertEqual((summary['gross_revenue'], summary['refund_amount'], summary['net_revenue']),
                         ('340000.00', '40000.00', '300000.00'))
        self.assertEqual((summary['matched_refunds'], summary['unmatched_refunds'],
                          summary['unmatched_refund_amount']), (1, 1, '500000.00'))
        shopee = next(row for row in report['marketplaces'] if row['key'] == 'shopee')
        tokopedia = next(row for row in report['marketplaces'] if row['key'] == 'tokopedia')
        self.assertEqual((shopee['refund_amount'], shopee['net_revenue']), ('40000.00', '200000.00'))
        self.assertEqual((tokopedia['refund_amount'], tokopedia['net_revenue']), ('0.00', '100000.00'))
        self.assertIsNotNone(report['return_snapshot_at'])

    def test_refunds_against_uncompleted_orders_are_not_netted_off(self):
        self.map_product()
        self.post('/api/integrations/jubelio/order-snapshots', self.body([
            self.order(status='cancelled', lines=[self.line(gross_revenue='240000')]),
        ]))
        self.post('/api/integrations/jubelio/return-snapshots',
                  self.returns_body([self.refund(refund_amount='40000')]))
        summary = self.performance()['summary']
        # Gross counts completed orders only, so a refund on a cancelled order stays unmatched.
        self.assertEqual((summary['gross_revenue'], summary['net_revenue']), ('0.00', '0.00'))
        self.assertEqual((summary['matched_refunds'], summary['unmatched_refunds'],
                          summary['unmatched_refund_amount']), (0, 1, '40000.00'))

    def test_command_center_exposes_marketplace_block_and_keeps_existing_sales_fields(self):
        from beeloft.command_center import build_command_center
        self.map_product()
        self.post('/api/integrations/jubelio/order-snapshots', self.body([
            self.order(lines=[self.line(gross_revenue='240000')]),
        ]))
        sales = build_command_center(self.app.state.store)['sales']
        for field in ('snapshot_at', 'accepted_orders', 'quarantined_orders', 'units', 'gross_revenue',
                      'pending', 'processing', 'completed', 'cancelled'):
            self.assertIn(field, sales)
        self.assertEqual((sales['accepted_orders'], sales['units'], sales['gross_revenue']),
                         (1, 2, '240000.00'))
        marketplace = sales['marketplace']
        self.assertEqual(sorted(marketplace), ['daily', 'marketplaces', 'period_end', 'period_start',
                                               'products', 'return_snapshot_at', 'snapshot_at', 'summary',
                                               'trend_end', 'trend_start'])
        self.assertEqual(marketplace['summary']['average_order_value'], '240000.00')
        self.assertEqual(marketplace['marketplaces'][0]['marketplace'], 'Shopee')
        self.assertEqual(marketplace['products'][0]['sku'], 'LUNA-BLUE-M')
        self.assertEqual(marketplace['daily'][0]['date'], '2026-09-13')
        self.assertEqual((marketplace['period_start'], marketplace['period_end']),
                         ('2026-09-13', '2026-09-13'))


    def mixed_case_channel_batch(self):
        """One snapshot where two real channels each arrive under three different spellings."""
        self.map_product()
        self.post('/api/integrations/jubelio/order-snapshots', self.body([
            self.order(marketplace='Shopee', lines=[self.line(quantity=2, gross_revenue='200000')]),
            self.order(external_order_id='order-43', external_order_reference='JUB-ORDER-0043',
                       marketplace='shopee', lines=[self.line(quantity=1, gross_revenue='100000')]),
            self.order(external_order_id='order-44', external_order_reference='JUB-ORDER-0044',
                       marketplace='  SHOPEE  ', lines=[self.line(quantity=3, gross_revenue='300000')]),
            self.order(external_order_id='order-45', external_order_reference='JUB-ORDER-0045',
                       marketplace='Tokopedia', lines=[self.line(quantity=4, gross_revenue='400000')]),
            self.order(external_order_id='order-46', external_order_reference='JUB-ORDER-0046',
                       marketplace='TOKOPEDIA', status='cancelled',
                       lines=[self.line(quantity=9, gross_revenue='900000')]),
            self.order(external_order_id='order-47', external_order_reference='JUB-ORDER-0047',
                       marketplace='tokopedia', lines=[self.line(quantity=1, gross_revenue='50000')]),
        ]))

    def test_legacy_order_summary_groups_channels_case_insensitively(self):
        self.mixed_case_channel_batch()
        report = self.client.get('/api/integrations/jubelio/order-summary').json()
        # Three spellings each collapse to one channel with the canonical mixed-case label.
        self.assertEqual(report['marketplaces'], [
            {'marketplace': 'Shopee', 'orders': 3, 'units': 6, 'gross_revenue': '600000.00'},
            {'marketplace': 'Tokopedia', 'orders': 3, 'units': 5, 'gross_revenue': '450000.00'},
        ])
        # The response shape is unchanged: exactly the four original keys, still sorted by channel name.
        self.assertEqual([sorted(row) for row in report['marketplaces']],
                         [['gross_revenue', 'marketplace', 'orders', 'units']] * 2)
        # Batch-wide totals are untouched by the grouping change.
        self.assertEqual((report['summary']['accepted_orders'], report['summary']['units'],
                          report['summary']['gross_revenue']), (6, 11, '1050000.00'))

    def test_both_summary_paths_produce_the_same_channel_grouping(self):
        self.mixed_case_channel_batch()
        legacy = self.app.state.store.jubelio_order_summary()['marketplaces']
        modern = self.performance()['marketplaces']
        shape = lambda rows: {row['marketplace']: (row['orders'], row['units'], row['gross_revenue'])
                              for row in rows}
        self.assertEqual(shape(legacy), shape(modern))
        self.assertEqual(len(legacy), len(modern))
        # Both resolve the same canonical labels, and neither leaks a raw spelling variant.
        self.assertEqual({row['marketplace'] for row in legacy}, {'Shopee', 'Tokopedia'})
        self.assertEqual({row['marketplace'] for row in modern}, {'Shopee', 'Tokopedia'})
        # Ordering intentionally differs: legacy is alphabetical, the business view leads with revenue.
        self.assertEqual([row['marketplace'] for row in legacy], ['Shopee', 'Tokopedia'])
        self.assertEqual([row['marketplace'] for row in modern], ['Shopee', 'Tokopedia'])
        self.assertEqual([row['key'] for row in modern], ['shopee', 'tokopedia'])

    def test_both_summary_paths_agree_when_a_channel_has_no_completed_order(self):
        self.map_product()
        self.post('/api/integrations/jubelio/order-snapshots', self.body([
            self.order(marketplace='Shopee', lines=[self.line(quantity=2, gross_revenue='200000')]),
            self.order(external_order_id='order-43', external_order_reference='JUB-ORDER-0043',
                       marketplace='LAZADA', status='pending',
                       lines=[self.line(quantity=5, gross_revenue='500000')]),
            self.order(external_order_id='order-44', external_order_reference='JUB-ORDER-0044',
                       marketplace='lazada', status='cancelled',
                       lines=[self.line(quantity=2, gross_revenue='200000')]),
        ]))
        legacy = self.app.state.store.jubelio_order_summary()['marketplaces']
        modern = self.performance()['marketplaces']
        shape = lambda rows: {row['marketplace']: (row['orders'], row['units'], row['gross_revenue'])
                              for row in rows}
        self.assertEqual(shape(legacy), shape(modern))
        # A channel with orders but nothing completed still appears, counted but with no revenue.
        self.assertEqual(shape(legacy)['LAZADA'], (2, 0, '0.00'))
        # All-caps is the only spelling seen for that channel, so it is reported as-is.
        self.assertEqual({row['marketplace'] for row in legacy}, {'Shopee', 'LAZADA'})
