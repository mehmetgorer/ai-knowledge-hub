# AI Knowledge Hub

[English](README.md) | **Türkçe**

**Belgelerde anlamsal arama ve kaynaklı soru-cevap**

PDF, TXT ve Markdown dosyalarını yükleyip içeriklerinde arama yapabilir, belgelerle ilgili sorularınıza kaynak gösteren yanıtlar alabilirsiniz. Embedding ve yanıt üretimi bilgisayarınızda çalışır (Ollama); repoda barındırılmış bir demo yoktur.

![Ask AI: backend teknolojisi sorusuna rag-test.pdf kaynaklı yanıt](docs/screenshots/ask-ai-grounded-answer.png)

## Uygulama ne yapar?

- **Koleksiyonlar** — Neon Auth ile giriş; koleksiyon ve belgeler hesabınıza bağlıdır (API isteklerinde JWT).
- **Yükleme** — PDF, TXT veya Markdown; boyut ve tür kontrolü.
- **İşle & indeksle** — Metin çıkarımı, parçalama, **`intfloat/multilingual-e5-small`** ile embedding (384 boyut), **PostgreSQL + pgvector**’e yazma.
- **Anlamsal arama** — Seçili koleksiyondaki parçaları kosinüs mesafesine göre sıralar. *(Aşağıda ekran görüntüsü yok; Ask AI aynı retrieval adımını kullanır.)*
- **Ask AI** — İlgili parçaları getirir, **Ollama (`qwen3:1.7b`)** ile yanıt üretir, atıf ve alıntıları doğrular; destekleyici kanıt yoksa veya doğrulama geçmezse yanıt vermez.

## Ekran görüntüleri

Görsellerdeki **`rag-test.pdf`**, “Northstar Data Platform” adlı **kurgu demo metnidir**. PDF’teki rakamlar ve politikalar bu projenin gerçek operasyonunu anlatmaz.

### Atıflı yanıt

Üstteki görsel: Türkçe backend sorusu, **[S1]** atıflı yanıt, model satırı ve yapısal doğrulama notu.

### Yanıtın dayandığı kaynak

![S1 açık: PDF alıntısı, sayfa numaraları, retrieval sırası](docs/screenshots/ask-ai-source-evidence.png)

* **[S1]** genişletilmiş: `rag-test.pdf` parça metni, sayfalar, kosinüs mesafesi.*

### Kaynak bulunamadığında

![Doğrulanmış kaynak olmadığında yanıt üretilmiyor](docs/screenshots/ask-ai-abstention.png)

*Bulut sağlayıcı sorusu; arayüz doğrulanmış kaynak dönmediğini bildiriyor—uydurma cevap yok.*

### İndekslenmiş belge

![Documents sekmesinde Ready durumundaki rag-test.pdf](docs/screenshots/documents-indexed-pdf.png)

*Yükleme, işleme ve indeksleme sonrası **Ready** (aranabilir).*

### PDF'den alınan sayısal bilgi

![Sayfa 3’teki 14 günlük yedek saklama bilgisine atıflı yanıt](docs/screenshots/ask-ai-numeric-fact.png)

*Tek bir bilgi satırı ve **[S1]**; birden fazla bağımsız bilgi isteyen sorular tutarlı yanıtlanmayabilir.*

## Belgeler yanıta nasıl dönüşür?

Model tüm arşivi görmez—yalnızca getirilen parçalar prompt’a girer.

```
Yükleme → çıkarım → parçalama → E5 embedding → pgvector
Soru → sorgu embedding → parça seçimi → Ollama (JSON)
→ atıf / alıntı doğrulama → yanıt + kaynaklar veya abstention
```

**Atıflar** — API, atıf kimliklerinin ve alıntıların getirilen metinle uyumunu kontrol eder (yapısal doğrulama). Birçok uydurma referans elenir; **her cümle için tam doğruluk** iddiası değildir.

**Testler** — 5D denetiminde sahiplik regresyonları, işleme/indeksleme sırasında atomik silme ve CI’da PostgreSQL entegrasyon testleri eklendi. Bu, **kurumsal güvenlik veya SLA** vaadi değildir.

## Mimari ve teknoloji

| Katman | Teknoloji |
| ------ | --------- |
| Arayüz | Next.js, TypeScript, Tailwind |
| Kimlik | Neon Auth → API’ye JWT |
| API | Python 3.12, FastAPI, SQLAlchemy 2, uv |
| Veri | PostgreSQL 17, pgvector, Alembic |
| Embedding | Sentence Transformers, `intfloat/multilingual-e5-small` (384 boyut, yerel CPU) |
| Yanıt | Ollama `qwen3:1.7b` (sunucu tarafı HTTP; bu repoda fine-tune yok) |

```
apps/web ──JWT/REST──► services/api ◄──► PostgreSQL (pgvector)
                           ├── yerel dosya depolama
                           ├── Sentence Transformers (E5)
                           └── Ollama HTTP
```

## Testler ve CI

[![CI](https://github.com/mehmetgorer/ai-knowledge-hub/actions/workflows/ci.yml/badge.svg)](https://github.com/mehmetgorer/ai-knowledge-hub/actions/workflows/ci.yml)

`main` dalına her push’ta:

1. **Frontend** — lint, typecheck, birim testler, build  
2. **Backend** — Ruff, **180+** birim test  
3. **Backend integration** — pgvector’lü geçici Postgres’te **95+** test  

Ayrıntı: [`docs/QUALITY_AUDIT.md`](docs/QUALITY_AUDIT.md)

```powershell
npm run lint
npm run typecheck
npm run test --workspace=web
npm run build
cd services\api
uv run ruff check .
uv run pytest
uv run pytest -m integration
```

## Yerel kurulum

**Canlı demo yok**—Postgres, API, Ollama ve Next.js’i yerelde çalıştırırsınız. `.env` / `.env.local` commit etmeyin.

**Gereksinimler:** Node.js, Python 3.12+, [uv](https://docs.astral.sh/uv/), Docker (Postgres), [Ollama](https://ollama.com), Neon Auth değişkenleri (web: `NEON_AUTH_*`, API: `AUTH_*`).

1. **Veritabanı** (repo kökü): `Copy-Item .env.example .env` ardından `docker compose up -d` (varsayılan port **5433**).  
2. **API** (`services/api`): `uv sync` → `.env` içinde `AUTH_*` ve Ollama → `uv run alembic upgrade head` → `uv run ai-knowledge-hub-api` → `ollama pull qwen3:1.7b`.  
3. **Web** (repo kökü): `npm install` → `apps/web/.env.example` → `.env.local` → `npm run dev` → [http://localhost:3000/dashboard](http://localhost:3000/dashboard).

Geliştirme notları: [`docs/HANDOFF.md`](docs/HANDOFF.md)

## Bilinen sınırlar

- Portföy MVP; tüm servisleri siz işletirsiniz.  
- Yapısal atıf kontrolü mükemmel cevap garantisi değildir; çok adımlı sorular kısmen yanlış veya abstention olabilir.  
- İşleme/indeksleme API sürecinde senkron; çökme sonrası belge durumu manuel düzeltme gerektirebilir.  
- CI’da Ask için Ollama mock’lanır; kaliteyi yerelde Ollama ile deneyin.
