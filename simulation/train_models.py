import pandas as pd
import numpy as np
import pickle
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
import os

# Configuration
DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ml_engine", "solar_data_30days.csv")
MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ml_engine", "models")
IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "images")

# Ensure directories exist
os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(IMG_DIR, exist_ok=True)

print("Loading data...")
df = pd.read_csv(DATA_PATH)

# Features to use for training
# We exclude 'timestamp' and 'label' from X
feature_cols = [
    'pv_voltage', 'pv_current', 'pv_power_watts', 'batt_voltage', 
    'batt_voltage_ma_10', 'soc_percent', 'load_current', 'net_energy_flux',
    'irradiance_lux', 'current_to_lux_ratio', 
    'temp_ambient', 'temp_probe', 'temp_delta'
]

# Check if columns exist
missing_cols = [c for c in feature_cols if c not in df.columns]
if missing_cols:
    print(f"Error: Missing columns {missing_cols}")
    print("Available columns:", df.columns.tolist())
    exit(1)

X = df[feature_cols]
y = df['label']

print(f"Data Shape: {X.shape}")
print(f"Anomaly Count: {y.sum()}")

# ==========================================
# 1. Random Forest (Supervised - Battery Health)
# ==========================================
print("\n--- Training Random Forest (Supervised) ---")
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

rf_model = RandomForestClassifier(n_estimators=100, random_state=42)
rf_model.fit(X_train, y_train)

# Evaluation
y_pred = rf_model.predict(X_test)
print("Classification Report:")
print(classification_report(y_test, y_pred))

# Feature Importance
importances = rf_model.feature_importances_
feature_imp_df = pd.DataFrame({'Feature': feature_cols, 'Importance': importances})
feature_imp_df = feature_imp_df.sort_values(by='Importance', ascending=False)

print("\nTop 5 Important Features:")
print(feature_imp_df.head(5))

# Plot Feature Importance
plt.figure(figsize=(10, 6))
sns.barplot(x='Importance', y='Feature', data=feature_imp_df, palette='viridis')
plt.title('Feature Importance (Random Forest)')
plt.tight_layout()
plt.savefig(f"{IMG_DIR}/feature_importance.png")
print(f"Feature importance plot saved to {IMG_DIR}/feature_importance.png")

# Save RF Model
with open(f"{MODEL_DIR}/rf_model.pkl", 'wb') as f:
    pickle.dump(rf_model, f)
print("Random Forest model saved.")

# ==========================================
# 2. Isolation Forest (Unsupervised - Anomaly Detection)
# ==========================================
print("\n--- Training Isolation Forest (Unsupervised - Novelty Detection) ---")
# ACADEMICALLY RIGOROUS: Train strictly on NORMAL data only.
# The model learns the mathematical shape of healthy solar curves.
# Any deviation from this shape (F1-F5) is flagged as an outlier.
# We never expose the model to fault examples during training.
X_normal = X_train[y_train == 0]
print(f"Training on {len(X_normal)} clean normal samples (label=0 only).")

if_model = IsolationForest(contamination=0.015, random_state=42, n_jobs=-1)
if_model.fit(X_normal)

# Test (IF returns -1 for anomaly, 1 for normal)
if_preds = if_model.predict(X_test)
# Convert binary y_test (0=Normal, 1=Anomaly) to IF format (1=Normal, -1=Anomaly)
y_test_if = np.where(y_test == 0, 1, -1)

# Accuracy check (just for our info)
correct = (if_preds == y_test_if).sum()
print(f"Isolation Forest Accuracy on Test Set: {correct/len(y_test):.4f}")

# Save IF Model
with open(f"{MODEL_DIR}/if_model.pkl", 'wb') as f:
    pickle.dump(if_model, f)
print("Isolation Forest model saved.")

print("\nPhase 3 Model Training Complete.")
