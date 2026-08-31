"""
Dashboard Operacional de Ativos — Sprint 2.

Conecta o cadastro do ativo (TAG) à sua localização (planta / área) e aos
seus dados de telemetria, oferecendo a digitalização visual do estado dos
motores:

  • navegação hierárquica por planta e área;
  • painel de telemetria com os valores atuais dos sensores;
  • indicadores (gauges) e alertas com cores semânticas verde/amarelo/vermelho;
  • gráficos de séries temporais para análise de tendências;
  • a placa de identificação do motor com os campos extraídos por OCR.

Os gráficos consomem o histórico de telemetria persistido em disco
(`data/historico/`), derivado do cadastro técnico estruturado na Sprint 1.
"""

from datetime import timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.backend import health
from src.backend.health import CORES, EMOJIS, ROTULOS, avaliar_leitura
from src.backend.nameplate import extrair_campos_ocr, gerar_imagem_placa
from src.backend.repository import EquipamentoRepository
from src.backend.telemetria import TelemetriaService
from src.config.settings import (
    CORRENTE_FATOR_ALERTA,
    CORRENTE_FATOR_CRITICO,
    HISTORICO_DIAS,
    TEMPERATURA_LIMITE_ALERTA,
    TEMPERATURA_LIMITE_BOM,
    VIBRACAO_LIMITE_ALERTA,
    VIBRACAO_LIMITE_BOM,
    VIBRACAO_LIMITE_CRITICO,
)

# Rótulos para ativos sem planta/área preenchida
_SEM_PLANTA = "— Sem planta definida —"
_SEM_AREA = "— Sem área definida —"

# Períodos de visualização das séries temporais
_PERIODOS = {
    "Últimas 24 h": timedelta(hours=24),
    "Últimos 3 dias": timedelta(days=3),
    "Últimos 7 dias": timedelta(days=7),
    f"Tudo ({HISTORICO_DIAS} dias)": None,
}

# Cores translúcidas das faixas (gráficos e gauges)
_Z_VERDE = "rgba(16,185,129,0.13)"
_Z_AMBAR = "rgba(245,158,11,0.15)"
_Z_VERMELHO = "rgba(239,68,68,0.15)"
_G_VERDE = "rgba(16,185,129,0.35)"
_G_AMBAR = "rgba(245,158,11,0.40)"
_G_VERMELHO = "rgba(239,68,68,0.40)"

_BADGE = {
    "Ativo": "badge-ativo",
    "Manutenção": "badge-manutencao",
    "Inativo": "badge-inativo",
}


def _planta(eq) -> str:
    return eq.planta.strip() if eq.planta and eq.planta.strip() else _SEM_PLANTA


def _area(eq) -> str:
    return eq.area.strip() if eq.area and eq.area.strip() else _SEM_AREA


# --------------------------------------------------------------------------- #
# Funções com cache
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def _carregar_historico(equipamento_id: str, buster: int) -> pd.DataFrame:
    """Carrega (gerando e persistindo na 1ª vez) o histórico de telemetria.

    `buster` é passado sem underscore de propósito: no `st.cache_data` do
    Streamlit, parâmetros prefixados com `_` são ignorados no hash da chave
    de cache, então usá-los para "forçar" recomputação não funciona.
    """
    repo = EquipamentoRepository()
    eq = repo.buscar_por_id(equipamento_id)
    if eq is None:
        return pd.DataFrame()

    leituras = TelemetriaService().obter_historico(eq)
    df = pd.DataFrame(leituras)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)
    return df


@st.cache_data(show_spinner=False)
def _placa_png(equipamento_id: str, com_deteccoes: bool, marca: str):
    """Renderiza (com cache) a imagem da placa de identificação do ativo."""
    repo = EquipamentoRepository()
    eq = repo.buscar_por_id(equipamento_id)
    if eq is None:
        return None
    return gerar_imagem_placa(eq, com_deteccoes=com_deteccoes)


