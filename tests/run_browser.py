"""Run browser acceptance checks against a disposable demo server/database."""
import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from beeloft.models import MovementCreate, OrderCreate
from beeloft.store import Store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--node', default='node')
    parser.add_argument('--playwright-module', default='playwright')
    parser.add_argument('--channel', default='msedge')
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='beeloft-browser-') as temporary:
        work = Path(temporary)
        database = work / 'demo.sqlite3'
        result = subprocess.run([sys.executable, '-m', 'beeloft', '--db', str(database), 'demo'],
                                cwd=project, capture_output=True, text=True, check=True)
        credentials = json.loads(result.stdout)
        (work / 'credentials.json').write_text(json.dumps(credentials), encoding='utf-8')
        store = Store(database)
        actor = store.authenticate(credentials['users'][0]['api_key'])
        product = store.products()[0]
        for ref, qty, days in [('DEMO-PROD-002', 300, -2), ('DEMO-PROD-003', 200, 12)]:
            order = store.create_order(OrderCreate(reference=ref, title='CONTOH - ' + ref,
                owner_id=credentials['users'][1]['id'], due_date=date.today()+timedelta(days=days),
                lines=[{'product_id':product['id'], 'quantity':qty}]).model_dump(mode='json'), actor, ref)
            if days < 0:
                store.move(MovementCreate(line_id=order['lines'][0]['id'], from_stage='planned',
                    to_stage='cutting', quantity=200).model_dump(), actor, ref+'-move')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        base = f'http://127.0.0.1:{port}'
        with (work / 'server.log').open('w') as log:
            server = subprocess.Popen([sys.executable, '-m', 'beeloft', '--db', str(database),
                'serve', '--port', str(port)], cwd=project, stdout=log, stderr=log)
            try:
                for _ in range(100):
                    if server.poll() is not None:
                        raise RuntimeError('Test server exited during startup')
                    try:
                        with urllib.request.urlopen(base + '/health', timeout=1):
                            break
                    except urllib.error.URLError:
                        time.sleep(.1)
                else:
                    raise RuntimeError('Test server startup timed out')
                env = os.environ | {'BEELOFT_QA_BASE':base, 'BEELOFT_QA_WORK':str(work),
                    'BEELOFT_QA_CREDENTIALS':str(work / 'credentials.json'),
                    'BEELOFT_PLAYWRIGHT_MODULE':args.playwright_module, 'BEELOFT_BROWSER_CHANNEL':args.channel}
                subprocess.run([args.node, 'tests/browser_smoke.cjs'], cwd=project, env=env, check=True)
            finally:
                server.terminate()
                server.wait(timeout=10)


if __name__ == '__main__':
    main()
