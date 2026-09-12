# ProcessIQ (MVP)

**Yapay Zekâ Destekli Yazılım Süreç Analiz Platformu** — kurumsal yazılım geliştirme süreçlerindeki riskleri, gecikmeleri ve kalite sinyallerini **LLM + tool calling** ile analiz eden karar destek ürünü.

> Bu proje bir doküman yönetim sistemi veya klasik RAG chatbot değildir. LLM yalnızca intent anlayan ve service tool’larını çağıran orkestrasyon katmanıdır.

---

## Mimari

```
React (TypeScript + Tailwind)
        ↓
FastAPI  (/api/*)
        ↓
LLM Orchestrator (OpenAI tool calling · key yoksa heuristic)
        ↓
Service Layer (interface)
  ├── Requirement / Task / Commit / Test / Bug / Release / Project
        ↓
PostgreSQL  veya  demo için SQLite (spip.db)
```

Service interface’leri ileride SharePoint, Jira, Azure DevOps, Git, TestRail vb. adaptörlerle değiştirilebilir; frontend ve LLM tarafı aynı kalır.

---

## Hızlı başlangıç

### 1) Backend

```bash
cd backend
py -m pip install -r requirements.txt
copy .env.example .env
py -m app.seed.seed_data
py -m uvicorn app.main:app --reload --port 8001
```

> Frontend proxy varsayılan olarak **8001** portuna bakar (`frontend/vite.config.ts`). Farklı port kullanırsanız proxy’yi güncelleyin.

Varsayılan DB: `sqlite:///./spip.db` (kurulum gerektirmez).

PostgreSQL için:

```bash
docker compose up -d
```

`.env` örneği:

