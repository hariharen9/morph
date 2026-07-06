"""
Auto-discovers and imports every converter module in this package.

Dropping a new file in morph/converters/ (that calls `register(...)` at
import time) is enough to add a conversion — nothing else needs editing.
Files prefixed with `_` are treated as private engines (e.g. _csv_to_excel.py)
and are not auto-imported themselves; they're imported by whichever module
wraps them.
"""

from __future__ import annotations

import importlib
import pkgutil

for _finder, _name, _ispkg in pkgutil.iter_modules(__path__):
    if _name.startswith("_"):
        continue
    importlib.import_module(f"{__name__}.{_name}")
