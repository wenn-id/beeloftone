"""A3 gives the one A2 lens physics: a cancellable RAF spring that keeps its velocity.

These assertions describe architecture, not pixels. Convergence, exact settling, velocity
continuity and idle cost are measured against the real renderer in
`tests/browser_navigation_spring.cjs`; what cannot be measured there is whether the code is
still shaped so those properties hold — one spring configuration, one physical state, a
retarget path that never zeroes a running velocity, separate measurement and motion frames,
and no CSS travel, timer loop or optical effect smuggled in beside the physics.
"""
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / 'beeloft' / 'static'
HTML = (STATIC / 'index.html').read_text(encoding='utf-8')
CSS = (STATIC / 'style.css').read_text(encoding='utf-8')
JS = (STATIC / 'app.mjs').read_text(encoding='utf-8')
# The same region A2's contract reads: everything the lens owns, and nothing else.
LENS = JS[JS.index('const navigationSurface ='):JS.index('// Drawer mobile.')]

# A1 published these values and A3 is not allowed to retune them. Stated here literally so a
# silent edit to the shared motion language fails alongside the spring contract.
MOTION_TOKENS = {'--motion-instant': '80ms', '--motion-fast': '120ms', '--motion-base': '180ms',
                 '--motion-enter': '220ms', '--motion-dialog': '260ms', '--motion-slow': '320ms',
                 '--ease-standard': 'cubic-bezier(.22,1,.36,1)',
                 '--ease-enter': 'cubic-bezier(.16,1,.3,1)',
                 '--ease-exit': 'cubic-bezier(.4,0,1,1)'}
VELOCITIES = ('vx', 'vy', 'vWidth', 'vHeight')


def body(name):
    """The balanced-brace body of one function declaration in the lens region."""
    start = LENS.index('function ' + name + '(')
    opening = LENS.index('{', start)
    depth, index = 0, opening
    while index < len(LENS):
        if LENS[index] == '{':
            depth += 1
        elif LENS[index] == '}':
            depth -= 1
            if depth == 0:
                return LENS[opening + 1:index]
        index += 1
    raise AssertionError(name + ' has no balanced body')


class OneLensStillOwnsSelectionTest(unittest.TestCase):
    def test_physics_did_not_add_a_second_or_ghost_lens(self):
        class Markup(HTMLParser):
            lenses = []

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if 'nav-selection-lens' in attrs.get('class', '').split():
                    self.lenses.append(attrs)

        parsed = Markup()
        parsed.feed(HTML)
        self.assertEqual(len(parsed.lenses), 1)
        self.assertEqual(parsed.lenses[0]['aria-hidden'], 'true')
        # No cloned, ghosted, faded or approval-specific second indicator hides the reparent.
        for fabrication in ('createElement', 'cloneNode', 'insertAdjacentHTML', 'outerHTML'):
            self.assertNotIn(fabrication, LENS)
        # Two rules, one class: the shared surface and the stacking level it needs inside the
        # approval CTA. Nothing declares a second indicator for the approval destination.
        # One class, two selector atoms: the shared surface and the stacking level it needs inside
        # the approval CTA. A4 added optical declarations for both of those atoms and grouped them
        # with the chrome in its fallback blocks, so the set is compared rather than the occurrence
        # list — but the set itself is still exactly two, with no third indicator and no pseudo-element
        # standing in for one.
        lens_targets = set()
        rules = re.sub(r'/\*.*?\*/', '', CSS, flags=re.S)
        for group in re.findall(r'([^{}@]*\.nav-selection-lens[^{}]*)\{', rules):
            for part in group.split(','):
                if '.nav-selection-lens' in part:
                    lens_targets.add(''.join(part.split()))
        self.assertEqual(lens_targets, {'.nav-selection-lens', '.sidebar-cta>.nav-selection-lens'})
        self.assertIn('.sidebar-cta>.nav-selection-lens{z-index:1}', CSS,
                      'the approval context reuses the one lens instead of owning another')
        self.assertEqual(len(re.findall(r'nav-selection-lens', HTML)), 2, 'one id, one class')

    def test_semantic_selection_still_precedes_and_outranks_presentation(self):
        active = JS[JS.index('function activeNavigation('):JS.index('// Registri tujuan workspace')]
        self.assertLess(active.index("setAttribute('aria-current','page')"),
                        active.index('scheduleNavigationLensSync()'))
        self.assertNotRegex(active, r'Motion|spring|await')
        self.assertIn('querySelector(\'[aria-current="page"]\')', LENS)
        # The controller may read the selected id; it may not write navigation, focus, session
        # or request state, and nothing semantic may wait for it.
        self.assertNotRegex(LENS, r'setAttribute\([\'"]aria-current|activateWorkspace\(|\.focus\('
                                  r'|api\.|epoch|Request\+\+|await ')
        self.assertNotIn('targetId', body('measureNavigationTarget'),
                         'measurement stays independent of which destination the spring is chasing')


