"""
Challenge - Sistema de Gestão e Visualização Operacional de Ativos Industriais
Aplicação Streamlit principal (entry point).

A arquitetura é desacoplada em camadas:
- src/backend  -> regras de negócio, persistência, simulação, conversão e
                  avaliação de saúde dos sensores
- src/frontend -> camada de apresentação (Streamlit), pode ser substituída por
                  Gradio/FastAPI sem afetar o backend
- src/config   -> configurações globais

Para rodar localmente:
    pip install -r requirements.txt
    streamlit run app.py
"""

import streamlit as st

from src.config.settings import APP_TITLE, APP_ICON, APP_DESCRIPTION
from src.frontend.components.sidebar import render_sidebar
from src.frontend.pages import alertas, consulta, cadastro, dados_brutos, dashboard


# --------------------------------------------------------------------------- #
# Configuração da página
# --------------------------------------------------------------------------- #
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": f"{APP_TITLE} - {APP_DESCRIPTION}",
    },
)

# --------------------------------------------------------------------------- #
# Estilo customizado (cores semânticas, espaçamentos, etc.)
# --------------------------------------------------------------------------- #
st.markdown(
    """
    <style>
        /* Reduz o padding superior do conteúdo principal */
        .block-container { padding-top: 2rem; padding-bottom: 2rem; }

        /* Botões da sidebar com aparência mais limpa */
        section[data-testid="stSidebar"] button { text-align: left; }

        /* Cores semânticas para badges de status */
        .badge-ativo       { background:#10b981; color:#fff; padding:2px 10px; border-radius:12px; font-size:0.8rem; }
        .badge-manutencao  { background:#f59e0b; color:#fff; padding:2px 10px; border-radius:12px; font-size:0.8rem; }
        .badge-inativo     { background:#6b7280; color:#fff; padding:2px 10px; border-radius:12px; font-size:0.8rem; }

        /* Cards de métricas com sombra sutil */
        div[data-testid="stMetric"] {
            background: rgba(255,255,255,0.02);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 8px;
            padding: 12px;
        }

        /* Headers das tabs */
        button[role="tab"] { font-weight: 500; }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------- #
# Estado da sessão (simples roteamento via session_state)
# --------------------------------------------------------------------------- #
if "page" not in st.session_state:
    st.session_state.page = "alertas"

if "selected_equipment_id" not in st.session_state:
    st.session_state.selected_equipment_id = None

if "tele_buster" not in st.session_state:
    st.session_state.tele_buster = 0


# --------------------------------------------------------------------------- #
# Sidebar (menu de navegação)
# --------------------------------------------------------------------------- #
render_sidebar()


# --------------------------------------------------------------------------- #
# Roteamento das páginas
# --------------------------------------------------------------------------- #
PAGES = {
    "alertas": alertas.render,
    "dashboard": dashboard.render,
    "consulta": consulta.render,
    "cadastro": cadastro.render,
    "dados_brutos": dados_brutos.render,
}

page_render = PAGES.get(st.session_state.page, alertas.render)
page_render()
