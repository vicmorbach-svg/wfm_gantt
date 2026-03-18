import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from config import PALETA_STATUS, ESTADOS_PRODUTIVOS, ESTADOS_PAUSA, ESTADOS_FORA
from utils.data_loader import get_agentes


# ── Funções de visualização ────────────────────────────────────────────────────

def _gantt(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    agentes = sorted(df["agente"].unique())
    estados_vistos = set()

    for agente in agentes:
        df_ag = df[df["agente"] == agente].sort_values("inicio")
        for _, row in df_ag.iterrows():
            cor    = PALETA_STATUS.get(row["estado"], "#bdc3c7")
            meia   = row["inicio"].replace(hour=0, minute=0, second=0, microsecond=0)
            base   = (row["inicio"] - meia).total_seconds() / 60
            dur    = (row["fim"]    - row["inicio"]).total_seconds() / 60
            label  = row["estado"]
            show   = label not in estados_vistos
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
                    f"Início: {row['inicio'].strftime('%H:%M')}<br>"
                    f"Fim: {row['fim'].strftime('%H:%M')}<br>"
                    f"Duração: {row.get('minutos', dur):.1f} min"
                    "<extra></extra>"
                ),
            ))

    # Marcadores de hora no eixo X
    horas   = list(range(0, 1441, 60))
    rotulos = [f"{h // 60:02d}:00" for h in horas]

    fig.update_layout(
    barmode="overlay",
    height=max(300, len(agentes) * 55 + 120),
    title="Timeline de Status por Agente",
    xaxis=dict(
        title="Hora do dia",
        tickvals=tick_vals,
        ticktext=tick_text,
        range=[0, 1440],
        showgrid=True,
        gridcolor="#e0e0e0",
        zeroline=False,
        color="#111111",        # cor do texto do eixo X
    ),
    yaxis=dict(
        title="Agente",
        automargin=True,
        color="#111111",        # cor do texto do eixo Y
    ),
    legend=dict(
        title="Status",
        font=dict(color="#111111"),
    ),
    title_font=dict(color="#111111"),
    plot_bgcolor="#ffffff",
    paper_bgcolor="#ffffff",
)
    return fig


from config import ESTADOS_PRODUTIVOS, ESTADOS_PAUSA, ESTADOS_FORA

