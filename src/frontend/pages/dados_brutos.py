"""
Página de Visualização de Dados Brutos.

Mostra as leituras dos sensores (já convertidas em unidades de engenharia)
e também os valores brutos do ADC para fins de diagnóstico.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.backend.converters import SensorConverter
from src.backend.repository import EquipamentoRepository
from src.backend.sensor_simulator import SensorSimulator
from src.config.settings import (
    TEMPERATURA_LIMITE_ALERTA,
    TEMPERATURA_LIMITE_BOM,
    VIBRACAO_LIMITE_ALERTA,
    VIBRACAO_LIMITE_BOM,
    VIBRACAO_LIMITE_CRITICO,
)


# --------------------------------------------------------------------------- #
# Helpers de cor semântica para st.metric (delta_color)
# --------------------------------------------------------------------------- #
def _cor_tensao(valor: float, nominal: float) -> str:
    desvio = abs(valor - nominal) / nominal if nominal else 0
    if desvio < 0.05:
        return "normal"
    if desvio < 0.10:
        return "off"
    return "inverse"


def _cor_corrente(valor: float, nominal: float) -> str:
    if nominal == 0:
        return "off"
    if valor < nominal * 1.10:
        return "normal"
    if valor < nominal * 1.20:
        return "off"
    return "inverse"


def _cor_temperatura(valor: float) -> str:
    if valor < TEMPERATURA_LIMITE_BOM:
        return "normal"
    if valor < TEMPERATURA_LIMITE_ALERTA:
        return "off"
    return "inverse"


def _cor_vibracao(valor: float) -> str:
    if valor < VIBRACAO_LIMITE_BOM:
        return "normal"
    if valor < VIBRACAO_LIMITE_ALERTA:
        return "off"
    return "inverse"


# --------------------------------------------------------------------------- #
# Cache (evita re-simular dados a cada interação trivial)
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def _gerar_dados_cached(equipamento_id: str, cache_buster: int, n_amostras: int) -> list:
    """
    Gera amostras simuladas. O `cache_buster` é só um inteiro que muda
    quando o usuário clica em "Atualizar leitura", forçando a recomputação.
    Passado sem underscore de propósito: no `st.cache_data` do Streamlit,
    parâmetros prefixados com `_` são ignorados no hash da chave de cache,
    então usá-los para "forçar" recomputação não funciona.
    """
    from src.backend.repository import EquipamentoRepository
    repo = EquipamentoRepository()
    eq = repo.buscar_por_id(equipamento_id)
    if eq is None:
        return []
    simulator = SensorSimulator()
    brutas = simulator.gerar_amostras(eq, n_amostras=n_amostras)
    return SensorConverter.converter_lote(brutas, eq)


# --------------------------------------------------------------------------- #
def render() -> None:
    st.title("📊 Visualização de Dados Brutos")
    st.caption(
        "Leituras dos sensores convertidas para unidades de engenharia (V, A, RPM, °C, mm/s). "
        "Em produção, esses dados virão de CLPs / sensores via Modbus, MQTT ou OPC-UA."
    )

    repo = EquipamentoRepository()
    equipamentos = repo.listar()

    if not equipamentos:
        st.info("📭 Cadastre ao menos um equipamento para visualizar dados de sensores.")
        if st.button("➕ Ir para o cadastro", type="primary"):
            st.session_state.page = "cadastro"
            st.session_state.selected_equipment_id = None
            st.rerun()
        return

    # -------------------------------------------------- Seleção do equipamento
    pre_selecionado = None
    if st.session_state.selected_equipment_id:
        pre_selecionado = next(
            (e for e in equipamentos if e.id == st.session_state.selected_equipment_id),
            None,
        )
    indice_inicial = equipamentos.index(pre_selecionado) if pre_selecionado else 0

    selecionado = st.selectbox(
        "Equipamento monitorado:",
        options=equipamentos,
        index=indice_inicial,
        format_func=lambda e: f"{e.tag}  ·  {e.modelo}  ·  {e.fabricante}",
    )
    st.session_state.selected_equipment_id = selecionado.id

    # ---- Resumo das nominais
    with st.expander("ℹ️ Especificações nominais (placa do equipamento)", expanded=False):
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Potência", f"{selecionado.potencia_kw:.1f} kW")
        c2.metric("Tensão Nominal", f"{selecionado.tensao_v:.0f} V")
        c3.metric("Corrente Nominal", f"{selecionado.corrente_nominal_a:.1f} A")
        c4.metric("Rotação Nominal", f"{selecionado.rotacao_nominal_rpm:,}".replace(",", "."))
        c5.metric("Frequência", f"{selecionado.frequencia_hz:.0f} Hz")

    # -------------------------------------------------- Controles
    col_a, col_b, col_c = st.columns([2, 2, 1])
    n_amostras = col_a.slider("Número de amostras", min_value=20, max_value=200, value=60, step=10)
    janela_seg = col_b.select_slider(
        "Janela de tempo (segundos por amostra)",
        options=[1, 2, 5, 10],
        value=1,
    )

    if "cache_buster" not in st.session_state:
        st.session_state.cache_buster = 0
    if col_c.button("🔄 Atualizar leitura", use_container_width=True, type="primary"):
        st.session_state.cache_buster += 1

    # -------------------------------------------------- Geração / conversão
    with st.spinner("Adquirindo dados dos sensores…"):
        amostras = _gerar_dados_cached(
            selecionado.id, st.session_state.cache_buster, n_amostras
        )

    if not amostras:
        st.error("Falha ao gerar leituras. Tente novamente.")
        return

    df = pd.DataFrame(amostras)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    st.markdown("---")

    # -------------------------------------------------- Última leitura (cards)
    st.subheader("📡 Última leitura")

    ultimo = df.iloc[-1]
    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Tensão",
        f"{ultimo['tensao_v']:.1f} V",
        delta=f"{ultimo['tensao_v'] - selecionado.tensao_v:+.1f} V vs nominal",
        delta_color=_cor_tensao(ultimo["tensao_v"], selecionado.tensao_v),
    )
    c2.metric(
        "Corrente",
        f"{ultimo['corrente_a']:.2f} A",
        delta=f"{ultimo['corrente_a'] - selecionado.corrente_nominal_a:+.2f} A vs nominal",
        delta_color=_cor_corrente(ultimo["corrente_a"], selecionado.corrente_nominal_a),
    )
    c3.metric(
        "Rotação",
        f"{ultimo['rpm']:.0f} RPM",
        delta=f"{ultimo['rpm'] - selecionado.rotacao_nominal_rpm:+.0f} RPM vs nominal",
    )
    c4.metric(
        "Temperatura",
        f"{ultimo['temperatura_c']:.1f} °C",
        delta_color=_cor_temperatura(ultimo["temperatura_c"]),
    )
    c5.metric(
        "Vibração (RMS)",
        f"{ultimo['vibracao_mms']:.2f} mm/s",
        delta_color=_cor_vibracao(ultimo["vibracao_mms"]),
    )

    # Indicador de saúde geral simples (somente leitura, sem ML ainda)
    pior = max(
        ["normal", "off", "inverse"].index(_cor_tensao(ultimo["tensao_v"], selecionado.tensao_v)),
        ["normal", "off", "inverse"].index(_cor_corrente(ultimo["corrente_a"], selecionado.corrente_nominal_a)),
        ["normal", "off", "inverse"].index(_cor_temperatura(ultimo["temperatura_c"])),
        ["normal", "off", "inverse"].index(_cor_vibracao(ultimo["vibracao_mms"])),
    )
    if pior == 0:
        st.success("🟢 Operação dentro dos parâmetros normais.")
    elif pior == 1:
        st.warning("🟡 Atenção: ao menos uma grandeza está fora da faixa ideal — investigar.")
    else:
        st.error("🔴 Crítico: ao menos uma grandeza ultrapassou o limite seguro de operação.")

    st.markdown("---")

    # -------------------------------------------------- Tabs
    tab1, tab2, tab3 = st.tabs([
        "📈 Tendências",
        "📋 Dados em Engenharia",
        "🔢 Sinal Bruto (ADC)",
    ])

    # ---------- TAB 1: gráficos
    with tab1:
        fig = make_subplots(
            rows=3, cols=2,
            subplot_titles=(
                "Tensão (V)", "Corrente (A)",
                "Rotação (RPM)", "Temperatura (°C)",
                "Vibração (mm/s)", "",
            ),
            vertical_spacing=0.12,
            horizontal_spacing=0.08,
        )

        fig.add_trace(
            go.Scatter(x=df["timestamp"], y=df["tensao_v"], mode="lines",
                       line=dict(color="#3b82f6", width=2), name="Tensão"),
            row=1, col=1,
        )
        fig.add_hline(y=selecionado.tensao_v, line_dash="dash", line_color="gray",
                      annotation_text="Nominal", annotation_position="top right",
                      row=1, col=1)

        fig.add_trace(
            go.Scatter(x=df["timestamp"], y=df["corrente_a"], mode="lines",
                       line=dict(color="#f59e0b", width=2), name="Corrente"),
            row=1, col=2,
        )
        fig.add_hline(y=selecionado.corrente_nominal_a, line_dash="dash", line_color="gray",
                      row=1, col=2)

        fig.add_trace(
            go.Scatter(x=df["timestamp"], y=df["rpm"], mode="lines",
                       line=dict(color="#10b981", width=2), name="RPM"),
            row=2, col=1,
        )
        fig.add_hline(y=selecionado.rotacao_nominal_rpm, line_dash="dash", line_color="gray",
                      row=2, col=1)

        fig.add_trace(
            go.Scatter(x=df["timestamp"], y=df["temperatura_c"], mode="lines",
                       line=dict(color="#ef4444", width=2), name="Temperatura"),
            row=2, col=2,
        )
        fig.add_hline(y=TEMPERATURA_LIMITE_BOM, line_dash="dot", line_color="green", row=2, col=2)
        fig.add_hline(y=TEMPERATURA_LIMITE_ALERTA, line_dash="dot", line_color="red", row=2, col=2)

        fig.add_trace(
            go.Scatter(x=df["timestamp"], y=df["vibracao_mms"], mode="lines",
                       line=dict(color="#8b5cf6", width=2), name="Vibração"),
            row=3, col=1,
        )
        fig.add_hline(y=VIBRACAO_LIMITE_BOM, line_dash="dot", line_color="green",
                      annotation_text="ISO A/B", annotation_position="top left",
                      row=3, col=1)
        fig.add_hline(y=VIBRACAO_LIMITE_ALERTA, line_dash="dot", line_color="orange",
                      annotation_text="ISO B/C", annotation_position="top left",
                      row=3, col=1)
        fig.add_hline(y=VIBRACAO_LIMITE_CRITICO, line_dash="dot", line_color="red",
                      annotation_text="ISO C/D", annotation_position="top left",
                      row=3, col=1)

        fig.update_layout(
            height=720,
            showlegend=False,
            margin=dict(t=60, b=20, l=10, r=10),
            template="plotly_dark",
        )
        st.plotly_chart(fig, use_container_width=True)

    # ---------- TAB 2: tabela engenharia
    with tab2:
        st.caption("Valores convertidos para unidades de engenharia, prontos para análise e modelagem.")
        df_eng = df[[
            "timestamp", "tensao_v", "corrente_a", "rpm",
            "temperatura_c", "vibracao_mms",
        ]].copy()
        df_eng.columns = [
            "Timestamp", "Tensão (V)", "Corrente (A)",
            "RPM", "Temperatura (°C)", "Vibração (mm/s)",
        ]
        st.dataframe(df_eng, use_container_width=True, hide_index=True, height=400)

        col1, col2, _ = st.columns([1, 1, 3])
        col1.download_button(
            "📥 Baixar CSV",
            data=df_eng.to_csv(index=False).encode("utf-8"),
            file_name=f"dados_engenharia_{selecionado.tag}.csv",
            mime="text/csv",
            use_container_width=True,
        )
        col2.download_button(
            "📥 Baixar JSON",
            data=df_eng.to_json(orient="records", date_format="iso", indent=2).encode("utf-8"),
            file_name=f"dados_engenharia_{selecionado.tag}.json",
            mime="application/json",
            use_container_width=True,
        )

    # ---------- TAB 3: sinal bruto
    with tab3:
        st.caption("Valores como saem do conversor analógico-digital (ADC 12-bit, 0–4095). "
                   "Úteis para diagnóstico de hardware e calibração.")
        df_raw = df[[
            "timestamp", "tensao_raw", "corrente_raw", "rpm_raw",
            "temperatura_raw", "vibracao_raw",
        ]].copy()
        df_raw.columns = [
            "Timestamp", "Tensão (raw)", "Corrente (raw)",
            "RPM (raw)", "Temperatura (raw)", "Vibração (raw)",
        ]
        st.dataframe(df_raw, use_container_width=True, hide_index=True, height=400)

        with st.expander("📐 Como é feita a conversão?", expanded=False):
            st.markdown(
                f"""
