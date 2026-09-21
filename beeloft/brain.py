from decimal import Decimal


INTENT_TERMS = {
    'stockout': ('stockout','stok habis','stok akan habis','kehabisan','persediaan','restock','replenish','replenishment',
                 'safety stock','rekomendasi stok','beli bahan','pembelian bahan','demand'),
    'approvals': ('approval','persetujuan','menunggu keputusan','perlu disetujui','antrian approval'),
    'margin': ('margin','kontribusi','profit','laba','omzet','pendapatan','biaya'),
    'production': ('produksi','order','terlambat','telat','wip','kendala','rework'),
    'overview': ('ringkasan','kondisi','bisnis','prioritas','perhatian','hari ini'),
}
INTENT_PRIORITY = ('stockout','approvals','margin','production','overview')

# Banyaknya item approval yang ditampilkan sebagai contoh pada findings dan rekomendasi. Angka
# ringkasan tidak dibatasi oleh nilai ini.
APPROVAL_SAMPLE = 10
APPROVAL_SUMMARY_SOURCE = '/api/approvals/summary?status=pending'
APPROVAL_LIST_SOURCE = '/api/approvals?status=pending'


def _intent(question):
    normalized=' '.join(question.casefold().split())
    matches={name:[term for term in terms if term in normalized]
             for name,terms in INTENT_TERMS.items()}
    score=max((len(terms) for terms in matches.values()),default=0)
    selected=next((name for name in INTENT_PRIORITY if len(matches[name])==score),'overview') if score else 'overview'
    confidence='high' if score>=2 else 'medium' if score else 'low'
    return selected,confidence,matches[selected],normalized


def _focus(store, normalized):
    products=store.products(1_000_000_000,0)
    orders=store.orders(1_000_000_000,0)
    matched_products=[row for row in products if row['sku'].casefold() in normalized
                      or (len(row['name'])>=3 and row['name'].casefold() in normalized)]
    matched_orders=[row for row in orders if row['reference'].casefold() in normalized
                    or (len(row['title'])>=3 and row['title'].casefold() in normalized)]
    return {'products':[{'id':row['id'],'sku':row['sku'],'name':row['name']} for row in matched_products],
            'orders':[{'id':row['id'],'reference':row['reference'],'title':row['title']}
                      for row in matched_orders]},products,orders


def _fact(label,value,unit,source):
    return {'label':label,'value':value,'unit':unit,'source':source}


def _proposal(kind,title,detail,source,preview):
    return {'kind':kind,'title':title,'detail':detail,'source':source,
            'approval_required':True,'executable':False,'preview':preview}


def _stock(store,payload,focus):
    query=focus['products'][0]['sku'] if len(focus['products'])==1 else ''
    report=store.replenishment_recommendations(payload['as_of'],payload['window_days'],
        payload['lead_time_days'],payload['review_period_days'],payload['safety_stock_days'],
        payload['batch_multiple'],query,'',100,0)
    summary=report['summary']
    urgent=summary['out_of_stock']+summary['stockout_before_replenishment']
    answer=(f"Ada {urgent} SKU berisiko stockout sebelum replenishment, "
            f"{summary['below_safety_stock']} SKU di bawah safety stock, dan "
            f"{summary['recommended_production_quantity']} pcs direkomendasikan untuk produksi.")
    facts=[_fact('SKU berisiko segera',urgent,'sku','/api/replenishment-recommendations'),
           _fact('Rekomendasi produksi',summary['recommended_production_quantity'],'pcs',
                 '/api/replenishment-recommendations'),
           _fact('Bahan perlu dibeli',summary['materials_to_purchase'],'material',
                 '/api/replenishment-recommendations')]
    severity={'out_of_stock':'critical','stockout_before_replenishment':'high',
              'below_safety_stock':'medium','insufficient_history':'info','no_demand':'info'}
    risk_label={'out_of_stock':'stok sudah habis','stockout_before_replenishment':'stockout sebelum replenishment',
                'below_safety_stock':'di bawah safety stock','insufficient_history':'riwayat demand belum cukup',
                'no_demand':'tidak ada demand pada window'}
    findings=[]
    for row in report['product_recommendations']:
        if row['stockout_risk']=='covered':
            continue
        cover='belum tersedia' if row['days_of_cover'] is None else row['days_of_cover']+' hari'
        findings.append({'severity':severity[row['stockout_risk']],
            'title':row['sku']+' · '+risk_label[row['stockout_risk']],
            'detail':f"Stok tersedia {row['available_quantity']} pcs, coverage {cover}, "
                     f"produksi berjalan {row['inbound_production_quantity']} pcs.",
            'source':'/api/replenishment-recommendations','entity':{'type':'product','id':row['id']}})
    proposals=[]
    for row in report['product_recommendations']:
        if row['recommended_production_quantity']:
            proposals.append(_proposal('create_production_order',f"Produksi {row['sku']}",
                f"Pertimbangkan produksi {row['recommended_production_quantity']} pcs.",
                '/api/replenishment-recommendations',{'product_id':row['id'],
                 'quantity':row['recommended_production_quantity']}))
    for row in report['material_purchase_recommendations']:
        if row['status']=='purchase':
            proposals.append(_proposal('create_purchase_request',f"Beli {row['code']}",
                f"Kekurangan terhitung {row['recommended_purchase_quantity']} {row['unit']}.",
                '/api/replenishment-recommendations',{'material_id':row['material_id'],
                 'quantity':row['recommended_purchase_quantity'],'unit':row['unit']}))
    for gap in report['coverage_gaps']:
        proposals.append(_proposal('complete_bom',f"Lengkapi BOM {gap['sku']}",
            'BOM diperlukan sebelum kebutuhan bahan dapat dipercaya.',
            '/api/products/{product_id}/bom',{'product_id':gap['product_id']}))
    return answer,facts,findings[:10],proposals[:10],{'replenishment':report}


