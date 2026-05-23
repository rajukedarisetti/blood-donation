-- ========================================================
-- LIFELINK: AI BLOOD DONATION FINDER - DATABASE SCHEMA
-- Compatible with SQLite, PostgreSQL, and MySQL
-- ========================================================

-- 1. USERS TABLE (Core Authentication & Role Management)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL, -- 'donor', 'patient', 'admin'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. DONORS TABLE (Profile details, availability, and AI ranking fields)
CREATE TABLE IF NOT EXISTS donors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(50) NOT NULL,
    blood_group VARCHAR(5) NOT NULL, -- A+, A-, B+, B-, AB+, AB-, O+, O-
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    last_donation_date DATE, -- NULL if never donated
    total_donations INTEGER DEFAULT 0,
    response_speed_history INTEGER DEFAULT 300, -- Average response speed in seconds
    is_available BOOLEAN DEFAULT 1, -- 1 = Available, 0 = Unavailable
    ai_donor_score REAL DEFAULT 70.0, -- Composite AI ranking score (0-100)
    badges VARCHAR(555) DEFAULT '[]', -- JSON string of badges: ["lifesaver", "fastresponder"]
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 3. PATIENTS TABLE (Patient Profile Details)
CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(50) NOT NULL,
    medical_condition VARCHAR(255),
    hospital_name VARCHAR(255),
    latitude REAL,
    longitude REAL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 4. BLOOD REQUESTS TABLE (Emergency Requests)
CREATE TABLE IF NOT EXISTS blood_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    blood_group VARCHAR(5) NOT NULL,
    units_needed INTEGER NOT NULL DEFAULT 1,
    hospital_name VARCHAR(255) NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    priority VARCHAR(50) DEFAULT 'Medium', -- 'Critical', 'High', 'Medium', 'Low'
    status VARCHAR(50) DEFAULT 'Pending', -- 'Pending', 'Matching', 'Fulfilled', 'Cancelled'
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 5. DONATION HISTORY TABLE (Logs of completed blood donations)
CREATE TABLE IF NOT EXISTS donation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    donor_id INTEGER NOT NULL,
    request_id INTEGER,
    units INTEGER DEFAULT 1,
    donation_date DATE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'Completed', -- 'Completed', 'Scheduled'
    certificate_code VARCHAR(100) UNIQUE,
    FOREIGN KEY (donor_id) REFERENCES donors(id) ON DELETE CASCADE,
    FOREIGN KEY (request_id) REFERENCES blood_requests(id) ON DELETE SET NULL
);

-- 6. NOTIFICATIONS TABLE (Real-time & System dashboard alerts)
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT 0,
    type VARCHAR(50) DEFAULT 'info', -- 'emergency', 'success', 'info', 'badge'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 7. AI PREDICTIONS LOG (Audits model performance & logs details)
CREATE TABLE IF NOT EXISTS ai_predictions_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_type VARCHAR(100) NOT NULL, -- 'availability', 'demand_forecast', 'priority'
    input_parameters TEXT NOT NULL, -- JSON dump of features
    prediction_result TEXT NOT NULL, -- JSON dump of outputs
    confidence_score REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
