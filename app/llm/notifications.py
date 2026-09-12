"""AI Bildirim Merkezi — trigger odaklı proaktif bildirim üretimi."""

from __future__ import annotations

import random
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any

from app.services import build_services

CATEGORY_META = {
    "critical_risk": {"label": "Kritik Risk", "priority": 1, "emoji": "🔴"},
    "process_warning": {"label": "Süreç Uyarısı", "priority": 2, "emoji": "⚠"},
    "performance": {"label": "Performans", "priority": 3, "emoji": "🟡"},
    "info": {"label": "Bilgilendirme", "priority": 4, "emoji": "🔵"},
    "ai_suggestion": {"label": "AI Önerisi", "priority": 5, "emoji": "💡"},
}


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _days_until(date_str: str | None) -> int | None:
    d = _parse_dt(date_str)
    if not d:
        return None
    return (d.date() - datetime.utcnow().date()).days


def _chips(*labels: str) -> list[dict[str, str]]:
    return [{"label": label, "value": ""} for label in labels if label]


def _pick(items: list, rng: random.Random, fallback_index: int = 0):
    if not items:
        return None
    if len(items) == 1:
        return items[0]
    return items[rng.randrange(len(items))]


def generate_notifications(db, project_id: int | None = None) -> dict[str, Any]:
    """Olay tetikleyicilerini değerlendirip yorumlanmış, dinamik bildirimler üretir."""
    services = build_services(db)
    now = datetime.utcnow()
    since_7d = now - timedelta(days=7)
    # Her ~20 sn / her taramada farklı odak — demo için dinamik his
    seed = int(now.timestamp()) // 20
    rng = random.Random(seed)

    critical_bugs = services["bugs"].get_bugs(
        status="active", severity="critical", limit=2000, project_id=project_id
    )
    active_bugs = services["bugs"].get_bugs(status="active", limit=2000, project_id=project_id)
    failed_tests = services["tests"].get_tests(result="failed", limit=2000, project_id=project_id)
    all_tests = services["tests"].get_tests(limit=2000, project_id=project_id)
    tasks = services["tasks"].get_tasks(limit=2000, project_id=project_id)
    delayed = [t for t in tasks if t.get("is_delayed")]
    blocked = [t for t in delayed if t.get("status") == "blocked"]
    requirements = services["requirements"].get_requirements(limit=500, project_id=project_id)
    changed_reqs = [r for r in requirements if r.get("status") == "changed"]
    commits = services["commits"].get_commits(since=since_7d, limit=500, project_id=project_id)
    releases = services["releases"].get_releases(limit=200, project_id=project_id)

    by_req_failed: Counter[str] = Counter()
    for t in failed_tests:
        rid = t.get("requirement_external_id")
        if rid:
            by_req_failed[rid] += 1

    churn = sorted(
        [
            r
            for r in requirements
            if int(r.get("revision_count") or 0) >= 3 or r.get("status") == "changed"
        ],
        key=lambda r: (int(r.get("revision_count") or 0), r.get("status") == "changed"),
        reverse=True,
    )

    commit_req_ids = {c.get("requirement_id") for c in commits if c.get("requirement_id")}
    recent_tested = {
        t.get("requirement_id")
        for t in all_tests
        if t.get("requirement_id")
        and (dt := _parse_dt(t.get("executed_at")))
        and dt >= since_7d
    }

    bugs_by_module: dict[str, list] = defaultdict(list)
    for b in active_bugs:
        req = next((r for r in requirements if r.get("id") == b.get("requirement_id")), None)
        mod = (req or {}).get("module") or b.get("project_code") or "—"
        bugs_by_module[mod].append(b)
    hot_modules = sorted(bugs_by_module.items(), key=lambda x: len(x[1]), reverse=True)

    candidates: list[dict[str, Any]] = []

    def add(
        *,
        scenario: str,
        nid: str,
        category: str,
        title: str,
        chips: list[str],
        analysis: str,
        action: str,
        related_ids: list[str],
        focus: str | None = None,
        deepen_prompt: str | None = None,
    ) -> None:
        meta = CATEGORY_META[category]
        related = [{"id": rid, "note": ""} for rid in related_ids if rid]
        trigger_line = " · ".join(chips)
        candidates.append(
            {
                "id": nid,
                "scenario": scenario,
                "category": category,
                "category_label": meta["label"],
                "category_emoji": meta["emoji"],
                "priority": meta["priority"],
                "title": title,
                "trigger": trigger_line,
                "triggers": _chips(*chips),
                "analysis": analysis,
                "recommended_action": action,
                "related_records": related,
                "focus_entity": focus,
                "deepen_prompt": deepen_prompt
                or (f"{focus} değişirse neler etkilenir?" if focus else title),
                "created_at": now.isoformat(),
            }
        )

    # ── 1) Gereksinim değişikliği → çapraz etki ────────────────────────────
    if churn:
        pool = churn[: min(5, len(churn))]
        req = _pick(pool, rng) or churn[0]
        eid = req["external_id"]
        rid = req["id"]
        rev = int(req.get("revision_count") or 0)
        linked_tasks = [t for t in tasks if t.get("requirement_id") == rid]
        linked_tests = [t for t in all_tests if t.get("requirement_id") == rid]
        linked_commits = [c for c in commits if c.get("requirement_id") == rid]
        linked_bugs = [b for b in active_bugs if b.get("requirement_id") == rid]
        open_tasks = [t for t in linked_tasks if t.get("status") != "done"]
        failed_linked = [t for t in linked_tests if t.get("result") == "failed"]
        rel_ver = req.get("release_version")

        related = [eid]
        related += [t["external_id"] for t in open_tasks[:3]]
        related += [t["external_id"] for t in linked_tests[:3]]
        related += [b["external_id"] for b in linked_bugs[:2]]
        if rel_ver:
            related.append(f"REL-{rel_ver}")

        chips = [f"Revizyon ≥ {max(rev, 3)}", f"{eid} güncellendi"]
        if req.get("status") == "changed":
            chips.append("Durum: changed")
        if failed_linked:
            chips.append("Bağlı testlerde başarısızlık")

        impact_bits = []
        if linked_tests:
            impact_bits.append(f"{len(linked_tests)} test senaryosunu")
        if open_tasks:
            impact_bits.append(f"{len(open_tasks)} aktif görevi")
        if linked_commits:
            impact_bits.append(f"{len(linked_commits)} commit’i")
        if linked_bugs:
            impact_bits.append(f"{len(linked_bugs)} açık hatayı")
        impact = ", ".join(impact_bits) if impact_bits else "bağlı süreç kayıtlarını"

        analysis = (
            f"{eid} son revizyonlarından sonra bağlı zincirde etki yayıldı: {impact} doğrudan "
            f"etkiliyor"
            + (
                f"; bunların {len(failed_linked)}’i hâlihazırda başarısız."
                if failed_linked
                else "."
            )
            + (
                f" Bu değişiklik kalite kapısını zayıflatıyor"
                + (f" ve REL-{rel_ver} için go-live riskini artırıyor." if rel_ver else ".")
            )
            + " Release öncesinde ilgili testlerin güncellenip yeniden çalıştırılması önerilir."
        )

        add(
            scenario="req_change",
            nid=f"req-change-impact-{eid}",
            category="process_warning",
            title="Gereksinim Değişiklik Uyarısı",
            chips=chips,
            analysis=analysis,
            action=(
                f"{eid}’e bağlı test ve görevler gözden geçirilmeli; "
                "regression yeşile dönmeden ilgili sürüm ilerletilmemeli."
            ),
            related_ids=related,
            focus=eid,
            deepen_prompt=f"{eid} değişirse neler etkilenir?",
        )

    # ── 2) Kritik bug ──────────────────────────────────────────────────────
    if len(critical_bugs) >= 1:
        top = critical_bugs[:3]
        chips = [f"Kritik Bug ≥ {len(critical_bugs)}"]
        near_rel = None
        for r in releases:
            if r.get("status") == "released":
                continue
            d = _days_until(r.get("release_date"))
            if d is not None and 0 <= d <= 14:
                near_rel = (d, r)
                break
        if near_rel:
            chips.append(f"Release’e {near_rel[0]} Gün Kala")
        chips.append("Canlıya çıkış riski")

        focus_bug = _pick(top, rng) or top[0]
        analysis = (
            f"{focus_bug['external_id']} başta olmak üzere kritik açıklar kapanmadan canlıya çıkış "
            "kararı almak, sprint taahhüdünü ve müşteri güvenini aynı anda riske atar. "
            + (
                f"Özellikle REL-{near_rel[1].get('version')} penceresi daraldığı için "
                "öncelik netleştirilmeli."
                if near_rel
                else "Bu kayıtlar triage kuyruğunun en üstüne alınmalı."
            )
        )
        related = [b["external_id"] for b in top]
        if near_rel:
            related.append(f"REL-{near_rel[1].get('version')}")

        add(
            scenario="critical_bug",
            nid="critical-bug-opened",
            category="critical_risk",
            title="Kritik Bug Uyarısı",
            chips=chips,
            analysis=analysis,
            action=(
                f"Öncelikle {top[0]['external_id']}"
                + (f" ve {top[1]['external_id']}" if len(top) > 1 else "")
                + " kapatılmalı."
            ),
            related_ids=related,
            focus=focus_bug["external_id"],
            deepen_prompt="Açık kritik hata sayısı neden arttı?",
        )

    # ── 3) Başarısız test artışı ───────────────────────────────────────────
    if len(failed_tests) > 10:
        top_reqs = by_req_failed.most_common(4) or [("—", 0)]
        top_req, top_n = _pick(top_reqs, rng) or top_reqs[0]
        related = [t["external_id"] for t in failed_tests[:4]]
        if top_req != "—":
            related = [top_req] + related

        chips = ["Başarısız Test > 10", "Son dönem"]
        if top_req != "—":
            chips.append("Aynı Gereksinim ile İlişkili")

        # linked req revision hint
        req_row = next((r for r in requirements if r.get("external_id") == top_req), None)
        rev_hint = int((req_row or {}).get("revision_count") or 0)

        if top_req != "—":
            analysis = (
                f"{top_req} son "
                + (f"revizyonundan sonra " if rev_hint else "dönemde ")
                + "başarısız testlerde kümelenme tespit edildi. Bu durum gereksinim "
                "değişikliğinin kaliteyi etkilediğini gösteriyor. Release öncesinde ilgili "
                "testlerin yeniden çalıştırılması ve kök nedenin kapatılması önerilir."
            )
        else:
            analysis = (
                "Başarısız testler tek bir zincire bağlı değil; dağınık regresyon riski var. "
                "Önce en sık kırılan senaryolar önceliklendirilmeli."
            )

        add(
            scenario="failed_tests",
            nid=f"failed-test-rise-{top_req}",
            category="critical_risk",
            title="Başarısız Test Artışı",
            chips=chips,
            analysis=analysis,
            action=(
                f"{top_req} için kök neden ve regression planı açılmalı."
                if top_req != "—"
                else "Başarısız test kümeleri için öncelikli triage yapılmalı."
            ),
            related_ids=related[:6],
            focus=top_req if top_req != "—" else None,
            deepen_prompt=(
                f"{top_req} bağlı başarısız testler neden arttı?"
                if top_req != "—"
                else "Başarısız testler neden arttı?"
            ),
        )

    # ── 4) Release riski ───────────────────────────────────────────────────
    upcoming: list[tuple[int, dict]] = []
    for r in releases:
        if r.get("status") == "released":
            continue
        days = _days_until(r.get("release_date"))
        if days is not None and 0 <= days <= 21:
            upcoming.append((days, r))
        elif r.get("is_risky"):
            upcoming.append((30, r))
    upcoming.sort(key=lambda x: (x[0], -float(x[1].get("risk_score") or 0)))
    if upcoming:
        pool = upcoming[: min(3, len(upcoming))]
        days, rel = _pick(pool, rng) or upcoming[0]
        ver = rel.get("version")
        score = rel.get("risk_score")
        related = [f"REL-{ver}"] + [b["external_id"] for b in critical_bugs[:2]]

        chips = [f"Risk skoru ≥ {int(float(score or 0))}"]
        if isinstance(days, int) and days <= 21:
            chips.append(f"Release’e {days} Gün Kala")
        if critical_bugs:
            chips.append(f"Kritik Bug ≥ {len(critical_bugs)}")

        analysis = (
            f"REL-{ver} için zaman penceresi daralırken kalite sinyalleri hâlâ kırmızı. "
            f"Kritik açıklar ve başarısız testler birlikte okunduğunda go-live kararı "
            "erken görünüyor; yayın ertelenmezse müşteri etkisi oluşabilir."
        )

        add(
            scenario="release_risk",
            nid=f"release-risk-{ver}",
            category="critical_risk",
            title="Release Risk Uyarısı",
            chips=chips,
            analysis=analysis,
            action=f"Kritik hatalar kapatıldıktan sonra REL-{ver} yeniden değerlendirilmeli.",
            related_ids=related,
            focus=f"REL-{ver}",
            deepen_prompt=f"REL-{ver} yayınlanabilir mi?",
        )

    # ── 5) Sprint gecikmesi ────────────────────────────────────────────────
    if len(delayed) >= 8:
        sample = delayed[:]
        rng.shuffle(sample)
        chips = [f"Geciken Görev ≥ {len(delayed)}"]
        if blocked:
            chips.append(f"Bloke ≥ {len(blocked)}")
        chips.append("Sprint tempo sapması")

        analysis = (
            "Geciken ve bloke işler biriktiğinde sprint çıktısı yalnızca gecikmez; bağlı "
            "release tarihleri de kayar. Engeller açılmadan kapsamı korumak gerçekçi değil — "
            "önce bloke kayıtlar temizlenmeli."
        )

        add(
            scenario="sprint_delay",
            nid="sprint-delay",
            category="performance",
            title="Sprint Gecikme Uyarısı",
            chips=chips,
            analysis=analysis,
            action="Bloke işler için engel temizliği yapılmalı; süre aşımı tahminleri revize edilmeli.",
            related_ids=[t["external_id"] for t in sample[:5]],
            focus=sample[0]["external_id"],
            deepen_prompt="Sprint neden planın gerisinde?",
        )

    # ── 6) Kod değişti, test yok ───────────────────────────────────────────
    untested = [
        r
        for r in requirements
        if r["id"] in commit_req_ids and r["id"] not in recent_tested
    ]
    if untested:
        pool = untested[: min(6, len(untested))]
        r0 = _pick(pool, rng) or untested[0]
        chips = ["Commit var", "Son 7 Gün", "Test çalışması yok"]
        analysis = (
            f"{r0['external_id']} üzerinde kod değişikliği izlendi ancak yakın dönemde bağlı "
            "test çalışması görülmedi. Bu boşluk sessiz regressiyon üretir; PR kapanmadan "
            "doğrulama tamamlanmalı."
        )
        add(
            scenario="commit_no_test",
            nid=f"commit-no-test-{r0['external_id']}",
            category="ai_suggestion",
            title="Kod Değişti, Test Çalıştırılmadı",
            chips=chips,
            analysis=analysis,
            action=(
                f"{r0['external_id']} bağlı testleri çalıştırılmalı; "
                "sonuç yeşil olmadan PR kapatılmamalı."
            ),
            related_ids=[r["external_id"] for r in ([r0] + [x for x in pool if x is not r0])[:4]],
            focus=r0["external_id"],
            deepen_prompt=f"{r0['external_id']} için hangi testler eksik?",
        )

    # ── 7) Gereksinim değişti, test güncellenmedi ──────────────────────────
    changed_no_test = []
    for r in changed_reqs:
        recent = [
            t
            for t in all_tests
            if t.get("requirement_id") == r["id"]
            and (dt := _parse_dt(t.get("executed_at")))
            and dt >= since_7d
        ]
        if not recent:
            changed_no_test.append(r)
    if changed_no_test:
        pool = changed_no_test[: min(6, len(changed_no_test))]
        r0 = _pick(pool, rng) or changed_no_test[0]
        chips = ["Gereksinim: changed", "Bağlı test güncellenmedi", "Doğrulama boşluğu"]
        analysis = (
            f"{r0['external_id']} değişti fakat test sözleşmesi aynı kaldı. Gereksinim ile test "
            "arasındaki bu uyumsuzluk release öncesi gizli risk bırakır; senaryolar "
            "gözden geçirilmeden ilerlenmemeli."
        )
        add(
            scenario="changed_no_test",
            nid=f"changed-no-test-{r0['external_id']}",
            category="ai_suggestion",
            title="Gereksinim Değişti, Test Güncellenmedi",
            chips=chips,
            analysis=analysis,
            action=(
                f"{r0['external_id']} için test senaryoları gözden geçirilip "
                "yeniden çalıştırılmalı."
            ),
            related_ids=[r["external_id"] for r in ([r0] + [x for x in pool if x is not r0])[:4]],
            focus=r0["external_id"],
            deepen_prompt=f"{r0['external_id']} değişirse neler etkilenir?",
        )

    # ── 8) Modül bug yoğunluğu ─────────────────────────────────────────────
    if hot_modules and len(hot_modules[0][1]) >= 4:
        pool = [m for m in hot_modules if len(m[1]) >= 4][:4] or [hot_modules[0]]
        mod, bugs = _pick(pool, rng) or hot_modules[0]
        chips = [f"Modül: {mod}", f"Aktif Hata ≥ {len(bugs)}", "Kümelenme"]
        analysis = (
            f"{mod} modülünde hataların aynı bölgede yoğunlaşması rastgele değil; ortak bir "
            "değişiklik veya eksik regresyon ihtimali yüksek. Dağınık hotfix yerine kök neden "
            "odaklı remediation daha hızlı sonuç verir."
        )
        add(
            scenario="module_bugs",
            nid=f"module-bugs-{mod}",
            category="process_warning",
            title="Modül Bug Yoğunluğu",
            chips=chips,
            analysis=analysis,
            action=f"{mod} için ortak kök neden review’u ve hedefli test paketi açılmalı.",
            related_ids=[b["external_id"] for b in bugs[:5]],
            focus=bugs[0]["external_id"],
            deepen_prompt=f"{mod} modülündeki hataların kök nedeni nedir?",
        )

    # Dinamik seçim: senaryo çeşitliliği + rotasyon (her taramada farklı karışım)
    by_scenario: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for n in candidates:
        by_scenario[n["scenario"]].append(n)

    scenario_order = list(by_scenario.keys())
    rng.shuffle(scenario_order)
    # Kritik senaryoları öne al ama yine de karıştır
    preferred = ["critical_bug", "failed_tests", "release_risk", "req_change"]
    scenario_order.sort(key=lambda s: (0 if s in preferred else 1, preferred.index(s) if s in preferred else 99))

    selected: list[dict[str, Any]] = []
    seen_focus: set[str] = set()
    max_items = 5 + (seed % 2)  # 5 veya 6

    for scen in scenario_order:
        if len(selected) >= max_items:
            break
        item = by_scenario[scen][0]
        focus = item.get("focus_entity")
        if focus and focus in seen_focus and len(by_scenario[scen]) == 1:
            # aynı odak tekrarını azalt
            continue
        if focus:
            seen_focus.add(str(focus))
        # scenario alanını API'ye göndermeden önce temizle
        clean = {k: v for k, v in item.items() if k != "scenario"}
        selected.append(clean)

    # Hâlâ azsa kalan adaylardan doldur
    if len(selected) < min(4, len(candidates)):
        for n in candidates:
            if len(selected) >= max_items:
                break
            if any(s["id"] == n["id"] for s in selected):
                continue
            clean = {k: v for k, v in n.items() if k != "scenario"}
            selected.append(clean)

    selected.sort(key=lambda n: (n["priority"], n["title"]))

    records_scanned = (
        len(requirements)
        + len(tasks)
        + len(commits)
        + len(all_tests)
        + len(active_bugs)
        + len(releases)
    )
    critical_count = sum(1 for n in selected if n["category"] == "critical_risk")
    return {
        "generated_at": now.isoformat(),
        "count": len(selected),
        "summary": {
            "records_scanned": records_scanned,
            "notifications_created": len(selected),
            "critical_count": critical_count,
            "text": (
                f"Son tarama tamamlandı. {records_scanned} kayıt analiz edildi, "
                f"{len(selected)} tetikleyici bildirimi oluşturuldu."
                + (
                    f" Bunların {critical_count}'ü kritik risk seviyesinde."
                    if critical_count
                    else ""
                )
            ),
        },
        "items": selected,
    }
