from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.llm.executive_summary import generate_executive_summary

router = APIRouter(tags=["executive-summary"])


@router.get("/api/executive-summary")
@router.get("/api/executive-summary/")
def get_executive_summary(
    period: str = Query("week", description="today|week|month"),
    project_id: int | None = None,
    db: Session = Depends(get_db),
):
    if period not in ("today", "week", "month"):
        period = "week"
    return generate_executive_summary(db, period=period, project_id=project_id)  # type: ignore[arg-type]
