<div align="center">

# 🧠 Vaulty AI — Creator Knowledge Vault

**Capture. Connect. Create.**

Your digital second brain: save notes, PDFs and YouTube videos, then search, chat and remix them with AI.

[![Live Demo](https://img.shields.io/badge/live_demo-vaulty--16po.onrender.com-46E3B7?style=for-the-badge&logo=render&logoColor=white)](https://vaulty-16po.onrender.com)
[![Python](https://img.shields.io/badge/Python-3.11.6-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.1.2-000000?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Tests](https://img.shields.io/badge/tests-18_passing-brightgreen?style=flat-square)](tests/test_smoke.py)
[![Deploy](https://img.shields.io/badge/deploy-Render_+_Neon-1f6feb?style=flat-square)](#-deployment)

[Features](#-features) · [Screenshots](#-screenshots) · [Architecture](#-architecture) · [Quick Start](#-quick-start) · [Configuration](#-configuration) · [Deployment](#-deployment) · [API Routes](#-routes)

</div>

---

## 📖 What is Vaulty?

Vaulty is a **personal knowledge management (PKM) app built for content creators**. Instead of scattering ideas across Notes, Drive, bookmarks and a dozen chat windows, you drop everything into one vault — and then talk to it.

Every piece of content you save is embedded into a vector so you can search by **meaning** rather than exact wording, ask questions grounded in your own material, and remix a transcript into a thread, a blog outline or a summary in one click.

> **Live demo:** <https://vaulty-16po.onrender.com>
> Hosted on a free Render instance kept warm by a GitHub Actions ping, so there is no cold start.

---

## ✨ Features

| | Feature | What it does |
| :-- | :--- | :--- |
| 📥 | **Omni-capture** | Save plain notes and ideas, upload `.txt` / `.pdf`, or paste a YouTube URL to pull the transcript automatically. |
| 🔍 | **Semantic search** | Gemini embeddings + cosine similarity rank results by meaning. Keyword hits are highlighted in a centred snippet. |
| 💬 | **Chat with your vault** | Groq-powered assistant answers using your saved content as context, with per-session history. |
| 🧠 | **Persistent memory** | Facts the assistant learns during a chat are stored as memories and reused in later conversations. |
| ♻️ | **AI remix engine** | Turn one piece of content into a Twitter/X thread, LinkedIn post, blog outline or summary. |
| 🧭 | **Explore ideas** | Keyword discovery over Reddit (OAuth) with an automatic Hacker News fallback, plus AI summaries. |
| 📺 | **YouTube channel sync** | Connect a channel once; Vaulty polls its RSS feed and imports new video transcripts on demand. |
| 🗑️ | **Soft delete & restore** | Content is soft-deleted, individually restorable, and can be purged or restored in bulk. |
| 📊 | **Usage meter** | Per-user, per-feature credit counters (lifetime allowance + per-minute burst) surfaced in the UI. |
| 🔐 | **Firebase auth** | Email/password signup and login, server-side session, CSRF protection on every mutating route. |

---

## 📸 Screenshots

<div align="center">

![Vaulty landing page](docs/screenshots/landing.png)

*The landing page — dark, purple-accented, built with plain Jinja templates and one hand-written stylesheet.*

</div>

---

## 🏗 Architecture

```mermaid
flowchart TB
    subgraph Client
        B[Browser<br/>Jinja templates + vanilla JS]
    end

    subgraph Render["Render (Docker/Python, Singapore)"]
        GW[Gunicorn<br/>1 worker · 8 threads]
        F[Flask app factory<br/>ProxyFix · HTTPS redirect · security headers]
        GW --> F
    end

    subgraph Blueprints
        AU[auth.py]
        CO[content.py]
        SE[search.py]
        CH[chat.py]
        RE[remix.py]
        EX[explore/]
        ST[settings.py]
    end

    subgraph Services
        AI[ai.py<br/>embeddings · LLM · cosine]
        RL[rate_limit.py<br/>per-user credit buckets]
        YT[youtube_utils.py]
        RD[reddit_utils.py]
    end

    subgraph External
        FB[Firebase Auth]
        GQ[Groq API]
        GE[Google GenAI]
        YTA[YouTube transcripts / RSS]
        RED[Reddit · Hacker News]
    end

    DB[(PostgreSQL<br/>Neon)]

    B -->|HTTPS| GW
    F --> AU & CO & SE & CH & RE & EX & ST
    AU --> FB
    CO --> YT & AI
    SE --> AI
    CH --> AI & RL
    RE --> AI & RL
    EX --> RD & AI
    ST --> YT
    AI --> GQ & GE
    YT --> YTA
    RD --> RED
    AU & CO & SE & CH & RE & EX & ST --> DB
```

### Request lifecycle

```mermaid
sequenceDiagram
    autonumber
    participant U as Browser
    participant F as Flask
    participant R as rate_limit
    participant A as ai.py
    participant G as Groq
    participant D as Postgres

    U->>F: POST /chat/42/send (JSON + CSRF)
    F->>F: before_request → resolve Firebase session (g.user_id)
    F->>F: ensure schema exists (once per process)
    F->>R: check_and_increment(user, "groq_chat")
    alt burst or credit limit hit
        R-->>F: 429 + retry hint
        F-->>U: {"error": "..."} (credit refunded)
    else allowed
        R-->>F: ok
        F->>D: load vault context + chat history
        F->>A: generate reply
        A->>G: chat completion
        G-->>A: tokens
        A-->>F: reply
        F->>D: persist user + assistant messages
        F-->>U: JSON reply
    end
```

### Data model

```mermaid
erDiagram
    CONTENT ||--o| EMBEDDING : "has vector"
    CHAT_SESSION ||--o{ CHAT_MESSAGE : "contains"

    CONTENT {
        int id PK
        string user_id "Firebase UID"
        string title
        text body
        string content_type "note|idea|pdf|youtube"
        string source_url
        bool is_deleted
        datetime created_at
    }
    EMBEDDING {
        int id PK
        int content_id FK
        text vector "JSON float array"
    }
    CHAT_SESSION {
        int id PK
        string user_id
        string title
        datetime created_at
        datetime updated_at
    }
    CHAT_MESSAGE {
        int id PK
        int session_id FK
        string role "user|assistant"
        text content
        datetime created_at
    }
    MEMORY {
        int id PK
        string user_id
        text fact
        string source
        datetime created_at
    }
    SOCIAL_PROFILE {
        int id PK
        string user_id
        string platform
        string profile_url
        string channel_id
        string last_synced_video
    }
    USER_API_USAGE {
        int id PK
        string user_id
        string api_type
        datetime window_start
        int call_count
    }
    USER_API_MINUTE_USAGE {
        int id PK
        string user_id
        string api_type
        int call_count
        datetime minute_start
    }
```

---

## 🧰 Tech stack

| Layer | Choice | Why |
| :--- | :--- | :--- |
| Web framework | **Flask 3.1** + Blueprints | Small surface area, one blueprint per feature domain |
| ORM / DB | **SQLAlchemy 2.0** via Flask-SQLAlchemy | SQLite locally, PostgreSQL in production, same models |
| Auth | **Firebase Authentication** | No password storage, no user table to maintain |
| LLM | **Groq** (`qwen/qwen3.8-27b`) | Fast, cheap chat + remix + title generation |
| Embeddings | **Google GenAI** (`gemini-embedding-001`) | 768-dim vectors for semantic search |
| Summaries | **Gemini** (`gemini-2.5-flash`) | Explore topic summaries |
| Ingestion | `youtube-transcript-api`, `yt-dlp`, `feedparser`, `pypdf` | Video transcripts, channel RSS, PDF text |
| Frontend | Jinja2 + vanilla JS + one CSS file | No build step, no node_modules |
| Server | **Gunicorn** | `1 worker × 8 threads` on free tier, `2 × 4` in Docker |
| Hosting | **Render** (free) + **Neon** Postgres (free) | No credit card, no DB expiry |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- A **Groq** key — <https://console.groq.com/keys>
- A **Gemini** key — <https://aistudio.google.com/app/apikey>
- A **Firebase Web API key** — Firebase console → Project settings → Your apps → Web API key

### 1. Clone & install

```bash
git clone https://github.com/AvishkarJadkar/creator_knowledge_vault.git
cd creator_knowledge_vault

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
```

Fill in at minimum:

```env
FLASK_ENV=development
SECRET_KEY=dev-secret-key-ONLY-for-local

GROQ_API_KEY=...
GEMINI_API_KEY=...
FIREBASE_API_KEY=...
```

### 3. Run

```bash
python app.py
```

Open <http://localhost:8000>. The SQLite database (`instance/vault.db`) is created automatically on the first request — no migration step.

### 4. Test

```bash
python -m unittest discover -s tests -v
```

> 18 offline smoke tests (auth, CRUD, search snippets, uploads, CSRF, security headers, error pages). AI calls are mocked and the database is a throwaway SQLite file, so **no quota is consumed** and `instance/vault.db` is never touched.
>
> Run the same suite against PostgreSQL with:
> ```bash
> TEST_DATABASE_URL=postgresql://user:pass@host/db python -m unittest discover -s tests -v
> ```

---

## ⚙️ Configuration

### Environment variables

| Variable | Required | Default | Notes |
| :--- | :---: | :--- | :--- |
| `FLASK_ENV` | ✅ | `development` | `production` enables secure cookies + HTTPS redirect and **refuses to boot without `SECRET_KEY`** |
| `SECRET_KEY` | ✅ (prod) | — | Long random string used to sign sessions and CSRF tokens |
| `GROQ_API_KEY` | ✅ | — | Chat, remix, chat titles |
| `GEMINI_API_KEY` | ✅ | — | Embeddings + Explore summaries |
| `FIREBASE_API_KEY` | ✅ | — | Signup/login; without it auth is disabled |
| `DATABASE_URL` | — | `sqlite:///instance/vault.db` | `postgres://` and `postgresql://` are both normalised to the bundled psycopg2 driver |
| `REDDIT_CLIENT_ID` | — | — | Enables Reddit's authenticated API for Explore |
| `REDDIT_CLIENT_SECRET` | — | — | Without Reddit creds, Explore falls back to Hacker News |
| `GROQ_CHAT_MODEL` | — | `qwen/qwen3.8-27b` | Override without touching code |
| `GROQ_FAST_MODEL` | — | `qwen/qwen3.8-27b` | Used for titles / short tasks |
| `GEMINI_MODEL` | — | `gemini-2.5-flash` | Explore summaries |
| `GEMINI_EMBED_MODEL` | — | `gemini-embedding-001` | Search embeddings |

### Free-tier credit buckets

`rate_limit.py` keeps a central `TRIAL_LIMITS` table. Two counters are enforced per user **per feature** — a lifetime allowance and a per-minute burst guard:

| Feature (`api_type`) | Label | Credits | Burst / min |
| :--- | :--- | ---: | ---: |
| `groq_chat` | Chat Credits | 50 | 5 |
| `groq_remix` | Remix Credits | 30 | 3 |
| `gemini_embed` | Search & Embedding Credits | 200 | 10 |
| `gemini_explore` | Explore Credits | 20 | 3 |

Rejected calls are **refunded** so a failed AI request never burns a credit. Adjust the table to introduce paid tiers.

---

## 🗺 Project structure

```text
creator_knowledge_vault/
├── app.py                 # App factory: config, ProxyFix, hooks, error handlers, /health, /healthz
├── auth.py                # Signup / login / logout (Firebase + server session)
├── content.py             # Add, view, soft-delete, restore, bulk purge
├── search.py              # Semantic search + snippet builder
├── chat.py                # Chat sessions, messages, memory
├── remix.py               # Content → thread / post / outline / summary
├── settings.py            # Profile, onboarding, YouTube sync, /api/usage
├── ai.py                  # Groq + Gemini clients, embeddings, cosine similarity
├── rate_limit.py          # Per-user, per-feature credit buckets
├── youtube_utils.py       # Transcripts, titles, channel RSS
├── reddit_utils.py        # Reddit OAuth + Hacker News fallback
├── firebase_client.py     # ID-token verification
├── models.py              # 8 SQLAlchemy models
├── extensions.py          # Shared db instance
├── explore/               # Explore blueprint (search + summaries)
├── api/index.py           # Vercel serverless entry point
├── templates/             # 14 Jinja templates
├── static/style.css       # Single stylesheet (design tokens + components)
├── tests/test_smoke.py    # 18 stdlib unittest cases
├── Dockerfile             # python:3.11-slim + gunicorn
├── render.yaml            # Render blueprint (free plan)
├── railway.json           # Railway config
├── vercel.json            # Vercel config
└── .github/workflows/     # keepalive.yml — stops the free instance from sleeping
```

---

## 🔌 Routes

| Method | Path | Purpose |
| :--- | :--- | :--- |
| `GET` | `/` | Landing page, or redirect to dashboard when signed in |
| `GET` | `/healthz` | Liveness only, no database call (`200`) — used by Render/Docker health checks |
| `GET` | `/health` | Liveness + `SELECT 1` database check (`200` / `503`) |
| `GET` `POST` | `/signup`, `/login` | Firebase-backed auth |
| `POST` | `/logout` | CSRF-protected sign out |
| `GET` | `/dashboard` | Content list with live counts |
| `GET` `POST` | `/add` | Note / idea / `.txt` / `.pdf` / YouTube import |
| `GET` | `/content/<id>` | Content detail |
| `POST` | `/content/<id>/delete`, `/restore` | Soft delete / restore |
| `POST` | `/content/delete_all`, `/restore_all` | Bulk operations |
| `GET` `POST` | `/search` | Semantic search (JSON for AJAX) |
| `GET` | `/chat`, `/chat/<session_id>` | Chat UI |
| `POST` | `/chat/new`, `/chat/<id>/send`, `/chat/<id>/delete` | Chat lifecycle |
| `POST` | `/chat/memory/<id>/delete` | Forget a stored fact |
| `GET` `POST` | `/remix/<content_id>` | Remix a piece of content |
| `GET` | `/explore`, `/explore/search` | Idea discovery + summaries |
| `GET` | `/settings`, `/onboarding` | Profile + onboarding |
| `POST` | `/settings/add-profile`, `/settings/remove-profile/<id>`, `/settings/sync-youtube/<id>` | Social profiles + YouTube sync |
| `GET` | `/api/usage` | Credit usage for the current user |

---

## ☁️ Deployment

The repo ships four deployment paths. The live instance uses the first one.

### Render + Neon (free, no credit card)

| Piece | Service | Free allowance |
| :--- | :--- | :--- |
| Web app | Render web service (`render.yaml`) | 750 instance hours/mo, 0.1 CPU / 512 MB |
| Database | [Neon](https://neon.com) Postgres | 1 GB storage, 100 CU-hours/mo, no expiry |
| Keep-alive | GitHub Actions (`.github/workflows/keepalive.yml`) | unlimited on public repos |

**Steps**

1. Sign up at <https://dashboard.render.com/register> (GitHub login, no card).
2. Create a Neon project at <https://neon.com/signup> and copy the connection string (`postgresql://…?sslmode=require`).
3. Render → **New → Blueprint** → pick this repo and `main`. `render.yaml` creates the service.
4. Fill the `sync: false` env vars (table above); `DATABASE_URL` is the Neon string.
5. Optionally set the repository variable `VAULTY_URL` (Settings → Secrets and variables → Actions → Variables) if your hostname differs from the default in the workflow.

**Free-tier traps, already handled:**

- **15-minute spin-down.** The keep-alive workflow pings `/` every 5 minutes, so the service should never idle long enough to sleep. In practice GitHub's scheduler is best-effort and often coalesces these runs to one every few hours, which is *not* enough — so add a free external pinger as well:
  1. Create a free account at [cron-job.org](https://cron-job.org) (or UptimeRobot / Better Stack).
  2. Add a job for `https://vaulty-16po.onrender.com/` (**not** `/health`) every 5 minutes.
  3. Keep the GitHub workflow as a backup, and check its runs occasionally.

  Pinging `/` instead of `/health` lets Neon scale to zero, staying inside its 100 CU-hour allowance.
- **Free Postgres expires after 30 days.** That is why the database is on Neon.
- **750 instance hours/month.** Running 24/7 uses ~744 of the 750 free hours, leaving very little headroom — if Render ever suspends the service, trim the pinger to daytime hours (e.g. `0 1-18 * * *` UTC) so it sleeps at night.

### Docker

```bash
docker build -t vaulty .
docker run --rm -p 8000:8000 --env-file .env -e FLASK_ENV=development vaulty
```

The image runs `gunicorn app:app --workers 2 --threads 4 --timeout 120 --preload` and exposes `GET /healthz` for container health checks.

### Railway

`railway.json` + `Procfile` are included; point `DATABASE_URL` at a Railway/Neon Postgres and set the same env vars.

### Vercel

`vercel.json` + `api/index.py` work for a demo, but **serverless functions have no persistent filesystem**, so uploads and background YouTube syncs are not reliable. Use Render/Railway for the full feature set.

---

## 🩺 Troubleshooting

| Symptom | Cause | Fix |
| :--- | :--- | :--- |
| `ModuleNotFoundError: No module named 'psycopg'` | SQLAlchemy 2.0 defaults `postgresql://` to psycopg **3**, but this app ships psycopg2 | Already fixed — `app.py` rewrites the URL to `postgresql+psycopg2://` |
| App exits on boot in production | `SECRET_KEY` missing | Set a long random `SECRET_KEY` |
| Login/signup page loads but auth fails | `FIREBASE_API_KEY` missing or wrong project | Re-copy the Web API key from Firebase |
| First request takes ~1 minute, or the browser shows Render's "service starting" splash | Render free instance was asleep (15-minute spin-down) | Add the external 5-minute pinger from the keep-alive section — GitHub's cron alone runs too rarely |
| Deploy marked **failed** but the previous version still serves | Platform health check hit a sleeping database, or free instance hours ran out | Health checks now use `/healthz`; check the Render event log for `health check` vs `exited with status` |
| `503` from `/health` | Database unreachable | Check `DATABASE_URL`, Neon project status, and that `sslmode=require` is present |
| YouTube import fails | The video has no transcript, or the IP is rate-limited by YouTube | Retry later or paste the text as a note |
| `429` / "credits" message | Free-tier bucket exhausted | See the credit table above; counters live in `user_api_usage` |

---

## 🤝 Contributing

1. Fork the repo and create a branch: `git checkout -b feat/my-feature`
2. Keep the existing blueprint structure and inline-template JS style.
3. Add a test in `tests/test_smoke.py` for any behaviour change.
4. Run `python -m unittest discover -s tests -v` — all 18 must pass.
5. Open a pull request describing the change and the test you added.

Bug reports and feature requests are welcome in the issue tracker.

---

<div align="center">

**Built by [Avishkar Jadkar](https://github.com/AvishkarJadkar)**

*Vaulty is a personal project — if you find it useful, a ⭐ helps.*

</div>
