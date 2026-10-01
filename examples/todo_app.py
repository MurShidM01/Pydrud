"""
Todo — a complete small app in ~120 lines.

Shows: Store-based state, keyed lists, swipe-to-delete, filtering with a
SegmentedButton, persistence through page.storage, and a confirm dialog.

Run it headless (prints the widget tree, no device needed)::

    python examples/todo_app.py --tree

Or drop it into a scaffolded project as ``src/app/main.py``.
"""

from pydrud import (
    App, AppBar, Button, Checkbox, Colors, Column, Dismissible, Icons,
    ListTile, ListView, Row, Scaffold, SearchBar, SegmentedButton, Store,
    Text, TextField,
)

store = Store({"todos": [], "filter": 0, "query": "", "draft": ""})
FILTERS = ("All", "Active", "Done")
app: App | None = None


@store.action
def add_todo(state, text):
    text = text.strip()
    if not text:
        return None
    return {"todos": state["todos"] + [{"text": text, "done": False}],
            "draft": ""}


@store.action
def toggle_todo(state, index):
    todos = [dict(t) for t in state["todos"]]
    todos[index]["done"] = not todos[index]["done"]
    return {"todos": todos}


@store.action
def delete_todo(state, index):
    return {"todos": [t for i, t in enumerate(state["todos"]) if i != index]}


def visible_todos():
    mode = store["filter"]
    query = store["query"].lower()
    for index, todo in enumerate(store["todos"]):
        if mode == 1 and todo["done"]:
            continue
        if mode == 2 and not todo["done"]:
            continue
        if query and query not in todo["text"].lower():
            continue
        yield index, todo


def main(page):
    page.bgcolor = Colors.BACKGROUND

    def save(_event=None):
        page.storage.set("todos", store["todos"])

    def on_draft(event):
        store.set("draft", event.value or "")

    def submit(_event):
        add_todo(store["draft"])
        save()

    def clear_done(_event):
        page.dialog.confirm("Remove every completed task?",
                            title="Clear done").then(_clear_confirmed)

    def _clear_confirmed(yes):
        if not yes:
            return
        store.set("todos", [t for t in store["todos"] if not t["done"]])
        save()
        page.toast("Cleared")

    rows = []
    for index, todo in visible_todos():
        rows.append(Dismissible(
            key=f"row_{index}",
            background=Colors.ERROR,
            icon=Icons.DELETE,
            on_dismiss=lambda _e, i=index: (delete_todo(i), save()),
            child=ListTile(
                todo["text"],
                key=f"tile_{index}",
                subtitle="Done" if todo["done"] else None,
                leading=Icons.CHECK_CIRCLE if todo["done"] else Icons.LIST,
                on_click=lambda _e, i=index: (toggle_todo(i), save()),
            ),
        ))

    page.add(Scaffold(
        key="todo",
        app_bar=AppBar(title="Todo", key="bar", bg_color=Colors.PRIMARY),
        body=Column(spacing=12, children=[
            SearchBar(store["query"], key="search", hint="Filter tasks",
                      on_change=lambda e: store.set("query", e.value or "")),
            SegmentedButton(list(FILTERS), key="filter",
                            selected=store["filter"],
                            on_change=lambda e: store.set("filter", e.value)),
            Row(key="composer", spacing=8, children=[
                TextField(store["draft"], key="draft", hint="What's next?",
                          expand=1, on_change=on_draft, on_submit=submit),
                Button("Add", key="add", on_click=submit),
            ]),
            ListView(key="rows", expand=1, spacing=4, children=rows)
            if rows else
            Text("Nothing here yet.", key="empty",
                 color=Colors.TEXT_SECONDARY),
            Button("Clear completed", key="clear", variant="text",
                   on_click=clear_done),
        ]),
    ))


def start_app():
    """Entry point used by the Android activity."""
    global app
    app = App(target=main, title="Todo")
    app.bind(store)
    app.run()


if __name__ == "__main__":
    import sys

    demo = App(target=main, title="Todo")
    if "--tree" in sys.argv:
        print(demo.build().to_json())
    else:
        demo.bind(store).run(retry=False)
