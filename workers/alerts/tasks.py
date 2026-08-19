from __future__ import annotations

import sys
from pathlib import Path

from workers.alerts.celery_app import celery_app

API_ROOT = Path("/app") if Path("/app/app").exists() else Path(__file__).resolve().parents[2] / "services" / "api"
sys.path.insert(0, str(API_ROOT))


@celery_app.task(name="workers.alerts.tasks.evaluate_missed_followups_task")
def evaluate_missed_followups_task() -> int:
    from app.core.db import SessionLocal
    from app.services.prediction import evaluate_missed_followups

    db = SessionLocal()
    try:
        return evaluate_missed_followups(db)
    finally:
        db.close()
