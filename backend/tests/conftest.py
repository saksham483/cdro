import pytest
import os
import sys
import tempfile
import shutil

# Ensure backend and root are in python path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
root_dir = os.path.abspath(os.path.join(backend_dir, ".."))
if backend_dir in sys.path:
    sys.path.remove(backend_dir)
sys.path.insert(0, backend_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from app import create_app
from app.config import Config
from app.extensions import db
from app.models.user import User
from app.models.application import Application, ApplicationStatus
from app.models.backup import Backup
import demoapp.app as demoapp_module

@pytest.fixture
def temp_storage():
    tmp = tempfile.mkdtemp(prefix="cdro_test_storage_")
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)

@pytest.fixture
def test_app(temp_storage):
    class TestConfig(Config):
        TESTING = True
        RUN_BACKGROUND_WORKERS = False
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
        STORAGE_BACKEND = "local"
        LOCAL_BACKUP_PATH = temp_storage
        HEALTH_FAILURE_THRESHOLD = 3
        RTO_TARGET_SECONDS = 60
        NOTIFICATION_BACKEND = "console"

    app = create_app(TestConfig)
    with app.app_context():
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(test_app):
    return test_app.test_client()

@pytest.fixture
def admin_token(client):
    res = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    return res.json["access_token"]

@pytest.fixture
def operator_token(client):
    res = client.post("/api/auth/login", json={"username": "operator", "password": "operator123"})
    return res.json["access_token"]

@pytest.fixture
def demoapp_client(monkeypatch, temp_storage):
    db_file = os.path.join(temp_storage, "test_demoapp.db")
    monkeypatch.setattr(demoapp_module, "DB_PATH", db_file)
    monkeypatch.setattr(demoapp_module, "FAILURE_FLAG_PATH", os.path.join(temp_storage, ".test_failure"))
    demoapp_module.init_db()
    demoapp_module.set_failure_mode(False)
    client = demoapp_module.app.test_client()
    return client
