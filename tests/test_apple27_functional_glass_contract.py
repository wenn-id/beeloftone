"""A4: bounded optical material on functional chrome, and nothing else.

This module asserts the *architecture* of the glass rather than its appearance, which is what the
browser contract measures. The central claim is an ordering one: the A1 solid materials are the
unconditional base declaration, and every optical property lives inside one feature gate, so an
engine without backdrop filtering never reaches a translucent surface and the fallback is the
foundation instead of a patch.

The stylesheet is parsed into a real rule tree rather than searched as text, because the questions
worth asking are structural — *which* selector received a filter, and *inside which* at-rules — and
a substring search cannot tell a gated declaration from an ungated one.

A4 is a CSS-only phase: `beeloft/static/app.mjs` is untouched, so the A3 spring constants, the morph
constants and the frame/timer inventory are pinned here as regression evidence that the material
rides on the existing physics instead of replacing or retuning it.
"""
import re
import unittest
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / 'beeloft' / 'static'
RAW = (STATIC / 'style.css').read_text(encoding='utf-8')
CSS = re.sub(r'/\*.*?\*/', '', RAW, flags=re.S)
HTML = (STATIC / 'index.html').read_text(encoding='utf-8')
JS = (STATIC / 'app.mjs').read_text(encoding='utf-8')
CLIENT = (STATIC / 'client.mjs').read_text(encoding='utf-8')
LENS = JS[JS.index('const navigationSurface ='):JS.index('// Drawer mobile.')]


def code(text):
    """Comment-free source, so an exclusion cannot be tripped by prose that documents the exclusion.

    This file's own subject matter means the words `refraction`, `backdrop` and `glass` appear
    legitimately in both stylesheet and script commentary. Asserting their absence from *code* is the
    real guarantee; asserting their absence from documentation would only discourage documentation.
    """
    without_block = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return re.sub(r'(?m)^\s*//.*$|(?<![:\w])//[^\n\'"`]*$', '', without_block)


CODE = {'app.mjs': code(JS), 'client.mjs': code(CLIENT), 'style.css': CSS, 'index.html': code(HTML)}

GATE = '@supports'
# The surfaces §3 authorises to carry the optical material. `.sidebar-actions` is deliberately
# absent: it is re-tinted so the glass sidebar stays coherent, but it must never become a second
# blurred layer.
AUTHORISED_GLASS = {'.masthead', '.app-sidebar', '.nav-selection-lens',
                    '.sidebar-cta>.nav-selection-lens'}
# The subset that may actually declare a backdrop filter. The lens is translucent in both contexts,
# but it is only *filtered* inside the approval card. In the navigation column it sits inside the
# already-filtered sidebar, which is a backdrop root: a filter there would sample that root's flat
# tint, produce no visible blur, and force the whole column to be re-sampled on every frame the lens
# moves. That measurably dropped a frame per travel and collapsed A3's velocity-continuity
# measurement, so it was removed. One blurred surface per column, no nested blur.
FILTERED_GLASS = {'.masthead', '.app-sidebar', '.sidebar-cta>.nav-selection-lens'}
# Content, business and floating surfaces that A4 must never filter.
FORBIDDEN_GLASS = ('.workspace-main', '.card', '.sku-block', '.hero-panel', '.summary',
                   '.attention-panel', '.command-snapshot', '.command-center-content', 'dialog',
                   '.notice', '.state', '.error', '.stages', '.stage', '.barchart', '.order-row',
                   '.table-head', '.table-scroll', '.scan-result', '.login-form', '.filters',
                   '.filter-bar', '.sidebar-cta', 'body', 'html', '*', '.activity-item',
                   '.approval-list', '.workforce-summary', 'progress', 'table')


