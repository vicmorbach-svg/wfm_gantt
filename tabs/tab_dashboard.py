import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, time, timedelta
from config import CORES_STATUS, ESTADOS_PRODUTIVOS, ESTADOS_PAUSA, ESTADOS_IMPRODUTIVOS, DIAS_SEMANA_ORDEM

def _gantt_chart(df_agente_dia: pd.DataFrame, agente_gantt: str, data_gantt: datetime):
    if df_agente_dia.empty:
        st.warning(f"Não há dados para o agente {agente_gantt} no dia {data_gantt.strftime('%d/%m/%Y')}.")
        return go.Figure()

    # Filtrar para o agente e dia selecionados
    df_gantt = df_agente_dia[
        (df_agente_dia["agente"] == agente_gantt) &
        (df_agente_dia["inicio"].dt.date == data_gantt.date())
    ].copy() # Use .copy() to avoid SettingWithCopyWarning

    if df_gantt.empty:
        st.warning(f"Não há dados para o agente {agente_gantt} no dia {data_gantt.strftime('%d/%m/%Y')}.")
        return go.Figure()

    # Garantir que as colunas de tempo são datetime
    df_gantt["inicio"] = pd.to_datetime(df_gantt["inicio"])
    df_gantt["fim"] = pd.to_datetime(df_gantt["fim"])

    # Ordenar por início para garantir a sequência correta
    df_gantt = df_gantt.sort_values(by="inicio").reset_index(drop=True)

    # Criar o gráfico de Gantt
    fig = px.timeline(
        df_gantt,
        x_start="inicio",
        x_end="fim",
        y="agente",
        color="estado",
        color_discrete_map=CORES_STATUS,
        title=f"Linha do Tempo do Agente: {agente_gantt} em {data_gantt.strftime('%d/%m/%Y')}"
    )

    # Ajustar o layout do gráfico
    fig.update_layout(
        xaxis_title="Hora do Dia",
        yaxis_title="Agente",
        hovermode="x unified",
        barmode="overlay",
        height=200,
        margin=dict(l=140, r=20, t=60, b=50),
        xaxis=dict(
            tickformat="%H:%M",
            dtick="H1", # Tick a cada hora
            range=[
                datetime(data_gantt.year, data_gantt.month, data_gantt.day, 0, 0, 0),
                datetime(data_gantt.year, data_gantt.month, data_gantt.day, 23, 59, 59)
            ]
        )
    )

    # Adicionar linhas verticais para cada hora do dia
    for h in range(24):
        # Corrected datetime construction: ensure h is an integer for hour
        fig.add_vline(
            x=datetime(data_gantt.year, data_gantt.month, data_gantt.day, h, 0, 0).timestamp() * 1000, # Plotly expects milliseconds
            line_width=0.5,
            line_dash="dot",
            line_color="gray",
            annotation_text=f"{h:02d}:00",
            annotation_position="top right",
            annotation_font_size=10,
            annotation_font_color="gray"
        )

    fig.update_yaxes(autorange="reversed") # Inverte a ordem para o agente aparecer no topo
    return fig

def _calcular_metricas_diarias(df_filtrado: pd.DataFrame, df_escala: pd.DataFrame):
    if df_filtrado.empty:
        return pd.DataFrame()

    # Garantir que 'inicio' é datetime e extrair a data
    df_filtrado['data'] = df_filtrado['inicio'].dt.normalize()

    # Calcular tempo total em cada estado por agente por dia
    df_sum = df_filtrado.groupby(["agente", "data", "estado"])["minutos"].sum().reset_index()

    # Pivotar para ter estados como colunas
    df_pivot = df_sum.pivot_table(index=["agente", "data"], columns="estado", values="minutos", fill_value=0).reset_index()

    # Calcular tempo produtivo, pausa e improdutivo
    df_pivot["Tempo Produtivo (min)"] = df_pivot[[col for col in ESTADOS_PRODUTIVOS if col in df_pivot.columns]].sum(axis=1)
    df_pivot["Tempo em Pausa (min)"] = df_pivot[[col for col in ESTADOS_PAUSA if col in df_pivot.columns]].sum(axis=1)
    df_pivot["Tempo Improdutivo (min)"] = df_pivot[[col for col in ESTADOS_IMPRODUTIVOS if col in df_pivot.columns]].sum(axis=1)

    # Merge com a escala para obter as horas de trabalho esperadas
    df_metricas = pd.merge(df_pivot, df_escala, on=["agente", "data"], how="left")

    # Calcular duração da escala em minutos
    # Converter hora_inicio_escala e hora_fim_escala para datetime para o cálculo
    df_metricas['inicio_escala_dt'] = df_metricas.apply(lambda row: datetime.combine(row['data'], row['hora_inicio_escala']), axis=1)
    df_metricas['fim_escala_dt'] = df_metricas.apply(lambda row: datetime.combine(row['data'], row['hora_fim_escala']), axis=1)
    df_metricas["Duracao Escala (min)"] = (df_metricas["fim_escala_dt"] - df_metricas["inicio_escala_dt"]).dt.total_seconds() / 60

    # Calcular aderência
    # Aderência = (Tempo Produtivo + Tempo em Pausa) / Duração da Escala
    df_metricas["Aderência (%)"] = (
        (df_metricas["Tempo Produtivo (min)"] + df_metricas["Tempo em Pausa (min)"]) / df_metricas["Duracao Escala (min)"]
    ) * 100
    df_metricas["Aderência (%)"] = df_metricas["Aderência (%)"].fillna(0).round(2)

    # Calcular Ociosidade
    # Ociosidade = Tempo Improdutivo / Duração da Escala
    df_metricas["Ociosidade (%)"] = (df_metricas["Tempo Improdutivo (min)"] / df_metricas["Duracao Escala (min)"]) * 100
    df_metricas["Ociosidade (%)"] = df_metricas["Ociosidade (%)"].fillna(0).round(2)

    return df_metricas.sort_values(by=["data", "agente"])

