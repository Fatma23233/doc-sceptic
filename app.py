from __future__ import annotations

from datetime import datetime, timezone
from html import escape

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


# =============================================================================
# STYLE
# Important : on ne masque pas le header Streamlit. Le bouton permettant de
# rouvrir la sidebar doit rester accessible si elle est repliée.
# =============================================================================

st.markdown(
    """
    <style>
    :root {
        --navy: #0b1f3d;
        --text: #132746;
        --muted: #607291;
        --blue: #1268db;
        --blue-2: #1683ff;
        --line: #dfe7f1;
        --sidebar: #f8fbff;
        --green: #0aa968;
        --green-soft: #eaf8f1;
    }

    html, body, [class*="css"] {
        font-family: "Segoe UI", Inter, Arial, sans-serif;
    }

    .stApp {
        color: var(--text);
        background:
            radial-gradient(circle at 69% 0%, rgba(221,235,255,.58), transparent 29%),
            radial-gradient(circle at 89% 55%, rgba(232,247,251,.45), transparent 31%),
            #ffffff;
    }

    #MainMenu, footer { visibility: hidden; }

    /* Le header reste présent pour conserver le bouton de sidebar. */
    [data-testid="stHeader"] {
        background: transparent !important;
    }

    [data-testid="stSidebarCollapsedControl"] {
        display: flex !important;
        visibility: visible !important;
        z-index: 100000 !important;
    }

    .block-container {
        max-width: 1180px;
        padding: 1.35rem 2rem 6.8rem;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        width: 334px !important;
        min-width: 334px !important;
        background: rgba(248,251,255,.98) !important;
        border-right: 1px solid #e3eaf3;
    }

    [data-testid="stSidebar"] > div:first-child {
        width: 334px !important;
    }

    [data-testid="stSidebar"] .block-container {
        padding: 1.2rem 1rem 1rem !important;
    }

    .brand {
        display: flex;
        align-items: center;
        gap: .75rem;
        margin: .05rem .25rem 1.15rem;
    }

    .brand-star {
        color: #1468d8;
        font-size: 2rem;
        line-height: 1;
    }

    .brand-title {
        color: var(--navy);
        font-size: 1.3rem;
        font-weight: 760;
        letter-spacing: -.025em;
    }

    .brand-subtitle {
        color: #516481;
        font-size: .76rem;
        margin-top: .2rem;
    }

    .sidebar-section {
        color: #526580;
        font-size: .82rem;
        font-weight: 650;
        margin: 1rem .3rem .5rem;
    }

    .conversation-time {
        margin: -.05rem 0 .35rem .3rem;
        color: #71819a;
        font-size: .64rem;
    }

    .empty-history {
        margin: .5rem .25rem 1rem;
        padding: .8rem;
        border: 1px dashed #cbd8e8;
        border-radius: 10px;
        color: #71819a;
        font-size: .74rem;
        background: rgba(255,255,255,.7);
    }

    [data-testid="stSidebar"] [class*="st-key-conversation_"] button {
        width: 100% !important;
        min-height: 30px !important;
        padding: .2rem .35rem !important;
        border: 0 !important;
        border-radius: 8px !important;
        background: transparent !important;
        box-shadow: none !important;
        color: var(--navy) !important;
        font-size: .76rem !important;
        font-weight: 550 !important;
        justify-content: flex-start !important;
        text-align: left !important;
    }

    [data-testid="stSidebar"] [class*="st-key-conversation_"] button:hover {
        color: #0e60c9 !important;
        background: #eef5ff !important;
    }

    [data-testid="stSidebar"] [class*="st-key-manage_"] button {
        min-height: 28px !important;
        height: 28px !important;
        width: 28px !important;
        padding: 0 !important;
        border: 0 !important;
        background: transparent !important;
        box-shadow: none !important;
        color: #7184a1 !important;
    }

    .user-row {
        position: relative;
        min-height: 34px;
        padding: .42rem 1.2rem .35rem 2.35rem;
        color: #183253;
        font-size: .7rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .user-row::before {
        content: "F";
        position: absolute;
        left: .2rem;
        top: .24rem;
        display: grid;
        place-items: center;
        width: 26px;
        height: 26px;
        border-radius: 50%;
        color: white;
        background: #164fa3;
        font-size: .68rem;
        font-weight: 700;
    }

    /* Hero */
    .hero {
        text-align: center;
        padding: .3rem 1rem 1.2rem;
    }

    .hero h1 {
        margin: 0;
        color: #071c3b;
        font-size: 3.55rem;
        line-height: 1.05;
        letter-spacing: -.045em;
    }

    .hero-tagline {
        margin-top: .52rem;
        color: #526684;
        font-size: 1.02rem;
    }

    .hero-description {
        max-width: 760px;
        margin: 1.25rem auto 0;
        color: #526887;
        font-size: .98rem;
        line-height: 1.55;
    }

    .suggestions [data-testid="stButton"] button {
        min-height: 44px !important;
        border: 1px solid #dce5f0 !important;
        border-radius: 13px !important;
        background: rgba(255,255,255,.88) !important;
        color: #10264a !important;
        font-size: .82rem !important;
        box-shadow: none !important;
    }

    /* Chat */
    [data-testid="stChatMessageAvatarUser"],
    [data-testid="stChatMessageAvatarAssistant"],
    [data-testid="stChatMessageAvatarCustom"] {
        display: none !important;
    }

    [data-testid="stChatMessage"] {
        border: 0 !important;
        background: transparent !important;
        box-shadow: none !important;
        padding: .3rem 0 !important;
        margin: 0 0 .7rem !important;
    }

    [data-testid="stChatMessageContent"] {
        width: 100% !important;
        padding-left: 0 !important;
    }

    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
        margin-left: 38% !important;
    }

    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"])
    [data-testid="stChatMessageContent"] {
        padding: .95rem 1.1rem !important;
        border: 1px solid #d2e3fb !important;
        border-radius: 14px !important;
        background: linear-gradient(105deg,#ebf4ff,#e5efff) !important;
    }

    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"])
    [data-testid="stChatMessageContent"] {
        padding: 1.05rem 1.18rem !important;
        border: 1px solid #dce4ee !important;
        border-radius: 15px !important;
        background: rgba(255,255,255,.94) !important;
        box-shadow: 0 8px 26px rgba(26,59,101,.05) !important;
    }

    .assistant-name {
        display: inline-block;
        margin-bottom: .38rem;
        color: #0866df;
        font-size: .91rem;
        font-weight: 720;
    }

    .decision-card {
        display: inline-flex;
        margin: .1rem 0 .7rem;
        padding: .34rem .68rem;
        border-radius: 999px;
    }

    .decision-card.recommend {
        color: #096546;
        background: var(--green-soft);
        border: 1px solid #c7ead7;
    }

    .decision-card.clarify {
        color: #9a5a02;
        background: #fff7e6;
        border: 1px solid #f0dca8;
    }

    .decision-card.abstain {
        color: #9d332b;
        background: #fff1ef;
        border: 1px solid #efcac5;
    }

    .sources-title {
        margin: 1rem 0 .45rem;
        padding-top: .9rem;
        border-top: 1px solid #e5eaf1;
        color: #0b2243;
        font-size: 1.08rem;
        font-weight: 760;
    }

    .source-card {
        display: block;
        min-height: 64px;
        padding: .55rem .68rem;
        border: 1px solid #dbe4ef;
        border-radius: 12px;
        color: #13294c !important;
        background: rgba(255,255,255,.96);
        text-decoration: none !important;
    }

    .source-index { color: #176bdd; font-size: .68rem; font-weight: 720; }
    .source-name { margin-top: .15rem; font-size: .72rem; font-weight: 650; }
    .source-section { margin-top: .12rem; color: #60738f; font-size: .64rem; }

    [data-testid="stChatInput"] {
        border: 1px solid #dce4ee !important;
        border-radius: 16px !important;
        background: white !important;
        box-shadow: 0 10px 28px rgba(30,62,103,.08) !important;
    }

    @media (max-width: 900px) {
        [data-testid="stSidebar"] { width: 280px !important; min-width: 280px !important; }
        [data-testid="stSidebar"] > div:first-child { width: 280px !important; }
        .block-container { padding-left: 1rem; padding-right: 1rem; }
        .hero h1 { font-size: 2.7rem; }
        [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
            margin-left: 10% !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# CONSTANTES ET HELPERS
# =============================================================================

ACTION_META = {
    "recommend": "✓  Recommandation documentée",
    "clarify": "?  Précision nécessaire",
    "abstain": "○  Preuves insuffisantes",
    "chat": "",
}

SUGGESTIONS = {
    "Warehouse ou Lakehouse ?": (
        "Notre équipe travaille en T-SQL avec des données structurées, des "
        "transactions multi-tables et Power BI. Faut-il utiliser un Warehouse "
        "ou un Lakehouse ?"
    ),
    "Architecture medallion": (
        "Propose une architecture Bronze, Silver et Gold dans Microsoft Fabric "
        "pour des fichiers et des données SQL, avec une consommation Power BI."
    ),
    "Spark et données variées": (
        "Nous traitons avec PySpark des données structurées et non structurées "
        "dans OneLake. Quel stockage Fabric faut-il privilégier ?"
    ),
}


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
        """
        <div class="brand">
            <div class="brand-star">✦</div>
            <div>
                <div class="brand-title">Doc-Sceptic</div>
                <div class="brand-subtitle">Microsoft Fabric Advisor</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_hero() -> None:
    st.markdown(
        """
        <div class="hero">
            <h1>Doc-Sceptic</h1>
            <div class="hero-tagline">Concevez, comparez, décidez. Avec des preuves.</div>
            <div class="hero-description">
                Je suis un conseiller d’architecture Microsoft Fabric. Je m’appuie sur la documentation officielle<br>
                pour analyser vos besoins, proposer des recommandations et savoir aussi demander une précision<br>
                ou m’abstenir quand les preuves sont insuffisantes.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_decision(action: str) -> None:
    label = ACTION_META.get(action, "")
    if not label:
        return
    st.markdown(
        f'<div class="decision-card {escape(action)}">{escape(label)}</div>',
        unsafe_allow_html=True,
    )


def render_sources(sources: list[dict], message_id: str) -> None:
    if not sources:
        return

    st.markdown('<div class="sources-title">Sources</div>', unsafe_allow_html=True)
    visible = sources[:3]
    columns = st.columns(len(visible), gap="small")

    for index, (column, source) in enumerate(zip(columns, visible), 1):
        title = escape(str(source.get("title") or "Documentation Fabric"))
        section = escape(str(source.get("section") or "Documentation"))
        url = escape(
            str(source.get("url") or "https://learn.microsoft.com/fabric/"),
            quote=True,
        )
        with column:
            st.markdown(
                f"""
                <a class="source-card" href="{url}" target="_blank" rel="noopener noreferrer">
                    <div class="source-index">▣ &nbsp; [S{index}]</div>
                    <div class="source-name">{title}</div>
                    <div class="source-section">{section}</div>
                </a>
                """,
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
        st.markdown(
            '<div class="assistant-name">Doc-Sceptic</div>',
            unsafe_allow_html=True,
        )
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
            password = st.text_input(
                "Mot de passe",
                type="password",
                key="login_password",
            )
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
            signup_password = st.text_input(
                "Mot de passe",
                type="password",
                key="signup_password",
            )
            if st.button("Créer le compte", use_container_width=True):
                try:
                    st.session_state.sb.auth.sign_up(
                        {"email": signup_email, "password": signup_password}
                    )
                    st.success(
                        "Compte créé. Confirme l’adresse si la validation email est activée."
                    )
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

with st.sidebar:
    render_brand()

    top_a, top_b = st.columns([7, 3], gap="small")
    with top_a:
        if st.button(
            "＋ Nouvelle conversation",
            key="new_chat",
            use_container_width=True,
        ):
            st.session_state.conversation_id = None
            st.session_state.pending_prompt = None
            st.session_state.show_home = True
            st.session_state.manage_conversation_id = None
            st.rerun()
    with top_b:
        if st.button("↻", key="refresh_history", help="Actualiser l’historique"):
            st.rerun()

    if st.button("⌂ Accueil", key="home_nav", use_container_width=True):
        st.session_state.conversation_id = None
        st.session_state.pending_prompt = None
        st.session_state.show_home = True
        st.session_state.manage_conversation_id = None
        st.rerun()

    st.markdown(
        '<div class="sidebar-section">Conversations récentes</div>',
        unsafe_allow_html=True,
    )

    conversations, history_error = safe_list_conversations(history)

    if history_error:
        st.error("Impossible de charger l’historique.")
        with st.expander("Détail technique"):
            st.code(history_error)
    elif not conversations:
        st.markdown(
            """
            <div class="empty-history">
                Aucune conversation enregistrée pour ce compte.<br>
                La première conversation apparaîtra ici après l’envoi d’une question.
            </div>
            """,
            unsafe_allow_html=True,
        )

    for conversation in conversations:
        conversation_id_item = conversation["id"]
        title = str(conversation.get("title") or "Conversation")[:42]
        when = format_time(conversation.get("updated_at"))
        selected = st.session_state.conversation_id == conversation_id_item
        display_title = f"● {title}" if selected else title

        col_title, col_action = st.columns([8.5, 1.5], gap="small")
        with col_title:
            if st.button(
                display_title,
                key=f"conversation_{conversation_id_item}",
                use_container_width=True,
            ):
                st.session_state.conversation_id = conversation_id_item
                st.session_state.show_home = False
                st.session_state.manage_conversation_id = None
                st.rerun()
        with col_action:
            if st.button(
                "⋯",
                key=f"manage_{conversation_id_item}",
                help="Gérer la conversation",
            ):
                current = st.session_state.manage_conversation_id
                st.session_state.manage_conversation_id = (
                    None if current == conversation_id_item else conversation_id_item
                )
                st.rerun()

        if when:
            st.markdown(
                f'<div class="conversation-time">{escape(when)}</div>',
                unsafe_allow_html=True,
            )

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
        "▣ Documentation",
        "https://learn.microsoft.com/fabric/",
        use_container_width=True,
    )

    if st.button("ⓘ À propos", key="about_doc_sceptic", use_container_width=True):
        st.session_state.show_about = not st.session_state.show_about

    if st.session_state.show_about:
        st.info(
            "Doc-Sceptic analyse les contraintes d’un projet Microsoft Fabric, "
            "recherche des preuves dans la documentation indexée, puis recommande, "
            "demande une précision ou s’abstient."
        )

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown(
        f'<div class="user-row">{escape(str(user.email or "Utilisateur"))}</div>',
        unsafe_allow_html=True,
    )

    if st.button("↪ Déconnexion", key="logout", use_container_width=True):
        st.session_state.sb.auth.sign_out()
        st.session_state.session = None
        st.session_state.conversation_id = None
        st.session_state.agent = None
        st.rerun()


# =============================================================================
# CONTENU PRINCIPAL
# =============================================================================

render_hero()

st.markdown('<div class="suggestions">', unsafe_allow_html=True)
suggestion_columns = st.columns(3, gap="medium")
for column, (label, suggestion) in zip(suggestion_columns, SUGGESTIONS.items()):
    with column:
        if st.button(label, key=f"suggestion_{label}", use_container_width=True):
            st.session_state.pending_prompt = suggestion
            st.rerun()
st.markdown("</div>", unsafe_allow_html=True)

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
            st.markdown(
                '<div class="assistant-name">Doc-Sceptic</div>',
                unsafe_allow_html=True,
            )
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

        history.save_sources(
            assistant_message["id"],
            source_payload,
        )

        # Le rerun recharge immédiatement l'historique depuis Supabase.
        st.rerun()

    except Exception as error:
        st.error(f"Erreur pendant le traitement : {error}")
