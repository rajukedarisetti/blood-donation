import os
import sys
import unittest
import json
import sqlite3

# Set the path so we can import from backend
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from database import DB_PATH, get_db_connection
import ai_models

class LifeLinkTestSuite(unittest.TestCase):
    
    def setUp(self):
        app.config['TESTING'] = True
        app.config['DEBUG'] = False
        self.client = app.test_client()

    def test_01_environment_check(self):
        """Verify the execution mode (ML-Models vs Pure-Python Heuristics)."""
        print(f"\n[TEST] Verifying AI Execution Mode...")
        if ai_models.HAS_ML_LIBS:
            print("-> Running in standard MACHINE LEARNING Mode (scikit-learn active).")
            self.assertTrue(os.path.exists(ai_models.AVAILABILITY_PATH), "ML models have not been trained!")
        else:
            print("-> Running in HIGH-PERFORMANCE HEURISTIC fallback Mode (pure-python active).")
            self.assertFalse(ai_models.HAS_ML_LIBS)

    def test_02_database_seeded_properly(self):
        """Verify that SQLite tables exist and contain seeded donor/patient records."""
        print("\n[TEST] Verifying database seeding and tables...")
        self.assertTrue(os.path.exists(DB_PATH), "Database file not found!")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check users count
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        self.assertGreater(user_count, 0, "No users found in database!")

        # Check donors count
        cursor.execute("SELECT COUNT(*) FROM donors")
        donor_count = cursor.fetchone()[0]
        self.assertGreater(donor_count, 0, "No donors found in database!")
        
        # Check active requests
        cursor.execute("SELECT COUNT(*) FROM blood_requests")
        req_count = cursor.fetchone()[0]
        self.assertGreater(req_count, 0, "No blood requests found in database!")

        conn.close()
        print(f"-> Relational database tables validated. Found {user_count} users, {donor_count} donors, {req_count} requests.")

    def test_03_auth_apis(self):
        """Test User Registration and Login Flow (JWT generation)."""
        print("\n[TEST] Verifying JWT Authentication APIs...")
        
        # 1. Register a test donor
        email = f"test_donor_{int(sqlite3.connect(DB_PATH).cursor().execute('SELECT COUNT(*) FROM users').fetchone()[0])}@lifelink.com"
        reg_payload = {
            "email": email,
            "password": "password123",
            "role": "donor",
            "name": "Test Verified Donor",
            "phone": "+1-555-9999",
            "blood_group": "O-",
            "latitude": 12.9800,
            "longitude": 77.6000
        }
        
        response = self.client.post('/api/auth/register', 
                                    data=json.dumps(reg_payload),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertIn("successful", response.json['message'])

        # 2. Login to retrieve Token
        login_payload = {
            "email": email,
            "password": "password123"
        }
        response = self.client.post('/api/auth/login',
                                    data=json.dumps(login_payload),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.json)
        self.assertEqual(response.json['user']['role'], 'donor')
        print(f"-> JWT Auth validated successfully. Assigned token for {email}.")

    def test_04_ai_priority_classification(self):
        """Test patient request creation and AI Emergency Priority Classifier."""
        print("\n[TEST] Verifying AI Emergency Priority Classifier API...")
        
        # Login as patient Bruce Wayne
        login_payload = {
            "email": "bruce.wayne@waynecorp.com",
            "password": "password123"
        }
        login_resp = self.client.post('/api/auth/login',
                                      data=json.dumps(login_payload),
                                      content_type='application/json')
        patient_token = login_resp.json['token']

        # Create emergency request payload (simulating internal trauma patient)
        req_payload = {
            "blood_group": "O-",
            "units_needed": 3,
            "hospital_name": "St. Marys Hospital",
            "latitude": 12.9650,
            "longitude": 77.6050,
            "patient_age": 42,
            "hemoglobin_level": 5.8,       # Highly critical! Normal is >12
            "active_bleeding": 1,          # Active bleeding
            "trauma_or_accident": 1,       # Trauma incident
            "surgery_scheduled": 1,
            "details": "Trauma recovery surgery. Internal bleeding."
        }

        response = self.client.post('/api/requests',
                                    data=json.dumps(req_payload),
                                    headers={'Authorization': f'Bearer {patient_token}'},
                                    content_type='application/json')
        
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['data']['priority'], 'Critical', "AI failed to classify priority level correctly!")
        self.assertGreaterEqual(response.json['data']['notified_donors_count'], 1, "Alerts did not broadcast to O- donors nearby!")
        
        print(f"-> AI Priority Classification successfully verified. Outputs Level: '{response.json['data']['priority']}', dispatched to {response.json['data']['notified_donors_count']} matching donors.")

    def test_05_ai_donor_matching_search(self):
        """Test AI Blood Donor Matching and ranking algorithm."""
        print("\n[TEST] Verifying AI Donor Proximity & Suitability Matching API...")
        
        # Get patient token from before
        login_payload = {
            "email": "bruce.wayne@waynecorp.com",
            "password": "password123"
        }
        login_resp = self.client.post('/api/auth/login',
                                      data=json.dumps(login_payload),
                                      content_type='application/json')
        patient_token = login_resp.json['token']

        # Search matching donors for Request ID 1
        response = self.client.get('/api/requests/1/matches',
                                   headers={'Authorization': f'Bearer {patient_token}'})
        
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.json['data']), 0, "No compatible matches returned!")
        
        first_match = response.json['data'][0]
        self.assertEqual(first_match['blood_group'], 'A+', "Match returned incompatible blood group for request 1 (A+)!")
        self.assertGreater(first_match['ai_match_score'], 50.0, "AI suitability ranking score is failing calculations!")
        self.assertGreater(first_match['ai_availability_probability'], 0.0, "AI availability response probability is failing predictions!")

        print(f"-> AI Donor Matching search successfully verified. Best Match: '{first_match['name']}', Proximity: {first_match['distance_km']}km, Suitability: {first_match['ai_match_score']}/100, Response Prob: {first_match['ai_availability_probability']}%")

if __name__ == '__main__':
    unittest.main()
