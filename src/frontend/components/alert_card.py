"""
Componente reutilizável: card de alerta operacional.

Usado pelo Painel de Alertas e Estados (página inicial) para exibir, de
forma padronizada, o estado de um ativo, o resumo gerado por IA/NLP
(`src/backend/insights.py`) e as recomendações de apoio à decisão.

Mantido isolado em `components/` — como já é convenção do projeto
(`sidebar.py`) — para poder ser reaproveitado em outras páginas
(ex.: uma futura lista de alertas dentro do próprio Dashboard).
"""

from __future__ import annotations

import streamlit as st

from src.backend import health
from src.backend.health import CORES, EMOJIS, ROTULOS, Diagnostico
from src.backend.insights import Insight
from src.backend.models import Equipamento

_BADGE_STATUS = {
    "Ativo": "badge-ativo",
    "Manutenção": "badge-manutencao",
    "Inativo": "badge-inativo",
}

_PRIORIDADE_ICONE = {health.NORMAL: "🟢", health.ALERTA: "🟡", health.CRITICO: "🔴"}


def _localizacao(eq: Equipamento) -> str:
    trilha = " › ".join(x for x in [eq.planta, eq.area] if x and x.strip())
    return trilha or "Localização não definida"


def render_alert_card(
    equipamento: Equipamento,
    diagnostico: Diagnostico,
    insight: Insight,
    *,
    is_new_event: bool = False,
) -> None:
    """Renderiza um card completo de alerta para um ativo."""
    nivel = diagnostico.nivel_geral
    cor = CORES[nivel]

    with st.container(border=True):
        # ---- Cabeçalho: TAG, modelo, localização, status
        c1, c2 = st.columns([4, 1])
        with c1:
            titulo = f"{EMOJIS[nivel]} {equipamento.tag} — {equipamento.modelo}"
            if is_new_event:
                titulo += "  🆕"
            st.markdown(f"#### {titulo}")
            st.caption(f"📍 {_localizacao(equipamento)}  ·  {equipamento.fabricante}")
        with c2:
            st.markdown(
                f"<div style='text-align:right'>"
                f"<span class='{_BADGE_STATUS.get(equipamento.status, 'badge-inativo')}'>"
                f"{equipamento.status}</span></div>",
                unsafe_allow_html=True,
            )

        # ---- Banner de estado geral (mesma linguagem visual do Dashboard)
        n_alertas = len(diagnostico.alertas)
        st.markdown(
            f"<div style='background:{cor}1f;border-left:6px solid {cor};"
            f"padding:10px 14px;border-radius:8px;margin:6px 0 10px 0;'>"
            f"<span style='font-weight:700;color:{cor};'>"
            f"Estado: {ROTULOS[nivel]}</span>"
            f"<span style='opacity:.85'> — {n_alertas} alerta(s) ativo(s)</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

        # ---- Resumo inteligente (NLP / heurística)
        fonte_label = (
            "🤖 Resumo gerado por modelo de NLP"
            if insight.resumo.origem == "modelo_nlp"
            else "🤖 Resumo automático (heurística local — estrutura pronta para NLP)"
        )
        st.markdown(
            f"<div style='background:rgba(255,255,255,0.035);border:1px solid "
            f"rgba(255,255,255,0.08);border-radius:8px;padding:10px 14px;margin-bottom:10px;'>"
            f"<div style='font-size:0.75rem;font-weight:600;opacity:.65;"
            f"text-transform:uppercase;letter-spacing:.03em;margin-bottom:4px;'>"
            f"{fonte_label}</div>"
            f"<div style='opacity:.92;line-height:1.45;'>{insight.resumo.texto}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

        # ---- Chips de métricas-chave
        chips = st.columns(5)
        for col, m in zip(chips, diagnostico.metricas):
            col.markdown(
                f"<div style='text-align:center;padding:6px 2px;border-radius:6px;"
                f"background:rgba(255,255,255,0.03);'>"
                f"<div style='font-size:0.68rem;opacity:.6'>{m.nome}</div>"
                f"<div style='font-weight:700;color:{CORES[m.nivel]}'>"
                f"{m.valor:.1f}{'' if m.unidade=='RPM' else ' ' + m.unidade}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        # ---- Apoio inicial à decisão
        if insight.recomendacoes:
            st.markdown("**🧭 Apoio à decisão**")
            for rec in insight.recomendacoes[:3]:
                st.markdown(
                    f"{_PRIORIDADE_ICONE.get(rec.prioridade, '⚪')} **{rec.titulo}** — "
                    f"{rec.descricao}"
                )

        # ---- Ação
        if st.button(
            "Ver dashboard completo →",
            key=f"alerta_abrir_{equipamento.id}",
            use_container_width=True,
        ):
            st.session_state.selected_equipment_id = equipamento.id
            st.session_state.page = "dashboard"
            st.rerun()
