import streamlit as st
from utils.db import save_resume_chunk, get_resume_chunks, get_resume_text
from utils.llm import upsert_to_vectordb, delete_from_vectordb

DEFAULT_SECTIONS = [
    "Summary / Objective",
    "Work Experience",
    "Education",
    "Skills & Technologies",
    "Projects",
    "Certifications",
    "Achievements & Awards",
]


def render():
    st.markdown("""
    <div class="main-header">
        <h1 style='margin:0;font-size:1.8rem'>📄 Resume Vault</h1>
        <p style='margin:0.3rem 0 0;opacity:0.85'>Store your resume — the AI agent will use it for context automatically</p>
    </div>
    """, unsafe_allow_html=True)

    chunks = get_resume_chunks()
    existing = {c["section"]: c["content"] for c in chunks}

    st.info("💡 Your resume is stored in **SQLite** and indexed in **ChromaDB** so the AI can semantically search it when crafting your materials.")

    tab1, tab2 = st.tabs(["✏️ Edit Resume", "👁️ Preview & Export"])

    with tab1:
        col1, col2 = st.columns([1, 1])

        with col1:
            st.subheader("Add / Edit Section")

            # Section selector
            all_sections = DEFAULT_SECTIONS + [c for c in existing.keys() if c not in DEFAULT_SECTIONS]
            section_choice = st.selectbox("Select section", all_sections + ["+ Custom section"])

            if section_choice == "+ Custom section":
                section_name = st.text_input("Section name", placeholder="e.g. Publications")
            else:
                section_name = section_choice

            content = st.text_area(
                "Content",
                value=existing.get(section_name, ""),
                height=280,
                placeholder=f"Enter your {section_name} here…"
            )

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("💾 Save section", type="primary", use_container_width=True):
                    if section_name and content:
                        save_resume_chunk(section_name, content)
                        # Vectorize
                        doc_id = f"resume_{section_name}".replace(" ", "_").lower()
                        upsert_to_vectordb(
                            doc_id=doc_id,
                            text=f"Resume section — {section_name}:\n{content}",
                            metadata={"type": "resume", "section": section_name},
                            collection="resume_knowledge"
                        )
                        st.success(f"✅ Saved & indexed: {section_name}")
                        st.rerun()
                    else:
                        st.warning("Section name and content are required.")

            with col_b:
                if section_name in existing:
                    if st.button("🗑️ Delete section", use_container_width=True):
                        # Remove from SQLite
                        from utils.db import get_conn
                        conn = get_conn()
                        conn.execute("DELETE FROM resume_chunks WHERE section=?", (section_name,))
                        conn.commit()
                        conn.close()
                        # Remove from vector DB
                        doc_id = f"resume_{section_name}".replace(" ", "_").lower()
                        delete_from_vectordb(doc_id)
                        st.success(f"Deleted: {section_name}")
                        st.rerun()

        with col2:
            st.subheader("Paste full resume (auto-split)")
            st.caption("Paste your entire resume and we'll try to split it into sections automatically.")
            full_resume = st.text_area("Full resume text", height=300,
                                       placeholder="Paste your resume here and click Import…")
            if st.button("📥 Import & split", use_container_width=True) and full_resume:
                with st.spinner("Parsing your resume with llama3.2…"):
                    from utils.llm import ollama_chat
                    import json, re

                    # Always use llama3.2 for text tasks — never the embed model
                    messages = [
                        {"role": "system", "content": (
                            "You are a resume parser. Your only job is to split a resume into sections and return valid JSON. "
                            "Return ONLY a raw JSON object — no markdown, no code fences, no explanation, no extra text. "
                            "Keys should be section names like 'Summary', 'Work Experience', 'Education', 'Skills', 'Projects'. "
                            "Values should be the full text content of each section as a string."
                        )},
                        {"role": "user", "content": f"Parse this resume into a JSON object with section names as keys:\n\n{full_resume}"}
                    ]
                    raw = ollama_chat(messages, model="llama3.2")

                    if raw.startswith("❌"):
                        st.error(raw)
                    else:
                        try:
                            # Strip markdown code fences if model added them
                            cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
                            # Extract first JSON object found
                            match = re.search(r'\{.*\}', cleaned, re.DOTALL)
                            if match:
                                parsed = json.loads(match.group())
                                def flatten(val):
                                    """Recursively flatten any value to a plain string."""
                                    if isinstance(val, str):
                                        return val.strip()
                                    elif isinstance(val, list):
                                        return "\n".join(flatten(v) for v in val)
                                    elif isinstance(val, dict):
                                        parts = []
                                        for k, v in val.items():
                                            parts.append(f"{k}:\n{flatten(v)}")
                                        return "\n\n".join(parts)
                                    else:
                                        return str(val).strip()

                                count = 0
                                for sec, cont in parsed.items():
                                    text = flatten(cont)
                                    if text:
                                        save_resume_chunk(str(sec), text)
                                        doc_id = f"resume_{sec}".replace(" ", "_").lower()
                                        upsert_to_vectordb(
                                            doc_id=doc_id,
                                            text=f"Resume section — {sec}:\n{text}",
                                            metadata={"type": "resume", "section": str(sec)},
                                            collection="resume_knowledge"
                                        )
                                        count += 1
                                if count > 0:
                                    st.success(f"✅ Imported {count} sections successfully!")
                                    st.rerun()
                                else:
                                    st.error("Parsed but no sections found. Try adding sections manually.")
                            else:
                                st.error("Could not find JSON in the response.")
                                with st.expander("See raw model output"):
                                    st.text(raw)
                        except json.JSONDecodeError as e:
                            st.error(f"JSON parse error: {e}")
                            with st.expander("See raw model output (copy and fix manually)"):
                                st.text(raw)

    with tab2:
        resume_text = get_resume_text()
        if resume_text:
            st.subheader("Your Resume")
            st.markdown(resume_text)
            st.markdown("---")
            col_x, col_y = st.columns(2)
            with col_x:
                st.download_button(
                    "⬇️ Download as .txt",
                    data=resume_text,
                    file_name="my_resume.txt",
                    mime="text/plain",
                    use_container_width=True
                )
            with col_y:
                st.markdown("**Sections stored:**")
                chunks = get_resume_chunks()
                for c in chunks:
                    st.caption(f"✅ {c['section']}")
        else:
            st.info("No resume sections saved yet. Go to the Edit Resume tab to add your content.")
