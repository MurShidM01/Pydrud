# Pydrud Preview Protocol v1

Status: **stable host-side contract**  
Preview protocol: `pydrud.preview` version `1`  
Renderer protocol: Pydrud bridge protocol version `2`

This document defines the Android-agnostic connection between `pydrud dev`
and an independent live-preview renderer such as Pydash. It does not define a
Pydash product, Android lifecycle, packaging, or arbitrary platform-specific
development features.

## Responsibilities

The developer machine is authoritative. It:

- imports and executes project Python;
- owns the `App`, router, state, event handlers and widget tree;
- watches source files and performs hot reload;
- computes snapshots and keyed tree patches;
- tracks desired, in-flight and renderer-confirmed revisions; and
- accepts UI events and optional client-service results.

The preview client is a lightweight renderer. It:

- applies complete widget snapshots and incremental patches;
- emits ACK or NACK for every render transaction;
- sends user, window-metrics and lifecycle events;
- reports renderer capabilities and current device metrics; and
- requests resynchronization by NACKing an inapplicable transaction.

Project source code is never sent to or executed by the preview client. The
preview channel is not an APK build/install channel.

## Transport and framing

The host listens on TCP. The default is `0.0.0.0:8597`; `--host`, `--port` and
`--connect-host` configure the bind and advertised addresses. Clients use the
advertised address from the QR payload.

Every frame is one UTF-8 JSON object followed by `\n` (NDJSON). A frame,
including the newline, is limited to 2 MiB. Non-object JSON, invalid UTF-8,
invalid JSON and oversized frames are protocol errors.

There is no TLS in protocol v1. It is a local-development protocol intended
for a trusted LAN. Authentication prevents an unpaired local peer from taking
over a session, but traffic and the bearer token are not encrypted. Do not
forward the port to the public internet or share the QR/connection URI.

## QR connection payload

`pydrud dev` creates a random session UUID and a cryptographically random,
single-run 256-bit bearer token. The exact QR value is a URI:

```text
pydrud://preview/connect?host=192.168.1.24&port=8597&session=<uuid>&token=<token>&protocol=1&renderer=2&project=com.example.app&name=Example+App
```

All fields occur exactly once:

| Field | Meaning |
|---|---|
| `host` | Connectable LAN IP or hostname; never `0.0.0.0`/`::` |
| `port` | TCP port, 1–65535 |
| `session` | Random identity for this `pydrud dev` process |
| `token` | Random bearer credential for this process |
| `protocol` | Preview handshake protocol, currently `1` |
| `renderer` | Widget renderer protocol, currently `2` |
| `project` | Stable project identity (normally the configured package) |
| `name` | Human-readable project name |

The token and session expire when `pydrud dev` exits. Restarting the command
always produces a new pair. The project identity is informational and is also
returned by the authenticated handshake.

## Handshake

The client's first frame must arrive within 10 seconds and must be a
`preview_hello`. No bridge commands or UI events may precede it.

```json
{
  "type": "preview_hello",
  "protocol": "pydrud.preview",
  "protocol_version": 1,
  "renderer_protocol_version": 2,
  "session_id": "9fe1737d-87d7-4a27-a024-055e74095071",
  "token": "single-run-bearer-token",
  "client": {
    "name": "Pydash",
    "version": "1.0.0",
    "platform": "android"
  },
  "capabilities": {
    "transactional_render": true,
    "revisioned_render": true,
    "ack_nack": true,
    "resync": true,
    "native_animations": false,
    "services": ["storage", "share"],
    "widget_types": ["Stack", "Column", "Text", "Button"],
    "native_view": false,
    "commands": []
  },
  "last_revision": 0,
  "metrics": {
    "width": 412,
    "height": 915,
    "density": 2.75,
    "text_scale": 1.0,
    "platform_version": "35",
    "orientation": "portrait",
    "padding_top": 24,
    "padding_right": 0,
    "padding_bottom": 24,
    "padding_left": 0
  }
}
```

The four Boolean renderer capabilities shown as `true` are required. Other
capabilities are optional and additive. `commands` may name optional commands
implemented by a renderer; the host must not infer unsupported services merely
from the client name or platform.

`last_revision` is `0` for a new client. A reconnecting client reports its
last successfully applied renderer revision. Metrics are density-independent
window details used before the first tree is built. Unknown metric and
capability fields must be ignored for forward compatibility.

After validating versions, session, constant-time token comparison and
required capabilities, the host sends:

```json
{
  "type": "preview_welcome",
  "protocol": "pydrud.preview",
  "protocol_version": 1,
  "renderer_protocol_version": 2,
  "session_id": "9fe1737d-87d7-4a27-a024-055e74095071",
  "project": {"id": "com.example.app", "name": "Example App"},
  "port": 8597,
  "capabilities": {
    "host_python": true,
    "file_watching": true,
    "stateful_hot_reload": true,
    "initial_snapshot": true,
    "incremental_patches": true,
    "reconnect_resync": true
  },
  "limits": {"max_frame_bytes": 2097152}
}
```

A rejected handshake receives one `preview_reject` when possible, then the
host closes that socket:

```json
{
  "type": "preview_reject",
  "protocol": "pydrud.preview",
  "protocol_version": 1,
  "code": "authentication_failed",
  "message": "invalid session or token"
}
```

