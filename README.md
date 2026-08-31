# Sistema de Gestão e Visualização Operacional de Ativos Industriais

Aplicação web para **cadastro técnico** de equipamentos industriais (motores, bombas, compressores, ventiladores) e **visualização operacional** da saúde desses ativos em tempo real e ao longo do tempo. Construída com **Streamlit**.

O sistema mantém a ficha técnica completa de cada ativo e oferece um **Dashboard Operacional** que conecta o cadastro (TAG) à sua localização (planta/área) e à sua telemetria, aplicando cores semânticas (verde / amarelo / vermelho) baseadas em normas como a ISO 10816 (vibração) para indicar se o motor está **saudável ou crítico**.

> **Sprint 1** estruturou a base de dados técnica e a conversão de sinais dos sensores.
> **Sprint 2** entrega a digitalização visual: navegação por planta/área, dashboards de telemetria, gráficos de séries temporais, alertas e a integração do cadastro com a placa do motor (visão computacional).
> **Sprint 3** adiciona a camada de inteligência operacional: um **Painel de Alertas e Estados** como página inicial, com resumos textuais (estrutura pronta para IA/NLP), apoio inicial à decisão para a manutenção e histórico de eventos.

---

## Funcionalidades

### Painel de Alertas e Estados (Sprint 3)

- **Página inicial da aplicação** — antes de escolher qualquer equipamento, o usuário vê o estado de todos os ativos monitorados.
- **Resumos inteligentes** — resumo textual do estado de cada ativo, gerado por uma camada de NLP (`src/backend/insights.py`). Hoje resolvida por uma heurística local, com um "gancho" para plugar um modelo de NLP real sem alterar o Front-End (ver seção *Arquitetura*).
- **Apoio inicial à decisão** — cada card traz recomendações objetivas para a equipe de manutenção, derivadas da(s) grandeza(s) que motivou o alerta (ex.: inspecionar rolamentos, verificar refrigeração, checar sobrecarga).
- **Atualização manual e automática** — botão "Atualizar dados agora" (simula nova aquisição para todos os ativos) e um timer opcional (`streamlit-autorefresh`) que repete a atualização em intervalo configurável.
- **Simulação de anomalia (demo)** — botão dedicado que injeta uma leitura crítica real em um ativo saudável (usando o próprio `SensorSimulator`, com o perfil "Crítico" só naquela leitura), para demonstrar a transição de estado sem esperar o histórico natural.
- **Gestão de estado dinâmica** — o estado visual de cada ativo (🟢/🟡/🔴) é recalculado a cada atualização; toda mudança de nível dispara uma notificação (`st.toast`) e é gravada no histórico de eventos.
- **Histórico de eventos** — linha do tempo persistida (`data/eventos/eventos.json`) com todas as transições de estado detectadas, quem mudou, de que nível para que nível e qual grandeza motivou.

### Dashboard Operacional (Sprint 2)

- **Navegação por Planta / Área** — estrutura hierárquica Planta → Área → Equipamento (TAG) para localizar qualquer motor da operação.
- **Visão geral da área** — grade de cartões com o estado de saúde de todos os ativos da seleção (saudáveis / em atenção / críticos).
- **Dashboard de Telemetria** — valores atuais dos sensores (Tensão, Corrente, Rotação, Temperatura, Vibração) com cor semântica por grandeza e desvio em relação ao nominal.
- **Indicadores (gauges)** — medidores de Temperatura, Vibração e Corrente com faixas coloridas verde/amarelo/vermelho.
- **Gráficos de séries temporais** — evolução histórica das grandezas (Plotly) com faixas de limite operacional, linha nominal e média móvel, para análise de tendências de degradação. Filtros de período (24 h / 3 / 7 / 14 dias).
- **Alertas e Status** — banner de estado geral do ativo + lista de alertas ativos derivados dos limites operacionais.
- **Cadastro Visual / Visão Computacional** — imagem da placa de identificação do motor (renderizada a partir do cadastro) com as caixas de detecção de OCR e a tabela de campos extraídos com a respectiva confiança.
- **Telemetria em tempo real** — botão que simula a aquisição de uma nova leitura e a anexa ao histórico persistido.

### Cadastro e consulta (Sprint 1)

