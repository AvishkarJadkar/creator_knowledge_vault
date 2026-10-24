# Vaulty AI - Creator Knowledge Vault

Vaulty AI is a powerful, AI-driven personal knowledge management (PKM) tool designed specifically for content creators. It acts as your "second brain," connecting your scattered ideas, notes, and content across various platforms into a centralized, searchable vault.

## Live Demo
Currently live at: [https://vaultyai.onrender.com](https://vaultyai.onrender.com)
*(Note: As it is hosted on Render's free tier, the application sleeps after 15 minutes of inactivity. Please allow 1-2 minutes for it to wake up on your first visit.)*

## Concept & Features

* **Centralized Knowledge Hub:** Connect and sync your content to automatically import videos, transcripts, and insights into one unified vault.
* **AI-Assisted Search & Discovery:** Move beyond keywords. Vaulty uses semantic search and state-of-the-art vector embeddings via Google GenAI to find exactly what you're looking for, even if you don't remember the exact phrasing.
* **Chat with Your Vault:** Discuss your ideas, ask questions, and brainstorm with an AI that has full context of your entire knowledge base. The assistant also builds memories based on facts from your chat sessions.
* **Content Remixing:** Repurpose your existing content. Vaulty helps you remix your ideas into new formats, translating a transcript into a dynamic social media thread or a comprehensive blog post structure.
* **Explore Connections:** Visualize similarities between pieces of content to uncover patterns in your creative thinking and unearth forgotten ideas.
* **Explore Ideas:** Explore new ideas from reddit by using keyword search feature.

## Tech Stack
* **Backend Framework:** Flask (Python)
* **Database:** PostgreSQL (production), SQLite (local) & SQLAlchemy (ORM)
* **Search & AI Models:** Groq API (LLM generation) & Google GenAI (Semantic search & Embeddings)
* **Data Ingestion:** `youtube-transcript-api`, `yt-dlp`, `feedparser`
* **Deployment Platform:** Docker / Northflank (always-on free tier) · Render & Railway configs included

---

## Local Setup Guide

Follow these steps to get Vaulty AI running on your local machine.

### Prerequisites
* Python 3.8+
* API keys for the AI providers:
  * [Groq Cloud](https://console.groq.com/keys)
  * [Google AI Studio (Gemini)](https://aistudio.google.com/app/apikey)

### Installation Steps

1. **Clone the repository and access the vault:**
   If you haven't already:
   ```bash
   git clone https://github.com/AvishkarJadkar/creator_knowledge_vault
   cd creator_knowledge_vault
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment:**
   * **Windows:**
     ```cmd
     venv\Scripts\activate
     ```
   * **macOS/Linux:**
     ```bash
     source venv/bin/activate
     ```

4. **Install the required dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

5. **Set up Environment Variables:**
   Create a `.env` file in the root directory (`creator_knowledge_vault`) and add your API keys. Include the following configuration keys:
   ```env
   # Application Configuration
   FLASK_ENV=development
   SECRET_KEY=dev-secret-key-ONLY-for-local

   # APIs (Required)
   GROQ_API_KEY=your_groq_api_key_here
   GEMINI_API_KEY=your_google_api_key_here
   FIREBASE_API_KEY=your_firebase_web_api_key_here

   # Optional: Reddit API for Explore (falls back to Hacker News when unset)
   # REDDIT_CLIENT_ID=your_reddit_client_id
   # REDDIT_CLIENT_SECRET=your_reddit_client_secret

   # Database (Optional - Defaults to SQLite if omitted)
   # DATABASE_URL=postgresql://user:password@localhost/dbname
   ```

   > `FIREBASE_API_KEY` is required for signup/login. Grab it from the Firebase
   > console → Project settings → Your apps → Web API key.

6. **Initialize the Database & Run the Application:**
   ```bash
   python app.py
   ```
   *The Flask app starts on local port 8000. The SQLite database (`instance/vault.db`)
   is created automatically on the first request.*

7. **Access the Application:**
   Open your browser and navigate to: `http://localhost:8000` or `http://127.0.0.0:8000`

8. **Run the test suite (optional but recommended):**
   ```bash
   python -m unittest discover -s tests -v
   ```
   *18 offline smoke tests covering auth, CRUD, search, uploads, CSRF and error
   pages. They use a temporary SQLite database and mock the AI calls, so no API
   quota is consumed.*

## Deployment (production)

The app ships as a container (`Dockerfile`) and also includes platform configs
for **Northflank** (recommended), **Render** (`render.yaml`), **Railway**
(`railway.json` / `Procfile`) and **Vercel** (`vercel.json`).

### Why Northflank

| | Northflank Sandbox | Render Free |
| --- | --- | --- |
| Sleeps when idle | **No — always on** | Yes, after 15 min (~1 min cold start) |
| Free database | 1 addon included, no expiry | Postgres expires after 30 days |
| Credit card | Not required | Not required |
| Included compute | Up to $20/mo of resources | 750 instance hours/mo |
| Custom domain + TLS | Included | Included |

Sandbox limits: 2 services, 2 jobs, 1 database, 1 project. That is enough for
this app (one web service + one Postgres).

### Deploy on Northflank (no card)

1. Sign up at <https://app.northflank.com/signup> and create a project.
2. **Add a PostgreSQL addon** to the project (1 GB is plenty), then copy its
   connection string.
3. **Create a service** → *Combined* → *Build from repository* → connect GitHub
   → pick this repo and the `main` branch.
4. Build settings: **Dockerfile** (path `Dockerfile`), build context `/`.
5. Set the service's internal port to **8000** and the health check path to
   **`/health`**.
6. Add the environment variables from the table below (`DATABASE_URL` = the
   addon's connection string).
7. Deploy. The first build installs the pinned dependencies (~2–4 min).

The container runs:
`gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120 --preload`

### Environment variables

| Variable | Required | Notes |
| --- | --- | --- |
| `FLASK_ENV` | ✅ | Set to `production`. Enables secure cookies and HTTPS redirects. |
| `SECRET_KEY` | ✅ | Long random string. The app refuses to boot without it in production. |
| `DATABASE_URL` | ✅ | PostgreSQL connection string. |
| `GROQ_API_KEY` | ✅ | Chat, Remix and chat titles. |
| `GEMINI_API_KEY` | ✅ | Embeddings + Explore summaries. |
| `FIREBASE_API_KEY` | ✅ | Signup/login. Without it auth is disabled. |
| `REDDIT_CLIENT_ID` | optional | Enables Reddit's authenticated API for Explore. |
| `REDDIT_CLIENT_SECRET` | optional | Without Reddit creds, Explore falls back to Hacker News. |

Model names can be overridden without code changes:
`GROQ_CHAT_MODEL`, `GROQ_FAST_MODEL`, `GEMINI_MODEL`, `GEMINI_EMBED_MODEL`.

Dependencies are pinned in `requirements.txt` to the versions this release was
tested with, and Python is pinned to 3.11.6 (`.python-version`, `Dockerfile`).
Database tables are created on the first request, so a fresh Postgres instance
needs no manual migration step.

### Run the production image locally

```bash
docker build -t vaulty .
docker run --rm -p 8000:8000 --env-file .env -e FLASK_ENV=development vaulty
```

### Render (free tier)

`render.yaml` deploys the service and a Postgres database in one blueprint.
Two free-tier caveats: web services **spin down after 15 minutes** of no
traffic, and free Postgres **expires after 30 days**.

A keep-alive ping every 10 minutes prevents the spin-down (750 free instance
hours ≈ a full month of one always-on service), e.g. a GitHub Actions schedule:

```yaml
on:
  schedule: [{ cron: "*/10 * * * *" }]
jobs:
  ping:
    runs-on: ubuntu-latest
    steps:
      - run: curl -fsS https://YOUR-SERVICE.onrender.com/health
```

That does not fix the database expiry — pair it with a free Postgres from
Neon/Supabase, or use Northflank/Railway instead.

> **Vercel:** `vercel.json` is included, but serverless functions have no
> persistent filesystem, so uploads and background YouTube syncs won't work.
> Use Northflank, Render or Railway with PostgreSQL for the full feature set.

## Contributing

Contributions, issues, and feature requests are welcome! Ensure that all new features and bug fixes have adequate tests if necessary.
