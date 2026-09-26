"""A6.3 - People + Scan workflows: the static half of the migration contract.

A6.0 built the shared inner-workspace language, A6.1 spent it on Produksi, A6.2 on the two
master-data workspaces, and A6.3 spends it on three *workflow* surfaces: the daily roster
(`#people-view`), the production bundle scanner (`#bundle-scan-view`), the finished-goods scanner
(`#finished-goods-scan-view`), the People dialogs that ARE the People workflow, and the two result
dialogs the scanners exist to open.

Three workspaces with three different jobs makes this mostly an *identity* contract, and a second
thing besides: a contract that they did not collapse into one another, into Produksi, into Bahan
baku, or into a KPI dashboard. So what is asserted here is

  * People is roster-centric - a record list of people, a compact six-cell daily state, a command
    bar the user submits on purpose - and the two scanners are scan-surface utilities that consume
    the `.scan-target` / `.scan-state` family A6.0 reserved for exactly this phase;
  * the roster's six figures are the six that already existed, computed from every matching ACTIVE
    employee rather than from the filtered rows, and no seventh figure is derived - no productivity
    score, no attendance health, no scan rate, no stock health;
  * `workforcePage()` still walks every page (limit 500, offset = accumulated count) rather than
    reading one;
  * the roster's four attendance states, their post-join filter semantics, the Jakarta default date
    and its `max` are unchanged, and the search is still submitted rather than typed into the network;
  * attendance is still one record per employee per date, corrections still carry
    `expected_revision`, and `present` is still the only status that enables the clock fields;
  * approval still only grants permission - it never records attendance - and the copy still says so;
  * the scanners still speak to exactly `/api/bundles/scan` and
    `/api/finished-goods-receipts/scan`, still with `?code=`, still GET, with no camera and no new
    scanning library;
  * one shared `scanRequest` generation still protects both scanners, autofocus still yields to an
    open drawer, and the success tint is still the one `SCAN_TINT_HOLD` system A6.0 shipped;
  * the bundle detail's twelve actions and the finished-goods detail's nineteen are all still
    present, with their `data-action`, `data-kind` and ids intact, and every role/state gate is
    still the same JS comparison - none moved to CSS;
  * finished-goods inventory keeps quantity / available / reserved as three separate figures and
    keeps `sellable` / `hold` / `damaged` as their own words;
  * all four blocking counts stay visible, and the reversal gate still requires all four to be zero;
  * the A5.2 shell, the A5.3 lens, the A3 spring and the frame/timer budget are untouched;
  * A6.1 Produksi and A6.2 Bahan baku / Master SKU are not regressed;
  * no route, no schema, no migration.

The behavioural half lives in tests/browser_people_scan_modern_workspaces.cjs. The containment
half - that A6 primitives reached exactly these three workspaces and their named dialogs and
nothing else - stays in tests/test_apple27_modern_workspace_foundation_contract.py, whose
allow-list A6.3 widened on purpose; what this file adds is the mirror image, that the A6.3 CSS
block cannot reach a fourth page.
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
PRIMITIVES = (STATIC / 'workspace-primitives.css').read_text(encoding='utf-8')
SHELL = (STATIC / 'workspace.css').read_text(encoding='utf-8')


def section(html, element_id):
    """The complete markup of one `<section id=...>`, nested sections included."""
    start = html.index(f'<section id="{element_id}"')
    depth = 0
    for match in re.finditer(r'<section\b|</section>', html[start:]):
        depth += 1 if match.group().startswith('<section') else -1
        if depth == 0:
            return html[start:start + match.end()]
    raise AssertionError(f'#{element_id} is not a closed section')


def code(source):
    """`source` with its comments removed.

    Every "this must not appear" assertion runs against this rather than the raw text: the A6.3
    renderers are heavily commented and several of those comments necessarily NAME the thing being
    ruled out - "bukan enam KPI", "tidak ada status yang dikarang". String literals are left
    intact, because the markup lives inside template literals and that markup is the subject.
    """
    return re.sub(r'(?<!:)//[^\n]*', '', re.sub(r'/\*.*?\*/', '', source, flags=re.S))


def code_css(source):
    return re.sub(r'/\*.*?\*/', '', source, flags=re.S)


def renderer(name):
    """One top-level declaration's body from app.mjs, function or arrow const alike."""
    start = re.search(r'^(?:async )?(?:function|const) ' + re.escape(name) + r'\b', APP, re.M)
    assert start, f'{name} is missing from app.mjs'
    following = re.search(r'^(?:async )?function \w+\(|^const \w+ =|^let \w+ =',
                          APP[start.end():], re.M)
    return APP[start.start():start.end() + (following.start() if following else len(APP))]


APP_CODE = code(APP)
PEOPLE = section(HTML, 'people-view')
BUNDLE_SCAN = section(HTML, 'bundle-scan-view')
GOODS_SCAN = section(HTML, 'finished-goods-scan-view')
BOARD = section(HTML, 'board-view')
MATERIALS = section(HTML, 'materials-view')
PRODUCTS = section(HTML, 'products-view')

# The A6.3 containment block: from its first selector to the end of the stylesheet. Its A6.2
# counterpart is now bounded above by this same marker, so the blocks are checked separately and
# neither test can silently start covering the other's rules.
A63_MARKER = '#people-view,#bundle-scan-view,#finished-goods-scan-view{max-width:1360px'
# A6.4 appended the Analitik block after this one, so A6.3's slice is now bounded above by the
# A6.4 marker - the same deliberate act A6.2 performed when A6.3 arrived. Without it every rule
# A6.4 writes would be read as an A6.3 rule and fail A6.3's own containment gate.
A64_MARKER = '#analytics-view{max-width:1360px'
A63_BLOCK = code_css(CSS)[code_css(CSS).index(A63_MARKER):code_css(CSS).index(A64_MARKER)]

LOAD_PEOPLE = renderer('loadPeople')
SHOW_PEOPLE = renderer('showPeople')
SHOW_SCANNER = renderer('showScanner')
BUNDLE_DIALOG = renderer('bundleDialog')
GOODS_DIALOG = renderer('finishedGoodsReceiptDialog')
ATTENDANCE_FORM = renderer('workforceAttendanceForm')
EMPLOYEE_FORM = renderer('workforceEmployeeForm')
REQUEST_FORM = renderer('workforceRequestForm')
REQUESTS_DIALOG = renderer('workforceRequestsDialog')
REQUEST_DIALOG = renderer('workforceRequestDialog')

PEOPLE_RENDERERS = ('loadPeople', 'workforceEmployeeMasterDialog', 'workforceEmployeeForm',
                    'workforceEmployeeHistoryDialog', 'workforceAttendanceForm',
                    'workforceAttendanceHistoryDialog', 'workforceRequestsDialog',
                    'workforceRequestForm', 'workforceRequestDialog',
                    'workforceRequestDecisionForm')
SCAN_RENDERERS = ('showScanner', 'bundleDialog', 'finishedGoodsReceiptDialog')


def uses(text, primitive):
    """Whole-token class match, exactly as the A6.0 containment test models it."""
    return re.search(r'class="[^"]*(?<![\w-])' + re.escape(primitive) + r'(?![\w-])', text)


