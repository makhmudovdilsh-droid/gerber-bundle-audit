"""Command-line interface for the standalone bundle auditor."""

import argparse
import json
import sys
from pathlib import Path

from .audit import AuditError, audit_bundle


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="gerber-bundle-audit",
        description="Read-only manifest and basic completeness checks for a Gerber/Excellon folder or ZIP",
    )
    parser.add_argument("bundle", type=Path, help="Gerber/Excellon directory or ZIP archive")
    parser.add_argument("--json", action="store_true", help="print a JSON report")
    args = parser.parse_args(argv)

    try:
        report = audit_bundle(args.bundle)
    except (AuditError, OSError, ValueError) as exc:
        print(f"gerber-bundle-audit: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Gerber Bundle Audit: {report['summary']['file_count']} inspected file(s)")
        for item in report["files"]:
            print(f"  {item['role']:<22} {item['size_bytes']:>10} B  {item['path']}")
        for issue in report["issues"]:
            print(f"{issue['severity'].upper()}: {issue['code']}: {issue['message']}")
        print("Basic package check: " + ("PASS" if report["ok"] else "FAIL"))
        print("Not a geometry, connectivity or manufacturability check.")
    return 0 if report["ok"] else 1
