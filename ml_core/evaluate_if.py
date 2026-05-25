"""
SentinelIQ — Isolation Forest Evaluation
=========================================
Evaluates the trained IF model against the test set.

Outputs
-------
  • Classification report (precision, recall, F1)
  • Confusion matrix                → eval_plots/01_confusion_matrix.png
  • ROC curve (IF only)             → eval_plots/02_roc_curve.png
  • Precision-Recall curve          → eval_plots/03_pr_curve.png
  • SHAP feature importance         → eval_plots/04_shap_importance.png
  • Tier distribution               → eval_plots/05_tier_distribution.png
  • Score distribution              → eval_plots/06_score_distribution.png

Run:
    python evaluate_if.py
"""

import json
import warnings
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    average_precision_score,
    classification_report,
    confusion_matrix,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)

warnings.filterwarnings("ignore")

# ─── Paths ─────────────────────────────────────────────────────────────────────

BASE_DIR  = Path(__file__).parent
DATA_PATH = BASE_DIR / "data" / "syn_auth_login_test.csv"
MODEL_DIR = BASE_DIR / "models"
PLOT_DIR  = MODEL_DIR / "eval_plots"
PLOT_DIR.mkdir(parents=True, exist_ok=True)

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

RISK_TIERS = {
    "ALLOW":        (0.00, 0.40),
    "MFA_STEP_UP":  (0.40, 0.70),
    "ACCOUNT_LOCK": (0.70, 0.90),
    "HARD_BLOCK":   (0.90, 1.01),
}

TIER_COLORS = {
    "ALLOW":        "#2ecc71",
    "MFA_STEP_UP":  "#f39c12",
    "ACCOUNT_LOCK": "#e67e22",
    "HARD_BLOCK":   "#e74c3c",
}

DARK = {
    "figure.facecolor": "#0f1117",
    "axes.facecolor":   "#1a1d27",
    "axes.edgecolor":   "#3a3d4d",
    "axes.labelcolor":  "#e0e0e0",
    "xtick.color":      "#b0b0b0",
    "ytick.color":      "#b0b0b0",
    "text.color":       "#e0e0e0",
    "grid.color":       "#2a2d3a",
    "grid.alpha":       0.5,
}
plt.rcParams.update(DARK)


# ─── Helpers ───────────────────────────────────────────────────────────────────

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ip_type_enc"] = df["ip_type"].str.lower().map(IP_TYPE_MAP).fillna(2).astype(int)
    df["is_foreign"]  = (df["country"].str.upper() != "NP").astype(int)
    for col in ["is_known_vpn","is_datacenter_ip","is_tor","is_new_device","impossible_travel"]:
        df[col] = df[col].astype(str).str.lower().map({"true":1,"false":0}).fillna(0).astype(int)
    df["suspicious_isp"] = (df["is_known_vpn"] | df["is_datacenter_ip"] | df["is_tor"]).astype(int)
    df["high_distance"]  = (df["distance_from_last_login_km"] > 500).astype(int)
    df["velocity_ratio"] = df["velocity_last_1hr"] / (df["velocity_last_24hr"] + 1)
    df["is_odd_hour"]    = ((df["hour_of_day"] < 5) | (df["hour_of_day"] >= 23)).astype(int)
    df["target"]         = (df["label"] == "anomaly").astype(int)
    return df


def assign_tier(score: float) -> str:
    for tier, (lo, hi) in RISK_TIERS.items():
        if lo <= score < hi:
            return tier
    return "HARD_BLOCK"


def savefig(name: str) -> None:
    path = PLOT_DIR / name
    plt.savefig(path, dpi=150, bbox_inches="tight",
                facecolor=plt.rcParams["figure.facecolor"])
    print(f"      Saved → {path}")
    plt.close()


# ─── Load ──────────────────────────────────────────────────────────────────────

def load_models():
    print("[1/7] Loading models …")
    iso       = joblib.load(MODEL_DIR / "iso_forest.pkl")
    explainer = joblib.load(MODEL_DIR / "shap_explainer.pkl")
    with open(MODEL_DIR / "model_meta.json") as fh:
        meta = json.load(fh)
    print(f"      IF AUC (meta): {meta['iso_auc']}  |  "
          f"Contamination: {meta['contamination']:.0%}")
    return iso, explainer, meta


