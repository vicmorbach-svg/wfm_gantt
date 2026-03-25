import os
import json
import pandas as pd
from config import HISTORICO_PATH, ESCALA_PATH

# ── HISTÓRICO ──────────────────────────────────────────────────────────────────

def carregar_historico() -> pd.DataFrame:
    if os.path.exists(HISTORICO_PATH):
        return pd.read_parquet(HISTORICO_PATH)
    return pd.DataFrame()

def salvar_historico(df: pd.DataFrame):
    df.to_parquet(HISTORICO_PATH, index=False)

def limpar_historico():
    if os.path.exists(HISTORICO_PATH):
        os.remove(HISTORICO_PATH)

# ── ESCALA ─────────────────────────────────────────────────────────────────────

ESCALA_COLS = [
    "agente", "dia_semana", "dia_semana_num",
    "turno_inicio", "turno_fim",
    "intervalos_json", "observacao",
]

def carregar_escala() -> pd.DataFrame:
    if os.path.exists(ESCALA_PATH):
        return pd.read_parquet(ESCALA_PATH)
    return pd.DataFrame(columns=ESCALA_COLS)

def salvar_escala(df: pd.DataFrame):
    df.to_parquet(ESCALA_PATH, index=False)

def escala_para_display(df_escala: pd.DataFrame) -> pd.DataFrame:
    """Converte JSON de intervalos para texto legível."""
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
            "Dia":            r["dia_semana"],
            "Turno Início":   r["turno_inicio"],
            "Turno Fim":      r["turno_fim"],
            "Intervalos":     txt,
            "Observação":     r.get("observacao", ""),
        })
    return pd.DataFrame(rows)
