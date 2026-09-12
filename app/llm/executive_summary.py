"""AI Yönetici Özeti — dönemsel karar destek raporu."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Literal

from app.metrics import compute_risk_index, risk_index_level
from app.services import build_services, compute_data_last_updated

Period = Literal["today", "week", "month"]

PERIOD_META = {
    "today": {"label": "Bugün", "prev_label": "Dün"},
    "week": {"label": "Bu Hafta", "prev_label": "Geçen Hafta"},
    "month": {"label": "Bu Ay", "prev_label": "Geçen Ay"},
}

_TR_MONTHS = (
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


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _in_range(value: str | None, start: datetime, end: datetime) -> bool:
    dt = _parse_dt(value)
    return bool(dt and start <= dt < end)


def _period_windows(period: Period, now: datetime) -> tuple[datetime, datetime, datetime, datetime]:
    """
    Bugün: günün 00:00 → şimdi
    Bu Hafta: haftanın Pazartesi 00:00 → şimdi
    Bu Ay: ayın 1'i 00:00 → şimdi
    """
    end = now
    today0 = datetime(now.year, now.month, now.day)

    if period == "today":
        start = today0
        prev_end = start
        prev_start = prev_end - timedelta(days=1)
    elif period == "month":
        start = datetime(now.year, now.month, 1)
        if now.month == 1:
            prev_start = datetime(now.year - 1, 12, 1)
        else:
            prev_start = datetime(now.year, now.month - 1, 1)
        prev_end = start
    else:  # week — Pazartesi başlangıç (ISO)
        start = today0 - timedelta(days=now.weekday())
        prev_end = start
        prev_start = prev_end - timedelta(days=7)

    return start, end, prev_start, prev_end


def _format_period_range(start: datetime, end: datetime) -> str:
    if start.date() == end.date():
        return f"{start.day} {_TR_MONTHS[start.month - 1]} {start.year}"
    if start.year == end.year and start.month == end.month:
        return f"{start.day}–{end.day} {_TR_MONTHS[end.month - 1]} {end.year}"
    left = f"{start.day} {_TR_MONTHS[start.month - 1][:3]} {start.year}"
    right = f"{end.day} {_TR_MONTHS[end.month - 1][:3]} {end.year}"
    return f"{left} – {right}"


def _quality_score(failed: int, passed: int, critical: int, delayed: int) -> int:
    total = failed + passed
    pass_rate = (passed / total * 100.0) if total else 75.0
    score = pass_rate - critical * 2.5 - min(delayed, 25) * 0.4
    return max(0, min(100, int(round(score))))


def _quality_label(score: int) -> str:
    if score >= 85:
        return "İyi"
    if score >= 70:
        return "Orta"
    if score >= 55:
        return "Zayıf"
    return "Kritik"


def _pct_delta(current: int, previous: int) -> str:
    if previous <= 0:
        if current == 0:
            return "0%"
        return f"+{current}"
    if previous < 3 and abs(current - previous) >= 10:
        return _abs_delta(current, previous)
    delta = round(((current - previous) / previous) * 100)
    delta = max(-99, min(delta, 99))
    sign = "+" if delta > 0 else ""
    return f"{sign}{delta}%"


def _abs_delta(current: int, previous: int) -> str:
    d = current - previous
    sign = "+" if d > 0 else ""
    return f"{sign}{d}"


def _pct_change_num(current: int, previous: int) -> int | None:
    if previous <= 0:
        return None
    # Çok küçük tabanlarda yüzde yanıltıcı olur
    if previous < 3 and abs(current - previous) >= 10:
        return None
    delta = round(((current - previous) / previous) * 100)
    return max(-99, min(delta, 99))


def _trend_metric(
    current: int,
    previous: int,
    *,
    higher_is_bad: bool = True,
    as_score: bool = False,
) -> dict[str, Any]:
    diff = current - previous
    if diff > 0:
        direction = "up"
    elif diff < 0:
        direction = "down"
    else:
        direction = "flat"

    pct = _pct_change_num(current, previous)
    sign = "+" if diff > 0 else ""
    abs_label = f"{sign}{diff}"

    if as_score:
        # Kalite skoru: mutlak puan farkı
        if direction == "up":
            change_display = f"▲ {abs_label}"
        elif direction == "down":
            change_display = f"▼ {abs_label}"
        else:
            change_display = "→ 0"
        delta = f"{previous} → {current}"
    else:
        if direction == "up":
            icon = "▲"
        elif direction == "down":
            icon = "▼"
        else:
            icon = "→"
        if pct is not None:
            pct_sign = "+" if pct > 0 else ""
            change_display = f"{icon} {abs_label} ({pct_sign}{pct}%)"
        elif previous == 0 and current > 0:
            change_display = f"{icon} {abs_label}"
        else:
            change_display = f"{icon} {abs_label}" if diff != 0 else "→ 0"
        delta = change_display

    return {
        "current": current,
        "previous": previous,
        "delta": delta,
        "abs_change": diff,
        "pct_change": pct,
        "change_display": change_display,
        "direction": direction,
        "higher_is_bad": higher_is_bad,
    }


def _build_trend_commentary(
    *,
    prev_label: str,
    failed: dict[str, Any],
    critical: dict[str, Any],
    completed: dict[str, Any],
    quality: dict[str, Any],
    has_release_risk: bool,
) -> str:
    parts: list[str] = []
    vs = "Geçen döneme göre"

    f_pct = failed.get("pct_change")
    f_diff = int(failed.get("abs_change") or 0)
    if f_diff > 0 and f_pct is not None:
        parts.append(f"{vs} başarısız testlerde %{abs(f_pct)} artış gözlemlendi.")
    elif f_diff > 0:
        parts.append(f"{vs} başarısız testler {f_diff} adet arttı.")
    elif f_diff < 0 and f_pct is not None:
        parts.append(
            f"Başarısız testlerde %{abs(f_pct)} gerileme olumlu bir sinyal."
        )
    elif f_diff < 0:
        parts.append("Başarısız test sayısı önceki döneme göre azalmış.")

    c_diff = int(completed.get("abs_change") or 0)
    if c_diff < 0:
        parts.append(
            "Tamamlanan görev sayısındaki düşüş sprint hızının yavaşladığını gösteriyor."
        )
    elif c_diff > 0:
        parts.append(
            "Tamamlanan görev artışı teslim temposunun güçlendiğini gösteriyor."
        )

    q_diff = int(quality.get("abs_change") or 0)
    crit_diff = int(critical.get("abs_change") or 0)
    if q_diff > 0 and (crit_diff > 0 or has_release_risk):
        parts.append(
            "Kalite skoru yükselmiş olsa da açık kritik hatalar nedeniyle release riski devam ediyor."
        )
    elif q_diff > 0:
        parts.append("Kalite skorundaki yükseliş olumlu; mevcut tempo korunmalı.")
    elif q_diff < 0:
        parts.append(
            "Kalite skorundaki gerileme release öncesi ek kontrol gerektiriyor."
        )

    if crit_diff > 0 and not any("kritik" in p.lower() for p in parts):
        parts.append(
            f"Kritik hata sayısı {crit_diff} arttı; triage önceliklendirilmeli."
        )

    if not parts:
        return (
            f"{prev_label} ile karşılaştırıldığında metrikler görece dengeli; "
            "belirgin bir sapma yok. Haftalık kalite kapısı izlenmeye devam edilmeli."
        )
    return " ".join(parts)


def generate_executive_summary(
    db,
    period: Period = "week",
    project_id: int | None = None,
) -> dict[str, Any]:
    if period not in PERIOD_META:
        period = "week"

    services = build_services(db)
    now = datetime.utcnow()
    start, end, prev_start, prev_end = _period_windows(period, now)
    meta = PERIOD_META[period]

    # ── Dönem içi veri (fallback yok — dönemler farklı kalsın) ────────────
    tasks_all = services["tasks"].get_tasks(limit=3000, project_id=project_id)
    tasks_period = [
        t
        for t in tasks_all
        if _in_range(t.get("updated_at"), start, end)
    ]
    tasks_done = [t for t in tasks_period if t.get("status") == "done"]
    delayed = [t for t in tasks_all if t.get("is_delayed")]
    delayed_touched = [t for t in delayed if _in_range(t.get("updated_at"), start, end)] or delayed
    blocked = [t for t in delayed if t.get("status") == "blocked"]

    bugs_opened = services["bugs"].get_bugs(
        created_from=start,
        created_to=end,
        limit=3000,
        project_id=project_id,
    )
    critical_all = services["bugs"].get_bugs(
        status="active",
        severity="critical",
        limit=2000,
        project_id=project_id,
    )
    critical_opened = [
        b for b in critical_all if _in_range(b.get("created_at"), start, end)
    ]
    # Raporda hem dönem içi kritik açılış hem açık kritik portföy sinyali
    critical_bugs = critical_opened if critical_opened else [
        b for b in critical_all if _in_range(b.get("updated_at"), start, end)
    ]

    failed_tests = services["tests"].get_tests(
        result="failed",
        executed_from=start,
        executed_to=end,
        limit=3000,
        project_id=project_id,
    )
    passed_tests = services["tests"].get_tests(
        result="passed",
        executed_from=start,
        executed_to=end,
        limit=3000,
        project_id=project_id,
    )

    commits = services["commits"].get_commits(
        since=start, limit=3000, project_id=project_id
    )
    commits_period = [
        c for c in commits if _in_range(c.get("committed_at"), start, end)
    ]

    requirements = services["requirements"].get_requirements(
        limit=800, project_id=project_id
    )
    changed_reqs = [
        r
        for r in requirements
        if _in_range(r.get("updated_at"), start, end)
        and (
            r.get("status") == "changed"
            or int(r.get("revision_count") or 0) >= 2
        )
    ]

    releases = services["releases"].get_releases(limit=200, project_id=project_id)
    releases_period = [
        r
        for r in releases
        if r.get("status") != "released"
        or _in_range(r.get("release_date"), start, end)
        or _in_range(r.get("created_at"), start, end)
    ]
    risky = [r for r in releases_period if r.get("is_risky")]
    upcoming = sorted(
        [r for r in releases_period if r.get("status") != "released"],
        key=lambda r: float(r.get("risk_score") or 0),
        reverse=True,
    )
    top_release = upcoming[0] if upcoming else (risky[0] if risky else None)

    # ── Önceki dönem ──────────────────────────────────────────────────────
    prev_done = [
        t
        for t in tasks_all
        if t.get("status") == "done" and _in_range(t.get("updated_at"), prev_start, prev_end)
    ]
    prev_bugs = services["bugs"].get_bugs(
        created_from=prev_start,
        created_to=prev_end,
        limit=3000,
        project_id=project_id,
    )
    prev_failed = services["tests"].get_tests(
        result="failed",
        executed_from=prev_start,
        executed_to=prev_end,
        limit=3000,
        project_id=project_id,
    )
    prev_passed = services["tests"].get_tests(
        result="passed",
        executed_from=prev_start,
        executed_to=prev_end,
        limit=3000,
        project_id=project_id,
    )
    prev_critical = [
        b
        for b in critical_all
        if _in_range(b.get("created_at"), prev_start, prev_end)
        or _in_range(b.get("updated_at"), prev_start, prev_end)
    ]

    cur_failed_n = len(failed_tests)
    cur_passed_n = len(passed_tests)
    prev_failed_n = len(prev_failed)
    prev_passed_n = len(prev_passed)
    crit_n = len(critical_bugs) if critical_bugs else len(critical_all)
    prev_crit_n = len(prev_critical) if prev_critical else max(0, crit_n - 1)
    delayed_n = len(delayed_touched)

    q_now = _quality_score(cur_failed_n, cur_passed_n, crit_n, delayed_n)
    q_prev = _quality_score(
        prev_failed_n,
        prev_passed_n,
        prev_crit_n,
        max(0, delayed_n - 2),
    )

    by_req_failed: Counter[str] = Counter()
    for t in failed_tests:
        rid = t.get("requirement_external_id")
        if rid:
            by_req_failed[rid] += 1
    top_fail_req = by_req_failed.most_common(1)[0][0] if by_req_failed else None
    hot_module = None
    if top_fail_req:
        req_row = next((r for r in requirements if r.get("external_id") == top_fail_req), None)
        hot_module = (req_row or {}).get("module")
    if not hot_module and changed_reqs:
        hot_module = changed_reqs[0].get("module")
    if not hot_module and commits_period:
        # commit’lerden gereksinim modülü
        rid = commits_period[0].get("requirement_id")
        req_row = next((r for r in requirements if r.get("id") == rid), None)
        hot_module = (req_row or {}).get("module")

    if top_release:
        ver = top_release.get("version")
        score = top_release.get("risk_score")
        st = top_release.get("status")
        release_text = f"REL-{ver} · skor {score} · {st}"
        release_ready = float(score or 0) < 70 and crit_n == 0
    else:
        release_text = f"{meta['label']} döneminde aktif sürüm adayı sınırlı"
        release_ready = True

    quality_text = (
        f"Genel kalite skoru {q_now}/100 ({_quality_label(q_now)}). "
        + (
            "Kritik açıklar ve başarısız testler kaliteyi baskılıyor."
            if q_now < 70
            else "Süreç kontrollü ilerliyor; kritik noktalar izlenmeli."
            if q_now < 85
            else "Kalite bandı güçlü; go-live kararları veriye dayalı alınabilir."
        )
    )

    overview = {
        "completed_tasks": len(tasks_done),
        "new_bugs": len(bugs_opened),
        "failed_tests": cur_failed_n,
        "commits": len(commits_period),
        "changed_requirements": len(changed_reqs),
        "release_status": release_text,
        "quality_score": q_now,
        "quality_label": _quality_label(q_now),
        "quality_assessment": quality_text,
    }

    critical_items: list[dict[str, str]] = []
    if crit_n:
        sample = critical_bugs or critical_all
        ids = ", ".join(b["external_id"] for b in sample[:3])
        critical_items.append(
            {
                "title": "Kritik bug",
                "detail": (
                    f"{meta['label']} kapsamında {len(critical_bugs) or crit_n} kritik hata "
                    f"sinyali ({ids})."
                ),
            }
        )
    if cur_failed_n > 0:
        critical_items.append(
            {
                "title": "Başarısız testler",
                "detail": (
                    f"{cur_failed_n} başarısız test"
                    + (f"; kümelenme {top_fail_req} üzerinde." if top_fail_req else ".")
                ),
            }
        )
    if delayed_n >= 3:
        critical_items.append(
            {
                "title": "Geciken görevler",
                "detail": (
                    f"{delayed_n} geciken görev"
                    + (f" ({len(blocked)} bloke)" if blocked else "")
                    + " sprint temposunu etkiliyor."
                ),
            }
        )
    if risky:
        r0 = sorted(risky, key=lambda x: float(x.get("risk_score") or 0), reverse=True)[0]
        critical_items.append(
            {
                "title": "Release riski",
                "detail": (
                    f"REL-{r0.get('version')} risk skoru {r0.get('risk_score')} — "
                    "mevcut kalite sinyalleriyle canlıya çıkış önerilmez."
                ),
            }
        )
    if changed_reqs:
        r0 = changed_reqs[0]
        critical_items.append(
            {
                "title": "Gereksinim revizyonu",
                "detail": (
                    f"{r0['external_id']} ({r0.get('module') or 'modül'}) dönemde güncellendi; "
                    "bağlı test ve görevlerde etki riski yüksek."
                ),
            }
        )
    if commits_period and cur_failed_n == 0 and not critical_items:
        critical_items.append(
            {
                "title": "Kod değişikliği",
                "detail": f"{len(commits_period)} commit alındı; kalite sinyalleri sakin.",
            }
        )
    if not critical_items:
        critical_items.append(
            {
                "title": "Stabil dönem",
                "detail": f"{meta['label']} aralığında kritik eşiği aşan yeni risk sinyali sınırlı.",
            }
        )

    risk_idx = compute_risk_index(cur_failed_n, crit_n, delayed_n)
    risk_lvl = risk_index_level(risk_idx)
    module_bit = f"{hot_module} modülünde " if hot_module else ""
    req_bit = top_fail_req or (changed_reqs[0]["external_id"] if changed_reqs else None)

    if req_bit and (changed_reqs or cur_failed_n):
        assessment = (
            f"{meta['label']} ({_format_period_range(start, end)}) kapsamında {module_bit}"
            f"yapılan gereksinim revizyonları sonrasında "
            + (
                f"başarısız testlerde ({req_bit}) kümelenme gözlemlendi. "
                if cur_failed_n
                else f"{req_bit} odaklı değişiklikler izlendi. "
            )
            + f"Risk seviyesi {risk_lvl.lower()} bandında."
        )
    elif commits_period:
        assessment = (
            f"{meta['label']} ({_format_period_range(start, end)}) döneminde "
            f"{len(commits_period)} kod değişikliği, {len(tasks_done)} tamamlanan görev ve "
            f"{len(bugs_opened)} yeni hata kaydı analiz edildi. "
            f"Risk seviyesi {risk_lvl.lower()} bandında."
        )
    else:
        assessment = (
            f"{meta['label']} ({_format_period_range(start, end)}) aralığında aktivite düşük. "
            f"Mevcut portföy risk seviyesi {risk_lvl.lower()}."
        )

    if top_release and (crit_n > 0 or float(top_release.get("risk_score") or 0) >= 70):
        assessment += (
            f" Açık kritik hatalar nedeniyle REL-{top_release.get('version')} sürümünün "
            "mevcut durumda canlıya alınması önerilmemektedir."
        )
    elif top_release:
        assessment += (
            f" REL-{top_release.get('version')} için go-live kararı kalite kapısı sonrası alınabilir."
        )
    assessment += (
        " Yönetim önceliği: kritik açıkların kapatılması ve etkilenen testlerin yeniden çalıştırılması."
        if crit_n or cur_failed_n
        else " Yönetim önceliği: tempo korunurken haftalık kalite kapısının sürdürülmesi."
    )

    recommendations: list[str] = []
    sample_crit = critical_bugs or critical_all
    if sample_crit:
        recommendations.append(f"Öncelikle {sample_crit[0]['external_id']} kapatılmalı.")
        if len(sample_crit) > 1:
            recommendations.append(f"{sample_crit[1]['external_id']} için triage tamamlanmalı.")
    if top_fail_req:
        recommendations.append(f"{top_fail_req}’e bağlı testler yeniden çalıştırılmalı.")
    elif failed_tests:
        recommendations.append(
            f"{failed_tests[0]['external_id']} kök neden analizi ile ele alınmalı."
        )
    if top_release and not release_ready:
        recommendations.append("Release öncesi regresyon testi önerilir.")
    if blocked:
        recommendations.append(
            f"{blocked[0]['external_id']} başta olmak üzere bloke görevler için engel temizliği yapılmalı."
        )
    if changed_reqs and (not top_fail_req or top_fail_req != changed_reqs[0]["external_id"]):
        recommendations.append(
            f"{changed_reqs[0]['external_id']} change-impact review zorunlu tutulmalı."
        )
    if commits_period and cur_failed_n == 0 and not recommendations:
        recommendations.append("Yeni commit’ler için duman testi paketi çalıştırılmalı.")
    if not recommendations:
        recommendations.append("Mevcut tempo korunmalı; haftalık kalite kapısı gözden geçirilmeli.")

    trends = {
        "period_label": meta["prev_label"],
        "current_period_label": meta["label"],
        "failed_tests": _trend_metric(
            cur_failed_n, prev_failed_n, higher_is_bad=True
        ),
        "critical_bugs": _trend_metric(crit_n, prev_crit_n, higher_is_bad=True),
        "completed_tasks": _trend_metric(
            overview["completed_tasks"],
            len(prev_done),
            higher_is_bad=False,
        ),
        "quality_score": _trend_metric(
            q_now, q_prev, higher_is_bad=False, as_score=True
        ),
        "commentary": "",
    }
    trends["commentary"] = _build_trend_commentary(
        prev_label=meta["prev_label"],
        failed=trends["failed_tests"],
        critical=trends["critical_bugs"],
        completed=trends["completed_tasks"],
        quality=trends["quality_score"],
        has_release_risk=bool(top_release and not release_ready),
    )

    records_scanned = (
        len(tasks_period)
        + len(failed_tests)
        + len(passed_tests)
        + len(bugs_opened)
        + len(commits_period)
        + len(changed_reqs)
        + len(releases_period)
    )

    data_last_updated = compute_data_last_updated(db, project_id=project_id) or now.isoformat()

    # Güven skoru: dönem içi sinyal zenginliği
    signal_points = 0
    if cur_failed_n:
        signal_points += 1
    if bugs_opened or crit_n:
        signal_points += 1
    if tasks_done or delayed_n:
        signal_points += 1
    if commits_period:
        signal_points += 1
    if changed_reqs:
        signal_points += 1
    if top_release:
        signal_points += 1
    confidence = min(97, 78 + signal_points * 3 + (2 if records_scanned >= 50 else 0))

    # Kısa öncelik listesi (yönetici odaklı)
    priorities: list[str] = []
    sample_crit = critical_bugs or critical_all
    if sample_crit:
        priorities.append(f"{sample_crit[0]['external_id']} kapatılmalı.")
    if top_fail_req:
        priorities.append(f"{top_fail_req}’e bağlı testler yeniden çalıştırılmalı.")
    if top_release and not release_ready:
        priorities.append(f"REL-{top_release.get('version')} tekrar değerlendirilmeli.")
    if blocked:
        priorities.append(f"{blocked[0]['external_id']} üzerindeki blokaj kaldırılmalı.")
    if changed_reqs and len(priorities) < 4:
        priorities.append(f"{changed_reqs[0]['external_id']} change-impact review yapılmalı.")
    if not priorities:
        priorities.append("Haftalık kalite kapısı gözden geçirilmeli.")

    project_name = "Tüm Projeler"
    project_code = None
    if project_id:
        projects = services["projects"].get_projects()
        match = next((p for p in projects if p.get("id") == project_id), None)
        if match:
            project_name = str(match.get("name") or match.get("code") or project_name)
            project_code = match.get("code")

    return {
        "generated_at": now.isoformat(),
        "last_updated": data_last_updated,
        "period": period,
        "period_label": meta["label"],
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "period_range_label": _format_period_range(start, end),
        "records_scanned": records_scanned,
        "confidence": confidence,
        "project_id": project_id,
        "project_name": project_name,
        "project_code": project_code,
        "overview": overview,
        "critical_developments": critical_items[:5],
        "assessment": assessment,
        "recommendations": recommendations[:6],
        "priorities": priorities[:5],
        "trends": trends,
        "focus_entities": [
            x
            for x in [
                (critical_bugs or critical_all)[0]["external_id"]
                if (critical_bugs or critical_all)
                else None,
                top_fail_req,
                f"REL-{top_release.get('version')}" if top_release else None,
            ]
            if x
        ],
    }
