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

# ── Constantes para o Gantt ───────────────────────────────────────────────────
_TICK_VALS = list(range(0, 1441, 60)) # A cada 60 minutos (1 hora)
_TICK_TEXT = [f"{v//60:02d}:00" for v in _TICK_VALS]

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
        return go.Figure(layout=go.Layout(template="plotly_white")) # Retorna figura vazia com tema

    esc = esc.iloc[0]
    turno_ini_str = esc["turno_inicio"]
    turno_fim_str = esc["turno_fim"]

    t_ini_min = _hhmm_para_min(turno_ini_str)
    t_fim_min = _hhmm_para_min(turno_fim_str)

    # histórico real
    df_dia = df_hist[
        (df_hist["agente"] == agente) &
        (df_hist["data"]   == data)
    ].copy()
    if df_dia.empty:
        return go.Figure(layout=go.Layout(template="plotly_white")) # Retorna figura vazia com tema

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
    fig.update_layout(
        barmode="overlay",
        height=220,
        title=f"Gantt Escala x Status – {agente} ({data.strftime('%d/%m/%Y')})",
        xaxis=dict(
            title="Hora",
            tickvals=_TICK_VALS,
            ticktext=_TICK_TEXT,
            range=[0, 1440],
            tickfont=dict(color="#111111"), # Corrigido para tickfont
            title_font=dict(color="#111111"), # Corrigido para title_font
            gridcolor="#e0e0e0",
        ),
        yaxis=dict(
            title="",
            tickfont=dict(color="#111111"), # Corrigido para tickfont
            title_font=dict(color="#111111"), # Corrigido para title_font
        ),
        legend=dict(
            title="Status",
            font=dict(color="#111111"),
        ),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        font=dict(color="#111111"), # Corrigido para cor do texto
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
            key="ader_agentes_sel",
        )

    with col_f2:
        meta = st.slider(
            "🎯 Meta de aderência (%)",
            min_value=50,
            max_value=100,
            value=80,
            step=5,
            key="ader_meta_slider",
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
                key="ader_periodo",
            )
            if isinstance(periodo, tuple) and len(periodo) == 2:
                data_inicio_filtro, data_fim_filtro = periodo
            else:
                data_inicio_filtro, data_fim_filtro = data_min, data_max
        elif len(datas_disp) == 1:
            data_inicio_filtro = data_fim_filtro = pd.Timestamp(datas_disp[0]).date()
            st.date_input(
                "📅 Período",
                value=data_inicio_filtro,
                min_value=data_inicio_filtro,
                max_value=data_fim_filtro,
                key="ader_periodo_single",
            )
        else:
            st.info("Nenhum dado de data disponível para filtrar.")
            return

    # ── Cálculo e filtragem ───────────────────────────────────────────────────
    df_aderencia = _calcular_aderencia(df_hist, df_escala)

    if df_aderencia.empty:
        st.info("Não foi possível calcular a aderência com os dados e escalas fornecidos.")
        return

    df_ad_filtrado = df_aderencia[
        (df_aderencia["Agente"].isin(agentes_sel)) &
        (df_aderencia["Data"].dt.date >= data_inicio_filtro) &
        (df_aderencia["Data"].dt.date <= data_fim_filtro)
    ].copy()

    if df_ad_filtrado.empty:
        st.warning("Nenhum dado de aderência encontrado para os filtros selecionados.")
        return

    # ── KPIs ──────────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("📊 Resumo de Aderência")

    # Calcular KPIs médios
    media_aderencia = df_ad_filtrado["% Aderência"].mean()
    agentes_acima_meta = df_ad_filtrado[df_ad_filtrado["% Aderência"] >= meta]["Agente"].nunique()
    total_agentes_filtrados = df_ad_filtrado["Agente"].nunique()

    col_k1, col_k2, col_k3 = st.columns(3)
    col_k1.metric(
        "📈 Média de Aderência",
        f"{media_aderencia:.1f}%",
        delta=f"{agentes_acima_meta} agentes acima da meta",
        delta_color="normal" if agentes_acima_meta >= total_agentes_filtrados / 2 else "inverse",
    )
    col_k2.metric(
        "🎯 Agentes Acima da Meta",
        f"{agentes_acima_meta}",
        help=f"Total de {total_agentes_filtrados} agentes filtrados."
    )
    col_k3.metric(
        "⏳ Tempo Produtivo Total",
        f"{df_ad_filtrado['Produtivo Real (min)'].sum():.0f} min",
        help="Soma do tempo produtivo real dentro dos turnos planejados."
    )

    st.divider()

    # ── Ranking ───────────────────────────────────────────────────────────────
    st.subheader("🏆 Ranking de Aderência")
    df_rank = df_ad_filtrado.groupby("Agente")["% Aderência"].mean().reset_index()
    df_rank = df_rank.sort_values("% Aderência", ascending=False)

    fig_rank = px.bar(
        df_rank,
        x="Agente",
        y="% Aderência",
        color="% Aderência",
        color_continuous_scale="RdYlGn",
        range_color=[0, 100],
        text="% Aderência",
        title="Média de Aderência por Agente",
    )
    fig_rank.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig_rank.add_hline(y=meta, line_dash="dash", line_color="red",
                       annotation_text=f"Meta {meta}%",
                       annotation_position="top right")
    fig_rank.update_layout(
        coloraxis_showscale=False,
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        font=dict(color="#111111"),
        yaxis_range=[0, 110],
    )
    st.plotly_chart(fig_rank, use_container_width=True, key="ader_fig_rank")

    st.divider()

    # ── Evolução Histórica ────────────────────────────────────────────────────
    st.subheader("📈 Evolução da Aderência")
    df_ev = df_ad_filtrado.groupby(["Data", "Agente"])["% Aderência"].mean().reset_index()
    if not df_ev.empty:
        fig_ev = px.line(
            df_ev,
            x="Data",
            y="% Aderência",
            color="Agente",
            markers=True,
            title="Evolução Diária da Aderência",
        )
        fig_ev.add_hline(y=meta, line_dash="dash", line_color="red",
                         annotation_text=f"Meta {meta}%",
                         annotation_position="top right")
        fig_ev.update_layout(
            plot_bgcolor="#ffffff",
            paper_bgcolor="#ffffff",
            font=dict(color="#111111"),
            yaxis_range=[0, 110],
        )
        st.plotly_chart(fig_ev, use_container_width=True, key="ader_fig_ev")
    else:
        st.info("Não há dados suficientes para mostrar a evolução da aderência.")

    st.divider()

    # ── Gantt de Aderência (para um agente e dia específico) ──────────────────
    st.subheader("🗓️ Detalhe da Aderência (Gantt)")
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        agente_gantt = st.selectbox(
            "Agente para Gantt",
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
        data=df_to_xlsx(df_rank), # Usando df_rank do ranking acima
        file_name="aderencia_ranking.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="ader_exp_rank",
    )
