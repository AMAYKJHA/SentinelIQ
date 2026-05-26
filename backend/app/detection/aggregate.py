from __future__ import annotations

from app.core.config import settings
from app.schemas.dto import VelocityResult, GeoResult
from app.detection.device import DeviceCheckResult
from app.detection.behavioral import BehavioralCheckResult


def _clamp(value: float, min_value: float = 0.0, max_value: float = 1.0) -> float:
	return max(min_value, min(max_value, value))


def _velocity_risk(velocity: VelocityResult) -> float:
	return _clamp(max(velocity.user_risk, velocity.ip_risk))


def _device_risk(device: DeviceCheckResult) -> float:
	risk = 0.0
	if not device.is_known_device:
		risk += 0.5
	risk += device.headless_score * 0.5
	return _clamp(risk)


def _behavioral_risk(behavioral: BehavioralCheckResult) -> float:
	return _clamp(behavioral.bot_behavior_score)


def _rule_weighted_average(weights: dict[str, float], risks: dict[str, float]) -> float:
	total_weight = sum(weights.values())
	if total_weight <= 0:
		return 0.0
	weighted_sum = sum(risks[key] * weights[key] for key in weights)
	return _clamp(weighted_sum / total_weight)


def compute_rule_based_risk(
	velocity: VelocityResult,
	geo: GeoResult,
	device: DeviceCheckResult,
	behavioral: BehavioralCheckResult,
) -> float:
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
	return _rule_weighted_average(weights, risks)


def compute_final_risk(rule_based_risk: float, ml_risk: float | None = None) -> float:
	ml_score = _clamp(ml_risk or 0.0)
	weighted = (rule_based_risk * settings.RULE_BASE_WEIGHT) + (ml_score * settings.ML_WEIGHT)
	return _clamp(weighted)
