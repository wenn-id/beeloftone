"""A2 owns one inert decoration, its geometry and its visibility — not navigation.

A3 took over the final presentation step at the seam A2 reserved for it, so the renderer named
here is now `retargetNavigationLens` and a second frame handle exists beside the measurement
one. Everything else this module asserts is still A2's: one empty non-interactive node, the
scoped legacy fallback, measurement that rejects invalid targets, semantics written before
presentation is asked for, and a measurement frame that runs once and stops. The spring itself
— its configuration, velocity, integrator, settling and idle cost — is asserted in
`test_apple27_navigation_spring_contract.py`.
"""
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
        # A2 required the lens to have no optical treatment at all. A4 gave it one, so what this
        # assertion now defends is A2's actual guarantee: the solid accent-soft selection surface is
        # unconditional, so a browser without backdrop filtering — or a user who has asked for less
        # transparency — still sees a fully rendered selected destination. The glass itself lives
        # inside the feature gate and is the subject of `test_apple27_functional_glass_contract.py`.
        self.assertNotIn('backdrop-filter', block)
        self.assertNotRegex(CSS, r'(?:^|[^-\w])(?:-webkit-)?filter\s*:[^;}]*blur\(')
        self.assertNotRegex(CSS[:CSS.index('@supports')], r'backdrop-filter')

    def test_semantics_precede_decoration_and_geometry_is_separate(self):
        active = JS[JS.index('function activeNavigation('):JS.index('// Registri tujuan workspace')]
        self.assertLess(active.index("setAttribute('aria-current','page')"),
                        active.index('scheduleNavigationLensSync()'))
        self.assertIn('querySelector(\'[aria-current="page"]\')', LENS)
        self.assertNotRegex(LENS, r'setAttribute\([\'"]aria-current|activateWorkspace\(|\.focus\(|api\.|epoch|Request\+\+')
        # A3 replaced the instant apply seam with `retargetNavigationLens`, exactly where A2
        # reserved it. Measurement, visibility and scheduling still belong to A2 and stay here.
        for name in ('measureNavigationTarget', 'retargetNavigationLens', 'hideNavigationLens',
                     'syncNavigationLens', 'scheduleNavigationLensSync'):
            self.assertIn('function ' + name + '(', LENS)
        for coordinate in ('context.clientLeft', 'context.clientTop', 'context.scrollLeft', 'context.scrollTop'):
            self.assertIn(coordinate, LENS)
        for validity in ('isConnected', 'contains(target)', 'getClientRects', 'Number.isFinite',
                         'details:not([open])'):
            self.assertIn(validity, LENS)

    def test_measurement_is_still_a_bounded_one_shot_frame(self):
        """A2's measurement contract, unchanged by A3's physics.

        A3 added an integrator with its own handle; that loop and its constants are the subject
        of `test_apple27_navigation_spring_contract.py`. What is asserted here is that the
        measurement layer did not become part of it: one scheduling site, one nullable handle
        cleared at callback entry, no self-scheduling, and no timer or polling mechanism
        anywhere in the lens region.
        """
        self.assertEqual(LENS.count('requestAnimationFrame(syncNavigationLens)'), 1)
        self.assertIn('navigationLensSyncFrame === null', LENS)
        sync = LENS[LENS.index('function syncNavigationLens()'):LENS.index('function scheduleNavigationLensSync()')]
        self.assertIn('navigationLensSyncFrame = null;', sync)
        self.assertNotIn('requestAnimationFrame', sync)
        self.assertNotIn('scheduleNavigationLensSync', sync)
        # The measurement handle and the motion handle are distinct names, so neither job can
        # silently cancel or inherit the other's frame.
        self.assertIn('let navigationLensSyncFrame = null, navigationLensMotionFrame = null;', LENS)
        self.assertNotRegex(LENS, r'setInterval|setTimeout|\.animate\(|requestIdleCallback'
                                  r'|\bwhile\s*\(\s*true\b')
        for lifecycle in ('clearWorkspace', 'enterWorkspace'):
            self.assertRegex(JS, rf'function {lifecycle}\([^)]*\)\s*\{{\s*hideNavigationLens\(\);')
        # Teardown cancels both frames and discards the physical history with them.
        hide = LENS[LENS.index('function hideNavigationLens()'):LENS.index('function syncNavigationLens()')]
        self.assertIn('cancelNavigationLensMotion(true)', hide)
        self.assertIn('cancelAnimationFrame(navigationLensSyncFrame)', hide)


if __name__ == '__main__':
    unittest.main()
