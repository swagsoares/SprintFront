"""
Serviço de telemetria.

Orquestra a geração, a persistência e a leitura do histórico de telemetria de
cada ativo. É o ponto único pelo qual a camada de apresentação obtém dados de
sensores — abstraindo se eles foram gerados agora ou lidos do disco.

Fluxo:
    obter_historico()  -> lê o histórico persistido; gera e persiste na 1ª vez
    nova_leitura()     -> simula uma aquisição "em tempo real" e a anexa ao histórico
    regenerar()        -> recria o histórico do zero (ex.: após editar a ficha técnica)
"""

from typing import List

from src.backend.converters import SensorConverter
from src.backend.historico_repository import HistoricoRepository
from src.backend.models import Equipamento
from src.backend.sensor_simulator import SensorSimulator
from src.config.settings import HISTORICO_DIAS, HISTORICO_PASSO_MIN


class TelemetriaService:
    """Fachada de acesso aos dados de telemetria (histórico + tempo real)."""

    def __init__(self):
        self.repo = HistoricoRepository()
        self.simulador = SensorSimulator()

    # ----------------------------------------------------------------------- #
    def obter_historico(self, equipamento: Equipamento) -> List[dict]:
        """
        Retorna o histórico de leituras (convertidas) do ativo.

        Se ainda não houver histórico persistido, ele é gerado a partir do
        cadastro técnico do equipamento e gravado em disco — passando a ser
        reaproveitado nas próximas execuções.
        """
        leituras = self.repo.carregar(equipamento.id)
        if not leituras:
            leituras = self._gerar(equipamento)
            self.repo.salvar(equipamento.id, leituras)
        return leituras

    def nova_leitura(self, equipamento: Equipamento, *, perfil_override: str | None = None) -> dict:
        """
        Simula a aquisição de uma leitura nova e a anexa ao histórico persistido.

        `perfil_override` permite gerar uma única leitura com um perfil
        diferente do cadastrado (usado pelo Painel de Alertas para demonstrar
        uma anomalia sob demanda) sem alterar a ficha técnica do ativo.
        """
        # Garante que o arquivo de histórico exista antes de anexar.
        self.obter_historico(equipamento)

        bruta = self.simulador.gerar_leitura_unica(
            equipamento, perfil=perfil_override or equipamento.perfil_simulacao
        )
        leitura = SensorConverter.converter_amostra(bruta, equipamento)
        self.repo.acrescentar(equipamento.id, leitura)
        return leitura

    def regenerar(self, equipamento: Equipamento) -> List[dict]:
        """Recria o histórico do zero (útil quando a ficha técnica muda)."""
        leituras = self._gerar(equipamento)
        self.repo.salvar(equipamento.id, leituras)
        return leituras

    # ----------------------------------------------------------------------- #
    def _gerar(self, equipamento: Equipamento) -> List[dict]:
        """Gera a série histórica bruta e a converte em unidades de engenharia."""
        brutas = self.simulador.gerar_serie_historica(
            equipamento,
            dias=HISTORICO_DIAS,
            passo_min=HISTORICO_PASSO_MIN,
            perfil=equipamento.perfil_simulacao,
        )
        return SensorConverter.converter_lote(brutas, equipamento)
