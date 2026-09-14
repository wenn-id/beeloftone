import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from beeloft.store import Store
import test_production as production_tests


class IntegrationSyncTest(TestCase):
    setUp = production_tests.ProductionTest.setUp
    post = production_tests.ProductionTest.post

    def body(self, system='jubelio', scope='orders', status='succeeded', **changes):
        finished=datetime.now(timezone.utc).replace(microsecond=0)
        body={'system':system,'scope':scope,'status':status,
              'started_at':(finished-timedelta(minutes=2)).isoformat(),
              'finished_at':finished.isoformat(),'records_read':12,'records_written':10,
              'external_cursor':'cursor-12','error':'API vendor timeout' if status=='failed' else '',
              'reason':'Sinkronisasi incremental terjadwal'}
        body.update(changes)
        return body

    def test_contract_exposes_source_of_truth_without_claiming_a_sync(self):
        result=self.client.get('/api/integrations').json()
        self.assertEqual(result['stale_after_minutes'],1440)
        self.assertEqual([row['system'] for row in result['systems']],['jubelio','mekari'])
        jubelio=result['systems'][0]
        self.assertEqual((jubelio['health'],jubelio['attention_count']),('never_synced',4))
        scopes={row['scope']:row for row in jubelio['scopes']}
        self.assertEqual((scopes['orders']['source_of_truth'],scopes['orders']['direction'],
                          scopes['orders']['mode'],scopes['orders']['latest_run']),
                         ('Jubelio','inbound','read_only',None))
        mekari=result['systems'][1]
        self.assertEqual({row['scope'] for row in mekari['scopes']},
                         {'finance_summary','payables','receivables','payroll'})
        self.assertEqual(self.client.get('/api/integrations',headers={'X-API-Key':'bad'}).status_code,401)

    def test_runs_are_idempotent_filterable_and_drive_health(self):
        payload=self.body()
        run=self.post('/api/integration-sync-runs',payload,key='jubelio-orders-sync')
        self.assertEqual(run,self.post('/api/integration-sync-runs',payload,key='jubelio-orders-sync'))
        failed=self.post('/api/integration-sync-runs',self.body(scope='finished_goods',status='failed'),
                         key='jubelio-stock-failure')
        old=(datetime.now(timezone.utc)-timedelta(days=2)).replace(microsecond=0)
        stale=self.post('/api/integration-sync-runs',self.body(system='mekari',scope='finance_summary',
            started_at=(old-timedelta(minutes=3)).isoformat(),finished_at=old.isoformat()),key='mekari-old')
        systems={row['system']:row for row in self.client.get('/api/integrations').json()['systems']}
        jubelio={row['scope']:row for row in systems['jubelio']['scopes']}
        self.assertEqual((systems['jubelio']['health'],jubelio['orders']['health'],
                          jubelio['finished_goods']['health']),('failed','healthy','failed'))
        mekari={row['scope']:row for row in systems['mekari']['scopes']}
        self.assertEqual(mekari['finance_summary']['health'],'stale')
        filtered=self.client.get('/api/integration-sync-runs?system=jubelio&status=failed').json()
        self.assertEqual([row['id'] for row in filtered],[failed['id']])
        page=self.client.get('/api/integration-sync-runs?limit=1').json()
        older=self.client.get('/api/integration-sync-runs?before='+str(page[0]['sequence'])).json()
        self.assertEqual((page[0]['id'],older[0]['id']),(stale['id'],failed['id']))
        detail=self.client.get('/api/integration-sync-runs/'+run['id']).json()
        self.assertEqual((detail['records_read'],detail['records_written'],detail['actor_id']),(12,10,self.admin['id']))
        self.post('/api/integration-sync-runs',self.body(),api_key=self.operator['api_key'],status=403)
        self.post('/api/integration-sync-runs',self.body(),api_key=self.viewer['api_key'],status=403)

    def test_validation_rejects_false_or_inconsistent_sync_records(self):
        invalid=({'system':'mekari'},{'scope':'payables'},
                 {'started_at':'2026-09-13T10:00:00'},{'finished_at':'2026-09-13T10:00:00'},
                 {'started_at':'2026-09-13T11:00:00+00:00','finished_at':'2026-09-13T10:00:00+00:00'},
                 {'status':'failed','error':''},{'status':'succeeded','error':'Tidak boleh ada'},
                 {'records_read':True},{'records_written':-1},{'unexpected':'value'})
        for changes in invalid:
            self.post('/api/integration-sync-runs',self.body(**changes),status=422)
        self.assertEqual(self.client.get('/api/integration-sync-runs?system=bad').status_code,422)
        self.assertEqual(self.client.get('/api/integration-sync-runs?status=bad').status_code,422)
        self.assertEqual(self.client.get('/api/integration-sync-runs?scope=unknown').json(),[])
        self.assertEqual(self.client.get('/api/integration-sync-runs/missing').status_code,404)

    def test_rollback_immutability_backup_and_migration_from_32(self):
        with self.app.state.store.transaction(write=True) as db:
            db.execute("""CREATE TRIGGER fail_integration_sync BEFORE INSERT ON requests
                WHEN NEW.key='fail-integration-sync' BEGIN SELECT RAISE(ABORT,'fail'); END""")
        self.post('/api/integration-sync-runs',self.body(),key='fail-integration-sync',status=409)
        self.assertEqual(self.client.get('/api/integration-sync-runs').json(),[])
        with self.app.state.store.transaction(write=True) as db:
            db.execute('DROP TRIGGER fail_integration_sync')
        run=self.post('/api/integration-sync-runs',self.body(),key='saved-integration-sync')
        with closing(sqlite3.connect(self.path)) as db:
            for sql in ('UPDATE integration_sync_runs SET created_at=created_at',
                        'DELETE FROM integration_sync_runs'):
                with self.assertRaises(sqlite3.IntegrityError): db.execute(sql)
        backup=self.path.with_name('integration-sync-backup.sqlite3')
        self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).integration_sync_run(run['id'])['external_cursor'],'cursor-12')
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP TABLE integration_sync_runs')
            db.execute('PRAGMA user_version=32');db.commit()
        Store(self.path);Store(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],45)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM integration_sync_runs').fetchone()[0],0)
