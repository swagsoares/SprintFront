"""
Placa de identificação (nameplate) do motor + simulação da extração por
visão computacional.

A Sprint 2 conecta o cadastro técnico do ativo à imagem da sua placa de
identificação: os campos da ficha são apresentados como se tivessem sido
lidos automaticamente de uma fotografia da placa por um pipeline de OCR /
visão computacional, cada um com a sua confiança de detecção.

A imagem é renderizada com Matplotlib (uma das bibliotecas de visualização
previstas no enunciado), o que dispensa fontes externas e funciona igual em
qualquer sistema operacional.
"""

from __future__ import annotations

import hashlib
import io
import random
from dataclasses import dataclass
from typing import List

import matplotlib

matplotlib.use("Agg")  # backend sem interface gráfica (necessário no servidor)
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle  # noqa: E402

from src.backend.models import Equipamento  # noqa: E402


@dataclass
class CampoOCR:
    """Um campo lido da placa pela visão computacional."""

    rotulo: str
    valor: str
    confianca: float   # 0.0 a 1.0

    @property
    def revisar(self) -> bool:
        """True quando a confiança é baixa e o campo deve ser conferido."""
        return self.confianca < 0.90


def _seed(equipamento: Equipamento) -> int:
    """Seed determinística por ativo — confianças estáveis entre execuções."""
    return int(hashlib.md5(equipamento.id.encode("utf-8")).hexdigest(), 16) & 0xFFFFFFFF


# --------------------------------------------------------------------------- #
# Extração simulada dos campos da placa
# --------------------------------------------------------------------------- #
def extrair_campos_ocr(equipamento: Equipamento) -> List[CampoOCR]:
    """
    Simula a saída de um pipeline de OCR sobre a foto da placa do motor,
    devolvendo cada campo da ficha técnica com a sua confiança de detecção.
    """
    rnd = random.Random(_seed(equipamento))

    base = [
        ("Fabricante", equipamento.fabricante or "—"),
        ("Modelo", equipamento.modelo or "—"),
        ("Nº de série", equipamento.numero_serie or "—"),
        ("Potência", f"{equipamento.potencia_kw:.1f} kW"),
        ("Tensão nominal", f"{equipamento.tensao_v:.0f} V"),
        ("Corrente nominal", f"{equipamento.corrente_nominal_a:.1f} A"),
        ("Rotação", f"{equipamento.rotacao_nominal_rpm} rpm"),
        ("Frequência", f"{equipamento.frequencia_hz:.0f} Hz"),
    ]

    campos = [CampoOCR(rot, val, round(rnd.uniform(0.93, 0.995), 3)) for rot, val in base]

    # Realismo: um campo é extraído com confiança mais baixa e precisa revisão.
    idx_baixo = rnd.randrange(len(campos))
    campos[idx_baixo].confianca = round(rnd.uniform(0.82, 0.89), 3)
    return campos


