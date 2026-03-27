# utils/data_loader.py
import pandas as pd
from datetime import datetime, timedelta
import streamlit as st
import re # Importar o módulo 're' para expressões regulares
from config import ESTADOS_INTERESSE, ESTADOS_EXCLUIR, MAP_WEEKDAY_TO_NAME # Usar MAP_WEEKDAY_TO_NAME
from dedup import deduplicar # Importar a função de deduplicação

def processar_arquivo(uploaded_file) -> pd.DataFrame:
    try:
        # Ler o arquivo Excel
        df = pd.read_excel(uploaded_file)

        # Mapeamento dos nomes originais das colunas para os nomes padronizados
        col_mapping = {
            "Nome do agente": "agente",
            "Hora de início do estado - Carimbo de data/hora": "inicio",
            "Hora de término do estado - Carimbo de data/hora": "fim",
            "Estado": "estado",
            "Tempo do agente no estado / Minutos": "minutos"
        }

        # Limpar nomes das colunas do DataFrame para facilitar a correspondência
        df.columns = [re.sub(r'\s+', ' ', col).strip() for col in df.columns]

        # Verificar se todas as colunas esperadas (após a limpeza básica) existem no DataFrame
        cleaned_col_mapping_keys = {re.sub(r'\s+', ' ', k).strip(): k for k in col_mapping.keys()}
        colunas_faltantes = [cleaned_key for cleaned_key in cleaned_col_mapping_keys if cleaned_key not in df.columns]

        if colunas_faltantes:
            reverse_col_mapping = {re.sub(r'\s+', ' ', k).strip(): k for k in col_mapping.keys()}
            original_missing_cols = [reverse_col_mapping.get(col, col) for col in colunas_faltantes]

            raise ValueError(f"As seguintes colunas esperadas não foram encontradas no arquivo: {', '.join(original_missing_cols)}. "
                             f"Colunas disponíveis: {', '.join(df.columns)}")

        # Renomear as colunas de interesse usando o mapeamento
        cleaned_col_mapping = {re.sub(r'\s+', ' ', k).strip(): v for k, v in col_mapping.items()}
        df = df.rename(columns=cleaned_col_mapping)

        # Converter colunas de tempo para datetime
        df["inicio"] = pd.to_datetime(df["inicio"], errors='coerce')
        df["fim"]    = pd.to_datetime(df["fim"], errors='coerce')

        # Remover linhas onde 'inicio' ou 'fim' não puderam ser convertidos
        df.dropna(subset=["inicio", "fim"], inplace=True)

        # Remover linhas onde 'minutos' é NaN
        df.dropna(subset=["minutos"], inplace=True)

        # Filtrar estados de interesse
        df = df[df["estado"].isin(ESTADOS_INTERESSE)]

        # Lidar com eventos que cruzam a meia-noite
        df_processado = []
        for _, row in df.iterrows():
            inicio = row["inicio"]
            fim = row["fim"]
            estado = row["estado"]
            agente = row["agente"]
            minutos = row["minutos"]

            current_day = inicio.normalize()
            next_day = current_day + timedelta(days=1)

            while inicio < fim:
                end_of_segment = min(fim, next_day)
                duration_segment = (end_of_segment - inicio).total_seconds() / 60

                # Adicionar apenas se a duração for positiva
                if duration_segment > 0:
                    df_processado.append({
                        "agente": agente,
                        "estado": estado,
                        "inicio": inicio,
                        "fim": end_of_segment,
                        "minutos": duration_segment,
                        "data": current_day.date() # Armazenar como datetime.date
                    })

                inicio = end_of_segment
                current_day = inicio.normalize()
                next_day = current_day + timedelta(days=1)

        df_final = pd.DataFrame(df_processado)

        # Adicionar coluna 'dia_semana' e 'dia_semana_num'
        df_final["dia_semana"] = df_final["data"].apply(lambda x: MAP_WEEKDAY_TO_NAME[x.weekday()])
        df_final["dia_semana_num"] = df_final["data"].apply(lambda x: x.weekday())

        # Chamar a função de deduplicação
        df_final = deduplicar(df_final)

        return df_final

    except ValueError as e:
        st.error(f"Erro ao processar o arquivo: {e}")
        # st.exception(e) # Comentado para evitar redundância de traceback no Streamlit
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Ocorreu um erro inesperado: {e}")
        # st.exception(e) # Comentado para evitar redundância de traceback no Streamlit
        return pd.DataFrame()

def get_agentes(df: pd.DataFrame) -> list:
    """Retorna uma lista de agentes únicos do DataFrame."""
    return sorted(df["agente"].unique().tolist())