# --------------------------------------------------------------------------- #
# Página
# --------------------------------------------------------------------------- #
def render() -> None:
    st.session_state.setdefault("tele_buster", 0)

    st.title("🏭 Dashboard Operacional de Ativos")
    st.caption(
        "Visualização operacional da saúde dos motores: navegue por planta e "
        "área, acompanhe a telemetria em tempo real e identifique tendências "
        "de falha através dos gráficos."
    )

    repo = EquipamentoRepository()
    equipamentos = repo.listar()

    if not equipamentos:
        st.info("📭 Nenhum equipamento cadastrado. Cadastre um ativo para liberar o dashboard.")
        if st.button("➕ Ir para o cadastro", type="primary"):
            st.session_state.page = "cadastro"
            st.session_state.selected_equipment_id = None
            st.rerun()
        return

    planta, area, eq_sel, eqs_escopo = _barra_navegacao(equipamentos)
    st.markdown("---")

    if eq_sel is None:
        _painel_visao_geral(eqs_escopo, planta, area)
    else:
        _painel_ativo(eq_sel)


# --------------------------------------------------------------------------- #
# Navegação por planta / área (Requisito Funcional 1)
# --------------------------------------------------------------------------- #
def _barra_navegacao(equipamentos):
    """Renderiza a navegação Planta → Área → Equipamento e devolve a seleção."""
    # Pré-seleção "one-shot" ao chegar de outra página com um ativo escolhido.
    pre = None
    sel_id = st.session_state.get("selected_equipment_id")
    if sel_id and st.session_state.get("_dash_consumed_id") != sel_id:
        pre = next((e for e in equipamentos if e.id == sel_id), None)
        st.session_state["_dash_consumed_id"] = sel_id

    st.markdown("#### 🧭 Navegação por Planta / Área")
    c1, c2, c3 = st.columns(3)

    # --- Planta
    plantas = sorted({_planta(e) for e in equipamentos})
    alvo_planta = _planta(pre) if pre else st.session_state.get("dash_planta", plantas[0])
    if alvo_planta not in plantas:
        alvo_planta = plantas[0]
    planta = c1.selectbox("🏭 Planta", plantas, index=plantas.index(alvo_planta))
    st.session_state["dash_planta"] = planta

    eqs_planta = [e for e in equipamentos if _planta(e) == planta]

    # --- Área
    areas = ["Todas as áreas"] + sorted({_area(e) for e in eqs_planta})
    alvo_area = _area(pre) if pre else st.session_state.get("dash_area", "Todas as áreas")
    if alvo_area not in areas:
        alvo_area = "Todas as áreas"
    area = c2.selectbox("📍 Área", areas, index=areas.index(alvo_area))
    st.session_state["dash_area"] = area

    if area == "Todas as áreas":
        eqs_escopo = eqs_planta
    else:
        eqs_escopo = [e for e in eqs_planta if _area(e) == area]

    # --- Equipamento (TAG)
    # A seleção é rastreada pelo id do ativo (objetos Equipamento não são
    # "hasháveis", então o selectbox não preserva a escolha sozinho).
    opcoes = [None] + eqs_escopo
    alvo_eq_id = pre.id if pre else st.session_state.get("dash_equip_id")
    idx_eq = 0
    if alvo_eq_id:
        for i, e in enumerate(opcoes):
            if e is not None and e.id == alvo_eq_id:
                idx_eq = i
                break
    equip = c3.selectbox(
        "⚙️ Equipamento (TAG)",
        options=opcoes,
        index=idx_eq,
        format_func=lambda e: "🗺️ Visão geral da área" if e is None
        else f"{e.tag}  ·  {e.modelo}",
    )
    st.session_state["dash_equip_id"] = equip.id if equip else None

    return planta, area, equip, eqs_escopo


