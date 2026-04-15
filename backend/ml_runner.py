import os
import pickle
import numpy as np
import pandas as pd
import mysql.connector
from datetime import datetime
from sklearn.ensemble import IsolationForest
from sklearn.metrics import mean_squared_error, mean_absolute_error

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')

DB_HOST     = os.environ.get('DB_HOST',     'localhost')
DB_USER     = os.environ.get('DB_USER',     'root')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '0786682192@Tk')
DB_NAME     = os.environ.get('DB_NAME',     'solar_monitoring')

FEATURE_COLS = [
    'pv_voltage', 'pv_current', 'batt_voltage', 'load_current', 'temperature',
    'irradiance_lux', 'pv_power_watts', 'net_energy_flux', 'batt_voltage_ma_10',
    'soc_percent', 'current_to_lux_ratio'
]

def retrain_isolation_forest():
    """
    Extracts last 30 days of 'Normal' records from the normalized schema,
    retrains the Isolation Forest, and logs RMSE/MAE to calibration_log.
    Addresses Concept Drift (panel degradation) without cementing faults as normal.
    """
    print("[Retrainer] Initiating Isolation Forest automated retraining pipeline...")

    conn = None
    try:
        conn = mysql.connector.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME
        )

        # 1. Database Extraction — JOIN normalized tables, filter 'Normal' only
        query = """
            SELECT
                t.pv_voltage, t.pv_current, t.batt_voltage, t.load_current,
                t.temperature, t.irradiance_lux, t.pv_power_watts,
                t.net_energy_flux, t.soc_percent
            FROM telemetry_data t
            JOIN inference_results i ON t.telemetry_id = i.telemetry_id
            WHERE i.pred_label = 'Normal'
              AND t.timestamp_unix >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            ORDER BY t.timestamp_unix DESC
        """
        df = pd.read_sql(query, conn)

        # 2. Derive contextual feature (must match train_models.py formula exactly)
        df['current_to_lux_ratio'] = (df['pv_current'] / (df['irradiance_lux'] + 1)) * 1000
        df['batt_voltage_ma_10']   = df['batt_voltage'].rolling(window=10, min_periods=1).mean()

        # 3. Data Validation
        if len(df) < 100:
            print(f"[Retrainer] Aborted: Only {len(df)} healthy rows. Need >= 100.")
            if conn: conn.close()
            return False

        print(f"[Retrainer] Extracted {len(df)} healthy records. Training...")

        X = df[FEATURE_COLS]

        # 4. Train on Clean Data Only (Novelty Detection paradigm)
        new_if = IsolationForest(contamination='auto', random_state=42, n_jobs=-1)
        new_if.fit(X)

        # 5. Compute RMSE / MAE of anomaly scores vs expected 'Normal' baseline
        scores       = new_if.decision_function(X)
        target_score = np.zeros(len(scores))  # Perfect normal = score of 0
        rmse = float(np.sqrt(mean_squared_error(target_score, scores)))
        mae  = float(mean_absolute_error(target_score, scores))
        print(f"[Retrainer] RMSE: {rmse:.4f} | MAE: {mae:.4f}")

        # 6. Save retrained model to disk
        model_path = os.path.join(MODEL_DIR, "if_model.pkl")
        with open(model_path, 'wb') as f:
            pickle.dump(new_if, f)
        print("[Retrainer] Model saved to disk.")

        # 7. Log to calibration_log (closes the documentation loop for Chapter 4)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DATEDIFF(NOW(), MAX(retrain_timestamp)) FROM calibration_log"
        )
        row = cursor.fetchone()
        days_elapsed = row[0] if row[0] is not None else 0

        cursor.execute(
            """INSERT INTO calibration_log (retrain_timestamp, rmse_score, mae_score, days_elapsed)
               VALUES (%s, %s, %s, %s)""",
            (datetime.now(), rmse, mae, int(days_elapsed))
        )
        conn.commit()
        cursor.close()
        print(f"[Retrainer] calibration_log updated (days_elapsed={days_elapsed}).")

        return True

    except Exception as e:
        print(f"[Retrainer] FATAL ERROR: {e}")
        return False
    finally:
        if conn and conn.is_connected():
            conn.close()

if __name__ == "__main__":
    retrain_isolation_forest()
