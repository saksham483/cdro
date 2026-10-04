import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

class Config:
    APP_ENV = os.environ.get("APP_ENV", "development")
    SECRET_KEY = os.environ.get("SECRET_KEY", "cdro-super-secret-key-38472910-enterprise-orchestrator-key-2026")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "cdro-jwt-secret-key-19283746-enterprise-orchestrator-key-2026")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)

    # Database
    db_url = os.environ.get("DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "cdro.db"))
    # Handle postgres:// vs postgresql:// compatibility in newer SQLAlchemy
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # DemoApp & Internal endpoints
    DEMOAPP_URL = os.environ.get("DEMOAPP_URL", "http://localhost:5001")
    INTERNAL_SECRET = os.environ.get("INTERNAL_SECRET", "demoapp-internal-auth-token-48291")

    # Health & Failure Thresholds
    HEALTH_CHECK_INTERVAL_SECONDS = int(os.environ.get("HEALTH_CHECK_INTERVAL_SECONDS", 5))
    HEALTH_FAILURE_THRESHOLD = int(os.environ.get("HEALTH_FAILURE_THRESHOLD", 3))

    # Backup settings
    BACKUP_INTERVAL_SECONDS = int(os.environ.get("BACKUP_INTERVAL_SECONDS", 300))
    BACKUP_RETENTION_COUNT = int(os.environ.get("BACKUP_RETENTION_COUNT", 10))

    # Recovery SLA targets
    RECOVERY_TIMEOUT_SECONDS = int(os.environ.get("RECOVERY_TIMEOUT_SECONDS", 120))
    RTO_TARGET_SECONDS = int(os.environ.get("RTO_TARGET_SECONDS", 60))

    # Storage Backend
    STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "local")
    LOCAL_BACKUP_PATH = os.environ.get("LOCAL_BACKUP_PATH", os.path.join(BASE_DIR, "storage", "backups"))
    S3_BUCKET = os.environ.get("S3_BUCKET", "")
    AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
    AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")

    # Notifications
    NOTIFICATION_BACKEND = os.environ.get("NOTIFICATION_BACKEND", "console")
    SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "")
    ADMIN_NOTIFICATION_EMAIL = os.environ.get("ADMIN_NOTIFICATION_EMAIL", "admin@example.com")

    # Background workers
    RUN_BACKGROUND_WORKERS = os.environ.get("RUN_BACKGROUND_WORKERS", "true").lower() == "true"
