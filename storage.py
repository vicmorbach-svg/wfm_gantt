import os
import json
import pandas as pd
from datetime import time, date # Importar time e date
from config import HISTORICO_PATH, ESCALA_PATH

# ── HISTÓRICO ──────────────────────────────────────────────────────────────────

def carregar_historico() -> pd.DataFrame:
    if os.path.exists(HISTORICO_PATH):
        df = pd.read_parquet(HISTORICO_PATH)
        # Garantir que 'data' seja datetime.date e 'inicio'/'fim' sejam datetime
        if 'data' in df.columns:
            df['data'] = pd.to_datetime(df['data']).dt.date
        if 'inicio' in df.columns:
            df['inicio'] = pd.to_datetime(df['inicio'])
        if 'fim' in df.columns:
            df['fim'] = pd.to_datetime(df['fim'])
        return df
    return pd.DataFrame()

def salvar_historico(df: pd.DataFrame):
    # Converter 'data' para string ou datetime para salvar no parquet
    df_to_save = df.copy()
    if 'data' in df_to_save.columns:
        df_to_save['data'] = df_to_save['data'].astype(str) # Salvar como string para manter o formato date
    df_to_save.to_parquet(HISTORICO_PATH, index=False)

def limpar_historico():
    if os.path.exists(HISTORICO_PATH):
        os.remove(HISTORICO_PATH)

# ── ESCALA ─────────────────────────────────────────────────────────────────────

ESCALA_COLS = [
    "agente", "data", "dia_semana", "dia_semana_num",
    "hora_inicio_escala", "hora_fim_escala", # Renomeado para consistência
    "intervalos_json", "observacao",
]

def carregar_escala() -> pd.DataFrame:
    if os.path.exists(ESCALA_PATH):
        df = pd.read_parquet(ESCALA_PATH)
        # Garantir que 'data' seja datetime.date e as horas sejam datetime.time
        if 'data' in df.columns:
            df['data'] = pd.to_datetime(df['data']).dt.date
        if 'hora_inicio_escala' in df.columns:
            df['hora_inicio_escala'] = df['hora_inicio_escala'].apply(lambda x: time.fromisoformat(str(x)) if isinstance(x, str) else x)
        if 'hora_fim_escala' in df.columns:
            df['hora_fim_escala'] = df['hora_fim_escala'].apply(lambda x: time.fromisoformat(str(x)) if isinstance(x, str) else x)
        return df
    return pd.DataFrame(columns=ESCALA_COLS)

def salvar_escala(df: pd.DataFrame):
    df_to_save = df.copy()
    # Converter 'data' para string e 'time' para string para salvar no parquet
    if 'data' in df_to_save.columns:
        df_to_save['data'] = df_to_save['data'].astype(str)
    if 'hora_inicio_escala' in df_to_save.columns:
        df_to_save['hora_inicio_escala'] = df_to_save['hora_inicio_escala'].astype(str)
    if 'hora_fim_escala' in df_to_save.columns:
        df_to_save['hora_fim_escala'] = df_to_save['hora_fim_escala'].astype(str)
    df_to_save.to_parquet(ESCALA_PATH, index=False)

def escala_para_display(df_escala: pd.DataFrame) -> pd.DataFrame:
    """Converte JSON de intervalos para texto legível e formata a escala para exibição."""
    if df_escala.empty:
        return pd.DataFrame(columns=["Agente", "Data", "Dia", "Início", "Fim", "Intervalos", "Observação"])

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
            "Data":           r["data"].strftime('%d/%m/%Y') if isinstance(r["data"], date) else str(r["data"]),
            "Dia":            r["dia_semana"],
            "Início":         r["hora_inicio_escala"].strftime('%H:%M') if isinstance(r["hora_inicio_escala"], time) else str(r["hora_inicio_escala"]),
            "Fim":            r["hora_fim_escala"].strftime('%H:%M') if isinstance(r["hora_fim_escala"], time) else str(r["hora_fim_escala"]),
            "Intervalos":     txt,
            "Observação":     r.get("observacao", ""),
        })
    return pd.DataFrame(rows)
