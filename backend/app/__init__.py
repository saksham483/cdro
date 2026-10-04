import os
from flask import Flask, jsonify, send_from_directory
from app.config import Config
from app.extensions import db, jwt, migrate
from app.models.user import User
from app.models.application import Application, ApplicationStatus
from app.models.system_setting import SystemSetting
from app.models.audit_log import AuditLog
from app.routes import (
    auth_bp,
    apps_bp,
    health_bp,
    backups_bp,
    recovery_bp,
    dashboard_bp,
    events_bp,
    simulation_bp
)

health_worker = None
backup_worker = None

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize Extensions
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)

    # Register Blueprints
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(apps_bp, url_prefix="/api/applications")
    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(backups_bp, url_prefix="/api/backups")
    app.register_blueprint(recovery_bp, url_prefix="/api/recoveries")
    app.register_blueprint(dashboard_bp, url_prefix="/api/dashboard")
    app.register_blueprint(events_bp, url_prefix="/api")
    app.register_blueprint(simulation_bp, url_prefix="/api/simulation")

    # Serve Frontend static and pages
    frontend_dir = os.environ.get("FRONTEND_DIR") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
    if not os.path.exists(frontend_dir) and os.path.exists("/app/frontend"):
        frontend_dir = "/app/frontend"

    @app.route("/", methods=["GET"])
    def index():
        return send_from_directory(frontend_dir, "index.html")

    @app.route("/<path:path>", methods=["GET"])
    def serve_frontend_files(path):
        if os.path.exists(os.path.join(frontend_dir, path)):
            return send_from_directory(frontend_dir, path)
        return send_from_directory(frontend_dir, "index.html")

    # Error handling
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "NOT_FOUND", "message": "The requested resource was not found"}), 404

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({"error": "INTERNAL_SERVER_ERROR", "message": "An internal server error occurred"}), 500

    # Auto seed initial database objects on startup
    with app.app_context():
        db.create_all()
        _seed_initial_data(app)

    # Start Background Workers if enabled
    if app.config.get("RUN_BACKGROUND_WORKERS", True):
        _start_workers(app)

    return app

def _seed_initial_data(app):
    # 1. Seed Users (Admin & Operator)
    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin", email="admin@cdro.internal", role="admin")
        admin.set_password("admin123")
        db.session.add(admin)

    if not User.query.filter_by(username="operator").first():
        operator = User(username="operator", email="operator@cdro.internal", role="operator")
        operator.set_password("operator123")
        db.session.add(operator)

    # 2. Seed Default Monitored Application: DemoApp
    demo_app = Application.query.filter_by(name="DemoApp").first()
    demo_url = app.config.get("DEMOAPP_URL", "http://localhost:5001")
    if not demo_app:
        demo_app = Application(
            name="DemoApp",
            description="Core Cloud E-Commerce Demo Application (Users & Catalog)",
            health_url=f"{demo_url}/health",
            api_url=f"{demo_url}/api/data",
            internal_url=demo_url,
            status=ApplicationStatus.HEALTHY,
            consecutive_failures=0
        )
        db.session.add(demo_app)
        db.session.flush()

        audit = AuditLog(
            application_id=demo_app.id,
            event_type="APPLICATION_REGISTERED",
            severity="INFO",
            message="DemoApp registered for continuous health monitoring and automated disaster recovery."
        )
        db.session.add(audit)

    # 3. Seed System Settings
    defaults = {
        "HEALTH_CHECK_INTERVAL": str(app.config.get("HEALTH_CHECK_INTERVAL_SECONDS", 5)),
        "HEALTH_FAILURE_THRESHOLD": str(app.config.get("HEALTH_FAILURE_THRESHOLD", 3)),
        "BACKUP_INTERVAL": str(app.config.get("BACKUP_INTERVAL_SECONDS", 300)),
        "BACKUP_RETENTION_COUNT": str(app.config.get("BACKUP_RETENTION_COUNT", 10)),
        "RTO_TARGET_SECONDS": str(app.config.get("RTO_TARGET_SECONDS", 60)),
        "STORAGE_BACKEND": app.config.get("STORAGE_BACKEND", "local")
    }
    for k, v in defaults.items():
        if not SystemSetting.query.filter_by(key=k).first():
            db.session.add(SystemSetting(key=k, value=v, description=f"Config setting for {k}"))

    db.session.commit()

def _start_workers(app):
    global health_worker, backup_worker
    from app.workers.health_monitor import HealthMonitorWorker
    from app.workers.backup_scheduler import BackupSchedulerWorker

    if health_worker is None:
        health_worker = HealthMonitorWorker(lambda: app)
        health_worker.start()

    if backup_worker is None:
        backup_worker = BackupSchedulerWorker(lambda: app)
        backup_worker.start()
