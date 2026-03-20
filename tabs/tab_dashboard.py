# tabs/tab_dashboard.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from config import (
    PALETA_STATUS,
    ESTADOS_PRODUTIVOS,
    ESTADOS_PAUSA,
    ESTADOS_FORA,
)
from utils.data_loader import get_agentes


# ── GANTT ─────────────────────────────────────────────────────────────────────

def _gantt(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    agentes = sorted(df["agente"].unique())
    estados_vistos = set()

    for agente in agentes:
        df_ag = df[df["agente"] == agente].sort_values("inicio")
        for _, row in df_ag.iterrows():
            ini = row["inicio"]
            fim = row["fim"]
            if pd.isna(ini) or pd.isna(fim):
                continue

            cor   = PALETA_STATUS.get(row["estado"], "#bdc3c7")
            meia  = ini.replace(hour=0, minute=0, second=0, microsecond=0)
            base  = (ini - meia).total_seconds() / 60
            dur   = (fim - ini).total_seconds() / 60
            if dur <= 0:
                continue

            label = row["estado"]
            show  = label not in estados_vistos
            estados_vistos.add(label)

            fig.add_trace(go.Bar(
                x=[dur],
                y=[agente],
                base=[base],
                orientation="h",
                marker_color=cor,
                name=label,
                legendgroup=label,
                showlegend=show,
                hovertemplate=(
                    f"<b>{agente}</b><br>"
                    f"Status: {row['estado']}<br>"
                    f"Início: {ini.strftime('%H:%M')}<br>"
                    f"Fim: {fim.strftime('%H:%M')}<br>"
                    f"Duração: {row.get('minutos', dur):.1f} min"
                    "<extra></extra>"
                ),
            ))

    horas   = list(range(0, 1441, 60))
    rotulos = [f"{h // 60:02d}:00" for h in horas]

    fig.update_layout(
        barmode="overlay",
        height=max(300, len(agentes) * 55 + 120),
        title="Timeline de Status por Agente",
        xaxis=dict(
            title=dict(text="Hora do dia", font=dict(color="#111111")),
            tickvals=horas,
            ticktext=rotulos,
            range=[0, 1440],
            showgrid=True,
            gridcolor="#e0e0e0",
            zeroline=False,
            tickfont=dict(color="#111111"),
        ),
        yaxis=dict(
            title=dict(text="Agente", font=dict(color="#111111")),
            automargin=True,
            tickfont=dict(color="#111111"),
        ),
        legend=dict(
            title=dict(text="Status", font=dict(color="#111111")),
            font=dict(color="#111111"),
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="#cccccc",
            borderwidth=1,
        ),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        title_font=dict(color="#111111"),
        margin=dict(l=180, r=20, t=60, b=60),
    )
    return fig


# ── KPIs ──────────────────────────────────────────────────────────────────────

def kpis_dia(df: pd.DataFrame) -> dict:
    agentes_com_online = df[df["estado"].isin(ESTADOS_PRODUTIVOS)]["agente"].unique()

    if len(agentes_com_online) == 0:
        df_base = df.copy()
    else:
        df_base = df[df["agente"].isin(agentes_com_online)].copy()

    prod  = df_base[df_base["estado"].isin(ESTADOS_PRODUTIVOS)]["minutos"].sum()
    pausa = df_base[df_base["estado"].isin(ESTADOS_PAUSA)]["minutos"].sum()
    fora  = df_base[df_base["estado"].isin(ESTADOS_FORA)]["minutos"].sum()
    total = prod + pausa + fora

    if total == 0:
        total = 1

    return {
        "prod_min":  prod,
        "pausa_min": pausa,
        "fora_min":  fora,
        "total_min": prod + pausa + fora,
        "pct_prod":  prod  / total * 100,
        "pct_pausa": pausa / total * 100,
        "pct_fora":  fora  / total * 100,
    }


def _ranking(df: pd.DataFrame):
    rows = []
    for ag in df["agente"].unique():
        d = df[df["agente"] == ag]
        prod  = d[d["estado"].isin(ESTADOS_PRODUTIVOS)]["minutos"].sum()
        pausa = d[d["estado"].isin(ESTADOS_PAUSA)]["minutos"].sum()
        fora  = d[d["estado"].isin(ESTADOS_FORA)]["minutos"].sum()
        total = prod + pausa + fora
        if total == 0:
            total = 1

        rows.append({
            "Agente":       ag,
            "Produtivo":    prod,
            "Pausa":        pausa,
            "Fora":         fora,
            "% Produtivo":  prod  / total * 100,
            "% Pausa":      pausa / total * 100,
            "% Fora":       fora  / total * 100,
        })

    df_rank = pd.DataFrame(rows)
    df_rank = df_rank.sort_values("% Produtivo", ascending=False)

    fig = px.bar(
        df_rank,
        x="Agente",
        y="% Produtivo",
        title="% de Tempo Produtivo por Agente (dia selecionado)",
        color="% Produtivo",
        color_continuous_scale="Greens",
        template="plotly_white",
    )
    fig.update_layout(
        xaxis_title="Agente",
        yaxis_title="% Produtivo",
        xaxis_tickangle=-45,
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        font=dict(color="#111111"),
        title_font=dict(color="#111111"),
        xaxis_tickfont=dict(color="#111111"),
        yaxis_tickfont=dict(color="#111111"),
    )

    return fig, df_rank


def render(df_hist: pd.DataFrame, limite_alerta: int):
    st.header("📊 Dashboard de Status")

    if df_hist.empty:
        st.info("Faça upload de ao menos um relatório para visualizar o dashboard.")
        return

    datas = sorted(df_hist["data"].unique())
    data_sel = st.date_input(
        "📅 Dia",
        value=max(datas),
        min_value=min(datas),
        max_value=max(datas),
        key="dash_data",
    )

    df_dia = df_hist[df_hist["data"] == data_sel].copy()

    agentes_disp = get_agentes(df_dia)
    agentes_sel = st.multiselect(
        "👥 Agentes",
        options=agentes_disp,
        default=agentes_disp,
        key="dash_agentes",
    )

    df_dia = df_dia[df_dia["agente"].isin(agentes_sel)]

    if df_dia.empty:
        st.warning("Nenhum dado para os filtros selecionados.")
        return

    # KPIs
    k = kpis_dia(df_dia)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🟢 Produtivo", f"{k['pct_prod']:.1f}%", f"{k['prod_min']:.0f} min")
    c2.metric("🟡 Pausa",     f"{k['pct_pausa']:.1f}%", f"{k['pausa_min']:.0f} min")
    c3.metric("🔴 Fora",      f"{k['pct_fora']:.1f}%", f"{k['fora_min']:.0f} min")
    c4.metric("⏱️ Total Registrado", f"{k['total_min']:.0f} min")

    st.divider()

    st.subheader("⏱️ Timeline por Agente")
    st.plotly_chart(_gantt(df_dia), use_container_width=True, key="dash_gantt")

    st.divider()

    st.subheader("🏆 Ranking de Produtividade")
    fig_rank, df_rank = _ranking(df_dia)
    st.plotly_chart(fig_rank, use_container_width=True, key="dash_rank")
    with st.expander("📋 Ver tabela"):
        st.dataframe(df_rank, use_container_width=True)
