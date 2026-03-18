import io
import json
import streamlit as st
import pandas as pd
from config import DIAS_SEMANA_ORDEM
from utils.storage import carregar_escala, salvar_escala, escala_para_display


# ─── HELPER XLSX ──────────────────────────────────────────────────────────────

def df_to_xlsx(df: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()


# ─── VALIDAÇÃO ────────────────────────────────────────────────────────────────

def _validar_hora(hora_str: str) -> bool:
    """Valida se a string está no formato HH:MM válido."""
    try:
        partes = hora_str.strip().split(":")
        if len(partes) != 2:
            return False
        h, m = int(partes[0]), int(partes[1])
        return 0 <= h <= 23 and 0 <= m <= 59
    except Exception:
        return False


# ─── RENDER ───────────────────────────────────────────────────────────────────

def render(agentes: list):
    st.header("📅 Configurar Escala dos Agentes")

    df_escala = carregar_escala()

    # ── Visualização atual ─────────────────────────────────────────────────
    st.subheader("📋 Escalas Cadastradas")
    if df_escala.empty:
        st.info("Nenhuma escala cadastrada ainda.")
    else:
        df_display = escala_para_display(df_escala)

        col_fa, col_fd = st.columns(2)
        with col_fa:
            ag_filt = st.multiselect(
                "Filtrar por agente",
                sorted(df_escala["agente"].unique()),
                default=list(df_escala["agente"].unique()),
                key="filt_ag",
            )
        with col_fd:
            dia_filt = st.multiselect(
                "Filtrar por dia",
                DIAS_SEMANA_ORDEM,
                default=list(df_escala["dia_semana"].unique()),
                key="filt_dia",
            )

        df_view = df_display[
            df_display["Agente"].isin(ag_filt) &
            df_display["Dia"].isin(dia_filt)
        ]
        st.dataframe(df_view, use_container_width=True, height=300)

    st.divider()

    # ── Formulário de cadastro ─────────────────────────────────────────────
    st.subheader("➕ Cadastrar / Atualizar Escala")

    if not agentes:
        st.warning(
            "Faça o upload de um relatório primeiro para carregar a lista de agentes."
        )
        return

    with st.form("form_escala", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            agente_sel = st.selectbox("👤 Agente", agentes)
            dias_sel = st.multiselect(
                "📆 Dias da semana",
                DIAS_SEMANA_ORDEM,
                default=[
                    "Segunda-feira", "Terça-feira", "Quarta-feira",
                    "Quinta-feira", "Sexta-feira",
                ],
            )

        with col2:
            turno_ini = st.text_input(
                "🕐 Início do turno",
                value="08:00",
                placeholder="HH:MM",
            )
            turno_fim = st.text_input(
                "🕔 Fim do turno",
                value="17:00",
                placeholder="HH:MM",
            )

        observacao = st.text_input("📝 Observação (opcional)", value="")

        st.markdown("**Intervalos planejados** (ex.: almoço, descanso)")
        n_intervalos = st.number_input(
            "Quantidade de intervalos",
            min_value=0,
            max_value=6,
            value=2,
            step=1,
        )

        intervalos_raw = []
        for i in range(int(n_intervalos)):
            ca, cb, cc = st.columns(3)
            with ca:
                nome_int = st.text_input(
                    f"Nome #{i+1}",
                    value=f"Intervalo {i+1}",
                    key=f"int_nome_{i}",
                )
            with cb:
                ini_int = st.text_input(
                    f"Início #{i+1}",
                    value="12:00",
                    placeholder="HH:MM",
                    key=f"int_ini_{i}",
                )
            with cc:
                fim_int = st.text_input(
                    f"Fim #{i+1}",
                    value="13:00",
                    placeholder="HH:MM",
                    key=f"int_fim_{i}",
                )
            # Guarda como strings puras — sem .strftime()
            intervalos_raw.append({
                "nome":   nome_int.strip(),
                "inicio": ini_int.strip(),
                "fim":    fim_int.strip(),
            })

        salvar_btn = st.form_submit_button("💾 Salvar escala", type="primary")

    # ── Validação e persistência ───────────────────────────────────────────
    if salvar_btn:
        erros = []

        if not dias_sel:
            erros.append("Selecione ao menos um dia da semana.")

        if not _validar_hora(turno_ini):
            erros.append(f"Início do turno inválido: '{turno_ini}'. Use HH:MM.")

        if not _validar_hora(turno_fim):
            erros.append(f"Fim do turno inválido: '{turno_fim}'. Use HH:MM.")

        if (
            _validar_hora(turno_ini)
            and _validar_hora(turno_fim)
            and turno_fim.strip() <= turno_ini.strip()
        ):
            erros.append("O fim do turno deve ser posterior ao início.")

        intervalos_validos = []
        for iv in intervalos_raw:
            ini, fim = iv["inicio"], iv["fim"]
            if ini or fim:
                if not _validar_hora(ini):
                    erros.append(
                        f"Intervalo '{iv['nome']}': início inválido '{ini}'. Use HH:MM."
                    )
                elif not _validar_hora(fim):
                    erros.append(
                        f"Intervalo '{iv['nome']}': fim inválido '{fim}'. Use HH:MM."
                    )
                else:
                    intervalos_validos.append(iv)

        if erros:
            for e in erros:
                st.error(e)
        else:
            df_escala = carregar_escala()
            novas = []
            for dia in dias_sel:
                # Remove registro anterior do mesmo agente + dia
                if not df_escala.empty:
                    df_escala = df_escala[
                        ~(
                            (df_escala["agente"] == agente_sel) &
                            (df_escala["dia_semana"] == dia)
                        )
                    ]
                num_dia = DIAS_SEMANA_ORDEM.index(dia)
                novas.append({
                    "agente":          agente_sel,
                    "dia_semana":      dia,
                    "dia_semana_num":  num_dia,
                    "turno_inicio":    turno_ini.strip(),   # str pura
                    "turno_fim":       turno_fim.strip(),   # str pura
                    "intervalos_json": json.dumps(
                        intervalos_validos, ensure_ascii=False
                    ),
                    "observacao":      observacao.strip(),
                })

            df_escala = pd.concat(
                [df_escala, pd.DataFrame(novas)],
                ignore_index=True,
            )
            salvar_escala(df_escala)
            st.success(
                f"✅ Escala de **{agente_sel}** salva para: "
                f"{', '.join(dias_sel)} | "
                f"{turno_ini.strip()} – {turno_fim.strip()}"
            )
            st.rerun()

    st.divider()

    # ── Remoção ────────────────────────────────────────────────────────────
    st.subheader("🗑️ Remover Escala")

    df_escala = carregar_escala()

    if not df_escala.empty:
        col_r1, col_r2, col_r3 = st.columns([2, 2, 1])

        with col_r1:
            ag_del = st.selectbox(
                "Agente",
                [""] + sorted(df_escala["agente"].unique().tolist()),
                key="del_ag",
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
            remover = st.button(
                "🗑️ Remover",
                type="secondary",
                use_container_width=True,
            )

        if remover and ag_del:
            df_escala = carregar_escala()
            if dia_del == "Todos os dias":
                df_escala = df_escala[df_escala["agente"] != ag_del]
                msg = f"Escala de **{ag_del}** removida em todos os dias."
            else:
                df_escala = df_escala[
                    ~(
                        (df_escala["agente"] == ag_del) &
                        (df_escala["dia_semana"] == dia_del)
                    )
                ]
                msg = f"Escala de **{ag_del}** removida em **{dia_del}**."
            salvar_escala(df_escala)
            st.success(msg)
            st.rerun()
    else:
        st.info("Nenhuma escala para remover.")

    st.divider()

    # ── Export ─────────────────────────────────────────────────────────────
    st.subheader("💾 Exportar Escalas")

    df_escala = carregar_escala()

    if not df_escala.empty:
        df_display_export = escala_para_display(df_escala)
        col_ex1, col_ex2 = st.columns(2)

        col_ex1.download_button(
            "⬇️ Exportar XLSX",
            data=df_to_xlsx(df_display_export),
            file_name="escalas_agentes.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet"
            ),
            use_container_width=True,
        )
        col_ex2.download_button(
            "⬇️ Exportar JSON",
            data=df_escala.to_json(
                orient="records", force_ascii=False, indent=2
            ).encode("utf-8"),
            file_name="escalas_agentes.json",
            mime="application/json",
            use_container_width=True,
        )
    else:
        st.info("Nenhuma escala cadastrada para exportar.")
