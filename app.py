import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# Importar funções e configurações
from utils.data_loader import processar_arquivo, get_agentes
from tabs.tab_dashboard import render as tab_dashboard
from tabs.tab_aderencia import render as tab_aderencia
from tabs.tab_escala import render as tab_escala
from storage import carregar_historico, salvar_historico, limpar_historico, carregar_escala, salvar_escala, escala_para_display
from config import ESTADOS_ADMISSAO, ESTADOS_EXCLUIR, ESTADOS_PRODUTIVOS, ESTADOS_PAUSA, ESTADOS_IMPRODUTIVOS, CORES_ESTADOS, LIMITE_ALERTA_AWAY_MINUTOS

st.set_page_config(layout="wide", page_title="WFM Gantt & Dashboard")

def main():
    st.sidebar.title("Navegação")
    selected_tab = st.sidebar.radio("Escolha uma aba:", ["Dashboard", "Aderência", "Escala"])

    st.sidebar.header("Upload de Arquivo")
    arq = st.sidebar.file_uploader("Carregue seu arquivo de dados (CSV ou Excel)", type=["csv", "xlsx", "xls"])

    df_hist = pd.DataFrame()
    agentes = []

    if arq is not None:
        df_p = processar_arquivo(arq)
        if not df_p.empty:
            df_hist = df_p
            salvar_historico(df_hist) # Salva o histórico processado
            agentes = get_agentes(df_hist) # Get agents after processing
    else:
        df_hist = carregar_historico() # Tenta carregar o histórico salvo
        if not df_hist.empty:
            agentes = get_agentes(df_hist)

    if df_hist.empty:
        st.warning("Por favor, carregue um arquivo para visualizar os dados.")
        return

    # Filtros globais
    st.sidebar.header("Filtros")
    agente_selecionado = st.sidebar.selectbox("Selecione o Agente:", ["Todos"] + agentes)

    # Filtrar o DataFrame com base no agente selecionado
    if agente_selecionado != "Todos":
        df_filtrado_agente = df_hist[df_hist["agente"] == agente_selecionado]
    else:
        df_filtrado_agente = df_hist

    # Carregar a escala real usando a função de storage
    df_escala = carregar_escala()

    # Se a escala estiver vazia, podemos criar uma escala padrão inicial para preencher
    if df_escala.empty and not df_hist.empty:
        all_dates = pd.to_datetime(df_hist["inicio"].dt.date.unique())
        all_agents = df_hist["agente"].unique()
        df_escala_expanded = []
        for agent in all_agents:
            for date in all_dates:
                df_escala_expanded.append({
                    "agente": agent,
                    "data": date,
                    "hora_inicio_escala": pd.to_datetime("08:00:00").time(),
                    "hora_fim_escala": pd.to_datetime("17:00:00").time(),
                    "dia_semana": date.strftime("%A"), # Adiciona dia da semana
                    "dia_semana_num": date.weekday(), # Adiciona número do dia da semana
                    "intervalos_json": "[]", # Inicializa com JSON vazio
                    "observacao": ""
                })
        df_escala = pd.DataFrame(df_escala_expanded)
        df_escala["data"] = pd.to_datetime(df_escala["data"]) # Garante tipo datetime
        salvar_escala(df_escala) # Salva a escala padrão inicial

    # Renderizar a aba selecionada
    if selected_tab == "Dashboard":
        tab_dashboard.render(df_hist: pd.DataFrame, df_escala: pd.DataFrame, limite_alerta: int)
    elif selected_tab == "Aderência":
        tab_aderencia.render(df_filtrado_agente, df_escala)
    elif selected_tab == "Escala":
        tab_escala.render(df_escala)

if __name__ == "__main__":
    main()