- **Consulta de equipamentos** — datatable com filtros, planta/área e cards de resumo.
- **Cadastro técnico** — formulário completo com validação inline, TAG única e edição da ficha.
- **Exclusão protegida** — confirmação explícita antes de remover qualquer registro.
- **Painel de Dados Brutos** — leituras convertidas do sinal ADC para unidades de engenharia, com gráficos e exportação CSV/JSON.
- **Tema dark** de alto contraste, layout responsivo e sidebar de navegação.

---

## Mapa dos Requisitos da Sprint 3

| Requisito Funcional | Onde está implementado |
|---|---|
| Página inicial com Painel de Alertas e Estados | `src/frontend/pages/alertas.py` → `render()`, registrado como página padrão em `app.py` |
| Resumos inteligentes (integração com NLP) | `src/backend/insights.py` → `gerar_resumo()`; renderizado em `components/alert_card.py`. Arquitetura já preparada para um pipeline real em `src.ml.nlp_pipeline` (ver docstring do módulo) |
| Apoio inicial à decisão | `src/backend/insights.py` → `gerar_recomendacoes()`; cards em `components/alert_card.py` |
| Botão de atualização + timer automático | `alertas.py` → `_controles_atualizacao()` (botão sempre disponível; timer via `streamlit-autorefresh`, com *fallback* elegante se o pacote não estiver instalado) |
| Simulação de notificação/alerta | `alertas.py` → `_simular_anomalia_demo()`, reaproveitando `SensorSimulator`/`TelemetriaService` com `perfil_override` |
| Reaproveitamento da página inicial existente | Não havia página inicial dedicada — a antiga tela inicial (Dashboard) foi mantida intacta e o Painel de Alertas passou a ser a nova porta de entrada |

| Requisito Técnico | Como foi atendido |
|---|---|
| Componentização (cards de alerta / histórico de eventos) | `src/frontend/components/alert_card.py` e `src/frontend/components/event_timeline.py` — reutilizáveis fora da página de alertas |
| Gestão de estado dinâmica (botão ou timer) | `alertas.py` compara o nível de saúde a cada rerun (`_registrar_transicoes`) e atualiza a UI e o histórico de eventos automaticamente |
| Arquitetura desacoplada | O Front-End só consome `health.py`, `insights.py` e `eventos_repository.py` — nenhuma regra de negócio vive na página |
| UX/UI para decisão (cores semânticas consistentes) | Reaproveita as mesmas cores/emojis de `health.py` (`CORES`, `EMOJIS`, `ROTULOS`) já usados no Dashboard |

---

## Mapa dos Requisitos da Sprint 2

| Requisito Funcional | Onde está implementado |
|---|---|
| Navegação por Planta/Área | `dashboard.py` → `_barra_navegacao` (selectboxes Planta → Área → TAG) |
| Dashboard de Telemetria/Sensor | `dashboard.py` → `_cards_telemetria` e `_gauge` (aba *Telemetria & Status*) |
| Gráficos Temporais (Séries Temporais) | `dashboard.py` → `_grafico_unico` / `_grafico_geral` (aba *Séries Temporais*) |
| Alertas e Status | `dashboard.py` → `_banner_saude` e `_painel_alertas`; regras em `backend/health.py` |
| Integração de Cadastro Visual | `dashboard.py` → `_aba_cadastro_visual`; imagem e OCR em `backend/nameplate.py` |

| Requisito Técnico | Como foi atendido |
|---|---|
| Visualização de dados | **Plotly** (séries temporais e gauges) + **Matplotlib** (placa do motor) |
| Persistência de dados | Histórico de telemetria gravado em `data/historico/` e consumido pelos gráficos (`telemetria.py` + `historico_repository.py`) |
| UX/UI — rastreabilidade e controle | Trilha Planta › Área › Ativo, cores semânticas, filtros de período/grandeza, exportação CSV |

---

## Arquitetura

A aplicação é organizada em camadas, com a UI completamente desacoplada das regras de negócio e da persistência. É possível trocar o framework de interface (Streamlit → Gradio, FastAPI + React) sem alterar o backend.