class SpringConfigurationTest(unittest.TestCase):
    def test_one_central_configuration_declares_mass_stiffness_and_damping(self):
        declarations = re.findall(r'const navigationLensSpring = \{([^}]*)\}', LENS)
        self.assertEqual(len(declarations), 1, 'exactly one navigation-lens spring configuration')
        config = dict(re.findall(r'(\w+):([\d.]+)', declarations[0]))
        self.assertEqual(sorted(config), ['damping', 'mass', 'stiffness'])
        mass, stiffness, damping = (float(config['mass']), float(config['stiffness']),
                                    float(config['damping']))
        self.assertEqual(mass, 1)
        self.assertTrue(500 <= stiffness <= 540, stiffness)
        self.assertTrue(38 <= damping <= 42, damping)
        # High damping, deliberately just under critical: quick arrival, no cartoon bounce.
        ratio = damping / (2 * (stiffness * mass) ** .5)
        self.assertTrue(.82 <= ratio <= 1, f'damping ratio {ratio:.3f} is not a high-damping regime')
        # The integrator reads the configuration instead of carrying its own copies.
        step = body('navigationLensSpringStep')
        self.assertIn('navigationLensSpring', step)
        self.assertNotRegex(step, r'\d{2,}')

    def test_the_force_law_is_an_actual_spring_with_damping(self):
        step = body('navigationLensSpringStep')
        self.assertRegex(step, r'-\s*stiffness \* \(value - target\)')
        self.assertRegex(step, r'-\s*damping \* velocity')
        self.assertIn('/ mass', step)
        # Semi-implicit Euler: velocity is advanced first, then position uses the new velocity.
        self.assertLess(step.index('velocity + acceleration * step'), step.index('value + speed * step'))

    def test_frame_time_is_measured_in_seconds_with_bounded_substeps(self):
        constants = dict(re.findall(r'(LENS_MAX_SUBSTEP|LENS_MAX_FRAME|LENS_STALL) = ([\d./]+)', LENS))
        self.assertEqual(sorted(constants), ['LENS_MAX_FRAME', 'LENS_MAX_SUBSTEP', 'LENS_STALL'])
        self.assertEqual(constants['LENS_MAX_SUBSTEP'], '1/120')
        step = body('stepNavigationLensMotion')
        self.assertIn('(timestamp - previous) / 1000', step)
        self.assertIn('Math.min(elapsed, LENS_MAX_FRAME)', step)
        self.assertIn('Math.min(elapsed, LENS_MAX_SUBSTEP)', step)
        # 60Hz is never assumed, and an abnormal gap settles instead of being integrated.
        self.assertNotRegex(step, r'16\.6|1000 / 60|0\.016')
        self.assertRegex(step, r'elapsed > LENS_STALL.*settleNavigationLensMotion\(\)')
        self.assertRegex(step, r'!Number\.isFinite\(elapsed\) \|\| elapsed < 0')
        self.assertIn('Number.isFinite(navigationLensMotion[value])', step)
        self.assertRegex(step, r'width <= 0 \|\| navigationLensMotion\.height <= 0')


class PhysicalStateTest(unittest.TestCase):
    def setUp(self):
        self.state = re.search(r'const navigationLensMotion = \{(.*?)\n\};', LENS, re.S).group(1)

    def test_state_is_centre_dimensions_velocity_and_target_only(self):
        for field in ('cx', 'cy', 'width', 'height', 'targetCx', 'targetCy', 'targetWidth',
                      'targetHeight', 'initialized', 'context', 'running', 'lastTimestamp', *VELOCITIES):
            self.assertIn(field, self.state)
        # Centre-based, so position and size share one origin; no top-left edge state.
        self.assertNotRegex(self.state, r'\bleft\b|\btop\b|\bright\b|\bbottom\b')
        # No navigation, session or business truth is duplicated into the physics state.
        self.assertNotRegex(self.state, r'\bview\b|\brole\b|\buser\b|\bsection\b|\bnavId\b')
        self.assertEqual(len(re.findall(r'const navigationLensMotion = \{', LENS)), 1)

    def test_every_axis_is_integrated_settled_and_written_from_one_list(self):
        axes = re.search(r'const LENS_AXES = \[(.*?)\];', LENS, re.S).group(1)
        for value, speed, target in (('cx', 'vx', 'targetCx'), ('cy', 'vy', 'targetCy'),
                                     ('width', 'vWidth', 'targetWidth'),
                                     ('height', 'vHeight', 'targetHeight')):
            self.assertIn(f"['{value}','{speed}','{target}']", axes.replace(' ', ''))
        for consumer in ('stepNavigationLensMotion', 'navigationLensSettled',
                         'settleNavigationLensMotion'):
            with self.subTest(consumer=consumer):
                self.assertIn('LENS_AXES', body(consumer))


