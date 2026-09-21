import re
import unittest
from pathlib import Path

# README menyatakan jumlah test Python tetap ("berisi N test"). Angka itu usang
# setiap kali test ditambah tanpa README disentuh; issue #37 menemukan 354 di
# README padahal discovery menjalankan 527. Test ini memaksa angka mengikuti
# discovery, atau README harus mengganti kalimatnya dengan redaksi tanpa angka.
REPO = Path(__file__).resolve().parent.parent
README = REPO / "README.md"
# Hanya modul Python test yang dihitung: runner browser (run_browser.py) dan
# modul .cjs/.mjs adalah alat, bukan TestCase.
PATTERN = re.compile(r"Suite Python berisi (\d+) test")


class ReadmeTestCountTest(unittest.TestCase):
    def discovered_count(self):
        loader = unittest.TestLoader()
        return loader.discover(str(REPO / "tests")).countTestCases()

    def test_readme_states_current_test_count(self):
        text = README.read_text(encoding="utf-8")
        match = PATTERN.search(text)
        self.assertIsNotNone(match, "README tidak menyebut jumlah test Python; "
                            "sederhanakan kalimatnya tanpa angka atau perbarui pola "
                            "test ini")
        stated = int(match.group(1))
        actual = self.discovered_count()
        self.assertEqual(stated, actual,
                         f"README menyebut {stated} test, discovery menemukan "
                         f"{actual}. Perbarui README atau jalankan ulang "
                         f"`python -m unittest discover -s tests`.")


if __name__ == "__main__":
    unittest.main()
