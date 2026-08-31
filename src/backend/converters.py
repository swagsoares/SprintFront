"""
Conversores de sinal bruto -> unidade de engenharia.

Os sensores entregam um valor inteiro (ADC 12-bit, 0-4095). Cada grandeza
precisa ser convertida usando os parâmetros nominais do equipamento:

    - Tensão (V):       raw mapeado em [0, 2 * Vnominal]
    - Corrente (A):     raw mapeado em [0, 2 * Inominal]
    - Rotação (RPM):    raw mapeado em [0, 2 * RPMnominal]
    - Temperatura (°C): raw mapeado em [0, 150]
    - Vibração (mm/s):  raw mapeado em [0, 10]   (faixa típica ISO 10816)

Manter os dois valores (bruto e convertido) é importante: o bruto serve
para diagnóstico de hardware/calibração; o convertido é o que vai para
modelos e dashboards.
"""

from typing import Dict, List

from src.backend.models import Equipamento
from src.config.settings import ADC_RESOLUTION


class SensorConverter:
    """Converte um lote de amostras brutas em unidades de engenharia."""

    # ----------------------------------------------------------------------- #
    @staticmethod
    def _escala_linear(raw: int, faixa_max: float) -> float:
        """Mapeia raw (0-4095) -> [0, faixa_max]."""
        return (raw / ADC_RESOLUTION) * faixa_max

    # ----------------------------------------------------------------------- #
    @classmethod
    def converter_tensao(cls, raw: int, tensao_nominal: float) -> float:
        return cls._escala_linear(raw, tensao_nominal * 2)

    @classmethod
    def converter_corrente(cls, raw: int, corrente_nominal: float) -> float:
        return cls._escala_linear(raw, corrente_nominal * 2)

    @classmethod
    def converter_rpm(cls, raw: int, rpm_nominal: int) -> float:
        return cls._escala_linear(raw, rpm_nominal * 2)

    @classmethod
    def converter_temperatura(cls, raw: int) -> float:
        return cls._escala_linear(raw, 150.0)

    @classmethod
    def converter_vibracao(cls, raw: int) -> float:
        return cls._escala_linear(raw, 10.0)

    # ----------------------------------------------------------------------- #
    @classmethod
    def converter_amostra(cls, amostra: Dict, equipamento: Equipamento) -> Dict:
        """Converte uma única amostra mantendo os valores brutos."""
        return {
            "timestamp": amostra["timestamp"],
            # Engenharia
            "tensao_v": round(cls.converter_tensao(amostra["tensao_raw"], equipamento.tensao_v), 2),
            "corrente_a": round(cls.converter_corrente(amostra["corrente_raw"], equipamento.corrente_nominal_a), 2),
            "rpm": round(cls.converter_rpm(amostra["rpm_raw"], equipamento.rotacao_nominal_rpm), 0),
            "temperatura_c": round(cls.converter_temperatura(amostra["temperatura_raw"]), 1),
            "vibracao_mms": round(cls.converter_vibracao(amostra["vibracao_raw"]), 2),
            # Brutos (preservados)
            "tensao_raw": amostra["tensao_raw"],
            "corrente_raw": amostra["corrente_raw"],
            "rpm_raw": amostra["rpm_raw"],
            "temperatura_raw": amostra["temperatura_raw"],
            "vibracao_raw": amostra["vibracao_raw"],
        }

    @classmethod
    def converter_lote(cls, amostras: List[Dict], equipamento: Equipamento) -> List[Dict]:
        return [cls.converter_amostra(a, equipamento) for a in amostras]
