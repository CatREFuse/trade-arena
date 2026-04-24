from __future__ import annotations

from app.config import settings
from app.main import app


def test_dev_reset_route_is_not_registered_by_default():
    assert settings.dev_routes_enabled is False
    assert not any(getattr(route, "path", None) == "/api/dev/reset" for route in app.routes)
