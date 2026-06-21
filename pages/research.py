import streamlit as st
from utils.llm import ollama_chat, upsert_to_vectordb


RESEARCH_PROMPTS = {
    "🏢 Company Overview": {
        "key": "company_overview",
        "prompt": "Provide a comprehensive overview of {company}: their mission, products/services, culture, recent news, growth trajectory, and what makes them unique. What should a job candidate know?",
    },
    "💰 Salary Benchmark": {
        "key": "salary",
        "prompt": "What is the typical compensation for a {job_title} role at {company} or similar companies? Break down: base salary range, bonus, equity/RSUs, total comp. Include levels if relevant (e.g. L4, L5 at big tech).",
    },
    "🎯 Interview Prep": {
        "key": "interview_prep",
        "prompt": "Give me a comprehensive interview prep guide for a {job_title} role at {company}. Include: behavioral questions (with STAR tips), technical/skills questions, culture-fit questions, and what interviewers typically look for.",
    },
    "❓ Questions to Ask": {
        "key": "questions_to_ask",
        "prompt": "Generate 10 smart, thoughtful questions I should ask during an interview for {job_title} at {company}. Mix strategic, culture, growth, and role-specific questions. Explain WHY each question is good to ask.",
    },
    "📈 Industry Trends": {
        "key": "industry_trends",
        "prompt": "What are the current trends, challenges, and opportunities in the industry where {company} operates, relevant to a {job_title} role? What should I know to sound informed in an interview?",
    },
    "🔑 Keywords & Skills": {
        "key": "keywords",
        "prompt": "For a {job_title} role, what are the most important keywords, skills, and buzzwords I should include in my resume and LinkedIn profile to pass ATS screening and impress hiring managers?",
    },
}


def render():
    st.markdown("""
    <div class="main-header">
        <h1 style='margin:0;font-size:1.8rem'>🔍 Job Research</h1>
        <p style='margin:0.3rem 0 0;opacity:0.85'>Deep research on companies, salaries, and interview strategies</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Research Target")
        company = st.text_input("Company", placeholder="e.g. Stripe")
        job_title = st.text_input("Role / Job title", placeholder="e.g. Senior Product Manager")

        st.markdown("---")
        st.subheader("Research Type")
        selected = st.radio("What to research", list(RESEARCH_PROMPTS.keys()))

        run = st.button("🔍 Research", type="primary", use_container_width=True)

        st.markdown("---")
        st.info("💡 **Tip:** Research results are saved to your vector knowledge base so the AI agent can reference them later.")

    with col2:
        if "research_output" not in st.session_state:
            st.session_state.research_output = ""
        if "research_topic" not in st.session_state:
            st.session_state.research_topic = ""

        if run:
            if not company and not job_title:
                st.warning("Enter a company or job title to research.")
            else:
                cfg = RESEARCH_PROMPTS[selected]
                prompt = cfg["prompt"].format(
                    company=company or "the target company",
                    job_title=job_title or "this role"
                )
                with st.spinner(f"Researching {company or job_title}…"):
                    messages = [
                        {"role": "system", "content": "You are an expert career researcher and industry analyst. Provide detailed, practical, and accurate insights to help job seekers. Use structured formatting with headers and bullet points."},
                        {"role": "user", "content": prompt}
                    ]
                    result = ollama_chat(messages)
                    st.session_state.research_output = result
                    st.session_state.research_topic = f"{selected} — {company} {job_title}"

                    # Auto-save to vector DB
                    doc_id = f"research_{cfg['key']}_{company}_{job_title}".replace(" ", "_").lower()
                    upsert_to_vectordb(
                        doc_id=doc_id,
                        text=f"{selected} for {job_title} at {company}:\n{result}",
                        metadata={"type": "research", "company": company, "role": job_title, "topic": cfg["key"]},
                        collection="resume_knowledge"
                    )
                    st.success("✅ Research saved to knowledge base for AI context")

        if st.session_state.research_output:
            st.subheader(st.session_state.research_topic)
            st.markdown(st.session_state.research_output)

            st.markdown("---")
            col_a, col_b = st.columns(2)
            with col_a:
                st.download_button(
                    "⬇️ Download research",
                    data=st.session_state.research_output,
                    file_name=f"research_{company}_{job_title}.txt".replace(" ", "_"),
                    mime="text/plain", use_container_width=True
                )
            with col_b:
                follow_up = st.text_input("Ask a follow-up question")
                if st.button("Ask", use_container_width=True) and follow_up:
                    with st.spinner("Thinking…"):
                        messages = [
                            {"role": "system", "content": "You are an expert career researcher."},
                            {"role": "user", "content": f"Research context:\n{st.session_state.research_output}"},
                            {"role": "assistant", "content": "I've analyzed this information."},
                            {"role": "user", "content": follow_up}
                        ]
                        extra = ollama_chat(messages)
                    st.markdown("**Follow-up answer:**")
                    st.markdown(extra)
        else:
            st.markdown("""
            ### How to use Research
            1. Enter a **company name** and/or **job title** on the left
            2. Choose a research type
            3. Click **Research**

            The results will be stored in your **vector knowledge base** so the AI chat agent can reference them when answering questions about your job search.

            ---
            **Available research types:**
            - 🏢 Company culture, mission, recent news
            - 💰 Salary benchmarks and total comp
            - 🎯 Interview question prep
            - ❓ Smart questions to ask interviewers
            - 📈 Industry trends and context
            - 🔑 ATS keywords and must-have skills
            """)
