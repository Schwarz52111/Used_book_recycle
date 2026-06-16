"""人工复核接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.review import service

router = APIRouter(prefix="/review", tags=["review"])


class ResolveRequest(BaseModel):
    action: str                 # approve | correct | reject
    new_price: float | None = None
    note: str = ""
    operator: str = ""


@router.get("/tasks")
def list_tasks(status: str = "pending", db: Session = Depends(get_db)):
    return service.list_tasks(db, status)


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    return service.summary(db)


@router.post("/tasks/{task_id}/resolve")
def resolve(task_id: int, req: ResolveRequest, db: Session = Depends(get_db)):
    try:
        task = service.resolve(db, task_id, req.action, req.new_price, req.note, req.operator)
    except service.ReviewError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": task.id, "status": task.status.value}
