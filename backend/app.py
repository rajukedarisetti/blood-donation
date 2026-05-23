import os
import json
import jwt
import math
import random
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

# Import database and AI engine helpers
from database import get_db_connection, DB_PATH
import ai_models

# Initialize Flask with custom template and static folders mapping to the frontend directory
app = Flask(
    __name__, 
    template_folder='../frontend/templates', 
    static_folder='../frontend/static'
)
app.config['SECRET_KEY'] = 'lifelink_ultra_secure_ai_blood_secret_key_2026'
CORS(app) # Enable CORS for all routes to support seamless frontend integrations

# ========================================================
# FRONTEND PAGE ROUTING
# ========================================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/auth')
def auth_page():
    return render_template('auth.html')

@app.route('/donor')
def donor_page():
    return render_template('donor.html')

@app.route('/patient')
def patient_page():
    return render_template('patient.html')

@app.route('/admin')
def admin_page():
    return render_template('admin.html')

@app.route('/certificate/<code>')
def certificate_page(code):
    return render_template('certificate.html', cert_code=code)

# ========================================================
# GEODETIC & SECURITY HELPER FUNCTIONS
# ========================================================

def haversine(lat1, lon1, lat2, lon2):
    """Calculates geodetic distance in kilometers between two lat/long points."""
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return 9999.0
    R = 6371.0 # Earth's radius in kilometers
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (math.sin(d_lat / 2) ** 2 + 
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# Token required decorator for JWT authentication
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(" ")[1]
        
        if not token:
            return jsonify({'status': 'error', 'message': 'Authentication token is missing!'}), 401
        
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, email, role FROM users WHERE id = ?", (data['user_id'],))
            user = cursor.fetchone()
            conn.close()
            
            if not user:
                return jsonify({'status': 'error', 'message': 'Invalid user context!'}), 401
            
            current_user = dict(user)
        except jwt.ExpiredSignatureError:
            return jsonify({'status': 'error', 'message': 'Token has expired!'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'status': 'error', 'message': 'Invalid token!'}), 401
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 401
            
        return f(current_user, *args, **kwargs)
    return decorated

# ========================================================
# JINJA TEMPLATE RENDERING ROUTEPAGES
# ========================================================

@app.route('/')
def render_index():
    return render_template('index.html')

@app.route('/auth')
def render_auth():
    return render_template('auth.html')

@app.route('/donor')
def render_donor():
    return render_template('donor.html')

@app.route('/patient')
def render_patient():
    return render_template('patient.html')

@app.route('/admin')
def render_admin():
    return render_template('admin.html')

@app.route('/certificate/<string:code>')
def render_certificate(code):
    return render_template('certificate.html', cert_code=code)

# ========================================================
# REST API ENDPOINTS - AUTHENTICATION
# ========================================================

@app.route('/api/status', methods=['GET'])
def system_status():
    return jsonify({
        'status': 'healthy',
        'app': 'LifeLink API Server',
        'timestamp': datetime.now().isoformat(),
        'ai_models': {
            'availability_predictor': ai_models._availability_data is not None or 'loaded (fallback available)',
            'demand_forecaster': ai_models._demand_data is not None or 'loaded (fallback available)',
            'priority_classifier': ai_models._priority_data is not None or 'loaded (fallback available)'
        }
    })

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')
    role = data.get('role') # 'donor', 'patient', 'admin'
    name = data.get('name')
    phone = data.get('phone')
    blood_group = data.get('blood_group', 'O+')
    
    # Coordinates default to Bangalore (12.9716, 77.5946) if not specified
    latitude = float(data.get('latitude', 12.9716))
    longitude = float(data.get('longitude', 77.5946))
    
    medical_condition = data.get('medical_condition', '')
    hospital_name = data.get('hospital_name', '')

    if not email or not password or not role or not name or not phone:
        return jsonify({'status': 'error', 'message': 'Missing required fields!'}), 400

    if role not in ['donor', 'patient', 'admin']:
        return jsonify({'status': 'error', 'message': 'Invalid role specified!'}), 400

    hashed_password = generate_password_hash(password)

    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Insert user
        cursor.execute(
            "INSERT INTO users (email, password_hash, role) VALUES (?, ?, ?)",
            (email, hashed_password, role)
        )
        user_id = cursor.lastrowid
        
        # Insert profile
        if role == 'donor':
            cursor.execute(
                """INSERT INTO donors (user_id, name, phone, blood_group, latitude, longitude, 
                   is_available, ai_donor_score, badges) VALUES (?, ?, ?, ?, ?, ?, 1, 75.0, '[]')""",
                (user_id, name, phone, blood_group, latitude, longitude)
            )
        elif role == 'patient':
            cursor.execute(
                """INSERT INTO patients (user_id, name, phone, medical_condition, hospital_name, latitude, longitude) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, name, phone, medical_condition, hospital_name, latitude, longitude)
            )
        
        # Welcome notification
        cursor.execute(
            "INSERT INTO notifications (user_id, title, message, type) VALUES (?, ?, ?, ?)",
            (user_id, 'Welcome to LifeLink!', f'Hello {name}, your registration as a {role} was successful. Thank you for joining our life-saving community.', 'info')
        )
        
        conn.commit()
        return jsonify({'status': 'success', 'message': 'Registration completed successfully!'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'status': 'error', 'message': 'User with this email already exists!'}), 409
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'status': 'error', 'message': 'Email and password are required!'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()

    if not user or not check_password_hash(user['password_hash'], password):
        conn.close()
        return jsonify({'status': 'error', 'message': 'Invalid email or password!'}), 401

    user_id = user['id']
    role = user['role']
    name = email.split('@')[0].replace('.', ' ').title()
    phone = ''
    blood_group = ''
    profile_details = {}

    if role == 'donor':
        cursor.execute("SELECT * FROM donors WHERE user_id = ?", (user_id,))
        donor = cursor.fetchone()
        if donor:
            name = donor['name']
            phone = donor['phone']
            blood_group = donor['blood_group']
            profile_details = dict(donor)
    elif role == 'patient':
        cursor.execute("SELECT * FROM patients WHERE user_id = ?", (user_id,))
        patient = cursor.fetchone()
        if patient:
            name = patient['name']
            phone = patient['phone']
            profile_details = dict(patient)

    conn.close()

    # Generate JWT Token (expires in 24 hours)
    token = jwt.encode({
        'user_id': user_id,
        'email': user['email'],
        'role': role,
        'exp': datetime.utcnow() + timedelta(hours=24)
    }, app.config['SECRET_KEY'], algorithm="HS256")

    return jsonify({
        'status': 'success',
        'message': 'Login successful!',
        'token': token,
        'user': {
            'id': user_id,
            'email': user['email'],
            'role': role,
            'name': name,
            'phone': phone,
            'blood_group': blood_group,
            'profile': profile_details
        }
    })

# ========================================================
# REST API ENDPOINTS - PROFILES & STATUS
# ========================================================

@app.route('/api/user/profile', methods=['GET'])
@token_required
def get_profile(current_user):
    conn = get_db_connection()
    cursor = conn.cursor()
    user_id = current_user['id']
    role = current_user['role']
    
    profile = {'email': current_user['email'], 'role': role}
    
    if role == 'donor':
        cursor.execute("SELECT * FROM donors WHERE user_id = ?", (user_id,))
        res = cursor.fetchone()
        if res:
            profile.update(dict(res))
    elif role == 'patient':
        cursor.execute("SELECT * FROM patients WHERE user_id = ?", (user_id,))
        res = cursor.fetchone()
        if res:
            profile.update(dict(res))
            
    conn.close()
    return jsonify({'status': 'success', 'data': profile})

@app.route('/api/user/profile', methods=['PUT'])
@token_required
def update_profile(current_user):
    data = request.get_json() or {}
    conn = get_db_connection()
    cursor = conn.cursor()
    user_id = current_user['id']
    role = current_user['role']
    
    try:
        if role == 'donor':
            cursor.execute(
                """UPDATE donors SET name=?, phone=?, blood_group=?, latitude=?, longitude=?, is_available=?
                   WHERE user_id=?""",
                (data.get('name'), data.get('phone'), data.get('blood_group'), 
                 float(data.get('latitude', 12.9716)), float(data.get('longitude', 77.5946)), 
                 int(data.get('is_available', 1)), user_id)
            )
        elif role == 'patient':
            cursor.execute(
                """UPDATE patients SET name=?, phone=?, medical_condition=?, hospital_name=?, latitude=?, longitude=?
                   WHERE user_id=?""",
                (data.get('name'), data.get('phone'), data.get('medical_condition'), data.get('hospital_name'),
                 float(data.get('latitude', 12.9716)), float(data.get('longitude', 77.5946)), user_id)
            )
        conn.commit()
        return jsonify({'status': 'success', 'message': 'Profile updated successfully!'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()

# Availability toggles
@app.route('/api/user/toggle-availability', methods=['POST'])
@app.route('/api/donors/toggle-availability', methods=['POST'])
@token_required
def toggle_availability(current_user):
    if current_user['role'] != 'donor':
        return jsonify({'status': 'error', 'message': 'Only donors can change their availability!'}), 403
    
    data = request.get_json() or {}
    status = int(data.get('is_available', 1))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE donors SET is_available = ? WHERE user_id = ?", (status, current_user['id']))
    conn.commit()
    conn.close()
    
    return jsonify({
        'status': 'success', 
        'message': f"Availability status successfully updated to {'Available' if status else 'Busy'}!"
    })

# ========================================================
# REST API ENDPOINTS - DONOR DISPATCH & MATCHING
# ========================================================

@app.route('/api/donors/search', methods=['POST'])
@token_required
def search_compatible_donors(current_user):
    """
    Evaluates compatible available donors near patient target coordinates.
    Expects JSON payload with: blood_group, latitude, longitude.
    """
    data = request.get_json() or {}
    bg = data.get('blood_group')
    lat = float(data.get('latitude', 12.9716))
    lon = float(data.get('longitude', 77.5946))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM donors")
    all_donors = cursor.fetchall()
    
    matches = []
    now = datetime.now()
    hour = now.hour
    day_of_week = now.weekday()
    
    for d in all_donors:
        # Distance calculation
        dist = haversine(lat, lon, d['latitude'], d['longitude'])
        
        # AI score calculation
        score = ai_models.calculate_donor_recommendation_score(
            donor_bg=d['blood_group'],
            patient_bg=bg,
            distance_km=dist,
            last_donation_date_str=d['last_donation_date'],
            average_speed_seconds=d['response_speed_history'],
            is_available=bool(d['is_available'])
        )
        
        if score > 0:
            # Predict availability probability
            cursor.execute("SELECT COUNT(*) FROM donation_history WHERE donor_id = ?", (d['id'],))
            total_donated = cursor.fetchone()[0]
            historic_rate = min(0.99, max(0.40, 0.4 + (total_donated * 0.05)))
            
            prob = ai_models.predict_donor_availability(
                distance_km=dist,
                hour=hour,
                day_of_week=day_of_week,
                avg_response_speed=d['response_speed_history'],
                is_available_toggle=d['is_available'],
                historic_response_rate=historic_rate
            )
            
            matches.append({
                'name': d['name'],
                'blood_group': d['blood_group'],
                'distance_km': round(dist, 2),
                'ai_suitability_score': score,
                'ai_response_probability': round(prob * 100, 1),
                'phone': d['phone'],
                'lat': d['latitude'],
                'lng': d['longitude']
            })
            
    # Sort matches by suitability score descending
    matches.sort(key=lambda x: x['ai_suitability_score'], reverse=True)
    conn.close()
    
    return jsonify(matches)

# ========================================================
# REST API ENDPOINTS - BLOOD REQUESTS
# ========================================================

@app.route('/api/requests', methods=['POST'])
@app.route('/api/requests/create', methods=['POST'])
@token_required
def create_blood_request(current_user):
    if current_user['role'] != 'patient':
        return jsonify({'status': 'error', 'message': 'Only patients can create blood requests!'}), 403
        
    data = request.get_json() or {}
    blood_group = data.get('blood_group')
    units_needed = int(data.get('units_needed', 1))
    hospital_name = data.get('hospital_name')
    details = data.get('details', '')
    
    # Read AI Priority indicators
    hemoglobin_level = float(data.get('hemoglobin_level', 9.5))
    active_bleeding = int(data.get('active_bleeding', 0))
    trauma_or_accident = int(data.get('trauma_or_accident', 0))
    surgery_scheduled = int(data.get('surgery_scheduled', 0))
    patient_age = int(data.get('patient_age', 35))
    
    lat = float(data.get('latitude', 12.9716))
    lon = float(data.get('longitude', 77.5946))
    
    # Run AI Classification Model for Priority
    priority = ai_models.predict_emergency_priority(
        hemoglobin_level=hemoglobin_level,
        active_bleeding=active_bleeding,
        trauma_or_accident=trauma_or_accident,
        surgery_scheduled=surgery_scheduled,
        patient_age=patient_age
    )
    
    # Log prediction details to database
    input_params = {
        'hemoglobin_level': hemoglobin_level,
        'active_bleeding': active_bleeding,
        'trauma_or_accident': trauma_or_accident,
        'surgery_scheduled': surgery_scheduled,
        'patient_age': patient_age
    }
    pred_res = {'priority': priority}
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO ai_predictions_log (model_type, input_parameters, prediction_result, confidence_score) VALUES (?, ?, ?, ?)",
        ('priority', json.dumps(input_params), json.dumps(pred_res), 0.92)
    )
    
    # Insert request
    cursor.execute(
        """INSERT INTO blood_requests (patient_id, blood_group, units_needed, hospital_name, latitude, longitude, priority, status, details) 
           VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending', ?)""",
        (current_user['id'], blood_group, units_needed, hospital_name, lat, lon, priority, details)
    )
    request_id = cursor.lastrowid
    
    # Trigger notifications
    cursor.execute("SELECT * FROM donors WHERE is_available = 1")
    donors = cursor.fetchall()
    count_alerted = 0
    for donor in donors:
        comp_score = ai_models.is_blood_compatible(donor['blood_group'], blood_group)
        if comp_score > 0:
            dist = haversine(lat, lon, donor['latitude'], donor['longitude'])
            if dist <= 15.0:
                cursor.execute(
                    "INSERT INTO notifications (user_id, title, message, type) VALUES (?, ?, ?, ?)",
                    (donor['user_id'], f"EMERGENCY: {priority} Blood Request Nearby!",
                     f"A patient needs {blood_group} blood urgently at {hospital_name} ({round(dist, 1)} km away). Your compatibility match is high.",
                     'emergency')
                )
                count_alerted += 1
                
    # Add confirmation notification to patient
    cursor.execute(
        "INSERT INTO notifications (user_id, title, message, type) VALUES (?, ?, ?, ?)",
        (current_user['id'], 'Emergency Blood Request Active',
         f'Your request for {blood_group} has been successfully broadcasted. AI classified priority is {priority}.',
         'success')
    )
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'status': 'success',
        'message': "Emergency blood request successfully registered on the LifeLink ledger!",
        'ai_priority': priority,
        'data': {
            'id': request_id,
            'priority': priority,
            'notified_donors_count': count_alerted
        }
    }), 201