# --------------------------------------------------------------------------- #
# Visão geral da planta/área (grade de ativos)
# --------------------------------------------------------------------------- #
def _painel_visao_geral(equipamentos, planta, area):
    escopo = area if area != "Todas as áreas" else planta
    st.subheader(f"🗺️ Visão geral — {escopo}")
    st.caption("Estado de saúde de todos os ativos da seleção. "
               "Escolha um equipamento na navegação acima para abrir o dashboard detalhado.")

    if not equipamentos:
        st.info("Nenhum equipamento nesta seleção.")
        return

    # Diagnóstico da última leitura de cada ativo
    diags = []
    for e in equipamentos:
        df = _carregar_historico(e.id, st.session_state.tele_buster)
        d = avaliar_leitura(df.iloc[-1].to_dict(), e) if not df.empty else None
        diags.append((e, d))

    n_ok = sum(1 for _, d in diags if d and d.nivel_geral == health.NORMAL)
    n_alt = sum(1 for _, d in diags if d and d.nivel_geral == health.ALERTA)
    n_crit = sum(1 for _, d in diags if d and d.nivel_geral == health.CRITICO)

    c = st.columns(4)
    c[0].metric("⚙️ Ativos monitorados", len(equipamentos))
    c[1].metric("🟢 Saudáveis", n_ok)
    c[2].metric("🟡 Em atenção", n_alt)
    c[3].metric("🔴 Críticos", n_crit)
    st.markdown("")

    # Grade de cartões (3 por linha)
    colunas = st.columns(3)
    for i, (e, d) in enumerate(diags):
        nivel = d.nivel_geral if d else health.NORMAL
        with colunas[i % 3].container(border=True):
            st.markdown(f"#### {EMOJIS[nivel]} {e.tag}")
            st.caption(f"{e.modelo} · {e.tipo}")
            st.markdown(f"📍 {_area(e)}")
            st.markdown(
                f"<span style='color:{CORES[nivel]};font-weight:700'>"
                f"Saúde: {ROTULOS[nivel]}</span>"
                f"&nbsp;&nbsp;<span class='{_BADGE.get(e.status, 'badge-inativo')}'>"
                f"{e.status}</span>",
                unsafe_allow_html=True,
            )
            if d:
                te = d.metrica("temperatura_c")
                vi = d.metrica("vibracao_mms")
                m1, m2 = st.columns(2)
                m1.metric("🌡️ Temperatura", f"{te.valor:.0f} °C",
                          delta=ROTULOS[te.nivel], delta_color=health.delta_color(te.nivel))
                m2.metric("📳 Vibração", f"{vi.valor:.1f} mm/s",
                          delta=ROTULOS[vi.nivel], delta_color=health.delta_color(vi.nivel))
            if st.button("Abrir dashboard →", key=f"abrir_{e.id}", use_container_width=True):
                st.session_state.selected_equipment_id = e.id
                st.rerun()


# --------------------------------------------------------------------------- #
# Painel detalhado de um ativo
# --------------------------------------------------------------------------- #
def _painel_ativo(eq):
    df = _carregar_historico(eq.id, st.session_state.tele_buster)
    if df.empty:
        st.error("Não foi possível carregar o histórico de telemetria deste ativo.")
        return

    ultimo = df.iloc[-1].to_dict()
    diag = avaliar_leitura(ultimo, eq)

    _cabecalho_ativo(eq)
    _banner_saude(diag)

    tab1, tab2, tab3 = st.tabs([
        "📡 Telemetria & Status",
        "📈 Séries Temporais",
        "🪪 Cadastro Visual (OCR)",
    ])
    with tab1:
        _aba_telemetria(eq, df, diag)
    with tab2:
        _aba_series(eq, df)
    with tab3:
        _aba_cadastro_visual(eq)


def _cabecalho_ativo(eq):
    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(f"### ⚙️ {eq.tag} — {eq.modelo}")
            st.markdown(f"**Fabricante:** {eq.fabricante}  ·  **Tipo:** {eq.tipo}")
            trilha = " › ".join(
                x for x in [_planta(eq), _area(eq)] if not x.startswith("—")
            )
            local = trilha or "Localização não definida"
            if eq.localizacao:
                local += f"  ·  {eq.localizacao}"
            st.markdown(f"📍 {local}")
        with c2:
            st.markdown(
                f"<span class='{_BADGE.get(eq.status, 'badge-inativo')}'>{eq.status}</span>",
                unsafe_allow_html=True,
            )
            st.caption(f"Perfil de telemetria: **{eq.perfil_simulacao}**")