class VelocityContinuityTest(unittest.TestCase):
    def test_retargeting_replaces_the_target_and_never_the_velocity(self):
        retarget = body('retargetNavigationLens')
        for name in ('targetCx', 'targetCy', 'targetWidth', 'targetHeight'):
            self.assertIn(name + ' =', retarget)
        # The critical rule: a new destination may not zero, scale or re-seed a live velocity,
        # and may not rewrite the current physical position either.
        for velocity in VELOCITIES:
            with self.subTest(velocity=velocity):
                self.assertNotRegex(retarget, rf'\b{velocity}\s*[-+*/]?=')
        for position in ('cx', 'cy', 'width', 'height'):
            with self.subTest(position=position):
                self.assertNotRegex(retarget, rf'Motion\.{position}\s*[-+*/]?=')
        self.assertNotIn('cancelNavigationLensMotion(true)', retarget)
        self.assertIn('startNavigationLensMotion()', retarget)

    def test_velocity_is_only_zeroed_where_the_object_genuinely_stops_or_dies(self):
        # Both spellings count: a velocity named outright, and the axis-list alias the settle
        # path uses. Either way, only these two functions are allowed to write a zero.
        zeroing = re.compile('|'.join([rf'\b{velocity}\b\s*:?\s*0' for velocity in VELOCITIES]
                                      + [r'\[speed\]\s*=\s*0']))
        writers = {name for name in re.findall(r'function (\w+)\(', LENS)
                   if zeroing.search(body(name))}
        self.assertEqual(writers, {'settleNavigationLensMotion', 'cancelNavigationLensMotion'})
        # Discarding physical history is an explicit, separate decision from stopping the loop.
        cancel = body('cancelNavigationLensMotion')
        self.assertIn('if (!reset) return;', cancel)
        self.assertLess(cancel.index('if (!reset) return;'), cancel.index('vx:0'))
        self.assertIn('initialized:false', cancel)
        self.assertIn('cancelNavigationLensMotion(true)', body('hideNavigationLens'))

    def test_a_new_positioning_context_converts_coordinates_instead_of_restarting(self):
        rebase = body('rebaseNavigationLensContext')
        for term in ('clientLeft', 'clientTop', 'scrollLeft', 'scrollTop',
                     'getBoundingClientRect()', 'context.prepend(navigationLens)'):
            self.assertIn(term, rebase)
        # Same object, new basis: velocity and running state are untouched by the conversion.
        for velocity in (*VELOCITIES, 'running'):
            with self.subTest(field=velocity):
                self.assertNotRegex(rebase, rf'\b{velocity}\s*=')
        self.assertNotRegex(rebase, r'requestAnimationFrame|cancelAnimationFrame|settle|start')