class MigrationHappenedTest(unittest.TestCase):
    """The door A6.3 opened in the A6.0 allow-list has to be earning its keep."""

    def test_people_is_a_modern_workspace_page(self):
        for primitive in ('workspace-page', 'workspace-heading', 'workspace-heading-copy',
                          'workspace-title', 'workspace-subtitle', 'workspace-actions',
                          'metric-strip', 'command-bar', 'command-filters', 'command-filter',
                          'command-search', 'command-actions', 'info-panel', 'workspace-subhead',
                          'workspace-section-title', 'workspace-meta'):
            with self.subTest(primitive=primitive):
                self.assertTrue(uses(PEOPLE, primitive), f'#people-view must consume .{primitive}')

    def test_people_identity_is_the_workspace_not_a_slogan(self):
        self.assertIn('<h1 class="workspace-title">People</h1>', PEOPLE)
        self.assertIn('Pantau kehadiran, jam kerja, lembur, dan status tim.', PEOPLE)
        # The legacy heading block and its eyebrow are gone, not restyled.
        for legacy in ('page-heading', 'eyebrow', 'filters', 'search-field', 'workforce-summary'):
            with self.subTest(legacy=legacy):
                self.assertFalse(uses(PEOPLE, legacy), f'.{legacy} must not survive in #people-view')

    def test_the_roster_is_the_visual_centre(self):
        # A record list of people, written by loadPeople - not a table, and not a card grid.
        self.assertRegex(LOAD_PEOPLE, r'class="record-list"')
        self.assertRegex(LOAD_PEOPLE, r'class="record-row" data-workforce-employee=')
        self.assertNotRegex(code(LOAD_PEOPLE), r'<table')
        # The roster host keeps the exact class the motion contract addresses it by.
        self.assertIn('<div id="workforce-list" class="list-host"></div>', PEOPLE)
        # Summary sits above the command bar, and the roster below it: identity, state, controls, rows.
        self.assertLess(PEOPLE.index('id="workforce-summary"'), PEOPLE.index('id="workforce-filter"'))
        self.assertLess(PEOPLE.index('id="workforce-filter"'), PEOPLE.index('id="workforce-list"'))

    def test_people_rows_use_the_a6_record_grammar_and_keep_their_heading(self):
        for primitive in ('record-row-copy', 'record-row-aside', 'data-primary', 'data-secondary',
                          'data-meta', 'chip-row', 'status-chip', 'status-dot', 'metric-icon'):
            with self.subTest(primitive=primitive):
                self.assertTrue(uses(LOAD_PEOPLE, primitive))
        # The employee name stays a heading: a roster row is a record about a person.
        self.assertIn('<h3 class="data-primary">${e(employee.name)}</h3>', LOAD_PEOPLE)
        # No fabricated avatar, and no generated initials.
        for forbidden in ('avatar', 'initial', 'gravatar', 'photo'):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, code(LOAD_PEOPLE).lower())

    def test_both_scanners_consume_the_reserved_scan_surface_family(self):
        for name, markup in (('bundle', BUNDLE_SCAN), ('finished goods', GOODS_SCAN)):
            for primitive in ('workspace-page', 'workspace-heading', 'workspace-title',
                              'workspace-subtitle', 'scan-surface', 'scan-target', 'scan-state',
                              'field', 'field-label', 'field-actions', 'action-primary'):
                with self.subTest(scanner=name, primitive=primitive):
                    self.assertTrue(uses(markup, primitive),
                                    f'the {name} scanner must consume .{primitive}')
            # The legacy filter-form shell the scanners used to borrow is gone.
            for legacy in ('filter-form', 'page-heading', 'form-actions', 'form-info'):
                with self.subTest(scanner=name, legacy=legacy):
                    self.assertFalse(uses(markup, legacy))

    def test_the_scan_result_is_a_focused_a6_record(self):
        self.assertRegex(SHOW_SCANNER, r'class="scan-recent"')
        self.assertRegex(SHOW_SCANNER, r'class="record-row"')
        self.assertRegex(SHOW_SCANNER, r'class="data-primary">\$\{e\(row\.reference\)\}')
        # The legacy production-event card is no longer the scanner's result shell.
        self.assertFalse(uses(code(SHOW_SCANNER), 'material-event'))

    def test_both_result_dialogs_are_modernised(self):
        for name, body in (('bundle', BUNDLE_DIALOG), ('finished goods', GOODS_DIALOG)):
            for primitive in ('utility-panel', 'utility-panel-title', 'utility-rows', 'record-row',
                              'detail-grid', 'detail-field', 'status-chip', 'action-row',
                              'action-secondary', 'action-destructive', 'info-panel', 'panel-grid'):
                with self.subTest(dialog=name, primitive=primitive):
                    self.assertTrue(uses(body, primitive), f'{name} detail must consume .{primitive}')
            # The legacy `.actions` capsule wall and `.form-info` header are gone.
            for legacy in ('form-info', 'material-event'):
                with self.subTest(dialog=name, legacy=legacy):
                    self.assertFalse(uses(code(body), legacy))

    def test_every_migrated_renderer_actually_speaks_a6(self):
        # Most renderers emit markup directly. The three forms do not contain a single literal
        # `class="` on purpose: they are composed entirely from the A6 field helpers, which is the
        # stronger form of the same guarantee - a form cannot drift away from the grammar it does
        # not spell out itself.
        composed = {'workforceEmployeeForm', 'workforceRequestForm', 'workforceRequestDecisionForm'}
        for name in PEOPLE_RENDERERS + SCAN_RENDERERS:
            body = renderer(name)
            with self.subTest(renderer=name):
                if name in composed:
                    self.assertRegex(body, r'workforceField\(|workforceSelect\(|workforceFact\(',
                                     f'{name} must build its fields from the A6 field helpers')
                    self.assertIn('reasonField(', body)
                    # ...and must not fall back to the legacy wrapping-label helper.
                    self.assertNotRegex(code(body), r'(?<![\w])field\(\'')
                else:
                    self.assertIn('class="', body)

    def test_the_a6_field_helpers_carry_the_grammar_for_the_forms(self):
        for name in ('workforceField', 'workforceSelect', 'workforceFact'):
            body = renderer(name)
            with self.subTest(helper=name):
                self.assertTrue(uses(body, 'field'))
        # Only the two real controls need an id to be labelled by; a fact is not focusable and
        # deliberately carries no `for`/`id` pair, which is also why it cannot collide with one.
        for name in ('workforceField', 'workforceSelect'):
            with self.subTest(helper=name):
                self.assertIn('wf-', renderer(name))
        self.assertNotIn('wf-', renderer('workforceFact'))
        # Explicit `for`/`id` pairing is what keeps every accessible name identical to the wrapping
        # label it replaced, which is the whole reason the browser contract still resolves.
        self.assertIn('<label class="field-label" for="wf-${name}">', renderer('workforceField'))
        self.assertIn('<label class="field-label" for="wf-${name}">', renderer('workforceSelect'))


