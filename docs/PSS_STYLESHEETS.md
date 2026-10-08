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
| Universal | `*` | Every widget |
| Compound | `Button.primary` | A `Button` carrying class `primary` |
| Selector list | `.primary, .notice` | Either selector |
| Descendant | `.screen Button` | A `Button` anywhere below a `.screen` ancestor |
| Direct child | `.screen > Button` | A `Button` whose direct parent matches `.screen` |
| Pseudo-class | `.fab:active` | A `.fab` in that interaction state |
| Structural pseudo | `.row:first-child` | The first `.row` among its siblings |
| Negation | `.item:not(.special)` | An `.item` without the `.special` class |

Compound selectors may combine type, class, explicit-key and pseudo-class
tests. Generated structural keys do not match `#id` selectors; assign a
deliberate `key=` when an ID rule is needed. Attribute selectors,
`::before`/`::after` generated content, `@supports`/`@import` and `!important`
are recognised but have no effect.

### Pseudo-classes

Structural pseudo-classes are computed from the widget tree:
`:first-child`, `:last-child`, `:only-child`, `:nth-child(an+b)` (including
`odd`/`even`), `:empty` and `:not(<compound>)`.

Interaction pseudo-classes split in two:

* **Transient** — `:active`, `:hover`, `:focus`. A rule using one is captured
  as a renderer sub-spec (`press`, `hover`, `focus`) and applied by the native
  renderer at the right moment. `.fab:active { transform: scale(.92) }` shrinks
  the button on touch-down.
* **Persistent** — `:disabled`, `:checked`, `:selected`, `:enabled`. These
  match against the state a widget reports (`_pseudo_states`, or `state` /
  `disabled` / `checked` props) and apply as ordinary declarations.

`:root` is the global variable scope (see below).

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
values (`{ size: 18, family: sans }`) as well as quoted JSON-style keys, and
entries may be separated with `,` or `;` — a multi-line block reads naturally
with the same separator as a declaration block:

```pss
.card {
    shadow: {
        color: #40000000;
        offsetX: 0;
        offsetY: 10;
        blur: 24;
        spread: 0;
    };
}
```

Composite keys are camelCase (`offsetX`, `borderRadius`, `mainAxisAlignment`),
matching the inline `style=` dictionaries. Use Pydrud properties such as `bg`,
not browser properties such as `background-color`. Unknown property names
produce diagnostics; renderer support for a known property remains
renderer-specific.

Matching rules follow CSS-like precedence: selector specificity first, then
source order. For a widget with multiple classes, all matching rules
participate. Its inline `style=` values are merged last and therefore override
PSS declarations. PSS declarations are kept separately from inline styles, so
removing a declaration from a stylesheet removes its effect on the next build
instead of leaving a stale value behind.

## Theme tokens (`$token`)

A value may reference a live theme value with `$name`. Tokens are resolved
when the stylesheet is applied — on every build — against the active palette,
so a single stylesheet follows light/dark mode and re-tints after
`Theme.seed(...)`, `Theme.dark()` or `Theme.system()` without a second copy of
every rule.

```pss
.card {
    bg: $surface;
    border-radius: $radius_card;
    padding: { all: $card_padding };
    font: { color: $text, size: $text_title };
}
.badge { bg: $primary; color: $on_primary; }
```

Two families of names resolve:

* **Colour roles** from `Theme` — `$primary`, `$secondary`, `$background`,
  `$surface`, `$surface_variant`, `$outline`, `$error`, `$text`,
  `$text_secondary`, `$on_primary`.
* **Design metrics** from `Tokens` — `$radius_card`, `$radius_button`,
  `$radius_fab`, `$gutter`, `$section`, `$card_padding`, `$text_title`,
  `$text_body`, `$elevation_card`, `$duration_normal`, and every other public
  `Tokens` attribute.

