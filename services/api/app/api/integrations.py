from __future__ import annotations

from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import require_permission
from app.models.enums import AuditAction, IntegrationEventType, NotificationChannel
from app.models.operations import IntegrationEvent, Notification
from app.models.paediatric import Child, Visit
from app.schemas.common import CounterfactualRequest
from app.services.audit import write_audit

router = APIRouter(tags=["integrations"])


def _persist_event(db: Session, event_type: IntegrationEventType, payload: dict, target: str) -> IntegrationEvent:
    event = IntegrationEvent(event_type=event_type, payload=payload, target=target)
    db.add(event)
    db.flush()
    return event


@router.post("/integrations/counterfactual/request")
def request_counterfactual(
    body: CounterfactualRequest,
    request: Request,
    db: Session = Depends(get_db),
    current=Depends(require_permission("integration:request")),
):
    """Request intervention reassessment from Component 3. Does not change treatment."""
    settings = get_settings()
    payload = body.model_dump(mode="json")
    payload["requested_by"] = str(current.id)
    event = _persist_event(db, IntegrationEventType.COUNTERFACTUAL_REQUESTED, payload, "c3")
    result = {"event_id": str(event.id), "status": "queued"}
    if settings.c3_counterfactual_url:
        try:
            r = httpx.post(f"{settings.c3_counterfactual_url}/reassess", json=payload, timeout=10)
            r.raise_for_status()
            event.delivered_at = datetime.now(UTC)
            result["adapter"] = "c3"
            result["response"] = r.json()
        except httpx.HTTPError as exc:
            event.delivery_error = str(exc)
            result["adapter"] = "c3_error"
            result["message"] = "Component 3 is unavailable. Request was stored and can be retried."
    else:
        result["adapter"] = "mock"
        result["message"] = "Component 3 is not connected. A mock adapter stored the reassessment request."
        result["mock"] = True
    write_audit(
        db,
        action=AuditAction.REASSESSMENT_REQUESTED,
        resource_type="integration",
        resource_id=str(event.id),
        user_id=current.id,
        role=current.role.value,
        ip=request.client.host if request.client else None,
        metadata={"trigger": body.trigger, "child_id": body.child_id},
    )
    return result


@router.post("/integrations/explainability/request")
def request_explainability(visit_id: str, db: Session = Depends(get_db), current=Depends(require_permission("child:read"))):
    settings = get_settings()
    visit = db.get(Visit, visit_id)
    if not visit:
        raise HTTPException(404, "Visit not found")
    payload = {"visit_id": visit_id, "model_inputs": "approved_feature_schema", "component": "c2"}
    event = _persist_event(db, IntegrationEventType.EXPLAINABILITY_REQUESTED, payload, "c2")
    if settings.c2_explainability_url:
        try:
            r = httpx.post(f"{settings.c2_explainability_url}/explain", json=payload, timeout=10)
            event.delivered_at = datetime.now(UTC)
            return {"event_id": str(event.id), "result": r.json()}
        except httpx.HTTPError:
            event.delivery_error = "c2_unavailable"
    return {
        "event_id": str(event.id),
        "connected": False,
        "message": "Explainability component not connected",
    }


@router.post("/integrations/drift/observe")
def drift_observe(payload: dict, db: Session = Depends(get_db), current=Depends(require_permission("research:read", "admin:system"))):
    """Forward population-level observation metadata to Component 4. C1 does not implement drift logic."""
    event = _persist_event(db, IntegrationEventType.DRIFT_OBSERVATION, payload, "c4")
    settings = get_settings()
    if settings.c4_drift_url:
        try:
            httpx.post(f"{settings.c4_drift_url}/observe", json=payload, timeout=10)
            event.delivered_at = datetime.now(UTC)
        except httpx.HTTPError as exc:
            event.delivery_error = str(exc)
    return {"event_id": str(event.id), "note": "Component 4 owns concept-drift logic. This is an event interface only."}


@router.get("/notifications")
def notifications(db: Session = Depends(get_db), current=Depends(require_permission("child:read", "alert:read", "research:read"))):
    rows = db.scalars(
        select(Notification).where(Notification.user_id == current.id).order_by(Notification.created_at.desc()).limit(50)
    ).all()
    return {
        "items": [
            {
                "id": str(n.id),
                "title": n.title,
                "body": n.body,
                "severity": n.severity,
                "read_at": n.read_at.isoformat() if n.read_at else None,
                "created_at": n.created_at.isoformat(),
                "resource_type": n.resource_type,
                "resource_id": n.resource_id,
            }
            for n in rows
        ]
    }


@router.post("/notifications/{notification_id}/read")
def read_notification(notification_id: str, db: Session = Depends(get_db), current=Depends(require_permission("child:read", "alert:read"))):
    row = db.get(Notification, notification_id)
    if not row or row.user_id != current.id:
        raise HTTPException(404, "Notification not found")
    row.read_at = datetime.now(UTC)
    return {"ok": True}


@router.get("/product")
def product():
    from app.core.policy import load_product

    return load_product()
