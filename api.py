"""
Job Assistant Agent — REST API
Run with: uvicorn api:app --reload --port 8000
Docs at:  http://localhost:8000/docs
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List
import uuid
import json

from utils.db import (
    init_db,
    add_application, get_applications, update_application,
    delete_application, get_application, get_stats,
    save_material, get_materials,
    save_resume_chunk, get_resume_chunks, get_resume_text,
    save_chat, get_chat_history,
)
from utils.llm import (
    ollama_chat, ollama_stream, stream_agent, run_agent,
    upsert_to_vectordb, query_vectordb, list_ollama_models,
    build_rag_context, SYSTEM_PROMPT,
)

# ── Init ───────────────────────────────────────────────────────────────────────

init_db()

app = FastAPI(
    title="Job Assistant Agent API",
    description="Local AI-powered job application assistant — Ollama + ChromaDB + SQLite",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Schemas ────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., description="User message")
    session_id: Optional[str] = Field(None, description="Session ID for conversation history")
    use_rag: bool = Field(True, description="Inject resume/research context via RAG")
    model: Optional[str] = Field(None, description="Ollama model override")

class ChatMessage(BaseModel):
    role: str
    message: str

class CraftRequest(BaseModel):
    type: str = Field(..., description="cover_letter | resume_bullets | cold_email | linkedin_request | follow_up | thank_you")
    job_title: str = Field("", description="Target job title")
    company: str = Field("", description="Target company")
    job_description: Optional[str] = Field("", description="Job description text")
    background: Optional[str] = Field("", description="Your background/experience")
    model: Optional[str] = None

class RefineRequest(BaseModel):
    original: str = Field(..., description="The original generated text")
    feedback: str = Field(..., description="Your refinement feedback")
    type: str = Field("", description="Material type for context")
    model: Optional[str] = None

class ResearchRequest(BaseModel):
    company: str = Field("", description="Company to research")
    job_title: str = Field("", description="Role to research")
    topic: str = Field(..., description="company_overview | salary | interview_prep | questions_to_ask | industry_trends | keywords")
    save_to_kb: bool = Field(True, description="Save results to vector knowledge base")
    model: Optional[str] = None

class ApplicationCreate(BaseModel):
    job_title: str
    company: str
    location: Optional[str] = ""
    job_url: Optional[str] = ""
    job_description: Optional[str] = ""
    status: Optional[str] = "applied"
    notes: Optional[str] = ""
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    applied_date: Optional[str] = None

class ApplicationUpdate(BaseModel):
    job_title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    job_url: Optional[str] = None
    job_description: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None

class ResumeSection(BaseModel):
    section: str = Field(..., description="Section name e.g. 'Work Experience'")
    content: str = Field(..., description="Section content")

class VectorQuery(BaseModel):
    query: str
    n_results: int = Field(5, ge=1, le=20)
    collection: str = Field("resume_knowledge")


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "app": "Job Assistant Agent API", "version": "1.0.0"}


@app.get("/health", tags=["Health"])
def health():
    import requests as req
    try:
        r = req.get("http://localhost:11434/api/tags", timeout=3)
        ollama_ok = r.ok
        models = [m["name"] for m in r.json().get("models", [])] if r.ok else []
    except Exception:
        ollama_ok = False
        models = []

    return {
        "ollama": "connected" if ollama_ok else "disconnected",
        "models_available": models,
        "sqlite": "ok",
        "chromadb": "ok",
    }


# ── Models ─────────────────────────────────────────────────────────────────────

@app.get("/models", tags=["Models"])
def get_models():
    """List all available Ollama models."""
    return {"models": list_ollama_models()}


# ── Chat Agent ─────────────────────────────────────────────────────────────────

@app.post("/chat", tags=["Agent"])
def chat(req: ChatRequest):
    """
    Send a message to the AI job agent.
    Returns a complete response (non-streaming).
    """
    session_id = req.session_id or str(uuid.uuid4())
    history = get_chat_history(session_id, limit=20)

    if req.model:
        import streamlit as st
        # model override via header
        pass

    response = run_agent(req.message, history, use_rag=req.use_rag)

    save_chat(session_id, "user", req.message)
    save_chat(session_id, "assistant", response)

    return {
        "session_id": session_id,
        "response": response,
        "rag_used": req.use_rag,
    }


@app.post("/chat/stream", tags=["Agent"])
def chat_stream(req: ChatRequest):
    """
    Stream the agent's response token by token (SSE).
    Use with EventSource or fetch with stream: true.
    """
    session_id = req.session_id or str(uuid.uuid4())
    history = get_chat_history(session_id, limit=20)

    context = build_rag_context(req.message) if req.use_rag else ""
    system = SYSTEM_PROMPT + (f"\n\n{context}" if context else "")

    messages = [{"role": "system", "content": system}]
    for h in history[-10:]:
        messages.append({"role": h["role"], "content": h["message"]})
    messages.append({"role": "user", "content": req.message})

    full_response = []

    def generate():
        for chunk in ollama_stream(messages, model=req.model):
            full_response.append(chunk)
            yield f"data: {json.dumps({'chunk': chunk, 'session_id': session_id})}\n\n"
        # Save after stream completes
        save_chat(session_id, "user", req.message)
        save_chat(session_id, "assistant", "".join(full_response))
        yield f"data: {json.dumps({'done': True, 'session_id': session_id})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/chat/history/{session_id}", tags=["Agent"])
def get_history(session_id: str, limit: int = 20):
    """Get conversation history for a session."""
    history = get_chat_history(session_id, limit=limit)
    return {"session_id": session_id, "messages": history}


@app.delete("/chat/history/{session_id}", tags=["Agent"])
def clear_history(session_id: str):
    """Clear conversation history for a session."""
    from utils.db import get_conn
    conn = get_conn()
    conn.execute("DELETE FROM chat_history WHERE session_id=?", (session_id,))
    conn.commit()
    conn.close()
    return {"message": f"History cleared for session {session_id}"}


# ── Craft Materials ────────────────────────────────────────────────────────────

CRAFT_PROMPTS = {
    "cover_letter": "Write a compelling, tailored 3-paragraph cover letter (no placeholders, ready to send).\n\nRole: {job_title} at {company}\nJob Description: {jd}\nBackground: {bg}",
    "resume_bullets": "Write 5 strong resume bullet points using STAR method with action verbs and metrics.\n\nRole: {job_title} at {company}\nJob Description: {jd}\nBackground: {bg}",
    "cold_email": "Write a short genuine cold email (under 150 words) to the hiring manager at {company} for {job_title}.\nBackground: {bg}",
    "linkedin_request": "Write a LinkedIn connection request (under 60 words) to someone at {company} re: {job_title}.\nBackground: {bg}",
    "follow_up": "Write a polite follow-up email for {job_title} at {company} after applying with no response.",
    "thank_you": "Write a warm thank-you email after an interview for {job_title} at {company}. Under 150 words.",
}


@app.post("/craft", tags=["Craft"])
def craft_material(req: CraftRequest):
    """
    Generate a job application material.
    Types: cover_letter, resume_bullets, cold_email, linkedin_request, follow_up, thank_you
    """
    if req.type not in CRAFT_PROMPTS:
        raise HTTPException(400, f"Invalid type. Choose: {list(CRAFT_PROMPTS.keys())}")

    # Use resume from vault if no background provided
    background = req.background
    if not background:
        background = get_resume_text()

    prompt = CRAFT_PROMPTS[req.type].format(
        job_title=req.job_title or "this role",
        company=req.company or "the company",
        jd=req.job_description or "Not provided",
        bg=background or "Not provided",
    )

    messages = [
        {"role": "system", "content": "You are an expert career coach and professional writer. Produce high-quality, ready-to-use job application materials. Be specific and concise. No filler."},
        {"role": "user", "content": prompt},
    ]

    result = ollama_chat(messages, model=req.model)
    return {
        "type": req.type,
        "job_title": req.job_title,
        "company": req.company,
        "content": result,
    }


@app.post("/craft/refine", tags=["Craft"])
def refine_material(req: RefineRequest):
    """Refine a previously generated material based on feedback."""
    messages = [
        {"role": "system", "content": "You are an expert career writer."},
        {"role": "user", "content": f"Here is a {req.type} I generated:\n\n{req.original}"},
        {"role": "assistant", "content": "I've reviewed this material."},
        {"role": "user", "content": f"Please revise it based on this feedback: {req.feedback}"},
    ]
    result = ollama_chat(messages, model=req.model)
    return {"refined_content": result, "feedback_applied": req.feedback}


# ── Research ───────────────────────────────────────────────────────────────────

RESEARCH_PROMPTS = {
    "company_overview": "Give a comprehensive overview of {company}: mission, products, culture, recent news, and what a job candidate should know.",
    "salary": "What is the typical compensation for a {job_title} at {company}? Include base, bonus, equity ranges and total comp.",
    "interview_prep": "Comprehensive interview prep guide for {job_title} at {company}. Behavioral, technical, and culture-fit questions with tips.",
    "questions_to_ask": "Generate 10 smart questions to ask during an interview for {job_title} at {company}. Explain why each is valuable.",
    "industry_trends": "What are the key trends in the industry where {company} operates, relevant to a {job_title}?",
    "keywords": "What ATS keywords and skills should a {job_title} at {company} include in their resume and LinkedIn?",
}


@app.post("/research", tags=["Research"])
def research(req: ResearchRequest):
    """Research a company or role. Results are optionally saved to the vector KB."""
    if req.topic not in RESEARCH_PROMPTS:
        raise HTTPException(400, f"Invalid topic. Choose: {list(RESEARCH_PROMPTS.keys())}")

    prompt = RESEARCH_PROMPTS[req.topic].format(
        company=req.company or "the company",
        job_title=req.job_title or "this role",
    )

    messages = [
        {"role": "system", "content": "You are an expert career researcher. Give detailed, practical, accurate insights. Use structured formatting."},
        {"role": "user", "content": prompt},
    ]

    result = ollama_chat(messages, model=req.model)

    if req.save_to_kb:
        doc_id = f"research_{req.topic}_{req.company}_{req.job_title}".replace(" ", "_").lower()
        upsert_to_vectordb(
            doc_id=doc_id,
            text=f"Research — {req.topic} for {req.job_title} at {req.company}:\n{result}",
            metadata={"type": "research", "company": req.company, "role": req.job_title, "topic": req.topic},
        )

    return {
        "topic": req.topic,
        "company": req.company,
        "job_title": req.job_title,
        "content": result,
        "saved_to_kb": req.save_to_kb,
    }


# ── Applications ───────────────────────────────────────────────────────────────

@app.get("/applications", tags=["Tracker"])
def list_applications(status: Optional[str] = None):
    """List all job applications, optionally filtered by status."""
    return {"applications": get_applications(status)}


@app.post("/applications", tags=["Tracker"])
def create_application(app_data: ApplicationCreate):
    """Add a new job application."""
    app_id = add_application(**app_data.dict())
    return {"id": app_id, "message": "Application added", **app_data.dict()}


@app.get("/applications/{app_id}", tags=["Tracker"])
def get_app(app_id: int):
    """Get a single application by ID."""
    app = get_application(app_id)
    if not app:
        raise HTTPException(404, "Application not found")
    return app


@app.patch("/applications/{app_id}", tags=["Tracker"])
def update_app(app_id: int, updates: ApplicationUpdate):
    """Update fields of an application."""
    if not get_application(app_id):
        raise HTTPException(404, "Application not found")
    data = {k: v for k, v in updates.dict().items() if v is not None}
    if data:
        update_application(app_id, **data)
    return {"message": "Updated", "id": app_id, "updates": data}


@app.delete("/applications/{app_id}", tags=["Tracker"])
def delete_app(app_id: int):
    """Delete an application and its materials."""
    if not get_application(app_id):
        raise HTTPException(404, "Application not found")
    delete_application(app_id)
    return {"message": "Deleted", "id": app_id}


@app.get("/applications/{app_id}/materials", tags=["Tracker"])
def get_app_materials(app_id: int):
    """Get all saved materials for an application."""
    return {"materials": get_materials(app_id)}


@app.post("/applications/{app_id}/materials", tags=["Tracker"])
def add_material(app_id: int, material_type: str, content: str):
    """Save a material to an application."""
    if not get_application(app_id):
        raise HTTPException(404, "Application not found")
    save_material(app_id, material_type, content)
    return {"message": "Material saved"}


@app.get("/stats", tags=["Tracker"])
def pipeline_stats():
    """Get pipeline summary statistics."""
    return get_stats()


# ── Resume Vault ───────────────────────────────────────────────────────────────

@app.get("/resume", tags=["Resume"])
def get_resume():
    """Get the full resume as text."""
    return {"resume": get_resume_text(), "sections": get_resume_chunks()}


@app.post("/resume/section", tags=["Resume"])
def upsert_resume_section(section: ResumeSection):
    """Add or update a resume section (also vectorizes it)."""
    save_resume_chunk(section.section, section.content)
    doc_id = f"resume_{section.section}".replace(" ", "_").lower()
    upsert_to_vectordb(
        doc_id=doc_id,
        text=f"Resume — {section.section}:\n{section.content}",
        metadata={"type": "resume", "section": section.section},
    )
    return {"message": f"Section '{section.section}' saved and indexed"}


@app.delete("/resume/section/{section_name}", tags=["Resume"])
def delete_resume_section(section_name: str):
    """Delete a resume section."""
    from utils.db import get_conn
    from utils.llm import delete_from_vectordb
    conn = get_conn()
    conn.execute("DELETE FROM resume_chunks WHERE section=?", (section_name,))
    conn.commit()
    conn.close()
    doc_id = f"resume_{section_name}".replace(" ", "_").lower()
    delete_from_vectordb(doc_id)
    return {"message": f"Section '{section_name}' deleted"}


# ── Vector Knowledge Base ──────────────────────────────────────────────────────

@app.post("/kb/query", tags=["Knowledge Base"])
def query_kb(req: VectorQuery):
    """Semantic search the vector knowledge base."""
    results = query_vectordb(req.query, n_results=req.n_results, collection=req.collection)
    return {"query": req.query, "results": results}


@app.post("/kb/upsert", tags=["Knowledge Base"])
def upsert_kb(doc_id: str, text: str, metadata: dict = {}):
    """Manually add a document to the vector knowledge base."""
    upsert_to_vectordb(doc_id=doc_id, text=text, metadata=metadata)
    return {"message": f"Document '{doc_id}' added to KB"}