@app.route('/api/requests', methods=['GET'])
def list_requests():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    patient_id = request.args.get('patient_id')
    if patient_id:
        cursor.execute("""
            SELECT br.*, p.name as patient_name, p.phone as patient_phone 
            FROM blood_requests br
            JOIN patients p ON br.patient_id = p.user_id
            WHERE br.patient_id = ? 
            ORDER BY br.id DESC
        """, (patient_id,))
    else:
        cursor.execute("""
            SELECT br.*, p.name as patient_name, p.phone as patient_phone 
            FROM blood_requests br
            JOIN patients p ON br.patient_id = p.user_id
            ORDER BY 
                CASE br.priority 
                    WHEN 'Critical' THEN 1
                    WHEN 'High' THEN 2
                    WHEN 'Medium' THEN 3
                    WHEN 'Low' THEN 4
                END, br.id DESC
        """)
        
    requests_list = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({'status': 'success', 'data': requests_list})

@app.route('/api/requests/my-requests', methods=['GET'])
@token_required
def get_my_requests(current_user):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM blood_requests 
        WHERE patient_id = ? 
        ORDER BY id DESC
    """, (current_user['id'],))
    requests_list = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    for r in requests_list:
        if isinstance(r['created_at'], str):
            r['created_at'] = r['created_at'].split('.')[0]
            
    return jsonify(requests_list)

@app.route('/api/requests/<int:req_id>/matches', methods=['GET'])
@token_required
def recommend_donors_for_request(current_user, req_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Fetch request details
    cursor.execute("SELECT * FROM blood_requests WHERE id = ?", (req_id,))
    req = cursor.fetchone()
    if not req:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Blood request not found!'}), 404
        
    req_bg = req['blood_group']
    req_lat = req['latitude']
    req_lon = req['longitude']
    
    # 2. Fetch all donors
    cursor.execute("SELECT * FROM donors")
    all_donors = cursor.fetchall()
    
    matches = []
    now = datetime.now()
    hour = now.hour
    day_of_week = now.weekday()
    
    for d in all_donors:
        # Distance calculation
        dist = haversine(req_lat, req_lon, d['latitude'], d['longitude'])
        
        # AI Smart Score calculation
        recommendation_score = ai_models.calculate_donor_recommendation_score(
            donor_bg=d['blood_group'],
            patient_bg=req_bg,
            distance_km=dist,
            last_donation_date_str=d['last_donation_date'],
            average_speed_seconds=d['response_speed_history'],
            is_available=bool(d['is_available'])
        )
        
        if recommendation_score > 0:
            # Predict availability
            cursor.execute("SELECT COUNT(*) FROM donation_history WHERE donor_id = ?", (d['id'],))
            total_donated = cursor.fetchone()[0]
            historic_rate = min(0.99, max(0.40, 0.4 + (total_donated * 0.05)))
            
            availability_prob = ai_models.predict_donor_availability(
                distance_km=dist,
                hour=hour,
                day_of_week=day_of_week,
                avg_response_speed=d['response_speed_history'],
                is_available_toggle=d['is_available'],
                historic_response_rate=historic_rate
            )
            
            donor_details = dict(d)
            donor_details['distance_km'] = round(dist, 2)
            donor_details['ai_match_score'] = recommendation_score
            donor_details['ai_availability_probability'] = round(availability_prob * 100, 1)
            
            cooldown_days_left = 0
            if d['last_donation_date']:
                last_d = datetime.strptime(d['last_donation_date'], '%Y-%m-%d')
                days_passed = (now - last_d).days
                if days_passed < 90:
                    cooldown_days_left = 90 - days_passed
                    
            donor_details['cooldown_days_left'] = cooldown_days_left
            donor_details['badges'] = json.loads(d['badges']) if d['badges'] else []
            
            matches.append(donor_details)
            
    # Sort matches by AI Score descending
    matches.sort(key=lambda x: x['ai_match_score'], reverse=True)
    
    conn.close()
    return jsonify({'status': 'success', 'data': matches})

# ========================================================
# REST API ENDPOINTS - DONOR HISTORY & COMPLETIONS
# ========================================================

@app.route('/api/donors/dashboard', methods=['GET'])
@token_required
def get_donor_dashboard(current_user):
    """Donor analytical metrics endpoint expected by the Jinja templates."""
    if current_user['role'] != 'donor':
        return jsonify({'status': 'error', 'message': 'Access denied!'}), 403
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM donors WHERE user_id = ?", (current_user['id'],))
    donor = cursor.fetchone()
    if not donor:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Donor profile not found!'}), 404
        
    donor_id = donor['id']
    
    # Calculate eligibility
    is_eligible = True
    days_left = 0
    if donor['last_donation_date']:
        last_d = datetime.strptime(donor['last_donation_date'], '%Y-%m-%d')
        days_passed = (datetime.now() - last_d).days
        if days_passed < 90:
            is_eligible = False
            days_left = 90 - days_passed
            
    # Fetch history
    cursor.execute("""
        SELECT dh.*, br.hospital_name, br.blood_group
        FROM donation_history dh
        LEFT JOIN blood_requests br ON dh.request_id = br.id
        WHERE dh.donor_id = ?
        ORDER BY dh.id DESC
    """, (donor_id,))
    history = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    # Map badges to template requirements: 'first_drop' -> 'newbie'
    badges = json.loads(donor['badges']) if donor['badges'] else []
    mapped_badges = []
    for b in badges:
        if b in ['first_drop', 'newbie']:
            mapped_badges.append('newbie')
        elif b == 'lifesaver':
            mapped_badges.append('lifesaver')
        elif b in ['veterandonor', 'champion', 'century_donor']:
            mapped_badges.append('champion')
            
    return jsonify({
        "profile": {
            "ai_score": donor['ai_donor_score'],
            "total_donations": donor['total_donations'],
            "avg_response_speed": donor['response_speed_history'],
            "badges": mapped_badges,
            "is_available": bool(donor['is_available'])
        },
        "eligibility": {
            "is_eligible": is_eligible,
            "days_left_cooldown": days_left
        },
        "history": history
    })

@app.route('/api/requests/<int:req_id>/donate', methods=['POST'])
@token_required
def accept_donation_request(current_user, req_id):
    if current_user['role'] != 'donor':
        return jsonify({'status': 'error', 'message': 'Only registered donors can fulfill request!'}), 403
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, name, total_donations, badges, response_speed_history FROM donors WHERE user_id = ?", (current_user['id'],))
    donor = cursor.fetchone()
    if not donor:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Donor profile not found!'}), 404
        
    donor_id = donor['id']
    donor_name = donor['name']
    
    cursor.execute("SELECT * FROM blood_requests WHERE id = ?", (req_id,))
    req = cursor.fetchone()
    if not req:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Blood request not found!'}), 404
        
    if req['status'] == 'Fulfilled':
        conn.close()
        return jsonify({'status': 'error', 'message': 'This request has already been completed!'}), 400
        
    # Mark request fulfilled
    cursor.execute("UPDATE blood_requests SET status = 'Fulfilled' WHERE id = ?", (req_id,))
    
    # Generate unique certificate code
    cert_code = f"LL-CERT-{random.randint(100000, 999999)}"
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    # Insert in donation history
    cursor.execute(
        """INSERT INTO donation_history (donor_id, request_id, units, donation_date, status, certificate_code)
           VALUES (?, ?, ?, ?, 'Completed', ?)""",
        (donor_id, req_id, req['units_needed'], today_str, cert_code)
    )
    
    new_total = donor['total_donations'] + 1
    
    # Gamification badges mapping
    badges_list = json.loads(donor['badges']) if donor['badges'] else []
    if new_total >= 1 and "newbie" not in badges_list:
        badges_list.append("newbie")
    if new_total >= 5 and "lifesaver" not in badges_list:
        badges_list.append("lifesaver")
    if new_total >= 10 and "champion" not in badges_list:
        badges_list.append("champion")
        
    new_speed = max(120, int(donor['response_speed_history'] * 0.9))
    new_ai_score = min(99.0, float(70.0 + (new_total * 3.0)))
    
    cursor.execute(
        """UPDATE donors 
           SET total_donations = ?, last_donation_date = ?, badges = ?, response_speed_history = ?, ai_donor_score = ?
           WHERE id = ?""",
        (new_total, today_str, json.dumps(badges_list), new_speed, new_ai_score, donor_id)
    )
    
    # Notifications
    cursor.execute(
        "INSERT INTO notifications (user_id, title, message, type) VALUES (?, ?, ?, ?)",
        (current_user['id'], 'Donation Completed! Certificate Generated',
         f'Thank you, {donor_name}! You successfully donated {req["units_needed"]} units. Download your official LifeLink certificate now.',
         'success')
    )
    
    cursor.execute(
        "INSERT INTO notifications (user_id, title, message, type) VALUES (?, ?, ?, ?)",
        (req['patient_id'], 'Emergency Request Fulfilled!',
         f'Wonderful news! Donor {donor_name} has accepted and completed your blood request.',
         'success')
    )
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'status': 'success',
        'message': 'Thank you! Blood request successfully fulfilled.',
        'data': {
            'certificate_code': cert_code,
            'badges': badges_list,
            'ai_score': new_ai_score
        }
    })

@app.route('/api/donor/history', methods=['GET'])
@token_required
def get_donor_history(current_user):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM donors WHERE user_id = ?", (current_user['id'],))
    donor = cursor.fetchone()
    if not donor:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Donor profile not found!'}), 404
        
    cursor.execute("""
        SELECT dh.*, br.hospital_name, br.blood_group, p.name as patient_name
        FROM donation_history dh
        LEFT JOIN blood_requests br ON dh.request_id = br.id
        LEFT JOIN patients p ON br.patient_id = p.user_id
        WHERE dh.donor_id = ?
        ORDER BY dh.id DESC
    """, (donor['id'],))
    
    history = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({'status': 'success', 'data': history})

@app.route('/api/donor/certificate/<string:code>', methods=['GET'])
def get_certificate_details(code):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT dh.*, d.name as donor_name, d.blood_group, br.hospital_name
        FROM donation_history dh
        JOIN donors d ON dh.donor_id = d.id
        LEFT JOIN blood_requests br ON dh.request_id = br.id
        WHERE dh.certificate_code = ?
    """, (code,))
    
    cert = cursor.fetchone()
    conn.close()
    
    if not cert:
        return jsonify({'status': 'error', 'message': 'Invalid certificate code!'}), 404
        
    return jsonify({'status': 'success', 'data': dict(cert)})

