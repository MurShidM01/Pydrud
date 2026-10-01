"""
Pydrud — Build native Android apps with Python.

A lightweight, Flutter-inspired framework that converts a declarative
Python widget tree into native Android Views at runtime. No XML layouts,
no Kotlin UI code — just Python.
"""

__version__ = "1.0.1"
__app_name__ = "Pydrud"

from pydrud.main import App
from pydrud.core.state import State, ReactiveDict
from pydrud.core.responsive import Responsive, MediaQuery
from pydrud.navigation import Router, NavigationStack, Route
from pydrud.widgets import (
    Widget,
    Container,
    Column,
    Row,
    Center,
    Spacer,
    Divider,
    Text,
    Button,
    TextField,
    Image,
    Icon,
    Checkbox,
    Switch,
    AppBar,
    Scaffold,
    FloatingActionButton,
    Style,
    EdgeInsets,
    Alignment,
    FontStyle,
    Border,
    BorderRadius,
)

__all__ = [
    "App",
    "Responsive",
    "MediaQuery",
    "Router",
    "NavigationStack",
    "Route",
    "State",
    "ReactiveDict",
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
