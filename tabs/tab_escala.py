import streamlit as st
import pandas as pd
from datetime import datetime, time
from storage import escala_para_display # Importa a função de display

def render(df_escala: pd.DataFrame):
    st.title("Visualização da Escala")

    if df_escala.empty:
        st.warning("Nenhum dado de escala disponível. Carregue um arquivo de dados para gerar uma escala padrão ou adicione manualmente.")
        return

    st.subheader("Escala de Trabalho dos Agentes")

    # Usar a função escala_para_display do módulo storage para formatar
    df_escala_formatada = escala_para_display(df_escala)

    st.dataframe(df_escala_formatada.set_index(["Agente", "Dia"]))

    # Opcional: Adicionar filtros para a escala
    agentes_escala = df_escala_formatada["Agente"].unique().tolist() # Usar df_escala_formatada para os agentes
    agente_selecionado_escala = st.selectbox("Filtrar escala por agente:", ["Todos"] + agentes_escala)

    if agente_selecionado_escala != "Todos":
        df_escala_filtrada = df_escala_formatada[df_escala_formatada["Agente"] == agente_selecionado_escala]
        st.dataframe(df_escala_filtrada.set_index(["Agente", "Dia"]))
