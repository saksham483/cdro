import os
import json
import sqlite3
from datetime import datetime, timezone
from flask import Flask, jsonify, request
try:
    from models import get_db, init_db, DB_PATH
except ImportError:
    from demoapp.models import get_db, init_db, DB_PATH

app = Flask(__name__)

# State flags
INTERNAL_SECRET = os.environ.get("INTERNAL_SECRET", "demoapp-internal-auth-token-48291")
FAILURE_FLAG_PATH = os.path.join(os.path.dirname(__file__), "data", ".failure_state")

def is_failure_mode_active():
    return os.path.exists(FAILURE_FLAG_PATH)

def set_failure_mode(active: bool):
    os.makedirs(os.path.dirname(FAILURE_FLAG_PATH), exist_ok=True)
    if active:
        with open(FAILURE_FLAG_PATH, "w") as f:
            f.write(f"failed_at={datetime.now(timezone.utc).isoformat()}")
    else:
        if os.path.exists(FAILURE_FLAG_PATH):
            try:
                os.remove(FAILURE_FLAG_PATH)
            except OSError:
                pass

# Initialize database on startup
init_db()

@app.route("/", methods=["GET"])
def index():
    if is_failure_mode_active():
        return jsonify({
            "status": "error",
            "error": "DemoApp service unavailable (Simulated Outage)",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 500

    with get_db() as conn:
        users_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        products_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]

    return jsonify({
        "application": "DemoApp",
        "description": "Sample Cloud Production Web Application",
        "version": "1.0.0",
        "status": "online",
        "records": {
            "users": users_count,
            "products": products_count
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }), 200

@app.route("/health", methods=["GET"])
def health():
    if is_failure_mode_active():
        return jsonify({
            "status": "unhealthy",
            "application": "DemoApp",
            "error": "Simulated hardware/network/application failure active",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "1.0.0"
        }), 500

    return jsonify({
        "status": "healthy",
        "application": "DemoApp",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0"
    }), 200

@app.route("/api/data", methods=["GET"])
def get_data():
    if is_failure_mode_active():
        return jsonify({"error": "Service Unavailable - Application in Failure State"}), 500

    with get_db() as conn:
        users = [dict(r) for r in conn.execute("SELECT * FROM users ORDER BY id ASC").fetchall()]
        products = [dict(r) for r in conn.execute("SELECT * FROM products ORDER BY id ASC").fetchall()]

    return jsonify({
        "status": "success",
        "application": "DemoApp",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": {
            "users": users,
            "products": products
        }
    }), 200

@app.route("/api/data/user", methods=["POST"])
def add_user():
    if is_failure_mode_active():
        return jsonify({"error": "Service Unavailable"}), 500

    payload = request.get_json(silent=True) or {}
    name = payload.get("name")
    email = payload.get("email")
    if not name or not email:
        return jsonify({"error": "Both 'name' and 'email' are required"}), 400

    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (name, email) VALUES (?, ?)", (name, email))
            new_id = cursor.lastrowid
            conn.commit()
        return jsonify({"status": "created", "id": new_id, "name": name, "email": email}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "Email already exists"}), 409

@app.route("/api/data/product", methods=["POST"])
def add_product():
    if is_failure_mode_active():
        return jsonify({"error": "Service Unavailable"}), 500

    payload = request.get_json(silent=True) or {}
    name = payload.get("name")
    price = payload.get("price")
    if not name or price is None:
        return jsonify({"error": "Both 'name' and 'price' are required"}), 400

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO products (name, price) VALUES (?, ?)", (name, float(price)))
        new_id = cursor.lastrowid
        conn.commit()
    return jsonify({"status": "created", "id": new_id, "name": name, "price": float(price)}), 201

