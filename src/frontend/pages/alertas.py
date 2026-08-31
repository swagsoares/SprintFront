"""
Painel de Alertas e Estados — página inicial da aplicação (Sprint 3).

Camada de inteligência operacional e apoio à decisão: mostra, antes mesmo da
seleção de um equipamento, o estado de saúde de todos os ativos, um resumo
textual gerado por IA/NLP (`src/backend/insights.py`) para cada um, apoio
inicial à decisão para a equipe de manutenção, e o histórico de eventos de
mudança de estado.

Arquitetura desacoplada: esta página não calcula saúde, resumo nem
recomendação — apenas consome `health.py`, `insights.py` e
`eventos_repository.py` e monta a UI. Trocar a heurística de resumo por um
modelo de NLP real, ou os limites de saúde por um modelo de ML, não exige
tocar neste arquivo.
"""

from __future__ import annotations

import streamlit as st

from src.backend import health
from src.backend.eventos_repository import Evento, EventoRepository
from src.backend.health import avaliar_leitura
from src.backend.insights import Insight, gerar_recomendacoes, gerar_resumo
from src.backend.repository import EquipamentoRepository
from src.backend.telemetria import TelemetriaService
from src.config.settings import PERFIL_CRITICO
from src.frontend.components.alert_card import render_alert_card
from src.frontend.components.event_timeline import render_event_timeline

_INTERVALOS = {"15 s": 15_000, "30 s": 30_000, "60 s": 60_000}


# --------------------------------------------------------------------------- #
def render() -> None:
    st.session_state.setdefault("tele_buster", 0)
    st.session_state.setdefault("alertas_nivel_anterior", {})
    st.session_state.setdefault("alertas_autorefresh_tick", 0)
    st.session_state.setdefault("alertas_novos_ids", set())

    st.title("🚨 Painel de Alertas e Estados")
    st.caption(
        "Visão geral da operação antes de abrir qualquer equipamento: estado "
        "de saúde de cada ativo, resumo automático da situação e apoio "
        "inicial à decisão para a equipe de manutenção."
    )

    repo = EquipamentoRepository()
    equipamentos = repo.listar()

    if not equipamentos:
        st.info("📭 Nenhum equipamento cadastrado. Cadastre um ativo para liberar o painel de alertas.")
        if st.button("➕ Ir para o cadastro", type="primary"):
            st.session_state.page = "cadastro"
            st.session_state.selected_equipment_id = None
            st.rerun()
        return

    _controles_atualizacao(equipamentos)
    st.markdown("---")

    diagnosticos = _diagnosticar_todos(equipamentos)
    _registrar_transicoes(diagnosticos)

    _resumo_geral(diagnosticos)
    st.markdown("---")

    _grade_de_cards(diagnosticos)

    st.markdown("---")
    st.subheader("📜 Histórico de eventos")
    st.caption("Transições de estado detectadas a cada atualização de dados.")
    eventos = EventoRepository().listar(limit=50)
    render_event_timeline(eventos)


# --------------------------------------------------------------------------- #
# Controles: botão de atualização + timer automático opcional
# --------------------------------------------------------------------------- #
def _controles_atualizacao(equipamentos) -> None:
    c1, c2, c3, c4 = st.columns([1.3, 1.3, 1.1, 1.6])

    if c1.button("🔄 Atualizar dados agora", type="primary", use_container_width=True,
                 help="Simula uma nova aquisição de leitura para todos os ativos "
                      "e reavalia os alertas."):
        _executar_atualizacao(equipamentos)
        st.rerun()

    if c2.button("🧪 Simular alerta (demo)", use_container_width=True,
                 help="Injeta uma leitura anômala em um ativo saudável, só para "
                      "demonstração — não altera o cadastro do equipamento."):
        _simular_anomalia_demo(equipamentos)
        st.rerun()

    auto = c3.toggle("⏱️ Auto", value=False, help="Atualização automática por timer.")
    intervalo_label = c4.selectbox("Intervalo", list(_INTERVALOS.keys()),
                                    index=1, label_visibility="collapsed",
                                    disabled=not auto)

    if auto:
        try:
            from streamlit_autorefresh import st_autorefresh
        except ImportError:
            st.warning(
                "⚠️ Pacote `streamlit-autorefresh` não encontrado — a "
                "atualização automática por timer está desabilitada nesta "
                "instalação. Use o botão manual, ou instale com "
                "`pip install streamlit-autorefresh`."
            )
        else:
            tick = st_autorefresh(interval=_INTERVALOS[intervalo_label], key="alertas_timer")
            if tick != st.session_state.alertas_autorefresh_tick:
                st.session_state.alertas_autorefresh_tick = tick
                if tick > 0:
                    _executar_atualizacao(equipamentos)


def _executar_atualizacao(equipamentos) -> None:
    """Simula uma nova leitura para cada ativo (fluxo normal de tempo real)."""
    servico = TelemetriaService()
    for eq in equipamentos:
        servico.nova_leitura(eq)
    st.session_state.tele_buster += 1


