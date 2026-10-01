"""Widget system for Pydrud."""

from pydrud.widgets.base import Widget
from pydrud.widgets.styling import Style, EdgeInsets, Alignment, FontStyle, Border, BorderRadius
from pydrud.widgets.layout import Container, Column, Row, Center, Spacer, Divider
from pydrud.widgets.basic import Text, Button, TextField, Image, Icon, Checkbox, Switch
from pydrud.widgets.app_bar import AppBar
from pydrud.widgets.scaffold import Scaffold
from pydrud.widgets.fab import FloatingActionButton

__all__ = [
    "Widget",
    "Container",
    "Column",
    "Row",
    "Center",
    "Spacer",
    "Divider",
    "Text",
    "Button",
    "TextField",
    "Image",
    "Icon",
    "Checkbox",
    "Switch",
    "AppBar",
    "Scaffold",
    "FloatingActionButton",
    "Style",
    "EdgeInsets",
    "Alignment",
    "FontStyle",
    "Border",
    "BorderRadius",
]
