# tabs/tab_dashboard.py
import io
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from config import (
    PALETA_STATUS, ESTADOS_PRODUTIVOS,
    ESTADOS_PAUSA, ESTADOS_FORA,
)
from utils.data_loader import get_agentes

# ─── CONSTANTES ───────────────────────────────────────────────────────────────

_TICK_VALS = list(range(0, 1441, 60))
_TICK_TEXT = [f"{v // 60:02d}:00" for v in _TICK_VALS]


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _to_xlsx(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False)
    return buf.getvalue()


# ─── GANTT ────────────────────────────────────────────────────────────────────

def _gantt(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    agentes = sorted(df["agente"].unique(), reverse=True)
    estados_vis = set()

    for agente in agentes:
        df_ag = df[df["agente"] == agente].sort_values("inicio")
        for _, row in df_ag.iterrows():
            ini = row["inicio"]
            fim = row["fim"]
            if pd.isna(ini) or pd.isna(fim):
                continue
            meia = ini.replace(hour=0, minute=0, second=0, microsecond=0)
            base = (ini - meia).total_seconds() / 60
            dur  = (fim - ini).total_seconds() / 60
            if dur <= 0:
                continue

            estado = row["estado"]
            cor    = PALETA_STATUS.get(estado, "#aaaaaa")
            show   = estado not in estados_vis
            estados_vis.add(estado)

            fig.add_trace(go.Bar(
                x=[dur],
                y=[agente],
                base=[base],
                orientation="h",
                marker=dict(color=cor, line=dict(width=0)),
                name=estado,
                legendgroup=estado,
                showlegend=show,
                hovertemplate=(
                    f"<b>{agente}</b><br>"
                    f"Status: {estado}<br>"
                    f"Início: {ini.strftime('%H:%M')}<br>"
                    f"Fim: {fim.strftime('%H:%M')}<br>"
                    f"Duração: {dur:.1f} min<extra></extra>"
                ),
            ))

    fig.update_layout(
        barmode="overlay",
        height=max(400, len(agentes) * 48 + 140),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        font=dict(color="#111111", size=12),
        title=dict(
            text="Timeline de Status por Agente",
            font=dict(color="#111111"),
        ),
        xaxis=dict(
            title=dict(text="Hora do dia", font=dict(color="#111111")),
            tickvals=_TICK_VALS,
            ticktext=_TICK_TEXT,
            range=[0, 1440],
            showgrid=True,
            gridcolor="#e5e5e5",
            zeroline=False,
            tickfont=dict(color="#111111"),
        ),
        yaxis=dict(
            title=dict(text="", font=dict(color="#111111")),
            tickfont=dict(color="#111111"),
            automargin=True,
        ),
        legend=dict(
            title=dict(text="Status", font=dict(color="#111111")),
            font=dict(color="#111111"),
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="#cccccc",
            borderwidth=1,
        ),
        margin=dict(l=220, r=20, t=60, b=60),
    )
    return fig


# ─── KPIs ─────────────────────────────────────────────────────────────────────

def _kpis(df: pd.DataFrame) -> dict:
    agentes_online = df[
        df["estado"].isin(ESTADOS_PRODUTIVOS)
    ]["agente"].unique()

    df_base = (
        df[df["agente"].isin(agentes_online)].copy()
        if len(agentes_online) > 0
        else df.copy()
    )

    prod  = df_base[df_base["estado"].isin(ESTADOS_PRODUTIVOS)]["minutos"].sum()
    pausa = df_base[df_base["estado"].isin(ESTADOS_PAUSA)]["minutos"].sum()
    fora  = df_base[df_base["estado"].isin(ESTADOS_FORA)]["minutos"].sum()
    total = prod + pausa + fora or 1

    return {
        "prod_min":  round(prod, 1),
        "pausa_min": round(pausa, 1),
        "fora_min":  round(fora, 1),
        "total_min": round(prod + pausa + fora, 1),
        "pct_prod":  prod  / total * 100,
        "pct_pausa": pausa / total * 100,
        "pct_fora":  fora  / total * 100,
        "n_agentes": int(len(agentes_online)),
    }


# ─── RANKING ──────────────────────────────────────────────────────────────────

def _ranking(df: pd.DataFrame):
    rows = []
    for ag in df["agente"].unique():
        d     = df[df["agente"] == ag]
        prod  = d[d["estado"].isin(ESTADOS_PRODUTIVOS)]["minutos"].sum()
        pausa = d[d["estado"].isin(ESTADOS_PAUSA)]["minutos"].sum()
        fora  = d[d["estado"].isin(ESTADOS_FORA)]["minutos"].sum()
        total = prod + pausa + fora
        rows.append({
            "Agente":          ag,
            "Produtivo (min)": round(prod,  1),
            "Pausa (min)":     round(pausa, 1),
            "Fora (min)":      round(fora,  1),
            "Total (min)":     round(total, 1),
            "% Produtivo":     round(prod / total * 100, 1) if total > 0 else 0.0,
        })

    df_r = pd.DataFrame(rows).sort_values("% Produtivo", ascending=False)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_r["Agente"],
        y=df_r["% Produtivo"],
        marker=dict(
            color=df_r["% Produtivo"],
            colorscale="RdYlGn",
            cmin=0,
            cmax=100,
            showscale=False,
        ),
        text=df_r["% Produtivo"].apply(lambda v: f"{v:.1f}%"),
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>% Produtivo: %{y:.1f}%<extra></extra>",
    ))
    fig.update_layout(
        title=dict(
            text="% Tempo Produtivo por Agente",
            font=dict(color="#111111"),
        ),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        font=dict(color="#111111", size=12),
        yaxis=dict(
            range=[0, 115],
            title=dict(text="% Produtivo", font=dict(color="#111111")),
            tickfont=dict(color="#111111"),
        ),
        xaxis=dict(
            tickangle=-30,
            tickfont=dict(color="#111111"),
        ),
        margin=dict(t=60, b=100),
    )
    return fig, df_r


