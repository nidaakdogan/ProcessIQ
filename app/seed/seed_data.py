"""
İlişkili SDLC seed verisi.

Her kayıt bağımsız üretilmez. Temel birim zincirdir:

  Proje → Sürüm → Gereksinim → Görev → Commit → Test → Hata

Aynı gereksinim altındaki task / commit / test / bug aynı zincire aittir;
bug her zaman aynı gereksinimdeki başarısız teste bağlanır;
gereksinim hedeflediği sürüme (release_id) bağlanır.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.database import Base, engine, SessionLocal
from app.models import (
    Project,
    Requirement,
    Task,
    Commit,
    TestCase,
    Bug,
    Release,
    ProjectStatus,
    Priority,
    RequirementStatus,
    TaskStatus,
    TestResult,
    BugStatus,
    ReleaseStatus,
)

PROJECTS = [
    # (code, name, desc, sprint, status)
    ("CORE-BANK", "Ana Bankacılık Modernizasyonu", "Ana bankacılık modüllerinin modernizasyonu", "Sprint-14", ProjectStatus.ACTIVE),
    ("MOBILE-APP", "Mobil Bankacılık Uygulaması", "Mobil bankacılık uygulaması", "Sprint-8", ProjectStatus.TESTING),
    ("PAYMENTS", "Ödeme Geçidi", "Ödeme geçidi ve entegrasyonlar", "Sprint-11", ProjectStatus.READY_FOR_RELEASE),
    ("CRM-X", "Müşteri 360 CRM", "Müşteri 360 CRM platformu", "Sprint-6", ProjectStatus.ACTIVE),
    ("DATA-PLAT", "Veri Platformu", "Kurumsal veri platformu ve ETL", "Sprint-9", ProjectStatus.PLANNING),
]

DEVELOPERS = [
    "Ayşe Yılmaz",
    "Mehmet Demir",
    "Zeynep Kaya",
    "Can Öztürk",
    "Elif Şahin",
    "Burak Arslan",
    "Deniz Çelik",
    "Selin Aydın",
]

ASSIGNEES = DEVELOPERS + ["Fatma Koç", "Emre Yıldız"]

MODULES = [
    "Auth",
    "Accounts",
    "Transfers",
    "Cards",
    "Notifications",
    "Reporting",
    "Onboarding",
    "Compliance",
    "API Gateway",
    "Batch",
]


def _dt(days_ago: int, hour: int = 10, minute: int | None = None) -> datetime:
    base = datetime.utcnow() - timedelta(days=days_ago)
    m = minute if minute is not None else (abs(days_ago) * 7 + hour * 3) % 60
    return base.replace(hour=hour % 24, minute=m, second=0, microsecond=0)


@dataclass
class TaskSpec:
    title: str
    status: TaskStatus
    estimated: float = 8.0
    actual: float | None = None
    external_id: str | None = None


@dataclass
class TestSpec:
    title: str
    result: TestResult
    external_id: str | None = None
    days_ago: int = 3


@dataclass
class BugSpec:
    title: str
    test_index: int
    severity: Priority = Priority.HIGH
    priority: Priority = Priority.HIGH
    status: BugStatus = BugStatus.OPEN
    external_id: str | None = None


@dataclass
class ChainSpec:
    """Tek bir SDLC senaryo zinciri."""

    project_code: str
    module: str
    title: str
    release_version: str
    req_status: RequirementStatus = RequirementStatus.IN_PROGRESS
    priority: Priority = Priority.MEDIUM
    req_external_id: str | None = None
    req_days_ago: int = 10
    tasks: list[TaskSpec] = field(default_factory=list)
    tests: list[TestSpec] = field(default_factory=list)
    bugs: list[BugSpec] = field(default_factory=list)
    commits_per_task: int = 2
    recent_commits: bool = False


# Sabit vitrin zinciri — kullanıcı örneği ile aynı kimlikler
SHOWCASE_CRM = ChainSpec(
    project_code="CRM-X",
    module="Onboarding",
    title="Müşteri 360 profil senkronizasyonu",
    release_version="2.2",
    req_status=RequirementStatus.CHANGED,
    priority=Priority.CRITICAL,
    req_external_id="REQ-064",
    req_days_ago=4,
    tasks=[
        TaskSpec(
            external_id="TASK-040",
            title="Profil senkron API entegrasyonu",
            status=TaskStatus.BLOCKED,
            estimated=16.0,
            actual=22.0,
        ),
        TaskSpec(
            title="CRM olay dinleyicisi",
            status=TaskStatus.IN_PROGRESS,
            estimated=12.0,
            actual=9.0,
        ),
        TaskSpec(
            title="Senkron hata yeniden deneme",
            status=TaskStatus.TODO,
            estimated=8.0,
        ),
    ],
    tests=[
        TestSpec(
            external_id="TEST-052",
            title="Profil senkron tutarlılık testi",
            result=TestResult.FAILED,
            days_ago=2,
        ),
        TestSpec(
            title="Onboarding adım ilerleme kontrolü",
            result=TestResult.PASSED,
            days_ago=5,
        ),
        TestSpec(
            title="CRM olay sırası doğrulama",
            result=TestResult.FAILED,
            days_ago=1,
        ),
    ],
    bugs=[
        BugSpec(
            external_id="BUG-026",
            title="Profil senkronu sonrası eski adres görünüyor",
            test_index=0,
            severity=Priority.CRITICAL,
            priority=Priority.CRITICAL,
            status=BugStatus.OPEN,
        ),
        BugSpec(
            title="CRM olay sırasında sıra bozuluyor",
            test_index=2,
            severity=Priority.HIGH,
            priority=Priority.HIGH,
            status=BugStatus.IN_PROGRESS,
        ),
    ],
    commits_per_task=2,
    recent_commits=True,
)


def _problem_scenarios() -> list[ChainSpec]:
    """Riskli / analiz edilebilir senaryolar — her biri tam ilişkili zincir."""
    return [
        SHOWCASE_CRM,
        ChainSpec(
            project_code="CORE-BANK",
            module="Transfers",
            title="Havale limit kontrolü modernizasyonu",
            release_version="2.1",
            req_status=RequirementStatus.CHANGED,
            priority=Priority.CRITICAL,
            req_days_ago=3,
            tasks=[
                TaskSpec("Limit motoru refactor", TaskStatus.BLOCKED, 24.0, 30.0),
                TaskSpec("Gece batch uyumu", TaskStatus.IN_PROGRESS, 16.0, 18.0),
                TaskSpec("Limit audit log", TaskStatus.TODO, 8.0),
            ],
            tests=[
                TestSpec("Limit aşımı reddi", TestResult.FAILED, days_ago=1),
                TestSpec("Eşzamanlı havale kilidi", TestResult.FAILED, days_ago=2),
                TestSpec("Limit geçmişi raporu", TestResult.PASSED, days_ago=6),
            ],
            bugs=[
                BugSpec(
                    "Limit aşımında işlem yine de tamamlanıyor",
                    0,
                    Priority.CRITICAL,
                    Priority.CRITICAL,
                    BugStatus.OPEN,
                ),
                BugSpec(
                    "Eşzamanlı havale çift kayıt oluşturuyor",
                    1,
                    Priority.HIGH,
                    Priority.HIGH,
                    BugStatus.IN_PROGRESS,
                ),
            ],
            recent_commits=True,
        ),
        ChainSpec(
            project_code="CORE-BANK",
            module="Auth",
            title="Çok faktörlü kimlik doğrulama güçlendirme",
            release_version="2.1",
            req_status=RequirementStatus.IN_PROGRESS,
            priority=Priority.HIGH,
            req_days_ago=8,
            tasks=[
                TaskSpec("OTP servis entegrasyonu", TaskStatus.IN_PROGRESS, 16.0, 14.0),
                TaskSpec("Cihaz güven skoru", TaskStatus.BLOCKED, 12.0, 10.0),
            ],
            tests=[
                TestSpec("OTP süresi dolunca erişim engeli", TestResult.FAILED),
                TestSpec("Yeni cihaz onayı", TestResult.PASSED),
            ],
            bugs=[
                BugSpec(
                    "OTP süresi dolunca oturum açık kalıyor",
                    0,
                    Priority.CRITICAL,
                    Priority.CRITICAL,
                    BugStatus.OPEN,
                ),
            ],
            recent_commits=True,
        ),
        ChainSpec(
            project_code="PAYMENTS",
            module="Cards",
            title="Kart limit aşımı bildirim akışı",
            release_version="2.0",
            req_status=RequirementStatus.CHANGED,
            priority=Priority.HIGH,
            req_days_ago=5,
            tasks=[
                TaskSpec("Limit olay üreticisi", TaskStatus.IN_PROGRESS, 12.0, 15.0),
                TaskSpec("Push bildirim şablonu", TaskStatus.TODO, 6.0),
                TaskSpec("SMS yedek kanalı", TaskStatus.DONE, 8.0, 7.5),
            ],
            tests=[
                TestSpec("Kart limit aşımı uyarısı", TestResult.FAILED),
                TestSpec("SMS yedek kanalı", TestResult.PASSED),
            ],
            bugs=[
                BugSpec(
                    "Kart limiti aşıldığında uyarı gösterilmiyor",
                    0,
                    Priority.CRITICAL,
                    Priority.HIGH,
                    BugStatus.OPEN,
                ),
            ],
            recent_commits=True,
        ),
        ChainSpec(
            project_code="PAYMENTS",
            module="API Gateway",
            title="Ödeme callback idempotency",
            release_version="3.0-beta",
            req_status=RequirementStatus.IN_PROGRESS,
            priority=Priority.CRITICAL,
            req_days_ago=2,
            tasks=[
                TaskSpec("Idempotency anahtarı", TaskStatus.BLOCKED, 16.0, 20.0),
                TaskSpec("Retry kuyruğu", TaskStatus.IN_PROGRESS, 12.0, 8.0),
            ],
            tests=[
                TestSpec("Çift callback tek kayıt", TestResult.FAILED),
                TestSpec("Timeout sonrası yeniden deneme", TestResult.FAILED),
            ],
            bugs=[
                BugSpec(
                    "İade işlemi çift kayıt oluşturuyor",
                    0,
                    Priority.CRITICAL,
                    Priority.CRITICAL,
                    BugStatus.OPEN,
                ),
                BugSpec(
                    "Timeout sonrası partial payment kalıyor",
                    1,
                    Priority.HIGH,
                    Priority.HIGH,
                    BugStatus.IN_PROGRESS,
                ),
            ],
            recent_commits=True,
        ),
        ChainSpec(
            project_code="MOBILE-APP",
            module="Auth",
            title="Mobil oturum yenileme ve güvenli çıkış",
            release_version="1.2",
            req_status=RequirementStatus.CHANGED,
            priority=Priority.HIGH,
            req_days_ago=6,
            tasks=[
                TaskSpec("Token yenileme akışı", TaskStatus.IN_PROGRESS, 10.0, 13.0),
                TaskSpec("Güvenli logout", TaskStatus.TODO, 6.0),
            ],
            tests=[
                TestSpec("Arka planda token yenileme", TestResult.FAILED),
                TestSpec("Logout sonrası lokal cache temizliği", TestResult.PASSED),
            ],
            bugs=[
                BugSpec(
                    "Mobil uygulamada oturum düşüyor",
                    0,
                    Priority.CRITICAL,
                    Priority.CRITICAL,
                    BugStatus.OPEN,
                ),
            ],
            recent_commits=True,
        ),
        ChainSpec(
            project_code="MOBILE-APP",
            module="Notifications",
            title="Push bildirim teslim garantisi",
            release_version="hotfix-1.2.1",
            req_status=RequirementStatus.IN_PROGRESS,
            priority=Priority.MEDIUM,
            req_days_ago=9,
            tasks=[
                TaskSpec("FCM retry politikası", TaskStatus.IN_PROGRESS, 8.0, 6.0),
                TaskSpec("Okundu bilgisi senkronu", TaskStatus.DONE, 6.0, 5.5),
            ],
            tests=[
                TestSpec("Bildirim gönderim doğrulaması", TestResult.FAILED),
                TestSpec("Okundu durumu senkronu", TestResult.PASSED),
            ],
            bugs=[
                BugSpec(
                    "Bildirimler gecikmeli iletiliyor",
                    0,
                    Priority.HIGH,
                    Priority.MEDIUM,
                    BugStatus.IN_PROGRESS,
                ),
            ],
            recent_commits=True,
        ),
        ChainSpec(
            project_code="DATA-PLAT",
            module="Batch",
            title="Gece ETL tutarlılık kontrolleri",
            release_version="1.1",
            req_status=RequirementStatus.CHANGED,
            priority=Priority.HIGH,
            req_days_ago=4,
            tasks=[
                TaskSpec("Checksum doğrulama", TaskStatus.BLOCKED, 20.0, 24.0),
                TaskSpec("Hatalı satır karantina", TaskStatus.IN_PROGRESS, 12.0, 11.0),
            ],
            tests=[
                TestSpec("ETL satır sayısı tutarlılığı", TestResult.FAILED),
                TestSpec("Karantina tablo yazımı", TestResult.FAILED),
            ],
            bugs=[
                BugSpec(
                    "ETL sonrası satır sayısı uyuşmazlığı",
                    0,
                    Priority.CRITICAL,
                    Priority.CRITICAL,
                    BugStatus.OPEN,
                ),
                BugSpec(
                    "Karantina kayıtları kayboluyor",
                    1,
                    Priority.HIGH,
                    Priority.HIGH,
                    BugStatus.OPEN,
                ),
            ],
            recent_commits=True,
        ),
        ChainSpec(
            project_code="DATA-PLAT",
            module="Reporting",
            title="Uyumluluk rapor şablonları",
            release_version="1.0",
            req_status=RequirementStatus.IN_PROGRESS,
            priority=Priority.MEDIUM,
            req_days_ago=12,
            tasks=[
                TaskSpec("Rapor alan eşlemesi", TaskStatus.IN_PROGRESS, 14.0, 10.0),
                TaskSpec("PDF dışa aktarım", TaskStatus.TODO, 8.0),
            ],
            tests=[
                TestSpec("Uyumluluk zorunlu alan kontrolü", TestResult.FAILED),
                TestSpec("PDF sayfa düzeni", TestResult.SKIPPED),
            ],
            bugs=[
                BugSpec(
                    "Uyumluluk raporunda eksik alanlar",
                    0,
                    Priority.HIGH,
                    Priority.HIGH,
                    BugStatus.OPEN,
                ),
            ],
        ),
        ChainSpec(
            project_code="CRM-X",
            module="Accounts",
            title="Müşteri hesap özeti birleştirme",
            release_version="2.2",
            req_status=RequirementStatus.IN_PROGRESS,
            priority=Priority.HIGH,
            req_days_ago=7,
            tasks=[
                TaskSpec("Hesap özet agregasyonu", TaskStatus.IN_PROGRESS, 16.0, 12.0),
                TaskSpec("Yetki matrisi", TaskStatus.DONE, 8.0, 8.0),
            ],
            tests=[
                TestSpec("Hesap bakiyesi tutarlılık kontrolü", TestResult.FAILED),
                TestSpec("Yetkisiz erişim reddi", TestResult.PASSED),
            ],
            bugs=[
                BugSpec(
                    "API 500 hatası: hesap özeti servisi",
                    0,
                    Priority.CRITICAL,
                    Priority.HIGH,
                    BugStatus.OPEN,
                ),
            ],
            recent_commits=True,
        ),
        ChainSpec(
            project_code="PAYMENTS",
            module="Transfers",
            title="Toplu ödeme kısmi başarı yönetimi",
            release_version="2.0",
            req_status=RequirementStatus.CHANGED,
            priority=Priority.HIGH,
            req_days_ago=3,
            tasks=[
                TaskSpec("Kısmi başarı durumu", TaskStatus.BLOCKED, 12.0, 16.0),
                TaskSpec("Başarısız kalem yeniden kuyruk", TaskStatus.TODO, 8.0),
            ],
            tests=[
                TestSpec("Toplu transfer işlem testi", TestResult.FAILED),
                TestSpec("Kısmi başarı özeti", TestResult.PASSED),
            ],
            bugs=[
                BugSpec(
                    "Toplu transferde kısmi kayıt oluşuyor",
                    0,
                    Priority.HIGH,
                    Priority.HIGH,
                    BugStatus.IN_PROGRESS,
                ),
            ],
            recent_commits=True,
        ),
        ChainSpec(
            project_code="CORE-BANK",
            module="Compliance",
            title="Şüpheli işlem bildirim eşikleri",
            release_version="2.1.1",
            req_status=RequirementStatus.IN_PROGRESS,
            priority=Priority.MEDIUM,
            req_days_ago=11,
            tasks=[
                TaskSpec("Eşik konfigürasyonu", TaskStatus.IN_PROGRESS, 10.0, 7.0),
                TaskSpec("Bildirim paneli", TaskStatus.DONE, 8.0, 7.0),
            ],
            tests=[
                TestSpec("Eşik aşımında uyarı", TestResult.FAILED),
                TestSpec("Yanlış pozitif azaltma", TestResult.PASSED),
            ],
            bugs=[
                BugSpec(
                    "Şüpheli işlem eşiği tetiklenmiyor",
                    0,
                    Priority.HIGH,
                    Priority.MEDIUM,
                    BugStatus.OPEN,
                ),
            ],
        ),
    ]


def _healthy_chain(
    project_code: str,
    module: str,
    title: str,
    release_version: str,
    idx: int,
) -> ChainSpec:
    """Sağlıklı ama yine de tamamen ilişkili dolgu zinciri."""
    statuses = [
        RequirementStatus.APPROVED,
        RequirementStatus.IN_PROGRESS,
        RequirementStatus.DONE,
        RequirementStatus.DRAFT,
    ]
    return ChainSpec(
        project_code=project_code,
        module=module,
        title=title,
        release_version=release_version,
        req_status=statuses[idx % len(statuses)],
        priority=[Priority.LOW, Priority.MEDIUM, Priority.HIGH][idx % 3],
        req_days_ago=15 + (idx % 30),
        tasks=[
            TaskSpec(
                f"{title} — tasarım",
                TaskStatus.DONE if idx % 4 != 0 else TaskStatus.IN_PROGRESS,
                8.0,
                7.5 if idx % 4 != 0 else 4.0,
            ),
            TaskSpec(
                f"{title} — geliştirme",
                TaskStatus.DONE if idx % 5 != 0 else TaskStatus.TODO,
                12.0,
                11.0 if idx % 5 != 0 else None,
            ),
            TaskSpec(
                f"{title} — kod incelemesi",
                TaskStatus.DONE if idx % 3 == 0 else TaskStatus.IN_PROGRESS,
                4.0,
                4.0 if idx % 3 == 0 else 2.0,
            ),
        ],
        tests=[
            TestSpec(f"{module} mutlu yol senaryosu", TestResult.PASSED, days_ago=8 + idx % 5),
            TestSpec(
                f"{module} kenar durum senaryosu",
                TestResult.PASSED if idx % 7 else TestResult.SKIPPED,
                days_ago=6,
            ),
            TestSpec(f"{module} regresyon paketi", TestResult.PASSED, days_ago=4),
        ],
        bugs=[],
        commits_per_task=1 if idx % 2 else 2,
        recent_commits=False,
    )


# Proje başına sürümler (risk skoru senaryoyla uyumlu)
RELEASE_DEFS: list[tuple[str, str, ReleaseStatus, float, int]] = [
    # (project_code, version, status, risk_score, days_offset)
    ("CORE-BANK", "2.1", ReleaseStatus.IN_PROGRESS, 78.0, 12),
    ("CORE-BANK", "2.1.1", ReleaseStatus.PLANNED, 52.0, 35),
    ("MOBILE-APP", "1.2", ReleaseStatus.DELAYED, 74.0, 8),
    ("MOBILE-APP", "hotfix-1.2.1", ReleaseStatus.IN_PROGRESS, 61.0, 5),
    ("PAYMENTS", "2.0", ReleaseStatus.READY, 71.0, 10),
    ("PAYMENTS", "3.0-beta", ReleaseStatus.IN_PROGRESS, 82.0, 18),
    ("CRM-X", "2.2", ReleaseStatus.IN_PROGRESS, 76.0, 14),
    ("CRM-X", "3.0-alpha", ReleaseStatus.PLANNED, 38.0, 45),
    ("DATA-PLAT", "1.1", ReleaseStatus.DELAYED, 69.0, 9),
    ("DATA-PLAT", "1.0", ReleaseStatus.RELEASED, 28.0, -40),
]


class _Counters:
    def __init__(self) -> None:
        self.req = 1
        self.task = 1
        self.test = 1
        self.bug = 1
        self.commit = 0
        self.reserved_req: set[str] = set()
        self.reserved_task: set[str] = set()
        self.reserved_test: set[str] = set()
        self.reserved_bug: set[str] = set()

    def reserve_from_specs(self, chains: list[ChainSpec]) -> None:
        for ch in chains:
            if ch.req_external_id:
                self.reserved_req.add(ch.req_external_id)
            for t in ch.tasks:
                if t.external_id:
                    self.reserved_task.add(t.external_id)
            for te in ch.tests:
                if te.external_id:
                    self.reserved_test.add(te.external_id)
            for b in ch.bugs:
                if b.external_id:
                    self.reserved_bug.add(b.external_id)

    def next_req(self, preferred: str | None = None) -> str:
        if preferred:
            return preferred
        while f"REQ-{self.req:03d}" in self.reserved_req:
            self.req += 1
        eid = f"REQ-{self.req:03d}"
        self.req += 1
        return eid

    def next_task(self, preferred: str | None = None) -> str:
        if preferred:
            return preferred
        while f"TASK-{self.task:03d}" in self.reserved_task:
            self.task += 1
        eid = f"TASK-{self.task:03d}"
        self.task += 1
        return eid

    def next_test(self, preferred: str | None = None) -> str:
        if preferred:
            return preferred
        while f"TEST-{self.test:03d}" in self.reserved_test:
            self.test += 1
        eid = f"TEST-{self.test:03d}"
        self.test += 1
        return eid

    def next_bug(self, preferred: str | None = None) -> str:
        if preferred:
            return preferred
        while f"BUG-{self.bug:03d}" in self.reserved_bug:
            self.bug += 1
        eid = f"BUG-{self.bug:03d}"
        self.bug += 1
        return eid


def _light_risk_chain(
    project_code: str,
    module: str,
    title: str,
    release_version: str,
    idx: int,
) -> ChainSpec:
    """Tek başarısız test + bağlı bug içeren orta risk zinciri."""
    return ChainSpec(
        project_code=project_code,
        module=module,
        title=title,
        release_version=release_version,
        req_status=RequirementStatus.IN_PROGRESS if idx % 2 else RequirementStatus.CHANGED,
        priority=Priority.HIGH if idx % 3 else Priority.MEDIUM,
        req_days_ago=5 + (idx % 10),
        tasks=[
            TaskSpec(f"{title} — geliştirme", TaskStatus.IN_PROGRESS, 12.0, 14.0),
            TaskSpec(f"{title} — doğrulama", TaskStatus.TODO, 6.0),
        ],
        tests=[
            TestSpec(f"{module} regresyon — {title}", TestResult.FAILED, days_ago=2),
            TestSpec(f"{module} mutlu yol — {title}", TestResult.PASSED, days_ago=5),
        ],
        bugs=[
            BugSpec(
                f"{module}: {title} regresyon hatası",
                0,
                Priority.HIGH if idx % 2 else Priority.MEDIUM,
                Priority.HIGH,
                BugStatus.OPEN if idx % 3 else BugStatus.IN_PROGRESS,
            ),
        ],
        commits_per_task=2,
        recent_commits=True,
    )


def _build_all_chains() -> list[ChainSpec]:
    chains = list(_problem_scenarios())
    # Ek ilişkili risk zincirleri → ~40 bug hedefine yaklaş
    light_titles = [
        ("CORE-BANK", "Accounts", "Hesap dondurma iş kuralları"),
        ("CORE-BANK", "Cards", "Kart iptal sonrası yetki temizliği"),
        ("CORE-BANK", "Notifications", "Kritik işlem SMS şablonu"),
        ("MOBILE-APP", "Transfers", "Hızlı havale tutar doğrulama"),
        ("MOBILE-APP", "Onboarding", "KYC belge yükleme adımı"),
        ("MOBILE-APP", "API Gateway", "Mobil gateway rate limit"),
        ("PAYMENTS", "Auth", "Ödeme oturum bağlama"),
        ("PAYMENTS", "Compliance", "Ödeme AML kontrol noktası"),
        ("PAYMENTS", "Batch", "Günsonu mutabakat dosyası"),
        ("CRM-X", "Reporting", "Müşteri etkileşim raporu"),
        ("CRM-X", "Notifications", "CRM kampanya tetikleyicisi"),
        ("CRM-X", "API Gateway", "CRM webhook imza doğrulama"),
        ("DATA-PLAT", "API Gateway", "Veri API sayfalama tutarlılığı"),
        ("DATA-PLAT", "Compliance", "Kişisel veri maskeleme"),
        ("DATA-PLAT", "Onboarding", "Kaynak sistem bağlantı sağlığı"),
        ("CORE-BANK", "Batch", "Faiz tahakkuk yeniden hesap"),
        ("MOBILE-APP", "Cards", "Kart görsel önizleme"),
        ("PAYMENTS", "Accounts", "Cüzdan bakiye senkronu"),
        ("CRM-X", "Transfers", "Lead atama kural motoru"),
        ("DATA-PLAT", "Auth", "Veri platformu servis hesabı"),
        ("CORE-BANK", "Reporting", "Şube performans özeti"),
        ("MOBILE-APP", "Compliance", "Aydınlatma metni onayı"),
        ("PAYMENTS", "Onboarding", "Üye işyeri aktivasyon"),
        ("CRM-X", "Batch", "Gece lead skorlama"),
    ]
    for i, (project_code, module, title) in enumerate(light_titles):
        project_releases = [r for r in RELEASE_DEFS if r[0] == project_code]
        release_version = project_releases[i % len(project_releases)][1]
        chains.append(_light_risk_chain(project_code, module, title, release_version, i))

    target = 100
    idx = 0
    while len(chains) < target:
        project_code, *_ = PROJECTS[idx % len(PROJECTS)]
        module = MODULES[idx % len(MODULES)]
        project_releases = [r for r in RELEASE_DEFS if r[0] == project_code]
        release_version = project_releases[idx % len(project_releases)][1]
        title = f"{module} işlevsel iyileştirme {idx + 1}"
        chains.append(_healthy_chain(project_code, module, title, release_version, idx))
        idx += 1
    return chains


def _validate_integrity(
    requirements: list[Requirement],
    tasks: list[Task],
    commits: list[Commit],
    tests: list[TestCase],
    bugs: list[Bug],
) -> None:
    """Seed sonrası tutarlılık — bozuk ilişki varsa seed başarısız olsun."""
    req_by_id = {r.id: r for r in requirements}
    test_by_id = {t.id: t for t in tests}
    task_by_id = {t.id: t for t in tasks}

    for t in tasks:
        assert t.requirement_id is not None, f"{t.external_id} gereksinimsiz"
        assert t.project_id == req_by_id[t.requirement_id].project_id

    for c in commits:
        assert c.task_id is not None, f"commit {c.commit_hash} görevsiz"
        assert c.requirement_id is not None
        task = task_by_id[c.task_id]
        assert c.requirement_id == task.requirement_id
        assert c.project_id == task.project_id

    for te in tests:
        assert te.requirement_id is not None, f"{te.external_id} gereksinimsiz"
        assert te.project_id == req_by_id[te.requirement_id].project_id

    for b in bugs:
        assert b.test_id is not None, f"{b.external_id} testsiz"
        assert b.requirement_id is not None
        test = test_by_id[b.test_id]
        assert b.requirement_id == test.requirement_id, (
            f"{b.external_id} test ile farklı gereksinim"
        )
        assert b.project_id == test.project_id
        assert test.result == TestResult.FAILED, (
            f"{b.external_id} başarısız olmayan teste bağlı"
        )

    for r in requirements:
        if r.release_id is not None:
            assert r.release is not None
            assert r.release.project_id == r.project_id


def seed(db: Session | None = None) -> dict:
    own_session = db is None
    if own_session:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()

    try:
        if not own_session:
            for model in (Bug, TestCase, Commit, Task, Requirement, Release, Project):
                db.query(model).delete()
            db.commit()

        projects: dict[str, Project] = {}
        for code, name, desc, sprint, status in PROJECTS:
            p = Project(
                code=code,
                name=name,
                description=desc,
                status=status,
                active_sprint=sprint,
            )
            db.add(p)
            projects[code] = p
        db.flush()

        releases: dict[tuple[str, str], Release] = {}
        for project_code, version, status, risk, day_off in RELEASE_DEFS:
            p = projects[project_code]
            rel_date = date.today() + timedelta(days=day_off)
            if status == ReleaseStatus.RELEASED:
                rel_date = date.today() + timedelta(days=min(day_off, -5))
            r = Release(
                version=version,
                release_date=rel_date,
                status=status,
                risk_score=risk,
                notes=f"{p.name} sürüm {version}",
                project_id=p.id,
                created_at=_dt(max(14, abs(day_off) + 10), hour=11),
                updated_at=_dt(max(0, abs(min(day_off, 0))), hour=14),
            )
            db.add(r)
            releases[(project_code, version)] = r
        db.flush()

        chains = _build_all_chains()
        counters = _Counters()
        counters.reserve_from_specs(chains)

        requirements: list[Requirement] = []
        tasks: list[Task] = []
        commits: list[Commit] = []
        tests: list[TestCase] = []
        bugs: list[Bug] = []

        for chain_i, chain in enumerate(chains):
            project = projects[chain.project_code]
            release = releases[(chain.project_code, chain.release_version)]
            req_eid = counters.next_req(chain.req_external_id)
            req = Requirement(
                external_id=req_eid,
                title=chain.title,
                description=(
                    f"{project.name} · {chain.module} · hedef sürüm {chain.release_version}. "
                    f"{chain.title}."
                ),
                priority=chain.priority,
                status=chain.req_status,
                module=chain.module,
                project_id=project.id,
                release_id=release.id,
                updated_at=_dt(chain.req_days_ago),
                created_at=_dt(chain.req_days_ago + 20),
            )
            db.add(req)
            db.flush()
            requirements.append(req)

            chain_tasks: list[Task] = []
            for ti, tspec in enumerate(chain.tasks):
                sprint = project.active_sprint if ti % 3 else f"Sprint-{(ti % 5) + 4}"
                task = Task(
                    external_id=counters.next_task(tspec.external_id),
                    title=tspec.title,
                    assignee=ASSIGNEES[(chain_i + ti) % len(ASSIGNEES)],
                    status=tspec.status,
                    sprint=sprint,
                    estimated_hours=tspec.estimated,
                    actual_hours=tspec.actual,
                    project_id=project.id,
                    requirement_id=req.id,
                    updated_at=_dt(max(0, chain.req_days_ago - ti)),
                    created_at=_dt(chain.req_days_ago + 10),
                )
                db.add(task)
                chain_tasks.append(task)
                tasks.append(task)
            db.flush()

            module_slug = chain.module.lower().replace(" ", "-")
            for ti, task in enumerate(chain_tasks):
                n_commits = chain.commits_per_task
                for ci in range(n_commits):
                    counters.commit += 1
                    days = (
                        (ci + ti) % 12
                        if chain.recent_commits
                        else 15 + ((chain_i + ti + ci) % 40)
                    )
                    h = hashlib.sha1(
                        f"{req.external_id}-{task.external_id}-{ci}".encode()
                    ).hexdigest()[:12]
                    branch = (
                        f"feature/{module_slug}-{req.external_id.lower()}"
                        if ci == 0
                        else f"bugfix/{module_slug}-{task.external_id.lower()}"
                    )
                    msg = (
                        f"Özellik ({chain.module}): {task.title} — {req.external_id}"
                        if ci == 0
                        else f"Düzeltme ({chain.module}): {task.title} düzeltmesi — {req.external_id}"
                    )
                    c = Commit(
                        commit_hash=h,
                        branch=branch,
                        developer=DEVELOPERS[(chain_i + ti + ci) % len(DEVELOPERS)],
                        message=msg,
                        committed_at=_dt(days, hour=9 + ci),
                        project_id=project.id,
                        requirement_id=req.id,
                        task_id=task.id,
                    )
                    db.add(c)
                    commits.append(c)
            db.flush()

            chain_tests: list[TestCase] = []
            for te_i, tespec in enumerate(chain.tests):
                te = TestCase(
                    external_id=counters.next_test(tespec.external_id),
                    title=tespec.title,
                    result=tespec.result,
                    executed_at=_dt(tespec.days_ago),
                    project_id=project.id,
                    requirement_id=req.id,
                )
                db.add(te)
                chain_tests.append(te)
                tests.append(te)
            db.flush()

            for bspec in chain.bugs:
                if bspec.test_index < 0 or bspec.test_index >= len(chain_tests):
                    raise ValueError(
                        f"{req.external_id}: bug test_index {bspec.test_index} geçersiz"
                    )
                linked_test = chain_tests[bspec.test_index]
                if linked_test.result != TestResult.FAILED:
                    linked_test.result = TestResult.FAILED
                bug = Bug(
                    external_id=counters.next_bug(bspec.external_id),
                    title=bspec.title,
                    priority=bspec.priority,
                    severity=bspec.severity,
                    status=bspec.status,
                    project_id=project.id,
                    requirement_id=req.id,
                    test_id=linked_test.id,
                    created_at=_dt(max(0, chain.req_days_ago - 1)),
                    updated_at=_dt(0 if bspec.status == BugStatus.OPEN else 2),
                )
                db.add(bug)
                bugs.append(bug)

        db.flush()
        _validate_integrity(requirements, tasks, commits, tests, bugs)

        # Proje / sürüm Son Güncelleme = bağlı kayıtlardaki en son aktivite
        for p in projects.values():
            stamps: list[datetime] = [p.created_at] if p.created_at else []
            for coll in (p.requirements, p.tasks, p.bugs):
                for row in coll or []:
                    if getattr(row, "updated_at", None):
                        stamps.append(row.updated_at)
            for c in p.commits or []:
                if c.committed_at:
                    stamps.append(c.committed_at)
            for te in p.tests or []:
                if te.executed_at:
                    stamps.append(te.executed_at)
            if stamps:
                p.updated_at = max(stamps)
            elif not p.updated_at:
                p.updated_at = p.created_at or datetime.utcnow()

        for r in releases.values():
            stamps = [r.created_at] if r.created_at else []
            if r.updated_at:
                stamps.append(r.updated_at)
            for req in r.requirements or []:
                if req.updated_at:
                    stamps.append(req.updated_at)
            if stamps:
                r.updated_at = max(stamps)

        db.commit()

        return {
            "projects": len(projects),
            "requirements": len(requirements),
            "tasks": len(tasks),
            "commits": len(commits),
            "tests": len(tests),
            "bugs": len(bugs),
            "releases": len(releases),
            "showcase": {
                "requirement": "REQ-064",
                "task": "TASK-040",
                "test": "TEST-052",
                "bug": "BUG-026",
                "release": "2.2",
                "project": "CRM-X",
            },
        }
    finally:
        if own_session and db:
            db.close()


if __name__ == "__main__":
    result = seed()
    print("Seed complete:", result)
