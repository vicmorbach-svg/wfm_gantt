import json
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date
from config import ESTADOS_PRODUTIVOS, DIAS_SEMANA_ORDEM
from utils.storage import carregar_escala


def _minutos_para_time(hhmm: str) -> int:
    """Converte 'HH:MM' em minutos desde meia-noite."""
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m


def _calcular_aderencia(df_hist: pd.DataFrame, df_escala: pd.DataFrame) -> pd.DataFrame:
    """
    Para cada agente + dia do histórico, verifica se havia escala e
    calcula % do turno planejado em que o agente ficou Online.
    """
    rows = []

    for ag in df_hist["agente"].unique():
        for dt in df_hist["data"].unique():
            # Dia da semana em português
            dia_num  = pd.Timestamp(dt).dayofweek          # 0=Seg … 6=Dom
            dia_nome = DIAS_SEMANA_ORDEM[dia_num]

            # Busca escala
            esc = df_escala[
                (df_escala["agente"]      == ag) &
                (df_escala["dia_semana"]  == dia_nome)
            ]
            if esc.empty:
                continue

            esc = esc.iloc[0]
            turno_ini_min = _minutos_para_time(esc["turno_inicio"])
            turno_fim_min = _minutos_para_time(esc["turno_fim"])
            turno_total   = turno_fim_min - turno_ini_min

            if turno_total <= 0:
                continue

            # Intervalos planejados
            try:
                intervalos = json.loads(esc["intervalos_json"])
            except Exception:
                intervalos = []

            intervalo_total = sum(
                _minutos_para_time(i["fim"]) - _minutos_para_time(i["inicio"])
                for i in intervalos
                if _minutos_para_time(i["fim"]) > _minutos_para_time(i["inicio"])
            )
            turno_efetivo = turno_total - intervalo_total

            # Filtra registros do agente no dia, dentro do turno
            df_ag = df_hist[
                (df_hist["agente"] == ag) &
                (df_hist["data"]   == dt)
            ].copy()

            # Converte início em minutos desde meia-noite
            df_ag["ini_min"] = (
                df_ag["inicio"].dt.hour * 60 + df_ag["inicio"].dt.minute
            )
            df_ag["fim_min"] = (
                df_ag["fim"].dt.hour * 60 + df_ag["fim"].dt.minute
            )

            # Clipa para o turno
            df_ag["ini_clip"] = df_ag["ini_min"].clip(lower=turno_ini_min)
            df_ag["fim_clip"] = df_ag["fim_min"].clip(upper=turno_fim_min)
            df_ag = df_ag[df_ag["fim_clip"] > df_ag["ini_clip"]]

            # Tempo Online dentro do turno
            prod_dentro = df_ag[
                df_ag["estado"].isin(ESTADOS_PRODUTIVOS)
            ].apply(
                lambda r: max(0, r["fim_clip"] - r["ini_clip"]), axis=1
            ).sum()

            pct = round(prod_dentro / turno_efetivo * 100, 1) if turno_efetivo > 0 else 0.0
            pct = min(pct, 100.0)

            # Login / Logout real
            if not df_ag.empty:
                login_real  = df_ag["inicio"].min().strftime("%H:%M")
                logout_real = df_ag["fim"].max().strftime("%H:%M")
            else:
                login_real = logout_real = "—"

            rows.append({
                "Data":             str(dt),
                "Agente":           ag,
                "Dia":              dia_nome,
                "Turno Planejado":  f"{esc['turno_inicio']}–{esc['turno_fim']}",
                "Login Real":       login_real,
                "Logout Real":      logout_real,
                "Prod. no turno (min)": round(prod_dentro, 1),
                "Turno efetivo (min)":  round(turno_efetivo, 1),
                "% Aderência":      pct,
            })

    return pd.DataFrame(rows)


