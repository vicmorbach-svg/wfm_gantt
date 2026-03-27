# tabs/tab_aderencia.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date, time # Importar date e time
from config import CORES_ESTADOS, ESTADOS_PRODUTIVOS, ESTADOS_PAUSA, ESTADOS_IMPRODUTIVOS, MAP_WEEKDAY_TO_NAME
from storage import escala_para_display # Para exibir a escala formatada

def _calcular_metricas_aderencia(df_hist: pd.DataFrame, df_escala: pd.DataFrame) -> pd.DataFrame:
    if df_hist.empty or df_escala.empty:
        return pd.DataFrame()

    # Garantir que 'data' seja datetime.date em ambos os DataFrames
    if "data" in df_hist.columns:
        df_hist["data"] = pd.to_datetime(df_hist["data"]).dt.date
    if "data" in df_escala.columns:
        df_escala["data"] = pd.to_datetime(df_escala["data"]).dt.date

    # Merge do histórico com a escala pela data e agente
    df_merged = pd.merge(df_hist, df_escala, on=["agente", "data"], how="left")

    # Calcular tempo total em estados produtivos, pausa e improdutivos
    df_merged["minutos_produtivos"] = df_merged[df_merged["estado"].isin(ESTADOS_PRODUTIVOS)]["minutos"].fillna(0)
    df_merged["minutos_pausa"] = df_merged[df_merged["estado"].isin(ESTADOS_PAUSA)]["minutos"].fillna(0)
    df_merged["minutos_improdutivos"] = df_merged[df_merged["estado"].isin(ESTADOS_IMPRODUTIVOS)]["minutos"].fillna(0)

    # Agrupar por agente e data para obter totais diários
    resumo_diario = df_merged.groupby(["agente", "data"]).agg(
        total_minutos_produtivos=("minutos_produtivos", "sum"),
        total_minutos_pausa=("minutos_pausa", "sum"),
        total_minutos_improdutivos=("minutos_improdutivos", "sum"),
        hora_inicio_escala=("hora_inicio_escala", "first"),
        hora_fim_escala=("hora_fim_escala", "first")
    ).reset_index()

    # Calcular duração da escala em minutos
    # Usar datetime.combine para criar objetos datetime para cálculo de diferença
    resumo_diario["duracao_escala_minutos"] = resumo_diario.apply(
        lambda row: (datetime.combine(row["data"], row["hora_fim_escala"]) - datetime.combine(row["data"], row["hora_inicio_escala"])).total_seconds() / 60
        if pd.notna(row["hora_inicio_escala"]) and pd.notna(row["hora_fim_escala"]) else 0,
        axis=1
    )

    # Evitar divisão por zero se a duração da escala for 0
    resumo_diario["aderencia"] = resumo_diario.apply(
        lambda row: (row["total_minutos_produtivos"] / row["duracao_escala_minutos"]) * 100
        if row["duracao_escala_minutos"] > 0 else 0,
        axis=1
    )

    # Calcular tempo "away" como porcentagem da escala
    resumo_diario["away_percent"] = resumo_diario.apply(
        lambda row: (row["total_minutos_pausa"] / row["duracao_escala_minutos"]) * 100
        if row["duracao_escala_minutos"] > 0 else 0,
        axis=1
    )

    return resumo_diario