def parse(css, index=0):
    """Minimal but correct-enough CSS block parser: preludes, nesting, declarations.

    Quotes and parentheses are tracked so a `;` inside a value or a `{` inside a string cannot
    split a rule. That is enough for this stylesheet and keeps the tree honest.
    """
    nodes, buffer, quote, depth = [], '', '', 0
    while index < len(css):
        char = css[index]
        if quote:
            buffer += char
            if char == quote and css[index - 1] != '\\':
                quote = ''
            index += 1
            continue
        if char in '"\'':
            quote, buffer = char, buffer + char
            index += 1
            continue
        if char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
        if depth == 0 and char == '{':
            children, index = parse(css, index + 1)
            nodes.append({'prelude': ' '.join(buffer.split()), 'children': children})
            buffer = ''
            continue
        if depth == 0 and char == '}':
            if buffer.strip():
                nodes.append({'declaration': ' '.join(buffer.split())})
            return nodes, index + 1
        if depth == 0 and char == ';':
            if buffer.strip():
                nodes.append({'declaration': ' '.join(buffer.split())})
            buffer = ''
            index += 1
            continue
        buffer += char
        index += 1
    if buffer.strip():
        nodes.append({'declaration': ' '.join(buffer.split())})
    return nodes, index


TREE, _ = parse(CSS)


def walk(nodes=None, context=()):
    """Yield (at-rule context, selector, declaration) for every declaration in the sheet."""
    for node in (TREE if nodes is None else nodes):
        if 'declaration' in node:
            yield context, None, node['declaration']
            continue
        prelude = node['prelude']
        if prelude.startswith('@'):
            yield from walk(node['children'], context + (prelude,))
            continue
        for child in node['children']:
            if 'declaration' in child:
                yield context, prelude, child['declaration']
            else:
                yield from walk([child], context + (prelude,))


DECLARATIONS = list(walk())


def selectors(declaration_pattern, context_filter=None):
    found = set()
    for context, selector, declaration in DECLARATIONS:
        if selector is None or not re.search(declaration_pattern, declaration):
            continue
        if context_filter is not None and not context_filter(context):
            continue
        for part in selector.split(','):
            found.add(''.join(part.split()))
    return found


def block(selector, context_filter=lambda context: context == ()):
    """Every declaration for one selector under a context predicate, concatenated."""
    out = []
    for context, found, declaration in DECLARATIONS:
        if found is None or not context_filter(context):
            continue
        if any(''.join(part.split()) == selector for part in found.split(',')):
            out.append(declaration)
    return '; '.join(out)


def root_tokens(selector):
    return dict(re.findall(r'(--[\w-]+)\s*:\s*(.+)', block(selector).replace('; ', '\n')))


