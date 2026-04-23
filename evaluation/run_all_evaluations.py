import subprocess
import sys
import os
import io

# Force UTF-8 output on Windows so box-drawing characters render correctly.
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

"""
Chapter 4 Evaluation Suite — Master Runner
run_all_evaluations.py

Executes all evaluation scripts in the correct dependency order and
prints section headers that map directly to Chapter 4 sub-sections.

Usage:
    python evaluation/run_all_evaluations.py

Requirements:
    - Broker (Mosquitto) running for the Pipeline section.
      Start with:  docker-compose up -d mosquitto
    - ML models trained:  ml_engine/models/if_model.pkl  &  rf_model.pkl
"""

EVAL_DIR    = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(EVAL_DIR)

PYTHON = sys.executable

def run(script_path: str, section_label: str) -> bool:
    """Run a script and return True on success."""
    rel = os.path.relpath(script_path, PROJECT_DIR)
    print(f"\n{'─' * 60}")
    print(f"  >>  {section_label}")
    print(f"      Script: {rel}")
    print(f"{'─' * 60}")
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    result = subprocess.run([PYTHON, script_path], cwd=PROJECT_DIR, env=env)
    if result.returncode != 0:
        print(f"\n  [FAILED] {rel} exited with code {result.returncode}")
        return False
    return True


def main():
    print()
    print("+" + "=" * 58 + "+")
    print("|        Chapter 4 -- Full Evaluation Suite Runner          |")
    print("+" + "=" * 58 + "+")

    steps = [
        # -- Section 4.x.1 -- ML Dataset Generation ----------------------
        (
            os.path.join(EVAL_DIR, "ml", "generate_ml_dataset.py"),
            "Section 4.x.1 -- ML Dataset Generation (F1/F2/F3/F5)"
        ),
        # -- Section 4.x.2a -- ML Model Performance ----------------------
        (
            os.path.join(EVAL_DIR, "ml", "evaluate_ml_models.py"),
            "Section 4.x.2a -- ML Model Performance (IF + RF Metrics)"
        ),
        # -- Section 4.x.2b -- Baseline Comparison -----------------------
        (
            os.path.join(EVAL_DIR, "ml", "baseline_comparison.py"),
            "Section 4.x.2b -- Baseline Comparison (Nassar et al. vs. IF)"
        ),
        # -- Section 4.x.3 -- Pipeline Reliability (F4 MQTT QoS 1) -------
        (
            os.path.join(EVAL_DIR, "pipeline", "simulate_f4_outage.py"),
            "Section 4.x.3 -- F4 Outage Simulation (Live MQTT QoS 1 Test)"
        ),
        (
            os.path.join(EVAL_DIR, "pipeline", "evaluate_pipeline.py"),
            "Section 4.x.3 -- Pipeline Metrics (PDR, Latency, Jitter)"
        ),
    ]

    passed, failed = 0, 0
    for script_path, label in steps:
        ok = run(script_path, label)
        if ok:
            passed += 1
        else:
            failed += 1

    print()
    print("+" + "=" * 58 + "+")
    print(f"|  Evaluation Complete -- {passed} passed, {failed} failed" + " " * (34 - len(f"{passed} passed, {failed} failed")) + "|")
    print("+" + "=" * 58 + "+")
    print("|  Outputs:                                                |")
    print("|    evaluation/ml_test_dataset.csv                        |")
    print("|    evaluation/ml_results_table.csv                       |")
    print("|    evaluation/baseline_vs_ml_comparison.csv              |")
    print("|    evaluation/f4_outage_log.csv                          |")
    print("|    evaluation/pipeline_results_table.csv                 |")
    print("|    docs/images/confusion_matrix_ml.png                   |")
    print("|    docs/images/baseline_vs_ml_bar.png                    |")
    print("|    docs/images/f4_latency_profile.png                    |")
    print("+" + "=" * 58 + "+")
    print()

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
