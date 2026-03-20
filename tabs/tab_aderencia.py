# tabs/tab_aderencia.py
import io
import json
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from config import PALETA_STATUS, ESTADOS_PRODUTIVOS, DIAS_SEMANA_ORDEM
from utils.storage import carregar_escala

# ─── CONSTANTES (para gráficos) ───────────────────────────────────────────────
_TICK_VALS = list(range(0, 1441, 60))
_TICK_TEXT = [f"{v // 60:02d}:00" for v in _TICK_VALS]

# ─── HELPER XLSX ──────────────────────────────────────────────────────────────

def df_to_xlsx(df: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()


# ─── UTILIDADES ───────────────────────────────────────────────────────────────

def _hhmm_para_min(hhmm: str) -> int:
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m

def _min_para_hhmm(total_min: int) -> str:
    h = total_min // 60
    m = total_min % 60
    return f"{h:02d}:{m:02d}"

def calcular_aderencia(df_hist: pd.DataFrame, df_escala: pd.DataFrame) -> pd.DataFrame:
    if df_hist.empty or df_escala.empty:
        return pd.DataFrame()

    df_aderencia = []

    for (agente, data), df_ag_dia in df_hist.groupby(["agente", "data"]):
        dia_semana_num = data.dayofweek
        escala_ag = df_escala[
            (df_escala["agente"] == agente) &
            (df_escala["dia_semana_num"] == dia_semana_num)
        ]

        if escala_ag.empty:
            continue # Sem escala para este agente/dia

        escala = escala_ag.iloc[0]
        turno_inicio_min = _hhmm_para_min(escala["turno_inicio"])
        turno_fim_min    = _hhmm_para_min(escala["turno_fim"])

        # Ajustar turno se passar da meia-noite (ex: 22:00-06:00)
        if turno_fim_min < turno_inicio_min:
            turno_fim_min += 1440 # Adiciona 24h em minutos

        # Calcular minutos produtivos dentro do turno
        minutos_produtivos_reais = 0
        for _, row_hist in df_ag_dia.iterrows():
            estado_min = _hhmm_para_min(row_hist["inicio"].strftime("%H:%M"))
            estado_max = _hhmm_para_min(row_hist["fim"].strftime("%H:%M"))
            if estado_max < estado_min: # Evento que passou da meia-noite
                estado_max += 1440

            # Intersecção do estado com o turno
            overlap_inicio = max(turno_inicio_min, estado_min)
            overlap_fim    = min(turno_fim_min, estado_max)

            if overlap_fim > overlap_inicio and row_hist["estado"] in ESTADOS_PRODUTIVOS:
                minutos_produtivos_reais += (overlap_fim - overlap_inicio)

        # Calcular minutos de intervalos planejados dentro do turno
        minutos_intervalos_planejados = 0
        intervalos = json.loads(escala["intervalos_json"])
        for intervalo in intervalos:
            int_inicio_min = _hhmm_para_min(intervalo["inicio"])
            int_fim_min    = _hhmm_para_min(intervalo["fim"])
            if int_fim_min < int_inicio_min: # Intervalo que passa da meia-noite
                int_fim_min += 1440

            # Intersecção do intervalo com o turno
            overlap_inicio = max(turno_inicio_min, int_inicio_min)
            overlap_fim    = min(turno_fim_min, int_fim_min)

            if overlap_fim > overlap_inicio:
                minutos_intervalos_planejados += (overlap_fim - overlap_inicio)

        # Minutos totais do turno (descontando intervalos)
        minutos_turno_planejado = (turno_fim_min - turno_inicio_min) - minutos_intervalos_planejados
        if minutos_turno_planejado < 0:
            minutos_turno_planejado = 0 # Evita valores negativos

        pct_aderencia = (
            (minutos_produtivos_reais / minutos_turno_planejado * 100)
            if minutos_turno_planejado > 0 else 0
        )

        df_aderencia.append({
            "Agente": agente,
            "Data": data,
            "Dia Semana": escala["dia_semana"],
            "Turno Início": escala["turno_inicio"],
            "Turno Fim": escala["turno_fim"],
            "Minutos Produtivos Reais": round(minutos_produtivos_reais, 1),
            "Minutos Turno Planejado": round(minutos_turno_planejado, 1),
            "% Aderência": round(pct_aderencia, 1),
        })

    return pd.DataFrame(df_aderencia)


# ─── GANTT DE ADERÊNCIA ───────────────────────────────────────────────────────

def _gantt_aderencia(
    df_hist: pd.DataFrame,
    df_escala: pd.DataFrame,
    agente_sel: str,
    data_sel: pd.Timestamp,
) -> go.Figure:
    fig = go.Figure(layout=go.Layout(template="plotly_white"))

    # 1. Desenhar o turno planejado e intervalos
    escala_ag_dia = df_escala[
        (df_escala["agente"] == agente_sel) &
        (df_escala["dia_semana_num"] == data_sel.dayofweek)
    ]

    if not escala_ag_dia.empty:
        escala = escala_ag_dia.iloc[0]
        turno_inicio_min = _hhmm_para_min(escala["turno_inicio"])
        turno_fim_min    = _hhmm_para_min(escala["turno_fim"])
        if turno_fim_min < turno_inicio_min:
            turno_fim_min += 1440 # Para turnos que atravessam a meia-noite

        # Turno total
        fig.add_trace(go.Bar(
            x=[turno_fim_min - turno_inicio_min],
            y=["Turno Planejado"],
            base=[turno_inicio_min],
            orientation="h",
            marker=dict(color="#d4edda", line=dict(width=0)), # Verde claro
            name="Turno Planejado",
            legendgroup="Turno Planejado",
            showlegend=True,
            hovertemplate=(
                f"<b>Turno Planejado</b><br>"
                f"Início: {escala['turno_inicio']}<br>"
                f"Fim: {escala['turno_fim']}<br>"
                f"Duração: {turno_fim_min - turno_inicio_min:.0f} min<extra></extra>"
            ),
        ))

        # Intervalos planejados
        intervalos = json.loads(escala["intervalos_json"])
        for i, intervalo in enumerate(intervalos):
            int_inicio_min = _hhmm_para_min(intervalo["inicio"])
            int_fim_min    = _hhmm_para_min(intervalo["fim"])
            if int_fim_min < int_inicio_min:
                int_fim_min += 1440

            # Apenas se o intervalo estiver dentro do turno planejado
            overlap_inicio = max(turno_inicio_min, int_inicio_min)
            overlap_fim    = min(turno_fim_min, int_fim_min)

            if overlap_fim > overlap_inicio:
                fig.add_trace(go.Bar(
                    x=[overlap_fim - overlap_inicio],
                    y=["Turno Planejado"],
                    base=[overlap_inicio],
                    orientation="h",
                    marker=dict(color="#f8d7da", line=dict(width=0)), # Vermelho claro
                    name=f"Intervalo: {intervalo['nome']}",
                    legendgroup="Intervalos Planejados",
                    showlegend=(i == 0), # Mostrar legenda só uma vez para intervalos
                    hovertemplate=(
                        f"<b>Intervalo Planejado: {intervalo['nome']}</b><br>"
                        f"Início: {intervalo['inicio']}<br>"
                        f"Fim: {intervalo['fim']}<br>"
                        f"Duração: {overlap_fim - overlap_inicio:.0f} min<extra></extra>"
                    ),
                ))

    # 2. Desenhar o status real do agente
    df_ag_dia = df_hist[
        (df_hist["agente"] == agente_sel) &
        (df_hist["data"] == data_sel)
    ].copy()

    estados_vis = set()
    for _, row in df_ag_dia.iterrows():
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
            y=["Status Real"],
            base=[base],
            orientation="h",
            marker=dict(color=cor, line=dict(width=0)),
            name=estado,
            legendgroup=estado,
            showlegend=show,
            hovertemplate=(
                f"<b>{agente_sel}</b><br>"
                f"Status: {estado}<br>"
                f"Início: {ini.strftime('%H:%M')}<br>"
                f"Fim: {fim.strftime('%H:%M')}<br>"
                f"Duração: {dur:.1f} min<extra></extra>"
            ),
        ))

    fig.update_layout(
        barmode="overlay",
        height=250,
        title=dict(
            text=f"Timeline de Aderência para {agente_sel} em {data_sel.strftime('%d/%m/%Y')}",
            font=dict(color="#111111"),
        ),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        font=dict(color="#111111", size=12),
        xaxis=dict(
            title=dict(text="Hora do dia", font=dict(color="#111111")),
            tickvals=_TICK_VALS, # Definido no topo do arquivo
            ticktext=_TICK_TEXT, # Definido no topo do arquivo
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
            categoryorder="array", # Garante a ordem das categorias
            categoryarray=["Status Real", "Turno Planejado"],
        ),
        legend=dict(
            title=dict(text="Status", font=dict(color="#111111")),
            font=dict(color="#111111"),
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="#cccccc",
            borderwidth=1,
        ),
        margin=dict(l=140, r=20, t=60, b=50),
    )
    return fig


