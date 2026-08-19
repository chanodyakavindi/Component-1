from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.policy import load_clinical_policy
from app.models.enums import (
    AlertStatus,
    AlertType,
    AuditAction,
    FollowUpStatus,
    IntegrationEventType,
    ModelStatus,
    NotificationChannel,
    ProgressState,
    VisitStatus,
)
from app.models.intelligence import LatentEmbedding, ModelVersion, Prediction, TrajectoryMetric
from app.models.operations import Alert, FollowUpSchedule, IntegrationEvent, Notification
from app.models.paediatric import Child, Visit
from app.services.alerts import deterioration_alert, event_window_key, relapse_alert, severity_for, stagnation_alert
from app.services.audit import write_audit
from app.services.longitudinal import LongitudinalError, classify_progress, elapsed_months


def _input_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def active_model(db: Session) -> ModelVersion:
    row = db.scalar(select(ModelVersion).where(ModelVersion.status == ModelStatus.ACTIVE).limit(1))
    if row:
        return row
    row = db.scalar(select(ModelVersion).where(ModelVersion.is_demo.is_(True)).limit(1))
    if row:
        return row
    raise HTTPException(status_code=503, detail="No model version is registered")


def build_inference_payload(visit: Visit, child: Child) -> dict:
    return {
        "child_pseudonymous_id": child.pseudonymous_id,
        "visit_number": visit.visit_number,
        "visit_date": visit.visit_date.isoformat(),
        "anthropometric": {
            "age_months": visit.anthropometry.age_months if visit.anthropometry else None,
            "sex": visit.anthropometry.sex.value if visit.anthropometry else None,
            "height_cm": visit.anthropometry.height_cm if visit.anthropometry else None,
            "weight_kg": visit.anthropometry.weight_kg if visit.anthropometry else None,
            "muac_cm": visit.anthropometry.muac_cm if visit.anthropometry else None,
            "birth_weight_kg": visit.anthropometry.birth_weight_kg if visit.anthropometry else None,
            "head_circumference_cm": visit.anthropometry.head_circumference_cm if visit.anthropometry else None,
        },
        "socioeconomic": _to_dict(visit.socioeconomic),
        "dietary": _to_dict(visit.dietary),
        "maternal_child_health": _to_dict(visit.maternal_child_health),
    }


def _to_dict(obj) -> dict:
    if obj is None:
        return {}
    data = {}
    for col in obj.__table__.columns:
        if col.name in {"id", "visit_id", "created_at", "updated_at"}:
            continue
        val = getattr(obj, col.name)
        data[col.name] = val.value if hasattr(val, "value") else val
    return data


