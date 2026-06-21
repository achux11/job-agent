import streamlit as st
import uuid
from utils.llm import stream_agent, list_ollama_models, get_model
from utils.db import save_chat, get_chat_history

QUICK_PROMPTS = [
    "✉️ Write a cover letter for this job",
    "📄 Tailor my resume bullets to this JD",
    "🎯 Give me 10 interview questions for a PM role",
    "📬 Write a cold email to a hiring manager",
    "💼 Write a LinkedIn connection request",
    "💰 How do I negotiate salary?",
    "🔍 How should I research a company before interview?",
    "📊 Review my job search strategy",
]


def render():
    st.markdown("""
    <div class="main-header">
        <h1 style='margin:0;font-size:1.8rem'>🤖 Job Assistant Agent</h1>
        <p style='margin:0.3rem 0 0;opacity:0.85'>Your AI-powered career coach — powered by Ollama + RAG</p>
    </div>
    """, unsafe_allow_html=True)

    # Session init
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    session_id = st.session_state.session_id

    # Top controls
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        models = list_ollama_models()
        # Filter out embedding-only models — they can't do chat
        chat_models = [m for m in models if "embed" not in m.lower()]
        if chat_models:
            current = st.session_state.get("ollama_model", "")
            if current not in chat_models:
                current = chat_models[0]
                st.session_state.ollama_model = current
            idx = chat_models.index(current)
            model = st.selectbox("Model", chat_models, index=idx, label_visibility="collapsed")
            st.session_state.ollama_model = model
        elif models:
            st.warning("⚠️ Only embedding models found. Run: `ollama pull llama3.2`")
        else:
            st.warning("⚠️ No Ollama models found. Run: `ollama pull llama3.2`")

    with col2:
        use_rag = st.toggle("RAG context", value=True, help="Inject your resume/knowledge into prompts")

    with col3:
        if st.button("🗑️ Clear chat", use_container_width=True):
            st.session_state.chat_messages = []
            st.session_state.session_id = str(uuid.uuid4())
            st.rerun()

    st.markdown("---")

    # Quick prompts
    st.markdown("**Quick actions:**")
    cols = st.columns(4)
    for i, qp in enumerate(QUICK_PROMPTS):
        if cols[i % 4].button(qp, use_container_width=True, key=f"qp_{i}"):
            st.session_state.pending_prompt = qp
            st.rerun()

    st.markdown("---")

    # Chat history display
    chat_container = st.container()
    with chat_container:
        if not st.session_state.chat_messages:
            st.info("👋 Ask me anything about your job search! I can write cover letters, prep you for interviews, research companies, and more.")
        else:
            for msg in st.session_state.chat_messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

    # Input
    prompt = st.chat_input("Ask your job agent anything…")

    # Handle quick prompt injection
    if "pending_prompt" in st.session_state:
        prompt = st.session_state.pop("pending_prompt")

    if prompt:
        # Add user message
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        save_chat(session_id, "user", prompt)

        with st.chat_message("user"):
            st.markdown(prompt)

        # Stream agent response
        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            full_response = ""

            history = [{"role": m["role"], "message": m["content"]}
                       for m in st.session_state.chat_messages[:-1]]

            try:
                for chunk in stream_agent(prompt, history, use_rag=use_rag):
                    full_response += chunk
                    response_placeholder.markdown(full_response + "▌")
                response_placeholder.markdown(full_response)
            except Exception as e:
                full_response = f"❌ Error: {e}"
                response_placeholder.markdown(full_response)

        st.session_state.chat_messages.append({"role": "assistant", "content": full_response})
        save_chat(session_id, "assistant", full_response)

    # Job description context panel
    with st.expander("📋 Paste job description for context", expanded=False):
        st.info("Paste a job description here and it will be included in your next message automatically.")
        jd = st.text_area("Job description", height=150, key="jd_context",
                           placeholder="Paste the full job posting here…")
        if st.button("📌 Attach to next message") and jd:
            st.session_state.pending_prompt = f"Here's the job description I'm targeting:\n\n{jd}\n\nPlease help me tailor my application."
            st.success("Job description attached! Send a message to use it.")
