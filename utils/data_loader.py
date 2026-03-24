# utils/data_loader.py

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
    except Exception as e:
        st.error(
            f"Formato de arquivo inválido ou erro ao ler o Excel: {e}. "
            "Por favor, suba um arquivo Excel (.xlsx)."
        )
        return pd.DataFrame()

    # 1. Padronizar nomes das colunas existentes no DataFrame
    # Remove espaços extras e converte para Title Case para facilitar o match
    # Ex: "Nome do agente" -> "Nome Do Agente"
    df.columns = [col.strip().title() for col in df.columns]

    # Mapeamento dos nomes *exatos* das colunas do seu arquivo (já em Title Case)
    # para os nomes internos padronizados.
    col_mapping = {
        "Nome Do Agente":                   "agente",
        "Hora De Início Do Estado - Carimbo De Data/Hora": "inicio",
        "Hora De Término Do Estado - Carimbo De Data/Hora": "fim",
        "Estado":                           "estado",
        "Tempo Do Agente No Estado / Minutos": "minutos",
        # "Hora De Início Do Estado - Dia Do Mês" não será mapeada para uma coluna interna
        # pois a data será extraída de "inicio"
    }

    # Colunas internas que esperamos ter após o renomeio
    colunas_internas_esperadas = ["agente", "inicio", "fim", "estado", "minutos"]

    # Verificar se todas as colunas *originais esperadas* estão presentes no DataFrame
    # antes de tentar renomear. Usamos as chaves do col_mapping para isso.
    missing_original_cols = [
        original_col for original_col in col_mapping.keys()
        if original_col not in df.columns
    ]

    if missing_original_cols:
        st.error(
            "O arquivo Excel não contém todas as colunas esperadas. "
            f"Colunas faltando: {', '.join(missing_original_cols)}. "
            "Verifique se os nomes das colunas estão corretos e sem erros de digitação."
        )
        return pd.DataFrame()

    # Renomear as colunas
    df = df.rename(columns=col_mapping)

    # Selecionar e reordenar colunas finais
    df = df[colunas_internas_esperadas].copy()

    # Converter colunas de tempo para datetime, tratando erros
    df["inicio"] = pd.to_datetime(df["inicio"], errors='coerce')
    df["fim"]    = pd.to_datetime(df["fim"], errors='coerce')

    # Remover linhas onde 'inicio' ou 'fim' são NaT (erros de conversão)
    df.dropna(subset=["inicio", "fim"], inplace=True)

    # Remover estados indesejados (ex: "Invisible")
    df = df[~df["estado"].isin(ESTADOS_EXCLUIR)].copy()

    # Garantir que 'minutos' seja numérico, tratando NaNs
    # Se a coluna 'minutos' já veio preenchida, usamos ela.
    # Caso contrário, calculamos a partir de 'inicio' e 'fim'.
    # O `data_loader` agora garante que 'minutos' sempre virá do arquivo,
    # mas esta verificação é uma salvaguarda.
    df["minutos"] = pd.to_numeric(df["minutos"], errors='coerce').fillna(0)
    # Se ainda houver minutos zerados ou inválidos após a conversão,
    # e se 'fim' e 'inicio' forem válidos, recalcular.
    invalid_minutes_mask = (df["minutos"] <= 0) & df["inicio"].notna() & df["fim"].notna()
    df.loc[invalid_minutes_mask, "minutos"] = (
        (df.loc[invalid_minutes_mask, "fim"] - df.loc[invalid_minutes_mask, "inicio"]).dt.total_seconds() / 60
    )


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
            # Parte 1: do início até o final do dia (23:59:59)
            meia_noite_inicio = datetime(
                inicio_dt.year, inicio_dt.month, inicio_dt.day, 23, 59, 59
            )
            duracao_p1 = (meia_noite_inicio - inicio_dt).total_seconds() / 60
            if duracao_p1 > 0:
                rows_split.append({
                    "agente":  row["agente"],
                    "inicio":  inicio_dt,
                    "fim":     meia_noite_inicio,
                    "estado":  row["estado"],
                    "minutos": duracao_p1,
                })

            # Parte 2: do início do próximo dia (00:00:00) até o fim real
            meia_noite_fim    = datetime(
                fim_dt.year, fim_dt.month, fim_dt.day, 0, 0, 0
            )
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

    df_processado = pd.DataFrame(rows_split)

    # Adicionar coluna 'data' para facilitar filtros por dia
    df_processado["data"] = df_processado["inicio"].dt.date

    # Adicionar dia da semana para aderência
    df_processado["dia_semana_num"] = df_processado["inicio"].dt.dayofweek

    return df_processado

def get_agentes(df: pd.DataFrame) -> list:
    if df.empty:
        return []
    return sorted(df["agente"].unique().tolist())