A value that is *exactly* one reference keeps the token's own type, so
`border-radius: $radius_card` stays a number. A reference embedded in a longer
string is substituted in place (`"$gutter 2"`). An unknown name is left
untouched and reported as a diagnostic (`Unknown style token reference(s): $x`).
Tokens are intentionally **not** evaluated by the parser: they are resolved by
the platform-neutral resolver, so they work on every renderer.

## CSS custom properties (`--name`, `var()`)

PSS also has CSS custom properties. Declare them on `:root` (or any rule) and
read them with `var()`:

```pss
:root {
    --bg: #F8F7F3;
    --heart: #E85D68;
    --heart-soft: rgba(232, 93, 104, .08);
}

.app    { bg: var(--bg); }
.glow   { bg: var(--heart-soft); }
.badge  { color: var(--heart, #E85D68); }   /* with a fallback */
```

A custom property declared on an ancestor is visible to its descendants, so a
variable can scope to a subtree (`.running { --tint: … }`). An unknown name
with no fallback is left untouched and reported
(`Unknown CSS variable reference(s): --x`).

`var(--x)` and `$token` are complementary: `$token` resolves against the live
`Theme`/`Tokens` palette, `var(--x)` against the stylesheet's own variables.
Use `$token` for theme-driven colours and `var(--x)` for the design's own
values.

## The CSS value language (`clamp()`, `calc()`, `env()`, units)

Numeric values may use CSS math and units. They are evaluated against the live
window — the same dp metrics `MediaQuery` reports — and collapse to a dp number:

```pss
.app {
    padding: max(16px, calc(18px + env(safe-area-inset-top)))
             clamp(16px, 5vw, 24px)
             max(16px, calc(18px + env(safe-area-inset-bottom)));
    min-height: 100dvh;
}
.number { font-size: clamp(78px, 24vw, 108px); }
```

Supported: `calc()`, `min()`, `max()`, `clamp()`, `env(safe-area-inset-*)`,
`+ - * /` with parentheses, and the units `px`/`dp`, `vw`/`dvh`/`svh`/`lvw`…
(viewport), `vmin`/`vmax`, and `%`. A fragment that cannot be resolved (a
percentage of an unknown parent, a colour, a keyword) is left as written for
the renderer. `border-radius: 50%` is the one percentage special case: it maps
to the Pydrud circle idiom (`999`).

## Responsive rules (`@media`)

```pss
@media (max-width: 699px) { .fab { right: clamp(14px, 5vw, 20px); } }
@media (max-width: 360px) and (min-height: 500px) { .number { margin-top: -8px; } }
@media (max-width: 1px), (min-width: 2px) { … }   /* comma = OR */
```

Conditions test `width` and `height` in dp against the live window. `min-`,
`max-`, `and`-joined features, comma lists and nested `@media` are supported;
later rules win by source order exactly as in CSS.

## Declarative animation (`@keyframes`, `animation`, `transition`)

```pss
@keyframes glow {
    0%   { opacity: .18; transform: scale(.78) }
    100% { opacity: 0;   transform: scale(1.7) }
}

.running .glow { animation: glow 1.12s ease-out infinite; }
.dot           { transition: background .2s ease; }
```

`@keyframes` supports `from`/`to`, percentages, and `0%, 100%` lists.
`animation` accepts the CSS shorthand (`name duration timing delay iteration
direction fill`); the native renderer runs the timeline, repeating it for
`infinite`. `transition` tweens a property change when the value changes.
`transform` is decomposed into Pydrud's `scale`/`rotation`; translation is
layout and is dropped.

## CSS long-hands and shorthands

CSS spellings are folded into Pydrud's canonical composites, so the renderer
only ever sees the canonical form:

