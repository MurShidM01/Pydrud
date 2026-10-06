"""
Theme helpers — a Material colour palette, icon catalogue and design tokens.

These constants keep app code readable and guarantee the values are
understood by the Android renderer::

    from pydrud import Colors, Icons, Text, Icon

    Text("Hi", color=Colors.PRIMARY)
    Icon(Icons.SETTINGS)

The package is split by concern into sibling modules; this ``__init__``
re-exports the public names so ``from pydrud.widgets.theme import Colors``
keeps working.
"""

from pydrud.widgets.theme.colors import ColorScheme, Colors
from pydrud.widgets.theme.icons import Icons
from pydrud.widgets.theme.theme import Theme, ThemeExtension
from pydrud.widgets.theme.tokens import Elevation, Motion, Radius, Spacing
from pydrud.widgets.theme.typography import TextTheme, Typography

__all__ = [
    "Colors", "ColorScheme",
    "Icons",
    "Spacing", "Radius", "Elevation", "Motion",
    "TextTheme", "Typography",
    "Theme", "ThemeExtension",
]