@app.route("/api/data/<item_type>/<int:item_id>", methods=["DELETE"])
def delete_item(item_type, item_id):
    if is_failure_mode_active():
        return jsonify({"error": "Service Unavailable"}), 500

    table = "users" if item_type == "user" else "products" if item_type == "product" else None
    if not table:
        return jsonify({"error": "Invalid item type. Use 'user' or 'product'"}), 400

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {table} WHERE id = ?", (item_id,))
        if cursor.rowcount == 0:
            return jsonify({"error": f"Item with id {item_id} not found"}), 404
        conn.commit()
    return jsonify({"status": "deleted", "type": item_type, "id": item_id}), 200

# -------------------------------------------------------------
# Controlled Failure & Recovery Internal Endpoints
# -------------------------------------------------------------
def verify_internal_auth():
    auth_header = request.headers.get("X-Internal-Token")
    auth_param = request.args.get("secret")
    body_secret = None
    if request.is_json:
        body_secret = (request.get_json(silent=True) or {}).get("secret")

    provided = auth_header or auth_param or body_secret
    if provided != INTERNAL_SECRET:
        return False
    return True

@app.route("/internal/failure/enable", methods=["POST"])
def enable_failure():
    if not verify_internal_auth():
        return jsonify({"error": "Unauthorized access to internal failure endpoint"}), 401
    set_failure_mode(True)
    return jsonify({
        "status": "failure_enabled",
        "application": "DemoApp",
        "message": "DemoApp has entered controlled simulated outage mode. Health checks will now fail.",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }), 200

@app.route("/internal/failure/disable", methods=["POST"])
def disable_failure():
    if not verify_internal_auth():
        return jsonify({"error": "Unauthorized access to internal failure endpoint"}), 401
    set_failure_mode(False)
    return jsonify({
        "status": "failure_disabled",
        "application": "DemoApp",
        "message": "DemoApp failure mode disabled. Service is operating normally.",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }), 200

@app.route("/internal/backup/export", methods=["GET"])
def export_backup():
    if not verify_internal_auth():
        return jsonify({"error": "Unauthorized access to internal export endpoint"}), 401

    with get_db() as conn:
        users = [dict(r) for r in conn.execute("SELECT * FROM users ORDER BY id ASC").fetchall()]
        products = [dict(r) for r in conn.execute("SELECT * FROM products ORDER BY id ASC").fetchall()]

    return jsonify({
        "application": "DemoApp",
        "schema_version": "1.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "database": {
            "users": users,
            "products": products
        }
    }), 200

@app.route("/internal/restore", methods=["POST"])
def restore_backup():
    if not verify_internal_auth():
        return jsonify({"error": "Unauthorized access to internal restore endpoint"}), 401

    payload = request.get_json(silent=True) or {}
    database_data = payload.get("database")
    if not database_data or "users" not in database_data or "products" not in database_data:
        return jsonify({"error": "Invalid backup payload format"}), 400

    # 1. Restore sqlite database tables cleanly
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS users")
        cursor.execute("DROP TABLE IF EXISTS products")
        cursor.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE
            )
        ''')
        cursor.execute('''
            CREATE TABLE products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL
            )
        ''')
        for u in database_data["users"]:
            cursor.execute("INSERT INTO users (id, name, email) VALUES (?, ?, ?)",
                           (u["id"], u["name"], u["email"]))
        for p in database_data["products"]:
            cursor.execute("INSERT INTO products (id, name, price) VALUES (?, ?, ?)",
                           (p["id"], p["name"], p["price"]))
        conn.commit()

    # 2. Disable failure state to ensure service recovers
    set_failure_mode(False)

    return jsonify({
        "status": "restored",
        "application": "DemoApp",
        "restored_at": datetime.now(timezone.utc).isoformat(),
        "restored_records": {
            "users": len(database_data["users"]),
            "products": len(database_data["products"])
        }
    }), 200

if __name__ == "__main__":
    port = int(os.environ.get("DEMOAPP_PORT", 5001))
    print(f"Starting DemoApp on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False)
