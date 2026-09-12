from datetime import date, datetime, timedelta
from typing import Any
import re

from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from app.interfaces import (
    RequirementDataSource,
    TaskDataSource,
    CommitDataSource,
    TestDataSource,
    BugDataSource,
    ReleaseDataSource,
    ProjectDataSource,
)
from app.models import (
    Project,
    Requirement,
    Task,
    Commit,
    TestCase,
    Bug,
    Release,
    ProjectStatus,
    TaskStatus,
    TestResult,
    BugStatus,
    Priority,
    RequirementStatus,
    ReleaseStatus,
)
from app.metrics import (
    KPI_DEFINITIONS,
    compute_risk_index,
    is_bug_active,
    is_critical_active_bug,
    is_project_risky,
    is_release_active,
    is_release_risky,
    is_task_blocked,
    is_task_delayed,
    is_task_overrun,
    release_risk_band,
    risk_index_level,
)


def _enum_val(v):
    return v.value if hasattr(v, "value") else v


def _requirement_revision_count(r: Requirement) -> int:
    """Bağlı commit sayısı (gerçek ilişki) — değişen gereksinimlerde en az 1."""
    linked = len(r.commits) if r.commits else 0
    if r.status == RequirementStatus.CHANGED:
        return max(linked, 1)
    return linked


