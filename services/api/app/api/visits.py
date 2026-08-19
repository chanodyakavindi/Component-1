from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_permission
from app.core.policy import load_clinical_policy
from app.models.enums import AuditAction, Sex, VisitStatus, VisitType
from app.models.paediatric import (
    AnthropometricRecord,
    Child,
    DietaryRecord,
    MaternalChildHealthRecord,
    SocioeconomicRecord,
    Visit,
)
from app.schemas.common import VisitCreate, VisitOut
from app.security.rbac import assert_child_access
from app.services.audit import write_audit
from app.services.prediction import run_inference
from app.services.quality import validate_visit_payload

router = APIRouter(tags=["visits"])


def _visit_number(db: Session, child_id) -> int:
    last = db.scalar(select(Visit).where(Visit.child_id == child_id).order_by(Visit.visit_number.desc()).limit(1))
    return 0 if last is None else last.visit_number + 1


@router.get("/children/{child_id}/visits")
def list_visits(child_id: UUID, db: Session = Depends(get_db), current=Depends(require_permission("visit:read"))):
    child = db.get(Child, child_id)
    if not child:
        raise HTTPException(404, "Child not found")
    assert_child_access(current, child)
    visits = db.scalars(select(Visit).where(Visit.child_id == child_id).order_by(Visit.visit_number)).all()
    return [
        VisitOut(
            id=v.id,
            child_id=v.child_id,
            visit_number=v.visit_number,
            visit_date=v.visit_date,
            visit_type=v.visit_type.value,
            status=v.status.value,
            scheduled=v.scheduled,
            data_quality=v.data_quality,
        )
        for v in visits
    ]


@router.post("/children/{child_id}/visits", status_code=201)
def create_visit(
    child_id: UUID,
    body: VisitCreate,
    request: Request,
    db: Session = Depends(get_db),
    current=Depends(require_permission("visit:write")),
):
    child = db.get(Child, child_id)
    if not child:
        raise HTTPException(404, "Child not found")
    assert_child_access(current, child)
    policy = load_clinical_policy()
    payload = body.model_dump()
    previous = db.scalar(select(Visit).where(Visit.child_id == child_id).order_by(Visit.visit_number.desc()).limit(1))
    stale = False
    if body.socioeconomic and not body.socioeconomic.household_changed and previous and previous.socioeconomic:
        payload["socioeconomic"] = {
            "wealth_proxy": previous.socioeconomic.wealth_proxy,
            "maternal_education": previous.socioeconomic.maternal_education,
            "paternal_education": previous.socioeconomic.paternal_education,
            "maternal_employment": previous.socioeconomic.maternal_employment,
            "household_size": previous.socioeconomic.household_size,
            "geographical_area": previous.socioeconomic.geographical_area,
            "drinking_water": previous.socioeconomic.drinking_water,
            "sanitation": previous.socioeconomic.sanitation,
        }
        stale = True
    report = validate_visit_payload(payload, policy, socioeconomic_stale=stale)
    if not body.save_as_draft and not report.complete:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "This visit contains values outside the configured validation range. Review the highlighted fields before continuing."
                if any(i.flag.value == "OUTLIER_REVIEW_REQUIRED" for i in report.blocking_errors)
                else "A prediction cannot be generated from the available information. Complete the required fields or request clinical review.",
                "quality": report.as_dict(),
            },
        )
    if not body.save_as_draft and not body.confirmation_attested:
        raise HTTPException(status_code=422, detail="Confirmation is required before prediction: entered information must match the clinic record.")

    visit = Visit(
        child_id=child.id,
        facility_id=child.facility_id,
        visit_number=_visit_number(db, child.id),
        visit_date=body.visit_date,
        visit_type=VisitType(body.visit_type),
        scheduled=body.scheduled,
        recorded_by=current.id,
        status=VisitStatus.DRAFT if body.save_as_draft else VisitStatus.SUBMITTED,
        confirmation_attested=body.confirmation_attested,
        data_quality=report.as_dict(),
    )
    db.add(visit)
    db.flush()
    anthro = body.anthropometric
    db.add(
        AnthropometricRecord(
            visit_id=visit.id,
            age_months=anthro.age_months,
            sex=Sex(anthro.sex),
            height_cm=anthro.height_cm,
            weight_kg=anthro.weight_kg,
            muac_cm=anthro.muac_cm,
            birth_weight_kg=anthro.birth_weight_kg,
            head_circumference_cm=anthro.head_circumference_cm,
            previous_weight_kg=anthro.previous_weight_kg,
            previous_height_cm=anthro.previous_height_cm,
        )
    )
    socio = payload.get("socioeconomic") or {}
    db.add(SocioeconomicRecord(visit_id=visit.id, carried_forward=stale, **{k: socio.get(k) for k in [
        "wealth_proxy", "maternal_education", "paternal_education", "maternal_employment",
        "household_size", "geographical_area", "drinking_water", "sanitation"
    ]}))
    diet = (body.dietary.model_dump() if body.dietary else {})
    db.add(DietaryRecord(visit_id=visit.id, **diet))
    mch = (body.maternal_child_health.model_dump() if body.maternal_child_health else {})
    db.add(MaternalChildHealthRecord(visit_id=visit.id, **mch))
    write_audit(
        db,
        action=AuditAction.VISIT_CREATED,
        resource_type="visit",
        resource_id=str(visit.id),
        user_id=current.id,
        role=current.role.value,
        facility_id=child.facility_id,
        ip=request.client.host if request.client else None,
        metadata={"draft": body.save_as_draft, "visit_number": visit.visit_number},
    )
    db.flush()
    result = {
        "visit": VisitOut(
            id=visit.id,
            child_id=visit.child_id,
            visit_number=visit.visit_number,
            visit_date=visit.visit_date,
            visit_type=visit.visit_type.value,
            status=visit.status.value,
            scheduled=visit.scheduled,
            data_quality=visit.data_quality,
        ),
        "quality": report.as_dict(),
        "prediction": None,
    }
    if body.save_as_draft:
        return result
    db.refresh(visit)
    visit.anthropometry  # load
    prediction = run_inference(db, visit, child, current.id, request.client.host if request.client else None)
    result["prediction"] = {
        "id": str(prediction.id),
        "status": prediction.status_prediction,
        "severity": prediction.severity_prediction,
        "risk": prediction.primary_risk_score,
        "confidence": prediction.confidence,
        "mode": prediction.mode.value if hasattr(prediction.mode, "value") else prediction.mode,
        "run_number": prediction.run_number,
        "inference_ms": prediction.inference_ms,
    }
    result["visit"].status = visit.status.value
    return result


