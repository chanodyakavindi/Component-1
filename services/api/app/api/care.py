from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_permission
from app.models.enums import AuditAction, FollowUpStatus
from app.models.operations import ClinicalNote, FollowUpSchedule
from app.models.paediatric import Child
from app.schemas.common import FollowUpCreate, FollowUpPatch, NoteCreate
from app.security.rbac import assert_child_access, facility_scope_ids
from app.services.audit import write_audit

router = APIRouter(tags=["care"])


@router.post("/children/{child_id}/notes")
def add_note(child_id: UUID, body: NoteCreate, request: Request, db: Session = Depends(get_db), current=Depends(require_permission("note:write"))):
    child = db.get(Child, child_id)
    if not child:
        raise HTTPException(404, "Child not found")
    assert_child_access(current, child)
    note = ClinicalNote(child_id=child.id, visit_id=body.visit_id, author_id=current.id, body=body.body)
    db.add(note)
    write_audit(
        db,
        action=AuditAction.CLINICAL_NOTE_CREATED,
        resource_type="clinical_note",
        resource_id=str(child.id),
        user_id=current.id,
        role=current.role.value,
        facility_id=child.facility_id,
        ip=request.client.host if request.client else None,
        metadata={"not_used_for_ml": True},
    )
    db.flush()
    return {"id": str(note.id), "created_at": note.created_at.isoformat()}


@router.post("/children/{child_id}/follow-ups")
def create_follow_up(child_id: UUID, body: FollowUpCreate, request: Request, db: Session = Depends(get_db), current=Depends(require_permission("visit:write"))):
    child = db.get(Child, child_id)
    if not child:
        raise HTTPException(404, "Child not found")
    assert_child_access(current, child)
    row = FollowUpSchedule(
        child_id=child.id,
        facility_id=child.facility_id,
        expected_date=body.expected_date,
        interval_days=body.interval_days,
        responsible_user_id=body.responsible_user_id or current.id,
        status=FollowUpStatus.SCHEDULED,
        notes=body.notes,
    )
    db.add(row)
    write_audit(
        db,
        action=AuditAction.FOLLOW_UP_CHANGED,
        resource_type="follow_up",
        resource_id=str(child.id),
        user_id=current.id,
        role=current.role.value,
        facility_id=child.facility_id,
        ip=request.client.host if request.client else None,
    )
    db.flush()
    return {"id": str(row.id), "expected_date": row.expected_date.isoformat(), "status": row.status.value}


@router.get("/follow-ups")
def list_follow_ups(db: Session = Depends(get_db), current=Depends(require_permission("visit:read"))):
    stmt = select(FollowUpSchedule)
    scope = facility_scope_ids(current)
    if scope:
        stmt = stmt.where(FollowUpSchedule.facility_id.in_(scope))
    rows = db.scalars(stmt.order_by(FollowUpSchedule.expected_date).limit(200)).all()
    out = []
    for r in rows:
        child = db.get(Child, r.child_id)
        out.append(
            {
                "id": str(r.id),
                "child": child.pseudonymous_id if child else None,
                "child_id": str(r.child_id),
                "expected_date": r.expected_date.isoformat(),
                "status": r.status.value,
                "interval_days": r.interval_days,
            }
        )
    return {"items": out}


@router.patch("/follow-ups/{follow_up_id}")
def patch_follow_up(follow_up_id: UUID, body: FollowUpPatch, db: Session = Depends(get_db), current=Depends(require_permission("visit:write"))):
    row = db.get(FollowUpSchedule, follow_up_id)
    if not row:
        raise HTTPException(404, "Follow-up not found")
    if body.expected_date:
        row.expected_date = body.expected_date
        if body.status is None:
            row.status = FollowUpStatus.RESCHEDULED
    if body.status:
        row.status = FollowUpStatus(body.status)
    if body.notes is not None:
        row.notes = body.notes
    return {"ok": True, "status": row.status.value}
