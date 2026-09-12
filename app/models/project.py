from datetime import datetime, date
from sqlalchemy import String, Text, Integer, Float, DateTime, Date, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.database import Base


def _enum(enum_cls):
    return SAEnum(enum_cls, values_callable=lambda x: [e.value for e in x], native_enum=False)


class Priority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RequirementStatus(str, enum.Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CHANGED = "changed"


class TaskStatus(str, enum.Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"


class TestResult(str, enum.Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class BugStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class ReleaseStatus(str, enum.Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    READY = "ready"
    RELEASED = "released"
    DELAYED = "delayed"


class ProjectStatus(str, enum.Enum):
    ACTIVE = "active"
    PLANNING = "planning"
    TESTING = "testing"
    READY_FOR_RELEASE = "ready_for_release"
    MAINTENANCE = "maintenance"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(_enum(ProjectStatus), default=ProjectStatus.ACTIVE)
    active_sprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    requirements = relationship("Requirement", back_populates="project")
    tasks = relationship("Task", back_populates="project")
    commits = relationship("Commit", back_populates="project")
    tests = relationship("TestCase", back_populates="project")
    bugs = relationship("Bug", back_populates="project")
    releases = relationship("Release", back_populates="project")


class Requirement(Base):
    __tablename__ = "requirements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[Priority] = mapped_column(_enum(Priority), default=Priority.MEDIUM)
    status: Mapped[RequirementStatus] = mapped_column(
        _enum(RequirementStatus), default=RequirementStatus.APPROVED
    )
    module: Mapped[str | None] = mapped_column(String(100), nullable=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    release_id: Mapped[int | None] = mapped_column(ForeignKey("releases.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="requirements")
    release = relationship("Release", back_populates="requirements")
    tasks = relationship("Task", back_populates="requirement")
    commits = relationship("Commit", back_populates="requirement")
    tests = relationship("TestCase", back_populates="requirement")
    bugs = relationship("Bug", back_populates="requirement")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(300))
    assignee: Mapped[str] = mapped_column(String(100))
    status: Mapped[TaskStatus] = mapped_column(_enum(TaskStatus), default=TaskStatus.TODO)
    sprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    estimated_hours: Mapped[float] = mapped_column(Float, default=8.0)
    actual_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    requirement_id: Mapped[int | None] = mapped_column(ForeignKey("requirements.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="tasks")
    requirement = relationship("Requirement", back_populates="tasks")
    commits = relationship("Commit", back_populates="task")


class Commit(Base):
    __tablename__ = "commits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    commit_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    branch: Mapped[str] = mapped_column(String(100))
    developer: Mapped[str] = mapped_column(String(100))
    message: Mapped[str] = mapped_column(Text)
    committed_at: Mapped[datetime] = mapped_column(DateTime)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    requirement_id: Mapped[int | None] = mapped_column(ForeignKey("requirements.id"), nullable=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"), nullable=True)

    project = relationship("Project", back_populates="commits")
    requirement = relationship("Requirement", back_populates="commits")
    task = relationship("Task", back_populates="commits")


class TestCase(Base):
    __tablename__ = "test_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(300))
    result: Mapped[TestResult] = mapped_column(_enum(TestResult), default=TestResult.PASSED)
    executed_at: Mapped[datetime] = mapped_column(DateTime)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    requirement_id: Mapped[int | None] = mapped_column(ForeignKey("requirements.id"), nullable=True)

    project = relationship("Project", back_populates="tests")
    requirement = relationship("Requirement", back_populates="tests")
    bugs = relationship("Bug", back_populates="test")


class Bug(Base):
    __tablename__ = "bugs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(300))
    priority: Mapped[Priority] = mapped_column(_enum(Priority), default=Priority.MEDIUM)
    severity: Mapped[Priority] = mapped_column(_enum(Priority), default=Priority.MEDIUM)
    status: Mapped[BugStatus] = mapped_column(_enum(BugStatus), default=BugStatus.OPEN)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    requirement_id: Mapped[int | None] = mapped_column(ForeignKey("requirements.id"), nullable=True)
    test_id: Mapped[int | None] = mapped_column(ForeignKey("test_cases.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    project = relationship("Project", back_populates="bugs")
    requirement = relationship("Requirement", back_populates="bugs")
    test = relationship("TestCase", back_populates="bugs")


class Release(Base):
    __tablename__ = "releases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(String(32), index=True)
    release_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[ReleaseStatus] = mapped_column(_enum(ReleaseStatus), default=ReleaseStatus.PLANNED)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    project = relationship("Project", back_populates="releases")
    requirements = relationship("Requirement", back_populates="release")


class AnalysisHistory(Base):
    """AI Analiz Merkezi geçmişi — Dashboard 'Son AI Analizleri' buradan beslenir."""

    __tablename__ = "analysis_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(String(300), default="")
    risk_level: Mapped[str] = mapped_column(String(32), default="Orta")
    summary: Mapped[str] = mapped_column(Text, default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    project_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
