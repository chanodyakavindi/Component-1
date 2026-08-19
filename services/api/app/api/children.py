from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.db import get_db
from app.core.deps import require_permission
from app.core.security import FieldEncryptor
from app.core.config import get_settings
from app.models.enums import AlertStatus, AuditAction, EntityStatus, Sex
from app.models.identity import Facility
from app.models.intelligence import Prediction, TrajectoryMetric
from app.models.operations import Alert, FollowUpSchedule
from app.models.paediatric import Child, Caregiver, Visit
from app.schemas.common import ChildCreate, ChildListItem, ChildUpdate, Page
from app.security.rbac import assert_child_access, facility_scope_ids
from app.services.audit import write_audit

router = APIRouter(prefix="/children", tags=["children"])


def _next_pseudo(db: Session) -> str:
    count = db.scalar(select(func.count()).select_from(Child)) or 0
    return f"C-{1100 + count}"


def _age_months(dob: date) -> int:
    today = date.today()
    return max(0, (today.year - dob.year) * 12 + today.month - dob.month)


@router.get("", response_model=Page)
def list_children(
    q: str | None = None,
    facility: str | None = None,
    age_band: str | None = None,
    nutritional_status: str | None = None,
    risk: str | None = None,
    progress: str | None = None,
    alert_type: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str = "pseudonymous_id",
    db: Session = Depends(get_db),
    current=Depends(require_permission("child:read")),
):
    stmt = select(Child).where(Child.deleted_at.is_(None))
    scope = facility_scope_ids(current)
    if scope:
        stmt = stmt.where(Child.facility_id.in_(scope))
    if facility:
        fac = db.scalar(select(Facility).where(Facility.code == facility))
        if fac:
            stmt = stmt.where(Child.facility_id == fac.id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Child.pseudonymous_id.ilike(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Child.pseudonymous_id).offset((page - 1) * page_size).limit(page_size)).all()
    items = [_to_list_item(db, c) for c in rows]
    if nutritional_status:
        items = [i for i in items if (i.current_status or "").lower() == nutritional_status.lower()]
    if progress:
        items = [i for i in items if (i.progress or "").lower() == progress.lower()]
    if alert_type:
        items = [i for i in items if (i.alert_type or "") == alert_type]
    if risk == "high":
        items = [i for i in items if (i.current_risk or 0) >= 0.6]
    if age_band:
        items = [i for i in items if _band(i.age_months) == age_band]
    return Page(items=items, total=total, page=page, page_size=page_size)


def _band(age: int) -> str:
    if age < 6:
        return "0-5"
    if age < 12:
        return "6-11"
    if age < 24:
        return "12-23"
    return "24-59"


def _to_list_item(db: Session, child: Child) -> ChildListItem:
    last = db.scalar(select(Visit).where(Visit.child_id == child.id).order_by(Visit.visit_number.desc()).limit(1))
    pred = None
    progress = None
    if last:
        pred = db.scalar(select(Prediction).where(Prediction.visit_id == last.id, Prediction.is_active.is_(True)))
        metric = db.scalar(
            select(TrajectoryMetric).where(TrajectoryMetric.to_visit_id == last.id).order_by(TrajectoryMetric.created_at.desc())
        )
        progress = metric.progress_state.value if metric else None
    follow = db.scalar(
        select(FollowUpSchedule)
        .where(FollowUpSchedule.child_id == child.id)
        .order_by(FollowUpSchedule.expected_date.desc())
        .limit(1)
    )
    alert = db.scalar(
        select(Alert).where(Alert.child_id == child.id, Alert.status == AlertStatus.OPEN).order_by(Alert.created_at.desc()).limit(1)
    )
    fac = db.get(Facility, child.facility_id)
    return ChildListItem(
        id=child.id,
        pseudonymous_id=child.pseudonymous_id,
        age_months=_age_months(child.date_of_birth),
        sex=child.sex.value,
        last_visit=last.visit_date if last else None,
        current_status=pred.status_prediction if pred else None,
        current_risk=pred.primary_risk_score if pred else None,
        progress=progress,
        next_follow_up=follow.expected_date if follow else None,
        facility_code=fac.code if fac else None,
        alert_type=alert.type.value if alert else None,
        synthetic=True,
    )


@router.post("", status_code=201)
def create_child(body: ChildCreate, request: Request, db: Session = Depends(get_db), current=Depends(require_permission("child:write"))):
    facility_id = body.facility_id or current.user.facility_id
    if str(facility_id) != current.facility_id and not current.can("child:read_any"):
        raise HTTPException(status_code=403, detail="Cannot register a child in another facility")
    enc = FieldEncryptor(get_settings().encryption_key)
    child = Child(
        facility_id=facility_id,
        pseudonymous_id=_next_pseudo(db),
        external_patient_id_encrypted=enc.encrypt(body.external_patient_id),
        date_of_birth=body.date_of_birth,
        sex=Sex(body.sex),
        status=EntityStatus.ACTIVE,
        responsible_team=body.responsible_team,
        registered_by=current.id,
    )
    db.add(child)
    db.flush()
    if body.caregiver_display_name or body.caregiver_phone:
        db.add(
            Caregiver(
                child_id=child.id,
                kinship=body.caregiver_relationship or "mother",
                display_name=body.caregiver_display_name,
                phone_encrypted=enc.encrypt(body.caregiver_phone),
            )
        )
    write_audit(
        db,
        action=AuditAction.CHILD_CREATED,
        resource_type="child",
        resource_id=child.pseudonymous_id,
        user_id=current.id,
        role=current.role.value,
        facility_id=facility_id,
        ip=request.client.host if request.client else None,
    )
    return {"id": str(child.id), "pseudonymous_id": child.pseudonymous_id}


