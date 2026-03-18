import streamlit as st
from utils.data_loader import processar_arquivo, get_agentes
from utils.storage     import carregar_historico, salvar_historico, limpar_historico
from utils.dedup       import deduplicar
from tabs              import tab_dashboard, tab_escala, tab_aderencia
import pandas as pd

st.set_page_config(
    page_title="Monitor de Status – Zendesk",
    page_icon="📊",
    layout="wide",
)


def main():
    st.title("📊 Monitor de Status de Agentes – Zendesk")

    # ── Sidebar ────────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("📁 Upload de Relatório")
        arquivos = st.file_uploader(
            "Arquivo(s) do Zendesk Explore",
            type=["xlsx", "xls", "csv"],
            accept_multiple_files=True,
        )

        st.divider()
        limite_alerta = st.slider(
            "⚠️ Limite de alerta de pausa (min)",
            min_value=10, max_value=120, value=30, step=5,
        )

        st.divider()
        if st.button("🗑️ Limpar histórico", type="secondary",
                     use_container_width=True):
            limpar_historico()
            st.success("Histórico removido.")
            st.rerun()

        st.caption("Monitor de Status v3.0 | Inner AI")

    # ── Carregamento e acúmulo ─────────────────────────────────────────────
    df_hist = carregar_historico()

    if arquivos:
        novos = []
        for arq in arquivos:
            df_p = processar_arquivo(arq)
            if not df_p.empty:
                novos.append(df_p)
                st.sidebar.success(f"✅ {arq.name}")

        if novos:
            df_novo = pd.concat(novos, ignore_index=True)
            df_hist = (
                pd.concat([df_hist, df_novo], ignore_index=True)
                if not df_hist.empty else df_novo
            )
            df_hist = deduplicar(df_hist)
            salvar_historico(df_hist)

    agentes = get_agentes(df_hist)

    # ── Tabs ───────────────────────────────────────────────────────────────
    tab1, tab2, tab3 = st.tabs([
        "📊 Dashboard",
        "📅 Configurar Escala",
        "🎯 Aderência à Escala",
    ])

    with tab1:
        tab_dashboard.render(df_hist, limite_alerta)

    with tab2:
        tab_escala.render(agentes)

    with tab3:
        tab_aderencia.render(df_hist)


if __name__ == "__main__":
    main()