def _banner_saude(diag):
    nivel = diag.nivel_geral
    cor = CORES[nivel]
    mensagem = {
        health.NORMAL: "Ativo operando dentro dos parâmetros normais.",
        health.ALERTA: "Atenção: ao menos uma grandeza está fora da faixa ideal. "
                       "Recomenda-se inspeção.",
        health.CRITICO: "Crítico: limite operacional seguro ultrapassado. "
                        "Manutenção imediata recomendada.",
    }[nivel]
    n_alertas = len(diag.alertas)
    st.markdown(
        f"<div style='background:{cor}1f;border-left:6px solid {cor};"
        f"padding:14px 18px;border-radius:8px;margin:12px 0;'>"
        f"<span style='font-size:1.05rem;font-weight:700;color:{cor};'>"
        f"{EMOJIS[nivel]} Estado do ativo: {ROTULOS[nivel]}</span><br>"
        f"<span style='opacity:.88'>{mensagem} — {n_alertas} alerta(s) ativo(s).</span>"
        f"</div>",
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------- #
# Aba 1 — Telemetria & Status (Requisitos Funcionais 2 e 4)
# --------------------------------------------------------------------------- #
def _aba_telemetria(eq, df, diag):
    ts = pd.to_datetime(diag.timestamp)
    c1, c2 = st.columns([3, 1])
    c1.subheader("📡 Telemetria — última leitura")
    c1.caption(
        f"Leitura mais recente: {ts:%d/%m/%Y %H:%M}  ·  "
        f"{len(df)} amostras no histórico persistido"
    )
    if c2.button("🔄 Atualizar leitura", use_container_width=True, type="primary",
                 help="Simula a aquisição de uma nova leitura e a anexa ao histórico."):
        TelemetriaService().nova_leitura(eq)
        st.session_state.tele_buster += 1
        st.rerun()

    _cards_telemetria(diag, eq)

    st.markdown("---")
    st.subheader("🎯 Indicadores operacionais")
    st.caption("Faixas coloridas — verde: normal · amarelo: atenção · vermelho: crítico.")

    te = diag.metrica("temperatura_c")
    vi = diag.metrica("vibracao_mms")
    co = diag.metrica("corrente_a")
    g = st.columns(3)
    with g[0]:
        st.markdown("**🌡️ Temperatura**")
        st.plotly_chart(
            _gauge(te.valor, 150,
                   [(TEMPERATURA_LIMITE_BOM, _G_VERDE),
                    (TEMPERATURA_LIMITE_ALERTA, _G_AMBAR),
                    (150, _G_VERMELHO)],
                   te.nivel, " °C"),
            use_container_width=True, key="gauge_temp",
        )
    with g[1]:
        st.markdown("**📳 Vibração (RMS)**")
        st.plotly_chart(
            _gauge(vi.valor, 10,
                   [(VIBRACAO_LIMITE_BOM, _G_VERDE),
                    (VIBRACAO_LIMITE_ALERTA, _G_AMBAR),
                    (10, _G_VERMELHO)],
                   vi.nivel, " mm/s"),
            use_container_width=True, key="gauge_vib",
        )
    with g[2]:
        st.markdown("**⚡ Corrente**")
        fmax = eq.corrente_nominal_a * 2
        st.plotly_chart(
            _gauge(co.valor, fmax,
                   [(eq.corrente_nominal_a * CORRENTE_FATOR_ALERTA, _G_VERDE),
                    (eq.corrente_nominal_a * CORRENTE_FATOR_CRITICO, _G_AMBAR),
                    (fmax, _G_VERMELHO)],
                   co.nivel, " A"),
            use_container_width=True, key="gauge_cor",
        )

    st.markdown("---")
    _painel_alertas(diag)


def _cards_telemetria(diag, eq):
    """Cartões de leitura atual com cor semântica por grandeza (RF2 + RF4)."""
    m = {x.chave: x for x in diag.metricas}
    t, co, r = m["tensao_v"], m["corrente_a"], m["rpm"]
    te, vi = m["temperatura_c"], m["vibracao_mms"]

    c = st.columns(5)
    c[0].metric("🔌 Tensão", f"{t.valor:.1f} V",
                delta=f"{t.valor - eq.tensao_v:+.1f} V vs nominal",
                delta_color=health.delta_color(t.nivel))
    c[1].metric("⚡ Corrente", f"{co.valor:.1f} A",
                delta=f"{co.valor - eq.corrente_nominal_a:+.1f} A vs nominal",
                delta_color=health.delta_color(co.nivel))
    c[2].metric("🔄 Rotação", f"{r.valor:.0f} RPM",
                delta=f"{r.valor - eq.rotacao_nominal_rpm:+.0f} RPM vs nominal",
                delta_color=health.delta_color(r.nivel))
    c[3].metric("🌡️ Temperatura", f"{te.valor:.1f} °C",
                delta=ROTULOS[te.nivel], delta_color=health.delta_color(te.nivel))
    c[4].metric("📳 Vibração", f"{vi.valor:.2f} mm/s",
                delta=ROTULOS[vi.nivel], delta_color=health.delta_color(vi.nivel))


def _painel_alertas(diag):
    """Lista de alertas ativos derivados da última leitura (RF4)."""
    st.subheader("🚨 Alertas e status")
    alertas = sorted(diag.alertas, key=lambda mt: mt.nivel == health.CRITICO, reverse=True)
    if not alertas:
        st.success("🟢 Nenhum alerta ativo — todas as grandezas dentro dos limites operacionais.")
        return
    for mt in alertas:
        texto = f"**{mt.nome}: {mt.valor:.2f} {mt.unidade}** — {mt.detalhe}"
        if mt.nivel == health.CRITICO:
            st.error("🔴 " + texto)
        else:
            st.warning("🟡 " + texto)


def _gauge(valor, faixa_max, marcos, nivel, sufixo):
    """Cria um medidor (gauge) Plotly com faixas coloridas verde/amarelo/vermelho."""
    steps, prev = [], 0.0
    for limite, cor in marcos:
        steps.append({"range": [prev, limite], "color": cor})
        prev = limite

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=round(float(valor), 1),
        number={"suffix": sufixo, "font": {"size": 24, "color": "#f1f5f9"}},
        gauge={
            "axis": {"range": [0, faixa_max], "tickcolor": "#64748b",
                     "tickfont": {"size": 9, "color": "#94a3b8"}},
            "bar": {"color": CORES[nivel], "thickness": 0.32},
            "bgcolor": "rgba(0,0,0,0)",
            "borderwidth": 0,
            "steps": steps,
        },
    ))
    fig.update_layout(
        height=215, margin=dict(t=20, b=10, l=25, r=25),
        paper_bgcolor="rgba(0,0,0,0)", font={"color": "#cbd5e1"},
    )
    return fig


