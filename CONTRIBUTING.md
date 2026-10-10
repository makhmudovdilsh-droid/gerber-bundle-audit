# Contributing

Please keep contributions scoped to this standalone utility. Do not copy code
from proprietary CAD products or upload customer Gerber, Excellon, PCB image,
project or manufacturing files.

Use synthetic fixtures in tests. Run:

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
```

Bug reports should include a minimal synthetic reproducer, the tool version,
Python version and expected/actual behavior. Never post credentials or private
board data in issues or pull requests.
