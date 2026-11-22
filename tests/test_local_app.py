import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_fastapi_app_imports_and_routes():
    import src.server as server

    routes = {getattr(r, "path", None) for r in server.app.routes}
    assert "/" in routes
    assert any(p and p.startswith("/api/") for p in routes)


def test_root_ui_serves_html():
    from fastapi.testclient import TestClient
    import src.server as server

    with patch.object(server.auth, "init_telethon", new=AsyncMock()), \
         patch.object(server.auth, "get_client", new=AsyncMock(return_value=None)), \
         patch.object(server.download_manager, "start", new=MagicMock()), \
         patch.object(server.download_manager, "stop", new=AsyncMock()):
        with TestClient(server.app) as client:
            resp = client.get("/")
            assert resp.status_code == 200
            assert "html" in resp.text.lower()