```
.
├── app.py                          # Entry point Streamlit (roteamento)
├── requirements.txt
├── .streamlit/
│   └── config.toml                 # Tema visual
├── data/
│   ├── equipamentos.json           # Cadastro técnico (persistência)
│   ├── historico/                  # Histórico de telemetria por ativo (gerado em runtime)
│   └── eventos/                    # Histórico de eventos de alerta (gerado em runtime, Sprint 3)
└── src/
    ├── config/
    │   └── settings.py             # Constantes globais, plantas, perfis e limites
    ├── backend/
    │   ├── models.py               # Dataclass Equipamento
    │   ├── repository.py           # Persistência do cadastro
    │   ├── sensor_simulator.py     # Gerador de leituras brutas (histórico + tempo real)
    │   ├── converters.py           # ADC → unidade de engenharia
    │   ├── historico_repository.py # Persistência do histórico de telemetria
    │   ├── telemetria.py           # Serviço de telemetria (gera/persiste/lê histórico)
    │   ├── health.py               # Motor de avaliação de saúde (normal/atenção/crítico)
    │   ├── insights.py             # Resumos "IA/NLP" + apoio à decisão (Sprint 3)
    │   ├── eventos_repository.py   # Histórico de eventos de alerta (Sprint 3)
    │   └── nameplate.py            # Placa do motor + extração OCR simulada
    └── frontend/
        ├── components/
        │   ├── sidebar.py          # Menu lateral
        │   ├── alert_card.py       # Card reutilizável de alerta (Sprint 3)
        │   └── event_timeline.py   # Linha do tempo de eventos (Sprint 3)
        └── pages/
            ├── alertas.py          # Painel de Alertas e Estados — página inicial (Sprint 3)
            ├── dashboard.py        # Dashboard Operacional (Sprint 2)
            ├── consulta.py         # Lista de equipamentos
            ├── cadastro.py         # Formulário de cadastro / edição
            └── dados_brutos.py     # Painel de sensores (Sprint 1)
```

### Fluxo dos dados de telemetria

```
cadastro técnico (data/equipamentos.json)
        │
        ▼
SensorSimulator ──► converte ADC ──► TelemetriaService
        │                                   │
        │                                   ▼
        │                       data/historico/<id>.json   (persistência)
        │                                   │
        ▼                                   ▼
gerar_leitura_unica()  ──────────►  health.py (avaliar_leitura)
   (tempo real)                              │
                              ┌───────────────┼───────────────┐
                              ▼               ▼               ▼
                       Dashboard        insights.py      eventos_repository.py
                    (gráficos, gauges)  (resumo + apoio   (transições de estado
                                          à decisão)        → data/eventos/)
                                              │
                                              ▼
                                   Painel de Alertas e Estados
```

---

## Como rodar localmente

### Pré-requisitos

- Python 3.10+
- pip

### Instalação

```bash
git clone <url-do-repositorio>
cd challenge_sprint1_frontend

# (opcional) ambiente virtual
python -m venv .venv
.venv\Scripts\activate              # Windows PowerShell
# source .venv/bin/activate          # Linux / macOS

pip install -r requirements.txt
streamlit run app.py
```

A interface fica disponível em `http://localhost:8501`. O repositório já vem com 4 equipamentos de exemplo. O **histórico de telemetria é gerado e persistido automaticamente** em `data/historico/` na primeira vez que cada ativo é aberto no dashboard.

---

## Perfis de simulação da telemetria

Como ainda não há sensores reais, cada ativo tem um **perfil de simulação** que define como sua telemetria evolui no histórico de 14 dias — permitindo demonstrar motores saudáveis e motores caminhando para a falha:

| Perfil | Comportamento | Exemplo no projeto |
|---|---|---|
| **Saudável** | Temperatura e vibração estáveis dentro da faixa normal | `MOT-001`, `BMB-002` |
| **Em degradação** | Tendência crescente de temperatura e vibração até a zona de atenção | `VEN-004` |
| **Crítico** | Tendência acentuada que ultrapassa os limites seguros (falha iminente) | `CMP-003` |

O perfil é editável na tela de cadastro. Ao alterar a ficha técnica, o histórico do ativo é recriado para refletir as novas especificações.

---

## Limites de saúde (cores semânticas)

| Grandeza | 🟢 Normal | 🟡 Atenção | 🔴 Crítico |
|---|---|---|---|
| Tensão | desvio < 5% do nominal | 5–10% | > 10% |
| Corrente | < 110% do nominal | 110–120% | > 120% |
| Temperatura | < 70 °C | 70–90 °C | > 90 °C |
| Vibração | < 2.8 mm/s (ISO 10816 A/B) | 2.8–4.5 (B/C) | > 4.5 (C/D) |
| Rotação | desvio < 5% do nominal | 5–10% | > 10% |

