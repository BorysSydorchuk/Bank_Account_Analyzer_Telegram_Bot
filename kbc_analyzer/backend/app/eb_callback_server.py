"""Temporary local HTTP server that catches Enable Banking's OAuth redirect
automatically (S3-07 Item 2) — replaces S2-02's copy-paste-the-URL flow.

Listens on CALLBACK_PORT for exactly one request, then shuts itself down.
Runs in the celery_worker process (see tasks/auth.py), never in the FastAPI
process — waiting for a browser redirect can take minutes, and blocking a
worker process is exactly what the whole Celery setup (S3-03/S3-04) exists to
allow, unlike blocking an API request.
"""
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)

CALLBACK_PORT = 3001


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        params = parse_qs(urlparse(self.path).query)
        # Stashed on the server instance (not a class attribute) so a second,
        # unrelated reconnect attempt's server can never read another one's
        # result — see wait_for_callback(), which creates one handler class
        # per call specifically to keep this isolated.
        self.server.callback_result = {  # type: ignore[attr-defined]
            "code": params.get("code", [None])[0],
            "state": params.get("state", [None])[0],
        }
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(
            b"<html><body><h2>Authorization received.</h2>"
            b"<p>You can close this tab and return to KBC Analyzer.</p></body></html>"
        )

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - matches base signature
        pass  # BaseHTTPRequestHandler logs every request to stderr by default; too noisy here


class CallbackPortBusyError(Exception):
    """Another reconnect attempt's server is still bound to CALLBACK_PORT —
    confirmed live: refreshing the page mid-reconnect and clicking Reconnect
    again fires a second task while the first is still waiting (up to its
    full timeout), and the second one's bind() fails with "Address already
    in use" if not caught here."""


def wait_for_callback(timeout_seconds: int = 300) -> dict:
    """Starts a local server on CALLBACK_PORT, blocks until Enable Banking's
    redirect hits it (or timeout_seconds elapses), then shuts down.

    Raises TimeoutError if nothing arrives in time, CallbackPortBusyError if
    another attempt already owns the port. Returns {"code": str|None,
    "state": str|None} otherwise — callers still need to check code is present,
    since a malformed redirect could hit this with no code at all.
    """
    try:
        server = HTTPServer(("0.0.0.0", CALLBACK_PORT), _CallbackHandler)
    except OSError as exc:
        raise CallbackPortBusyError(
            f"Port {CALLBACK_PORT} is already in use by another reconnect attempt."
        ) from exc

    server.callback_result = None  # type: ignore[attr-defined]
    server.timeout = timeout_seconds

    server.handle_request()  # blocks for exactly one request, or until timeout
    server.server_close()

    result = getattr(server, "callback_result", None)
    if result is None:
        raise TimeoutError(f"No authorization callback received within {timeout_seconds} seconds.")
    return result
