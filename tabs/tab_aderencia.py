import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, time, timedelta, date # Importar date
from config import CORES_ESTADOS, ESTADOS_PRODUTIVOS, ESTADOS_PAUSA, ESTADOS_IMPRODUTIVOS, MAP_WEEKDAY_TO_NAME # Usar MAP_WEEKDAY_TO_NAME

def _gantt_aderencia(df_agente_dia: pd.DataFrame, df_escala_agente_dia: pd.DataFrame, agente_gantt: str, data_gantt: date): # data_gantt agora é date
    if df_agente_dia.empty:
        st.warning(f"Não há dados para o agente {agente_gantt} no dia {data_gantt.strftime('%d/%m/%Y')}.")
        return go.Figure()

    # Filtrar para o agente e dia selecionados
    df_gantt = df_agente_dia[
        (df_agente_dia["agente"] == agente_gantt) &
        (df_agente_dia["data"] == data_gantt) # Comparar diretamente com datetime.date
    ].copy()

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
        color_discrete_map=CORES_ESTADOS,
        title=f"Linha do Tempo do Agente: {agente_gantt} em {data_gantt.strftime('%d/%m/%Y')}"
    )

    # Adicionar a barra de escala
    escala_dia = df_escala_agente_dia[
        (df_escala_agente_dia["agente"] == agente_gantt) &
        (df_escala_agente_dia["data"] == data_gantt) # Comparar diretamente com datetime.date
    ]

    if not escala_dia.empty:
        escala_inicio = datetime.combine(data_gantt, escala_dia["hora_inicio_escala"].iloc[0])
        escala_fim = datetime.combine(data_gantt, escala_dia["hora_fim_escala"].iloc[0])

        fig.add_trace(go.Scatter(
            x=[escala_inicio, escala_fim],
            y=[agente_gantt, agente_gantt],
            mode='lines',
            line=dict(color='blue', width=4, dash='dot'),
            name='Escala Prevista',
            hoverinfo='text',
            text=[f"Escala: {escala_inicio.strftime('%H:%M')} - {escala_fim.strftime('%H:%M')}",
                  f"Escala: {escala_inicio.strftime('%H:%M')} - {escala_fim.strftime('%H:%M')}"]
        ))

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
                datetime.combine(data_gantt, time.min),
                datetime.combine(data_gantt, time.max)
            ]
        )
    )

    # Adicionar linhas verticais para cada hora do dia
    for h in range(24):
        fig.add_vline(
            x=datetime.combine(data_gantt, time(h)), # Usar datetime.combine com time(h)
            line_width=0.5,
            line_dash="dot",
            line_color="gray",
            annotation_text=f"{h:02d}:00",
            annotation_position="top right",
            annotation_font_size=10,
            annotation_font_color="gray"
        )

    fig.update_yaxes(autorange="reversed")
    return fig

def _calcular_metricas_aderencia(df_filtrado: pd.DataFrame, df_escala: pd.DataFrame):
    if df_filtrado.empty:
        return pd.DataFrame()

    # 'data' já deve ser datetime.date do data_loader
    df_sum = df_filtrado.groupby(["agente", "data", "estado"])["minutos"].sum().reset_index()

    df_pivot = df_sum.pivot_table(index=["agente", "data"], columns="estado", values="minutos", fill_value=0).reset_index()

    df_pivot["Tempo Produtivo (min)"] = df_pivot[[col for col in ESTADOS_PRODUTIVOS if col in df_pivot.columns]].sum(axis=1)
    df_pivot["Tempo em Pausa (min)"] = df_pivot[[col for col in ESTADOS_PAUSA if col in df_pivot.columns]].sum(axis=1)
    df_pivot["Tempo Improdutivo (min)"] = df_pivot[[col for col in ESTADOS_IMPRODUTIVOS if col in df_pivot.columns]].sum(axis=1)

    df_escala_copy = df_escala.copy()
    # Garantir que a coluna 'data' na escala seja datetime.date para o merge
    if 'data' in df_escala_copy.columns:
        df_escala_copy['data'] = pd.to_datetime(df_escala_copy['data']).dt.date

    df_metricas = pd.merge(df_pivot, df_escala_copy, on=["agente", "data"], how="left")

    # Preencher NaNs para agentes/dias sem escala para evitar erros no cálculo
    # Se não houver escala, a duração da escala será 0, resultando em aderência 0
    df_metricas["hora_inicio_escala"] = df_metricas["hora_inicio_escala"].fillna(time(0,0))
    df_metricas["hora_fim_escala"] = df_metricas["hora_fim_escala"].fillna(time(0,0))

    df_metricas['inicio_escala_dt'] = df_metricas.apply(lambda row: datetime.combine(row['data'], row['hora_inicio_escala']), axis=1)
    df_metricas['fim_escala_dt'] = df_metricas.apply(lambda row: datetime.combine(row['data'], row['hora_fim_escala']), axis=1)
    df_metricas["Duracao Escala (min)"] = (df_metricas["fim_escala_dt"] - df_metricas["inicio_escala_dt"]).dt.total_seconds() / 60
    df_metricas["Duracao Escala (min)"] = df_metricas["Duracao Escala (min)"].apply(lambda x: x if x > 0 else 0) # Garante duração não negativa

    # Evitar divisão por zero
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

    df_filtrado_aderencia = df_hist[
        (df_hist["data"] >= data_inicio_aderencia) & # Comparar diretamente com date objects
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