class SolidFirstArchitectureTest(unittest.TestCase):
    """The A1 baseline is the foundation, not a fallback bolted on afterwards."""

    def test_solid_functional_chrome_is_the_unconditional_base_declaration(self):
        for selector in ('.masthead', '.app-sidebar'):
            with self.subTest(selector=selector):
                base = block(selector)
                self.assertIn('background:var(--material-functional-chrome-solid)', base)
                self.assertIn('var(--chrome-border)', base)
                self.assertNotIn('backdrop-filter', base)
        lens = block('.nav-selection-lens')
        self.assertIn('background:var(--color-accent-soft)', lens)
        self.assertIn('border:1px solid var(--color-separator-strong)', lens)
        self.assertNotIn('backdrop-filter', lens)
        # The sticky approval plate and the selected-approval fallback are equally unconditional, so
        # the column is a finished rendering with the optical layer deleted.
        self.assertIn('background:var(--surface)', block('.sidebar-actions'))
        self.assertRegex(block('#approvals[aria-current=page]'),
                         r'background:var\(--color-accent-soft\)')

    def test_the_base_material_needs_no_supports_query_to_be_usable(self):
        """Deleting every conditional group must still leave a complete, opaque shell."""
        unconditional = ' '.join(declaration for context, selector, declaration in DECLARATIONS
                                 if selector is not None and context == ())
        self.assertNotIn('backdrop-filter', unconditional)
        # The translucent roles are defined at the root but consumed only inside the gate, so no
        # unconditional surface can resolve to a see-through material.
        self.assertNotIn('var(--chrome-tint', unconditional)
        self.assertNotIn('var(--lens-glass', unconditional)
        for selector in ('.masthead', '.app-sidebar', '.nav-selection-lens'):
            with self.subTest(selector=selector):
                declarations = block(selector)
                self.assertRegex(declarations, r'background:\S+')
                self.assertRegex(declarations, r'border')

    def test_optical_tokens_extend_the_a1_roles_instead_of_forking_the_palette(self):
        light = root_tokens(':root')
        dark = root_tokens(':root[data-theme=dark]')
        for role in ('tint', 'border', 'highlight', 'shadow'):
            self.assertIn('--chrome-' + role, light, 'the four A1 optical roles survive')
        # A1's structural border and its shadow tier are consumed, not duplicated.
        self.assertEqual(light['--chrome-border'], 'var(--color-separator)')
        self.assertEqual(light['--chrome-shadow'], 'var(--shadow-raised)')
        self.assertIn('var(--chrome-highlight)', CSS)
        self.assertIn('var(--chrome-shadow)', CSS)
        # No second unrelated palette: every optical addition is in one of the two families.
        optical = {name for name in light if re.search(r'blur|saturation|tint|glass', name)}
        self.assertTrue(optical)
        for name in optical:
            self.assertRegex(name, r'^--(chrome|lens-glass)-', 'one semantic optical hierarchy')
        # Colour roles are tuned per theme; the optical geometry is deliberately theme-invariant so a
        # theme change can never re-animate or snap the filter.
        for name in ('--chrome-tint', '--chrome-tint-dense', '--chrome-glass-edge', '--chrome-highlight',
                     '--lens-glass-tint', '--lens-glass-edge', '--lens-glass-highlight',
                     '--lens-glass-shadow', '--lens-glass-cta-tint', '--lens-glass-cta-edge',
                     '--lens-glass-cta-highlight'):
            with self.subTest(token=name):
                self.assertIn(name, light)
                self.assertIn(name, dark, 'every optical colour has an intentional dark treatment')
                self.assertNotEqual(light[name], dark[name], 'dark is tuned, not inherited')
        for name in ('--chrome-blur', '--chrome-saturation', '--lens-glass-blur', '--lens-glass-saturation'):
            with self.subTest(token=name):
                self.assertIn(name, light)
                self.assertNotIn(name, dark)
                self.assertEqual(len(re.findall(re.escape(name) + r'\s*:', CSS)), 1)

    def test_tints_are_actually_translucent_and_stay_in_the_tuned_band(self):
        light, dark = root_tokens(':root'), root_tokens(':root[data-theme=dark]')
        for theme in (light, light | dark):
            for name in ('--chrome-tint', '--chrome-tint-dense', '--lens-glass-tint', '--lens-glass-cta-tint'):
                with self.subTest(token=name, canvas=theme['--color-canvas']):
                    alpha = int(re.fullmatch(r'#[\da-f]{6}([\da-f]{2})', theme[name]).group(1), 16) / 255
                    self.assertLess(alpha, 1, 'a tint must transmit something')
                    self.assertGreater(alpha, .5, 'and must still carry a readable foreground')
            # The plate that masks scrolled navigation is denser than the material it sits on.
            self.assertGreater(int(theme['--chrome-tint-dense'][-2:], 16),
                               int(theme['--chrome-tint'][-2:], 16))
        radius = float(light['--chrome-blur'].removesuffix('px'))
        lens_radius = float(light['--lens-glass-blur'].removesuffix('px'))
        self.assertTrue(12 <= radius <= 28, f'chrome blur {radius}px is a bounded radius')
        self.assertTrue(8 <= lens_radius <= 18, f'lens blur {lens_radius}px is a smaller budget')
        self.assertLess(lens_radius, radius, 'the small moving surface blurs less than static chrome')
        for name in ('--chrome-saturation', '--lens-glass-saturation'):
            saturation = float(light[name])
            self.assertTrue(1 < saturation <= 1.6, f'{name} {saturation} stays restrained')


