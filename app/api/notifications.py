from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.llm.notifications import generate_notifications

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
def list_notifications(
    project_id: int | None = None,
    category: str | None = Query(
        None,
        description="critical_risk|process_warning|performance|info|ai_suggestion",
    ),
    db: Session = Depends(get_db),
):
    payload = generate_notifications(db, project_id=project_id)
    items = payload["items"]
    if category:
        items = [n for n in items if n.get("category") == category]
    return {
        **payload,
        "count": len(items),
        "items": items,
    }
