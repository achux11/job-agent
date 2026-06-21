import streamlit as st

st.set_page_config(
    page_title="Job Assistant Agent",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    [data-testid="stSidebar"] { background: #1a1a2e; }
    [data-testid="stSidebar"] * { color: #e0e0e0 !important; }
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] h1, h2, h3 { color: #ffffff !important; }
    .main-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 2rem; border-radius: 12px; margin-bottom: 1.5rem; color: white;
    }
    .metric-card {
        background: #f8f9fa; border: 1px solid #e9ecef;
        border-radius: 10px; padding: 1rem; text-align: center;
    }
    .status-badge {
        display: inline-block; padding: 3px 10px;
        border-radius: 12px; font-size: 0.8em; font-weight: 600;
    }
    .chat-msg-user {
        background: #e3f2fd; border-radius: 10px;
        padding: 10px 14px; margin: 6px 0; text-align: right;
    }
    .chat-msg-ai {
        background: #f3e5f5; border-radius: 10px;
        padding: 10px 14px; margin: 6px 0;
    }
    div[data-testid="stExpander"] { border: 1px solid #e9ecef; border-radius: 10px; }
    .stButton > button {
        border-radius: 8px; font-weight: 500;
        transition: all 0.2s ease;
    }
    .stButton > button:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
</style>
""", unsafe_allow_html=True)

from utils.db import init_db
init_db()

st.sidebar.markdown("## 💼 Job Assistant")
st.sidebar.markdown("---")

pages = {
    "🤖 AI Chat Agent": "chat",
    "📝 Craft Materials": "craft",
    "🔍 Job Research": "research",
    "📊 Application Tracker": "tracker",
    "📄 Resume Vault": "vault",
    "⚙️ Settings": "settings",
}

if "page" not in st.session_state:
    st.session_state.page = "chat"

for label, key in pages.items():
    if st.sidebar.button(label, use_container_width=True, type="primary" if st.session_state.page == key else "secondary"):
        st.session_state.page = key
        st.rerun()

st.sidebar.markdown("---")

# Quick stats in sidebar
from utils.db import get_stats
stats = get_stats()
st.sidebar.markdown("### 📈 Pipeline")
col1, col2 = st.sidebar.columns(2)
col1.metric("Applied", stats["total"])
col2.metric("Interviews", stats["interviews"])
col3, col4 = st.sidebar.columns(2)
col3.metric("Active", stats["active"])
col4.metric("Offers", stats["offers"])

st.sidebar.markdown("---")
st.sidebar.caption("Powered by Ollama + ChromaDB + SQLite")

# Route to pages
page = st.session_state.page

if page == "chat":
    from pages import chat; chat.render()
elif page == "craft":
    from pages import craft; craft.render()
elif page == "research":
    from pages import research; research.render()
elif page == "tracker":
    from pages import tracker; tracker.render()
elif page == "vault":
    from pages import vault; vault.render()
elif page == "settings":
    from pages import settings; settings.render()
