"""Uçtan uca veri tutarlılığı denetimi — Dashboard / listeler / zincir / AI KPI."""
from __future__ import annotations

from datetime import datetime

from app.database import SessionLocal
from app.services import build_services
from app.models import Requirement, Task, Commit, TestCase, Bug


def check(name: str, a, b, errors: list[str]) -> None:
    ok = a == b
    mark = "OK" if ok else "FAIL"
    print(f"  {mark} {name}: {a} vs {b}")
    if not ok:
        errors.append(f"{name}: {a} != {b}")


def main() -> int:
    db = SessionLocal()
    svc = build_services(db)
    errors: list[str] = []

    print("=== Dashboard KPI vs listeler ===")
    d = svc["projects"].get_dashboard_metrics()
    c = d["cards"]
    ch = d["charts"]
    check("failed_tests", c["failed_tests"], len(svc["tests"].get_tests(result="failed", limit=2000)), errors)
    check("failed chart", c["failed_tests"], ch["test_counts"]["failed"], errors)
    check(
        "critical_bugs",
        c["critical_bugs"],
        len(svc["bugs"].get_bugs(severity="critical", status="active", limit=2000)),
        errors,
    )
    check(
        "delayed_tasks",
        c["delayed_tasks"],
        len(svc["tasks"].get_tasks(is_delayed=True, limit=2000)),
        errors,
    )
    check(
        "risky_releases",
        c["risky_releases"],
        len(svc["releases"].get_releases(is_risky=True, limit=500)),
        errors,
    )
    high = next(x["count"] for x in ch["release_risk_distribution"] if x["label"] == "Yüksek")
    check("chart Yuksek vs risky KPI", high, c["risky_releases"], errors)
    check("not_released sum", ch["release_counts"]["not_released"], sum(x["count"] for x in ch["release_risk_distribution"]), errors)
    check(
        "active_projects",
        c["active_projects"],
        len(svc["projects"].get_projects(status="active")),
        errors,
    )

    print("=== Projeler vs modul sayilari ===")
    for p in svc["projects"].get_projects():
        pid = p["id"]
        check(
            f"{p['code']} req",
            p["requirement_count"],
            len(svc["requirements"].get_requirements(project_id=pid, limit=500)),
            errors,
        )
        check(
            f"{p['code']} tasks",
            p["task_count"],
            len(svc["tasks"].get_tasks(project_id=pid, limit=2000)),
            errors,
        )
        check(
            f"{p['code']} tests",
            p["test_count"],
            len(svc["tests"].get_tests(project_id=pid, limit=2000)),
            errors,
        )
        check(
            f"{p['code']} open bugs",
            p["open_bugs"],
            len(svc["bugs"].get_bugs(project_id=pid, status="active", limit=2000)),
            errors,
        )

    print("=== SDLC zincir project_id butunlugu ===")
    bad = 0
    for req in db.query(Requirement).all():
        for t in req.tasks or []:
            if t.project_id != req.project_id:
                bad += 1
        for cmt in req.commits or []:
            if cmt.project_id != req.project_id:
                bad += 1
        for te in req.tests or []:
            if te.project_id != req.project_id:
                bad += 1
        for b in req.bugs or []:
            if b.project_id != req.project_id:
                bad += 1
            if b.test_id:
                te = db.get(TestCase, b.test_id)
                if te and te.requirement_id != req.id:
                    bad += 1
        if req.release_id and req.release and req.release.project_id != req.project_id:
            bad += 1
    check("cross-project links", 0, bad, errors)

    print("=== AI Ozeti verify penceresi ===")
    ins = ch.get("risk_trend_insight") or {}
    v = (ins.get("verify") or {}).get("tests") or {}
    if v.get("executed_from") and v.get("executed_to"):
        listed = svc["tests"].get_tests(
            result="failed",
            executed_from=datetime.fromisoformat(v["executed_from"]),
            executed_to=datetime.fromisoformat(v["executed_to"]),
            limit=2000,
        )
        check("insight failed verify", ins.get("failed_tests"), len(listed), errors)
        days = {(r.get("executed_at") or "")[:10] for r in listed}
        start_day = v["executed_from"][:10]
        check("insight single calendar day", {start_day}, days or {start_day}, errors)

    print("=== get_project_summary vs Dashboard kritik ===")
    for p in svc["projects"].get_projects():
        sm = svc["projects"].get_project_summary(project_id=p["id"])
        dash_p = svc["projects"].get_dashboard_metrics(project_id=p["id"])
        check(
            f"{p['code']} summary critical",
            sm["critical_bugs"],
            dash_p["cards"]["critical_bugs"],
            errors,
        )
        check(
            f"{p['code']} summary failed",
            sm["failed_tests"],
            dash_p["cards"]["failed_tests"],
            errors,
        )

    print("=== Proje filtreli dashboard ===")
    if svc["projects"].get_projects():
        pid = svc["projects"].get_projects()[0]["id"]
        dp = svc["projects"].get_dashboard_metrics(project_id=pid)
        check(
            "scoped failed",
            dp["cards"]["failed_tests"],
            len(svc["tests"].get_tests(result="failed", project_id=pid, limit=2000)),
            errors,
        )

    db.close()
    print()
    if errors:
        print(f"FAIL ({len(errors)}):")
        for e in errors:
            print(" -", e)
        return 1
    print("PASS - tum kontroller basarili")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
