import os
import pickle
import pandas as pd
import mysql.connector
from sklearn.ensemble import IsolationForest

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')

# Avoid hardcoding DB credentials ideally, use ENV vars.
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_USER = os.environ.get('DB_USER', 'root')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '0786682192@Tk')
DB_NAME = os.environ.get('DB_NAME', 'solar_monitoring')

def retrain_isolation_forest():
    """
    Extracts the last 30 days of 'Normal' data from MySQL and retrains the Isolation Forest model.
    Addresses Concept Drift (e.g., panel degradation) without cementing Anomalies as baselines.
    """
    print("[Retrainer] Initiating Isolation Forest automated retraining pipeline...")
    
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        
        # 1. Database Extraction (Anomaly Filtered & 30-Day Window)
        query = """
            SELECT pv_voltage, pv_current, batt_voltage, load_current, temperature,
                   irradiance_lux, pv_power_watts, net_energy_flux, batt_voltage_ma_10, soc_percent 
            FROM solar_readings 
            WHERE pred_label = 'Normal' 
              AND timestamp >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            ORDER BY timestamp DESC
        """
        df = pd.read_sql(query, conn)
        conn.close()

        # 2. Data Validation
        if len(df) < 100:
            print(f"[Retrainer] Aborted: Insufficient healthy data ({len(df)} rows). Need at least 100.")
            return False

        print(f"[Retrainer] Successfully extracted {len(df)} healthy records. Training model...")

        # 3. Model Training (CPU Bound)
        # Assuming typical contamination rate is ~5%
        new_iso_forest = IsolationForest(
            n_estimators=100,
            contamination=0.05,
            random_state=42,
            n_jobs=-1 # Utilize all cores
        )
        new_iso_forest.fit(df)
        
        # 4. Save to Disk
        model_path = os.path.join(MODEL_DIR, "if_model.pkl")
        with open(model_path, 'wb') as f:
            pickle.dump(new_iso_forest, f)
            
        print("[Retrainer] Isolation Forest successfully retrained and saved to disk.")
        return True

    except Exception as e:
        print(f"[Retrainer] FATAL ERROR during retraining: {e}")
        return False

# Can be run as a standalone script for manual OS cron jobs
if __name__ == "__main__":
    retrain_isolation_forest()
