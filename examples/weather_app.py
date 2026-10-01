"""
Weather — an app that talks to the network and the platform.

Shows: the non-blocking HTTP client, pull-to-refresh, permissions + GPS,
a Chart, Skeleton loading states, and bottom navigation between screens.

    python examples/weather_app.py --tree
"""

from pydrud import (
    App, AppBar, Avatar, BottomNavigationBar, Card, Chart, Colors, Column,
    Icons, ListTile, NavItem, RefreshIndicator, Row, Scaffold, Skeleton,
    State, Text,
)

API = "https://api.open-meteo.com/v1/forecast"

screen = State(0)
loading = State(True)
place = State("Karachi")
forecast = State([])          # list[dict(day, temp)]
app: App | None = None


def main(page):
    page.bgcolor = Colors.BACKGROUND

    # ── data ────────────────────────────────────────────────────────────
    def load(_event=None):
        loading.value = True
        page.update()
        page.http.get(API, params={
            "latitude": 24.86, "longitude": 67.00,
            "daily": "temperature_2m_max", "timezone": "auto",
        }, timeout=10).then(_loaded).catch(_failed)

    def _loaded(response):
        daily = (response.json or {}).get("daily", {})
        temps = daily.get("temperature_2m_max", [])[:7]
        days = [d[5:] for d in daily.get("time", [])[:7]]
        forecast.value = [{"day": d, "temp": t} for d, t in zip(days, temps)]
        loading.value = False
        page.end_refresh()
        page.update()

    def _failed(error):
        loading.value = False
        page.end_refresh()
        page.snack_bar(f"Could not refresh: {error}", action="RETRY")
        page.update()

    def locate(_event):
        page.permissions.request("location").then(_permission_result)

    def _permission_result(granted):
        if not granted or not list(granted.values())[0]:
            page.toast("Location permission denied")
            return
        page.location.current().then(
            lambda pos: page.toast(f"{pos['lat']:.2f}, {pos['lon']:.2f}"))

    # ── screens ─────────────────────────────────────────────────────────
    def today_screen():
        if loading.value:
            return Column(key="loading", spacing=12, children=[
                Skeleton(key="sk_title", height=28, lines=1),
                Skeleton(key="sk_chart", height=120, lines=1),
                Skeleton(key="sk_rows", height=16, lines=4),
            ])
        temps = [item["temp"] for item in forecast.value]
        return Column(key="today", spacing=16, children=[
            Row(key="place_row", spacing=12, children=[
                Avatar(icon=Icons.LOCATION, key="place_avatar",
                       bg=Colors.SECONDARY),
                Column(key="place_col", children=[
                    Text(place.value, key="place", size=22, weight=700),
                    Text(f"{temps[0]:.0f}°C now" if temps else "—",
                         key="now", color=Colors.TEXT_SECONDARY),
                ]),
            ]),
            Card(key="chart_card", child=Chart(
                temps, key="chart", kind="area",
                labels=[i["day"] for i in forecast.value])),
            Column(key="rows", spacing=0, children=[
                ListTile(item["day"], key=f"day_{index}",
                         subtitle=f"{item['temp']:.0f}°C",
                         leading=Icons.CALENDAR)
                for index, item in enumerate(forecast.value)
            ]),
        ])

    def places_screen():
        return Column(key="places", children=[
            ListTile(name, key=f"place_{name}", leading=Icons.LOCATION,
                     trailing=Icons.CHEVRON_RIGHT,
                     on_click=lambda _e, n=name: _pick(n))
            for name in ("Karachi", "Lahore", "Islamabad")
        ])

    def _pick(name):
        place.value = name
        screen.value = 0
        load()

    def settings_screen():
        return Column(key="settings", children=[
            ListTile("Use my location", key="gps", leading=Icons.LOCATION,
                     on_click=locate),
            ListTile("Share forecast", key="share", leading=Icons.SHARE,
                     on_click=lambda _e: page.share.text(
                         f"Weather in {place.value}")),
        ])

    body = (today_screen, places_screen, settings_screen)[screen.value]()

    page.add(Scaffold(
        key="weather",
        app_bar=AppBar(title="Weather", key="bar", bg_color=Colors.PRIMARY),
        body=RefreshIndicator(key="refresh", child=body, on_refresh=load),
        bottom_navigation=BottomNavigationBar([
            NavItem("Today", icon=Icons.HOME),
            NavItem("Places", icon=Icons.LOCATION),
            NavItem("Settings", icon=Icons.SETTINGS),
        ], key="nav", selected=screen.value,
            on_change=lambda e: (setattr(screen, "value", e.value),
                                 page.update())),
    ))

    if loading.value and not forecast.value:
        page.after(0.1, load)


def start_app():
    global app
    app = App(target=main, title="Weather")
    app.bind(screen, loading, forecast, place)
    app.run()


if __name__ == "__main__":
    import sys

    demo = App(target=main, title="Weather")
    if "--tree" in sys.argv:
        loading.value = False
        forecast.value = [{"day": "06-01", "temp": 33.0}]
        print(demo.build().to_json())
    else:
        demo.bind(screen, loading, forecast, place).run(retry=False)
