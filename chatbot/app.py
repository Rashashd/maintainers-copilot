import os

import httpx
import streamlit as st

from utils import apply_styles

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Maintainer's Co-pilot", layout="centered")
apply_styles()

if st.session_state.get("token"):
    st.switch_page("pages/1_Chat.py")

# "view" controls which form is rendered: "login" (default) or "signup"
if "view" not in st.session_state:
    st.session_state.view = "login"

st.markdown(
    "<h1 style='color:#18355e;margin-bottom:0'>Maintainer's Co-pilot</h1>",
    unsafe_allow_html=True,
)
st.caption("AI assistant for open-source maintainers.")
st.write("")

# --- Log in ---
if st.session_state.view == "login":
    if st.session_state.pop("signup_success", False):
        st.success("Account created! You can now log in.")

    with st.form("login_form"):
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        submitted = st.form_submit_button("Log in", use_container_width=True)

    st.write("Don't have an account?")
    if st.button("Sign up", use_container_width=True):
        st.session_state.view = "signup"
        st.rerun()

    if submitted:
        if not email or not password:
            st.error("Email and password are required.")
        else:
            with st.spinner("Logging in..."):
                try:
                    resp = httpx.post(
                        f"{API_URL}/auth/jwt/login",
                        data={"username": email, "password": password},
                        timeout=10.0,
                    )
                except httpx.RequestError as exc:
                    st.error(f"Cannot reach API: {exc}")
                    st.stop()

            if resp.status_code == 200:
                st.session_state.token = resp.json()["access_token"]
                st.session_state.email = email
                try:
                    me = httpx.get(
                        f"{API_URL}/users/me",
                        headers={"Authorization": f"Bearer {st.session_state.token}"},
                        timeout=10.0,
                    )
                    st.session_state.role = (
                        me.json().get("role", "user") if me.status_code == 200 else "user"
                    )
                except httpx.RequestError:
                    st.session_state.role = "user"
                st.switch_page("pages/1_Chat.py")
            else:
                st.error("Invalid email or password.")

# --- Sign up ---
else:
    st.subheader("Create an account")

    with st.form("signup_form"):
        new_email = st.text_input("Email", key="signup_email")
        new_password = st.text_input("Password", type="password", key="signup_password")
        new_password2 = st.text_input(
            "Confirm password", type="password", key="signup_password2"
        )
        signup_submitted = st.form_submit_button(
            "Create account", use_container_width=True
        )

    if st.button("Back to login", use_container_width=True):
        st.session_state.view = "login"
        st.rerun()

    if signup_submitted:
        if not new_email or not new_password:
            st.error("Email and password are required.")
        elif new_password != new_password2:
            st.error("Passwords do not match.")
        else:
            with st.spinner("Creating account..."):
                try:
                    resp = httpx.post(
                        f"{API_URL}/auth/register",
                        json={"email": new_email, "password": new_password},
                        timeout=10.0,
                    )
                except httpx.RequestError as exc:
                    st.error(f"Cannot reach API: {exc}")
                    st.stop()

            if resp.status_code == 201:
                st.session_state.signup_success = True
                st.session_state.view = "login"
                st.rerun()
            elif resp.status_code == 400:
                detail = resp.json().get("detail", "")
                if "already exists" in str(detail).lower():
                    st.error("An account with this email already exists.")
                else:
                    st.error(f"Registration failed: {detail}")
            else:
                st.error(f"Registration failed ({resp.status_code}).")
