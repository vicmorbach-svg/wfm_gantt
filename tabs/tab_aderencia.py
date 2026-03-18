import io
import json
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.storage import carregar_escala
from config import (
    PALETA_STATUS, ESTADOS_PRODUTIVOS, DIAS_SEMANA_ORDEM,
)


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _to_xlsx(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False)
    return buf.getvalue()


def _hhmm_para_min(hhmm: str) -> int:
    try:
        h, m = str(hhmm).strip().split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return 0


_LAYOUT_BASE = dict(
    template="plotly_white",
    plot_bgcolor="#ffffff",
    paper_bgcolor="#ffffff",
    font=dict(color="#111111", size=12),
)

_TICK_VALS = list(range(0, 1441, 60))
_TICK_TEXT = [f"{v // 60:02d}:00" for v in _TICK_VALS]


# ─── GANTT ESCALA x STATUS ────────────────────────────────────────────────────

def _gantt_aderencia(
    df_hist: pd.DataFrame,
    df_escala: pd.DataFrame,
    agente: str,
    data,
) -> go.Figure:
    """
    Duas linhas no Gantt:
      • 'Turno planejado' — faixa cinza do horário da escala
      • 'Status real'     — blocos coloridos dos estados reais
    """
    data_date = pd.Timestamp(data).date()
    dia_num   = pd.Timestamp(data_date).dayofweek  # 0=Seg

    # Escala do agente para o dia da semana
    esc_rows = df_escala[
        (df_escala["agente"] == agente) &
        (df_escala["dia_semana_num"] == dia_num)
    ]
    if esc_rows.empty:
        fig = go.Figure()
        fig.update_layout(
            title=f"Sem escala cadastrada para {agente} em "
                  f"{DIAS_SEMANA_ORDEM[dia_num]}",
            **_LAYOUT_BASE,
        )
        return fig

    esc = esc_rows.iloc[0]
    t_ini_str = esc["turno_inicio"]
    t_fim_str = esc["turno_fim"]
    t_ini_min = _hhmm_para_min(t_ini_str)
    t_fim_min = _hhmm_para_min(t_fim_str)

    # Intervalos planejados
    try:
        intervalos = json.loads(esc.get("intervalos_json", "[]"))
    except Exception:
        intervalos = []

    # Histórico do agente no dia
    df_dia = df_hist[
        (df_hist["agente"] == agente) &
        (df_hist["data"] == data_date)
    ].copy()

    fig = go.Figure()

    # ── Linha 1: Turno planejado ────────────────────────────────────────────
    fig.add_trace(go.Bar(
        x=[t_fim_min - t_ini_min],
        y=["Turno planejado"],
        base=[t_ini_min],
        orientation="h",
        marker=dict(color="#d0e8ff", line=dict(color="#4a90d9", width=2)),
        name="Turno planejado",
        hovertemplate=f"Turno: {t_ini_str} – {t_fim_str}<extra></extra>",
        showlegend=True,
    ))

    # Intervalos planejados sobre a mesma linha
    for iv in intervalos:
        iv_ini = _hhmm_para_min(iv.get("inicio", ""))
        iv_fim = _hhmm_para_min(iv.get("fim", ""))
        if iv_fim > iv_ini:
            fig.add_trace(go.Bar(
                x=[iv_fim - iv_ini],
                y=["Turno planejado"],
                base=[iv_ini],
                orientation="h",
                marker=dict(color="#f9c74f", line=dict(width=0)),
                name=iv.get("nome", "Intervalo"),
                legendgroup=iv.get("nome", "Intervalo"),
                showlegend=True,
                hovertemplate=(
                    f"Intervalo: {iv.get('nome','')}<br>"
                    f"{iv.get('inicio','')} – {iv.get('fim','')}"
                    "<extra></extra>"
                ),
            ))

    # ── Linha 2: Status reais ───────────────────────────────────────────────
    if df_dia.empty:
        fig.add_annotation(
            text="Sem dados de status para este dia",
            xref="paper", yref="paper",
            x=0.5, y=0, showarrow=False,
            font=dict(color="red"),
        )
    else:
        df_dia["ini_min"] = (
            df_dia["inicio"].dt.hour * 60 +
            df_dia["inicio"].dt.minute +
            df_dia["inicio"].dt.second / 60
        )
        df_dia["fim_min"] = (
            df_dia["fim"].dt.hour * 60 +
            df_dia["fim"].dt.minute +
            df_dia["fim"].dt.second / 60
        )

        estados_vis = set()
        for _, row in df_dia.sort_values("ini_min").iterrows():
            dur = row["fim_min"] - row["ini_min"]
            if dur <= 0:
                continue
            estado  = row["estado"]
            cor     = PALETA_STATUS.get(estado, "#aaaaaa")
            show    = estado not in estados_vis
            estados_vis.add(estado)

            fig.add_trace(go.Bar(
                x=[dur],
                y=["Status real"],
                base=[row["ini_min"]],
                orientation="h",
                marker=dict(color=cor, line=dict(width=0)),
                name=estado,
                legendgroup=estado,
                showlegend=show,
                hovertemplate=(
                    f"Status: {estado}<br>"
                    f"Início: {row['inicio'].strftime('%H:%M')}<br>"
                    f"Fim: {row['fim'].strftime('%H:%M')}<br>"
                    f"Duração: {row['minutos']:.1f} min"
                    "<extra></extra>"
                ),
            ))

    fig.update_layout(
        **_LAYOUT_BASE,
        barmode="overlay",
        height=280,
        title=dict(
            text=(
                f"Escala x Status — {agente} "
                f"({pd.Timestamp(data_date).strftime('%d/%m/%Y')})"
            ),
            font=dict(color="#111111"),
        ),
        xaxis=dict(
            title="Hora do dia",
            tickvals=_TICK_VALS,
            ticktext=_TICK_TEXT,
            range=[0, 1440],
            showgrid=True,
            gridcolor="#e5e5e5",
            tickfont=dict(color="#111111"),
            titlefont=dict(color="#111111"),
        ),
        yaxis=dict(
            tickfont=dict(color="#111111"),
            automargin=True,
        ),
        legend=dict(
            font=dict(color="#111111"),
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="#cccccc",
            borderwidth=1,
        ),
        margin=dict(l=130, r=20, t=60, b=50),
    )
    return fig