| CSS | Pydrud |
|-----|--------|
| `font-size`, `font-weight`, `font-family`, `letter-spacing`, `line-height` | `font.{size,weight,family,letterSpacing,lineHeight}` |
| `color` (on a text widget) | `font.color` |
| `padding: a b c d`, `margin: a b` | `padding`/`margin` `{top,right,bottom,left}` |
| `padding: 24`, `margin: 8px` | `padding`/`margin` `{all: 24}` (all four sides) |
| `padding-top`, `margin-left`, … | `padding.top`, `margin.left`, … |
| `border: 1px solid red`, `border-color`, `border-width` | `border: {width, color}` |
| `background`, `background-color` | `bg` |
| `gap` | `spacing` |
| `z-index`, `aspect-ratio` | `zIndex`, `aspectRatio` |
| `transform: scale(.9) rotate(5deg)` | `scale`, `rotation` |

`inherit` / `initial` / `unset` / `revert` drop the declaration, as in CSS.

## Web-only declarations

Pydrud renders a native widget tree, not a browser box model. Some CSS
declarations therefore have no native meaning and are **accepted then
ignored**, with one aggregated warning per stylesheet, so a rule copied from
the web drops in cleanly: `display`, `box-sizing`, `pointer-events`,
`touch-action`, `appearance`, `cursor`, `user-select`, `visibility`,
`flex*`/`align-*`/`justify-*`, `gap`-family spacing on grid, `place-items`,
`fill`, `outline`, `font-variant-numeric`, and the `-webkit-*` vendor
prefixes. Pydrud expresses those with widgets — `Row`/`Column`/`Stack` instead
of `display:flex`, a `Stack` instead of absolutely-positioned children.

A complete worked example lives at
[`docs/examples/heartbeat-css-parity.pss`](examples/heartbeat-css-parity.pss).

## Design-system properties

These properties are resolved by the Android renderer and are the ones the
starter theme uses. Each has a kebab-case alias (`border-top-left-radius`).

| Property | Value | Notes |
|----------|-------|-------|
| `bg`, `color` | colour | `#RRGGBB` / `#AARRGGBB` |
| `borderRadius` | number | Uniform corner radius |
| `borderTopLeftRadius`, `borderTopRightRadius`, `borderBottomLeftRadius`, `borderBottomRightRadius` | number | Per-corner radius; overrides `borderRadius` for that corner |
| `border` | number \| `{ width, color }` | Stroke |
| `gradient` | `{ angle, colors, stops? }` | `angle` is CSS-style (0° = up, 90° = right); `stops` are 0–1 positions |
| `shadow` | number \| `{ color, offsetX, offsetY, blur, spread }` | A bare number is a quick elevation-style shadow |
| `elevation` | number | Native elevation |
| `ripple` | colour | Press ripple tint |
| `blur` | number | Gaussian blur of the view's own content (dp), like CSS `filter: blur()`; Android 12+ only |
| `padding`, `margin` | `{ all }` or `{ left, top, right, bottom }` | |
| `font` | `{ size, weight, color, family, italic, letterSpacing }` | |
| `mainAxisAlignment` | `start` \| `center` \| `end` \| `space_between` \| `space_around` \| `space_evenly` | Linear layouts |
| `crossAxisAlignment` | `start` \| `center` \| `end` \| `stretch` | |
| `spacing` | number | Gap between linear-layout children |
| `aspectRatio` | number | Width ÷ height |
| `width`, `height`, `minWidth`, `maxWidth`, `minHeight`, `maxHeight` | number \| `match` \| `wrap` \| `"50%w"` | |
| `opacity`, `scale`, `rotation` | number | Transform |
| `position`, `top`, `left`, `right`, `bottom` | keyword / number | `absolute` inside a `Stack` |

`mainAxisAlignment: space_between` and friends distribute free space without
inserting spacer views, so list indices stay stable across patches.

`blur` draws the view through a hardware layer with an Android `RenderEffect`,
so it softens the view's *own* content — a background image, or a whole
panel's children. It is a no-op below Android 12 (API 31). Blurring what is
*behind* a view is a window-level effect (`Window.setBackgroundBlurRadius`)
and is not exposed per widget.

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
