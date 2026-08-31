"""
Histórico de eventos do Painel de Alertas.

Registra, de forma persistida, toda transição relevante de estado de saúde
de um ativo (ex.: Normal -> Atenção, Atenção -> Crítico) para compor a
trilha de auditoria exigida pela Sprint ("histórico de eventos").

Segue o mesmo padrão de persistência local em JSON já usado pelo restante
do projeto (`historico_repository.py`, `repository.py`), podendo ser trocado
por um banco relacional/time-series sem alterar a API pública.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from src.config.settings import DATA_DIR

EVENTOS_FILE = DATA_DIR / "eventos" / "eventos.json"

# Evita crescimento ilimitado do arquivo de eventos em demonstrações longas.
MAX_EVENTOS = 300


@dataclass
class Evento:
    """Um evento de mudança de estado de um ativo."""

    equipamento_id: str
    equipamento_tag: str
    nivel_anterior: str
    nivel_novo: str
    metrica_gatilho: str      # nome amigável da grandeza que motivou a transição
    resumo: str                 # frase curta para a linha do tempo
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Evento":
        valid = {f for f in cls.__dataclass_fields__.keys()}
        return cls(**{k: v for k, v in data.items() if k in valid})


class EventoRepository:
    """Repositório de eventos, um único arquivo JSON (lista cronológica)."""

    def __init__(self, file_path: Path = EVENTOS_FILE):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self.file_path.write_text("[]", encoding="utf-8")

    def listar(self, limit: Optional[int] = None) -> List[Evento]:
        """Retorna os eventos mais recentes primeiro."""
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                bruto = json.load(f)
        except (json.JSONDecodeError, OSError):
            bruto = []
        eventos = [Evento.from_dict(e) for e in bruto]
        eventos.sort(key=lambda e: e.timestamp, reverse=True)
        return eventos[:limit] if limit else eventos

    def registrar(self, evento: Evento) -> None:
        eventos = self.listar()
        eventos.insert(0, evento)
        eventos = eventos[:MAX_EVENTOS]
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump([e.to_dict() for e in reversed(eventos)], f,
                      ensure_ascii=False, indent=2)