class FeatureGateTest(unittest.TestCase):
    """Glass exists only inside one supported-enhancement scope."""

    def setUp(self):
        self.gates = {prelude for context, _, _ in DECLARATIONS for prelude in context
                      if prelude.startswith(GATE)}

    def test_exactly_one_gate_guards_the_optical_layer_and_tests_both_properties(self):
        self.assertEqual(len(self.gates), 1, f'one feature gate, found {self.gates}')
        condition = next(iter(self.gates))
        self.assertRegex(condition, r'\(\s*backdrop-filter\s*:\s*blur\(1px\)\s*\)')
        self.assertRegex(condition, r'\(\s*-webkit-backdrop-filter\s*:\s*blur\(1px\)\s*\)')
        self.assertIn(' or ', condition, 'either property satisfies the gate')
        self.assertNotRegex(CSS, r'prefers-reduced-transparency[^{]*\)\s*\{[^}]*backdrop-filter:\s*blur',
                            'the transparency preference is never used as the gate')
        self.assertNotRegex(CODE['app.mjs'], r'userAgent|navigator\.vendor|navigator\.platform'
                                             r'|userAgentData|isChrom|isSafari|isFirefox|isWebkit',
                            'no scripted user-agent detection was introduced')

    def test_every_active_backdrop_filter_is_inside_the_gate(self):
        for context, selector, declaration in DECLARATIONS:
            if 'backdrop-filter' not in declaration:
                continue
            value = declaration.split(':', 1)[1].strip()
            with self.subTest(selector=selector, declaration=declaration):
                if value == 'none':
                    # Only ever used to withdraw the enhancement.
                    self.assertTrue(any('forced-colors' in part or 'prefers-reduced-transparency' in part
                                        for part in context), context)
                else:
                    self.assertTrue(any(part.startswith(GATE) for part in context),
                                    'an active filter outside the gate would break the fallback')

    def test_both_vendor_paths_are_declared_on_every_glass_surface(self):
        gated = lambda context: any(part.startswith(GATE) for part in context) \
            and not any('prefers-reduced-transparency' in part for part in context)
        standard = selectors(r'^backdrop-filter\s*:\s*(?!none)', gated)
        prefixed = selectors(r'^-webkit-backdrop-filter\s*:\s*(?!none)', gated)
        self.assertEqual(standard, prefixed, 'both spellings cover the same surfaces')
        self.assertEqual(standard, FILTERED_GLASS)

    def test_only_authorised_functional_chrome_becomes_glass(self):
        touched = selectors(r'backdrop-filter\s*:\s*(?!none)')
        self.assertTrue(touched <= AUTHORISED_GLASS, f'unauthorised glass targets: {touched - AUTHORISED_GLASS}')
        self.assertEqual(touched, FILTERED_GLASS)
        self.assertIn('.masthead', touched)
        self.assertIn('.app-sidebar', touched)
        self.assertIn('.sidebar-cta>.nav-selection-lens', touched)
        # One blurred surface per column: the sticky plate is re-tinted, never re-filtered.
        gated = lambda context: any(part.startswith(GATE) for part in context) \
            and not any('prefers-reduced-transparency' in part for part in context)
        plate = block('.sidebar-actions', gated)
        self.assertIn('var(--chrome-tint-dense)', plate)
        self.assertNotIn('backdrop-filter', plate)
        self.assertIn('var(--chrome-tint-dense)', block('.sidebar-actions::before', gated))
        self.assertIn('var(--lens-glass-cta-tint)', block('.sidebar-cta>.nav-selection-lens', gated))


