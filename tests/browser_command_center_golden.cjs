const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

module.exports = async ({page, login, admin, apiGet, openSidebarDestination, work}) => {
  const shots = process.env.BEELOFT_QA_SCREENSHOTS || work;
  await login(admin);
  await page.emulateMedia({reducedMotion:'no-preference',forcedColors:'none'});
  const empty = await apiGet('/api/command-center');
  const report = structuredClone(empty);
  report.generated_at = '2026-09-23T03:30:00+00:00';
  report.production = {active_orders:27, overdue_orders:3, in_progress_quantity:1840,
    rework_quantity:42, open_issues:2};
  report.approvals = {pending_count:12, pending_amount:'18750000.50', pending_without_amount:3,
    by_kind:{purchase_request:2,purchase_order:2,supplier_payment:2,marketing_budget:1,
      production_change:1,workforce_leave:1,workforce_overtime:1,payroll_batch:1,ai_action:1}};
  report.attention = [
    {id:'production-overdue',priority:'critical',kind:'production',title:'Order melewati target',
      detail:'3 order masih aktif setelah tanggal target.',action:'production_overdue',action_label:'Lihat order overdue'},
    {id:'production-issues',priority:'critical',kind:'production',title:'Kendala produksi terbuka',
      detail:'2 kendala masih menunggu penyelesaian.',action:'production_issues',action_label:'Lihat order terkendala'},
    {id:'approvals-pending',priority:'warning',kind:'approval',title:'Keputusan menunggu',
      detail:'12 pengajuan menunggu keputusan di inbox.',action:'approvals',action_label:'Buka inbox approval'},
    {id:'integration-mekari',priority:'warning',kind:'integration',title:'Mekari perlu perhatian',
      detail:'1 scope belum memiliki snapshot terbaru.',action:'integrations',action_label:'Lihat kesehatan integrasi'}];
  report.status = {state:'attention',attention_count:4,critical_count:2};
  report.integrations = {attention_count:1,systems:[
    {system:'jubelio',label:'Jubelio',health:'healthy',attention_count:0},
    {system:'mekari',label:'Mekari',health:'stale',attention_count:1}]};
  report.quality = {...report.quality,as_of:'2026-09-23',period_start:'2026-08-25',
    inspected_quantity:1200,first_pass_yield_percent:'96.50',nonconforming_rate_percent:'3.50',attention_groups:1};
  report.capacity = {...report.capacity,horizon_end:'2026-10-06',required_minutes:'7200.000',
    available_minutes:9600,capacity_complete:true,coverage_gaps:0,missing_standard_quantity:0};
  report.workforce = {...report.workforce,as_of:'2026-09-23',active_employees:32,
    present:28,leave:2,absent:1,unrecorded_employees:1,overtime_minutes:180};
  report.finance = {...report.finance,snapshot_at:report.generated_at,
    current:{period_start:'2026-09-01',period_end:'2026-09-22',net_revenue:'95000000.00',
      net_profit:'21750000.00',cash_balance:'67500000.00'},
    payables:{snapshot_at:report.generated_at,outstanding:'5500000.00',overdue_count:0,overdue_amount:'0.00',due_next_7_days_amount:'5500000.00'},
    receivables:{snapshot_at:report.generated_at,outstanding:'8000000.00',overdue_count:0,overdue_amount:'0.00',due_next_7_days_amount:'8000000.00'}};
  report.inventory = {...report.inventory,snapshot_at:report.generated_at,out_of_stock:0,at_risk:2,
    materials_to_purchase:3,recommended_production_quantity:240,mismatched:1,missing_from_snapshot:0,quarantined:0};
  const channels = [
    {marketplace:'Shopee',orders:150,completed:130,processing:12,pending:5,cancelled:3,
      units:210,gross_revenue:'31500000.00',net_revenue:'30850000.00',refund_amount:'650000.00',
      average_order_value:'242307.69',contribution_percent:'70.00'},
    {marketplace:'Tokopedia',orders:62,completed:50,processing:7,pending:3,cancelled:2,
      units:90,gross_revenue:'13500000.00',net_revenue:'13500000.00',refund_amount:'0.00',
      average_order_value:'270000.00',contribution_percent:'30.00'}];
  report.sales = {...report.sales,snapshot_at:report.generated_at,accepted_orders:212,
    units:300,gross_revenue:'45000000.00',quarantined_orders:0,
    marketplace:{snapshot_at:report.generated_at,return_snapshot_at:report.generated_at,
      period_start:'2026-09-16',period_end:'2026-09-22',trend_start:'2026-09-16',trend_end:'2026-09-22',
      summary:{orders:212,completed_orders:180,pending:8,processing:19,completed:180,cancelled:5,
        units:300,gross_revenue:'45000000.00',net_revenue:'44350000.00',refund_amount:'650000.00',
        average_order_value:'250000.00',marketplaces:2,unmatched_refunds:0,unmatched_refund_amount:'0.00'},
      marketplaces:channels,
      daily:[4,6,5,8,7,9,6].map((value,index)=>({date:`2026-09-${16+index}`,
        orders:value*4,units:[30,40,30,50,50,60,40][index],gross_revenue:String(value*1000000)})),
      products:[{sku:'LUNA-BLUE-M',product_name:'Luna Daily Shirt',color:'Blue',size:'M',orders:85,units:140,gross_revenue:'21000000.00'},
        {sku:'NOVA-SAND-L',product_name:'Nova Linen Pants',color:'Sand',size:'L',orders:60,units:100,gross_revenue:'15000000.00'},
        {sku:'ARA-WHITE-M',product_name:'Ara Essential Top',color:'White',size:'M',orders:35,units:60,gross_revenue:'9000000.00'}]}};
  let payload = report, holdNext = null, failNext = false;
  await page.route('**/api/command-center', async route => {
    const json = structuredClone(payload), held = holdNext, fail = failNext;
    holdNext = null; failNext = false;
    if (held) { held.started(); await held.gate; }
    await route.fulfill(fail ? {status:503,json:{detail:'Snapshot gagal dimuat'}} : {json});
  });
  const hold = () => {
    let started, release;
    const waiting = new Promise(resolve => { started = resolve; });
    const gate = new Promise(resolve => { release = resolve; });
    holdNext = {started,gate};
    return {waiting,release};
  };
  const settle = () => page.waitForFunction(() => !document.querySelector('.motion-enter,.is-theming')
    && getComputedStyle(document.getElementById('nav-selection-lens')).willChange === 'auto'
    && document.getAnimations().every(animation=>animation.playState==='finished'));
  const open = async () => {
    await openSidebarDestination('Command center');
    await page.locator('#command-center-content:not([hidden])').waitFor();
    await page.locator('#command-center-summary:not([aria-busy])').waitFor({state:'attached'});
    await settle();
  };
  const theme = async value => {
    if ((await page.locator('html').getAttribute('data-theme') || 'light') !== value)
      await page.locator('#theme').click();
    await settle();
  };
  const refresh = async () => {
    await page.locator('#command-center-refresh').click();
    await page.locator('#command-center-summary:not([aria-busy])').waitFor({state:'attached'});
    await settle();
  };
  await theme('light');
  const first = hold();
  await openSidebarDestination('Command center');
  await first.waiting;
  assert.equal(await page.locator('#command-center').getAttribute('aria-current'),'page');
  assert.equal(await page.locator('#command-center-view').isVisible(),true);
  assert.equal(await page.locator('#command-center-content').isHidden(),true);
  assert.match(await page.locator('#command-center-message').innerText(),/Menggabungkan/);
  first.release();
  await page.locator('#command-center-content:not([hidden])').waitFor();
  await open();
  const kpis = await page.locator('#command-center-summary .kpi-card').allTextContents();
  assert.equal(kpis.length,4);
  for (const [index,label,value] of [[0,'Penjualan bersih','Rp44.350.000,00'],[1,'Total order','212'],
    [2,'Unit terjual','300'],[3,'AOV order selesai','Rp250.000,00']]) {
    assert.ok(kpis[index].includes(label));
    assert.ok(kpis[index].includes(value),`${label} uses the response, including exact money`);
  }
  assert.match(await page.locator('#command-center-operations').innerText(),/27 order[\s\S]*12 pengajuan[\s\S]*4 perlu perhatian/);
  assert.equal(await page.locator('.pulse-total dd').innerText(),'4');
  assert.match(await page.locator('.pulse-critical').innerText(),/2 kritis/);
  assert.equal(await page.locator('.approval-total dd').innerText(),'12');
  assert.equal(await page.locator('.approval-amount').innerText(),'Rp18.750.000,50');
  assert.match(await page.locator('.approval-panel').innerText(),/3 pengajuan tanpa nominal/);
  await page.locator('.approval-breakdown summary').click();
  assert.equal(await page.locator('.approval-breakdown dt').count(),9);
  const kinds = await page.locator('.approval-breakdown dt').allTextContents();
  assert.ok(kinds.includes('People · cuti') && kinds.includes('People · lembur') && kinds.includes('People · batch payroll'));
  assert.ok(kinds.every(label=>!label.includes('_')));
  assert.deepEqual(await page.locator('.approval-breakdown dd').allTextContents(),['2','2','2','1','1','1','1','1','1']);
  await page.locator('.approval-breakdown summary').click();
  const priorities = await page.locator('[data-command-attention]').evaluateAll(rows=>rows.map(row=>
    ['critical','warning','info'].find(priority=>row.classList.contains(priority))));
  assert.deepEqual(priorities,['critical','critical','warning','warning']);
  assert.deepEqual(await page.locator('#command-center-channels .channel-name').allTextContents(),['Shopee','Tokopedia']);
  const channelText = await page.locator('#command-center-channels').innerText();
  assert.ok(channelText.includes('Rp31.500.000,00') && channelText.includes('70.00%'));
  assert.deepEqual(await page.locator('#command-center-products .rank-name').allTextContents(),
    report.sales.marketplace.products.map(row=>row.product_name));
  assert.equal(await page.locator('.trend-dot').count(),7);
  assert.match(await page.locator('.trend svg').getAttribute('aria-label'),/Penjualan order selesai.*16 Sep.*22 Sep/);
  assert.match(await page.locator('#command-center-period').innerText(),/Jubelio snapshot.*23 Sep 2026/);
  assert.deepEqual(await page.locator('.integration-panel dd').allTextContents(),['Sehat','Stale']);

  const before = await page.locator('#command-center-content').innerHTML();
  const held = hold();
  await page.locator('#command-center-refresh').click(); await held.waiting;
  assert.equal(await page.locator('#command-center-content').innerHTML(),before);
  assert.equal(await page.locator('#command-center-content').getAttribute('aria-busy'),'true');
  assert.equal(await page.locator('#command-center-content').isVisible(),true);
  held.release(); await page.locator('#command-center-summary:not([aria-busy])').waitFor();
  await settle();
  assert.equal(await page.locator('#command-center-content').getAttribute('aria-busy'),null);
  payload = structuredClone(report); payload.production.active_orders = 31;
  await refresh();
  assert.match(await page.locator('#command-center-operations').innerText(),/31 order/);
  const beforeStale = await page.locator('#command-center-content').innerHTML();
  payload = structuredClone(report); payload.production.active_orders = 999;
  const stale = hold();
  await page.locator('#command-center-refresh').click(); await stale.waiting;
  await openSidebarDestination('Produksi');
  const response = page.waitForResponse(response=>response.url().endsWith('/api/command-center'));
  stale.release(); await response;
  await page.evaluate(()=>new Promise(resolve=>setTimeout(resolve,0)));
  assert.equal(await page.locator('#command-center-view').isHidden(),true);
  assert.equal(await page.locator('#board-home').getAttribute('aria-current'),'page');
  assert.equal(await page.locator('#command-center-content').innerHTML(),beforeStale);
  payload = report; await open();
  failNext = true; await refresh();
  assert.match(await page.locator('#command-center-message').innerText(),/Snapshot gagal dimuat/);
  for (const id of ['summary','hero','channels','contribution','products','operations','attention','context','snapshots'])
    assert.equal(await page.locator('#command-center-'+id).textContent(),'');
  assert.equal(await page.locator('#command-center-content').isHidden(),true);
  await refresh();

  // Exercise every unchanged dispatch destination. Snapshot routes remain read-only dialogs.
  for (const [action,target] of [
    ['command-production-overdue','#board-view'],['command-production-issues','#board-view'],
    ['approvals','#approvals-view'],['integrations','#integrations-view'],
    ['production-quality-insights','#analytics-view'],['capacity-plan','#analytics-view'],
    ['command-workforce','#people-view'],['replenishment','#analytics-view'],['ai-brain','#ai-view'],
    ['jubelio-order-summary','#dialog[open]'],['mekari-finance-summary','#dialog[open]']]) {
    await page.locator(`#command-center-view [data-action="${action}"]`).first().click();
    await page.locator(target).waitFor();
    if (target.startsWith('#dialog')) {
      await page.keyboard.press('Escape'); await page.locator('#dialog').waitFor({state:'hidden'});
    }
    await open();
  }
  for (const [action,dispatch] of [['jubelio_stock','jubelio-stock-reconciliation'],
    ['mekari_payables','mekari-payables-summary'],['mekari_receivables','mekari-receivables-summary']]) {
    payload = structuredClone(report);
    payload.attention = [{...report.attention[0],action}];
    await refresh();
    await page.locator(`#command-center-attention [data-action="${dispatch}"]`).click();
    await page.locator('#dialog[open]').waitFor();
    await page.keyboard.press('Escape'); await page.locator('#dialog').waitFor({state:'hidden'});
  }
  for (const [health,label] of [['failed','Gagal'],['incomplete','Belum lengkap'],['never','Belum sync']]) {
    payload = structuredClone(report); payload.integrations.systems[1].health = health;
    await refresh();
    assert.equal(await page.locator('.integration-panel dd').last().innerText(),label);
  }
  payload = structuredClone(report);
  payload.sales = {...report.sales,snapshot_at:null,accepted_orders:0,units:0,gross_revenue:'0.00',
    marketplace:{...report.sales.marketplace,snapshot_at:null,return_snapshot_at:null,
      period_start:null,period_end:null,trend_start:null,trend_end:null,marketplaces:[],products:[],daily:[],
      summary:Object.fromEntries(Object.entries(report.sales.marketplace.summary).map(([key,value])=>[key,typeof value==='string'?'0.00':0]))}};
  payload.finance = {...report.finance,snapshot_at:null,current:null};
  await refresh();
  assert.equal(await page.locator('.trend svg').count(),0);
  assert.match(await page.locator('#command-center-summary').innerText(),/Snapshot order Jubelio belum tersedia/);
  assert.doesNotMatch(await page.locator('#command-center-summary').innerText(),/Rp|Tanpa refund cocok/);
  assert.doesNotMatch(await page.locator('[data-command-snapshot="sales"]').innerText(),/Rp0/);
  assert.match(await page.locator('[data-command-snapshot="finance"]').innerText(),/Snapshot keuangan belum tersedia/);
  assert.doesNotMatch(await page.locator('[data-command-snapshot="finance"]').innerText(),/Rp0/);
  assert.equal(await page.locator('.pulse-total dd').innerText(),'4');
  await page.screenshot({path:path.join(shots,'a5-empty-missing.png'),fullPage:true});
  payload = structuredClone(report); payload.attention = []; payload.status = {state:'clear',attention_count:0,critical_count:0};
  payload.approvals = {pending_count:0,pending_amount:'0.00',pending_without_amount:0,
    by_kind:Object.fromEntries(Object.keys(report.approvals.by_kind).map(kind=>[kind,0]))};
  payload.production.overdue_orders=0; payload.production.open_issues=0;
  payload.integrations = {attention_count:0,systems:report.integrations.systems.map(row=>({...row,health:'healthy',attention_count:0}))};
  payload.quality.attention_groups=0; payload.inventory.at_risk=0; payload.inventory.mismatched=0;
  await refresh();
  assert.equal(await page.locator('.pulse-total dd').innerText(),'0');
  assert.match(await page.locator('#command-center-attention').innerText(),/Tidak ada exception aktif dari sumber yang sudah tersambung/);
  await page.locator('.approval-breakdown summary').click();
  assert.deepEqual(await page.locator('.approval-breakdown dd').allTextContents(),Array(9).fill('0'));
  await page.locator('.approval-breakdown summary').click();
  payload = structuredClone(report); payload.sales.marketplace.daily = [{date:'2026-09-22',orders:1,units:1,gross_revenue:'0.00'}];
  await refresh();
  assert.equal(await page.locator('.trend-peak').innerText(),'Puncak Rp0');
  assert.equal(await page.locator('.trend-dot').count(),1);
  payload = report; await refresh();
  // The same populated report is used for local before/after optical and visual evidence.
  const optics = [], performance = [];
  let phase = 'after';
  const profile = async () => {
    await theme('light');
    await page.evaluate(() => {
      const raf = window.requestAnimationFrame, cancel = window.cancelAnimationFrame;
      const state = {raf,cancel,pending:new Set(),executed:0};
      window.a5Frames = state;
      window.requestAnimationFrame = callback => {
        const id = raf.call(window,time=>{state.pending.delete(id);state.executed++;callback(time);});
        state.pending.add(id); return id;
      };
      window.cancelAnimationFrame = id => {state.pending.delete(id);cancel.call(window,id);};
    });
    const sample = async (label, action) => {
      await page.evaluate(() => {
        const state = window.a5Frames;
        state.times = []; state.longTasks = []; state.shifts = []; state.start = performance.now(); state.sampling = true;
        state.observer = new PerformanceObserver(list=>list.getEntries().forEach(row=>{
          if(row.entryType==='longtask')state.longTasks.push(row.duration);
          else state.shifts.push({value:row.value,recentInput:row.hadRecentInput});
        }));
        state.observer.observe({type:'longtask'});
        state.observer.observe({type:'layout-shift'});
        const tick = time => {if(state.sampling){state.times.push(time);state.sampleId=state.raf.call(window,tick);}};
        state.sampleId = state.raf.call(window,tick);
      });
      await action(); await settle();
      const result = await page.evaluate(() => {
        const s=window.a5Frames; s.sampling=false; s.cancel.call(window,s.sampleId); s.observer.disconnect();
        const gaps=s.times.slice(1).map((time,index)=>time-s.times[index]).sort((a,b)=>a-b);
        return {duration:performance.now()-s.start,frames:s.times.length,
          median:gaps[Math.floor(gaps.length*.5)]||0,p95:gaps[Math.floor(gaps.length*.95)]||0,
          max:gaps.at(-1)||0,over32:gaps.filter(value=>value>32).length,longTasks:s.longTasks,layoutShifts:s.shifts};
      });
      performance.push({phase,label,...result});
    };
    await openSidebarDestination('Produksi'); await settle();
    await sample('first populated render',open);
    await sample('scroll',async()=>{
      for (const y of [300,600,900,1200,600,0]) {
        await page.evaluate(y=>window.scrollTo(0,y),y);
        await page.waitForTimeout(100);
      }
    });
    await sample('rapid navigation and spring',()=>page.evaluate(async()=>{
      for (const id of ['workforce','capacity-plan','replenishment','command-center']) {
        document.getElementById(id).click();
        await new Promise(resolve=>window.a5Frames.raf.call(window,()=>window.a5Frames.raf.call(window,resolve)));
      }
    }));
    await page.locator('#command-center-summary:not([aria-busy])').waitFor();
    await sample('theme transition',()=>theme('dark'));
    const resting = await page.evaluate(()=>({executed:window.a5Frames.executed,pending:window.a5Frames.pending.size}));
    await page.waitForTimeout(350);
    const idle = await page.evaluate(()=>({executed:window.a5Frames.executed,pending:window.a5Frames.pending.size}));
    assert.deepEqual(idle,resting,'settled Command Center executes zero RAF callbacks');
    assert.equal(idle.pending,0);
    performance.push({phase,label:'idle',duration:350,executed:idle.executed-resting.executed,pending:idle.pending});
    await page.evaluate(()=>{window.requestAnimationFrame=window.a5Frames.raf;window.cancelAnimationFrame=window.a5Frames.cancel;delete window.a5Frames;});
    await theme('light');
  };
  await profile();
  const luminance = values => values.slice(0,3).map(x => x/255)
    .map(x => x <= .04045 ? x/12.92 : ((x+.055)/1.055)**2.4)
    .reduce((sum,x,i) => sum+x*[.2126,.7152,.0722][i],0);
  const contrast = (a,b) => (Math.max(luminance(a),luminance(b))+.05)/(Math.min(luminance(a),luminance(b))+.05);
  const measure = async (label, selector) => {
    const node = page.locator(selector);
    const foreground = await node.evaluate(el => getComputedStyle(el).color.match(/[\d.]+/g).map(Number));
    const hide = await page.addStyleTag({content:`${selector},${selector} *{color:transparent!important;text-shadow:none!important;transition:none!important}`});
    const png = (await node.screenshot()).toString('base64');
    await hide.evaluate(el=>el.remove());
    const backgrounds = await page.evaluate(async png => {
      const bitmap = await createImageBitmap(await (await fetch('data:image/png;base64,'+png)).blob());
      const canvas = new OffscreenCanvas(bitmap.width,bitmap.height), ctx = canvas.getContext('2d');
      ctx.drawImage(bitmap,0,0);
      const colors = [];
      for (const x of [.25,.5,.75]) for (const y of [.3,.5,.7])
        colors.push([...ctx.getImageData(Math.floor(bitmap.width*x),Math.floor(bitmap.height*y),1,1).data]);
      return colors;
    }, png);
    const background = backgrounds.sort((a,b)=>contrast(foreground,a)-contrast(foreground,b))[0];
    const ratio = contrast(foreground,background);
    optics.push({phase,theme:await page.locator('html').getAttribute('data-theme')||'light',label,foreground,background,ratio});
    assert.ok(ratio>=4.5,`${phase} ${label} rendered contrast ${ratio}: ${foreground} on ${background}`);
  };
  for (const mode of ['light','dark']) {
    await theme(mode);
    await page.evaluate(() => window.scrollTo(0,0));
    await page.screenshot({path:path.join(shots,`a5-1440-${mode}.png`),fullPage:true});
    await page.screenshot({path:path.join(shots,`a5-1440-${mode}-viewport.png`)});
    await measure('selected navigation','#command-center');
    await measure('sidebar primary','#board-home');
    await measure('sidebar secondary','#capacity-plan');
    for (const scroll of [0,600,1200]) {
      await page.evaluate(y=>window.scrollTo(0,y),scroll);
      await measure('masthead brand at '+scroll,'.brand-word');
      await measure('masthead primary at '+scroll,'.top-context strong');
      await measure('masthead metadata at '+scroll,'.top-context>span');
      await measure('masthead account at '+scroll,'#account-name');
    }
    for (const [label,selector] of [['card body','.pulse-next h3'],['card secondary','.pulse-next p'],
      ['warning chip','#command-center-summary .chip-warning'],['critical status','.decision-row.critical .status-label']])
      await measure(label,selector.startsWith('.decision')?'.decision-row.critical:first-child .status-label':selector);
    await openSidebarDestination('Inbox approval'); await settle();
    await measure('approval selected','#approvals');
    await open();
  }
  await theme('light');
  for (const width of [1440,1280,1024,981,980,768,390,320]) {
    await page.setViewportSize({width,height:width<650?844:1000}); await settle();
    await page.evaluate(()=>window.scrollTo(0,0));
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth),true,`${width} no document overflow`);
    assert.equal(await page.locator('#command-center-view h1').isVisible(),true);
    for (const control of await page.locator('#command-center-view button:visible').all()) {
      const rect = await control.boundingBox();
      if (width<=980) assert.ok(rect.height>=44,`${width} ${await control.innerText()} target ${rect.height}px must be at least 44px`);
    }
    if ([1024,768,390].includes(width)) await page.screenshot({path:path.join(shots,`a5-${width}-light.png`),fullPage:true});
    if (width===390) {
      await theme('dark'); await page.screenshot({path:path.join(shots,'a5-390-dark.png'),fullPage:true}); await theme('light');
    }
  }
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  await settle();
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth),true,'320 at 200% no document overflow');
  const clipped = await page.locator('#command-center-summary dt, #command-center-view button').evaluateAll(nodes=>nodes
    .filter(node=>node.getClientRects().length && (node.scrollWidth>node.clientWidth+1 || node.scrollHeight>node.clientHeight+1)).map(node=>node.textContent));
  assert.deepEqual(clipped,[],'KPI labels and actions are not clipped');
  await page.locator('.approval-breakdown summary').click();
  assert.equal(await page.locator('.approval-breakdown dt').count(),9);
  await page.locator('.approval-breakdown summary').click();
  await page.evaluate(()=>window.scrollTo(0,0));
  await page.screenshot({path:path.join(shots,'a5-320-200-text.png')});
  await page.locator('#command-center-attention').scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(shots,'a5-320-200-decisions-viewport.png')});
  await page.locator('#command-center-snapshots article:last-child').scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(shots,'a5-320-200-bottom-viewport.png')});
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.setViewportSize({width:1440,height:900});
  await page.locator('#command-center-refresh').focus();
  await page.keyboard.press('Tab');
  assert.equal(await page.evaluate(()=>document.activeElement.matches(':focus-visible')),true);
  assert.notEqual(await page.evaluate(()=>getComputedStyle(document.activeElement).outlineStyle),'none');
  const material = await page.evaluate(()=>({
    supported:CSS.supports('backdrop-filter','blur(1px)')||CSS.supports('-webkit-backdrop-filter','blur(1px)'),
    chrome:getComputedStyle(document.querySelector('.masthead')).backdropFilter,
    lens:getComputedStyle(document.querySelector('#nav-selection-lens')).backdropFilter,
    content:[...document.querySelectorAll('#command-center-view .card,#command-center-view .hero-panel,#command-center-summary>div')]
      .map(node=>({filter:getComputedStyle(node).backdropFilter,bg:getComputedStyle(node).backgroundColor})),
    ambient:getComputedStyle(document.querySelector('.workspace-main'),'::before').pointerEvents}));
  if(material.supported)assert.notEqual(material.chrome,'none');
  else assert.equal(material.chrome,'none');
  assert.equal(material.lens,'none');
  assert.ok(material.content.every(row=>row.filter==='none' && !row.bg.startsWith('rgba')));
  assert.equal(material.ambient,'none');
  // Optional local evidence serves saved baseline assets without modifying the checkout.
  if (process.env.BEELOFT_A5_BASELINE_DIR) {
    phase = 'before';
    await page.setViewportSize({width:1440,height:1000});
    const baseline = process.env.BEELOFT_A5_BASELINE_DIR;
    const routes = [new URL(page.url()).origin+'/', '**/static/style.css', '**/static/app.mjs'];
    for (const [index,file] of ['index.html','style.css','app.mjs'].entries())
      await page.route(routes[index],route=>route.fulfill({path:path.join(baseline,file),
        contentType:index===0?'text/html':index===1?'text/css':'text/javascript'}));
    await page.reload(); await page.locator('#summary dd').first().waitFor();
    await open(); await profile();
    for (const mode of ['light','dark']) {
      await theme(mode); await page.evaluate(()=>window.scrollTo(0,0));
      await page.screenshot({path:path.join(baseline,`a5-1440-${mode}.png`),fullPage:true});
      await measure('selected navigation','#command-center');
      await measure('sidebar primary','#board-home');
      await measure('sidebar secondary','#capacity-plan');
      for (const scroll of [0,600,1200]) {
        await page.evaluate(y=>window.scrollTo(0,y),scroll);
        await measure('masthead brand at '+scroll,'.brand-word');
        await measure('masthead primary at '+scroll,'.top-context strong');
        await measure('masthead metadata at '+scroll,'.top-context>span');
        await measure('masthead account at '+scroll,'#account-name');
      }
      await openSidebarDestination('Inbox approval'); await settle();
      await measure('approval selected','#approvals'); await open();
    }
    for (const route of routes) await page.unroute(route);
    await page.reload(); await page.locator('#summary dd').first().waitFor(); await open();
  }
  fs.writeFileSync(path.join(shots,'a5-optics.json'),JSON.stringify(optics,null,2));
  fs.writeFileSync(path.join(shots,'a5-performance.json'),JSON.stringify(performance,null,2));
  await theme('light');
  await page.unroute('**/api/command-center');
  console.log('Command Center golden PASS: truth, actions, approvals, integrations, first load, refresh, stale/error, missing sources, themes, rendered contrast, 8 widths and 320 at 200%.');
};