@router.get("/{child_id}")
def get_child(child_id: UUID, request: Request, db: Session = Depends(get_db), current=Depends(require_permission("child:read"))):
    child = db.get(Child, child_id)
    if child is None or child.deleted_at:
        raise HTTPException(status_code=404, detail="Child not found")
    assert_child_access(current, child)
    write_audit(
        db,
        action=AuditAction.CHILD_VIEWED,
        resource_type="child",
        resource_id=child.pseudonymous_id,
        user_id=current.id,
        role=current.role.value,
        facility_id=child.facility_id,
        ip=request.client.host if request.client else None,
    )
    return _child_profile(db, child)


@router.patch("/{child_id}")
def patch_child(child_id: UUID, body: ChildUpdate, request: Request, db: Session = Depends(get_db), current=Depends(require_permission("child:write"))):
    child = db.get(Child, child_id)
    if child is None:
        raise HTTPException(status_code=404, detail="Child not found")
    assert_child_access(current, child)
    if body.responsible_team is not None:
        child.responsible_team = body.responsible_team
    if body.status is not None:
        child.status = EntityStatus(body.status)
    if body.external_patient_id is not None:
        child.external_patient_id_encrypted = FieldEncryptor(get_settings().encryption_key).encrypt(body.external_patient_id)
    write_audit(
        db,
        action=AuditAction.CHILD_CHANGED,
        resource_type="child",
        resource_id=child.pseudonymous_id,
        user_id=current.id,
        role=current.role.value,
        facility_id=child.facility_id,
        ip=request.client.host if request.client else None,
    )
    return {"ok": True, "pseudonymous_id": child.pseudonymous_id}


def _child_profile(db: Session, child: Child) -> dict:
    from app.models.identity import Facility
    from app.models.intelligence import LatentEmbedding, ModelVersion
    from app.models.operations import ClinicalNote
    from app.models.enums import VisitStatus

    facility = db.get(Facility, child.facility_id)
    visits = db.scalars(select(Visit).where(Visit.child_id == child.id).order_by(Visit.visit_number)).all()
    history = []
    for visit in visits:
        pred = db.scalar(select(Prediction).where(Prediction.visit_id == visit.id, Prediction.is_active.is_(True)))
        metric = db.scalar(select(TrajectoryMetric).where(TrajectoryMetric.to_visit_id == visit.id))
        emb = db.scalar(select(LatentEmbedding).where(LatentEmbedding.visit_id == visit.id))
        model = db.get(ModelVersion, visit.model_version_id) if visit.model_version_id else None
        history.append(
            {
                "id": str(visit.id),
                "visit_number": visit.visit_number,
                "visit_date": visit.visit_date.isoformat(),
                "status": visit.status.value,
                "prediction": None
                if not pred
                else {
                    "status": pred.status_prediction,
                    "severity": pred.severity_prediction,
                    "risk": pred.primary_risk_score,
                    "confidence": pred.confidence,
                    "mode": pred.mode.value if hasattr(pred.mode, "value") else pred.mode,
                    "model": f"{model.model_key}-{model.version}" if model else None,
                    "run_number": pred.run_number,
                },
                "progress": metric.progress_state.value if metric else None,
                "risk_velocity": metric.risk_velocity if metric else None,
                "baseline_recovery_rate": metric.baseline_recovery_rate if metric else None,
                "warning": metric.warning if metric else None,
                "embedding_space_id": emb.embedding_space_id if emb else None,
                "projection": {"x": emb.projection_x, "y": emb.projection_y} if emb else None,
            }
        )
    latest = history[-1] if history else None
    follow = db.scalar(select(FollowUpSchedule).where(FollowUpSchedule.child_id == child.id).order_by(FollowUpSchedule.expected_date.desc()))
    alerts = db.scalars(select(Alert).where(Alert.child_id == child.id).order_by(Alert.created_at.desc())).all()
    notes = db.scalars(select(ClinicalNote).where(ClinicalNote.child_id == child.id).order_by(ClinicalNote.created_at.desc())).all()
    baseline_risk = history[0]["prediction"]["risk"] if history and history[0]["prediction"] else None
    current_risk = latest["prediction"]["risk"] if latest and latest["prediction"] else None
    risk_change = None
    if baseline_risk is not None and current_risk is not None and len(history) > 1:
        prev = history[-2]["prediction"]["risk"] if history[-2]["prediction"] else None
        if prev is not None:
            risk_change = round((current_risk - prev) * 100, 1)
    model_warning = None
    spaces = {h["embedding_space_id"] for h in history if h["embedding_space_id"]}
    if len(spaces) > 1:
        model_warning = "Model version changed — latent trajectory restarted/re-aligned"
    return {
        "id": str(child.id),
        "pseudonymous_id": child.pseudonymous_id,
        "age_months": _age_months(child.date_of_birth),
        "sex": child.sex.value,
        "date_of_birth": child.date_of_birth.isoformat(),
        "facility": {"name": facility.name, "code": facility.code, "district": facility.district} if facility else None,
        "responsible_team": child.responsible_team,
        "synthetic": True,
        "current": latest,
        "risk_change_pp": risk_change,
        "next_follow_up": follow.expected_date.isoformat() if follow else None,
        "follow_up_status": follow.status.value if follow else None,
        "visits": history,
        "model_warning": model_warning,
        "alerts": [
            {
                "id": str(a.id),
                "type": a.type.value,
                "severity": a.severity.value,
                "status": a.status.value,
                "message": a.message,
                "created_at": a.created_at.isoformat(),
                "trigger_value": a.trigger_value,
            }
            for a in alerts
        ],
        "notes": [
            {"id": str(n.id), "body": n.body, "created_at": n.created_at.isoformat(), "author_id": str(n.author_id)}
            for n in notes
        ],
    }
