"""
Material Design 3 component library.

The complete M3 component set including Snackbar, DatePicker, TimePicker,
SideSheet, BottomAppBar, FABMenu, SearchView, StandardBottomSheet,
FullScreenDialog, LoadingIndicator, ButtonGroup, SplitButton, Toolbar.
"""

from pydrud.widgets.material.lists import (
    ExpansionPanel, ExpansionPanelList, ExpansionTile, ListTile,
)
from pydrud.widgets.material.chips import (
    AssistChip, Avatar, Badge, Banner, Chip, FilterChip, InputChip,
    SuggestionChip, Tooltip,
)
from pydrud.widgets.material.feedback import (
    CircularProgress, Rating, RefreshIndicator, SearchBar, Skeleton, Stepper,
)
from pydrud.widgets.material.menus import (
    DropdownMenu, MenuDivider, MenuItem, PopupMenu, PopupMenuButton,
)
from pydrud.widgets.material.tabs import Tab, TabBar, Tabs
from pydrud.widgets.material.bottom_nav import (
    BottomNavigationBar, NavItem, NavigationBar, NavigationDestination,
    NavigationItem,
)
from pydrud.widgets.material.rail import Drawer, NavigationRail, SegmentedButton
from pydrud.widgets.material.media import Chart, VideoPlayer, WebView
from pydrud.widgets.material.overlays import AlertDialog, Dialog, ModalBottomSheet
# Material 3 components
from pydrud.widgets.material.snackbar import Snackbar
from pydrud.widgets.material.pickers import DatePicker, DateRangePicker, TimePicker
from pydrud.widgets.material.sheets import (
    StandardBottomSheet, SideSheet, FullScreenDialog,
)
from pydrud.widgets.material.nav_components import (
    BottomAppBar, FABMenu, FABMenuItem, SearchView,
)
from pydrud.widgets.material.expressive import (
    ButtonGroup, LoadingIndicator, SplitButton, Toolbar,
)

__all__ = [
    # lists
    "ListTile", "ExpansionTile", "ExpansionPanel", "ExpansionPanelList",
    # chips and small informational widgets
    "Chip", "AssistChip", "FilterChip", "InputChip", "SuggestionChip",
    "Badge", "Avatar", "Banner", "Tooltip",
    # menus
    "MenuItem", "MenuDivider", "PopupMenu", "PopupMenuButton", "DropdownMenu",
    # navigation
    "Tab", "Tabs", "TabBar", "NavItem", "NavigationItem",
    "NavigationDestination", "BottomNavigationBar", "NavigationBar",
    "NavigationRail", "Drawer", "SegmentedButton",
    # input and feedback
    "SearchBar", "Rating", "CircularProgress", "Skeleton", "RefreshIndicator",
    "Stepper",
    # media
    "WebView", "VideoPlayer", "Chart",
    # overlays
    "AlertDialog", "Dialog", "ModalBottomSheet",
    # Snackbar
    "Snackbar",
    # Date and time pickers
    "DatePicker", "DateRangePicker", "TimePicker",
    # Sheets
    "StandardBottomSheet", "SideSheet", "FullScreenDialog",
    # Navigation components
    "BottomAppBar", "FABMenu", "FABMenuItem", "SearchView",
    # Expressive components
    "ButtonGroup", "LoadingIndicator", "SplitButton", "Toolbar",
]