class PostgresRequirementService(RequirementDataSource):
    def __init__(self, db: Session):
        self.db = db

    def get_requirements(
        self,
        project_id: int | None = None,
        status: str | None = None,
        priority: str | None = None,
        updated_since: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        q = self.db.query(Requirement)
        if project_id:
            q = q.filter(Requirement.project_id == project_id)
        if status:
            q = q.filter(Requirement.status == status)
        if priority:
            q = q.filter(Requirement.priority == priority)
        if updated_since:
            q = q.filter(Requirement.updated_at >= updated_since)
        rows = q.order_by(Requirement.updated_at.desc()).limit(limit).all()
        return [
            {
                "id": r.id,
                "external_id": r.external_id,
                "title": _clean_record_title(r.title, r.module),
                "priority": _enum_val(r.priority),
                "status": _enum_val(r.status),
                "module": r.module,
                "project_id": r.project_id,
                **_project_fields(r.project),
                "release_id": r.release_id,
                "release_version": r.release.version if r.release else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                "revision_count": _requirement_revision_count(r),
            }
            for r in rows
        ]


class PostgresTaskService(TaskDataSource):
    def __init__(self, db: Session):
        self.db = db

    def get_tasks(
        self,
        project_id: int | None = None,
        status: str | None = None,
        sprint: str | None = None,
        requirement_id: int | None = None,
        updated_from: datetime | None = None,
        updated_to: datetime | None = None,
        is_delayed: bool | None = None,
        is_overrun: bool | None = None,
        req_status: str | None = None,
        has_failed_test: bool | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        q = self.db.query(Task)
        if project_id:
            q = q.filter(Task.project_id == project_id)
        if status:
            q = q.filter(Task.status == status)
        if sprint:
            q = q.filter(Task.sprint == sprint)
        if requirement_id:
            q = q.filter(Task.requirement_id == requirement_id)
        if updated_from:
            q = q.filter(Task.updated_at >= updated_from)
        if updated_to:
            q = q.filter(Task.updated_at < updated_to)
        # KPI filtreleri serialize sonrası uygulanır; limit en sonda kesilir
        rows = q.order_by(Task.updated_at.desc()).all()
        result = [
            {
                "id": t.id,
                "external_id": t.external_id,
                "title": _clean_record_title(t.title),
                "assignee": t.assignee,
                "status": _enum_val(t.status),
                "sprint": t.sprint,
                "estimated_hours": t.estimated_hours,
                "actual_hours": t.actual_hours,
                "delay_hours": (
                    round(t.actual_hours - t.estimated_hours, 1)
                    if t.actual_hours is not None and t.estimated_hours is not None
                    else None
                ),
                "project_id": t.project_id,
                **_project_fields(t.project),
                "requirement_id": t.requirement_id,
                "requirement_external_id": t.requirement.external_id if t.requirement else None,
                "is_delayed": is_task_delayed(
                    t.status, t.estimated_hours, t.actual_hours
                ),
                "is_overrun": is_task_overrun(
                    t.status, t.estimated_hours, t.actual_hours
                ),
                "requirement_status": (
                    _enum_val(t.requirement.status) if t.requirement else None
                ),
                "has_failed_test": bool(
                    t.requirement
                    and any(
                        x.result == TestResult.FAILED for x in (t.requirement.tests or [])
                    )
                ),
                "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            }
            for t in rows
        ]
        if is_delayed is not None:
            result = [r for r in result if bool(r["is_delayed"]) is is_delayed]
        if is_overrun is not None:
            result = [r for r in result if bool(r["is_overrun"]) is is_overrun]
        if req_status:
            result = [r for r in result if r.get("requirement_status") == req_status]
        if has_failed_test is not None:
            result = [
                r for r in result if bool(r.get("has_failed_test")) is has_failed_test
            ]
        return result[:limit]


class PostgresCommitService(CommitDataSource):
    def __init__(self, db: Session):
        self.db = db

    def get_commits(
        self,
        project_id: int | None = None,
        since: datetime | None = None,
        requirement_id: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        q = self.db.query(Commit)
        if project_id:
            q = q.filter(Commit.project_id == project_id)
        if since:
            q = q.filter(Commit.committed_at >= since)
        if requirement_id:
            q = q.filter(Commit.requirement_id == requirement_id)
        rows = q.order_by(Commit.committed_at.desc()).limit(limit).all()
        return [_serialize_commit(c) for c in rows]


def _commit_seed(c: Commit) -> int:
    try:
        return int(c.commit_hash[:8], 16)
    except (TypeError, ValueError):
        return c.id * 9973


def _display_branch(c: Commit) -> str:
    """Seed'deki ilişkili branch'i koru; yoksa gereksinim/modülden üret."""
    raw = (c.branch or "").strip()
    if raw and raw not in ("main", "develop"):
        return raw
    seed = _commit_seed(c)
    req = c.requirement.external_id.lower() if c.requirement else f"req-{(c.id % 90) + 1:03d}"
    module = (c.requirement.module or "core").lower().replace(" ", "-") if c.requirement else "core"
    options = [
        f"feature/{module}-{req}",
        f"bugfix/{module}-{req}",
        f"hotfix/{module}-security",
    ]
    return options[seed % len(options)]


def _localize_commit_message(raw: str) -> str:
    """Conventional commit öneklerini Türkçeleştir (feat/fix → Özellik/Düzeltme)."""
    m = re.match(
        r"^(feat|fix|chore|refactor|docs|test|hotfix|bugfix)\(([^)]+)\):\s*(.*)$",
        raw.strip(),
        re.IGNORECASE,
    )
    if not m:
        return raw
    kind = m.group(1).lower()
    module = m.group(2).replace("-", " ").strip()
    rest = m.group(3).strip()
    kind_tr = {
        "feat": "Özellik",
        "fix": "Düzeltme",
        "chore": "Bakım",
        "refactor": "Yeniden düzenleme",
        "docs": "Dokümantasyon",
        "test": "Test",
        "hotfix": "Acil düzeltme",
        "bugfix": "Hata düzeltme",
    }.get(kind, kind)
    module_tr = module[:1].upper() + module[1:] if module else module
    return f"{kind_tr} ({module_tr}): {rest}"


def _display_message(c: Commit) -> str:
    """Seed mesajını koru — rastgele yeniden yazma; İngilizce önekleri Türkçeleştir."""
    raw = (c.message or "").strip()
    if raw:
        return _localize_commit_message(raw)
    req = c.requirement.external_id if c.requirement else None
    task = c.task.external_id if c.task else None
    module = module_title(c)
    if task and req:
        return f"Özellik ({module}): {task} — {req}"
    if req:
        return f"Özellik ({module}): değişiklik — {req}"
    return f"Özellik ({module}): kod değişikliği"


def module_title(c: Commit) -> str:
    if c.requirement and c.requirement.module:
        return c.requirement.module
    return "modül"


def _serialize_commit(c: Commit) -> dict[str, Any]:
    seed = _commit_seed(c)
    files_changed = (seed % 17) + 1
    additions = (seed % 380) + 12
    deletions = (seed % 95) + 3
    branch = _display_branch(c)
    risk = "low"
    if files_changed >= 12 or additions + deletions >= 350:
        risk = "high"
    elif files_changed >= 6 or additions >= 160:
        risk = "medium"
    if "hotfix" in branch or "bugfix" in branch:
        risk = "high" if risk != "low" else "medium"
    if c.requirement:
        crit = sum(
            1
            for b in c.requirement.bugs
            if b.severity == Priority.CRITICAL
            and b.status in (BugStatus.OPEN, BugStatus.IN_PROGRESS)
        )
        if crit:
            risk = "high"

    return {
        "id": c.id,
        "commit_hash": c.commit_hash,
        "branch": branch,
        "developer": c.developer,
        "message": _display_message(c),
        "files_changed": files_changed,
        "additions": additions,
        "deletions": deletions,
        "risk_level": risk,
        "committed_at": c.committed_at.isoformat() if c.committed_at else None,
        "updated_at": c.committed_at.isoformat() if c.committed_at else None,
        "project_id": c.project_id,
        **_project_fields(c.project),
        "requirement_id": c.requirement_id,
        "requirement_external_id": c.requirement.external_id if c.requirement else None,
        "task_id": c.task_id,
        "task_external_id": c.task.external_id if c.task else None,
    }


class PostgresTestService(TestDataSource):
    def __init__(self, db: Session):
        self.db = db

    def get_tests(
        self,
        project_id: int | None = None,
        result: str | None = None,
        requirement_id: int | None = None,
        executed_from: datetime | None = None,
        executed_to: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        q = self.db.query(TestCase)
        if project_id:
            q = q.filter(TestCase.project_id == project_id)
        if result:
            q = q.filter(TestCase.result == result)
        if requirement_id:
            q = q.filter(TestCase.requirement_id == requirement_id)
        if executed_from:
            q = q.filter(TestCase.executed_at >= executed_from)
        if executed_to:
            q = q.filter(TestCase.executed_at < executed_to)
        rows = q.order_by(TestCase.executed_at.desc()).limit(limit).all()
        return [_serialize_test(t) for t in rows]


TEST_TITLE_POOL = [
    "Başarısız giriş denemesi kontrolü",
    "Ödeme doğrulama testi",
    "Kullanıcı yetki kontrolü",
    "Hesap bakiyesi tutarlılık kontrolü",
    "Oturum zaman aşımı senaryosu",
    "Kart limit aşımı doğrulaması",
    "Bildirim gönderim doğrulaması",
    "API kimlik doğrulama akışı",
    "Toplu transfer işlem testi",
    "Müşteri onboarding adım kontrolü",
    "Uyumluluk raporu doğrulaması",
    "Şifre sıfırlama akış testi",
    "Çok faktörlü doğrulama kontrolü",
    "İşlem iptal senaryosu",
    "Veri dışa aktarma doğrulaması",
    "Yetkisiz erişim engelleme testi",
    "Ödeme iade süreci kontrolü",
    "Hesap kilitleme senaryosu",
]

TEST_TYPES = ["Unit", "Integration", "System", "UAT"]
TEST_RUNNERS = [
    "Ayşe Yılmaz",
    "Mehmet Demir",
    "Zeynep Kaya",
    "Can Öztürk",
    "CI · jenkins-main",
    "CI · azure-pipelines",
    "CI · github-actions",
    "QA · nightly-regression",
]


def _serialize_test(t: TestCase) -> dict[str, Any]:
    seed = t.id * 7919
    test_type = TEST_TYPES[seed % len(TEST_TYPES)]
    # Unit hızlı, UAT daha yavaş
    duration_sec = {
        "Unit": 0.4 + (seed % 40) / 10,
        "Integration": 2.0 + (seed % 80) / 10,
        "System": 8.0 + (seed % 120) / 10,
        "UAT": 15.0 + (seed % 200) / 10,
    }[test_type]
    duration_sec = round(duration_sec, 1)
    title = TEST_TITLE_POOL[seed % len(TEST_TITLE_POOL)]
    if t.requirement and t.requirement.module:
        # Modüle göre hafif varyasyon
        module = t.requirement.module
        module_titles = {
            "Auth": "Başarısız giriş denemesi kontrolü",
            "Transfers": "Ödeme doğrulama testi",
            "Cards": "Kart limit aşımı doğrulaması",
            "Compliance": "Uyumluluk raporu doğrulaması",
            "Onboarding": "Müşteri onboarding adım kontrolü",
            "API Gateway": "API kimlik doğrulama akışı",
            "Accounts": "Hesap bakiyesi tutarlılık kontrolü",
            "Notifications": "Bildirim gönderim doğrulaması",
        }
        title = module_titles.get(module, title)
    runner = TEST_RUNNERS[seed % len(TEST_RUNNERS)]
    # Başarısız testlerde pipeline daha sık
    if _enum_val(t.result) == "failed" and seed % 3 == 0:
        runner = "CI · azure-pipelines"

    return {
        "id": t.id,
        "external_id": t.external_id,
        "title": title,
        "test_type": test_type,
        "duration_sec": duration_sec,
        "executed_by": runner,
        "result": _enum_val(t.result),
        "executed_at": t.executed_at.isoformat() if t.executed_at else None,
        "updated_at": t.executed_at.isoformat() if t.executed_at else None,
        "project_id": t.project_id,
        **_project_fields(t.project),
        "requirement_id": t.requirement_id,
        "requirement_external_id": t.requirement.external_id if t.requirement else None,
    }


class PostgresBugService(BugDataSource):
    def __init__(self, db: Session):
        self.db = db

    def get_bugs(
        self,
        project_id: int | None = None,
        status: str | None = None,
        priority: str | None = None,
        severity: str | None = None,
        requirement_id: int | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        q = self.db.query(Bug)
        if project_id:
            q = q.filter(Bug.project_id == project_id)
        if priority:
            q = q.filter(Bug.priority == priority)
        if severity:
            q = q.filter(Bug.severity == severity)
        if requirement_id:
            q = q.filter(Bug.requirement_id == requirement_id)
        if created_from:
            q = q.filter(Bug.created_at >= created_from)
        if created_to:
            q = q.filter(Bug.created_at < created_to)
        # Workflow filtreleri (UI) → DB durumları
        # "active" = Dashboard kritik hata KPI ile aynı (OPEN + IN_PROGRESS)
        if status:
            workflow_to_db = {
                "active": [BugStatus.OPEN, BugStatus.IN_PROGRESS],
                "open": [BugStatus.OPEN],
                "reviewing": [BugStatus.IN_PROGRESS],
                "in_development": [BugStatus.IN_PROGRESS],
                "in_test": [BugStatus.RESOLVED],
                "closed": [BugStatus.CLOSED],
                "resolved": [BugStatus.RESOLVED],
                "in_progress": [BugStatus.IN_PROGRESS],
            }
            db_statuses = workflow_to_db.get(status, [status])
            q = q.filter(Bug.status.in_(db_statuses))
        rows = q.order_by(Bug.updated_at.desc()).limit(limit).all()
        result = [_serialize_bug(b) for b in rows]
        # reviewing / in_development aynı DB status'undan geldiği için istemci filtresiyle daralt
        if status in ("reviewing", "in_development"):
            result = [r for r in result if r["status"] == status]
        return result


BUG_ASSIGNEES = [
    "Ayşe Yılmaz",
    "Mehmet Demir",
    "Zeynep Kaya",
    "Can Öztürk",
    "Elif Şahin",
    "Burak Arslan",
    "Deniz Çelik",
    "Selin Aydın",
]

BUG_TITLE_POOL = [
    "Ödeme sonrası bakiye güncellenmiyor",
    "Başarısız girişte oturum kilidi oluşmuyor",
    "Kart limiti aşıldığında uyarı gösterilmiyor",
    "Bildirimler gecikmeli iletiliyor",
    "Yetkisiz kullanıcı rapor ekranına erişebiliyor",
    "Toplu transferde kısmi kayıt oluşuyor",
    "Şifre sıfırlama bağlantısı süresi yanlış",
    "API 500 hatası: hesap özeti servisi",
    "Mobil uygulamada oturum düşüyor",
    "Uyumluluk raporunda eksik alanlar",
    "İade işlemi çift kayıt oluşturuyor",
    "Onboarding adımında ilerleme kayboluyor",
]


def _bug_workflow_status(b: Bug) -> str:
    """Açık → İnceleniyor → Çözüm Geliştiriliyor → Testte → Kapatıldı"""
    raw = _enum_val(b.status)
    if raw == "open":
        return "open"
    if raw == "closed":
        return "closed"
    if raw == "resolved":
        return "in_test"
    # in_progress
    return "reviewing" if b.id % 2 == 0 else "in_development"


def _serialize_bug(b: Bug) -> dict[str, Any]:
    workflow = _bug_workflow_status(b)
    title = (b.title or "").strip()
    # Eski zayıf seed başlıklarını (REQ-xxx hatası) zenginleştir; yeni senaryo başlıklarını koru
    if not title or title.lower().endswith(" hatası") or (
        title.startswith("REQ-") and "—" in title
    ):
        title = BUG_TITLE_POOL[b.id % len(BUG_TITLE_POOL)]
    active = is_bug_active(b.status)
    return {
        "id": b.id,
        "external_id": b.external_id,
        "title": _clean_record_title(title),
        "priority": _enum_val(b.priority),
        "severity": _enum_val(b.severity),
        "status": workflow,
        "status_raw": _enum_val(b.status),
        "is_active": active,
        "assignee": BUG_ASSIGNEES[b.id % len(BUG_ASSIGNEES)],
        "created_at": b.created_at.isoformat() if b.created_at else None,
        "updated_at": b.updated_at.isoformat() if b.updated_at else None,
        "project_id": b.project_id,
        **_project_fields(b.project),
        "requirement_id": b.requirement_id,
        "requirement_external_id": b.requirement.external_id if b.requirement else None,
        "test_id": b.test_id,
        "test_external_id": b.test.external_id if b.test else None,
    }


class PostgresReleaseService(ReleaseDataSource):
    def __init__(self, db: Session):
        self.db = db

    def get_releases(
        self,
        project_id: int | None = None,
        status: str | None = None,
        version: str | None = None,
        is_risky: bool | None = None,
        is_active: bool | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        q = self.db.query(Release)
        if project_id:
            q = q.filter(Release.project_id == project_id)
        if status:
            q = q.filter(Release.status == status)
        if version:
            q = q.filter(Release.version.ilike(f"%{version}%"))
        rows = q.order_by(Release.release_date.desc().nullslast()).all()
        result = [_serialize_release(r) for r in rows]
        # is_active = henüz yayında değil (grafik kapsamı)
        if is_active is not None:
            result = [r for r in result if bool(r["is_active"]) is is_active]
        # is_risky = skor ≥70 ve henüz yayında değil (KPI)
        if is_risky is not None:
            result = [r for r in result if bool(r["is_risky"]) is is_risky]
        return result[:limit]


# Liste ekranlarında gösterilen proje kodları (= DB kodları)
PROJECT_SHORT_CODES = {
    "CRM-X": "CRM-X",
    "CORE-BANK": "CORE-BANK",
    "MOBILE-APP": "MOBILE-APP",
    "DATA-PLAT": "DATA-PLAT",
    "PAYMENTS": "PAYMENTS",
}

# Detay panelinde tam ad
PROJECT_DISPLAY_NAMES = {
    "CRM-X": "Customer 360 CRM",
    "CORE-BANK": "Core Banking Modernization",
    "MOBILE-APP": "Mobile Banking App",
    "DATA-PLAT": "Data Platform",
    "PAYMENTS": "Payment Gateway",
}

_PROJECT_CODE_RE = re.compile(
    r"\b(?:CRM-X|CORE-BANK|MOBILE-APP|DATA-PLAT|PAYMENTS)\b",
    re.IGNORECASE,
)

_MODULE_TITLE_TR = {
    "Auth": "Kimlik doğrulama gereksinimi",
    "Accounts": "Hesap yönetimi gereksinimi",
    "Transfers": "Transfer işlemleri gereksinimi",
    "Cards": "Kart işlemleri gereksinimi",
    "Notifications": "Bildirim yönetimi gereksinimi",
    "Reporting": "Raporlama gereksinimi",
    "Onboarding": "Müşteri onboarding gereksinimi",
    "Compliance": "Uyumluluk gereksinimi",
    "API Gateway": "API Gateway gereksinimi",
    "Batch": "Batch işleme gereksinimi",
}


def _project_fields(project) -> dict[str, Any]:
    if not project:
        return {"project_code": "—", "project_name": "—"}
    raw = project.code
    return {
        "project_code": PROJECT_SHORT_CODES.get(raw, raw),
        "project_name": PROJECT_DISPLAY_NAMES.get(raw, project.name),
    }


def _clean_record_title(title: str | None, module: str | None = None) -> str:
    """Başlıktan proje kodlarını çıkar; proje yalnızca Proje sütununda gösterilir."""
    if not title:
        return _MODULE_TITLE_TR.get(module or "", "Kayıt")
    t = title
    # "Modül — CODE gereksinimi N" → modül adı
    t = re.sub(
        r"\s*[—–-]\s*(?:CRM-X|CORE-BANK|MOBILE-APP|DATA-PLAT|PAYMENTS)\s*gereksinimi\s*\d*",
        "",
        t,
        flags=re.IGNORECASE,
    )
    t = _PROJECT_CODE_RE.sub("", t)
    t = re.sub(r"\s+", " ", t).strip(" —–-\t")
    if not t and module:
        return _MODULE_TITLE_TR.get(module, f"{module} gereksinimi")
    # Yalnızca modül adı kaldıysa anlamlı başlığa çevir
    if t in _MODULE_TITLE_TR:
        return _MODULE_TITLE_TR[t]
    if module and t.lower() in ("gereksinim", "gereksinimi"):
        return _MODULE_TITLE_TR.get(module, f"{module} gereksinimi")
    return t or _MODULE_TITLE_TR.get(module or "", "Gereksinim")


_MONTHS_TR = (
    "Ocak",
    "Şubat",
    "Mart",
    "Nisan",
    "Mayıs",
    "Haziran",
    "Temmuz",
    "Ağustos",
    "Eylül",
    "Ekim",
    "Kasım",
    "Aralık",
)


def _format_day_tr(dt: datetime) -> str:
    return f"{dt.day} {_MONTHS_TR[dt.month - 1]}"


def _join_tr(parts: list[str]) -> str:
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} ve {parts[1]}"
    return f"{', '.join(parts[:-1])} ve {parts[-1]}"


def _build_risk_trend_insight(risk_trend: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Zirve dilimindeki Risk Endeksi'ni yönetici dilinde açıklar (formül göstermeden)."""
    if not risk_trend:
        return None

    peak = max(risk_trend, key=lambda x: int(x.get("risk_index") or 0))
    peak_idx = risk_trend.index(peak)
    avg_risk = sum(int(x.get("risk_index") or 0) for x in risk_trend) / len(risk_trend)
    prev_risk = (
        int(risk_trend[peak_idx - 1].get("risk_index") or 0) if peak_idx > 0 else avg_risk
    )

    period_label = str(peak.get("period_label") or peak.get("period") or "")
    failed = int(peak.get("failed_tests") or 0)
    critical = int(peak.get("critical_bugs") or 0)
    delayed = int(peak.get("delayed_tasks") or 0)
    # Grafik ile aynı sayı — compute_risk_index tek kaynak
    peak_risk = compute_risk_index(failed, critical, delayed)
    level = risk_index_level(peak_risk)

    is_spike = peak_risk > 0 and (
        peak_risk >= avg_risk * 1.35
        or peak_risk >= prev_risk + 4
        or (
            peak_risk == max(int(x.get("risk_index") or 0) for x in risk_trend)
            and peak_risk > avg_risk
        )
    )

    period_start = peak.get("period_start")
    period_end = peak.get("period_end")

    if peak_risk <= 0 or not is_spike:
        return {
            "period": peak.get("period"),
            "period_label": period_label,
            "period_start": period_start,
            "period_end": period_end,
            "kind": "stable",
            "risk_index": peak_risk,
            "risk_level": risk_index_level(peak_risk),
            "text": (
                "Risk seviyesi son dönemde görece dengeli; belirgin bir ani artış gözlenmedi. "
                "Kalite ve teslim sinyalleri izlenmeye devam edilmeli."
            ),
            "failed_tests": failed,
            "critical_bugs": critical,
            "delayed_tasks": delayed,
        }

    drivers: list[str] = []
    if failed:
        drivers.append(f"{failed} başarısız test")
    if critical:
        drivers.append(f"{critical} açık kritik hata")
    if delayed:
        drivers.append(f"{delayed} geciken görev")

    if drivers:
        cause = _join_tr(drivers)
        text = (
            f"{period_label} tarihinde Risk Endeksi {peak_risk}'e yükseldi. "
            f"Artışın temel nedenleri {cause} olarak tespit edildi. "
            f"Bu göstergeler birlikte değerlendirildiğinde ilgili günün risk seviyesi "
            f'"{level}" olarak hesaplandı. '
            f"Bu değer son 14 gün içerisindeki en yüksek risk seviyesidir."
        )
    else:
        text = (
            f"{period_label} tarihinde Risk Endeksi {peak_risk}'e yükseldi. "
            f'İlgili günün risk seviyesi "{level}" olarak hesaplandı. '
            f"Bu değer son 14 gün içerisindeki en yüksek risk seviyesidir."
        )

    return {
        "period": peak.get("period"),
        "period_label": period_label,
        "period_start": period_start,
        "period_end": period_end,
        "kind": "spike",
        "text": text,
        "failed_tests": failed,
        "critical_bugs": critical,
        "delayed_tasks": delayed,
        "risk_index": peak_risk,
        "risk_level": level,
        "verify": {
            "tests": {
                "result": "failed",
                "executed_from": period_start,
                "executed_to": period_end,
                "expected_count": failed,
            },
            "bugs": {
                "severity": "critical",
                "status": "active",
                "created_from": period_start,
                "created_to": period_end,
                "expected_count": critical,
            },
            "tasks": {
                "is_delayed": "true",
                "updated_from": period_start,
                "updated_to": period_end,
                "expected_count": delayed,
            },
        },
    }


def _risk_band(score: float) -> str:
    band = release_risk_band(score)
    return {"Düşük": "low", "Orta": "medium", "Yüksek": "high"}[band]


def _serialize_project(p: Project) -> dict[str, Any]:
    """Projeler ekranı metrikleri — diğer modüllerle aynı kayıtlardan dinamik."""
    open_bugs = [b for b in p.bugs if is_bug_active(b.status)]
    open_by_sev = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for b in open_bugs:
        sev = _enum_val(b.severity)
        if sev in open_by_sev:
            open_by_sev[sev] += 1
        elif sev == "high":
            open_by_sev["high"] += 1

    critical_bugs = open_by_sev["critical"]
    failed_tests = sum(1 for t in p.tests if t.result == TestResult.FAILED)
    risky_release_count = sum(
        1 for r in p.releases if is_release_risky(r.risk_score, r.status)
    )
    tasks_total = len(p.tasks)
    tasks_done = sum(1 for t in p.tasks if t.status == TaskStatus.DONE)
    sprint_pct = round((tasks_done / tasks_total) * 100) if tasks_total else 0

    active_releases = [r for r in p.releases if is_release_active(r.status)]
    latest = None
    if p.releases:
        latest = sorted(
            p.releases,
            key=lambda r: (r.release_date or date.min, r.id),
            reverse=True,
        )[0]

    return {
        "id": p.id,
        "code": PROJECT_SHORT_CODES.get(p.code, p.code),
        "name": PROJECT_DISPLAY_NAMES.get(p.code, p.name),
        "description": p.description,
        "status": _enum_val(p.status),
        "active_sprint": p.active_sprint,
        "requirement_count": len(p.requirements),
        "task_count": tasks_total,
        "tasks_done": tasks_done,
        "sprint_done": tasks_done,
        "sprint_total": tasks_total,
        "sprint_progress_pct": sprint_pct,
        "commit_count": len(p.commits),
        "test_count": len(p.tests),
        "failed_tests": failed_tests,
        "open_bugs": len(open_bugs),
        "critical_bugs": critical_bugs,
        "bugs_critical": open_by_sev["critical"],
        "bugs_high": open_by_sev["high"],
        "bugs_medium": open_by_sev["medium"],
        "bugs_low": open_by_sev["low"],
        "risky_release_count": risky_release_count,
        "active_release_count": len(active_releases),
        "latest_release": (
            {
                "version": latest.version,
                "status": _enum_val(latest.status),
                "risk_score": float(latest.risk_score or 0),
            }
            if latest
            else None
        ),
        "is_risky": is_project_risky(
            critical_bugs=critical_bugs,
            failed_tests=failed_tests,
            risky_release_count=risky_release_count,
        ),
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": _project_updated_at(p),
    }


def _project_updated_at(p: Project) -> str | None:
    """Proje kaydının son aktivite zamanı (kolon veya bağlı kayıtlar)."""
    stamps: list[datetime] = []
    if getattr(p, "updated_at", None):
        stamps.append(p.updated_at)
    if p.created_at:
        stamps.append(p.created_at)
    for r in p.requirements or []:
        if r.updated_at:
            stamps.append(r.updated_at)
    for t in p.tasks or []:
        if t.updated_at:
            stamps.append(t.updated_at)
    for c in p.commits or []:
        if c.committed_at:
            stamps.append(c.committed_at)
    for t in p.tests or []:
        if t.executed_at:
            stamps.append(t.executed_at)
    for b in p.bugs or []:
        if b.updated_at:
            stamps.append(b.updated_at)
        elif b.created_at:
            stamps.append(b.created_at)
    for r in p.releases or []:
        if getattr(r, "updated_at", None):
            stamps.append(r.updated_at)
        elif r.created_at:
            stamps.append(r.created_at)
    if not stamps:
        return None
    return max(stamps).isoformat()


def _serialize_release(r: Release) -> dict[str, Any]:
    status = _enum_val(r.status)
    score = float(r.risk_score or 0)
    active = is_release_active(r.status)
    updated = getattr(r, "updated_at", None) or r.created_at
    if not updated and r.requirements:
        req_stamps = [req.updated_at for req in r.requirements if req.updated_at]
        if req_stamps:
            updated = max(req_stamps)
    return {
        "id": r.id,
        "version": r.version,
        "release_date": r.release_date.isoformat() if r.release_date else None,
        "status": status,
        "risk_score": score,
        "risk_band": _risk_band(score),
        "risk_band_label": release_risk_band(score),
        "is_active": active,
        "is_risky": is_release_risky(score, r.status),
        "risk_is_historical": not active,
        "notes": r.notes,
        "project_id": r.project_id,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": updated.isoformat() if updated else None,
        **_project_fields(r.project),
    }


class PostgresProjectService(ProjectDataSource):
    def __init__(self, db: Session):
        self.db = db

    def get_projects(
        self,
        status: str | None = None,
        is_risky: bool | None = None,
    ) -> list[dict[str, Any]]:
        q = self.db.query(Project)
        if status:
            q = q.filter(Project.status == status)
        rows = q.order_by(Project.name).all()
        result = [_serialize_project(p) for p in rows]
        if is_risky is not None:
            result = [r for r in result if bool(r["is_risky"]) is is_risky]
        return result

    def get_project_summary(self, project_id: int | None = None) -> dict[str, Any]:
        if project_id:
            projects = self.db.query(Project).filter(Project.id == project_id).all()
        else:
            projects = self.db.query(Project).all()

        summaries = []
        for p in projects:
            open_bugs = [b for b in p.bugs if is_bug_active(b.status)]
            failed_tests = [t for t in p.tests if t.result == TestResult.FAILED]
            incomplete_tasks = [t for t in p.tasks if t.status != TaskStatus.DONE]
            risky_reqs = [
                r
                for r in p.requirements
                if r.status == RequirementStatus.CHANGED
                or r.priority in (Priority.HIGH, Priority.CRITICAL)
            ]
            summaries.append(
                {
                    "project_id": p.id,
                    "code": PROJECT_SHORT_CODES.get(p.code, p.code),
                    "name": PROJECT_DISPLAY_NAMES.get(p.code, p.name),
                    "status": _enum_val(p.status),
                    "active_sprint": p.active_sprint,
                    "requirements": len(p.requirements),
                    "tasks_total": len(p.tasks),
                    "tasks_incomplete": len(incomplete_tasks),
                    "open_bugs": len(open_bugs),
                    # Dashboard KPI ile aynı: severity=critical + aktif akış
                    "critical_bugs": sum(
                        1 for b in open_bugs if is_critical_active_bug(b.severity, b.status)
                    ),
                    "failed_tests": len(failed_tests),
                    "risky_requirements": len(risky_reqs),
                    "releases": [
                        {
                            "version": r.version,
                            "status": _enum_val(r.status),
                            "risk_score": r.risk_score,
                            "is_risky": is_release_risky(r.risk_score, r.status),
                        }
                        for r in p.releases
                    ],
                }
            )

        if project_id and summaries:
            return summaries[0]
        return {"projects": summaries}

    def get_dashboard_metrics(self, project_id: int | None = None) -> dict[str, Any]:
        now = datetime.utcnow()
        since_14 = now - timedelta(days=14)

        active_q = self.db.query(func.count(Project.id)).filter(
            Project.status == ProjectStatus.ACTIVE
        )
        if project_id:
            active_q = active_q.filter(Project.id == project_id)
        active_projects = active_q.scalar() or 0

        task_q = self.db.query(Task)
        if project_id:
            task_q = task_q.filter(Task.project_id == project_id)
        all_tasks = task_q.all()
        delayed_tasks = sum(
            1
            for t in all_tasks
            if is_task_delayed(t.status, t.estimated_hours, t.actual_hours)
        )

        critical_bugs_q = self.db.query(func.count(Bug.id)).filter(
            Bug.status.in_([BugStatus.OPEN, BugStatus.IN_PROGRESS]),
            Bug.severity == Priority.CRITICAL,
        )
        if project_id:
            critical_bugs_q = critical_bugs_q.filter(Bug.project_id == project_id)
        critical_bugs = critical_bugs_q.scalar() or 0

        failed_tests_q = self.db.query(func.count(TestCase.id)).filter(
            TestCase.result == TestResult.FAILED
        )
        if project_id:
            failed_tests_q = failed_tests_q.filter(TestCase.project_id == project_id)
        failed_tests = failed_tests_q.scalar() or 0

        rel_q = self.db.query(Release)
        if project_id:
            rel_q = rel_q.filter(Release.project_id == project_id)
        all_releases = rel_q.all()
        active_releases = [r for r in all_releases if is_release_active(r.status)]
        risk_buckets = {"Düşük": 0, "Orta": 0, "Yüksek": 0}
        for r in active_releases:
            risk_buckets[release_risk_band(r.risk_score)] += 1

        risky_releases = sum(
            1 for r in all_releases if is_release_risky(r.risk_score, r.status)
        )
        release_counts = {
            "total": len(all_releases),
            "not_released": len(active_releases),
            "risky": risky_releases,
        }

        recent_commits_q = self.db.query(func.count(Commit.id)).filter(
            Commit.committed_at >= since_14
        )
        if project_id:
            recent_commits_q = recent_commits_q.filter(Commit.project_id == project_id)
        recent_commits = recent_commits_q.scalar() or 0

        blocked = sum(1 for t in all_tasks if is_task_blocked(t.status))
        overrun = sum(
            1
            for t in all_tasks
            if is_task_overrun(t.status, t.estimated_hours, t.actual_hours)
        )
        # Gecikme Nedenleri = geciken görevlerin parçalanması (KPI delayed_tasks ile tutarlı)
        # blocked + overrun == delayed_tasks (tanım gereği)
        changed_req_q = self.db.query(Requirement.id).filter(
            Requirement.status == RequirementStatus.CHANGED
        )
        if project_id:
            changed_req_q = changed_req_q.filter(Requirement.project_id == project_id)
        changed_req_ids = {r.id for r in changed_req_q.all()}
        changed_req_impact = sum(
            1
            for t in all_tasks
            if t.requirement_id in changed_req_ids
            and is_task_delayed(t.status, t.estimated_hours, t.actual_hours)
        )
        failed_req_q = (
            self.db.query(TestCase.requirement_id)
            .filter(
                TestCase.result == TestResult.FAILED,
                TestCase.requirement_id.isnot(None),
            )
            .distinct()
        )
        if project_id:
            failed_req_q = failed_req_q.filter(TestCase.project_id == project_id)
        failed_req_ids = {row[0] for row in failed_req_q.all()}
        failed_linked_delayed = sum(
            1
            for t in all_tasks
            if t.requirement_id in failed_req_ids
            and is_task_delayed(t.status, t.estimated_hours, t.actual_hours)
        )

        total_tests_q = self.db.query(func.count(TestCase.id))
        if project_id:
            total_tests_q = total_tests_q.filter(TestCase.project_id == project_id)
        total_tests = total_tests_q.scalar() or 0
        passed_tests_q = self.db.query(func.count(TestCase.id)).filter(
            TestCase.result == TestResult.PASSED
        )
        if project_id:
            passed_tests_q = passed_tests_q.filter(TestCase.project_id == project_id)
        passed_tests = passed_tests_q.scalar() or 0
        skipped_tests_q = self.db.query(func.count(TestCase.id)).filter(
            TestCase.result == TestResult.SKIPPED
        )
        if project_id:
            skipped_tests_q = skipped_tests_q.filter(TestCase.project_id == project_id)
        skipped_tests = skipped_tests_q.scalar() or 0
        # KPI failed_tests ile birebir aynı sayı — Test Başarı Oranı dilimi
        test_pass_rate = round((passed_tests / total_tests) * 100, 1) if total_tests else 0

        # Gecikme nedenleri: yalnızca geciken görev parçaları + doğrulanabilir etki etiketleri
        # "Başarısız Test" ASLA failed_tests KPI'sı değildir; bağlı geciken görev sayıdır.
        delay_reasons = sorted(
            [
                {
                    "reason": "Engellenmiş Görev",
                    "count": blocked,
                    "metric": "blocked_tasks",
                    "verify": {"status": "blocked"},
                },
                {
                    "reason": "Süre Aşımı",
                    "count": overrun,
                    "metric": "overrun_tasks",
                    "verify": {"is_overrun": "true"},
                },
                {
                    "reason": "Değişen Gereksinimli Gecikme",
                    "count": changed_req_impact,
                    "metric": "changed_req_delayed_tasks",
                    "verify": {"is_delayed": "true", "req_status": "changed"},
                },
                {
                    "reason": "Başarısız Teste Bağlı Gecikme",
                    "count": failed_linked_delayed,
                    "metric": "failed_test_linked_delayed_tasks",
                    "verify": {"is_delayed": "true", "has_failed_test": "true"},
                },
            ],
            key=lambda x: x["count"],
            reverse=True,
        )

        risk_trend = []
        # Takvim günü dilimleri (etiket = filtre aralığı). 2-günlük pencereler
        # "21 Temmuz" deyip 23 Temmuz kayıtlarını getirmesin diye gün başı/sonu kullanılır.
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        for i in range(13, -1, -1):
            day_start = today_start - timedelta(days=i)
            day_end = day_start + timedelta(days=1)
            failed_q = self.db.query(func.count(TestCase.id)).filter(
                and_(
                    TestCase.result == TestResult.FAILED,
                    TestCase.executed_at >= day_start,
                    TestCase.executed_at < day_end,
                )
            )
            if project_id:
                failed_q = failed_q.filter(TestCase.project_id == project_id)
            failed = int(failed_q.scalar() or 0)

            # KPI ile aynı tanım: kritik + açık (OPEN/IN_PROGRESS), dilimde oluşan
            bugs_q = self.db.query(Bug).filter(
                and_(Bug.created_at >= day_start, Bug.created_at < day_end)
            )
            if project_id:
                bugs_q = bugs_q.filter(Bug.project_id == project_id)
            period_bugs = bugs_q.all()
            critical_bugs_period = sum(
                1 for b in period_bugs if is_critical_active_bug(b.severity, b.status)
            )

            delayed_period = sum(
                1
                for t in all_tasks
                if is_task_delayed(t.status, t.estimated_hours, t.actual_hours)
                and t.updated_at
                and day_start <= t.updated_at < day_end
            )

            risk_index = compute_risk_index(failed, critical_bugs_period, delayed_period)
            risk_trend.append(
                {
                    "period": day_start.strftime("%d.%m"),
                    "period_label": _format_day_tr(day_start),
                    "period_start": day_start.isoformat(timespec="seconds"),
                    "period_end": day_end.isoformat(timespec="seconds"),
                    "risk_index": risk_index,
                    "risk_level": risk_index_level(risk_index),
                    "failed_tests": failed,
                    "critical_bugs": critical_bugs_period,
                    "delayed_tasks": delayed_period,
                }
            )

        risk_trend_insight = _build_risk_trend_insight(risk_trend)

        from app.analysis_store import list_recent_analyses

        return {
            "cards": {
                "active_projects": active_projects,
                "delayed_tasks": delayed_tasks,
                "failed_tests": failed_tests,
                "critical_bugs": critical_bugs,
                "risky_releases": risky_releases,
                "recent_commits_14d": recent_commits,
            },
            "kpi_definitions": KPI_DEFINITIONS,
            "charts": {
                "release_risk_distribution": [
                    {"label": k, "count": v} for k, v in risk_buckets.items()
                ],
                "release_counts": release_counts,
                "test_pass_rate": test_pass_rate,
                "test_counts": {
                    "passed": passed_tests,
                    "failed": failed_tests,
                    "skipped": skipped_tests,
                    "total": total_tests,
                },
                "delay_reasons": delay_reasons,
                "risk_trend_14d": risk_trend,
                "risk_trend_insight": risk_trend_insight,
            },
            "card_links": {
                "active_projects": {"path": "/projeler", "query": {"status": "active"}},
                "delayed_tasks": {"path": "/gorevler", "query": {"is_delayed": "true"}},
                "failed_tests": {"path": "/testler", "query": {"result": "failed"}},
                "critical_bugs": {
                    "path": "/hatalar",
                    "query": {"severity": "critical", "status": "active"},
                },
                "risky_releases": {"path": "/release", "query": {"is_risky": "true"}},
                "recent_commits_14d": {
                    "path": "/kod-degisiklikleri",
                    "query": {"committed_from": since_14.isoformat(timespec="seconds")},
                },
            },
            "recent_analyses": list_recent_analyses(
                self.db, limit=10, project_id=project_id
            ),
            "project_id": project_id,
            "last_updated": compute_data_last_updated(self.db, project_id=project_id),
        }

    def get_process_chains(
        self, limit: int = 12, project_id: int | None = None
    ) -> list[dict[str, Any]]:
        """Build Requirement → Task → Commit → Test → Bug → Release chains for UI."""
        from datetime import datetime, timedelta

        now = datetime.utcnow()
        since_14 = now - timedelta(days=14)

        requirements_q = self.db.query(Requirement).order_by(Requirement.updated_at.desc())
        if project_id:
            requirements_q = requirements_q.filter(Requirement.project_id == project_id)
        requirements = requirements_q.limit(50).all()
        releases_q = self.db.query(Release)
        if project_id:
            releases_q = releases_q.filter(Release.project_id == project_id)
        releases = releases_q.all()
        chains = []

        def node(
            kind: str,
            external_id: str,
            title: str,
            status: str,
            severity: str,
            reason: str | None = None,
        ):
            return {
                "kind": kind,
                "id": external_id,
                "title": title,
                "status": status,
                "severity": severity,
                "reason": reason,
            }

        for req in requirements:
            tasks = list(req.tasks) if req.tasks else []
            commits = list(req.commits) if req.commits else []
            tests = list(req.tests) if req.tests else []
            bugs = list(req.bugs) if req.bugs else []
            # Sürüm: gereksinimin hedeflediği release (aynı zincir); yoksa proje yedeği
            chain_releases: list[Release] = []
            if req.release is not None:
                chain_releases = [req.release]
            else:
                project_releases = [
                    r
                    for r in releases
                    if r.project_id == req.project_id and _enum_val(r.status) != "released"
                ]
                if not project_releases:
                    project_releases = [r for r in releases if r.project_id == req.project_id][:1]
                else:
                    project_releases = sorted(
                        project_releases, key=lambda x: x.risk_score or 0, reverse=True
                    )[:1]
                chain_releases = project_releases

            failed_tests = [t for t in tests if t.result == TestResult.FAILED]
            open_critical = [
                b for b in bugs if is_critical_active_bug(b.severity, b.status)
            ]
            open_bugs = [b for b in bugs if is_bug_active(b.status)]
            blocked_tasks = [t for t in tasks if is_task_blocked(t.status)]
            delayed_tasks = [
                t
                for t in tasks
                if is_task_delayed(t.status, t.estimated_hours, t.actual_hours)
            ]
            incomplete_tasks = [t for t in tasks if t.status != TaskStatus.DONE]
            changed = req.status == RequirementStatus.CHANGED
            recent_change = bool(req.updated_at and req.updated_at >= since_14)

            score = (
                (3 if open_critical else 0)
                + (2 if failed_tests else 0)
                + (2 if delayed_tasks else 0)
                + (1 if blocked_tasks else 0)
                + (1 if changed or recent_change else 0)
            )
            if score == 0:
                continue

            chain_nodes: list[dict[str, Any]] = []

            # Gereksinim — yalnızca kendi sorunu varsa vurgula
            if changed:
                chain_nodes.append(
                    node(
                        "requirement",
                        req.external_id,
                        _clean_record_title(req.title, req.module),
                        _enum_val(req.status),
                        "warning",
                        "Revize edildi",
                    )
                )
            elif recent_change:
                chain_nodes.append(
                    node(
                        "requirement",
                        req.external_id,
                        _clean_record_title(req.title, req.module),
                        _enum_val(req.status),
                        "warning",
                        "Son 14 günde değişti",
                    )
                )
            else:
                chain_nodes.append(
                    node(
                        "requirement",
                        req.external_id,
                        _clean_record_title(req.title, req.module),
                        _enum_val(req.status),
                        "normal",
                        None,
                    )
                )

            # Görev — Dashboard gecikme tanımı ile aynı
            if blocked_tasks:
                t = blocked_tasks[0]
                chain_nodes.append(
                    node(
                        "task",
                        t.external_id,
                        t.title,
                        _enum_val(t.status),
                        "critical",
                        "Görev bloke",
                    )
                )
            elif delayed_tasks:
                t = delayed_tasks[0]
                chain_nodes.append(
                    node(
                        "task",
                        t.external_id,
                        t.title,
                        _enum_val(t.status),
                        "warning",
                        "Süre aşıldı / gecikme",
                    )
                )
            elif incomplete_tasks:
                t = incomplete_tasks[0]
                chain_nodes.append(
                    node(
                        "task",
                        t.external_id,
                        t.title,
                        _enum_val(t.status),
                        "warning" if t.status == TaskStatus.IN_PROGRESS else "normal",
                        "Tamamlanmadı",
                    )
                )
            elif tasks:
                t = tasks[0]
                chain_nodes.append(
                    node(
                        "task",
                        t.external_id,
                        t.title,
                        _enum_val(t.status),
                        "done" if t.status == TaskStatus.DONE else "normal",
                        None,
                    )
                )

            # Commit — varsayılan nötr; yakın zamanda çok aktivite varsa uyarı
            if commits:
                c = max(commits, key=lambda x: x.committed_at or now)
                recent_commit = c.committed_at and c.committed_at >= since_14
                chain_nodes.append(
                    node(
                        "commit",
                        c.commit_hash[:8],
                        (c.message or "")[:80],
                        c.branch,
                        "warning" if recent_commit and (failed_tests or changed) else "normal",
                        "Son 14 günde kod değişti" if recent_commit and (failed_tests or changed) else None,
                    )
                )

            # Test — yalnızca başarısızsa vurgula
            if failed_tests:
                te = failed_tests[0]
                chain_nodes.append(
                    node(
                        "test",
                        te.external_id,
                        te.title,
                        _enum_val(te.result),
                        "critical",
                        "Test başarısız",
                    )
                )
            elif tests:
                te = tests[0]
                chain_nodes.append(
                    node(
                        "test",
                        te.external_id,
                        te.title,
                        _enum_val(te.result),
                        "done" if te.result == TestResult.PASSED else "normal",
                        None,
                    )
                )

            # Hata — yalnızca açık/kritikse vurgula
            if open_critical:
                b = open_critical[0]
                chain_nodes.append(
                    node(
                        "bug",
                        b.external_id,
                        b.title,
                        _enum_val(b.status),
                        "critical",
                        "Kritik hata açık",
                    )
                )
            elif open_bugs:
                b = open_bugs[0]
                chain_nodes.append(
                    node(
                        "bug",
                        b.external_id,
                        b.title,
                        _enum_val(b.status),
                        "warning",
                        "Açık hata var",
                    )
                )
            elif bugs:
                b = bugs[0]
                chain_nodes.append(
                    node(
                        "bug",
                        b.external_id,
                        b.title,
                        _enum_val(b.status),
                        "done",
                        None,
                    )
                )

            # Release — Riskli Sürümler KPI ile aynı (skor ≥70 ve yayında değil)
            if chain_releases:
                r = chain_releases[0]
                score_r = float(r.risk_score or 0)
                if is_release_risky(score_r, r.status):
                    rsev, reason = "critical", f"Risk skoru {int(score_r)} (yüksek, yayında değil)"
                elif is_release_active(r.status) and score_r >= 40:
                    rsev, reason = "warning", f"Risk skoru {int(score_r)} (orta)"
                elif not is_release_active(r.status):
                    rsev, reason = "done", "Yayında (tarihsel skor)"
                else:
                    rsev, reason = "normal", None
                chain_nodes.append(
                    node(
                        "release",
                        f"REL-{r.version}",
                        r.notes or r.version,
                        _enum_val(r.status),
                        rsev,
                        reason,
                    )
                )

            # Zincir şiddeti = en kötü düğüm
            order = {"critical": 3, "warning": 2, "done": 0, "normal": 0, "info": 0}
            chain_sev = max(
                (n["severity"] for n in chain_nodes),
                key=lambda s: order.get(s, 0),
            )
            if chain_sev not in ("critical", "warning"):
                chain_sev = "normal"

            pf = _project_fields(req.project)

            release_version = (
                f"REL-{chain_releases[0].version}" if chain_releases else None
            )

            chains.append(
                {
                    "requirement_id": req.external_id,
                    "project": pf["project_name"],
                    "project_code": pf["project_code"],
                    "release_version": release_version,
                    "severity": chain_sev,
                    "score": score,
                    "nodes": chain_nodes,
                }
            )

        chains.sort(key=lambda x: x["score"], reverse=True)
        return chains[:limit]


def compute_data_last_updated(
    db: Session,
    project_id: int | None = None,
    scope: str = "all",
) -> str | None:
    """Seçili proje / kapsam için en güncel veri zaman damgası."""
    candidates: list[datetime] = []

    def _add(value: datetime | None) -> None:
        if value is not None:
            candidates.append(value)

    scope = (scope or "all").lower()

    if scope in ("all", "dashboard", "process", "analysis", "requirements"):
        q = db.query(func.max(Requirement.updated_at))
        if project_id:
            q = q.filter(Requirement.project_id == project_id)
        _add(q.scalar())

    if scope in ("all", "dashboard", "process", "analysis", "tasks"):
        q = db.query(func.max(Task.updated_at))
        if project_id:
            q = q.filter(Task.project_id == project_id)
        _add(q.scalar())

    if scope in ("all", "dashboard", "process", "analysis", "commits"):
        q = db.query(func.max(Commit.committed_at))
        if project_id:
            q = q.filter(Commit.project_id == project_id)
        _add(q.scalar())

    if scope in ("all", "dashboard", "process", "analysis", "tests"):
        q = db.query(func.max(TestCase.executed_at))
        if project_id:
            q = q.filter(TestCase.project_id == project_id)
        _add(q.scalar())

    if scope in ("all", "dashboard", "process", "analysis", "bugs"):
        q = db.query(func.max(Bug.updated_at))
        if project_id:
            q = q.filter(Bug.project_id == project_id)
        _add(q.scalar())

    if scope in ("all", "dashboard", "process", "analysis", "releases"):
        q = db.query(func.max(Release.updated_at))
        if project_id:
            q = q.filter(Release.project_id == project_id)
        _add(q.scalar())
        q2 = db.query(func.max(Release.created_at))
        if project_id:
            q2 = q2.filter(Release.project_id == project_id)
        _add(q2.scalar())

    if scope in ("all", "dashboard", "projects"):
        q = db.query(func.max(Project.updated_at))
        if project_id:
            q = q.filter(Project.id == project_id)
        _add(q.scalar())
        q2 = db.query(func.max(Project.created_at))
        if project_id:
            q2 = q2.filter(Project.id == project_id)
        _add(q2.scalar())

    if not candidates:
        return None
    return max(candidates).isoformat()


def build_services(db: Session) -> dict[str, Any]:
    """Factory — replace any service with Jira/ADO adapters without changing callers."""
    return {
        "requirements": PostgresRequirementService(db),
        "tasks": PostgresTaskService(db),
        "commits": PostgresCommitService(db),
        "tests": PostgresTestService(db),
        "bugs": PostgresBugService(db),
        "releases": PostgresReleaseService(db),
        "projects": PostgresProjectService(db),
    }
