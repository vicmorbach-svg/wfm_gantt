# tabs/tab_dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date, time # Adicione 'date' e 'time' aqui
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
    data_inicio_dia = datetime.combine(data_selecionada, time.min)
    data_fim_dia = datetime.combine(data_selecionada, time.max)

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
            x=datetime.combine(data_selecionada, time(h)), # Usar datetime.combine
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
        title="Tempo Total em Cada Estado por Agente (Horas)",
        orientation="h",
        hover_data={"minutos": True, "horas": ":.2f"},
        height=400 + len(resumo_estados["agente"].unique()) * 30
    )

    fig.update_layout(
        xaxis_title="Horas",
        yaxis_title="Agente",
        legend_title="Estado"
    )

    if "Unified away" in resumo_estados["estado"].unique():
        df_away = resumo_estados[(resumo_estados["estado"] == "Unified away") & (resumo_estados["minutos"] > limite_alerta)]
        if not df_away.empty:
            for _, row in df_away.iterrows():
                fig.add_annotation(
                    x=row["horas"],
                    y=row["agente"],
                    text=f"Alerta! {row['minutos']:.0f} min",
                    showarrow=True,
                    arrowhead=2,
                    arrowsize=1,
                    arrowwidth=2,
                    arrowcolor="#ff0000",
                    font=dict(color="#ff0000", size=10),
                    ax=20,
                    ay=-30
                )

    return fig

def _metricas_principais(df_filtrado: pd.DataFrame, limite_alerta: int):
    if df_filtrado.empty:
        st.warning("Não há dados para exibir as métricas principais.")
        return

    total_minutos = df_filtrado["minutos"].sum()
    total_horas = total_minutos / 60

    online_minutos = df_filtrado[df_filtrado["estado"] == "Unified online"]["minutos"].sum()
    online_horas = online_minutos / 60

    away_minutos = df_filtrado[df_filtrado["estado"] == "Unified away"]["minutos"].sum()
    away_horas = away_minutos / 60

    offline_minutos = df_filtrado[df_filtrado["estado"] == "Unified offline"]["minutos"].sum()
    offline_horas = offline_minutos / 60

    transfers_only_minutos = df_filtrado[df_filtrado["estado"] == "Unified transfers only"]["minutos"].sum()
    transfers_only_horas = transfers_only_minutos / 60

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Total de Minutos Registrados", f"{total_minutos:.2f} min")
    with col2:
        st.metric("Total de Horas Registradas", f"{total_horas:.2f} h")
    with col3:
        st.metric("Tempo Online", f"{online_horas:.2f} h")
    with col4:
        st.metric("Tempo Ausente (Away)", f"{away_horas:.2f} h", delta=f"Limite: {limite_alerta} min", delta_color="inverse" if away_minutos > limite_alerta else "normal")
    with col5:
        st.metric("Tempo Offline", f"{offline_horas:.2f} h")

def render(df_hist_filtrado_global: pd.DataFrame, df_escala: pd.DataFrame, limite_alerta: int, data_selecionada_global: date): # data_selecionada_global agora é date
    st.header("Dashboard de Produtividade do Agente")

    if df_hist_filtrado_global.empty:
        st.info("Nenhum dado disponível para o período e agente selecionados. Por favor, carregue um arquivo ou ajuste os filtros.")
        return

    agentes_disponiveis = ["Todos"] + sorted(df_hist_filtrado_global["agente"].unique())
    agente_gantt = st.selectbox("Selecione o Agente para o Gantt", agentes_disponiveis, key="dashboard_agente_gantt") # Adicionado key

    if agente_gantt != "Todos":
        df_filtrado_gantt = df_hist_filtrado_global[df_hist_filtrado_global["agente"] == agente_gantt]
    else:
        df_filtrado_gantt = df_hist_filtrado_global.copy()

    # A data já vem filtrada para o dia selecionado na main, então usamos data_selecionada_global
    data_para_gantt = data_selecionada_global

    _metricas_principais(df_filtrado_gantt, limite_alerta)

    st.plotly_chart(_gantt_chart(df_filtrado_gantt, agente_gantt, data_para_gantt), use_container_width=True)
    st.plotly_chart(_resumo_estados_por_agente(df_filtrado_gantt, limite_alerta), use_container_width=True)
