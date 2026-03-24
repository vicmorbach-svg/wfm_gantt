# utils/data_loader.py
import pandas as pd
from datetime import datetime, timedelta
import streamlit as st # Adicione esta linha
from config import ESTADOS_INTERESSE, ESTADOS_EXCLUIR, DIAS_SEMANA_ORDEM

def processar_arquivo(uploaded_file) -> pd.DataFrame:
    try:
        # Ler o arquivo Excel
        df = pd.read_excel(uploaded_file)

        # Limpar nomes das colunas: remover espaços extras e caracteres especiais
        df.columns = df.columns.str.strip()
        df.columns = df.columns.str.replace(r'[^\w\s]', '', regex=True) # Remove caracteres não alfanuméricos (exceto espaços)
        df.columns = df.columns.str.replace(r'\s+', ' ', regex=True) # Substitui múltiplos espaços por um único espaço
        df.columns = df.columns.str.strip() # Remove espaços no início/fim novamente

        # Mapeamento dos nomes originais das colunas para os nomes padronizados
        # Usando os nomes exatos do arquivo Excel fornecido
        col_mapping = {
            "Nome do agente": "agente",
            "Hora de início do estado - Carimbo de data/hora": "inicio",
            "Hora de término do estado - Carimbo de data/hora": "fim",
            "Estado": "estado",
            "Tempo do agente no estado / Minutos": "minutos"
        }

        # Verificar se todas as colunas esperadas existem no DataFrame
        colunas_esperadas_originais = list(col_mapping.keys())
        colunas_faltantes = [col for col in colunas_esperadas_originais if col not in df.columns]

        if colunas_faltantes:
            raise ValueError(f"As seguintes colunas esperadas não foram encontradas no arquivo: {', '.join(colunas_faltantes)}. "
                             f"Colunas disponíveis: {', '.join(df.columns)}")

        # Selecionar e renomear as colunas de interesse
        df = df[colunas_esperadas_originais].rename(columns=col_mapping)

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
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Ocorreu um erro inesperado: {e}")
        return pd.DataFrame()

def get_agentes(df: pd.DataFrame) -> list:
    """Retorna uma lista de agentes únicos do DataFrame."""
    return sorted(df["agente"].unique().tolist())
