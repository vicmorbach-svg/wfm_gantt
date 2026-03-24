# tabs/tab_dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from config import CORES_ESTADOS, DIAS_SEMANA_ORDEM, ESTADOS_INTERESSE

def _gantt_chart(df_filtrado: pd.DataFrame, agente_selecionado: str, data_selecionada: datetime):
    if df_filtrado.empty:
        st.warning("Não há dados para exibir o gráfico de Gantt para o agente e data selecionados.")
        return go.Figure()

    df_gantt = df_filtrado.copy()
    df_gantt["duracao_horas"] = df_gantt["minutos"] / 60

    # Ordenar estados para garantir consistência na visualização
    # Priorizar "online", "away", "offline", "transfers only"
    estado_order = {estado: i for i, estado in enumerate(ESTADOS_INTERESSE)}
    df_gantt["estado_ordenado"] = df_gantt["estado"].map(estado_order)
    df_gantt = df_gantt.sort_values(by=["agente", "inicio", "estado_ordenado"])

    # Criar o gráfico de Gantt
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

    fig.update_yaxes(autorange="reversed") # Inverte a ordem para o primeiro agente aparecer no topo

    # Definir o range do eixo X para cobrir o dia inteiro
    data_inicio_dia = datetime(data_selecionada.year, data_selecionada.month, data_selecionada.day, 0, 0, 0)
    data_fim_dia = data_inicio_dia + timedelta(days=1)

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
            x=datetime(data_selecionada.year, data_selecionada.month, data_selecionada.day, h),
            line_width=1,
            line_dash="dot",
            line_color="gray"
        )

    fig.update_layout(
        xaxis_title="Hora do Dia",
        yaxis_title="Agente",
        hovermode="x unified",
        height=400 + len(df_gantt["agente"].unique()) * 30 # Ajusta a altura dinamicamente
    )

    return fig

def _resumo_estados_por_agente(df_filtrado: pd.DataFrame, limite_alerta: int):
    if df_filtrado.empty:
        st.warning("Não há dados para exibir o resumo de estados.")
        return go.Figure()

    resumo_estados = df_filtrado.groupby(["agente", "estado"])["minutos"].sum().reset_index()
    resumo_estados["horas"] = resumo_estados["minutos"] / 60

    # Calcular o total de minutos por agente para ordenação
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

    # Adicionar linha de alerta para "Unified away"
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

    # Corrigido para usar 5 colunas distintas
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
        # Se quiser "Transfers Only" em uma 6ª coluna, descomente e adicione col6 acima
        # st.metric("Tempo Transfers Only", f"{transfers_only_horas:.2f} h")


def render(df_hist: pd.DataFrame, limite_alerta: int):
    st.header("Dashboard de Produtividade do Agente")

    # Obter agentes e data do df_hist (que já está filtrado por data na main)
    agentes_disponiveis = ["Todos"] + sorted(df_hist["agente"].unique())
    agente_gantt = st.selectbox("Selecione o Agente para o Gantt", agentes_disponiveis)

    if agente_gantt != "Todos":
        df_filtrado_gantt = df_hist[df_hist["agente"] == agente_gantt]
    else:
        df_filtrado_gantt = df_hist.copy()

    # A data já vem filtrada para o dia selecionado na main, então pegamos a primeira data disponível
    if not df_filtrado_gantt.empty:
        data_gantt = df_filtrado_gantt["data"].iloc[0]
    else:
        data_gantt = datetime.now().date() # Fallback

    _metricas_principais(df_filtrado_gantt, limite_alerta)

    st.plotly_chart(_gantt_chart(df_filtrado_gantt, agente_gantt, data_gantt), use_container_width=True)
    st.plotly_chart(_resumo_estados_por_agente(df_filtrado_gantt, limite_alerta), use_container_width=True)
