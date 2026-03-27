import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date, time # Importar date e time
from config import CORES_ESTADOS, ESTADOS_PRODUTIVOS, ESTADOS_PAUSA, ESTADOS_IMPRODUTIVOS

def _gantt_aderencia(df_hist: pd.DataFrame, df_escala: pd.DataFrame, agente: str, data_gantt: date): # data_gantt agora é date
    df_hist_agente_dia = df_hist[
        (df_hist["agente"] == agente) &
        (df_hist["data"] == data_gantt) # Comparar com datetime.date
    ].copy()

    df_escala_agente_dia = df_escala[
        (df_escala["agente"] == agente) &
        (df_escala["data"] == data_gantt) # Comparar com datetime.date
    ].copy()

    if df_hist_agente_dia.empty and df_escala_agente_dia.empty:
        st.warning(f"Não há dados de histórico ou escala para o agente {agente} em {data_gantt.strftime('%d/%m/%Y')}.")
        return go.Figure()

    # Preparar dados do histórico
    df_hist_agente_dia["tipo"] = "Real"
    df_hist_agente_dia["inicio_dt"] = df_hist_agente_dia["inicio"]
    df_hist_agente_dia["fim_dt"] = df_hist_agente_dia["fim"]

    # Preparar dados da escala
    df_escala_agente_dia["tipo"] = "Escala"
    # Combinar data com hora para criar datetime objects
    df_escala_agente_dia["inicio_dt"] = df_escala_agente_dia.apply(lambda r: datetime.combine(r["data"], r["hora_inicio_escala"]), axis=1)
    df_escala_agente_dia["fim_dt"] = df_escala_agente_dia.apply(lambda r: datetime.combine(r["data"], r["hora_fim_escala"]), axis=1)
    df_escala_agente_dia["estado"] = "Escala Prevista" # Estado para a escala

    # Combinar dados para o Gantt
    df_gantt = pd.concat([
        df_hist_agente_dia[["agente", "estado", "inicio_dt", "fim_dt", "tipo"]],
        df_escala_agente_dia[["agente", "estado", "inicio_dt", "fim_dt", "tipo"]]
    ], ignore_index=True)

    # Definir cores para o Gantt de aderência
    cores_aderencia = CORES_ESTADOS.copy()
    cores_aderencia["Escala Prevista"] = "#6c757d" # Cinza para a escala

    fig = px.timeline(
        df_gantt,
        x_start="inicio_dt",
        x_end="fim_dt",
        y="tipo", # Mostrar "Real" e "Escala" separadamente
        color="estado",
        color_discrete_map=cores_aderencia,
        title=f"Aderência da Escala para {agente} em {data_gantt.strftime('%d/%m/%Y')}",
        hover_name="estado",
        hover_data={
            "inicio_dt": "|%H:%M:%S",
            "fim_dt": "|%H:%M:%S",
            "agente": False,
            "tipo": False
        }
    )

    fig.update_yaxes(autorange="reversed")

    # Definir o range do eixo X para cobrir o dia inteiro
    data_inicio_dia = datetime.combine(data_gantt, time.min)
    data_fim_dia = datetime.combine(data_gantt, time.max)

    fig.update_xaxes(
        range=[data_inicio_dia, data_fim_dia],
        tickformat="%H:%M",
        dtick=3600000, # 1 hora em milissegundos
        showgrid=True,
        gridwidth=1,
        gridcolor='LightGrey'
    )

    # Adicionar linhas verticais para cada hora
    for h in range(24):
        fig.add_vline(
            x=datetime.combine(data_gantt, time(h)),
            line_width=1,
            line_dash="dot",
            line_color="gray"
        )

    fig.update_layout(
        xaxis_title="Hora do Dia",
        yaxis_title="Tipo de Registro",
        hovermode="x unified",
        height=400
    )

    return fig

def _calcular_metricas_aderencia(df_hist: pd.DataFrame, df_escala: pd.DataFrame) -> pd.DataFrame:
    if df_hist.empty or df_escala.empty:
        return pd.DataFrame()

    # Garantir que 'data' em df_escala seja datetime.date para o merge
    if 'data' in df_escala.columns:
        df_escala['data'] = pd.to_datetime(df_escala['data']).dt.date

    # Merge do histórico com a escala pela data e agente
    df_merged = pd.merge(
        df_hist,
        df_escala,
        on=["agente", "data"], # Merge pela data e agente
        how="left",
        suffixes=("_hist", "_escala")
    )

    # Preencher NaNs para agentes sem escala no dia (ou remover, dependendo da lógica)
    df_merged.dropna(subset=["hora_inicio_escala", "hora_fim_escala"], inplace=True)

    if df_merged.empty:
        return pd.DataFrame()

    # Calcular tempo produtivo, em pausa e improdutivo
    df_merged["Tempo Produtivo (min)"] = df_merged[df_merged["estado"].isin(ESTADOS_PRODUTIVOS)]["minutos"].fillna(0)
    df_merged["Tempo em Pausa (min)"] = df_merged[df_merged["estado"].isin(ESTADOS_PAUSA)]["minutos"].fillna(0)
    df_merged["Tempo Improdutivo (min)"] = df_merged[df_merged["estado"].isin(ESTADOS_IMPRODUTIVOS)]["minutos"].fillna(0)

    # Agrupar por agente e data para somar os tempos
    df_metricas = df_merged.groupby(["agente", "data"]).agg(
        {"Tempo Produtivo (min)": "sum",
         "Tempo em Pausa (min)": "sum",
         "Tempo Improdutivo (min)": "sum",
         "hora_inicio_escala": "first", # Pegar o primeiro horário de escala do dia
         "hora_fim_escala": "first"}    # Pegar o último horário de escala do dia
    ).reset_index()

    # Calcular duração da escala
    df_metricas["Duracao Escala (min)"] = (
        df_metricas.apply(lambda r: datetime.combine(r["data"], r["hora_fim_escala"]) - datetime.combine(r["data"], r["hora_inicio_escala"]), axis=1)
    ).dt.total_seconds() / 60
    df_metricas["Duracao Escala (min)"] = df_metricas["Duracao Escala (min)"].apply(lambda x: x if x > 0 else 0) # Garante duração não negativa

    # Calcular aderência e ociosidade
    df_metricas["Aderência (%)"] = (
        (df_metricas["Tempo Produtivo (min)"] + df_metricas["Tempo em Pausa (min)"]) / df_metricas["Duracao Escala (min)"]
    ) * 100
    df_metricas["Aderência (%)"] = df_metricas["Aderência (%)"].fillna(0).replace([float('inf'), -float('inf')], 0).round(2)
    df_metricas["Aderência (%)"] = df_metricas["Aderência (%)"].apply(lambda x: min(x, 100.0)) # Limita a 100%

    df_metricas["Ociosidade (%)"] = (df_metricas["Tempo Improdutivo (min)"] / df_metricas["Duracao Escala (min)"]) * 100
    df_metricas["Ociosidade (%)"] = df_metricas["Ociosidade (%)"].fillna(0).replace([float('inf'), -float('inf')], 0).round(2)
    df_metricas["Ociosidade (%)"] = df_metricas["Ociosidade (%)"].apply(lambda x: min(x, 100.0)) # Limita a 100%

    return df_metricas.sort_values(by=["data", "agente"])

