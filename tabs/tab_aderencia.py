# tabs/tab_aderencia.py

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, time, timedelta
from config import (
    PALETA_STATUS,
    ESTADOS_PRODUTIVOS,
    ESTADOS_PAUSA,
    ESTADOS_FORA,
    DIAS_SEMANA_ORDEM,
)

# ─── CONSTANTES DE LAYOUT PARA GRÁFICOS ───────────────────────────────────────
_TICK_VALS = [
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
    21, 22, 23, 24
]
_TICK_TEXT = [
    "00h", "01h", "02h", "03h", "04h", "05h", "06h", "07h", "08h", "09h",
    "10h", "11h", "12h", "13h", "14h", "15h", "16h", "17h", "18h", "19h",
    "20h", "21h", "22h", "23h", "24h"
]

# ─── FUNÇÕES AUXILIARES ──────────────────────────────────────────────────────

def _calcular_aderencia(df_hist: pd.DataFrame, df_escala: pd.DataFrame) -> pd.DataFrame:
    if df_hist.empty or df_escala.empty:
        return pd.DataFrame()

    # Certificar que 'data' em df_hist é datetime.date para o merge
    df_hist_temp = df_hist.copy()
    df_hist_temp["data"] = pd.to_datetime(df_hist_temp["data"])

    # Merge com a escala para obter o turno planejado
    df_merged = pd.merge(
        df_hist_temp,
        df_escala,
        left_on=["agente", df_hist_temp["data"].dt.dayofweek],
        right_on=["agente", "dia_semana_num"],
        how="left",
        suffixes=("_hist", "_escala"),
    )
    df_merged.drop(columns=["key_0"], inplace=True) # Remover coluna de merge

    # Filtrar apenas os registros dentro do turno planejado
    # Ajustar hora_inicio e hora_fim da escala para a data do registro de histórico
    df_merged["turno_inicio_dt"] = df_merged.apply(
        lambda row: datetime.combine(row["data"], row["hora_inicio_escala"]), axis=1
    )
    df_merged["turno_fim_dt"] = df_merged.apply(
        lambda row: datetime.combine(row["data"], row["hora_fim_escala"]), axis=1
    )

    # Se o turno planejado cruza a meia-noite, ajustar turno_fim_dt para o dia seguinte
    df_merged.loc[
        df_merged["hora_fim_escala"] < df_merged["hora_inicio_escala"],
        "turno_fim_dt",
    ] += timedelta(days=1)

    # Filtrar eventos que ocorrem dentro do turno planejado
    df_dentro_turno = df_merged[
        (df_merged["inicio"] >= df_merged["turno_inicio_dt"])
        & (df_merged["fim"] <= df_merged["turno_fim_dt"])
    ].copy()

    # Calcular minutos produtivos e de pausa dentro do turno
    df_dentro_turno["minutos_produtivos"] = df_dentro_turno.apply(
        lambda row: row["minutos"]
        if row["estado"] in ESTADOS_PRODUTIVOS
        else 0,
        axis=1,
    )
    df_dentro_turno["minutos_pausa"] = df_dentro_turno.apply(
        lambda row: row["minutos"]
        if row["estado"] in ESTADOS_PAUSA
        else 0,
        axis=1,
    )

    # Agrupar por agente e data para calcular a aderência diária
    df_aderencia = (
        df_dentro_turno.groupby(["agente", "data", "turno_inicio_dt", "turno_fim_dt"])
        .agg(
            total_minutos_produtivos=("minutos_produtivos", "sum"),
            total_minutos_pausa=("minutos_pausa", "sum"),
        )
        .reset_index()
    )

    # Calcular a duração total do turno planejado em minutos
    df_aderencia["duracao_turno_min"] = (
        df_aderencia["turno_fim_dt"] - df_aderencia["turno_inicio_dt"]
    ).dt.total_seconds() / 60

    # Aderência = (Produtivo + Pausa) / Duração do Turno
    df_aderencia["% Aderência"] = (
        (df_aderencia["total_minutos_produtivos"] + df_aderencia["total_minutos_pausa"])
        / df_aderencia["duracao_turno_min"]
    ) * 100

    # Tratar casos de divisão por zero ou aderência > 100%
    df_aderencia.loc[df_aderencia["duracao_turno_min"] == 0, "% Aderência"] = 0
    df_aderencia.loc[df_aderencia["% Aderência"] > 100, "% Aderência"] = 100

    df_aderencia = df_aderencia.rename(columns={"agente": "Agente", "data": "Data"})
    return df_aderencia

