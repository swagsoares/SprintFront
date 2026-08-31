"""
Camada de persistência.

Abstrai a forma de armazenamento dos equipamentos. Hoje usa JSON local
para simplicidade no Sprint 1; nos próximos sprints pode ser substituído
por SQLite/Postgres/Supabase sem alterar o restante do código.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from src.backend.models import Equipamento
from src.config.settings import DATA_DIR, DATA_FILE


class EquipamentoRepository:
    """Repositório baseado em arquivo JSON local."""

    def __init__(self, file_path: Path = DATA_FILE):
        self.file_path = Path(file_path)
        self._garantir_arquivo()

    # ----------------------------------------------------------------------- #
    def _garantir_arquivo(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self.file_path.write_text("[]", encoding="utf-8")

    def _ler_tudo(self) -> List[dict]:
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _escrever_tudo(self, equipamentos: List[Equipamento]) -> None:
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(
                [e.to_dict() for e in equipamentos],
                f,
                indent=2,
                ensure_ascii=False,
            )

    # ----------------------------------------------------------------------- #
    # API pública
    # ----------------------------------------------------------------------- #
    def listar(self) -> List[Equipamento]:
        """Retorna todos os equipamentos cadastrados."""
        return [Equipamento.from_dict(item) for item in self._ler_tudo()]

    def buscar_por_id(self, equipamento_id: str) -> Optional[Equipamento]:
        for eq in self.listar():
            if eq.id == equipamento_id:
                return eq
        return None

    def buscar_por_tag(self, tag: str) -> Optional[Equipamento]:
        tag_norm = tag.strip().lower()
        for eq in self.listar():
            if eq.tag.lower() == tag_norm:
                return eq
        return None

    def salvar(self, equipamento: Equipamento) -> Equipamento:
        """Insere um novo equipamento."""
        equipamentos = self.listar()
        equipamentos.append(equipamento)
        self._escrever_tudo(equipamentos)
        return equipamento

    def atualizar(self, equipamento: Equipamento) -> bool:
        """Atualiza um equipamento existente. Retorna True se atualizou."""
        equipamentos = self.listar()
        for i, eq in enumerate(equipamentos):
            if eq.id == equipamento.id:
                equipamento.atualizado_em = datetime.now().isoformat(timespec="seconds")
                equipamentos[i] = equipamento
                self._escrever_tudo(equipamentos)
                return True
        return False

    def excluir(self, equipamento_id: str) -> bool:
        equipamentos = self.listar()
        nova_lista = [e for e in equipamentos if e.id != equipamento_id]
        if len(nova_lista) < len(equipamentos):
            self._escrever_tudo(nova_lista)
            return True
        return False
