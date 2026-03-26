# Vaulty AI - Creator Knowledge Vault

Vaulty AI is a powerful, AI-driven personal knowledge management (PKM) tool designed specifically for content creators. It acts as your "second brain," connecting your scattered ideas, notes, and content across various platforms into a centralized, searchable vault.

## Live Demo
Currently live at: [https://vaultyai.onrender.com](https://vaultyai.onrender.com)
*(Note: As it is hosted on Render's free tier, the application sleeps after 15 minutes of inactivity. Please allow 1-2 minutes for it to wake up on your first visit. v2 is pushed on branch-experiments and is not live on render yet)*

## Concept & Features

* **Centralized Knowledge Hub:** Connect and sync your content to automatically import videos, transcripts, and insights into one unified vault.
* **AI-Assisted Search & Discovery:** Move beyond keywords. Vaulty uses semantic search and state-of-the-art vector embeddings via Google GenAI to find exactly what you're looking for, even if you don't remember the exact phrasing.
* **Chat with Your Vault:** Discuss your ideas, ask questions, and brainstorm with an AI that has full context of your entire knowledge base. The assistant also builds memories based on facts from your chat sessions.
* **Content Remixing:** Repurpose your existing content. Vaulty helps you remix your ideas into new formats, translating a transcript into a dynamic social media thread or a comprehensive blog post structure.
* **Explore Connections:** Visualize similarities between pieces of content to uncover patterns in your creative thinking and unearth forgotten ideas.

## Tech Stack
* **Backend Framework:** Flask (Python)
* **Database:** PostgreSQL (production), SQLite (local) & SQLAlchemy (ORM)
* **Search & AI Models:** Groq API (LLM generation) & Google GenAI (Semantic search & Embeddings)
* **Data Ingestion:** `youtube-transcript-api`, `yt-dlp`, `feedparser`
* **Deployment Platform:** Render (Web Service) / Vercel (Configuration included)

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
   git clone <your-repository-url>
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

   # Database (Optional - Defaults to SQLite if omitted)
   # DATABASE_URL=postgresql://user:password@localhost/dbname
   ```

6. **Initialize the Database & Run the Application:**
   ```bash
   python app.py
   ```
   *The Flask app will start on local port 8000 and the required SQLite tables (`vault.db`) will be created automatically on the first request.*
   
7. **Access the Application:**
   Open your browser and navigate to: `http://localhost:8000` or `http://127.0.0.0:8000`

## Contributing

Contributions, issues, and feature requests are welcome! Ensure that all new features and bug fixes have adequate tests if necessary.
