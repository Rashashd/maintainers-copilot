import streamlit as st


_CSS = """
<style>
/* 1. Collapse the blank header area Streamlit reserves for auto-nav */
[data-testid="stSidebarHeader"] {
    min-height: 0 !important;
    padding: 0 !important;
    height: auto !important;
}
[data-testid="stSidebarNav"] {
    display: none !important;
    height: 0 !important;
    overflow: hidden !important;
}

/* 2. Nav link hover / active styling */
[data-testid="stSidebar"] [data-testid="stPageLink"] a {
    border-left: 3px solid transparent;
    padding-left: 0.5rem !important;
    border-radius: 0 6px 6px 0;
    font-weight: 500;
    transition: border-color 0.15s, background 0.15s;
    color: #1e293b !important;
    text-decoration: none !important;
}
[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover {
    border-left-color: #18355e !important;
    background: #dbeafe !important;
}
[data-testid="stSidebar"] [data-testid="stPageLink-active"] a {
    border-left-color: #18355e !important;
    background: #dbeafe !important;
    color: #18355e !important;
    font-weight: 700 !important;
}

/* 3. Footer user label */
.sidebar-user-label {
    font-size: 0.8rem;
    color: #64748b;
    padding: 0.25rem 0 0.4rem;
}

/* 4. Primary button colour */
div.stButton > button[kind="primary"],
div.stFormSubmitButton > button {
    background-color: #18355e !important;
    border-color: #18355e !important;
    color: #ffffff !important;
}
div.stButton > button[kind="primary"]:hover,
div.stFormSubmitButton > button:hover {
    background-color: #1e4080 !important;
    border-color: #1e4080 !important;
}
</style>
"""


def apply_styles() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def sidebar_nav() -> None:
    with st.sidebar:
        st.markdown(
            "<p style='font-size:1.05rem;font-weight:700;color:#18355e;"
            "margin:0.5rem 0 1rem;letter-spacing:-0.3px'>"
            "Maintainer&#39;s Co-pilot</p>",
            unsafe_allow_html=True,
        )

        st.page_link("pages/1_Chat.py", label="Chat")
        st.page_link("pages/2_Memory.py", label="Memory")
        if st.session_state.get("role") == "admin":
            st.page_link("pages/3_Admin.py", label="Admin")

        # Push footer down — calc leaves room for footer (~110px) + title/nav (~160px)
        st.markdown(
            "<div style='height:calc(100vh - 340px);min-height:2rem'></div>",
            unsafe_allow_html=True,
        )

        st.divider()
        st.markdown(
            f"<p class='sidebar-user-label'>Logged in as "
            f"<strong>{st.session_state.get('email', '')}</strong></p>",
            unsafe_allow_html=True,
        )
        if st.button("Log out", use_container_width=True, key="__logout__"):
            st.session_state.clear()
            st.switch_page("app.py")
