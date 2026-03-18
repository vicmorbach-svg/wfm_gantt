import json
import streamlit as st
import pandas as pd
from datetime import time
from config import DIAS_SEMANA_ORDEM
from utils.storage import carregar_escala, salvar_escala, escala_para_display


def render(agentes: list):
    st.header("📅 Configurar Escala dos Agentes")

    df_escala = carregar_escala()

    # ── Visualização atual ─────────────────────────────────────────────────
    st.subheader("📋 Escalas Cadastradas")
    if df_escala.empty:
        st.info("Nenhuma escala cadastrada ainda.")
    else:
        st.dataframe(escala_para_display(df_escala), use_container_width=True)

    st.divider()

    # ── Formulário de cadastro ─────────────────────────────────────────────
    st.subheader("➕ Cadastrar / Atualizar Escala")

    if not agentes:
        st.warning("Faça o upload de um relatório primeiro para carregar a lista de agentes.")
        return

    with st.form("form_escala", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            agente_sel = st.selectbox("👤 Agente", agentes)
            dias_sel   = st.multiselect(
                "📆 Dias da semana",
                DIAS_SEMANA_ORDEM,
                default=["Segunda-feira", "Terça-feira", "Quarta-feira",
                         "Quinta-feira", "Sexta-feira"],
            )
        with col2:
            turno_ini = st.time_input("🕐 Início do turno", value=time(8, 0))
            turno_fim = st.time_input("🕔 Fim do turno",    value=time(17, 0))

        observacao = st.text_input("📝 Observação (opcional)", "")

        # Intervalos planejados
        st.markdown("**Intervalos planejados** (ex.: almoço, descanso)")
        n_intervalos = st.number_input(
            "Quantidade de intervalos", min_value=0, max_value=6, value=2, step=1
        )

        intervalos = []
        for i in range(int(n_intervalos)):
            ca, cb, cc = st.columns(3)
            with ca:
                nome_int = st.text_input(f"Nome #{i+1}", f"Intervalo {i+1}",
                                         key=f"int_nome_{i}")
            with cb:
                ini_int  = st.time_input(f"Início #{i+1}", value=time(12, 0),
                                         key=f"int_ini_{i}")
            with cc:
                fim_int  = st.time_input(f"Fim #{i+1}",    value=time(13, 0),
                                         key=f"int_fim_{i}")
            intervalos.append({
                "nome":   nome_int,
                "inicio": ini_int.strftime("%H:%M"),
                "fim":    fim_int.strftime("%H:%M"),
            })

        salvar_btn = st.form_submit_button("💾 Salvar escala", type="primary")

    if salvar_btn:
        if not dias_sel:
            st.error("Selecione ao menos um dia da semana.")
        elif turno_fim <= turno_ini:
            st.error("O fim do turno deve ser posterior ao início.")
        else:
            df_escala = carregar_escala()
            novas = []
            for dia in dias_sel:
                # Remove registro anterior do mesmo agente+dia
                df_escala = df_escala[
                    ~((df_escala["agente"] == agente_sel) &
                      (df_escala["dia_semana"] == dia))
                ]
                num_dia = DIAS_SEMANA_ORDEM.index(dia)
                novas.append({
                    "agente":          agente_sel,
                    "dia_semana":      dia,
                    "dia_semana_num":  num_dia,
                    "turno_inicio":    turno_ini.strftime("%H:%M"),
                    "turno_fim":       turno_fim.strftime("%H:%M"),
                    "intervalos_json": json.dumps(intervalos, ensure_ascii=False),
                    "observacao":      observacao,
                })

            df_escala = pd.concat(
                [df_escala, pd.DataFrame(novas)], ignore_index=True
            )
            salvar_escala(df_escala)
            st.success(
                f"✅ Escala de **{agente_sel}** salva para: "
                f"{', '.join(dias_sel)}"
            )
            st.rerun()

    st.divider()

    # ── Remoção ────────────────────────────────────────────────────────────
    st.subheader("🗑️ Remover Escala")
    if not df_escala.empty:
        col_r1, col_r2, col_r3 = st.columns([2, 2, 1])
        with col_r1:
            ag_del = st.selectbox(
                "Agente", [""] + sorted(df_escala["agente"].unique().tolist()),
                key="del_ag"
            )
        with col_r2:
            if ag_del:
                dias_disp = ["Todos os dias"] + sorted(
                    df_escala[df_escala["agente"] == ag_del]["dia_semana"].tolist()
                )
            else:
                dias_disp = ["Todos os dias"]
            dia_del = st.selectbox("Dia", dias_disp, key="del_dia")
        with col_r3:
            st.write("")
            st.write("")
            remover = st.button("Remover", type="secondary",
                                use_container_width=True)

        if remover and ag_del:
            df_escala = carregar_escala()
            if dia_del == "Todos os dias":
                df_escala = df_escala[df_escala["agente"] != ag_del]
                msg = f"Escala de **{ag_del}** removida em todos os dias."
            else:
                df_escala = df_escala[
                    ~((df_escala["agente"] == ag_del) &
                      (df_escala["dia_semana"] == dia_del))
                ]
                msg = f"Escala de **{ag_del}** removida em **{dia_del}**."
            salvar_escala(df_escala)
            st.success(msg)
            st.rerun()

    st.divider()

    # ── Export ─────────────────────────────────────────────────────────────
    st.subheader("💾 Exportar Escalas")
    if not df_escala.empty:
        col_ex1, col_ex2 = st.columns(2)
        col_ex1.download_button(
            "⬇️ Exportar CSV",
            data=escala_para_display(df_escala).to_csv(index=False).encode("utf-8"),
            file_name="escalas_agentes.csv",
            mime="text/csv",
        )
        col_ex2.download_button(
            "⬇️ Exportar JSON",
            data=df_escala.to_json(
                orient="records", force_ascii=False, indent=2
            ).encode("utf-8"),
            file_name="escalas_agentes.json",
            mime="application/json",
        )
