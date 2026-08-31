"""
Camada de inteligência operacional: resumos textuais (NLP) e apoio à decisão.

Esta é a "porta de entrada" arquitetural para o time de Machine Learning /
Processamento de Linguagem Natural. Hoje ela é resolvida por um gerador
heurístico local (baseado nas métricas do `health.py`), mas a interface
pública — `gerar_resumo()` e `gerar_recomendacoes()` — já é a que o
Front-End consome e a que um pipeline de NLP real deverá respeitar.

Como plugar um modelo real no futuro
-------------------------------------
Se existir um pacote `src.ml.nlp_pipeline` com uma função
`resumir(equipamento: Equipamento, diagnostico: Diagnostico) -> str`,
ela é usada automaticamente no lugar da heurística (ver `_resumo_texto`).
Enquanto esse pacote não existir, o sistema opera com o resumo simulado
abaixo — sem quebrar o contrato com o Front-End. Isso atende ao requisito
de a interface já estar "preparada para receber o que será gerado por NLP"
mesmo antes do modelo existir.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from src.backend import health
from src.backend.health import ALERTA, CRITICO, NORMAL, Diagnostico, MetricaSaude
from src.backend.models import Equipamento

# --------------------------------------------------------------------------- #
# Estruturas de dados consumidas pelo Front-End
# --------------------------------------------------------------------------- #
@dataclass
class ResumoOperacional:
    """Resumo textual do estado do ativo, gerado por NLP (ou pela heurística)."""

    texto: str
    origem: str          # "simulado" (heurística local) ou "modelo_nlp"
    nivel: str            # nível geral no momento do resumo (NORMAL/ALERTA/CRITICO)


@dataclass
class Recomendacao:
    """Uma ação de apoio à decisão sugerida para a equipe de manutenção."""

    titulo: str
    descricao: str
    prioridade: str        # mesmos níveis semânticos de health.py


@dataclass
class Insight:
    """Pacote completo exibido no card de alerta: resumo + recomendações."""

    resumo: ResumoOperacional
    recomendacoes: List[Recomendacao]


# --------------------------------------------------------------------------- #
# Tenta usar um pipeline de NLP real, se ele existir no projeto.
# Enquanto não existir, cai automaticamente no gerador heurístico.
# --------------------------------------------------------------------------- #
def _resumo_via_modelo_nlp(equipamento: Equipamento, diagnostico: Diagnostico) -> str | None:
    try:
        from src.ml.nlp_pipeline import resumir  # type: ignore
    except ImportError:
        return None
    try:
        return resumir(equipamento, diagnostico)
    except Exception:
        # Um pipeline real instável nunca deve derrubar o painel de alertas;
        # a heurística assume como rede de segurança.
        return None


# --------------------------------------------------------------------------- #
# Gerador heurístico do resumo (placeholder do NLP)
# --------------------------------------------------------------------------- #
_NOME_CURTO = {
    "temperatura_c": "temperatura",
    "vibracao_mms": "vibração",
    "corrente_a": "corrente",
    "tensao_v": "tensão",
    "rpm": "rotação",
}


def _pior_metrica(diagnostico: Diagnostico) -> MetricaSaude | None:
    alertas = diagnostico.alertas
    if not alertas:
        return None
    return sorted(alertas, key=lambda m: m.nivel == CRITICO, reverse=True)[0]


def _resumo_texto(equipamento: Equipamento, diagnostico: Diagnostico) -> str:
    nivel = diagnostico.nivel_geral
    n_alertas = len(diagnostico.alertas)

    if nivel == NORMAL:
        return (
            f"{equipamento.tag} está operando dentro da faixa normal em todas as "
            f"grandezas monitoradas (tensão, corrente, rotação, temperatura e "
            f"vibração). Nenhuma ação é necessária no momento; a próxima leitura "
            f"programada seguirá o ciclo normal de acompanhamento."
        )

    pior = _pior_metrica(diagnostico)
    nome_pior = _NOME_CURTO.get(pior.chave, pior.nome.lower())
    outras = [_NOME_CURTO.get(m.chave, m.nome.lower()) for m in diagnostico.alertas if m is not pior]
    complemento = f" Também há desvio em {', '.join(outras)}." if outras else ""

    if nivel == CRITICO:
        return (
            f"{equipamento.tag} está em estado crítico: {nome_pior} em "
            f"{pior.valor:.2f} {pior.unidade} ultrapassou o limite operacional "
            f"seguro.{complemento} Recomenda-se intervenção da manutenção "
            f"antes da próxima janela de operação para evitar dano ao ativo."
        )

    return (
        f"{equipamento.tag} apresenta {n_alertas} grandeza(s) fora da faixa "
        f"ideal, com destaque para {nome_pior} em "
        f"{pior.valor:.2f} {pior.unidade}.{complemento} O quadro ainda não é "
        f"crítico, mas justifica inspeção programada para evitar agravamento."
    )


def gerar_resumo(equipamento: Equipamento, diagnostico: Diagnostico) -> ResumoOperacional:
    """Gera o resumo textual do estado do ativo (via modelo de NLP, se disponível)."""
    texto_modelo = _resumo_via_modelo_nlp(equipamento, diagnostico)
    if texto_modelo:
        return ResumoOperacional(texto=texto_modelo, origem="modelo_nlp",
                                  nivel=diagnostico.nivel_geral)
    return ResumoOperacional(
        texto=_resumo_texto(equipamento, diagnostico),
        origem="simulado",
        nivel=diagnostico.nivel_geral,
    )


# --------------------------------------------------------------------------- #
# Apoio inicial à decisão — recomendações por grandeza alertada
# --------------------------------------------------------------------------- #
_ACOES_POR_METRICA = {
    "temperatura_c": {
        ALERTA: (
            "Verificar refrigeração",
            "Inspecionar ventilação/arrefecimento e carga aplicada. Reduzir "
            "carga se a tendência de temperatura continuar subindo.",
        ),
        CRITICO: (
            "Risco de dano térmico",
            "Avaliar parada controlada. Verificar sistema de arrefecimento, "
            "obstrução de fluxo de ar e sobrecarga antes de religar.",
        ),
    },
    "vibracao_mms": {
        ALERTA: (
            "Agendar inspeção de vibração",
            "Programar análise de alinhamento e balanceamento na próxima "
            "janela de manutenção preventiva.",
        ),
        CRITICO: (
            "Inspecionar rolamentos e fixação",
            "Vibração na zona crítica (ISO 10816 C/D): risco de falha "
            "mecânica iminente. Priorizar inspeção de rolamentos, "
            "alinhamento e fixação do ativo.",
        ),
    },
    "corrente_a": {
        ALERTA: (
            "Monitorar carga do motor",
            "Corrente acima do esperado — acompanhar tendência e verificar "
            "se a carga do processo está dentro do projetado.",
        ),
        CRITICO: (
            "Investigar sobrecarga",
            "Corrente em sobrecarga crítica: risco de sobreaquecimento dos "
            "enrolamentos. Verificar carga mecânica e proteções elétricas.",
        ),
    },
    "tensao_v": {
        ALERTA: (
            "Checar qualidade de energia",
            "Desvio de tensão fora do esperado — verificar quadro de "
            "distribuição e qualidade do fornecimento.",
        ),
        CRITICO: (
            "Verificar alimentação elétrica",
            "Desvio crítico de tensão: risco para o isolamento do motor. "
            "Acionar equipe elétrica antes de manter o ativo em operação.",
        ),
    },
    "rpm": {
        ALERTA: (
            "Acompanhar rotação",
            "Rotação fora da faixa nominal — acompanhar para identificar "
            "escorregamento ou variação de carga no acionamento.",
        ),
        CRITICO: (
            "Investigar acionamento",
            "Desvio crítico de rotação: verificar acionamento, acoplamento "
            "e condições mecânicas do eixo.",
        ),
    },
}


def gerar_recomendacoes(diagnostico: Diagnostico) -> List[Recomendacao]:
    """Deriva recomendações de apoio à decisão a partir das métricas alertadas."""
    if not diagnostico.alertas:
        return [
            Recomendacao(
                titulo="Manter monitoramento de rotina",
                descricao="Sem desvios ativos. Manter o ciclo normal de "
                          "acompanhamento e a manutenção preventiva programada.",
                prioridade=NORMAL,
            )
        ]

    recomendacoes: List[Recomendacao] = []
    for metrica in sorted(diagnostico.alertas, key=lambda m: m.nivel == CRITICO, reverse=True):
        acoes = _ACOES_POR_METRICA.get(metrica.chave, {})
        acao = acoes.get(metrica.nivel)
        if acao:
            titulo, descricao = acao
            recomendacoes.append(Recomendacao(titulo=titulo, descricao=descricao,
                                               prioridade=metrica.nivel))
    return recomendacoes