class PeopleTruthTest(unittest.TestCase):
    """Only real workforce data, and all of it."""

    def test_workforce_page_still_walks_every_page(self):
        body = renderer('workforcePage')
        self.assertIn('limit:500', body)
        self.assertIn('offset:items.length', body)
        self.assertIn('while(page.items.length&&items.length<page.total)', body)

    def test_the_two_sources_and_their_parameters_are_unchanged(self):
        self.assertIn("workforcePage('/api/workforce/employees',{status:'active',q:params.q})",
                      LOAD_PEOPLE)
        self.assertIn("workforcePage('/api/workforce/attendance',{start_date:params.work_date,"
                      "end_date:params.work_date,status:'all',q:params.q})", LOAD_PEOPLE)

    def test_the_six_daily_figures_are_the_six_that_existed(self):
        for label in ('Karyawan aktif', 'Belum dicatat', 'Hadir', 'Cuti', 'Absen', 'Lembur'):
            with self.subTest(label=label):
                self.assertIn(f"['{label}'", LOAD_PEOPLE)
        # Exactly six cells, and each one is a metric card.
        self.assertEqual(LOAD_PEOPLE.count('metric-card${tone'), 1)
        self.assertEqual(len(re.findall(r"\n      \['[^']+',", LOAD_PEOPLE)), 6)

    def test_the_summary_mapping_is_still_the_shipped_arithmetic(self):
        self.assertIn("const recorded=rows.filter(row=>row.attendance)", LOAD_PEOPLE)
        self.assertIn("present=recorded.filter(row=>row.attendance.status==='present')", LOAD_PEOPLE)
        self.assertIn("leave=recorded.filter(row=>row.attendance.status==='leave')", LOAD_PEOPLE)
        self.assertIn("absent=recorded.filter(row=>row.attendance.status==='absent')", LOAD_PEOPLE)
        self.assertIn('overtime=recorded.reduce((total,row)=>total+row.attendance.overtime_minutes,0)',
                      LOAD_PEOPLE)
        self.assertIn('unrecorded=rows.length-recorded.length', LOAD_PEOPLE)
        # Derived from every active employee, not from the filtered rows: narrowing the roster by
        # status must not change the daily truth above it.
        self.assertIn("['Karyawan aktif',rows.length", LOAD_PEOPLE)
        self.assertIn("['Hadir',present.length", LOAD_PEOPLE)
        for forbidden in ("['Karyawan aktif',filtered.length", "['Hadir',filtered"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, LOAD_PEOPLE)

    def test_no_seventh_figure_is_invented(self):
        for invented in ('productivity', 'produktivitas', 'attendance_health', 'kesehatan',
                         'skor', 'score', 'adherence', 'kepatuhan', 'rata-rata', 'average',
                         'trend', 'tren lembur', 'persentase', 'percentage'):
            with self.subTest(invented=invented):
                self.assertNotIn(invented, code(LOAD_PEOPLE).lower())

    def test_the_post_join_filter_semantics_are_unchanged(self):
        self.assertIn("const filtered=rows.filter(row=>params.status==='all'?(true):"
                      "params.status==='unrecorded'?!row.attendance:"
                      "row.attendance?.status===params.status)", LOAD_PEOPLE)

    def test_the_roster_status_values_and_labels_are_unchanged(self):
        for value, label in (('all', 'Semua status'), ('unrecorded', 'Belum dicatat'),
                             ('present', 'Hadir'), ('leave', 'Cuti'), ('absent', 'Absen')):
            with self.subTest(value=value):
                self.assertIn(f'<option value="{value}">{label}</option>', PEOPLE)
        self.assertIn("workforceStatusLabels={present:'Hadir',leave:'Cuti',absent:'Absen',"
                      "unrecorded:'Belum dicatat'}", APP)

    def test_attendance_tone_uses_a_second_channel_and_leave_is_not_alarming(self):
        tone = renderer('workforceStatusTone')
        self.assertIn("present:['success','check-circle']", tone)
        self.assertIn("leave:['info','external']", tone)
        self.assertIn("absent:['warning','alert-triangle']", tone)
        self.assertIn("unrecorded:['neutral','clipboard']", tone)
        # Leave is an approved absence, not a failure: it may never be the danger tone.
        self.assertNotIn("leave:['danger'", tone)

    def test_the_attendance_detail_states_all_say_something_real(self):
        self.assertIn("item?.status==='present'?`${item.clock_in.slice(0,5)}–"
                      "${item.clock_out.slice(0,5)} · kerja ${minuteQty(item.work_minutes)} · "
                      "lembur ${minuteQty(item.overtime_minutes)}`:item?.notes||"
                      "'Belum ada catatan untuk tanggal ini.'", LOAD_PEOPLE)

    def test_the_date_default_and_ceiling_are_still_jakarta_today(self):
        self.assertIn('workforceFilters.work_date = workforceFilters.work_date || jakartaToday()',
                      SHOW_PEOPLE)
        self.assertIn('form.elements.work_date.max = jakartaToday()', SHOW_PEOPLE)

    def test_the_roster_query_is_submitted_not_typed(self):
        self.assertIn("$('workforce-filter').onsubmit = event => { event.preventDefault();"
                      " loadPeople(); }", APP)
        self.assertIn('Tampilkan roster', PEOPLE)
        # No live search: no input/keyup listener and no debounce anywhere near the roster.
        for forbidden in ('workforce-search').split():
            self.assertNotRegex(APP_CODE, re.escape(f"$('{forbidden}').oninput"))
        self.assertNotIn('debounce', APP_CODE.lower())

    def test_the_explanation_survives_as_a_note(self):
        self.assertIn('Karyawan aktif yang belum memiliki catatan tetap ditampilkan.', PEOPLE)
        self.assertIn('Koreksi kehadiran menyimpan revisi baru; catatan lama tetap utuh di riwayat.',
                      PEOPLE)
        self.assertTrue(uses(PEOPLE, 'info-panel'))

    def test_the_three_empty_states_are_distinct_and_never_lie(self):
        self.assertIn('Tidak ada karyawan yang cocok dengan status dan pencarian ini.', LOAD_PEOPLE)
        self.assertIn('Tidak ada karyawan aktif yang cocok dengan pencarian ini.', LOAD_PEOPLE)
        self.assertIn('Belum ada karyawan aktif.', LOAD_PEOPLE)
        # The filtered miss is only claimed when there really are active employees to miss.
        self.assertIn('else if(rows.length)pageState', LOAD_PEOPLE)

    def test_the_load_states_go_through_the_shared_a6_shell(self):
        self.assertIn("pageState('workforce-message','loading','Memuat roster karyawan…')",
                      LOAD_PEOPLE)
        self.assertIn("pageState('workforce-message','error','Roster karyawan gagal dimuat.'",
                      LOAD_PEOPLE)
        self.assertIn("$('workforce-retry').onclick=loadPeople", LOAD_PEOPLE)
        # The host keeps its id, role and `.state` class, and the A6 box is withdrawn in CSS.
        self.assertIn('<p id="workforce-message" class="state" role="status" hidden></p>', PEOPLE)

    def test_the_stale_guards_and_replacement_motion_survive(self):
        self.assertIn('const version = epoch, request = ++peopleRequest', LOAD_PEOPLE)
        self.assertEqual(LOAD_PEOPLE.count(
            "version!==epoch||request!==peopleRequest||view!=='people'"), 1)
        self.assertIn("version===epoch&&request===peopleRequest&&view==='people'", LOAD_PEOPLE)
        self.assertIn('const replacing = workforceRendered !== null && workforceRendered !== rendered',
                      LOAD_PEOPLE)
        self.assertIn("if (replacing) playEntryMotion($('workforce-list'), '--motion-base')",
                      LOAD_PEOPLE)

    def test_the_filter_reset_never_moves_the_work_date(self):
        reset = APP[APP.index("'reset-workforce-filter'"):]
        reset = reset[:reset.index('\n')]
        self.assertIn("form.elements.status.value='all'", reset)
        self.assertIn("form.elements.q.value=''", reset)
        self.assertNotIn('work_date', reset)


