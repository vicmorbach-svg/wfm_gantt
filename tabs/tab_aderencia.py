# tabs/tab_aderencia.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date, time # Importar date e time
from config import CORES_ESTADOS, ESTADOS_PRODUTIVOS, ESTADOS_PAUSA, ESTADOS_IMPRODUTIVOS, MAP_WEEKDAY_TO_NAME

def _gantt_aderencia(df_hist_filtrado: pd.DataFrame, df_escala_filtrada: pd.DataFrame, data_gantt: date): # data_gantt agora é date
    if df_hist_filtrado.empty and df_escala_filtrada.empty:
        st.warning("Não há dados de histórico ou escala para exibir o Gantt de aderência.")
        return go.Figure()

    df_gantt_data = []

    # Adicionar histórico
    for _, row in df_hist_filtrado.iterrows():
        df_gantt_data.append({
            "agente": row["agente"],
            "tipo": "Histórico",
            "inicio": row["inicio"],
            "fim": row["fim"],
            "estado": row["estado"],
            "cor": CORES_ESTADOS.get(row["estado"], "#cccccc")
        })

    # Adicionar escala
    for _, row in df_escala_filtrada.iterrows():
        # Combinar data_gantt (date) com hora_inicio_escala (time) para criar datetime
        inicio_escala = datetime.combine(data_gantt, row["hora_inicio_escala"])
        fim_escala = datetime.combine(data_gantt, row["hora_fim_escala"])

        df_gantt_data.append({
            "agente": row["agente"],
            "tipo": "Escala",
            "inicio": inicio_escala,
            "fim": fim_escala,
            "estado": "Escala Planejada",
            "cor": "#808080" # Cor cinza para escala
        })

    df_gantt = pd.DataFrame(df_gantt_data)

    if df_gantt.empty:
        st.warning("Não há dados para exibir o Gantt de aderência.")
        return go.Figure()

    # Ordenar por agente e depois por tipo (Escala primeiro, depois Histórico)
    df_gantt["tipo_ordenado"] = df_gantt["tipo"].map({"Escala": 0, "Histórico": 1})
    df_gantt = df_gantt.sort_values(by=["agente", "tipo_ordenado", "inicio"])

    fig = px.timeline(
        df_gantt,
        x_start="inicio",
        x_end="fim",
        y="agente",
        color="estado",
        color_discrete_map={**CORES_ESTADOS, "Escala Planejada": "#808080"}, # Adiciona cor para escala
        title=f"Gantt de Aderência para {data_gantt.strftime('%d/%m/%Y')}",
        hover_name="estado",
        hover_data={
            "inicio": "|%H:%M:%S",
            "fim": "|%H:%M:%S",
            "tipo": True
        }
    )

    fig.update_yaxes(autorange="reversed")

    # Definir o range do eixo X para cobrir o dia inteiro
    data_inicio_dia = datetime.combine(data_gantt, time.min) # Usar time.min
    data_fim_dia = datetime.combine(data_gantt, time.max) # Usar time.max

    fig.update_xaxes(
        range=[data_inicio_dia, data_fim_dia],
        tickformat="%H:%M",
        dtick=3600000, # 1 hora em milissegundos
        showgrid=True,
        gridwidth=1,
        gridcolor='LightGrey'
    )

    for h in range(24):
        fig.add_vline(
            x=datetime.combine(data_gantt, time(h, 0, 0)), # Usar time(h,0,0)
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

def _calcular_metricas_aderencia(df_hist: pd.DataFrame, df_escala: pd.DataFrame) -> pd.DataFrame:
    if df_hist.empty or df_escala.empty:
        return pd.DataFrame()

    # Garantir que a coluna 'data' em df_escala seja datetime.date para o merge
    if "data" in df_escala.columns and pd.api.types.is_datetime64_any_dtype(df_escala["data"]):
        df_escala["data"] = df_escala["data"].dt.date

    # Agrupar histórico por agente e data para somar minutos produtivos
    df_hist_produtivo = df_hist[df_hist["estado"].isin(ESTADOS_PRODUTIVOS)].copy()
    df_hist_produtivo["data"] = df_hist_produtivo["data"].dt.date # Garantir que 'data' seja datetime.date
    minutos_produtivos_hist = df_hist_produtivo.groupby(["agente", "data"])["minutos"].sum().reset_index()
    minutos_produtivos_hist.rename(columns={"minutos": "minutos_produtivos_hist"}, inplace=True)

    # Calcular duração da escala em minutos
    df_escala_calc = df_escala.copy()
    # Combinar data (date) com hora_inicio/fim (time) para criar datetime para cálculo de duração
    df_escala_calc["inicio_dt"] = df_escala_calc.apply(lambda row: datetime.combine(row["data"], row["hora_inicio_escala"]), axis=1)
    df_escala_calc["fim_dt"] = df_escala_calc.apply(lambda row: datetime.combine(row["data"], row["hora_fim_escala"]), axis=1)
    df_escala_calc["duracao_escala_minutos"] = (df_escala_calc["fim_dt"] - df_escala_calc["inicio_dt"]).dt.total_seconds() / 60

    # Agrupar escala por agente e data para somar duração total
    duracao_escala_total = df_escala_calc.groupby(["agente", "data"])["duracao_escala_minutos"].sum().reset_index()
    duracao_escala_total.rename(columns={"duracao_escala_minutos": "minutos_escala_total"}, inplace=True)

    # Merge para combinar histórico e escala
    df_metricas = pd.merge(
        minutos_produtivos_hist,
        duracao_escala_total,
        on=["agente", "data"],
        how="outer"
    )

    # Preencher NaNs com 0 para agentes/datas sem histórico ou escala
    df_metricas["minutos_produtivos_hist"] = df_metricas["minutos_produtivos_hist"].fillna(0)
    df_metricas["minutos_escala_total"] = df_metricas["minutos_escala_total"].fillna(0)

    # Calcular aderência
    # Evitar divisão por zero: se minutos_escala_total for 0, aderência é 0
    df_metricas["aderencia"] = df_metricas.apply(
        lambda row: (row["minutos_produtivos_hist"] / row["minutos_escala_total"]) * 100
        if row["minutos_escala_total"] > 0 else 0,
        axis=1
    )

    # Limitar aderência a 100% (não pode ser mais aderente do que o planejado)
    df_metricas["aderencia"] = df_metricas["aderencia"].clip(upper=100)

    return df_metricas

def render(df_hist: pd.DataFrame, df_escala: pd.DataFrame):
    st.title("Aderência à Escala")

    if df_hist.empty:
        st.warning("Por favor, carregue um arquivo de histórico para calcular a aderência.")
        return
    if df_escala.empty:
        st.warning("Por favor, adicione entradas de escala para calcular a aderência.")
        return

    # Filtros de data para a aba de aderência
    min_date_hist = df_hist["data"].min()
    max_date_hist = df_hist["data"].max()

    col_start, col_end = st.columns(2)
    with col_start:
        data_inicio_aderencia = st.date_input(
            "Data de Início:",
            value=min_date_hist,
            min_value=min_date_hist,
            max_value=max_date_hist,
            key="aderencia_start_date"
        )
    with col_end:
        data_fim_aderencia = st.date_input(
            "Data de Fim:",
            value=max_date_hist,
            min_value=min_date_hist,
            max_value=max_date_hist,
            key="aderencia_end_date"
        )

    # Filtrar histórico e escala pelo período selecionado
    df_hist_filtrado_periodo = df_hist[
        (df_hist["data"] >= data_inicio_aderencia) & (df_hist["data"] <= data_fim_aderencia)
    ]
    df_escala_filtrada_periodo = df_escala[
        (df_escala["data"] >= data_inicio_aderencia) & (df_escala["data"] <= data_fim_aderencia)
    ]

    if df_hist_filtrado_periodo.empty:
        st.info("Não há dados de histórico no período selecionado para calcular a aderência.")
        return
    if df_escala_filtrada_periodo.empty:
        st.info("Não há dados de escala no período selecionado para calcular a aderência.")
        return

    df_metricas_aderencia = _calcular_metricas_aderencia(df_hist_filtrado_periodo, df_escala_filtrada_periodo)

    if df_metricas_aderencia.empty:
        st.warning("Não foi possível calcular as métricas de aderência com os dados fornecidos.")
        return

    st.subheader("Métricas de Aderência por Agente e Data")
    st.dataframe(df_metricas_aderencia.style.format({
        "minutos_produtivos_hist": "{:.0f} min",
        "minutos_escala_total": "{:.0f} min",
        "aderencia": "{:.2f}%"
    }), use_container_width=True)

    st.subheader("Aderência Média por Agente")
    aderencia_media_agente = df_metricas_aderencia.groupby("agente")["aderencia"].mean().reset_index()
    aderencia_media_agente = aderencia_media_agente.sort_values("aderencia", ascending=False)

    fig_aderencia = px.bar(
        aderencia_media_agente,
        x="agente",
        y="aderencia",
        title="Aderência Média à Escala por Agente",
        labels={"agente": "Agente", "aderencia": "Aderência Média (%)"},
        color="aderencia",
        color_continuous_scale=px.colors.sequential.Greens,
        height=500
    )
    fig_aderencia.update_yaxes(range=[0, 100])
    st.plotly_chart(fig_aderencia, use_container_width=True)

    st.subheader("Gantt de Aderência (Visualização Detalhada)")
    # Filtro de data para o Gantt de aderência (um único dia)
    data_gantt_aderencia = st.date_input(
        "Selecione a Data para o Gantt de Aderência:",
        value=data_inicio_aderencia,
        min_value=data_inicio_aderencia,
        max_value=data_fim_aderencia,
        key="gantt_aderencia_date"
    )

    df_hist_gantt = df_hist_filtrado_periodo[df_hist_filtrado_periodo["data"] == data_gantt_aderencia]
    df_escala_gantt = df_escala_filtrada_periodo[df_escala_filtrada_periodo["data"] == data_gantt_aderencia]

    st.plotly_chart(_gantt_aderencia(df_hist_gantt, df_escala_gantt, data_gantt_aderencia), use_container_width=True)
