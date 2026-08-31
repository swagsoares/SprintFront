"""Configurações globais da aplicação."""

from pathlib import Path

APP_TITLE = "Gestão de Ativos Industriais"
APP_ICON = "⚙️"
APP_DESCRIPTION = "Sprint 2 - Visualização operacional e dashboards de ativos"

# --------------------------------------------------------------------------- #
# Caminhos de dados
# --------------------------------------------------------------------------- #
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "data"
DATA_FILE = DATA_DIR / "equipamentos.json"

# Histórico de telemetria persistido (gerado/armazenado entre execuções)
HISTORICO_DIR = DATA_DIR / "historico"

# --------------------------------------------------------------------------- #
# Cadastro
# --------------------------------------------------------------------------- #
# Tipos de equipamentos suportados
TIPOS_EQUIPAMENTO = [
    "Motor Elétrico",
    "Bomba Centrífuga",
    "Compressor",
    "Ventilador / Exaustor",
    "Gerador",
    "Redutor",
    "Outro",
]

STATUS_OPCOES = ["Ativo", "Manutenção", "Inativo"]

# --------------------------------------------------------------------------- #
# Sprint 2 — Navegação por planta / área
# --------------------------------------------------------------------------- #
# Plantas industriais disponíveis para a navegação operacional.
PLANTAS = [
    "Planta Industrial Sul",
    "Planta Industrial Norte",
    "Centro de Distribuição",
]

# --------------------------------------------------------------------------- #
# Sprint 2 — Perfis de simulação da telemetria
# --------------------------------------------------------------------------- #
# Cada perfil define o comportamento do histórico de sensores gerado para o
# ativo, permitindo demonstrar motores saudáveis e motores em falha.
PERFIL_SAUDAVEL = "Saudável"
PERFIL_DEGRADACAO = "Em degradação"
PERFIL_CRITICO = "Crítico"
PERFIS_SIMULACAO = [PERFIL_SAUDAVEL, PERFIL_DEGRADACAO, PERFIL_CRITICO]

# Janela do histórico de telemetria gerado e persistido
HISTORICO_DIAS = 14          # dias de histórico
HISTORICO_PASSO_MIN = 60     # intervalo entre leituras (1 leitura por hora)

# --------------------------------------------------------------------------- #
# Limites para classificação semântica de leituras (cores no dashboard)
# --------------------------------------------------------------------------- #
# Vibração: zonas ISO 10816 para máquinas médias rígidas (15-300 kW), mm/s RMS
VIBRACAO_LIMITE_BOM = 2.8      # mm/s (zona A/B)
VIBRACAO_LIMITE_ALERTA = 4.5   # mm/s (zona B/C)
VIBRACAO_LIMITE_CRITICO = 7.1  # mm/s (zona C/D)

# Temperatura típica de carcaça de motor industrial, °C
TEMPERATURA_LIMITE_BOM = 70      # °C
TEMPERATURA_LIMITE_ALERTA = 90   # °C
TEMPERATURA_LIMITE_CRITICO = 110 # °C (referência de fim de escala do gauge)

# Tensão: desvio percentual aceitável em relação ao valor nominal
TENSAO_DESVIO_ALERTA = 0.05    # 5%
TENSAO_DESVIO_CRITICO = 0.10   # 10%

# Corrente: fração da corrente nominal a partir da qual há alerta
CORRENTE_FATOR_ALERTA = 1.10   # 110% do nominal
CORRENTE_FATOR_CRITICO = 1.20  # 120% do nominal

# Rotação: desvio percentual aceitável em relação ao valor nominal
ROTACAO_DESVIO_ALERTA = 0.05   # 5%
ROTACAO_DESVIO_CRITICO = 0.10  # 10%

# Resolução do conversor analógico-digital simulado (12 bits)
ADC_RESOLUTION = 4095