class AttendanceAndEmployeeWorkflowTest(unittest.TestCase):
    def test_admin_visibility_stays_in_javascript(self):
        self.assertIn("$('new-employee').hidden = user.role !== 'admin'", SHOW_PEOPLE)
        self.assertIn('id="new-employee"', PEOPLE)
        # No role logic in CSS, on any of the three pages.
        for selector in ('admin', 'viewer', 'operator', 'role'):
            with self.subTest(selector=selector):
                self.assertNotIn(selector, A63_BLOCK)

    def test_the_roster_write_action_is_still_gated_and_history_is_not(self):
        self.assertIn("user.role!=='viewer'?`<button type=\"button\" class=\"action-secondary\" "
                      'data-action="attendance-form"', LOAD_PEOPLE)
        self.assertIn("${item?'Koreksi':'Catat'} kehadiran", LOAD_PEOPLE)
        self.assertIn('data-action="attendance-history"', LOAD_PEOPLE)
        self.assertIn('data-date="${e(params.work_date)}"', LOAD_PEOPLE)

    def test_attendance_is_one_record_per_employee_per_date_with_a_revision(self):
        self.assertIn('expected_revision:current?.revision||0', ATTENDANCE_FORM)
        self.assertIn('Satu catatan per karyawan per tanggal.', ATTENDANCE_FORM)
        self.assertIn('Koreksi menambah revisi baru; catatan lama tetap utuh.', ATTENDANCE_FORM)
        self.assertIn('/attendance`', ATTENDANCE_FORM)

    def test_present_is_the_only_status_that_enables_the_clock_fields(self):
        self.assertIn("const present=form.elements.status.value==='present';"
                      "for(const name of ['clock_in','clock_out','overtime_minutes'])"
                      "{form.elements[name].disabled=!present;form.elements[name].required=present;}"
                      "if(!present){form.elements.clock_in.value='';form.elements.clock_out.value='';"
                      "form.elements.overtime_minutes.value='0';}", ATTENDANCE_FORM)
        self.assertIn("form.elements.status.onchange=toggle;toggle();", ATTENDANCE_FORM)

    def test_new_attendance_keeps_its_shipped_defaults_and_readonly_date(self):
        self.assertIn("form.elements.clock_in.value='08:00'", ATTENDANCE_FORM)
        self.assertIn("form.elements.clock_out.value='17:00'", ATTENDANCE_FORM)
        self.assertIn('required readonly value="${e(workDate)}"', ATTENDANCE_FORM)

    def test_the_attendance_payload_is_unchanged(self):
        for field in ('work_date', 'expected_revision', 'status', 'clock_in', 'clock_out',
                      'overtime_minutes', 'notes', 'reason'):
            with self.subTest(field=field):
                self.assertIn(f'{field}:', ATTENDANCE_FORM)
        self.assertIn('clock_in:present?data.get(\'clock_in\'):null', ATTENDANCE_FORM)
        self.assertIn('overtime_minutes:present?Number(data.get(\'overtime_minutes\')):0',
                      ATTENDANCE_FORM)

    def test_the_notes_label_is_exactly_the_word_it_has_always_been(self):
        # The accessible name is a contract; an "optional" marker inside the label would change it.
        self.assertIn('<label class="field-label" for="wf-notes">Catatan</label>', ATTENDANCE_FORM)

    def test_the_employee_code_rule_is_stated_and_never_editable(self):
        self.assertIn('Kode dinormalisasi menjadi huruf besar dan tidak dapat dipakai ulang.',
                      EMPLOYEE_FORM)
        self.assertIn('Kode karyawan tidak dapat diubah.', EMPLOYEE_FORM)
        self.assertIn("workforceFact('Kode karyawan'", EMPLOYEE_FORM)
        # The edit branch renders the code as a fact, never as an input.
        self.assertNotIn("workforceField('code'", EMPLOYEE_FORM.split('changing?')[1].split(':')[0])

    def test_the_employee_field_limits_and_revision_are_unchanged(self):
        self.assertIn("workforceField('code','Kode karyawan','text','required maxlength=\"40\" "
                      "autocomplete=\"off\"')", EMPLOYEE_FORM)
        self.assertIn("workforceField('name','Nama karyawan','text','required maxlength=\"160\"')",
                      EMPLOYEE_FORM)
        self.assertIn("workforceField('department','Departemen','text','required maxlength=\"160\"')",
                      EMPLOYEE_FORM)
        self.assertIn('expected_revision:employee.revision', EMPLOYEE_FORM)
        self.assertIn('maxlength="1000"', renderer('reasonField'))

    def test_both_histories_are_timelines_that_collapse_nothing(self):
        for name, anchor in (('workforceEmployeeHistoryDialog', 'Riwayat karyawan'),
                             ('workforceAttendanceHistoryDialog', 'Riwayat kehadiran')):
            body = renderer(name)
            with self.subTest(dialog=name):
                self.assertIn('limit=100', body)
                self.assertTrue(uses(body, 'timeline'))
                self.assertTrue(uses(body, 'timeline-item'))
                self.assertIn('Revisi ${n(item.revision)}', body)
                self.assertIn('Menampilkan 100 revisi terbaru.', body)
                self.assertIn(anchor, body)
                # No pagination the shipped dialog never had.
                self.assertNotIn('Muat catatan sebelumnya', body)


class LeaveAndOvertimeWorkflowTest(unittest.TestCase):
    def test_the_approval_distinction_is_stated_in_both_places(self):
        self.assertIn('Approval memberi izin; kehadiran aktual tetap dicatat terpisah',
                      REQUESTS_DIALOG)
        self.assertIn('Permintaan masuk ke inbox approval. Persetujuan tidak otomatis mencatat '
                      'kehadiran aktual.', REQUEST_FORM)
        self.assertIn('Persetujuan tidak otomatis mencatat kehadiran aktual', REQUEST_DIALOG)

    def test_the_request_filters_and_their_values_are_unchanged(self):
        for value in ('all', 'submitted', 'approved', 'rejected', 'cancelled'):
            with self.subTest(status=value):
                self.assertIn(f'<option value="{value}">', REQUESTS_DIALOG)
        for value in ('all', 'leave', 'overtime'):
            with self.subTest(kind=value):
                self.assertIn(f'<option value="{value}">', REQUESTS_DIALOG)
        self.assertIn('Tampilkan permintaan', REQUESTS_DIALOG)
        self.assertIn('form.onsubmit=event=>{event.preventDefault();load();}', REQUESTS_DIALOG)

    def test_the_request_summary_comes_only_from_the_api(self):
        for label, source in (('Total', 'report.total'), ('Menunggu', 'report.summary.submitted'),
                              ('Disetujui', 'report.summary.approved'),
                              ('Cuti', 'report.summary.leave'),
                              ('Lembur', 'report.summary.overtime')):
            with self.subTest(label=label):
                self.assertIn(f"['{label}',{source}", REQUESTS_DIALOG)

    def test_each_request_record_keeps_every_field(self):
        for field in ('item.reference', 'item.department', 'item.code', 'item.employee_name',
                      'item.kind', 'item.start_date', 'item.end_date', 'item.overtime_minutes',
                      'item.reason', 'item.status'):
            with self.subTest(field=field):
                self.assertIn(field, REQUESTS_DIALOG)
        self.assertIn('Rincian</button>', REQUESTS_DIALOG)

    def test_the_request_form_refuses_to_render_without_active_employees(self):
        self.assertIn("workforcePage('/api/workforce/employees',{status:'active'})", REQUEST_FORM)
        self.assertIn("if(!employees.items.length){notify('Tambahkan karyawan aktif sebelum "
                      "membuat permintaan.');return;}", REQUEST_FORM)

    def test_overtime_couples_the_end_date_and_requires_the_minutes(self):
        self.assertIn("const overtime=form.elements.kind.value==='overtime';"
                      'form.elements.end_date.readOnly=overtime;'
                      'form.elements.overtime_minutes.disabled=!overtime;'
                      'form.elements.overtime_minutes.required=overtime;', REQUEST_FORM)
        self.assertIn('if(overtime)form.elements.end_date.value=form.elements.start_date.value',
                      REQUEST_FORM)
        self.assertIn("end_date:kind==='overtime'?start:data.get('end_date')", REQUEST_FORM)

    def test_the_request_detail_keeps_its_identity_line_and_every_fact(self):
        # `reference · status` stays one text node: it is the sentence an operator comes back for.
        self.assertIn('<p class="workspace-meta">${e(item.reference)} · '
                      '${e(approvalStatus[item.status])}</p>', REQUEST_DIALOG)
        for fact in ('item.code', 'item.employee_name', 'item.department', 'item.employee_active',
                     'item.kind', 'item.start_date', 'item.end_date', 'item.days',
                     'item.overtime_minutes', 'item.reason', 'item.actor_name', 'item.created_at'):
            with self.subTest(fact=fact):
                self.assertIn(fact, REQUEST_DIALOG)
        self.assertIn(' · karyawan nonaktif', REQUEST_DIALOG)
        self.assertTrue(uses(REQUEST_DIALOG, 'timeline-item'), 'decision history is a timeline')

    def test_the_decision_permissions_are_exactly_the_shipped_comparisons(self):
        self.assertIn("const pending=item.status==='submitted',"
                      "canCancel=pending&&user.role==='operator'&&user.id===item.actor_id",
                      REQUEST_DIALOG)
        self.assertIn("pending&&user.role==='admin'?", REQUEST_DIALOG)
        self.assertIn('data-status="approved"', REQUEST_DIALOG)
        self.assertIn('data-status="rejected"', REQUEST_DIALOG)
        self.assertIn('data-status="cancelled"', REQUEST_DIALOG)

    def test_the_decision_payload_and_endpoint_are_unchanged(self):
        decision = renderer('workforceRequestDecisionForm')
        self.assertIn('expected_revision:item.revision', decision)
        self.assertIn('/decisions`', decision)
        self.assertIn('Keputusan tersimpan permanen di riwayat approval.', decision)
        self.assertIn('reason:new FormData(form).get(\'reason\').trim()', decision)


