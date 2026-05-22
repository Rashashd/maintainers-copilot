import os
import uuid

import httpx
import streamlit as st

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from utils import apply_styles, sidebar_nav

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Chat", layout="wide")
apply_styles()

if not st.session_state.get("token"):
    st.warning("Please log in first.")
    st.page_link("app.py", label="Go to Login")
    st.stop()

sidebar_nav()

if "messages" not in st.session_state:
    st.session_state.messages = []
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = str(uuid.uuid4())

col_title, col_btn = st.columns([5, 2])
with col_title:
    st.markdown("<h1 style='color:#18355e;margin-bottom:0'>Chat</h1>", unsafe_allow_html=True)
with col_btn:
    st.write("")
    if st.button("New conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.conversation_id = str(uuid.uuid4())
        st.rerun()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("tools_used"):
            st.caption("Tools used: " + ", ".join(f"`{t}`" for t in msg["tools_used"]))

prompt = st.chat_input("Paste a GitHub issue or ask a question about Home Assistant...")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                resp = httpx.post(
                    f"{API_URL}/chat",
                    json={
                        "message": prompt,
                        "conversation_id": st.session_state.conversation_id,
                    },
                    headers={"Authorization": f"Bearer {st.session_state.token}"},
                    timeout=60.0,
                )
            except httpx.RequestError as exc:
                st.error(f"Request failed: {exc}")
                st.stop()

        if resp.status_code == 200:
            data = resp.json()
            reply = data["reply"]
            tools_used = data.get("tools_used", [])
            st.session_state.conversation_id = data["conversation_id"]
            st.markdown(reply)
            if tools_used:
                st.caption("Tools used: " + ", ".join(f"`{t}`" for t in tools_used))
            st.session_state.messages.append({"role": "assistant", "content": reply, "tools_used": tools_used})
        elif resp.status_code == 401:
            st.error("Session expired. Please log in again.")
            st.session_state.clear()
            st.switch_page("app.py")
        else:
            st.error(f"Error {resp.status_code}: {resp.text}")
