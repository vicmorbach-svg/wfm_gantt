# tabs/tab_dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date # Importar 'date' aqui
from config import CORES_ESTADOS, DIAS_SEMANA_ORDEM, ESTADOS_INTERESSE, LIMITE_ALERTA_AWAY_MINUTOS

def _gantt_chart(df_filtrado: pd.DataFrame, agente_selecionado: str, data_selecionada: date): # data_selecionada agora é date
    if df_filtrado.empty:
        st.warning("Não há dados para exibir o gráfico de Gantt para o agente e data selecionados.")
        return go.Figure()

    df_gantt = df_filtrado.copy()
    df_gantt["duracao_horas"] = df_gantt["minutos"] / 60

    estado_order = {estado: i for i, estado in enumerate(ESTADOS_INTERESSE)}
    df_gantt["estado_ordenado"] = df_gantt["estado"].map(estado_order)
    df_gantt = df_gantt.sort_values(by=["agente", "inicio", "estado_ordenado"])

    fig = px.timeline(
        df_gantt,
        x_start="inicio",
        x_end="fim",
        y="agente",
        color="estado",
        color_discrete_map=CORES_ESTADOS,
        title=f"Gantt de Atividades para {agente_selecionado} em {data_selecionada.strftime('%d/%m/%Y')}",
        hover_name="estado",
        hover_data={
            "inicio": "|%H:%M:%S",
            "fim": "|%H:%M:%S",
            "minutos": True,
            "duracao_horas": ":.2f"
        }
    )

    fig.update_yaxes(autorange="reversed")

    # Definir o range do eixo X para cobrir o dia inteiro
    # Usar datetime.combine para criar objetos datetime a partir de date e time
    data_inicio_dia = datetime.combine(data_selecionada, datetime.min.time())
    data_fim_dia = datetime.combine(data_selecionada, datetime.max.time())

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
            x=datetime.combine(data_selecionada, datetime.min.time().replace(hour=h)), # Usar datetime.combine
            line_width=1,
            line_dash="dot",
            line_color="gray"
        )

    fig.update_layout(
        xaxis_title="Hora do Dia",
        yaxis_title="Agente",
        hovermode="x unified",
        height=400 + len(df_gantt["agente"].unique()) * 30
    )

    return fig

def _resumo_estados_por_agente(df_filtrado: pd.DataFrame, limite_alerta: int):
    if df_filtrado.empty:
        st.warning("Não há dados para exibir o resumo de estados.")
        return go.Figure()

    resumo_estados = df_filtrado.groupby(["agente", "estado"])["minutos"].sum().reset_index()
    resumo_estados["horas"] = resumo_estados["minutos"] / 60

    total_minutos_agente = resumo_estados.groupby("agente")["minutos"].sum().sort_values(ascending=False)
    resumo_estados["agente"] = pd.Categorical(resumo_estados["agente"], categories=total_minutos_agente.index, ordered=True)
    resumo_estados = resumo_estados.sort_values("agente")

    fig = px.bar(
        resumo_estados,
        x="horas",
        y="agente",
        color="estado",
        color_discrete_map=CORES_ESTADOS,
        title="Tempo Total em Cada Estado por Agente",
        labels={"horas": "Tempo (horas)", "agente": "Agente", "estado": "Estado"},
        orientation="h"
    )
    fig.update_layout(
        xaxis_title="Tempo (horas)",
        yaxis_title="Agente",
        hovermode="y unified",
        height=400 + len(resumo_estados["agente"].unique()) * 30
    )
    return fig

def _metricas_principais(df_filtrado: pd.DataFrame, df_escala: pd.DataFrame, limite_alerta: int, data_selecionada: date):
    if df_filtrado.empty:
        st.info("Não há dados para calcular as métricas principais.")
        return

    # Filtrar escala para a data selecionada
    df_escala_dia = df_escala[df_escala["data"] == data_selecionada]

    total_agentes_ativos = df_filtrado["agente"].nunique()
    total_minutos_away = df_filtrado[df_filtrado["estado"] == "Unified away"]["minutos"].sum()
    total_minutos_online = df_filtrado[df_filtrado["estado"] == "Unified online"]["minutos"].sum()

    # Calcular aderência (exemplo simplificado)
    # Soma dos minutos produtivos no dia
    minutos_produtivos_dia = df_filtrado[df_filtrado["estado"].isin(["Unified online", "Unified transfers only"])]["minutos"].sum()

    # Soma da duração da escala para os agentes presentes no histórico do dia
    agentes_no_historico_dia = df_filtrado["agente"].unique()
    df_escala_agentes_presentes = df_escala_dia[df_escala_dia["agente"].isin(agentes_no_historico_dia)]

    duracao_escala_total_minutos = 0
    if not df_escala_agentes_presentes.empty:
        duracao_escala_total_minutos = df_escala_agentes_presentes.apply(
            lambda row: (datetime.combine(data_selecionada, row["hora_fim_escala"]) - datetime.combine(data_selecionada, row["hora_inicio_escala"])).total_seconds() / 60
            if pd.notna(row["hora_inicio_escala"]) and pd.notna(row["hora_fim_escala"]) else 0,
            axis=1
        ).sum()

    aderencia_percentual = (minutos_produtivos_dia / duracao_escala_total_minutos) * 100 if duracao_escala_total_minutos > 0 else 0
    aderencia_percentual = round(aderencia_percentual, 2)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="Agentes Ativos (Dia)", value=total_agentes_ativos)
    with col2:
        st.metric(label="Tempo Online (horas)", value=f"{total_minutos_online / 60:.2f}")
    with col3:
        st.metric(label="Tempo Away (horas)", value=f"{total_minutos_away / 60:.2f}")
    with col4:
        st.metric(label="Aderência (%)", value=f"{aderencia_percentual:.2f}%")

    if total_minutos_away > limite_alerta:
        st.warning(f"⚠️ Alerta: Tempo total 'Away' ({total_minutos_away:.0f} minutos) excedeu o limite de {limite_alerta} minutos!")

def render(df_hist_filtrado_global: pd.DataFrame, df_escala: pd.DataFrame, limite_alerta: int, data_selecionada_global: date): # data_selecionada_global agora é date
    st.title("Dashboard de Atividades dos Agentes")

    if df_hist_filtrado_global.empty:
        st.info("Não há dados de atividades para o agente e data selecionados. Por favor, ajuste os filtros ou carregue um arquivo.")
        return

    agente_selecionado = df_hist_filtrado_global["agente"].iloc[0] if df_hist_filtrado_global["agente"].nunique() == 1 else "Todos"

    _metricas_principais(df_hist_filtrado_global, df_escala, limite_alerta, data_selecionada_global)

    st.subheader("Gantt de Atividades")
    st.plotly_chart(_gantt_chart(df_hist_filtrado_global, agente_selecionado, data_selecionada_global), use_container_width=True)

    st.subheader("Resumo de Estados por Agente")
    st.plotly_chart(_resumo_estados_por_agente(df_hist_filtrado_global, limite_alerta), use_container_width=True)
