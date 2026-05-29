from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.core.config import settings
from app.schemas.dto import VelocityResult, GeoResult
from app.detection.device import DeviceCheckResult
from app.detection.behavioral import BehavioralCheckResult


class RiskDecision(str, Enum):
    ALLOW = "allow"
    STEP_UP = "step_up"
    BLOCK = "block"


@dataclass
class RiskBreakdown:
    velocity: float
    geo: float
    device: float
    behavioral: float
    rule_based: float
    final: float
    decision: RiskDecision


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _velocity_risk(v: VelocityResult) -> float:
    return _clamp(max(v.user_risk, v.ip_risk, v.user_ip_risk))


def _device_risk(d: DeviceCheckResult) -> float:
    if d.is_trusted_device:
        risk = 0.0
    elif d.is_known_device:
        # similar (fuzzy) match — small bump, not a full "new device"
        risk = 0.15 if d.is_similar_device else 0.0
    else:
        risk = 0.5
    risk += d.headless_score * 0.5
    return _clamp(risk)


def _behavioral_risk(b: BehavioralCheckResult) -> float:
    # combine static bot score with per-user baseline anomaly
    return _clamp(max(b.bot_behavior_score, b.baseline_anomaly_score))


def _weighted(weights: dict[str, float], risks: dict[str, float]) -> float:
    total = sum(weights.values())
    if total <= 0:
        return 0.0
    return _clamp(sum(risks[k] * weights[k] for k in weights) / total)


def compute_rule_based_risk(
    velocity: VelocityResult,
    geo: GeoResult,
    device: DeviceCheckResult,
    behavioral: BehavioralCheckResult,
) -> tuple[float, dict[str, float]]:
    weights = {
        "velocity": settings.VELOCITY_WEIGHT,
        "geo": settings.GEO_WEIGHT,
        "device": settings.DEVICE_WEIGHT,
        "behavioral": settings.BEHAVIORAL_WEIGHT,
    }
    risks = {
        "velocity": _velocity_risk(velocity),
        "geo": _clamp(geo.risk),
        "device": _device_risk(device),
        "behavioral": _behavioral_risk(behavioral),
    }
    return _weighted(weights, risks), risks


def compute_final_risk(rule_based_risk: float, ml_risk: float | None = None) -> float:
    ml_score = _clamp(ml_risk or 0.0)
    weighted = (rule_based_risk * settings.RULE_BASE_WEIGHT) + (ml_score * settings.ML_WEIGHT)
    return _clamp(weighted)


def decide(final_risk: float, is_trusted_device: bool) -> RiskDecision:
    """Map final risk + trust into an action.

    Trusted devices skip MFA unless risk is extreme (TRUSTED_DEVICE_HARD_BLOCK).
    """
    if final_risk >= settings.RISK_BLOCK_MIN:
        return RiskDecision.BLOCK
    if is_trusted_device and final_risk < settings.TRUSTED_DEVICE_HARD_BLOCK:
        return RiskDecision.ALLOW
    if final_risk >= settings.RISK_ALLOW_MAX:
        return RiskDecision.STEP_UP
    return RiskDecision.ALLOW


def build_breakdown(
    velocity: VelocityResult,
    geo: GeoResult,
    device: DeviceCheckResult,
    behavioral: BehavioralCheckResult,
    ml_risk: float | None = None,
) -> RiskBreakdown:
    rule_based, risks = compute_rule_based_risk(velocity, geo, device, behavioral)
    final = compute_final_risk(rule_based, ml_risk)
    return RiskBreakdown(
        velocity=risks["velocity"],
        geo=risks["geo"],
        device=risks["device"],
        behavioral=risks["behavioral"],
        rule_based=round(rule_based, 4),
        final=round(final, 4),
        decision=decide(final, device.is_trusted_device),
    )
