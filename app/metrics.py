"""
Tek kaynaklı metrik tanımları.

Dashboard KPI kartları, liste ekranları ve AI araçları aynı eşikleri kullanır.
Kullanıcı Dashboard'da gördüğü sayıyı ilgili modülde aynı filtreyle doğrulayabilir.
"""

from __future__ import annotations

from app.models.project import BugStatus, Priority, ProjectStatus, ReleaseStatus, TaskStatus, TestResult

# Release risk bantları (Release ekranı ile birebir)
RISK_LOW_MAX = 39  # 0–39 Düşük
RISK_MED_MAX = 69  # 40–69 Orta
# 70–100 Yüksek
RISKY_RELEASE_MIN = 70


def release_risk_band(score: float | None) -> str:
    s = float(score or 0)
    if s <= RISK_LOW_MAX:
        return "Düşük"
    if s <= RISK_MED_MAX:
        return "Orta"
    return "Yüksek"


def is_release_active(status) -> bool:
    val = status.value if hasattr(status, "value") else str(status)
    return val != ReleaseStatus.RELEASED.value


def is_release_risky(score: float | None, status) -> bool:
    """Aktif (yayında olmayan) ve risk skoru >= 70."""
    return is_release_active(status) and float(score or 0) >= RISKY_RELEASE_MIN


def is_task_delayed(status, estimated_hours, actual_hours) -> bool:
    """Görevler ekranı ve Dashboard ile aynı: bloke VEYA süre aşımı."""
    st = status.value if hasattr(status, "value") else str(status)
    if st == TaskStatus.BLOCKED.value:
        return True
    return is_task_overrun(status, estimated_hours, actual_hours)


def is_task_overrun(status, estimated_hours, actual_hours) -> bool:
    """Bloke olmayan, gerçek süre > tahmini süre. Gecikme Nedenleri · Süre Aşımı."""
    st = status.value if hasattr(status, "value") else str(status)
    if st == TaskStatus.BLOCKED.value:
        return False
    if actual_hours is not None and estimated_hours and actual_hours > estimated_hours:
        return True
    return False


def is_task_blocked(status) -> bool:
    st = status.value if hasattr(status, "value") else str(status)
    return st == TaskStatus.BLOCKED.value


def is_bug_active(status) -> bool:
    """Açık kritik hatalar KPI: OPEN veya IN_PROGRESS (henüz çözülmemiş)."""
    st = status.value if hasattr(status, "value") else str(status)
    return st in (BugStatus.OPEN.value, BugStatus.IN_PROGRESS.value)


def is_critical_active_bug(severity, status) -> bool:
    sev = severity.value if hasattr(severity, "value") else str(severity)
    return sev == Priority.CRITICAL.value and is_bug_active(status)


# Risk trend endeksi — AI Özeti ile birebir aynı formül (tek kaynak)
# Risk Endeksi = 2×başarısız_test + 10×açık_kritik_hata + 3×geciken_görev
RISK_INDEX_W_FAILED = 2
RISK_INDEX_W_CRITICAL = 10
RISK_INDEX_W_DELAYED = 3


def compute_risk_index(
    failed_tests: int,
    critical_active_bugs: int,
    delayed_tasks: int,
) -> int:
    """Grafik Risk Endeksi — dahili skor; kullanıcıya formül gösterilmez."""
    return int(
        failed_tests * RISK_INDEX_W_FAILED
        + critical_active_bugs * RISK_INDEX_W_CRITICAL
        + delayed_tasks * RISK_INDEX_W_DELAYED
    )


def risk_index_level(score: int | float | None) -> str:
    """Risk Endeksi yorum bandı (yönetici dili) — formül katsayıları gösterilmez."""
    s = int(score or 0)
    if s <= RISK_LOW_MAX:
        return "Düşük"
    if s <= RISK_MED_MAX:
        return "Orta"
    return "Yüksek"


def is_project_risky(
    *,
    critical_bugs: int,
    failed_tests: int,
    risky_release_count: int,
) -> bool:
    """
    Riskli proje: seçici sinyal (portföyün tamamı riskli görünmesin).
    — 2+ kritik açık hata ve (riskli sürüm≥2 VEYA başarısız test≥9), VEYA
    — 1+ kritik + riskli sürüm + başarısız test≥10
    """
    if critical_bugs >= 2 and (risky_release_count >= 2 or failed_tests >= 9):
        return True
    if critical_bugs >= 1 and risky_release_count >= 1 and failed_tests >= 10:
        return True
    return False


# Filtre etiketleri (API / dokümantasyon)
KPI_DEFINITIONS = {
    "active_projects": {
        "filter": {"status": ProjectStatus.ACTIVE.value},
        "module": "projects",
        "label": "Aktif projeler",
    },
    "risky_projects": {
        "filter": {"is_risky": True},
        "module": "projects",
        "label": "Riskli projeler (kritik hata + sürüm/test sinyali)",
    },
    "failed_tests": {
        "filter": {"result": TestResult.FAILED.value},
        "module": "tests",
        "label": "Başarısız testler",
    },
    "critical_bugs": {
        "filter": {"severity": Priority.CRITICAL.value, "is_active": True},
        "module": "bugs",
        "label": "Açık kritik hatalar (OPEN/IN_PROGRESS)",
    },
    "risky_releases": {
        "filter": {"is_risky": True},
        "module": "releases",
        "label": f"Risk skoru ≥ {RISKY_RELEASE_MIN} ve henüz yayında olmayan",
    },
    "active_releases": {
        "filter": {"is_active": True},
        "module": "releases",
        "label": "Henüz yayında olmayan sürümler (risk dağılımı grafiği)",
    },
    "all_releases": {
        "filter": {},
        "module": "releases",
        "label": "Tüm sürümler (yayında olanlar dahil)",
    },
    "delayed_tasks": {
        "filter": {"is_delayed": True},
        "module": "tasks",
        "label": "Bloke veya süre aşımı olan görevler",
    },
    "blocked_tasks": {
        "filter": {"status": TaskStatus.BLOCKED.value},
        "module": "tasks",
        "label": "Engellenmiş (bloke) görevler",
    },
    "overrun_tasks": {
        "filter": {"is_overrun": True},
        "module": "tasks",
        "label": "Süre aşımı olan görevler (bloke hariç)",
    },
    "risk_index": {
        "module": "dashboard.risk_trend",
        "label": "Risk Endeksi (trend / AI özeti — dahili skor)",
        "bands": "0–39 Düşük · 40–69 Orta · 70+ Yüksek",
    },
}
