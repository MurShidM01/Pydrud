# Architecture

Pydrud is two programs talking over one socket: a **Python actor** that owns
the widget tree, and an **Android runtime** that owns real views. Neither
side guesses what the other is doing — every change is a transaction.

```
your screens  ──►  pydrud.runtime.App  ──NDJSON──►  BridgeService (Java)
                       │  tree, state, events                │
                       ◄──────── events, acks ───────────────┘
```

## Layers

| Package | Owns |
| --- | --- |
| `pydrud/runtime/` | `App` (the single-threaded UI actor, event loop, render transactions, hot reload) and `navigation` (`Router`, `Route`, the back stack) |
| `pydrud/core/` | the machinery `App` is built from: `protocol`, `bridge`, `diff`, `elements`, `events`, `state`, `store`, `results`, `tasks`, `subscriptions`, `responsive`, `controllers`, `watcher` |
| `pydrud/widgets/` | the widget vocabulary — `base`, `layout`, `basic`, `material`, `forms`, `advanced`, `canvas`, `animation`, `theme`, `styling`, `tokens`, `scaffold`, `app_bar`, `gestures`, `responsive` |
| `pydrud/services/` | device capabilities called from Python — `native` (camera, BLE, NFC, sensors, …) and `http` |
| `pydrud/data/` | `database` (SQLite) and `cache` |
| `pydrud/android/` | `templates/` (the generated Java/Gradle/Python project) and `javacheck` (static Java validation, no JDK needed) |
| `pydrud/commands/` | the `pydrud` CLI — `project`, `builder`, `release`, `analyzer`, `doctor`, `docs`, `inspector`, `packages` |
| `pydrud/testing.py` | `FakeDevice` and `AppTester`: run a whole app with no emulator |
| `pydrud/compatibility.py` | the frozen toolchain matrix (AGP, Gradle, Chaquopy, SDK, NDK, JDK) and the protocol version |

Application code should import from the top-level namespace
(`from pydrud import App, Router, Column`); the layout above is for people
working *on* Pydrud.

## The rendering contract

1. Python builds a desired tree and diffs it against the last tree the
   device **acknowledged** (not the last one sent).
2. The diff goes out as a `render_transaction` with a revision number —
   a patch batch, or a snapshot when patches exceed `MAX_PATCHES`.
3. The device applies it atomically and replies `render_ack` with that
   exact revision; only then does Python advance its confirmed snapshot.
   A `render_nack` makes Python resend a full snapshot.

Because the confirmed snapshot only moves on an ack, a dropped or
reordered message can never leave the two trees silently out of step.

## Threading

One Python thread handles everything UI: the event loop drains a single
queue of device events and `run_on_ui` callbacks. Work from other threads
must go through `App.run_on_ui` — the same rule as `runOnUiThread`.
Handler exceptions are isolated and routed to `App.on_error` so one bad
callback cannot kill the loop.

## Native services

Each Java service class takes `(activity, bridge)` and exposes
`boolean handle(String cmd, JSONObject msg)`, returning `true` when it
owns the command. `BridgeService.handleMessage` tries them in order:
explicit cases → `platform` → `capture` → `connectivity` → `services` →
`replyUnsupported`. Every path answers exactly once, so a Python `Result`
can never hang.

## Testing

`tests/` runs the real app against `FakeDevice` over a real socket — the
protocol, the diff, the ack handshake and the screens are all exercised
without an emulator. `tools/check_java.py` parses every Java template and
resolves every symbol, which catches the class of error a Gradle build
would otherwise find for you.
