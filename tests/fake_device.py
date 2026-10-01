"""Backwards-compatible shim: the harness now ships inside the package.

``pydrud.testing`` is public API, so *users* can test their own apps exactly
the way the framework tests itself.
"""

from pydrud.testing import AppTester, FakeDevice, RenderedNode, run_app  # noqa: F401

__all__ = ["FakeDevice", "RenderedNode", "run_app", "AppTester"]
