from unittest import TestCase
from xml.etree import ElementTree

import test_materials as material_tests


class MaterialBatchScanningTest(TestCase):
    setUp=material_tests.MaterialsTest.setUp
    post=material_tests.MaterialsTest.post
    material=material_tests.MaterialsTest.material
    receipt=material_tests.MaterialsTest.receipt

    def test_lookup_accepts_qr_code_or_reference_for_every_role(self):
        batch=self.post('/api/material-batches',self.receipt(self.material(),reference='Batch-Scan-001'))
        self.assertEqual(batch['scan_code'],'BEELOFT:MATERIAL-BATCH:'+batch['id'])
        self.assertEqual(batch['received_quantity'],'10.125')
        self.assertEqual(batch['status'],'active')
        for code in (batch['scan_code'],batch['scan_code'].upper(),' batch-scan-001 '):
            found=self.client.get('/api/material-batches/scan',params={'code':code}).json()
            self.assertEqual(found['id'],batch['id'])
        for account in (self.operator,self.viewer):
            response=self.client.get('/api/material-batches/scan',params={'code':batch['scan_code']},
                headers={'X-API-Key':account['api_key']})
            self.assertEqual(response.status_code,200)
        self.post('/api/material-movements/'+batch['receipt_id']+'/reverse',
            {'reason':'Penerimaan batch dibatalkan'})
        self.assertEqual(self.client.get('/api/material-batches/scan',params={
            'code':batch['scan_code']}).json()['status'],'corrected')
        self.assertEqual(self.client.get('/api/material-batches/'+batch['id']+'/label.svg').status_code,409)

    def test_unknown_invalid_and_unauthenticated_scan(self):
        for code in ('missing','BEELOFT:MATERIAL-BATCH:missing','   '):
            response=self.client.get('/api/material-batches/scan',params={'code':code})
            self.assertEqual(response.status_code,404)
        self.assertEqual(self.client.get('/api/material-batches/scan').status_code,422)
        self.assertEqual(self.client.get('/api/material-batches/scan',params={'code':'x'*201}).status_code,422)
        self.assertEqual(self.client.get('/api/material-batches/scan',params={'code':'missing'},
            headers={'X-API-Key':'invalid'}).status_code,401)

    def test_label_is_safe_accessible_qr_svg(self):
        material=self.post('/api/materials',{'code':'KAIN-SCAN','name':'Katun <biru> & putih','unit':'m'})
        batch=self.post('/api/material-batches',self.receipt(material,reference='BATCH-<SCAN>'))
        for account in (self.admin,self.operator,self.viewer):
            response=self.client.get('/api/material-batches/'+batch['id']+'/label.svg',
                headers={'X-API-Key':account['api_key']})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.headers['content-type'],'image/svg+xml')
            self.assertEqual(response.headers['x-content-type-options'],'nosniff')
        svg=response.text
        root=ElementTree.fromstring(svg)
        namespace={'svg':'http://www.w3.org/2000/svg'}
        self.assertEqual(root.attrib['role'],'img')
        self.assertEqual(root.find('svg:title',namespace).text,'QR batch bahan BATCH-<SCAN>')
        self.assertEqual(root.find('svg:desc',namespace).text,batch['scan_code'])
        self.assertIsNotNone(root.find('svg:path',namespace))
        self.assertNotIn('<script',svg.casefold())
        self.assertEqual(self.client.get('/api/material-batches/missing/label.svg').status_code,404)
