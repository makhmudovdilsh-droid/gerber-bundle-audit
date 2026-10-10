# Gerber Bundle Audit

A small, read-only command-line tool that inventories a Gerber/Excellon output
folder or ZIP archive. It identifies common layer roles from Gerber X2
`FileFunction` attributes or conventional filenames, computes SHA-256 hashes,
and flags obvious package problems such as a missing outline or duplicate roles.

This is an independent open-source utility. **MDPerformance CAD is a separate,
private-source product; its source code is not in this repository and is not
licensed under MIT.** The MIT license here applies only to this utility.

## Quick start

Python 3.10 or newer is required. No runtime packages or accounts are needed.

```sh
python -m pip install .
gerber-bundle-audit path/to/gerber-folder
gerber-bundle-audit path/to/fabrication.zip --json
```

To run without installation from a clone:

```sh
PYTHONPATH=src python -m gerber_bundle_audit path/to/gerber-folder
```

On Windows PowerShell, use `$env:PYTHONPATH = 'src'` before the last command.

The JSON output has a stable `schema_version` of `1`. Exit code `0` means no
basic package errors were found; `1` means at least one error was found; `2`
means the input could not be inspected. Warnings do not change the exit code.

## What it checks

- Read-only inventory of Gerber and Excellon files in a directory or ZIP.
- File size, SHA-256 and inferred role for every inspected file.
- Gerber X2 `FileFunction` attributes when available, with filename fallback.
- At least one copper file and one board-outline file.
- Duplicate known roles and disagreement between X2 role and filename role.

The tool **does not** validate copper geometry, nets, layer stack-up, drill
alignment, clearances, solder-mask webs, manufacturability or electrical
correctness. A clean result is not manufacturing approval. Always inspect the
actual files in an independent Gerber viewer and follow your fabricator's rules.

The tool does not upload files or contact a server. It reads only supported
Gerber/Excellon extensions, skips filesystem symlinks, and limits ZIP inputs to
10,000 entries, 100 MiB per inspected file and 500 MiB total uncompressed
inspected data. Do not paste confidential board data into public issues.

## Development

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
```

The tests use synthetic fixtures, not customer PCB files. Contributions are
welcome; see [CONTRIBUTING.md](CONTRIBUTING.md). Security reports can be sent
to `makhmudov.dilshd@gmail.com` without attaching confidential Gerbers.

## Sponsorship

If this open-source utility is useful to you, you can support its maintenance
through [GitHub Sponsors](https://github.com/sponsors/makhmudovdilsh-droid).
Sponsorship does not include access to MDPerformance CAD source code, a CAD
license, or private PCB projects.