# ─── Score ─────────────────────────────────────────────────────────────────────

def compute_scores(iso, meta, X: np.ndarray) -> np.ndarray:
    print("[2/7] Computing IF scores …")
    iso_min = meta["iso_score_min"]
    iso_max = meta["iso_score_max"]
    raw     = -iso.score_samples(X)
    normed  = np.clip((raw - iso_min) / (iso_max - iso_min + 1e-9), 0, 1)
    return normed


# ─── Metrics ───────────────────────────────────────────────────────────────────

def print_metrics(y: np.ndarray, scores: np.ndarray) -> float:
    print("[3/7] Computing metrics …")
    threshold = 0.5
    preds     = (scores >= threshold).astype(int)

    auc = roc_auc_score(y, scores)
    ap  = average_precision_score(y, scores)

    print(f"\n  {'Metric':<30} {'Value':>10}")
    print(f"  {'-'*42}")
    print(f"  {'AUC-ROC (Isolation Forest)':<30} {auc:>10.4f}")
    print(f"  {'Average Precision':<30} {ap:>10.4f}")
    print(f"\n  Classification Report (threshold = {threshold}):")
    print(classification_report(y, preds, target_names=["Normal","Anomaly"], digits=4))
    return auc


# ─── Confusion Matrix ──────────────────────────────────────────────────────────

def plot_confusion_matrix(y: np.ndarray, scores: np.ndarray) -> None:
    print("[4/7] Plotting confusion matrix …")
    preds = (scores >= 0.5).astype(int)
    cm    = confusion_matrix(y, preds)

    fig, ax = plt.subplots(figsize=(6, 5))
    ConfusionMatrixDisplay(cm, display_labels=["Normal","Anomaly"]).plot(
        ax=ax, colorbar=False, cmap="Blues"
    )
    ax.set_title("Confusion Matrix — Isolation Forest (threshold=0.5)", fontsize=12, pad=12)
    plt.tight_layout()
    savefig("01_confusion_matrix.png")


# ─── ROC Curve ─────────────────────────────────────────────────────────────────

def plot_roc_curve(y: np.ndarray, scores: np.ndarray) -> None:
    print("[5/7] Plotting ROC curve …")
    fpr, tpr, _ = roc_curve(y, scores)
    auc         = roc_auc_score(y, scores)

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(fpr, tpr, color="#9b59b6", lw=2.5,
            label=f"Isolation Forest  AUC={auc:.4f}")
    ax.plot([0,1], [0,1], "k--", alpha=0.4, label="Random baseline")
    ax.set_title("ROC Curve — Isolation Forest", fontsize=13, pad=12)
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    savefig("02_roc_curve.png")


# ─── PR Curve ──────────────────────────────────────────────────────────────────

def plot_pr_curve(y: np.ndarray, scores: np.ndarray) -> None:
    print("[6/7] Plotting Precision-Recall curve …")
    prec, rec, thresholds = precision_recall_curve(y, scores)
    ap = average_precision_score(y, scores)

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(rec, prec, color="#9b59b6", lw=2, label=f"IF  AP={ap:.4f}")
    ax.axhline(y.mean(), ls="--", color="#e74c3c", alpha=0.7,
               label=f"Baseline (prevalence={y.mean():.3f})")

    idx = np.argmin(np.abs(thresholds - 0.5))
    ax.scatter(rec[idx], prec[idx], color="#f39c12", zorder=5, s=80,
               label=f"@t=0.5  P={prec[idx]:.3f} R={rec[idx]:.3f}")

    ax.set_title("Precision-Recall Curve — Isolation Forest", fontsize=13, pad=12)
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    savefig("03_pr_curve.png")


# ─── SHAP ──────────────────────────────────────────────────────────────────────

def plot_shap_importance(explainer, X: np.ndarray, sample_size: int = 500) -> None:
    print("[7/7] Computing SHAP importances …")
    idx = np.random.RandomState(42).choice(len(X), size=min(sample_size,len(X)), replace=False)
    sv  = explainer.shap_values(X[idx])               # (n, n_features)

    mean_abs = np.abs(sv).mean(axis=0)
    order    = np.argsort(mean_abs)

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh(
        [FEATURES[i] for i in order], mean_abs[order],
        color="#9b59b6", edgecolor="#6c3483", linewidth=0.5,
    )
    ax.set_title(f"SHAP Feature Importance — IF (n={len(idx)} samples)", fontsize=13, pad=12)
    ax.set_xlabel("Mean |SHAP value|")
    ax.grid(True, axis="x", alpha=0.3)
    plt.tight_layout()
    savefig("04_shap_importance.png")


