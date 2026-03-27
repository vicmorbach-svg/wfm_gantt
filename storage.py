# storage.py
import pandas as pd
import os
from datetime import datetime, time, date # Importar date e time
import json
from config import HISTORICO_PATH, ESCALA_PATH, MAP_WEEKDAY_TO_NAME

# Colunas esperadas para o histórico
HISTORICO_COLS = ["agente", "estado", "inicio", "fim", "minutos", "data", "dia_semana", "dia_semana_num"]

# Colunas esperadas para a escala
ESCALA_COLS = [
    "agente", "data", "dia_semana", "dia_semana_num",
    "hora_inicio_escala", "hora_fim_escala",
    "intervalos_json", "observacao"
]

def carregar_historico() -> pd.DataFrame:
    if os.path.exists(HISTORICO_PATH):
        df = pd.read_parquet(HISTORICO_PATH)
        # Garantir que as colunas de data/hora estejam nos tipos corretos
        df["inicio"] = pd.to_datetime(df["inicio"])
        df["fim"] = pd.to_datetime(df["fim"])
        df["data"] = pd.to_datetime(df["data"]).dt.date # Garantir que 'data' seja datetime.date
        return df
    return pd.DataFrame(columns=HISTORICO_COLS)

def salvar_historico(df: pd.DataFrame):
    # Garantir que 'data' seja datetime.date antes de salvar, se necessário
    if "data" in df.columns and pd.api.types.is_datetime64_any_dtype(df["data"]):
        df["data"] = df["data"].dt.date
    df.to_parquet(HISTORICO_PATH, index=False)

def limpar_historico():
    if os.path.exists(HISTORICO_PATH):
        os.remove(HISTORICO_PATH)
        print(f"Arquivo de histórico removido: {HISTORICO_PATH}")

def carregar_escala() -> pd.DataFrame:
    if os.path.exists(ESCALA_PATH):
        df = pd.read_parquet(ESCALA_PATH)
        # Garantir que as colunas de data/hora estejam nos tipos corretos
        df["data"] = pd.to_datetime(df["data"]).dt.date # Garantir que 'data' seja datetime.date
        # Converter strings de hora para objetos time
        df["hora_inicio_escala"] = df["hora_inicio_escala"].apply(lambda x: time.fromisoformat(str(x)) if isinstance(x, str) else x)
        df["hora_fim_escala"] = df["hora_fim_escala"].apply(lambda x: time.fromisoformat(str(x)) if isinstance(x, str) else x)
        return df
    return pd.DataFrame(columns=ESCALA_COLS)

def salvar_escala(df: pd.DataFrame):
    # Antes de salvar, garantir que 'data' seja datetime.date e horas sejam strings ISO
    if "data" in df.columns and pd.api.types.is_datetime664_any_dtype(df["data"]):
        df["data"] = df["data"].dt.date
    df["hora_inicio_escala"] = df["hora_inicio_escala"].apply(lambda x: x.isoformat() if isinstance(x, time) else x)
    df["hora_fim_escala"] = df["hora_fim_escala"].apply(lambda x: x.isoformat() if isinstance(x, time) else x)
    df.to_parquet(ESCALA_PATH, index=False)

def escala_para_display(df_escala: pd.DataFrame) -> pd.DataFrame:
    """Formata o DataFrame de escala para exibição no Streamlit."""
    if df_escala.empty:
        return pd.DataFrame(columns=["ID", "Agente", "Data", "Dia", "Início", "Fim", "Intervalos", "Observação"])

    df_display = df_escala.copy()
    df_display["ID"] = df_display.index + 1 # Adiciona um ID para facilitar a referência
    df_display["Data"] = df_display["data"].dt.strftime('%d/%m/%Y') if pd.api.types.is_datetime64_any_dtype(df_display["data"]) else df_display["data"].apply(lambda x: x.strftime('%d/%m/%Y'))
    df_display["Dia"] = df_display["dia_semana"]
    df_display["Início"] = df_display["hora_inicio_escala"].apply(lambda x: x.strftime('%H:%M') if isinstance(x, time) else x)
    df_display["Fim"] = df_display["hora_fim_escala"].apply(lambda x: x.strftime('%H:%M') if isinstance(x, time) else x)
    df_display["Intervalos"] = df_display["intervalos_json"].apply(lambda x: json.loads(x) if isinstance(x, str) else x)
    df_display["Observação"] = df_display["observacao"]

    return df_display[["ID", "agente", "Data", "Dia", "Início", "Fim", "Intervalos", "Observação"]].rename(columns={"agente": "Agente"})
