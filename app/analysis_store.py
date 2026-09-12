"""AI analiz geçmişi — PostgreSQL/SQLite'taki analysis_history tablosu."""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.project import AnalysisHistory


def push_analysis(db: Session, result: dict, project_id: int | None = None) -> dict:
    title = str(result.get("title") or result.get("question") or "AI Analizi")[:300]
    row = AnalysisHistory(
        question=str(result.get("question") or ""),
        title=title,
        risk_level=str(result.get("risk_level") or "Orta"),
        summary=str(result.get("summary") or "")[:2000],
        payload_json=json.dumps(result, ensure_ascii=False, default=str),
        project_id=project_id if project_id is not None else result.get("project_id"),
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _row_to_recent(row)


def list_recent_analyses(
    db: Session, limit: int = 10, project_id: int | None = None
) -> list[dict]:
    q = db.query(AnalysisHistory).order_by(AnalysisHistory.created_at.desc())
    if project_id is not None:
        q = q.filter(AnalysisHistory.project_id == project_id)
    rows = q.limit(limit).all()
    return [_row_to_recent(r) for r in rows]


def _row_to_recent(row: AnalysisHistory) -> dict:
    return {
        "id": row.id,
        "question": row.question,
        "title": row.title or row.question or "AI Analizi",
        "risk_level": row.risk_level,
        "summary": row.summary,
        "project_id": row.project_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
