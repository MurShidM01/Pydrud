"""Well-known local TCP ports used by Pydrud's runtime channels.

Defined once here because four different layers refer to them: the Python
runtime, the CLI, the generated Java bridge and the Gradle templates. A
drift between any two of them breaks hot reload in a way that is hard to
diagnose, so the numbers live in exactly one place.
"""

from __future__ import annotations

#: Java BridgeService <-> Python App (render traffic).
DEFAULT_BRIDGE_PORT = 8595

#: DevServer: hot reload, hot restart, diagnostics. Debug builds only.
DEFAULT_DEV_PORT = 8596

#: Pydash preview listener (host side).
DEFAULT_PREVIEW_PORT = 8597

__all__ = ["DEFAULT_BRIDGE_PORT", "DEFAULT_DEV_PORT", "DEFAULT_PREVIEW_PORT"]
