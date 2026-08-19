from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_permission
from app.models.intelligence import LatentEmbedding, Prediction, TrajectoryMetric
from app.models.paediatric import Child, Visit
from app.security.rbac import assert_child_access

router = APIRouter(tags=["trajectory"])


@router.get("/children/{child_id}/trajectory")
def trajectory(child_id: UUID, db: Session = Depends(get_db), current=Depends(require_permission("child:read"))):
    child = db.get(Child, child_id)
    if not child:
        raise HTTPException(404, "Child not found")
    assert_child_access(current, child)
    visits = db.scalars(select(Visit).where(Visit.child_id == child_id).order_by(Visit.visit_number)).all()
    points = []
    spaces = set()
    for visit in visits:
        emb = db.scalar(select(LatentEmbedding).where(LatentEmbedding.visit_id == visit.id))
        pred = db.scalar(select(Prediction).where(Prediction.visit_id == visit.id, Prediction.is_active.is_(True)))
        if not emb or not pred:
            continue
        spaces.add(emb.embedding_space_id)
        points.append(
            {
                "visit_number": visit.visit_number,
                "visit_id": str(visit.id),
                "date": visit.visit_date.isoformat(),
                "x": emb.projection_x,
                "y": emb.projection_y,
                "risk": pred.primary_risk_score,
                "status": pred.status_prediction,
                "severity": pred.severity_prediction,
                "embedding_space_id": emb.embedding_space_id,
                "dimension": emb.embedding_dimension,
                "model_version_id": str(emb.model_version_id),
            }
        )
    warning = None
    if len(spaces) > 1:
        warning = "Model version changed — latent trajectory restarted/re-aligned"
    return {
        "child": child.pseudonymous_id,
        "points": points,
        "warning": warning,
        "disclaimer": "This visualization represents changes in the model's learned multidimensional representation. It does not independently determine clinical status.",
    }


@router.get("/children/{child_id}/risk-history")
def risk_history(child_id: UUID, db: Session = Depends(get_db), current=Depends(require_permission("child:read"))):
    child = db.get(Child, child_id)
    if not child:
        raise HTTPException(404, "Child not found")
    assert_child_access(current, child)
    visits = db.scalars(select(Visit).where(Visit.child_id == child_id).order_by(Visit.visit_number)).all()
    series = []
    for visit in visits:
        pred = db.scalar(select(Prediction).where(Prediction.visit_id == visit.id, Prediction.is_active.is_(True)))
        metric = db.scalar(select(TrajectoryMetric).where(TrajectoryMetric.to_visit_id == visit.id))
        if pred:
            series.append(
                {
                    "visit_number": visit.visit_number,
                    "date": visit.visit_date.isoformat(),
                    "risk": pred.primary_risk_score,
                    "severity": pred.severity_prediction,
                    "status": pred.status_prediction,
                    "progress": metric.progress_state.value if metric else None,
                    "risk_velocity": metric.risk_velocity if metric else None,
                }
            )
    return {"child": child.pseudonymous_id, "series": series}


@router.get("/children/{child_id}/progress")
def progress(child_id: UUID, db: Session = Depends(get_db), current=Depends(require_permission("child:read"))):
    child = db.get(Child, child_id)
    if not child:
        raise HTTPException(404, "Child not found")
    assert_child_access(current, child)
    metric = db.scalar(
        select(TrajectoryMetric).where(TrajectoryMetric.child_id == child_id).order_by(TrajectoryMetric.created_at.desc())
    )
    if not metric:
        return {"child": child.pseudonymous_id, "progress_state": "unknown"}
    return {
        "child": child.pseudonymous_id,
        "progress_state": metric.progress_state.value,
        "risk_velocity": metric.risk_velocity,
        "baseline_recovery_rate": metric.baseline_recovery_rate,
        "current_risk": metric.current_risk,
        "previous_risk": metric.previous_risk,
        "warning": metric.warning,
    }


@router.get("/children/{child_id}/report")
def report(child_id: UUID, request=None, db: Session = Depends(get_db), current=Depends(require_permission("report:export", "child:read"))):
    from app.models.enums import AuditAction
    from app.services.audit import write_audit
    from fastapi import Request

    child = db.get(Child, child_id)
    if not child:
        raise HTTPException(404, "Child not found")
    assert_child_access(current, child)
    write_audit(
        db,
        action=AuditAction.REPORT_EXPORTED,
        resource_type="child_report",
        resource_id=child.pseudonymous_id,
        user_id=current.id,
        role=current.role.value,
        facility_id=child.facility_id,
    )
    hist = risk_history(child_id, db, current)
    prog = progress(child_id, db, current)
    return {
        "pseudonymous_id": child.pseudonymous_id,
        "disclaimer": "AI-assisted decision support. Clinical review required. Synthetic demonstration data.",
        "progress": prog,
        "risk_history": hist["series"],
        "latent_vectors_excluded": True,
    }
