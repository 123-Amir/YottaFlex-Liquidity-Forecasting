from fastapi.testclient import TestClient

from app.api_routes import get_db
from app.main import app


def test_forecast_request_validation_rejects_invalid_horizon() -> None:
    def no_database():
        yield None

    app.dependency_overrides[get_db] = no_database
    try:
        response = TestClient(app).post(
            "/api/forecast-runs",
            json={"scenario_code": "BASE", "simulation_date": "2026-01-01", "horizon_days": 0},
        )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_dashboard_and_openapi_are_available() -> None:
    client = TestClient(app)
    assert client.get("/").status_code == 200
    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    assert "/api/summary" in schema.json()["paths"]