class ContentStaysOpaqueTest(unittest.TestCase):
    def test_no_content_business_or_dialog_surface_is_a_filter_target(self):
        """A forbidden surface may be an *ancestor* of a filtered element, never the filtered one.

        `.sidebar-cta > .nav-selection-lens` is the case that makes the distinction matter: the CTA
        is content and stays unfiltered, while the lens that travels into it is authorised. So the
        subject of the selector — the compound after the last combinator — is what gets checked.
        """
        for selector in selectors(r'backdrop-filter\s*:\s*(?!none)'):
            subject = re.split(r'[>+~ ]', selector)[-1]
            for forbidden in FORBIDDEN_GLASS:
                with self.subTest(selector=selector, subject=subject, forbidden=forbidden):
                    self.assertNotEqual(subject, forbidden)
                    self.assertFalse(subject.startswith(forbidden + ':')
                                     or subject.startswith(forbidden + '.')
                                     or subject.startswith(forbidden + '['))

    def test_nothing_anywhere_blurs_rendered_content(self):
        for context, selector, declaration in DECLARATIONS:
            with self.subTest(selector=selector, declaration=declaration[:80]):
                self.assertNotRegex(declaration, r'^filter\s*:[^;]*blur\(')
                self.assertNotRegex(declaration, r'^-webkit-filter\s*:[^;]*blur\(')

    def test_no_gpu_refraction_or_shader_renderer_exists(self):
        source = '\n'.join(CODE.values())
        self.assertNotRegex(source, r'navigator\.gpu|WebGPU|getContext\([\'"]webg|createShader'
                                    r'|ShaderMaterial|requestAdapter|GPUDevice')
        # A CSS approximation is the whole of A4: no scripted optical distortion of any kind.
        self.assertNotRegex(source, r'refract\w*\s*[({=]|chromatic\w*\s*[({=]|aberration\s*[({=]')
        self.assertNotIn('OffscreenCanvas', source)
        self.assertNotRegex(source, r'getContext\([\'"]2d')
        self.assertNotRegex(source, r'<canvas|createElement\([\'"]canvas')
        # A5.2 explicitly adds two local scenic wallpapers, with a separate presentation stylesheet.
        # The one pre-existing `url(#…)` is an in-document SVG paint-server reference, not an asset.
        self.assertNotRegex(CSS, r'url\((?!#)|@import|@font-face|image-set\(')
        self.assertEqual(re.findall(r'url\([^)]*\)', CSS), ['url(#trend-fill)'])
        self.assertEqual([path.name for path in STATIC.rglob('*') if path.suffix.lower() in
                          ('.png', '.jpg', '.jpeg', '.webp', '.avif', '.svg', '.mp4', '.woff', '.woff2')],
                         ['wallpaper-landscape.webp', 'wallpaper-mist.webp'])


