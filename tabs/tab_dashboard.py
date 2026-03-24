# tabs/tab_dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, time, timedelta
from config import CORES_STATUS, DIAS_SEMANA_ORDEM, ESTADOS_INTERESSE

def _gantt_chart(df_filtrado: pd.DataFrame, agente_gantt: str, data_gantt: datetime):
    if df_filtrado.empty:
        st.warning("Nenhum dado disponível para exibir o Gantt.")
        return go.Figure()

    df_agente_dia = df_filtrado[(df_filtrado["agente"] == agente_gantt) & (df_filtrado["data"] == data_gantt.date())].copy()

    if df_agente_dia.empty:
        st.info(f"Nenhum dado de status para o agente {agente_gantt} no dia {data_gantt.strftime('%d/%m/%Y')}.")
        return go.Figure()

    # Filtrar estados para incluir apenas os de interesse
    df_agente_dia = df_agente_dia[df_agente_dia["estado"].isin(ESTADOS_INTERESSE)]

    fig = px.timeline(
        df_agente_dia,
        x_start="inicio",
        x_end="fim",
        y="agente",
        color="estado",
        color_discrete_map=CORES_STATUS,
        title=f"Gantt para {agente_gantt} em {data_gantt.strftime('%d/%m/%Y')}",
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
    start_of_day = datetime(data_gantt.year, data_gantt.month, data_gantt.day, 0, 0, 0)
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
            x=datetime(data_gantt.year, data_gantt.month, data_gantt.day, h),
            line_width=0.5,
            line_dash="dot",
            line_color="gray"
        )

    return fig

def _total_minutos_por_estado(df: pd.DataFrame):
    if df.empty:
        return pd.DataFrame()

    # Filtrar estados para incluir apenas os de interesse
    df_filtered = df[df["estado"].isin(ESTADOS_INTERESSE)]

    total_por_estado = df_filtered.groupby("estado")["minutos"].sum().reset_index()
    total_por_estado.columns = ["Estado", "Total Minutos"]
    return total_por_estado

def _minutos_por_agente_e_estado(df: pd.DataFrame):
    if df.empty:
        return pd.DataFrame()

    # Filtrar estados para incluir apenas os de interesse
    df_filtered = df[df["estado"].isin(ESTADOS_INTERESSE)]

    minutos_agente_estado = df_filtered.groupby(["agente", "estado"])["minutos"].sum().unstack(fill_value=0)
    minutos_agente_estado["Total"] = minutos_agente_estado.sum(axis=1)
    minutos_agente_estado = minutos_agente_estado.sort_values("Total", ascending=False).drop("Total", axis=1)
    return minutos_agente_estado

def _total_minutos_por_dia_semana(df: pd.DataFrame):
    if df.empty:
        return pd.DataFrame()

    # Filtrar estados para incluir apenas os de interesse
    df_filtered = df[df["estado"].isin(ESTADOS_INTERESSE)]

    total_por_dia = df_filtered.groupby("dia_semana")["minutos"].sum().reset_index()
    total_por_dia.columns = ["Dia da Semana", "Total Minutos"]
    return total_por_dia

def _distribuicao_estados_ao_longo_do_dia(df: pd.DataFrame):
    if df.empty:
        return go.Figure()

    # Filtrar estados para incluir apenas os de interesse
    df_filtered = df[df["estado"].isin(ESTADOS_INTERESSE)]

    df_filtered["hora"] = df_filtered["inicio"].dt.hour
    distribuicao = df_filtered.groupby(["hora", "estado"])["minutos"].sum().unstack(fill_value=0)

    fig = px.area(
        distribuicao,
        x=distribuicao.index,
        y=distribuicao.columns,
        title="Distribuição de Estados ao Longo do Dia",
        labels={"x": "Hora do Dia", "value": "Minutos", "estado": "Estado"},
        color_discrete_map=CORES_STATUS
    )
    fig.update_layout(
        xaxis_title="Hora do Dia",
        yaxis_title="Total de Minutos",
        hovermode="x unified",
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(color="black"),
    )
    return fig