```
DATABASE_URL=postgresql+psycopg2://spip:spip@localhost:5432/spip
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

`OPENAI_API_KEY` yoksa AI modülleri **heuristic tool orkestrasyonu** ile çalışır (demo için yeterli).

### 2) Frontend

```bash
cd frontend
npm install
npm run dev
```

| Servis | Adres |
|--------|--------|
| Uygulama | http://localhost:5173 |
| API docs | http://localhost:8001/docs |

---

## Modüller

Tüm liste ekranlarında ortak standartlar:

- Üstte **Son Güncelleme** (sayfa verisinin en güncel zaman damgası)
- Tablolarda **Son Güncelleme** sütunu (`25 Tem 2026 14:35` formatı)
- Global **Proje** filtresi (üst sağ)
- Satır tıklanınca / ID ile **detay paneli**
- Dashboard KPI’larından ilgili listeye **doğrudan filtreli geçiş**

### 1. Gösterge Paneli (`/`)

Yönetici özeti kartları ve canlı KPI’lar:

- Aktif projeler, başarısız testler, kritik hatalar, riskli release’ler, geciken görevler
- Kart tıklanınca ilgili modüle filtrelenmiş yönlendirme
- **Son AI Analizleri** — `analysis_history` tablosundan (statik örnek yok)

### 2. Projeler (`/projeler`)

- Proje kodu, durum, aktif sprint ilerlemesi, gereksinim / açık hata özeti
- Riskli proje vurgusu
- **Son Güncelleme** — projeye bağlı en son aktivite

### 3. Gereksinimler (`/gereksinimler`)

- ID, proje, başlık, öncelik, durum
- **Son Güncelleme** + altında **N revizyon** (revizyon sayısı korunur; tarih son revizyon zamanını gösterir)
- Showcase senaryosu: `REQ-064` vb. ilişkili zincirler

### 4. Görevler (`/gorevler`)

- Sorumlu, sprint, tahmini / gerçek süre, gecikme tonu
- Filtreler: durum, geciken, overrun, başarısız teste bağlı vb.
- **Son Güncelleme** — görev `updated_at`

### 5. Kod Değişiklikleri (`/kod-degisiklikleri`)

- Commit hash, mesaj (Türkçe özellik/düzeltme), dal, geliştirici, dosya sayısı, risk
- **Son Güncelleme** — commit zamanı
- Mesajlarda `feat`/`fix` yerine Türkçe etiketler

### 6. Testler (`/testler`)

- Sonuç (geçti / başarısız / atlandı), bağlı gereksinim
- **Son Güncelleme** — son çalıştırma zamanı
- Dashboard “Başarısız Testler” kartı buraya filtreli açılır

### 7. Hatalar (`/hatalar`)

- Öncelik, etki seviyesi, durum, bağlı gereksinim / test
- Açılma tarihi (detay) + tabloda **Son Güncelleme**
- Kritik + aktif filtre Dashboard ile aynı metriği kullanır

### 8. Sürümler (`/release`)

- Sürüm, yayın tarihi, durum, risk skoru (bant: düşük / orta / yüksek)
- Yayın tarihi ayrı kalır; **Son Güncelleme** sürüm kaydının son düzenlenmesidir
- Riskli / aktif filtreler Dashboard KPI ile uyumlu

### 9. Süreç Görünümü (`/surec`)

- Gereksinim → görev → commit → test → bug → release zinciri
- Kırık / zayıf bağlantıları ve skorlu süreç yollarını gösterir
- Aynı DB kayıtlarından üretilir

### 10. AI Analiz Merkezi (`/analiz`)

- Doğal dil soru → intent → tool calling → yapılandırılmış bulgu
- Kayıt ID’leri (`REQ-`, `TASK-`, `TEST-`, `BUG-`, `REL-`) tıklanabilir linkler
- Sonuçlar `analysis_history`’e yazılır; Dashboard beslenir
- API key yoksa heuristic motor

### 11. AI Bildirim Merkezi (`/bildirimler`)

- Sayfa açılınca otomatik tarama (animasyonlu adımlar)
- Tetikleyici odaklı bildirimler: başlık, tetikleyici chip’leri, AI yorumu, önerilen aksiyon, ilgili kayıtlar
- Özet satırı: son tarama · tarama kayıt sayısı · üretilen bildirim
- Backend: `GET /api/notifications`

### 12. AI Yönetici Özeti (`/yonetici-ozeti`)

Dönem seçimi (**Bugün / Bu Hafta / Bu Ay**) + **AI Raporu Oluştur** ile üretilir (otomatik yüklenmez).

Rapor bölümleri:

| Bölüm | İçerik |
|--------|--------|
| Meta | Dönem aralığı, analiz edilen kayıt, son güncelleme, güven skoru |
| Genel Durum | Görev, bug, test, kalite skoru, release durumu |
| Kritik Gelişmeler | Dönem içi önemli olaylar |
| AI Değerlendirme | Yönetici diliyle özet + güven skoru |
| AI Önerileri | Aksiyon maddeleri |
| Trend | Önceki dönem ↔ bu dönem karşılaştırma tablosu + **AI Trend Yorumu** |
| AI Öncelikleri | İlk odaklanılacak kayıtlar |

**Trend tablosu:** Metrik · Önceki Dönem · Bu Dönem · Değişim  
Değişimde artış yeşil (▲), azalış kırmızı (▼); yüzde farkı gösterilir.

**İndirme:** PDF · Word · Excel · Markdown (`frontend/src/lib/executive-export.ts`)  
Backend: `GET /api/executive-summary?period=week|month|today`

---

## Veri tutarlılığı

Tüm ekranlar **aynı veritabanı** üzerinden çalışır. KPI tanımları `backend/app/metrics.py` içinde tek kaynaktır:

| Dashboard kartı | Doğrulama filtresi |
|-----------------|--------------------|
| Aktif Projeler | Projeler → durum = aktif |
| Başarısız Testler | Testler → sonuç = başarısız |
| Kritik Hatalar | Hatalar → etki = kritik + akış = aktif |
| Riskli Release’ler | Release → Riskli (≥70, aktif) |
| Geciken Görevler | Görevler → Gecikme = geciken |

AI analiz sonuçları `analysis_history` tablosuna yazılır. Statik örnek sayı kullanılmaz.

---

## Demo veri

```bash
cd backend
py -m app.seed.seed_data
```

Yaklaşık ölçek: **5 proje · ~100 gereksinim · ~300 görev · ~500 commit · ~250 test · ~40 bug · ~10 sürüm** — birbirine bağlı zincirler (showcase: `REQ-064`, `TASK-040`, `TEST-052`, `BUG-026` vb.).

---

## LLM tool’ları

`get_requirements` · `get_tasks` · `get_commits` · `get_tests` · `get_bugs` · `get_releases` · `get_project_summary`

LLM SQL yazmaz; yalnızca tool çağırır. Intent örnekleri: kök neden, etki analizi, release hazırlığı, risk, yönetici özeti, anomali, gereksinim revizyonu.

---

## Teknoloji özeti

| Katman | Stack |
|--------|--------|
| Frontend | React, TypeScript, Vite, Tailwind v4, Recharts, Lucide |
| Backend | FastAPI, SQLAlchemy, Pydantic |
| AI | OpenAI tool calling (opsiyonel) + heuristic fallback |
| Export | jsPDF, docx, SheetJS (xlsx) |
| DB | SQLite (demo) / PostgreSQL |

---

## Proje yapısı (özet)

```
backend/
  app/
    api/           # REST: data, analysis, notifications, executive-summary
    llm/           # orchestrator, notifications, executive_summary
    models/        # SQLAlchemy modelleri
    services/      # veri erişim / serileştirme
    seed/          # demo seed
frontend/
  src/
    pages/         # ekranlar (modül başına bir sayfa)
    components/    # layout, DataTable, DetailPanel, Badge…
    lib/           # api, utils, export, project-filter
```