def render(df_hist: pd.DataFrame):
    st.header("🎯 Aderência à Escala Planejada")

    df_escala = carregar_escala()

    if df_escala.empty:
        st.warning("Configure as escalas na aba **📅 Configurar Escala** primeiro.")
        return

    if df_hist.empty:
        st.warning("Faça o upload de um relatório do Zendesk para calcular aderência.")
        return

    # ── Filtros ────────────────────────────────────────────────────────────
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        agentes_disp = sorted(df_hist["agente"].unique().tolist())
        agentes_sel  = st.multiselect(
            "👤 Agentes", agentes_disp, default=agentes_disp
        )
    with col_f2:
        meta = st.slider("🎯 Meta de aderência (%)", 50, 100, 80, 5)

    # ── Calcular ───────────────────────────────────────────────────────────
    df_hist_fil = df_hist[df_hist["agente"].isin(agentes_sel)]
    df_ad = _calcular_aderencia(df_hist_fil, df_escala)

    if df_ad.empty:
        st.info(
            "Nenhum dado cruzado encontrado. "
            "Verifique se os dias do histórico coincidem com os dias cadastrados na escala."
        )
        return

    # ── KPIs ───────────────────────────────────────────────────────────────
    media_geral = df_ad["% Aderência"].mean()
    abaixo_meta = (df_ad["% Aderência"] < meta).sum()
    dias_ok     = (df_ad["% Aderência"] >= meta).sum()

    k1, k2, k3 = st.columns(3)
    k1.metric("📊 Aderência Média",      f"{media_geral:.1f}%")
    k2.metric("✅ Dias acima da meta",   str(dias_ok))
    k3.metric("⚠️ Dias abaixo da meta", str(abaixo_meta))

    st.divider()

    # ── Ranking por agente ─────────────────────────────────────────────────
    st.subheader("🏆 Aderência Média por Agente")
    df_rank = (
        df_ad.groupby("Agente")["% Aderência"]
        .mean()
        .reset_index()
        .rename(columns={"% Aderência": "Aderência Média (%)"})
        .sort_values("Aderência Média (%)", ascending=False)
    )
    df_rank["Aderência Média (%)"] = df_rank["Aderência Média (%)"].round(1)

    fig_rank = px.bar(
        df_rank,
        x="Agente",
        y="Aderência Média (%)",
        color="Aderência Média (%)",
        color_continuous_scale="RdYlGn",
        range_color=[0, 100],
        text="Aderência Média (%)",
        title="Aderência Média por Agente",
    )
    fig_rank.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig_rank.add_hline(
        y=meta, line_dash="dash", line_color="red",
        annotation_text=f"Meta {meta}%"
    )
    fig_rank.update_layout(coloraxis_showscale=False, plot_bgcolor="#f8f9fa")
    st.plotly_chart(fig_rank, use_container_width=True)

    st.divider()

    # ── Evolução dia a dia ─────────────────────────────────────────────────
    st.subheader("📈 Evolução da Aderência por Dia")
    fig_ev = px.line(
        df_ad.sort_values("Data"),
        x="Data", y="% Aderência",
        color="Agente", markers=True,
        title="Aderência ao longo do tempo",
    )
    fig_ev.add_hline(
        y=meta, line_dash="dash", line_color="red",
        annotation_text=f"Meta {meta}%"
    )
    fig_ev.update_layout(plot_bgcolor="#f8f9fa", yaxis_range=[0, 110])
    st.plotly_chart(fig_ev, use_container_width=True)

    st.divider()

    # ── Tabela detalhada ───────────────────────────────────────────────────
    st.subheader("📋 Detalhamento por Dia e Agente")

    def _colorir(val):
        if isinstance(val, float):
            cor = "#d4edda" if val >= meta else "#f8d7da"
            return f"background-color: {cor}"
        return ""

    st.dataframe(
        df_ad.sort_values(["Data", "Agente"]).style.applymap(
            _colorir, subset=["% Aderência"]
        ),
        use_container_width=True,
        height=400,
    )

    st.divider()

    # ── Export ─────────────────────────────────────────────────────────────
    st.download_button(
        "⬇️ Exportar Aderência (CSV)",
        data=df_ad.to_csv(index=False).encode("utf-8"),
        file_name="aderencia_escala.csv",
        mime="text/csv",
    )
