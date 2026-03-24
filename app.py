import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# Importar funções e configurações
from utils.data_loader import processar_arquivo, get_agentes
from tabs.tab_dashboard import render as tab_dashboard
from tabs.tab_aderencia import render as tab_aderencia
from tabs.tab_escala import render as tab_escala
from config import ESTADOS_ADMISSAO, ESTADOS_EXCLUIR, ESTADOS_PRODUTIVOS, ESTADOS_PAUSA, ESTADOS_IMPRODUTIVOS, CORES_STATUS

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
            agentes = get_agentes(df_hist) # Get agents after processing

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

    # Se a aba de escala for selecionada, precisamos de um df_escala.
    # Por enquanto, vamos criar um df_escala dummy ou assumir que ele virá de outro lugar.
    # Para o propósito deste exemplo, vamos criar um df_escala simples.
    # Em um cenário real, df_escala seria carregado ou gerado de outra fonte.
    df_escala = pd.DataFrame({
        "agente": df_hist["agente"].unique(),
        "data": pd.to_datetime(df_hist["inicio"].dt.date.unique()),
        "hora_inicio_escala": pd.to_datetime("08:00:00").time(),
        "hora_fim_escala": pd.to_datetime("17:00:00").time(),
    })
    # Expandir df_escala para ter uma linha por agente por dia
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
            })
    df_escala = pd.DataFrame(df_escala_expanded)
    df_escala["data"] = pd.to_datetime(df_escala["data"]) # Ensure datetime type

    # Renderizar a aba selecionada
    if selected_tab == "Dashboard":
        tab_dashboard.render(df_filtrado_agente, df_escala) # Pass df_escala
    elif selected_tab == "Aderência":
        tab_aderencia.render(df_filtrado_agente, df_escala) # Pass df_escala
    elif selected_tab == "Escala":
        tab_escala.render(df_escala) # Pass df_escala

if __name__ == "__main__":
    main()