def render(df_hist: pd.DataFrame, df_escala: pd.DataFrame):
    st.title("Relatório de Aderência Detalhada")

    if df_hist.empty:
        st.info("Nenhum dado disponível para o período e agente selecionados. Por favor, carregue um arquivo ou ajuste os filtros.")
        return

    min_date = df_hist["data"].min() if not df_hist.empty else datetime.now().date() # Usar df_hist["data"]
    max_date = df_hist["data"].max() if not df_hist.empty else datetime.now().date() # Usar df_hist["data"]

    col1, col2 = st.columns(2)
    with col1:
        data_inicio_aderencia = st.date_input("Data de Início:", min_value=min_date, max_value=max_date, value=min_date, key="aderencia_data_inicio")
    with col2:
        data_fim_aderencia = st.date_input("Data de Fim:", min_value=min_date, max_value=max_date, value=max_date, key="aderencia_data_fim")

    # Filtrar df_hist por data (agora comparando datetime.date)
    df_filtrado_aderencia = df_hist[
        (df_hist["data"] >= data_inicio_aderencia) &
        (df_hist["data"] <= data_fim_aderencia)
    ]

    if df_filtrado_aderencia.empty:
        st.warning("Não há dados para o período selecionado na Aderência.")
        return

    df_metricas_aderencia = _calcular_metricas_aderencia(df_filtrado_aderencia, df_escala)

    if df_metricas_aderencia.empty:
        st.warning("Não foi possível calcular as métricas de aderência para o período selecionado.")
        return

    st.subheader("Aderência Diária por Agente")
    st.dataframe(df_metricas_aderencia[[
        "agente", "data", "Duracao Escala (min)", "Tempo Produtivo (min)",
        "Tempo em Pausa (min)", "Tempo Improdutivo (min)", "Aderência (%)", "Ociosidade (%)"
    ]].set_index(["agente", "data"]), use_container_width=True)

    st.subheader("Aderência por Agente ao Longo do Tempo")
    fig_aderencia_tempo = px.line(
        df_metricas_aderencia,
        x="data",
        y="Aderência (%)",
        color="agente",
        title="Aderência Diária por Agente",
        labels={"data": "Data", "Aderência (%)": "Aderência (%)", "agente": "Agente"},
        hover_data={"Tempo Produtivo (min)": ":.2f", "Tempo em Pausa (min)": ":.2f", "Tempo Improdutivo (min)": ":.2f"}
    )
    fig_aderencia_tempo.update_layout(hovermode="x unified")
    st.plotly_chart(fig_aderencia_tempo, use_container_width=True)

    st.subheader("Visualização Detalhada (Gráfico de Gantt)")

    agentes_disponiveis = df_filtrado_aderencia["agente"].unique().tolist()
    if not agentes_disponiveis:
        st.warning("Nenhum agente disponível para o Gantt no período selecionado.")
        return

    col_gantt1, col_gantt2 = st.columns(2)
    with col_gantt1:
        agente_gantt = st.selectbox("Selecione o Agente para o Gantt (Aderência):", agentes_disponiveis, key="aderencia_agente_gantt")
    with col_gantt2:
        # Usar df_filtrado_aderencia["data"] que já é datetime.date
        datas_disponiveis = sorted(df_filtrado_aderencia[df_filtrado_aderencia["agente"] == agente_gantt]["data"].unique().tolist())
        if not datas_disponiveis:
            st.warning(f"Nenhuma data disponível para o agente {agente_gantt}.")
            return
        data_gantt = st.selectbox("Selecione o Dia para o Gantt (Aderência):", datas_disponiveis, key="aderencia_data_gantt")

    if agente_gantt and data_gantt:
        fig_gantt_aderencia = _gantt_aderencia(df_filtrado_aderencia, df_escala, agente_gantt, data_gantt) # Passar data_gantt como date
        st.plotly_chart(fig_gantt_aderencia, use_container_width=True)
