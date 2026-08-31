"""Página de Cadastro / Edição da ficha técnica do equipamento."""

from datetime import date

import streamlit as st

from src.backend.models import Equipamento
from src.backend.repository import EquipamentoRepository
from src.backend.telemetria import TelemetriaService
from src.config.settings import (
    PERFIS_SIMULACAO,
    PLANTAS,
    STATUS_OPCOES,
    TIPOS_EQUIPAMENTO,
)


def _safe_index(opcoes: list, valor, default: int = 0) -> int:
    try:
        return opcoes.index(valor)
    except (ValueError, TypeError):
        return default


def render() -> None:
    repo = EquipamentoRepository()

    edicao = st.session_state.selected_equipment_id is not None
    atual = repo.buscar_por_id(st.session_state.selected_equipment_id) if edicao else None

    # ----------------------------------------------------------------- Header
    if edicao and atual is not None:
        col_a, col_b = st.columns([4, 1])
        col_a.title(f"📝 Ficha Técnica: {atual.tag}")
        col_a.caption("Visualize ou edite os dados técnicos deste equipamento.")
        if col_b.button("← Voltar", use_container_width=True):
            st.session_state.page = "consulta"
            st.session_state.selected_equipment_id = None
            st.rerun()
    elif edicao and atual is None:
        st.error("Equipamento não encontrado.")
        if st.button("← Voltar para a consulta"):
            st.session_state.page = "consulta"
            st.session_state.selected_equipment_id = None
            st.rerun()
        return
    else:
        st.title("📝 Novo Cadastro Técnico")
        st.caption("Preencha as informações para que o sistema 'conheça' este equipamento.")

    # ----------------------------------------------------------------- Formulário
    with st.form("form_equipamento", clear_on_submit=not edicao, border=True):

        # ---- Identificação
        st.subheader("🏷️ Identificação")
        col1, col2 = st.columns(2)
        tag = col1.text_input(
            "TAG de identificação *",
            value=atual.tag if atual else "",
            placeholder="Ex: MOT-001",
            help="Identificador único do equipamento na planta.",
        )
        modelo = col2.text_input(
            "Modelo *",
            value=atual.modelo if atual else "",
            placeholder="Ex: W22 IR3 Premium",
        )

        col1, col2 = st.columns(2)
        fabricante = col1.text_input(
            "Fabricante *",
            value=atual.fabricante if atual else "",
            placeholder="Ex: WEG",
        )
        tipo = col2.selectbox(
            "Tipo de equipamento *",
            options=TIPOS_EQUIPAMENTO,
            index=_safe_index(TIPOS_EQUIPAMENTO, atual.tipo if atual else None, default=0),
        )

        # ---- Características elétricas
        st.subheader("⚡ Características Elétricas / Mecânicas")
        col1, col2, col3 = st.columns(3)
        potencia = col1.number_input(
            "Potência (kW) *",
            min_value=0.0,
            step=0.1,
            value=float(atual.potencia_kw) if atual else 0.0,
            format="%.2f",
        )
        tensao = col2.number_input(
            "Tensão Nominal (V) *",
            min_value=0.0,
            step=1.0,
            value=float(atual.tensao_v) if atual else 220.0,
            format="%.1f",
        )
        corrente = col3.number_input(
            "Corrente Nominal (A) *",
            min_value=0.0,
            step=0.1,
            value=float(atual.corrente_nominal_a) if atual else 0.0,
            format="%.2f",
        )

        col1, col2 = st.columns(2)
        rpm = col1.number_input(
            "Rotação Nominal (RPM) *",
            min_value=0,
            step=10,
            value=int(atual.rotacao_nominal_rpm) if atual else 1750,
        )
        freq = col2.number_input(
            "Frequência (Hz) *",
            min_value=0.0,
            step=1.0,
            value=float(atual.frequencia_hz) if atual else 60.0,
            format="%.1f",
        )

        # ---- Complementares
        st.subheader("📋 Informações Complementares")
        col1, col2 = st.columns(2)
        numero_serie = col1.text_input(
            "Número de série",
            value=atual.numero_serie if atual else "",
            placeholder="Ex: 1024-XYZ-2024",
        )
        localizacao = col2.text_input(
            "Descrição da localização",
            value=atual.localizacao if atual else "",
            placeholder="Ex: Linha de Extrusão 1",
        )

        # ---- Localização hierárquica (navegação operacional — Sprint 2)
        col1, col2 = st.columns(2)
        planta = col1.selectbox(
            "Planta *",
            options=PLANTAS,
            index=_safe_index(PLANTAS, atual.planta if atual else None, default=0),
            help="Planta industrial usada na navegação do Dashboard Operacional.",
        )
        area = col2.text_input(
            "Área / Setor *",
            value=atual.area if atual else "",
            placeholder="Ex: Setor A - Extrusão",
            help="Área dentro da planta onde o motor está instalado.",
        )

        col1, col2 = st.columns(2)
        try:
            valor_data = (
                date.fromisoformat(atual.data_instalacao)
                if (atual and atual.data_instalacao) else date.today()
            )
        except ValueError:
            valor_data = date.today()

        data_inst = col1.date_input("Data de instalação", value=valor_data, format="DD/MM/YYYY")
        status = col2.selectbox(
            "Status operacional",
            options=STATUS_OPCOES,
            index=_safe_index(STATUS_OPCOES, atual.status if atual else None, default=0),
            help="Ativo: em operação · Manutenção: parado para serviço · Inativo: desligado",
        )

        observacoes = st.text_area(
            "Observações",
            value=atual.observacoes if atual else "",
            placeholder="Notas adicionais sobre o equipamento, histórico, particularidades…",
            height=100,
        )

        # ---- Telemetria (Sprint 2)
        st.subheader("🛰️ Telemetria")
        perfil_simulacao = st.selectbox(
            "Perfil de simulação da telemetria",
            options=PERFIS_SIMULACAO,
            index=_safe_index(
                PERFIS_SIMULACAO,
                atual.perfil_simulacao if atual else None,
                default=0,
            ),
            help=(
                "Define o comportamento dos dados de sensores exibidos no "
                "Dashboard Operacional. 'Saudável' gera telemetria estável; "
                "'Em degradação' e 'Crítico' geram tendências de falha "
                "(aumento de temperatura e vibração) para fins de demonstração."
            ),
        )

        st.caption("Os campos marcados com * são obrigatórios.")

        # ---- Botões
        col1, col2, _ = st.columns([1, 1, 2])
        if edicao:
            submit = col1.form_submit_button("💾 Salvar alterações", type="primary", use_container_width=True)
            cancelar = col2.form_submit_button("❌ Cancelar", use_container_width=True)
        else:
            submit = col1.form_submit_button("✅ Cadastrar equipamento", type="primary", use_container_width=True)
            cancelar = col2.form_submit_button("🔄 Limpar", use_container_width=True)

        # ---- Submissão
        if submit:
            erros = _validar(
                tag=tag, modelo=modelo, fabricante=fabricante,
                potencia=potencia, tensao=tensao, corrente=corrente, rpm=rpm,
                area=area,
            )

            # Verifica TAG duplicada (case-insensitive). Em edição, ignora a si mesmo.
            existente = repo.buscar_por_tag(tag.strip())
            if existente and (not edicao or existente.id != (atual.id if atual else None)):
                erros.append(f"A TAG '{tag.strip()}' já está cadastrada em outro equipamento.")

            if erros:
                for e in erros:
                    st.error(f"❌ {e}")
            else:
                if edicao and atual is not None:
                    atual.tag = tag.strip()
                    atual.modelo = modelo.strip()
                    atual.fabricante = fabricante.strip()
                    atual.tipo = tipo
                    atual.potencia_kw = float(potencia)
                    atual.tensao_v = float(tensao)
                    atual.corrente_nominal_a = float(corrente)
                    atual.rotacao_nominal_rpm = int(rpm)
                    atual.frequencia_hz = float(freq)
                    atual.numero_serie = numero_serie.strip()
                    atual.localizacao = localizacao.strip()
                    atual.planta = planta
                    atual.area = area.strip()
                    atual.perfil_simulacao = perfil_simulacao
                    atual.data_instalacao = data_inst.isoformat()
                    atual.status = status
                    atual.observacoes = observacoes.strip()
                    repo.atualizar(atual)
                    # Ficha técnica / perfil mudaram: recria o histórico de
                    # telemetria para refletir as novas especificações.
                    TelemetriaService().regenerar(atual)
                    st.cache_data.clear()
                    st.success(f"✅ Equipamento `{tag}` atualizado com sucesso!")
                else:
                    novo = Equipamento(
                        tag=tag.strip(),
                        modelo=modelo.strip(),
                        fabricante=fabricante.strip(),
                        tipo=tipo,
                        potencia_kw=float(potencia),
                        tensao_v=float(tensao),
                        corrente_nominal_a=float(corrente),
                        rotacao_nominal_rpm=int(rpm),
                        frequencia_hz=float(freq),
                        numero_serie=numero_serie.strip(),
                        localizacao=localizacao.strip(),
                        planta=planta,
                        area=area.strip(),
                        perfil_simulacao=perfil_simulacao,
                        data_instalacao=data_inst.isoformat(),
                        status=status,
                        observacoes=observacoes.strip(),
                    )
                    repo.salvar(novo)
                    st.success(f"✅ Equipamento `{tag}` cadastrado com sucesso!")
                    st.balloons()

        if cancelar:
            st.session_state.page = "consulta"
            st.session_state.selected_equipment_id = None
            st.rerun()

    # ----------------------------------------------------------------- Pós formulário (modo edição)
    if edicao and atual is not None:
        st.markdown("---")
        with st.expander("ℹ️ Metadados do registro", expanded=False):
            st.text(f"ID interno      : {atual.id}")
            st.text(f"Criado em       : {atual.criado_em}")
            if atual.atualizado_em:
                st.text(f"Atualizado em   : {atual.atualizado_em}")


# --------------------------------------------------------------------------- #
def _validar(*, tag, modelo, fabricante, potencia, tensao, corrente, rpm, area) -> list:
    erros: list[str] = []
    if not tag.strip():
        erros.append("TAG é obrigatória.")
    if not modelo.strip():
        erros.append("Modelo é obrigatório.")
    if not fabricante.strip():
        erros.append("Fabricante é obrigatório.")
    if not area.strip():
        erros.append("Área / Setor é obrigatória.")
    if potencia <= 0:
        erros.append("Potência deve ser maior que zero.")
    if tensao <= 0:
        erros.append("Tensão deve ser maior que zero.")
    if corrente <= 0:
        erros.append("Corrente nominal deve ser maior que zero.")
    if rpm <= 0:
        erros.append("Rotação nominal deve ser maior que zero.")
    return erros