def run_inference(db: Session, visit: Visit, child: Child, user_id, ip: str | None) -> Prediction:
    settings = get_settings()
    model = active_model(db)
    payload = build_inference_payload(visit, child)
    payload["model_mode"] = settings.model_mode
    started = datetime.now(UTC)
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(f"{settings.inference_url}/predict", json=payload)
            response.raise_for_status()
            result = response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Prediction service is temporarily unavailable. The visit has been saved safely. Try prediction again later.",
        ) from exc

    existing_runs = db.scalars(select(Prediction).where(Prediction.visit_id == visit.id)).all()
    for pred in existing_runs:
        pred.is_active = False
    run_number = len(existing_runs) + 1

    prediction = Prediction(
        visit_id=visit.id,
        model_version_id=model.id,
        run_number=run_number,
        is_active=True,
        mode=result.get("mode", "DEMO"),
        status_prediction=result["status"],
        severity_prediction=result["severity"],
        raw_probabilities=result["raw_probabilities"],
        calibrated_probabilities=result["calibrated_probabilities"],
        primary_risk_score=float(result["risk_score"]),
        confidence=result.get("confidence", "moderate"),
        inference_ms=float(result.get("inference_ms") or (datetime.now(UTC) - started).total_seconds() * 1000),
        input_hash=_input_hash(payload),
        feature_schema_version=result.get("feature_schema_version", "fs-2026-001"),
        calibration_version=result.get("calibration_version", "demo-temp-v1"),
    )
    db.add(prediction)
    db.flush()

    embedding = result.get("latent_embedding") or []
    x, y = _project(embedding)
    db.add(
        LatentEmbedding(
            visit_id=visit.id,
            prediction_id=prediction.id,
            model_version_id=model.id,
            embedding_space_id=model.embedding_space_id,
            embedding_dimension=len(embedding) or model.embedding_dimension,
            embedding=embedding,
            projection_x=x,
            projection_y=y,
            projection_version="pca-demo-v1",
        )
    )

    visit.status = VisitStatus.PREDICTED
    visit.model_version_id = model.id

    _update_trajectory(db, child, visit, prediction, model)
    _emit_event(
        db,
        IntegrationEventType.PREDICTION_COMPLETED,
        {
            "child_id": child.pseudonymous_id,
            "visit_id": str(visit.id),
            "model_version": f"{model.model_key}-{model.version}",
            "risk": prediction.primary_risk_score,
            "mode": prediction.mode,
        },
    )
    write_audit(
        db,
        action=AuditAction.PREDICTION_GENERATED,
        resource_type="prediction",
        resource_id=str(prediction.id),
        user_id=user_id,
        facility_id=child.facility_id,
        metadata={"visit_id": str(visit.id), "mode": prediction.mode},
        ip=ip,
    )
    return prediction


def _project(embedding: list[float]) -> tuple[float | None, float | None]:
    if not embedding:
        return None, None
    # Deterministic 2D reference projection for demo/PCA-like display.
    n = len(embedding)
    x = sum(embedding[i] * (1 if i % 2 == 0 else -1) for i in range(n)) / n
    y = sum(embedding[i] * (1 if i % 3 == 0 else -0.5) for i in range(n)) / n
    return float(x), float(y)


def _update_trajectory(db: Session, child: Child, visit: Visit, prediction: Prediction, model: ModelVersion) -> TrajectoryMetric:
    policy = load_clinical_policy()
    visits = db.scalars(
        select(Visit)
        .where(Visit.child_id == child.id, Visit.status == VisitStatus.PREDICTED)
        .order_by(Visit.visit_number)
        .options(joinedload(Visit.predictions))
    ).unique().all()
    predicted = [v for v in visits if v.id != visit.id] + [visit]
    predicted.sort(key=lambda v: v.visit_number)

    is_baseline = visit.visit_number == 0 or len(predicted) == 1
    previous = predicted[-2] if len(predicted) >= 2 else None
    baseline = predicted[0]
    prev_active = _active_prediction(previous) if previous else None
    base_active = _active_prediction(baseline)

    previous_model = previous.model_version_id if previous else None
    compatible = previous_model is None or previous_model == model.id or _compatible(db, previous_model, model)

    months = None
    months_from_baseline = None
    warning = None
    try:
        if previous:
            months = elapsed_months(previous.visit_date, visit.visit_date)
        if baseline.id != visit.id:
            months_from_baseline = elapsed_months(baseline.visit_date, visit.visit_date)
    except LongitudinalError as exc:
        warning = str(exc)
        months = None

    consecutive = _consecutive_stagnation_count(db, child.id) if previous else 0
    evaluation = classify_progress(
        is_baseline=is_baseline,
        previous_risk=prev_active.primary_risk_score if prev_active else None,
        current_risk=prediction.primary_risk_score,
        baseline_risk=base_active.primary_risk_score if base_active else None,
        months=months,
        months_from_baseline=months_from_baseline,
        stagnation_threshold=policy.stagnation_threshold,
        deterioration_delta=policy.deterioration_delta,
        consecutive_near_zero=consecutive + 1,
        consecutive_required=policy.consecutive_followups,
        model_compatible=compatible,
    )
    if warning:
        evaluation.warning = warning

    metric = TrajectoryMetric(
        child_id=child.id,
        from_visit_id=previous.id if previous else None,
        to_visit_id=visit.id,
        baseline_visit_id=baseline.id,
        risk_velocity=evaluation.risk_velocity,
        baseline_recovery_rate=evaluation.baseline_recovery_rate,
        elapsed_days=int((months or 0) * 30.4375) if months else None,
        elapsed_months=evaluation.elapsed_months,
        previous_risk=prev_active.primary_risk_score if prev_active else None,
        current_risk=prediction.primary_risk_score,
        progress_state=evaluation.progress_state,
        model_compatible=compatible,
        warning=evaluation.warning,
    )
    db.add(metric)
    db.flush()

    _maybe_create_alerts(db, child, visit, prediction, prev_active, base_active, evaluation, policy, consecutive)
    _schedule_follow_up(db, child, visit, policy)
    _emit_event(
        db,
        IntegrationEventType.TRAJECTORY_UPDATED,
        {
            "child_id": child.pseudonymous_id,
            "visit_id": str(visit.id),
            "progress_state": evaluation.progress_state.value,
            "risk_velocity": evaluation.risk_velocity,
        },
    )
    return metric


