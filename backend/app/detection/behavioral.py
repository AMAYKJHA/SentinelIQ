"""
behavioral.py

Responsibilities:
    1. Score behavioral signals for obvious bot/stuffing patterns (fast, rule-based)
    2. Extract behavioral features for ML inference
"""

from dataclasses import dataclass
from app.schemas.auth import BehavioralSignals


@dataclass
class BehavioralCheckResult:
    is_likely_bot: bool
    is_likely_stuffing: bool

    form_time_ms: int
    password_pasted: bool
    username_pasted: bool
    both_pasted: bool
    avg_dwell_time_ms: float
    avg_flight_time_ms: float
    keystroke_variance: float
    typo_count: int
    mouse_linearity: float
    mouse_avg_speed: float
    used_tab_to_navigate: bool

    bot_behavior_score: float


# Tunable thresholds
_BOT_FORM_TIME_MS = 1500        # suspiciously fast form fill
_BOT_DWELL_MAX_MS = 20          # inhuman key hold speed
_BOT_VARIANCE_MAX = 2.0         # near-zero variance = uniform robot typing
_BOT_MOUSE_SPEED_MAX = 10.0     # pixels/ms — inhuman cursor speed
_BOT_MOUSE_LINEARITY_MIN = 0.95 # perfectly straight movement


def _bot_behavior_score(signals: BehavioralSignals) -> float:
    score = 0.0

    if signals.form_time_ms < _BOT_FORM_TIME_MS:
        score += 0.3

    if signals.avg_dwell_time_ms < _BOT_DWELL_MAX_MS:
        score += 0.2

    if signals.keystroke_variance < _BOT_VARIANCE_MAX:
        score += 0.2

    if signals.password_pasted and signals.username_pasted:
        score += 0.2

    if (
        signals.mouse_event_count > 0
        and signals.mouse_linearity > _BOT_MOUSE_LINEARITY_MIN
        and signals.mouse_avg_speed > _BOT_MOUSE_SPEED_MAX
    ):
        score += 0.1

    return min(score, 1.0)


def check_behavioral(signals: BehavioralSignals) -> BehavioralCheckResult:
    bot_score = _bot_behavior_score(signals)
    both_pasted = signals.password_pasted and signals.username_pasted

    return BehavioralCheckResult(
        is_likely_bot=bot_score >= 0.6,
        is_likely_stuffing=both_pasted,

        # ML features (pass through as-is)
        form_time_ms=signals.form_time_ms,
        password_pasted=signals.password_pasted,
        username_pasted=signals.username_pasted,
        both_pasted=both_pasted,
        avg_dwell_time_ms=signals.avg_dwell_time_ms,
        avg_flight_time_ms=signals.avg_flight_time_ms,
        keystroke_variance=signals.keystroke_variance,
        typo_count=signals.typo_count,
        mouse_linearity=signals.mouse_linearity,
        mouse_avg_speed=signals.mouse_avg_speed,
        used_tab_to_navigate=signals.used_tab_to_navigate,

        bot_behavior_score=bot_score,
    )