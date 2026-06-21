import streamlit as st
from utils.llm import ollama_chat, get_model
from utils.db import get_resume_text, save_material, get_applications


def build_prompt(task, job_title, company, jd, background):
    prompts = {
        "cover_letter": f"""Write a compelling, tailored 3-paragraph cover letter.

Role: {job_title} at {company}
Job Description: {jd or 'Not provided'}
My Background: {background or 'Not provided'}

Write the complete letter ready to send. No placeholders. Be specific about why this role and company.""",

        "resume_bullets": f"""Create 5 strong resume bullet points tailored to this job using the STAR method.
Use strong action verbs. Include metrics where possible.

Role: {job_title} at {company}
Job Description: {jd or 'Not provided'}
My Background: {background or 'Not provided'}

Output ONLY the 5 bullet points, each starting with •""",

        "cold_email": f"""Write a short, genuine cold outreach email (under 150 words) to the hiring manager at {company} for the {job_title} role.
Subject line + body. Make it human, not template-like.

My Background: {background or 'Not provided'}""",

        "linkedin_request": f"""Write a LinkedIn connection request (under 60 words) to someone at {company}.
Sound natural and specific. Mention the {job_title} role.

My Background: {background or 'Not provided'}""",

        "follow_up": f"""Write a polite follow-up email for the {job_title} role at {company}.
I applied [X days] ago and haven't heard back. Keep it brief and professional.""",

        "thank_you": f"""Write a thank-you email to send after an interview for {job_title} at {company}.
Warm, specific, and under 150 words.""",
    }
    return prompts.get(task, "")


def render():
    st.markdown("""
    <div class="main-header">
        <h1 style='margin:0;font-size:1.8rem'>📝 Craft Application Materials</h1>
        <p style='margin:0.3rem 0 0;opacity:0.85'>Generate tailored cover letters, resume bullets, emails & more</p>
    </div>
    """, unsafe_allow_html=True)

    # Pull resume if available
    resume_text = get_resume_text()

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Job Details")
        job_title = st.text_input("Job title", placeholder="e.g. Senior Product Manager")
        company = st.text_input("Company", placeholder="e.g. Stripe")
        jd = st.text_area("Job description", height=200,
                           placeholder="Paste the job posting or key requirements…")

        st.subheader("Your Background")
        if resume_text:
            st.success("✅ Resume loaded from vault — will be used automatically")
            background = resume_text
            show_bg = st.text_area("Additional notes (optional)", height=80,
                                   placeholder="Any extra context for this specific role…")
            if show_bg:
                background = resume_text + "\n\nAdditional notes: " + show_bg
        else:
            background = st.text_area("Background / highlights",
                                      height=120,
                                      placeholder="e.g. 5 years in fintech, led 3 product launches, MBA…\n\nTip: Add your resume in the Resume Vault for automatic context!")

        # Optional: link to existing application
        apps = get_applications()
        if apps:
            st.markdown("**Link to application (optional)**")
            app_options = {"None": None}
            app_options.update({f"{a['job_title']} @ {a['company']}": a["id"] for a in apps})
            linked_app = st.selectbox("Save output to application", list(app_options.keys()))
            linked_app_id = app_options[linked_app]
        else:
            linked_app_id = None

    with col2:
        st.subheader("Choose what to generate")

        tasks = {
            "✉️ Cover Letter": "cover_letter",
            "📄 Resume Bullets": "resume_bullets",
            "📬 Cold Outreach Email": "cold_email",
            "💼 LinkedIn Request": "linkedin_request",
            "🔔 Follow-Up Email": "follow_up",
            "🙏 Thank You Email": "thank_you",
        }

        selected_task = st.radio("Material type", list(tasks.keys()))
        task_key = tasks[selected_task]

        generate = st.button("⚡ Generate", type="primary", use_container_width=True)

        if "craft_output" not in st.session_state:
            st.session_state.craft_output = ""
        if "craft_task" not in st.session_state:
            st.session_state.craft_task = ""

        if generate:
            if not job_title and not company:
                st.warning("Please enter at least a job title or company.")
            else:
                prompt_text = build_prompt(task_key, job_title, company, jd, background)
                with st.spinner("✍️ Generating…"):
                    messages = [
                        {"role": "system", "content": "You are an expert career coach and professional writer. Produce high-quality, ready-to-use job application materials. Be specific, confident, and concise. No generic filler."},
                        {"role": "user", "content": prompt_text}
                    ]
                    result = ollama_chat(messages)
                    st.session_state.craft_output = result
                    st.session_state.craft_task = task_key

        if st.session_state.craft_output:
            st.markdown("---")
            st.subheader("Generated Output")
            output = st.text_area("", value=st.session_state.craft_output,
                                  height=400, key="output_area")

            btn1, btn2, btn3 = st.columns(3)
            with btn1:
                st.download_button("⬇️ Download", data=output,
                                   file_name=f"{task_key}_{company or 'output'}.txt",
                                   mime="text/plain", use_container_width=True)
            with btn2:
                if st.button("📋 Copy to clipboard", use_container_width=True):
                    st.code(output, language=None)
            with btn3:
                if linked_app_id and st.button("💾 Save to application", use_container_width=True):
                    save_material(linked_app_id, st.session_state.craft_task, output)
                    st.success("Saved!")

            # Regenerate with feedback
            st.markdown("**Refine the output:**")
            feedback = st.text_input("Feedback", placeholder="e.g. Make it more concise, add more enthusiasm, focus on leadership…")
            if st.button("🔄 Regenerate with feedback") and feedback:
                with st.spinner("Refining…"):
                    messages = [
                        {"role": "system", "content": "You are an expert career writer."},
                        {"role": "user", "content": build_prompt(task_key, job_title, company, jd, background)},
                        {"role": "assistant", "content": st.session_state.craft_output},
                        {"role": "user", "content": f"Please revise based on this feedback: {feedback}"}
                    ]
                    st.session_state.craft_output = ollama_chat(messages)
                    st.rerun()
