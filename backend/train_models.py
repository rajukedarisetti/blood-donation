import os
import pickle
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.tree import DecisionTreeClassifier
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer

MODEL_DIR = os.path.dirname(__file__)

def train_donor_availability_model():
    """Trains a Logistic Regression to predict the probability of a donor accepting a request."""
    print("Training Donor Availability Model...")
    np.random.seed(42)
    n_samples = 1500

    # Synthesize Features
    distance_km = np.random.uniform(0.1, 15.0, n_samples)
    hour = np.random.randint(0, 24, n_samples)
    day_of_week = np.random.randint(0, 7, n_samples)
    avg_response_speed = np.random.uniform(60, 1800, n_samples) # average speed in seconds
    is_available_toggle = np.random.binomial(1, 0.8, n_samples) # 80% toggle available
    historic_response_rate = np.random.uniform(0.1, 1.0, n_samples)

    # Label generation based on a probability formula
    # High availability, low distance, fast response speed, day time (8am - 10pm) increases probability
    logits = (
        2.5 * is_available_toggle
        - 0.25 * distance_km
        + 1.5 * historic_response_rate
        - 0.0005 * avg_response_speed
        - 0.05 * np.abs(hour - 14) # peak availability around 2 PM (hour 14)
        - 0.2 # bias
    )
    prob = 1 / (1 + np.exp(-logits))
    accepted = np.random.binomial(1, prob)

    # Format into DataFrame
    df = pd.DataFrame({
        'distance_km': distance_km,
        'hour': hour,
        'day_of_week': day_of_week,
        'avg_response_speed': avg_response_speed,
        'is_available_toggle': is_available_toggle,
        'historic_response_rate': historic_response_rate
    })

    # Preprocessing
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df)

    # Model Training
    model = LogisticRegression(random_state=42)
    model.fit(X_scaled, accepted)

    # Save Model & Scaler
    model_data = {
        'model': model,
        'scaler': scaler
    }
    with open(os.path.join(MODEL_DIR, 'donor_availability_model.pkl'), 'wb') as f:
        pickle.dump(model_data, f)
    print("Donor Availability Model trained and saved.")

def train_blood_demand_forecaster():
    """Trains a Ridge Regressor to forecast the units of a blood group needed in the next week."""
    print("Training Blood Demand Forecaster...")
    np.random.seed(42)
    n_samples = 1200

    # Blood groups list
    blood_groups = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
    
    # Synthesize Features
    bg_choice = np.random.choice(blood_groups, n_samples)
    historical_rolling_average = np.random.uniform(2.0, 15.0, n_samples)
    seasonality_index = np.sin(np.random.uniform(0, 2 * np.pi, n_samples)) * 1.5 + 2.0 # seasonal demand variations
    active_epidemic_warnings = np.random.binomial(1, 0.15, n_samples) # 15% chance of epidemic alert
    local_hospital_occupancy = np.random.uniform(0.4, 0.95, n_samples)

    # Base demand formula: O+, A+ have higher baseline demand
    base_demand = np.zeros(n_samples)
    base_demand[bg_choice == 'O+'] = 12.0
    base_demand[bg_choice == 'A+'] = 9.0
    base_demand[bg_choice == 'B+'] = 8.0
    base_demand[bg_choice == 'O-'] = 7.0 # high critical emergency demand
    base_demand[base_demand == 0] = 4.0   # rare types have lower baseline demand

    demand = (
        base_demand 
        + 0.8 * historical_rolling_average 
        + 1.2 * seasonality_index 
        + 3.5 * active_epidemic_warnings 
        + 2.0 * local_hospital_occupancy 
        + np.random.normal(0, 1.5, n_samples)
    )
    demand = np.maximum(0, demand) # Demand cannot be negative

    df = pd.DataFrame({
        'blood_group': bg_choice,
        'historical_rolling_average': historical_rolling_average,
        'seasonality_index': seasonality_index,
        'active_epidemic_warnings': active_epidemic_warnings,
        'local_hospital_occupancy': local_hospital_occupancy
    })

    # Preprocessing pipelines for categories and numbers
    preprocessor = ColumnTransformer(
        transformers=[
            ('cat', OneHotEncoder(drop='first', sparse_output=False), ['blood_group']),
            ('num', StandardScaler(), ['historical_rolling_average', 'seasonality_index', 'local_hospital_occupancy'])
        ],
        remainder='passthrough' # active_epidemic_warnings is binary, no scaling needed
    )

    X_processed = preprocessor.fit_transform(df)

    # Model Training
    model = Ridge(alpha=1.0, random_state=42)
    model.fit(X_processed, demand)

    # Save Model & Preprocessor
    model_data = {
        'model': model,
        'preprocessor': preprocessor
    }
    with open(os.path.join(MODEL_DIR, 'blood_demand_model.pkl'), 'wb') as f:
        pickle.dump(model_data, f)
    print("Blood Demand Forecaster trained and saved.")

def train_emergency_priority_classifier():
    """Trains a Decision Tree Classifier to rank patient emergency requests into priority categories."""
    print("Training Emergency Priority Classifier...")
    np.random.seed(42)
    n_samples = 1000

    # Synthesize Features
    hemoglobin_level = np.random.uniform(4.0, 15.0, n_samples) # Normal is 12-16, critical is <7
    active_bleeding = np.random.binomial(1, 0.35, n_samples) # 35% are actively bleeding
    trauma_or_accident = np.random.binomial(1, 0.25, n_samples)
    surgery_scheduled = np.random.binomial(1, 0.45, n_samples)
    patient_age = np.random.randint(1, 95, n_samples)

    # Priority Label logic:
    # 0 = Low, 1 = Medium, 2 = High, 3 = Critical
    priority = np.zeros(n_samples, dtype=int)

    for i in range(n_samples):
        score = 0
        if hemoglobin_level[i] < 6.5:
            score += 4
        elif hemoglobin_level[i] < 8.5:
            score += 2
        elif hemoglobin_level[i] < 11.0:
            score += 1
            
        if active_bleeding[i] == 1:
            score += 3
        if trauma_or_accident[i] == 1:
            score += 2
        if surgery_scheduled[i] == 1:
            score += 1
            
        if patient_age[i] < 10 or patient_age[i] > 70:
            score += 1 # Vulnerable patient markup

        # Classify
        if score >= 6:
            priority[i] = 3 # Critical
        elif score >= 4:
            priority[i] = 2 # High
        elif score >= 2:
            priority[i] = 1 # Medium
        else:
            priority[i] = 0 # Low

    df = pd.DataFrame({
        'hemoglobin_level': hemoglobin_level,
        'active_bleeding': active_bleeding,
        'trauma_or_accident': trauma_or_accident,
        'surgery_scheduled': surgery_scheduled,
        'patient_age': patient_age
    })

    # Standard scaling is perfect for trees as well (maintains range, although not strictly necessary, good practice)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df)

    # Model Training
    model = DecisionTreeClassifier(max_depth=5, random_state=42)
    model.fit(X_scaled, priority)

    # Save Model & Scaler
    model_data = {
        'model': model,
        'scaler': scaler
    }
    with open(os.path.join(MODEL_DIR, 'emergency_priority_model.pkl'), 'wb') as f:
        pickle.dump(model_data, f)
    print("Emergency Priority Classifier trained and saved.")

def train_all():
    print("Starting all ML training jobs...")
    train_donor_availability_model()
    train_blood_demand_forecaster()
    train_emergency_priority_classifier()
    print("All models successfully trained!")

if __name__ == '__main__':
    train_all()
