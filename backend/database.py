import os
import json
import sqlite3
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

# ============================================================
# DATABASE MODE DETECTION
# Priority order (Vercel-safe, IPv4 pooler first):
#   1. POSTGRES_URL        → Vercel Supabase pooler (IPv4, port 6543)
#   2. POSTGRES_PRISMA_URL → Session pooler fallback
#   3. DATABASE_URL        → Custom URL (last resort)
# Local dev: falls back to SQLite
# ============================================================

# psycopg2-supported connection URI parameters only
_VALID_PG_PARAMS = {
    'host','port','dbname','user','password','sslmode','sslcert','sslkey',
    'sslrootcert','connect_timeout','application_name','options'
}

def _clean_url(val):
    """Strip whitespace, newlines, and unsupported query params from a Postgres URL."""
    if not val:
        return None
    val = val.strip()
    try:
        parsed = urlparse(val)
        # Keep only psycopg2-compatible query parameters
        qs = parse_qs(parsed.query, keep_blank_values=True)
        filtered = {k: v for k, v in qs.items() if k in _VALID_PG_PARAMS}
        clean = parsed._replace(query=urlencode(filtered, doseq=True))
        return urlunparse(clean)
    except Exception:
        return val

DATABASE_URL = (
    _clean_url(os.environ.get('POSTGRES_URL')) or
    _clean_url(os.environ.get('POSTGRES_PRISMA_URL')) or
    _clean_url(os.environ.get('DATABASE_URL'))
)
IS_POSTGRES  = bool(DATABASE_URL)
IS_VERCEL    = os.environ.get('VERCEL') == '1'

# SQLite fallback path (local dev only)
if IS_VERCEL and not IS_POSTGRES:
    DB_PATH = '/tmp/lifelink.db'
else:
    DB_PATH = os.path.join(os.path.dirname(__file__), 'lifelink.db')

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), 'schema.sql')



# ============================================================
# UNIFIED CONNECTION WRAPPER
# Returns a connection that behaves like sqlite3 for app.py
# ============================================================

class PgCursor:
    """Wraps psycopg2 RealDictCursor to behave like sqlite3.Row cursor."""
    def __init__(self, cursor):
        self._cur = cursor

    def execute(self, sql, params=None):
        sql = _to_pg(sql)
        self._cur.execute(sql, params or ())
        return self

    def executemany(self, sql, seq):
        sql = _to_pg(sql)
        for params in seq:
            self._cur.execute(sql, params)

    def fetchone(self):
        row = self._cur.fetchone()
        if row is None:
            return None
        return _DictRow(dict(row))

    def fetchall(self):
        rows = self._cur.fetchall()
        return [_DictRow(dict(r)) for r in rows]

    @property
    def lastrowid(self):
        return self._cur.fetchone()[0] if self._cur.description else None

    def close(self):
        self._cur.close()


class _DictRow(dict):
    """Dict that also supports integer index access (like sqlite3.Row)."""
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


def _to_pg(sql):
    """Convert SQLite-style ? placeholders to PostgreSQL %s."""
    return sql.replace('?', '%s')


class PgConnection:
    """Wraps psycopg2 connection to match sqlite3 interface used in app.py."""
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        import psycopg2.extras
        return PgCursor(self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor))

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    # Support `with` statement
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()


# ============================================================
# PUBLIC API
# ============================================================

def get_db_connection():
    """Return a unified DB connection (PostgreSQL or SQLite)."""
    if IS_POSTGRES:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        return PgConnection(conn)
    else:
        if not os.path.exists(DB_PATH):
            init_db()
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn


def init_db():
    """Create all tables and seed initial data if the DB is empty."""
    print("Initializing LifeLink database...")

    if IS_POSTGRES:
        _init_postgres()
    else:
        _init_sqlite()


# ============================================================
# SQLITE INIT
# ============================================================

def _init_sqlite():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    with open(SCHEMA_PATH, 'r') as f:
        cursor.executescript(f.read())
    conn.commit()
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        print("Seeding SQLite...")
        seed_data(conn)
    else:
        print("SQLite already seeded.")
    conn.close()


# ============================================================
# POSTGRES INIT
# ============================================================

