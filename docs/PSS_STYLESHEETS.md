# Pydrud Style Sheets (PSS)

PSS is Pydrud's Python-side stylesheet format. It is a small, CSS-like rule
language that resolves into the same platform-neutral style dictionaries used
by inline `style=` values. It is **not** browser CSS: PSS defines selectors and
values in terms of Pydrud widgets and the shared Pydrud style schema, and it
does not require a browser, Android renderer, or platform-specific runtime.

## Loading stylesheets

Every `*.pss` file beneath a project's `src/` directory is discovered
recursively in deterministic path order. To register a file outside that tree
or provide PSS in memory, use the `App` API:

```python
app = App(target=main, stylesheet="theme/custom.pss")
app.add_stylesheet("shared/controls.pss")
app.add_stylesheet_source(
    ".notice { color: #334155; }",
    filename="<notice-styles>",
)
```

`stylesheet=` and `stylesheets=` can also be supplied when constructing an
`App`. Relative paths are resolved against its project root. Disk stylesheets
are combined in sorted path order; explicitly registered in-memory sources
are applied as overlays after disk sources.

Every project created with `pydrud create` ships `src/app/theme.pss`, wired
to its starter screens through `class_`, so editing the stylesheet re-skins
the app without touching Python. On-device standalone targets load that file
explicitly (the APK has no project root to discover from); `pydrud analyze`
validates stylesheets alongside Python source.

## Widget classes and selectors

Use `class_=` on a widget to attach one or more Python-side class names. A
string can contain whitespace-separated names, or pass a sequence:

```python
Button("Save", key="save", class_="primary large")
Text("Ready", class_=["status", "success"])
```

PSS supports these selector forms:

| Form | Example | Matches |
|------|---------|---------|
| Widget type | `Button` | Widgets whose Pydrud type is `Button` |
| Class | `.primary` | Widgets with `class_="primary"` |
| Explicit key | `#save` | A widget with explicit `key="save"` |
| Compound | `Button.primary` | A `Button` carrying class `primary` |
| Selector list | `.primary, .notice` | Either selector |
| Descendant | `.screen Button` | A `Button` anywhere below a `.screen` ancestor |
| Direct child | `.screen > Button` | A `Button` whose direct parent matches `.screen` |

Compound selectors may combine type, class, and explicit-key tests. Generated
structural keys do not match `#id` selectors; assign a deliberate `key=` when
an ID rule is needed. Pseudo-classes, attribute selectors, media queries, and
browser-specific CSS properties are not part of the current PSS grammar.

`class_` is resolver metadata only. It is deliberately separate from `style`
and is never serialized to the renderer. Legacy `class_*` style markers are
also filtered from wire styles. `class_` is not an entry in
`NATIVE_IGNORED_PROPS` because it is stylesheet metadata, not a renderer property.

## Declarations and cascade

A rule contains Pydrud style properties. Property names are normalized through
the shared style schema, so supported aliases such as `text-align` and
`border-radius` map to the canonical Pydrud keys `textAlign` and
`borderRadius`.

```pss
/* src/theme.pss */
Column.page > Text.title {
    font: { size: 24, weight: 700, color: #111827 };
}

Button.primary {
    bg: #4F46E5;
    color: #FFFFFF;
    padding: { horizontal: 16, vertical: 10 };
}

#save { border-radius: 999; }
```

PSS values include numbers, booleans, `null`, quoted strings, bare names and
nested object/list values. Composite values accept CSS-style bare keys and
values (`{ size: 18, family: sans }`) as well as quoted JSON-style keys. Use
Pydrud properties such as `bg`, not browser properties such as
`background-color`. Unknown property names produce diagnostics; renderer
support for a known property remains renderer-specific.

Matching rules follow CSS-like precedence: selector specificity first, then
source order. For a widget with multiple classes, all matching rules
participate. Its inline `style=` values are merged last and therefore override
PSS declarations. PSS declarations are kept separately from inline styles, so
removing a declaration from a stylesheet removes its effect on the next build
instead of leaving a stale value behind.

## Diagnostics and hot reload

The file watcher handles Python and PSS files. Creating, editing, moving, or
deleting a `.pss` file in a watched source tree triggers a rebuild. A PSS-only
edit does not re-execute Python modules. Deletion removes the deleted file's
rules from the next resolved tree.

Stylesheets are applied transactionally on reload. A file with a syntax error
reports a source-located diagnostic and retains that file's last known-good
rules; a newly created invalid file contributes no partial rules. The latest
combined sheet and diagnostics are available from `App.stylesheet` and
`App.stylesheet_diagnostics`. When PSS arrives in a development hot-reload
batch, the batch is validated before any file or module changes are applied.

The Android adapter may supply optional `RendererProfile` data for renderer-
specific collisions or capabilities. The parser, selector matcher, style
schema, and resolver themselves remain platform-neutral and do not infer
Android behavior.
