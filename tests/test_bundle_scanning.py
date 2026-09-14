from unittest import TestCase
from xml.etree import ElementTree

import test_bundles as bundle_tests


class BundleScanningTest(TestCase):
    setUp=bundle_tests.BundleTest.setUp
    post=bundle_tests.BundleTest.post
    order=bundle_tests.BundleTest.order
    material=bundle_tests.BundleTest.material
    receipt=bundle_tests.BundleTest.receipt
    issue=bundle_tests.BundleTest.issue
    setup_stock=bundle_tests.BundleTest.setup_stock
    prepare=bundle_tests.BundleTest.prepare
    cut=bundle_tests.BundleTest.cut
    setup_run=bundle_tests.BundleTest.setup_run
    create_bundle=bundle_tests.BundleTest.create_bundle

    def test_lookup_accepts_qr_code_or_reference_for_every_role(self):
        _,run=self.setup_run();bundle=self.create_bundle(run,reference='BDL-Scan-001')
        self.assertEqual(bundle['scan_code'],'BEELOFT:BUNDLE:'+bundle['id'])
        for code in (bundle['scan_code'],bundle['scan_code'].upper(),' bdl-scan-001 '):
            found=self.client.get('/api/bundles/scan',params={'code':code}).json()
            self.assertEqual(found['id'],bundle['id'])
        for account in (self.operator,self.viewer):
            response=self.client.get('/api/bundles/scan',params={'code':bundle['scan_code']},
                headers={'X-API-Key':account['api_key']})
            self.assertEqual(response.status_code,200)
        self.post('/api/bundles/'+bundle['id']+'/reverse',{'reason':'Label fisik dibatalkan'})
        self.assertEqual(self.client.get('/api/bundles/scan',params={
            'code':bundle['scan_code']}).json()['status'],'corrected')
        self.assertEqual(self.client.get('/api/bundles/'+bundle['id']+'/label.svg').status_code,409)

    def test_unknown_invalid_and_unauthenticated_scan(self):
        for code in ('missing','BEELOFT:BUNDLE:missing','   '):
            response=self.client.get('/api/bundles/scan',params={'code':code})
            self.assertEqual(response.status_code,404)
        self.assertEqual(self.client.get('/api/bundles/scan').status_code,422)
        self.assertEqual(self.client.get('/api/bundles/scan',params={'code':'x'*201}).status_code,422)
        self.assertEqual(self.client.get('/api/bundles/scan',params={'code':'missing'},
            headers={'X-API-Key':'invalid'}).status_code,401)

    def test_label_is_safe_accessible_qr_svg(self):
        _,run=self.setup_run();bundle=self.create_bundle(run,reference='BDL-<SCAN>')
        for account in (self.admin,self.operator,self.viewer):
            response=self.client.get('/api/bundles/'+bundle['id']+'/label.svg',
                headers={'X-API-Key':account['api_key']})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.headers['content-type'],'image/svg+xml')
            self.assertEqual(response.headers['x-content-type-options'],'nosniff')
        svg=response.text
        root=ElementTree.fromstring(svg)
        namespace={'svg':'http://www.w3.org/2000/svg'}
        self.assertEqual(root.attrib['role'],'img')
        self.assertEqual(root.find('svg:title',namespace).text,'QR bundle BDL-<SCAN>')
        self.assertEqual(root.find('svg:desc',namespace).text,bundle['scan_code'])
        self.assertIsNotNone(root.find('svg:path',namespace))
        self.assertNotIn('<script',svg.casefold())
        self.assertEqual(self.client.get('/api/bundles/missing/label.svg').status_code,404)