def gantt_aderencia(df_hist: pd.DataFrame, df_escala: pd.DataFrame, agente: str, data: datetime.date):
    df_agente_dia = df_hist[
        (df_hist["agente"] == agente) & (df_hist["data"] == data)
    ].copy()

    df_escala_dia = df_escala[
        (df_escala["agente"] == agente) & (df_escala["dia_semana_num"] == data.weekday())
    ].copy()

    if df_agente_dia.empty and df_escala_dia.empty:
        return go.Figure().update_layout(
            title=f"Nenhum dado ou escala para {agente} em {data.strftime('%d/%m/%Y')}",
            plot_bgcolor="#ffffff",
            paper_bgcolor="#ffffff",
            font=dict(color="#111111"),
        )

    gantt_data = []

    # Adicionar o turno planejado da escala
    if not df_escala_dia.empty:
        escala_row = df_escala_dia.iloc[0]
        turno_inicio = datetime.combine(data, escala_row["hora_inicio_escala"])
        turno_fim = datetime.combine(data, escala_row["hora_fim_escala"])
        if turno_fim < turno_inicio: # Turno que cruza a meia-noite
            turno_fim += timedelta(days=1)

        gantt_data.append(
            dict(
                Task="Turno Planejado",
                Start=turno_inicio,
                Finish=turno_fim,
                Resource="Planejado",
                Color="lightgray",
            )
        )

    # Adicionar os status reais do histórico
    for _, row in df_agente_dia.iterrows():
        gantt_data.append(
            dict(
                Task=row["estado"],
                Start=row["inicio"],
                Finish=row["fim"],
                Resource="Real",
                Color=PALETA_STATUS.get(row["estado"], "#bdc3c7"),
            )
        )

    df_gantt = pd.DataFrame(gantt_data)

    if df_gantt.empty:
        return go.Figure().update_layout(
            title=f"Nenhum dado ou escala para {agente} em {data.strftime('%d/%m/%Y')}",
            plot_bgcolor="#ffffff",
            paper_bgcolor="#ffffff",
            font=dict(color="#111111"),
        )

    # Criar o gráfico de Gantt
    fig = px.timeline(
        df_gantt,
        x_start="Start",
        x_end="Finish",
        y="Resource", # Eixo Y para "Planejado" e "Real"
        color="Color", # Usar a coluna 'Color' para mapear as cores
        title=f"Aderência de {agente} em {data.strftime('%d/%m/%Y')}",
    )

    # Atualizar cores manualmente para garantir que 'Planejado' seja cinza
    fig.update_traces(marker_color=df_gantt["Color"])

    fig.update_yaxes(
        categoryorder="array",
        categoryarray=["Real", "Planejado"], # Ordem específica
        tickfont=dict(color="#111111"),
        title=dict(text="Tipo de Registro", font=dict(color="#111111")),
    )

    fig.update_xaxes(
        tickvals=[
            datetime(data.year, data.month, data.day, h)
            for h in _TICK_VALS
        ],
        ticktext=_TICK_TEXT,
        range=[
            datetime(data.year, data.month, data.day, 0, 0, 0),
            datetime(data.year, data.month, data.day, 23, 59, 59) + timedelta(seconds=1)
        ],
        tickformat="%Hh",
        showgrid=True,
        gridcolor="#e0e0e0",
        tickfont=dict(color="#111111"),
        title=dict(text="Hora do Dia", font=dict(color="#111111")),
    )

    fig.update_layout(
        hovermode="x unified",
        xaxis_title="Hora do Dia",
        yaxis_title="Tipo de Registro",
        template="plotly_white",
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        font=dict(color="#111111"),
        showlegend=False, # A legenda de cores não é útil aqui com 'Color' direto
    )

    return fig

