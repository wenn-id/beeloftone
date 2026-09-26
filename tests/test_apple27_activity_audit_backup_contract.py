"""A6.6 - Aktivitas + Audit trail + Cadangan data modern workspaces: the static half of the contract.

A6.6 is presentation-only. What can break here is not a layout; it is a quietly weakened invariant:
Activity's server-default Jakarta day, its auto-change loading, its stale-filter invalidation, its
range-wide summary, its 50-row two-part cursor or its full-filter CSV; Audit's admin gate, its
users-first setup, its 25-row sequence cursor, its escaped verbatim evidence; Backup's admin gates,
its guardPending, its request fence and its busy lock. Each of those is pinned below against the
source text, together with the containment of the A6.6 CSS block, the unchanged frame/timer budget,
the untouched shell and the aligned version.

The migration allowance itself lives in tests/test_apple27_modern_workspace_foundation_contract.py,
which A6.6 widened to exactly the three sections and the named renderers. The behavioural half is
tests/browser_activity_audit_backup_modern_workspaces.cjs.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / 'beeloft' / 'static'
HTML = (STATIC / 'index.html').read_text(encoding='utf-8')
APP = (STATIC / 'app.mjs').read_text(encoding='utf-8')
CSS = (STATIC / 'style.css').read_text(encoding='utf-8')
API = (ROOT / 'beeloft' / 'api.py').read_text(encoding='utf-8')


def section(html, element_id):
    start = html.index(f'<section id="{element_id}"')
    depth = 0
    for match in re.finditer(r'<section\b|</section>', html[start:]):
        depth += 1 if match.group().startswith('<section') else -1
        if depth == 0:
            return html[start:start + match.end()]
    raise AssertionError(f'#{element_id} is not a closed section')


def code_css(source):
    return re.sub(r'/\*.*?\*/', '', source, flags=re.S)


def between(start, end):
    return APP[APP.index(start):APP.index(end, APP.index(start))]


ACTIVITY = section(HTML, 'activity-view')
AUDIT = section(HTML, 'audit-view')
BACKUP = section(HTML, 'backup-view')
LOAD_ACTIVITY = between('async function loadActivity(', '\nconst activityTone')
ACTIVITY_EVENT = between('function activityEvent(', '\n// Errors stay inline')
ACTIVITY_WIRING = between("$('activity').onclick", 'function saveDownload(')
LOAD_AUDIT = between('async function loadAuditEvents(', 'async function auditEventDialog(')
AUDIT_DIALOG = between('async function auditEventDialog(', '\n// Keluar dialog')
BACKUP_JS = APP[APP.index("$('backup').onclick"):]
A66_MARKER = '#activity-view,#audit-view,#backup-view{max-width:1360px'
# A6.7 appended its own block after this one; the A6.6 slice ends where it begins, so the checks
# below keep meaning exactly what they meant when A6.6 was approved.
A67_MARKER = '#purchase-requests-view,#marketing-budgets-view,#approvals-view{max-width:1360px'
A66_BLOCK = code_css(CSS)[code_css(CSS).index(A66_MARKER):code_css(CSS).index(A67_MARKER)]


class ActivityTest(unittest.TestCase):
    def test_section_consumes_a6_with_the_approved_identity(self):
        self.assertIn('<section id="activity-view" class="workspace-page" hidden>', ACTIVITY)
        self.assertIn('<h1 class="workspace-title">Aktivitas</h1>', ACTIVITY)
        self.assertIn('Telusuri catatan produksi dalam waktu Jakarta dan ekspor hasilnya.', ACTIVITY)
        self.assertIn('waktu Jakarta', ACTIVITY)
        self.assertIn('<form id="activity-form" class="command-bar"', ACTIVITY)
        self.assertIn('class="metric-strip"', ACTIVITY)
        self.assertIn('class="timeline"', ACTIVITY)
        self.assertNotRegex(ACTIVITY, r'class="(?:page-heading|eyebrow|filters|summary|hint|pagination)"')

    def test_every_id_is_preserved(self):
        for element in ('activity-back', 'activity-form', 'activity-day', 'activity-end', 'activity-kind',
                        'activity-export', 'activity-summary', 'activity-message', 'activity-list',
                        'activity-count', 'activity-more'):
            with self.subTest(element=element):
                self.assertIn(f'id="{element}"', ACTIVITY)

    def test_the_seven_filter_values_and_labels(self):
        options = re.findall(r'<option value="([^"]+)">([^<]+)</option>', ACTIVITY)
        self.assertEqual(options, [('all', 'Semua aktivitas'), ('movement', 'Perpindahan barang'),
                                   ('reversal', 'Koreksi perpindahan'), ('issue_opened', 'Kendala dicatat'),
                                   ('issue_resolved', 'Kendala selesai'), ('order_created', 'Order dibuat'),
                                   ('order_changed', 'Tenggat / PIC diubah')])
        self.assertIn("const activityLabels = {movement:'Perpindahan barang',reversal:'Koreksi perpindahan',"
                      "issue_opened:'Kendala dicatat',issue_resolved:'Kendala selesai',order_created:'Order dibuat',"
                      "order_changed:'Tenggat / PIC diubah'};", APP)

    def test_dates_are_required_and_have_no_max_rule(self):
        for element in ('activity-day', 'activity-end'):
            tag = re.search(r'<input id="' + element + r'"[^>]*>', ACTIVITY).group()
            self.assertIn('type="date"', tag)
            self.assertIn('required', tag)
            self.assertNotIn('max=', tag)

    def test_submit_change_and_input_wiring(self):
        self.assertIn("$('activity-form').onsubmit = event => { event.preventDefault(); loadActivity(); };", ACTIVITY_WIRING)
        self.assertIn("$('activity-day').onchange = $('activity-end').onchange = $('activity-kind').onchange = () => "
                      "{ if ($('activity-form').reportValidity()) loadActivity(); };", ACTIVITY_WIRING)
        invalidate = between("for (const id of ['activity-day','activity-end','activity-kind'])", "$('activity-export').onclick")
        for fragment in ("addEventListener('input'", 'activityRequest++', 'activityQuery = null', 'activityCursor = null',
                         'activityRows = []', "$('activity-list').replaceChildren()", "$('activity-summary').replaceChildren()",
                         "$('activity-count').textContent = ''", "$('activity-more').hidden = true",
                         "$('activity-export').disabled = true"):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, invalidate)

    def test_the_request_contract_is_unchanged(self):
        self.assertIn("const query = more ? {...activityQuery,...activityCursor} : {kind:$('activity-kind').value,limit:50};", LOAD_ACTIVITY)
        self.assertIn("if (!more && ($('activity-day').value || $('activity-end').value)) { query.start_date = "
                      "$('activity-day').value; query.end_date = $('activity-end').value; }", LOAD_ACTIVITY)
        self.assertIn("api.get('/api/activity?' + new URLSearchParams(query))", LOAD_ACTIVITY)
        self.assertIn("activityQuery = {start_date:result.start_date,end_date:result.end_date,kind:query.kind,limit:50}; "
                      "$('activity-day').value = result.start_date; $('activity-end').value = result.end_date;", LOAD_ACTIVITY)
        self.assertIn('activityCursor = result.next_before', LOAD_ACTIVITY)
        self.assertIn("$('activity-more').hidden = !activityCursor", LOAD_ACTIVITY)
        self.assertIn("if (version !== epoch || request !== activityRequest || view !== 'activity') return;", LOAD_ACTIVITY)
        self.assertIn('Muat aktivitas sebelumnya', ACTIVITY)
        # The backend cursor is still the before_time + before_id pair.
        self.assertRegex(API, r'before_time: datetime \| None = None,\s*before_id:')
        self.assertIn('"before_time": rows[-1]["created_at"], "before_id": rows[-1]["event_id"]',
                      (ROOT / 'beeloft' / 'store.py').read_text(encoding='utf-8'))

    def test_the_summary_is_the_returned_four_and_range_wide(self):
        for label, field in (('Aktivitas tercatat', 's.events'), ('Gudang bersih', 's.warehouse_net'),
                             ('Kendala dicatat', 's.issues_opened'), ('Kendala selesai', 's.issues_resolved')):
            with self.subTest(label=label):
                self.assertRegex(LOAD_ACTIVITY, re.escape(f"['{label}',{field},"))
        self.assertIn('class="metric-card metric-card-info"', LOAD_ACTIVITY)
        self.assertNotIn('metric-card-danger', LOAD_ACTIVITY, 'a negative warehouse net is not an error')
        self.assertIn('Ringkasan mencakup semua jenis pada rentang terpilih. Gudang bersih = barang masuk dikurangi '
                      'pembalikannya pada rentang pencatatan; angkanya bisa negatif. Posisi barang saat ini ada di papan produksi.',
                      ACTIVITY)
        # The backend computes the summary before the kind filter; A6.6 did not touch that.
        store = (ROOT / 'beeloft' / 'store.py').read_text(encoding='utf-8')
        body = store[store.index('    def activity(self, day=None'):]
        body = body[:body.index('\n    def ', 10)]
        self.assertLess(body.index('summary = dict('), body.index('filtered, params'))
        self.assertNotIn(":kind", body[body.index('summary = dict('):body.index('filtered, params')])

    def test_each_event_keeps_its_data_escaped_in_jakarta_time(self):
        self.assertIn("timeZone:'Asia/Jakarta'", APP[APP.index('const activityStamp'):APP.index('function activityEvent(')])
        for fragment in ("${n(item.quantity)} pcs · ${labels[item.from_stage]} → ${labels[item.to_stage]}",
                         "${labels[item.to_stage]} · PIC: ${item.details.owner_name}",
                         "${labels[item.to_stage]} · ${item.details.description}",
                         "Tenggat: ${date(item.details.old_due_date)} → ${date(item.details.new_due_date)} · PIC: "
                         "${item.details.old_owner_name} → ${item.details.new_owner_name}",
                         'data-action="detail" data-id="${e(item.order_id)}"', '${e(item.reference)} · ${e(item.title)}',
                         '${e(item.sku)}', '${e(detail)}', '${e(item.reason)}', 'Dicatat ${e(item.actor_name)}',
                         'class="timeline-item activity-item'):
            with self.subTest(fragment=fragment[:50]):
                self.assertIn(fragment, ACTIVITY_EVENT)
        self.assertIn('activityRows.map(activityEvent)', LOAD_ACTIVITY)

    def test_count_and_empty_wording(self):
        self.assertIn('`${n(activityRows.length)} catatan ditampilkan · ${n(result.total)} cocok saat dimuat`', LOAD_ACTIVITY)
        self.assertIn("pageState('activity-message','empty','Tidak ada aktivitas yang cocok pada rentang ini.'", LOAD_ACTIVITY)

    def test_csv_export_is_the_full_successful_filter(self):
        export = between("$('activity-export').onclick", 'function saveDownload(')
        self.assertIn('if (!activityQuery || exportBusy) return;', export)
        self.assertIn('query = {...activityQuery}; delete query.limit;', export)
        self.assertNotIn('activityCursor', export, 'export never carries a cursor')
        self.assertIn("api.download('/api/activity.csv?' + new URLSearchParams(query))", export)
        self.assertIn("saveDownload(blob,`beeloft-aktivitas-${query.start_date}-${query.end_date}-${query.kind}.csv`)", export)
        self.assertIn("exportBusy = true; $('activity-export').disabled = true; $('activity-export').textContent = 'Menyiapkan CSV…';", export)
        self.assertIn("exportBusy = false; $('activity-export').textContent = 'Unduh CSV'; $('activity-export').disabled = !activityQuery;", export)
        self.assertIn("$('activity-export').disabled = !activityQuery || exportBusy", LOAD_ACTIVITY)
        self.assertIn('CSV memuat seluruh hasil filter; maksimal 366 hari dan 10.000 catatan.', ACTIVITY)
        self.assertIn('MAX_EXPORT_ROWS = 10_000', API)

    def test_activity_is_readable_by_every_role(self):
        self.assertNotRegex(ACTIVITY_WIRING[:ACTIVITY_WIRING.index('async function loadActivity(')], r"role\s*[!=]==")
        self.assertIn('id="activity" class="nav-item"', HTML)
        self.assertNotRegex(APP, r"\$\('activity'\)\.hidden")


class AuditTest(unittest.TestCase):
    def test_section_consumes_a6_with_the_approved_identity(self):
        self.assertIn('<section id="audit-view" class="workspace-page" hidden>', AUDIT)
        self.assertIn('<h1 class="workspace-title">Audit trail</h1>', AUDIT)
        self.assertIn('Telusuri perubahan bisnis dan keputusan approval yang tersimpan sebagai catatan read-only.', AUDIT)
        self.assertIn('Catatan bersifat read-only, urut dari yang terbaru, dan dikelola admin.', AUDIT)
        self.assertIn('id="audit-back"', AUDIT)
        self.assertIn('<form id="audit-filter" class="command-bar">', LOAD_AUDIT)
        self.assertIn('class="record-list audit-ledger"', LOAD_AUDIT)

    def test_admin_only_navigation_and_api(self):
        self.assertIn("$('audit-trail').hidden=me.role!=='admin'", APP)
        self.assertEqual(API.count("Hanya admin yang dapat membaca global audit trail."), 2)

    def test_entry_guard_and_page_fence(self):
        self.assertIn("function showAuditEvents() {\n  if (guardPending()) return;\n  activateWorkspace('audit-trail');\n  loadAuditEvents();\n}", APP)
        self.assertIn("const current=()=>version===epoch&&request===auditRequest&&view==='audit';", LOAD_AUDIT)
        self.assertLess(LOAD_AUDIT.index("await api.get('/api/users')"), LOAD_AUDIT.index("api.get('/api/audit-events?'"))
        self.assertIn('Coba lagi</button>', LOAD_AUDIT[LOAD_AUDIT.rindex('}catch(error){'):])
        self.assertIn('data-action="audit-events"', LOAD_AUDIT[LOAD_AUDIT.rindex('}catch(error){'):])

    def test_filter_state_categories_and_actor_source(self):
        self.assertIn("let auditFilters = {q:'',category:'all',actor_id:'',start_date:'',end_date:''};", APP)
        self.assertIn("auditFilters={q:'',category:'all',actor_id:'',start_date:'',end_date:''};loadAuditEvents();", LOAD_AUDIT)
        self.assertIn("const auditCategories = {master_data:'Master data',production:'Produksi',materials:'Bahan baku',\n"
                      "  purchasing:'Pembelian',warehouse:'Gudang',marketplace:'Marketplace',approval:'Approval',\n"
                      "  ai:'AI',integration:'Integrasi'};", APP)
        self.assertIn('<option value="all">Semua kategori</option>', LOAD_AUDIT)
        self.assertIn('<option value="">Semua pelaku</option>${users.map(item=>option(item.id,`${item.name} · ${item.role}`)).join(\'\')}', LOAD_AUDIT)
        self.assertIn('name="q" type="search" maxlength="160"', LOAD_AUDIT)
        self.assertIn('Cari operasi, referensi, pelaku, atau request key', LOAD_AUDIT)
        for name in ('category', 'actor_id', 'start_date', 'end_date'):
            self.assertIn(f'name="{name}"', LOAD_AUDIT)
        self.assertIn('Terapkan filter', LOAD_AUDIT)
        self.assertIn('id="audit-reset"', LOAD_AUDIT)
        self.assertNotRegex(LOAD_AUDIT, r"oninput|addEventListener\('input'", 'search submits explicitly')

    def test_pagination_total_and_motion(self):
        self.assertIn("new URLSearchParams({limit:'25',...auditFilters,...(before?{before:String(before)}:{})})", LOAD_AUDIT)
        self.assertIn('for(const [key,value] of [...params])if(!value)params.delete(key);', LOAD_AUDIT)
        self.assertIn('before=page.next_before;render(page.total)', LOAD_AUDIT)
        self.assertIn('`${n(total)} catatan sesuai filter.`', LOAD_AUDIT)
        self.assertIn("const replacing=auditRendered!==null&&auditRendered!==rendered;", LOAD_AUDIT)
        self.assertIn("if(replacing)playEntryMotion($('audit-list'),'--motion-base');", LOAD_AUDIT)
        self.assertEqual(LOAD_AUDIT.count('playEntryMotion('), 1)
        self.assertIn("button.textContent='Coba lagi'", LOAD_AUDIT)
        self.assertIn('Muat catatan sebelumnya', LOAD_AUDIT)
        self.assertIn('ORDER BY sequence DESC', (ROOT / 'beeloft' / 'store.py').read_text(encoding='utf-8'))

    def test_records_are_escaped_neutral_and_jakarta(self):
        self.assertIn('status-chip status-chip-neutral', LOAD_AUDIT)
        self.assertNotRegex(LOAD_AUDIT, r'status-chip-(?:success|warning|danger|info)')
        for fragment in ('${e(item.subject_reference||item.operation)}', '${e(item.operation)} · ${e(item.subject_type)}',
                         '${e(item.actor_name)} · ${e(item.actor_role)}', '${auditStamp(item.created_at)}',
                         'data-action="audit-event" data-id="${e(item.id)}"'):
            self.assertIn(fragment, LOAD_AUDIT)
        self.assertIn('Tidak ada catatan audit yang sesuai filter.', LOAD_AUDIT)
        self.assertIn("timeZone:'Asia/Jakarta'}).format(new Date(value));", APP[APP.index('const auditStamp'):])

    def test_evidence_dialog_keeps_every_field_and_both_raw_documents(self):
        self.assertIn('`Audit · ${item.subject_reference||item.operation}`', AUDIT_DIALOG)
        for label in ('Kategori', 'Operasi', 'Pelaku', 'Waktu Jakarta', 'Objek', 'Referensi', 'Request key'):
            self.assertIn(f"fact('{label}'", AUDIT_DIALOG)
        self.assertIn('${e(item.subject_type)} · ${e(item.subject_id||\'-\')}', AUDIT_DIALOG)
        self.assertIn('${e(item.request_key)}', AUDIT_DIALOG)
        self.assertIn('Input perubahan</h3><pre class="audit-json"', AUDIT_DIALOG)
        self.assertIn('Hasil tersimpan</h3><pre class="audit-json"', AUDIT_DIALOG)
        self.assertIn('${e(JSON.stringify(item.changes,null,2))}', AUDIT_DIALOG)
        self.assertIn('${e(JSON.stringify(item.outcome,null,2))}', AUDIT_DIALOG)
        self.assertIn('data-action="audit-events">Kembali ke audit trail', AUDIT_DIALOG)
        self.assertIn('if(version!==epoch||modal!==dialogVersion||!$(\'dialog\').open)return;', AUDIT_DIALOG)

    def test_no_mutation_action_exists(self):
        for text in (AUDIT, LOAD_AUDIT, AUDIT_DIALOG):
            self.assertNotRegex(text, r'<button[^>]*>(?:Ubah|Hapus|Edit|Delete|Pulihkan|Restore|Replay|Undo|Batalkan)[^<]*<')
        self.assertNotRegex(API, r'@app\.(?:post|put|patch|delete)\([\'"]/api/audit-events')


class BackupTest(unittest.TestCase):
    def test_section_is_one_focused_a6_utility(self):
        self.assertIn('<section id="backup-view" class="workspace-page" hidden>', BACKUP)
        self.assertIn('<h1 class="workspace-title">Cadangan data</h1>', BACKUP)
        self.assertIn('Unduh salinan database Beeloft yang konsisten untuk arsip dan pemulihan.', BACKUP)
        self.assertIn('class="attention-note"', BACKUP)
        self.assertIn('class="info-panel"', BACKUP)
        self.assertIn('<button id="download-backup" type="button" class="action-primary">Unduh cadangan database</button>', BACKUP)
        self.assertIn('id="backup-message"', BACKUP)
        self.assertNotRegex(BACKUP, r'<table|<input|type="file"|status-chip|data-surface')

    def test_security_copy_is_precise(self):
        for truth in ('order, posisi barang, riwayat, kendala, perubahan jadwal, dan akun',
                      'File ini memuat seluruh data produksi dan hash kunci akses akun.',
                      'hanya bisa diakses orang yang berwenang', 'Kunci akses asli tidak disertakan.',
                      'Simpan kunci yang sudah lu miliki untuk masuk setelah pemulihan.',
                      'Salinan diambil saat unduhan diminta; perubahan setelahnya masuk cadangan berikutnya.',
                      '.sqlite3', 'ikuti langkah pemulihan di README proyek', 'Pemulihan tidak dilakukan dari halaman ini.'):
            with self.subTest(truth=truth[:40]):
                self.assertIn(truth, BACKUP)
        self.assertNotRegex(BACKUP, r'(?i)password|kata sandi|berisi kunci akses|riwayat cadangan|terakhir|terjadwal|ukuran database')

    def test_no_restore_or_upload_ui(self):
        self.assertNotRegex(BACKUP + BACKUP_JS, r'(?i)unggah|upload|restore|pulihkan sekarang|ganti database|drop')
        self.assertEqual(len(re.findall(r'<button', BACKUP)), 1)

    def test_admin_gates_guard_and_request_fence(self):
        self.assertIn("$('backup').hidden=me.role!=='admin'", APP)
        self.assertIn("if (user?.role !== 'admin' || guardPending()) return;\n  activateWorkspace('backup');", BACKUP_JS)
        self.assertIn('const version = epoch, request = ++backupRequest;', BACKUP_JS)
        self.assertIn("const current = () => version === epoch && request === backupRequest && view === 'backup' && user?.role === 'admin';", BACKUP_JS)
        self.assertIn('if (!current() || button.disabled || guardPending()) return;', BACKUP_JS)
        self.assertIn('Hanya admin yang dapat mengunduh cadangan database.', API)

    def test_download_lifecycle(self):
        self.assertIn("button.disabled = true; button.textContent = 'Menyiapkan cadangan…';", BACKUP_JS)
        self.assertIn("const blob = await api.download('/api/backup');\n      if (!current()) return;", BACKUP_JS)
        self.assertIn("saveDownload(blob,`beeloft-backup-${new Date().toISOString().replace(/[:.]/g,'-')}.sqlite3`);", BACKUP_JS)
        self.assertIn("'Unduhan dimulai. Periksa daftar unduhan browser untuk memastikan file sudah tersimpan.'", BACKUP_JS)
        self.assertIn("catch (error) { if (current()) fail(error,'backup-message'); }", BACKUP_JS)
        self.assertIn("finally { if (current()) { button.disabled = false; button.textContent = 'Unduh cadangan database'; } }", BACKUP_JS)
        self.assertIn('@app.get("/api/backup"', API)
        self.assertNotIn('@app.post("/api/backup"', API)
        self.assertIn('"Cache-Control": "no-store"', API[API.index('def download_backup'):])


class GlobalTest(unittest.TestCase):
    def test_the_css_block_reaches_only_a66_surfaces(self):
        allowed = ('#activity-', '#audit-', '#backup-', '.activity-', '.audit-', '.backup-')
        selectors = [part.strip() for match in re.finditer(r'([^{}]+)\{', A66_BLOCK)
                     for part in match.group(1).split(',') if part.strip() and not part.strip().startswith('@')]
        self.assertTrue(selectors)
        for selector in selectors:
            with self.subTest(selector=selector[-70:]):
                self.assertTrue(any(name in selector for name in allowed), f'{selector!r} is not an A6.6 surface')

    def test_no_primitive_or_earlier_phase_is_redefined(self):
        for primitive in ('.record-row', '.record-list', '.metric-card', '.metric-strip', '.command-bar', '.timeline',
                          '.timeline-item', '.status-chip', '.info-panel', '.utility-panel', '.attention-note',
                          '.empty-state', '.error-state', '.detail-grid', '.field'):
            self.assertNotRegex(A66_BLOCK, r'(?m)^' + re.escape(primitive) + r'[^{,]*\{')
        for foreign in ('#board-view', '#detail-view', '#materials-view', '#products-view', '#people-view',
                        '#analytics-view', '#ai-view', '#integrations-view', '#approvals-view',
                        '#purchase-requests-view', '#marketing-budgets-view', '#command-center'):
            self.assertNotIn(foreign, A66_BLOCK)
        self.assertNotRegex(A66_BLOCK, r'backdrop-filter|@keyframes|animation\s*:|transition\s*:')

    def test_a67_workspaces_are_migrated_by_a67_not_by_a66(self):
        # A6.6 promised to leave the three business queues alone. A6.7 has since migrated them; what
        # A6.6 still owes is that none of that migration lives in, or leaks through, its own block.
        for element in ('approvals-view', 'purchase-requests-view', 'marketing-budgets-view'):
            with self.subTest(section=element):
                self.assertIn('workspace-page', section(HTML, element))
                self.assertNotIn('#' + element, A66_BLOCK)
        for name in ('#approval-', '#pr-page-', '#marketing-budget-', '#po-', '.queue-', '.request-'):
            with self.subTest(a67=name):
                self.assertNotIn(name, A66_BLOCK)

    def test_frame_timer_budget_and_no_polling(self):
        self.assertEqual(len(re.findall(r'requestAnimationFrame\(', APP)), 6)
        self.assertEqual(len(re.findall(r'cancelAnimationFrame\(', APP)), 4)
        self.assertEqual(len(re.findall(r'setTimeout\(', APP)), 7)
        self.assertEqual(len(re.findall(r'setInterval\(', APP)), 0)
        for text in (LOAD_ACTIVITY, ACTIVITY_EVENT, ACTIVITY_WIRING, LOAD_AUDIT, AUDIT_DIALOG, BACKUP_JS):
            self.assertNotRegex(text, r'setTimeout|setInterval|requestAnimationFrame|EventSource|WebSocket')

    def test_shell_and_lens_are_untouched(self):
        for selector in ('.workspace-window', '.traffic-light', '.masthead', '.app-sidebar', '.nav-selection-lens',
                         '.sidebar-cta', 'body::before'):
            self.assertNotIn(selector, A66_BLOCK)
        lens = APP[APP.index('const navigationSurface ='):APP.index('// Drawer mobile.')]
        self.assertIn('const navigationLensSpring = {mass:1, stiffness:520, damping:40};', lens)
        self.assertIn('<button id="activity" class="nav-item" type="button">', HTML)

    def test_version_schema_and_routes(self):
        version = re.search(r'^version = "([^"]+)"', (ROOT / 'pyproject.toml').read_text(encoding='utf-8'), re.M).group(1)
        self.assertEqual(version, '0.114.0', 'A6.7 is the visible workspace milestone')
        self.assertIn(f'version="{version}"', API)
        contract = json.loads((ROOT / 'docs' / 'openapi.json').read_text(encoding='utf-8'))
        self.assertEqual(contract['info']['version'], version)
        self.assertEqual(len(contract['paths']), 221, 'A6.6 is presentation only')
        versions = [int(value) for path in (ROOT / 'beeloft').glob('*.sql')
                    for value in re.findall(r'PRAGMA user_version\s*=\s*(\d+)', path.read_text(encoding='utf-8'))]
        self.assertEqual(max(versions), 55)

    def test_documentation_exists(self):
        text = (ROOT / 'docs' / 'apple27-activity-audit-backup-modern-workspaces.md').read_text(encoding='utf-8')
        for anchor in ('6014cefaa57647a5bf927f1987b38fe9ab90bb94', '0.112.0', 'activity-view', 'audit-view',
                       'backup-view', 'Asia/Jakarta', 'before_time', 'A6.8'):
            self.assertIn(anchor, text)


if __name__ == '__main__':
    unittest.main()
