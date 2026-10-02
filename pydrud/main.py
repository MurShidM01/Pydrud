"""Deprecated alias for :mod:`pydrud.runtime.app`.

``App`` moved to ``pydrud.runtime.app`` in 2.0 so that the top level of
the package describes layers (runtime, widgets, services, data, commands)
rather than holding a 1 600-line module called "main". Import it from the
public namespace instead::

    from pydrud import App

This shim keeps ``from pydrud.main import App`` working and will be
removed in 3.0.
"""

from __future__ import annotations

import warnings

from pydrud.runtime.app import *  # noqa: F401,F403
from pydrud.runtime.app import App, MAX_PATCHES, _module_name_for  # noqa: F401

warnings.warn(
    "pydrud.main is deprecated; import from pydrud (or pydrud.runtime.app)",
    DeprecationWarning,
    stacklevel=2,
)
