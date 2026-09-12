from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import Base, engine
from app.api.routes import router as data_router
from app.api.analysis import router as analysis_router
from app.api.notifications import router as notifications_router
from app.api.executive_summary import router as executive_summary_router
import app.models  # noqa: F401 — register all ORM tables for create_all

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(data_router)
app.include_router(analysis_router)
app.include_router(notifications_router)
app.include_router(executive_summary_router)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    # SQLite demo: create_all yeni kolon eklemez — analysis_history.title uyumu
    from sqlalchemy import text, inspect

    try:
        insp = inspect(engine)
        if "analysis_history" in insp.get_table_names():
            cols = {c["name"] for c in insp.get_columns("analysis_history")}
            if "title" not in cols:
                with engine.begin() as conn:
                    conn.execute(
                        text(
                            "ALTER TABLE analysis_history ADD COLUMN title VARCHAR(300) DEFAULT ''"
                        )
                    )
            if "project_id" not in cols:
                with engine.begin() as conn:
                    conn.execute(
                        text("ALTER TABLE analysis_history ADD COLUMN project_id INTEGER")
                    )
        if "requirements" in insp.get_table_names():
            req_cols = {c["name"] for c in insp.get_columns("requirements")}
            if "release_id" not in req_cols:
                with engine.begin() as conn:
                    conn.execute(
                        text("ALTER TABLE requirements ADD COLUMN release_id INTEGER")
                    )
        for table in ("projects", "releases"):
            if table not in insp.get_table_names():
                continue
            cols = {c["name"] for c in insp.get_columns(table)}
            if "updated_at" not in cols:
                with engine.begin() as conn:
                    conn.execute(
                        text(
                            f"ALTER TABLE {table} ADD COLUMN updated_at DATETIME"
                        )
                    )
                    conn.execute(
                        text(
                            f"UPDATE {table} SET updated_at = COALESCE(created_at, CURRENT_TIMESTAMP) "
                            f"WHERE updated_at IS NULL"
                        )
                    )
    except Exception:
        pass


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.app_name}
