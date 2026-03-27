import streamlit as st
import pandas as pd
from datetime import datetime, time, timedelta
import json # Importar json para lidar com intervalos
from storage import escala_para_display, salvar_escala, carregar_escala # Importar funções de salvar/carregar
from config import MAP_WEEKDAY_TO_NAME, DIAS_SEMANA_ORDEM # Para dias da semana

def render(df_escala_original: pd.DataFrame, agentes_disponiveis: list):
    st.title("Gestão da Escala")

    # Usar uma cópia para não modificar o DataFrame original diretamente
    df_escala = df_escala_original.copy()

    st.subheader("Escala de Trabalho Atual")

    if df_escala.empty:
        st.warning("Nenhum dado de escala disponível. Adicione uma nova escala abaixo.")
    else:
        # Usar a função escala_para_display do módulo storage para formatar
        df_escala_formatada = escala_para_display(df_escala)

        # Opcional: Adicionar filtros para a escala exibida
        agentes_escala_display = ["Todos"] + sorted(df_escala_formatada["Agente"].unique().tolist())
        agente_selecionado_escala = st.selectbox("Filtrar escala por agente:", agentes_escala_display, key="filter_escala_agente")

        if agente_selecionado_escala != "Todos":
            df_escala_filtrada = df_escala_formatada[df_escala_formatada["Agente"] == agente_selecionado_escala]
        else:
            df_escala_filtrada = df_escala_formatada

        st.dataframe(df_escala_filtrada.set_index(["Agente", "Data", "Dia"]), use_container_width=True)

    st.subheader("Adicionar/Editar Escala")

    with st.form("form_escala"):
        col1, col2 = st.columns(2)
        with col1:
            agente = st.selectbox("Agente:", agentes_disponiveis, key="escala_agente_select")
            data_escala = st.date_input("Data da Escala:", value=datetime.now().date(), key="escala_data_input")
            hora_inicio = st.time_input("Hora de Início do Turno:", value=time(8, 0), key="escala_inicio_input")
            hora_fim = st.time_input("Hora de Fim do Turno:", value=time(17, 0), key="escala_fim_input")
        with col2:
            st.markdown("---") # Separador visual
            st.write("Intervalos (Ex: Almoço 12:00-13:00; Pausa 15:00-15:15)")
            intervalos_str = st.text_area("Intervalos (JSON ou texto simples):", value="[]", key="escala_intervalos_input")
            observacao = st.text_area("Observação:", key="escala_observacao_input")

        submitted = st.form_submit_button("Salvar Escala")

        if submitted:
            if agente and data_escala and hora_inicio and hora_fim:
                # Validar horários
                if hora_inicio >= hora_fim:
                    st.error("A hora de início do turno deve ser anterior à hora de fim.")
                else:
                    # Tentar parsear intervalos como JSON, se falhar, salvar como string
                    try:
                        json.loads(intervalos_str) # Tenta carregar para validar
                        intervalos_json = intervalos_str
                    except json.JSONDecodeError:
                        st.warning("Formato de intervalos inválido. Salvando como texto simples. Por favor, use formato JSON válido (ex: [{\"nome\": \"Almoço\", \"inicio\": \"12:00\", \"fim\": \"13:00\"}]).")
                        intervalos_json = json.dumps([{"nome": "Custom", "inicio": "N/A", "fim": "N/A", "descricao": intervalos_str}]) # Salva como um JSON com a string

                    # Converter data_escala para datetime para consistência
                    data_escala_dt = datetime.combine(data_escala, time.min)

                    novo_registro = {
                        "agente": agente,
                        "data": data_escala_dt,
                        "dia_semana": MAP_WEEKDAY_TO_NAME[data_escala.weekday()],
                        "dia_semana_num": data_escala.weekday(),
                        "hora_inicio_escala": hora_inicio,
                        "hora_fim_escala": hora_fim,
                        "intervalos_json": intervalos_json,
                        "observacao": observacao
                    }

                    # Verificar se já existe uma escala para o agente e data
                    idx_existente = df_escala[
                        (df_escala["agente"] == agente) &
                        (df_escala["data"].dt.date == data_escala)
                    ].index

                    if not idx_existente.empty:
                        # Atualizar registro existente
                        for key, value in novo_registro.items():
                            df_escala.loc[idx_existente, key] = value
                        st.success(f"Escala para {agente} em {data_escala.strftime('%d/%m/%Y')} atualizada com sucesso!")
                    else:
                        # Adicionar novo registro
                        df_escala = pd.concat([df_escala, pd.DataFrame([novo_registro])], ignore_index=True)
                        st.success(f"Escala para {agente} em {data_escala.strftime('%d/%m/%Y')} adicionada com sucesso!")

                    salvar_escala(df_escala)
                    st.rerun() # Recarrega a página para mostrar a escala atualizada
            else:
                st.error("Por favor, preencha todos os campos obrigatórios da escala.")

    st.subheader("Excluir Escala")
    if not df_escala.empty:
        agentes_para_excluir = sorted(df_escala["agente"].unique().tolist())
        agente_excluir = st.selectbox("Selecione o Agente para excluir escala:", [""] + agentes_para_excluir, key="excluir_agente_select")

        if agente_excluir:
            datas_para_excluir = sorted(df_escala[df_escala["agente"] == agente_excluir]["data"].dt.date.unique().tolist())
            data_excluir = st.selectbox(f"Selecione a Data da escala de {agente_excluir} para excluir:", [""] + datas_para_excluir, key="excluir_data_select")

            if data_excluir:
                if st.button(f"Confirmar Exclusão da Escala para {agente_excluir} em {data_excluir.strftime('%d/%m/%Y')}"):
                    df_escala = df_escala[
                        ~((df_escala["agente"] == agente_excluir) & (df_escala["data"].dt.date == data_excluir))
                    ].reset_index(drop=True)
                    salvar_escala(df_escala)
                    st.success("Escala excluída com sucesso!")
                    st.rerun()
    else:
        st.info("Não há escalas para excluir.")
