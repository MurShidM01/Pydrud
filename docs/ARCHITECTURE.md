# Architecture

Pydrud's core model is a platform-neutral Python widget tree connected to a
renderer. It owns Python app state, events, style resolution, tree diffs, and
render transaction bookkeeping. The two supported runtime modes choose
separate connection/setup paths around that core:

```text
Pydash default (`pydrud dev`)
  local project Python ── authenticated LAN preview v1 ──► independent renderer
       source stays on host     renderer protocol v2: snapshots/patches/ACKs/events

Chaquopy opt-in (generated Android APK)
  embedded Python ── existing local NDJSON bridge v2 ──► generated BridgeService
                                                        └─ Android native Views
```

Pydash preview has a single-run token-authenticated LAN handshake, described
in [Preview Protocol v1](PREVIEW_PROTOCOL.md). After pairing, the peers use
the existing renderer-v2 transaction and event contract. The handshake does
not change `RenderTransaction`, keyed patch semantics, the wire format of the
Android bridge, or the Python app's desired/confirmed render identity. The
Pydash client is separate from this repository; Pydrud does not build, bundle,
or validate that client, and this work does not add a standalone Pydash export
target.

## Layers

| Package | Owns |
| --- | --- |
| `pydrud/runtime/` | `App`, `Page`, the Python UI actor, app lifecycle, host/embedded event handling, render transactions, and hot reload integration |
| `pydrud/core/` | Platform-neutral machinery: renderer protocol/bridge, preview handshake data and server, keyed `diff`, widget `elements`, events, results, responsive metrics, tasks, watcher, and PSS style engine |
| `pydrud/core/styles/` | Shared style-key schema, PSS lexer/parser, selector model, style resolution, renderer-profile data contract, and stylesheet discovery/reload manager |
| `pydrud/platforms/android/` | Android-only adapter data (`AndroidRendererProfile`), the embedded development/source-sync server, and logcat output adapter |
| `pydrud/widgets/` | The widget vocabulary, styling helpers, theme, responsive widgets, and composites; `class_` is local stylesheet metadata, not wire data |
| `pydrud/services/` | APIs for optional client/device services and the cross-platform HTTP client |
| `pydrud/android/` | Build-time templates for the Chaquopy Android project and static Java-template checks; never imported by the PSS resolver |
| `pydrud/commands/` | CLI, runtime-aware package management and analyzer, scaffold/build/sync commands, and host preview runner |
| `pydrud/testing.py` | `FakeRenderer` / `AppTester`: local socket renderer for protocol and app tests without an Android device |

Application code should import from the top-level namespace (`from pydrud
import App, Router, Column`). The layout above is for people working on
Pydrud.

## Runtime selection and packaging

A new or otherwise unconfigured project selects `pydash`. That path runs the
installed Pydrud package on the host and does not inspect an Android SDK, build
an APK, or vendor the Pydash client. Pydash package declarations are recorded
in `pydrud.toml`; installing those dependencies into the Python environment
used by `pydrud dev` remains the developer's responsibility.

`chaquopy` is the explicit Android-only APK target. Its build path vendors the
runtime packages needed inside the generated app, applies the Android package
policy, and syncs Python dependencies into Gradle. An already-generated
Android project with no `runtime` key is recognized as legacy Chaquopy so an
upgrade does not silently change its behavior; a successful `sync` persists
that inferred selection.

Android assumptions belong in `pydrud/platforms/android/` or the generated
Android templates, not in `pydrud/core/`. The Android profile supplies
renderer-specific style facts as data; the neutral parser/resolver never
imports the Android adapter implicitly.

## Rendering contract

1. Python builds a desired widget tree and resolves PSS before serialization.
2. The diff is computed against the last tree acknowledged by the renderer,
   not simply the last tree sent.
3. One `RenderTransaction` is in flight at a time. A transaction contains a
   full snapshot or keyed patches, a strictly increasing revision, and its
   confirmed base revision.
4. The renderer applies the transaction atomically and ACKs that exact
   revision. Only then does Python advance the confirmed snapshot.
5. A NACK or reconnect causes a full snapshot resynchronization; intervening
   UI updates coalesce against the latest desired tree.

These semantics are shared by the host preview and the generated Android
renderer. Pydash's preview-protocol handshake sits outside the renderer-v2
transaction envelope.

## Python-side stylesheets

PSS is a platform-neutral stylesheet language, not a CSS renderer. `src/**/*.pss`
files are discovered and merged in stable order. Its selectors support widget
types, Python-side classes, explicit keys, compounds, selector lists,
descendants, and direct children. Rules cascade by specificity and source
order; inline widget styles override PSS.

The `class_` argument is retained only on the Python widget object so the PSS
resolver can match classes. It is omitted from serialized nodes and styles and
is not listed in `NATIVE_IGNORED_PROPS`. The parser, shared style vocabulary,
selector matching, and resolver have no Android dependency. Renderer-specific
warnings can be supplied through the optional `RendererProfile` data type.

The watcher reloads `.py` and `.pss` files. A PSS-only edit rebuilds style
resolution without re-executing Python modules; deleting a sheet removes its
rules. Invalid edits report diagnostics and retain that file's last-known-good
rules. See [PSS Stylesheets](PSS_STYLESHEETS.md) for syntax and behavior.

## Generated app import boundary

Generated applications keep route state in `app/runtime.py` and route
registration in `app/main.py`. Screen modules may import the already-created
`app.runtime.router` and small runtime helpers, but `app/runtime.py` must
never import `app.screens` or a module that imports a screen. Register routes
in `main.py` after importing both the runtime and screen builders.

## Threading and optional services

One Python thread handles UI events and `run_on_ui` callbacks. Work from other
threads must be marshalled through `App.run_on_ui`. Handler exceptions are
isolated and routed to `App.on_error` so one bad callback cannot kill the
loop.

Device and client services are optional capabilities of the connected
renderer. A service request is sent only when the renderer advertises that
service or the concrete command. If unavailable, Pydrud completes the
corresponding `Result` with an actionable failure instead of sending a request
the client cannot handle. Android manifest permissions and Chaquopy-generated
service implementations remain Android-target concerns.

## Testing and verification boundaries

The tests exercise Pydrud against `FakeRenderer` over a local socket, including
snapshots, keyed patches, ACK/NACK behavior, app events, runtime selection,
package/analyzer policy, PSS parsing/resolution, and generated-project
scaffolds. Generated Java templates are parsed and symbol-checked without
requiring Gradle or a device. Passing these tests does not establish that an
Android APK was built or installed, nor does it verify a separate Pydash
client implementation.
