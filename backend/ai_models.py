import os
import pickle
import math
import random
from datetime import datetime

# Optional imports for machine learning libraries
try:
    import numpy as np
    import pandas as pd
    HAS_ML_LIBS = True
except ImportError:
    HAS_ML_LIBS = False
    print("[LifeLink System warning] AI libraries (numpy, pandas, scikit-learn) not found.")
    print("[LifeLink System status] Booting in High-Performance Deterministic Heuristics Mode.")

MODEL_DIR = os.path.dirname(__file__)

# Paths to the pickle files
AVAILABILITY_PATH = os.path.join(MODEL_DIR, 'donor_availability_model.pkl')
DEMAND_PATH = os.path.join(MODEL_DIR, 'blood_demand_model.pkl')
PRIORITY_PATH = os.path.join(MODEL_DIR, 'emergency_priority_model.pkl')

# Global variables for models
_availability_data = None
_demand_data = None
_priority_data = None

def load_models():
    """Loads all machine learning models if libraries and pickles are available."""
    global _availability_data, _demand_data, _priority_data
    
    if not HAS_ML_LIBS:
        return
        
    if os.path.exists(AVAILABILITY_PATH) and _availability_data is None:
        try:
            with open(AVAILABILITY_PATH, 'rb') as f:
                _availability_data = pickle.load(f)
        except Exception as e:
            print(f"Error loading Availability model: {e}")

    if os.path.exists(DEMAND_PATH) and _demand_data is None:
        try:
            with open(DEMAND_PATH, 'rb') as f:
                _demand_data = pickle.load(f)
        except Exception as e:
            print(f"Error loading Demand model: {e}")

    if os.path.exists(PRIORITY_PATH) and _priority_data is None:
        try:
            with open(PRIORITY_PATH, 'rb') as f:
                _priority_data = pickle.load(f)
        except Exception as e:
            print(f"Error loading Priority model: {e}")

# Try to load models on startup
load_models()

# ========================================================
# 1. AI DONOR RECOMMENDATION (SMART RANKING)
# ========================================================

BLOOD_COMPATIBILITY = {
    'A+': ['A+', 'A-', 'O+', 'O-'],
    'A-': ['A-', 'O-'],
    'B+': ['B+', 'B-', 'O+', 'O-'],
    'B-': ['B-', 'O-'],
    'AB+': ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'],
    'AB-': ['A-', 'B-', 'AB-', 'O-'],
    'O+': ['O+', 'O-'],
    'O-': ['O-']
}

def is_blood_compatible(donor_bg, patient_bg):
    """Returns compatibility score (100 for exact match, 70 for compatible match, 0 for incompatible)"""
    if donor_bg == patient_bg:
        return 100
    if donor_bg in BLOOD_COMPATIBILITY.get(patient_bg, []):
        return 70
    return 0

def calculate_donor_recommendation_score(donor_bg, patient_bg, distance_km, last_donation_date_str, average_speed_seconds, is_available=True):
    """
    Ranks donor suitability on a 0-100 scale:
    - Compatibility (40%)
    - Proximity (30%)
    - Cooldown Check (10%)
    - Historic Response Speed (20%)
    """
    if not is_available:
        return 0.0

    # 1. Compatibility
    compat_score = is_blood_compatible(donor_bg, patient_bg)
    if compat_score == 0:
        return 0.0

    # 2. Distance Decay (Proximity)
    # Exponential decay using standard math.exp
    distance_score = 100.0 * math.exp(-0.1 * distance_km)

    # 3. Cooldown Check
    cooldown_score = 100.0
    if last_donation_date_str:
        try:
            last_date = datetime.strptime(last_donation_date_str, '%Y-%m-%d')
            days_since = (datetime.now() - last_date).days
            if days_since < 90:
                cooldown_score = 0.0
        except Exception:
            pass

    # 4. Response Speed Score
    speed_score = 100.0 * math.exp(-0.002 * average_speed_seconds)

    # Composite Score
    total_score = (
        0.4 * compat_score +
        0.3 * distance_score +
        0.1 * cooldown_score +
        0.2 * speed_score
    )
    
    if cooldown_score == 0:
        total_score = total_score * 0.1

    return round(float(total_score), 2)

# ========================================================
# 2. DONOR AVAILABILITY PREDICTION (LOGISTIC REGRESSION)
# ========================================================

