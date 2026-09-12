from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.llm.orchestrator import LLMOrchestrator
from app.schemas.analysis import AnalyzeRequest
from app.analysis_store import push_analysis

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.post("/ask")
def ask(payload: AnalyzeRequest, db: Session = Depends(get_db)):
    orchestrator = LLMOrchestrator(db)
    history = [h.model_dump() for h in payload.history]
    result = orchestrator.analyze(
        payload.question,
        project_id=payload.project_id,
        history=history,
    )
    result["project_id"] = payload.project_id
    push_analysis(db, result, project_id=payload.project_id)
    return result


PROMPT_CARDS = [
    {
        "id": "root_cause",
        "title": "Kök Neden Analizi",
        "prompt": "Son sprintte başarısız testler neden arttı?",
    },
    {
        "id": "impact",
        "title": "Etki Analizi",
        "prompt": "REQ-064 değişirse neler etkilenir?",
    },
    {
        "id": "go_live",
        "title": "Canlıya Çıkış Değerlendirmesi",
        "prompt": "REL-2.1 yayınlanabilir mi?",
    },
    {
        "id": "risk",
        "title": "Risk Analizi",
        "prompt": "En riskli gereksinim hangisi ve neden?",
    },
    {
        "id": "executive",
        "title": "Yönetici Özeti",
        "prompt": "Tüm projeler için yönetici özeti hazırla: riskler, açık kritik bug'lar, release durumu ve önerilen aksiyonlar.",
    },
    {
        "id": "sprint",
        "title": "Sprint Özeti",
        "prompt": "Aktif sprintlerdeki geciken ve engellenmiş görevleri özetle.",
    },
    {
        "id": "anomaly",
        "title": "Anomali Tespiti",
        "prompt": "Süreçlerde olağandışı sapma veya anomali var mı?",
    },
]


@router.get("/prompts")
def prompt_cards():
    return PROMPT_CARDS
