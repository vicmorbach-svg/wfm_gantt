# utils/data_loader.py
import pandas as pd
from datetime import datetime, timedelta
import streamlit as st
import re
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
            original_missing_cols = [cleaned_col_mapping_keys[col] for col in colunas_faltantes]
            raise ValueError(f"As seguintes colunas esperadas não foram encontradas no arquivo: {', '.join(original_missing_cols)}. "
                             f"Por favor, verifique se o arquivo contém as colunas: {', '.join(col_mapping.keys())}. "
                             f"Colunas disponíveis no arquivo: {', '.join(df.columns)}")

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
            # minutos = row["minutos"] # O tempo em minutos será recalculado para cada segmento

            current_day_start = inicio.normalize()

            while inicio < fim:
                end_of_segment = min(fim, current_day_start + timedelta(days=1))
                duration_segment = (end_of_segment - inicio).total_seconds() / 60

                # Adicionar apenas se a duração for positiva
                if duration_segment > 0:
                    df_processado.append({
                        "agente": agente,
                        "estado": estado,
                        "inicio": inicio,
                        "fim": end_of_segment,
                        "minutos": duration_segment,
                        "data": current_day_start.date()
                    })

                inicio = end_of_segment
                current_day_start = inicio.normalize() # Atualiza para o início do próximo dia

        df_final = pd.DataFrame(df_processado)

        if df_final.empty:
            return pd.DataFrame()

        # Adicionar coluna 'dia_semana' usando o mapeamento
        df_final["dia_semana"] = df_final["data"].apply(lambda x: MAP_WEEKDAY_TO_NAME[x.weekday()])
        df_final["dia_semana_num"] = df_final["data"].apply(lambda x: x.weekday())

        # Aplicar deduplicação
        df_final = deduplicar(df_final)

        return df_final

    except ValueError as e:
        st.error(f"Erro ao processar o arquivo: {e}")
        # st.exception(e) # Comentado para evitar traceback completo para o usuário final
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Ocorreu um erro inesperado ao processar o arquivo: {e}. Por favor, verifique o formato do arquivo.")
        # st.exception(e) # Comentado
        return pd.DataFrame()

def get_agentes(df: pd.DataFrame) -> list:
    """Retorna uma lista de agentes únicos do DataFrame."""
    if df.empty:
        return []
    return sorted(df["agente"].unique().tolist())
