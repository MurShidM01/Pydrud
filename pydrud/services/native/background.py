"""
WorkManager jobs and foreground services.
"""

from __future__ import annotations

from typing import Any, Callable, Optional, Sequence

from pydrud.core.results import Result
from pydrud.services.native._base import Invoke, _Service



class Background(_Service):
    """WorkManager jobs and foreground services.

    A *job* is a Python callable that WorkManager re-invokes later — even
    after the app is killed or the device reboots::

        page.background.schedule("sync", every=900, network=True)

        @page.background.job("sync")
        def sync_now(inputs):
            Note.where(dirty=True).update(dirty=False)

    A *foreground service* keeps Python alive with a sticky notification
    (music playback, long downloads, location tracking).
    """

    NETWORKS = ("any", "connected", "unmetered", "not_roaming")

    def __init__(self, invoke: Invoke):
        super().__init__(invoke)
        self._jobs: dict[str, Callable] = {}

    # ── jobs ─────────────────────────────────────────────────────────────

    def job(self, name: str) -> Callable:
        """Decorator registering the Python callable WorkManager will run."""
        def decorator(fn: Callable) -> Callable:
            if not callable(fn):
                raise TypeError("background job must be callable")
            self._jobs[str(name)] = fn
            return fn
        return decorator

    def register(self, name: str, fn: Callable) -> "Background":
        self.job(name)(fn)
        return self

    def run_job(self, name: str, inputs: Optional[dict] = None) -> Any:
        """Invoke a registered job locally (used by the worker and in tests)."""
        fn = self._jobs.get(str(name))
        if fn is None:
            from pydrud.core.tasks import GLOBAL_JOBS
            fn = GLOBAL_JOBS.get(str(name))
        if fn is None:
            raise KeyError(f"No background job named {name!r}")
        try:
            return fn(dict(inputs or {}))
        except TypeError:
            return fn()

    @property
    def jobs(self) -> list[str]:
        from pydrud.core.tasks import GLOBAL_JOBS
        return sorted(set(self._jobs) | set(GLOBAL_JOBS))

    # ── scheduling ───────────────────────────────────────────────────────

    def schedule(self, name: str, *, every: Optional[float] = None,
                 delay: float = 0, network: Any = False,
                 charging: bool = False, idle: bool = False,
                 battery_not_low: bool = False, replace: bool = True,
                 inputs: Optional[dict] = None) -> Result:
        """Queue a job. With *every* it repeats (minimum 15 minutes)."""
        if every is not None and float(every) < 900:
            raise ValueError(
                "WorkManager's minimum periodic interval is 900 seconds")
        if isinstance(network, bool):
            network = "connected" if network else "any"
        if network not in self.NETWORKS:
            raise ValueError(f"network must be one of {self.NETWORKS}")
        return self._invoke("work_schedule", name=str(name),
                            every=None if every is None else float(every),
                            delay=float(delay), network=network,
                            charging=bool(charging), idle=bool(idle),
                            battery_not_low=bool(battery_not_low),
                            replace=bool(replace), inputs=dict(inputs or {}))

    def cancel(self, name: str) -> Result:
        return self._invoke("work_cancel", name=str(name))

    def cancel_all(self) -> Result:
        return self._invoke("work_cancel", name=None, all=True)

    def status(self, name: str) -> Result:
        """Resolves with ``enqueued`` / ``running`` / ``succeeded`` / …"""
        return self._invoke("work_status", name=str(name))

    # ── foreground service ───────────────────────────────────────────────

    def start_service(self, *, title: str = "Running",
                      message: str = "", icon: str = "",
                      ongoing: bool = True,
                      actions: Optional[Sequence[str]] = None) -> Result:
        """Promote the app to a foreground service with a sticky notification."""
        return self._invoke("service_start", title=title, message=message,
                            icon=icon, ongoing=bool(ongoing),
                            actions=[str(a) for a in (actions or [])])

    def update_service(self, *, title: str = "", message: str = "",
                       progress: Optional[int] = None) -> Result:
        return self._invoke("service_update", title=title, message=message,
                            progress=progress)

    def stop_service(self) -> Result:
        return self._invoke("service_stop")

    def request_battery_exemption(self) -> Result:
        """Ask the user to exempt the app from Doze (use sparingly)."""
        return self._invoke("battery_exemption")
