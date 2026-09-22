"""A2 owns one inert decoration and instant geometry, not navigation or physics."""
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / 'beeloft' / 'static'
HTML = (STATIC / 'index.html').read_text(encoding='utf-8')
CSS = (STATIC / 'style.css').read_text(encoding='utf-8')
JS = (STATIC / 'app.mjs').read_text(encoding='utf-8')
LENS = JS[JS.index('const navigationSurface ='):JS.index('// Drawer mobile.')]


class NavigationLensTest(unittest.TestCase):
    def test_one_empty_decorative_lens_inside_primary_sidebar(self):
        class Markup(HTMLParser):
            inside = False
            lenses = []

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == 'aside':
                    self.inside = attrs.get('id') == 'app-sidebar'
                if 'nav-selection-lens' in attrs.get('class', '').split():
                    self.lenses.append((self.inside, tag, attrs))

            def handle_endtag(self, tag):
                if tag == 'aside':
                    self.inside = False

        parsed = Markup()
        parsed.feed(HTML)
        self.assertEqual(len(parsed.lenses), 1)
        inside, tag, attrs = parsed.lenses[0]
        self.assertTrue(inside)
        self.assertEqual(tag, 'span')
        self.assertEqual(attrs['aria-hidden'], 'true')
        self.assertIn('hidden', attrs)
        for attribute in ('tabindex', 'role', 'aria-label', 'aria-current'):
            self.assertNotIn(attribute, attrs)
        self.assertRegex(HTML, r'id="nav-selection-lens"[^>]*></span>')
        self.assertNotIn('createElement', LENS)
        self.assertNotIn('cloneNode', LENS)

    def test_solid_instant_noninteractive_surface_and_scoped_fallback(self):
        block = re.search(r'\.nav-selection-lens\s*\{([^}]+)\}', CSS).group(1)
        for declaration in ('pointer-events:none', 'transition:none', 'animation:none',
                            'background:var(--color-accent-soft)'):
            self.assertIn(declaration, block)
        self.assertIn('.nav-item[aria-current=page]{background:var(--primary-soft)', CSS)
        self.assertIn('.nav-item[aria-current=page]::before{', CSS)
        self.assertIn('.app-sidebar.nav-lens-ready .nav-item[aria-current=page]{background:transparent}', CSS)
        self.assertIn('.app-sidebar.nav-lens-ready #approvals[aria-current=page]', CSS)
        self.assertRegex(CSS, r'#approvals\[aria-current=page\]\s*\{\s*background:var\(--color-accent-soft\)')
        self.assertNotRegex(CSS, r'backdrop-filter|filter\s*:[^;}]*blur\(')

    def test_semantics_precede_decoration_and_geometry_is_separate(self):
        active = JS[JS.index('function activeNavigation('):JS.index('// Registri tujuan workspace')]
        self.assertLess(active.index("setAttribute('aria-current','page')"),
                        active.index('scheduleNavigationLensSync()'))
        self.assertIn('querySelector(\'[aria-current="page"]\')', LENS)
        self.assertNotRegex(LENS, r'setAttribute\([\'"]aria-current|activateWorkspace\(|\.focus\(|api\.|epoch|Request\+\+')
        for name in ('measureNavigationTarget', 'applyNavigationLensGeometry', 'hideNavigationLens',
                     'syncNavigationLens', 'scheduleNavigationLensSync'):
            self.assertIn('function ' + name + '(', LENS)
        for coordinate in ('context.clientLeft', 'context.clientTop', 'context.scrollLeft', 'context.scrollTop'):
            self.assertIn(coordinate, LENS)
        for validity in ('isConnected', 'contains(target)', 'getClientRects', 'Number.isFinite',
                         'details:not([open])'):
            self.assertIn(validity, LENS)

    def test_bounded_scheduler_has_no_physics_or_idle_loop(self):
        self.assertEqual(LENS.count('requestAnimationFrame('), 1)
        self.assertIn('navigationLensFrame === null', LENS)
        sync = LENS[LENS.index('function syncNavigationLens()'):LENS.index('function scheduleNavigationLensSync()')]
        self.assertNotIn('requestAnimationFrame', sync)
        self.assertNotIn('scheduleNavigationLensSync', sync)
        self.assertNotRegex(LENS, r'setInterval|setTimeout|\.animate\(|velocity|spring|integrat|\bwhile\s*\(')
        for lifecycle in ('clearWorkspace', 'enterWorkspace'):
            self.assertRegex(JS, rf'function {lifecycle}\([^)]*\)\s*\{{\s*hideNavigationLens\(\);')


if __name__ == '__main__':
    unittest.main()