@router.get("/visits/{visit_id}")
def get_visit(visit_id: UUID, db: Session = Depends(get_db), current=Depends(require_permission("visit:read"))):
    visit = db.get(Visit, visit_id)
    if not visit:
        raise HTTPException(404, "Visit not found")
    child = db.get(Child, visit.child_id)
    assert_child_access(current, child)
    return {
        "id": str(visit.id),
        "child_id": str(visit.child_id),
        "visit_number": visit.visit_number,
        "visit_date": visit.visit_date.isoformat(),
        "status": visit.status.value,
        "anthropometric": _row(visit.anthropometry),
        "socioeconomic": _row(visit.socioeconomic),
        "dietary": _row(visit.dietary),
        "maternal_child_health": _row(visit.maternal_child_health),
        "data_quality": visit.data_quality,
    }


@router.post("/visits/{visit_id}/predict")
def predict_visit(visit_id: UUID, request: Request, db: Session = Depends(get_db), current=Depends(require_permission("predict:run"))):
    visit = db.get(Visit, visit_id)
    if not visit:
        raise HTTPException(404, "Visit not found")
    child = db.get(Child, visit.child_id)
    assert_child_access(current, child)
    if visit.status == VisitStatus.DRAFT:
        raise HTTPException(422, "Submit the visit before running prediction")
    prediction = run_inference(db, visit, child, current.id, request.client.host if request.client else None)
    return {
        "id": str(prediction.id),
        "run_number": prediction.run_number,
        "status": prediction.status_prediction,
        "severity": prediction.severity_prediction,
        "risk": prediction.primary_risk_score,
        "mode": prediction.mode.value if hasattr(prediction.mode, "value") else prediction.mode,
        "inference_ms": prediction.inference_ms,
    }


@router.get("/visits/{visit_id}/prediction")
def get_prediction(visit_id: UUID, db: Session = Depends(get_db), current=Depends(require_permission("visit:read"))):
    from app.models.intelligence import Prediction

    visit = db.get(Visit, visit_id)
    if not visit:
        raise HTTPException(404, "Visit not found")
    assert_child_access(current, db.get(Child, visit.child_id))
    preds = db.scalars(select(Prediction).where(Prediction.visit_id == visit_id).order_by(Prediction.run_number)).all()
    return [
        {
            "id": str(p.id),
            "run_number": p.run_number,
            "is_active": p.is_active,
            "status": p.status_prediction,
            "severity": p.severity_prediction,
            "risk": p.primary_risk_score,
            "mode": p.mode.value if hasattr(p.mode, "value") else p.mode,
            "raw_probabilities": p.raw_probabilities,
            "calibrated_probabilities": p.calibrated_probabilities,
            "confidence": p.confidence,
            "created_at": p.created_at.isoformat(),
        }
        for p in preds
    ]


def _row(obj):
    if obj is None:
        return None
    data = {}
    for col in obj.__table__.columns:
        if col.name in {"id", "visit_id", "created_at", "updated_at"}:
            continue
        val = getattr(obj, col.name)
        data[col.name] = val.value if hasattr(val, "value") else val
    return data
