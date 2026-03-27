import streamlit as st
import pandas as pd
from datetime import datetime, time, date # Importar date e time
import json
from storage import escala_para_display, salvar_escala # Importa a função de display e salvar
from config import MAP_WEEKDAY_TO_NAME # Importar MAP_WEEKDAY_TO_NAME

def render(df_escala: pd.DataFrame):
    st.title("Gestão da Escala de Trabalho")

    # --- Seção de Adicionar/Editar Escala ---
    st.subheader("Adicionar ou Editar Entrada de Escala")

    # Obter lista de agentes únicos da escala existente ou do histórico (se houver)
    agentes_existentes = sorted(df_escala["agente"].unique().tolist()) if not df_escala.empty else []

    with st.form("form_escala"):
        col1, col2 = st.columns(2)
        with col1:
            agente_input = st.selectbox("Agente:", [""] + agentes_existentes, key="agente_escala_input")
            data_input = st.date_input("Data:", value=datetime.now().date(), key="data_escala_input")
            hora_inicio_input = st.time_input("Hora Início:", value=time(8, 0), key="inicio_escala_input")
        with col2:
            hora_fim_input = st.time_input("Hora Fim:", value=time(17, 0), key="fim_escala_input")
            intervalos_input = st.text_area("Intervalos (JSON, ex: [{\"inicio\":\"12:00\",\"fim\":\"13:00\"}]):", value="[]", key="intervalos_escala_input")
            observacao_input = st.text_area("Observação:", key="obs_escala_input")

        # Campo para ID de edição (opcional)
        id_edicao = st.number_input("ID da Entrada para Editar (deixe 0 para Adicionar Nova):", min_value=0, value=0, step=1, key="id_edicao_escala")

        submitted = st.form_submit_button("Salvar Escala")

        if submitted:
            if not agente_input:
                st.error("O nome do agente não pode ser vazio.")
            elif hora_inicio_input >= hora_fim_input:
                st.error("A hora de início deve ser anterior à hora de fim.")
            else:
                try:
                    # Validar JSON de intervalos
                    parsed_intervalos = json.loads(intervalos_input)
                    if not isinstance(parsed_intervalos, list):
                        raise ValueError("Intervalos devem ser uma lista JSON.")
                    for interval in parsed_intervalos:
                        if not isinstance(interval, dict) or "inicio" not in interval or "fim" not in interval:
                            raise ValueError("Cada intervalo deve ser um objeto com 'inicio' e 'fim'.")
                        # Tentar converter para time para validar formato
                        time.fromisoformat(interval["inicio"])
                        time.fromisoformat(interval["fim"])

                    nova_entrada = {
                        "agente": agente_input,
                        "data": data_input,
                        "hora_inicio_escala": hora_inicio_input,
                        "hora_fim_escala": hora_fim_input,
                        "dia_semana": MAP_WEEKDAY_TO_NAME[data_input.weekday()],
                        "dia_semana_num": data_input.weekday(),
                        "intervalos_json": intervalos_input, # Salvar como string JSON
                        "observacao": observacao_input
                    }

                    if id_edicao > 0 and not df_escala.empty:
                        # Edição
                        if id_edicao <= len(df_escala):
                            idx_real = id_edicao - 1
                            for key, value in nova_entrada.items():
                                df_escala.loc[idx_real, key] = value
                            salvar_escala(df_escala)
                            st.session_state.df_escala = df_escala # Atualiza o session_state
                            st.success(f"Entrada de escala ID {id_edicao} atualizada com sucesso!")
                            st.rerun()
                        else:
                            st.error(f"ID {id_edicao} não encontrado para edição.")
                    else:
                        # Adição
                        if df_escala.empty:
                            df_escala = pd.DataFrame([nova_entrada], columns=df_escala.columns if not df_escala.empty else nova_entrada.keys())
                        else:
                            df_escala = pd.concat([df_escala, pd.DataFrame([nova_entrada])], ignore_index=True)
                        salvar_escala(df_escala)
                        st.session_state.df_escala = df_escala # Atualiza o session_state
                        st.success("Nova entrada de escala adicionada com sucesso!")
                        st.rerun()

                except json.JSONDecodeError:
                    st.error("Formato JSON inválido para intervalos. Por favor, verifique.")
                except ValueError as ve:
                    st.error(f"Erro de validação: {ve}")
                except Exception as e:
                    st.error(f"Ocorreu um erro ao salvar a escala: {e}")

    st.subheader("Escala de Trabalho Atual")

    if df_escala.empty:
        st.info("Nenhum dado de escala disponível. Adicione entradas acima.")
        return

    # Usar a função escala_para_display do módulo storage para formatar
    df_escala_formatada = escala_para_display(df_escala)

    # Filtros para a tabela de escala
    col_filter1, col_filter2 = st.columns(2)
    with col_filter1:
        agentes_escala_filter = ["Todos"] + sorted(df_escala_formatada["Agente"].unique().tolist())
        agente_selecionado_escala_filter = st.selectbox("Filtrar por Agente:", agentes_escala_filter, key="filter_agente_escala")
    with col_filter2:
        dias_escala_filter = ["Todos"] + sorted(df_escala_formatada["Dia"].unique().tolist(), key=lambda x: list(MAP_WEEKDAY_TO_NAME.values()).index(x) if x in MAP_WEEKDAY_TO_NAME.values() else 99)
        dia_selecionado_escala_filter = st.selectbox("Filtrar por Dia:", dias_escala_filter, key="filter_dia_escala")

    df_escala_exibicao = df_escala_formatada.copy()
    if agente_selecionado_escala_filter != "Todos":
        df_escala_exibicao = df_escala_exibicao[df_escala_exibicao["Agente"] == agente_selecionado_escala_filter]
    if dia_selecionado_escala_filter != "Todos":
        df_escala_exibicao = df_escala_exibicao[df_escala_exibicao["Dia"] == dia_selecionado_escala_filter]

    if df_escala_exibicao.empty:
        st.info("Nenhuma entrada de escala encontrada com os filtros aplicados.")
    else:
        st.dataframe(df_escala_exibicao.set_index("ID"), use_container_width=True)

    # --- Seção de Excluir Escala ---
    st.subheader("Excluir Entrada de Escala")
    id_para_excluir = st.number_input("Digite o ID da entrada para excluir:", min_value=0, value=0, step=1, key="id_excluir_escala")
    if st.button("Excluir Entrada", key="btn_excluir_escala"):
        if id_para_excluir > 0 and not df_escala.empty:
            if id_para_excluir <= len(df_escala):
                idx_real = id_para_excluir - 1
                agente_excluido = df_escala.loc[idx_real, "agente"]
                data_excluida = df_escala.loc[idx_real, "data"].strftime('%d/%m/%Y')
                df_escala = df_escala.drop(idx_real).reset_index(drop=True)
                salvar_escala(df_escala)
                st.session_state.df_escala = df_escala # Atualiza o session_state
                st.success(f"Escala para {agente_excluido} em {data_excluida} excluída com sucesso!")
                st.rerun()
            else:
                st.error("ID inválido. Por favor, digite um ID existente na tabela.")
        else:
            st.info("Não há entradas de escala para excluir ou ID inválido.")