class FallbackHierarchyTest(unittest.TestCase):
    def test_reduced_transparency_returns_the_a1_solid_materials(self):
        scope = lambda context: any('prefers-reduced-transparency' in part for part in context)
        contexts = [context for context, _, _ in DECLARATIONS if scope(context)]
        self.assertTrue(contexts, 'a reduced-transparency path exists')
        for context in contexts:
            self.assertTrue(any(part.startswith(GATE) for part in context),
                            'it withdraws the enhancement from inside the gate that added it')
        self.assertEqual({part for context in contexts for part in context
                          if 'prefers-reduced-transparency' in part},
                         {'@media(prefers-reduced-transparency:reduce)'})
        for selector in ('.masthead', '.app-sidebar'):
            with self.subTest(selector=selector):
                restored = block(selector, scope)
                self.assertIn('var(--material-functional-chrome-solid)', restored)
                self.assertIn('backdrop-filter:none', restored)
                self.assertIn('-webkit-backdrop-filter:none', restored)
                self.assertIn('box-shadow:none', restored)
        for selector in ('.nav-selection-lens', '.sidebar-cta>.nav-selection-lens'):
            with self.subTest(selector=selector):
                lens = block(selector, scope)
                self.assertIn('var(--color-accent-soft)', lens)
                self.assertIn('border-color:var(--color-separator-strong)', lens)
                self.assertIn('backdrop-filter:none', lens)
                self.assertIn('box-shadow:none', lens)
        self.assertIn('var(--surface)', block('.sidebar-actions', scope))
        self.assertIn('var(--surface)', block('.sidebar-actions::before', scope))

    def test_reduced_transparency_is_not_the_only_route_to_solid_chrome(self):
        """The preference has limited availability, so the gate itself is the real guarantee."""
        gates = {part for context, _, _ in DECLARATIONS for part in context if part.startswith(GATE)}
        self.assertEqual(len(gates), 1)
        self.assertNotIn('prefers-reduced-transparency', next(iter(gates)))
        self.assertIn('background:var(--material-functional-chrome-solid)', block('.masthead'))

    def test_forced_colors_disables_the_optics_and_keeps_the_selection_visible(self):
        scope = lambda context: any('forced-colors' in part for part in context)
        contexts = [context for context, _, _ in DECLARATIONS if scope(context)]
        self.assertTrue(contexts, 'an explicit forced-colors contract exists')
        for context in contexts:
            self.assertEqual(context, ('@media(forced-colors:active)',),
                             'it sits outside the gate so it also corrects the solid baseline')
        combined = ' '.join(declaration for context, _, declaration in DECLARATIONS if scope(context))
        self.assertIn('backdrop-filter:none', combined)
        self.assertIn('-webkit-backdrop-filter:none', combined)
        self.assertIn('box-shadow:none', combined)
        for system in ('Canvas', 'CanvasText', 'Highlight'):
            self.assertIn(system, combined, 'system colours keep real boundaries')
        for selector in ('.nav-selection-lens', '.sidebar-cta>.nav-selection-lens'):
            with self.subTest(selector=selector):
                lens = block(selector, scope)
                self.assertIn('border:2px solid Highlight', lens,
                              'selection survives as a visible outline')
                self.assertIn('background:transparent', lens,
                              'the label keeps the system foreground instead of sitting on a forced block')
        self.assertIn('border-bottom:1px solid CanvasText', block('.masthead', scope))
        self.assertIn('border-right:1px solid CanvasText', block('.app-sidebar', scope))
        # Semantics are untouched: nothing here writes or overrides aria-current itself.
        self.assertNotRegex(combined, r'content\s*:|display\s*:\s*none|visibility')


