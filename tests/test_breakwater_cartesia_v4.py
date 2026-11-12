import importlib.util
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _Handler(BaseHTTPRequestHandler):
    def _reply(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        body = b"\x00\x01\x02\x03" * 64
        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_POST = _reply
    do_GET = _reply

    def log_message(self, *args):
        pass


@pytest.fixture()
def server():
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:%d" % httpd.server_port
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_test2_module_imports_and_runs_with_real_client(server, monkeypatch):
    monkeypatch.setenv("CARTESIA_BASE_URL", server)
    monkeypatch.setenv("CARTESIA_API_KEY", "test-key")

    import cartesia

    real_sync = cartesia.Cartesia
    real_async = cartesia.AsyncCartesia

    class Cartesia(real_sync):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("base_url", server)
            super().__init__(*args, **kwargs)

    class AsyncCartesia(real_async):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("base_url", server)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(cartesia, "Cartesia", Cartesia)
    monkeypatch.setattr(cartesia, "AsyncCartesia", AsyncCartesia)

    spec = importlib.util.spec_from_file_location(
        "repo_test2_under_test", os.path.join(REPO, "test2.py")
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "repo_test2_under_test", module)
    # Executes the repository's code: imports and the client.tts.bytes call.
    spec.loader.exec_module(module)

    assert isinstance(module.client, real_sync)
