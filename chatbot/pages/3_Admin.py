import json
import os

import httpx
import streamlit as st

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from utils import apply_styles, sidebar_nav

API_URL = os.getenv("API_URL", "http://localhost:8000")
DEFAULT_WIDGET_ID = os.getenv("WIDGET_ID", "")

st.set_page_config(page_title="Admin", layout="wide")
apply_styles()

if not st.session_state.get("token"):
    st.warning("Please log in first.")
    st.page_link("app.py", label="Go to Login")
    st.stop()

if st.session_state.get("role") != "admin":
    st.error("Admin access required.")
    st.stop()

sidebar_nav()

st.markdown("<h1 style='color:#18355e;margin-bottom:0'>Admin</h1>", unsafe_allow_html=True)

tab_widget, tab_users, tab_audit, tab_memory = st.tabs(["Widget Config", "Users", "Audit Log", "Memory"])

# ── Widget Config ──────────────────────────────────────────────────────────

with tab_widget:
    # Fetch all widgets owned by this admin
    try:
        widgets_resp = httpx.get(
            f"{API_URL}/admin/widgets",
            headers={"Authorization": f"Bearer {st.session_state.token}"},
            timeout=10.0,
        )
    except httpx.RequestError as exc:
        st.error(str(exc))
        st.stop()

    widgets = widgets_resp.json() if widgets_resp.status_code == 200 else []

    # Create-new form always visible at the top
    with st.expander("Create new widget", expanded=len(widgets) == 0):
        with st.form("create_widget_form"):
            new_name = st.text_input("Widget name", value="Home Assistant Copilot")
            new_greeting = st.text_input("Greeting", value="How can I help you?")
            created = st.form_submit_button("Create widget", use_container_width=True)

        if created and new_name:
            try:
                cr = httpx.post(
                    f"{API_URL}/widget/config",
                    json={"name": new_name, "greeting": new_greeting},
                    headers={"Authorization": f"Bearer {st.session_state.token}"},
                    timeout=10.0,
                )
            except httpx.RequestError as exc:
                st.error(str(exc))
                st.stop()
            if cr.status_code == 201:
                st.session_state.widget_id = str(cr.json()["id"])
                st.success(f"Widget created: `{st.session_state.widget_id}`")
                st.rerun()
            else:
                st.error(f"Create failed: {cr.status_code} {cr.text}")

    if not widgets:
        st.info("No widgets yet — create one above.")
    else:
        # Widget picker — default to session_state if previously selected
        widget_names = [f"{w['name']}  ({w['id'][:8]}…)" for w in widgets]
        saved_id = st.session_state.get("widget_id", "")
        default_idx = next(
            (i for i, w in enumerate(widgets) if w["id"] == saved_id), 0
        )
        chosen_idx = st.selectbox(
            "Select widget",
            range(len(widgets)),
            format_func=lambda i: widget_names[i],
            index=default_idx,
        )
        widget_id = widgets[chosen_idx]["id"]
        st.session_state.widget_id = widget_id

        # Reset form to expanded when a different widget is selected
        if st.session_state.get("_cfg_widget_id") != widget_id:
            st.session_state._cfg_widget_id = widget_id
            st.session_state._cfg_expanded = True

        try:
            cfg_resp = httpx.get(
                f"{API_URL}/widget/config/{widget_id}",
                headers={"Authorization": f"Bearer {st.session_state.token}"},
                timeout=10.0,
            )
        except httpx.RequestError as exc:
            st.error(f"Cannot reach API: {exc}")
            st.stop()

        if cfg_resp.status_code == 404:
            st.error("Widget not found.")
        elif cfg_resp.status_code != 200:
            st.error(f"Error {cfg_resp.status_code}: {cfg_resp.text}")
        else:
            cfg = cfg_resp.json()

            if st.session_state.get("_cfg_save_success"):
                st.success("Settings saved.")
                st.session_state._cfg_save_success = False

            with st.expander("Widget settings", expanded=st.session_state.get("_cfg_expanded", True)):
                with st.form("widget_form"):
                    name = st.text_input("Name", value=cfg.get("name", ""))
                    greeting = st.text_area("Greeting", value=cfg.get("greeting", ""))
                    origins_raw = st.text_area(
                        "Allowed origins (one per line)",
                        value="\n".join(cfg.get("allowed_origins") or []),
                        help="Domains allowed to embed this widget. One URL per line.",
                    )
                    tools_raw = st.text_area(
                        "Enabled tools (one per line)",
                        value="\n".join(cfg.get("enabled_tools") or []),
                        help="Agent tools available to widget visitors. One tool name per line.",
                    )
                    theme_raw = st.text_area(
                        "Theme (JSON)",
                        value=json.dumps(cfg.get("theme") or {}, indent=2),
                        height=100,
                        help="Visual customisation passed to the widget UI (reserved for future use).",
                    )
                    saved = st.form_submit_button("Save changes", use_container_width=True)

                if saved:
                    try:
                        theme = json.loads(theme_raw)
                    except json.JSONDecodeError:
                        st.error("Theme must be valid JSON.")
                        st.stop()

                    try:
                        patch = httpx.patch(
                            f"{API_URL}/widget/config/{widget_id}",
                            json={
                                "name": name,
                                "greeting": greeting,
                                "allowed_origins": [
                                    o.strip() for o in origins_raw.splitlines() if o.strip()
                                ],
                                "enabled_tools": [
                                    t.strip() for t in tools_raw.splitlines() if t.strip()
                                ],
                                "theme": theme,
                            },
                            headers={"Authorization": f"Bearer {st.session_state.token}"},
                            timeout=10.0,
                        )
                    except httpx.RequestError as exc:
                        st.error(f"Save failed: {exc}")
                        st.stop()

                    if patch.status_code == 200:
                        st.session_state._cfg_expanded = False
                        st.session_state._cfg_save_success = True
                        st.rerun()
                    else:
                        st.error(f"Save failed: {patch.status_code} {patch.text}")

            st.divider()

            widget_host_url = st.text_input(
                "Widget host URL", value="http://localhost:3000", key="widget_host_url",
                help="URL of the Vite dev server (or production frontend).",
            )
            col_single, col_all = st.columns(2)
            col_single.link_button(
                "Open demo (this widget)",
                f"{widget_host_url}/demo.html?widget_id={widget_id}",
                use_container_width=True,
            )
            all_ids = ",".join(w["id"] for w in widgets)
            col_all.link_button(
                "Open demo (all widgets)",
                f"{widget_host_url}/demo.html?widget_ids={all_ids}",
                use_container_width=True,
            )

            st.divider()
            st.subheader("Embed snippet")
            st.caption(
                "Copy this tag and paste it into any HTML page where you want the chat widget to appear. "
                "Replace the Public API URL with your deployed server address when going to production."
            )
            public_url = st.text_input(
                "Public API URL", value="http://localhost:8000", key="public_url"
            )
            snippet = (
                f'<script src="{public_url}/widget.js" '
                f'data-widget-id="{widget_id}"></script>'
            )
            st.code(snippet, language="html")