class ScannerContractTest(unittest.TestCase):
    def test_the_scanner_identities_are_utilities_not_dashboards(self):
        self.assertIn('<h1 class="workspace-title">Scan bundle</h1>', BUNDLE_SCAN)
        self.assertIn('Pindai label bundle untuk membuka identitas dan statusnya.', BUNDLE_SCAN)
        self.assertIn('<h1 class="workspace-title">Scan barang jadi</h1>', GOODS_SCAN)
        self.assertIn('Pindai label penerimaan barang jadi untuk membuka rincian stok.', GOODS_SCAN)
        # No metric strip, no KPI, no dashboard on a scanner page.
        for name, markup in (('bundle', BUNDLE_SCAN), ('finished goods', GOODS_SCAN)):
            for forbidden in ('metric-strip', 'metric-card', 'data-surface', 'progress-meter'):
                with self.subTest(scanner=name, forbidden=forbidden):
                    self.assertFalse(uses(markup, forbidden))

    def test_the_input_attributes_and_ids_are_preserved_exactly(self):
        for element_id, markup, label in (('bundle-scan-code', BUNDLE_SCAN, 'Kode bundle'),
                                          ('finished-goods-scan-code', GOODS_SCAN,
                                           'Kode barang jadi')):
            with self.subTest(input=element_id):
                self.assertIn(f'<label class="field-label" for="{element_id}">{label}</label>',
                              markup)
                field = markup[markup.index(f'<input id="{element_id}"'):]
                field = field[:field.index('>')]
                for attribute in ('name="code"', 'type="search"', 'required', 'maxlength="200"',
                                  'autocomplete="off"', 'autocapitalize="characters"',
                                  'spellcheck="false"'):
                    self.assertIn(attribute, field, f'{element_id} must keep {attribute}')

    def test_each_scanner_form_has_exactly_one_submit_and_keeps_its_hosts(self):
        for kind, markup, label in (('bundle', BUNDLE_SCAN, 'Buka bundle'),
                                    ('finished-goods', GOODS_SCAN, 'Buka barang jadi')):
            with self.subTest(scanner=kind):
                self.assertEqual(markup.count('type="submit"'), 1)
                self.assertIn(f'>{label}</button>', markup)
                self.assertIn(f'<form id="{kind}-scan-form" class="scan-surface">', markup)
                self.assertIn(f'<p id="{kind}-scan-message" class="state scan-state" '
                              'role="status" hidden></p>', markup)
                self.assertIn(f'<p id="{kind}-scan-error" class="error" role="alert" hidden></p>',
                              markup)
                self.assertIn(f'<div id="{kind}-scan-result" class="scan-result" '
                              'aria-live="polite"></div>', markup)

    def test_the_hardware_instruction_stays_next_to_the_input(self):
        for markup in (BUNDLE_SCAN, GOODS_SCAN):
            self.assertIn('Scanner USB/Bluetooth bekerja seperti keyboard', markup)
            self.assertIn('lalu tekan Enter.', markup)
            self.assertTrue(uses(markup, 'scan-state'))
        # No camera scanning is introduced anywhere.
        for forbidden in ('getUserMedia', 'BarcodeDetector', 'mediaDevices', 'webrtc',
                          'jsqr', 'quagga', 'zxing'):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden.lower(), APP_CODE.lower())

    def test_the_two_endpoints_are_untouched(self):
        self.assertIn("(kind==='bundle'?'/api/bundles/scan?':'/api/finished-goods-receipts/scan?')"
                      "+new URLSearchParams({code:input.value.trim()})", SHOW_SCANNER)
        self.assertIn('api.get(', SHOW_SCANNER)
        self.assertNotIn('api.post', SHOW_SCANNER)

    def test_autofocus_yields_to_an_open_drawer(self):
        self.assertIn("const drawerOpen=document.body.classList.contains('nav-open')", SHOW_SCANNER)
        self.assertIn('if(!drawerOpen)input.focus();', SHOW_SCANNER)
        # The flag is read BEFORE activateWorkspace, which is what closes the drawer.
        self.assertLess(SHOW_SCANNER.index('drawerOpen=document.body'),
                        SHOW_SCANNER.index("activateWorkspace('scan-'+kind)"))

    def test_one_shared_generation_guard_protects_both_scanners(self):
        self.assertEqual(len(re.findall(r'\blet scanRequest\b|scanRequest = 0', APP)), 1)
        self.assertIn('let request=++scanRequest;', SHOW_SCANNER)
        self.assertIn('const current=()=>version===epoch&&request===scanRequest&&view===prefix;',
                      SHOW_SCANNER)
        self.assertIn('request=++scanRequest; button.disabled=true;', SHOW_SCANNER)

    def test_the_submission_lifecycle_is_unchanged(self):
        self.assertIn('event.preventDefault(); if(!current()||button.disabled||guardPending())return;',
                      SHOW_SCANNER)
        self.assertIn('clearScanFeedback(result); result.replaceChildren();', SHOW_SCANNER)
        self.assertIn("message(prefix+'-error',''); message(prefix+'-message','Mencari hasil scan…');",
                      SHOW_SCANNER)
        self.assertIn('finally{if(current())button.disabled=false;}', SHOW_SCANNER)

    def test_success_and_failure_both_leave_the_code_selected(self):
        self.assertIn("message(prefix+'-message',''); input.select();", SHOW_SCANNER)
        self.assertIn("{message(prefix+'-message','');fail(error,prefix+'-error');input.select();}",
                      SHOW_SCANNER)
        # A failed scan may never leave a stale result looking current.
        self.assertLess(SHOW_SCANNER.index('result.replaceChildren()'),
                        SHOW_SCANNER.index('const row=await api.get('))

    def test_the_scan_tint_system_is_reused_not_duplicated(self):
        self.assertIn('playScanFeedback(result);', SHOW_SCANNER)
        self.assertEqual(len(re.findall(r'const SCAN_TINT_HOLD', APP)), 1)
        self.assertEqual(len(re.findall(r'function playScanFeedback', APP)), 1)
        self.assertEqual(len(re.findall(r'function clearScanFeedback', APP)), 1)
        self.assertEqual(APP.count("classList.add('is-scan-ok')"), 1)
        # The tint lives on the result host, so nothing inside it may paint over the feedback.
        self.assertIn('#bundle-scan-result .record-row,#finished-goods-scan-result .record-row',
                      A63_BLOCK)
        self.assertIn('background:none', A63_BLOCK)

    def test_only_the_last_result_is_shown_and_none_is_stored(self):
        self.assertIn('Hasil scan terakhir', SHOW_SCANNER)
        self.assertIn('Belum ada hasil scan. Pindai label atau masukkan kode.', SHOW_SCANNER)
        self.assertEqual(SHOW_SCANNER.count('<li class="record-row">'), 1)
        for forbidden in ('localStorage', 'sessionStorage', 'scanHistory', 'recentScans'):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, code(SHOW_SCANNER))

    def test_the_result_states_only_what_the_scan_endpoint_returns(self):
        for field in ('row.reference', 'row.sku', 'row.size', 'row.quantity',
                      'row.received_quantity', 'row.order_reference', 'row.id'):
            with self.subTest(field=field):
                self.assertIn(field, SHOW_SCANNER)
        self.assertIn('Rincian bundle', SHOW_SCANNER)
        self.assertIn('Rincian barang jadi', SHOW_SCANNER)


