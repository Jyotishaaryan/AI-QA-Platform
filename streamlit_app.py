"""Streamlit client for the AI-QA Platform API."""

import os
from pathlib import Path

import httpx
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
HTTP_TIMEOUT = httpx.Timeout(100.0, connect=4.0)

st.set_page_config(
    page_title="Fieldnotes | AI-QA research desk",
    page_icon="📓",
    layout="wide",
    initial_sidebar_state="expanded",
)

stylesheet = Path(__file__).parent / "assets" / "styles.css"
st.markdown(f"<style>{stylesheet.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def init_state() -> None:
    defaults = {
        "access_token": None,
        "username": None,
        "messages": [],
        "last_meta": None,
        "pending_question": None,
        "login_error": None,
    }
    for name, value in defaults.items():
        if name not in st.session_state:
            st.session_state[name] = value


def request_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {st.session_state.access_token}"}


def get_backend_status() -> tuple[bool, str]:
    try:
        response = httpx.get(f"{API_BASE_URL}/health/ready", timeout=HTTP_TIMEOUT)
        body = response.json()
        if response.is_success:
            return True, "All systems operational"
        checks = body.get("checks", {})
        unavailable = [name for name, is_ok in checks.items() if not is_ok]
        detail = ", ".join(unavailable) if unavailable else "API not ready"
        return False, detail
    except (httpx.HTTPError, ValueError):
        return False, "API unreachable"


def error_message(response: httpx.Response) -> str:
    try:
        detail = response.json().get("detail")
    except ValueError:
        detail = None
    messages = {
        401: "Your session expired. Please sign in again.",
        403: "This account does not have permission to use chat.",
        429: "You’ve reached a request limit. Wait a moment and try again.",
        502: "The AI provider is temporarily unavailable. Please try again shortly.",
        503: "A required service is unavailable. Check the service status and try again.",
        504: "The AI provider took too long to respond. Please try again.",
    }
    return messages.get(response.status_code, str(detail or "The request could not be completed."))


def clear_session() -> None:
    st.session_state.access_token = None
    st.session_state.username = None
    st.session_state.messages = []
    st.session_state.last_meta = None
    st.rerun()


def render_sidebar(backend_ok: bool, backend_detail: str) -> None:
    with st.sidebar:
        brand_html = (
            '<div class="brand-row"><div class="brand-mark">F.</div>'
            '<div><div class="brand-title">Fieldnotes</div>'
            '<div class="brand-sub">AI-QA · research desk</div></div></div>'
        )
        st.markdown(
            brand_html,
            unsafe_allow_html=True,
        )
        st.markdown('<div class="side-caption">Workspace</div>', unsafe_allow_html=True)
        status_color = "#72ddb7" if backend_ok else "#ffab9f"
        st.markdown(
            f'<div class="status-card"><div style="font-weight:700">API status</div>'
            f'<div style="color:{status_color};font-size:12px;margin-top:7px">'
            f"● &nbsp;{backend_detail}</div></div>",
            unsafe_allow_html=True,
        )
        if st.session_state.access_token:
            st.markdown('<div class="side-caption">Signed in as</div>', unsafe_allow_html=True)
            st.caption(st.session_state.username)
            if st.button("＋  New conversation", use_container_width=True):
                st.session_state.messages = []
                st.session_state.last_meta = None
                st.rerun()
            st.divider()
            if st.button("Sign out", use_container_width=True):
                clear_session()
        st.markdown(
            '<div style="position:fixed;bottom:22px;color:#69748b;font-size:11px">'
            "FIELDNOTES · AI-QA RESEARCH DESK</div>",
            unsafe_allow_html=True,
        )


def render_login(backend_ok: bool) -> None:
    st.markdown(
        '<div class="eyebrow">FIELDNOTES / AI-QA RESEARCH DESK</div>'
        '<h1 class="hero-title">Good questions<br>deserve room.</h1>'
        '<p class="hero-copy">A considered space for working through ideas. '
        "Sign in to start a conversation and keep the useful details close.</p>",
        unsafe_allow_html=True,
    )
    left, center, right = st.columns([1, 1.12, 1])
    with center:
        st.markdown('<div class="section-label">Secure sign in</div>', unsafe_allow_html=True)
        with st.container(border=True):
            with st.form("login_form", clear_on_submit=False):
                username = st.text_input("Email address", placeholder="you@example.com")
                password = st.text_input(
                    "Password", type="password", placeholder="Enter your password"
                )
                submitted = st.form_submit_button(
                    "Continue to workspace", type="primary", use_container_width=True
                )
            if st.session_state.login_error:
                st.error(st.session_state.login_error)
            if submitted:
                if not backend_ok:
                    st.error("The API is unavailable. Start the backend, then try again.")
                else:
                    try:
                        response = httpx.post(
                            f"{API_BASE_URL}/auth/login",
                            json={"username": username.strip(), "password": password},
                            timeout=HTTP_TIMEOUT,
                        )
                        if response.is_success:
                            st.session_state.access_token = response.json()["access_token"]
                            st.session_state.username = username.strip()
                            st.session_state.login_error = None
                            st.rerun()
                        st.session_state.login_error = (
                            "Check your email and password, then try again."
                            if response.status_code == 401
                            else error_message(response)
                        )
                        st.rerun()
                    except httpx.HTTPError:
                        st.session_state.login_error = "Could not reach the API. Please try again."
                        st.rerun()
        st.markdown(
            '<div class="hint">A quiet place for clear thinking and useful answers.</div>',
            unsafe_allow_html=True,
        )


def render_chat_header(backend_ok: bool) -> None:
    left, right = st.columns([4, 1])
    with left:
        st.markdown(
            '<div class="eyebrow">FIELDNOTES / 01 — QUESTION DESK</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<h1 class="hero-title">What are we working through?</h1>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="hero-copy">Ask a question and get a clear answer, '
            "backed by transparent request "
            "details and usage.</p>",
            unsafe_allow_html=True,
        )
    with right:
        st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
        connection_color = "#28b887" if backend_ok else "#e46b6b"
        connection_label = "Connected" if backend_ok else "Reconnecting"
        st.markdown(
            f'<div class="pill"><span class="dot" style="background:{connection_color}"></span>'
            f"{connection_label}</div>",
            unsafe_allow_html=True,
        )


def render_metrics() -> None:
    meta = st.session_state.last_meta
    if not meta:
        return
    st.markdown('<div class="section-label">Latest response</div>', unsafe_allow_html=True)
    usage = meta.get("usage") or {}
    values = [
        ("Response time", f"{meta.get('latency_ms', 0)} ms"),
        (
            "Prompt tokens",
            usage.get("prompt_tokens") if usage.get("prompt_tokens") is not None else "—",
        ),
        (
            "Answer tokens",
            usage.get("completion_tokens") if usage.get("completion_tokens") is not None else "—",
        ),
        (
            "Total tokens",
            usage.get("total_tokens") if usage.get("total_tokens") is not None else "—",
        ),
    ]
    columns = st.columns(4)
    for column, (label, value) in zip(columns, values, strict=True):
        column.markdown(
            f'<div class="metric-card"><div class="metric-label">{label}</div>'
            f'<div class="metric-value">{value}</div></div>',
            unsafe_allow_html=True,
        )
    request_id = meta.get("request_id")
    if request_id:
        st.caption(f"Request ID  ·  `{request_id}`")


def submit_question(question: str) -> None:
    question = question.strip()
    if not question:
        return
    st.session_state.messages.append({"role": "user", "content": question})
    try:
        with st.spinner("Thinking through your question…"):
            response = httpx.post(
                f"{API_BASE_URL}/chat",
                json={"question": question},
                headers=request_headers(),
                timeout=HTTP_TIMEOUT,
            )
        if response.status_code == 401:
            clear_session()
        if not response.is_success:
            st.session_state.messages.append({"role": "error", "content": error_message(response)})
            st.session_state.last_meta = None
            return
        payload = response.json()
        st.session_state.messages.append({"role": "assistant", "content": payload["answer"]})
        st.session_state.last_meta = payload
    except httpx.TimeoutException:
        st.session_state.messages.append(
            {"role": "error", "content": "The request timed out. Please try again."}
        )
        st.session_state.last_meta = None
    except httpx.HTTPError:
        st.session_state.messages.append(
            {
                "role": "error",
                "content": "Could not connect to the API. Check its status and retry.",
            }
        )
        st.session_state.last_meta = None


def render_chat() -> None:
    for message in st.session_state.messages:
        if message["role"] == "error":
            with st.chat_message("assistant", avatar="⚠️"):
                st.warning(message["content"])
            continue
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if not st.session_state.messages:
        st.markdown('<div class="section-label">Try asking</div>', unsafe_allow_html=True)
        suggestions = [
            "Explain a complex idea simply",
            "Help me compare two approaches",
            "Give me a step-by-step plan",
        ]
        columns = st.columns(3)
        for column, suggestion in zip(columns, suggestions, strict=True):
            if column.button(suggestion, use_container_width=True):
                st.session_state.pending_question = suggestion
                st.rerun()

    question = st.chat_input("Ask anything…", max_chars=8000, key="chat_composer")
    question = question or st.session_state.pending_question
    if question:
        st.session_state.pending_question = None
        submit_question(question)
        st.rerun()


init_state()
backend_ok, backend_detail = get_backend_status()
render_sidebar(backend_ok, backend_detail)

if st.session_state.access_token:
    render_chat_header(backend_ok)
    render_metrics()
    st.markdown('<div class="section-label">Conversation notes</div>', unsafe_allow_html=True)
    render_chat()
else:
    render_login(backend_ok)