# ─── ALERTAS ──────────────────────────────────────────────────────────────────

def _alertas(df: pd.DataFrame, limite: int) -> pd.DataFrame:
    estados_alerta = ESTADOS_PAUSA + ESTADOS_FORA
    rows = []
    for _, r in df[df["estado"].isin(estados_alerta)].iterrows():
        mins = r.get("minutos", 0) or 0
        if mins >= limite:
            rows.append({
                "Agente":        r["agente"],
                "Status":        r["estado"],
                "Início":        r["inicio"].strftime("%H:%M"),
                "Fim":           r["fim"].strftime("%H:%M"),
                "Duração (min)": round(mins, 1),
            })
    return (
        pd.DataFrame(rows).sort_values("Duração (min)", ascending=False)
        if rows else pd.DataFrame()
    )


# ─── HISTÓRICO ────────────────────────────────────────────────────────────────

def _historico_linha(df_hist: pd.DataFrame):
    if df_hist.empty:
        return None

    rows = []
    for ag in df_hist["agente"].unique():
        for dt in df_hist["data"].unique():
            d     = df_hist[(df_hist["agente"] == ag) & (df_hist["data"] == dt)]
            prod  = d[d["estado"].isin(ESTADOS_PRODUTIVOS)]["minutos"].sum()
            total = d["minutos"].sum()
            rows.append({
                "Agente":      ag,
                "Data":        pd.Timestamp(dt),
                "% Produtivo": round(prod / total * 100, 1) if total > 0 else 0.0,
            })

    df_ev = pd.DataFrame(rows).sort_values("Data")
    if df_ev.empty:
        return None

    fig = go.Figure()
    for ag in df_ev["Agente"].unique():
        d = df_ev[df_ev["Agente"] == ag]
        fig.add_trace(go.Scatter(
            x=d["Data"],
            y=d["% Produtivo"],
            mode="lines+markers",
            name=ag,
            hovertemplate=f"<b>{ag}</b><br>%{{x}}<br>%{{y:.1f}}%<extra></extra>",
        ))

    fig.add_hline(
        y=80,
        line_dash="dash",
        line_color="red",
        annotation_text="Meta 80%",
        annotation_font_color="#111111",
    )
    fig.update_layout(
        title=dict(
            text="Evolução Histórica – % Tempo Produtivo",
            font=dict(color="#111111"),
        ),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        font=dict(color="#111111", size=12),
        yaxis=dict(
            range=[0, 110],
            title=dict(text="% Produtivo", font=dict(color="#111111")),
            tickfont=dict(color="#111111"),
        ),
        xaxis=dict(
            title=dict(text="Data", font=dict(color="#111111")),
            tickfont=dict(color="#111111"),
        ),
        legend=dict(font=dict(color="#111111")),
    )
    return fig