def kpis_dia(df: pd.DataFrame) -> dict:
    # agentes que ficaram online em algum momento no dia
    agentes_com_online = df[
        df["estado"].isin(ESTADOS_PRODUTIVOS)
    ]["agente"].unique().tolist()

    if not agentes_com_online:
        # fallback: se ninguém ficou online, usa todo mundo pra não quebrar
        df_base = df.copy()
    else:
        df_base = df[df["agente"].isin(agentes_com_online)].copy()

    prod  = df_base[df_base["estado"].isin(ESTADOS_PRODUTIVOS)]["minutos"].sum()
    pausa = df_base[df_base["estado"].isin(ESTADOS_PAUSA)]["minutos"].sum()
    fora  = df_base[df_base["estado"].isin(ESTADOS_FORA)]["minutos"].sum()

    total = prod + pausa + fora
    if total == 0:
        total = 1  # evita divisão por zero

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
        pct   = round(prod / total * 100, 1) if total > 0 else 0.0
        rows.append({
            "Agente": ag,
            "Produtivo (min)": round(prod, 1),
            "Pausa (min)":     round(pausa, 1),
            "Fora (min)":      round(fora, 1),
            "Total (min)":     round(total, 1),
            "% Produtivo":     pct,
        })

    df_rank = pd.DataFrame(rows).sort_values("% Produtivo", ascending=False)

    fig = px.bar(
        df_rank,
        x="Agente",
        y="% Produtivo",
        color="% Produtivo",
        color_continuous_scale="RdYlGn",
        range_color=[0, 100],
        text="% Produtivo",
        title="% Tempo Produtivo por Agente",
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(
        coloraxis_showscale=False,
        plot_bgcolor="#f8f9fa",
        yaxis_range=[0, 110],
    )
    return fig, df_rank


def _alertas(df: pd.DataFrame, limite: int) -> pd.DataFrame:
    rows = []
    for ag in df["agente"].unique():
        d = df[
            (df["agente"] == ag) &
            (df["estado"].isin(ESTADOS_PAUSA + ESTADOS_FORA))
        ]
        for _, r in d.iterrows():
            if r.get("minutos", 0) >= limite:
                rows.append({
                    "Agente":        ag,
                    "Status":        r["estado"],
                    "Início":        r["inicio"].strftime("%H:%M"),
                    "Fim":           r["fim"].strftime("%H:%M"),
                    "Duração (min)": round(r["minutos"], 1),
                })
    return pd.DataFrame(rows)


def _historico_linha(df_hist: pd.DataFrame) -> go.Figure | None:
    if df_hist.empty:
        return None

    rows = []
    for ag in df_hist["agente"].unique():
        for dt in df_hist["data"].unique():
            d = df_hist[(df_hist["agente"] == ag) & (df_hist["data"] == dt)]
            prod  = d[d["estado"].isin(ESTADOS_PRODUTIVOS)]["minutos"].sum()
            total = d["minutos"].sum()
            pct   = round(prod / total * 100, 1) if total > 0 else 0.0
            rows.append({"Agente": ag, "Data": dt, "% Produtivo": pct})

    df_ev = pd.DataFrame(rows).sort_values("Data")
    if df_ev.empty:
        return None

    fig = px.line(
        df_ev, x="Data", y="% Produtivo",
        color="Agente", markers=True,
        title="Evolução Histórica – % Tempo Produtivo",
    )
    fig.add_hline(y=80, line_dash="dash", line_color="red",
                  annotation_text="Meta 80%")
    fig.update_layout(plot_bgcolor="#f8f9fa", yaxis_range=[0, 110])
    return fig


# ── Renderização da aba ────────────────────────────────────────────────────────

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
            "📅 Data",
            datas,
            format_func=lambda d: (
                d.strftime("%d/%m/%Y") if hasattr(d, "strftime") else str(d)
            ),
        )
    with col_f2:
        agentes_sel = st.multiselect(
            "👤 Agentes", agentes_disp, default=agentes_disp
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
    c1.metric("🟢 Produtivo",      f"{k['pct_prod']:.1f}%",  f"{k['prod_min']:.0f} min")
    c2.metric("🟡 Em Pausa",       f"{k['pct_pausa']:.1f}%", f"{k['pausa_min']:.0f} min")
    c3.metric("🔴 Fora/Offline",   f"{k['pct_fora']:.1f}%",  f"{k['fora_min']:.0f} min")
    c4.metric("⏱️ Total Registrado", f"{k['total_min']:.0f} min")

    st.divider()

    # ── Gantt ─────────────────────────────────────────────────────────────────
    st.subheader("📈 Timeline de Status")
    st.plotly_chart(_gantt(df_dia), use_container_width=True)

    st.divider()

    # ── Ranking ───────────────────────────────────────────────────────────────
    st.subheader("🏆 Ranking de Aderência Produtiva")
    fig_rank, df_rank = _ranking(df_dia)
    st.plotly_chart(fig_rank, use_container_width=True)
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
        st.plotly_chart(fig_hist, use_container_width=True)
    else:
        st.info("Suba mais dias para ver a evolução histórica.")

    st.divider()

    # ── Export ────────────────────────────────────────────────────────────────
    st.subheader("💾 Exportar Dados")
    c_e1, c_e2 = st.columns(2)
    c_e1.download_button(
        "⬇️ Dia selecionado (CSV)",
        data=df_dia.to_csv(index=False).encode("utf-8"),
        file_name=f"status_{data_sel}.csv",
        mime="text/csv",
    )
    c_e2.download_button(
        "⬇️ Histórico completo (CSV)",
        data=df_hist.to_csv(index=False).encode("utf-8"),
        file_name="historico_status_agentes.csv",
        mime="text/csv",
    )
