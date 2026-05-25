"""
SentinelIQ — Isolation Forest Training Pipeline
================================================
Trains and saves:
  1. Isolation Forest (unsupervised) → models/iso_forest.pkl
  2. SHAP TreeExplainer for IF       → models/shap_explainer.pkl
  3. Calibration metadata            → models/model_meta.json

No labels required for training — IF learns "normal" login patterns
from the data itself. Labels are only used for AUC evaluation.

Run:
    python train_if.py

Directory layout expected:
    data/
        syn_auth_login_fixed.csv    ← training set
    models/                         ← created automatically
"""

import json
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shap
from sklearn.ensemble import IsolationForest
from sklearn.metrics import roc_auc_score

warnings.filterwarnings("ignore")

# ─── Paths ─────────────────────────────────────────────────────────────────────

BASE_DIR  = Path(__file__).parent
DATA_PATH = BASE_DIR / "data" / "syn_auth_login_fixed.csv"
MODEL_DIR = BASE_DIR / "models"
MODEL_DIR.mkdir(exist_ok=True)

# ─── Config ────────────────────────────────────────────────────────────────────

IP_TYPE_MAP = {
    "residential": 0,
    "mobile":      1,
    "datacenter":  2,
    "vpn":         3,
    "tor":         4,
}

FEATURES = [
    "ip_type_enc", "is_foreign", "is_known_vpn", "is_datacenter_ip",
    "is_tor", "suspicious_isp", "latitude", "longitude",
    "distance_from_last_login_km", "impossible_travel", "high_distance",
    "is_new_device", "velocity_last_1hr", "velocity_last_24hr",
    "velocity_ratio", "hours_since_last_login", "hour_of_day",
    "day_of_week", "hour_deviation", "is_odd_hour",
]

ISO_PARAMS = dict(
    n_estimators  = 300,       # more trees → smoother scores
    contamination = 0.08,      # ~8% anomalies in training data
    max_samples   = "auto",    # 256 samples per tree by default
    max_features  = 1.0,       # use all features per tree
    bootstrap     = False,
    random_state  = 42,
    n_jobs        = -1,
)

RISK_TIERS = {
    "ALLOW":        (0.00, 0.40),
    "MFA_STEP_UP":  (0.40, 0.70),
    "ACCOUNT_LOCK": (0.70, 0.90),
    "HARD_BLOCK":   (0.90, 1.01),
}


# ─── 1. Load Data ──────────────────────────────────────────────────────────────

def load_data(path: Path) -> pd.DataFrame:
    print(f"[1/5] Loading data from {path} …")
    df = pd.read_csv(path)
    print(f"      Rows: {len(df):,}  |  "
          f"Anomaly rate: {(df['label']=='anomaly').mean():.2%}")
    return df


# ─── 2. Feature Engineering ────────────────────────────────────────────────────

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    print("[2/5] Engineering features …")
    df = df.copy()

    df["ip_type_enc"] = (
        df["ip_type"].str.lower().map(IP_TYPE_MAP).fillna(2).astype(int)
    )
    df["is_foreign"] = (df["country"].str.upper() != "NP").astype(int)

    bool_cols = [
        "is_known_vpn", "is_datacenter_ip", "is_tor",
        "is_new_device", "impossible_travel",
    ]
    for col in bool_cols:
        df[col] = (
            df[col].astype(str).str.lower()
            .map({"true": 1, "false": 0}).fillna(0).astype(int)
        )

    df["suspicious_isp"] = (
        df["is_known_vpn"] | df["is_datacenter_ip"] | df["is_tor"]
    ).astype(int)

    df["high_distance"]  = (df["distance_from_last_login_km"] > 500).astype(int)
    df["velocity_ratio"] = df["velocity_last_1hr"] / (df["velocity_last_24hr"] + 1)
    df["is_odd_hour"]    = (
        (df["hour_of_day"] < 5) | (df["hour_of_day"] >= 23)
    ).astype(int)

    df["target"] = (df["label"] == "anomaly").astype(int)

    print(f"      {len(FEATURES)} features ready.")
    return df


# ─── 3. Train Isolation Forest ─────────────────────────────────────────────────

