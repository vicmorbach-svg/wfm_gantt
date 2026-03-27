# storage.py
import pandas as pd
import os
import json
from datetime import datetime, time, date # Importar date e time
from config import HISTORICO_PATH, ESCALA_PATH, MAP_WEEKDAY_TO_NAME # Importar MAP_WEEKDAY_TO_NAME

# --- Funções para Histórico de Agentes ---
def carregar_historico() -> pd.DataFrame:
    if os.path.exists(HISTORICO_PATH):
        df = pd.read_parquet(HISTORICO_PATH)
        # Garantir que 'data' seja datetime.date e 'inicio'/'fim' sejam datetime
        if "data" in df.columns:
            df["data"] = pd.to_datetime(df["data"]).dt.date
        if "inicio" in df.columns:
            df["inicio"] = pd.to_datetime(df["inicio"])
        if "fim" in df.columns:
            df["fim"] = pd.to_datetime(df["fim"])
        return df
    return pd.DataFrame()

def salvar_historico(df: pd.DataFrame):
    if not df.empty:
        # Converter 'data' para string antes de salvar se for datetime.date, para evitar problemas com parquet
        # Ou garantir que o parquet salve datetime.date corretamente (geralmente ele lida bem)
        # Para maior segurança, podemos converter para datetime completo ou string
        df_to_save = df.copy()
        if "data" in df_to_save.columns and pd.api.types.is_object_dtype(df_to_save["data"]):
            # Se for object (datetime.date), converter para datetime para parquet
            df_to_save["data"] = df_to_save["data"].apply(lambda x: datetime.combine(x, time.min) if isinstance(x, date) else x)

        df_to_save.to_parquet(HISTORICO_PATH, index=False)

def limpar_historico():
    if os.path.exists(HISTORICO_PATH):
        os.remove(HISTORICO_PATH)

# --- Funções para Escala de Agentes ---
ESCALA_COLS = [
    "agente", "data", "dia_semana", "dia_semana_num",
    "hora_inicio_escala", "hora_fim_escala", # Nomes padronizados
    "intervalos_json", "observacao",
]

def carregar_escala() -> pd.DataFrame:
    if os.path.exists(ESCALA_PATH):
        df = pd.read_parquet(ESCALA_PATH)
        # Garantir que 'data' seja datetime.date e as horas sejam datetime.time
        if "data" in df.columns:
            df["data"] = pd.to_datetime(df["data"]).dt.date
        if "hora_inicio_escala" in df.columns:
            df["hora_inicio_escala"] = df["hora_inicio_escala"].apply(lambda x: x.time() if isinstance(x, datetime) else x)
        if "hora_fim_escala" in df.columns:
            df["hora_fim_escala"] = df["hora_fim_escala"].apply(lambda x: x.time() if isinstance(x, datetime) else x)
        return df
    return pd.DataFrame(columns=ESCALA_COLS)

def salvar_escala(df: pd.DataFrame):
    if not df.empty:
        # Garantir que as colunas existam antes de salvar
        for col in ESCALA_COLS:
            if col not in df.columns:
                df[col] = None # Adiciona colunas ausentes com valores nulos

        # Converter datetime.date para datetime para salvar no parquet
        df_to_save = df.copy()
        if "data" in df_to_save.columns and pd.api.types.is_object_dtype(df_to_save["data"]):
            df_to_save["data"] = df_to_save["data"].apply(lambda x: datetime.combine(x, time.min) if isinstance(x, date) else x)

        # Converter datetime.time para string ou datetime para salvar no parquet
        if "hora_inicio_escala" in df_to_save.columns and pd.api.types.is_object_dtype(df_to_save["hora_inicio_escala"]):
            df_to_save["hora_inicio_escala"] = df_to_save["hora_inicio_escala"].apply(lambda x: datetime.combine(date.min, x) if isinstance(x, time) else x)
        if "hora_fim_escala" in df_to_save.columns and pd.api.types.is_object_dtype(df_to_save["hora_fim_escala"]):
            df_to_save["hora_fim_escala"] = df_to_save["hora_fim_escala"].apply(lambda x: datetime.combine(date.min, x) if isinstance(x, time) else x)

        df_to_save[ESCALA_COLS].to_parquet(ESCALA_PATH, index=False)
    else:
        # Se o DataFrame estiver vazio, criar um arquivo parquet vazio ou remover o existente
        pd.DataFrame(columns=ESCALA_COLS).to_parquet(ESCALA_PATH, index=False)


def escala_para_display(df_escala: pd.DataFrame) -> pd.DataFrame:
    """Formata o DataFrame de escala para exibição amigável."""
    if df_escala.empty:
        return pd.DataFrame(columns=["Agente", "Data", "Dia", "Início", "Fim", "Intervalos", "Observação"])

    df_display = df_escala.copy()
    df_display["Data"] = df_display["data"].dt.strftime('%d/%m/%Y') if pd.api.types.is_datetime64_any_dtype(df_display["data"]) else df_display["data"].apply(lambda x: x.strftime('%d/%m/%Y') if isinstance(x, date) else '')
    df_display["Início"] = df_display["hora_inicio_escala"].apply(lambda x: x.strftime('%H:%M') if isinstance(x, time) else '')
    df_display["Fim"] = df_display["hora_fim_escala"].apply(lambda x: x.strftime('%H:%M') if isinstance(x, time) else '')
    df_display["Intervalos"] = df_display["intervalos_json"].apply(lambda x: json.dumps(json.loads(x), indent=2) if x else "[]")

    # Renomear colunas para exibição
    df_display = df_display.rename(columns={
        "agente": "Agente",
        "dia_semana": "Dia",
        "observacao": "Observação"
    })

    return df_display[["Agente", "Data", "Dia", "Início", "Fim", "Intervalos", "Observação"]]
