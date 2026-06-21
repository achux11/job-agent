# 💼 Job Assistant Agent

A fully local AI-powered job application assistant built with:
- **Ollama** — local LLM inference (llama3.2, mistral, etc.)
- **ChromaDB** — vector database for RAG (resume & research context)
- **SQLite** — persistent storage for applications, materials, chat history
- **Streamlit** — web UI

---

## 🚀 Quick Start

### 1. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 2. Install Ollama
Download from **https://ollama.com** and install for your OS.

### 3. Start Ollama & pull models
```bash
# In terminal 1 — start Ollama server
ollama serve

# In terminal 2 — pull models
ollama pull llama3.2            # main chat model (4.7GB)
ollama pull nomic-embed-text    # embeddings for RAG (274MB)

# Optional: lighter/heavier alternatives
ollama pull gemma2:2b           # faster, smaller
ollama pull llama3.1:8b         # smarter, larger
ollama pull mistral             # great for writing
```

### 4. Run the app
```bash
streamlit run app.py
```

Open **http://localhost:8501** in your browser.

---

## 📱 Features

| Page | What it does |
|------|-------------|
| 🤖 AI Chat Agent | Conversational agent with RAG — ask anything about your job search |
| 📝 Craft Materials | Generate cover letters, resume bullets, cold emails, LinkedIn messages |
| 🔍 Research | Company overviews, salary benchmarks, interview prep, industry trends |
| 📊 Tracker | Full application pipeline — add jobs, track status, kanban view |
| 📄 Resume Vault | Store your resume in sections, auto-vectorized for AI context |
| ⚙️ Settings | Model selection, storage stats, setup guide |

---

## 🧠 How RAG Works

1. You add your resume to the **Resume Vault** → stored in SQLite + indexed in ChromaDB
2. You research a company → results saved to ChromaDB
3. When you chat or craft materials → agent queries ChromaDB for relevant context
4. Context is injected into the prompt → AI gives personalized, grounded responses

---

## 📁 Project Structure

```
job-agent/
├── app.py              # Main Streamlit entry point
├── requirements.txt
├── data/
│   ├── jobs.db         # SQLite database
│   └── chroma/         # ChromaDB vector store
├── pages/
│   ├── chat.py         # AI agent chat
│   ├── craft.py        # Material generator
│   ├── research.py     # Company research
│   ├── tracker.py      # Application tracker
│   ├── vault.py        # Resume vault
│   └── settings.py     # Settings & setup
└── utils/
    ├── db.py           # SQLite helpers
    └── llm.py          # Ollama + ChromaDB helpers
```

---

## 💡 Tips

- Start by adding your resume in **Resume Vault** — it makes all AI outputs much more personalized
- Use **Research** before interviews — results are saved to your knowledge base
- The **AI Chat Agent** is the most powerful feature — describe your situation and ask for help
- All data is 100% local — nothing leaves your machine