class FrameOwnershipTest(unittest.TestCase):
    def test_measurement_and_motion_hold_separate_frame_handles(self):
        self.assertIn('let navigationLensSyncFrame = null, navigationLensMotionFrame = null;', LENS)
        self.assertNotIn('navigationLensFrame', LENS, 'one overloaded handle cannot own both jobs')
        schedule = body('scheduleNavigationLensSync')
        self.assertIn('navigationLensSyncFrame === null', schedule)
        self.assertNotIn('navigationLensMotionFrame', schedule)
        start = body('startNavigationLensMotion')
        self.assertIn('navigationLensMotionFrame !== null', start)
        self.assertNotIn('navigationLensSyncFrame', start)
        # A2's measurement callback still runs once and never re-schedules itself.
        sync = body('syncNavigationLens')
        self.assertNotIn('requestAnimationFrame', sync)
        self.assertNotIn('scheduleNavigationLensSync', sync)

    def test_the_motion_loop_stops_completely_when_it_settles(self):
        settle = body('settleNavigationLensMotion')
        self.assertIn('cancelNavigationLensMotion()', settle)
        self.assertNotIn('requestAnimationFrame', settle)
        cancel = body('cancelNavigationLensMotion')
        self.assertIn('cancelAnimationFrame(navigationLensMotionFrame)', cancel)
        self.assertIn('navigationLensMotionFrame = null', cancel)
        self.assertIn('running = false', cancel)
        # Exact final geometry, zero velocity: no fractional drift is left behind for ever.
        self.assertIn('navigationLensMotion[value] = navigationLensMotion[target]', settle)
        self.assertIn('navigationLensMotion[speed] = 0', settle)
        step = body('stepNavigationLensMotion')
        self.assertIn('navigationLensMotionFrame = null;', step)
        self.assertIn('navigationLensSettled()', step)
        settled = body('navigationLensSettled')
        self.assertIn('LENS_SETTLE_DISTANCE', settled)
        self.assertIn('LENS_SETTLE_SPEED', settled)
        self.assertEqual(len(re.findall(r'requestAnimationFrame\(stepNavigationLensMotion\)', LENS)), 2,
                         'the loop is re-armed from the step and started once; nothing else drives it')

    def test_no_interval_poll_or_second_animation_mechanism_exists(self):
        self.assertNotRegex(LENS, r'setInterval|setTimeout|queueMicrotask|\.animate\('
                                  r'|Animation\(|requestIdleCallback')
        # A visibility listener that runs for ever is not how a suspended tab is handled.
        self.assertNotIn('visibilitychange', LENS)
        self.assertNotRegex(LENS, r'\bwhile\s*\(\s*true\b|\bfor\s*\(\s*;;')

    def test_the_physics_loop_reads_no_layout(self):
        step = body('stepNavigationLensMotion') + body('renderNavigationLensMotion') \
            + body('navigationLensSpringStep') + body('navigationLensSettled') \
            + body('settleNavigationLensMotion')
        for read in ('getBoundingClientRect', 'getComputedStyle', 'offsetTop', 'offsetHeight',
                     'offsetWidth', 'clientWidth', 'clientHeight', 'getClientRects', 'scrollTop'):
            with self.subTest(read=read):
                self.assertNotIn(read, step)
        # Measurement stays in the bounded synchronisation layer where it already lived.
        self.assertIn('getBoundingClientRect', body('measureNavigationTarget'))


class RenderOnlyDeformationTest(unittest.TestCase):
    def test_deformation_is_derived_from_velocity_and_tightly_capped(self):
        caps = dict(re.findall(r'(LENS_MORPH_MAX|LENS_MORPH_SPEED) = ([\d.]+)', LENS))
        self.assertTrue(.06 <= float(caps['LENS_MORPH_MAX']) <= .08, caps)
        self.assertGreater(float(caps['LENS_MORPH_SPEED']), 0)
        render = body('renderNavigationLensMotion')
        self.assertIn('Math.min(LENS_MORPH_MAX', render)
        self.assertRegex(render, r'Math\.abs\(vy\) >= Math\.abs\(vx\)')
        self.assertRegex(render, r'vertical \? 1 - stretch / 2 : 1 \+ stretch')
        self.assertRegex(render, r'vertical \? 1 \+ stretch : 1 - stretch / 2')

    def test_deformation_never_feeds_back_into_physics_or_measurement(self):
        render = body('renderNavigationLensMotion')
        # The stretch is a local render value: it touches no target, no physical value, no
        # velocity and no measurement, so it cannot compound into runaway feedback.
        for field in ('targetCx', 'targetCy', 'targetWidth', 'targetHeight', *VELOCITIES):
            with self.subTest(field=field):
                self.assertNotRegex(render, rf'\b{field}\s*[-+*/]?=')
        self.assertNotRegex(render, r'navigationLensMotion\.(cx|cy|width|height)\s*[-+*/]?=')
        self.assertEqual(len(re.findall(r'\bstretch\b', body('stepNavigationLensMotion'))), 0)
        self.assertNotIn('stretch', body('retargetNavigationLens'))
        self.assertNotIn('stretch', body('measureNavigationTarget'))

    def test_position_moves_with_a_compositor_friendly_transform(self):
        render = body('renderNavigationLensMotion')
        self.assertRegex(render, r'width:\$\{width\}px;height:\$\{height\}px')
        # Travel asks the compositor for help twice over, and both requests are withdrawn on
        # settling: `will-change` is dropped *and* the 3D transform becomes a 2D one, because a
        # lingering 3D transform is itself enough to hold a separate layer for ever.
        travel, resting = re.search(r'running \? `([^`]*)`\s*:\s*`([^`]*)`', render).groups()
        self.assertIn('translate3d(', travel)
        self.assertIn('will-change:transform', travel)
        self.assertIn('translate(', resting)
        self.assertNotIn('translate3d', resting)
        self.assertNotIn('will-change', resting)
        self.assertNotIn('will-change', CSS)
        self.assertNotRegex(LENS, r'contain\s*:|backface-visibility|translateZ\(\s*[1-9]')


