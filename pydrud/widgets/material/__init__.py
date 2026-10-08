"""
Material Design 3 component library.

Everything here maps onto a real Android view in ``ViewFactory``:
``ListTile`` becomes a ``LinearLayout`` with the standard 16dp/72dp metrics,
``Tabs`` and ``BottomNavigationBar`` become Pydrud's own ``PydrudTabBar``
and ``PydrudNavBar`` views, which honour every style property Python
sends instead of only the ones a Material theme attribute exposes.

The Python side stays declarative: build the widget, hand it a callback,
return it from your page builder.

The widgets are grouped by concern into sibling modules; this package
re-exports them so ``from pydrud.widgets.material import ListTile`` keeps
working.
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
]
