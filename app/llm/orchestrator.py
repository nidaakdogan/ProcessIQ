from datetime import datetime, timedelta
from typing import Any
import json
import re

from openai import OpenAI

from app.config import get_settings
from app.services import build_services

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_requirements",
            "description": (
                "Gereksinimleri getir. Revizyon/değişen gereksinim sorularında status=changed "
                "kullan; her kayıtta revision_count alanı vardır."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer"},
                    "status": {
                        "type": "string",
                        "enum": ["draft", "approved", "in_progress", "done", "changed"],
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                    },
                    "updated_within_days": {
                        "type": "integer",
                        "description": "Son N günde güncellenen gereksinimler",
                    },
                    "limit": {"type": "integer", "default": 50},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tasks",
            "description": "Görevleri getir. Yalnızca gecikme, sprint veya engel sorularında kullan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer"},
                    "status": {
                        "type": "string",
                        "enum": ["todo", "in_progress", "blocked", "done"],
                    },
                    "sprint": {"type": "string"},
                    "requirement_id": {"type": "integer"},
                    "limit": {"type": "integer", "default": 50},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_commits",
            "description": "Kod değişikliklerini getir. Yalnızca commit/kod değişikliği sorularında kullan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer"},
                    "within_days": {
                        "type": "integer",
                        "description": "Son N gündeki commitler",
                    },
                    "requirement_id": {"type": "integer"},
                    "limit": {"type": "integer", "default": 50},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tests",
            "description": "Test sonuçlarını getir. Başarısız test sorularında result=failed kullan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer"},
                    "result": {
                        "type": "string",
                        "enum": ["passed", "failed", "skipped"],
                    },
                    "requirement_id": {"type": "integer"},
                    "limit": {"type": "integer", "default": 50},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_bugs",
            "description": "Hataları getir. Yalnızca bug/hata sorularında kullan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer"},
                    "status": {
                        "type": "string",
                        "enum": ["open", "in_progress", "resolved", "closed"],
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                    },
                    "requirement_id": {"type": "integer"},
                    "limit": {"type": "integer", "default": 50},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_releases",
            "description": "Sürüm bilgilerini getir. Yalnızca release/sürüm/riskli sürüm sorularında kullan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer"},
                    "status": {
                        "type": "string",
                        "enum": ["planned", "in_progress", "ready", "released", "delayed"],
                    },
                    "version": {"type": "string"},
                    "limit": {"type": "integer", "default": 20},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_project_summary",
            "description": (
                "Çok kaynaklı proje özeti. YALNIZCA kullanıcı açıkça yönetici özeti, "
                "genel portföy durumu veya çok boyutlu canlıya çıkış riski istediğinde kullan. "
                "Tek konu sorularında (revizyon, test, bug, sürüm) ASLA çağırma."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer"},
                },
            },
        },
    },
]

SYSTEM_PROMPT = """Sen kurumsal bir Yazılım Süreç Analiz ve Karar Destek analistisin.
Kullanıcıyla sohbet edersin ama cevapların chatbot sohbeti değil; kart tabanlı karar destek raporudur.
Genel dashboard özeti ASLA üretme — yalnızca sorulan soruya cevap ver.

Kurallar:
1. ASLA SQL yazma. Sadece tool'ları çağır. Yalnızca soru için gerekli tool'ları kullan.
2. Intent türleri: root_cause | impact | release_readiness | risk | executive_summary | sprint | anomaly
3. Önceki konuşma (history) varsa referansları (REQ/TASK/TEST/BUG/REL) takip et.
4. İlişkileri analiz et: aynı gereksinim, commit, geliştirici, sprint, sürüm.
5. Cevabı saf JSON olarak ver:
{
  "analysis_type": "root_cause",
  "analysis_type_label": "Kök Neden Analizi",
  "risk_level": "low|medium|high|critical",
  "title": "Kısa başlık",
  "conclusion": "Tek net sonuç cümlesi",
  "summary": "conclusion ile aynı veya kısa destek",
  "findings": ["bulgu 1", "bulgu 2"],
  "recommended_actions": ["öneri 1"],
  "related_records": [{"id": "REQ-064", "note": "..."}],
  "impact_chain": [{"kind": "task", "label": "Görev", "count": 8}],
  "focus_entity": "REQ-064 veya null",
  "summary_stats": {},
  "risk_reasons": [{"id": "...", "text": "..."}],
  "affected_records": [{"id": "...", "note": "..."}],
  "metrics": {}
}
6. Türkçe yanıt ver. Spekülasyon yapma.
"""

HEURISTIC_NOTE = (
    "OPENAI_API_KEY tanımlı değil — demo heuristic orkestrasyon kullanıldı. "
    "Key eklenince GPT tool-calling devreye girer."
)

INTENT_LABELS = {
    "root_cause": "Kök Neden Analizi",
    "impact": "Etki Analizi",
    "release_readiness": "Canlıya Çıkış Değerlendirmesi",
    "risk": "Risk Analizi",
    "executive_summary": "Yönetici Özeti",
    "sprint": "Sprint Özeti",
    "anomaly": "Anomali Tespiti",
    "requirement_revisions": "Risk Analizi",
    "failed_tests": "Kök Neden Analizi",
    "risky_releases": "Risk Analizi",
    "delayed_tasks": "Sprint Özeti",
    "critical_bugs": "Risk Analizi",
    "commits": "Risk Analizi",
    "change_risk": "Canlıya Çıkış Değerlendirmesi",
    "requirements": "Risk Analizi",
    "clarify": "Analiz",
}

ENTITY_RE = re.compile(r"\b((?:REQ|TASK|TEST|BUG|REL)-[\w.]+)", re.I)
SOURCE_MODULE_LABELS = {
    "requirements": "Gereksinimler",
    "tasks": "Görevler",
    "commits": "Kod Değişiklikleri",
    "tests": "Testler",
    "bugs": "Hatalar",
    "releases": "Sürümler",
}


def extract_entity(text: str | None) -> str | None:
    if not text:
        return None
    m = ENTITY_RE.search(text)
    if not m:
        return None
    raw = m.group(1)
    prefix, _, rest = raw.partition("-")
    return f"{prefix.upper()}-{rest}"


def resolve_with_history(
    question: str, history: list[dict[str, Any]] | None
) -> tuple[str, str | None]:
    """Takip sorularını önceki focus_entity ile birleştir."""
    focus = extract_entity(question)
    last_focus = None
    for turn in reversed(history or []):
        last_focus = turn.get("focus_entity") or extract_entity(
            turn.get("content") or turn.get("summary") or ""
        )
        if last_focus:
            break

    ql = question.lower().strip()
    follow = any(
        k in ql
        for k in (
            "bunun",
            "bunu",
            "peki",
            "nedeni",
            "detay",
            "daha fazla",
            "ya o",
            "onun",
            "neden",
            "nasıl",
            "hangi",
        )
    ) and len(ql) < 80

    if not focus and last_focus and follow:
        focus = last_focus
        return f"{last_focus} bağlamında: {question}", focus
    if not focus:
        focus = last_focus if follow else None
    return question, focus


