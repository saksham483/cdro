import sqlite3
import os

DB_PATH = os.environ.get("DEMOAPP_DB_PATH", os.path.join(os.path.dirname(__file__), "data", "demoapp.db"))

def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL
            )
        ''')
        # Seed initial data if empty
        cursor.execute('SELECT COUNT(*) FROM users')
        if cursor.fetchone()[0] == 0:
            cursor.executemany(
                'INSERT INTO users (name, email) VALUES (?, ?)',
                [
                    ('Alice Johnson', 'alice@example.com'),
                    ('Bob Smith', 'bob@example.com'),
                    ('Charlie Brown', 'charlie@example.com')
                ]
            )
        cursor.execute('SELECT COUNT(*) FROM products')
        if cursor.fetchone()[0] == 0:
            cursor.executemany(
                'INSERT INTO products (name, price) VALUES (?, ?)',
                [
                    ('Enterprise Cloud Laptop', 1299.99),
                    ('Secure Hardware Token Phone', 799.50),
                    ('Mechanical Ops Keyboard', 149.00),
                    ('Ultra-wide 4K Monitor', 499.00)
                ]
            )
        conn.commit()
