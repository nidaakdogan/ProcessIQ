from pydantic import BaseModel, Field


class HistoryTurn(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = ""
    focus_entity: str | None = None
    intent: str | None = None
    summary: str | None = None


class AnalyzeRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    project_id: int | None = None
    history: list[HistoryTurn] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    risk_level: str
    title: str
    summary: str
    risk_reasons: list[str] = []
    affected_releases: list[str] = []
    affected_items: list[dict] = []
    recommended_actions: list[str] = []
    metrics: dict = {}
    tools_used: list[dict] = []
    mode: str = "llm"
    note: str | None = None
