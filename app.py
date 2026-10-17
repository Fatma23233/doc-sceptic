from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from urllib.parse import urlparse

import streamlit as st

from doc_sceptic.agent import DataArchitectureAgent
from doc_sceptic.config import Settings
from doc_sceptic.supabase_store import HistoryStore, anon_client


st.set_page_config(
    page_title="Doc-Sceptic | Microsoft Fabric Advisor",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "theme" not in st.session_state:
    st.session_state.theme = "light"


# =============================================================================
# THÈMES
# Toutes les couleurs passent par des variables CSS : clair et sombre ne
# diffèrent que par ce dictionnaire.
# =============================================================================

PALETTES = {
    "light": {
        "bg": "#ffffff",
        "glow1": "rgba(221,235,255,.58)",
        "glow2": "rgba(232,247,251,.45)",
        "text": "#132746",
        "title": "#071c3b",
        "muted": "#607291",
        "soft": "#71819a",
        "blue": "#1268db",
        "blue-strong": "#0e60c9",
        "sidebar": "rgba(248,251,255,.98)",
        "sidebar-line": "#e3eaf3",
        "card": "rgba(255,255,255,.95)",
        "card-line": "#dce4ee",
        "shadow": "0 8px 26px rgba(26,59,101,.06)",
        "user-bg": "linear-gradient(105deg,#ebf4ff,#e5efff)",
        "user-line": "#d2e3fb",
        "chip": "rgba(255,255,255,.9)",
        "chip-line": "#dce5f0",
        "hover": "#eef5ff",
        "active": "#e1edfc",
        "input": "#ffffff",
        "avatar": "#dbeafe",
        "avatar-fg": "#1268db",
        "ok-bg": "#eaf8f1",
        "ok-fg": "#096546",
        "ok-line": "#c7ead7",
        "ok-dot": "#0aa968",
        "warn-bg": "#fff7e6",
        "warn-fg": "#9a5a02",
        "warn-line": "#f0dca8",
        "warn-dot": "#e39a14",
        "bad-bg": "#fff1ef",
        "bad-fg": "#9d332b",
        "bad-line": "#efcac5",
        "bad-dot": "#d9534f",
    },
    "dark": {
        "bg": "#0a1020",
        "glow1": "rgba(37,99,200,.28)",
        "glow2": "rgba(20,140,160,.16)",
        "text": "#cfdbef",
        "title": "#f1f5fc",
        "muted": "#8da1c0",
        "soft": "#7f93b3",
        "blue": "#4f9dff",
        "blue-strong": "#7db4ff",
        "sidebar": "rgba(12,20,36,.98)",
        "sidebar-line": "#1c2a43",
        "card": "rgba(17,28,48,.92)",
        "card-line": "#25365a",
        "shadow": "0 8px 26px rgba(0,0,0,.35)",
        "user-bg": "linear-gradient(105deg,#15305a,#12284b)",
        "user-line": "#24457a",
        "chip": "rgba(17,28,48,.85)",
        "chip-line": "#25365a",
        "hover": "#13223d",
        "active": "#16305a",
        "input": "#0f1a2e",
        "avatar": "#1d3a6b",
        "avatar-fg": "#9cc7ff",
        "ok-bg": "#0e2d24",
        "ok-fg": "#5fe0a8",
        "ok-line": "#1b5642",
        "ok-dot": "#0aa968",
        "warn-bg": "#33270c",
        "warn-fg": "#f0c060",
        "warn-line": "#5c4614",
        "warn-dot": "#e39a14",
        "bad-bg": "#3a1714",
        "bad-fg": "#ff9a90",
        "bad-line": "#66302b",
        "bad-dot": "#d9534f",
    },
}

# Attention : ne pas masquer le header Streamlit, il contient le bouton qui
# rouvre la sidebar quand elle est repliée.
CSS = """
html, body, [class*="css"] {
    font-family: "Segoe UI", Inter, system-ui, Arial, sans-serif;
}

.stApp {
    color: var(--text);
    background:
        radial-gradient(circle at 69% 0%, var(--glow1), transparent 29%),
        radial-gradient(circle at 89% 55%, var(--glow2), transparent 31%),
        var(--bg);
}

#MainMenu, footer { visibility: hidden; }

[data-testid="stHeader"] { background: transparent !important; }

[data-testid="stSidebarCollapsedControl"] {
    display: flex !important;
    visibility: visible !important;
    z-index: 100000 !important;
}

[data-testid="stBottom"],
[data-testid="stBottom"] > div { background: transparent !important; }

.block-container {
    position: relative;
    max-width: 1180px;
    padding: 1.35rem 2rem 6.8rem;
}

[data-testid="stMarkdownContainer"] { color: var(--text); }

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] {
    width: 334px !important;
    min-width: 334px !important;
    background: var(--sidebar) !important;
    border-right: 1px solid var(--sidebar-line);
}
[data-testid="stSidebar"] > div:first-child { width: 334px !important; }
[data-testid="stSidebar"] > div:first-child,
[data-testid="stSidebarContent"] { background: transparent !important; }
[data-testid="stSidebar"] .block-container { padding: 1.2rem 1rem 1rem !important; }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: .3rem; }
[data-testid="stSidebar"] hr { border-color: var(--sidebar-line); margin: .8rem 0; }

.brand { display: flex; align-items: center; gap: .75rem; margin: .05rem .25rem 1.1rem; }
.brand-star { color: var(--blue); font-size: 2rem; line-height: 1; }
.brand-title { color: var(--title); font-size: 1.3rem; font-weight: 760; letter-spacing: -.025em; }
.brand-subtitle { color: var(--muted); font-size: .76rem; margin-top: .2rem; }

.sidebar-section { color: var(--muted); font-size: .82rem; font-weight: 600; margin: 1rem .3rem .4rem; }

.conversation-time { margin: -.2rem 0 .25rem .45rem; color: var(--soft); font-size: .64rem; }

.empty-history {
    margin: .5rem .25rem 1rem; padding: .8rem;
    border: 1px dashed var(--card-line); border-radius: 10px;
    color: var(--soft); font-size: .74rem; background: var(--card);
}

/* Bouton « Nouvelle conversation » : carte blanche + pastille bleue « + » */
[class*="st-key-new_chat"] button {
    position: relative;
    min-height: 48px !important;
    justify-content: center !important;
    border: 1px solid var(--chip-line) !important;
    border-radius: 12px !important;
    background: var(--chip) !important;
    box-shadow: 0 4px 14px rgba(26,59,101,.07) !important;
    color: var(--title) !important;
    font-weight: 600 !important;
}
[class*="st-key-new_chat"] button [data-testid="stIconMaterial"] {
    position: absolute; left: .55rem; top: 50%; transform: translateY(-50%);
    display: grid !important; place-items: center;
    width: 30px; height: 30px; border-radius: 8px;
    background: var(--blue); color: #fff !important; font-size: 1.25rem !important;
}

/* Lignes de navigation (Accueil, À propos, Documentation, Déconnexion) */
[data-testid="stSidebar"] [class*="st-key-nav_"] button,
[data-testid="stSidebar"] [class*="st-key-navactive_"] button,
[data-testid="stSidebar"] [data-testid="stLinkButton"] a {
    min-height: 42px; width: 100%;
    justify-content: flex-start !important; gap: .7rem;
    padding: .4rem .75rem !important;
    border: 0 !important; border-radius: 10px !important;
    background: transparent !important; box-shadow: none !important;
    color: var(--text) !important;
    font-size: .86rem !important; font-weight: 500 !important;
    text-decoration: none !important;
}
[data-testid="stSidebar"] [class*="st-key-nav_"] button:hover,
[data-testid="stSidebar"] [data-testid="stLinkButton"] a:hover {
    background: var(--hover) !important; color: var(--blue-strong) !important;
}
[data-testid="stSidebar"] [class*="st-key-navactive_"] button {
    background: var(--active) !important; color: var(--blue-strong) !important;
}
[data-testid="stSidebar"] button p { color: inherit !important; }
[data-testid="stSidebar"] [data-testid="stIconMaterial"] { color: var(--blue) !important; }

/* Historique */
[data-testid="stSidebar"] [class*="st-key-conversation_"] button,
[data-testid="stSidebar"] [class*="st-key-convactive_"] button {
    width: 100% !important; min-height: 30px !important;
    padding: .2rem .45rem !important;
    border: 0 !important; border-radius: 8px !important;
    background: transparent !important; box-shadow: none !important;
    color: var(--title) !important;
    font-size: .8rem !important; font-weight: 550 !important;
    justify-content: flex-start !important; text-align: left !important;
}
[data-testid="stSidebar"] [class*="st-key-conversation_"] button:hover {
    color: var(--blue-strong) !important; background: var(--hover) !important;
}
[data-testid="stSidebar"] [class*="st-key-convactive_"] button {
    color: var(--blue-strong) !important; background: var(--active) !important;
}
[data-testid="stSidebar"] [class*="st-key-manage_"] button {
    min-height: 28px !important; height: 28px !important; width: 28px !important;
    padding: 0 !important; border: 0 !important;
    background: transparent !important; box-shadow: none !important;
    color: var(--soft) !important;
}

.user-row {
    display: flex; align-items: center; gap: .7rem;
    padding: .35rem .3rem; color: var(--text); font-size: .76rem;
}
.user-avatar {
    flex: 0 0 auto; display: grid; place-items: center;
    width: 30px; height: 30px; border-radius: 50%;
    color: #fff; background: #164fa3; font-size: .72rem; font-weight: 700;
}
.user-mail { overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }

/* ---------- Bascule clair / sombre ---------- */
[class*="st-key-theme_bar"] {
    position: absolute; top: .45rem; right: 1.2rem;
    width: 96px; z-index: 5;
}
[class*="st-key-theme_"] button,
[class*="st-key-themeon_"] button {
    min-height: 36px !important; height: 36px; padding: 0 !important;
    border: 1px solid var(--chip-line) !important; border-radius: 10px !important;
    background: var(--chip) !important; box-shadow: none !important;
    color: var(--soft) !important; font-size: 1rem !important;
}
[class*="st-key-themeon_"] button {
    background: var(--active) !important; color: var(--blue) !important;
    border-color: var(--blue) !important;
}

/* ---------- Hero ---------- */
.hero { text-align: center; padding: .3rem 1rem 1.2rem; }
.hero h1 {
    margin: 0; padding: 0; color: var(--title);
    font-size: 3.55rem; line-height: 1.05; letter-spacing: -.045em; font-weight: 800;
}
.hero-tagline { margin-top: .52rem; color: var(--muted); font-size: 1.02rem; }
.hero-description {
    max-width: 760px; margin: 1.25rem auto 0;
    color: var(--muted); font-size: .98rem; line-height: 1.55;
}

/* Les <div> ouverts dans un st.markdown ne contiennent pas les widgets qui
   suivent : on cible donc les chips via la clé du bouton. */
[class*="st-key-suggestion_"] button {
    min-height: 46px !important;
    border: 1px solid var(--chip-line) !important; border-radius: 12px !important;
    background: var(--chip) !important; box-shadow: none !important;
    color: var(--title) !important; font-size: .84rem !important; font-weight: 500 !important;
}
[class*="st-key-suggestion_"] button:hover {
    border-color: var(--blue) !important; color: var(--blue-strong) !important;
}
[class*="st-key-suggestion_"] button [data-testid="stIconMaterial"] { color: var(--blue) !important; }

/* ---------- Chat ---------- */
[data-testid="stChatMessageAvatarAssistant"],
[data-testid="stChatMessageAvatarCustom"] { display: none !important; }

[data-testid="stChatMessageAvatarUser"] {
    display: flex !important; flex: 0 0 auto;
    width: 40px !important; height: 40px !important; border-radius: 50% !important;
    background: var(--avatar) !important;
}
[data-testid="stChatMessageAvatarUser"],
[data-testid="stChatMessageAvatarUser"] * {
    color: var(--avatar-fg) !important; fill: var(--avatar-fg) !important;
}

[data-testid="stChatMessage"] {
    border: 0 !important; background: transparent !important; box-shadow: none !important;
    padding: .3rem 0 !important; margin: 0 0 .7rem !important;
}
[data-testid="stChatMessageContent"] { width: 100% !important; padding-left: 0 !important; }

/* Message utilisateur : à droite, bulle bleutée, avatar rond à droite */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    flex-direction: row-reverse; align-items: center; gap: .8rem;
    width: fit-content; max-width: 80%; margin-left: auto !important;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"])
[data-testid="stChatMessageContent"] {
    width: auto !important; padding: .9rem 1.15rem !important;
    border: 1px solid var(--user-line) !important; border-radius: 14px !important;
    background: var(--user-bg) !important;
}

/* Message assistant : carte large */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"])
[data-testid="stChatMessageContent"] {
    padding: 1.05rem 1.2rem !important;
    border: 1px solid var(--card-line) !important; border-radius: 15px !important;
    background: var(--card) !important; box-shadow: var(--shadow) !important;
}

.assistant-name { display: inline-block; margin-bottom: .4rem; color: var(--blue); font-size: .92rem; font-weight: 720; }

.decision-card {
    display: inline-flex; align-items: center; gap: .45rem;
    margin: .1rem 0 .7rem; padding: .28rem .75rem .28rem .35rem;
    border-radius: 999px; font-size: .74rem; font-weight: 600;
}
.decision-dot {
    display: grid; place-items: center; width: 18px; height: 18px;
    border-radius: 50%; color: #fff; font-size: .62rem; font-weight: 800;
}
.decision-card.recommend { color: var(--ok-fg); background: var(--ok-bg); border: 1px solid var(--ok-line); }
.decision-card.recommend .decision-dot { background: var(--ok-dot); }
.decision-card.clarify { color: var(--warn-fg); background: var(--warn-bg); border: 1px solid var(--warn-line); }
.decision-card.clarify .decision-dot { background: var(--warn-dot); }
.decision-card.abstain { color: var(--bad-fg); background: var(--bad-bg); border: 1px solid var(--bad-line); }
.decision-card.abstain .decision-dot { background: var(--bad-dot); }

.sources-title {
    margin: 1rem 0 .5rem; padding-top: .9rem;
    border-top: 1px solid var(--card-line);
    color: var(--title); font-size: 1.05rem; font-weight: 760;
}
.source-card {
    display: block; min-height: 74px; padding: .6rem .75rem;
    border: 1px solid var(--card-line); border-radius: 12px;
    color: var(--title) !important; background: var(--card);
    text-decoration: none !important;
}
.source-card:hover { border-color: var(--blue); }
.source-head { display: flex; align-items: center; gap: .4rem; color: var(--blue); font-size: .7rem; font-weight: 700; }
.source-head svg { flex: 0 0 auto; }
.source-name { margin-top: .22rem; font-size: .76rem; font-weight: 700; line-height: 1.25; }
.source-section {
    margin-top: .22rem; color: var(--muted); font-size: .66rem;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

/* ---------- Zone de saisie ---------- */
[data-testid="stChatInput"] {
    border: 1px solid var(--card-line) !important; border-radius: 16px !important;
    background: var(--input) !important;
    box-shadow: 0 10px 28px rgba(30,62,103,.08) !important;
}
[data-testid="stChatInput"]:focus-within { border-color: var(--blue) !important; }
[data-testid="stChatInput"] textarea {
    color: var(--text) !important; background: transparent !important;
}
[data-testid="stChatInput"] textarea::placeholder { color: var(--muted) !important; }
[data-testid="stChatInputSubmitButton"] {
    background: var(--blue) !important; color: #fff !important; border-radius: 10px !important;
}
[data-testid="stChatInputSubmitButton"]:disabled { opacity: .45; }

/* ---------- Widgets natifs (surtout utiles en thème sombre) ---------- */
[data-baseweb="input"], [data-baseweb="base-input"] { background: var(--input) !important; }
input, textarea { color: var(--text) !important; }
[data-testid="stExpander"] { border-color: var(--card-line) !important; background: var(--card); }
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary p { color: var(--text) !important; }

@media (max-width: 900px) {
    [data-testid="stSidebar"] { width: 280px !important; min-width: 280px !important; }
    [data-testid="stSidebar"] > div:first-child { width: 280px !important; }
    .block-container { padding-left: 1rem; padding-right: 1rem; }
    .hero h1 { font-size: 2.7rem; }
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) { max-width: 94%; }
}
"""


def build_css(theme_name: str) -> str:
    palette = PALETTES.get(theme_name, PALETTES["light"])
    variables = ";".join(f"--{key}:{value}" for key, value in palette.items())
    scheme = "dark" if theme_name == "dark" else "light"
    return f"<style>:root{{{variables};color-scheme:{scheme}}}{CSS}</style>"


st.markdown(build_css(st.session_state.theme), unsafe_allow_html=True)


# =============================================================================
# CONSTANTES ET HELPERS
# =============================================================================

ACTION_META = {
    "recommend": ("Recommandation documentée", "✓"),
    "clarify": ("Précision nécessaire", "?"),
    "abstain": ("Preuves insuffisantes", "–"),
}

SUGGESTIONS = [
    (
        "Warehouse ou Lakehouse ?",
        ":material/database:",
        "Notre équipe travaille en T-SQL avec des données structurées, des "
        "transactions multi-tables et Power BI. Faut-il utiliser un Warehouse "
        "ou un Lakehouse ?",
    ),
    (
        "Architecture medallion",
        ":material/layers:",
        "Propose une architecture Bronze, Silver et Gold dans Microsoft Fabric "
        "pour des fichiers et des données SQL, avec une consommation Power BI.",
    ),
    (
        "Spark et données variées",
        ":material/code:",
        "Nous traitons avec PySpark des données structurées et non structurées "
        "dans OneLake. Quel stockage Fabric faut-il privilégier ?",
    ),
]

LINK_ICON = (
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>'
    '<path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>'
)


def format_time(value: str | None) -> str:
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone()
        now = datetime.now().astimezone()
        delta = (now.date() - dt.date()).days
        if delta == 0:
            prefix = "Aujourd’hui"
        elif delta == 1:
            prefix = "Hier"
        else:
            prefix = dt.strftime("%d/%m/%Y")
        return f"{prefix}, {dt.strftime('%H:%M')}"
    except Exception:
        return ""


def publisher_name(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if host.endswith("learn.microsoft.com"):
        return "Microsoft Learn"
    return host or "Documentation"


def safe_url(url: str) -> str:
    """N'autorise que http(s) pour les liens injectés en HTML brut."""
    if urlparse(url).scheme in ("http", "https"):
        return url
    return "https://learn.microsoft.com/fabric/"


def conversation_export_text(title: str, messages: list[dict]) -> str:
    lines = [f"# {title}", "", "Export Doc-Sceptic", ""]
    for message in messages:
        role = "Vous" if message.get("role") == "user" else "Doc-Sceptic"
        lines.extend([f"## {role}", str(message.get("content") or "")])
        sources = message.get("sources") or []
        if sources:
            lines.extend(["", "Sources :"])
            for index, source in enumerate(sources, 1):
                title_value = source.get("title") or "Source"
                url_value = source.get("url") or ""
                lines.append(f"- [S{index}] {title_value} - {url_value}")
        lines.append("")
    return "\n".join(lines)


def render_brand() -> None:
    st.markdown(
        '<div class="brand"><div class="brand-star">✦</div><div>'
        '<div class="brand-title">Doc-Sceptic</div>'
        '<div class="brand-subtitle">Microsoft Fabric Advisor</div>'
        "</div></div>",
        unsafe_allow_html=True,
    )


def render_hero() -> None:
    st.markdown(
        '<div class="hero"><h1>Doc-Sceptic</h1>'
        '<div class="hero-tagline">Concevez, comparez, décidez. Avec des preuves.</div>'
        '<div class="hero-description">'
        "Je suis un conseiller d’architecture Microsoft Fabric. Je m’appuie sur la "
        "documentation officielle pour analyser vos besoins, proposer des "
        "recommandations et savoir aussi demander une précision ou m’abstenir "
        "quand les preuves sont insuffisantes."
        "</div></div>",
        unsafe_allow_html=True,
    )


def render_theme_toggle() -> None:
    current = st.session_state.theme
    with st.container(key="theme_bar"):
        col_light, col_dark = st.columns(2, gap="small")
        with col_light:
            if st.button(
                "☀",
                key="themeon_light" if current == "light" else "theme_light",
                help="Thème clair",
                use_container_width=True,
            ):
                st.session_state.theme = "light"
                st.rerun()
        with col_dark:
            if st.button(
                "☾",
                key="themeon_dark" if current == "dark" else "theme_dark",
                help="Thème sombre",
                use_container_width=True,
            ):
                st.session_state.theme = "dark"
                st.rerun()


def render_decision(action: str) -> None:
    meta = ACTION_META.get(action)
    if not meta:
        return
    label, dot = meta
    st.markdown(
        f'<div class="decision-card {escape(action)}">'
        f'<span class="decision-dot">{dot}</span>{escape(label)}</div>',
        unsafe_allow_html=True,
    )


def render_sources(sources: list[dict], message_id: str) -> None:
    if not sources:
        return

    st.markdown('<div class="sources-title">Sources</div>', unsafe_allow_html=True)
    visible = sources[:3]
    columns = st.columns(len(visible), gap="small")

    for index, (column, source) in enumerate(zip(columns, visible), 1):
        raw_url = safe_url(str(source.get("url") or "https://learn.microsoft.com/fabric/"))
        title = escape(str(source.get("title") or "Documentation Fabric"))
        section = str(source.get("section") or "").strip()
        meta = publisher_name(raw_url) + (f" · {section}" if section else "")
        url = escape(raw_url, quote=True)
        with column:
            st.markdown(
                f'<a class="source-card" href="{url}" target="_blank" '
                f'rel="noopener noreferrer" title="{title}">'
                f'<div class="source-head">{LINK_ICON}<span>[S{index}]</span></div>'
                f'<div class="source-name">{title}</div>'
                f'<div class="source-section">{escape(meta)}</div></a>',
                unsafe_allow_html=True,
            )

    if len(sources) > 3:
        with st.expander(f"Voir les {len(sources)} sources"):
            for index, source in enumerate(sources, 1):
                st.markdown(f"**[S{index}] {source.get('title') or 'Source'}**")
                st.caption(source.get("section") or "")
                st.markdown(source.get("text") or "")
                if source.get("url"):
                    st.link_button(
                        "Ouvrir la source",
                        source["url"],
                        key=f"source_{message_id}_{index}",
                    )


def render_user_message(message: dict) -> None:
    with st.chat_message("user"):
        st.markdown(message.get("content") or "")


def render_assistant_message(message: dict) -> None:
    action = message.get("action") or "chat"
    sources = message.get("sources") or []
    with st.chat_message("assistant"):
        st.markdown('<div class="assistant-name">Doc-Sceptic</div>', unsafe_allow_html=True)
        render_decision(action)
        st.markdown(message.get("content") or "")
        render_sources(sources, str(message.get("id") or "history"))


def safe_list_conversations(store: HistoryStore) -> tuple[list[dict], str | None]:
    try:
        items = store.list_conversations()
        return list(items or []), None
    except Exception as error:
        return [], str(error)


# =============================================================================
# SESSION ET AUTHENTIFICATION
# =============================================================================

settings = Settings()

if "sb" not in st.session_state:
    st.session_state.sb = anon_client(settings)
if "session" not in st.session_state:
    st.session_state.session = None
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None
if "show_home" not in st.session_state:
    st.session_state.show_home = True
if "show_about" not in st.session_state:
    st.session_state.show_about = False
if "manage_conversation_id" not in st.session_state:
    st.session_state.manage_conversation_id = None
if "agent" not in st.session_state:
    st.session_state.agent = None


if st.session_state.session is None:
    left, center, right = st.columns([1, 1.05, 1])
    with center:
        st.markdown("<br><br>", unsafe_allow_html=True)
        render_brand()
        st.header("Connexion")
        st.caption("Retrouve tes conversations et tes décisions d’architecture.")

        login_tab, signup_tab = st.tabs(["Se connecter", "Créer un compte"])

        with login_tab:
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Mot de passe", type="password", key="login_password")
            if st.button("Se connecter", type="primary", use_container_width=True):
                try:
                    response = st.session_state.sb.auth.sign_in_with_password(
                        {"email": email, "password": password}
                    )
                    st.session_state.session = response.session
                    st.session_state.agent = None
                    st.rerun()
                except Exception as error:
                    st.error(str(error))

        with signup_tab:
            signup_email = st.text_input("Email", key="signup_email")
            signup_password = st.text_input("Mot de passe", type="password", key="signup_password")
            if st.button("Créer le compte", use_container_width=True):
                try:
                    st.session_state.sb.auth.sign_up(
                        {"email": signup_email, "password": signup_password}
                    )
                    st.success("Compte créé. Confirme l’adresse si la validation email est activée.")
                except Exception as error:
                    st.error(str(error))

    st.stop()


user = st.session_state.session.user
history = HistoryStore(st.session_state.sb)

if st.session_state.agent is None:
    st.session_state.agent = DataArchitectureAgent(settings, st.session_state.sb)


# =============================================================================
# SIDEBAR ET HISTORIQUE
# =============================================================================

home_active = st.session_state.show_home or not st.session_state.conversation_id

with st.sidebar:
    render_brand()

    if st.button(
        "Nouvelle conversation",
        key="new_chat",
        icon=":material/add:",
        use_container_width=True,
    ):
        st.session_state.conversation_id = None
        st.session_state.pending_prompt = None
        st.session_state.show_home = True
        st.session_state.manage_conversation_id = None
        st.rerun()

    if st.button(
        "Accueil",
        key="navactive_home" if home_active else "nav_home",
        icon=":material/home:",
        use_container_width=True,
    ):
        st.session_state.conversation_id = None
        st.session_state.pending_prompt = None
        st.session_state.show_home = True
        st.session_state.manage_conversation_id = None
        st.rerun()

    st.markdown('<div class="sidebar-section">Conversations récentes</div>', unsafe_allow_html=True)

    conversations, history_error = safe_list_conversations(history)

    if history_error:
        st.error("Impossible de charger l’historique.")
        with st.expander("Détail technique"):
            st.code(history_error)
    elif not conversations:
        st.markdown(
            '<div class="empty-history">Aucune conversation enregistrée pour ce compte.<br>'
            "La première conversation apparaîtra ici après l’envoi d’une question.</div>",
            unsafe_allow_html=True,
        )

    for conversation in conversations:
        conversation_id_item = conversation["id"]
        title = str(conversation.get("title") or "Conversation")[:42]
        when = format_time(conversation.get("updated_at"))
        selected = (
            st.session_state.conversation_id == conversation_id_item
            and not st.session_state.show_home
        )
        prefix = "convactive" if selected else "conversation"

        col_title, col_action = st.columns([8.5, 1.5], gap="small")
        with col_title:
            if st.button(
                title,
                key=f"{prefix}_{conversation_id_item}",
                use_container_width=True,
            ):
                st.session_state.conversation_id = conversation_id_item
                st.session_state.show_home = False
                st.session_state.manage_conversation_id = None
                st.rerun()
        with col_action:
            if st.button("⋯", key=f"manage_{conversation_id_item}", help="Gérer la conversation"):
                current = st.session_state.manage_conversation_id
                st.session_state.manage_conversation_id = (
                    None if current == conversation_id_item else conversation_id_item
                )
                st.rerun()

        if when:
            st.markdown(f'<div class="conversation-time">{escape(when)}</div>', unsafe_allow_html=True)

        if st.session_state.manage_conversation_id == conversation_id_item:
            try:
                manage_messages = history.messages(conversation_id_item)
            except Exception as error:
                st.error(f"Lecture impossible : {error}")
                manage_messages = []

            export_text = conversation_export_text(title, manage_messages)
            action_a, action_b = st.columns(2, gap="small")
            with action_a:
                st.download_button(
                    "Télécharger",
                    data=export_text,
                    file_name=f"doc-sceptic-{conversation_id_item}.md",
                    mime="text/markdown",
                    key=f"download_{conversation_id_item}",
                    use_container_width=True,
                )
            with action_b:
                if st.button(
                    "Supprimer",
                    key=f"delete_{conversation_id_item}",
                    use_container_width=True,
                    type="secondary",
                ):
                    history.delete_conversation(conversation_id_item)
                    if st.session_state.conversation_id == conversation_id_item:
                        st.session_state.conversation_id = None
                        st.session_state.show_home = True
                    st.session_state.manage_conversation_id = None
                    st.rerun()

    st.markdown("<hr>", unsafe_allow_html=True)

    st.link_button(
        "Documentation",
        "https://learn.microsoft.com/fabric/",
        icon=":material/menu_book:",
        use_container_width=True,
    )

    if st.button("À propos", key="nav_about", icon=":material/info:", use_container_width=True):
        st.session_state.show_about = not st.session_state.show_about

    if st.session_state.show_about:
        st.info(
            "Doc-Sceptic analyse les contraintes d’un projet Microsoft Fabric, "
            "recherche des preuves dans la documentation indexée, puis recommande, "
            "demande une précision ou s’abstient."
        )

    st.markdown("<hr>", unsafe_allow_html=True)

    email_label = str(user.email or "Utilisateur")
    st.markdown(
        f'<div class="user-row"><span class="user-avatar">{escape(email_label[:1].upper())}</span>'
        f'<span class="user-mail">{escape(email_label)}</span></div>',
        unsafe_allow_html=True,
    )

    if st.button("Déconnexion", key="nav_logout", icon=":material/logout:", use_container_width=True):
        st.session_state.sb.auth.sign_out()
        st.session_state.session = None
        st.session_state.conversation_id = None
        st.session_state.agent = None
        st.rerun()


# =============================================================================
# CONTENU PRINCIPAL
# =============================================================================

render_theme_toggle()
render_hero()

suggestion_columns = st.columns(3, gap="medium")
for index, (column, (label, icon, suggestion)) in enumerate(zip(suggestion_columns, SUGGESTIONS)):
    with column:
        if st.button(label, key=f"suggestion_{index}", icon=icon, use_container_width=True):
            st.session_state.pending_prompt = suggestion
            st.rerun()

conversation_id = st.session_state.conversation_id

if conversation_id and not st.session_state.show_home:
    try:
        current_messages = history.messages(conversation_id)
        for message in current_messages:
            if message.get("role") == "user":
                render_user_message(message)
            else:
                render_assistant_message(message)
    except Exception as error:
        st.error(f"Impossible de charger cette conversation : {error}")

prompt = st.chat_input("Posez une autre question...")

if st.session_state.pending_prompt:
    prompt = st.session_state.pending_prompt
    st.session_state.pending_prompt = None

if prompt:
    try:
        if not conversation_id:
            conversation = history.create_conversation(prompt[:80], user.id)
            conversation_id = conversation["id"]
            st.session_state.conversation_id = conversation_id

        st.session_state.show_home = False

        history.save_message(
            conversation_id=conversation_id,
            user_id=user.id,
            role="user",
            content=prompt,
        )

        render_user_message({"content": prompt})

        with st.chat_message("assistant"):
            st.markdown('<div class="assistant-name">Doc-Sceptic</div>', unsafe_allow_html=True)
            with st.status("Analyse de la demande...", expanded=False) as status:
                result = st.session_state.agent.ask(prompt)
                status.update(label="Réponse prête", state="complete")

            render_decision(result.action)
            st.markdown(result.answer)
            source_payload = [source.model_dump() for source in result.citations]
            render_sources(source_payload, "new")

        assistant_message = history.save_message(
            conversation_id=conversation_id,
            user_id=user.id,
            role="assistant",
            content=result.answer,
            action=result.action,
            confidence=result.confidence,
            metadata={
                "requirements": result.requirements.model_dump(),
                "trace": result.trace,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        history.save_sources(assistant_message["id"], source_payload)

        # Le rerun recharge immédiatement l'historique depuis Supabase.
        st.rerun()

    except Exception as error:
        st.error(f"Erreur pendant le traitement : {error}")