# ========================================================
# REST API ENDPOINTS - NOTIFICATIONS
# ========================================================

@app.route('/api/notifications', methods=['GET'])
@token_required
def get_notifications(current_user):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM notifications WHERE user_id = ? ORDER BY id DESC LIMIT 20",
        (current_user['id'],)
    )
    notifs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(notifs)

@app.route('/api/notifications/read', methods=['POST'])
@token_required
def mark_notifications_read(current_user):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (current_user['id'],))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success', 'message': 'Notifications marked as read!'})

# ========================================================
# REST API ENDPOINTS - ADMINISTRATOR & COMPLETIONS
# ========================================================

@app.route('/api/admin/analytics', methods=['GET'])
@token_required
def get_admin_analytics(current_user):
    if current_user['role'] != 'admin':
        return jsonify({'status': 'error', 'message': 'Access denied!'}), 403
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Broad counts
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM donors")
    total_donors = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM donors WHERE is_available = 1")
    available_donors = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM blood_requests")
    total_requests = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM blood_requests WHERE status = 'Fulfilled'")
    fulfilled_requests = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(units) FROM donation_history")
    total_units_donated = cursor.fetchone()[0] or 0
    
    # 2. Demand forecasts
    blood_groups = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
    demand_predictions = []
    
    for bg in blood_groups:
        cursor.execute("SELECT COUNT(*) FROM blood_requests WHERE blood_group = ?", (bg,))
        group_requests = cursor.fetchone()[0]
        
        rolling_avg = float(group_requests / 4.0 if group_requests > 0 else 1.0)
        active_warnings = 1 if bg in ['O-', 'A-'] else 0
        hospital_occupancy = 0.82
        
        pred_units = ai_models.predict_blood_demand(
            blood_group=bg,
            historical_rolling_average=rolling_avg,
            active_epidemic_warnings=active_warnings,
            local_hospital_occupancy=hospital_occupancy
        )
        
        cursor.execute("SELECT SUM(units_needed) FROM blood_requests WHERE blood_group = ? AND status != 'Fulfilled'", (bg,))
        requested = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM donors WHERE blood_group = ? AND is_available = 1", (bg,))
        available_supply = cursor.fetchone()[0]
        
        demand_predictions.append({
            'blood_group': bg,
            'current_supply_count': available_supply,
            'outstanding_requests_units': requested,
            'ai_forecasted_demand_units': pred_units,
            'shortage_status': 'Critical' if (pred_units > available_supply * 2 and bg in ['O-', 'A-', 'B-']) else ('Moderate' if pred_units > available_supply else 'Normal')
        })
        
    # 3. Fraud alerts
    cursor.execute("""
        SELECT patient_id, COUNT(*) as request_count, MAX(created_at) as last_time
        FROM blood_requests 
        GROUP BY patient_id, DATE(created_at)
        HAVING request_count > 2
    """)
    fraud_warnings = [dict(row) for row in cursor.fetchall()]
    
    # 4. Grids
    cursor.execute("""
        SELECT u.id, u.email, u.role, u.created_at, 
               COALESCE(d.name, p.name, 'Admin') as name,
               COALESCE(d.phone, p.phone, '-') as phone
        FROM users u
        LEFT JOIN donors d ON u.id = d.user_id
        LEFT JOIN patients p ON u.id = p.user_id
        ORDER BY u.id DESC
    """)
    users_list = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute("""
        SELECT br.*, p.name as patient_name 
        FROM blood_requests br
        JOIN patients p ON br.patient_id = p.user_id
        ORDER BY br.id DESC LIMIT 15
    """)
    recent_requests = [dict(row) for row in cursor.fetchall()]

    conn.close()
    
    return jsonify({
        'status': 'success',
        'data': {
            'statistics': {
                'total_users': total_users,
                'total_donors': total_donors,
                'available_donors': available_donors,
                'total_requests': total_requests,
                'fulfilled_requests': fulfilled_requests,
                'total_units_donated': total_units_donated
            },
            'blood_demand_forecasts': demand_predictions,
            'fraud_spam_alerts': {
                'warnings_count': len(fraud_warnings),
                'suspicious_accounts': fraud_warnings
            },
            'users_grid': users_list,
            'recent_requests_grid': recent_requests
        }
    })

