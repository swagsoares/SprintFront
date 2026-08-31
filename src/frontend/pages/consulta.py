"""Página de Consulta — tela inicial com a lista de equipamentos cadastrados."""

import pandas as pd
import streamlit as st

from src.backend.historico_repository import HistoricoRepository
from src.backend.repository import EquipamentoRepository


def _badge_status(status: str) -> str:
    css_class = {
        "Ativo": "badge-ativo",
        "Manutenção": "badge-manutencao",
        "Inativo": "badge-inativo",
    }.get(status, "badge-inativo")
    return f'<span class="{css_class}">{status}</span>'


def render() -> None:
    st.title("🏠 Consulta de Equipamentos")
    st.caption("Selecione um equipamento para abrir sua ficha técnica ou inspecionar os dados de sensores.")

    repo = EquipamentoRepository()
    equipamentos = repo.listar()

    # ---------------------------------------------------------------- Métricas
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📦 Total cadastrado", len(equipamentos))
    col2.metric("🟢 Ativos", sum(1 for e in equipamentos if e.status == "Ativo"))
    col3.metric("🟡 Em manutenção", sum(1 for e in equipamentos if e.status == "Manutenção"))
    col4.metric("⚪ Inativos", sum(1 for e in equipamentos if e.status == "Inativo"))

    st.markdown("---")

    # ---------------------------------------------------------------- Vazio
    if not equipamentos:
        st.info("📭 Nenhum equipamento cadastrado ainda.")
        col_a, col_b = st.columns([1, 4])
        if col_a.button("➕ Cadastrar primeiro equipamento", type="primary", use_container_width=True):
            st.session_state.page = "cadastro"
            st.session_state.selected_equipment_id = None
            st.rerun()
        return

    # ---------------------------------------------------------------- Filtros
    with st.expander("🔍 Filtros", expanded=False):
        col1, col2, col3 = st.columns([2, 2, 1])
        filtro_busca = col1.text_input("Buscar por TAG, modelo ou fabricante", placeholder="Ex: MOT-001, WEG, W22…")
        filtro_status = col2.multiselect(
            "Status",
            options=["Ativo", "Manutenção", "Inativo"],
            default=["Ativo", "Manutenção", "Inativo"],
        )
        filtro_tipo = col3.multiselect(
            "Tipo",
            options=sorted({e.tipo for e in equipamentos}),
            default=sorted({e.tipo for e in equipamentos}),
        )

    busca = (filtro_busca or "").strip().lower()
    filtrados = [
        e for e in equipamentos
        if (
            not busca
            or busca in e.tag.lower()
            or busca in e.modelo.lower()
            or busca in e.fabricante.lower()
        )
        and e.status in filtro_status
        and e.tipo in filtro_tipo
    ]

    if not filtrados:
        st.warning("Nenhum equipamento encontrado com os filtros aplicados.")
        return

    # ---------------------------------------------------------------- Tabela
    st.subheader(f"📋 Equipamentos ({len(filtrados)})")

    df = pd.DataFrame(
        [
            {
                "TAG": e.tag,
                "Modelo": e.modelo,
                "Fabricante": e.fabricante,
                "Tipo": e.tipo,
                "Potência (kW)": e.potencia_kw,
                "Tensão (V)": e.tensao_v,
                "Corrente (A)": e.corrente_nominal_a,
                "RPM": e.rotacao_nominal_rpm,
                "Planta": e.planta or "—",
                "Área": e.area or "—",
                "Status": e.status,
            }
            for e in filtrados
        ]
    )

    st.dataframe(df, use_container_width=True, hide_index=True, height=320)

    st.markdown("---")

    # ---------------------------------------------------------------- Ações por equipamento
    st.subheader("🔧 Ações")

    selecionado = st.selectbox(
        "Selecione um equipamento:",
        options=[None] + filtrados,
        format_func=lambda e: "— escolha um equipamento —" if e is None else f"{e.tag}  ·  {e.modelo}  ·  {e.fabricante}",
    )

    if selecionado is None:
        st.info("ℹ️ Escolha um equipamento acima para liberar as ações de visualização e edição.")
        return

    # Card resumo
    with st.container(border=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"### {selecionado.tag} — {selecionado.modelo}")
            st.markdown(f"**Fabricante:** {selecionado.fabricante}  ·  **Tipo:** {selecionado.tipo}")
            if selecionado.localizacao:
                st.markdown(f"📍 {selecionado.localizacao}")
        with col2:
            st.markdown(_badge_status(selecionado.status), unsafe_allow_html=True)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Potência", f"{selecionado.potencia_kw:.1f} kW")
        c2.metric("Tensão", f"{selecionado.tensao_v:.0f} V")
        c3.metric("Corrente", f"{selecionado.corrente_nominal_a:.1f} A")
        c4.metric("Rotação", f"{selecionado.rotacao_nominal_rpm:,} RPM".replace(",", "."))

    # Botões de ação
    col1, col2, col3, col4 = st.columns(4)
    if col1.button("🏭 Abrir no Dashboard", use_container_width=True, type="primary"):
        st.session_state.selected_equipment_id = selecionado.id
        st.session_state.page = "dashboard"
        st.rerun()

    if col2.button("👁️ Ver / Editar Ficha", use_container_width=True):
        st.session_state.selected_equipment_id = selecionado.id
        st.session_state.page = "cadastro"
        st.rerun()

    if col3.button("📊 Dados Brutos", use_container_width=True):
        st.session_state.selected_equipment_id = selecionado.id
        st.session_state.page = "dados_brutos"
        st.rerun()

    # Exclusão com confirmação (human-in-the-loop)
    confirm_key = f"confirmar_exclusao_{selecionado.id}"
    if col4.button("🗑️ Excluir", use_container_width=True):
        st.session_state[confirm_key] = True

    if st.session_state.get(confirm_key, False):
        st.warning(f"⚠️ Tem certeza que deseja **excluir** o equipamento `{selecionado.tag}`? Esta ação não pode ser desfeita.")
        col_a, col_b = st.columns([1, 1])
        if col_a.button("✅ Sim, excluir definitivamente", type="primary", use_container_width=True):
            repo.excluir(selecionado.id)
            # Remove também o histórico de telemetria persistido do ativo.
            HistoricoRepository().excluir(selecionado.id)
            st.cache_data.clear()
            st.session_state.pop(confirm_key, None)
            st.success(f"Equipamento `{selecionado.tag}` excluído.")
            st.rerun()
        if col_b.button("❌ Cancelar", use_container_width=True):
            st.session_state.pop(confirm_key, None)
            st.rerun()
