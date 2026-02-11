import pandas as pd
import numpy as np
import pickle
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
import os

# Configuration
DATA_PATH = "solar_data_30days.csv"
MODEL_DIR = "backend/models"
IMG_DIR = "docs/images"

# Ensure directories exist
os.makedirs(IMG_DIR, exist_ok=True)

def load_models():
    try:
        with open(f"{MODEL_DIR}/rf_model.pkl", 'rb') as f:
            rf = pickle.load(f)
        with open(f"{MODEL_DIR}/if_model.pkl", 'rb') as f:
            iso = pickle.load(f)
        return rf, iso
    except Exception as e:
        print(f"Error loading models: {e}")
        return None, None

def evaluate():
    print("Loading Data and Models...")
    df = pd.read_csv(DATA_PATH)
    rf_model, if_model = load_models()
    
    if not rf_model:
        return

    # Prepare Featuers
    feature_cols = [
        'pv_voltage', 'pv_current', 'batt_voltage', 'load_current', 'temperature',
        'pv_power_watts', 'net_energy_flux', 'batt_voltage_ma_10', 'soc_percent'
    ]
    
    # Check for missing columns (in case data was generated without features)
    # The previous phases ensured these exist, but good to be safe.
    for col in feature_cols:
        if col not in df.columns:
            print(f"Missing column: {col}. Please re-run data generation.")
            return

    X = df[feature_cols]
    y_true = df['label']

    print(f"Evaluating on {len(df)} samples...")

    # 1. Random Forest Evaluation
    print("\n--- Random Forest (Battery Health) Results ---")
    y_pred_rf = rf_model.predict(X)
    
    acc = accuracy_score(y_true, y_pred_rf)
    print(f"Accuracy: {acc:.4f}")
    
    print("\nClassification Report:")
    report = classification_report(y_true, y_pred_rf)
    print(report)
    
    # Confusion Matrix Plot
    cm = confusion_matrix(y_true, y_pred_rf)
    plt.figure(figsize=(6, 5))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', cbar=False)
    plt.title('Confusion Matrix - Battery Health')
    plt.xlabel('Predicted')
    plt.ylabel('Actual')
    plt.savefig(f"{IMG_DIR}/confusion_matrix.png")
    print(f"Confusion Matrix saved to {IMG_DIR}/confusion_matrix.png")

    # 2. Isolation Forest Evaluation
    print("\n--- Isolation Forest (Anomaly Detection) Results ---")
    # IF returns -1 for anomaly, 1 for normal
    if_preds = if_model.predict(X)
    # Convert to 0 (Normal) and 1 (Anomaly) for easier comparison
    if_preds_binary = np.where(if_preds == 1, 0, 1)
    
    # We can't strictly calculate "Accuracy" against the same labels if IF detects *different*
    # kinds of anomalies, but we can check overlap.
    
    detected_anomalies = if_preds_binary.sum()
    print(f"Total Anomalies Detected by IF: {detected_anomalies}")
    print(f"Total Known Artifact Anomalies: {y_true.sum()}")
    
    # Overlap
    overlap = ((if_preds_binary == 1) & (y_true == 1)).sum()
    print(f"Overlap (True Positives against labeled faults): {overlap}")

if __name__ == "__main__":
    evaluate()