Os sensores entregam um inteiro de 12 bits (**0 a 4095**) representando o valor analógico amostrado.
Cada grandeza é mapeada linearmente para sua faixa física, usando os parâmetros nominais
deste equipamento (`{selecionado.tag}`):

| Grandeza | Fórmula | Faixa |
|---|---|---|
| Tensão | `raw × (2 × {selecionado.tensao_v:.0f}) / 4095` | 0 a {2*selecionado.tensao_v:.0f} V |
| Corrente | `raw × (2 × {selecionado.corrente_nominal_a:.1f}) / 4095` | 0 a {2*selecionado.corrente_nominal_a:.1f} A |
| RPM | `raw × (2 × {selecionado.rotacao_nominal_rpm}) / 4095` | 0 a {2*selecionado.rotacao_nominal_rpm} |
| Temperatura | `raw × 150 / 4095` | 0 a 150 °C |
| Vibração | `raw × 10 / 4095` | 0 a 10 mm/s (ISO 10816) |

Manter os valores brutos arquivados é importante: caso a calibração do sensor mude
ou o range nominal seja ajustado, os dados podem ser reconvertidos sem perda.
                """,
            )

        col1, _ = st.columns([1, 4])
        col1.download_button(
            "📥 Baixar CSV (bruto)",
            data=df_raw.to_csv(index=False).encode("utf-8"),
            file_name=f"dados_brutos_{selecionado.tag}.csv",
            mime="text/csv",
            use_container_width=True,
        )