class BundleDetailTest(unittest.TestCase):
    ACTIONS = (
        ('bundle-order', 'Buka order produksi'), ('cutting-run', 'Hasil cutting asal'),
        ('material-batch', 'Batch bahan asal'), ('bundles', 'Semua bundle'),
        ('sewing-jobs', 'Sewing / makloon order'), ('bundle-handoffs', 'Riwayat serah-terima'),
        ('new-bundle-handoff', 'Serahkan bundle'), ('accept-bundle-handoff', 'Konfirmasi terima'),
        ('cancel-bundle-handoff', 'Batalkan handoff'), ('new-sewing-job', 'Kirim ke sewing'),
        ('print-bundle', 'Cetak label'), ('reverse-bundle', 'Koreksi bundle'),
    )

    def test_every_action_and_its_hook_survives(self):
        for hook, label in self.ACTIONS:
            with self.subTest(action=hook):
                self.assertIn(f"'{hook}'", BUNDLE_DIALOG)
                self.assertIn(label, BUNDLE_DIALOG)
        self.assertEqual(len(self.ACTIONS), 12)

    def test_the_hierarchy_puts_identity_and_position_before_the_action_catalogue(self):
        order = ('bundle.reference', 'Posisi bundle sekarang', 'Asal bundle', 'bundle-label',
                 'panel-grid')
        positions = [BUNDLE_DIALOG.index(anchor) for anchor in order]
        self.assertEqual(positions, sorted(positions), f'bundle detail order: {order}')

    def test_the_status_truth_is_binary(self):
        self.assertIn("active=bundle.status==='active'", BUNDLE_DIALOG)
        self.assertIn("${active?'Aktif':'Sudah dikoreksi'}", BUNDLE_DIALOG)
        for invented in ('quality', 'kualitas', 'skor', 'health'):
            with self.subTest(invented=invented):
                self.assertNotIn(invented, code(BUNDLE_DIALOG).lower())

    def test_allocation_stays_two_plain_numbers(self):
        self.assertIn('${n(bundle.sewing_allocated_quantity)}', BUNDLE_DIALOG)
        self.assertIn('${n(bundle.sewing_unassigned_quantity)}', BUNDLE_DIALOG)
        # No derived percentage or progress bar over an allocation the API does not express that way.
        self.assertFalse(uses(BUNDLE_DIALOG, 'progress-meter'))
        self.assertNotIn('%', BUNDLE_DIALOG.split('panel-grid')[0].replace('100%', ''))

    def test_a_pending_handoff_is_never_shown_as_a_completed_transfer(self):
        self.assertIn('${e(bundle.custody_location)}', BUNDLE_DIALOG)
        self.assertIn('Menuju ${e(handoff.to_location)}', BUNDLE_DIALOG)
        self.assertIn('menunggu penerima mengonfirmasi', BUNDLE_DIALOG)
        self.assertTrue(uses(BUNDLE_DIALOG, 'attention-note'))

    def test_the_reversal_is_restrained_but_complete(self):
        self.assertIn('Sudah dikoreksi</h3>', BUNDLE_DIALOG)
        for field in ('bundle.reversal.reason', 'bundle.reversal.actor_name',
                      'bundle.reversal.created_at'):
            with self.subTest(field=field):
                self.assertIn(field, BUNDLE_DIALOG)

    def test_the_printable_label_is_untouched(self):
        self.assertIn('<section class="bundle-label" aria-label="Label bundle ${e(bundle.reference)}">',
                      BUNDLE_DIALOG)
        self.assertIn('/api/bundles/${e(encodeURIComponent(bundle.id))}/label.svg', BUNDLE_DIALOG)
        self.assertIn('class="bundle-label-qty"', BUNDLE_DIALOG)
        # The print stylesheet reaches the label as a DIRECT child of #dialog-content.
        self.assertIn('#dialog-content .bundle-label{display:grid!important', CSS)

    def test_every_permission_gate_is_the_shipped_comparison(self):
        self.assertIn("writer=user.role!=='viewer'", BUNDLE_DIALOG)
        self.assertIn("writer&&active&&!handoff&&['new-bundle-handoff'", BUNDLE_DIALOG)
        self.assertIn("writer&&handoff&&handoff.sender_id!==user.id&&['accept-bundle-handoff'",
                      BUNDLE_DIALOG)
        self.assertIn("user.role==='admin'&&handoff&&['cancel-bundle-handoff'", BUNDLE_DIALOG)
        self.assertIn("writer&&active&&bundle.sewing_unassigned_quantity>0&&['new-sewing-job'",
                      BUNDLE_DIALOG)
        self.assertIn("user.role==='admin'&&active&&['reverse-bundle'", BUNDLE_DIALOG)

    def test_the_correction_still_states_what_it_does_not_change(self):
        self.assertIn('Koreksi melepaskan alokasi identitas bundle. Posisi WIP tidak berubah dan '
                      'riwayat asli tetap tersimpan.', BUNDLE_DIALOG)
        self.assertIn('/reverse', BUNDLE_DIALOG)


