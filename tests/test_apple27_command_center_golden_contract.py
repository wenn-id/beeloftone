"""A5 presentation boundaries; the browser module checks the rendered report."""
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

from test_apple27_functional_glass_contract import CSS, JS, HTML, DECLARATIONS, FILTERED_GLASS, selectors

ROOT = Path(__file__).resolve().parents[1]
RENDER = JS[JS.index('async function showCommandCenter('):JS.index('async function loadBoard(')]
HOSTS = ('summary content period operations hero channels contribution products attention snapshots message updated').split()


class CommandCenterGoldenTest(unittest.TestCase):
    def test_one_primary_destination_retains_every_runtime_host(self):
        class Markup(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids = []

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if 'id' in attrs:
                    self.ids.append(attrs['id'])

        parsed = Markup()
        parsed.feed(HTML)
        for name in ['view', 'context', 'capacity', *HOSTS]:
            self.assertEqual(parsed.ids.count('command-center-' + name), 1)
        self.assertEqual(JS.count("'command-center':'command-center-view'"), 1)
        self.assertIn('<dl id="command-center-summary"', HTML)
        self.assertIn('role="img" aria-label="${e(caption)}"', JS)

    def test_request_lifecycle_and_new_context_cleanup(self):
        ordered = ['guardPending()', "activateWorkspace('command-center')", '++commandCenterRequest',
                   "api.get('/api/command-center')", "version!==epoch||request!==commandCenterRequest||view!=='command-center'",
                   "$('command-center-summary').innerHTML", 'commandCenterReport=true']
        positions = [RENDER.index(value) for value in ordered]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("refresh&&commandCenterReport&&markRefreshing('command-center-content')", RENDER)
        self.assertIn("settleRefreshing('command-center-content')", RENDER)
        failure = RENDER[RENDER.index('}catch(error)'):]
        self.assertIn('commandCenterReport=false', failure)
        self.assertIn("'command-center-context'", failure)
        self.assertIn("'command-center-capacity'", failure)
        teardown = JS[JS.index('function clearWorkspace('):JS.index('const LOGOUT_FAILED')]
        self.assertIn("'command-center-context'", teardown)
        self.assertIn("'command-center-capacity'", teardown)
        self.assertEqual(re.findall(r'api\.\w+\([^\n;]+', RENDER), ["api.get('/api/command-center')"])

    def test_ambient_layer_is_static_css_and_scoped_to_the_active_page(self):
        environment = [(selector, declaration) for _, selector, declaration in DECLARATIONS
                       if selector and '::before' in selector and '#command-center-view' in selector]
        self.assertTrue(environment)
        self.assertTrue(all(':not([hidden])' in selector for selector, _ in environment))
        declarations = ';'.join(value for _, value in environment)
        self.assertIn('pointer-events:none', declarations)
        self.assertIn('radial-gradient', declarations)
        self.assertNotRegex(declarations, r'filter:|animation:|transition:|url\(')
        self.assertNotRegex(RENDER, r'requestAnimationFrame|setTimeout|setInterval|createElement\(.canvas')

    def test_content_never_enters_the_filtered_chrome_set(self):
        self.assertEqual(selectors(r'backdrop-filter\s*:\s*(?!none)'), FILTERED_GLASS)
        self.assertEqual(CSS.count('@supports'), 1)
        self.assertNotRegex(CSS, r'@font-face|@import|https?://')
        self.assertNotRegex(HTML, r'<(?:video|canvas)\b')
        self.assertEqual(re.findall(r'<img[^>]+src="([^"]+)"', HTML),
                         ['/static/wallpaper-landscape.webp', '/static/wallpaper-mist.webp'])

    def test_existing_truth_fields_and_priority_order_drive_the_new_panels(self):
        for field in ('pending_count','pending_amount','pending_without_amount','by_kind'):
            self.assertIn('report.approvals.' + field, RENDER)
        self.assertIn('approvalKind[kind]', RENDER)
        self.assertIn('report.integrations.systems.map', RENDER)
        for state in ('healthy','failed','stale','incomplete'):
            self.assertIn("row.health==='" + state + "'", RENDER)
        self.assertIn('report.attention.map', RENDER)
        self.assertNotIn('report.attention.sort', RENDER)
        self.assertIn('report.status.attention_count', RENDER)
        self.assertNotRegex(RENDER, r'health.score|health.percent|Math\.random|Rp[1-9]')
        for field in ('gross_revenue','completed_orders','units','unmatched_refunds'):
            self.assertIn('stat.' + field, RENDER)

    def test_no_new_idle_work_or_replacement_physics(self):
        self.assertIn('const navigationLensSpring = {mass:1, stiffness:520, damping:40};', JS)
        self.assertIn('const LENS_SETTLE_DISTANCE = .25, LENS_SETTLE_SPEED = 2;', JS)
        self.assertIn('const LENS_MAX_SUBSTEP = 1/120, LENS_MAX_FRAME = .032, LENS_STALL = .2;', JS)
        self.assertIn('const LENS_MORPH_MAX = .07, LENS_MORPH_SPEED = 3000;', JS)
        for call, count in [('requestAnimationFrame',6),('cancelAnimationFrame',3),('setTimeout',7),('setInterval',0)]:
            self.assertEqual(len(re.findall(r'\b' + call + r'\(', JS)), count)


if __name__ == '__main__':
    unittest.main()
