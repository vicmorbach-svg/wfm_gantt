# tabs/tab_aderencia.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, time, timedelta
from config import CORES_STATUS, DIAS_SEMANA_ORDEM, ESTADOS_INTERESSE

def _gantt_aderencia(df_hist: pd.DataFrame, df_escala: pd.DataFrame, agente_gantt: str, dt_gantt: datetime):
    if df_hist.empty:
        st.warning("Nenhum dado histórico disponível para exibir o Gantt de aderência.")
        return go.Figure()

    df_agente_dia = df_hist[(df_hist["agente"] == agente_gantt) & (df_hist["data"] == dt_gantt.date())].copy()

    if df_agente_dia.empty:
        st.info(f"Nenhum dado de status para o agente {agente_gantt} no dia {dt_gantt.strftime('%d/%m/%Y')}.")
        return go.Figure()

    # Filtrar estados para incluir apenas os de interesse
    df_agente_dia = df_agente_dia[df_agente_dia["estado"].isin(ESTADOS_INTERESSE)]

    # Criar o gráfico de Gantt
    fig = px.timeline(
        df_agente_dia,
        x_start="inicio",
        x_end="fim",
        y="agente",
        color="estado",
        color_discrete_map=CORES_STATUS,
        title=f"Gantt de Aderência para {agente_gantt} em {dt_gantt.strftime('%d/%m/%Y')}",
        hover_name="estado",
        hover_data={
            "inicio": "|%H:%M:%S",
            "fim": "|%H:%M:%S",
            "minutos": True,
            "estado": False,
        }
    )

    fig.update_yaxes(autorange="reversed") # Para exibir o agente de cima para baixo

    # Definir o range do eixo X para cobrir 24 horas do dia selecionado
    start_of_day = datetime(dt_gantt.year, dt_gantt.month, dt_gantt.day, 0, 0, 0)
    end_of_day = start_of_day + timedelta(days=1)
    fig.update_xaxes(
        range=[start_of_day, end_of_day],
        tickformat="%H:%M",
        dtick=3600000, # Um tick a cada hora
        title="Hora do Dia"
    )

    fig.update_layout(
        barmode="overlay",
        xaxis_showgrid=True,
        yaxis_showgrid=True,
        xaxis_tickangle=-45,
        height=200,
        margin=dict(l=140, r=20, t=60, b=50),
        plot_bgcolor="white", # Fundo branco
        paper_bgcolor="white", # Fundo do papel branco
        font=dict(color="black"), # Cor da fonte preta
    )

    # Adicionar linhas verticais para cada hora
    for h in range(0, 24):
        fig.add_vline(
            x=datetime(dt_gantt.year, dt_gantt.month, dt_gantt.day, h),
            line_width=0.5,
            line_dash="dot",
            line_color="gray"
        )

    # Adicionar a escala do agente (se houver)
    if not df_escala.empty:
        escala_agente_dia = df_escala[(df_escala["agente"] == agente_gantt) & (df_escala["data"] == dt_gantt.date())].copy()
        if not escala_agente_dia.empty:
            for _, row in escala_agente_dia.iterrows():
                fig.add_shape(
                    type="rect",
                    x0=row["inicio_escala"],
                    y0=-0.5, # Ajuste para cobrir a barra do agente
                    x1=row["fim_escala"],
                    y1=0.5,  # Ajuste para cobrir a barra do agente
                    fillcolor="rgba(0, 128, 0, 0.2)", # Verde claro transparente
                    line_width=0,
                    layer="below"
                )
                fig.add_annotation(
                    x=row["inicio_escala"] + (row["fim_escala"] - row["inicio_escala"]) / 2,
                    y=0.5, # Posição da anotação
                    text="Escala",
                    showarrow=False,
                    font=dict(color="darkgreen", size=10),
                    yanchor="bottom"
                )

    return fig

def _resumo_aderencia(df_hist: pd.DataFrame, df_escala: pd.DataFrame, agente_gantt: str, dt_gantt: datetime):
    if df_hist.empty:
        st.warning("Nenhum dado histórico disponível para exibir o resumo de aderência.")
        return pd.DataFrame()

    df_agente_dia = df_hist[(df_hist["agente"] == agente_gantt) & (df_hist["data"] == dt_gantt.date())].copy()

    if df_agente_dia.empty:
        st.info(f"Nenhum dado de status para o agente {agente_gantt} no dia {dt_gantt.strftime('%d/%m/%Y')}.")
        return pd.DataFrame()

    # Filtrar estados para incluir apenas os de interesse
    df_agente_dia = df_agente_dia[df_agente_dia["estado"].isin(ESTADOS_INTERESSE)]

    resumo = df_agente_dia.groupby("estado")["minutos"].sum().reset_index()
    resumo.columns = ["Estado", "Tempo Total (minutos)"]

    # Adicionar a escala do agente ao resumo
    if not df_escala.empty:
        escala_agente_dia = df_escala[(df_escala["agente"] == agente_gantt) & (df_escala["data"] == dt_gantt.date())].copy()
        if not escala_agente_dia.empty:
            total_escala_min = (escala_agente_dia["fim_escala"] - escala_agente_dia["inicio_escala"]).dt.total_seconds().sum() / 60
            resumo = pd.concat([resumo, pd.DataFrame([{"Estado": "Tempo em Escala", "Tempo Total (minutos)": total_escala_min}])], ignore_index=True)

    return resumo

def render(df_hist: pd.DataFrame, df_escala: pd.DataFrame):
    st.subheader("Aderência do Agente")

    if df_hist.empty:
        st.info("Por favor, carregue um arquivo para visualizar a aderência.")
        return

    agentes = sorted(df_hist["agente"].unique())
    if not agentes:
        st.warning("Nenhum agente encontrado nos dados.")
        return

    col1, col2 = st.columns(2)
    with col1:
        agente_selecionado = st.selectbox("Selecione o Agente", agentes)
    with col2:
        datas_disponiveis = sorted(df_hist[df_hist["agente"] == agente_selecionado]["data"].unique())
        if not datas_disponiveis:
            st.warning(f"Nenhuma data disponível para o agente {agente_selecionado}.")
            return
        data_selecionada = st.selectbox("Selecione a Data", datas_disponiveis)

    if agente_selecionado and data_selecionada:
        st.write(f"Visualizando aderência para **{agente_selecionado}** em **{data_selecionada.strftime('%d/%m/%Y')}**")

        # Exibir o gráfico de Gantt
        fig_gantt = _gantt_aderencia(df_hist, df_escala, agente_selecionado, datetime.combine(data_selecionada, time.min))
        st.plotly_chart(fig_gantt, use_container_width=True)

        # Exibir o resumo de aderência
        st.subheader("Resumo de Tempo por Estado")
        resumo_df = _resumo_aderencia(df_hist, df_escala, agente_selecionado, datetime.combine(data_selecionada, time.min))
        if not resumo_df.empty:
            st.dataframe(resumo_df, use_container_width=True)
        else:
            st.info("Nenhum resumo de tempo disponível para os estados selecionados.")
