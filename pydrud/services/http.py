"""
A dependency-free HTTP client that never blocks the UI thread.

Chaquopy ships the standard library, so ``urllib`` is always available while
``requests`` may not be.  :class:`Http` wraps ``urllib`` with the ergonomics
people expect (JSON in/out, timeouts, headers, base URL, retries) and runs
every call on the page's task runner, handing you a
:class:`~pydrud.core.results.Result`::

    page.http.get("/posts").then(render_posts).catch(show_error)

Responses are :class:`HttpResponse` objects; ``.json`` parses lazily and
never raises on malformed bodies (it returns ``None``).
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Optional

from pydrud.core.results import Result

DEFAULT_TIMEOUT = 20.0


def user_agent() -> str:
    """Versioned client identity — never a stale hardcoded string."""
    try:
        from pydrud import __version__
        return f"Pydrud/{__version__} (Android)"
    except Exception:  # frozen/minimal environments without package metadata
        return "Pydrud/2 (Android)"


class HttpResponse:
    """A completed HTTP response."""

    __slots__ = ("status", "body", "headers", "url", "elapsed")

    def __init__(self, status: int, body: str, headers: dict, url: str,
                 elapsed: float = 0.0):
        self.status = int(status)
        self.body = body
        self.headers = {str(k).lower(): v for k, v in (headers or {}).items()}
        self.url = url
        self.elapsed = elapsed

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    @property
    def json(self) -> Any:
        try:
            return json.loads(self.body)
        except (ValueError, TypeError):
            return None

    def raise_for_status(self) -> "HttpResponse":
        if not self.ok:
            raise RuntimeError(f"HTTP {self.status} for {self.url}")
        return self

    def __bool__(self) -> bool:
        return self.ok

    def __repr__(self) -> str:
        return f"<HttpResponse {self.status} {self.url} {len(self.body)}b>"


class Http:
    """An async-by-default HTTP client bound to a page's task runner."""

    def __init__(self, submit: Callable[..., Any], *, base_url: str = "",
                 headers: Optional[dict] = None,
                 timeout: float = DEFAULT_TIMEOUT):
        self._submit = submit
        self.base_url = base_url.rstrip("/")
        self.headers = dict(headers or {})
        self.timeout = float(timeout)

    # ── configuration ────────────────────────────────────────────────────

    def configure(self, *, base_url: Optional[str] = None,
                  headers: Optional[dict] = None,
                  timeout: Optional[float] = None) -> "Http":
        if base_url is not None:
            self.base_url = base_url.rstrip("/")
        if headers is not None:
            self.headers.update(headers)
        if timeout is not None:
            self.timeout = float(timeout)
        return self

    def bearer(self, token: str) -> "Http":
        """Attach an ``Authorization: Bearer`` header to every request."""
        self.headers["Authorization"] = f"Bearer {token}"
        return self

    # ── verbs ────────────────────────────────────────────────────────────

    def get(self, url: str, *, params: Optional[dict] = None, **kw) -> Result:
        return self.request("GET", url, params=params, **kw)

    def post(self, url: str, *, json_body: Any = None, data: Any = None,
             **kw) -> Result:
        return self.request("POST", url, json_body=json_body, data=data, **kw)

    def put(self, url: str, *, json_body: Any = None, data: Any = None,
            **kw) -> Result:
        return self.request("PUT", url, json_body=json_body, data=data, **kw)

    def patch(self, url: str, *, json_body: Any = None, data: Any = None,
              **kw) -> Result:
        return self.request("PATCH", url, json_body=json_body, data=data, **kw)

    def delete(self, url: str, **kw) -> Result:
        return self.request("DELETE", url, **kw)

    def download(self, url: str, dest: str, **kw) -> Result:
        """Stream a URL to *dest* on a worker thread; resolves with the path."""
        result = Result(f"download:{url}", "download")

        def _work():
            try:
                request = urllib.request.Request(self._url(url),
                                                 headers=self.headers)
                with urllib.request.urlopen(request, timeout=self.timeout) as r, \
                        open(dest, "wb") as out:
                    while True:
                        chunk = r.read(64 * 1024)
                        if not chunk:
                            break
                        out.write(chunk)
                result.complete(dest)
            except Exception as exc:  # noqa: BLE001
                result.fail(str(exc))

        self._submit(_work)
        return result

    # ── core ─────────────────────────────────────────────────────────────

    def request(self, method: str, url: str, *, params: Optional[dict] = None,
                json_body: Any = None, data: Any = None,
                headers: Optional[dict] = None,
                timeout: Optional[float] = None,
                retries: int = 0, retry_delay: float = 0.5) -> Result:
        """Perform a request off the UI thread and return a Result."""
        method = method.upper()
        full_url = self._url(url, params)
        merged = {**self.headers, **(headers or {})}
        payload: Optional[bytes] = None
        if json_body is not None:
            payload = json.dumps(json_body).encode("utf-8")
            merged.setdefault("Content-Type", "application/json")
        elif data is not None:
            if isinstance(data, dict):
                payload = urllib.parse.urlencode(data).encode("utf-8")
                merged.setdefault("Content-Type",
                                  "application/x-www-form-urlencoded")
            elif isinstance(data, str):
                payload = data.encode("utf-8")
            else:
                payload = bytes(data)
        merged.setdefault("Accept", "application/json, text/plain, */*")
        merged.setdefault("User-Agent", user_agent())

        result = Result(f"{method} {full_url}", "http")
        effective_timeout = self.timeout if timeout is None else float(timeout)
        attempts = max(0, int(retries)) + 1

        def _work():
            last_error = ""
            for attempt in range(attempts):
                started = time.monotonic()
                try:
                    request = urllib.request.Request(full_url, data=payload,
                                                     headers=merged,
                                                     method=method)
                    with urllib.request.urlopen(request,
                                                timeout=effective_timeout) as response:
                        body = response.read().decode("utf-8", errors="replace")
                        result.complete(HttpResponse(
                            response.status, body, dict(response.headers),
                            full_url, time.monotonic() - started))
                        return
                except urllib.error.HTTPError as exc:
                    body = ""
                    try:
                        body = exc.read().decode("utf-8", errors="replace")
                    except Exception:
                        pass
                    # 4xx is an answer, not a transport failure — deliver it.
                    result.complete(HttpResponse(
                        exc.code, body, dict(exc.headers or {}), full_url,
                        time.monotonic() - started))
                    return
                except Exception as exc:  # noqa: BLE001 - network/DNS/timeout
                    last_error = str(exc)
                    if attempt + 1 < attempts:
                        time.sleep(retry_delay * (2 ** attempt))
            result.fail(last_error or "request failed")

        self._submit(_work)
        return result

    def _url(self, url: str, params: Optional[dict] = None) -> str:
        if url.startswith(("http://", "https://")):
            full = url
        else:
            full = f"{self.base_url}/{url.lstrip('/')}" if self.base_url else url
        if params:
            query = urllib.parse.urlencode(
                {k: v for k, v in params.items() if v is not None}, doseq=True)
            full = f"{full}{'&' if '?' in full else '?'}{query}"
        return full

    def __repr__(self) -> str:
        return f"<Http base_url={self.base_url!r} timeout={self.timeout}>"
