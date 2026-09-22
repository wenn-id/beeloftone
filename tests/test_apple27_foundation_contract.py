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

    def test_no_glass_lens_spring_or_external_font_assets(self):
        source = '\n'.join(p.read_text(encoding='utf-8') for p in STATIC.iterdir()
                           if p.suffix in ('.css', '.mjs', '.html'))
        self.assertNotRegex(CSS, r'backdrop-filter|filter\s*:[^;}]*blur\(|@import|@font-face')
        self.assertNotRegex(source, r'nav-selection-lens|springController|SpringController|navigator\.gpu|getContext\([\"\x27]webgl')
        self.assertNotRegex(source, r'fonts\.googleapis|fonts\.gstatic|use\.typekit|prefers-reduced-transparency')
        self.assertEqual([p.name for p in STATIC.rglob('*') if p.suffix.lower() in
                          ('.woff', '.woff2', '.otf', '.ttf', '.png', '.jpg', '.webp', '.svg')], [])


if __name__ == '__main__':
    unittest.main()