# ─── CÁLCULO DE ADERÊNCIA ─────────────────────────────────────────────────────

def _calcular_aderencia(
    df_hist: pd.DataFrame,
    df_escala: pd.DataFrame,
) -> pd.DataFrame:
    if df_hist.empty or df_escala.empty:
        return pd.DataFrame()

    resultados = []

    for _, esc in df_escala.iterrows():
        agente    = esc["agente"]
        dia_num   = int(esc["dia_semana_num"])
        t_ini_min = _hhmm_para_min(esc["turno_inicio"])
        t_fim_min = _hhmm_para_min(esc["turno_fim"])
        turno_tot = t_fim_min - t_ini_min
        if turno_tot <= 0:
            continue

        try:
            intervalos = json.loads(esc.get("intervalos_json", "[]"))
        except Exception:
            intervalos = []

        int_tot = sum(
            _hhmm_para_min(iv["fim"]) - _hhmm_para_min(iv["inicio"])
            for iv in intervalos
            if iv.get("inicio") and iv.get("fim")
        )
        turno_esperado = max(turno_tot - int_tot, 1)

        df_ag = df_hist[df_hist["agente"] == agente]
        if df_ag.empty:
            continue

        datas_ag = df_ag[
            df_ag["inicio"].dt.dayofweek == dia_num
        ]["data"].unique()

        for data_dia in datas_ag:
            df_dia   = df_ag[df_ag["data"] == data_dia].copy()
            data_ref = pd.Timestamp(data_dia)
            t_ini_dt = data_ref + pd.Timedelta(minutes=t_ini_min)
            t_fim_dt = data_ref + pd.Timedelta(minutes=t_fim_min)

            df_prod = df_dia[
                df_dia["estado"].isin(ESTADOS_PRODUTIVOS) &
                (df_dia["fim"]    > t_ini_dt) &
                (df_dia["inicio"] < t_fim_dt)
            ].copy()

            tempo_prod = 0.0
            for _, row in df_prod.iterrows():
                ini         = max(row["inicio"], t_ini_dt)
                fim         = min(row["fim"],    t_fim_dt)
                tempo_prod += (fim - ini).total_seconds() / 60

            pct = min(round(tempo_prod / turno_esperado * 100, 1), 100.0)

            resultados.append({
                "Data":                 data_dia,
                "Agente":               agente,
                "Dia Semana":           DIAS_SEMANA_ORDEM[dia_num],
                "Turno":                f"{esc['turno_inicio']} – {esc['turno_fim']}",
                "Turno Esperado (min)": round(turno_esperado, 1),
                "Produtivo Real (min)": round(tempo_prod, 1),
                "% Aderência":          pct,
            })

    if not resultados:
        return pd.DataFrame()

    df_res = pd.DataFrame(resultados)
    df_res["Data"] = pd.to_datetime(df_res["Data"])
    return df_res.sort_values(["Data", "Agente"]).reset_index(drop=True)