def detect_intent(question: str) -> str:
    """Kurumsal analiz türü — genel dashboard varsayılanı yok."""
    q = question.lower()

    if any(k in q for k in ("etki", "etkilen", "değişirse", "degisirse", "impact", "ne etkilenir")):
        return "impact"

    if any(k in q for k in ("anomali", "olağandışı", "olagandisi", "sapma", "anormal")):
        return "anomaly"

    if any(
        k in q
        for k in (
            "risk analiz",
            "en riskli",
            "riskli gereksinim",
            "hangi risk",
        )
    ):
        return "risk"

    if any(
        k in q
        for k in (
            "kök neden",
            "kok neden",
            "neden arttı",
            "neden artti",
            "neden oldu",
            "neden başarısız",
            "neden basarisiz",
            "root cause",
        )
    ) or ("neden" in q and any(k in q for k in ("test", "gecik", "hata", "bug"))):
        return "root_cause"

    if any(
        k in q
        for k in (
            "yayınlanabilir",
            "yayinlanabilir",
            "hazır mı",
            "hazir mi",
            "canlıya çıkış değerl",
            "go-live",
            "go live",
        )
    ) or re.search(r"\brel-[\w.]+", q) or (
        ("release" in q or "sürüm" in q or "surum" in q)
        and any(k in q for k in ("hazır", "hazir", "yayın", "yayin", "canlı", "canli"))
    ):
        return "release_readiness"

    if any(
        k in q
        for k in (
            "yönetici özet",
            "yonetici ozet",
            "portföy özet",
            "executive",
            "tüm projeler için",
        )
    ):
        return "executive_summary"

    if "sprint" in q and any(k in q for k in ("özet", "ozet", "sağlık", "saglik", "durum")):
        return "sprint"
    if any(k in q for k in ("sprint özet", "sprint ozet")):
        return "sprint"

    if any(
        k in q
        for k in (
            "revizyon",
            "revize",
            "değişen gereksinim",
            "degisen gereksinim",
            "en fazla değiş",
            "en fazla degis",
        )
    ):
        return "requirement_revisions"

    if any(k in q for k in ("başarısız test", "basarisiz test", "failed test", "test başarısız")):
        return "root_cause"

    if any(k in q for k in ("riskli sürüm", "riskli surum", "risky release")):
        return "risky_releases"

    if re.search(r"release\s*[\d.]+", q) or re.search(r"sürüm\s*[\d.]+", q):
        return "release_readiness"

    if any(k in q for k in ("gecikme", "engellen", "bloke", "blocked", "sprint")):
        return "sprint"

    if any(k in q for k in ("kritik hata", "kritik bug", "açık bug", "acik bug", "critical bug")):
        return "critical_bugs"

    if any(k in q for k in ("kod değişikliği", "kod degisikligi", "commit")):
        return "commits"

    if any(
        k in q
        for k in (
            "canlıya çık",
            "canliya cik",
            "son iki hafta",
            "son 2 hafta",
            "değişikliklerden dolayı",
        )
    ):
        return "change_risk"

    if any(k in q for k in ("sürüm", "surum", "release")):
        return "risky_releases"

    if "test" in q:
        return "root_cause"

    if any(k in q for k in ("bug", "hata")):
        return "critical_bugs"

    if any(k in q for k in ("gereksinim", "requirement", "req-")):
        return "risk"

    if any(k in q for k in ("özet", "ozet", "genel durum", "nasıl gidiyor", "nasil gidiyor")):
        return "executive_summary"

    return "clarify"


def _data_sources_from_tools(tools_used: list[dict[str, Any]]) -> dict[str, int]:
    mapping = {
        "get_requirements": "requirements",
        "get_tasks": "tasks",
        "get_commits": "commits",
        "get_tests": "tests",
        "get_bugs": "bugs",
        "get_releases": "releases",
    }
    sources: dict[str, int] = {
        "requirements": 0,
        "tasks": 0,
        "commits": 0,
        "tests": 0,
        "bugs": 0,
        "releases": 0,
    }
    for t in tools_used:
        key = mapping.get(t.get("tool", ""))
        if key:
            sources[key] += int(t.get("count") or 0)
    return sources


def _empty_sources() -> dict[str, int]:
    return {
        "requirements": 0,
        "tasks": 0,
        "commits": 0,
        "tests": 0,
        "bugs": 0,
        "releases": 0,
    }


def _modules_from_sources(sources: dict[str, int] | None) -> list[str]:
    out = []
    for key, label in SOURCE_MODULE_LABELS.items():
        if sources and int(sources.get(key) or 0) > 0:
            out.append(label)
    return out


def finalize_card_response(result: dict[str, Any], intent: str) -> dict[str, Any]:
    """Kart UI alanlarını doldur (conclusion / findings / …)."""
    result.setdefault("intent", intent)
    result["analysis_type"] = intent
    result["analysis_type_label"] = result.get("analysis_type_label") or INTENT_LABELS.get(
        intent, "Analiz"
    )
    conclusion = result.get("conclusion") or result.get("summary") or ""
    result["conclusion"] = conclusion
    if not result.get("summary"):
        result["summary"] = conclusion

    findings = result.get("findings")
    if not findings:
        findings = []
        for item in result.get("risk_reasons") or []:
            if isinstance(item, dict):
                text = item.get("text") or item.get("note") or ""
                eid = item.get("id")
                findings.append(f"{eid}: {text}" if eid and eid != "—" and text else text or str(item))
            else:
                findings.append(str(item))
        stats = result.get("summary_stats") or {}
        for k, v in stats.items():
            findings.append(f"{k.replace('_', ' ')}: {v}")
        result["findings"] = findings[:12]
    else:
        # normalize to strings
        norm = []
        for f in findings:
            if isinstance(f, dict):
                norm.append(f.get("text") or f.get("note") or str(f))
            else:
                norm.append(str(f))
        result["findings"] = norm

    if not result.get("related_records"):
        result["related_records"] = result.get("affected_records") or []

    result.setdefault("impact_chain", result.get("impact_chain") or [])
    result.setdefault("focus_entity", result.get("focus_entity") or extract_entity(conclusion))
    result["modules_used"] = result.get("modules_used") or _modules_from_sources(
        result.get("data_sources")
    )
    result.setdefault("recommended_actions", result.get("recommended_actions") or [])
    return result


def _base_result(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "risk_level": "low",
        "title": "Analiz",
        "summary": "",
        "conclusion": "",
        "findings": [],
        "summary_stats": {},
        "risk_reasons": [],
        "affected_requirements": [],
        "delayed_tasks": [],
        "failed_tests": [],
        "critical_bugs": [],
        "affected_releases": [],
        "affected_records": [],
        "related_records": [],
        "affected_items": [],
        "recommended_actions": [],
        "impact_chain": [],
        "focus_entity": None,
        "modules_used": [],
        "metrics": {},
        "data_sources": _empty_sources(),
        "tools_used": [],
        "mode": "heuristic",
        "note": HEURISTIC_NOTE,
    }
    base.update(overrides)
    return base