# --------------------------------------------------------------------------- #
# Aba 2 — Séries temporais (Requisito Funcional 3)
# --------------------------------------------------------------------------- #
def _aba_series(eq, df):
    st.subheader("📈 Séries temporais — análise de tendências")
    st.caption(
        "Evolução histórica das grandezas do motor, lida do histórico "
        "persistido em disco (data/historico/). Use para identificar "
        "tendências de degradação antes da falha."
    )

    c1, c2 = st.columns([3, 2])
    periodo = c1.radio("Período", list(_PERIODOS.keys()), index=3, horizontal=True)
    metrica = c2.selectbox(
        "Grandeza",
        ["Visão geral (todas)", "Temperatura", "Vibração", "Corrente", "Tensão", "Rotação"],
    )
    media = st.checkbox("Exibir média móvel (12 h)", value=True)

    # Filtro de período
    delta = _PERIODOS[periodo]
    if delta is not None:
        corte = df["timestamp"].max() - delta
        dfp = df[df["timestamp"] >= corte].copy()
    else:
        dfp = df.copy()

    if dfp.empty:
        st.info("Sem amostras no período selecionado.")
        return

    if metrica == "Visão geral (todas)":
        st.plotly_chart(_grafico_geral(dfp, eq), use_container_width=True, key="serie_geral")
    else:
        cfg = _config_metrica(metrica, eq)
        st.plotly_chart(_grafico_unico(dfp, cfg, media), use_container_width=True,
                        key="serie_unica")

    with st.expander("📋 Tabela de dados históricos do período"):
        tabela = dfp[["timestamp", "tensao_v", "corrente_a", "rpm",
                      "temperatura_c", "vibracao_mms"]].copy()
        tabela.columns = ["Timestamp", "Tensão (V)", "Corrente (A)", "RPM",
                          "Temperatura (°C)", "Vibração (mm/s)"]
        st.dataframe(tabela, use_container_width=True, hide_index=True, height=300)
        st.download_button(
            "📥 Baixar CSV do período",
            data=tabela.to_csv(index=False).encode("utf-8"),
            file_name=f"historico_{eq.tag}.csv",
            mime="text/csv",
        )


