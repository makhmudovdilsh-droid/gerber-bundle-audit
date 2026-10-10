"""Synthetic fixtures only: no customer or proprietary manufacturing files."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gerber_bundle_audit import AuditError, audit_bundle
from gerber_bundle_audit.cli import main


TOP = b"%FSLAX36Y36*%\n%TF.FileFunction,Copper,L1,Top*%\nM02*\n"
BOTTOM = b"%TF.FileFunction,Copper,L2,Bot*%\nM02*\n"
OUTLINE = b"%TF.FileFunction,Profile,NP*%\nM02*\n"


class BundleAuditTests(unittest.TestCase):
    def test_x2_directory_with_drill_and_hashes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Top_Copper.gbr").write_bytes(TOP)
            (root / "Bottom_Copper.gbr").write_bytes(BOTTOM)
            (root / "Board_Outline.gbr").write_bytes(OUTLINE)
            (root / "PTH.drl").write_bytes(b"M48\n;TYPE=PLATED\nM30\n")
            report = audit_bundle(root)
            self.assertTrue(report["ok"])
            self.assertEqual(report["summary"]["file_count"], 4)
            self.assertEqual({item["role"] for item in report["files"]},
                             {"copper_top", "copper_bottom", "board_outline", "drill_pth"})
            self.assertTrue(all(len(item["sha256"]) == 64 for item in report["files"]))

    def test_missing_outline_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp) / "Top_Copper.gbr").write_bytes(TOP)
            report = audit_bundle(temp)
            self.assertFalse(report["ok"])
            self.assertIn("NO_OUTLINE", {item["code"] for item in report["issues"]})

    def test_duplicate_role_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Top_Copper.gbr").write_bytes(TOP)
            (root / "another.gtl").write_bytes(TOP)
            (root / "Board_Outline.gbr").write_bytes(OUTLINE)
            report = audit_bundle(root)
            self.assertFalse(report["ok"])
            self.assertIn("DUPLICATE_ROLE", {item["code"] for item in report["issues"]})

    def test_zip_uses_x2_before_filename_and_warns(self):
        with tempfile.TemporaryDirectory() as temp:
            archive_path = Path(temp) / "synthetic.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("fabrication/Bottom_Copper.gbr", TOP)
                archive.writestr("fabrication/Board_Outline.gbr", OUTLINE)
            report = audit_bundle(archive_path)
            self.assertTrue(report["ok"])
            self.assertEqual(report["input_type"], "zip")
            self.assertIn("X2_FILENAME_CONFLICT", {item["code"] for item in report["issues"]})

    def test_empty_directory_is_not_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            report = audit_bundle(temp)
            self.assertFalse(report["ok"])
            self.assertEqual(report["summary"]["file_count"], 0)

    def test_cli_json_and_exit_code(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Top_Copper.gbr").write_bytes(TOP)
            (root / "Board_Outline.gbr").write_bytes(OUTLINE)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main([str(root), "--json"])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output.getvalue())["schema_version"], 1)

    def test_bad_input_is_audit_error(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(AuditError):
                audit_bundle(Path(temp) / "missing.zip")


if __name__ == "__main__":
    unittest.main()
