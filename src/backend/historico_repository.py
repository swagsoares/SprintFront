"""
Camada de persistência do histórico de telemetria.

Cada ativo tem seu histórico de leituras (já convertidas em unidades de
engenharia) armazenado em um arquivo JSON próprio dentro de `data/historico/`.
Isso atende ao requisito da Sprint 2 de que os gráficos consumam dados
históricos *persistidos* — e não recalculados a cada interação.

Hoje a persistência é em arquivos JSON locais; pode ser trocada por
SQLite / Postgres / um time-series database sem alterar a API pública.
"""

import json
from pathlib import Path
from typing import List

from src.config.settings import HISTORICO_DIR


class HistoricoRepository:
    """Repositório de séries históricas de telemetria, um arquivo por ativo."""

    def __init__(self, base_dir: Path = HISTORICO_DIR):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    # ----------------------------------------------------------------------- #
    def _caminho(self, equipamento_id: str) -> Path:
        return self.base_dir / f"{equipamento_id}.json"

    def existe(self, equipamento_id: str) -> bool:
        return self._caminho(equipamento_id).exists()

    # ----------------------------------------------------------------------- #
    def carregar(self, equipamento_id: str) -> List[dict]:
        """Retorna o histórico persistido do ativo (lista vazia se não houver)."""
        caminho = self._caminho(equipamento_id)
        if not caminho.exists():
            return []
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []

    def salvar(self, equipamento_id: str, leituras: List[dict]) -> None:
        """Sobrescreve o histórico do ativo."""
        with open(self._caminho(equipamento_id), "w", encoding="utf-8") as f:
            json.dump(leituras, f, ensure_ascii=False)

    def acrescentar(self, equipamento_id: str, leitura: dict) -> List[dict]:
        """Adiciona uma nova leitura ao final do histórico e persiste."""
        leituras = self.carregar(equipamento_id)
        leituras.append(leitura)
        self.salvar(equipamento_id, leituras)
        return leituras

    def excluir(self, equipamento_id: str) -> bool:
        """Remove o histórico persistido do ativo."""
        caminho = self._caminho(equipamento_id)
        if caminho.exists():
            caminho.unlink()
            return True
        return False
