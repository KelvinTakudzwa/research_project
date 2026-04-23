import os
import pickle
import numpy as np
import pandas as pd
import mysql.connector
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sklearn.ensemble import IsolationForest
from sklearn.metrics import mean_squared_error, mean_absolute_error

MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', 'models')

DB_HOST     = os.environ.get('DB_HOST',     'localhost')
DB_USER     = os.environ.get('DB_USER',     'root')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '0786682192@Tk')
DB_NAME     = os.environ.get('DB_NAME',     'solar_monitoring')

FEATURE_COLS = [
    'pv_voltage', 'pv_current', 'pv_power_watts', 'batt_voltage',
    'batt_voltage_ma_10', 'soc_percent', 'load_current', 'net_energy_flux',
    'irradiance_lux', 'current_to_lux_ratio',
    'temp_ambient', 'temp_probe', 'temp_delta'
]

# Path to the synthetic baseline CSV (packaged alongside this script in backend/)
CSV_BASELINE = os.path.join(os.path.dirname(__file__), '..', 'solar_data_365days.csv')


def retrain_isolation_forest():
    """
    HYBRID RETRAINING PIPELINE (Sim-to-Real Transfer):
    Combines validated real sensor readings (pred_label='Normal') from the live DB
    with synthetic baseline data from the 30-day simulation CSV.
    This ensures robustness against hardware noise AND concept drift,
    even when live Normal samples are insufficient for standalone training.
    """
    print("[Retrainer] Initiating Hybrid Isolation Forest retraining pipeline...")

    conn = None
    try:
        conn = mysql.connector.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME
        )

        # ── PART 1: Extract validated Normal readings from live DB ──
        # Use URL.create() so special chars in password (e.g. '@') are handled safely
        db_url = URL.create(
            drivername="mysql+mysqlconnector",
            username=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            database=DB_NAME
        )
        engine = create_engine(db_url)
        query = """
            SELECT
                t.pv_voltage, t.pv_current, t.batt_voltage, t.load_current,
                t.temp_ambient, t.temp_probe, t.irradiance_lux, t.pv_power_watts,
                t.net_energy_flux, t.soc_percent
            FROM telemetry_data t
            JOIN inference_results i ON t.telemetry_id = i.telemetry_id
            WHERE i.pred_label = 'Normal'
              AND t.timestamp_unix >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            ORDER BY t.timestamp_unix DESC
        """
        with engine.connect() as connection:
            df_live = pd.read_sql(query, connection)
        engine.dispose()

        print(f"[Retrainer] Live DB: {len(df_live)} validated Normal readings.")

        # ── PART 2: Load synthetic baseline (Sim-to-Real augmentation) ──
        df_sim = pd.DataFrame()
        if os.path.exists(CSV_BASELINE):
            df_csv = pd.read_csv(CSV_BASELINE)
            # Use only the clean Normal rows from simulation
            if 'label' in df_csv.columns:
                df_csv = df_csv[df_csv['label'] == 0]
            # Align columns to what the DB returns
            shared_cols = ['pv_voltage', 'pv_current', 'batt_voltage', 'load_current',
                           'temp_ambient', 'temp_probe', 'irradiance_lux', 'pv_power_watts',
                           'net_energy_flux', 'soc_percent']
            df_sim = df_csv[[c for c in shared_cols if c in df_csv.columns]].copy()
            print(f"[Retrainer] Synthetic CSV: {len(df_sim)} clean baseline rows.")
        else:
            print(f"[Retrainer] Warning: CSV not found at {CSV_BASELINE}. Using live data only.")

        # ── PART 3: Merge (real data takes priority, simulation fills the gap) ──
        df = pd.concat([df_live, df_sim], ignore_index=True)
        print(f"[Retrainer] Combined dataset: {len(df)} rows ({len(df_live)} real + {len(df_sim)} simulated).")

        if len(df) < 30:
            print(f"[Retrainer] Aborted: Combined dataset too small ({len(df)} rows).")
            return False

        # ── PART 4: Feature Engineering (must match train_models.py exactly) ──
        df['current_to_lux_ratio'] = (df['pv_current'] / (df['irradiance_lux'] + 1)) * 1000
        df['temp_delta']           = (df['temp_probe'] - df['temp_ambient']).round(2)
        df['batt_voltage_ma_10']   = df['batt_voltage'].rolling(window=10, min_periods=1).mean()

        X = df[FEATURE_COLS]

        # ── PART 5: Train on combined clean data (Novelty Detection) ──
        new_if = IsolationForest(contamination=0.015, random_state=42, n_jobs=-1)
        new_if.fit(X)

        # ── PART 6: Compute RMSE / MAE ──
        scores       = new_if.decision_function(X)
        target_score = np.zeros(len(scores))
        rmse = float(np.sqrt(mean_squared_error(target_score, scores)))
        mae  = float(mean_absolute_error(target_score, scores))
        print(f"[Retrainer] RMSE: {rmse:.4f} | MAE: {mae:.4f}")

        # ── PART 7: Save retrained model ──
        model_path = os.path.join(MODEL_DIR, "if_model.pkl")
        with open(model_path, 'wb') as f:
            pickle.dump(new_if, f)
        print("[Retrainer] Model saved (sklearn trained inside Docker container).")

        # ── PART 8: Log to calibration_log ──
        cursor = conn.cursor()
        cursor.execute("SELECT DATEDIFF(NOW(), MAX(retrain_timestamp)) FROM calibration_log")
        row = cursor.fetchone()
        days_elapsed = int(row[0]) if row[0] is not None else 0

        cursor.execute(
            """INSERT INTO calibration_log (retrain_timestamp, rmse_score, mae_score, days_elapsed)
               VALUES (%s, %s, %s, %s)""",
            (datetime.now(), rmse, mae, days_elapsed)
        )
        conn.commit()
        cursor.close()
        print(f"[Retrainer] calibration_log updated. Pipeline complete.")
        return True

    except Exception as e:
        print(f"[Retrainer] FATAL ERROR: {e}")
        return False
    finally:
        if conn and conn.is_connected():
            conn.close()


if __name__ == "__main__":
    retrain_isolation_forest()
