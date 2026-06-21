# 💼 Job Application Agent

An AI-powered job application assistant built with a full local stack — no external APIs needed.

## 🤖 What it does
- Writes tailored cover letters, resume bullets, cold emails and LinkedIn messages
- Researches companies, salaries and interview questions with live web search
- Tracks all job applications with status updates and pipeline view
- Stores your resume and vectorizes it for personalized AI responses (RAG)
- AI chat agent that knows your background and gives personalized advice

## 🛠️ Tech Stack
- **UI** — Streamlit
- **LLM** — Ollama + llama3.2 (local)
- **Vector DB** — ChromaDB (resume + research storage)
- **Embeddings** — nomic-embed-text via Ollama
- **Relational DB** — SQLite (applications, chat history, materials)
- **Architecture** — RAG (Retrieval Augmented Generation)
- **Streaming** — Ollama streaming API

## 🚀 How to run
1. Install Ollama from https://ollama.com
2. Pull models:
   - `ollama pull llama3.2`
   - `ollama pull nomic-embed-text`
3. Install dependencies: `pip install -r requirements.txt`
4. Run: `streamlit run app.py`
5. Open http://localhost:8501

## 📱 Pages
- 🤖 AI Chat Agent — Conversational agent with RAG context
- 📝 Craft Materials — Cover letters, emails, resume bullets
- 🔍 Research — Company research, salary benchmarks, interview prep
- 📊 Application Tracker — Full pipeline with kanban view
- 📄 Resume Vault — Store and vectorize your resume
- ⚙️ Settings — Model config and storage stats

## 👤 Author
Built by [achux11](https://github.com/achux11)
