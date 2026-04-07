import hashlib
import hmac
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


def _signed_headers(body: bytes, secret: str) -> dict[str, str]:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return {
        "content-type": "application/json",
        "x-github-event": "push",
        "x-hub-signature-256": f"sha256={digest}",
    }


def _payload() -> dict:
    return {
        "ref": "refs/heads/main",
        "after": "abc123",
        "repository": {"full_name": "owner/repo"},
        "pusher": {"name": "tester", "email": "tester@example.com"},
        "commits": [{"message": "test commit"}],
    }


def _configure_for_test(monkeypatch) -> None:
    monkeypatch.setattr(main, "WEBHOOK_SECRET", "test-secret")
    monkeypatch.setattr(main, "OPS_ALLOWED_BRANCHES", ("main",))
    monkeypatch.setattr(main, "_spawn_runner", lambda: None)
    monkeypatch.setattr(main, "_write_webhook_log", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        main,
        "_enqueue_job",
        lambda *args, **kwargs: {"job_id": "job_test", "status": "queued"},
    )


def test_canonical_endpoint_still_works(monkeypatch):
    _configure_for_test(monkeypatch)
    body = json.dumps(_payload()).encode("utf-8")
    headers = _signed_headers(body, "test-secret")

    with TestClient(main.app) as client:
        response = client.post("/hooks/github/push", content=body, headers=headers)

    assert response.status_code == 200
    assert response.json()["job_id"] == "job_test"
    assert "X-Trade-Arena-Webhook-Deprecated" not in response.headers


def test_legacy_webhook_endpoint_is_backward_compatible(monkeypatch):
    _configure_for_test(monkeypatch)
    body = json.dumps(_payload()).encode("utf-8")
    headers = _signed_headers(body, "test-secret")

    with TestClient(main.app) as client:
        response = client.post("/webhook", content=body, headers=headers)

    assert response.status_code == 200
    assert response.json()["job_id"] == "job_test"
    assert response.headers["X-Trade-Arena-Webhook-Deprecated"] == "Use /hooks/github/push"