def _gantt_aderencia(df_hist: pd.DataFrame, df_escala: pd.DataFrame, data_gantt: date, agente_selecionado: str):
    if df_hist.empty or df_escala.empty:
        st.warning("Não há dados de histórico ou escala para exibir o Gantt de aderência.")
        return go.Figure()

    # Filtrar histórico e escala para a data selecionada
    df_hist_filtrado = df_hist[df_hist["data"] == data_gantt].copy()
    df_escala_filtrada = df_escala[df_escala["data"] == data_gantt].copy()

    if agente_selecionado != "Todos":
        df_hist_filtrado = df_hist_filtrado[df_hist_filtrado["agente"] == agente_selecionado]
        df_escala_filtrada = df_escala_filtrada[df_escala_filtrada["agente"] == agente_selecionado]

    if df_hist_filtrado.empty and df_escala_filtrada.empty:
        st.info(f"Não há dados de atividades ou escala para {agente_selecionado} em {data_gantt.strftime('%d/%m/%Y')}.")
        return go.Figure()

    # Preparar dados para o Gantt
    gantt_data = []

    # Adicionar atividades do histórico
    for _, row in df_hist_filtrado.iterrows():
        gantt_data.append({
            "agente": row["agente"],
            "tipo": "Atividade Real",
            "estado": row["estado"],
            "inicio": row["inicio"],
            "fim": row["fim"],
            "cor": CORES_ESTADOS.get(row["estado"], "#6c757d") # Cor padrão cinza
        })

    # Adicionar escala planejada
    for _, row in df_escala_filtrada.iterrows():
        # Escala principal
        gantt_data.append({
            "agente": row["agente"],
            "tipo": "Escala Planejada",
            "estado": "Escala",
            "inicio": datetime.combine(data_gantt, row["hora_inicio_escala"]),
            "fim": datetime.combine(data_gantt, row["hora_fim_escala"]),
            "cor": "#4CAF50" # Verde para escala
        })
        # Intervalos dentro da escala (se houver)
        if row["intervalos_json"]:
            try:
                intervalos = json.loads(row["intervalos_json"])
                for intervalo in intervalos:
                    gantt_data.append({
                        "agente": row["agente"],
                        "tipo": "Escala Planejada",
                        "estado": intervalo["tipo"], # Ex: "Almoço", "Pausa"
                        "inicio": datetime.combine(data_gantt, time.fromisoformat(intervalo["inicio"])),
                        "fim": datetime.combine(data_gantt, time.fromisoformat(intervalo["fim"])),
                        "cor": "#FFD700" # Amarelo para intervalos
                    })
            except json.JSONDecodeError:
                st.warning(f"Formato JSON inválido para intervalos do agente {row['agente']} na data {data_gantt}.")

    df_gantt = pd.DataFrame(gantt_data)

    if df_gantt.empty:
        st.info(f"Não há dados para o Gantt de aderência para {agente_selecionado} em {data_gantt.strftime('%d/%m/%Y')}.")
        return go.Figure()

    # Ordenar para visualização
    df_gantt = df_gantt.sort_values(by=["agente", "inicio"])

    fig = px.timeline(
        df_gantt,
        x_start="inicio",
        x_end="fim",
        y="agente",
        color="estado",
        color_discrete_map={**CORES_ESTADOS, "Escala": "#4CAF50", "Almoço": "#FFD700", "Pausa": "#FFD700"}, # Cores adicionais
        title=f"Gantt de Aderência para {agente_selecionado} em {data_gantt.strftime('%d/%m/%Y')}",
        hover_name="estado",
        hover_data={
            "inicio": "|%H:%M:%S",
            "fim": "|%H:%M:%S",
            "tipo": True # Mostrar se é atividade real ou escala planejada
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
            x=datetime.combine(data_gantt, time(h, 0, 0)),
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

def render(df_hist_para_aderencia: pd.DataFrame, df_escala: pd.DataFrame):
    st.title("Análise de Aderência")

    if df_hist_para_aderencia.empty:
        st.warning("Por favor, carregue um arquivo de dados para visualizar a aderência.")
        return

    # Filtros de data para a aba de aderência
    min_date_hist = df_hist_para_aderencia["data"].min()
    max_date_hist = df_hist_para_aderencia["data"].max()

    col1, col2 = st.columns(2)
    with col1:
        data_inicio_aderencia = st.date_input(
            "Data de Início:",
            value=min_date_hist,
            min_value=min_date_hist,
            max_value=max_date_hist,
            key="aderencia_data_inicio"
        )
    with col2:
        data_fim_aderencia = st.date_input(
            "Data de Fim:",
            value=max_date_hist,
            min_value=min_date_hist,
            max_value=max_date_hist,
            key="aderencia_data_fim"
        )

    if data_inicio_aderencia > data_fim_aderencia:
        st.error("A data de início não pode ser posterior à data de fim.")
        return

    df_hist_filtrado_periodo = df_hist_para_aderencia[
        (df_hist_para_aderencia["data"] >= data_inicio_aderencia) &
        (df_hist_para_aderencia["data"] <= data_fim_aderencia)
    ].copy()

    df_escala_filtrada_periodo = df_escala[
        (df_escala["data"] >= data_inicio_aderencia) &
        (df_escala["data"] <= data_fim_aderencia)
    ].copy()

    if df_hist_filtrado_periodo.empty:
        st.info("Não há dados de histórico para o período selecionado.")
        return

    # Calcular métricas de aderência
    df_metricas = _calcular_metricas_aderencia(df_hist_filtrado_periodo, df_escala_filtrada_periodo)

    if df_metricas.empty:
        st.info("Não foi possível calcular as métricas de aderência para o período e agentes selecionados. Verifique se há dados de escala para o período.")
        return

    st.subheader("Métricas de Aderência por Agente e Dia")
    st.dataframe(df_metricas.set_index(["agente", "data"]), use_container_width=True)

    # Gráfico de Aderência ao longo do tempo
    st.subheader("Aderência Média por Dia")
    aderencia_media_dia = df_metricas.groupby("data")["aderencia"].mean().reset_index()
    fig_aderencia_dia = px.line(
        aderencia_media_dia,
        x="data",
        y="aderencia",
        title="Aderência Média Diária",
        labels={"data": "Data", "aderencia": "Aderência (%)"},
        markers=True
    )
    fig_aderencia_dia.update_yaxes(range=[0, 100])
    st.plotly_chart(fig_aderencia_dia, use_container_width=True)

    st.subheader("Aderência Média por Agente")
    aderencia_media_agente = df_metricas.groupby("agente")["aderencia"].mean().reset_index().sort_values("aderencia", ascending=False)
    fig_aderencia_agente = px.bar(
        aderencia_media_agente,
        x="agente",
        y="aderencia",
        title="Aderência Média por Agente",
        labels={"agente": "Agente", "aderencia": "Aderência (%)"}
    )
    fig_aderencia_agente.update_yaxes(range=[0, 100])
    st.plotly_chart(fig_aderencia_agente, use_container_width=True)

    # Gantt de Aderência para um dia específico
    st.subheader("Gantt de Aderência (Comparativo Escala vs. Real)")
    agentes_gantt = ["Todos"] + sorted(df_hist_filtrado_periodo["agente"].unique().tolist())
    agente_selecionado_gantt = st.selectbox("Selecione o Agente para o Gantt:", agentes_gantt, key="aderencia_gantt_agente")

    datas_disponiveis_gantt = sorted(df_hist_filtrado_periodo["data"].unique().tolist())
    if datas_disponiveis_gantt:
        data_gantt = st.date_input(
            "Selecione a Data para o Gantt:",
            value=datas_disponiveis_gantt[0],
            min_value=datas_disponiveis_gantt[0],
            max_value=datas_disponiveis_gantt[-1],
            key="aderencia_gantt_data"
        )
        st.plotly_chart(_gantt_aderencia(df_hist_filtrado_periodo, df_escala_filtrada_periodo, data_gantt, agente_selecionado_gantt), use_container_width=True)
    else:
        st.info("Não há datas disponíveis para o Gantt de aderência no período selecionado.")