class FinishedGoodsDetailTest(unittest.TestCase):
    ACTIONS = (
        ('finished-goods-traceability', 'Jejak stok lengkap'),
        ('finished-goods-order', 'Buka order produksi'), ('final-qc-record', 'Final QC asal'),
        ('finishing-record', 'Finishing asal'), ('sewing-job', 'Job sewing asal'),
        ('bundle', 'Bundle asal'), ('finished-goods', 'Semua barang jadi'),
        ('warehouse', 'Gudang order'), ('marketplace-reservations', 'Reservasi order'),
        ('finished-goods-adjustments', 'Riwayat adjustment'),
        ('finished-goods-stock-counts', 'Riwayat stock opname'),
        ('print-finished-goods', 'Cetak label barang jadi'),
        ('new-finished-goods-stock-count', 'Catat stock opname'),
        ('new-finished-goods-adjustment', 'Catat adjustment'),
        ('new-marketplace-reservation', 'Reservasi marketplace'),
        ('new-warehouse-movement', 'Transfer lokasi'), ('new-warehouse-movement', 'Lepaskan hold'),
        ('new-warehouse-movement', 'Tandai damaged'),
        ('reverse-finished-goods', 'Koreksi penerimaan'),
    )

    def test_every_action_and_its_hook_survives(self):
        for hook, label in self.ACTIONS:
            with self.subTest(action=label):
                self.assertIn(f"'{hook}'", GOODS_DIALOG)
                self.assertIn(label, GOODS_DIALOG)
        self.assertEqual(len(self.ACTIONS), 19)

    def test_the_warehouse_movement_kinds_survive(self):
        for kind in ('transfer', 'hold_release', 'hold_damage'):
            with self.subTest(kind=kind):
                self.assertIn(f"'{kind}'", GOODS_DIALOG)
        self.assertIn('data-kind="${kind}"', GOODS_DIALOG)

    def test_inventory_now_sits_above_the_action_catalogue(self):
        order = ('receipt.reference', 'Inventori sekarang', 'Sumber penerimaan', 'Jejak produksi',
                 'finished-goods-label', 'panel-grid')
        positions = [GOODS_DIALOG.index(anchor) for anchor in order]
        self.assertEqual(positions, sorted(positions), f'finished-goods detail order: {order}')

    def test_the_three_inventory_numbers_are_never_merged(self):
        self.assertIn('<dt>Jumlah</dt><dd>${n(row.quantity)}', GOODS_DIALOG)
        self.assertIn('<dt>Available</dt><dd>${n(row.available_quantity)}', GOODS_DIALOG)
        self.assertIn('<dt>Reserved</dt><dd>${n(row.reserved_quantity)}', GOODS_DIALOG)
        # Available and reserved are only claimed for the rows that actually carry them.
        self.assertIn("row.stock_status==='sellable'?`<div class=\"detail-field\"><dt>Available</dt>",
                      GOODS_DIALOG)

    def test_the_stock_statuses_keep_their_own_words(self):
        self.assertIn("stockTone={sellable:'success',hold:'warning',damaged:'danger'", GOODS_DIALOG)
        self.assertIn('warehouseStatus[row.stock_status]', GOODS_DIALOG)
        self.assertIn("warehouseStatus={sellable:'Sellable',hold:'Hold',damaged:'Damaged'", APP)
        for marketing in ('sehat', 'healthy', 'bagus', 'optimal', 'aman dijual'):
            with self.subTest(marketing=marketing):
                self.assertNotIn(marketing, code(GOODS_DIALOG).lower())

    def test_the_receipt_status_truth_is_binary(self):
        self.assertIn("active=receipt.status==='active'", GOODS_DIALOG)
        self.assertIn("${active?'Aktif':'Sudah dikoreksi'}", GOODS_DIALOG)

    def test_all_four_blocking_counts_stay_visible_with_their_real_numbers(self):
        for count, phrase in (('active_movement_count', 'pergerakan gudang aktif'),
                              ('active_reservation_count', 'reservasi marketplace aktif'),
                              ('active_adjustment_count', 'adjustment aktif'),
                              ('active_stock_count_count', 'stock opname aktif')):
            with self.subTest(count=count):
                self.assertIn(f'receipt.{count}', GOODS_DIALOG)
                self.assertIn(phrase, GOODS_DIALOG)
        self.assertIn('.filter(([count])=>count)', GOODS_DIALOG)
        self.assertTrue(uses(GOODS_DIALOG, 'attention-note'))

    def test_the_production_lineage_is_complete(self):
        for reference in ('final_qc_reference', 'finishing_reference', 'sewing_reference',
                          'bundle_reference'):
            with self.subTest(reference=reference):
                self.assertIn(f'receipt.{reference}', GOODS_DIALOG)

    def test_the_receipt_source_is_complete(self):
        for field in ('receipt.location', 'receipt.received_date', 'receipt.scanned_sku'):
            with self.subTest(field=field):
                self.assertIn(field, GOODS_DIALOG)

    def test_the_printable_label_is_untouched(self):
        self.assertIn('class="bundle-label finished-goods-label"', GOODS_DIALOG)
        self.assertIn('/api/finished-goods-receipts/${e(encodeURIComponent(receipt.id))}/label.svg',
                      GOODS_DIALOG)
        self.assertIn('class="bundle-label-qty"', GOODS_DIALOG)

    def test_every_permission_gate_is_the_shipped_comparison(self):
        self.assertIn("writer=user.role!=='viewer'", GOODS_DIALOG)
        self.assertIn("writer&&active&&['new-finished-goods-stock-count'", GOODS_DIALOG)
        self.assertIn("writer&&active&&['new-finished-goods-adjustment'", GOODS_DIALOG)
        self.assertIn("writer&&active&&reservable&&['new-marketplace-reservation'", GOODS_DIALOG)
        self.assertIn("writer&&active&&(sellable||hold||damaged)&&['new-warehouse-movement'",
                      GOODS_DIALOG)
        self.assertIn("writer&&active&&hold&&['new-warehouse-movement','Lepaskan hold'",
                      GOODS_DIALOG)
        self.assertIn("writer&&active&&hold&&['new-warehouse-movement','Tandai damaged'",
                      GOODS_DIALOG)
        # The derivations the gates read are unchanged.
        self.assertIn("sellable=receipt.inventory.some(row=>row.stock_status==='sellable')",
                      GOODS_DIALOG)
        self.assertIn("reservable=receipt.inventory.some(row=>row.stock_status==='sellable'"
                      '&&row.available_quantity>0)', GOODS_DIALOG)

    def test_the_reversal_gate_still_requires_all_four_counts_to_be_zero(self):
        self.assertIn("user.role==='admin'&&active&&!receipt.active_movement_count"
                      '&&!receipt.active_reservation_count&&!receipt.active_adjustment_count'
                      "&&!receipt.active_stock_count_count&&['reverse-finished-goods'",
                      GOODS_DIALOG)

    def test_the_correction_still_states_what_it_does_not_change(self):
        self.assertIn('Koreksi melepaskan klasifikasi sellable/hold tanpa mengubah saldo WIP '
                      'warehouse. Riwayat asli tetap tersimpan.', GOODS_DIALOG)


class ContainmentTest(unittest.TestCase):
    """The mirror image of the widened allow-list: the A6.3 CSS block cannot reach a fourth page."""

    ALLOWED = ('#people-view', '#bundle-scan-view', '#finished-goods-scan-view', '.people-work',
               '#workforce-message', '#workforce-request-message', '#bundle-scan-message',
               '#finished-goods-scan-message', '#bundle-scan-error', '#finished-goods-scan-error',
               '#workforce-revision-note', '#workforce-list', '#workforce-request-list',
               '#workforce-master-list', '#workforce-summary', '#bundle-scan-form',
               '#finished-goods-scan-form', '#bundle-scan-result', '#finished-goods-scan-result',
               '#dialog-content')

    def test_every_selector_is_scoped_to_something_a63_owns(self):
        selectors = [part.strip() for match in re.finditer(r'([^{}]+)\{', A63_BLOCK)
                     for part in match.group(1).split(',')]
        self.assertTrue(selectors)
        for selector in selectors:
            if not selector or selector.startswith('@') or selector.startswith('}'):
                continue
            with self.subTest(selector=selector):
                self.assertTrue(any(name in selector for name in self.ALLOWED),
                                f'{selector} is not scoped to an A6.3 surface')

    def test_no_a6_primitive_is_redefined_and_no_earlier_block_is_touched(self):
        # A bare primitive selector would redesign every migrated workspace at once.
        for primitive in ('.record-row', '.record-list', '.metric-card', '.metric-strip',
                          '.command-bar', '.status-chip', '.timeline-item', '.detail-grid',
                          '.scan-surface', '.scan-target', '.utility-panel', '.field',
                          '.action-primary', '.empty-state', '.error-state'):
            with self.subTest(primitive=primitive):
                self.assertNotRegex(A63_BLOCK, r'(?m)^' + re.escape(primitive) + r'[^{]*\{')
        for foreign in ('#board-view', '#detail-view', '#materials-view', '#products-view',
                        '#order-list', '#batch-list', '#product-list', '#summary',
                        '#issues-summary', '.production-work', '.materials-work', '.products-work'):
            with self.subTest(foreign=foreign):
                self.assertNotIn(foreign, A63_BLOCK)

    def test_the_block_declares_nothing_about_the_shell_or_the_lens(self):
        for selector in ('.app-shell', '.app-sidebar', '.masthead', '.workspace-main', '.nav-item',
                         '.window-controls', 'traffic', 'lens', 'wallpaper', 'shimmer'):
            with self.subTest(selector=selector):
                self.assertNotIn(selector, A63_BLOCK)

    def test_the_block_adds_no_material_and_no_motion(self):
        self.assertNotRegex(A63_BLOCK, r'backdrop-filter|filter\s*:\s*blur')
        self.assertNotRegex(A63_BLOCK, r'@keyframes|animation\s*:|transition\s*:')

    def test_the_retired_legacy_rules_stay_for_the_surfaces_that_still_render_them(self):
        for kept in ('.filters,', '.page-heading', '.search-field{', '.hint', '.form-info{',
                     '.form-grid', '.form-actions', '.filter-form', '.material-event',
                     '.history-item', '.product-list{', '.product-item{', '.scan-result',
                     '.bundle-label', '.list-host', '.state{', '.workforce-summary',
                     '.workforce-row', '.workforce-screen'):
            with self.subTest(kept=kept):
                self.assertIn(kept, CSS, f'{kept} is still used by an unmigrated surface')

    def test_the_migrated_surfaces_stopped_emitting_the_legacy_vocabulary(self):
        for legacy in ('page-heading', 'filters', 'search-field', 'filter-form', 'form-actions'):
            for name, markup in (('people', PEOPLE), ('bundle scan', BUNDLE_SCAN),
                                 ('finished-goods scan', GOODS_SCAN)):
                with self.subTest(legacy=legacy, page=name):
                    self.assertFalse(uses(markup, legacy))
        for legacy in ('workforce-summary', 'workforce-row', 'workforce-row-actions',
                       'workforce-heading', 'product-item', 'history-item'):
            for name in PEOPLE_RENDERERS:
                with self.subTest(legacy=legacy, renderer=name):
                    self.assertFalse(uses(code(renderer(name)), legacy))

    def test_the_people_dialogs_keep_the_wide_dialog_hook(self):
        # `.workforce-screen` is the only thing making a People dialog 960px wide, and the
        # approvals overflow assertions depend on it.
        self.assertEqual(APP.count('class="workforce-screen"'), 5)
        self.assertIn('dialog:has(.workforce-screen)', CSS)

    def test_no_a6_primitive_name_leaks_into_a_stylesheet_or_the_shell_modules(self):
        for text, label in ((CSS, 'style.css'), (SHELL, 'workspace.css')):
            for name in ('scan-surface', 'scan-target', 'scan-recent', 'record-list',
                         'workspace-heading', 'command-bar', 'metric-strip', 'utility-rows'):
                with self.subTest(sheet=label, name=name):
                    self.assertNotRegex(text, r'class="[^"]*(?<![\w-])' + name + r'(?![\w-])')