# ─── RANKING DE ADERÊNCIA ─────────────────────────────────────────────────────

def _ranking_aderencia(df_ad: pd.DataFrame):
    if df_ad.empty:
        return go.Figure(layout=go.Layout(template="plotly_white")), pd.DataFrame()

    df_rank = (
        df_ad.groupby("Agente")["% Aderência"]
        .mean().reset_index()
        .sort_values("% Aderência", ascending=False)
    )

    fig = px.bar(
        df_rank,
        x="Agente",
        y="% Aderência",
        color="% Aderência",
        color_continuous_scale="RdYlGn",
        range_color=[0, 100],
        text="% Aderência",
        title="Aderência Média (%) por Agente",
        template="plotly_white",
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(
        coloraxis_showscale=False,
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        font=dict(color="#111111"),
        yaxis_range=[0, 110],
        title_font=dict(color="#111111"),
        xaxis_title_font=dict(color="#111111"),
        yaxis_title_font=dict(color="#111111"),
        xaxis_tickfont=dict(color="#111111"),
        yaxis_tickfont=dict(color="#111111"),
    )
    return fig, df_rank


# ─── RENDERIZAÇÃO DA ABA ──────────────────────────────────────────────────────

def render(df_hist: pd.DataFrame):
    st.header("🎯 Aderência à Escala")

    df_escala = carregar_escala()

    if df_hist.empty:
        st.info("Faça o upload de um relatório na barra lateral para começar.")
        return
    if df_escala.empty:
        st.info("Cadastre as escalas dos agentes na aba 'Configurar Escala'.")
        return

    df_ad = calcular_aderencia(df_hist, df_escala)

    if df_ad.empty:
        st.warning("Não foi possível calcular a aderência. Verifique se há dados históricos e escalas cadastradas para os mesmos agentes/dias.")
        return

    # ── Filtros ───────────────────────────────────────────────────────────────
    col_f1, col_f2, col_f3 = st.columns([1, 1, 2])
    with col_f1:
        agentes_aderencia = sorted(df_ad["Agente"].unique())
        ag_sel_ader = st.multiselect(
            "👤 Agentes",
            options=agentes_aderencia,
            default=agentes_aderencia,
            key="ader_agentes_sel",
        )
    with col_f2:
        meta = st.slider(
            "🎯 Meta de Aderência (%)",
            min_value=0, max_value=100, value=80, step=5,
            key="ader_meta_slider",
        )
    with col_f3:
        datas_aderencia = sorted(df_ad["Data"].unique(), reverse=True)
        periodo = st.date_input(
            "🗓️ Período",
            value=(
                datas_aderencia[-1] if len(datas_aderencia) > 1 else datas_aderencia[0],
                datas_aderencia[0]
            ),
            min_value=datas_aderencia[-1],
            max_value=datas_aderencia[0],
            key="ader_periodo",
        )
        if len(periodo) == 2:
            data_inicio, data_fim = periodo
        else:
            data_inicio, data_fim = periodo[0], periodo[0]

    df_ad_filtrado = df_ad[
        (df_ad["Agente"].isin(ag_sel_ader)) &
        (df_ad["Data"] >= pd.Timestamp(data_inicio)) &
        (df_ad["Data"] <= pd.Timestamp(data_fim))
    ]

    if df_ad_filtrado.empty:
        st.info("Nenhum dado de aderência para os filtros selecionados.")
        return

    # ── KPIs de Aderência ─────────────────────────────────────────────────────
    media_aderencia = df_ad_filtrado["% Aderência"].mean()
    col_k1, col_k2, col_k3 = st.columns(3)
    col_k1.metric(
        "📊 Aderência Média",
        f"{media_aderencia:.1f}%",
        delta=f"{media_aderencia - meta:.1f}% vs Meta",
        delta_color="normal" if media_aderencia >= meta else "inverse",
    )
    col_k2.metric(
        "⬆️ Maior Aderência",
        f"{df_ad_filtrado['% Aderência'].max():.1f}%",
    )
    col_k3.metric(
        "⬇️ Menor Aderência",
        f"{df_ad_filtrado['% Aderência'].min():.1f}%",
    )

    st.divider()

    # ── Gantt de Aderência por Agente/Dia ─────────────────────────────────────
    st.subheader("⏱️ Timeline de Aderência Detalhada")
    col_g1, col_g2 = st.columns([1, 1])
    with col_g1:
        ag_gantt = st.selectbox(
            "👤 Agente para detalhe",
            options=ag_sel_ader,
            key="ader_gantt_agente",
        )
    with col_g2:
        datas_ag_gantt = sorted(
            df_ad_filtrado[df_ad_filtrado["Agente"] == ag_gantt]["Data"].unique(),
            reverse=True,
        )
        dt_gantt = st.selectbox(
            "🗓️ Data para detalhe",
            datas_ag_gantt,
            format_func=lambda d: pd.Timestamp(d).strftime("%d/%m/%Y"),
            key="ader_gantt_data",
        )

    fig_gantt = _gantt_aderencia(df_hist, df_escala, ag_gantt, pd.Timestamp(dt_gantt))
    if len(fig_gantt.data) == 0:
        st.info("Não há escala ou status para essa combinação de agente/data.")
    else:
        st.plotly_chart(fig_gantt, use_container_width=True, key="ader_fig_gantt")

    st.divider()

    # ── Ranking ───────────────────────────────────────────────────────────────
    st.subheader("🏆 Ranking de Aderência Média")
    fig_rank, df_rank = _ranking_aderencia(df_ad_filtrado)
    st.plotly_chart(fig_rank, use_container_width=True, key="ader_fig_rank")
    with st.expander("📋 Ver tabela completa"):
        st.dataframe(df_rank, use_container_width=True)

    st.divider()

    # ── Evolução ──────────────────────────────────────────────────────────────
    st.subheader("📈 Evolução da Aderência")

    df_ev = (
        df_ad_filtrado.groupby(["Data", "Agente"])["% Aderência"]
        .mean().reset_index()
        .sort_values("Data")
    )
    fig_ev = px.line(
        df_ev, x="Data", y="% Aderência",
        color="Agente", markers=True,
        title="Evolução da Aderência ao longo do tempo",
        template="plotly_white",
    )
    fig_ev.add_hline(
        y=meta, line_dash="dash",
        line_color="red", annotation_text=f"Meta {meta}%",
    )
    fig_ev.update_layout(
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        font=dict(color="#111111", size=12),
        yaxis_range=[0, 115],
        title_font=dict(color="#111111"),
        xaxis_title_font=dict(color="#111111"),
        yaxis_title_font=dict(color="#111111"),
        legend_font=dict(color="#111111"),
        xaxis_tickfont=dict(color="#111111"),
        yaxis_tickfont=dict(color="#111111"),
    )
    st.plotly_chart(fig_ev, use_container_width=True, key="ader_fig_ev")

    st.divider()

    # ── Heatmap ───────────────────────────────────────────────────────────────
    st.subheader("🗓️ Heatmap por Dia da Semana")

    df_heat  = (
        df_ad_filtrado.groupby(["Agente", "Dia Semana"])["% Aderência"]
        .mean().reset_index()
    )
    df_pivot = df_heat.pivot(
        index="Agente", columns="Dia Semana", values="% Aderência"
    )
    dias_ok  = [d for d in DIAS_SEMANA_ORDEM if d in df_pivot.columns]
    df_pivot = df_pivot[dias_ok]

    fig_heat = go.Figure(
        data=go.Heatmap(
            z=df_pivot.values,
            x=df_pivot.columns.tolist(),
            y=df_pivot.index.tolist(),
            colorscale="RdYlGn",
            zmin=0, zmax=100,
            text=df_pivot.values.round(1),
            texttemplate="%{text:.1f}%",
            hovertemplate=(
                "Agente: %{y}<br>"
                "Dia: %{x}<br>"
                "Aderência: %{z:.1f}%<extra></extra>"
            ),
        )
    )
    fig_heat.update_layout(
        title=dict(
            text="Aderência Média (%) por Agente × Dia da Semana",
            font=dict(color="#111111"),
        ),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        font=dict(color="#111111", size=12),
        xaxis=dict(
            tickfont=dict(color="#111111"),
            title=dict(text="Dia da Semana", font=dict(color="#111111")),
        ),
        yaxis=dict(
            tickfont=dict(color="#111111"),
            title=dict(text="Agente", font=dict(color="#111111")),
        ),
    )
    st.plotly_chart(fig_heat, use_container_width=True, key="ader_fig_heat")

    st.divider()

    # ── Tabela detalhada ──────────────────────────────────────────────────────
    st.subheader("📋 Detalhamento por Dia e Agente")

    df_exib = df_ad_filtrado.copy()
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
        data=df_to_xlsx(df_exib),
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
