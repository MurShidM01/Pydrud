"""Small reusable UI components shared by the starter screens.

Keep application-wide building blocks here. As the app grows, add focused
modules beside this one (for example ``components/profile.py``) rather than
turning a screen into a collection of local helper functions.
"""

from pydrud import (
    Button, Center, Column, Container, EdgeInsets, Responsive, Spacing, Text,
    Theme,
)


def section(title, key):
    """A quiet, all-caps section label — the spine of a tidy screen."""
    return Container(
        key=key,
        width="match",
        padding=EdgeInsets(left=Spacing.XS, top=Spacing.SM,
                           bottom=Spacing.XXS),
        child=Text(title.upper(), key=f"{key}_label", size=12, weight=700,
                   color=Theme.text_secondary,
                   style={"font": {"letterSpacing": 0.08}}),
    )


def demo_button(label, icon, key, on_click):
    """One playground action: a tonal button that always answers back."""
    return Button(label, key=key, icon=icon, variant="tonal",
                  full_width=True).on_click(on_click)


def page_body(key, children):
    """A scrolling column with a readable responsive gutter."""
    gutter = Responsive.value(phone=Spacing.GUTTER, tablet=Spacing.XXL)
    content = Column(
        key=f"{key}_scroll",
        scroll=True,
        spacing=Spacing.LG,
        style={"padding": EdgeInsets(
            left=gutter, right=gutter, top=Spacing.LG,
            bottom=Spacing.HUGE).to_dict()},
        children=children,
    )
    if not Responsive.is_tablet():
        return content
    return Center(
        key=f"{key}_center",
        child=Container(key=f"{key}_wrap", width=640, height="match",
                        child=content),
    )
