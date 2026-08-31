"""
Componente reutilizável: linha do tempo de eventos.

Renderiza a lista de transições de estado (Normal → Atenção → Crítico, ou
o inverso, quando o ativo se recupera) registradas pelo
`EventoRepository`. Reaproveitável em qualquer página que precise mostrar
histórico de eventos, mantendo o Painel de Alertas como único ponto que
decide *quando* um evento é registrado.
"""

from __future__ import annotations

from datetime import datetime
from typing import List

import streamlit as st

from src.backend.eventos_repository import Evento
from src.backend.health import ALERTA, CORES, CRITICO, EMOJIS, NORMAL

_ICONE_TRANSICAO = {
    (NORMAL, ALERTA): "⬆️",
    (NORMAL, CRITICO): "⬆️",
    (ALERTA, CRITICO): "⬆️",
    (CRITICO, ALERTA): "⬇️",
    (ALERTA, NORMAL): "⬇️",
    (CRITICO, NORMAL): "⬇️",
}


def render_event_timeline(eventos: List[Evento], *, altura: int = 360) -> None:
    """Renderiza a linha do tempo de eventos (mais recente primeiro)."""
    if not eventos:
        st.info(
            "📭 Nenhum evento registrado ainda. Eventos aparecem aqui quando o "
            "estado de um ativo muda (ex.: de Normal para Atenção ou Crítico) "
            "após uma atualização de dados."
        )
        return

    with st.container(height=altura, border=True):
        for ev in eventos:
            cor = CORES.get(ev.nivel_novo, "#94a3b8")
            seta = _ICONE_TRANSICAO.get((ev.nivel_anterior, ev.nivel_novo), "•")
            try:
                ts = datetime.fromisoformat(ev.timestamp).strftime("%d/%m %H:%M:%S")
            except ValueError:
                ts = ev.timestamp

            st.markdown(
                f"<div style='border-left:3px solid {cor};padding:4px 10px 4px 12px;"
                f"margin-bottom:8px;'>"
                f"<span style='opacity:.6;font-size:0.75rem'>{ts}</span><br>"
                f"<span style='font-weight:600'>{EMOJIS.get(ev.nivel_novo, '⚪')} "
                f"{ev.equipamento_tag}</span> "
                f"<span style='opacity:.75'>{seta} {ev.resumo}</span> "
                f"<span style='opacity:.55;font-size:0.78rem'>"
                f"— gatilho: {ev.metrica_gatilho}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