def _config_metrica(nome, eq):
    """Configuração (coluna, cor, faixas) de cada grandeza para o gráfico único."""
    INF = 1e6
    if nome == "Temperatura":
        return dict(col="temperatura_c", titulo="Temperatura (°C)", cor="#ef4444",
                    unidade="°C", nominal=None,
                    zonas=[(0, 70, _Z_VERDE), (70, 90, _Z_AMBAR), (90, INF, _Z_VERMELHO)])
    if nome == "Vibração":
        return dict(col="vibracao_mms", titulo="Vibração RMS (mm/s)", cor="#8b5cf6",
                    unidade="mm/s", nominal=None,
                    zonas=[(0, 2.8, _Z_VERDE), (2.8, 4.5, _Z_AMBAR), (4.5, INF, _Z_VERMELHO)])
    if nome == "Corrente":
        nom = eq.corrente_nominal_a
        return dict(col="corrente_a", titulo="Corrente (A)", cor="#f59e0b",
                    unidade="A", nominal=nom,
                    zonas=[(0, nom * 1.1, _Z_VERDE), (nom * 1.1, nom * 1.2, _Z_AMBAR),
                           (nom * 1.2, INF, _Z_VERMELHO)])
    if nome == "Tensão":
        nom = eq.tensao_v
        return dict(col="tensao_v", titulo="Tensão (V)", cor="#3b82f6",
                    unidade="V", nominal=nom,
                    zonas=[(0, nom * 0.9, _Z_VERMELHO), (nom * 0.9, nom * 0.95, _Z_AMBAR),
                           (nom * 0.95, nom * 1.05, _Z_VERDE),
                           (nom * 1.05, nom * 1.10, _Z_AMBAR), (nom * 1.10, INF, _Z_VERMELHO)])
    # Rotação
    nom = float(eq.rotacao_nominal_rpm)
    return dict(col="rpm", titulo="Rotação (RPM)", cor="#10b981",
                unidade="RPM", nominal=nom,
                zonas=[(0, nom * 0.9, _Z_VERMELHO), (nom * 0.9, nom * 0.95, _Z_AMBAR),
                       (nom * 0.95, nom * 1.05, _Z_VERDE),
                       (nom * 1.05, nom * 1.10, _Z_AMBAR), (nom * 1.10, INF, _Z_VERMELHO)])


def _grafico_unico(df, cfg, media):
    fig = go.Figure()
    for lo, hi, cor in cfg["zonas"]:
        fig.add_hrect(y0=lo, y1=hi, fillcolor=cor, line_width=0, layer="below")

    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=df[cfg["col"]], mode="lines", name=cfg["titulo"],
        line=dict(color=cfg["cor"], width=2),
    ))
    if media and len(df) > 6:
        mm = df[cfg["col"]].rolling(12, min_periods=1).mean()
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=mm, mode="lines", name="Média móvel (12 h)",
            line=dict(color="#e2e8f0", width=1.6, dash="dot"),
        ))
    if cfg["nominal"]:
        fig.add_hline(y=cfg["nominal"], line_dash="dash", line_color="#94a3b8",
                      annotation_text="Nominal", annotation_position="bottom right")

    fig.update_layout(
        height=430, template="plotly_dark", title=cfg["titulo"],
        yaxis_title=cfg["unidade"], xaxis_title="Tempo",
        margin=dict(t=55, b=40, l=10, r=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=1.04, x=0),
    )
    return fig