# --------------------------------------------------------------------------- #
# Renderização da imagem da placa
# --------------------------------------------------------------------------- #
def gerar_imagem_placa(equipamento: Equipamento, com_deteccoes: bool = False) -> bytes:
    """
    Renderiza a placa de identificação do motor como PNG (bytes).

    Quando `com_deteccoes=True`, sobrepõe as caixas delimitadoras (bounding
    boxes) da visão computacional, coloridas pela confiança de cada leitura.
    """
    campos = {c.rotulo: c.confianca for c in extrair_campos_ocr(equipamento)}

    fig = plt.figure(figsize=(7.4, 4.8), dpi=150)
    fig.patch.set_facecolor("#0f172a")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # ---- Corpo metálico da placa
    ax.add_patch(
        FancyBboxPatch(
            (0.04, 0.06), 0.92, 0.88,
            boxstyle="round,pad=0,rounding_size=0.02",
            facecolor="#c7ccd4", edgecolor="#3f4651", linewidth=3,
        )
    )
    ax.add_patch(
        Rectangle((0.07, 0.09), 0.86, 0.82,
                  facecolor="#dadee4", edgecolor="#aab0b9", linewidth=1.2)
    )
    # Parafusos nos cantos
    for sx, sy in [(0.088, 0.882), (0.912, 0.882), (0.088, 0.118), (0.912, 0.118)]:
        ax.add_patch(Circle((sx, sy), 0.016, facecolor="#8b919b", edgecolor="#5b6068", lw=1))

    # ---- Cabeçalho com o fabricante
    ax.add_patch(Rectangle((0.11, 0.785), 0.78, 0.092, facecolor="#1f2937", edgecolor="none"))
    ax.text(0.13, 0.831, (equipamento.fabricante or "—").upper(),
            color="#f8fafc", fontsize=16, fontweight="bold",
            va="center", ha="left", family="monospace")
    ax.text(0.87, 0.831, "IEC 60034", color="#9aa3b2", fontsize=8,
            va="center", ha="right", family="monospace")

    # ---- Subtítulo
    ax.text(0.13, 0.726, f"{(equipamento.tipo or 'EQUIPAMENTO').upper()}  —  PLACA DE IDENTIFICAÇÃO",
            color="#374151", fontsize=8.5, fontweight="bold",
            va="center", ha="left", family="monospace")
    ax.plot([0.13, 0.87], [0.70, 0.70], color="#9aa0aa", lw=1)

    # ---- Grade de campos (2 colunas x 4 linhas)
    cells = [
        ("MODELO", equipamento.modelo or "—", "Modelo"),
        ("Nº DE SÉRIE", equipamento.numero_serie or "—", "Nº de série"),
        ("POTÊNCIA", f"{equipamento.potencia_kw:.1f} kW", "Potência"),
        ("TENSÃO NOMINAL", f"{equipamento.tensao_v:.0f} V", "Tensão nominal"),
        ("CORRENTE NOMINAL", f"{equipamento.corrente_nominal_a:.1f} A", "Corrente nominal"),
        ("ROTAÇÃO", f"{equipamento.rotacao_nominal_rpm} rpm", "Rotação"),
        ("FREQUÊNCIA", f"{equipamento.frequencia_hz:.0f} Hz", "Frequência"),
        ("TAG / ATIVO", equipamento.tag or "—", None),
    ]
    col_x = [0.135, 0.535]
    row_y = [0.605, 0.455, 0.305, 0.165]

    for idx, (rotulo, valor, ocr_key) in enumerate(cells):
        cx = col_x[idx % 2]
        cy = row_y[idx // 2]
        ax.text(cx, cy + 0.046, rotulo, color="#6b7280", fontsize=7.3,
                fontweight="bold", va="center", ha="left", family="monospace")
        cor_valor = "#1d4ed8" if ocr_key is None else "#111827"
        ax.text(cx, cy, valor, color=cor_valor, fontsize=11,
                fontweight="bold", va="center", ha="left", family="monospace")

        if com_deteccoes and ocr_key is not None:
            conf = campos.get(ocr_key, 0.95)
            cor = "#16a34a" if conf >= 0.90 else "#ea580c"
            ax.add_patch(
                Rectangle((cx - 0.014, cy - 0.034), 0.358, 0.068,
                          fill=False, edgecolor=cor, linewidth=1.6)
            )
            ax.text(cx + 0.344, cy + 0.052, f"{conf * 100:.0f}%",
                    color="#0f172a", fontsize=6.6, fontweight="bold",
                    va="bottom", ha="right", family="monospace",
                    bbox=dict(boxstyle="square,pad=0.18", fc=cor, ec="none"))

    # ---- Caixa de detecção do cabeçalho (fabricante)
    if com_deteccoes:
        conf = campos.get("Fabricante", 0.97)
        cor = "#16a34a" if conf >= 0.90 else "#ea580c"
        ax.add_patch(Rectangle((0.118, 0.796), 0.34, 0.068,
                               fill=False, edgecolor=cor, linewidth=1.8))
        ax.text(0.462, 0.872, f"OCR {conf * 100:.0f}%",
                color="#0f172a", fontsize=6.6, fontweight="bold",
                va="bottom", ha="right", family="monospace",
                bbox=dict(boxstyle="square,pad=0.18", fc=cor, ec="none"))
        ax.text(0.13, 0.118, "▭  campo detectado por visão computacional (OCR)",
                color="#475569", fontsize=7, va="center", ha="left", family="monospace")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=fig.get_facecolor())
    plt.close(fig)
    return buf.getvalue()
