from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import UserDevice
from app.schemas.auth import DeviceSpec, SessionMetadata


@dataclass
class DeviceCheckResult:
    is_known_device: bool
    days_since_first_seen: int | None

    # ML features
    hardware_concurrency: int
    device_memory: float
    pixel_ratio: float
    is_touch: bool
    is_mobile: bool
    device_tier: str                   # "low" | "mid" | "high"

    # headless / bot flags (from session metadata)
    webdriver: bool
    chrome_headless: bool
    no_plugins: bool
    headless_score: float              # 0.0–1.0 composite


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


async def check_device(
    user_id: int,
    device: DeviceSpec,
    session: SessionMetadata,
    db: AsyncSession,
) -> DeviceCheckResult:

    result = db.execute(
        select(UserDevice).where(
            UserDevice.user_id == user_id,
            UserDevice.device_fingerprint == device.device_fingerprint,
        )
    )
    user_device = result.scalar_one_or_none()

    is_known = user_device is not None
    days_since_first_seen = None

    if user_device:
        from datetime import datetime, timezone
        delta = datetime.now(timezone.utc) - user_device.first_seen_at
        days_since_first_seen = delta.days
    else:
        new_device = UserDevice(
            user_id=user_id,
            device_fingerprint=device.device_fingerprint,
        )
        db.add(new_device)
        db.flush()   # get it persisted without committing the outer txn yet

    return DeviceCheckResult(
        is_known_device=is_known,
        days_since_first_seen=days_since_first_seen,
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