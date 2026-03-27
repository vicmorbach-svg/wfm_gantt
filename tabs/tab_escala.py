import streamlit as st
import pandas as pd
from datetime import datetime, time, date # Importar date e time
import json
from storage import escala_para_display, salvar_escala, carregar_escala # Importar salvar_escala e carregar_escala
from config import MAP_WEEKDAY_TO_NAME # Para mapear dia da semana

def render(df_escala: pd.DataFrame):
    st.title("Gestão da Escala")

    # Recarregar escala para garantir que as operações de CRUD sejam refletidas
    df_escala = carregar_escala()

    if df_escala.empty:
        st.info("Nenhum dado de escala disponível. Adicione uma escala abaixo.")
    else:
        st.subheader("Escala de Trabalho Atual")
        # Usar a função escala_para_display do módulo storage para formatar
        df_escala_formatada = escala_para_display(df_escala)
        st.dataframe(df_escala_formatada.set_index(["Agente", "Data", "Dia"]), use_container_width=True)

    st.subheader("Adicionar/Editar Entrada de Escala")

    # Obter lista de agentes do histórico (se houver) ou da escala existente
    agentes_existentes = sorted(df_escala["agente"].unique().tolist()) if not df_escala.empty else []
    # Se houver histórico, podemos pegar agentes de lá também
    if 'df_hist' in st.session_state and not st.session_state.df_hist.empty:
        agentes_do_historico = st.session_state.df_hist["agente"].unique().tolist()
        agentes_existentes = sorted(list(set(agentes_existentes + agentes_do_historico)))

    with st.form("form_escala"):
        col1, col2 = st.columns(2)
        with col1:
            agente_selecionado = st.selectbox("Agente:", ["Novo Agente"] + agentes_existentes, key="escala_agente_select")
            if agente_selecionado == "Novo Agente":
                novo_agente = st.text_input("Nome do Novo Agente:", key="escala_novo_agente_input")
                agente_final = novo_agente if novo_agente else None
            else:
                agente_final = agente_selecionado

            data_escala = st.date_input("Data da Escala:", value=datetime.now().date(), key="escala_data_input")
            hora_inicio = st.time_input("Hora de Início:", value=time(8, 0), key="escala_inicio_input")
            hora_fim = st.time_input("Hora de Fim:", value=time(17, 0), key="escala_fim_input")

        with col2:
            intervalos_json_str = st.text_area("Intervalos (JSON - ex: [{\"nome\": \"Almoço\", \"inicio\": \"12:00\", \"fim\": \"13:00\"}]):", value="[]", key="escala_intervalos_input")
            observacao = st.text_area("Observação:", key="escala_observacao_input")

        submitted = st.form_submit_button("Salvar Escala")

        if submitted:
            if not agente_final:
                st.error("Por favor, insira o nome do agente.")
            elif hora_inicio >= hora_fim:
                st.error("A hora de início deve ser anterior à hora de fim.")
            else:
                try:
                    # Validar JSON de intervalos
                    intervalos_validos = json.loads(intervalos_json_str)
                    if not isinstance(intervalos_validos, list):
                        raise ValueError("O JSON de intervalos deve ser uma lista.")
                    for intervalo in intervalos_validos:
                        if not all(k in intervalo for k in ["nome", "inicio", "fim"]):
                            raise ValueError("Cada intervalo deve ter 'nome', 'inicio' e 'fim'.")
                        # Tentar converter para time para validar formato
                        time.fromisoformat(intervalo["inicio"])
                        time.fromisoformat(intervalo["fim"])

                    nova_entrada = {
                        "agente": agente_final,
                        "data": data_escala,
                        "dia_semana": MAP_WEEKDAY_TO_NAME[data_escala.weekday()],
                        "dia_semana_num": data_escala.weekday(),
                        "hora_inicio_escala": hora_inicio,
                        "hora_fim_escala": hora_fim,
                        "intervalos_json": intervalos_json_str,
                        "observacao": observacao
                    }

                    # Verificar se já existe uma entrada para o mesmo agente e data
                    idx_existente = df_escala[
                        (df_escala["agente"] == agente_final) &
                        (df_escala["data"] == data_escala)
                    ].index

                    if not idx_existente.empty:
                        # Atualizar entrada existente
                        df_escala.loc[idx_existente, list(nova_entrada.keys())] = list(nova_entrada.values())
                        st.success(f"Escala para {agente_final} em {data_escala.strftime('%d/%m/%Y')} atualizada com sucesso!")
                    else:
                        # Adicionar nova entrada
                        df_escala = pd.concat([df_escala, pd.DataFrame([nova_entrada])], ignore_index=True)
                        st.success(f"Escala para {agente_final} em {data_escala.strftime('%d/%m/%Y')} adicionada com sucesso!")

                    salvar_escala(df_escala)
                    st.session_state.df_escala = df_escala # Atualiza o session_state
                    st.rerun() # Recarrega a página para mostrar a escala atualizada

                except json.JSONDecodeError:
                    st.error("Formato JSON inválido para os intervalos. Por favor, verifique a sintaxe.")
                except ValueError as ve:
                    st.error(f"Erro de validação: {ve}")
                except Exception as e:
                    st.error(f"Ocorreu um erro ao salvar a escala: {e}")

    st.subheader("Excluir Entrada de Escala")
    if not df_escala.empty:
        df_escala_formatada_para_excluir = df_escala_formatada.copy()
        df_escala_formatada_para_excluir["ID"] = df_escala_formatada_para_excluir.index # Adiciona um ID para seleção

        st.dataframe(df_escala_formatada_para_excluir.set_index("ID"), use_container_width=True)

        id_para_excluir = st.number_input("Digite o ID da entrada de escala para excluir:", min_value=0, max_value=len(df_escala)-1, step=1, key="escala_excluir_id")

        if st.button("Excluir Escala", key="escala_excluir_button"):
            if id_para_excluir in df_escala.index:
                agente_excluido = df_escala.loc[id_para_excluir, "agente"]
                data_excluida = df_escala.loc[id_para_excluir, "data"].strftime('%d/%m/%Y')
                df_escala = df_escala.drop(id_para_excluir).reset_index(drop=True)
                salvar_escala(df_escala)
                st.session_state.df_escala = df_escala # Atualiza o session_state
                st.success(f"Escala para {agente_excluido} em {data_excluida} excluída com sucesso!")
                st.rerun()
            else:
                st.error("ID inválido. Por favor, digite um ID existente na tabela.")
    else:
        st.info("Não há entradas de escala para excluir.")
