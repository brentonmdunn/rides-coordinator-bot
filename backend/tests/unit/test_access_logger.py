import sys
from pathlib import Path
from unittest.mock import patch

# Add backend directory to sys.path to allow importing api if not already in path
# valid for running pytest from backend root
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from fastapi import FastAPI, Response
from fastapi.testclient import TestClient

from api.middleware.access_logger import AccessLogMiddleware


@patch("api.middleware.access_logger.access_logger")
def test_health_check_success_skipped(mock_logger):
    """Test that successful health checks are NOT logged."""
    app = FastAPI()
    app.add_middleware(AccessLogMiddleware)

    @app.get("/health")
    def health_check():
        return {"status": "ok"}

    client = TestClient(app)

    response = client.get("/health")
    assert response.status_code == 200

    # Verify no log methods were called
    mock_logger.info.assert_not_called()
    mock_logger.warning.assert_not_called()
    mock_logger.error.assert_not_called()


@patch("api.middleware.access_logger.access_logger")
def test_health_check_failure_logged(mock_logger):
    """Test that failed health checks ARE logged."""
    app = FastAPI()
    app.add_middleware(AccessLogMiddleware)

    @app.get("/health")
    def health_check_error():
        # Simulate a 500 error
        return Response(status_code=500)

    client = TestClient(app)

    response = client.get("/health")
    assert response.status_code == 500

    # Verify error log was called
    mock_logger.error.assert_called_once()


@patch("api.middleware.access_logger.access_logger")
def test_other_endpoints_logged(mock_logger):
    """Test that other endpoints ARE logged normally."""
    app = FastAPI()
    app.add_middleware(AccessLogMiddleware)

    @app.get("/other")
    def other():
        return {"status": "ok"}

    client = TestClient(app)

    response = client.get("/other")
    assert response.status_code == 200

    # Verify info log was called
    mock_logger.info.assert_called_once()
