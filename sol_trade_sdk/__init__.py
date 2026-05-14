"""Compatibility package for editable installs.

The source tree keeps the implementation in ``src/``.  Hatch can rewrite that
package name for wheels, but editable installs cannot rewrite a prefix.  This
shim exposes ``src`` as ``sol_trade_sdk`` so tests and local development use the
same public import path as the built package.
"""

from pathlib import Path

_SOURCE_DIR = Path(__file__).resolve().parent.parent / "src"
__path__ = [str(_SOURCE_DIR)]

_init_file = _SOURCE_DIR / "__init__.py"
if _init_file.exists():
    exec(compile(_init_file.read_text(), str(_init_file), "exec"), globals())

