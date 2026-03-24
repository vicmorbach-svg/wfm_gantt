import streamlit as st
import pandas as pd
from datetime import datetime, time

def render(df_escala: pd.DataFrame):
    st.title("Visualização da Escala")

    if df_escala.empty:
        st.warning("Nenhum dado de escala disponível.")
        return

    st.subheader("Escala de Trabalho dos Agentes")

    # Exibir a escala em um DataFrame
    # Ajustar para exibir apenas as colunas relevantes e formatar a data/hora
    df_escala_display = df_escala.copy()
    df_escala_display["data"] = df_escala_display["data"].dt.strftime("%d/%m/%Y")
    df_escala_display["hora_inicio_escala"] = df_escala_display["hora_inicio_escala"].apply(lambda x: x.strftime("%H:%M"))
    df_escala_display["hora_fim_escala"] = df_escala_display["hora_fim_escala"].apply(lambda x: x.strftime("%H:%M"))

    st.dataframe(df_escala_display.set_index(["agente", "data"]))

    # Opcional: Adicionar filtros para a escala
    agentes_escala = df_escala["agente"].unique().tolist()
    agente_selecionado_escala = st.selectbox("Filtrar escala por agente:", ["Todos"] + agentes_escala)

    if agente_selecionado_escala != "Todos":
        df_escala_filtrada = df_escala_display[df_escala_display["agente"] == agente_selecionado_escala]
        st.dataframe(df_escala_filtrada.set_index(["agente", "data"]))
