import unittest
from pathlib import Path


class BuildScriptTests(unittest.TestCase):
    def test_import_verification_runs_before_final_codesign_verification(self):
        script = Path("scripts/build-app.sh").read_text(encoding="utf-8")

        precompile = script.index("compileall")
        import_check = script.index("PyObjC imports ok")
        codesign_sign = script.index("codesign --force")
        signature_verify = script.index("screenlog.bundle_verify")

        self.assertLess(precompile, codesign_sign)
        self.assertLess(import_check, codesign_sign)
        self.assertLess(codesign_sign, signature_verify)

    def test_py2app_excludes_tkinter(self):
        setup_py = Path("setup.py").read_text(encoding="utf-8")

        self.assertIn("'excludes'", setup_py)
        self.assertIn("'tkinter'", setup_py)
        self.assertIn("'_tkinter'", setup_py)

    def test_build_script_resigns_after_bundle_mutation_even_without_identity(self):
        script = Path("scripts/build-app.sh").read_text(encoding="utf-8")

        self.assertIn('CODESIGN_IDENTITY="${SCREENLOG_CODESIGN_IDENTITY:--}"', script)
        self.assertIn('codesign --force --deep --sign "$CODESIGN_IDENTITY"', script)


if __name__ == "__main__":
    unittest.main()