def _active_prediction(visit: Visit | None) -> Prediction | None:
    if visit is None:
        return None
    for pred in visit.predictions:
        if pred.is_active:
            return pred
    return visit.predictions[-1] if visit.predictions else None


def _compatible(db: Session, previous_id, current: ModelVersion) -> bool:
    previous = db.get(ModelVersion, previous_id)
    if previous is None:
        return False
    if previous.embedding_space_id == current.embedding_space_id:
        return True
    compat = current.compatible_with or []
    return previous.version in compat or str(previous.id) in compat


def _consecutive_stagnation_count(db: Session, child_id) -> int:
    rows = db.scalars(
        select(TrajectoryMetric).where(TrajectoryMetric.child_id == child_id).order_by(TrajectoryMetric.created_at.desc())
    ).all()
    count = 0
    for row in rows:
        if row.progress_state in {ProgressState.STAGNATING, ProgressState.STABLE}:
            count += 1
        else:
            break
    return count


def _maybe_create_alerts(db, child, visit, prediction, prev_active, base_active, evaluation, policy, consecutive) -> None:
    created: list[AlertType] = []
    if stagnation_alert(
        progress_state=evaluation.progress_state,
        consecutive_stagnating=consecutive + 1,
        policy=policy,
    ):
        created.append(AlertType.STAGNATION)
        _emit_event(db, IntegrationEventType.PROGRESS_STAGNATING, {"child_id": child.pseudonymous_id})
    if deterioration_alert(
        previous_risk=prev_active.primary_risk_score if prev_active else None,
        current_risk=prediction.primary_risk_score,
        policy=policy,
    ):
        created.append(AlertType.DETERIORATION)
        _emit_event(db, IntegrationEventType.PROGRESS_DETERIORATING, {"child_id": child.pseudonymous_id})
    improved = False
    if base_active:
        improved = (base_active.primary_risk_score - prediction.primary_risk_score) >= policy.relapse_prior_improvement
    if relapse_alert(
        improved_from_baseline=improved,
        previous_risk=prev_active.primary_risk_score if prev_active else None,
        current_risk=prediction.primary_risk_score,
        policy=policy,
    ):
        created.append(AlertType.RELAPSE)

    for alert_type in created:
        key = event_window_key(str(child.id), alert_type, str(visit.id))
        existing = db.scalar(select(Alert).where(Alert.event_window_key == key))
        if existing:
            continue
        prev = prev_active.primary_risk_score if prev_active else None
        message = {
            AlertType.STAGNATION: "Progress stagnation detected",
            AlertType.DETERIORATION: "Deterioration detected",
            AlertType.RELAPSE: "Possible relapse / regression",
        }[alert_type]
        alert = Alert(
            child_id=child.id,
            visit_id=visit.id,
            facility_id=child.facility_id,
            type=alert_type,
            severity=severity_for(alert_type, policy),
            status=AlertStatus.OPEN,
            message=message,
            trigger_value={
                "previous_risk": prev,
                "current_risk": prediction.primary_risk_score,
                "risk_velocity": evaluation.risk_velocity,
                "policy_id": policy.policy_id,
            },
            threshold_version=policy.policy_id,
            event_window_key=key,
        )
        db.add(alert)
        db.flush()
        _notify_facility(db, child, alert)
        _emit_event(
            db,
            IntegrationEventType.ALERT_CREATED,
            {"child_id": child.pseudonymous_id, "type": alert_type.value, "alert_id": str(alert.id)},
        )


