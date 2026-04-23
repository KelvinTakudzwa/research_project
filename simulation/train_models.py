import pandas as pd
import numpy as np
import pickle
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.ensemble import RandomForestRegressor, IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error, mean_absolute_percentage_error, confusion_matrix
import os

# Configuration
DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ml_engine", "solar_data_365days.csv")
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
y = df['soh_percent']
y_clf = df['label']

print(f"Data Shape: {X.shape}")
print(f"Anomaly Count: {y_clf.sum()}")

# ==========================================
# 1. Random Forest (Supervised - Battery Health)
# ==========================================
print("\n--- Training Random Forest Regressor (Supervised) ---")
X_train, X_test, y_train, y_test, y_train_clf, y_test_clf = train_test_split(
    X, y, y_clf, test_size=0.2, random_state=42
)

rf_model = RandomForestRegressor(n_estimators=200, max_depth=15, min_samples_leaf=5, n_jobs=-1, random_state=42)
rf_model.fit(X_train, y_train)

# Evaluation
y_pred = rf_model.predict(X_test)
print("Regression Evaluation (Chapter 5 Metrics):")
mse = mean_squared_error(y_test, y_pred)
rmse = np.sqrt(mse)
mae = mean_absolute_error(y_test, y_pred)
mape = mean_absolute_percentage_error(y_test, y_pred)
r2 = r2_score(y_test, y_pred)

print(f"MSE:  {mse:.4f}")
print(f"RMSE: {rmse:.4f}")
print(f"MAE:  {mae:.4f}")
print(f"MAPE: {mape*100:.4f}%")
print(f"R2 Score: {r2:.4f}")

# Plot Actual vs Predicted SoH (Chapter 5 Result Graph)
plt.figure(figsize=(8, 8))
plt.scatter(y_test, y_pred, alpha=0.3, color='indigo')
plt.plot([y.min(), y.max()], [y.min(), y.max()], 'r--', lw=2, label='Perfect Prediction')
plt.title('Random Forest Regressor: Actual vs Predicted SoH')
plt.xlabel('Actual State of Health (%)')
plt.ylabel('Predicted State of Health (%)')
plt.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(f"{IMG_DIR}/soh_regression_scatter.png")
print(f"Regression Scatter Plot saved to {IMG_DIR}/soh_regression_scatter.png")

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

# Save the held-out test split so evaluation scripts use the identical
# 20% test set the model was validated against during training.
import pickle as _pkl
with open(f"{MODEL_DIR}/rf_test_split.pkl", 'wb') as f:
    _pkl.dump({'X_test': X_test, 'y_test': y_test}, f)
print("RF test split saved to rf_test_split.pkl (used by evaluate_ml_models.py).")

# ==========================================
# 2. Isolation Forest (Unsupervised - Anomaly Detection)
# ==========================================
print("\n--- Training Isolation Forest (Unsupervised - Novelty Detection) ---")
# ACADEMICALLY RIGOROUS: Train strictly on NORMAL data only.
# The model learns the mathematical shape of healthy solar curves.
# Any deviation from this shape (F1-F5) is flagged as an outlier.
# We never expose the model to fault examples during training.
X_normal = X_train[y_train_clf == 0]
print(f"Training on {len(X_normal)} clean normal samples (label=0 only).")

# Contamination = empirical anomaly rate from the dataset.
# Using the actual measured fault ratio gives the IF a calibrated prior,
# preventing the train/evaluation distribution mismatch that degrades F1-Score.
actual_contamination = round(float(y_train_clf.mean()), 4)
print(f"Empirical contamination rate: {actual_contamination:.4f} ({actual_contamination*100:.2f}% of training data is anomalous)")
if_model = IsolationForest(contamination=actual_contamination, random_state=42, n_jobs=-1)
if_model.fit(X_normal)

# Test (IF returns -1 for anomaly, 1 for normal)
if_preds = if_model.predict(X_test)
# Convert binary y_test (0=Normal, 1=Anomaly) to IF format (1=Normal, -1=Anomaly)
y_test_if = np.where(y_test_clf == 0, 1, -1)

# Accuracy check (just for our info)
correct = (if_preds == y_test_if).sum()
print(f"Isolation Forest Accuracy on Test Set: {correct/len(y_test):.4f}")

# Chapter 5: Confusion Matrix for Anomaly Detection
cm = confusion_matrix(y_test_if, if_preds, labels=[1, -1])
plt.figure(figsize=(6, 5))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
            xticklabels=['Normal', 'Anomaly'], 
            yticklabels=['Normal', 'Anomaly'])
plt.title('Isolation Forest Anomaly Detection Performance')
plt.ylabel('Actual Ground Truth')
plt.xlabel('Model Prediction')
plt.tight_layout()
plt.savefig(f"{IMG_DIR}/if_confusion_matrix.png")
print(f"Isolation Forest Confusion Matrix saved to {IMG_DIR}/if_confusion_matrix.png")

# Save IF Model
with open(f"{MODEL_DIR}/if_model.pkl", 'wb') as f:
    pickle.dump(if_model, f)
print("Isolation Forest model saved.")

print("\nPhase 3 Model Training Complete.")
