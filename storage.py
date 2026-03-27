# storage.py
import os
import json
import pandas as pd
from config import HISTORICO_PATH, ESCALA_PATH, MAP_WEEKDAY_TO_NAME
from datetime import datetime, time

# ── HISTÓRICO ──────────────────────────────────────────────────────────────────

def carregar_historico() -> pd.DataFrame:
    if os.path.exists(HISTORICO_PATH):
        df = pd.read_parquet(HISTORICO_PATH)
        # Garantir que as colunas de data/hora estejam no formato correto
        if "inicio" in df.columns:
            df["inicio"] = pd.to_datetime(df["inicio"])
        if "fim" in df.columns:
            df["fim"] = pd.to_datetime(df["fim"])
        if "data" in df.columns:
            df["data"] = pd.to_datetime(df["data"]).dt.date # Armazenar como date object
        return df
    return pd.DataFrame()

def salvar_historico(df: pd.DataFrame):
    # Garantir que 'data' seja apenas a data antes de salvar
    if "data" in df.columns:
        df["data"] = df["data"].apply(lambda x: x.date() if isinstance(x, datetime) else x)
    df.to_parquet(HISTORICO_PATH, index=False)

def limpar_historico():
    if os.path.exists(HISTORICO_PATH):
        os.remove(HISTORICO_PATH)

# ── ESCALA ─────────────────────────────────────────────────────────────────────

# Adicionando 'data' à lista de colunas da escala
ESCALA_COLS = [
    "agente", "data", "dia_semana", "dia_semana_num",
    "hora_inicio_escala", "hora_fim_escala",
    "intervalos_json", "observacao",
]

def carregar_escala() -> pd.DataFrame:
    if os.path.exists(ESCALA_PATH):
        df = pd.read_parquet(ESCALA_PATH)
        # Garantir que 'data' seja datetime e horas sejam time objects
        if "data" in df.columns:
            df["data"] = pd.to_datetime(df["data"]).dt.normalize() # Garante que seja datetime sem hora
        if "hora_inicio_escala" in df.columns:
            df["hora_inicio_escala"] = df["hora_inicio_escala"].apply(lambda x: pd.to_datetime(str(x)).time() if isinstance(x, str) else x)
        if "hora_fim_escala" in df.columns:
            df["hora_fim_escala"] = df["hora_fim_escala"].apply(lambda x: pd.to_datetime(str(x)).time() if isinstance(x, str) else x)
        return df
    return pd.DataFrame(columns=ESCALA_COLS)

def salvar_escala(df: pd.DataFrame):
    # Garantir que 'data' seja apenas a data antes de salvar
    if "data" in df.columns:
        df["data"] = df["data"].dt.date # Salva apenas a data
    df.to_parquet(ESCALA_PATH, index=False)

def escala_para_display(df_escala: pd.DataFrame) -> pd.DataFrame:
    """Converte JSON de intervalos para texto legível e formata para exibição."""
    if df_escala.empty:
        return pd.DataFrame(columns=["Agente", "Data", "Dia", "Turno Início", "Turno Fim", "Intervalos", "Observação"])

    rows = []
    for _, r in df_escala.iterrows():
        try:
            intervalos = json.loads(r["intervalos_json"])
            txt = "; ".join(
                f"{i['nome']} {i['inicio']}–{i['fim']}"
                for i in intervalos
            ) if intervalos else "—"
        except Exception:
            txt = "—"
        rows.append({
            "Agente":         r["agente"],
            "Data":           r["data"].strftime("%d/%m/%Y") if pd.notna(r["data"]) else "",
            "Dia":            r["dia_semana"],
            "Turno Início":   r["hora_inicio_escala"].strftime("%H:%M") if pd.notna(r["hora_inicio_escala"]) else "",
            "Turno Fim":      r["hora_fim_escala"].strftime("%H:%M") if pd.notna(r["hora_fim_escala"]) else "",
            "Intervalos":     txt,
            "Observação":     r.get("observacao", ""),
        })
    return pd.DataFrame(rows)
