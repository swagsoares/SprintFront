"""
Simulador de sensores.

Ainda não há hardware real entregando dados, então este módulo gera leituras
"brutas" (valores ADC 12-bit, 0-4095) que mimetizam o que viria de um CLP /
microcontrolador via Modbus, MQTT, OPC-UA etc.

Sprint 1: `gerar_amostras()` — janela curta de leituras em torno do "agora".
Sprint 2: `gerar_serie_historica()` — janela longa (dias) que alimenta os
          gráficos de tendência, e `gerar_leitura_unica()` — uma leitura nova
          para simular aquisição em tempo real.

Cada perfil de simulação (`Saudável`, `Em degradação`, `Crítico`) define como
temperatura, vibração e corrente evoluem ao longo do histórico, permitindo
demonstrar tanto um motor saudável quanto um motor caminhando para a falha.

Em sprints futuros, este módulo será substituído por um adaptador que consome
dados reais sem mudar a interface pública.
"""

import hashlib
import math
import random
from datetime import datetime, timedelta
from typing import Dict, List

from src.backend.models import Equipamento
from src.config.settings import (
    ADC_RESOLUTION,
    HISTORICO_DIAS,
    HISTORICO_PASSO_MIN,
    PERFIL_CRITICO,
    PERFIL_DEGRADACAO,
    PERFIL_SAUDAVEL,
)

# --------------------------------------------------------------------------- #
# Parâmetros de cada perfil de simulação.
# Cada grandeza é descrita por uma tupla (valor_inicial, valor_final): o
# simulador interpola linearmente ao longo do histórico, criando uma
# tendência. "carga" é a fração da corrente nominal consumida pelo motor.
# --------------------------------------------------------------------------- #
_PERFIS = {
    PERFIL_SAUDAVEL:   {"temp": (60.0, 65.0), "vib": (1.6, 2.3), "carga": (0.66, 0.72)},
    PERFIL_DEGRADACAO: {"temp": (62.0, 86.0), "vib": (2.2, 4.4), "carga": (0.70, 0.97)},
    PERFIL_CRITICO:    {"temp": (68.0, 99.0), "vib": (3.0, 6.8), "carga": (0.74, 1.19)},
}


def _seed_estavel(texto: str) -> int:
    """Gera uma seed determinística a partir de uma string (ex.: id do ativo)."""
    return int(hashlib.md5(texto.encode("utf-8")).hexdigest(), 16) & 0xFFFFFFFF


