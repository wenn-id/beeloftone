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


def cutting_runs_csv(plan_code, runs):
    """Ekspor detail hasil cutting P02 (issue #49): parameter operasional,
    satuan, referensi, estimasi berlabel, dan status koreksi per baris output.
    Estimasi TIDAK menggantikan angka aktual; kolomnya terpisah."""
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(['Kode rencana', 'Referensi cutting', 'Tanggal cutting', 'Status koreksi',
                     'Referensi PO', 'Kode bahan', 'Satuan bahan', 'Bahan terpakai', 'Waste bahan',
                     'Jumlah rol', 'Total lembar (semua rol)', 'Berat rol total (kg)',
                     'Berat bahan terukur (kg)', 'SKU', 'Ukuran', 'Warna', 'Target pcs',
                     'Hasil aktual pcs (run ini)', 'Realisasi lini pcs', 'Sisa target pcs',
                     'Setelan per lembar', 'Estimasi pcs', 'Dasar estimasi',
                     'Berat produk (gram)', 'Pemakaian bahan aktual (gram)',
                     'Estimasi bahan (gram)', 'Pencatat', 'Waktu catat', 'Referensi kebijakan'])
    for run in runs:
        detail = run.get('detail') or {}
        rolls = detail.get('rolls') or []
        reversal = 'Dikoreksi' if run.get('reversal') else 'Aktif'
        for line in run['outputs']:
            writer.writerow(map(csv_cell, [
                plan_code, run['reference'], detail.get('cut_date') or '', reversal,
                detail.get('po_reference') or '', run.get('code'), run.get('unit'),
                run.get('used'), run.get('waste'),
                detail.get('roll_count') or '', detail.get('total_sheets') or '',
                detail.get('total_roll_weight_kg') or '', detail.get('weight_kg') or '',
                line.get('sku'), line.get('size'), line.get('color'),
                line.get('target_quantity'), line['quantity'],
                line.get('line_realized_quantity'), line.get('line_remaining_target'),
                line.get('setelan_per_lembar') or '', line.get('estimated_output_pcs') or '',
                line.get('estimate_basis') or '', line.get('product_weight_gram') or '',
                line.get('material_used_gram') or '', line.get('estimated_material_gram') or '',
                run.get('actor_name'), run.get('created_at'),
                line.get('estimate_policy_ref') or detail.get('calculation_policy_ref') or '']))
    return '\ufeff' + output.getvalue()


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
