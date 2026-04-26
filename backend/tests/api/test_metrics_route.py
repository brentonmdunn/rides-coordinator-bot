"""Integration tests for the Prometheus metrics endpoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_fastapi_instrumentator import Instrumentator


def test_metrics_endpoint_exposes_prometheus_payload():
    """The instrumentator should produce a text/plain Prometheus exposition."""
    app = FastAPI()

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"status": "ok"}

    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

    client = TestClient(app)

    # Generate at least one request so a counter exists.
    assert client.get("/ping").status_code == 200

    metrics_resp = client.get("/metrics")
    assert metrics_resp.status_code == 200
    assert metrics_resp.headers["content-type"].startswith("text/plain")
    body = metrics_resp.text
    # Prometheus exposition format always includes HELP/TYPE comment lines.
    assert "# HELP" in body
    assert "# TYPE" in body
