import main
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATABASE_PATH", tmp_path / "test.db")
    with TestClient(main.app) as test_client:
        yield test_client


def test_patient_crud_and_derived_bmi(client):
    patient = {
        "patient_id": "P-100",
        "name": "Jordan Lee",
        "city": "Pune",
        "age": 34,
        "gender": "other",
        "height_m": 1.75,
        "weight_kg": 70,
    }

    created = client.post("/patients", json=patient)
    assert created.status_code == 201
    assert created.json()["bmi"] == 22.86
    assert created.json()["bmi_category"] == "healthy"
    assert client.get("/patients/P-100").json()["name"] == "Jordan Lee"
    assert len(client.get("/patients").json()) == 1

    updated = client.patch("/patients/P-100", json={"weight_kg": 85})
    assert updated.status_code == 200
    assert updated.json()["bmi_category"] == "overweight"

    assert client.delete("/patients/P-100").status_code == 204
    assert client.get("/patients/P-100").status_code == 404


def test_duplicate_ids_and_invalid_input_are_rejected(client):
    patient = {
        "patient_id": "P-100",
        "name": "Jordan Lee",
        "city": "Pune",
        "age": 34,
        "gender": "other",
        "height_m": 1.75,
        "weight_kg": 70,
    }
    assert client.post("/patients", json=patient).status_code == 201
    assert client.post("/patients", json=patient).status_code == 409
    patient["age"] = 0
    assert client.post("/patients", json=patient).status_code == 422