PG_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS donors (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(50) NOT NULL,
    blood_group VARCHAR(5) NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    last_donation_date DATE,
    total_donations INTEGER DEFAULT 0,
    response_speed_history INTEGER DEFAULT 300,
    is_available BOOLEAN DEFAULT TRUE,
    ai_donor_score REAL DEFAULT 70.0,
    badges TEXT DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS patients (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(50) NOT NULL,
    medical_condition VARCHAR(255),
    hospital_name VARCHAR(255),
    latitude REAL,
    longitude REAL
);

CREATE TABLE IF NOT EXISTS blood_requests (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    blood_group VARCHAR(5) NOT NULL,
    units_needed INTEGER NOT NULL DEFAULT 1,
    hospital_name VARCHAR(255) NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    priority VARCHAR(50) DEFAULT 'Medium',
    status VARCHAR(50) DEFAULT 'Pending',
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS donation_history (
    id SERIAL PRIMARY KEY,
    donor_id INTEGER NOT NULL REFERENCES donors(id) ON DELETE CASCADE,
    request_id INTEGER REFERENCES blood_requests(id) ON DELETE SET NULL,
    units INTEGER DEFAULT 1,
    donation_date DATE DEFAULT CURRENT_DATE,
    status VARCHAR(50) DEFAULT 'Completed',
    certificate_code VARCHAR(100) UNIQUE
);

CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    type VARCHAR(50) DEFAULT 'info',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ai_predictions_log (
    id SERIAL PRIMARY KEY,
    model_type VARCHAR(100) NOT NULL,
    input_parameters TEXT NOT NULL,
    prediction_result TEXT NOT NULL,
    confidence_score REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS hospitals_and_banks (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL,
    phone VARCHAR(50) NOT NULL,
    address VARCHAR(255) NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS password_resets (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    otp VARCHAR(6) NOT NULL,
    expires_at TIMESTAMP NOT NULL
);
"""

def _init_postgres():
    import psycopg2
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute(PG_SCHEMA)
    conn.commit()

    # Check if already seeded
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()

    if count == 0:
        print("Seeding PostgreSQL...")
        pg_conn = PgConnection(psycopg2.connect(DATABASE_URL))
        seed_data(pg_conn)
        pg_conn.close()
    else:
        print("PostgreSQL already seeded.")


# ============================================================
# SEED DATA (shared for both SQLite and PostgreSQL)
# ============================================================

def seed_data(conn):
    cursor = conn.cursor()

    hashed_pwd  = generate_password_hash("password123")
    admin_pwd   = generate_password_hash("admin123")

    # 1. Users
    users_data = [
        ('admin@lifelink.com',             admin_pwd,   'admin'),
        ('john.doe@gmail.com',             hashed_pwd,  'donor'),
        ('jane.smith@yahoo.com',           hashed_pwd,  'donor'),
        ('alice.johnson@outlook.com',      hashed_pwd,  'donor'),
        ('bob.brown@gmail.com',            hashed_pwd,  'donor'),
        ('charlie.green@gmail.com',        hashed_pwd,  'donor'),
        ('david.miller@gmail.com',         hashed_pwd,  'donor'),
        ('emily.davis@gmail.com',          hashed_pwd,  'donor'),
        ('sarah.connor@gmail.com',         hashed_pwd,  'patient'),
        ('bruce.wayne@waynecorp.com',      hashed_pwd,  'patient'),
        ('clark.kent@dailyplanet.com',     hashed_pwd,  'patient'),
    ]

    for u in users_data:
        cursor.execute(
            "INSERT INTO users (email, password_hash, role) VALUES (?, ?, ?)",
            u
        )
    conn.commit()

    cursor.execute("SELECT id, email FROM users")
    user_map = {r['email']: r['id'] for r in cursor.fetchall()}

    # 2. Donors
    donors_data = [
        (user_map['john.doe@gmail.com'],        'John Doe',      '+91-9948712312', 'A+',  12.9785, 77.5902, '2026-02-15', 5,  120, 1, 92.5, json.dumps(["lifesaver","fastresponder"])),
        (user_map['jane.smith@yahoo.com'],       'Jane Smith',    '+91-9948712313', 'O-',  12.9692, 77.6015, '2026-04-10', 8,  240, 1, 95.8, json.dumps(["lifesaver","veterandonor","rareblood"])),
        (user_map['alice.johnson@outlook.com'],  'Alice Johnson', '+91-9948712314', 'B+',  12.9810, 77.6120, '2025-11-20', 2,  600, 1, 78.4, json.dumps(["newbie"])),
        (user_map['bob.brown@gmail.com'],        'Bob Brown',     '+91-9948712315', 'AB+', 12.9615, 77.5850, '2026-01-05', 12, 180, 0, 88.0, json.dumps(["veterandonor"])),
        (user_map['charlie.green@gmail.com'],    'Charlie Green', '+91-9948712316', 'O+',  12.9550, 77.5990, None,         0,  300, 1, 70.0, json.dumps([])),
        (user_map['david.miller@gmail.com'],     'David Miller',  '+91-9948712317', 'A-',  12.9902, 77.5780, '2026-03-01', 3,  150, 1, 84.2, json.dumps(["fastresponder"])),
        (user_map['emily.davis@gmail.com'],      'Emily Davis',   '+91-9948712318', 'B-',  12.9620, 77.6250, '2026-05-18', 4,  210, 1, 89.1, json.dumps(["lifesaver"])),
    ]

    cursor.executemany(
        """INSERT INTO donors (user_id, name, phone, blood_group, latitude, longitude,
           last_donation_date, total_donations, response_speed_history, is_available,
           ai_donor_score, badges) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        donors_data
    )

    # 3. Patients
    patients_data = [
        (user_map['sarah.connor@gmail.com'],    'Sarah Connor', '+91-9948712320', 'Anemia Relief',            'City General Hospital', 12.9716, 77.5946),
        (user_map['bruce.wayne@waynecorp.com'], 'Bruce Wayne',  '+91-9948712321', 'Emergency Trauma Surgery', 'St. Marys Hospital',    12.9650, 77.6050),
        (user_map['clark.kent@dailyplanet.com'],'Clark Kent',   '+91-9948712322', 'Leukemia Treatment',       'Metro Health Center',   12.9850, 77.5990),
    ]

    cursor.executemany(
        """INSERT INTO patients (user_id, name, phone, medical_condition, hospital_name, latitude, longitude)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        patients_data
    )

    # 4. Blood Requests
    requests_data = [
        (user_map['sarah.connor@gmail.com'],    'A+', 2, 'City General Hospital', 12.9716, 77.5946, 'High',     'Pending',  'Urgent need for blood due to scheduled surgery.'),
        (user_map['bruce.wayne@waynecorp.com'], 'O-', 3, 'St. Marys Hospital',    12.9650, 77.6050, 'Critical', 'Matching', 'Emergency request for internal bleeding trauma recovery.'),
        (user_map['clark.kent@dailyplanet.com'],'B-', 1, 'Metro Health Center',   12.9850, 77.5990, 'Medium',   'Fulfilled','Routine chemotherapy blood support.'),
    ]

    cursor.executemany(
        """INSERT INTO blood_requests (patient_id, blood_group, units_needed, hospital_name,
           latitude, longitude, priority, status, details) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        requests_data
    )
    conn.commit()

    # 5. Donation History
    cursor.execute("SELECT id FROM donors WHERE name = 'John Doe'")
    john_id = cursor.fetchone()[0]
    cursor.execute("SELECT id FROM donors WHERE name = 'Jane Smith'")
    jane_id = cursor.fetchone()[0]
    cursor.execute("SELECT id FROM blood_requests WHERE status = 'Fulfilled'")
    req_id  = cursor.fetchone()[0]

    history_data = [
        (john_id, None,   1, '2026-02-15', 'Completed', 'CERT-JD-98273'),
        (jane_id, req_id, 1, '2026-04-10', 'Completed', 'CERT-JS-43890'),
        (john_id, None,   1, '2025-10-12', 'Completed', 'CERT-JD-12948'),
    ]

    cursor.executemany(
        """INSERT INTO donation_history (donor_id, request_id, units, donation_date, status, certificate_code)
           VALUES (?, ?, ?, ?, ?, ?)""",
        history_data
    )

    # 6. Notifications
    notifications_data = [
        (user_map['john.doe@gmail.com'],    'Critical Request Nearby!', 'An emergency O- request was raised near your location.', 0, 'emergency'),
        (user_map['john.doe@gmail.com'],    'Badge Unlocked!',          'You unlocked the Life Saver badge for 5 donations.',       0, 'badge'),
        (user_map['sarah.connor@gmail.com'],'Matching Donors Found',    'AI found 2 nearby compatible donors. Notifications sent.', 0, 'success'),
        (user_map['admin@lifelink.com'],    'Critical Alert Broadcast', 'Urgent O- emergency broadcast to all O- donors in 10km.',  0, 'info'),
    ]

    cursor.executemany(
        "INSERT INTO notifications (user_id, title, message, is_read, type) VALUES (?, ?, ?, ?, ?)",
        notifications_data
    )

    # 7. Hospitals and Blood Banks
    hospitals_data = [
        ('Bangalore Blood Bank',                  'Blood Bank', '+91-80-555-1234', '12, Residency Rd, Bengaluru',          12.9680, 77.5920),
        ('Red Cross Blood Depot',                 'Blood Bank', '+91-80-555-5678', '45, Race Course Rd, Bengaluru',        12.9750, 77.5890),
        ('Mallya Hospital & Trauma Center',       'Hospital',   '+91-80-555-9999', '2, Vittal Mallya Rd, Bengaluru',       12.9650, 77.5970),
        ("St. John's Medical College & Hospital", 'Hospital',   '+91-80-555-8888', 'Sarjapur Rd, Bengaluru',               12.9340, 77.6210),
        ('Fortis Hospital',                       'Hospital',   '+91-80-555-7777', '14, Cunningham Rd, Bengaluru',         12.9780, 77.5910),
        ('Narayana Health Blood Bank',            'Blood Bank', '+91-80-555-4444', '258/A, Bommasandra, Bengaluru',        12.9720, 77.6110),
        ('Columbia Asia Blood Bank',              'Blood Bank', '+91-80-555-3333', 'Hebbal, Outer Ring Rd, Bengaluru',     12.9890, 77.6080),
    ]

    cursor.executemany(
        "INSERT INTO hospitals_and_banks (name, type, phone, address, latitude, longitude) VALUES (?, ?, ?, ?, ?, ?)",
        hospitals_data
    )

    conn.commit()
    print("Database seeding completed successfully!")


if __name__ == '__main__':
    init_db()