def predict_donor_availability(distance_km, hour, day_of_week, avg_response_speed, is_available_toggle, historic_response_rate):
    """
    Predicts probability of a donor accepting a request (0.0 to 1.0)
    using trained Logistic Regression. Falls back to a deterministic heuristic if libraries/pickles missing.
    """
    load_models()
    if HAS_ML_LIBS and _availability_data is not None:
        try:
            model = _availability_data['model']
            scaler = _availability_data['scaler']
            
            features = pd.DataFrame([{
                'distance_km': distance_km,
                'hour': hour,
                'day_of_week': day_of_week,
                'avg_response_speed': avg_response_speed,
                'is_available_toggle': is_available_toggle,
                'historic_response_rate': historic_response_rate
            }])
            
            X_scaled = scaler.transform(features)
            prob = model.predict_proba(X_scaled)[0][1]
            return round(float(prob), 4)
        except Exception as e:
            pass

    # FALLBACK DETERMINISTIC HEURISTIC (Pure Python)
    if not is_available_toggle:
        return 0.02
    
    prob = 0.5
    prob -= (distance_km * 0.03)
    
    if hour < 7 or hour > 22:
        prob -= 0.25
        
    if avg_response_speed < 300:
        prob += 0.15
    elif avg_response_speed > 1200:
        prob -= 0.15
        
    prob += (historic_response_rate - 0.5) * 0.4
    prob = max(0.01, min(0.99, prob))
    return round(float(prob), 4)

# ========================================================
# 3. BLOOD DEMAND FORECASTING (RIDGE REGRESSION)
# ========================================================

def predict_blood_demand(blood_group, historical_rolling_average, active_epidemic_warnings=0, local_hospital_occupancy=0.75):
    """
    Predicts blood units demand for a given group using Ridge Regression.
    Falls back to deterministic formula if ML libraries/models unavailable.
    """
    load_models()
    current_month = datetime.now().month
    seasonality_index = math.sin((current_month - 1) * 2 * math.pi / 12) * 1.5 + 2.0
    
    if HAS_ML_LIBS and _demand_data is not None:
        try:
            model = _demand_data['model']
            preprocessor = _demand_data['preprocessor']
            
            features = pd.DataFrame([{
                'blood_group': blood_group,
                'historical_rolling_average': historical_rolling_average,
                'seasonality_index': seasonality_index,
                'active_epidemic_warnings': active_epidemic_warnings,
                'local_hospital_occupancy': local_hospital_occupancy
            }])
            
            X_processed = preprocessor.transform(features)
            predicted_demand = model.predict(X_processed)[0]
            return round(float(max(0, predicted_demand)), 1)
        except Exception as e:
            pass

    # FALLBACK DETERMINISTIC HEURISTIC (Pure Python)
    base_demand_map = {'O+': 10, 'A+': 8, 'B+': 7, 'O-': 6, 'A-': 4, 'B-': 3, 'AB+': 4, 'AB-': 2}
    base = base_demand_map.get(blood_group, 5)
    
    forecast = (
        base 
        + 0.7 * historical_rolling_average 
        + 1.0 * seasonality_index 
        + 3.0 * active_epidemic_warnings 
        + 1.5 * local_hospital_occupancy
    )
    return round(float(max(0.0, forecast)), 1)

# ========================================================
# 4. EMERGENCY PRIORITY CLASSIFICATION (DECISION TREE)
# ========================================================

PRIORITY_LABELS = {0: 'Low', 1: 'Medium', 2: 'High', 3: 'Critical'}

def predict_emergency_priority(hemoglobin_level, active_bleeding, trauma_or_accident, surgery_scheduled, patient_age):
    """
    Predicts priority of a request (Low, Medium, High, Critical)
    using trained Decision Tree. Falls back to deterministic heuristic if ML libraries/models unavailable.
    """
    load_models()
    if HAS_ML_LIBS and _priority_data is not None:
        try:
            model = _priority_data['model']
            scaler = _priority_data['scaler']
            
            features = pd.DataFrame([{
                'hemoglobin_level': hemoglobin_level,
                'active_bleeding': active_bleeding,
                'trauma_or_accident': trauma_or_accident,
                'surgery_scheduled': surgery_scheduled,
                'patient_age': patient_age
            }])
            
            X_scaled = scaler.transform(features)
            class_idx = model.predict(X_scaled)[0]
            return PRIORITY_LABELS.get(int(class_idx), 'Medium')
        except Exception as e:
            pass

    # FALLBACK DETERMINISTIC HEURISTIC (Pure Python)
    score = 0
    if hemoglobin_level < 6.5:
        score += 4
    elif hemoglobin_level < 8.5:
        score += 2
    elif hemoglobin_level < 11.0:
        score += 1
        
    if active_bleeding:
        score += 3
    if trauma_or_accident:
        score += 2
    if surgery_scheduled:
        score += 1
        
    if patient_age < 10 or patient_age > 70:
        score += 1

    if score >= 6:
        return 'Critical'
    elif score >= 4:
        return 'High'
    elif score >= 2:
        return 'Medium'
    return 'Low'