@app.route('/api/admin/dashboard', methods=['GET'])
@token_required
def get_admin_dashboard(current_user):
    """Dashboard analytics expected by the Jinja admin panel."""
    if current_user['role'] != 'admin':
        return jsonify({'status': 'error', 'message': 'Access denied!'}), 403
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # stats
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM donors")
    total_donors = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(units) FROM donation_history")
    completed_donations = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT COUNT(*) FROM blood_requests WHERE status != 'Fulfilled'")
    active_requests = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM blood_requests WHERE priority = 'Critical' AND status != 'Fulfilled'")
    critical_requests = cursor.fetchone()[0]
    
    # demand forecasting
    blood_groups = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
    demand_forecast = {}
    
    for bg in blood_groups:
        cursor.execute("SELECT COUNT(*) FROM blood_requests WHERE blood_group = ?", (bg,))
        group_requests = cursor.fetchone()[0]
        
        rolling_avg = float(group_requests / 4.0 if group_requests > 0 else 1.0)
        active_warnings = 1 if bg in ['O-', 'A-'] else 0
        
        pred_units = ai_models.predict_blood_demand(
            blood_group=bg,
            historical_rolling_average=rolling_avg,
            active_epidemic_warnings=active_warnings,
            local_hospital_occupancy=0.82
        )
        
        demand_forecast[bg] = {
            "historical_count": group_requests,
            "forecasted_units_needed": int(pred_units)
        }
        
    # fraud alerts (overlapping within 2 hours)
    cursor.execute("""
        SELECT p.name, u.email, p.phone, COUNT(*) as request_count
        FROM blood_requests br
        JOIN patients p ON br.patient_id = p.user_id
        JOIN users u ON p.user_id = u.id
        WHERE br.created_at >= datetime('now', '-2 hours')
        GROUP BY br.patient_id
        HAVING request_count > 2
    """)
    fraud_alerts = [dict(row) for row in cursor.fetchall()]
    
    # active requests
    cursor.execute("""
        SELECT br.*, p.name as patient_name 
        FROM blood_requests br
        JOIN patients p ON br.patient_id = p.user_id
        WHERE br.status != 'Fulfilled'
        ORDER BY br.id DESC
    """)
    emergency_list = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return jsonify({
        "stats": {
            "total_users": total_users,
            "total_donors": total_donors,
            "completed_donations": completed_donations,
            "active_requests": active_requests,
            "critical_requests": critical_requests
        },
        "demand_forecast": demand_forecast,
        "fraud_alerts": fraud_alerts,
        "emergency_list": emergency_list
    })