def _grafico_geral(df, eq):
    fig = make_subplots(
        rows=3, cols=2, vertical_spacing=0.13, horizontal_spacing=0.09,
        subplot_titles=("Temperatura (°C)", "Vibração (mm/s)",
                        "Corrente (A)", "Tensão (V)", "Rotação (RPM)", ""),
    )
    fig.add_trace(go.Scatter(x=df["timestamp"], y=df["temperatura_c"], mode="lines",
                             line=dict(color="#ef4444", width=1.8)), row=1, col=1)
    fig.add_hline(y=TEMPERATURA_LIMITE_BOM, line_dash="dot", line_color="#10b981", row=1, col=1)
    fig.add_hline(y=TEMPERATURA_LIMITE_ALERTA, line_dash="dot", line_color="#ef4444", row=1, col=1)

    fig.add_trace(go.Scatter(x=df["timestamp"], y=df["vibracao_mms"], mode="lines",
                             line=dict(color="#8b5cf6", width=1.8)), row=1, col=2)
    fig.add_hline(y=VIBRACAO_LIMITE_BOM, line_dash="dot", line_color="#10b981", row=1, col=2)
    fig.add_hline(y=VIBRACAO_LIMITE_ALERTA, line_dash="dot", line_color="#f59e0b", row=1, col=2)
    fig.add_hline(y=VIBRACAO_LIMITE_CRITICO, line_dash="dot", line_color="#ef4444", row=1, col=2)

    fig.add_trace(go.Scatter(x=df["timestamp"], y=df["corrente_a"], mode="lines",
                             line=dict(color="#f59e0b", width=1.8)), row=2, col=1)
    fig.add_hline(y=eq.corrente_nominal_a, line_dash="dash", line_color="#94a3b8", row=2, col=1)

    fig.add_trace(go.Scatter(x=df["timestamp"], y=df["tensao_v"], mode="lines",
                             line=dict(color="#3b82f6", width=1.8)), row=2, col=2)
    fig.add_hline(y=eq.tensao_v, line_dash="dash", line_color="#94a3b8", row=2, col=2)

    fig.add_trace(go.Scatter(x=df["timestamp"], y=df["rpm"], mode="lines",
                             line=dict(color="#10b981", width=1.8)), row=3, col=1)
    fig.add_hline(y=eq.rotacao_nominal_rpm, line_dash="dash", line_color="#94a3b8", row=3, col=1)

    fig.update_layout(
        height=680, showlegend=False, template="plotly_dark",
        margin=dict(t=50, b=20, l=10, r=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


# --------------------------------------------------------------------------- #
# Aba 3 — Cadastro visual / visão computacional (Requisito Funcional 5)
# --------------------------------------------------------------------------- #
def _aba_cadastro_visual(eq):
    st.subheader("🪪 Cadastro visual & visão computacional")
    st.caption(
        "A ficha técnica deste ativo foi obtida a partir da placa de "
        "identificação do motor por um pipeline de visão computacional (OCR). "
        "Abaixo, a imagem da placa associada à TAG e os campos extraídos."
    )

    col_img, col_dados = st.columns([3, 2])

    with col_img:
        com_det = st.toggle("Mostrar detecções da visão computacional", value=True)
        marca = eq.atualizado_em or eq.criado_em
        png = _placa_png(eq.id, com_det, str(marca))
        if png:
            st.image(png, width="stretch",
                     caption=f"Placa de identificação — ativo {eq.tag}")

    with col_dados:
        st.markdown(f"**Ativo vinculado:** `{eq.tag}` — {eq.modelo}")
        campos = extrair_campos_ocr(eq)
        conf_media = sum(c.confianca for c in campos) / len(campos)
        st.metric("Confiança média do OCR", f"{conf_media * 100:.1f}%")

        df_ocr = pd.DataFrame([
            {
                "Campo": c.rotulo,
                "Valor extraído": c.valor,
                "Confiança": c.confianca * 100,
                "Status": "⚠️ Revisar" if c.revisar else "✅ OK",
            }
            for c in campos
        ])
        st.dataframe(
            df_ocr, hide_index=True, use_container_width=True,
            column_config={
                "Confiança": st.column_config.ProgressColumn(
                    "Confiança OCR", min_value=0, max_value=100, format="%.1f%%",
                ),
            },
        )

        if any(c.revisar for c in campos):
            st.warning("⚠️ Um ou mais campos foram extraídos com baixa confiança e "
                       "devem ser conferidos manualmente na ficha técnica.")
        else:
            st.success("✅ Todos os campos extraídos com alta confiança.")

    st.info(
        "ℹ️ A imagem da placa é uma simulação gerada a partir do cadastro técnico "
        "(Sprint 1). Em produção, seria a fotografia real capturada em campo e "
        "processada pelo modelo de visão computacional."
    )
