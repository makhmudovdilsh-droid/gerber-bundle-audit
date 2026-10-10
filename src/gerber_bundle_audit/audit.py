"""Read-only, deliberately limited Gerber/Excellon package checks.

This module does not parse board geometry or validate manufacturing rules.
"""

from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path
from typing import BinaryIO


class AuditError(Exception):
    """The input cannot be inspected safely or completely."""


SUPPORTED_SUFFIXES = {
    ".gbr", ".ger", ".gtl", ".gbl", ".gts", ".gbs", ".gtp",
    ".gbp", ".gto", ".gbo", ".gko", ".gm1", ".drl", ".xln",
    ".exc",
}
MAX_FILES = 10_000
MAX_FILE_BYTES = 100 * 1024 * 1024
MAX_TOTAL_BYTES = 500 * 1024 * 1024
HEAD_BYTES = 64 * 1024
CHUNK_BYTES = 1024 * 1024
FILE_FUNCTION_RE = re.compile(r"%TF\.FileFunction,([^*%]*)\*%", re.IGNORECASE)


def _candidate(name: str) -> bool:
    return Path(name).suffix.lower() in SUPPORTED_SUFFIXES


def _role_from_x2(file_function: str | None) -> str | None:
    if not file_function:
        return None
    tokens = [token.strip().lower() for token in file_function.split(",")]
    kind = tokens[0]
    side = "top" if "top" in tokens else "bottom" if "bot" in tokens or "bottom" in tokens else None
    if kind == "copper":
        if side:
            return f"copper_{side}"
        layer = next((token for token in tokens[1:] if re.fullmatch(r"l\d+", token)), None)
        return f"copper_{layer}" if layer else "copper_unknown"
    if kind in {"soldermask", "solder_mask"}:
        return f"soldermask_{side}" if side else "soldermask_unknown"
    if kind in {"paste", "solderpaste"}:
        return f"paste_{side}" if side else "paste_unknown"
    if kind in {"legend", "silkscreen"}:
        return f"silkscreen_{side}" if side else "silkscreen_unknown"
    if kind in {"profile", "boardoutline", "board_outline"}:
        return "board_outline"
    return None


def _role_from_filename(name: str) -> str | None:
    path = Path(name)
    suffix = path.suffix.lower()
    extension_roles = {
        ".gtl": "copper_top", ".gbl": "copper_bottom",
        ".gts": "soldermask_top", ".gbs": "soldermask_bottom",
        ".gtp": "paste_top", ".gbp": "paste_bottom",
        ".gto": "silkscreen_top", ".gbo": "silkscreen_bottom",
        ".gko": "board_outline", ".gm1": "board_outline",
    }
    if suffix in extension_roles:
        return extension_roles[suffix]

    stem = re.sub(r"[^a-z0-9]+", "_", path.stem.lower()).strip("_")
    if suffix in {".drl", ".xln", ".exc"}:
        if "npth" in stem or "non_plated" in stem or "nonplated" in stem:
            return "drill_npth"
        if "pth" in stem or "plated" in stem:
            return "drill_pth"
        return "drill_unknown"
    if "outline" in stem or "edge_cuts" in stem or "board_profile" in stem:
        return "board_outline"
    inner = re.search(r"(?:inner|internal)_?copper_?l?(\d+)", stem)
    if inner:
        return f"copper_l{inner.group(1)}"
    side = "top" if "top" in stem else "bottom" if "bottom" in stem or "bot" in stem else None
    if side and "copper" in stem:
        return f"copper_{side}"
    if side and ("solder_mask" in stem or "soldermask" in stem):
        return f"soldermask_{side}"
    if side and "paste" in stem:
        return f"paste_{side}"
    if side and ("silkscreen" in stem or "legend" in stem):
        return f"silkscreen_{side}"
    return None


def _drill_header_role(head: bytes) -> str | None:
    text = head.decode("ascii", errors="ignore").lower()
    if re.search(r";\s*type\s*=\s*(?:non[_ -]?plated|npth)", text):
        return "drill_npth"
    if re.search(r";\s*type\s*=\s*(?:plated|pth)", text):
        return "drill_pth"
    return None


