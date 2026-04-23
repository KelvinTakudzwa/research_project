import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

# 1. LOAD & ENHANCE DATA (Feature Engineering)
# Note: Ensure 'solar_data_365days.csv' exists.
# The previous step generated this file with slightly different column names for derived features.
# You may need to map them:
# pv_power_watts -> power_watts
# net_energy_flux -> net_current
# batt_voltage_ma_10 -> batt_v_smooth

df = pd.read_csv("solar_data_365days.csv")

# Checks if columns exist, if not, create them (fallback if running on raw data)
if 'pv_power_watts' in df.columns:
    df['power_watts'] = df['pv_power_watts']
else:
    df['power_watts'] = df['pv_voltage'] * df['pv_current']

if 'net_energy_flux' in df.columns:
    df['net_current'] = df['net_energy_flux']
else:
    df['net_current'] = df['pv_current'] - df['load_current']

if 'batt_voltage_ma_10' in df.columns:
    df['batt_v_smooth'] = df['batt_voltage_ma_10']
else:
    df['batt_v_smooth'] = df['batt_voltage'].rolling(window=10).mean().fillna(df['batt_voltage'])


# 2. PREPARE FOR ML
features = ['pv_voltage', 'pv_current', 'batt_voltage', 'load_current', 'temperature', 'power_watts', 'net_current']
X = df[features]
y = df['label']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# 3. TRAIN CLASSIFIER (Random Forest for Explainability)
model = RandomForestClassifier(n_estimators=100)
model.fit(X_train, y_train)

# 4. FEATURE IMPORTANCE (The "Distinction" Chart)
importances = model.feature_importances_
feature_importance_df = pd.DataFrame({'Feature': features, 'Importance': importances}).sort_values(by='Importance', ascending=False)

print("--- FEATURE IMPORTANCE ANALYSIS ---")
print(feature_importance_df)

# Plotting for your Dissertation
plt.figure(figsize=(10, 6))
plt.barh(feature_importance_df['Feature'], feature_importance_df['Importance'], color='skyblue')
plt.xlabel('Importance Score')
plt.title('Which Sensors Trigger Faults? (Feature Importance)')
plt.savefig('feature_importance.png')
print("Plot saved as feature_importance.png")
