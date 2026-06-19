import subprocess
import unittest
from pathlib import Path

from screenlog.bundle_verify import (
    BundleSignatureError,
    parse_codesign_details,
    verify_bundle_signature,
)


class BundleVerifyTests(unittest.TestCase):
    def test_parse_codesign_details_reads_team_identifier(self):
        details = parse_codesign_details(
            """
Executable=/tmp/ScreenLog.app/Contents/MacOS/ScreenLog
Identifier=com.screenlog.app
TeamIdentifier=ABCDE12345
"""
        )

        self.assertEqual(details["Identifier"], "com.screenlog.app")
        self.assertEqual(details["TeamIdentifier"], "ABCDE12345")

    def test_verify_bundle_signature_rejects_missing_team_identifier_when_required(self):
        def runner(command, **kwargs):
            if command[:2] == ["codesign", "--verify"]:
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="",
                stderr="Identifier=com.screenlog.app\nTeamIdentifier=not set\n",
            )

        with self.assertRaises(BundleSignatureError):
            verify_bundle_signature(
                Path("/tmp/ScreenLog.app"),
                require_team_id=True,
                runner=runner,
            )

    def test_verify_bundle_signature_rejects_unexpected_team_identifier(self):
        def runner(command, **kwargs):
            if command[:2] == ["codesign", "--verify"]:
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="",
                stderr="Identifier=com.screenlog.app\nTeamIdentifier=ABCDE12345\n",
            )

        with self.assertRaises(BundleSignatureError):
            verify_bundle_signature(
                Path("/tmp/ScreenLog.app"),
                expected_team_id="VWXYZ67890",
                runner=runner,
            )


if __name__ == "__main__":
    unittest.main()