def _simular_anomalia_demo(equipamentos) -> None:
    """Injeta uma leitura crítica em um ativo hoje saudável, só para a demo."""
    servico = TelemetriaService()
    diagnosticos_atuais = _diagnosticar_todos(equipamentos)
    candidato = next(
        (eq for eq, diag in diagnosticos_atuais if diag.nivel_geral == health.NORMAL),
        equipamentos[0],
    )
    servico.nova_leitura(candidato, perfil_override=PERFIL_CRITICO)
    st.session_state.tele_buster += 1
    st.toast(f"🧪 Anomalia simulada em {candidato.tag} para demonstração.", icon="🧪")


# --------------------------------------------------------------------------- #
# Diagnóstico de todos os ativos
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def _historico_cached(equipamento_id: str, buster: int) -> list:
    """
    `buster` (sem underscore, de propósito) participa da chave de cache do
    Streamlit: parâmetros prefixados com `_` são ignorados no hash usado
    pelo `st.cache_data`, então usá-los para "forçar" recomputação não
    funciona — o cache nunca seria invalidado quando o valor muda.
    """
    repo = EquipamentoRepository()
    eq = repo.buscar_por_id(equipamento_id)
    if eq is None:
        return []
    return TelemetriaService().obter_historico(eq)


def _diagnosticar_todos(equipamentos):
    """Retorna [(equipamento, diagnostico), ...] ordenado por severidade (pior primeiro)."""
    pares = []
    for eq in equipamentos:
        leituras = _historico_cached(eq.id, st.session_state.tele_buster)
        if not leituras:
            continue
        diag = avaliar_leitura(leituras[-1], eq)
        pares.append((eq, diag))

    ordem = {health.CRITICO: 0, health.ALERTA: 1, health.NORMAL: 2}
    pares.sort(key=lambda par: ordem.get(par[1].nivel_geral, 3))
    return pares


# --------------------------------------------------------------------------- #
# Detecção de transição de estado + registro de evento
# --------------------------------------------------------------------------- #
def _registrar_transicoes(diagnosticos) -> None:
    repo_eventos = EventoRepository()
    anteriores = st.session_state.alertas_nivel_anterior
    novos_ids = set()

    for eq, diag in diagnosticos:
        nivel_novo = diag.nivel_geral
        nivel_antigo = anteriores.get(eq.id)

        if nivel_antigo is not None and nivel_antigo != nivel_novo:
            pior = max(diag.metricas, key=lambda m: (m.nivel == health.CRITICO, m.nivel == health.ALERTA))
            resumo = f"estado mudou de {health.ROTULOS[nivel_antigo]} para {health.ROTULOS[nivel_novo]}"
            evento = Evento(
                equipamento_id=eq.id,
                equipamento_tag=eq.tag,
                nivel_anterior=nivel_antigo,
                nivel_novo=nivel_novo,
                metrica_gatilho=pior.nome,
                resumo=resumo,
            )
            repo_eventos.registrar(evento)
            novos_ids.add(eq.id)

            icone = "🔴" if nivel_novo == health.CRITICO else ("🟡" if nivel_novo == health.ALERTA else "🟢")
            st.toast(f"{icone} {eq.tag}: {resumo}", icon=icone)

        anteriores[eq.id] = nivel_novo

    st.session_state.alertas_novos_ids = novos_ids


# --------------------------------------------------------------------------- #
# Resumo geral (KPIs)
# --------------------------------------------------------------------------- #
def _resumo_geral(diagnosticos) -> None:
    n_ok = sum(1 for _, d in diagnosticos if d.nivel_geral == health.NORMAL)
    n_alt = sum(1 for _, d in diagnosticos if d.nivel_geral == health.ALERTA)
    n_crit = sum(1 for _, d in diagnosticos if d.nivel_geral == health.CRITICO)

    c = st.columns(4)
    c[0].metric("⚙️ Ativos monitorados", len(diagnosticos))
    c[1].metric("🟢 Saudáveis", n_ok)
    c[2].metric("🟡 Em atenção", n_alt)
    c[3].metric("🔴 Críticos", n_crit)

    if n_crit:
        st.error(f"🔴 {n_crit} ativo(s) em estado crítico — priorize a leitura dos cards abaixo.")
    elif n_alt:
        st.warning(f"🟡 {n_alt} ativo(s) em atenção — acompanhe de perto.")
    else:
        st.success("🟢 Toda a operação está dentro dos parâmetros normais.")


# --------------------------------------------------------------------------- #
# Grade de cards de alerta
# --------------------------------------------------------------------------- #
def _grade_de_cards(diagnosticos) -> None:
    st.subheader("🗂️ Alertas por ativo")
    st.caption("Ordenado por urgência — críticos primeiro.")

    novos_ids = st.session_state.get("alertas_novos_ids", set())
    colunas = st.columns(2)
    for i, (eq, diag) in enumerate(diagnosticos):
        insight_resumo = gerar_resumo(eq, diag)
        recomendacoes = gerar_recomendacoes(diag)
        with colunas[i % 2]:
            render_alert_card(
                eq, diag,
                insight=Insight(resumo=insight_resumo, recomendacoes=recomendacoes),
                is_new_event=eq.id in novos_ids,
            )
