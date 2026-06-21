import streamlit as st
from utils.db import (
    add_application, get_applications, update_application,
    delete_application, get_application, get_materials, get_stats
)

STATUS_COLORS = {
    "applied": "🟦",
    "screening": "🟡",
    "interview": "🟠",
    "offer": "🟢",
    "rejected": "🔴",
    "withdrawn": "⚫",
}

STATUS_OPTIONS = ["applied", "screening", "interview", "offer", "rejected", "withdrawn"]


def render():
    st.markdown("""
    <div class="main-header">
        <h1 style='margin:0;font-size:1.8rem'>📊 Application Tracker</h1>
        <p style='margin:0.3rem 0 0;opacity:0.85'>Track every application, update statuses, and stay organized</p>
    </div>
    """, unsafe_allow_html=True)

    # Stats row
    stats = get_stats()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📨 Total Applied", stats["total"])
    c2.metric("⚡ Active Pipeline", stats["active"])
    c3.metric("🎯 Interviews", stats["interviews"])
    c4.metric("🎉 Offers", stats["offers"])

    st.markdown("---")

    tab1, tab2 = st.tabs(["📋 All Applications", "➕ Add New"])

    # ── ADD NEW ──
    with tab2:
        st.subheader("Add New Application")
        col1, col2 = st.columns(2)
        with col1:
            new_title = st.text_input("Job title *", placeholder="e.g. Senior Product Manager")
            new_company = st.text_input("Company *", placeholder="e.g. Stripe")
            new_location = st.text_input("Location", placeholder="e.g. Austin, TX / Remote")
            new_url = st.text_input("Job URL", placeholder="https://...")
        with col2:
            new_status = st.selectbox("Status", STATUS_OPTIONS)
            new_date = st.date_input("Date applied")
            col_s1, col_s2 = st.columns(2)
            new_sal_min = col_s1.number_input("Salary min ($)", min_value=0, step=5000)
            new_sal_max = col_s2.number_input("Salary max ($)", min_value=0, step=5000)
            new_notes = st.text_area("Notes", height=80, placeholder="Recruiter name, referral, notes…")

        new_jd = st.text_area("Job description (optional)", height=120,
                               placeholder="Paste the job description for AI context…")

        if st.button("➕ Add Application", type="primary", use_container_width=True):
            if not new_title or not new_company:
                st.error("Job title and company are required.")
            else:
                add_application(
                    job_title=new_title, company=new_company, location=new_location,
                    job_url=new_url, job_description=new_jd, status=new_status,
                    notes=new_notes,
                    salary_min=new_sal_min if new_sal_min else None,
                    salary_max=new_sal_max if new_sal_max else None,
                    applied_date=str(new_date)
                )
                st.success(f"✅ Added: {new_title} @ {new_company}")
                st.rerun()

    # ── ALL APPLICATIONS ──
    with tab1:
        col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
        with col_f1:
            search = st.text_input("🔍 Search", placeholder="Filter by title or company…")
        with col_f2:
            filter_status = st.selectbox("Filter by status", ["All"] + STATUS_OPTIONS)
        with col_f3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔄 Refresh", use_container_width=True):
                st.rerun()

        apps = get_applications(filter_status)

        if search:
            s = search.lower()
            apps = [a for a in apps if s in a["job_title"].lower() or s in a["company"].lower()]

        if not apps:
            st.info("No applications found. Add your first one in the ➕ Add New tab!")
        else:
            for app in apps:
                with st.expander(
                    f"{STATUS_COLORS.get(app['status'], '⚪')} **{app['job_title']}** @ {app['company']}  |  {app['status'].title()}  |  {app['applied_date'] or ''}",
                    expanded=False
                ):
                    col_l, col_r = st.columns([2, 1])

                    with col_l:
                        st.markdown(f"**Location:** {app['location'] or '—'}")
                        if app["job_url"]:
                            st.markdown(f"**URL:** [{app['job_url'][:50]}...]({app['job_url']})")
                        if app["salary_min"] or app["salary_max"]:
                            sal = f"${app['salary_min']:,}" if app["salary_min"] else ""
                            sal += f" – ${app['salary_max']:,}" if app["salary_max"] else ""
                            st.markdown(f"**Salary range:** {sal}")
                        if app["notes"]:
                            st.markdown(f"**Notes:** {app['notes']}")

                        # Materials
                        materials = get_materials(app["id"])
                        if materials:
                            st.markdown(f"**Saved materials:** {len(materials)}")
                            for m in materials:
                                with st.expander(f"📄 {m['type'].replace('_',' ').title()} — {m['created_at'][:10]}"):
                                    st.text(m["content"])

                    with col_r:
                        new_status = st.selectbox(
                            "Update status",
                            STATUS_OPTIONS,
                            index=STATUS_OPTIONS.index(app["status"]) if app["status"] in STATUS_OPTIONS else 0,
                            key=f"status_{app['id']}"
                        )
                        if new_status != app["status"]:
                            if st.button("💾 Save status", key=f"save_{app['id']}", use_container_width=True):
                                update_application(app["id"], status=new_status)
                                st.success("Updated!")
                                st.rerun()

                        new_notes = st.text_area("Update notes", value=app["notes"] or "",
                                                  key=f"notes_{app['id']}", height=80)
                        if st.button("💾 Save notes", key=f"savenotes_{app['id']}", use_container_width=True):
                            update_application(app["id"], notes=new_notes)
                            st.success("Notes saved!")

                        st.markdown("---")
                        if st.button("🗑️ Delete", key=f"del_{app['id']}", use_container_width=True):
                            delete_application(app["id"])
                            st.rerun()

    # ── KANBAN SUMMARY ──
    st.markdown("---")
    st.subheader("📌 Pipeline Overview")
    all_apps = get_applications()
    cols = st.columns(len(STATUS_OPTIONS))
    for i, status in enumerate(STATUS_OPTIONS):
        bucket = [a for a in all_apps if a["status"] == status]
        with cols[i]:
            st.markdown(f"**{STATUS_COLORS[status]} {status.title()}**")
            st.markdown(f"<div style='font-size:2rem;font-weight:700;text-align:center'>{len(bucket)}</div>", unsafe_allow_html=True)
            for a in bucket[:5]:
                st.caption(f"{a['job_title'][:20]} @ {a['company'][:15]}")
            if len(bucket) > 5:
                st.caption(f"+{len(bucket)-5} more")
