"""Widget system for Pydrud."""

from pydrud.widgets.base import Widget, assign_stable_keys
from pydrud.widgets.styling import Style, EdgeInsets, Alignment, FontStyle, Border, BorderSide, BorderRadius
from pydrud.widgets.layout import (
    Container, Column, Row, Center, Spacer, Divider,
    Stack, Positioned, SizedBox, Padding, Card, ListView, GridView,
)
from pydrud.widgets.basic import (
    Text, Button, TextField, Image, Icon, Checkbox, Switch,
    ProgressBar, Slider, Dropdown, Radio,
)
from pydrud.widgets.theme import Colors, Icons, Theme
from pydrud.widgets.app_bar import AppBar
from pydrud.widgets.scaffold import Scaffold
from pydrud.widgets.fab import FloatingActionButton

__all__ = [
    "Widget",
    "assign_stable_keys",
    # layout
    "Container",
    "Column",
    "Row",
    "Center",
    "Spacer",
    "Divider",
    "Stack",
    "Positioned",
    "SizedBox",
    "Padding",
    "Card",
    "ListView",
    "GridView",
    # basic
    "Text",
    "Button",
    "TextField",
    "Image",
    "Icon",
    "Checkbox",
    "Switch",
    "ProgressBar",
    "Slider",
    "Dropdown",
    "Radio",
    # structure
    "AppBar",
    "Scaffold",
    "FloatingActionButton",
    # styling
    "Style",
    "EdgeInsets",
    "Alignment",
    "FontStyle",
    "Border",
    "BorderSide",
    "BorderRadius",
    "Colors",
    "Icons",
    "Theme",
]
