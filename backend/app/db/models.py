import uuid as uuid_lib
from datetime import datetime
import enum

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import (
    Boolean, Integer, String, Float, DateTime, ForeignKey,
    func, UniqueConstraint, UUID, Enum, Index, text
)
from sqlalchemy.dialects.postgresql import JSONB, INET


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ── Enums ────────────────────────────────────────────

class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"

class LoginOutcome(str, enum.Enum):
    success = "success"
    failed_credentials = "failed_credentials"
    blocked_risk = "blocked_risk"
    mfa_required = "mfa_required"

# ── Tables ───────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uuid: Mapped[uuid_lib.UUID] = mapped_column(UUID(as_uuid=True), default=uuid_lib.uuid4, unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), server_default="user")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_login_count: Mapped[int] = mapped_column(Integer, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    behavior_profile: Mapped["UserBehaviorProfile"] = relationship(back_populates="user")


class UserDevice(Base):
    __tablename__ = "user_devices"
    __table_args__ = (
        UniqueConstraint("user_id", "device_fingerprint", name="uq_user_device"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    device_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_logins: Mapped[int] = mapped_column(Integer, server_default=text("0"))



class UserBehaviorProfile(Base):
    __tablename__ = "user_behavior_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, unique=True, index=True
    )

    avg_dwell_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_flight_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    keystroke_variance: Mapped[float | None] = mapped_column(Float, nullable=True)
    typical_hour_histogram: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    total_logins: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    last_known_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)

    user: Mapped["User"] = relationship(back_populates="behavior_profile")


class LoginEvent(Base):
    __tablename__ = "login_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    device_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    outcome: Mapped[LoginOutcome] = mapped_column(Enum(LoginOutcome), server_default="failed_credentials")
    raw_signals: Mapped[dict | None] = mapped_column(JSONB, nullable=True)