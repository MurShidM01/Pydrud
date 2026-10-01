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
from pydrud.widgets.theme import (Colors, Icons, Theme, ColorScheme, Typography,
                                  Spacing, Radius, Elevation, Motion)
from pydrud.widgets.tokens import Tokens
from pydrud.widgets.material import (
    ListTile, ExpansionTile, Chip, Badge, Avatar, Banner, Tooltip,
    Tab, Tabs, NavItem, BottomNavigationBar, NavigationRail, Drawer,
    SegmentedButton, SearchBar, Rating, CircularProgress, Skeleton,
    RefreshIndicator, Stepper, WebView, VideoPlayer, Chart,
)
from pydrud.widgets.gestures import GestureDetector, InkWell, Dismissible, Draggable
from pydrud.widgets.animation import (
    Animation, AnimatedContainer, AnimatedOpacity, AnimatedScale,
    AnimatedRotation, AnimatedSwitcher, FadeIn, SlideIn, ScaleIn, Hero, animate,
)
from pydrud.widgets.forms import (
    Form, FormField, required, min_length, max_length, email, phone, url,
    numeric, between, pattern, matches, custom,
)
from pydrud.widgets.canvas import Canvas, Paint, Path, radial_point
from pydrud.widgets.advanced import (
    CameraPreview, InfiniteList, MapView, Markdown, Marker, ReorderableList,
    RichText, Span,
)
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
    "Spacing",
    "Radius",
    "Elevation",
    "Motion",
    "Tokens",
    "Icons",
    "Theme",
    "ColorScheme",
    "Typography",
    # material
    "ListTile",
    "ExpansionTile",
    "Chip",
    "Badge",
    "Avatar",
    "Banner",
    "Tooltip",
    "Tab",
    "Tabs",
    "NavItem",
    "BottomNavigationBar",
    "NavigationRail",
    "Drawer",
    "SegmentedButton",
    "SearchBar",
    "Rating",
    "CircularProgress",
    "Skeleton",
    "RefreshIndicator",
    "Stepper",
    "WebView",
    "VideoPlayer",
    "Chart",
    # gestures
    "GestureDetector",
    "InkWell",
    "Dismissible",
    "Draggable",
    # animation
    "Animation",
    "AnimatedContainer",
    "AnimatedOpacity",
    "AnimatedScale",
    "AnimatedRotation",
    "AnimatedSwitcher",
    "FadeIn",
    "SlideIn",
    "ScaleIn",
    "Hero",
    "animate",
    # forms
    "Form",
    "FormField",
    "required",
    "min_length",
    "max_length",
    "email",
    "phone",
    "url",
    "numeric",
    "between",
    "pattern",
    "matches",
    "custom",
    # v1.3 — painting, hardware, maps, rich text and big lists
    "Canvas",
    "Paint",
    "Path",
    "radial_point",
    "CameraPreview",
    "MapView",
    "Marker",
    "RichText",
    "Span",
    "Markdown",
    "ReorderableList",
    "InfiniteList",
]
