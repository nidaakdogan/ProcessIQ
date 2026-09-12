"""Data source interfaces — swap PostgreSQL for Jira/ADO/Git later without touching LLM or frontend."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class RequirementDataSource(ABC):
    @abstractmethod
    def get_requirements(
        self,
        project_id: int | None = None,
        status: str | None = None,
        priority: str | None = None,
        updated_since: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        ...


class TaskDataSource(ABC):
    @abstractmethod
    def get_tasks(
        self,
        project_id: int | None = None,
        status: str | None = None,
        sprint: str | None = None,
        requirement_id: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        ...


class CommitDataSource(ABC):
    @abstractmethod
    def get_commits(
        self,
        project_id: int | None = None,
        since: datetime | None = None,
        requirement_id: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        ...


class TestDataSource(ABC):
    @abstractmethod
    def get_tests(
        self,
        project_id: int | None = None,
        result: str | None = None,
        requirement_id: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        ...


class BugDataSource(ABC):
    @abstractmethod
    def get_bugs(
        self,
        project_id: int | None = None,
        status: str | None = None,
        priority: str | None = None,
        severity: str | None = None,
        requirement_id: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        ...


class ReleaseDataSource(ABC):
    @abstractmethod
    def get_releases(
        self,
        project_id: int | None = None,
        status: str | None = None,
        version: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        ...


class ProjectDataSource(ABC):
    @abstractmethod
    def get_projects(self, status: str | None = None) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def get_project_summary(self, project_id: int | None = None) -> dict[str, Any]:
        ...

    @abstractmethod
    def get_dashboard_metrics(self) -> dict[str, Any]:
        ...
