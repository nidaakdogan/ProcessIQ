from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import build_services, compute_data_last_updated

router = APIRouter(prefix="/api", tags=["data"])


@router.get("/last-updated")
def last_updated(
    project_id: int | None = None,
    scope: str = Query("all", description="all|requirements|tasks|commits|tests|bugs|releases|projects|process|analysis"),
    db: Session = Depends(get_db),
):
    return {
        "last_updated": compute_data_last_updated(db, project_id=project_id, scope=scope),
        "scope": scope,
        "project_id": project_id,
    }


@router.get("/dashboard")
def dashboard(
    project_id: int | None = None,
    db: Session = Depends(get_db),
):
    return build_services(db)["projects"].get_dashboard_metrics(project_id=project_id)


@router.get("/projects")
def list_projects(
    status: str | None = None,
    is_risky: bool | None = None,
    db: Session = Depends(get_db),
):
    return build_services(db)["projects"].get_projects(status=status, is_risky=is_risky)


@router.get("/projects/{project_id}/summary")
def project_summary(project_id: int, db: Session = Depends(get_db)):
    return build_services(db)["projects"].get_project_summary(project_id=project_id)


@router.get("/requirements")
def list_requirements(
    project_id: int | None = None,
    status: str | None = None,
    priority: str | None = None,
    limit: int = Query(500, le=2000),
    db: Session = Depends(get_db),
):
    return build_services(db)["requirements"].get_requirements(
        project_id=project_id, status=status, priority=priority, limit=limit
    )


@router.get("/tasks")
def list_tasks(
    project_id: int | None = None,
    status: str | None = None,
    sprint: str | None = None,
    requirement_id: int | None = None,
    updated_from: str | None = None,
    updated_to: str | None = None,
    is_delayed: bool | None = None,
    is_overrun: bool | None = None,
    req_status: str | None = None,
    has_failed_test: bool | None = None,
    limit: int = Query(500, le=2000),
    db: Session = Depends(get_db),
):
    from datetime import datetime

    def _parse(d: str | None):
        if not d:
            return None
        return datetime.fromisoformat(d)

    return build_services(db)["tasks"].get_tasks(
        project_id=project_id,
        status=status,
        sprint=sprint,
        requirement_id=requirement_id,
        updated_from=_parse(updated_from),
        updated_to=_parse(updated_to),
        is_delayed=is_delayed,
        is_overrun=is_overrun,
        req_status=req_status,
        has_failed_test=has_failed_test,
        limit=limit,
    )


@router.get("/commits")
def list_commits(
    project_id: int | None = None,
    requirement_id: int | None = None,
    since: str | None = None,
    limit: int = Query(1000, le=2000),
    db: Session = Depends(get_db),
):
    from datetime import datetime

    since_dt = datetime.fromisoformat(since.replace("Z", "+00:00")) if since else None
    return build_services(db)["commits"].get_commits(
        project_id=project_id,
        requirement_id=requirement_id,
        since=since_dt,
        limit=limit,
    )


@router.get("/tests")
def list_tests(
    project_id: int | None = None,
    result: str | None = None,
    requirement_id: int | None = None,
    executed_from: str | None = None,
    executed_to: str | None = None,
    limit: int = Query(500, le=2000),
    db: Session = Depends(get_db),
):
    from datetime import datetime

    def _parse(d: str | None):
        if not d:
            return None
        return datetime.fromisoformat(d)

    return build_services(db)["tests"].get_tests(
        project_id=project_id,
        result=result,
        requirement_id=requirement_id,
        executed_from=_parse(executed_from),
        executed_to=_parse(executed_to),
        limit=limit,
    )


@router.get("/bugs")
def list_bugs(
    project_id: int | None = None,
    status: str | None = None,
    priority: str | None = None,
    severity: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    limit: int = Query(500, le=2000),
    db: Session = Depends(get_db),
):
    from datetime import datetime

    def _parse(d: str | None):
        if not d:
            return None
        return datetime.fromisoformat(d)

    return build_services(db)["bugs"].get_bugs(
        project_id=project_id,
        status=status,
        priority=priority,
        severity=severity,
        created_from=_parse(created_from),
        created_to=_parse(created_to),
        limit=limit,
    )


@router.get("/releases")
def list_releases(
    project_id: int | None = None,
    status: str | None = None,
    version: str | None = None,
    is_risky: bool | None = None,
    is_active: bool | None = None,
    limit: int = Query(200, le=500),
    db: Session = Depends(get_db),
):
    return build_services(db)["releases"].get_releases(
        project_id=project_id,
        status=status,
        version=version,
        is_risky=is_risky,
        is_active=is_active,
        limit=limit,
    )


@router.get("/process-chains")
def process_chains(
    limit: int = Query(12, le=30),
    project_id: int | None = None,
    db: Session = Depends(get_db),
):
    return build_services(db)["projects"].get_process_chains(
        limit=limit, project_id=project_id
    )