class LensRemainsOnePhysicalObjectTest(unittest.TestCase):
    def test_exactly_one_lens_node_still_exists_and_no_ghost_was_added(self):
        self.assertEqual(len(re.findall(r'nav-selection-lens', HTML)), 2)  # id and class on one node
        self.assertEqual(len(re.findall(r'id="nav-selection-lens"', HTML)), 1)
        self.assertRegex(HTML, r'id="nav-selection-lens"[^>]*></span>')
        for cloner in ('createElement', 'cloneNode', 'insertAdjacentHTML'):
            self.assertNotIn(cloner, LENS)
        # A pseudo-element highlight would be allowed, but never a second interactive or moving one.
        for pseudo in re.findall(r'\.nav-selection-lens::(before|after)[^{]*\{([^}]*)\}', CSS):
            with self.subTest(pseudo=pseudo[0]):
                self.assertIn('pointer-events:none', pseudo[1])
                self.assertNotRegex(pseudo[1], r'animation\s*:\s*(?!none)|transition\s*:\s*(?!none)')

    def test_the_lens_surface_still_has_no_css_travel(self):
        base = block('.nav-selection-lens')
        for declaration in ('position:absolute', 'left:0', 'top:0', 'pointer-events:none',
                            'transition:none', 'animation:none'):
            self.assertIn(declaration, base)
        # No rule anywhere gives the lens a transition or animation that could race the integrator.
        for context, selector, declaration in DECLARATIONS:
            if selector is None or 'nav-selection-lens' not in selector:
                continue
            with self.subTest(selector=selector, declaration=declaration[:70]):
                self.assertNotRegex(declaration, r'^(transition|animation)[\w-]*\s*:\s*(?!none)')
                self.assertNotRegex(declaration, r'^will-change')
        self.assertNotIn('will-change', CSS)
        # The product's only keyframes are the pre-existing dialog entry pair; A4 adds none and the
        # lens references neither, so no optical shine can travel across it.
        self.assertEqual(sorted(re.findall(r'@keyframes\s+([\w-]+)', CSS)),
                         ['dialog-backdrop-enter', 'dialog-enter'])
        for context, selector, declaration in DECLARATIONS:
            if selector and 'nav-selection-lens' in selector:
                self.assertNotRegex(declaration, r'dialog-enter|dialog-backdrop-enter')
        # Glass appearance is state, so it is never handed to the theme transition either: the only
        # cross-surface colour transition in the product still animates exactly three properties, and
        # a blur radius is not one of them. That is what keeps a theme toggle from re-rendering the
        # optical filter or flashing opaque between the two palettes.
        theming = re.search(r':where\(html\.is-theming\)[^{]*\{([^}]*)\}', CSS).group(1)
        self.assertEqual(sorted(re.findall(r'(?:transition:|,)\s*([a-z-]+)\s+var\(--motion', theming)),
                         ['background-color', 'border-color', 'color'])
        for optical in ('backdrop-filter', 'box-shadow', 'filter'):
            with self.subTest(property=optical):
                self.assertNotIn(optical, theming)

    def test_the_lens_is_a_small_authorised_glass_target_in_both_contexts(self):
        gated = lambda context: any(part.startswith(GATE) for part in context) \
            and not any('prefers-reduced-transparency' in part or 'forced-colors' in part
                        for part in context)
        lens = block('.nav-selection-lens', gated)
        self.assertIn('background:var(--lens-glass-tint)', lens)
        self.assertIn('border-color:var(--lens-glass-edge)', lens)
        self.assertIn('inset 0 1px 0 var(--lens-glass-highlight)', lens)
        self.assertIn('var(--lens-glass-shadow)', lens)
        # No nested blur inside the filtered sidebar: the moving lens is translucent here, not
        # filtered. See FILTERED_GLASS above for the measurement that settled this.
        self.assertNotIn('backdrop-filter', lens)
        scoped = block('.sidebar-cta>.nav-selection-lens', gated)
        self.assertIn('background:var(--lens-glass-cta-tint)', scoped)
        self.assertIn('border-color:var(--lens-glass-cta-edge)', scoped)
        # The one context where the lens genuinely has something to refract.
        self.assertIn('blur(var(--lens-glass-blur))', scoped)
        self.assertIn('saturate(var(--lens-glass-saturation))', scoped)
        self.assertIn('-webkit-backdrop-filter:blur(var(--lens-glass-blur))', scoped)

    def test_no_filtered_surface_is_nested_inside_another_filtered_surface(self):
        """The performance rule A3's spring test caught: one blurred surface per column.

        A filtered element inside a filtered ancestor has to re-sample the ancestor's backdrop root
        every frame it moves, which is exactly what the travelling lens does. The masthead and the
        sidebar are siblings, and the only remaining filtered descendant is the approval-context
        lens, whose ancestor chain inside the sidebar is the CTA — itself unfiltered.
        """
        filtered = selectors(r'backdrop-filter\s*:\s*(?!none)')
        self.assertNotIn('.nav-selection-lens', filtered,
                         'the lens travelling inside the filtered sidebar must not add a nested blur')
        for selector in filtered:
            with self.subTest(selector=selector):
                self.assertFalse(selector.startswith('.app-sidebar ') or selector.startswith('.masthead '),
                                 'no descendant-combinator filter nests inside filtered chrome')
        # The sticky plate between the sidebar and the CTA lens stays a tint, never a filter.
        self.assertNotIn('.sidebar-actions', filtered)
        # Paint order and the shared node are A2's and are unchanged.
        self.assertIn('.sidebar-cta>.nav-selection-lens{z-index:1}', CSS)
        self.assertIn('.app-sidebar.nav-lens-ready #approvals[aria-current=page]', CSS)


