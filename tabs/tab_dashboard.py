# tabs/tab_dashboard.py

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

# ─── FUNÇÕES AUXILIARES PARA GRÁFICOS ────────────────────────────────────────

def _gantt_chart(df_hist: pd.DataFrame, agente_selecionado: str, data_selecionada: datetime.date):
    df_agente_dia = df_hist[
        (df_hist["agente"] == agente_selecionado)
        & (df_hist["data"] == data_selecionada)
    ].copy()

    if df_agente_dia.empty:
        return go.Figure().update_layout(
            title=f"Nenhum dado para {agente_selecionado} em {data_selecionada.strftime('%d/%m/%Y')}",
            plot_bgcolor="#ffffff",
            paper_bgcolor="#ffffff",
            font=dict(color="#111111"),
        )

    # Ordenar por início para garantir a sequência correta
    df_agente_dia = df_agente_dia.sort_values("inicio")

    # Criar o gráfico de Gantt
    fig = px.timeline(
        df_agente_dia,
        x_start="inicio",
        x_end="fim",
        y="estado", # Mostra os estados no eixo Y
        color="estado",
        color_discrete_map=PALETA_STATUS,
        title=f"Gantt de Status para {agente_selecionado} em {data_selecionada.strftime('%d/%m/%Y')}",
    )

    fig.update_yaxes(
        categoryorder="array",
        categoryarray=sorted(df_agente_dia["estado"].unique()),
        tickfont=dict(color="#111111"),
        title=dict(text="Estado", font=dict(color="#111111")),
    )

    fig.update_xaxes(
        tickvals=[
            datetime(data_selecionada.year, data_selecionada.month, data_selecionada.day, h)
            for h in _TICK_VALS
        ],
        ticktext=_TICK_TEXT,
        range=[
            datetime(data_selecionada.year, data_selecionada.month, data_selecionada.day, 0, 0, 0),
            datetime(data_selecionada.year, data_selecionada.month, data_selecionada.day, 23, 59, 59) + timedelta(seconds=1)
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
        yaxis_title="Estado",
        template="plotly_white",
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        font=dict(color="#111111"),
        legend_title_text="Status",
    )

    return fig

def _ranking_status(df_hist: pd.DataFrame, tipo_status: str):
    df_filtrado = df_hist[df_hist["estado"].isin(tipo_status)].copy()
    df_ranking = (
        df_filtrado.groupby("agente")["minutos"].sum().reset_index()
    )
    df_ranking["horas"] = df_ranking["minutos"] / 60
    df_ranking = df_ranking.sort_values("horas", ascending=False)

    fig = px.bar(
        df_ranking,
        x="agente",
        y="horas",
        title=f"Ranking de Agentes por Tempo em Status {tipo_status[0].split(' ')[0]}",
        labels={"agente": "Agente", "horas": "Horas"},
        color_discrete_sequence=px.colors.qualitative.Pastel,
    )
    fig.update_layout(
        xaxis_title="Agente",
        yaxis_title="Horas",
        template="plotly_white",
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        font=dict(color="#111111"),
        xaxis=dict(tickfont=dict(color="#111111"), titlefont=dict(color="#111111")),
        yaxis=dict(tickfont=dict(color="#111111"), titlefont=dict(color="#111111")),
    )
    return fig

def _historico_diario(df_hist: pd.DataFrame, agente_selecionado: str):
    df_agente = df_hist[df_hist["agente"] == agente_selecionado].copy()
    df_agente["data"] = pd.to_datetime(df_agente["data"]) # Garante que 'data' é datetime

    df_resumo_diario = (
        df_agente.groupby(["data", "estado"])["minutos"].sum().unstack(fill_value=0)
    )
    df_resumo_diario = df_resumo_diario.reindex(
        columns=list(PALETA_STATUS.keys()), fill_value=0
    ) # Garante todas as colunas de status

    df_resumo_diario["Total"] = df_resumo_diario.sum(axis=1)
    df_resumo_diario = df_resumo_diario.stack().reset_index(name="minutos")
    df_resumo_diario = df_resumo_diario.rename(columns={"level_0": "data", "level_1": "estado"})
    df_resumo_diario["horas"] = df_resumo_diario["minutos"] / 60

    fig = px.area(
        df_resumo_diario,
        x="data",
        y="horas",
        color="estado",
        title=f"Histórico Diário de Status para {agente_selecionado}",
        labels={"data": "Data", "horas": "Horas", "estado": "Estado"},
        color_discrete_map=PALETA_STATUS,
    )
    fig.update_layout(
        xaxis_title="Data",
        yaxis_title="Horas",
        template="plotly_white",
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        font=dict(color="#111111"),
        xaxis=dict(tickfont=dict(color="#111111"), titlefont=dict(color="#111111")),
        yaxis=dict(tickfont=dict(color="#111111"), titlefont=dict(color="#111111")),
    )
    return fig

# ─── FUNÇÃO PARA EXPORTAR DATAFRAME PARA XLSX ────────────────────────────────

def df_to_xlsx(df: pd.DataFrame) -> bytes:
    output = pd.ExcelWriter("temp.xlsx", engine="xlsxwriter")
    df.to_excel(output, index=False, sheet_name="Dados")
    output.close()
    with open("temp.xlsx", "rb") as f:
        excel_data = f.read()
    return excel_data

# ─── RENDERIZAÇÃO DA ABA DASHBOARD ───────────────────────────────────────────

def render(df_hist: pd.DataFrame, limite_alerta: int):
    st.title("📊 Dashboard de Monitoramento")

    if df_hist.empty:
        st.info("Por favor, suba um arquivo de histórico de status na barra lateral.")
        return

    # ── Filtros Globais ──────────────────────────────────────────────────────
    st.sidebar.subheader("⚙️ Filtros do Dashboard")
    agentes_unicos = sorted(df_hist["agente"].unique().tolist())
    agentes_selecionados = st.sidebar.multiselect(
        "Agentes", agentes_unicos, default=agentes_unicos, key="dash_agentes_filtro"
    )

    datas_unicas = sorted(df_hist["data"].unique().tolist(), reverse=True)
    datas_selecionadas = st.sidebar.multiselect(
        "Datas",
        datas_unicas,
        default=datas_unicas[:7], # Seleciona as últimas 7 datas por padrão
        format_func=lambda d: d.strftime("%d/%m/%Y"),
        key="dash_datas_filtro",
    )

    df_filtrado = df_hist[
        (df_hist["agente"].isin(agentes_selecionados))
        & (df_hist["data"].isin(datas_selecionadas))
    ].copy()

    if df_filtrado.empty:
        st.warning("Nenhum dado encontrado com os filtros selecionados.")
        return

    # ── KPIs ──────────────────────────────────────────────────────────────────
    total_minutos = df_filtrado["minutos"].sum()
    total_horas = total_minutos / 60

    minutos_produtivos = df_filtrado[df_filtrado["estado"].isin(ESTADOS_PRODUTIVOS)]["minutos"].sum()
    horas_produtivas = minutos_produtivos / 60
    perc_produtivo = (minutos_produtivos / total_minutos * 100) if total_minutos > 0 else 0

    minutos_pausa = df_filtrado[df_filtrado["estado"].isin(ESTADOS_PAUSA)]["minutos"].sum()
    horas_pausa = minutos_pausa / 60
    perc_pausa = (minutos_pausa / total_minutos * 100) if total_minutos > 0 else 0

    minutos_fora = df_filtrado[df_filtrado["estado"].isin(ESTADOS_FORA)]["minutos"].sum()
    horas_fora = minutos_fora / 60
    perc_fora = (minutos_fora / total_minutos * 100) if total_minutos > 0 else 0

    st.subheader("Sumário Geral")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Registrado", f"{total_horas:.1f}h")
    col2.metric("Produtivo", f"{horas_produtivas:.1f}h ({perc_produtivo:.1f}%)")
    col3.metric("Pausa", f"{horas_pausa:.1f}h ({perc_pausa:.1f}%)")
    col4.metric("Fora/Offline", f"{horas_fora:.1f}h ({perc_fora:.1f}%)")

    st.divider()

    # ── Gráfico de Gantt ──────────────────────────────────────────────────────
    st.subheader("Gantt de Status por Agente e Dia")
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        agente_gantt = st.selectbox(
            "Selecione um agente",
            agentes_selecionados,
            key="dash_gantt_agente",
        )
    with col_g2:
        datas_agente = sorted(
            df_filtrado[df_filtrado["agente"] == agente_gantt]["data"].unique(),
            reverse=True,
        )
        if datas_agente:
            data_gantt = st.selectbox(
                "Selecione a data",
                datas_agente,
                format_func=lambda d: pd.to_datetime(d).strftime("%d/%m/%Y"),
                key="dash_gantt_data",
            )
        else:
            data_gantt = None
            st.info("Selecione um agente com dados para ver o Gantt.")

    if agente_gantt and data_gantt:
        fig_gantt = _gantt_chart(df_filtrado, agente_gantt, data_gantt)
        st.plotly_chart(fig_gantt, use_container_width=True, key="dash_fig_gantt")
    else:
        st.info("Selecione um agente e uma data para visualizar o Gantt.")

    st.divider()

    # ── Ranking de Status Produtivo ───────────────────────────────────────────
    st.subheader("Ranking de Tempo Produtivo")
    fig_rank_prod = _ranking_status(df_filtrado, ESTADOS_PRODUTIVOS)
    st.plotly_chart(fig_rank_prod, use_container_width=True, key="dash_fig_rank_prod")

    st.divider()

    # ── Ranking de Status de Pausa ────────────────────────────────────────────
    st.subheader("Ranking de Tempo em Pausa")
    fig_rank_pausa = _ranking_status(df_filtrado, ESTADOS_PAUSA)
    st.plotly_chart(fig_rank_pausa, use_container_width=True, key="dash_fig_rank_pausa")

    st.divider()

    # ── Histórico Diário de Status ────────────────────────────────────────────
    st.subheader("Histórico Diário de Status por Agente")
    agente_hist = st.selectbox(
        "Selecione um agente para o histórico",
        agentes_selecionados,
        key="dash_hist_agente",
    )
    if agente_hist:
        fig_hist = _historico_diario(df_filtrado, agente_hist)
        st.plotly_chart(fig_hist, use_container_width=True, key="dash_fig_hist")
    else:
        st.info("Selecione um agente para visualizar o histórico diário.")

    st.divider()

    # ── Export ────────────────────────────────────────────────────────────────
    st.subheader("💾 Exportar Dados Filtrados")
    st.download_button(
        "⬇️ Exportar Dados do Dashboard (XLSX)",
        data=df_to_xlsx(df_filtrado),
        file_name="dashboard_dados_filtrados.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="dash_exp_filtrados",
    )
