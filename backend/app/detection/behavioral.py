"""
behavioral.py

Responsibilities:
    1. Score behavioral signals for obvious bot/stuffing patterns (rule-based)
    2. Compare this login's typing rhythm to the user's running baseline (z-score)
    3. Update the baseline after every successful login (EWMA)
"""

import math
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import UserBehaviorProfile
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

    # Baseline comparison (None until baseline is mature enough)
    has_baseline: bool = False
    dwell_zscore: float | None = None
    flight_zscore: float | None = None
    baseline_anomaly_score: float = 0.0


_BOT_FORM_TIME_MS = 1500
_BOT_DWELL_MAX_MS = 20
_BOT_VARIANCE_MAX = 2.0
_BOT_MOUSE_SPEED_MAX = 10.0
_BOT_MOUSE_LINEARITY_MIN = 0.95


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


def _zscore(value: float, mean: float | None, std: float | None) -> float | None:
    if mean is None or std is None or std <= 0:
        return None
    return (value - mean) / std


def check_behavioral(
    signals: BehavioralSignals,
    profile: UserBehaviorProfile | None = None,
) -> BehavioralCheckResult:
    bot_score = _bot_behavior_score(signals)
    both_pasted = signals.password_pasted and signals.username_pasted

    has_baseline = (
        profile is not None
        and (profile.total_logins or 0) >= settings.BEHAVIOR_MIN_LOGINS_FOR_BASELINE
    )

    dwell_z: float | None = None
    flight_z: float | None = None
    anomaly = 0.0

    if has_baseline:
        dwell_z = _zscore(signals.avg_dwell_time_ms, profile.avg_dwell_time_ms, profile.std_dwell_time_ms)
        flight_z = _zscore(signals.avg_flight_time_ms, profile.avg_flight_time_ms, profile.std_flight_time_ms)
        worst = max(abs(dwell_z or 0), abs(flight_z or 0))
        # 0 at z=0, 1.0 at z=BEHAVIOR_ZSCORE_FLAG
        anomaly = min(worst / settings.BEHAVIOR_ZSCORE_FLAG, 1.0)

    return BehavioralCheckResult(
        is_likely_bot=bot_score >= 0.6,
        is_likely_stuffing=both_pasted,
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
        has_baseline=has_baseline,
        dwell_zscore=dwell_z,
        flight_zscore=flight_z,
        baseline_anomaly_score=round(anomaly, 4),
    )


def _ewma(prev: float | None, new: float, alpha: float) -> float:
    if prev is None:
        return new
    return alpha * new + (1 - alpha) * prev


def _ewma_std(prev_std: float | None, prev_mean: float | None, new: float, alpha: float) -> float:
    """Exponentially-weighted running std deviation (rough but stable)."""
    if prev_std is None or prev_mean is None:
        return 0.0
    diff = new - prev_mean
    var = alpha * (diff * diff) + (1 - alpha) * (prev_std ** 2)
    return math.sqrt(var)


def update_baseline(
    db: Session,
    user_id: int,
    signals: BehavioralSignals,
    ip: str | None = None,
) -> None:
    """Call after a successful login to update the user's behavioral baseline."""
    alpha = settings.BEHAVIOR_EWMA_ALPHA
    profile = db.execute(
        select(UserBehaviorProfile).where(UserBehaviorProfile.user_id == user_id)
    ).scalar_one_or_none()

    if profile is None:
        profile = UserBehaviorProfile(
            user_id=user_id,
            avg_dwell_time_ms=signals.avg_dwell_time_ms,
            avg_flight_time_ms=signals.avg_flight_time_ms,
            std_dwell_time_ms=0.0,
            std_flight_time_ms=0.0,
            total_logins=1,
        )
        db.add(profile)
        db.flush()
        return

    new_std_dwell = _ewma_std(profile.std_dwell_time_ms, profile.avg_dwell_time_ms,
                              signals.avg_dwell_time_ms, alpha)
    new_std_flight = _ewma_std(profile.std_flight_time_ms, profile.avg_flight_time_ms,
                               signals.avg_flight_time_ms, alpha)
    profile.avg_dwell_time_ms = _ewma(profile.avg_dwell_time_ms, signals.avg_dwell_time_ms, alpha)
    profile.avg_flight_time_ms = _ewma(profile.avg_flight_time_ms, signals.avg_flight_time_ms, alpha)
    profile.std_dwell_time_ms = new_std_dwell
    profile.std_flight_time_ms = new_std_flight
    profile.total_logins = (profile.total_logins or 0) + 1
    db.flush()


def get_profile(db: Session, user_id: int) -> UserBehaviorProfile | None:
    return db.execute(
        select(UserBehaviorProfile).where(UserBehaviorProfile.user_id == user_id)
    ).scalar_one_or_none()