class PhysicsIsUntouchedTest(unittest.TestCase):
    """A4 adds no JavaScript at all; these pin that claim where it matters."""

    def test_a3_spring_constants_are_unchanged(self):
        self.assertIn('const navigationLensSpring = {mass:1, stiffness:520, damping:40};', JS)
        self.assertEqual(len(re.findall(r'const navigationLensSpring = \{', JS)), 1)
        self.assertIn('const LENS_SETTLE_DISTANCE = .25, LENS_SETTLE_SPEED = 2;', JS)
        self.assertIn('const LENS_MAX_SUBSTEP = 1/120, LENS_MAX_FRAME = .032, LENS_STALL = .2;', JS)

    def test_a3_morph_constants_are_unchanged(self):
        self.assertIn('const LENS_MORPH_MAX = .07, LENS_MORPH_SPEED = 3000;', JS)

    def test_no_optical_renderer_frame_or_timer_was_introduced(self):
        for name in ('app.mjs', 'client.mjs'):
            with self.subTest(source=name):
                # No optical vocabulary reaches the script at all: the material is entirely a
                # stylesheet concern, so there is nothing for a renderer to drive per frame.
                self.assertNotRegex(CODE[name], r'backdrop-?[fF]ilter|saturate\(|blur\(px|glass|Glass'
                                                r'|--chrome-|--lens-glass-|webkitBackdrop')
                self.assertNotRegex(CODE[name], r'mousemove|pointermove|setInterval|requestIdleCallback'
                                                r'|DeviceOrientation|matchMedia\([\'"]\(prefers-reduced-trans')
        # The frame and timer inventory is A3's exactly. A later phase that legitimately adds frame
        # work must change these numbers deliberately rather than by accident.
        self.assertEqual(len(re.findall(r'requestAnimationFrame\(', JS)), 6)
        self.assertEqual(len(re.findall(r'cancelAnimationFrame\(', JS)), 3)
        self.assertEqual(len(re.findall(r'setTimeout\(', JS)), 7)
        self.assertEqual(len(re.findall(r'setInterval\(', JS)), 0)

    def test_material_properties_stay_stylesheet_owned(self):
        """The physics renderer writes presentation geometry only; A4 rides on it."""
        writes = re.findall(r'navigationLens\.style\.cssText = `([^`]*)`', LENS)
        self.assertEqual(len(writes), 1, 'one style write per frame, as A3 left it')
        properties = {declaration.split(':', 1)[0].strip()
                      for declaration in re.sub(r'\$\{[^}]*\}', '', writes[0]).split(';')
                      if declaration.strip()}
        self.assertEqual(properties, {'transform', 'width', 'height'})
        # The only other property the renderer may write is the temporary compositor hint, and it is
        # carried inside the travel expression rather than by a material rule.
        travel = re.search(r'const travel = running \? `([^`]*)`\s*\n?\s*: `([^`]*)`', LENS)
        self.assertIsNotNone(travel, 'the running/settled transform branch is unchanged')
        self.assertIn('will-change:transform', travel.group(1))
        self.assertNotIn('will-change', travel.group(2))
        for material in ('background', 'border', 'box-shadow', 'boxShadow', 'backdrop',
                         'opacity', 'filter', 'color'):
            with self.subTest(property=material):
                self.assertNotIn(material, writes[0])
                self.assertNotIn(material, travel.group(1))
                self.assertNotIn(material, travel.group(2))
        self.assertNotRegex(LENS, r'\.style\.(background|border|boxShadow|backdropFilter|opacity|color|filter)')
        self.assertNotRegex(LENS, r'setProperty\([\'"]--')

    def test_reduced_motion_removes_travel_without_removing_the_material(self):
        reduced = CSS[CSS.index('@media(prefers-reduced-motion:reduce)'):]
        reduced = reduced[:reduced.index('@media(prefers-reduced-motion:no-preference)')]
        self.assertIn('transition:none!important', reduced)
        # Motion and transparency are separate dimensions: the no-motion path never touches the
        # optical material, so a reduced-motion user still sees a selected glass lens.
        for optical in ('backdrop-filter', 'background', '--chrome-tint', '--lens-glass'):
            with self.subTest(property=optical):
                self.assertNotIn(optical, reduced)
        gate = CSS[CSS.index('@supports'):]
        self.assertNotIn('prefers-reduced-motion', gate[:gate.index('@media(forced-colors:active)')])


if __name__ == '__main__':
    unittest.main()
