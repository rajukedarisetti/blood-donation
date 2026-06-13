import os
import sqlite3
import json
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

# Detect Vercel serverless environment — use /tmp for writable SQLite
IS_VERCEL = os.environ.get('VERCEL') == '1'

if IS_VERCEL:
    DB_PATH = '/tmp/lifelink.db'
else:
    DB_PATH = os.path.join(os.path.dirname(__file__), 'lifelink.db')

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), 'schema.sql')

def get_db_connection():
    # Auto-initialize DB if it doesn't exist (handles Vercel cold starts)
    if not os.path.exists(DB_PATH):
        init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database and seeds it if it is empty."""
    print("Initializing LifeLink database...")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Execute schema.sql to create tables
    with open(SCHEMA_PATH, 'r') as f:
        schema_sql = f.read()
    cursor.executescript(schema_sql)
    conn.commit()

    # Check if database is already seeded
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        print("Database empty. Seeding initial data...")
        seed_data(conn)
    else:
        print("Database already contains data. Skipping seeding.")
    
    conn.close()

def seed_data(conn):
    cursor = conn.cursor()

    # Hashed passwords for all roles (use simple common passwords for ease of testing)
    hashed_pwd = generate_password_hash("password123")
    admin_pwd = generate_password_hash("admin123")

    # 1. Seed Users (Admin, Donors, Patients)
    users_data = [
        # Admin
        ('admin@lifelink.com', admin_pwd, 'admin'),
        
        # Donors
        ('john.doe@gmail.com', hashed_pwd, 'donor'),
        ('jane.smith@yahoo.com', hashed_pwd, 'donor'),
        ('alice.johnson@outlook.com', hashed_pwd, 'donor'),
        ('bob.brown@gmail.com', hashed_pwd, 'donor'),
        ('charlie.green@gmail.com', hashed_pwd, 'donor'),
        ('david.miller@gmail.com', hashed_pwd, 'donor'),
        ('emily.davis@gmail.com', hashed_pwd, 'donor'),
        
        # Patients
        ('sarah.connor@gmail.com', hashed_pwd, 'patient'),
        ('bruce.wayne@waynecorp.com', hashed_pwd, 'patient'),
        ('clark.kent@dailyplanet.com', hashed_pwd, 'patient')
    ]

    cursor.executemany(
        "INSERT INTO users (email, password_hash, role) VALUES (?, ?, ?)",
        users_data
    )
    conn.commit()

    # Fetch User IDs to link profiles correctly
    cursor.execute("SELECT id, email, role FROM users")
    users = cursor.fetchall()
    user_map = {u['email']: u['id'] for u in users}

    # 2. Seed Donors
    # Coords centered around a mock metro city center, e.g. (12.9716, 77.5946) Bangalore or NY
    # We will use realistic latitude and longitude coordinates for local testing.
    donors_data = [
        (user_map['john.doe@gmail.com'], 'John Doe', '+1-555-0101', 'A+', 12.9785, 77.5902, '2026-02-15', 5, 120, 1, 92.5, json.dumps(["lifesaver", "fastresponder"])),
        (user_map['jane.smith@yahoo.com'], 'Jane Smith', '+1-555-0102', 'O-', 12.9692, 77.6015, '2026-04-10', 8, 240, 1, 95.8, json.dumps(["lifesaver", "veterandonor", "rareblood"])),
        (user_map['alice.johnson@outlook.com'], 'Alice Johnson', '+1-555-0103', 'B+', 12.9810, 77.6120, '2025-11-20', 2, 600, 1, 78.4, json.dumps(["newbie"])),
        (user_map['bob.brown@gmail.com'], 'Bob Brown', '+1-555-0104', 'AB+', 12.9615, 77.5850, '2026-01-05', 12, 180, 0, 88.0, json.dumps(["veterandonor"])),
        (user_map['charlie.green@gmail.com'], 'Charlie Green', '+1-555-0105', 'O+', 12.9550, 77.5990, None, 0, 300, 1, 70.0, json.dumps([])),
        (user_map['david.miller@gmail.com'], 'David Miller', '+1-555-0106', 'A-', 12.9902, 77.5780, '2026-03-01', 3, 150, 1, 84.2, json.dumps(["fastresponder"])),
        (user_map['emily.davis@gmail.com'], 'Emily Davis', '+1-555-0107', 'B-', 12.9620, 77.6250, '2026-05-18', 4, 210, 1, 89.1, json.dumps(["lifesaver"]))
    ]

    cursor.executemany(
        """INSERT INTO donors (user_id, name, phone, blood_group, latitude, longitude, 
           last_donation_date, total_donations, response_speed_history, is_available, ai_donor_score, badges)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        donors_data
    )

    # 3. Seed Patients
    patients_data = [
        (user_map['sarah.connor@gmail.com'], 'Sarah Connor', '+1-555-0201', 'Anemia Relief', 'City General Hospital', 12.9716, 77.5946),
        (user_map['bruce.wayne@waynecorp.com'], 'Bruce Wayne', '+1-555-0202', 'Emergency Trauma Surgery', 'St. Marys Hospital', 12.9650, 77.6050),
        (user_map['clark.kent@dailyplanet.com'], 'Clark Kent', '+1-555-0203', 'Leukemia Treatment', 'Metro Health Center', 12.9850, 77.5990)
    ]

    cursor.executemany(
        """INSERT INTO patients (user_id, name, phone, medical_condition, hospital_name, latitude, longitude)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        patients_data
    )

    # 4. Seed Blood Requests
    requests_data = [
        # Patient Sarah Connor (A+), Priority High
        (user_map['sarah.connor@gmail.com'], 'A+', 2, 'City General Hospital', 12.9716, 77.5946, 'High', 'Pending', 'Urgent need for O- or A+ blood due to major scheduled surgery.'),
        # Patient Bruce Wayne (O+), Priority Critical
        (user_map['bruce.wayne@waynecorp.com'], 'O-', 3, 'St. Marys Hospital', 12.9650, 77.6050, 'Critical', 'Matching', 'Emergency request for internal bleeding trauma recovery. Highly critical!'),
        # Patient Clark Kent (B-), Priority Medium, Already Fulfilled
        (user_map['clark.kent@dailyplanet.com'], 'B-', 1, 'Metro Health Center', 12.9850, 77.5990, 'Medium', 'Fulfilled', 'Routine chemotherapy blood support.')
    ]

    cursor.executemany(
        """INSERT INTO blood_requests (patient_id, blood_group, units_needed, hospital_name, latitude, longitude, priority, status, details)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        requests_data
    )
    conn.commit()

    # 5. Seed Donation History
    # We will link Emily Davis and John Doe as donors who completed historic donations
    cursor.execute("SELECT id FROM donors WHERE name = 'John Doe'")
    john_id = cursor.fetchone()[0]
    cursor.execute("SELECT id FROM donors WHERE name = 'Jane Smith'")
    jane_id = cursor.fetchone()[0]
    cursor.execute("SELECT id FROM blood_requests WHERE status = 'Fulfilled'")
    req_fulfilled_id = cursor.fetchone()[0]

    history_data = [
        (john_id, None, 1, '2026-02-15', 'Completed', 'CERT-JD-98273'),
        (jane_id, req_fulfilled_id, 1, '2026-04-10', 'Completed', 'CERT-JS-43890'),
        (john_id, None, 1, '2025-10-12', 'Completed', 'CERT-JD-12948')
    ]

    cursor.executemany(
        """INSERT INTO donation_history (donor_id, request_id, units, donation_date, status, certificate_code)
           VALUES (?, ?, ?, ?, ?, ?)""",
        history_data
    )

    # 6. Seed Notifications
    notifications_data = [
        (user_map['john.doe@gmail.com'], 'Critical Request Nearby!', 'An emergency O- request was raised near your location. Click to respond.', 0, 'emergency'),
        (user_map['john.doe@gmail.com'], 'Bronze Badge Unlocked!', 'Congratulations! You unlocked the "Life Saver" badge for completing 5 donations.', 0, 'badge'),
        (user_map['sarah.connor@gmail.com'], 'Matching Donors Found', 'AI has found 2 nearby donors compatible with your request. Notifications sent.', 0, 'success'),
        (user_map['admin@lifelink.com'], 'Critical Alert Broadcasted', 'Urgent O- emergency broadcasted to all available O- donors in a 10km radius.', 0, 'info')
    ]

    cursor.executemany(
        "INSERT INTO notifications (user_id, title, message, is_read, type) VALUES (?, ?, ?, ?, ?)",
        notifications_data
    )

    # 7. Seed AI Predictions Log
    predictions_data = [
        ('availability', json.dumps({'donor_id': 1, 'hour': 14, 'distance_km': 1.5}), json.dumps({'response_probability': 0.94}), 0.94),
        ('demand_forecast', json.dumps({'blood_group': 'O-', 'week': 22}), json.dumps({'predicted_shortage': 'Critical Shortage Expected'}), 0.88),
        ('priority', json.dumps({'hemoglobin': 7.5, 'bleeding': 1, 'trauma': 1}), json.dumps({'priority': 'Critical'}), 0.97)
    ]

    cursor.executemany(
        "INSERT INTO ai_predictions_log (model_type, input_parameters, prediction_result, confidence_score) VALUES (?, ?, ?, ?)",
        predictions_data
    )

    conn.commit()
    print("Database seeding completed successfully!")

if __name__ == '__main__':
    init_db()