def _ranking_aderencia(df_aderencia: pd.DataFrame):
    df_rank = df_aderencia.groupby("Agente")["% Aderência"].mean().reset_index()
    df_rank = df_rank.sort_values("% Aderência", ascending=False)

    fig = px.bar(
        df_rank,
        x="Agente",
        y="% Aderência",
        color="% Aderência",
        color_continuous_scale="RdYlGn",
        range_color=[0, 100],
        text="% Aderência",
        title="Ranking de Aderência Média por Agente",
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(
        coloraxis_showscale=False,
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        font=dict(color="#111111"),
        yaxis_range=[0, 110],
        xaxis=dict(tickfont=dict(color="#111111"), titlefont=dict(color="#111111")),
        yaxis=dict(tickfont=dict(color="#111111"), titlefont=dict(color="#111111")),
    )
    return fig

def _evolucao_aderencia(df_aderencia: pd.DataFrame, agente_selecionado: str):
    df_agente = df_aderencia[df_aderencia["Agente"] == agente_selecionado].copy()
    df_agente = df_agente.sort_values("Data")

    fig = px.line(
        df_agente,
        x="Data",
        y="% Aderência",
        title=f"Evolução da Aderência para {agente_selecionado}",
        labels={"Data": "Data", "% Aderência": "Aderência (%)"},
        markers=True,
    )
    fig.update_layout(
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        font=dict(color="#111111"),
        xaxis=dict(tickfont=dict(color="#111111"), titlefont=dict(color="#111111")),
        yaxis=dict(tickfont=dict(color="#111111"), titlefont=dict(color="#111111")),
    )
    return fig

def _heatmap_aderencia(df_aderencia: pd.DataFrame):
    df_pivot = df_aderencia.pivot_table(
        index="Agente",
        columns=df_aderencia["Data"].dt.day_name(locale="pt_BR"),
        values="% Aderência",
    )
    # Reordenar colunas do heatmap para seguir a ordem da semana
    df_pivot = df_pivot[DIAS_SEMANA_ORDEM]

    fig = px.heatmap(
        df_pivot,
        title="Aderência Média por Agente e Dia da Semana",
        color_continuous_scale="RdYlGn",
        range_color=[0, 100],
        labels={"Agente": "Agente", "Data": "Dia da Semana", "value": "Aderência (%)"},
    )
    fig.update_layout(
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        font=dict(color="#111111"),
        xaxis=dict(tickfont=dict(color="#111111"), titlefont=dict(color="#111111")),
        yaxis=dict(tickfont=dict(color="#111111"), titlefont=dict(color="#111111")),
    )
    return fig

def df_to_xlsx(df: pd.DataFrame) -> bytes:
    output = pd.ExcelWriter("temp.xlsx", engine="xlsxwriter")
    df.to_excel(output, index=False, sheet_name="Dados")
    output.close()
    with open("temp.xlsx", "rb") as f:
        excel_data = f.read()
    return excel_data

# ─── RENDERIZAÇÃO DA ABA ADERÊNCIA ───────────────────────────────────────────

def render(df_hist: pd.DataFrame, df_escala: pd.DataFrame):
    st.title("🎯 Aderência à Escala")

    if df_hist.empty or df_escala.empty:
        st.info(
            "Por favor, suba um arquivo de histórico de status e um arquivo de escala "
            "na barra lateral para calcular a aderência."
        )
        return

    df_aderencia = _calcular_aderencia(df_hist, df_escala)

    if df_aderencia.empty:
        st.warning("Não foi possível calcular a aderência com os dados fornecidos.")
        return

    # ── Filtros Globais ──────────────────────────────────────────────────────
    st.sidebar.subheader("⚙️ Filtros de Aderência")
    agentes_unicos = sorted(df_aderencia["Agente"].unique().tolist())
    agentes_selecionados = st.sidebar.multiselect(
        "Agentes", agentes_unicos, default=agentes_unicos, key="ader_agentes_filtro"
    )

    datas_unicas = sorted(df_aderencia["Data"].unique().tolist(), reverse=True)
    datas_selecionadas = st.sidebar.multiselect(
        "Datas",
        datas_unicas,
        default=datas_unicas[:7], # Seleciona as últimas 7 datas por padrão
        format_func=lambda d: pd.to_datetime(d).strftime("%d/%m/%Y"),
        key="ader_datas_filtro",
    )

    meta_aderencia = st.sidebar.slider(
        "Meta de Aderência (%)", 0, 100, 80, key="ader_meta_slider"
    )

    df_ad_filtrado = df_aderencia[
        (df_aderencia["Agente"].isin(agentes_selecionados))
        & (df_aderencia["Data"].isin(datas_selecionadas))
    ].copy()

    if df_ad_filtrado.empty:
        st.warning("Nenhum dado de aderência encontrado com os filtros selecionados.")
        return

    # ── KPIs de Aderência ─────────────────────────────────────────────────────
    media_geral = df_ad_filtrado["% Aderência"].mean()
    dias_ok     = int((df_ad_filtrado["% Aderência"] >= meta_aderencia).sum())
    dias_nok    = int((df_ad_filtrado["% Aderência"] <  meta_aderencia).sum())

    st.subheader("Sumário de Aderência")
    k1, k2, k3 = st.columns(3)
    k1.metric("📊 Aderência Média",      f"{media_geral:.1f}%")
    k2.metric("✅ Dias acima da meta",   str(dias_ok))
    k3.metric("⚠️ Dias abaixo da meta", str(dias_nok))

    st.divider()

    # ── Ranking de Aderência ──────────────────────────────────────────────────
    st.subheader("🏆 Ranking de Aderência")
    fig_rank = _ranking_aderencia(df_ad_filtrado)
    st.plotly_chart(fig_rank, use_container_width=True, key="ader_fig_rank")

    st.divider()

    # ── Evolução da Aderência ─────────────────────────────────────────────────
    st.subheader("📈 Evolução da Aderência por Agente")
    agente_evolucao = st.selectbox(
        "👤 Selecione um agente para ver a evolução",
        agentes_selecionados,
        key="ader_evolucao_agente",
    )
    if agente_evolucao:
        fig_evolucao = _evolucao_aderencia(df_ad_filtrado, agente_evolucao)
        st.plotly_chart(fig_evolucao, use_container_width=True, key="ader_fig_evolucao")
    else:
        st.info("Selecione um agente para visualizar a evolução da aderência.")

    st.divider()

    # ── Heatmap de Aderência ──────────────────────────────────────────────────
    st.subheader("🔥 Aderência por Agente e Dia da Semana")
    fig_heat = _heatmap_aderencia(df_ad_filtrado)
    st.plotly_chart(fig_heat, use_container_width=True, key="ader_fig_heat")

    st.divider()

    # ── Gantt de aderência ────────────────────────────────────────────────────
    st.subheader("📊 Gantt de Aderência Diária (Planejado vs. Real)")

    col_g1, col_g2 = st.columns(2)
    with col_g1:
        agente_gantt = st.selectbox(
            "👤 Selecione um agente para o Gantt",
            sorted(df_ad_filtrado["Agente"].unique()),
            key="ader_gantt_agente",
        )
    with col_g2:
        datas_agente = sorted(
            df_ad_filtrado[df_ad_filtrado["Agente"] == agente_gantt]["Data"].unique()
        )
        if datas_agente:
            data_gantt = st.selectbox(
                "Data para Gantt",
                datas_agente,
                format_func=lambda d: pd.to_datetime(d).strftime("%d/%m/%Y"),
                key="ader_gantt_data",
            )
        else:
            data_gantt = None
            st.info("Selecione um agente com dados para ver o Gantt.")

    if agente_gantt and data_gantt:
        fig_gantt = gantt_aderencia(df_hist, df_escala, agente_gantt, data_gantt)
        st.plotly_chart(fig_gantt, use_container_width=True, key="ader_fig_gantt")
    else:
        st.info("Selecione um agente e uma data para visualizar o Gantt de aderência.")

    st.divider()

    # ── Tabela detalhada ──────────────────────────────────────────────────────
    st.subheader("📋 Detalhamento por Dia e Agente")

    df_exib = df_ad_filtrado.copy()
    df_exib["Data"] = df_exib["Data"].dt.strftime("%d/%m/%Y")

    def _color(val):
        if isinstance(val, (int, float)):
            return f"background-color: {'#d4edda' if val >= meta_aderencia else '#f8d7da'}"
        return ""

    st.dataframe(
        df_exib.sort_values(["Data", "Agente"])
        .style.applymap(_color, subset=["% Aderência"]),
        use_container_width=True,
        height=420,
    )

    st.divider()

    # ── Export ────────────────────────────────────────────────────────────────
    st.subheader("💾 Exportar")
    ce1, ce2 = st.columns(2)
    ce1.download_button(
        "⬇️ Aderência detalhada (XLSX)",
        data=df_to_xlsx(df_exib),
        file_name="aderencia_detalhada.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="ader_exp_det",
    )
    ce2.download_button(
        "⬇️ Ranking (XLSX)",
        data=df_to_xlsx(df_rank), # Usando df_rank do ranking acima
        file_name="aderencia_ranking.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="ader_exp_rank",
    )
