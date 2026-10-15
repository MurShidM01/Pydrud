"""No v3 naming anywhere in the tree.

``CONTRIBUTING.md`` bans it outright — "No v3 naming, protocol reset or
breaking version jump belongs in routine contributions" — and the 2.1.5
Material 3 upgrade (which ships on the v2 line) managed to leave 45
``v3.0`` labels scattered through docstrings, comments and the Java
templates. They were user-visible: ``help(pydrud.widgets.material)`` and
the generated Java both read as if a v3 release existed.

This test is the guard, so the labels cannot quietly return.
"""

from __future__ import annotations

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent

SCANNED_SUFFIXES = (".py", ".j2", ".md", ".toml", ".cfg", ".txt", ".yaml", ".yml")

#: Third-party strings that legitimately contain a "v3" token.
ALLOWED = (
    "libbarhopper_v3.so",   # ML Kit's barcode scanner, an Android artifact
    "_v3.so",               # any other vendored native library
    "CONTRIBUTING.md",      # the policy text itself must be able to say it
    "tests/test_version_naming.py",  # this guard must be able to name it
)

#: A version-like mention of a v3 release.
BANNED = re.compile(r"\bv3\.0(?:\.0)?\b|\bV3\.0(?:\.0)?\b|\bv3\.x\b", re.IGNORECASE)


def _scanned_files():
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.suffix not in SCANNED_SUFFIXES:
            continue
        parts = set(path.parts)
        if {".git", "__pycache__", "node_modules", "build", "dist"} & parts:
            continue
        yield path


class TestNoV3Naming(unittest.TestCase):
    def test_no_v3_version_labels_anywhere(self):
        offences = []
        for path in _scanned_files():
            # POSIX form so the ALLOWED entries match on every platform.
            relative = path.relative_to(ROOT).as_posix()
            if any(allowed in relative for allowed in ALLOWED):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for number, line in enumerate(text.splitlines(), start=1):
                if BANNED.search(line) and not any(a in line for a in ALLOWED):
                    offences.append(f"{relative}:{number}: {line.strip()[:110]}")
        self.assertEqual(
            [],
            offences,
            "v3 naming is banned by CONTRIBUTING.md; rephrase these as "
            "Material 3 / 2.x wording:\n  " + "\n  ".join(offences),
        )

    def test_docstrings_do_not_claim_a_v3_release(self):
        """The public modules must describe the v2 line."""
        import pydrud
        import pydrud.widgets.material
        import pydrud.widgets.theme

        for module in (pydrud, pydrud.widgets.material, pydrud.widgets.theme):
            doc = module.__doc__ or ""
            with self.subTest(module=module.__name__):
                self.assertNotRegex(doc.lower(), r"\bv3\b")


if __name__ == "__main__":
    unittest.main()
