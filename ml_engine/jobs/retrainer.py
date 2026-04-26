import os
import joblib
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
DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
DB_NAME     = os.environ.get('DB_NAME',     'solar_monitoring')

# 15-feature normalized vector — must match FEATURE_COLS in main.py exactly
FEATURE_COLS = [
    'pv_voltage_norm', 'pv_current_norm', 'pv_power_norm',
    'battery_voltage_norm', 'battery_current_norm', 'battery_power_norm',
    'ac_power_norm', 'ac_current_norm', 'net_flux_norm', 'irradiance_norm',
    'soc_percent', 'ac_power_factor',
    'ambient_temp_c', 'battery_temp_c', 'temp_delta_c',
]

CSV_BASELINE = os.path.join(os.path.dirname(__file__), '..', 'solar_data_365days.csv')


def retrain_isolation_forest():
    """
    HYBRID RETRAINING PIPELINE (Sim-to-Real Transfer):
    Combines validated real sensor readings (pred_label='Normal') from the live DB
    with synthetic baseline data from the simulation CSV.
    Ensures robustness against hardware noise AND concept drift.
    """
    print("[Retrainer] Initiating Hybrid Isolation Forest retraining pipeline...")

    conn = None
    try:
        conn = mysql.connector.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME
        )

        # ── PART 1: Extract validated Normal readings from live DB ──────────
        # Look-back window in days — default 30, override via env for systems
        # where data accumulates slowly or timestamps are close to the boundary.
        lookback_days = int(os.environ.get('RETRAIN_LOOKBACK_DAYS', 30))

        db_url = URL.create(
            drivername="mysql+mysqlconnector",
            username=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            database=DB_NAME
        )
        engine = create_engine(db_url)

        # Pull the normalized columns that Node.js already computed
        query = f"""
            SELECT
                t.pv_voltage_v, t.pv_current_a, t.pv_power_w,
                t.battery_voltage_v, t.battery_current_a, t.battery_power_w,
                t.ac_power_w, t.ac_current_a,
                t.net_energy_flux_w, t.irradiance_wm2,
                t.soc_percent, t.ac_power_factor,
                t.ambient_temp_c, t.battery_temp_c, t.temp_delta_c
            FROM telemetry_data t
            JOIN inference_results i ON t.telemetry_id = i.telemetry_id
            WHERE i.pred_label = 'Normal'
              AND t.timestamp_utc >= DATE_SUB(NOW(), INTERVAL {lookback_days} DAY)
            ORDER BY t.timestamp_utc DESC
        """
        with engine.connect() as connection:
            df_live_raw = pd.read_sql(query, connection)
        engine.dispose()

        print(f"[Retrainer] Live DB: {len(df_live_raw)} validated Normal readings.")

        # ── PART 2: Normalize live DB readings using same BOUNDS logic ───────
        # _env() mirrors the guard in train_models.py: empty strings from Docker
        # Compose (e.g. MAX_PV_CURRENT_A=) are treated as missing and the
        # Ohm's Law fallback is used instead — exactly what systemBounds.js does.
        def _env(key, fallback):
            try:
                v = float(os.environ.get(key, ''))
                return v if v > 0 else fallback
            except (ValueError, TypeError):
                return fallback

        nominal_v   = _env('BATTERY_NOMINAL_VOLTAGE_V', 12.0)
        rated_pv_w  = _env('RATED_PV_WATTAGE_W',        200.0)
        rated_inv_w = _env('RATED_INVERTER_WATTAGE_W',  300.0)
        max_ac_v    = _env('MAX_AC_VOLTAGE_V',           240.0)
        max_irr     = _env('MAX_IRRADIANCE_WM2',         1000.0)

        pv_v_max   = _env('MAX_PV_VOLTAGE_V',    nominal_v * 1.15)
        pv_i_max   = _env('MAX_PV_CURRENT_A',    rated_pv_w / nominal_v)
        pv_p_max   = _env('MAX_PV_POWER_W',      rated_pv_w)
        batt_v_max = _env('MAX_BATTERY_VOLTAGE_V', nominal_v * 1.15)
        batt_i_max = _env('MAX_BATTERY_CURRENT_A', rated_pv_w / nominal_v)
        ac_p_max   = _env('MAX_AC_POWER_W',      rated_inv_w)
        ac_i_max   = _env('MAX_AC_CURRENT_A',    ac_p_max / max_ac_v)

        df_live = pd.DataFrame()
        if len(df_live_raw) > 0:
            df_live['pv_voltage_norm']      = df_live_raw['pv_voltage_v']      / pv_v_max
            df_live['pv_current_norm']      = df_live_raw['pv_current_a']      / pv_i_max
            df_live['pv_power_norm']        = df_live_raw['pv_power_w']        / pv_p_max
            df_live['battery_voltage_norm'] = df_live_raw['battery_voltage_v'] / batt_v_max
            df_live['battery_current_norm'] = df_live_raw['battery_current_a'] / batt_i_max
            df_live['battery_power_norm']   = df_live_raw['battery_power_w']   / pv_p_max
            df_live['ac_power_norm']        = df_live_raw['ac_power_w']        / ac_p_max
            df_live['ac_current_norm']      = df_live_raw['ac_current_a']      / ac_i_max
            df_live['net_flux_norm']        = df_live_raw['net_energy_flux_w'] / pv_p_max
            df_live['irradiance_norm']      = df_live_raw['irradiance_wm2']    / max_irr
            df_live['soc_percent']          = df_live_raw['soc_percent']
            df_live['ac_power_factor']      = df_live_raw['ac_power_factor']
            df_live['ambient_temp_c']       = df_live_raw['ambient_temp_c']
            df_live['battery_temp_c']       = df_live_raw['battery_temp_c']
            df_live['temp_delta_c']         = df_live_raw['temp_delta_c']

        # ── PART 3: Load synthetic baseline (Sim-to-Real augmentation) ───────
        df_sim = pd.DataFrame()
        if os.path.exists(CSV_BASELINE):
            df_csv = pd.read_csv(CSV_BASELINE)
            if 'label' in df_csv.columns:
                df_csv = df_csv[df_csv['label'] == 0]
            shared = [c for c in FEATURE_COLS if c in df_csv.columns]
            df_sim = df_csv[shared].copy()
            print(f"[Retrainer] Synthetic CSV: {len(df_sim)} clean baseline rows.")
        else:
            print(f"[Retrainer] Warning: CSV not found at {CSV_BASELINE}. Using live data only.")

        # ── PART 4: Merge ─────────────────────────────────────────────────────
        df = pd.concat([df_live, df_sim], ignore_index=True)
        print(f"[Retrainer] Combined: {len(df)} rows ({len(df_live)} real + {len(df_sim)} simulated).")

        if len(df) < 30:
            print(f"[Retrainer] Aborted: dataset too small ({len(df)} rows).")
            return False

        # Drop any rows where a FEATURE_COL is missing
        df = df[FEATURE_COLS].dropna()

        # ── PART 5: Train ─────────────────────────────────────────────────────
        new_if = IsolationForest(contamination=0.015, random_state=42, n_jobs=-1)
        new_if.fit(df[FEATURE_COLS])

        # ── PART 6: Metrics ───────────────────────────────────────────────────
        scores       = new_if.decision_function(df[FEATURE_COLS])
        target_score = np.zeros(len(scores))
        rmse = float(np.sqrt(mean_squared_error(target_score, scores)))
        mae  = float(mean_absolute_error(target_score, scores))
        print(f"[Retrainer] RMSE: {rmse:.4f} | MAE: {mae:.4f}")

        # ── PART 7: Save ──────────────────────────────────────────────────────
        model_path = os.path.join(MODEL_DIR, "if_model.pkl")
        joblib.dump(new_if, model_path)
        print("[Retrainer] Model saved.")

        # ── PART 8: Log ───────────────────────────────────────────────────────
        cursor = conn.cursor()
        cursor.execute("SELECT DATEDIFF(NOW(), MAX(retrain_timestamp)) FROM calibration_log")
        row = cursor.fetchone()
        days_elapsed = int(row[0]) if row[0] is not None else 0
        cursor.execute(
            "INSERT INTO calibration_log (retrain_timestamp, rmse_score, mae_score, days_elapsed) "
            "VALUES (%s, %s, %s, %s)",
            (datetime.now(), rmse, mae, days_elapsed)
        )
        conn.commit()
        cursor.close()
        print("[Retrainer] calibration_log updated. Pipeline complete.")
        return True

    except Exception as e:
        print(f"[Retrainer] FATAL ERROR: {e}")
        return False
    finally:
        if conn and conn.is_connected():
            conn.close()


if __name__ == "__main__":
    retrain_isolation_forest()