# ── Users ──────────────────────────────────────────────────────────────────

with tab_users:
    try:
        users_resp = httpx.get(
            f"{API_URL}/admin/users",
            headers={"Authorization": f"Bearer {st.session_state.token}"},
            timeout=10.0,
        )
    except httpx.RequestError as exc:
        st.error(str(exc))
        st.stop()

    if users_resp.status_code != 200:
        st.error(f"Failed to load users: {users_resp.status_code}")
    else:
        users = users_resp.json()
        st.write(f"{len(users)} registered user(s)")

        for user in users:
            col_email, col_role, col_action = st.columns([4, 2, 2])
            col_email.write(user["email"])
            col_role.write(user["role"])
            new_role = col_action.selectbox(
                "Role",
                ["user", "admin"],
                index=0 if user["role"] == "user" else 1,
                key=f"role_{user['id']}",
                label_visibility="collapsed",
            )
            if new_role != user["role"]:
                try:
                    patch = httpx.patch(
                        f"{API_URL}/admin/users/{user['id']}/role",
                        json={"role": new_role},
                        headers={"Authorization": f"Bearer {st.session_state.token}"},
                        timeout=10.0,
                    )
                except httpx.RequestError as exc:
                    st.error(str(exc))
                    continue
                if patch.status_code == 200:
                    st.rerun()
                else:
                    st.error(f"Role update failed: {patch.status_code}")

# ── Audit Log ──────────────────────────────────────────────────────────────

with tab_audit:
    try:
        audit_resp = httpx.get(
            f"{API_URL}/admin/audit",
            headers={"Authorization": f"Bearer {st.session_state.token}"},
            params={"limit": 100},
            timeout=10.0,
        )
    except httpx.RequestError as exc:
        st.error(str(exc))
        st.stop()

    if audit_resp.status_code != 200:
        st.error(f"Failed to load audit log: {audit_resp.status_code}")
    else:
        logs = audit_resp.json()
        if not logs:
            st.info("No audit events yet.")
        else:
            import pandas as pd
            df = pd.DataFrame([
                {
                    "Timestamp": log["created_at"][:19].replace("T", " "),
                    "User": log.get("actor_email") or str(log["actor_id"])[:8] + "...",
                    "Action": log["action"],
                    "Target": str(log["target"]),
                }
                for log in logs
            ])
            st.dataframe(df, use_container_width=True, hide_index=True)

# ── Memory (all users) ────────────────────────────────────────────────────────

with tab_memory:
    try:
        mem_resp = httpx.get(
            f"{API_URL}/admin/memory",
            headers={"Authorization": f"Bearer {st.session_state.token}"},
            params={"limit": 500},
            timeout=10.0,
        )
    except httpx.RequestError as exc:
        st.error(str(exc))
        st.stop()

    if mem_resp.status_code != 200:
        st.error(f"Failed to load memory: {mem_resp.status_code}")
    else:
        entries = mem_resp.json()
        if not entries:
            st.info("No memory entries yet.")
        else:
            import pandas as pd

            all_emails = sorted({e["user_email"] for e in entries})
            col_m, col_f = st.columns([3, 1])
            col_m.metric("Total entries", len(entries))
            col_f.metric("Users with memory", len(all_emails))

            selected_user = st.selectbox(
                "Filter by user",
                ["All users"] + all_emails,
                key="mem_user_filter",
            )
            filtered = (
                entries if selected_user == "All users"
                else [e for e in entries if e["user_email"] == selected_user]
            )

            df = pd.DataFrame([
                {
                    "Timestamp": e["created_at"][:19].replace("T", " "),
                    "User": e["user_email"],
                    "Role": e["role"],
                    "Conversation": e["conversation_id"][:8] + "...",
                    "Content": e["content"],
                }
                for e in filtered
            ])
            st.dataframe(df, use_container_width=True, hide_index=True)
