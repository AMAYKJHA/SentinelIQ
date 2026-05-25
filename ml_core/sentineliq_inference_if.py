"""
SentinelIQ — Isolation Forest Inference Engine
===============================================
Production inference module — pure Isolation Forest scoring.
No Random Forest, no labeled training data required.

Loads two artifacts from models/:
    iso_forest.pkl      — trained IsolationForest
    shap_explainer.pkl  — SHAP TreeExplainer (IF-based)
    model_meta.json     — score calibration metadata

Usage
-----
    from sentineliq_inference_if import SentinelIQ
    engine = SentinelIQ()
    result = engine.score(login_event_dict)
    print(result['tier'], result['score'])
"""

from __future__ import annotations

import json
import time
import warnings
from dataclasses import dataclass, asdict
from pathlib import Path

import joblib
import numpy as np

warnings.filterwarnings("ignore")

# ─── Constants ─────────────────────────────────────────────────────────────────

MODEL_DIR = Path(__file__).parent / "models"

RISK_TIERS = {
    "ALLOW":        (0.00, 0.40),
    "MFA_STEP_UP":  (0.40, 0.70),
    "ACCOUNT_LOCK": (0.70, 0.90),
    "HARD_BLOCK":   (0.90, 1.01),
}

TIER_ACTIONS = {
    "ALLOW":        "Grant access immediately — no extra friction.",
    "MFA_STEP_UP":  "Pause login, prompt OTP / TOTP before granting access.",
    "ACCOUNT_LOCK": "Freeze account, alert security team, require manual review.",
    "HARD_BLOCK":   "Reject immediately, freeze session, notify fraud ops.",
}

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

# Hard rules
VELOCITY_HARD_BLOCK_THRESHOLD = 10   # attempts / hour
IMPOSSIBLE_TRAVEL_SPEED_KMH   = 900  # km/h


# ─── Data Classes ──────────────────────────────────────────────────────────────

@dataclass
class LoginEvent:
    """Single login attempt — all fields the middleware must supply."""
    user_id:                     str
    ip_address:                  str
    timestamp_unix:              float
    hour_of_day:                 int          # 0–23
    day_of_week:                 int          # 0=Mon … 6=Sun
    ip_type:                     str          # residential|mobile|datacenter|vpn|tor
    country:                     str          # ISO-2, e.g. "NP"
    latitude:                    float
    longitude:                   float
    is_new_device:               bool
    is_known_vpn:                bool
    is_datacenter_ip:            bool
    is_tor:                      bool
    velocity_last_1hr:           int
    velocity_last_24hr:          int
    distance_from_last_login_km: float
    hours_since_last_login:      float
    hour_deviation:              int          # |hour - user_baseline_hour|


@dataclass
class ScoringResult:
    """Full output from SentinelIQ.score()."""
    user_id:        str
    score:          float          # IF risk score 0.0–1.0
    iso_score:      float          # raw normalised IF score (same as score)
    tier:           str
    action:         str
    rule_triggered: bool
    rule_reason:    str | None
    top_factors:    list[dict]     # SHAP-based explanation
    latency_ms:     float
    timestamp_unix: float

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


# ─── Engine ────────────────────────────────────────────────────────────────────