class LLMOrchestrator:
    def __init__(self, db):
        self.services = build_services(db)
        self.settings = get_settings()
        self.client = OpenAI(api_key=self.settings.openai_api_key) if self.settings.openai_api_key else None

    def _execute_tool(self, name: str, args: dict[str, Any]) -> Any:
        if name == "get_requirements":
            updated_since = None
            days = args.pop("updated_within_days", None)
            if days:
                updated_since = datetime.utcnow() - timedelta(days=int(days))
            return self.services["requirements"].get_requirements(
                project_id=args.get("project_id"),
                status=args.get("status"),
                priority=args.get("priority"),
                updated_since=updated_since,
                limit=args.get("limit", 50),
            )
        if name == "get_tasks":
            return self.services["tasks"].get_tasks(
                project_id=args.get("project_id"),
                status=args.get("status"),
                sprint=args.get("sprint"),
                requirement_id=args.get("requirement_id"),
                limit=args.get("limit", 50),
            )
        if name == "get_commits":
            since = None
            days = args.get("within_days")
            if days:
                since = datetime.utcnow() - timedelta(days=int(days))
            return self.services["commits"].get_commits(
                project_id=args.get("project_id"),
                since=since,
                requirement_id=args.get("requirement_id"),
                limit=args.get("limit", 50),
            )
        if name == "get_tests":
            return self.services["tests"].get_tests(
                project_id=args.get("project_id"),
                result=args.get("result"),
                requirement_id=args.get("requirement_id"),
                limit=args.get("limit", 50),
            )
        if name == "get_bugs":
            return self.services["bugs"].get_bugs(
                project_id=args.get("project_id"),
                status=args.get("status"),
                priority=args.get("priority"),
                severity=args.get("severity"),
                requirement_id=args.get("requirement_id"),
                limit=args.get("limit", 50),
            )
        if name == "get_releases":
            return self.services["releases"].get_releases(
                project_id=args.get("project_id"),
                status=args.get("status"),
                version=args.get("version"),
                limit=args.get("limit", 20),
            )
        if name == "get_project_summary":
            return self.services["projects"].get_project_summary(
                project_id=args.get("project_id")
            )
        return {"error": f"Unknown tool: {name}"}

    def analyze(
        self,
        question: str,
        project_id: int | None = None,
        history: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        self._project_id = project_id
        resolved, focus_hint = resolve_with_history(question, history)
        intent = detect_intent(resolved)

        if not self.client:
            result = self._heuristic_analyze(
                resolved, project_id=project_id, focus_entity=focus_hint, intent=intent
            )
            result["question"] = question
            result["resolved_question"] = resolved
            if focus_hint and not result.get("focus_entity"):
                result["focus_entity"] = focus_hint
            return finalize_card_response(result, result.get("intent") or intent)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]
        if history:
            hist_bits = []
            for turn in history[-6:]:
                role = turn.get("role", "user")
                content = turn.get("content") or turn.get("summary") or ""
                fe = turn.get("focus_entity") or ""
                hist_bits.append(f"{role}: {content}" + (f" [focus={fe}]" if fe else ""))
            messages.append(
                {
                    "role": "user",
                    "content": "Önceki konuşma:\n" + "\n".join(hist_bits),
                }
            )
        messages.append(
            {
                "role": "user",
                "content": (
                    f"Intent ipucu: {intent} ({INTENT_LABELS.get(intent, intent)})\n"
                    f"Soru: {resolved}"
                    + (f"\nOdak kayıt: {focus_hint}" if focus_hint else "")
                    + (
                        f"\n\n(Kapsam: yalnızca project_id={project_id} kayıtlarını kullan.)"
                        if project_id
                        else ""
                    )
                    + "\n\nYalnızca bu soruyu kart formatında cevapla; ilgisiz KPI ekleme."
                ),
            },
        )

        tools_used: list[dict[str, Any]] = []
        max_rounds = 4

        for _ in range(max_rounds):
            response = self.client.chat.completions.create(
                model=self.settings.openai_model,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
                temperature=0.2,
            )
            msg = response.choices[0].message

            if not msg.tool_calls:
                content = msg.content or ""
                parsed = self._parse_json_response(content)
                parsed["tools_used"] = tools_used
                parsed["mode"] = "llm"
                parsed["data_sources"] = _data_sources_from_tools(tools_used)
                parsed.setdefault("summary_stats", {})
                parsed["question"] = question
                parsed["resolved_question"] = resolved
                parsed["intent"] = intent
                if focus_hint and not parsed.get("focus_entity"):
                    parsed["focus_entity"] = focus_hint
                return finalize_card_response(parsed, intent)

            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                }
            )

            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments or "{}")
                if project_id and "project_id" not in args:
                    args["project_id"] = project_id
                result = self._execute_tool(tc.function.name, args)
                tools_used.append(
                    {
                        "tool": tc.function.name,
                        "args": args,
                        "count": len(result) if isinstance(result, list) else 1,
                    }
                )
                payload = result
                if isinstance(result, list) and len(result) > 40:
                    payload = result[:40]
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(payload, ensure_ascii=False, default=str),
                    }
                )

        return finalize_card_response(
            {
                "question": question,
                "resolved_question": resolved,
                "intent": intent,
                "focus_entity": focus_hint,
                "risk_level": "medium",
                "title": "Analiz tamamlanamadı",
                "summary": "Tool çağrı limitine ulaşıldı. Lütfen soruyu daraltın.",
                "conclusion": "Tool çağrı limitine ulaşıldı. Lütfen soruyu daraltın.",
                "findings": [],
                "risk_reasons": [],
                "affected_releases": [],
                "affected_items": [],
                "recommended_actions": ["Soruyu daha spesifik hale getirin."],
                "metrics": {},
                "tools_used": tools_used,
                "mode": "llm",
            },
            intent,
        )

    def _parse_json_response(self, content: str) -> dict[str, Any]:
        text = content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
        return {
            "risk_level": "medium",
            "title": "Analiz Sonucu",
            "summary": content,
            "risk_reasons": [],
            "affected_requirements": [],
            "delayed_tasks": [],
            "failed_tests": [],
            "critical_bugs": [],
            "affected_releases": [],
            "affected_items": [],
            "recommended_actions": [],
            "metrics": {},
        }

    def _track(self, tools_used: list, name: str, args: dict, count: int) -> None:
        tools_used.append({"tool": name, "args": args, "count": count})

    def _heuristic_analyze(
        self,
        question: str,
        project_id: int | None = None,
        focus_entity: str | None = None,
        intent: str | None = None,
    ) -> dict[str, Any]:
        """OpenAI key yoksa: soru intent'ine göre yalnızca ilgili kaynakları kullan."""
        intent = intent or detect_intent(question)
        pid = project_id
        handlers = {
            "root_cause": self._h_root_cause,
            "impact": self._h_impact,
            "anomaly": self._h_anomaly,
            "risk": self._h_risk,
            "sprint": self._h_delayed_tasks,
            "requirement_revisions": self._h_requirement_revisions,
            "failed_tests": self._h_failed_tests,
            "risky_releases": self._h_risky_releases,
            "release_readiness": self._h_release_readiness,
            "delayed_tasks": self._h_delayed_tasks,
            "critical_bugs": self._h_critical_bugs,
            "commits": self._h_commits,
            "requirements": self._h_requirements,
            "change_risk": self._h_change_risk,
            "executive_summary": self._h_executive_summary,
            "clarify": self._h_clarify,
        }
        handler = handlers.get(intent, self._h_clarify)
        try:
            result = handler(question, pid, focus_entity=focus_entity)  # type: ignore[misc]
        except TypeError:
            result = handler(question, pid)
        result["intent"] = intent
        result["analysis_type_label"] = INTENT_LABELS.get(intent, "Analiz")
        if focus_entity and not result.get("focus_entity"):
            result["focus_entity"] = focus_entity
        return result

    def _h_clarify(self, question: str, pid: int | None) -> dict[str, Any]:
        return _base_result(
            risk_level="low",
            title="Soru netleştirilmeli",
            summary=(
                "Sorunuz birden fazla süreç alanına işaret etmiyor veya yeterince spesifik değil. "
                "Örn. revize gereksinimler, başarısız testler, riskli sürümler, geciken görevler "
                "veya kritik hatalar diye sorun; yalnızca ilgili veri analiz edilir."
            ),
            recommended_actions=[
                "Analizi tek bir varlık türüne odaklayın (gereksinim, görev, test, hata veya sürüm).",
                "Hazır soru kartlarından birini seçebilirsiniz.",
            ],
            tools_used=[],
            data_sources=_empty_sources(),
        )

    def _h_requirement_revisions(self, question: str, pid: int | None) -> dict[str, Any]:
        tools_used: list[dict[str, Any]] = []
        changed = self.services["requirements"].get_requirements(
            status="changed", limit=200, project_id=pid
        )
        self._track(tools_used, "get_requirements", {"status": "changed", "project_id": pid}, len(changed))

        all_reqs = self.services["requirements"].get_requirements(limit=500, project_id=pid)
        self._track(tools_used, "get_requirements", {"project_id": pid, "limit": 500}, len(all_reqs))

        ranked = sorted(
            all_reqs,
            key=lambda r: (
                int(r.get("revision_count") or 0),
                1 if r.get("status") == "changed" else 0,
            ),
            reverse=True,
        )
        # "En fazla revizyon" = üst dilim; changed olanlar her zaman aday
        top = ranked[:12]
        if all_reqs:
            counts = sorted(int(r.get("revision_count") or 0) for r in all_reqs)
            p80 = counts[max(0, int(len(counts) * 0.8) - 1)]
            churn_threshold = max(3, p80)
        else:
            churn_threshold = 3
        high_churn = [
            r
            for r in all_reqs
            if int(r.get("revision_count") or 0) >= churn_threshold or r.get("status") == "changed"
        ]

        records = [
            {
                "id": r["external_id"],
                "note": (
                    f"{r['title']} · {int(r.get('revision_count') or 0)} revizyon · "
                    f"durum={r['status']}"
                    + (f" · {r.get('project_code')}" if r.get("project_code") else "")
                ),
            }
            for r in top
        ]
        reasons = [
            {
                "id": r["external_id"],
                "text": f"{int(r.get('revision_count') or 0)} revizyon (durum: {r['status']}).",
            }
            for r in top[:8]
        ]
        max_rev = int(top[0].get("revision_count") or 0) if top else 0
        risk = "high" if max_rev >= 5 or len(changed) >= 5 else ("medium" if high_churn else "low")

        return _base_result(
            risk_level=risk,
            title="Gereksinim Revizyon Analizi",
            summary=(
                f"Gereksinimler revision_count’a göre sıralandı. "
                f"En çok revize edilen: {top[0]['external_id']} ({max_rev} revizyon). "
                f"{len(changed)} kayıt 'changed' durumunda; "
                f"{len(high_churn)} gereksinim yüksek churn "
                f"({churn_threshold}+ revizyon veya changed)."
                if top
                else "Revizyon verisi bulunamadı."
            ),
            summary_stats={
                "changed_status": len(changed),
                "high_churn": len(high_churn),
                "top_revision_count": max_rev,
            },
            risk_reasons=reasons,
            affected_requirements=records,
            affected_records=records,
            affected_items=[{"id": r["id"], "type": "requirement", "note": r["note"]} for r in records],
            recommended_actions=[
                "Listedeki üst gereksinimler için change-impact review planlayın.",
                "changed durumundaki maddeleri onay kapısından geçirmeden geliştirmeye almayın.",
            ]
            if top
            else ["Revizyon takibi için gereksinim durum güncellemelerini gözden geçirin."],
            metrics={
                "changed_status": len(changed),
                "high_churn": len(high_churn),
                "top_revision_count": max_rev,
            },
            # UI'da yalnızca gerçekten kullanılan kayıt sayısı: sıralama için taranan + öne çıkan
            data_sources={**_empty_sources(), "requirements": len(all_reqs)},
            tools_used=tools_used,
        )

    def _h_failed_tests(self, question: str, pid: int | None) -> dict[str, Any]:
        tools_used: list[dict[str, Any]] = []
        failed = self.services["tests"].get_tests(result="failed", limit=2000, project_id=pid)
        self._track(tools_used, "get_tests", {"result": "failed", "project_id": pid}, len(failed))

        records = [
            {
                "id": t["external_id"],
                "note": (
                    f"{t['title']}"
                    + (f" · {t.get('requirement_external_id')}" if t.get("requirement_external_id") else "")
                    + (f" · {t.get('project_code')}" if t.get("project_code") else "")
                ),
            }
            for t in failed[:15]
        ]
        # Modül / gereksinim yoğunluğu
        by_req: dict[str, int] = {}
        for t in failed:
            key = t.get("requirement_external_id") or "—"
            by_req[key] = by_req.get(key, 0) + 1
        top_reqs = sorted(by_req.items(), key=lambda x: x[1], reverse=True)[:5]
        reasons = [
            {"id": rid, "text": f"{cnt} başarısız test bu gereksinime bağlı."}
            for rid, cnt in top_reqs
            if rid != "—"
        ]
        if not reasons and failed:
            reasons = [{"id": failed[0]["external_id"], "text": "Başarısız test kaydı."}]

        risk = "critical" if len(failed) >= 10 else ("high" if len(failed) >= 5 else ("medium" if failed else "low"))
        return _base_result(
            risk_level=risk,
            title="Başarısız Test Analizi",
            summary=(
                f"{len(failed)} başarısız test kaydı incelendi. "
                + (
                    f"En çok etkilenen gereksinim: {top_reqs[0][0]} ({top_reqs[0][1]} test)."
                    if top_reqs and top_reqs[0][0] != "—"
                    else "İlişkili gereksinim dağılımı sınırlı."
                )
                if failed
                else "Başarısız test kaydı bulunamadı."
            ),
            summary_stats={"failed_tests": len(failed)},
            risk_reasons=reasons,
            failed_tests=records,
            affected_records=records,
            recommended_actions=[
                "Başarısız testleri öncelik sırasıyla yeniden çalıştırın.",
                "Yoğunlaşan gereksinimler için kök neden analizi açın.",
            ]
            if failed
            else ["Test suite yeşil; izlemeye devam edin."],
            metrics={"failed_tests": len(failed)},
            data_sources={**_empty_sources(), "tests": len(failed)},
            tools_used=tools_used,
        )

    def _h_risky_releases(self, question: str, pid: int | None) -> dict[str, Any]:
        tools_used: list[dict[str, Any]] = []
        releases = self.services["releases"].get_releases(limit=500, project_id=pid)
        self._track(tools_used, "get_releases", {"project_id": pid}, len(releases))
        risky = [r for r in releases if r.get("is_risky")]
        risky.sort(key=lambda r: float(r.get("risk_score") or 0), reverse=True)

        records = [
            {
                "id": f"REL-{r['version']}",
                "note": (
                    f"Risk skoru {r.get('risk_score')} · durum={r.get('status')}"
                    + (f" · {r.get('project_code')}" if r.get("project_code") else "")
                ),
            }
            for r in risky[:12]
        ]
        reasons = [
            {
                "id": f"REL-{r['version']}",
                "text": f"Risk skoru {r.get('risk_score')} — {r.get('status')}.",
            }
            for r in risky[:6]
        ]
        risk = "critical" if len(risky) >= 4 else ("high" if risky else "low")
        return _base_result(
            risk_level=risk,
            title="Riskli Sürüm Analizi",
            summary=(
                f"{len(releases)} sürüm içinden {len(risky)} tanesi riskli işaretlendi. "
                + (
                    f"En yüksek risk: REL-{risky[0]['version']} (skor {risky[0].get('risk_score')})."
                    if risky
                    else ""
                )
            ).strip(),
            summary_stats={"risky_releases": len(risky), "total_releases": len(releases)},
            risk_reasons=reasons or [{"id": "—", "text": "Riskli sürüm yok."}],
            affected_releases=records,
            affected_records=records,
            recommended_actions=[
                "Yüksek skorlu sürümler için go-live checklist'i zorunlu tutun.",
                "Risk skoru düşmeden yayına alma kararını erteleyin.",
            ]
            if risky
            else ["Aktif sürümlerde belirgin risk skoru yok."],
            metrics={"risky_releases": len(risky), "total_releases": len(releases)},
            data_sources={**_empty_sources(), "releases": len(releases)},
            tools_used=tools_used,
        )

    def _h_release_readiness(
        self, question: str, pid: int | None, focus_entity: str | None = None
    ) -> dict[str, Any]:
        tools_used: list[dict[str, Any]] = []
        q = question.lower()
        version_match = re.search(r"(\d+\.\d+(?:\.\d+)?)", q)
        version = version_match.group(1) if version_match else None
        if not version and focus_entity and focus_entity.upper().startswith("REL-"):
            version = focus_entity.split("-", 1)[-1]

        releases = self.services["releases"].get_releases(
            version=version, limit=50, project_id=pid
        ) if version else self.services["releases"].get_releases(limit=50, project_id=pid)
        self._track(
            tools_used,
            "get_releases",
            {"version": version, "project_id": pid},
            len(releases),
        )
        if version and releases:
            exact = [r for r in releases if str(r.get("version")) == version]
            if exact:
                releases = exact
            else:
                # 2.1 → tercih et; ilike 2.1.1'i yanlış seçmesin
                prefix = [r for r in releases if str(r.get("version", "")).startswith(version)]
                releases = sorted(
                    prefix or releases,
                    key=lambda r: (0 if str(r.get("version")) == version else 1, str(r.get("version"))),
                )

        if not releases:
            return _base_result(
                title="Sürüm Hazırlık Analizi",
                summary=f"'{version or 'belirtilen'}' sürümü bulunamadı." if version else "Sürüm kaydı yok.",
                tools_used=tools_used,
                data_sources={**_empty_sources(), "releases": 0},
            )

        target = releases[0]
        # Aynı proje kapsamındaki bağlı sinyaller — yalnızca bu sürüm değerlendirmesi için
        failed = self.services["tests"].get_tests(result="failed", limit=2000, project_id=pid)
        bugs = self.services["bugs"].get_bugs(status="active", severity="critical", limit=500, project_id=pid)
        self._track(tools_used, "get_tests", {"result": "failed", "project_id": pid}, len(failed))
        self._track(tools_used, "get_bugs", {"status": "active", "severity": "critical", "project_id": pid}, len(bugs))

        # Sürüme bağlı filtre (release_version alanı varsa)
        ver = target.get("version")
        failed_rel = [t for t in failed if t.get("release_version") == ver] or failed[:8]
        bugs_rel = [b for b in bugs if b.get("release_version") == ver] or bugs[:8]

        is_risky = bool(target.get("is_risky"))
        status = target.get("status")
        ready = status in ("ready", "released") and not is_risky and not failed_rel[:1]

        records = [
            {
                "id": f"REL-{ver}",
                "note": f"durum={status} · risk_score={target.get('risk_score')} · is_risky={is_risky}",
            }
        ]
        for t in failed_rel[:5]:
            records.append({"id": t["external_id"], "note": f"Başarısız test · {t['title']}"})
        for b in bugs_rel[:5]:
            records.append({"id": b["external_id"], "note": f"Kritik hata · {b['title']}"})

        reasons = [{"id": f"REL-{ver}", "text": f"Sürüm durumu: {status}, risk skoru: {target.get('risk_score')}."}]
        if failed_rel:
            reasons.append({"id": failed_rel[0]["external_id"], "text": f"{len(failed_rel)} başarısız test sürüm kapsamıyla ilişkili."})
        if bugs_rel:
            reasons.append({"id": bugs_rel[0]["external_id"], "text": f"{len(bugs_rel)} kritik açık hata mevcut."})

        verdict = "Canlıya öneriliyor." if ready else "Canlıya önerilmiyor."
        findings = [
            f"{len(bugs_rel)} kritik bug",
            f"{len(failed_rel)} başarısız test",
            f"Risk skoru {target.get('risk_score')}",
            f"Durum: {status}",
        ]
        return _base_result(
            risk_level="critical" if is_risky or bugs_rel else ("high" if failed_rel else "medium"),
            title=f"Sürüm {ver} Hazırlık Analizi",
            summary=f"REL-{ver}: {verdict} Durum={status}, risk_score={target.get('risk_score')}.",
            conclusion=f"REL-{ver}: {verdict}",
            findings=findings,
            focus_entity=f"REL-{ver}",
            summary_stats={
                "risk_score": target.get("risk_score"),
                "failed_tests": len(failed_rel),
                "critical_bugs": len(bugs_rel),
            },
            risk_reasons=reasons,
            failed_tests=[{"id": t["external_id"], "note": t["title"]} for t in failed_rel[:8]],
            critical_bugs=[{"id": b["external_id"], "note": b["title"]} for b in bugs_rel[:8]],
            affected_releases=[{"id": f"REL-{ver}", "note": f"status={status}"}],
            affected_records=records,
            related_records=records,
            recommended_actions=[
                "Canlıya çıkış ertelenmeli." if not ready else "Go-live checklist tamamlandıktan sonra yayınlanabilir.",
                "Kritik hatalar kapatılmadan yayına çıkmayın." if bugs_rel else "Kritik hata yok — kalite kapısını doğrulayın.",
                "Başarısız testleri yeşile çevirin." if failed_rel else "Test sinyali temiz.",
            ],
            metrics={
                "risk_score": target.get("risk_score"),
                "failed_tests": len(failed_rel),
                "critical_bugs": len(bugs_rel),
            },
            data_sources={
                **_empty_sources(),
                "releases": len(releases),
                "tests": len(failed_rel),
                "bugs": len(bugs_rel),
            },
            tools_used=tools_used,
        )

    def _h_delayed_tasks(self, question: str, pid: int | None) -> dict[str, Any]:
        tools_used: list[dict[str, Any]] = []
        tasks = self.services["tasks"].get_tasks(limit=2000, project_id=pid)
        self._track(tools_used, "get_tasks", {"project_id": pid}, len(tasks))
        delayed = [t for t in tasks if t.get("is_delayed")]
        blocked = [t for t in delayed if t.get("status") == "blocked"]
        overrun = [t for t in delayed if t.get("status") != "blocked"]

        records = [
            {
                "id": t["external_id"],
                "note": f"{t['title']} · {t['status']} · {t.get('assignee') or '—'}",
            }
            for t in delayed[:15]
        ]
        reasons = []
        if blocked:
            reasons.append({"id": blocked[0]["external_id"], "text": f"{len(blocked)} görev bloke durumda."})
        if overrun:
            reasons.append({"id": overrun[0]["external_id"], "text": f"{len(overrun)} görev süre aşımında."})
        if not reasons:
            reasons.append({"id": "—", "text": "Geciken görev yok."})

        return _base_result(
            risk_level="high" if len(delayed) >= 8 else ("medium" if delayed else "low"),
            title="Sprint Özeti",
            summary=(
                f"{len(delayed)} geciken görev bulundu "
                f"({len(blocked)} bloke, {len(overrun)} süre aşımı)."
            ),
            conclusion=(
                f"Sprint sağlığı: {len(delayed)} geciken görev "
                f"({len(blocked)} bloke, {len(overrun)} süre aşımı)."
            ),
            findings=[
                f"{len(delayed)} geciken görev",
                f"{len(blocked)} bloke görev",
                f"{len(overrun)} süre aşımı",
            ],
            summary_stats={
                "delayed_tasks": len(delayed),
                "blocked_tasks": len(blocked),
                "overrun_tasks": len(overrun),
            },
            risk_reasons=reasons,
            delayed_tasks=records,
            affected_records=records,
            recommended_actions=[
                "Bloke görevlerin engellerini günlük stand-up'ta açın.",
                "Süre aşımı olan işler için tahminleri revize edin.",
            ]
            if delayed
            else ["Gecikme sinyali yok."],
            metrics={
                "delayed_tasks": len(delayed),
                "blocked_tasks": len(blocked),
                "overrun_tasks": len(overrun),
            },
            data_sources={**_empty_sources(), "tasks": len(tasks)},
            tools_used=tools_used,
        )

    def _h_critical_bugs(self, question: str, pid: int | None) -> dict[str, Any]:
        tools_used: list[dict[str, Any]] = []
        bugs = self.services["bugs"].get_bugs(
            status="active", severity="critical", limit=2000, project_id=pid
        )
        self._track(
            tools_used,
            "get_bugs",
            {"status": "active", "severity": "critical", "project_id": pid},
            len(bugs),
        )
        records = [
            {
                "id": b["external_id"],
                "note": f"{b['title']} · {b.get('status')} · {b.get('project_code') or ''}".strip(" ·"),
            }
            for b in bugs[:15]
        ]
        reasons = [
            {"id": b["external_id"], "text": f"Kritik açık hata: {b['title']}"}
            for b in bugs[:6]
        ]
        return _base_result(
            risk_level="critical" if len(bugs) >= 3 else ("high" if bugs else "low"),
            title="Kritik Hata Analizi",
            summary=(
                f"{len(bugs)} kritik açık hata incelendi."
                + (f" Örnek: {bugs[0]['external_id']}." if bugs else "")
            ),
            summary_stats={"critical_bugs": len(bugs)},
            risk_reasons=reasons or [{"id": "—", "text": "Kritik açık hata yok."}],
            critical_bugs=records,
            affected_records=records,
            recommended_actions=[
                "Kritik hataları hotfix önceliğine alın.",
                "Etkilenen sürümler için go-live'ı dondurun.",
            ]
            if bugs
            else ["Kritik açık hata bulunmuyor."],
            metrics={"critical_bugs": len(bugs)},
            data_sources={**_empty_sources(), "bugs": len(bugs)},
            tools_used=tools_used,
        )

    def _h_commits(self, question: str, pid: int | None) -> dict[str, Any]:
        tools_used: list[dict[str, Any]] = []
        since = datetime.utcnow() - timedelta(days=14)
        commits = self.services["commits"].get_commits(since=since, limit=500, project_id=pid)
        self._track(tools_used, "get_commits", {"within_days": 14, "project_id": pid}, len(commits))
        records = [
            {
                "id": c.get("external_id") or c.get("commit_hash", "")[:8],
                "note": f"{c.get('message') or c.get('title') or '—'} · {c.get('author') or ''}".strip(" ·"),
            }
            for c in commits[:15]
        ]
        return _base_result(
            risk_level="medium" if len(commits) >= 40 else "low",
            title="Kod Değişikliği Analizi",
            summary=f"Son 14 günde {len(commits)} kod değişikliği incelendi.",
            summary_stats={"commits_14d": len(commits)},
            risk_reasons=[
                {"id": records[0]["id"], "text": "Son dönem commit yoğunluğu yüksek."}
            ]
            if len(commits) >= 40 and records
            else [{"id": "—", "text": "Commit hacmi normal aralıkta."}],
            affected_records=records,
            recommended_actions=[
                "Yoğun değişen modüllerde ek code review uygulayın.",
            ],
            metrics={"commits_14d": len(commits)},
            data_sources={**_empty_sources(), "commits": len(commits)},
            tools_used=tools_used,
        )

    def _h_requirements(self, question: str, pid: int | None) -> dict[str, Any]:
        tools_used: list[dict[str, Any]] = []
        reqs = self.services["requirements"].get_requirements(limit=500, project_id=pid)
        self._track(tools_used, "get_requirements", {"project_id": pid}, len(reqs))
        changed = [r for r in reqs if r.get("status") == "changed"]
        high = [r for r in reqs if r.get("priority") in ("high", "critical")]
        focus = changed or high or reqs[:10]
        records = [
            {
                "id": r["external_id"],
                "note": f"{r['title']} · {r['status']} · öncelik={r['priority']}",
            }
            for r in focus[:12]
        ]
        return _base_result(
            risk_level="medium" if changed else "low",
            title="Gereksinim Analizi",
            summary=(
                f"{len(reqs)} gereksinim tarandı; {len(changed)} tanesi 'changed' durumunda, "
                f"{len(high)} yüksek/kritik öncelikli."
            ),
            summary_stats={
                "requirements": len(reqs),
                "changed_status": len(changed),
                "high_priority": len(high),
            },
            risk_reasons=[
                {"id": r["external_id"], "text": f"Durum={r['status']}, öncelik={r['priority']}"}
                for r in focus[:6]
            ],
            affected_requirements=records,
            affected_records=records,
            recommended_actions=[
                "Changed gereksinimleri yeniden onaylatın." if changed else "Öncelikli gereksinimlerin kapsamını sabitleyin.",
            ],
            metrics={"requirements": len(reqs), "changed_status": len(changed)},
            data_sources={**_empty_sources(), "requirements": len(reqs)},
            tools_used=tools_used,
        )

    def _h_change_risk(self, question: str, pid: int | None) -> dict[str, Any]:
        """Son dönem değişikliklere bağlı riskli işler — odak: değişen gereksinimler."""
        tools_used: list[dict[str, Any]] = []
        since = datetime.utcnow() - timedelta(days=14)
        commits = self.services["commits"].get_commits(since=since, limit=500, project_id=pid)
        requirements = self.services["requirements"].get_requirements(
            updated_since=since, limit=500, project_id=pid
        )
        changed = self.services["requirements"].get_requirements(
            status="changed", limit=200, project_id=pid
        )
        self._track(tools_used, "get_commits", {"within_days": 14, "project_id": pid}, len(commits))
        self._track(
            tools_used,
            "get_requirements",
            {"updated_within_days": 14, "project_id": pid},
            len(requirements),
        )
        self._track(tools_used, "get_requirements", {"status": "changed", "project_id": pid}, len(changed))

        changed_ids = {c["requirement_id"] for c in commits if c.get("requirement_id")}
        by_id = {r["id"]: r for r in requirements}
        for r in changed:
            by_id[r["id"]] = r

        risky = []
        for rid, req in by_id.items():
            score = int(req.get("revision_count") or 0)
            if rid in changed_ids:
                score += 2
            if req.get("status") == "changed":
                score += 3
            if score >= 2:
                risky.append((score, req))
        risky.sort(key=lambda x: x[0], reverse=True)
        top = [r for _, r in risky[:10]]

        records = [
            {
                "id": r["external_id"],
                "note": (
                    f"{r['title']} · revizyon={r.get('revision_count', 0)} · "
                    f"durum={r['status']}"
                ),
            }
            for r in top
        ]
        return _base_result(
            risk_level="high" if len(top) >= 5 else ("medium" if top else "low"),
            title="Değişiklik Kaynaklı Canlıya Çıkış Riski",
            summary=(
                f"Son 14 günde {len(commits)} commit ve {len(requirements)} güncellenmiş gereksinim "
                f"incelendi. Canlıya çıkış açısından {len(top)} gereksinim öne çıkıyor "
                f"({len(changed)} changed durumunda)."
            ),
            summary_stats={
                "risky_requirements": len(top),
                "changed_status": len(changed),
                "commits_14d": len(commits),
            },
            risk_reasons=[
                {
                    "id": r["external_id"],
                    "text": f"Son dönem değişim + durum={r['status']}, revizyon={r.get('revision_count', 0)}",
                }
                for r in top[:6]
            ]
            or [{"id": "—", "text": "Belirgin değişiklik riski yok."}],
            affected_requirements=records,
            affected_records=records,
            recommended_actions=[
                "Öne çıkan gereksinimler için ek regression planı çıkarın.",
                "Changed durumundaki maddeleri yayına alma öncesi kilitleyin.",
            ],
            metrics={
                "risky_requirements": len(top),
                "commits_14d": len(commits),
                "changed_status": len(changed),
            },
            data_sources={
                **_empty_sources(),
                "requirements": len(by_id),
                "commits": len(commits),
            },
            tools_used=tools_used,
        )

    def _h_executive_summary(self, question: str, pid: int | None) -> dict[str, Any]:
        """Yalnızca açıkça yönetici/portföy özeti istendiğinde çok kaynaklı özet."""
        tools_used: list[dict[str, Any]] = []
        dash = self.services["projects"].get_dashboard_metrics(project_id=pid)
        summary = self.services["projects"].get_project_summary(project_id=pid)
        self._track(tools_used, "get_dashboard_metrics", {"project_id": pid}, 1)
        self._track(tools_used, "get_project_summary", {"project_id": pid}, 1)

        kpi_failed = int(dash["cards"]["failed_tests"])
        kpi_critical = int(dash["cards"]["critical_bugs"])
        kpi_delayed = int(dash["cards"]["delayed_tasks"])
        kpi_risky_releases = int(dash["cards"]["risky_releases"])

        from app.metrics import compute_risk_index

        portfolio_index = compute_risk_index(kpi_failed, kpi_critical, kpi_delayed)
        risk_level = "critical" if kpi_critical >= 3 and kpi_failed else (
            "high" if portfolio_index >= 40 else ("medium" if portfolio_index >= 20 else "low")
        )

        reasons = [
            {"id": "KPI", "text": f"{kpi_failed} başarısız test"},
            {"id": "KPI", "text": f"{kpi_critical} kritik açık hata"},
            {"id": "KPI", "text": f"{kpi_delayed} geciken görev"},
            {"id": "KPI", "text": f"{kpi_risky_releases} riskli sürüm"},
        ]
        actions = [
            "Yüksek riskli release'ler için go-live kararı gözden geçirilsin.",
            "Kritik bug'lar kapatılmadan canlıya çıkılmasın.",
            "Engellenmiş/gecikmiş görevler için sprint planı revize edilsin.",
        ]
        return _base_result(
            risk_level=risk_level,
            title="Yönetici Özeti",
            summary=(
                f"Portföy özeti: {kpi_failed} başarısız test, {kpi_critical} kritik hata, "
                f"{kpi_delayed} geciken görev, {kpi_risky_releases} riskli sürüm "
                f"(risk indeksi {portfolio_index})."
            ),
            summary_stats={
                "failed_tests": kpi_failed,
                "critical_bugs": kpi_critical,
                "delayed_tasks": kpi_delayed,
                "risky_releases": kpi_risky_releases,
            },
            risk_reasons=reasons,
            affected_records=reasons,
            recommended_actions=actions,
            metrics={
                "failed_tests": kpi_failed,
                "critical_bugs": kpi_critical,
                "delayed_tasks": kpi_delayed,
                "risky_releases": kpi_risky_releases,
                "risk_index": portfolio_index,
            },
            data_sources={
                "requirements": int(summary.get("risky_requirements") or 0) if isinstance(summary, dict) else 0,
                "tasks": kpi_delayed,
                "commits": int(dash["cards"].get("recent_commits_14d") or 0),
                "tests": kpi_failed,
                "bugs": kpi_critical,
                "releases": kpi_risky_releases,
            },
            tools_used=tools_used,
        )

    def _find_requirement(self, external_id: str, pid: int | None) -> dict[str, Any] | None:
        reqs = self.services["requirements"].get_requirements(limit=500, project_id=pid)
        eid = external_id.upper()
        for r in reqs:
            if str(r.get("external_id", "")).upper() == eid:
                return r
        return None

    def _h_impact(
        self, question: str, pid: int | None, focus_entity: str | None = None
    ) -> dict[str, Any]:
        tools_used: list[dict[str, Any]] = []
        entity = extract_entity(question) or focus_entity
        if not entity or not entity.upper().startswith("REQ-"):
            changed = self.services["requirements"].get_requirements(
                status="changed", limit=50, project_id=pid
            )
            self._track(
                tools_used, "get_requirements", {"status": "changed", "project_id": pid}, len(changed)
            )
            if changed:
                entity = changed[0]["external_id"]
            else:
                return _base_result(
                    title="Etki Analizi",
                    conclusion="Etki analizi için bir gereksinim ID'si belirtin (örn. REQ-064).",
                    summary="Etki analizi için bir gereksinim ID'si belirtin (örn. REQ-064).",
                    findings=["Soru içinde REQ-… kimliği bulunamadı."],
                    recommended_actions=["Örn: REQ-064 değişirse neler etkilenir?"],
                    tools_used=tools_used,
                )

        req = self._find_requirement(entity, pid)
        self._track(tools_used, "get_requirements", {"project_id": pid}, 1 if req else 0)
        if not req:
            return _base_result(
                title="Etki Analizi",
                conclusion=f"{entity} bulunamadı.",
                summary=f"{entity} bulunamadı.",
                focus_entity=entity,
                tools_used=tools_used,
            )

        rid = req["id"]
        tasks = self.services["tasks"].get_tasks(requirement_id=rid, limit=200, project_id=pid)
        commits = self.services["commits"].get_commits(requirement_id=rid, limit=200, project_id=pid)
        tests = self.services["tests"].get_tests(requirement_id=rid, limit=200, project_id=pid)
        bugs = self.services["bugs"].get_bugs(requirement_id=rid, limit=200, project_id=pid)
        releases = self.services["releases"].get_releases(limit=100, project_id=pid)
        self._track(tools_used, "get_tasks", {"requirement_id": rid}, len(tasks))
        self._track(tools_used, "get_commits", {"requirement_id": rid}, len(commits))
        self._track(tools_used, "get_tests", {"requirement_id": rid}, len(tests))
        self._track(tools_used, "get_bugs", {"requirement_id": rid}, len(bugs))
        self._track(tools_used, "get_releases", {"project_id": pid}, len(releases))

        rel_ver = req.get("release_version")
        linked_rels = [r for r in releases if r.get("version") == rel_ver] if rel_ver else []
        rel_count = max(len(linked_rels), 1 if rel_ver else 0)
        chain = [
            {"kind": "task", "label": "Görev", "count": len(tasks)},
            {"kind": "commit", "label": "Commit", "count": len(commits)},
            {"kind": "test", "label": "Test", "count": len(tests)},
            {"kind": "bug", "label": "Bug", "count": len(bugs)},
            {"kind": "release", "label": "Sürüm", "count": rel_count},
        ]
        records = [{"id": entity, "note": f"{req.get('title')} · durum={req.get('status')}"}]
        records += [{"id": t["external_id"], "note": t["title"]} for t in tasks[:4]]
        records += [
            {
                "id": c.get("external_id") or (c.get("commit_hash") or "")[:8],
                "note": c.get("message") or "commit",
            }
            for c in commits[:3]
        ]
        records += [{"id": t["external_id"], "note": t["title"]} for t in tests[:4]]
        records += [{"id": b["external_id"], "note": b["title"]} for b in bugs[:3]]
        if rel_ver:
            records.append({"id": f"REL-{rel_ver}", "note": "Bağlı sürüm"})

        failed_n = sum(1 for t in tests if t.get("result") == "failed")
        return _base_result(
            risk_level="high" if failed_n or bugs else "medium",
            title=f"Etki Analizi — {entity}",
            conclusion=(
                f"{entity} değişirse {len(tasks)} görev, {len(commits)} commit, "
                f"{len(tests)} test, {len(bugs)} hata ve {rel_count} sürüm etkilenir."
            ),
            summary=(
                f"{entity} etki zinciri: {len(tasks)} görev → {len(commits)} commit → "
                f"{len(tests)} test → {len(bugs)} bug → {rel_count} sürüm."
            ),
            findings=[
                f"{len(tasks)} görev bağlı",
                f"{len(commits)} kod değişikliği bağlı",
                f"{len(tests)} test bağlı ({failed_n} başarısız)",
                f"{len(bugs)} hata bağlı",
                f"{rel_count} sürüm bağlı" if rel_count else "Doğrudan sürüm bağı zayıf",
            ],
            focus_entity=entity,
            impact_chain=chain,
            summary_stats={
                "tasks": len(tasks),
                "commits": len(commits),
                "tests": len(tests),
                "bugs": len(bugs),
                "releases": rel_count,
            },
            risk_reasons=[{"id": entity, "text": f"Revizyon/etki merkezi — durum={req.get('status')}"}],
            affected_records=records,
            related_records=records,
            recommended_actions=[
                f"{entity} için regression ve bağımlı testler yeniden çalıştırılsın.",
                "Bağlı sürüm yayını öncesi etki checklist'i tamamlanmalı.",
            ],
            metrics={
                "tasks": len(tasks),
                "commits": len(commits),
                "tests": len(tests),
                "bugs": len(bugs),
            },
            data_sources={
                **_empty_sources(),
                "requirements": 1,
                "tasks": len(tasks),
                "commits": len(commits),
                "tests": len(tests),
                "bugs": len(bugs),
                "releases": len(releases),
            },
            tools_used=tools_used,
        )

    def _h_root_cause(
        self, question: str, pid: int | None, focus_entity: str | None = None
    ) -> dict[str, Any]:
        tools_used: list[dict[str, Any]] = []
        entity = extract_entity(question) or focus_entity

        if entity and entity.upper().startswith("REQ-"):
            req = self._find_requirement(entity, pid)
            if req:
                rid = req["id"]
                tests = self.services["tests"].get_tests(
                    requirement_id=rid, result="failed", limit=200, project_id=pid
                )
                commits = self.services["commits"].get_commits(
                    requirement_id=rid, limit=100, project_id=pid
                )
                bugs = self.services["bugs"].get_bugs(
                    requirement_id=rid, status="active", limit=100, project_id=pid
                )
                self._track(
                    tools_used, "get_tests", {"requirement_id": rid, "result": "failed"}, len(tests)
                )
                self._track(tools_used, "get_commits", {"requirement_id": rid}, len(commits))
                self._track(tools_used, "get_bugs", {"requirement_id": rid}, len(bugs))
                return _base_result(
                    risk_level="high" if tests or bugs else "medium",
                    title=f"Kök Neden — {entity}",
                    conclusion=(
                        f"{entity} için kök neden sinyali: durum={req.get('status')}, "
                        f"{int(req.get('revision_count') or 0)} revizyon, "
                        f"{len(tests)} başarısız test, {len(bugs)} açık hata."
                    ),
                    summary=(
                        f"{entity} kök neden: revizyon={req.get('revision_count')}, "
                        f"başarısız test={len(tests)}, açık hata={len(bugs)}."
                    ),
                    findings=[
                        f"Gereksinim durumu: {req.get('status')}",
                        f"{int(req.get('revision_count') or 0)} revizyon",
                        f"{len(commits)} bağlı commit",
                        f"{len(tests)} başarısız test",
                        f"{len(bugs)} açık hata",
                    ],
                    focus_entity=entity,
                    recommended_actions=[
                        f"{entity} doğrulanmadan ilgili sürüm yayına alınmamalıdır.",
                        "Bağlı başarısız testler için kök neden kapatılsın.",
                    ],
                    affected_records=[{"id": entity, "note": req.get("title")}]
                    + [{"id": t["external_id"], "note": t["title"]} for t in tests[:6]],
                    related_records=[{"id": entity, "note": req.get("title")}]
                    + [{"id": t["external_id"], "note": t["title"]} for t in tests[:6]],
                    data_sources={
                        **_empty_sources(),
                        "requirements": 1,
                        "tests": len(tests),
                        "commits": len(commits),
                        "bugs": len(bugs),
                    },
                    tools_used=tools_used,
                )

        failed = self.services["tests"].get_tests(result="failed", limit=2000, project_id=pid)
        commits = self.services["commits"].get_commits(
            since=datetime.utcnow() - timedelta(days=14), limit=500, project_id=pid
        )
        reqs = self.services["requirements"].get_requirements(limit=500, project_id=pid)
        bugs = self.services["bugs"].get_bugs(
            status="active", severity="critical", limit=500, project_id=pid
        )
        self._track(tools_used, "get_tests", {"result": "failed", "project_id": pid}, len(failed))
        self._track(tools_used, "get_commits", {"within_days": 14, "project_id": pid}, len(commits))
        self._track(tools_used, "get_requirements", {"project_id": pid}, len(reqs))
        self._track(tools_used, "get_bugs", {"severity": "critical", "project_id": pid}, len(bugs))

        by_req: dict[str, list] = {}
        for t in failed:
            key = t.get("requirement_external_id") or "—"
            by_req.setdefault(key, []).append(t)
        top_req_id, top_tests = ("—", [])
        if by_req:
            top_req_id, top_tests = max(by_req.items(), key=lambda x: len(x[1]))

        req_meta = next((r for r in reqs if r.get("external_id") == top_req_id), None)
        related_commits = [c for c in commits if c.get("requirement_external_id") == top_req_id]
        related_bugs = [b for b in bugs if b.get("requirement_external_id") == top_req_id]

        conclusion = (
            f"Başarısız test artışının temel nedeni {top_req_id} gereksinimindeki "
            f"{'revizyon / değişikliktir' if req_meta and (req_meta.get('status') == 'changed' or int(req_meta.get('revision_count') or 0) >= 2) else 'kalite sapmasıdır'}."
            if top_req_id != "—"
            else "Başarısız testlerde ortak bir gereksinim kümesi bulunamadı."
        )
        findings = [
            f"{len(failed)} başarısız test",
            f"{len(top_tests)} test aynı gereksinimle ilişkili ({top_req_id})"
            if top_req_id != "—"
            else "Gereksinim bağı zayıf",
            f"{len(related_commits)} commit aynı gereksinimle ilişkili",
            f"{len(related_bugs)} kritik bug aynı gereksinimle ilişkili",
        ]
        if req_meta:
            findings.append(
                f"{top_req_id} durumu={req_meta.get('status')}, revizyon={req_meta.get('revision_count')}"
            )

        records = []
        if top_req_id != "—":
            records.append({"id": top_req_id, "note": (req_meta or {}).get("title") or "Kök gereksinim"})
        records += [{"id": t["external_id"], "note": t["title"]} for t in top_tests[:8]]
        records += [
            {
                "id": c.get("external_id") or (c.get("commit_hash") or "")[:8],
                "note": c.get("message") or "commit",
            }
            for c in related_commits[:4]
        ]
        records += [{"id": b["external_id"], "note": b["title"]} for b in related_bugs[:3]]

        return _base_result(
            risk_level="critical" if len(failed) >= 20 else ("high" if failed else "low"),
            title="Kök Neden Analizi",
            conclusion=conclusion,
            summary=conclusion,
            findings=findings,
            focus_entity=top_req_id if top_req_id != "—" else None,
            summary_stats={
                "failed_tests": len(failed),
                "linked_to_top_req": len(top_tests),
                "related_commits": len(related_commits),
                "critical_bugs": len(related_bugs),
            },
            risk_reasons=[{"id": top_req_id, "text": conclusion}],
            affected_records=records,
            related_records=records,
            recommended_actions=[
                f"{top_req_id} doğrulanmadan sürüm yayına alınmamalıdır."
                if top_req_id != "—"
                else "Başarısız test kümeleri için kök neden review açın.",
                "Aynı gereksinime bağlı commit ve testleri birlikte inceleyin.",
            ],
            metrics={"failed_tests": len(failed), "top_req_failures": len(top_tests)},
            data_sources={
                **_empty_sources(),
                "tests": len(failed),
                "commits": len(commits),
                "requirements": len(reqs),
                "bugs": len(bugs),
            },
            tools_used=tools_used,
        )

    def _h_risk(
        self, question: str, pid: int | None, focus_entity: str | None = None
    ) -> dict[str, Any]:
        ql = question.lower()
        if focus_entity and any(k in ql for k in ("neden", "detay", "peki")):
            return self._h_root_cause(question, pid, focus_entity=focus_entity)

        tools_used: list[dict[str, Any]] = []
        reqs = self.services["requirements"].get_requirements(limit=500, project_id=pid)
        failed = self.services["tests"].get_tests(result="failed", limit=2000, project_id=pid)
        bugs = self.services["bugs"].get_bugs(status="active", limit=2000, project_id=pid)
        self._track(tools_used, "get_requirements", {"project_id": pid}, len(reqs))
        self._track(tools_used, "get_tests", {"result": "failed"}, len(failed))
        self._track(tools_used, "get_bugs", {"status": "active"}, len(bugs))

        scored = []
        for r in reqs:
            rid = r["id"]
            ft = sum(1 for t in failed if t.get("requirement_id") == rid)
            bg = sum(
                1
                for b in bugs
                if b.get("requirement_id") == rid and b.get("severity") in ("critical", "high")
            )
            score = ft * 2 + bg * 3 + int(r.get("revision_count") or 0)
            if r.get("status") == "changed":
                score += 3
            scored.append((score, r, ft, bg))
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:8]
        best = top[0] if top else None

        if not best or best[0] <= 0:
            return _base_result(
                title="Risk Analizi",
                conclusion="Belirgin gereksinim riski bulunamadı.",
                summary="Belirgin gereksinim riski bulunamadı.",
                findings=["Risk skoru eşiğinin üzerinde kayıt yok."],
                tools_used=tools_used,
                data_sources={
                    **_empty_sources(),
                    "requirements": len(reqs),
                    "tests": len(failed),
                    "bugs": len(bugs),
                },
            )

        _, req, ft, bg = best
        eid = req["external_id"]
        records = [
            {
                "id": r["external_id"],
                "note": f"skor={sc} · başarısız test={f} · yüksek/kritik bug={b}",
            }
            for sc, r, f, b in top
        ]
        return _base_result(
            risk_level="critical" if best[0] >= 12 else "high",
            title="Risk Analizi",
            conclusion=f"En riskli gereksinim {eid}: {req.get('title')}.",
            summary=(
                f"En riskli gereksinim {eid}. {ft} başarısız test, {bg} yüksek/kritik bug, "
                f"revizyon={req.get('revision_count')}, durum={req.get('status')}."
            ),
            findings=[
                f"En riskli: {eid}",
                f"{ft} başarısız test bağlı",
                f"{bg} yüksek/kritik açık hata",
                f"Revizyon sayısı: {req.get('revision_count')}",
                f"Durum: {req.get('status')}",
            ],
            focus_entity=eid,
            summary_stats={"top_risk_score": best[0], "failed_tests": ft, "critical_bugs": bg},
            risk_reasons=[{"id": eid, "text": f"Risk skoru {best[0]}"}],
            affected_records=records,
            related_records=records,
            recommended_actions=[
                f"{eid} için öncelikli remediation planı çıkarın.",
                "Bağlı başarısız test ve kritik hataları kapatmadan yayına çıkmayın.",
            ],
            data_sources={
                **_empty_sources(),
                "requirements": len(reqs),
                "tests": len(failed),
                "bugs": len(bugs),
            },
            tools_used=tools_used,
        )

    def _h_anomaly(self, question: str, pid: int | None) -> dict[str, Any]:
        tools_used: list[dict[str, Any]] = []
        failed = self.services["tests"].get_tests(result="failed", limit=2000, project_id=pid)
        delayed = [
            t
            for t in self.services["tasks"].get_tasks(limit=2000, project_id=pid)
            if t.get("is_delayed")
        ]
        changed = self.services["requirements"].get_requirements(
            status="changed", limit=200, project_id=pid
        )
        risky = [
            r
            for r in self.services["releases"].get_releases(limit=200, project_id=pid)
            if r.get("is_risky")
        ]
        self._track(tools_used, "get_tests", {"result": "failed"}, len(failed))
        self._track(tools_used, "get_tasks", {"project_id": pid}, len(delayed))
        self._track(tools_used, "get_requirements", {"status": "changed"}, len(changed))
        self._track(tools_used, "get_releases", {"project_id": pid}, len(risky))

        anomalies = []
        if len(failed) >= 15:
            anomalies.append(f"Başarısız test hacmi yüksek: {len(failed)}")
        if len(delayed) >= 10:
            anomalies.append(f"Geciken görev kümesi: {len(delayed)}")
        if len(changed) >= 8:
            anomalies.append(f"Changed gereksinim yoğunluğu: {len(changed)}")
        if len(risky) >= 3:
            anomalies.append(f"Riskli sürüm yoğunluğu: {len(risky)}")

        fail_reqs = {t.get("requirement_external_id") for t in failed if t.get("requirement_external_id")}
        changed_ids = {r["external_id"] for r in changed}
        overlap = sorted(fail_reqs & changed_ids)
        if overlap:
            anomalies.append(f"Changed + başarısız test çakışması: {', '.join(overlap[:5])}")

        return _base_result(
            risk_level="high" if len(anomalies) >= 3 else ("medium" if anomalies else "low"),
            title="Anomali Tespiti",
            conclusion=(
                f"{len(anomalies)} süreç anomalisi tespit edildi."
                if anomalies
                else "Belirgin süreç anomalisi görülmedi."
            ),
            summary=(
                f"Anomali taraması: {len(anomalies)} sinyal."
                if anomalies
                else "Olağandışı sapma bulunamadı."
            ),
            findings=anomalies or ["Eşik üstü anomali yok."],
            focus_entity=overlap[0] if overlap else None,
            affected_records=[
                {"id": eid, "note": "Changed + başarısız test çakışması"} for eid in overlap[:8]
            ],
            related_records=[
                {"id": eid, "note": "Changed + başarısız test çakışması"} for eid in overlap[:8]
            ],
            recommended_actions=[
                "Çakışan gereksinimlerde acil kalite review açın."
                if overlap
                else "Mevcut eşikler izlenmeye devam edilsin.",
                "Anomali sinyallerini sprint retrospektifine taşıyın.",
            ],
            summary_stats={
                "failed_tests": len(failed),
                "delayed_tasks": len(delayed),
                "changed_status": len(changed),
                "risky_releases": len(risky),
            },
            data_sources={
                **_empty_sources(),
                "tests": len(failed),
                "tasks": len(delayed),
                "requirements": len(changed),
                "releases": len(risky),
            },
            tools_used=tools_used,
        )