def _inspect_stream(name: str, stream: BinaryIO) -> tuple[dict, str | None, str | None]:
    digest = hashlib.sha256()
    head = bytearray()
    actual_size = 0
    while chunk := stream.read(CHUNK_BYTES):
        actual_size += len(chunk)
        if actual_size > MAX_FILE_BYTES:
            raise AuditError(f"File exceeds {MAX_FILE_BYTES} bytes: {name}")
        digest.update(chunk)
        if len(head) < HEAD_BYTES:
            head.extend(chunk[: HEAD_BYTES - len(head)])

    text = head.decode("ascii", errors="ignore")
    match = FILE_FUNCTION_RE.search(text)
    file_function = match.group(1).strip() if match else None
    x2_role = _role_from_x2(file_function)
    filename_role = _role_from_filename(name)
    drill_role = _drill_header_role(head) if Path(name).suffix.lower() in {".drl", ".xln", ".exc"} else None
    if x2_role:
        role, source = x2_role, "gerber_x2"
    elif drill_role:
        role, source = drill_role, "excellon_header"
    elif filename_role:
        role, source = filename_role, "filename"
    else:
        role, source = "unknown", "unknown"
    return ({
        "path": name.replace("\\", "/"),
        "size_bytes": actual_size,
        "sha256": digest.hexdigest(),
        "role": role,
        "role_source": source,
        "x2_file_function": file_function,
    }, x2_role, filename_role)


def _check_size_limits(entries: list[tuple[str, int]]) -> None:
    if len(entries) > MAX_FILES:
        raise AuditError(f"Too many supported files: {len(entries)} > {MAX_FILES}")
    total = 0
    for name, size in entries:
        if size > MAX_FILE_BYTES:
            raise AuditError(f"File exceeds {MAX_FILE_BYTES} bytes: {name}")
        total += size
        if total > MAX_TOTAL_BYTES:
            raise AuditError(f"Total inspected data exceeds {MAX_TOTAL_BYTES} bytes")


def _issue(severity: str, code: str, message: str) -> dict[str, str]:
    return {"severity": severity, "code": code, "message": message}


def audit_bundle(path: Path | str) -> dict:
    """Inspect a directory or ZIP without changing the input or making requests."""
    bundle = Path(path)
    files = []
    issues = []
    if bundle.is_dir():
        input_type = "directory"
        paths = sorted(
            (item for item in bundle.rglob("*") if not item.is_symlink() and item.is_file() and _candidate(item.name)),
            key=lambda item: item.relative_to(bundle).as_posix().lower(),
        )
        _check_size_limits([(item.relative_to(bundle).as_posix(), item.stat().st_size) for item in paths])
        for item in paths:
            name = item.relative_to(bundle).as_posix()
            with item.open("rb") as stream:
                record, x2_role, filename_role = _inspect_stream(name, stream)
            files.append(record)
            if x2_role and filename_role and x2_role != filename_role:
                issues.append(_issue("warning", "X2_FILENAME_CONFLICT", f"{name}: X2={x2_role}, filename={filename_role}"))
    elif bundle.is_file() and bundle.suffix.lower() == ".zip":
        input_type = "zip"
        try:
            with zipfile.ZipFile(bundle) as archive:
                entries = sorted(
                    (item for item in archive.infolist() if not item.is_dir() and _candidate(item.filename)),
                    key=lambda item: item.filename.lower(),
                )
                _check_size_limits([(item.filename, item.file_size) for item in entries])
                for item in entries:
                    with archive.open(item) as stream:
                        record, x2_role, filename_role = _inspect_stream(item.filename, stream)
                    files.append(record)
                    if x2_role and filename_role and x2_role != filename_role:
                        issues.append(_issue("warning", "X2_FILENAME_CONFLICT", f"{item.filename}: X2={x2_role}, filename={filename_role}"))
        except (zipfile.BadZipFile, RuntimeError) as exc:
            raise AuditError(f"Cannot read ZIP archive: {exc}") from exc
    else:
        raise AuditError("Input must be an existing directory or ZIP archive")

    if not files:
        issues.append(_issue("error", "NO_FILES", "No supported Gerber or Excellon files found"))
    else:
        roles: dict[str, list[str]] = {}
        for item in files:
            role = item["role"]
            if role != "unknown" and not role.endswith("_unknown"):
                roles.setdefault(role, []).append(item["path"])
            elif role == "unknown":
                issues.append(_issue("warning", "UNKNOWN_ROLE", f"Could not identify role: {item['path']}"))
        for role, names in sorted(roles.items()):
            if len(names) > 1:
                issues.append(_issue("error", "DUPLICATE_ROLE", f"{role}: {', '.join(names)}"))
        if not any(item["role"].startswith("copper_") for item in files):
            issues.append(_issue("error", "NO_COPPER", "No copper layer was identified"))
        if "board_outline" not in roles:
            issues.append(_issue("error", "NO_OUTLINE", "No board-outline file was identified"))

    error_count = sum(issue["severity"] == "error" for issue in issues)
    warning_count = sum(issue["severity"] == "warning" for issue in issues)
    return {
        "schema_version": 1,
        "input_type": input_type,
        "files": files,
        "issues": issues,
        "summary": {
            "file_count": len(files),
            "total_bytes": sum(item["size_bytes"] for item in files),
            "errors": error_count,
            "warnings": warning_count,
        },
        "ok": error_count == 0,
    }
