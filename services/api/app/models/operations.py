from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, str_enum
from app.models.enums import AlertSeverity, AlertStatus, AlertType, FollowUpStatus, IntegrationEventType, NotificationChannel


class Alert(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "alerts"

    child_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("children.id"), nullable=False, index=True)
    visit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("visits.id"))
    facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), nullable=False, index=True)
    type: Mapped[AlertType] = mapped_column(str_enum(AlertType, "alert_type"), nullable=False, index=True)
    severity: Mapped[AlertSeverity] = mapped_column(str_enum(AlertSeverity, "alert_severity"), nullable=False)
    status: Mapped[AlertStatus] = mapped_column(str_enum(AlertStatus, "alert_status"), default=AlertStatus.OPEN, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_value: Mapped[dict | None] = mapped_column(JSON)
    threshold_version: Mapped[str | None] = mapped_column(String(80))
    event_window_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    resolution_notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (UniqueConstraint("event_window_key", name="uq_alert_event_window"),)


class FollowUpSchedule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "follow_up_schedules"

    child_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("children.id"), nullable=False, index=True)
    facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), nullable=False)
    expected_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    interval_days: Mapped[int] = mapped_column(Integer, default=30)
    responsible_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[FollowUpStatus] = mapped_column(
        str_enum(FollowUpStatus, "follow_up_status"), default=FollowUpStatus.SCHEDULED, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text)


class ClinicalNote(UUIDPrimaryKeyMixin, Base):
    """Free-text notes are operational only and are never fed into the model."""

    __tablename__ = "clinical_notes"

    child_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("children.id"), nullable=False, index=True)
    visit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("visits.id"))
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class AuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_logs"

    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str | None] = mapped_column(String(40))
    facility_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("facilities.id"))
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(80))
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSON)
    ip_address: Mapped[str | None] = mapped_column(String(64))


class Notification(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    channel: Mapped[NotificationChannel] = mapped_column(
        str_enum(NotificationChannel, "notification_channel"), default=NotificationChannel.IN_APP
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="INFO")
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resource_type: Mapped[str | None] = mapped_column(String(80))
    resource_id: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)


class IntegrationEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "integration_events"

    event_type: Mapped[IntegrationEventType] = mapped_column(
        str_enum(IntegrationEventType, "integration_event_type"), nullable=False, index=True
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    target: Mapped[str] = mapped_column(String(40), default="internal")
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivery_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
