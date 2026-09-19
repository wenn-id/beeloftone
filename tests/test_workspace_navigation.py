"""Keep the sidebar registry and remaining-dialog review complete."""
from html.parser import HTMLParser
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class NavigationMarkup(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.in_sidebar = False
        self.buttons = []
        self.sections = set()
        self.dialogs = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'aside' and attrs.get('id') == 'app-sidebar':
            self.in_sidebar = True
        if tag == 'button' and self.in_sidebar:
            self.buttons.append(attrs.get('id'))
        if tag == 'section':
            self.sections.add(attrs.get('id'))
        if tag == 'dialog':
            self.dialogs.append(attrs.get('id'))

    def handle_endtag(self, tag):
        if tag == 'aside':
            self.in_sidebar = False


class WorkspaceNavigationTests(unittest.TestCase):
    def test_sidebar_has_registered_page_hosts(self):
        app = (ROOT / 'beeloft/static/app.mjs').read_text(encoding='utf-8')
        markup = NavigationMarkup(
            (ROOT / 'beeloft/static/index.html').read_text(encoding='utf-8'))
        registry = re.search(r'const workspaceDestinations=\{(.*?)\n\};', app, re.S)
        self.assertIsNotNone(registry)
        destinations = re.findall(r"'([^']+)':'([^']+)'", registry[1])
        self.assertTrue(destinations)
        self.assertCountEqual(markup.buttons, [nav for nav, _ in destinations])
        self.assertEqual(len(markup.buttons), len(set(markup.buttons)))
        sections = re.search(r'const workspaceSections=\[(.*?)\n\];', app, re.S)
        self.assertIsNotNone(sections)
        registered = set(re.findall(r"id:'([^']+)'", sections[1]))
        self.assertLessEqual({host for _, host in destinations}, registered)
        self.assertLessEqual(registered, markup.sections)
        self.assertEqual(markup.dialogs, ['dialog'])

    def test_every_dialog_function_has_a_reviewed_classification(self):
        app = (ROOT / 'beeloft/static/app.mjs').read_text(encoding='utf-8')
        review = (ROOT / 'docs/workspace-dialog-classification.md').read_text(
            encoding='utf-8')
        functions = set(re.findall(r'^(?:async )?function (\w*Dialog)\(', app, re.M))
        documented = set(re.findall(r'`(\w+Dialog)`', review))
        self.assertTrue(functions)
        self.assertEqual(functions, documented)


if __name__ == '__main__':
    unittest.main()