# ─── RENDER ───────────────────────────────────────────────────────────────────

def render(df_hist: pd.DataFrame):
    st.header("🎯 Aderência à Escala Planejada")

    df_escala = carregar_escala()

    if df_escala.empty:
        st.warning(
            "Configure a escala dos agentes na aba "
            "**📅 Configurar Escala** primeiro."
        )
        return

    if df_hist.empty:
        st.warning("Faça upload de um relatório do Zendesk para calcular a aderência.")
        return

    # ── Filtros globais ───────────────────────────────────────────────────────
    agentes_disp = sorted(df_hist["agente"].unique().tolist())
    datas_disp   = sorted(df_hist["data"].unique())

    col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
    with col_f1:
        agentes_sel = st.multiselect(
            "👤 Agentes", agentes_disp, default=agentes_disp,
            key="ader_agentes_sel",
        )
    with col_f2:
        meta = st.slider(
            "🎯 Meta (%)", 50, 100, 80, 5,
            key="ader_meta_slider",
        )
    with col_f3:
        if len(datas_disp) >= 2:
            d_min = pd.Timestamp(min(datas_disp)).date()
            d_max = pd.Timestamp(max(datas_disp)).date()
            periodo = st.date_input(
                "📅 Período", value=(d_min, d_max),
                min_value=d_min, max_value=d_max,
                key="ader_periodo",
            )
        else:
            d = pd.Timestamp(datas_disp[0]).date() if datas_disp else None
            periodo = (d, d) if d else None

    # ── Calcular ──────────────────────────────────────────────────────────────
    df_fil = df_hist[df_hist["agente"].isin(agentes_sel)]
    df_ad  = _calcular_aderencia(df_fil, df_escala)

    if df_ad.empty:
        st.info(
            "Nenhum cruzamento encontrado. "
            "Verifique se os dias cadastrados na escala existem no histórico."
        )
        return

    if periodo and len(periodo) == 2:
        df_ad = df_ad[
            (df_ad["Data"] >= pd.Timestamp(periodo[0])) &
            (df_ad["Data"] <= pd.Timestamp(periodo[1]))
        ]

    if df_ad.empty:
        st.warning("Sem dados no período selecionado.")
        return

    # ── KPIs ──────────────────────────────────────────────────────────────────
    media  = df_ad["% Aderência"].mean()
    ok     = int((df_ad["% Aderência"] >= meta).sum())
    nok    = int((df_ad["% Aderência"] <  meta).sum())

    k1, k2, k3 = st.columns(3)
    k1.metric("📊 Aderência Média",      f"{media:.1f}%")
    k2.metric("✅ Dias acima da meta",   str(ok))
    k3.metric("⚠️ Dias abaixo da meta", str(nok))

    st.divider()

    # ── Gantt Escala x Status ─────────────────────────────────────────────────
    st.subheader("🗓️ Gantt: Escala Planejada x Status Real")

    agentes_gantt = sorted(df_ad["Agente"].unique())
    datas_gantt   = sorted(df_ad["Data"].dt.date.unique())

    cg1, cg2 = st.columns(2)
    with cg1:
        ag_gantt = st.selectbox(
            "👤 Agente", agentes_gantt,
            key="ader_gantt_agente",
        )
    with cg2:
        dt_gantt = st.selectbox(
            "📅 Data", datas_gantt,
            format_func=lambda d: d.strftime("%d/%m/%Y"),
            key="ader_gantt_data",
        )

    fig_gantt = _gantt_aderencia(df_hist, df_escala, ag_gantt, dt_gantt)
    st.plotly_chart(fig_gantt, use_container_width=True, key="ader_gantt_chart")

    st.divider()

    # ── Ranking por agente ────────────────────────────────────────────────────
    st.subheader("🏆 Aderência Média por Agente")

    df_rank = (
        df_ad.groupby("Agente")["% Aderência"]
        .mean().reset_index()
        .rename(columns={"% Aderência": "Aderência Média (%)"})
        .sort_values("Aderência Média (%)", ascending=False)
    )
    df_rank["Aderência Média (%)"] = df_rank["Aderência Média (%)"].round(1)

    fig_rank = px.bar(
        df_rank, x="Agente", y="Aderência Média (%)",
        color="Aderência Média (%)",
        color_continuous_scale="RdYlGn",
        range_color=[0, 100],
        text="Aderência Média (%)",
        title="Aderência Média por Agente",
        template="plotly_white",
    )
    fig_rank.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig_rank.add_hline(
        y=meta, line_dash="dash",
        line_color="red", annotation_text=f"Meta {meta}%",
    )
    fig_rank.update_layout(
        **_LAYOUT_BASE,
        coloraxis_showscale=False,
        yaxis_range=[0, 115],
        xaxis_tickangle=-30,
    )
    st.plotly_chart(fig_rank, use_container_width=True, key="ader_fig_rank")

    st.divider()

    # ── Evolução dia a dia ────────────────────────────────────────────────────
    st.subheader("📈 Evolução da Aderência por Dia")

    fig_ev = px.line(
        df_ad.sort_values("Data"),
        x="Data", y="% Aderência",
        color="Agente", markers=True,
        title="Aderência ao longo do tempo",
        template="plotly_white",
    )
    fig_ev.add_hline(
        y=meta, line_dash="dash",
        line_color="red", annotation_text=f"Meta {meta}%",
    )
    fig_ev.update_layout(**_LAYOUT_BASE, yaxis_range=[0, 115])
    st.plotly_chart(fig_ev, use_container_width=True, key="ader_fig_ev")

    st.divider()

    # ── Heatmap ───────────────────────────────────────────────────────────────
    st.subheader("🗓️ Heatmap por Dia da Semana")

    df_heat  = (
        df_ad.groupby(["Agente", "Dia Semana"])["% Aderência"]
        .mean().reset_index()
    )
    df_pivot = df_heat.pivot(
        index="Agente", columns="Dia Semana", values="% Aderência"
    )
    dias_ok  = [d for d in DIAS_SEMANA_ORDEM if d in df_pivot.columns]
    df_pivot = df_pivot[dias_ok]

    fig_heat = px.imshow(
        df_pivot,
        color_continuous_scale="RdYlGn",
        zmin=0, zmax=100,
        text_auto=".1f",
        title="Aderência Média (%) por Agente × Dia da Semana",
        template="plotly_white",
    )
    fig_heat.update_layout(**_LAYOUT_BASE)
    st.plotly_chart(fig_heat, use_container_width=True, key="ader_fig_heat")

    st.divider()

    # ── Tabela detalhada ──────────────────────────────────────────────────────
    st.subheader("📋 Detalhamento por Dia e Agente")

    df_exib = df_ad.copy()
    df_exib["Data"] = df_exib["Data"].dt.strftime("%d/%m/%Y")

    def _color(val):
        if isinstance(val, (int, float)):
            return f"background-color: {'#d4edda' if val >= meta else '#f8d7da'}"
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
        data=_to_xlsx(df_exib),
        file_name="aderencia_detalhada.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="ader_exp_det",
    )
    ce2.download_button(
        "⬇️ Ranking (XLSX)",
        data=_to_xlsx(df_rank),
        file_name="aderencia_ranking.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="ader_exp_rank",
    )
