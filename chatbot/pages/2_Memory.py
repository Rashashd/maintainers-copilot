import os
from collections import defaultdict

import httpx
import streamlit as st

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from utils import apply_styles, sidebar_nav

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Memory Inspector", layout="wide")
apply_styles()

if not st.session_state.get("token"):
    st.warning("Please log in first.")
    st.page_link("app.py", label="Go to Login")
    st.stop()

sidebar_nav()

st.markdown("<h1 style='color:#18355e;margin-bottom:0'>Memory Inspector</h1>", unsafe_allow_html=True)
st.caption(
    "Episodic long-term memory stored in pgvector. "
    "Entries from past conversations are injected as context on every new turn."
)

if st.button("Refresh"):
    st.rerun()

try:
    resp = httpx.get(
        f"{API_URL}/memory/history",
        headers={"Authorization": f"Bearer {st.session_state.token}"},
        params={"limit": 200},
        timeout=10.0,
    )
except httpx.RequestError as exc:
    st.error(f"Cannot reach API: {exc}")
    st.stop()

if resp.status_code == 401:
    st.error("Session expired.")
    st.session_state.clear()
    st.switch_page("app.py")
elif resp.status_code != 200:
    st.error(f"Failed to load memory: {resp.status_code}")
    st.stop()

entries = resp.json()
if not entries:
    st.info("No memory entries yet. Start a conversation to build episodic memory.")
    st.stop()

# Group by conversation to demonstrate cross-conversation recall
by_conv: dict[str, list] = defaultdict(list)
for e in entries:
    by_conv[e["conversation_id"]].append(e)

col_a, col_b = st.columns(2)
col_a.metric("Total entries", len(entries))
col_b.metric("Conversations", len(by_conv))

current_conv = st.session_state.get("conversation_id", "")

for conv_id, conv_entries in by_conv.items():
    is_current = conv_id == current_conv
    label = "Current conversation" if is_current else f"Conversation {conv_id[:8]}..."
    with st.expander(
        f"{label} — {len(conv_entries)} entries", expanded=is_current
    ):
        for entry in conv_entries:
            col_content, col_del = st.columns([10, 1])
            with col_content:
                icon = "👤" if entry["role"] == "user" else "🤖"
                st.markdown(f"**{icon} {entry['role']}** · `{entry['created_at'][:19]}`")
                st.caption(entry["content"])
            with col_del:
                if st.button("🗑", key=entry["id"], help="Delete"):
                    try:
                        del_resp = httpx.delete(
                            f"{API_URL}/memory/{entry['id']}",
                            headers={"Authorization": f"Bearer {st.session_state.token}"},
                            timeout=10.0,
                        )
                    except httpx.RequestError as exc:
                        st.error(str(exc))
                        continue
                    if del_resp.status_code == 204:
                        st.rerun()
                    else:
                        st.error(f"Delete failed ({del_resp.status_code}).")