def _approvals(store):
    # Jumlah dan nominal berasal dari agregat seluruh populasi. Daftar dibaca terpisah dan hanya
    # sebanyak contoh yang benar-benar ditampilkan, sehingga jawaban tidak lagi menganggap satu
    # halaman terbatas sebagai seluruh data.
    summary=store.approvals_summary('pending','all')
    rows=store.approvals(APPROVAL_SAMPLE,0,'pending','all')
    total,amount=summary['total'],summary['amount']
    answer=f"Ada {total} item menunggu keputusan dengan total nominal tercatat Rp{amount}."
    facts=[_fact('Approval tertunda',total,'item',APPROVAL_SUMMARY_SOURCE),
           _fact('Nominal tertunda',amount,'IDR',APPROVAL_SUMMARY_SOURCE)]
    facts.extend(_fact('Approval '+kind.replace('_',' '),row['count'],'item',APPROVAL_SUMMARY_SOURCE)
                 for kind,row in sorted(summary['by_kind'].items()) if row['count'])
    findings=[{'severity':'high','title':row['reference']+' · '+row['department'],
        'detail':row['title'],'source':APPROVAL_LIST_SOURCE,
        'entity':{'type':row['kind'],'id':row['id']}} for row in rows]
    proposals=[_proposal('review_approval','Review '+row['reference'],row['title'],
        APPROVAL_LIST_SOURCE,{'kind':row['kind'],'id':row['id']}) for row in rows]
    # Evidence memisahkan ringkasan seluruh populasi dari contoh item yang ditampilkan, sehingga
    # jawaban tetap dapat diaudit dan detail yang terpotong dinyatakan secara eksplisit.
    evidence={'approvals':{'summary':summary,'sample':rows,'sample_size':len(rows),
        'truncated':total>len(rows)}}
    return answer,facts,findings,proposals,evidence


def _production(store,focus):
    query=focus['orders'][0]['reference'] if len(focus['orders'])==1 else (
        focus['products'][0]['sku'] if len(focus['products'])==1 else '')
    board=store.production_board(100,0,query,'all','','all')
    # Ringkasan board selalu global supaya KPI-nya tidak bergoyang saat daftar difilter. Jawaban
    # fokus tidak boleh memakai kontrak itu: jawaban dan faktanya dihitung ulang atas populasi order
    # yang dipilih saja, dan atas seluruh populasi itu - bukan hanya halaman pertama daftar.
    scope=store.production_scope(query)
    summary=scope['summary']
    answer=(f"Ada {summary['active']} order aktif, {summary['overdue']} terlambat, "
            f"{scope['open_issues']} kendala terbuka, dan {summary['in_progress']} pcs sedang diproses.")
    facts=[_fact('Order aktif',summary['active'],'order','/api/production-board'),
           _fact('Order terlambat',summary['overdue'],'order','/api/production-board'),
           _fact('Kendala terbuka',scope['open_issues'],'issue','/api/production-board'),
           _fact('Sedang diproses',summary['in_progress'],'pcs','/api/production-board')]
    candidates=[row for row in board['orders'] if row['overdue'] or row['open_issues']]
    findings=[{'severity':'high' if row['overdue'] else 'medium',
        'title':row['reference']+(' · terlambat' if row['overdue'] else ' · ada kendala'),
        'detail':f"Sisa produksi {row['target_quantity']-row['totals']['warehouse']-row['totals']['reject']} pcs; "
                 f"{row['open_issues']} kendala terbuka.",
        'source':'/api/production-board','entity':{'type':'order','id':row['id']}}
        for row in candidates[:10]]
    proposals=[_proposal('investigate_order','Periksa '+row['reference'],
        'Buka order dan cek tahap, PIC, tenggat, serta kendala aktif.',
        '/api/production-board',{'order_id':row['id']}) for row in candidates[:10]]
    # `production_board` tetap membawa kontrak KPI global, sedangkan `production_scope` adalah
    # agregat yang benar-benar mendasari jawaban dan facts. Keduanya disimpan supaya snapshot dapat
    # diaudit tanpa menebak angka mana yang dipakai.
    return answer,facts,findings,proposals,{'production_board':board,'production_scope':scope}