# ─── RENDER ───────────────────────────────────────────────────────────────────

def render(df_hist: pd.DataFrame, limite_alerta: int):
    st.header("📊 Dashboard de Status")

    if df_hist.empty:
        st.info("Faça o upload de um relatório na barra lateral para começar.")
        return

    agentes_disp = get_agentes(df_hist)
    datas        = sorted(df_hist["data"].unique(), reverse=True)

    col_f1, col_f2 = st.columns([1, 3])
    with col_f1:
        data_sel = st.selectbox(
            "📅 Data", datas,
            format_func=lambda d: (
                d.strftime("%d/%m/%Y") if hasattr(d, "strftime") else str(d)
            ),
            key="dash_data_sel",
        )
    with col_f2:
        agentes_sel = st.multiselect(
            "👤 Agentes", agentes_disp, default=agentes_disp,
            key="dash_agentes_sel",
        )

    df_dia = df_hist[
        (df_hist["data"] == data_sel) &
        (df_hist["agente"].isin(agentes_sel))
    ].copy()

    if df_dia.empty:
        st.warning("Sem dados para o dia e agentes selecionados.")
        return

    # ── KPIs ──────────────────────────────────────────────────────────────────
    k = _kpis(df_dia)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "🟢 Produtivo",
        f"{k['pct_prod']:.1f}%",
        f"{k['prod_min']:.0f} min",
    )
    c2.metric(
        "🟡 Em Pausa",
        f"{k['pct_pausa']:.1f}%",
        f"{k['pausa_min']:.0f} min",
    )
    c3.metric(
        "🔴 Fora/Offline",
        f"{k['pct_fora']:.1f}%",
        f"{k['fora_min']:.0f} min",
    )
    c4.metric(
        "👥 Agentes com login",
        k["n_agentes"],
        f"de {len(agentes_sel)} selecionados",
    )

    st.divider()

    # ── Gantt ─────────────────────────────────────────────────────────────────
    st.subheader("📈 Timeline de Status")
    st.plotly_chart(
        _gantt(df_dia),
        use_container_width=True,
        key="dash_gantt",
    )

    st.divider()

    # ── Ranking ───────────────────────────────────────────────────────────────
    st.subheader("🏆 Ranking de Aderência Produtiva")
    fig_rank, df_rank = _ranking(df_dia)
    st.plotly_chart(fig_rank, use_container_width=True, key="dash_ranking")
    with st.expander("📋 Ver tabela completa"):
        st.dataframe(df_rank, use_container_width=True)

    st.divider()

    # ── Alertas ───────────────────────────────────────────────────────────────
    st.subheader(f"⚠️ Alertas: pausas/ausências ≥ {limite_alerta} min")
    df_al = _alertas(df_dia, limite_alerta)
    if df_al.empty:
        st.success("Nenhuma pausa/ausência prolongada detectada.")
    else:
        st.warning(f"{len(df_al)} ocorrência(s) detectada(s).")
        st.dataframe(df_al, use_container_width=True)

    st.divider()

    # ── Evolução histórica ────────────────────────────────────────────────────
    st.subheader("📅 Evolução Histórica")
    fig_hist = _historico_linha(df_hist)
    if fig_hist:
        st.plotly_chart(fig_hist, use_container_width=True, key="dash_historico")
    else:
        st.info("Suba mais dias para ver a evolução histórica.")

    st.divider()

    # ── Export ────────────────────────────────────────────────────────────────
    st.subheader("💾 Exportar Dados")
    c_e1, c_e2 = st.columns(2)
    c_e1.download_button(
        "⬇️ Dia selecionado (XLSX)",
        data=_to_xlsx(df_dia),
        file_name=f"status_{data_sel}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="dash_exp_dia",
    )
    c_e2.download_button(
        "⬇️ Histórico completo (XLSX)",
        data=_to_xlsx(df_hist),
        file_name="historico_status_agentes.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="dash_exp_hist",
    )
