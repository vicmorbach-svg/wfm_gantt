import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from config import ESTADOS_EXCLUIR, DIAS_SEMANA_ORDEM

# ─── FUNÇÕES DE CARREGAMENTO E PRÉ-PROCESSAMENTO ──────────────────────────────

@st.cache_data(ttl=3600) # Cacheia os dados por 1 hora
def processar_arquivo(uploaded_file) -> pd.DataFrame:
    if uploaded_file is None:
        return pd.DataFrame()

    try:
        # Tenta ler como Excel
        df = pd.read_excel(uploaded_file)
    except Exception:
        st.error("Formato de arquivo inválido. Por favor, suba um arquivo Excel (.xlsx).")
        return pd.DataFrame()

    # Renomear colunas para padronizar (ajustado para o nome exato da planilha)
    df = df.rename(columns={
        "Agent Name": "agente",
        "Start Time": "inicio",
        "End Time": "fim",
        "Status": "estado",
        "Duration (min)": "minutos", # A coluna já existe e pode ser usada
    })

    # Selecionar e reordenar colunas
    colunas_esperadas = ["agente", "inicio", "fim", "estado", "minutos"]
    if not all(col in df.columns for col in colunas_esperadas):
        st.error(
            "O arquivo Excel não contém todas as colunas esperadas: "
            f"{', '.join(colunas_esperadas)}. "
            "Verifique se o nome das colunas está correto."
        )
        return pd.DataFrame()

    df = df[colunas_esperadas].copy()

    # Converter colunas de tempo para datetime, tratando erros
    df["inicio"] = pd.to_datetime(df["inicio"], errors='coerce')
    df["fim"]    = pd.to_datetime(df["fim"], errors='coerce')

    # Remover linhas onde 'inicio' ou 'fim' são NaT (erros de conversão)
    df.dropna(subset=["inicio", "fim"], inplace=True)

    # Remover estados indesejados (ex: "Invisible")
    df = df[~df["estado"].isin(ESTADOS_EXCLUIR)].copy()

    # Garantir que 'minutos' seja numérico, tratando NaNs
    df["minutos"] = pd.to_numeric(df["minutos"], errors='coerce').fillna(0)

    # Filtrar durações inválidas (fim <= inicio)
    df = df[df["fim"] > df["inicio"]].copy()

    # ── Tratamento de passagem de dia ──────────────────────────────────────────
    # Divide eventos que cruzam a meia-noite em dois eventos separados
    rows_split = []
    for _, row in df.iterrows():
        inicio_dt = row["inicio"]
        fim_dt    = row["fim"]

        if inicio_dt.date() != fim_dt.date():
            # Evento que cruza a meia-noite
            meia_noite_inicio = datetime(
                inicio_dt.year, inicio_dt.month, inicio_dt.day, 23, 59, 59
            )
            meia_noite_fim    = datetime(
                fim_dt.year, fim_dt.month, fim_dt.day, 0, 0, 0
            )

            # Parte 1: do início até o final do dia
            duracao_p1 = (meia_noite_inicio - inicio_dt).total_seconds() / 60
            if duracao_p1 > 0:
                rows_split.append({
                    "agente":  row["agente"],
                    "inicio":  inicio_dt,
                    "fim":     meia_noite_inicio,
                    "estado":  row["estado"],
                    "minutos": duracao_p1,
                })

            # Parte 2: do início do próximo dia até o fim original
            duracao_p2 = (fim_dt - meia_noite_fim).total_seconds() / 60
            if duracao_p2 > 0:
                rows_split.append({
                    "agente":  row["agente"],
                    "inicio":  meia_noite_fim,
                    "fim":     fim_dt,
                    "estado":  row["estado"],
                    "minutos": duracao_p2,
                })
        else:
            rows_split.append(row.to_dict())

    df_processed = pd.DataFrame(rows_split)

    # Adicionar coluna 'data' para facilitar filtros por dia
    df_processed["data"] = df_processed["inicio"].dt.date

    # Ordenar para garantir consistência
    df_processed = df_processed.sort_values(
        ["agente", "inicio"]
    ).reset_index(drop=True)

    return df_processed

def get_agentes(df: pd.DataFrame) -> list:
    if df.empty:
        return []
    return sorted(df["agente"].unique().tolist())

def get_datas(df: pd.DataFrame) -> list:
    if df.empty:
        return []
    return sorted(df["data"].unique().tolist())