def _schedule_follow_up(db: Session, child: Child, visit: Visit, policy) -> None:
    expected = (visit.visit_date + timedelta(days=policy.default_followup_days)).date()
    existing_open = db.scalars(
        select(FollowUpSchedule).where(
            FollowUpSchedule.child_id == child.id,
            FollowUpSchedule.status.in_([FollowUpStatus.SCHEDULED, FollowUpStatus.OVERDUE, FollowUpStatus.RESCHEDULED]),
        )
    ).all()
    for row in existing_open:
        row.status = FollowUpStatus.COMPLETED
    db.add(
        FollowUpSchedule(
            child_id=child.id,
            facility_id=child.facility_id,
            expected_date=expected,
            interval_days=policy.default_followup_days,
            status=FollowUpStatus.SCHEDULED,
        )
    )


def _notify_facility(db: Session, child: Child, alert: Alert) -> None:
    from app.models.identity import User
    from app.models.enums import UserRole

    users = db.scalars(
        select(User).where(
            User.facility_id == child.facility_id,
            User.role.in_([UserRole.HEALTH_WORKER, UserRole.DOCTOR, UserRole.NUTRITIONIST, UserRole.FACILITY_ADMIN]),
        )
    ).all()
    for user in users:
        db.add(
            Notification(
                user_id=user.id,
                channel=NotificationChannel.IN_APP,
                title=alert.message,
                body=f"{child.pseudonymous_id}: {alert.message}",
                severity=alert.severity.value,
                resource_type="alert",
                resource_id=str(alert.id),
            )
        )


def _emit_event(db: Session, event_type: IntegrationEventType, payload: dict) -> None:
    db.add(IntegrationEvent(event_type=event_type, payload=payload, target="internal"))


def evaluate_missed_followups(db: Session) -> int:
    """Idempotent missed follow-up evaluation used by the worker."""
    from datetime import date

    policy = load_clinical_policy()
    today = date.today()
    due = db.scalars(
        select(FollowUpSchedule).where(
            FollowUpSchedule.status == FollowUpStatus.SCHEDULED,
            FollowUpSchedule.expected_date < today,
        )
    ).all()
    created = 0
    for sched in due:
        grace_end = sched.expected_date.toordinal() + policy.overdue_grace_days
        if today.toordinal() < grace_end:
            continue
        sched.status = FollowUpStatus.OVERDUE
        child = db.get(Child, sched.child_id)
        if child is None:
            continue
        key = event_window_key(str(child.id), AlertType.MISSED_FOLLOW_UP, None, extra=str(sched.id))
        existing = db.scalar(select(Alert).where(Alert.event_window_key == key))
        if existing:
            continue
        alert = Alert(
            child_id=child.id,
            facility_id=child.facility_id,
            type=AlertType.MISSED_FOLLOW_UP,
            severity=severity_for(AlertType.MISSED_FOLLOW_UP, policy),
            status=AlertStatus.OPEN,
            message="Follow-up overdue",
            trigger_value={
                "expected_date": sched.expected_date.isoformat(),
                "grace_period_days": policy.overdue_grace_days,
                "disclaimer": policy.disclaimer,
            },
            threshold_version=policy.policy_id,
            event_window_key=key,
        )
        db.add(alert)
        _notify_facility(db, child, alert)
        _emit_event(db, IntegrationEventType.FOLLOWUP_OVERDUE, {"child_id": child.pseudonymous_id})
        created += 1
    db.commit()
    return created