@app.route('/api/donations/complete', methods=['POST'])
@token_required
def complete_donation_record(current_user):
    """Fulfills donation entry, increments donor scores and issues badge notifications."""
    if current_user['role'] != 'admin':
        return jsonify({'status': 'error', 'message': 'Access denied!'}), 403
        
    data = request.get_json() or {}
    donor_id = int(data.get('donor_id'))
    req_id = data.get('request_id')
    units = int(data.get('units', 1))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check donor existence
    cursor.execute("SELECT * FROM donors WHERE id = ?", (donor_id,))
    donor = cursor.fetchone()
    if not donor:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Donor ID not found!'}), 404
        
    # Mark request fulfilled
    if req_id:
        cursor.execute("UPDATE blood_requests SET status = 'Fulfilled' WHERE id = ?", (req_id,))
        
    # Generate certificate
    cert_code = f"LL-CERT-{random.randint(100000, 999999)}"
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    cursor.execute(
        """INSERT INTO donation_history (donor_id, request_id, units, donation_date, status, certificate_code)
           VALUES (?, ?, ?, ?, 'Completed', ?)""",
        (donor_id, req_id, units, today_str, cert_code)
    )
    
    # Update donor profile
    new_total = donor['total_donations'] + units
    
    badges_list = json.loads(donor['badges']) if donor['badges'] else []
    new_badge = None
    
    if new_total >= 1 and "newbie" not in badges_list:
        badges_list.append("newbie")
        new_badge = "First Drop Hero"
    if new_total >= 5 and "lifesaver" not in badges_list:
        badges_list.append("lifesaver")
        new_badge = "Noble Life Saver"
    if new_total >= 10 and "champion" not in badges_list:
        badges_list.append("champion")
        new_badge = "LifeLink Champion"
        
    new_speed = max(120, int(donor['response_speed_history'] * 0.95))
    new_ai_score = min(99.0, float(70.0 + (new_total * 3.0)))
    
    cursor.execute(
        """UPDATE donors 
           SET total_donations = ?, last_donation_date = ?, badges = ?, response_speed_history = ?, ai_donor_score = ?
           WHERE id = ?""",
        (new_total, today_str, json.dumps(badges_list), new_speed, new_ai_score, donor_id)
    )
    
    # Notification to donor
    cursor.execute(
        "INSERT INTO notifications (user_id, title, message, type) VALUES (?, ?, ?, ?)",
        (donor['user_id'], 'Blood Donation Completed!',
         f'Administrator logged your donation of {units} unit(s). Certificate code issued: {cert_code}. Thank you!',
         'success')
    )
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'status': 'success',
        'message': "Donation entry successfully recorded on the LifeLink ledger!",
        'certificate_code': cert_code,
        'badge_unlocked': new_badge
    }), 200