Defined rejection codes are `invalid_hello`, `unsupported_version`,
`unsupported_renderer`, `authentication_failed`, `missing_capabilities`,
`invalid_metrics`, `invalid_revision`, `invalid_client`, `frame_too_large`
and `client_busy`. Authentication failures do not distinguish a wrong session
from a wrong token. Only one authenticated rendering client is active at a
time.

## Initial synchronization

After `preview_welcome`, the stream switches to the existing bridge protocol.
The host sends, in order:

1. a `theme` command containing the current palette;
2. one `render_transaction` with `kind: "snapshot"` and the complete widget
   tree.

The initial transaction is always a full snapshot, including after reconnect.
Its `base_revision` is the client's validated `last_revision`; its `revision`
is strictly greater. This avoids assuming that a host-side cached tree exactly
matches a newly attached renderer.

Example:

```json
{
  "cmd": "render_transaction",
  "protocol_version": 2,
  "transaction_id": "tx_4f8348f14e",
  "revision": 8,
  "base_revision": 7,
  "kind": "snapshot",
  "tree": {"type": "Stack", "key": "_page", "props": {}, "children": []}
}
```

The client applies a transaction atomically and answers with one event:

```json
{
  "type": "render_ack",
  "data": {"transaction_id": "tx_4f8348f14e", "revision": 8}
}
```

The host does not advance its confirmed tree/revision before that ACK.

## Incremental patches and events

Once a snapshot is acknowledged, source/state changes produce normal
`render_transaction` frames with `kind: "patch"`, `base_revision` equal to the
last confirmed revision, and a strictly increasing `revision`. Patch payloads
use the existing keyed widget-tree operations from `pydrud.core.diff`.
Large or unsafe diffs may be sent as a new snapshot instead.

Only one render transaction is in flight. Further updates coalesce against the
latest desired tree until the client confirms the active transaction.

Client events retain the bridge event envelope:

```json
{"type":"event","data":{"key":"save","event":"click","value":null}}
```

Window changes use `type: "metrics"`; lifecycle, back, result and other
negotiated bridge events keep their existing v2 shapes. Events are processed
on the host's single Python UI actor. They can execute Python handlers, mutate
state and trigger the next patch.

## NACK and resynchronization

If a transaction cannot be applied atomically—most commonly because
`base_revision` differs from its applied state—the client sends:

```json
{
  "type": "render_nack",
  "data": {
    "transaction_id": "tx_4f8348f14e",
    "revision": 8,
    "native_revision": 6,
    "code": "stale_base",
    "message": "expected base revision 6"
  }
}
```

The host sets its confirmed revision to `native_revision` and immediately
sends a fresh full snapshot based on that revision. A snapshot ACK then becomes
the new confirmed tree. Clients must not ACK a partially applied transaction.

## Disconnect and reconnect

TCP disconnect cancels pending service request/result calls and discards
in-flight transaction bookkeeping, but it does not stop the development
server or discard the authoritative Python app. File watching continues while
no client is attached.

A reconnect repeats the complete authenticated handshake with the same
single-run session/token and reports its own `last_revision`. The host always
sends theme plus a full snapshot before resuming patches. A client that lost
all render state reconnects with revision `0`.

Restarting `pydrud dev` creates a different session/token. A client must scan
or otherwise consume the new URI; old credentials are invalid.

## Hot reload failure behavior

Source watching is a host concern. A successful reload rebinds the generated
entrypoint/router, restores supported bound state, rebuilds the widget tree and
sends an incremental transaction. A syntax/import/runtime failure is printed
in the host terminal and the last acknowledged UI remains visible. The client
is not sent project source or a partially constructed tree.

## Compatibility rules

- Preview protocol versions are exact in v1. A client must reject an unknown
  `protocol` value or unsupported `protocol_version`.
- Renderer protocol compatibility is negotiated independently and is exact
  for the current v2 contract.
- Unknown object fields are ignored; missing required fields are errors.
- New optional capability names may be added without a version increment.
- Changing required sequencing, authentication semantics, framing, or existing
  field meaning requires a new preview protocol version.

### Optional renderer capabilities

Capability data is additive and platform-neutral. A client can advertise a
`services` array or object for optional request/response services (for example
`camera`, `haptics`, `storage`, `location`, or `notifications`), a
`widget_types` array or object for its supported widget vocabulary, and a
Boolean `native_view` for the `NativeView` escape hatch. The existing optional
`commands` list may instead name concrete commands. Unknown capability keys
are ignored; none of these fields changes protocol version 1 or renderer
protocol version 2.

The host checks service availability before sending a request. An unavailable
service returns a completed, actionable `Result` failure without putting a
request on the wire. If `widget_types` is explicitly provided and a widget is
not listed, the host substitutes a visible, non-interactive `Text` placeholder
with the same stable key and logs one warning per unsupported widget type.
`Text` is the fallback primitive. `NativeView` additionally requires the
explicit `native_view: true` capability. For compatibility with clients that
predate widget catalogs, omitting `widget_types` leaves ordinary widget types
unfiltered; omission of an optional service does not imply support.

Example reduced renderer declaration:

```json
{
  "transactional_render": true,
  "revisioned_render": true,
  "ack_nack": true,
  "resync": true,
  "services": ["storage", "share"],
  "widget_types": ["Stack", "Column", "Text", "Button"],
  "native_view": false
}
```