class SentinelIQ:
    """
    Pure Isolation Forest anomaly detection engine for eSewa login scoring.

    No labels required — the model learns what a "normal" Nepal login looks like
    and scores anything that deviates from that pattern.

    Example
    -------
        engine = SentinelIQ()

        event = LoginEvent(
            user_id="USR00121",
            ip_address="77.119.182.55",
            timestamp_unix=1_708_480_440.0,
            hour_of_day=2, day_of_week=2,
            ip_type="vpn", country="NL",
            latitude=50.8284, longitude=11.5518,
            is_new_device=True, is_known_vpn=True,
            is_datacenter_ip=False, is_tor=False,
            velocity_last_1hr=0, velocity_last_24hr=5,
            distance_from_last_login_km=6411.5,
            hours_since_last_login=18.8,
            hour_deviation=7,
        )
        result = engine.score(event)
        print(result.tier, result.score)
        # → HARD_BLOCK  0.94x
    """

    def __init__(self, model_dir: str | Path = MODEL_DIR) -> None:
        model_dir = Path(model_dir)

        self._iso       = joblib.load(model_dir / "iso_forest.pkl")
        self._explainer = joblib.load(model_dir / "shap_explainer.pkl")

        with open(model_dir / "model_meta.json") as fh:
            self._meta = json.load(fh)

        self._iso_min = self._meta["iso_score_min"]
        self._iso_max = self._meta["iso_score_max"]

        print(
            f"[SentinelIQ] Isolation Forest loaded — "
            f"AUC {self._meta['iso_auc']} | "
            f"Contamination {self._meta['contamination']:.0%}"
        )

    # ── Public API ─────────────────────────────────────────────────────────────

    def score(self, event: LoginEvent | dict) -> ScoringResult:
        """Score a single login attempt. Returns a ScoringResult."""
        t0 = time.perf_counter()

        if isinstance(event, dict):
            event = LoginEvent(**event)

        # 1. Hard rules (velocity burst, TOR, impossible travel)
        rule_triggered, rule_reason, forced_tier = self._hard_rules(event)

        # 2. Feature vector
        fv    = self._build_feature_vector(event)
        fv_2d = fv.reshape(1, -1)

        # 3. Isolation Forest score → normalise to [0, 1]
        iso_raw  = float(-self._iso.score_samples(fv_2d)[0])
        iso_norm = float(np.clip(
            (iso_raw - self._iso_min) / (self._iso_max - self._iso_min + 1e-9),
            0.0, 1.0,
        ))

        # 4. Tier
        tier = forced_tier if rule_triggered else self._assign_tier(iso_norm)

        # 5. SHAP explanation
        top_factors = self._explain(fv_2d)

        latency = (time.perf_counter() - t0) * 1000

        return ScoringResult(
            user_id        = event.user_id,
            score          = round(iso_norm, 4),
            iso_score      = round(iso_norm, 4),
            tier           = tier,
            action         = TIER_ACTIONS[tier],
            rule_triggered = rule_triggered,
            rule_reason    = rule_reason,
            top_factors    = top_factors,
            latency_ms     = round(latency, 2),
            timestamp_unix = event.timestamp_unix,
        )

    def score_batch(self, events: list[LoginEvent | dict]) -> list[ScoringResult]:
        """Score a list of login events — useful for batch testing."""
        return [self.score(e) for e in events]

    # ── Internal ───────────────────────────────────────────────────────────────

    def _build_feature_vector(self, e: LoginEvent) -> np.ndarray:
        ip_enc      = IP_TYPE_MAP.get(e.ip_type.lower(), 2)
        is_foreign  = int(e.country.upper() != "NP")
        is_vpn      = int(e.is_known_vpn)
        is_dc       = int(e.is_datacenter_ip)
        is_tor      = int(e.is_tor)
        susp_isp    = int(is_vpn or is_dc or is_tor)
        vel_ratio   = e.velocity_last_1hr / (e.velocity_last_24hr + 1)
        is_odd_hour = int(e.hour_of_day < 5 or e.hour_of_day >= 23)
        high_dist   = int(e.distance_from_last_login_km > 500)
        impossible  = int(self._is_impossible_travel(e))
        new_device  = int(e.is_new_device)

        return np.array([
            ip_enc, is_foreign, is_vpn, is_dc, is_tor, susp_isp,
            e.latitude, e.longitude,
            e.distance_from_last_login_km, impossible, high_dist,
            new_device,
            e.velocity_last_1hr, e.velocity_last_24hr, vel_ratio,
            e.hours_since_last_login, e.hour_of_day, e.day_of_week,
            e.hour_deviation, is_odd_hour,
        ], dtype=np.float32)

    def _is_impossible_travel(self, e: LoginEvent) -> bool:
        if e.hours_since_last_login <= 0:
            return False
        return (e.distance_from_last_login_km / e.hours_since_last_login) > IMPOSSIBLE_TRAVEL_SPEED_KMH

    def _hard_rules(self, e: LoginEvent) -> tuple[bool, str | None, str]:
        if e.is_tor:
            return True, "TOR exit node detected — hard block enforced.", "HARD_BLOCK"
        if e.velocity_last_1hr >= VELOCITY_HARD_BLOCK_THRESHOLD:
            return True, (
                f"Credential stuffing: {e.velocity_last_1hr} attempts in 1 h "
                f"(threshold {VELOCITY_HARD_BLOCK_THRESHOLD})."
            ), "HARD_BLOCK"
        if self._is_impossible_travel(e) and e.is_new_device:
            return True, (
                f"Impossible travel ({e.distance_from_last_login_km:.0f} km in "
                f"{e.hours_since_last_login:.1f} h) on unknown device."
            ), "ACCOUNT_LOCK"
        
        if e.is_known_vpn and (e.hour_of_day < 5 or e.hour_of_day >= 23) and e.country.upper() != "NP":
            return True, "VPN + foreign IP + odd hours — elevated block.", "HARD_BLOCK"
        return False, None, "ALLOW"

    def _assign_tier(self, score: float) -> str:
        for tier, (lo, hi) in RISK_TIERS.items():
            if lo <= score < hi:
                return tier
        return "HARD_BLOCK"

    def _explain(self, fv_2d: np.ndarray, top_n: int = 5) -> list[dict]:
        """
        SHAP values for IsolationForest: positive = pushes toward anomaly.
        """
        try:
            sv = self._explainer.shap_values(fv_2d)   # (1, n_features)
            sv_row = sv[0] if sv.ndim == 2 else sv

            ranked = sorted(
                zip(FEATURES, sv_row.tolist()),
                key=lambda x: abs(x[1]),
                reverse=True,
            )[:top_n]

            return [
                {
                    "feature":    feat,
                    "shap_value": round(val, 6),
                    "direction":  "↑ risk" if val > 0 else "↓ risk",
                }
                for feat, val in ranked
            ]
        except Exception:
            return []


