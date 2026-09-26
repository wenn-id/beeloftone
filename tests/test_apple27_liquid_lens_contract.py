"""A5.3 changes paint within the one A2 object, never its physical or semantic controller."""
import json
from pathlib import Path
import re
import unittest

from test_apple27_functional_glass_contract import parse, walk

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / 'beeloft' / 'static'
JS = (STATIC / 'app.mjs').read_text(encoding='utf-8')
CSS = (STATIC / 'workspace.css').read_text(encoding='utf-8')
LENS = JS[JS.index('const navigationSurface ='):JS.index('// Drawer mobile.')]


class LiquidLensContractTest(unittest.TestCase):
    def test_one_empty_semantically_inert_node_with_pseudo_optics(self):
        html = (STATIC / 'index.html').read_text(encoding='utf-8')
        self.assertEqual(len(re.findall(r'class="nav-selection-lens"', html)), 1)
        self.assertRegex(html, r'<span id="nav-selection-lens" class="nav-selection-lens" aria-hidden="true" hidden></span>')
        self.assertNotRegex(LENS, r'createElement|cloneNode|innerHTML|setAttribute\([\'"]aria-current')
        self.assertIn('.nav-selection-lens[style*="--liquid-stretch"]::before', CSS)
        self.assertIn('.nav-selection-lens[style*="--liquid-stretch"]::after', CSS)
        self.assertIn('inset:-1px;pointer-events:none', CSS)
        self.assertNotRegex(CSS, r'\.nav-item[^}]+--liquid')

    def test_frozen_physics_and_single_clock(self):
        for declaration in ('const navigationLensSpring = {mass:1, stiffness:520, damping:40};',
                            'const LENS_MORPH_MAX = .07, LENS_MORPH_SPEED = 3000;',
                            'const LENS_MAX_SUBSTEP = 1/120, LENS_MAX_FRAME = .032, LENS_STALL = .2;',
                            'const LENS_SETTLE_DISTANCE = .25, LENS_SETTLE_SPEED = 2;'):
            self.assertIn(declaration, LENS)
        self.assertEqual(LENS.count('requestAnimationFrame('), 3)
        self.assertEqual(LENS.count('cancelAnimationFrame('), 3)
        self.assertNotRegex(LENS, r'setTimeout|setInterval|\.animate\(')
        self.assertEqual(re.findall(r'@keyframes\s+([\w-]+)', CSS), ['sidebar-specular'])
        mapper = LENS[LENS.index('function navigationLensOptics'):LENS.index('function navigationLensSpringStep')]
        self.assertNotRegex(mapper, r'getBoundingClientRect|getComputedStyle|offsetWidth|clientWidth|Date\.|performance\.')
        self.assertIn('const optical = running ?', mapper)
        self.assertIn(" : '';", mapper)

    def test_ordinary_lens_has_no_nested_filter(self):
        for filename in ('style.css', 'workspace.css'):
            css = re.sub(r'/\*.*?\*/', '', (STATIC / filename).read_text(encoding='utf-8'), flags=re.S)
            for _, selector, declaration in walk(parse(css)[0]):
                if not selector or not re.match(r'(?:-webkit-)?backdrop-filter\s*:', declaration):
                    continue
                if declaration.split(':', 1)[1].strip() == 'none':
                    continue
                for target in selector.split(','):
                    if 'nav-selection-lens' in target:
                        self.assertEqual(target.strip(), '.sidebar-cta>.nav-selection-lens')
        self.assertNotRegex(CSS, r'@keyframes[^}]+(?:blur|backdrop-filter)')

    def test_motion_transparency_and_system_color_fallbacks(self):
        optics = CSS[CSS.index('/* Keep one paint owner'):]
        self.assertIn('@media(prefers-reduced-motion:no-preference)', optics)
        self.assertIn('@media(prefers-reduced-transparency:reduce)', optics)
        self.assertIn('--liquid-fill:var(--color-accent-soft)', optics)
        self.assertIn('.nav-selection-lens::after{display:none}', optics)
        forced = optics[optics.index('@media(forced-colors:active)'):]
        self.assertIn('.nav-selection-lens::before,.nav-selection-lens::after{display:none}', forced)
        self.assertIn('border:2px solid Highlight', forced)

    def test_version_and_schema(self):
        version = re.search(r'^version = "([^"]+)"', (ROOT / 'pyproject.toml').read_text(), re.M).group(1)
        self.assertEqual(version, '0.114.0')
        self.assertIn(f'version="{version}"', (ROOT / 'beeloft/api.py').read_text(encoding='utf-8'))
        self.assertEqual(json.loads((ROOT / 'docs/openapi.json').read_text(encoding='utf-8'))['info']['version'], version)
        versions = [int(value) for path in (ROOT / 'beeloft').glob('*.sql')
                    for value in re.findall(r'PRAGMA user_version\s*=\s*(\d+)', path.read_text(encoding='utf-8'))]
        self.assertEqual(max(versions), 55)


if __name__ == '__main__':
    unittest.main()
