from unittest import TestCase
import test_production


class BoardFilterTest(TestCase):
    setUp = test_production.ProductionTest.setUp
    post = test_production.ProductionTest.post
    order = test_production.ProductionTest.order
    move = test_production.ProductionTest.move

    def test_combined_filters_positive_balances_and_global_summary(self):
        first = self.order(reference='FILTER-A')
        second = self.order(reference='FILTER-B',owner_id=self.admin['id'])
        self.move(first['lines'][0]['id'],'planned','cutting',30)
        self.move(second['lines'][0]['id'],'planned','cutting',20)
        global_board = self.client.get('/api/production-board').json()
        filtered = self.client.get('/api/production-board',params={'owner_id':self.operator['id'],'stage':'cutting','q':'FILTER','status':'active'}).json()
        self.assertEqual([o['id'] for o in filtered['orders']],[first['id']])
        self.assertEqual(filtered['summary'],global_board['summary'])
        self.assertEqual(filtered['owners'],global_board['owners'])
        self.assertEqual(self.client.get('/api/production-board?stage=qc').json()['total'],0)
        self.move(first['lines'][0]['id'],'cutting','sewing',30)
        self.assertEqual(self.client.get('/api/production-board',params={'stage':'cutting','owner_id':self.operator['id']}).json()['total'],0)
        self.assertEqual(self.client.get('/api/production-board?stage=sewing').json()['total'],1)

    def test_inactive_pic_still_filterable_and_reassignment_updates_options(self):
        order = self.order()
        self.app.state.store.disable_user(self.operator['id'])
        board = self.client.get('/api/production-board',params={'owner_id':self.operator['id']}).json()
        self.assertEqual(board['total'],1)
        self.assertEqual(board['owners'],[{'id':self.operator['id'],'name':self.operator['name'],'active':0}])
        self.post('/api/orders/'+order['id']+'/changes',{'owner_id':self.admin['id'],'due_date':order['due_date'],'reason':'Ganti PIC','expected_revision':order['revision']})
        board = self.client.get('/api/production-board',params={'owner_id':self.operator['id']}).json()
        self.assertEqual(board['total'],0)
        self.assertEqual([u['id'] for u in board['owners']],[self.admin['id']])

    def test_filtered_pagination_validation_and_access(self):
        orders = [self.order(reference=f'PAGING-{i}') for i in range(3)]
        query={'stage':'planned','owner_id':self.operator['id'],'limit':1}
        pages=[self.client.get('/api/production-board',params=query|{'offset':i}).json() for i in range(3)]
        self.assertTrue(all(p['total']==3 for p in pages))
        self.assertEqual({p['orders'][0]['id'] for p in pages},{o['id'] for o in orders})
        self.assertEqual(self.client.get('/api/production-board?stage=invalid').status_code,422)
        self.assertEqual(self.client.get('/api/production-board?owner_id=missing').json()['total'],0)
        for account in [self.admin,self.operator,self.viewer]:
            self.assertEqual(self.client.get('/api/production-board',params=query,headers={'X-API-Key':account['api_key']}).status_code,200)
        self.assertEqual(self.client.get('/api/production-board',params=query,headers={'X-API-Key':'bad'}).status_code,401)