class SensorSimulator:
    """Gera leituras brutas simuladas de sensores."""

    def __init__(self, seed: int | None = None):
        if seed is not None:
            random.seed(seed)

    # ----------------------------------------------------------------------- #
    # Sprint 1 — janela curta de leituras (mantida para a página de dados brutos)
    # ----------------------------------------------------------------------- #
    def gerar_amostras(
        self,
        equipamento: Equipamento,
        n_amostras: int = 60,
        intervalo_segundos: int = 1,
    ) -> List[Dict]:
        """
        Retorna uma lista de leituras brutas no formato:

            { "timestamp": iso_str,
              "tensao_raw": int (0-4095),
              "corrente_raw": int (0-4095),
              "rpm_raw": int (0-4095),
              "temperatura_raw": int (0-4095),
              "vibracao_raw": int (0-4095) }
        """
        amostras: List[Dict] = []
        agora = datetime.now()

        # Pequena variação determinística (ciclo lento) + ruído gaussiano
        for i in range(n_amostras):
            ts = agora - timedelta(seconds=intervalo_segundos * (n_amostras - i))

            ruido = random.gauss(0, 0.015)
            ciclo = math.sin(i * 0.18) * 0.04

            # Tensão -> raw representa percentual da nominal (0.95-1.05 da nominal)
            tensao_pct = 1.0 + ruido + ciclo
            tensao_raw = self._mapear_pct(tensao_pct, fator=0.5)

            # Corrente -> motor operando ~70% da carga nominal com flutuações
            corrente_pct = 0.7 + ruido + ciclo
            corrente_raw = self._mapear_pct(corrente_pct, fator=0.5)

            # RPM -> próximo da nominal
            rpm_pct = 1.0 + ruido * 0.4
            rpm_raw = self._mapear_pct(rpm_pct, fator=0.5)

            # Temperatura -> ~65 °C com leve oscilação (faixa 0-150 °C)
            temp_c = 65 + ruido * 6 + ciclo * 12
            temp_raw = int((max(0, temp_c) / 150.0) * ADC_RESOLUTION)

            # Vibração -> ~2.5 mm/s, faixa 0-10 mm/s
            vib_mms = 2.5 + abs(ruido) * 2.5 + abs(ciclo)
            vib_raw = int((min(10, vib_mms) / 10.0) * ADC_RESOLUTION)

            amostras.append(
                {
                    "timestamp": ts.isoformat(timespec="seconds"),
                    "tensao_raw": tensao_raw,
                    "corrente_raw": corrente_raw,
                    "rpm_raw": rpm_raw,
                    "temperatura_raw": temp_raw,
                    "vibracao_raw": vib_raw,
                }
            )

        return amostras

    # ----------------------------------------------------------------------- #
    # Sprint 2 — série histórica longa para os gráficos de tendência
    # ----------------------------------------------------------------------- #
    def gerar_serie_historica(
        self,
        equipamento: Equipamento,
        *,
        dias: int = HISTORICO_DIAS,
        passo_min: int = HISTORICO_PASSO_MIN,
        perfil: str = PERFIL_SAUDAVEL,
    ) -> List[Dict]:
        """
        Gera um histórico longo de leituras brutas (uma a cada `passo_min`
        minutos, cobrindo `dias` dias). A geração é determinística por ativo
        (seed derivada do id), então o histórico é estável entre execuções.
        """
        random.seed(_seed_estavel(equipamento.id))

        n = max(2, int(dias * 24 * 60 / passo_min))
        agora = datetime.now().replace(minute=0, second=0, microsecond=0)
        inicio = agora - timedelta(minutes=passo_min * (n - 1))

        amostras: List[Dict] = []
        for i in range(n):
            ts = inicio + timedelta(minutes=passo_min * i)
            fracao = i / (n - 1)                    # 0.0 -> 1.0 ao longo do tempo
            hora_idx = i * (passo_min / 60.0)       # horas decorridas (ciclo diário)
            amostras.append(self._amostra_bruta(equipamento, perfil, fracao, hora_idx, ts))

        return amostras

    def gerar_leitura_unica(
        self,
        equipamento: Equipamento,
        perfil: str = PERFIL_SAUDAVEL,
        ts: datetime | None = None,
    ) -> Dict:
        """Gera uma única leitura nova (estado atual do ativo) para o "tempo real"."""
        ts = ts or datetime.now()
        hora_idx = ts.hour + ts.minute / 60.0
        return self._amostra_bruta(equipamento, perfil, 1.0, hora_idx, ts.replace(microsecond=0))

    # ----------------------------------------------------------------------- #
    # Núcleo de geração de uma amostra
    # ----------------------------------------------------------------------- #
    def _amostra_bruta(
        self,
        eq: Equipamento,
        perfil: str,
        fracao: float,
        hora_idx: float,
        ts: datetime,
    ) -> Dict:
        """Constrói uma amostra bruta para um instante, segundo o perfil do ativo."""
        p = _PERFIS.get(perfil, _PERFIS[PERFIL_SAUDAVEL])

        # Ciclo diário (período de 24 h) + ruído gaussiano por grandeza.
        ciclo = math.sin(hora_idx * (2 * math.pi / 24.0))

        temp = self._lerp(*p["temp"], fracao) + 2.4 * ciclo + random.gauss(0, 0.9)
        vib = self._lerp(*p["vib"], fracao) + 0.14 * ciclo + abs(random.gauss(0, 0.13))
        carga = self._lerp(*p["carga"], fracao) + 0.018 * ciclo + random.gauss(0, 0.016)

        corrente = max(0.0, eq.corrente_nominal_a * carga)
        tensao = eq.tensao_v * (1 + random.gauss(0, 0.012))
        rpm = eq.rotacao_nominal_rpm * (1 + random.gauss(0, 0.006))

        return {
            "timestamp": ts.isoformat(timespec="seconds"),
            "tensao_raw": self._eng_para_raw(tensao, eq.tensao_v * 2),
            "corrente_raw": self._eng_para_raw(corrente, eq.corrente_nominal_a * 2),
            "rpm_raw": self._eng_para_raw(rpm, eq.rotacao_nominal_rpm * 2),
            "temperatura_raw": self._eng_para_raw(temp, 150.0),
            "vibracao_raw": self._eng_para_raw(vib, 10.0),
        }

    # ----------------------------------------------------------------------- #
    # Helpers
    # ----------------------------------------------------------------------- #
    @staticmethod
    def _lerp(inicio: float, fim: float, t: float) -> float:
        """Interpolação linear entre `inicio` e `fim` para t em [0, 1]."""
        return inicio + (fim - inicio) * t

    @staticmethod
    def _eng_para_raw(valor: float, faixa_max: float) -> int:
        """Converte um valor em unidade de engenharia para o sinal ADC (0-4095)."""
        if faixa_max <= 0:
            return 0
        raw = int(round((valor / faixa_max) * ADC_RESOLUTION))
        return max(0, min(ADC_RESOLUTION, raw))

    @staticmethod
    def _mapear_pct(pct: float, fator: float = 0.5) -> int:
        """
        Mapeia um percentual (esperado próximo de 1.0) em um valor ADC.
        `fator=0.5` faz com que pct=1.0 corresponda à metade do range (~2047),
        deixando margem para subir e descer sem saturar.
        """
        valor = int(pct * fator * ADC_RESOLUTION)
        return max(0, min(ADC_RESOLUTION, valor))
