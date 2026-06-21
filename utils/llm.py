import requests
import json
import os
import chromadb
from chromadb.utils import embedding_functions
import streamlit as st

OLLAMA_BASE = os.getenv("OLLAMA_HOST", "http://localhost:11434")
CHROMA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "chroma")
os.makedirs(CHROMA_PATH, exist_ok=True)


# ─── Ollama ────────────────────────────────────────────────────────────────────

def get_model():
    return st.session_state.get("ollama_model", "llama3.2")


def list_ollama_models():
    try:
        r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=5)
        if r.ok:
            return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        pass
    return []


def ollama_chat(messages: list, model: str = None, stream: bool = False) -> str:
    model = model or get_model()
    payload = {"model": model, "messages": messages, "stream": stream}
    try:
        r = requests.post(
            f"{OLLAMA_BASE}/api/chat",
            json=payload,
            timeout=120,
            stream=stream
        )
        r.raise_for_status()
        if stream:
            return r  # caller handles streaming
        return r.json()["message"]["content"]
    except requests.exceptions.ConnectionError:
        return "❌ Cannot connect to Ollama. Make sure it's running: `ollama serve`"
    except Exception as e:
        return f"❌ Ollama error: {e}"


def ollama_stream(messages: list, model: str = None):
    """Yields text chunks for streaming output."""
    model = model or get_model()
    payload = {"model": model, "messages": messages, "stream": True}
    try:
        r = requests.post(
            f"{OLLAMA_BASE}/api/chat",
            json=payload,
            timeout=120,
            stream=True
        )
        r.raise_for_status()
        for line in r.iter_lines():
            if line:
                chunk = json.loads(line)
                if "message" in chunk and "content" in chunk["message"]:
                    yield chunk["message"]["content"]
                if chunk.get("done"):
                    break
    except requests.exceptions.ConnectionError:
        yield "❌ Cannot connect to Ollama. Make sure it's running: `ollama serve`"
    except Exception as e:
        yield f"❌ Error: {e}"


def ollama_embed(text: str, model: str = "nomic-embed-text") -> list:
    try:
        r = requests.post(
            f"{OLLAMA_BASE}/api/embeddings",
            json={"model": model, "prompt": text},
            timeout=30
        )
        r.raise_for_status()
        return r.json()["embedding"]
    except Exception:
        return []


# ─── ChromaDB Vector Store ─────────────────────────────────────────────────────

_chroma_client = None

def get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    return _chroma_client


def get_collection(name: str = "resume_knowledge"):
    client = get_chroma_client()
    # Use Ollama embeddings via custom function
    ef = OllamaEmbeddingFunction()
    return client.get_or_create_collection(name=name, embedding_function=ef)


class OllamaEmbeddingFunction(embedding_functions.EmbeddingFunction):
    def __call__(self, input):
        embeddings = []
        for text in input:
            emb = ollama_embed(text)
            if not emb:
                # Fallback: zero vector of dim 768
                emb = [0.0] * 768
            embeddings.append(emb)
        return embeddings


def upsert_to_vectordb(doc_id: str, text: str, metadata: dict = None, collection: str = "resume_knowledge"):
    col = get_collection(collection)
    col.upsert(
        ids=[doc_id],
        documents=[text],
        metadatas=[metadata or {}]
    )


def query_vectordb(query: str, n_results: int = 5, collection: str = "resume_knowledge") -> list:
    col = get_collection(collection)
    try:
        count = col.count()
        if count == 0:
            return []
        n = min(n_results, count)
        results = col.query(query_texts=[query], n_results=n)
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        return [{"text": d, "meta": m} for d, m in zip(docs, metas)]
    except Exception as e:
        return []


def delete_from_vectordb(doc_id: str, collection: str = "resume_knowledge"):
    col = get_collection(collection)
    try:
        col.delete(ids=[doc_id])
    except Exception:
        pass


# ─── Agent Prompts ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are JobBot, an expert AI job application assistant. You help users:
- Write compelling cover letters tailored to job descriptions
- Craft strong resume bullet points using the STAR method
- Prepare for interviews with common questions and strategies
- Research companies and roles
- Write cold outreach emails and LinkedIn messages
- Track and strategize their job search

You have access to the user's resume and past applications as context.
Be specific, practical, and encouraging. Format your responses clearly with headers and bullet points when helpful.
When writing materials (cover letters, emails), produce the full ready-to-use text."""


def build_rag_context(query: str) -> str:
    """Retrieve relevant resume/job context from vector DB."""
    results = query_vectordb(query, n_results=4)
    if not results:
        return ""
    context_parts = ["📚 Relevant context from your resume/knowledge base:"]
    for r in results:
        context_parts.append(f"- {r['text'][:300]}")
    return "\n".join(context_parts)


def run_agent(user_message: str, history: list, use_rag: bool = True) -> str:
    """Full agent call with RAG context injection."""
    context = build_rag_context(user_message) if use_rag else ""

    system = SYSTEM_PROMPT
    if context:
        system += f"\n\n{context}"

    messages = [{"role": "system", "content": system}]
    for h in history[-10:]:  # last 10 turns
        messages.append({"role": h["role"], "content": h["message"]})
    messages.append({"role": "user", "content": user_message})

    return ollama_chat(messages)


def stream_agent(user_message: str, history: list, use_rag: bool = True):
    """Stream agent response."""
    context = build_rag_context(user_message) if use_rag else ""

    system = SYSTEM_PROMPT
    if context:
        system += f"\n\n{context}"

    messages = [{"role": "system", "content": system}]
    for h in history[-10:]:
        messages.append({"role": h["role"], "content": h["message"]})
    messages.append({"role": "user", "content": user_message})

    return ollama_stream(messages)