# ========================================================
# REST API ENDPOINTS - INTEL AI CHATBOTS
# ========================================================

def handle_chat_query(message):
    response_text = "I'm LifeLink AI, your blood connectivity assistant. How can I save a life today? You can ask me about: **Eligibility guidelines**, **Blood compatibility matches**, or **how to raise emergency requests**."
    
    if not message:
         return jsonify({'reply': response_text, 'tips': ["Are O- compatible with A+?", "Check donation eligibility"]})
         
    if "eligible" in message or "qualification" in message or "can i donate" in message:
        response_text = """
<b>🩸 Am I Eligible to Donate Blood?</b><br>
According to standard clinical regulations, here are the main eligibility benchmarks:<br>
1. <b>Age</b>: You must be between <b>18 and 65 years old</b>.<br>
2. <b>Weight</b>: Minimum weight of <b>50 kg (110 lbs)</b> is mandatory.<br>
3. <b>Health</b>: No active infections, chronic diseases, or fever in the last 48 hours.<br>
4. <b>Cooldown Time</b>: At least <b>90 days</b> must have passed since your last blood donation.<br>
5. <b>Travel/Medication</b>: No recent dental surgeries (24h) or high-risk travel.<br><br>
<i>LifeLink includes an eligibility counter directly in your Donor Dashboard to track your precise date!</i>
        """
    elif "compat" in message or "match" in message or "give to" in message or "receive" in message:
        response_text = """
<b>🔄 Blood Group Compatibility Quick Check</b><br>
Here is a breakdown of clinical transfusion compatibility rules:<br>
- <b>O Negative (O-)</b>: The <b>Universal Donor</b>. Can give to all groups, but can only receive from <b>O-</b>.<br>
- <b>AB Positive (AB+)</b>: The <b>Universal Recipient</b>. Can receive from all groups, but can only donate to <b>AB+</b>.<br>
- <b>O Positive (O+)</b>: Highly demanded! Can give to O+, A+, B+, AB+ (all positive types).<br>
- <b>A Positive (A+)</b>: Can give to A+, AB+; receives from A+, A-, O+, O-.<br><br>
<i>Type any comparison (e.g. 'Can O- give to B+') to see an instant match analysis!</i>
        """
    elif "cooldown" in message or "how often" in message or "days" in message:
        response_text = """
<b>⏳ Donation Frequency (Cooldown)</b><br>
To protect donor health and allow your body to fully replenish iron levels:<br>
- <b>Whole Blood</b>: A mandatory rest period of <b>90 days (3 months)</b> is required between donations.<br>
- <b>Platelets / Plasma</b>: Can be donated more frequently (every 14 days), but whole blood is the core focus of emergency LifeLink alerts.
        """
    elif "o-" in message and "a+" in message:
        response_text = "Yes! <b>O- is compatible with A+</b>. Since O- is the universal donor type, any patient with A+ blood can safely receive O- red blood cells."
    elif "request" in message or "emergency" in message or "raise" in message:
        response_text = """
<b>🚨 How to Create an Emergency Blood Request</b><br>
1. Log in as a <b>Patient</b> or <b>Hospital</b> profile.<br>
2. Navigate to your <b>Patient Dashboard</b>.<br>
3. Complete the <b>Emergency Request Form</b> with details: hospital location, blood group, units, and priority factors (hemoglobin, bleeding).<br>
4. LifeLink AI will classify the severity and broadcast notifications to all compatible donors in a <b>15km radius</b>.<br>
5. You can view matching donors ranked by suitability in real-time.
        """
    elif "badge" in message or "reward" in message or "score" in message:
        response_text = """
<b>🎖️ LifeLink Donor Rewards & Gamification</b><br>
We believe in honoring our everyday heroes! On your <b>Donor Dashboard</b>, you can track:<br>
- <b>AI Response Score</b>: Calculated based on your response times to nearby emergency alerts.<br>
- <b>Rewards Badges</b>: First Drop, Noble Life Saver, and LifeLink Champion.<br>
- <b>Downloadable Certificates</b>: Official printable certificates with unique codes are generated instantly for every verified donation.
        """
        
    return jsonify({'reply': response_text.strip()})

@app.route('/api/chatbot', methods=['POST'])
def chat_assistant():
    data = request.get_json() or {}
    message = data.get('message', '').lower().strip()
    
    # Stands as wrapper of handle_chat_query returning tips for the standalone dashboard chatbot
    res = handle_chat_query(message)
    res_data = res.get_json()
    
    quick_tips = ["Are O- compatible with A+?", "Check donation eligibility", "Create emergency request"]
    if "eligible" in message:
        quick_tips = ["How long is cooldown?", "Can I donate with diabetes?"]
    elif "compat" in message:
        quick_tips = ["Can O- give to A+?", "Compatible groups for AB-"]
        
    return jsonify({
        'response': res_data['reply'],
        'tips': quick_tips
    })

@app.route('/api/chat', methods=['POST'])
def chat_alias():
    data = request.get_json() or {}
    message = data.get('message', '').lower().strip()
    return handle_chat_query(message)

# ========================================================
# MAIN APPLICATION THREAD
# ========================================================

if __name__ == '__main__':
    # Verify database setup is initialized before running the REST API
    if not os.path.exists(DB_PATH):
        print("lifelink.db not found. Initializing database on startup...")
        from database import init_db
        init_db()
        
    print("LifeLink REST API Server running on http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
