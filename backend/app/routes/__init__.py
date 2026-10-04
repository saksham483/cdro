from app.routes.auth import auth_bp
from app.routes.applications import apps_bp
from app.routes.health import health_bp
from app.routes.backups import backups_bp
from app.routes.recovery import recovery_bp
from app.routes.dashboard import dashboard_bp
from app.routes.events import events_bp
from app.routes.simulation import simulation_bp

__all__ = [
    "auth_bp",
    "apps_bp",
    "health_bp",
    "backups_bp",
    "recovery_bp",
    "dashboard_bp",
    "events_bp",
    "simulation_bp"
]
