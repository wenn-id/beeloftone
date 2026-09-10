import csv
import io
from datetime import datetime, timedelta, timezone

KINDS = {'movement':'Perpindahan barang', 'reversal':'Koreksi perpindahan', 'issue_opened':'Kendala dicatat',
         'issue_resolved':'Kendala selesai', 'order_created':'Order dibuat', 'order_changed':'Tenggat / PIC diubah'}
STAGES = {'planned':'Belum cutting','cutting':'Cutting','sewing':'Sewing','finishing':'Finishing',
          'qc':'QC','warehouse':'Gudang','rework':'Rework','reject':'Reject'}


def csv_cell(value):
    if isinstance(value, str) and (value.startswith(('\t', '\r', '\n')) or value.lstrip().startswith(('=', '+', '-', '@'))):
        return "'" + value
    return value


def activity_csv(items):
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(['ID kejadian','Waktu Jakarta','Jenis aktivitas','Referensi order','Nama order','SKU',
                     'Jumlah pcs','Tahap asal','Tahap tujuan','Gudang bersih pcs','Catatan','Pencatat',
                     'PIC kendala','Kendala asal','Tenggat lama','Tenggat baru','PIC lama','PIC baru'])
    for item in items:
        details = item['details']
        stamp = datetime.fromisoformat(item['created_at']).astimezone(timezone(timedelta(hours=7))).strftime('%Y-%m-%d %H:%M:%S')
        warehouse = 0
        if item['kind'] in ('movement','reversal'):
            warehouse = item['quantity'] if item['to_stage'] == 'warehouse' else -item['quantity'] if item['from_stage'] == 'warehouse' else 0
        writer.writerow(map(csv_cell, [item['event_id'],stamp,KINDS[item['kind']],item['reference'],item['title'],item['sku'],
            item['quantity'],STAGES.get(item['from_stage'],''),STAGES.get(item['to_stage'],''),warehouse,item['reason'],item['actor_name'],
            details.get('owner_name',''),details.get('description',''),details.get('old_due_date',''),details.get('new_due_date',''),
            details.get('old_owner_name',''),details.get('new_owner_name','')]))
    return '\ufeff' + output.getvalue()
