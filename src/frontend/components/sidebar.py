"""Componente de sidebar (menu lateral). Reutilizável em todas as páginas."""

import streamlit as st

from src.backend.repository import EquipamentoRepository


def _nav_button(label: str, page: str, *, ativo: bool) -> None:
    """Botão de navegação que atualiza a página atual."""
    if st.button(
        label,
        use_container_width=True,
        type="primary" if ativo else "secondary",
    ):
        st.session_state.page = page
        if page != "dashboard":
            # O dashboard preserva a seleção; as demais páginas a redefinem.
            st.session_state.selected_equipment_id = None
        st.rerun()


def render_sidebar() -> None:
    repo = EquipamentoRepository()
    total = len(repo.listar())
    pagina = st.session_state.get("page", "dashboard")

    with st.sidebar:
        st.markdown("## ⚙️ Gestão de Ativos")
        st.caption("Sprint 2 — Visualização Operacional")
        st.markdown("---")

        st.markdown("### Navegação")

        _nav_button("🚨 Painel de Alertas", "alertas",
                    ativo=pagina == "alertas")
        _nav_button("🏭 Dashboard Operacional", "dashboard",
                    ativo=pagina == "dashboard")
        _nav_button("🏠 Consulta de Equipamentos", "consulta",
                    ativo=pagina == "consulta")
        _nav_button(
            "📝 Novo Cadastro", "cadastro",
            ativo=(pagina == "cadastro"
                   and st.session_state.get("selected_equipment_id") is None),
        )
        _nav_button("📊 Dados Brutos dos Sensores", "dados_brutos",
                    ativo=pagina == "dados_brutos")

        st.markdown("---")
        st.metric("Equipamentos cadastrados", total)

        st.markdown("---")
        with st.expander("🗺️ Sobre as Sprints", expanded=False):
            st.caption(
                "• **Sprint 1**: cadastro técnico e conversão de sinais  \n"
                "• **Sprint 2**: dashboards, séries temporais e alertas  \n"
                "• **Sprint 3**: Painel de Alertas e Estados, resumos por "
                "IA/NLP e apoio à decisão  \n"
                "• **Sprint 4**: modelo preditivo & estimativa de RUL  \n"
                "• **Sprint 5**: integração com sensores reais"
            )

        st.caption("FIAP Challenge • 2025")
