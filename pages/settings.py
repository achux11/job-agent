import streamlit as st
import requests
import os
from utils.llm import list_ollama_models, OLLAMA_BASE, CHROMA_PATH
from utils.db import DB_PATH, get_conn


def render():
    st.markdown("""
    <div class="main-header">
        <h1 style='margin:0;font-size:1.8rem'>⚙️ Settings</h1>
        <p style='margin:0.3rem 0 0;opacity:0.85'>Configure your local AI stack</p>
    </div>
    """, unsafe_allow_html=True)

    # ── OLLAMA STATUS ──
    st.subheader("🦙 Ollama Status")
    col1, col2 = st.columns(2)

    with col1:
        try:
            r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=3)
            if r.ok:
                st.success(f"✅ Ollama is running at `{OLLAMA_BASE}`")
                models = [m["name"] for m in r.json().get("models", [])]
                if models:
                    st.markdown(f"**Installed models ({len(models)}):**")
                    for m in models:
                        st.code(m, language=None)
                else:
                    st.warning("No models installed. Run: `ollama pull llama3.2`")
            else:
                st.error("❌ Ollama running but returned an error")
        except Exception:
            st.error(f"❌ Cannot connect to Ollama at `{OLLAMA_BASE}`")
            st.markdown("""
            **To start Ollama:**
            ```bash
            ollama serve
            ```
            Then in a new terminal:
            ```bash
            ollama pull llama3.2
            ollama pull nomic-embed-text
            ```
            """)

    with col2:
        st.markdown("**Recommended models:**")
        model_recs = {
            "llama3.2": "Best overall — fast, smart",
            "llama3.1:8b": "Larger, better quality",
            "mistral": "Great for writing tasks",
            "gemma2:2b": "Lightweight, very fast",
            "nomic-embed-text": "Required for RAG embeddings",
        }
        for m, desc in model_recs.items():
            st.markdown(f"- `{m}` — {desc}")

    st.markdown("---")

    # ── MODEL SELECTION ──
    st.subheader("🤖 Active Model")
    models = list_ollama_models()
    if models:
        current = st.session_state.get("ollama_model", models[0])
        idx = models.index(current) if current in models else 0
        selected = st.selectbox("Chat model", models, index=idx)
        if st.button("Set as active model", type="primary"):
            st.session_state.ollama_model = selected
            st.success(f"✅ Active model set to: {selected}")

        embed_models = [m for m in models if "embed" in m.lower() or "nomic" in m.lower()]
        if embed_models:
            st.selectbox("Embedding model", embed_models)
        else:
            st.warning("No embedding model found. Run: `ollama pull nomic-embed-text`")
    else:
        st.warning("No models found. Make sure Ollama is running.")

    st.markdown("---")

    # ── STORAGE INFO ──
    st.subheader("🗄️ Storage")
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**SQLite Database**")
        st.code(DB_PATH)
        conn = get_conn()
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        for t in tables:
            count = conn.execute(f"SELECT COUNT(*) FROM {t[0]}").fetchone()[0]
            st.caption(f"• {t[0]}: {count} rows")
        conn.close()

    with col_b:
        st.markdown("**ChromaDB Vector Store**")
        st.code(CHROMA_PATH)
        try:
            import chromadb
            client = chromadb.PersistentClient(path=CHROMA_PATH)
            cols = client.list_collections()
            for c in cols:
                col_obj = client.get_collection(c.name)
                st.caption(f"• {c.name}: {col_obj.count()} vectors")
        except Exception as e:
            st.caption(f"Could not read ChromaDB: {e}")

    st.markdown("---")

    # ── DANGER ZONE ──
    st.subheader("⚠️ Danger Zone")
    with st.expander("Reset data"):
        col_x, col_y = st.columns(2)
        with col_x:
            if st.button("🗑️ Clear chat history", use_container_width=True):
                conn = get_conn()
                conn.execute("DELETE FROM chat_history")
                conn.commit()
                conn.close()
                st.session_state.chat_messages = []
                st.success("Chat history cleared.")

        with col_y:
            if st.button("🗑️ Clear vector store", use_container_width=True):
                try:
                    import chromadb, shutil
                    shutil.rmtree(CHROMA_PATH, ignore_errors=True)
                    os.makedirs(CHROMA_PATH, exist_ok=True)
                    st.success("Vector store cleared. Restart the app.")
                except Exception as e:
                    st.error(f"Error: {e}")

    st.markdown("---")
    st.subheader("📋 Setup Guide")
    st.markdown("""
    ```bash
    # 1. Install dependencies
    pip install streamlit chromadb requests

    # 2. Install & start Ollama
    # Download from: https://ollama.com
    ollama serve

    # 3. Pull required models (in a new terminal)
    ollama pull llama3.2          # main chat model
    ollama pull nomic-embed-text  # embeddings for RAG

    # 4. Run the app
    streamlit run app.py
    ```
    """)
