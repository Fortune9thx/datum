#!/usr/bin/env python3
"""
Bundles contracts/datum_lib.py's content into contracts/Datum.py to produce
artifacts/Datum.bundled.py -- the ONE file Studio actually receives (sibling
imports fail Studio's contract validation).

Pattern follows the single-file-deploy bundler used across every prior
GenLayer project on this machine (see e.g.
C:\\Users\\HP\\Desktop\\precedence-settler\\scripts\\deploy.mjs and sibling
projects' build_bundle.py for the established convention): read the pure
logic module's source, strip its own module docstring/imports that the
target file doesn't need duplicated, and inline the remainder between two
marker comments in the deployable file, then write out a fresh bundle
artifact -- never hand-edit the generated file.

Usage: python scripts/build_bundle.py
Output: artifacts/Datum.bundled.py
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB_PATH = ROOT / "contracts" / "datum_lib.py"
CONTRACT_PATH = ROOT / "contracts" / "Datum.py"
OUT_DIR = ROOT / "artifacts"
OUT_PATH = OUT_DIR / "Datum.bundled.py"

BEGIN_MARKER = "# BEGIN DATUM_LIB INLINE"
END_MARKER = "# END DATUM_LIB INLINE"

MAX_BUNDLE_BYTES = 52224  # Studio Dev size ceiling documented across prior projects


def _strip_lib_source(lib_source: str) -> str:
    """Removes datum_lib.py's own module docstring and `from __future__`/
    stdlib imports that Datum.py already re-imports at the top of the
    bundle (json, hashlib, re are all imported once, at the top level, to
    avoid duplicate-import lint noise)."""
    # Drop the leading module docstring (first triple-quoted block).
    text = lib_source
    docstring_match = re.match(r'\s*""".*?"""\s*', text, flags=re.DOTALL)
    if docstring_match:
        text = text[docstring_match.end() :]

    # Drop `from __future__ import annotations` and the stdlib import lines
    # -- Datum.py's bundle header imports json/hashlib/re once already.
    lines = text.splitlines()
    kept = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("from __future__ import"):
            continue
        if stripped in ("import hashlib", "import json", "import re"):
            continue
        kept.append(line)
    return "\n".join(kept).strip("\n") + "\n"


class _DocstringStripper(ast.NodeTransformer):
    """Drops module/class/function docstrings (and any other bare string-
    literal expression statements, which are otherwise-inert doc comments)
    so the deployed bundle stays comment/prose-free without touching
    program semantics. Comments are already dropped for free by
    ast.unparse (it never re-emits them)."""

    def _strip_body(self, body: list) -> list:
        new_body = []
        for i, node in enumerate(body):
            if (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                continue  # drop bare string-literal statement (docstring)
            new_body.append(node)
        if not new_body:
            new_body = [ast.Pass()]
        return new_body

    def visit_Module(self, node):
        self.generic_visit(node)
        node.body = self._strip_body(node.body)
        return node

    def visit_ClassDef(self, node):
        self.generic_visit(node)
        node.body = self._strip_body(node.body)
        return node

    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        node.body = self._strip_body(node.body)
        return node

    def visit_AsyncFunctionDef(self, node):
        self.generic_visit(node)
        node.body = self._strip_body(node.body)
        return node


def _minify(source: str) -> str:
    """Parses `source` and re-emits it via ast.unparse with all docstrings
    stripped. ast.unparse never re-emits comments, so this also drops every
    `#` comment in one pass. Semantics-preserving (it's still an AST
    round-trip of the exact same parsed program)."""
    tree = ast.parse(source)
    tree = _DocstringStripper().visit(tree)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


def build() -> Path:
    if not LIB_PATH.exists():
        raise SystemExit(f"missing {LIB_PATH}")
    if not CONTRACT_PATH.exists():
        raise SystemExit(f"missing {CONTRACT_PATH}")

    contract_source = CONTRACT_PATH.read_text(encoding="utf-8")
    lib_source = LIB_PATH.read_text(encoding="utf-8")

    if BEGIN_MARKER not in contract_source or END_MARKER not in contract_source:
        raise SystemExit(
            f"Datum.py is missing the {BEGIN_MARKER} / {END_MARKER} markers"
        )

    inlined_lib = _strip_lib_source(lib_source)

    before, rest = contract_source.split(BEGIN_MARKER, 1)
    _, after = rest.split(END_MARKER, 1)

    # Reconstruct: everything up to and including the BEGIN marker line,
    # then the inlined lib body, then the END marker line onward.
    bundled = (
        before
        + BEGIN_MARKER
        + " -- inlined by scripts/build_bundle.py, do not hand-edit)\n"
        + inlined_lib.rstrip("\n")
        + "\n"
        + END_MARKER
        + after
    )

    # Add necessary top-level imports datum_lib.py used (hashlib, re) right
    # after the existing `import json` line in Datum.py's header, once.
    if "import hashlib" not in bundled.split(BEGIN_MARKER)[0]:
        bundled = bundled.replace("import json\n", "import hashlib\nimport json\nimport re\n", 1)

    # The first line MUST stay a bare, literal `# { "Depends": ... }` comment
    # with nothing above it -- ast/unparse would drop it entirely (it's a
    # comment). Split it off, minify everything else, then re-prepend it.
    first_line, _, remainder = bundled.partition("\n")
    minified_body = _minify(remainder)
    bundled = first_line + "\n" + minified_body + "\n"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(bundled, encoding="utf-8", newline="\n")

    size = len(bundled.encode("utf-8"))
    print(f"Wrote {OUT_PATH} ({size} bytes)")
    if size > MAX_BUNDLE_BYTES:
        print(
            f"WARNING: bundle exceeds documented Studio size ceiling "
            f"({size} > {MAX_BUNDLE_BYTES} bytes)"
        )
    else:
        print(f"OK: bundle is under the {MAX_BUNDLE_BYTES}-byte ceiling "
              f"({MAX_BUNDLE_BYTES - size} bytes to spare)")
    return OUT_PATH


if __name__ == "__main__":
    build()
