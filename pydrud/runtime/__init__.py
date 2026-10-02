"""The running application.

This package is what exists *while the app is on a device*: the
:class:`~pydrud.runtime.app.App` actor that owns the widget tree, the
page API your screens talk to, and the router that drives navigation.

Everything here is re-exported from the top-level ``pydrud`` namespace,
so application code should keep writing ``from pydrud import App, Router``.
"""

from pydrud.runtime.app import App
from pydrud.runtime.navigation import (
    NavigationStack, Route, Router, parse_url,
)

__all__ = ["App", "NavigationStack", "Route", "Router", "parse_url"]
