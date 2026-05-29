from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import UserDevice
from app.schemas.auth import DeviceSpec, SessionMetadata


@dataclass
class DeviceCheckResult:
    is_known_device: bool
    is_similar_device: bool            # fuzzy match (e.g. Chrome auto-updated)
    is_trusted_device: bool
    similarity: float                  # 0.0–1.0
    days_since_first_seen: int | None
    device_id: int | None              # DB id of the matched (or just-created) UserDevice

    # ML features
    hardware_concurrency: int
    device_memory: float
    pixel_ratio: float
    is_touch: bool
    is_mobile: bool
    device_tier: str

    # headless / bot flags
    webdriver: bool
    chrome_headless: bool
    no_plugins: bool
    headless_score: float


def _device_tier(concurrency: int, memory: float | None) -> str:
    mem = memory or 0
    if concurrency >= 8 and mem >= 8:
        return "high"
    if concurrency >= 4 and mem >= 4:
        return "mid"
    return "low"


def _headless_score(session: SessionMetadata) -> float:
    return sum([
        0.5 if session.webdriver else 0.0,
        0.3 if session.chrome_headless else 0.0,
        0.2 if session.no_plugins else 0.0,
    ])


def _screen_str(d: DeviceSpec) -> str:
    return f"{d.screen_width}x{d.screen_height}"


def _components(d: DeviceSpec) -> dict:
    return {
        "user_agent": d.user_agent,
        "platform": d.platform,
        "screen": _screen_str(d),
        "canvas_hash": d.canvas_hash,
        "webgl_renderer": d.webgl_renderer,
        "hardware_concurrency": d.hardware_concurrency,
    }


def _similarity(spec: DeviceSpec, row: UserDevice) -> float:
    """Jaccard-like similarity across 6 stable components. Returns 0.0–1.0."""
    candidate = _components(spec)
    stored = {
        "user_agent": row.user_agent,
        "platform": row.platform,
        "screen": row.screen,
        "canvas_hash": row.canvas_hash,
        "webgl_renderer": row.webgl_renderer,
        "hardware_concurrency": row.hardware_concurrency,
    }
    matched = 0
    total = 0
    for key, candidate_val in candidate.items():
        stored_val = stored.get(key)
        if candidate_val is None and stored_val is None:
            continue
        total += 1
        if candidate_val == stored_val:
            matched += 1
    if total == 0:
        return 0.0
    return matched / total


def _is_trusted(row: UserDevice | None) -> bool:
    if row is None or row.trusted_until is None:
        return False
    return row.trusted_until > datetime.now(timezone.utc)


def _find_or_match_device(
    db: Session, user_id: int, spec: DeviceSpec,
) -> tuple[UserDevice | None, float, bool]:
    """Return (row, similarity, is_exact). Looks for exact fingerprint first,
    then falls back to component similarity across the user's other devices."""
    exact = db.execute(
        select(UserDevice).where(
            UserDevice.user_id == user_id,
            UserDevice.device_fingerprint == spec.device_fingerprint,
        )
    ).scalar_one_or_none()
    if exact is not None:
        return exact, 1.0, True

    rows = db.execute(
        select(UserDevice).where(UserDevice.user_id == user_id)
    ).scalars().all()

    best_row: UserDevice | None = None
    best_sim = 0.0
    for r in rows:
        sim = _similarity(spec, r)
        if sim > best_sim:
            best_sim, best_row = sim, r

    if best_row is not None and best_sim >= settings.DEVICE_SIMILARITY_THRESHOLD:
        return best_row, best_sim, False
    return None, best_sim, False


def check_device(
    user_id: int,
    device: DeviceSpec,
    session: SessionMetadata,
    db: Session,
    ip: str | None = None,
    city: str | None = None,
    country: str | None = None,
) -> DeviceCheckResult:
    """Looks up the device (exact or fuzzy), creates it if brand new,
    and updates last-seen context. Caller must commit the surrounding txn."""
    row, sim, is_exact = _find_or_match_device(db, user_id, device)

    is_known = row is not None
    is_similar = is_known and not is_exact
    days_since_first_seen: int | None = None
    now = datetime.now(timezone.utc)

    if row is None:
        row = UserDevice(
            user_id=user_id,
            device_fingerprint=device.device_fingerprint,
            user_agent=device.user_agent,
            platform=device.platform,
            screen=_screen_str(device),
            canvas_hash=device.canvas_hash,
            webgl_renderer=device.webgl_renderer,
            hardware_concurrency=device.hardware_concurrency,
            last_seen_at=now,
        )
        db.add(row)
        db.flush()
    else:
        days_since_first_seen = (now - row.first_seen_at).days
        # if fuzzy match, refresh the canonical fingerprint to the new one
        if is_similar:
            row.device_fingerprint = device.device_fingerprint
            row.canvas_hash = device.canvas_hash
            row.user_agent = device.user_agent
            row.webgl_renderer = device.webgl_renderer
        row.last_seen_at = now

    return DeviceCheckResult(
        is_known_device=is_known,
        is_similar_device=is_similar,
        is_trusted_device=_is_trusted(row) if is_known else False,
        similarity=round(sim, 3),
        days_since_first_seen=days_since_first_seen,
        device_id=row.id,
        hardware_concurrency=device.hardware_concurrency,
        device_memory=device.device_memory or 0.0,
        pixel_ratio=device.pixel_ratio,
        is_touch=device.is_touch,
        is_mobile=device.is_touch and device.pixel_ratio >= 2.0,
        device_tier=_device_tier(device.hardware_concurrency, device.device_memory),
        webdriver=session.webdriver,
        chrome_headless=session.chrome_headless,
        no_plugins=session.no_plugins,
        headless_score=_headless_score(session),
    )


def mark_device_trusted(db: Session, device_id: int) -> None:
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    row = db.get(UserDevice, device_id)
    if row is None:
        return
    row.trusted_until = now + timedelta(days=settings.TRUSTED_DEVICE_DAYS)
    db.flush()


def revoke_all_device_trust(db: Session, user_id: int) -> None:
    rows = db.execute(
        select(UserDevice).where(UserDevice.user_id == user_id)
    ).scalars().all()
    for r in rows:
        r.trusted_until = None
    db.flush()


def increment_device_login(db: Session, device_id: int) -> None:
    # No-op: total_logins column removed. Kept for call-site compatibility.
    return