As regras são centralizadas em `src/backend/health.py` e reutilizadas por todo o dashboard.

---

## Conversão de sinal: como funciona

Os sensores entregam um inteiro de 12 bits (`0` a `4095`) representando o valor analógico amostrado. Cada grandeza é mapeada linearmente para sua faixa física, usando os parâmetros nominais do equipamento:

| Grandeza | Faixa de saída |
|---|---|
| Tensão (V) | 0 a 2× nominal |
| Corrente (A) | 0 a 2× nominal |
| Rotação (RPM) | 0 a 2× nominal |
| Temperatura (°C) | 0 a 150 °C |
| Vibração (mm/s) | 0 a 10 mm/s (faixa típica ISO 10816) |

Os valores brutos são preservados ao lado dos convertidos: se a calibração mudar, os dados podem ser reconvertidos sem perda de informação.

---

## Deploy

A aplicação roda em qualquer ambiente que sustente um processo Python persistente com WebSocket. Vercel **não é compatível** (arquitetura serverless).

### Streamlit Community Cloud (mais simples)

1. Suba o repositório no GitHub (público).
2. Acesse [share.streamlit.io](https://share.streamlit.io) e faça login com GitHub.
3. **New app** → escolha o repositório → arquivo `app.py` → **Deploy**.

### Render.com / Railway / Hugging Face Spaces

- Build: `pip install -r requirements.txt`
- Start: `streamlit run app.py --server.port=$PORT --server.address=0.0.0.0`

---

## Stack

- **Python 3.10+**
- **Streamlit** — interface
- **Pandas** — manipulação tabular e séries temporais
- **Plotly** — gráficos interativos (séries temporais e gauges)
- **Matplotlib** — renderização da placa de identificação do motor
- **streamlit-autorefresh** — timer opcional de atualização automática do Painel de Alertas (Sprint 3)
- **JSON** — persistência local (cadastro, histórico de telemetria e histórico de eventos)

---

## Roadmap

A arquitetura desacoplada permite evoluir o sistema sem reescrever a UI:

- Substituir a heurística de `insights.py` por um modelo de NLP real (a interface pública já está pronta para isso — ver docstring do módulo).
- Detecção de anomalias por Machine Learning (hoje os alertas são por limiar/threshold, definidos em `settings.py`).
- Integração com modelo preditivo (treinamento offline + inferência online) e estimativa de RUL (*Remaining Useful Life*).
- Substituição do simulador por driver real (Modbus / MQTT / OPC-UA).
- Substituição do OCR simulado por um pipeline real de visão computacional sobre a foto da placa.
- Migração da persistência (cadastro, histórico de telemetria e histórico de eventos) para banco relacional ou time-series database.

---

## Qualidade — testes realizados nesta Sprint

O Painel de Alertas foi validado de ponta a ponta com `streamlit.testing.v1.AppTest` (execução headless de toda a navegação: alertas → dashboard → consulta → cadastro → dados brutos → alertas), cobrindo o fluxo completo de atualização, simulação de anomalia e registro de eventos. Esse processo revelou e corrigiu dois bugs reais, um deles pré-existente da Sprint 2:

1. **Cache-busting quebrado (`_buster` com underscore).** O `st.cache_data` do Streamlit ignora, de propósito, parâmetros cujo nome começa com `_` no cálculo da chave de cache (essa convenção existe para objetos não-hasheáveis). O padrão `_buster: int` usado para "forçar" recomputação após uma nova leitura, portanto, **nunca invalidava o cache** — o botão "Atualizar leitura" gravava a nova leitura em disco corretamente, mas a tela continuava mostrando o valor antigo até o processo reiniciar. Corrigido removendo o underscore (`buster`) em `dashboard.py`, `dados_brutos.py` e no novo `alertas.py`. Reproduzido isoladamente e confirmado antes e depois da correção.
2. **`st.image(..., use_column_width=True)` removido em versões recentes do Streamlit.** A aba "Cadastro Visual (OCR)" do Dashboard quebrava com `TypeError` ao ser aberta em uma instalação atual do Streamlit. Corrigido para `width="stretch"`, conforme a própria depreciação recomenda.

---

## Licença

Projeto educacional — FIAP Challenge.
