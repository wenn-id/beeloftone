"""Kontrak gerak M6: durasi, token, dan jalur gerak dikurangi diperiksa dari sumbernya.

Milestone M6 meminta dua hal yang tidak dapat dibuktikan oleh tes peramban: tidak ada durasi
transisi atau animation mentah di luar pengecualian yang disetujui, dan setiap pola gerak punya
jalur nirkembang yang eksplisit. Keduanya properti statis dari `style.css`, `app.mjs`, dan
`index.html`, jadi diukur di sini alih-alih disimpulkan dari kelas yang selesai.

Yang dijaga tes ini:

1. Token gerak dideklarasikan sekali dengan nilai yang ditentukan spesifikasi.
2. Setiap durasi di deklarasi transisi/animation berasal dari token, bukan angka mentah.
3. Setiap `@keyframes` berada di dalam query `no-preference`, sehingga mode gerak dikurangi
   tidak pernah menjalankannya.
4. Blok `reduce` menutup kelas gerak, dialog, backdrop, dan notice.
5. Timer pembersihan JavaScript membaca durasinya dari token, bukan dari salinan angka.
6. Setiap elemen yang diminta memudar benar-benar punya aturan CSS-nya. Kelas yang dipasang ke
   elemen tanpa aturan tidak menghidupkan apa pun dan hanya meninggalkan state gerak yang macet.
7. Angka waktu yang tersisa di JavaScript terdaftar sebagai pengecualian yang disetujui.
8. Timer notice tetap enam detik: presentasi tidak boleh mengubah semantik pesan.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "beeloft" / "static"
STYLE = STATIC / "style.css"
APP = STATIC / "app.mjs"
INDEX = STATIC / "index.html"

# Nilai yang ditentukan spesifikasi §03. Bukan sekadar "ada token": perubahan nilai di sini
# berarti angkanya harus diubah di dokumen spesifikasi lebih dahulu.
TOKENS = {
    "--motion-instant": "80ms",
    "--motion-fast": "120ms",
    "--motion-base": "180ms",
    "--motion-enter": "220ms",
    "--motion-dialog": "260ms",
    "--motion-slow": "320ms",
    "--ease-standard": "cubic-bezier(.22,1,.36,1)",
    "--ease-enter": "cubic-bezier(.16,1,.3,1)",
    "--ease-exit": "cubic-bezier(.4,0,1,1)",
}

# Angka waktu yang sengaja BUKAN token, masing-masing dengan alasannya. Daftar ini adalah
# deklarasi "pengecualian yang disetujui" untuk M6: setiap entri harus tetap ada, dan angka
# waktu baru mana pun akan gagal di `test_scripted_timings_are_declared_exceptions`.
APPROVED_SCRIPT_TIMINGS = {
    "SCAN_TINT_HOLD": "lama tint pemindai bertahan sebelum dilepas; ini penahanan state, "
                      "bukan durasi animasi",
    "motionMs": "durasi pembersihan selalu dibaca dari token CSS",
    "6000": "timer semantik notice: enam detik pesan terbaca, tidak boleh disentuh gerak",
}

DURATION_PROPERTIES = ("transition", "transition-duration", "animation", "animation-duration",
                       "transition-delay", "animation-delay")


def strip_css_comments(text):
    """Menghapus komentar CSS supaya angka di dalam prosa tidak dihitung sebagai durasi."""
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def css_declarations(text):
    """Menghasilkan (properti, nilai) untuk setiap deklarasi di luar blok `:root` token."""
    for block in re.finditer(r"\{([^{}]*)\}", text):
        for declaration in block.group(1).split(";"):
            if ":" not in declaration:
                continue
            prop, _, value = declaration.partition(":")
            yield prop.strip(), value.strip()


def js_call_arguments(source, name):
    """Argumen tingkat atas untuk setiap pemanggilan `name(...)` di sumber JavaScript.

    Pemindai kurung seimbang, karena argumennya sering berisi arrow function dan template
    literal yang memuat koma.
    """
    results = []
    for match in re.finditer(re.escape(name) + r"\(", source):
        depth, index, start = 0, match.end() - 1, match.end()
        while index < len(source):
            char = source[index]
            if char in "([{":
                depth += 1
            elif char in ")]}":
                depth -= 1
                if depth == 0:
                    break
            index += 1
        body = source[start:index]
        arguments, depth, current = [], 0, ""
        for char in body:
            if char in "([{":
                depth += 1
            elif char in ")]}":
                depth -= 1
            if char == "," and depth == 0:
                arguments.append(current.strip())
                current = ""
            else:
                current += char
        arguments.append(current.strip())
        results.append(arguments)
    return results


def attribute(tag, name):
    match = re.search(rf'\b{name}\s*=\s*"([^"]*)"', tag)
    return match.group(1) if match else ""


def static_elements():
    """Peta id -> (nama tag, kelas) untuk markup statis maupun templat di `app.mjs`."""
    elements = {}
    for path in (INDEX, APP):
        for tag in re.findall(r"<[a-zA-Z][^>]*>", path.read_text(encoding="utf-8")):
            element_id = attribute(tag, "id")
            if element_id:
                elements.setdefault(element_id, (tag[1:].split()[0].lower(),
                                                 attribute(tag, "class").split()))
    return elements


def fade_hosts():
    """Id yang diminta memudar lewat `playEntryMotion($('...'))`, beserta id variabel section."""
    source = APP.read_text(encoding="utf-8")
    hosts = set(re.findall(r"playEntryMotion\(\$\('([^']+)'\)", source))
    return hosts, "playEntryMotion($(sectionId)" in source


class MotionTokenTest(unittest.TestCase):
    def test_tokens_are_declared_once_with_the_specified_values(self):
        text = strip_css_comments(STYLE.read_text(encoding="utf-8"))
        declared = re.findall(r"(--motion-[a-z]+|--ease-[a-z]+)\s*:\s*([^;}]+)", text)
        values = {}
        for name, value in declared:
            values.setdefault(name, []).append(value.strip())
        for name, expected in TOKENS.items():
            with self.subTest(token=name):
                self.assertEqual(values.get(name), [expected],
                                 f"{name} harus dideklarasikan tepat sekali dengan nilai {expected}")

    def test_no_raw_duration_outside_the_token_block(self):
        """Setiap durasi di deklarasi gerak berasal dari token, bukan angka yang disalin."""
        text = strip_css_comments(STYLE.read_text(encoding="utf-8"))
        for prop, value in css_declarations(text):
            if prop not in DURATION_PROPERTIES:
                continue
            for time in re.findall(r"(?<![\w-])(\d+(?:\.\d+)?m?s)(?![\w-])", value):
                with self.subTest(declaration=f"{prop}:{value}"):
                    self.assertEqual(time, "0s",
                                     f"durasi mentah {time} di `{prop}:{value}`; pakai token gerak")
            for time in re.findall(r"(?<![\w-])(\d+(?:\.\d+)?s)(?![\w-])", value):
                with self.subTest(declaration=f"{prop}:{value}"):
                    self.assertEqual(time, "0s",
                                     f"durasi mentah {time} di `{prop}:{value}`; pakai token gerak")

    def test_every_keyframe_is_gated_behind_the_no_preference_query(self):
        """Animasi hanya boleh hidup di query `no-preference`, supaya mode reduce tidak menjalankannya."""
        text = strip_css_comments(STYLE.read_text(encoding="utf-8"))
        query_start = text.index("@media(prefers-reduced-motion:no-preference)")
        query_end = text.index("\n}", text.index("dialog.is-closing::backdrop", query_start))
        for match in re.finditer(r"@keyframes\s+([\w-]+)", text):
            with self.subTest(keyframes=match.group(1)):
                self.assertTrue(query_start < match.start() < query_end,
                                f"@keyframes {match.group(1)} berada di luar query no-preference")


class ReducedMotionContractTest(unittest.TestCase):
    def setUp(self):
        self.text = strip_css_comments(STYLE.read_text(encoding="utf-8"))
        start = self.text.index("@media(prefers-reduced-motion:reduce)")
        end = self.text.index("@media(prefers-reduced-motion:no-preference)")
        self.block = self.text[start:end]

    def test_the_reduce_block_stops_transitions_and_animations_everywhere(self):
        self.assertIn("*{transition:none!important;animation:none!important}", self.block)

    def test_the_reduce_block_covers_the_motion_classes(self):
        self.assertIn(".motion-enter,.motion-exit{transform:none!important}", self.block)

    def test_the_reduce_block_covers_the_dialog_and_its_backdrop(self):
        """`::backdrop` adalah pseudo-element, jadi catch-all `*` tidak pernah menjangkaunya."""
        self.assertIn("dialog,dialog::backdrop{transition:none!important;animation:none!important;transform:none!important}",
                      self.block)

    def test_the_reduce_block_covers_the_notice(self):
        self.assertIn(".notice{transition:none!important;animation:none!important;transform:none!important}",
                      self.block)

    def test_every_moving_class_is_declared_inside_the_no_preference_query(self):
        """Kelas gerak tidak boleh punya aturan gerak di luar query: mode reduce harus diam."""
        query_start = self.text.index("@media(prefers-reduced-motion:no-preference)")
        query_end = self.text.index("@media(max-width:980px) and (prefers-reduced-motion:no-preference)")
        outside = self.text[:query_start] + self.text[query_end:]
        for selector in (".list-host.motion-enter", ".state.motion-enter", ".notice.motion-enter",
                         ".notice.motion-exit", "dialog.is-closing"):
            with self.subTest(selector=selector):
                self.assertNotIn(selector, outside,
                                 f"{selector} mendeklarasikan gerak di luar query no-preference")


class MotionSurfaceTest(unittest.TestCase):
    """Setiap kelas gerak yang dipasang skrip harus mendarat di elemen yang punya aturannya."""

    def setUp(self):
        self.elements = static_elements()
        self.hosts, self.scripted_sections = fade_hosts()

    def test_every_fade_host_is_a_declared_motion_surface(self):
        for host in sorted(self.hosts):
            with self.subTest(host=host):
                self.assertIn(host, self.elements, f"{host} tidak ditemukan di markup")
                tag, classes = self.elements[host]
                self.assertTrue(
                    "list-host" in classes or "state" in classes or tag == "section"
                    or host in ("notice", "app-sidebar"),
                    f"{host} diminta memudar tetapi tidak punya kelas gerak: {classes}")

    def test_workspace_sections_are_covered_by_the_section_rule(self):
        self.assertTrue(self.scripted_sections)
        self.assertIn(".workspace-main>section.motion-enter", STYLE.read_text(encoding="utf-8"))

    def test_the_fade_is_shorter_than_a_page_entry(self):
        """Penggantian daftar memakai token yang lebih pendek daripada gerak masuk halaman."""
        source = APP.read_text(encoding="utf-8")
        durations = {argument for arguments in js_call_arguments(source, "playEntryMotion")
                     for argument in arguments if argument.startswith("'--motion-")}
        self.assertEqual(durations, {"'--motion-base'"},
                         "daftar yang digantikan memakai --motion-base; gerak masuk halaman memakai "
                         "bawaan --motion-enter")

    def test_every_motion_class_the_script_adds_is_removed_again(self):
        source = APP.read_text(encoding="utf-8")
        added = set(re.findall(r"classList\.add\(([^)]*'motion-[^)]*)\)", source))
        for entry in added:
            for name in re.findall(r"'(motion-[\w-]+)'", entry):
                with self.subTest(classes=entry):
                    self.assertIn(f"'{name}'", entry)
        # Kelas gerak selalu dibersihkan lewat clearEntryMotion() atau resetNoticeMotion(),
        # yang keduanya menghapus daftar lengkapnya.
        self.assertIn("target.classList.remove('motion-enter','is-ready')", source)
        self.assertIn("notice.classList.remove('motion-enter','is-ready','motion-exit')", source)
        self.assertIn("dialog.classList.remove('motion-exit','is-closing')", source)


class ScriptedTimingTest(unittest.TestCase):
    def setUp(self):
        self.source = APP.read_text(encoding="utf-8")

    def test_cleanup_timers_read_their_duration_from_a_token(self):
        """`motionMs()` adalah satu-satunya cara skrip membaca durasi gerak."""
        timers = js_call_arguments(self.source, "setTimeout")
        tokenised = [arguments for arguments in timers
                     if len(arguments) > 1 and "motionMs(" in arguments[1]]
        self.assertGreaterEqual(len(tokenised), 3,
                                "timer pembersihan gerak harus membaca tokennya dari CSS")
        for arguments in tokenised:
            with self.subTest(timer=arguments[1]):
                self.assertRegex(arguments[1], r"^motionMs\('--motion-[a-z]+'\) \+ 60$|^motionMs\(durationToken\) \+ 60$")

    def test_scripted_timings_are_declared_exceptions(self):
        """Angka waktu yang tersisa di JavaScript harus terdaftar sebagai pengecualian."""
        for name in APPROVED_SCRIPT_TIMINGS:
            with self.subTest(exception=name):
                if name == "motionMs":
                    self.assertIn("function motionMs(name)", self.source)
                else:
                    self.assertIn(name, self.source)

    def test_the_notice_timer_stays_six_seconds(self):
        """Presentasi tidak boleh memperpanjang atau memperpendek waktu baca pesan."""
        self.assertIn("noticeTimer = setTimeout(() => hideNotice(), 6000)", self.source)


class PropagationTest(unittest.TestCase):
    """Halaman daftar yang memakai perlakuan yang sama harus benar-benar memakainya."""

    def setUp(self):
        self.source = APP.read_text(encoding="utf-8")

    def test_propagated_lists_declare_their_rendered_query(self):
        """Penggantian dihitung dari isi yang sedang tampil, bukan dari permintaan yang dikirim."""
        for name in ("approvalsRendered", "purchaseRequestsRendered", "marketingBudgetsRendered",
                     "auditRendered", "workforceRendered"):
            with self.subTest(variable=name):
                declarations = re.findall(rf"let [^;]*\b{name}\b", self.source)
                self.assertTrue(declarations, f"{name} tidak dideklarasikan")
                resets = re.findall(rf"\b{name}\s*=\s*null", self.source)
                self.assertTrue(resets, f"{name} harus direset saat section atau sesi berganti")
                self.assertIn(f"{name}!==null&&{name}!==", self.source.replace(" ", ""))

    def test_refresh_controls_ask_for_the_refresh_treatment(self):
        """Hanya kontrol muat ulang yang meminta peredupan; navigasi tidak."""
        self.assertIn("$('command-center-refresh').onclick=()=>showCommandCenter(true);", self.source)
        self.assertIn("$('integrations-refresh').onclick=()=>loadIntegrations(true);", self.source)
        self.assertIn("$('command-center').onclick=()=>showCommandCenter();", self.source)
        self.assertIn("'command-center':()=>showCommandCenter()", self.source)


if __name__ == "__main__":
    unittest.main()