def _margin(store,focus,orders):
    selected=orders
    if focus['orders']:
        ids={row['id'] for row in focus['orders']};selected=[row for row in orders if row['id'] in ids]
    elif focus['products']:
        ids={row['id'] for row in focus['products']}
        selected=[row for row in orders if any(line['product_id'] in ids for line in row['lines'])]
    reports=[store.contribution_margin(row['id']) for row in selected[:100]]
    complete=[row for row in reports if row['status']=='complete']
    total=sum((Decimal(row['contribution_margin']) for row in complete),Decimal(0))
    answer=(f"{len(complete)} dari {len(reports)} order memiliki margin lengkap. "
            f"Total margin kontribusi yang dapat dihitung Rp{format(total,'.2f')}.")
    facts=[_fact('Margin lengkap',len(complete),'order','/api/orders/{id}/contribution-margin'),
           _fact('Margin belum lengkap',len(reports)-len(complete),'order',
                 '/api/orders/{id}/contribution-margin'),
           _fact('Total margin terhitung',format(total,'.2f'),'IDR',
                 '/api/orders/{id}/contribution-margin')]
    findings=[];proposals=[]
    for row in reports:
        if row['status']=='complete':
            rate=row['contribution_margin_rate']
            detail=('Rasio margin '+rate+'%.' if rate is not None else
                    'Rasio margin belum tersedia (pendapatan bersih Rp'+row['net_revenue']+').')
            findings.append({'severity':'medium' if Decimal(row['contribution_margin'])<0 else 'info',
                'title':row['order_reference']+' · margin Rp'+row['contribution_margin'],
                'detail':detail,
                'source':'/api/orders/{id}/contribution-margin',
                'entity':{'type':'order','id':row['order_id']}})
        else:
            kinds=sorted({gap['kind'] for gap in row['coverage_gaps']})
            findings.append({'severity':'high','title':row['order_reference']+' · margin belum lengkap',
                'detail':'Data yang belum lengkap: '+', '.join(kinds)+'.',
                'source':'/api/orders/{id}/contribution-margin',
                'entity':{'type':'order','id':row['order_id']}})
            proposals.append(_proposal('complete_margin_sources','Lengkapi '+row['order_reference'],
                'Periksa biaya produksi, shipment, settlement, dan retur.',
                '/api/orders/{id}/contribution-margin',{'order_id':row['order_id'],'gaps':kinds}))
    return answer,facts,findings[:10],proposals[:10],{'contribution_margins':reports,
        'truncated':len(selected)>100}


def investigate(store,payload):
    intent,confidence,matched,normalized=_intent(payload['question'])
    focus,_,orders=_focus(store,normalized)
    if intent=='stockout':
        result=_stock(store,payload,focus)
    elif intent=='approvals':
        result=_approvals(store)
    elif intent=='margin':
        result=_margin(store,focus,orders)
    elif intent=='production':
        result=_production(store,focus)
    else:
        production=_production(store,focus)
        approvals=_approvals(store)
        stock=_stock(store,payload,focus)
        result=(production[0]+' '+approvals[0]+' '+stock[0],
            production[1]+approvals[1]+stock[1],
            (production[2]+approvals[2]+stock[2])[:12],
            (production[3]+approvals[3]+stock[3])[:12],
            production[4]|approvals[4]|stock[4])
    answer,facts,findings,recommendations,evidence=result
    interpretation={'overview':'ringkasan bisnis','production':'kondisi produksi',
        'stockout':'risiko stockout dan replenishment','approvals':'antrean approval',
        'margin':'margin kontribusi'}[intent]
    return {'question':payload['question'],'intent':intent,'interpretation':interpretation,
        'confidence':confidence,'matched_terms':matched,'focus':focus,'as_of':payload['as_of'],
        'engine':'local_rules_v1','external_model_used':False,'read_only':True,'answer':answer,
        'facts':facts,'findings':findings,'recommendations':recommendations,'evidence':evidence,
        'limitations':['Bahasa dipetakan dengan aturan lokal; pertanyaan ambigu dapat masuk intent yang salah.',
            'Rekomendasi belum dapat dieksekusi dan tetap memerlukan pemeriksaan manusia serta approval.',
            'Jawaban hanya memakai ledger internal yang tersedia saat investigasi dijalankan.']}
