from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_permission
from app.models.enums import AlertStatus, FollowUpStatus, ProgressState
from app.models.identity import Facility
from app.models.intelligence import TrajectoryMetric
from app.models.operations import Alert, AuditLog, FollowUpSchedule
from app.models.paediatric import Child, Visit
from app.security.rbac import facility_scope_ids

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), current=Depends(require_permission("child:read", "research:read"))):
    scope = facility_scope_ids(current)
    child_stmt = select(Child).where(Child.deleted_at.is_(None))
    if scope:
        child_stmt = child_stmt.where(Child.facility_id.in_(scope))
    children = db.scalars(child_stmt).all()
    child_ids = [c.id for c in children]

    latest_metrics = {}
    if child_ids:
        metrics = db.scalars(select(TrajectoryMetric).where(TrajectoryMetric.child_id.in_(child_ids))).all()
        for m in metrics:
            latest_metrics[m.child_id] = m

    high_risk = 0
    stagnating = 0
    deteriorating = 0
    for child in children:
        m = latest_metrics.get(child.id)
        if not m:
            continue
        if m.current_risk >= 0.6:
            high_risk += 1
        if m.progress_state == ProgressState.STAGNATING:
            stagnating += 1
        if m.progress_state == ProgressState.DETERIORATING:
            deteriorating += 1

    missed_stmt = select(func.count()).select_from(FollowUpSchedule).where(FollowUpSchedule.status == FollowUpStatus.OVERDUE)
    if scope:
        missed_stmt = missed_stmt.where(FollowUpSchedule.facility_id.in_(scope))
    missed = db.scalar(missed_stmt) or 0

    attention = []
    alert_stmt = select(Alert).where(Alert.status.in_([AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED, AlertStatus.IN_REVIEW]))
    if scope:
        alert_stmt = alert_stmt.where(Alert.facility_id.in_(scope))
    alerts = db.scalars(alert_stmt.order_by(Alert.created_at.desc()).limit(40)).all()
    for alert in alerts:
        child = db.get(Child, alert.child_id)
        metric = latest_metrics.get(alert.child_id)
        attention.append(
            {
                "child_id": str(child.id) if child else None,
                "pseudonymous_id": child.pseudonymous_id if child else None,
                "age_months": None,
                "latest_visit": None,
                "status": metric.progress_state.value if metric else None,
                "current_risk": metric.current_risk if metric else None,
                "trend": metric.progress_state.value if metric else None,
                "alert": alert.type.value,
                "alert_id": str(alert.id),
                "next_action": "Review child record",
            }
        )

    improving = sum(1 for m in latest_metrics.values() if m.progress_state == ProgressState.IMPROVING)
    stable = sum(1 for m in latest_metrics.values() if m.progress_state in {ProgressState.STABLE, ProgressState.BASELINE})
    det = sum(1 for m in latest_metrics.values() if m.progress_state == ProgressState.DETERIORATING)
    stag = sum(1 for m in latest_metrics.values() if m.progress_state == ProgressState.STAGNATING)

    follow_stmt = select(FollowUpSchedule).where(
        FollowUpSchedule.status.in_([FollowUpStatus.SCHEDULED, FollowUpStatus.OVERDUE, FollowUpStatus.RESCHEDULED])
    )
    if scope:
        follow_stmt = follow_stmt.where(FollowUpSchedule.facility_id.in_(scope))
    follows = db.scalars(follow_stmt.order_by(FollowUpSchedule.expected_date).limit(12)).all()
    upcoming = []
    for f in follows:
        child = db.get(Child, f.child_id)
        fac = db.get(Facility, f.facility_id)
        upcoming.append(
            {
                "child": child.pseudonymous_id if child else None,
                "date": f.expected_date.isoformat(),
                "clinic": fac.name if fac else None,
                "status": f.status.value,
            }
        )

    activity_stmt = select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(12)
    if scope:
        activity_stmt = activity_stmt.where(AuditLog.facility_id.in_(scope))
    activity = [
        {"action": a.action, "resource_type": a.resource_type, "resource_id": a.resource_id, "timestamp": a.timestamp.isoformat()}
        for a in db.scalars(activity_stmt).all()
    ]

    return {
        "synthetic": True,
        "kpis": {
            "children_under_monitoring": len(children),
            "high_risk": high_risk,
            "stagnation_alerts": stagnating,
            "deteriorating": deteriorating,
            "missed_follow_ups": missed,
        },
        "attention": attention,
        "risk_trend": {"improving": improving, "stable": stable, "stagnating": stag, "deteriorating": det},
        "upcoming_follow_ups": upcoming,
        "recent_activity": activity,
    }


@router.get("/search")
def search(q: str = Query(min_length=1), db: Session = Depends(get_db), current=Depends(require_permission("child:read", "alert:read"))):
    scope = facility_scope_ids(current)
    like = f"%{q.strip()}%"
    child_stmt = select(Child).where(Child.deleted_at.is_(None), Child.pseudonymous_id.ilike(like))
    if scope:
        child_stmt = child_stmt.where(Child.facility_id.in_(scope))
    children = [
        {"type": "child", "id": str(c.id), "label": c.pseudonymous_id}
        for c in db.scalars(child_stmt.limit(8)).all()
    ]
    alert_stmt = select(Alert).where(Alert.message.ilike(like))
    if scope:
        alert_stmt = alert_stmt.where(Alert.facility_id.in_(scope))
    alerts = [
        {"type": "alert", "id": str(a.id), "label": a.message, "child_id": str(a.child_id)}
        for a in db.scalars(alert_stmt.limit(8)).all()
    ]
    return {"items": children + alerts}
