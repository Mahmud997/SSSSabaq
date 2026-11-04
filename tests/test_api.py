"""API smoke and workspace-isolation tests (no external AI calls)."""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

TEST_DB = Path("/tmp/ustaz_ai_pro_max_pytest.db")
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["APP_SECRET"] = "pytest-only-app-secret-change-me"
os.environ["ADMIN_SECRET"] = "pytest-only-admin-secret"
os.environ["AI_PROVIDER"] = "gemini"

from fastapi.testclient import TestClient
from app.main import app
from app.db import Base, engine

client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def create_workspace(name="Тестовый Учитель"):
    response = client.post("/api/workspaces", json={
        "teacher_name": name,
        "school_name": "Школа №1",
        "locality": "Шымкент",
        "subjects": ["Информатика"],
    })
    assert response.status_code == 200, response.text
    return response.json()


def test_health_and_frontend_are_available():
    assert client.get("/api/health").json()["status"] == "ok"
    response = client.get("/")
    assert response.status_code == 200
    assert "USTAZ" in response.text


def test_workspace_key_required_and_valid_key_works():
    workspace = create_workspace()
    assert client.get("/api/workspaces/me").status_code == 401
    response = client.get(
        "/api/workspaces/me",
        headers={"X-Workspace-Key": workspace["workspace_key"]},
    )
    assert response.status_code == 200
    assert response.json()["teacher_name"] == "Тестовый Учитель"


def test_workspace_data_is_isolated():
    first = create_workspace("Первый Учитель")
    second = create_workspace("Второй Учитель")
    create_response = client.post(
        "/api/lessons",
        headers={"X-Workspace-Key": first["workspace_key"]},
        json={
            "title": "Мой урок",
            "subject": "Информатика",
            "grade": "7",
            "topic": "Алгоритмы",
            "content": {"notes": "Тест"},
        },
    )
    assert create_response.status_code == 200
    lessons = client.get(
        "/api/lessons",
        headers={"X-Workspace-Key": second["workspace_key"]},
    )
    assert lessons.status_code == 200
    assert lessons.json() == []


def test_admin_routes_require_admin_secret():
    assert client.get("/api/admin/overview").status_code == 403
    response = client.get(
        "/api/admin/overview",
        headers={"Authorization": "Bearer pytest-only-admin-secret"},
    )
    assert response.status_code == 200
