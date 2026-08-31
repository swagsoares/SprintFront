"""
Motor de avaliação de saúde dos ativos.

Centraliza, em uma única camada de backend, as regras que classificam cada
grandeza medida em três níveis semânticos — normal / atenção / crítico — e
derivam o estado geral do equipamento.

Mantido fora da camada de UI para que o dashboard (Streamlit) e futuros
consumidores (API, serviço de alertas) compartilhem exatamente o mesmo
critério de classificação.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from src.backend.models import Equipamento
from src.config.settings import (
    CORRENTE_FATOR_ALERTA,
    CORRENTE_FATOR_CRITICO,
    ROTACAO_DESVIO_ALERTA,
    ROTACAO_DESVIO_CRITICO,
    TEMPERATURA_LIMITE_ALERTA,
    TEMPERATURA_LIMITE_BOM,
    TENSAO_DESVIO_ALERTA,
    TENSAO_DESVIO_CRITICO,
    VIBRACAO_LIMITE_ALERTA,
    VIBRACAO_LIMITE_BOM,
)

# Níveis semânticos --------------------------------------------------------- #
NORMAL = "normal"
ALERTA = "alerta"
CRITICO = "critico"

_ORDEM = {NORMAL: 0, ALERTA: 1, CRITICO: 2}

# Cores / rótulos / ícones associados a cada nível
CORES = {NORMAL: "#10b981", ALERTA: "#f59e0b", CRITICO: "#ef4444"}
ROTULOS = {NORMAL: "Normal", ALERTA: "Atenção", CRITICO: "Crítico"}
EMOJIS = {NORMAL: "🟢", ALERTA: "🟡", CRITICO: "🔴"}


def pior_nivel(*niveis: str) -> str:
    """Retorna o nível mais grave dentre os informados."""
    if not niveis:
        return NORMAL
    return max(niveis, key=lambda n: _ORDEM.get(n, 0))


def delta_color(nivel: str) -> str:
    """Traduz o nível para o parâmetro `delta_color` do st.metric."""
    return {NORMAL: "normal", ALERTA: "off", CRITICO: "inverse"}.get(nivel, "off")


# --------------------------------------------------------------------------- #
# Avaliadores por grandeza
# --------------------------------------------------------------------------- #
def _avaliar_desvio(valor: float, nominal: float, lim_alerta: float, lim_critico: float) -> str:
    """Classifica pelo desvio percentual em relação a um valor nominal."""
    if not nominal:
        return NORMAL
    desvio = abs(valor - nominal) / nominal
    if desvio >= lim_critico:
        return CRITICO
    if desvio >= lim_alerta:
        return ALERTA
    return NORMAL


def avaliar_tensao(valor: float, nominal: float) -> str:
    return _avaliar_desvio(valor, nominal, TENSAO_DESVIO_ALERTA, TENSAO_DESVIO_CRITICO)


def avaliar_rotacao(valor: float, nominal: float) -> str:
    return _avaliar_desvio(valor, nominal, ROTACAO_DESVIO_ALERTA, ROTACAO_DESVIO_CRITICO)


def avaliar_corrente(valor: float, nominal: float) -> str:
    if not nominal:
        return NORMAL
    if valor >= nominal * CORRENTE_FATOR_CRITICO:
        return CRITICO
    if valor >= nominal * CORRENTE_FATOR_ALERTA:
        return ALERTA
    return NORMAL


def avaliar_temperatura(valor: float) -> str:
    if valor >= TEMPERATURA_LIMITE_ALERTA:
        return CRITICO
    if valor >= TEMPERATURA_LIMITE_BOM:
        return ALERTA
    return NORMAL


def avaliar_vibracao(valor: float) -> str:
    if valor >= VIBRACAO_LIMITE_ALERTA:
        return CRITICO
    if valor >= VIBRACAO_LIMITE_BOM:
        return ALERTA
    return NORMAL


# --------------------------------------------------------------------------- #
# Estruturas de diagnóstico
# --------------------------------------------------------------------------- #
@dataclass
class MetricaSaude:
    """Resultado da avaliação de uma grandeza medida."""

    chave: str          # identificador interno (ex.: "temperatura_c")
    nome: str           # nome amigável (ex.: "Temperatura")
    valor: float        # valor medido
    unidade: str        # unidade de engenharia (ex.: "°C")
    nivel: str          # NORMAL / ALERTA / CRITICO
    detalhe: str        # explicação textual do estado
    nominal: Optional[float] = None  # valor de referência, quando aplicável


@dataclass
class Diagnostico:
    """Diagnóstico completo de uma leitura: conjunto de métricas + estado geral."""

    timestamp: str
    metricas: List[MetricaSaude]

    @property
    def nivel_geral(self) -> str:
        """Estado geral do ativo = pior nível entre todas as grandezas."""
        return pior_nivel(*[m.nivel for m in self.metricas])

    @property
    def alertas(self) -> List[MetricaSaude]:
        """Métricas que não estão em estado normal (alertas ativos)."""
        return [m for m in self.metricas if m.nivel != NORMAL]

    def metrica(self, chave: str) -> Optional[MetricaSaude]:
        return next((m for m in self.metricas if m.chave == chave), None)


# --------------------------------------------------------------------------- #
# Mensagens de detalhe
# --------------------------------------------------------------------------- #
def _detalhe_temperatura(v: float) -> str:
    if v >= TEMPERATURA_LIMITE_ALERTA:
        return f"Acima do limite crítico de {TEMPERATURA_LIMITE_ALERTA} °C — risco de dano térmico."
    if v >= TEMPERATURA_LIMITE_BOM:
        return f"Na faixa de atenção ({TEMPERATURA_LIMITE_BOM}–{TEMPERATURA_LIMITE_ALERTA} °C)."
    return f"Dentro da faixa normal (abaixo de {TEMPERATURA_LIMITE_BOM} °C)."


def _detalhe_vibracao(v: float) -> str:
    if v >= VIBRACAO_LIMITE_ALERTA:
        return f"Vibração crítica (zona ISO 10816 C/D, acima de {VIBRACAO_LIMITE_ALERTA} mm/s)."
    if v >= VIBRACAO_LIMITE_BOM:
        return f"Vibração elevada (zona ISO 10816 B/C, {VIBRACAO_LIMITE_BOM}–{VIBRACAO_LIMITE_ALERTA} mm/s)."
    return f"Vibração normal (zona ISO 10816 A/B, abaixo de {VIBRACAO_LIMITE_BOM} mm/s)."


def _detalhe_corrente(v: float, nominal: float, nivel: str) -> str:
    pct = (v / nominal * 100) if nominal else 0
    if nivel == CRITICO:
        return f"Corrente em {pct:.0f}% da nominal — sobrecarga crítica."
    if nivel == ALERTA:
        return f"Corrente em {pct:.0f}% da nominal — atenção à carga."
    return f"Corrente em {pct:.0f}% da nominal — dentro do esperado."


def _detalhe_desvio(v: float, nominal: float, nivel: str, unidade: str) -> str:
    desvio = ((v - nominal) / nominal * 100) if nominal else 0
    if nivel == CRITICO:
        return f"Desvio de {desvio:+.1f}% em relação ao nominal ({nominal:.0f} {unidade}) — crítico."
    if nivel == ALERTA:
        return f"Desvio de {desvio:+.1f}% em relação ao nominal ({nominal:.0f} {unidade}) — atenção."
    return f"Desvio de {desvio:+.1f}% em relação ao nominal ({nominal:.0f} {unidade}) — estável."


# --------------------------------------------------------------------------- #
# Avaliação de uma leitura completa
# --------------------------------------------------------------------------- #
def avaliar_leitura(leitura: dict, equipamento: Equipamento) -> Diagnostico:
    """
    Recebe uma leitura já convertida em unidades de engenharia e o equipamento,
    e devolve o diagnóstico completo (uma MetricaSaude por grandeza).
    """
    tensao = float(leitura["tensao_v"])
    corrente = float(leitura["corrente_a"])
    rpm = float(leitura["rpm"])
    temperatura = float(leitura["temperatura_c"])
    vibracao = float(leitura["vibracao_mms"])

    nivel_corrente = avaliar_corrente(corrente, equipamento.corrente_nominal_a)
    nivel_tensao = avaliar_tensao(tensao, equipamento.tensao_v)
    nivel_rpm = avaliar_rotacao(rpm, equipamento.rotacao_nominal_rpm)

    metricas = [
        MetricaSaude(
            "temperatura_c", "Temperatura", temperatura, "°C",
            avaliar_temperatura(temperatura), _detalhe_temperatura(temperatura),
        ),
        MetricaSaude(
            "vibracao_mms", "Vibração (RMS)", vibracao, "mm/s",
            avaliar_vibracao(vibracao), _detalhe_vibracao(vibracao),
        ),
        MetricaSaude(
            "corrente_a", "Corrente", corrente, "A", nivel_corrente,
            _detalhe_corrente(corrente, equipamento.corrente_nominal_a, nivel_corrente),
            nominal=equipamento.corrente_nominal_a,
        ),
        MetricaSaude(
            "tensao_v", "Tensão", tensao, "V", nivel_tensao,
            _detalhe_desvio(tensao, equipamento.tensao_v, nivel_tensao, "V"),
            nominal=equipamento.tensao_v,
        ),
        MetricaSaude(
            "rpm", "Rotação", rpm, "RPM", nivel_rpm,
            _detalhe_desvio(rpm, equipamento.rotacao_nominal_rpm, nivel_rpm, "RPM"),
            nominal=float(equipamento.rotacao_nominal_rpm),
        ),
    ]

    return Diagnostico(timestamp=str(leitura.get("timestamp", "")), metricas=metricas)