def train_isolation_forest(
    X: np.ndarray, y: np.ndarray
) -> tuple[IsolationForest, float, float, float]:
    """
    Trains IF on the full dataset (unsupervised — no labels used during fit).
    Labels are only used afterward to compute AUC for benchmarking.
    """
    print("[3/5] Training Isolation Forest …")
    print(f"      Params: {ISO_PARAMS}")

    iso = IsolationForest(**ISO_PARAMS)
    iso.fit(X)          # ← unsupervised: y is NOT passed here

    # score_samples returns negative anomaly scores; negate so ↑ = more anomalous
    raw_scores = -iso.score_samples(X)
    iso_auc    = roc_auc_score(y, raw_scores)

    iso_min = float(raw_scores.min())
    iso_max = float(raw_scores.max())

    print(f"      AUC (vs labels): {iso_auc:.4f}")
    print(f"      Raw score range: [{iso_min:.4f}, {iso_max:.4f}]")

    # Contamination check: fraction predicted as anomaly
    predicted_anomaly = (iso.predict(X) == -1).mean()
    print(f"      Predicted anomaly fraction: {predicted_anomaly:.2%}  "
          f"(target ≈ {ISO_PARAMS['contamination']:.0%})")

    return iso, iso_auc, iso_min, iso_max


# ─── 4. SHAP Explainer ─────────────────────────────────────────────────────────

def build_shap_explainer(
    iso: IsolationForest, X: np.ndarray, sample_size: int = 500
) -> shap.TreeExplainer:
    """
    SHAP TreeExplainer works natively with sklearn IsolationForest.
    Output shape: (n_samples, n_features) — positive SHAP = pushes toward anomaly.
    """
    print("[4/5] Building SHAP TreeExplainer …")
    explainer = shap.TreeExplainer(iso)

    # Validate on a small sample
    idx = np.random.RandomState(42).choice(len(X), size=min(sample_size, len(X)), replace=False)
    sv  = explainer.shap_values(X[idx])
    print(f"      SHAP output shape: {sv.shape}  ✓")

    # Top-5 global feature importances from SHAP
    mean_abs = np.abs(sv).mean(axis=0)
    top5 = sorted(zip(FEATURES, mean_abs.tolist()), key=lambda x: x[1], reverse=True)[:5]
    print("      Top-5 SHAP features:")
    for feat, val in top5:
        print(f"        {feat:<35} {val:.5f}")

    return explainer


# ─── 5. Save Artifacts ─────────────────────────────────────────────────────────

def save_artifacts(
    iso:      IsolationForest,
    explainer: shap.TreeExplainer,
    iso_auc:  float,
    iso_min:  float,
    iso_max:  float,
    X:        np.ndarray,
    model_dir: Path,
) -> None:
    print("[5/5] Saving artifacts …")

    joblib.dump(iso,       model_dir / "iso_forest.pkl",     compress=3)
    joblib.dump(explainer, model_dir / "shap_explainer.pkl", compress=3)

    # Global feature importances from SHAP (full training set, sampled)
    idx       = np.random.RandomState(42).choice(len(X), size=min(1000, len(X)), replace=False)
    sv        = explainer.shap_values(X[idx])
    mean_abs  = np.abs(sv).mean(axis=0)
    top_feats = sorted(
        zip(FEATURES, mean_abs.tolist()), key=lambda x: x[1], reverse=True
    )

    meta = {
        "model":          "IsolationForest",
        "features":       FEATURES,
        "feature_count":  len(FEATURES),
        "iso_auc":        round(iso_auc, 4),
        "iso_score_min":  iso_min,
        "iso_score_max":  iso_max,
        "contamination":  ISO_PARAMS["contamination"],
        "n_estimators":   ISO_PARAMS["n_estimators"],
        "ip_type_map":    IP_TYPE_MAP,
        "risk_tiers": {
            k: list(v) for k, v in RISK_TIERS.items()
        },
        "top_features": [[f, round(v, 6)] for f, v in top_feats[:10]],
    }

    with open(model_dir / "model_meta.json", "w") as fh:
        json.dump(meta, fh, indent=2)

    print(f"\n      Artifacts saved → {model_dir}/")
    print(f"      {'File':<30} {'Size':>10}")
    print(f"      {'-'*42}")
    for p in sorted(model_dir.iterdir()):
        print(f"      {p.name:<30} {p.stat().st_size/1024:>8.1f} KB")


# ─── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n" + "═" * 60)
    print("  SentinelIQ — Isolation Forest Training Pipeline")
    print("═" * 60 + "\n")

    df        = load_data(DATA_PATH)
    df        = engineer_features(df)
    X         = df[FEATURES].values.astype(np.float32)
    y         = df["target"].values

    iso, iso_auc, iso_min, iso_max = train_isolation_forest(X, y)
    explainer = build_shap_explainer(iso, X)
    save_artifacts(iso, explainer, iso_auc, iso_min, iso_max, X, MODEL_DIR)

    print("\n✅  Training complete!")
    print("\n    Next steps:")
    print("    • python evaluate_if.py            ← full evaluation & plots")
    print("    • python sentineliq_inference_if.py ← live scoring demo")
    print("═" * 60 + "\n")


if __name__ == "__main__":
    main()