# ─── CLI Demo ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    engine = SentinelIQ()

    # Test 1: Legitimate Kathmandu login
    normal_event = LoginEvent(
        user_id="USR00045", ip_address="27.206.59.153",
        timestamp_unix=1_712_668_320.0, hour_of_day=14, day_of_week=1,
        ip_type="residential", country="NP",
        latitude=27.7153, longitude=85.3201,
        is_new_device=False, is_known_vpn=False,
        is_datacenter_ip=False, is_tor=False,
        velocity_last_1hr=1, velocity_last_24hr=3,
        distance_from_last_login_km=14.42,
        hours_since_last_login=70.5, hour_deviation=2,
    )

    # Test 2: VPN from Netherlands at 2 AM
    vpn_event = LoginEvent(
        user_id="USR00121", ip_address="77.119.182.55",
        timestamp_unix=1_708_480_440.0, hour_of_day=2, day_of_week=2,
        ip_type="vpn", country="NL",
        latitude=50.8284, longitude=11.5518,
        is_new_device=True, is_known_vpn=True,
        is_datacenter_ip=False, is_tor=False,
        velocity_last_1hr=0, velocity_last_24hr=5,
        distance_from_last_login_km=6411.5,
        hours_since_last_login=18.8, hour_deviation=7,
    )

    # Test 3: Credential stuffing burst
    stuffing_event = LoginEvent(
        user_id="USR00999", ip_address="104.21.44.100",
        timestamp_unix=1_714_000_000.0, hour_of_day=3, day_of_week=0,
        ip_type="datacenter", country="US",
        latitude=37.751, longitude=-97.822,
        is_new_device=True, is_known_vpn=False,
        is_datacenter_ip=True, is_tor=False,
        velocity_last_1hr=15, velocity_last_24hr=30,
        distance_from_last_login_km=12500.0,
        hours_since_last_login=0.5, hour_deviation=14,
    )

    # Test 4: eSewa-specific — mobile login Pokhara to Kathmandu
    mobile_np_event = LoginEvent(
        user_id="USR00210", ip_address="202.70.89.12",
        timestamp_unix=1_715_000_000.0, hour_of_day=11, day_of_week=4,
        ip_type="mobile", country="NP",
        latitude=28.2096, longitude=83.9856,  # Pokhara
        is_new_device=False, is_known_vpn=False,
        is_datacenter_ip=False, is_tor=False,
        velocity_last_1hr=1, velocity_last_24hr=2,
        distance_from_last_login_km=198.0,
        hours_since_last_login=5.0, hour_deviation=1,
    )

    print("\n" + "═" * 62)
    for label, ev in [
        ("Normal Kathmandu Login",      normal_event),
        ("VPN — Netherlands 2AM",       vpn_event),
        ("Credential Stuffing",         stuffing_event),
        ("Normal Mobile (Pokhara→KTM)", mobile_np_event),
    ]:
        r = engine.score(ev)
        print(f"\n🔍 {label}")
        print(f"   Score: {r.score:.3f}  |  Tier: {r.tier}  |  Latency: {r.latency_ms} ms")
        print(f"   Action: {r.action}")
        if r.rule_triggered:
            print(f"   ⚠️  Rule: {r.rule_reason}")
        print(f"   Top factors: {[f['feature'] for f in r.top_factors[:3]]}")
    print("\n" + "═" * 62)
