# utils/data_loader.py
import pandas as pd
from datetime import datetime, timedelta
import streamlit as st
from config import ESTADOS_INTERESSE, ESTADOS_EXCLUIR, DIAS_SEMANA_ORDEM

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
        # Remover espaços extras no início/fim e substituir múltiplos espaços por um único
        df.columns = df.columns.str.strip().str.replace(r'\s+', ' ', regex=True)

        # Verificar se todas as colunas esperadas (após a limpeza básica) existem no DataFrame
        # Precisamos verificar se as chaves do col_mapping existem no df.columns
        colunas_esperadas_originais_limpas = [col.strip().replace(r'\s+', ' ', regex=True) for col in col_mapping.keys()]
        colunas_faltantes = [col for col in colunas_esperadas_originais_limpas if col not in df.columns]

        if colunas_faltantes:
            # Tentar um mapeamento mais flexível se as colunas exatas não forem encontradas
            # Criar um dicionário reverso para mapear os nomes limpos de volta aos originais para a mensagem de erro
            reverse_col_mapping = {v: k for k, v in col_mapping.items()}
            original_missing_cols = [reverse_col_mapping.get(col, col) for col in colunas_faltantes]

            raise ValueError(f"As seguintes colunas esperadas não foram encontradas no arquivo: {', '.join(original_missing_cols)}. "
                             f"Colunas disponíveis: {', '.join(df.columns)}")

        # Renomear as colunas de interesse usando o mapeamento
        # Criar um novo dicionário de mapeamento com as chaves limpas
        cleaned_col_mapping = {col.strip().replace(r'\s+', ' ', regex=True): new_name for col, new_name in col_mapping.items()}
        df = df.rename(columns=cleaned_col_mapping)

        # Selecionar apenas as colunas padronizadas
        df = df[list(col_mapping.values())]

        # Converter colunas de tempo para datetime
        # Usar errors='coerce' para transformar valores inválidos em NaT (Not a Time)
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
                        "data": current_day.date()
                    })

                inicio = end_of_segment
                current_day = inicio.normalize()
                next_day = current_day + timedelta(days=1)

        df_final = pd.DataFrame(df_processado)

        # Adicionar coluna 'dia_semana'
        df_final["dia_semana"] = df_final["data"].apply(lambda x: DIAS_SEMANA_ORDEM[x.weekday()])

        return df_final

    except ValueError as e:
        st.error(f"Erro ao processar o arquivo: {e}")
        st.exception(e) # Exibe o traceback completo para depuração
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Ocorreu um erro inesperado: {e}")
        st.exception(e) # Exibe o traceback completo para depuração
        return pd.DataFrame()

def get_agentes(df: pd.DataFrame) -> list:
    """Retorna uma lista de agentes únicos do DataFrame."""
    return sorted(df["agente"].unique().tolist())