# ─── Tier Distribution ─────────────────────────────────────────────────────────

def plot_tier_distribution(df: pd.DataFrame, scores: np.ndarray) -> None:
    print("[+] Plotting tier distribution …")
    df        = df.copy()
    df["tier"]   = [assign_tier(s) for s in scores]
    df["score"]  = scores

    tier_order = ["ALLOW","MFA_STEP_UP","ACCOUNT_LOCK","HARD_BLOCK"]
    counts     = [int((df["tier"]==t).sum()) for t in tier_order]
    colors     = [TIER_COLORS[t] for t in tier_order]

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle("SentinelIQ (IF) — Tier Distribution", fontsize=14, y=1.01)

    ax = axes[0]
    bars = ax.bar(tier_order, counts, color=colors, edgecolor="#0f1117", linewidth=1.2)
    for bar, cnt in zip(bars, counts):
        ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+20,
                f"{cnt:,}", ha="center", va="bottom", fontsize=10)
    ax.set_title("Logins per Tier")
    ax.set_ylabel("Count")
    ax.grid(True, axis="y", alpha=0.3)

    ax2 = axes[1]
    rates = []
    for t in tier_order:
        sub = df[df["tier"]==t]
        rates.append(sub["target"].mean()*100 if len(sub) else 0)
    ax2.bar(tier_order, rates, color=colors, edgecolor="#0f1117", linewidth=1.2)
    for i, rate in enumerate(rates):
        ax2.text(i, rate+0.5, f"{rate:.1f}%", ha="center", va="bottom", fontsize=10)
    ax2.set_title("Anomaly Rate per Tier")
    ax2.set_ylabel("Anomaly %")
    ax2.grid(True, axis="y", alpha=0.3)

    plt.tight_layout()
    savefig("05_tier_distribution.png")


# ─── Score Distribution ────────────────────────────────────────────────────────

def plot_score_distribution(y: np.ndarray, scores: np.ndarray) -> None:
    print("[+] Plotting score distribution …")
    normal  = scores[y == 0]
    anomaly = scores[y == 1]

    fig, ax = plt.subplots(figsize=(9, 5))
    bins = np.linspace(0, 1, 50)
    ax.hist(normal,  bins=bins, color="#2ecc71", alpha=0.6, density=True,
            label=f"Normal  (n={len(normal):,})")
    ax.hist(anomaly, bins=bins, color="#e74c3c", alpha=0.7, density=True,
            label=f"Anomaly (n={len(anomaly):,})")

    for thresh, lbl in [(0.40,"MFA"), (0.70,"LOCK"), (0.90,"BLOCK")]:
        ax.axvline(thresh, color="#f39c12", ls="--", lw=1.2, alpha=0.8)
        ax.text(thresh+0.005, ax.get_ylim()[1]*0.93, lbl, fontsize=8, color="#f39c12")

    ax.set_title("IF Score Distribution: Normal vs Anomaly", fontsize=13, pad=12)
    ax.set_xlabel("IF Risk Score")
    ax.set_ylabel("Density")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    savefig("06_score_distribution.png")


# ─── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n" + "═" * 60)
    print("  SentinelIQ — Isolation Forest Evaluation")
    print("═" * 60 + "\n")

    iso, explainer, meta = load_models()

    df = pd.read_csv(DATA_PATH)
    df = engineer_features(df)
    X  = df[FEATURES].values.astype(np.float32)
    y  = df["target"].values

    scores = compute_scores(iso, meta, X)

    print_metrics(y, scores)
    plot_confusion_matrix(y, scores)
    plot_roc_curve(y, scores)
    plot_pr_curve(y, scores)
    plot_shap_importance(explainer, X)
    plot_tier_distribution(df, scores)
    plot_score_distribution(y, scores)

    print(f"\n✅  Evaluation complete! All plots → {PLOT_DIR}/\n")
    print("═" * 60 + "\n")


if __name__ == "__main__":
    main()
