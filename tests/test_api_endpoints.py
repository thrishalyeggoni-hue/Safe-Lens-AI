import pytest
import io
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_health_ready():
    response = client.get("/api/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"]["ready"] is True

def test_capabilities():
    response = client.get("/api/capabilities")
    assert response.status_code == 200
    data = response.json()
    assert "link" in data["supported_modules"]
    assert "message" in data["supported_modules"]
    assert "screenshot" in data["supported_modules"]
    assert "qr" in data["supported_modules"]
    assert "document" in data["supported_modules"]
    assert "media" in data["supported_modules"]
    assert "offer" in data["supported_modules"]

def test_assessment_flow_session_isolation():
    # Session 1 creates an assessment
    s1 = TestClient(app)
    r1 = s1.post(
        "/api/assessments",
        json={"module_type": "link", "target_url": "https://google.com"}
    )
    assert r1.status_code == 200
    data1 = r1.json()
    asmt_id = data1["id"]
    assert data1["risk_category"] in ["Low Risk", "Caution", "High Risk"]
    
    # Session 1 can fetch it
    fetch_r1 = s1.get(f"/api/assessments/{asmt_id}")
    assert fetch_r1.status_code == 200

    # Session 1 dashboard shows 1 assessment
    dash1 = s1.get("/api/dashboard/summary").json()
    assert dash1["total_assessments"] >= 1

    # Session 2 cannot access Session 1's assessment
    s2 = TestClient(app)
    fetch_r2 = s2.get(f"/api/assessments/{asmt_id}")
    assert fetch_r2.status_code == 403

    # Session 2 has empty history
    dash2 = s2.get("/api/dashboard/summary").json()
    assert dash2["total_assessments"] == 0

    # Session 1 clears history
    del_r = s1.delete("/api/history")
    assert del_r.status_code == 200
    assert del_r.json()["cleared"] >= 1

    # Session 1 dashboard is now 0
    dash1_after = s1.get("/api/dashboard/summary").json()
    assert dash1_after["total_assessments"] == 0