def render(df_hist: pd.DataFrame, limite_alerta: int):
    st.subheader("Dashboard Geral")

    if df_hist.empty:
        st.info("Por favor, carregue um arquivo para visualizar o dashboard.")
        return

    # Filtrar df_hist para incluir apenas os estados de interesse
    df_hist_filtered = df_hist[df_hist["estado"].isin(ESTADOS_INTERESSE)].copy()

    if df_hist_filtered.empty:
        st.warning("Nenhum dado disponível para os estados de interesse selecionados.")
        return

    # Visão Geral dos Agentes
    st.markdown("### Visão Geral por Agente")
    minutos_agente_estado = _minutos_por_agente_e_estado(df_hist_filtered)
    if not minutos_agente_estado.empty:
        st.dataframe(minutos_agente_estado, use_container_width=True)
    else:
        st.info("Nenhum dado de minutos por agente e estado disponível.")

    # Total de Minutos por Estado
    st.markdown("### Total de Minutos por Estado")
    total_por_estado = _total_minutos_por_estado(df_hist_filtered)
    if not total_por_estado.empty:
        fig_total_estado = px.bar(
            total_por_estado,
            x="Estado",
            y="Total Minutos",
            title="Total de Minutos por Estado",
            color="Estado",
            color_discrete_map=CORES_STATUS
        )
        fig_total_estado.update_layout(
            plot_bgcolor="white",
            paper_bgcolor="white",
            font=dict(color="black"),
        )
        st.plotly_chart(fig_total_estado, use_container_width=True)
    else:
        st.info("Nenhum dado de total de minutos por estado disponível.")

    # Total de Minutos por Dia da Semana
    st.markdown("### Total de Minutos por Dia da Semana")
    total_por_dia_semana = _total_minutos_por_dia_semana(df_hist_filtered)
    if not total_por_dia_semana.empty:
        fig_total_dia = px.bar(
            total_por_dia_semana,
            x="Dia da Semana",
            y="Total Minutos",
            title="Total de Minutos por Dia da Semana",
            color="Dia da Semana",
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig_total_dia.update_layout(
            plot_bgcolor="white",
            paper_bgcolor="white",
            font=dict(color="black"),
        )
        st.plotly_chart(fig_total_dia, use_container_width=True)
    else:
        st.info("Nenhum dado de total de minutos por dia da semana disponível.")

    # Distribuição de Estados ao Longo do Dia
    st.markdown("### Distribuição de Estados ao Longo do Dia")
    fig_dist_dia = _distribuicao_estados_ao_longo_do_dia(df_hist_filtered)
    st.plotly_chart(fig_dist_dia, use_container_width=True)

    # Gantt Chart para um Agente Específico
    st.markdown("### Gantt Chart Detalhado")
    agentes = sorted(df_hist_filtered["agente"].unique())
    if agentes:
        col_gantt1, col_gantt2 = st.columns(2)
        with col_gantt1:
            agente_gantt = st.selectbox("Selecione o Agente para Gantt", agentes)
        with col_gantt2:
            datas_disponiveis = sorted(df_hist_filtered[df_hist_filtered["agente"] == agente_gantt]["data"].unique())
            if datas_disponiveis:
                data_gantt = st.selectbox("Selecione a Data para Gantt", datas_disponiveis)
            else:
                data_gantt = None
                st.warning(f"Nenhuma data disponível para o agente {agente_gantt}.")

        if agente_gantt and data_gantt:
            fig_gantt = _gantt_chart(df_hist_filtered, agente_gantt, datetime.combine(data_gantt, time.min))
            st.plotly_chart(fig_gantt, use_container_width=True)
    else:
        st.info("Nenhum agente disponível para o Gantt Chart.")

    # Alertas de Tempo em "Away"
    st.markdown("### Alertas de Tempo em 'Unified away'")
    df_away = df_hist_filtered[df_hist_filtered["estado"] == "Unified away"].copy()
    if not df_away.empty:
        df_away_longo = df_away[df_away["minutos"] > limite_alerta]
        if not df_away_longo.empty:
            st.warning(f"Os seguintes agentes estiveram em 'Unified away' por mais de {limite_alerta} minutos:")
            st.dataframe(df_away_longo[["agente", "data", "inicio", "fim", "minutos"]].sort_values(by="minutos", ascending=False), use_container_width=True)
        else:
            st.info(f"Nenhum agente esteve em 'Unified away' por mais de {limite_alerta} minutos.")
    else:
        st.info("Nenhum registro de 'Unified away' encontrado.")