class PresentationBoundaryTest(unittest.TestCase):
    def test_the_lens_surface_has_no_css_travel_and_no_glass(self):
        block = re.search(r'\.nav-selection-lens\s*\{([^}]+)\}', CSS).group(1)
        for declaration in ('position:absolute', 'left:0', 'top:0', 'pointer-events:none',
                            'transition:none', 'animation:none'):
            self.assertIn(declaration, block)
        # Physics owns travel. A CSS transition on the lens would fight the integrator.
        self.assertNotRegex(block, r'transition\s*:\s*(?!none)|animation\s*:\s*(?!none)|@keyframes')
        self.assertNotRegex(CSS, r'\.nav-selection-lens[^{]*\{[^}]*transition:[^n]')
        # A3 forbade optical rendering outright; A4 owns it now. What has to stay true for the spring
        # is narrower and more important: the lens's own rule is still solid and unfiltered, so the
        # integrator is never writing into, or competing with, a material declaration. Glass is state
        # applied by the stylesheet on top of the physics, not a second thing the physics drives.
        self.assertNotIn('backdrop-filter', block)
        self.assertNotRegex(CSS, r'(?:^|[^-\w])(?:-webkit-)?filter\s*:[^;}]*blur\(')
        script = (STATIC / 'app.mjs').read_text(encoding='utf-8')
        self.assertNotRegex(script, r'backdrop-?[fF]ilter|saturate\(|--lens-glass-|--chrome-',
                            'no optical property is ever written by script')
        source = '\n'.join(p.read_text(encoding='utf-8') for p in STATIC.iterdir()
                           if p.suffix in ('.css', '.mjs', '.html'))
        self.assertNotRegex(source, r'navigator\.gpu|getContext\([\'"]webg|WebGPU|createShader'
                                    r'|refract\w*\s*[({=]|chromatic\w*\s*[({=]')

    def test_reduced_motion_snaps_instead_of_travelling(self):
        retarget = body('retargetNavigationLens')
        self.assertIn('reducedMotion()', retarget)
        self.assertLess(retarget.index('reducedMotion()'), retarget.index('startNavigationLensMotion()'),
                        'the preference is checked before any motion is started')
        self.assertRegex(retarget, r'reducedMotion\(\)[^;]*\{\s*settleNavigationLensMotion\(\); return;')
        # A preference change during flight cancels and snaps; it never replays old travel.
        listener = re.search(r"reducedMotionQuery\.addEventListener\('change', \(\) => \{(.*?)\}\);",
                             LENS, re.S).group(1)
        self.assertIn('settleNavigationLensMotion()', listener)
        self.assertIn('reducedMotion()', listener)
        self.assertNotIn('startNavigationLensMotion', listener)
        # No fake near-zero duration is used as a completion signal.
        self.assertNotRegex(CSS, r'0\.01ms|\.01s')

    def test_failed_presentation_still_leaves_navigation_and_the_legacy_selection_working(self):
        for guarded in ('stepNavigationLensMotion', 'syncNavigationLens', 'scheduleNavigationLensSync'):
            with self.subTest(function=guarded):
                self.assertIn('catch { hideNavigationLens(); }', body(guarded))
        hide = body('hideNavigationLens')
        self.assertIn("classList.remove('nav-lens-ready')", hide)
        self.assertIn("removeAttribute('style')", hide)
        self.assertIn('.app-sidebar.nav-lens-ready .nav-item[aria-current=page]{background:transparent}', CSS)
        for lifecycle in ('clearWorkspace', 'enterWorkspace'):
            with self.subTest(lifecycle=lifecycle):
                self.assertRegex(JS, rf'function {lifecycle}\([^)]*\)\s*\{{\s*hideNavigationLens\(\);')

    def test_the_shared_motion_language_of_a1_is_untouched(self):
        for token, value in MOTION_TOKENS.items():
            with self.subTest(token=token):
                self.assertEqual(re.findall(rf'{token}\s*:\s*([^;]+);', CSS)[0].strip(), value)
        # The spring is an addition beside the existing patterns, not a replacement for them.
        for helper in ('playEntryMotion', 'clearEntryMotion', 'closeDialogAnimated', 'hideNotice',
                       'playScanFeedback', 'playProgressSettle'):
            with self.subTest(helper=helper):
                self.assertIn(helper, JS)
                self.assertNotIn(helper, LENS)
        self.assertIn('button:active:not(:disabled){scale:.985}', CSS)
        self.assertNotRegex(LENS, r'motion-enter|is-ready|--motion-|motionMs\(')


if __name__ == '__main__':
    unittest.main()
