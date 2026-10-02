"""Shared runtime handles: the router and the live :class:`App`.

Screens never import each other; they import this module. It owns the
router every screen registers with, plus the running app instance so any
handler can ask for a re-render with :func:`refresh`.
"""

from pydrud import App, Router

#: The app's router. Screens are registered in ``app.main``.
router = Router()

_app = None


def bind(instance):
    """Remember the running :class:`~pydrud.App` and return it."""
    global _app
    _app = instance
    return instance


def current():
    """The running app.

    Falls back to the most recently created :class:`~pydrud.App`, so tests
    and the dev runner work without calling :func:`bind` first.
    """
    return _app if _app is not None else App.current()


def refresh():
    """Re-render the current screen."""
    app = current()
    if app is not None:
        app.update()