class FrozenSurfacesTest(unittest.TestCase):
    def test_a61_produksi_markup_is_untouched(self):
        self.assertIn('<h1 class="workspace-title">Produksi</h1>', BOARD)
        self.assertIn('Pantau order, progres, kendala, dan output produksi.', BOARD)
        for primitive in ('metric-strip', 'command-bar', 'attention-note', 'data-surface',
                          'info-panel'):
            with self.subTest(primitive=primitive):
                self.assertTrue(uses(BOARD, primitive))
        self.assertIn('#board-view,#detail-view{max-width:1360px', CSS)
        self.assertIn('#order-list.is-refreshing{opacity:.78}', CSS)
        self.assertIn('#detail-content .utility-rows', CSS)

    def test_a62_bahan_baku_and_master_sku_markup_is_untouched(self):
        self.assertIn('<h1 class="workspace-title">Bahan baku</h1>', MATERIALS)
        self.assertIn('<h1 class="workspace-title">Master SKU</h1>', PRODUCTS)
        self.assertIn('#materials-view,#products-view{max-width:1360px', CSS)
        self.assertIn('#batch-list.is-refreshing,#product-list.is-refreshing{opacity:.78}', CSS)
        for name in ('loadMaterials', 'paintProducts', 'materialBatchScanDialog'):
            with self.subTest(renderer=name):
                self.assertIn('class="', renderer(name))

    def test_the_a52_shell_and_a53_lens_are_untouched(self):
        for selector in ('.app-shell', '.app-sidebar', '.masthead', '.workspace-main',
                         '.nav-item', '.window-controls'):
            with self.subTest(selector=selector):
                self.assertIn(selector, SHELL, f'{selector} must still be owned by the shell')

    def test_the_a3_spring_constants_are_unchanged(self):
        lens = APP[APP.index('const navigationSurface ='):APP.index('// Drawer mobile.')]
        for constant in ('LENS_SETTLE_SPEED = 2', 'LENS_MAX_SUBSTEP = 1/120', 'LENS_MAX_FRAME = .032',
                         'LENS_STALL = .2', 'LENS_MORPH_MAX = .07', 'LENS_MORPH_SPEED = 3000'):
            with self.subTest(constant=constant):
                self.assertIn(constant, APP)
        self.assertEqual(lens.count('requestAnimationFrame('), 3)
        self.assertEqual(lens.count('cancelAnimationFrame('), 3)

    def test_a63_adds_no_frame_no_timer_and_no_polling(self):
        # A6.3 is a presentation phase. The shipped budget is exact, and reusing the one scan-tint
        # timer is precisely why no new one was needed.
        self.assertEqual(len(re.findall(r'requestAnimationFrame\(', APP)), 6)
        self.assertEqual(len(re.findall(r'setTimeout\(', APP)), 7)
        self.assertEqual(len(re.findall(r'setInterval\(', APP)), 0)
        self.assertEqual(sorted(p.name for p in STATIC.iterdir() if p.suffix in ('.mjs', '.js')),
                         ['app.mjs', 'appearance.js', 'client.mjs', 'workspace.mjs'])
        # The inner-workspace language still carries no animation of its own, and A6.3's own block
        # adds none either (asserted separately in ContainmentTest).
        self.assertNotIn('@keyframes', PRIMITIVES)
        self.assertNotRegex(code_css(PRIMITIVES), r'(?<![-\w])animation\s*:')

    def test_the_sidebar_destinations_and_views_are_unchanged(self):
        self.assertIn("'scan-bundle':'bundle-scan-view'", APP)
        self.assertIn("'scan-finished-goods':'finished-goods-scan-view'", APP)
        self.assertIn("{id:'people-view',view:'people',invalidate(){peopleRequest++;}}", APP)
        self.assertIn("{id:'bundle-scan-view',view:'bundle-scan',invalidate(){scanRequest++;}}", APP)
        self.assertIn("{id:'finished-goods-scan-view',view:'finished-goods-scan',"
                      'invalidate(){scanRequest++;}}', APP)


class VersionAndBackendTest(unittest.TestCase):
    def test_version_is_aligned_across_every_source(self):
        version = re.search(r'^version = "([^"]+)"',
                            (ROOT / 'pyproject.toml').read_text(encoding='utf-8'), re.M).group(1)
        self.assertEqual(version, '0.110.0', 'A6.3 is the visible workspace migration milestone')
        self.assertIn(f'version="{version}"', (ROOT / 'beeloft' / 'api.py').read_text(encoding='utf-8'))
        contract = json.loads((ROOT / 'docs' / 'openapi.json').read_text(encoding='utf-8'))
        self.assertEqual(contract['info']['version'], version)

    def test_the_schema_is_untouched(self):
        versions = [int(value) for path in (ROOT / 'beeloft').glob('*.sql')
                    for value in re.findall(r'PRAGMA user_version\s*=\s*(\d+)',
                                            path.read_text(encoding='utf-8'))]
        self.assertEqual(max(versions), 55, 'A6.3 is presentation only')

    def test_no_backend_route_was_added_for_a_visual(self):
        api = (ROOT / 'beeloft' / 'api.py').read_text(encoding='utf-8')
        for invented in ('/attendance-health', '/productivity', '/scan-stats', '/roster-summary',
                         '/stock-health', '/bundle-quality'):
            with self.subTest(route=invented):
                self.assertNotIn(invented, api)

    def test_the_documentation_exists(self):
        doc = ROOT / 'docs' / 'apple27-people-scan-modern-workspaces.md'
        self.assertTrue(doc.exists(), f'{doc} records the A6.3 decisions')
        text = doc.read_text(encoding='utf-8')
        for anchor in ('c7f296a52fa7f97645a959726f339c941a7e97c4', '0.109.0', 'People',
                       'Scan bundle', 'Scan barang jadi'):
            with self.subTest(anchor=anchor):
                self.assertIn(anchor, text)


if __name__ == '__main__':
    unittest.main()
