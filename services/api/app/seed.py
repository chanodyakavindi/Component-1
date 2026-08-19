"""Seed synthetic demonstration data. Never use these passwords in production."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.policy import load_clinical_policy
from app.core.security import hash_password
from app.models.enums import (
    EntityStatus,
    FacilityType,
    FollowUpStatus,
    ModelStatus,
    OrganizationType,
    PredictionMode,
    ProgressState,
    Sex,
    UserRole,
    UserStatus,
    VisitStatus,
    VisitType,
)
from app.models.identity import Facility, Organization, User
from app.models.intelligence import ClinicalPolicyVersion, LatentEmbedding, ModelVersion, Prediction, TrajectoryMetric
from app.models.operations import FollowUpSchedule
from app.models.paediatric import (
    AnthropometricRecord,
    Caregiver,
    Child,
    DietaryRecord,
    MaternalChildHealthRecord,
    SocioeconomicRecord,
    Visit,
)
from app.services.longitudinal import classify_progress, elapsed_months
from app.services.prediction import _maybe_create_alerts, _project

DEMO_PASSWORD = "DemoPass123!"
CONTRACTS = Path("/contracts") if Path("/contracts").exists() else Path(__file__).resolve().parents[3] / "packages" / "contracts"


CASES = [
    {
        "pid": "C-1042",
        "sex": "female",
        "dob": "2025-02-19",
        "facility": "CCHC-04",
        "team": "Clinic 04",
        "scenario": "stagnation",
        "follow_up": "2026-09-15",
        "visits": [
            {"date": "2026-01-15", "risk": 0.82, "status": "wasting", "severity": "severe", "progress": "baseline"},
            {"date": "2026-02-18", "risk": 0.61, "status": "wasting", "severity": "moderate", "progress": "improving"},
            {"date": "2026-03-18", "risk": 0.59, "status": "wasting", "severity": "moderate", "progress": "stagnating"},
        ],
    },
    {
        "pid": "C-1001",
        "sex": "male",
        "dob": "2024-11-02",
        "facility": "CCHC-04",
        "scenario": "improving",
        "follow_up": "2026-09-01",
        "visits": [
            {"date": "2026-03-01", "risk": 0.74, "status": "underweight", "severity": "moderate", "progress": "baseline"},
            {"date": "2026-04-04", "risk": 0.58, "status": "underweight", "severity": "mild", "progress": "improving"},
            {"date": "2026-05-06", "risk": 0.41, "status": "normal", "severity": "none", "progress": "improving"},
            {"date": "2026-06-08", "risk": 0.28, "status": "normal", "severity": "none", "progress": "improving"},
        ],
    },
    {
        "pid": "C-1002",
        "sex": "female",
        "dob": "2025-01-10",
        "facility": "CCHC-04",
        "scenario": "deteriorating",
        "follow_up": "2026-08-25",
        "visits": [
            {"date": "2026-04-10", "risk": 0.38, "status": "stunting", "severity": "mild", "progress": "baseline"},
            {"date": "2026-05-12", "risk": 0.47, "status": "stunting", "severity": "moderate", "progress": "deteriorating"},
            {"date": "2026-06-14", "risk": 0.62, "status": "stunting", "severity": "moderate", "progress": "deteriorating"},
            {"date": "2026-07-16", "risk": 0.71, "status": "wasting", "severity": "moderate", "progress": "deteriorating"},
        ],
    },
    {
        "pid": "C-1003",
        "sex": "male",
        "dob": "2024-06-20",
        "facility": "CCHC-04",
        "scenario": "stable",
        "follow_up": "2026-09-10",
        "visits": [
            {"date": "2026-04-01", "risk": 0.22, "status": "normal", "severity": "none", "progress": "baseline"},
            {"date": "2026-05-02", "risk": 0.21, "status": "normal", "severity": "none", "progress": "stable"},
            {"date": "2026-06-03", "risk": 0.23, "status": "normal", "severity": "none", "progress": "stable"},
        ],
    },
    {
        "pid": "C-1004",
        "sex": "female",
        "dob": "2024-12-01",
        "facility": "CCHC-04",
        "scenario": "missed",
        "follow_up": "2026-07-01",
        "overdue": True,
        "visits": [
            {"date": "2026-03-20", "risk": 0.55, "status": "underweight", "severity": "moderate", "progress": "baseline"},
            {"date": "2026-04-22", "risk": 0.52, "status": "underweight", "severity": "moderate", "progress": "stable"},
            {"date": "2026-05-24", "risk": 0.50, "status": "underweight", "severity": "moderate", "progress": "stagnating"},
        ],
    },
    {
        "pid": "C-1005",
        "sex": "male",
        "dob": "2025-03-08",
        "facility": "CCHC-04",
        "scenario": "relapse",
        "follow_up": "2026-09-05",
        "visits": [
            {"date": "2026-02-01", "risk": 0.78, "status": "wasting", "severity": "severe", "progress": "baseline"},
            {"date": "2026-03-05", "risk": 0.49, "status": "wasting", "severity": "moderate", "progress": "improving"},
            {"date": "2026-04-08", "risk": 0.33, "status": "underweight", "severity": "mild", "progress": "improving"},
            {"date": "2026-06-12", "risk": 0.58, "status": "wasting", "severity": "moderate", "progress": "deteriorating"},
        ],
    },
    {
        "pid": "C-1006",
        "sex": "female",
        "dob": "2024-08-14",
        "facility": "KMCC-01",
        "scenario": "improving",
        "follow_up": "2026-09-12",
        "visits": [
            {"date": "2026-02-10", "risk": 0.66, "status": "stunting", "severity": "moderate", "progress": "baseline"},
            {"date": "2026-03-12", "risk": 0.51, "status": "stunting", "severity": "mild", "progress": "improving"},
            {"date": "2026-04-14", "risk": 0.39, "status": "stunting", "severity": "mild", "progress": "improving"},
            {"date": "2026-05-16", "risk": 0.30, "status": "normal", "severity": "none", "progress": "improving"},
        ],
    },
    {
        "pid": "C-1007",
        "sex": "male",
        "dob": "2025-04-22",
        "facility": "KMCC-01",
        "scenario": "improving",
        "follow_up": "2026-09-08",
        "visits": [
            {"date": "2026-05-01", "risk": 0.88, "status": "wasting", "severity": "severe", "progress": "baseline"},
            {"date": "2026-06-02", "risk": 0.70, "status": "wasting", "severity": "moderate", "progress": "improving"},
            {"date": "2026-07-04", "risk": 0.54, "status": "wasting", "severity": "moderate", "progress": "improving"},
        ],
    },
    {
        "pid": "C-1008",
        "sex": "female",
        "dob": "2024-09-30",
        "facility": "KMCC-01",
        "scenario": "stagnation",
        "follow_up": "2026-09-02",
        "visits": [
            {"date": "2026-03-08", "risk": 0.57, "status": "underweight", "severity": "moderate", "progress": "baseline"},
            {"date": "2026-04-10", "risk": 0.56, "status": "underweight", "severity": "moderate", "progress": "stable"},
            {"date": "2026-05-12", "risk": 0.55, "status": "underweight", "severity": "moderate", "progress": "stagnating"},
            {"date": "2026-06-14", "risk": 0.54, "status": "underweight", "severity": "moderate", "progress": "stagnating"},
        ],
    },
    {
        "pid": "C-1009",
        "sex": "male",
        "dob": "2025-05-05",
        "facility": "GCNU-02",
        "scenario": "stable",
        "follow_up": "2026-09-20",
        "visits": [
            {"date": "2026-04-20", "risk": 0.18, "status": "normal", "severity": "none", "progress": "baseline"},
            {"date": "2026-05-22", "risk": 0.17, "status": "normal", "severity": "none", "progress": "stable"},
            {"date": "2026-06-24", "risk": 0.19, "status": "normal", "severity": "none", "progress": "stable"},
            {"date": "2026-07-26", "risk": 0.16, "status": "normal", "severity": "none", "progress": "stable"},
        ],
    },
    {
        "pid": "C-1010",
        "sex": "female",
        "dob": "2024-10-11",
        "facility": "GCNU-02",
        "scenario": "deteriorating",
        "follow_up": "2026-08-28",
        "visits": [
            {"date": "2026-03-03", "risk": 0.44, "status": "wasting", "severity": "mild", "progress": "baseline"},
            {"date": "2026-04-05", "risk": 0.53, "status": "wasting", "severity": "moderate", "progress": "deteriorating"},
            {"date": "2026-05-07", "risk": 0.67, "status": "wasting", "severity": "moderate", "progress": "deteriorating"},
        ],
    },
    {
        "pid": "C-1011",
        "sex": "male",
        "dob": "2025-06-18",
        "facility": "CCHC-04",
        "scenario": "stagnation",
        "follow_up": "2026-09-18",
        "visits": [
            {"date": "2026-04-18", "risk": 0.69, "status": "wasting", "severity": "moderate", "progress": "baseline"},
            {"date": "2026-05-20", "risk": 0.48, "status": "underweight", "severity": "mild", "progress": "improving"},
            {"date": "2026-06-22", "risk": 0.47, "status": "underweight", "severity": "mild", "progress": "stagnating"},
            {"date": "2026-07-24", "risk": 0.46, "status": "underweight", "severity": "mild", "progress": "stagnating"},
        ],
    },
    {
        "pid": "C-1012",
        "sex": "female",
        "dob": "2024-07-07",
        "facility": "KMCC-01",
        "scenario": "missed",
        "follow_up": "2026-06-30",
        "overdue": True,
        "visits": [
            {"date": "2026-02-28", "risk": 0.81, "status": "wasting", "severity": "severe", "progress": "baseline"},
            {"date": "2026-04-01", "risk": 0.76, "status": "wasting", "severity": "severe", "progress": "stable"},
            {"date": "2026-05-03", "risk": 0.73, "status": "wasting", "severity": "moderate", "progress": "stable"},
        ],
    },
    {
        "pid": "C-1013",
        "sex": "male",
        "dob": "2025-02-02",
        "facility": "GCNU-02",
        "scenario": "improving",
        "follow_up": "2026-09-14",
        "visits": [
            {"date": "2026-03-14", "risk": 0.60, "status": "underweight", "severity": "moderate", "progress": "baseline"},
            {"date": "2026-04-16", "risk": 0.49, "status": "underweight", "severity": "mild", "progress": "improving"},
            {"date": "2026-05-18", "risk": 0.37, "status": "normal", "severity": "none", "progress": "improving"},
            {"date": "2026-06-20", "risk": 0.29, "status": "normal", "severity": "none", "progress": "improving"},
            {"date": "2026-07-22", "risk": 0.24, "status": "normal", "severity": "none", "progress": "improving"},
        ],
    },
    {
        "pid": "C-1014",
        "sex": "female",
        "dob": "2025-07-01",
        "facility": "CCHC-04",
        "scenario": "baseline",
        "follow_up": "2026-09-19",
        "visits": [
            {"date": "2026-06-01", "risk": 0.64, "status": "wasting", "severity": "moderate", "progress": "baseline"},
            {"date": "2026-07-04", "risk": 0.58, "status": "wasting", "severity": "moderate", "progress": "improving"},
            {"date": "2026-08-06", "risk": 0.57, "status": "wasting", "severity": "moderate", "progress": "stagnating"},
        ],
    },
]


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def _embedding(pid: str, visit_number: int, risk: float, dim: int = 128) -> list[float]:
    seed = sum(ord(c) for c in pid) + visit_number * 17
    vec = []
    for i in range(dim):
        vec.append(round(((seed * (i + 3)) % 1000) / 1000.0 - 0.5 + (1 - risk) * 0.2, 4))
    return vec


def _measurements(sex: str, age: float, risk: float) -> dict:
    base_w = 9.5 if sex == "female" else 10.0
    weight = round(base_w + age * 0.12 - risk * 3.2, 2)
    height = round(70 + age * 0.7 - risk * 4, 1)
    muac = round(14.5 - risk * 4.5, 1)
    return {"weight_kg": max(4.0, weight), "height_cm": max(55.0, height), "muac_cm": max(9.0, muac), "age_months": age}


def seed() -> None:
    db = SessionLocal()
    try:
        if db.scalar(select(User).limit(1)):
            print("Seed skipped — data already present")
            return
        directory = json.loads((CONTRACTS / "demo_directory.json").read_text())
        orgs = {}
        for item in directory["organizations"]:
            org = Organization(name=item["name"], code=item["code"], type=OrganizationType(item["type"]), status=EntityStatus.ACTIVE)
            db.add(org)
            db.flush()
            orgs[item["code"]] = org
        facs = {}
        for item in directory["facilities"]:
            fac = Facility(
                organization_id=orgs[item["organization_code"]].id,
                name=item["name"],
                code=item["code"],
                district=item["district"],
                type=FacilityType(item["type"]),
                status=EntityStatus.ACTIVE,
            )
            db.add(fac)
            db.flush()
            facs[item["code"]] = fac
        users = {}
        for item in directory["users"]:
            user = User(
                facility_id=facs[item["facility_code"]].id,
                email=item["email"],
                password_hash=hash_password(DEMO_PASSWORD),
                full_name=item["full_name"],
                role=UserRole(item["role"]),
                status=UserStatus.ACTIVE,
            )
            db.add(user)
            db.flush()
            users[item["email"]] = user

        model = ModelVersion(
            model_key="MCA",
            version="2026-001",
            architecture="multimodal_cross_attention",
            feature_schema_version="fs-2026-001",
            label_schema_version="dev-2026-001",
            training_dataset_version="synthetic-demo-001",
            calibration_version="demo-temp-v1",
            embedding_dimension=128,
            embedding_space_id="mca-demo-space-v1",
            status=ModelStatus.ACTIVE,
            is_demo=True,
            activated_at=datetime.now(UTC),
            notes="DEMO MODEL — NOT FOR CLINICAL USE. Deterministic demonstration adapter.",
        )
        db.add(model)
        db.flush()
        policy_cfg = load_clinical_policy()
        policy_row = ClinicalPolicyVersion(
            policy_key=policy_cfg.policy_id,
            stagnation_threshold=policy_cfg.stagnation_threshold,
            consecutive_visits=policy_cfg.consecutive_followups,
            deterioration_delta=policy_cfg.deterioration_delta,
            overdue_grace_days=policy_cfg.overdue_grace_days,
            relapse_prior_improvement=policy_cfg.relapse_prior_improvement,
            relapse_increase=policy_cfg.relapse_increase,
            default_followup_days=policy_cfg.default_followup_days,
            status="active",
            notes="Research / Demo Configuration",
            payload={"disclaimer": policy_cfg.disclaimer},
        )
        db.add(policy_row)

        recorder = users["phm@demo.local"]
        lookup = {}
        for case in CASES:
            fac = facs[case["facility"]]
            dob = date.fromisoformat(case["dob"])
            child = Child(
                facility_id=fac.id,
                pseudonymous_id=case["pid"],
                date_of_birth=dob,
                sex=Sex(case["sex"]),
                status=EntityStatus.ACTIVE,
                responsible_team=case.get("team", fac.name),
                registered_by=recorder.id,
            )
            db.add(child)
            db.flush()
            db.add(Caregiver(child_id=child.id, kinship="mother", display_name=None))
            previous_pred = None
            baseline_pred = None
            consecutive = 0
            predicted_visits = []
            for idx, spec in enumerate(case["visits"]):
                visit_date = _dt(spec["date"])
                age = (visit_date.date().year - dob.year) * 12 + visit_date.date().month - dob.month
                meas = _measurements(case["sex"], float(age), spec["risk"])
                visit = Visit(
                    child_id=child.id,
                    facility_id=fac.id,
                    visit_number=idx,
                    visit_date=visit_date,
                    visit_type=VisitType.ROUTINE if idx == 0 else VisitType.FOLLOW_UP,
                    scheduled=True,
                    recorded_by=recorder.id,
                    model_version_id=model.id,
                    status=VisitStatus.PREDICTED,
                    confirmation_attested=True,
                    data_quality={"complete": True, "optional_missing": 1, "synthetic": True},
                )
                db.add(visit)
                db.flush()
                db.add(
                    AnthropometricRecord(
                        visit_id=visit.id,
                        age_months=meas["age_months"],
                        sex=Sex(case["sex"]),
                        height_cm=meas["height_cm"],
                        weight_kg=meas["weight_kg"],
                        muac_cm=meas["muac_cm"],
                        birth_weight_kg=2.7 if case["sex"] == "female" else 2.9,
                    )
                )
                db.add(
                    SocioeconomicRecord(
                        visit_id=visit.id,
                        wealth_proxy="second",
                        maternal_education="secondary",
                        paternal_education="primary",
                        maternal_employment="home",
                        household_size=5,
                        geographical_area=fac.district.lower(),
                        drinking_water="piped",
                        sanitation="improved",
                    )
                )
                db.add(
                    DietaryRecord(
                        visit_id=visit.id,
                        breastfeeding_status="continued" if age < 18 else "stopped",
                        complementary_feeding=age >= 6,
                        dietary_diversity_score=3 if spec["risk"] > 0.5 else 5,
                        meal_frequency=3,
                        food_groups=["grains", "dairy"] if spec["risk"] > 0.5 else ["grains", "dairy", "legumes", "flesh"],
                        micronutrient_supplementation=True,
                    )
                )
                db.add(
                    MaternalChildHealthRecord(
                        visit_id=visit.id,
                        maternal_bmi=20.5,
                        gestational_age_weeks=38,
                        immunization_uptodate=True,
                        vitamin_a=True,
                        recent_diarrhoea=spec["risk"] > 0.7,
                        recent_respiratory_illness=False,
                        recent_hospitalization=spec["risk"] > 0.8,
                    )
                )
                status_probs = {k: 0.05 for k in ("normal", "stunting", "wasting", "underweight")}
                status_probs[spec["status"]] = max(0.55, spec["risk"])
                pred = Prediction(
                    visit_id=visit.id,
                    model_version_id=model.id,
                    run_number=1,
                    is_active=True,
                    mode=PredictionMode.DEMO,
                    status_prediction=spec["status"],
                    severity_prediction=spec["severity"],
                    raw_probabilities={"status": status_probs, "risk": spec["risk"] + 0.03},
                    calibrated_probabilities={"status": status_probs, "risk": spec["risk"]},
                    primary_risk_score=spec["risk"],
                    confidence="moderate",
                    inference_ms=12.0 + idx,
                    input_hash=f"seed-{case['pid']}-{idx}",
                    feature_schema_version="fs-2026-001",
                    calibration_version="demo-temp-v1",
                )
                db.add(pred)
                db.flush()
                emb = _embedding(case["pid"], idx, spec["risk"])
                x, y = _project(emb)
                db.add(
                    LatentEmbedding(
                        visit_id=visit.id,
                        prediction_id=pred.id,
                        model_version_id=model.id,
                        embedding_space_id=model.embedding_space_id,
                        embedding_dimension=128,
                        embedding=emb,
                        projection_x=x,
                        projection_y=y,
                        projection_version="pca-demo-v1",
                    )
                )
                lookup[(case["pid"], idx)] = {
                    "status": spec["status"],
                    "severity": spec["severity"],
                    "risk_score": spec["risk"],
                    "latent_embedding": emb,
                }
                months = None
                months_b = None
                if previous_pred is not None:
                    months = elapsed_months(predicted_visits[-1].visit_date, visit.visit_date)
                    months_b = elapsed_months(predicted_visits[0].visit_date, visit.visit_date)
                if spec["progress"] in {"stagnating", "stable"}:
                    consecutive += 1
                else:
                    consecutive = 0 if spec["progress"] != "baseline" else 0
                evaluation = classify_progress(
                    is_baseline=idx == 0,
                    previous_risk=previous_pred.primary_risk_score if previous_pred else None,
                    current_risk=pred.primary_risk_score,
                    baseline_risk=baseline_pred.primary_risk_score if baseline_pred else pred.primary_risk_score,
                    months=months,
                    months_from_baseline=months_b,
                    stagnation_threshold=policy_cfg.stagnation_threshold,
                    deterioration_delta=policy_cfg.deterioration_delta,
                    consecutive_near_zero=consecutive,
                    consecutive_required=policy_cfg.consecutive_followups,
                    model_compatible=True,
                )
                # Honour the designed demo scenario labels for the canonical cases.
                state = ProgressState(spec["progress"])
                metric = TrajectoryMetric(
                    child_id=child.id,
                    from_visit_id=predicted_visits[-1].id if predicted_visits else None,
                    to_visit_id=visit.id,
                    baseline_visit_id=predicted_visits[0].id if predicted_visits else visit.id,
                    risk_velocity=evaluation.risk_velocity,
                    baseline_recovery_rate=evaluation.baseline_recovery_rate,
                    elapsed_days=int((months or 0) * 30.4375) if months else None,
                    elapsed_months=evaluation.elapsed_months,
                    previous_risk=previous_pred.primary_risk_score if previous_pred else None,
                    current_risk=pred.primary_risk_score,
                    progress_state=state,
                    model_compatible=True,
                )
                db.add(metric)
                db.flush()
                evaluation.progress_state = state
                _maybe_create_alerts(
                    db, child, visit, pred, previous_pred, baseline_pred or pred, evaluation, policy_cfg, consecutive
                )
                predicted_visits.append(visit)
                if baseline_pred is None:
                    baseline_pred = pred
                previous_pred = pred

            follow_date = date.fromisoformat(case["follow_up"])
            status = FollowUpStatus.OVERDUE if case.get("overdue") else FollowUpStatus.SCHEDULED
            db.add(
                FollowUpSchedule(
                    child_id=child.id,
                    facility_id=fac.id,
                    expected_date=follow_date,
                    interval_days=30,
                    responsible_user_id=recorder.id,
                    status=status,
                )
            )
            if case.get("overdue") or case["pid"] == "C-1042":
                from app.models.enums import AlertType
                from app.models.operations import Alert
                from app.services.alerts import event_window_key, severity_for
                from app.models.enums import AlertStatus

                if case.get("overdue"):
                    key = event_window_key(str(child.id), AlertType.MISSED_FOLLOW_UP, None, extra="seed")
                    db.add(
                        Alert(
                            child_id=child.id,
                            facility_id=fac.id,
                            type=AlertType.MISSED_FOLLOW_UP,
                            severity=severity_for(AlertType.MISSED_FOLLOW_UP, policy_cfg),
                            status=AlertStatus.OPEN,
                            message="Follow-up overdue",
                            trigger_value={"disclaimer": policy_cfg.disclaimer, "expected_date": case["follow_up"]},
                            threshold_version=policy_cfg.policy_id,
                            event_window_key=key,
                        )
                    )
                if case["pid"] == "C-1042":
                    key = event_window_key(str(child.id), AlertType.STAGNATION, str(predicted_visits[-1].id), extra="seed")
                    db.add(
                        Alert(
                            child_id=child.id,
                            facility_id=fac.id,
                            type=AlertType.STAGNATION,
                            severity=severity_for(AlertType.STAGNATION, policy_cfg),
                            status=AlertStatus.OPEN,
                            message="Progress stagnation detected",
                            trigger_value={
                                "previous_risk": 0.61,
                                "current_risk": 0.59,
                                "risk_velocity": 0.02,
                                "disclaimer": "Research / Demo Configuration",
                            },
                            threshold_version=policy_cfg.policy_id,
                            event_window_key=key,
                        )
                    )

        db.commit()
        try:
            (CONTRACTS / "demo_cases.json").write_text(json.dumps({f"{k[0]}:{k[1]}": v for k, v in lookup.items()}, indent=2))
        except OSError:
            pass
        print(f"Seed complete: {len(CASES)} children, demo password is development-only.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