def render(df_hist: pd.DataFrame, df_escala: pd.DataFrame):
    st.title("Dashboard de Aderência e Produtividade")

    # Filtros de data para o dashboard
    min_date = df_hist["inicio"].min().date() if not df_hist.empty else datetime.now().date()
    max_date = df_hist["inicio"].max().date() if not df_hist.empty else datetime.now().date()

    col1, col2 = st.columns(2)
    with col1:
        data_inicio_dashboard = st.date_input("Data de Início:", min_value=min_date, max_value=max_date, value=min_date)
    with col2:
        data_fim_dashboard = st.date_input("Data de Fim:", min_value=min_date, max_value=max_date, value=max_date)

    # Converter para datetime para comparação
    data_inicio_dashboard_dt = datetime.combine(data_inicio_dashboard, time.min)
    data_fim_dashboard_dt = datetime.combine(data_fim_dashboard, time.max)

    df_filtrado_dashboard = df_hist[
        (df_hist["inicio"] >= data_inicio_dashboard_dt) &
        (df_hist["inicio"] <= data_fim_dashboard_dt)
    ]

    if df_filtrado_dashboard.empty:
        st.warning("Não há dados para o período selecionado no Dashboard.")
        return

    # Calcular métricas diárias
    df_metricas_diarias = _calcular_metricas_diarias(df_filtrado_dashboard, df_escala)

    if df_metricas_diarias.empty:
        st.warning("Não foi possível calcular as métricas diárias para o período selecionado.")
        return

    st.subheader("Métricas Diárias por Agente")
    st.dataframe(df_metricas_diarias[[
        "agente", "data", "Tempo Produtivo (min)", "Tempo em Pausa (min)",
        "Tempo Improdutivo (min)", "Duracao Escala (min)", "Aderência (%)", "Ociosidade (%)"
    ]].set_index(["agente", "data"]))

    # Gráfico de Aderência Média por Agente
    st.subheader("Aderência Média por Agente")
    df_aderencia_media = df_metricas_diarias.groupby("agente")["Aderência (%)"].mean().reset_index()
    fig_aderencia_media = px.bar(
        df_aderencia_media,
        x="agente",
        y="Aderência (%)",
        title="Aderência Média por Agente",
        labels={"agente": "Agente", "Aderência (%)": "Aderência Média (%)"},
        color="Aderência (%)",
        color_continuous_scale=px.colors.sequential.Viridis
    )
    st.plotly_chart(fig_aderencia_media, use_container_width=True)

    # Gráfico de Ociosidade Média por Agente
    st.subheader("Ociosidade Média por Agente")
    df_ociosidade_media = df_metricas_diarias.groupby("agente")["Ociosidade (%)"].mean().reset_index()
    fig_ociosidade_media = px.bar(
        df_ociosidade_media,
        x="agente",
        y="Ociosidade (%)",
        title="Ociosidade Média por Agente",
        labels={"agente": "Agente", "Ociosidade (%)": "Ociosidade Média (%)"},
        color="Ociosidade (%)",
        color_continuous_scale=px.colors.sequential.Plasma
    )
    st.plotly_chart(fig_ociosidade_media, use_container_width=True)

    # Gráfico de Gantt para um agente e dia específicos
    st.subheader("Visualização Detalhada (Gráfico de Gantt)")

    agentes_disponiveis = df_filtrado_dashboard["agente"].unique().tolist()
    if not agentes_disponiveis:
        st.warning("Nenhum agente disponível para o Gantt no período selecionado.")
        return

    col_gantt1, col_gantt2 = st.columns(2)
    with col_gantt1:
        agente_gantt = st.selectbox("Selecione o Agente para o Gantt:", agentes_disponiveis)
    with col_gantt2:
        # Filtrar datas disponíveis para o agente selecionado
        datas_disponiveis = sorted(df_filtrado_dashboard[df_filtrado_dashboard["agente"] == agente_gantt]["inicio"].dt.date.unique().tolist())
        if not datas_disponiveis:
            st.warning(f"Nenhuma data disponível para o agente {agente_gantt}.")
            return
        data_gantt = st.selectbox("Selecione o Dia para o Gantt:", datas_disponiveis)

    if agente_gantt and data_gantt:
        fig_gantt = _gantt_chart(df_filtrado_dashboard, agente_gantt, datetime.combine(data_gantt, time.min))
        st.plotly_chart(fig_gantt, use_container_width=True)
