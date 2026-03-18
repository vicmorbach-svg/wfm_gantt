# tabs/tab_aderencia.py
import io
import json
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from config import PALETA_STATUS
from utils.storage import carregar_escala
from config import ESTADOS_PRODUTIVOS, DIAS_SEMANA_ORDEM


# ─── HELPER XLSX ──────────────────────────────────────────────────────────────

def df_to_xlsx(df: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()


# ─── UTILIDADES ───────────────────────────────────────────────────────────────

def _hhmm_para_min(hhmm: str) -> int:
    """Converte string HH:MM em minutos desde meia-noite."""
    try:
        h, m = hhmm.strip().split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return 0

# ___ GANTT ADERÊNCIA __________

def gantt_aderencia(df_hist, df_escala, agente, data):
    """
    Monta um Gantt com:
      - linha do turno planejado
      - blocos de status reais no dia
    para um agente específico.
    """
    data = pd.to_datetime(data).date()

    # escala do agente para o dia da semana correspondente
    dia_semana = pd.Timestamp(data).dayofweek  # 0=Seg
    esc = df_escala[
        (df_escala["agente"] == agente) &
        (df_escala["dia_semana_num"] == dia_semana)
    ]
    if esc.empty:
        return go.Figure()

    esc = esc.iloc[0]
    turno_ini_str = esc["turno_inicio"]
    turno_fim_str = esc["turno_fim"]

    t_ini_min = int(turno_ini_str.split(":")[0]) * 60 + int(turno_ini_str.split(":")[1])
    t_fim_min = int(turno_fim_str.split(":")[0]) * 60 + int(turno_fim_str.split(":")[1])

    # histórico real
    df_dia = df_hist[
        (df_hist["agente"] == agente) &
        (df_hist["data"]   == data)
    ].copy()
    if df_dia.empty:
        return go.Figure()

    # converte início/fim para minutos desde meia-noite
    df_dia["ini_min"] = (
        df_dia["inicio"].dt.hour * 60 + df_dia["inicio"].dt.minute
    )
    df_dia["fim_min"] = (
        df_dia["fim"].dt.hour * 60 + df_dia["fim"].dt.minute
    )

    fig = go.Figure()

    # 1) Turno planejado (faixa cinza de fundo)
    fig.add_trace(go.Bar(
        x=[t_fim_min - t_ini_min],
        y=["Turno planejado"],
        base=[t_ini_min],
        orientation="h",
        marker_color="#eeeeee",
        name="Turno planejado",
        hovertemplate=(
            f"Turno: {turno_ini_str} – {turno_fim_str}<extra></extra>"
        ),
    ))

    # 2) Status reais
    estados_vistos = set()
    for _, row in df_dia.iterrows():
        if row["fim_min"] <= row["ini_min"]:
            continue
        cor = PALETA_STATUS.get(row["estado"], "#bdc3c7")
        show_leg = row["estado"] not in estados_vistos
        estados_vistos.add(row["estado"])

        fig.add_trace(go.Bar(
            x=[row["fim_min"] - row["ini_min"]],
            y=["Status real"],
            base=[row["ini_min"]],
            orientation="h",
            marker_color=cor,
            name=row["estado"],
            legendgroup=row["estado"],
            showlegend=show_leg,
            hovertemplate=(
                f"Status: {row['estado']}<br>"
                f"Início: {row['inicio'].strftime('%H:%M')}<br>"
                f"Fim: {row['fim'].strftime('%H:%M')}<br>"
                f"Duração: {row['minutos']:.1f} min<extra></extra>"
            ),
        ))

    # layout
    tick_vals = list(range(0, 1441, 60))
    tick_text = [f"{v//60:02d}:00" for v in tick_vals]

    fig.update_layout(
        barmode="overlay",
        height=220,
        title=f"Gantt Escala x Status – {agente} ({data.strftime('%d/%m/%Y')})",
        xaxis=dict(
            title="Hora",
            tickvals=tick_vals,
            ticktext=tick_text,
            range=[0, 1440],
            color="#111111",
            gridcolor="#e0e0e0",
        ),
        yaxis=dict(
            title="",
            color="#111111",
        ),
        legend=dict(
            title="Status",
            font=dict(color="#111111"),
        ),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
    )
    return fig

# ─── CÁLCULO DE ADERÊNCIA ─────────────────────────────────────────────────────

def _calcular_aderencia(
    df_hist: pd.DataFrame,
    df_escala: pd.DataFrame,
) -> pd.DataFrame:
    """
    Para cada linha da escala (agente + dia da semana),
    cruza com os dias do histórico que batem com aquele dia da semana
    e calcula o % do turno efetivo em que o agente ficou em estado produtivo.
    """
    if df_hist.empty or df_escala.empty:
        return pd.DataFrame()

    resultados = []

    for _, esc in df_escala.iterrows():
        agente    = esc["agente"]
        dia_num   = int(esc["dia_semana_num"])   # 0=Seg … 6=Dom
        t_ini_min = _hhmm_para_min(esc["turno_inicio"])
        t_fim_min = _hhmm_para_min(esc["turno_fim"])
        turno_tot = t_fim_min - t_ini_min

        if turno_tot <= 0:
            continue

        # Desconta intervalos planejados do turno esperado
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

        # Filtra apenas o agente no histórico
        df_ag = df_hist[df_hist["agente"] == agente].copy()
        if df_ag.empty:
            continue

        # Dias do histórico que correspondem ao dia da semana da escala
        datas_ag = df_ag[
            df_ag["inicio"].dt.dayofweek == dia_num
        ]["data"].unique()

        for data_dia in datas_ag:
            df_dia   = df_ag[df_ag["data"] == data_dia].copy()
            data_ref = pd.Timestamp(data_dia)
            t_ini_dt = data_ref + pd.Timedelta(minutes=t_ini_min)
            t_fim_dt = data_ref + pd.Timedelta(minutes=t_fim_min)

            # Apenas registros produtivos que tocam o intervalo do turno
            df_prod = df_dia[
                (df_dia["estado"].isin(ESTADOS_PRODUTIVOS)) &
                (df_dia["fim"]    > t_ini_dt) &
                (df_dia["inicio"] < t_fim_dt)
            ].copy()

            # Soma o tempo produtivo clipado dentro do turno
            tempo_prod = 0.0
            for _, row in df_prod.iterrows():
                ini         = max(row["inicio"], t_ini_dt)
                fim         = min(row["fim"],    t_fim_dt)
                tempo_prod += (fim - ini).total_seconds() / 60

            pct = min(round(tempo_prod / turno_esperado * 100, 1), 100.0)

            resultados.append({
                "Data":                   data_dia,
                "Agente":                 agente,
                "Dia Semana":             DIAS_SEMANA_ORDEM[dia_num],
                "Turno":                  f"{esc['turno_inicio']} – {esc['turno_fim']}",
                "Turno Esperado (min)":   round(turno_esperado, 1),
                "Produtivo Real (min)":   round(tempo_prod, 1),
                "% Aderência":            pct,
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
        st.warning(
            "Faça upload de um relatório do Zendesk "
            "para calcular a aderência."
        )
        return

    # ── Filtros ───────────────────────────────────────────────────────────────
    agentes_disp = sorted(df_hist["agente"].unique().tolist())
    datas_disp   = sorted(df_hist["data"].unique())

    col_f1, col_f2, col_f3 = st.columns([2, 1, 1])

    with col_f1:
        agentes_sel = st.multiselect(
            "👤 Agentes",
            agentes_disp,
            default=agentes_disp,
            key="ader_agentes_sel",          # ← key único
        )

    with col_f2:
        meta = st.slider(
            "🎯 Meta de aderência (%)",
            min_value=50,
            max_value=100,
            value=80,
            step=5,
            key="ader_meta_slider",          # ← key único
        )

    with col_f3:
        if len(datas_disp) >= 2:
            data_min = pd.Timestamp(min(datas_disp)).date()
            data_max = pd.Timestamp(max(datas_disp)).date()
            periodo  = st.date_input(
                "📅 Período",
                value=(data_min, data_max),
                min_value=data_min,
                max_value=data_max,
                key="ader_periodo",          # ← key único
            )
        elif len(datas_disp) == 1:
            d = pd.Timestamp(datas_disp[0]).date()
            periodo = (d, d)
            st.info(f"Apenas 1 data disponível: {d.strftime('%d/%m/%Y')}")
        else:
            periodo = None

    # ── Calcular ──────────────────────────────────────────────────────────────
    df_hist_fil = df_hist[df_hist["agente"].isin(agentes_sel)]
    df_ad       = _calcular_aderencia(df_hist_fil, df_escala)

    if df_ad.empty:
        st.info(
            "Nenhum dado cruzado encontrado. "
            "Verifique se os dias do histórico coincidem "
            "com os dias cadastrados na escala."
        )
        return

    # Filtro de período
    if periodo and len(periodo) == 2:
        d_ini = pd.Timestamp(periodo[0])
        d_fim = pd.Timestamp(periodo[1])
        df_ad = df_ad[
            (df_ad["Data"] >= d_ini) &
            (df_ad["Data"] <= d_fim)
        ]

    if df_ad.empty:
        st.warning("Sem dados no período selecionado.")
        return

    # ── KPIs ──────────────────────────────────────────────────────────────────
    media_geral = df_ad["% Aderência"].mean()
    dias_ok     = int((df_ad["% Aderência"] >= meta).sum())
    dias_nok    = int((df_ad["% Aderência"] <  meta).sum())

    k1, k2, k3 = st.columns(3)
    k1.metric("📊 Aderência Média",      f"{media_geral:.1f}%")
    k2.metric("✅ Dias acima da meta",   str(dias_ok))
    k3.metric("⚠️ Dias abaixo da meta", str(dias_nok))

    st.divider()

    # depois dos KPIs e antes/after dos gráficos de barra/linha

st.divider()
st.subheader("🗓️ Gantt Escala x Status (por agente/dia)")

# opções disponíveis conforme o que já foi calculado em df_ad
agentes_gantt = sorted(df_ad["Agente"].unique())
datas_gantt   = sorted(df_ad["Data"].dt.date.unique())

col_g1, col_g2 = st.columns(2)
with col_g1:
    ag_gantt = st.selectbox("Agente", agentes_gantt, key="ader_gantt_agente")
with col_g2:
    data_gantt = st.selectbox(
        "Data",
        datas_gantt,
        format_func=lambda d: d.strftime("%d/%m/%Y"),
        key="ader_gantt_data",
    )

fig_gantt = gantt_aderencia(df_hist, df_escala, ag_gantt, data_gantt)
if len(fig_gantt.data) == 0:
    st.info("Não há escala ou status para essa combinação de agente/data.")
else:
    st.plotly_chart(fig_gantt, use_container_width=True)
    
    # ── Ranking por agente ────────────────────────────────────────────────────
    st.subheader("🏆 Aderência Média por Agente")

    df_rank = (
        df_ad
        .groupby("Agente")["% Aderência"]
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
    fig_rank.update_traces(
        texttemplate="%{text:.1f}%",
        textposition="outside",
    )
    fig_rank.add_hline(
        y=meta,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Meta {meta}%",
    )
    fig_rank.update_layout(
        coloraxis_showscale=False,
        plot_bgcolor="#f8f9fa",
        yaxis_range=[0, 115],
        xaxis_tickangle=-30,
    )
    st.plotly_chart(fig_rank, use_container_width=True, key="fig_rank_ader")

    st.divider()

    # ── Evolução dia a dia ────────────────────────────────────────────────────
    st.subheader("📈 Evolução da Aderência por Dia")

    fig_ev = px.line(
        df_ad.sort_values("Data"),
        x="Data",
        y="% Aderência",
        color="Agente",
        markers=True,
        title="Aderência ao longo do tempo",
    )
    fig_ev.add_hline(
        y=meta,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Meta {meta}%",
    )
    fig_ev.update_layout(
        plot_bgcolor="#f8f9fa",
        yaxis_range=[0, 115],
    )
    st.plotly_chart(fig_ev, use_container_width=True, key="fig_ev_ader")

    st.divider()

    # ── Heatmap agente × dia da semana ───────────────────────────────────────
    st.subheader("🗓️ Heatmap de Aderência por Dia da Semana")

    df_heat = (
        df_ad
        .groupby(["Agente", "Dia Semana"])["% Aderência"]
        .mean()
        .reset_index()
    )
    df_pivot = df_heat.pivot(
        index="Agente", columns="Dia Semana", values="% Aderência"
    )

    # Reordena colunas conforme ordem da semana
    dias_presentes = [d for d in DIAS_SEMANA_ORDEM if d in df_pivot.columns]
    df_pivot       = df_pivot[dias_presentes]

    fig_heat = px.imshow(
        df_pivot,
        color_continuous_scale="RdYlGn",
        zmin=0,
        zmax=100,
        title="Aderência Média (%) por Agente e Dia da Semana",
        text_auto=".1f",
    )
    fig_heat.update_layout(
        xaxis_title="Dia da Semana",
        yaxis_title="Agente",
    )
    st.plotly_chart(fig_heat, use_container_width=True, key="fig_heat_ader")

    st.divider()

    # ── Tabela detalhada ──────────────────────────────────────────────────────
    st.subheader("📋 Detalhamento por Dia e Agente")

    def _colorir(val):
        if isinstance(val, (int, float)):
            cor = "#d4edda" if val >= meta else "#f8d7da"
            return f"background-color: {cor}"
        return ""

    df_exib = df_ad.copy()
    df_exib["Data"] = df_exib["Data"].dt.strftime("%d/%m/%Y")

    st.dataframe(
        df_exib
        .sort_values(["Data", "Agente"])
        .style.applymap(_colorir, subset=["% Aderência"]),
        use_container_width=True,
        height=420,
    )

    st.divider()

    # ── Export XLSX ───────────────────────────────────────────────────────────
    st.subheader("💾 Exportar")

    col_ex1, col_ex2 = st.columns(2)

    col_ex1.download_button(
        "⬇️ Exportar aderência detalhada (XLSX)",
        data=df_to_xlsx(df_exib),
        file_name="aderencia_detalhada.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument"
            ".spreadsheetml.sheet"
        ),
        use_container_width=True,
        key="btn_export_ader_det",
    )

    col_ex2.download_button(
        "⬇️ Exportar ranking (XLSX)",
        data=df_to_xlsx(df_rank),
        file_name="aderencia_ranking.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument"
            ".spreadsheetml.sheet"
        ),
        use_container_width=True,
        key="btn_export_ader_rank",
    )
