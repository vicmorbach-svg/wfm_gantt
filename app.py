import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time

# Importar funções e configurações
from utils.data_loader import processar_arquivo, get_agentes
from tabs.tab_dashboard import render as tab_dashboard
from tabs.tab_aderencia import render as tab_aderencia
from tabs.tab_escala import render as tab_escala
from storage import carregar_historico, salvar_historico, limpar_historico, carregar_escala, salvar_escala
from config import ESTADOS_INTERESSE, CORES_ESTADOS, LIMITE_ALERTA_AWAY_MINUTOS, MAP_WEEKDAY_TO_NAME

st.set_page_config(layout="wide", page_title="WFM Gantt & Dashboard")

# Inicializa o estado da sessão para o DataFrame de histórico e escala
if 'df_hist' not in st.session_state:
    st.session_state.df_hist = carregar_historico()
if 'df_escala' not in st.session_state:
    st.session_state.df_escala = carregar_escala()

def main():
    st.sidebar.title("Navegação")
    selected_tab = st.sidebar.radio("Escolha uma aba:", ["Dashboard", "Aderência", "Escala"])

    st.sidebar.header("Upload de Arquivo de Dados")
    arq = st.sidebar.file_uploader("Carregue seu arquivo de dados (CSV ou Excel)", type=["csv", "xlsx", "xls"])

    if arq is not None:
        df_p = processar_arquivo(arq)
        if not df_p.empty:
            st.session_state.df_hist = df_p
            salvar_historico(st.session_state.df_hist)
            st.sidebar.success("Arquivo processado e histórico atualizado!")
        else:
            st.sidebar.error("Falha ao processar o arquivo. Verifique o formato e as colunas.")

    # Recarregar histórico e escala após upload ou se já existirem
    df_hist = st.session_state.df_hist
    df_escala = st.session_state.df_escala

    if df_hist.empty:
        st.warning("Por favor, carregue um arquivo de dados para visualizar as informações.")
        # Se não há histórico, não há agentes para filtrar nem datas
        agentes = []
        min_date = datetime.now().date()
        max_date = datetime.now().date()
    else:
        agentes = get_agentes(df_hist)
        min_date = df_hist["data"].min()
        max_date = df_hist["data"].max()

    # --- Filtros Globais ---
    st.sidebar.header("Filtros Globais")

    # Filtro de data
    if not df_hist.empty:
        data_selecionada = st.sidebar.date_input(
            "Selecione a Data:",
            value=max_date, # Padrão para a data mais recente
            min_value=min_date,
            max_value=max_date,
            key="global_date_filter"
        )
    else:
        data_selecionada = datetime.now().date() # Fallback

    # Filtrar o histórico pelo dia selecionado
    df_hist_filtrado_data = df_hist[df_hist["data"] == data_selecionada] if not df_hist.empty else pd.DataFrame()

    # Filtro de agente (aplica-se aos dados já filtrados por data)
    agentes_disponiveis_para_filtro = ["Todos"] + sorted(df_hist_filtrado_data["agente"].unique().tolist()) if not df_hist_filtrado_data.empty else ["Todos"]
    agente_selecionado_global = st.sidebar.selectbox(
        "Selecione o Agente (Global):",
        agentes_disponiveis_para_filtro,
        key="global_agente_filter"
    )

    if agente_selecionado_global != "Todos":
        df_hist_filtrado_global = df_hist_filtrado_data[df_hist_filtrado_data["agente"] == agente_selecionado_global]
    else:
        df_hist_filtrado_global = df_hist_filtrado_data.copy()

    # --- Gerar Escala Padrão se Vazia ---
    if df_escala.empty and not df_hist.empty:
        st.sidebar.info("Nenhuma escala encontrada. Gerando uma escala padrão inicial (08:00-17:00) para todos os agentes e datas no histórico.")
        all_dates_in_hist = pd.to_datetime(df_hist["data"].unique())
        all_agents_in_hist = df_hist["agente"].unique()
        df_escala_expanded = []
        for agent in all_agents_in_hist:
            for date_obj in all_dates_in_hist:
                df_escala_expanded.append({
                    "agente": agent,
                    "data": date_obj, # Já é datetime.date
                    "hora_inicio_escala": time(8, 0),
                    "hora_fim_escala": time(17, 0),
                    "dia_semana": MAP_WEEKDAY_TO_NAME[date_obj.weekday()],
                    "dia_semana_num": date_obj.weekday(),
                    "intervalos_json": "[]",
                    "observacao": ""
                })
        st.session_state.df_escala = pd.DataFrame(df_escala_expanded)
        salvar_escala(st.session_state.df_escala)
        df_escala = st.session_state.df_escala # Atualiza a referência

    # Renderizar a aba selecionada
    if selected_tab == "Dashboard":
        tab_dashboard.render(df_hist_filtrado_global, df_escala, LIMITE_ALERTA_AWAY_MINUTOS, data_selecionada)
    elif selected_tab == "Aderência":
        # Para a aba de aderência, passamos o df_hist filtrado apenas pelo agente global,
        # pois ela tem seus próprios filtros de data de início/fim.
        # No entanto, se o filtro global de agente for "Todos", passamos o df_hist completo
        # para o período selecionado na própria aba de aderência.
        if agente_selecionado_global != "Todos":
            df_hist_para_aderencia = df_hist[df_hist["agente"] == agente_selecionado_global]
        else:
            df_hist_para_aderencia = df_hist.copy() # A aba de aderência fará o filtro de data

        tab_aderencia.render(df_hist_para_aderencia, df_escala)
    elif selected_tab == "Escala":
        tab_escala.render(df_escala, agentes) # Passa a lista de agentes para o seletor na aba de escala

if __name__ == "__main__":
    main()
