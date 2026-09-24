"""A1's solid foundation and migration boundary, independent of screenshots."""
import re
import unittest
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / 'beeloft' / 'static'
CSS = re.sub(r'/\*.*?\*/', '', (STATIC / 'style.css').read_text(encoding='utf-8'), flags=re.S)


def tokens(selector):
    blocks = re.findall(re.escape(selector) + r'\s*\{([^}]+)\}', CSS)
    return [dict(re.findall(r'(--[\w-]+)\s*:\s*([^;{}]+)', block)) for block in blocks]


def contrast(a, b):
    def luminance(color):
        digits = color.lstrip('#')
        if len(digits) == 3:
            digits = ''.join(c * 2 for c in digits)
        channels = [int(digits[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in channels]
        return sum(v * weight for v, weight in zip(linear, (.2126, .7152, .0722)))
    light, dark = sorted((luminance(a), luminance(b)), reverse=True)
    return (light + .05) / (dark + .05)


class Apple27FoundationTest(unittest.TestCase):
    def setUp(self):
        self.light = tokens(':root')[0]
        self.dark = tokens(':root[data-theme=dark]')[0]

    def test_native_font_and_rem_type_roles(self):
        self.assertEqual(self.light['--font-ui'],
                         '-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,"Noto Sans",sans-serif')
        for role in ('page-title', 'section-title', 'card-title', 'body', 'control', 'caption', 'data', 'metadata'):
            self.assertRegex(self.light['--type-' + role], r'^[.\d]+rem$')
            self.assertIn('var(--type-' + role + ')', CSS)
        self.assertIn('font-family:var(--font-ui)', CSS)

    def test_one_palette_and_full_dark_parity(self):
        for role in ('canvas', 'content', 'content-subtle', 'content-raised', 'label-primary',
                     'label-secondary', 'label-tertiary', 'separator', 'separator-strong',
                     'accent', 'accent-hover', 'accent-soft', 'danger', 'warning', 'success'):
            self.assertIn('--color-' + role, self.light)
        colors = {key for key in self.light if key.startswith('--color-')}
        self.assertEqual(colors, {key for key in self.dark if key.startswith('--color-')})
        for name in colors:
            self.assertEqual(len(re.findall(re.escape(name) + r'\s*:', CSS)), 2, name)
        self.assertEqual(len(tokens(':root[data-theme=dark]')), 1)

    def test_materials_resolve_to_opaque_colors_in_both_themes(self):
        materials = ('canvas', 'content', 'content-subtle', 'raised', 'functional-chrome-solid', 'floating-solid')
        for theme in (self.light, self.light | self.dark):
            for role in materials:
                source = re.fullmatch(r'var\((--color-[\w-]+)\)', theme['--material-' + role]).group(1)
                self.assertRegex(theme[source], r'^#(?:[\da-f]{3}|[\da-f]{6})$')
        for role in ('tint', 'border', 'highlight', 'shadow'):
            self.assertIn('--chrome-' + role, self.light)
        # A1 reserved the four optical roles and left them inert. A4 activated them, so `--chrome-tint`
        # is now genuinely translucent — which is exactly why the opaque guarantee has to live in the
        # `--material-*` roles above rather than in the optical ones. Those materials stay fully
        # opaque, and they remain what every unconditional surface resolves to.
        self.assertRegex(self.light['--chrome-tint'], r'^#[\da-f]{6}[\da-f]{2}$')
        self.assertEqual(self.light['--chrome-border'], 'var(--color-separator)')

    def test_compatibility_aliases_have_no_private_palette(self):
        legacy = ('canvas app-bg bg surface surface-subtle surface-sunken ink ink-2 muted line '
                  'line-strong edge control-line primary primary-hover primary-soft primary-edge '
                  'accent accent-bg focus danger danger-bg danger-edge warning warning-bg warning-edge '
                  'success success-bg success-edge r-card r-nav r-chip r-pill shadow-sm shadow-md shadow-lg shadow').split()
        for name in legacy:
            key = '--' + name
            self.assertRegex(self.light[key], r'^var\(--[\w-]+\)$')
            self.assertNotIn(key, self.dark)
            for value in re.findall(re.escape(key) + r'\s*:\s*([^;}]+)', CSS):
                self.assertRegex(value, r'^var\(--[\w-]+\)$', key)

    def test_geometry_and_elevation_hierarchy(self):
        values = [float(self.light['--radius-' + role].removesuffix('px'))
                  for role in ('prominent', 'content', 'control', 'compact')]
        self.assertTrue(all(a > b for a, b in zip(values, values[1:])))
        self.assertIn('--radius-pill', self.light)
        for role in ('content', 'raised', 'floating'):
            self.assertIn('--shadow-' + role, self.light)
            self.assertIn('--shadow-' + role, self.dark)
        for role in ('height', 'height-compact', 'radius', 'padding-x'):
            self.assertIn('--control-' + role, self.light)
            self.assertIn('var(--control-' + role + ')', CSS)
        self.assertGreaterEqual(float(self.light['--touch-target-min'].removesuffix('px')), 44)

    def test_text_states_and_focus_contrast(self):
        for theme in (self.light, self.light | self.dark):
            for label in ('primary', 'secondary', 'tertiary'):
                for surface in ('canvas', 'content', 'content-subtle', 'content-raised', 'content-sunken'):
                    with self.subTest(label=label, surface=surface, canvas=theme['--color-canvas']):
                        self.assertGreaterEqual(contrast(theme['--color-label-' + label], theme['--color-' + surface]), 4.5)
            for state in ('accent', 'danger', 'warning', 'success'):
                self.assertGreaterEqual(contrast(theme['--color-' + state], theme['--color-' + state + '-soft']), 4.5)
            for state in ('accent', 'accent-hover'):
                self.assertGreaterEqual(contrast(theme['--color-on-accent'], theme['--color-' + state]), 4.5)
            for surface in ('content', 'content-subtle', 'content-raised'):
                for role in ('focus', 'control-border'):
                    self.assertGreaterEqual(contrast(theme['--color-' + role], theme['--color-' + surface]), 3)

    def test_glass_stays_contained_and_no_gpu_renderer_or_external_font_assets(self):
        source = '\n'.join(p.read_text(encoding='utf-8') for p in STATIC.iterdir()
                           if p.suffix in ('.css', '.mjs', '.html'))
        # A1 banned every optical effect outright. A4 authorised a bounded one, so this became a
        # containment check rather than a removal. The A1 guarantee it still has to defend is that the
        # solid materials above are what the product actually renders whenever the enhancement is not
        # available — so no surface may be translucent *unconditionally*, and nothing may blur
        # rendered content at all. The authorised-target list and the fallback hierarchy are owned by
        # `test_apple27_functional_glass_contract.py`.
        self.assertNotRegex(CSS, r'(?:^|[^-\w])(?:-webkit-)?filter\s*:[^;}]*blur\(|@import|@font-face')
        gate = '@supports ((backdrop-filter:blur(1px)) or (-webkit-backdrop-filter:blur(1px)))'
        self.assertEqual(CSS.count('@supports'), 1, 'one feature gate holds the entire optical layer')
        start, depth = CSS.index(gate), 0
        for index in range(start, len(CSS)):
            if CSS[index] == '{':
                depth += 1
            elif CSS[index] == '}':
                depth -= 1
                if depth == 0:
                    break
        outside = CSS[:start] + CSS[index + 1:]
        self.assertNotRegex(outside, r'backdrop-filter\s*:\s*(?!none)',
                            'no surface is translucent outside the feature gate')
        self.assertIn('background:var(--material-functional-chrome-solid)',
                      re.search(r'\.masthead\s*\{([^}]*)\}', outside).group(1))
        self.assertIn('background:var(--material-functional-chrome-solid)',
                      re.search(r'\.app-sidebar\s*\{([^}]*)\}', outside).group(1))
        # Content and business surfaces are never filtered, inside the gate or out.
        for selector, declarations in re.findall(r'([^{}@]+)\{([^}]*backdrop-filter[^}]*)\}', CSS):
            if 'none' in re.search(r'backdrop-filter\s*:\s*(\S+?)[;\s}]', declarations).group(1):
                continue
            with self.subTest(selector=selector.strip()[-60:]):
                for forbidden in ('.workspace-main', '.card', 'dialog', '.notice', '.state',
                                  '.summary', '.hero-panel', 'table', '.sidebar-cta{', 'body'):
                    self.assertNotIn(forbidden, selector)
        self.assertNotRegex(source, r'navigator\.gpu|getContext\([\"\x27]webgl')
        # A1 forbade physics outright. A3 authorised one spring, for the navigation lens only, so
        # the exclusion is now a containment check: the integrator and its state stay inside the
        # lens region and no second animation engine appears beside it.
        script = (STATIC / 'app.mjs').read_text(encoding='utf-8')
        lens = script[script.index('const navigationSurface ='):script.index('// Drawer mobile.')]
        outside = script.replace(lens, '')
        self.assertNotRegex(outside, r'stiffness|damping|navigationLensSpring|velocity')
        self.assertEqual(len(re.findall(r'const navigationLensSpring = \{', script)), 1,
                         'one spring configuration exists in the whole application')
        self.assertNotRegex(source, r'fonts\.googleapis|fonts\.gstatic|use\.typekit')
        # A1 excluded the transparency preference because a speculative query with nothing to switch
        # off would have been dead code. A4 has something to switch off, so the exclusion becomes a
        # usage rule: the query appears exactly once and only ever withdraws the enhancement, never
        # enables it, so an engine that does not implement it still gets solid chrome from the gate.
        self.assertEqual(CSS.count('prefers-reduced-transparency'), 1)
        self.assertIn('@media(prefers-reduced-transparency:reduce)', CSS)
        withdraw = CSS[CSS.index('@media(prefers-reduced-transparency:reduce)'):]
        self.assertNotRegex(withdraw[:withdraw.index('@media(forced-colors:active)')],
                           r'backdrop-filter\s*:\s*(?!none)')
        self.assertEqual([p.name for p in STATIC.rglob('*') if p.suffix.lower() in
                          ('.woff', '.woff2', '.otf', '.ttf', '.png', '.jpg', '.webp', '.svg')],
                         ['wallpaper-landscape.webp', 'wallpaper-mist.webp'])


if __name__ == '__main__':
    unittest.main()
