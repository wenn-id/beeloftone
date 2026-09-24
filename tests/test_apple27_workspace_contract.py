"""A5.2 stays a local presentation layer with one bounded optical animation."""
from pathlib import Path
import re
import unittest

STATIC = Path(__file__).resolve().parents[1] / 'beeloft' / 'static'


class WorkspaceContractTest(unittest.TestCase):
    def test_local_assets_and_early_preferences(self):
        css = (STATIC / 'workspace.css').read_text(encoding='utf-8')
        html = (STATIC / 'index.html').read_text(encoding='utf-8')
        for name in ('landscape', 'mist'):
            data = (STATIC / f'wallpaper-{name}.webp').read_bytes()
            self.assertEqual(data[:4], b'RIFF')
            self.assertEqual(data[8:12], b'WEBP')
            self.assertIn(f'/static/wallpaper-{name}.webp', css)
        self.assertNotRegex(css, r'https?://|@import|@font-face')
        self.assertLess(html.index('/static/appearance.js'), html.index('/static/style.css'))

    def test_browser_controls_and_storage_boundary(self):
        js = (STATIC / 'workspace.mjs').read_text(encoding='utf-8')
        html = (STATIC / 'index.html').read_text(encoding='utf-8')
        for action in ('close', 'minimize', 'fullscreen'):
            self.assertRegex(html, rf'<button id="window-{action}"[^>]+type="button"[^>]+aria-label=')
        self.assertNotIn('window.close(', js)
        for text in ('guardPending()', 'requestFullscreen()', 'fullscreenchange', 'is-maximized',
                     "indexedDB.open('beeloft.appearance'", 'createImageBitmap(blob)', 'URL.revokeObjectURL(previous)',
                     '8 * 1024 * 1024', '32000000', "localStorage.setItem('beeloft.wallpaper', name)",
                     "addEventListener('online'", "addEventListener('offline'", 'target.click()'):
            self.assertIn(text, js)
        self.assertNotRegex(js, r'\bfetch\(|api\.|requestAnimationFrame\(|setInterval\(|setTimeout\(')
        self.assertNotRegex(js, r'localStorage\.setItem\([^\n]*(?:blob|base64)')

    def test_only_css_rim_and_accessible_fallbacks(self):
        css = (STATIC / 'workspace.css').read_text(encoding='utf-8')
        self.assertEqual(css.count(' infinite'), 1)
        self.assertEqual(re.findall(r'@keyframes\s+([^\s{]+)\{', css), ['sidebar-specular'])
        frames = css[css.index('@keyframes'):css.index(':root[data-theme=dark] .app-sidebar::after')]
        self.assertNotRegex(frames, r'(?:backdrop-filter|blur|width|height):')
        self.assertIn('@media(prefers-reduced-motion:reduce){.app-sidebar::after{animation:none', css)
        self.assertIn('@media(prefers-reduced-transparency:reduce)', css)
        self.assertIn('@media(forced-colors:active)', css)
        self.assertNotRegex(css, r'nav-selection-lens[^}]+backdrop-filter:(?!none)')


if __name__ == '__main__':
    unittest.main()
