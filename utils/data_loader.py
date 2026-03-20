import pandas as pd
import streamlit as st
from config import ESTADOS_EXCLUIR

MAPA_COLUNAS = {
    # Português
    "Nome do agente":                                        "agente",
    "Hora de início do estado - Dia do mês":                "dia_mes",
    "Hora de início do estado - Carimbo de data/hora":      "inicio",
    "Hora de término do estado - Carimbo de data/hora":     "fim",
    "Estado":                                               "estado",
    "Tempo do agente no estado / Minutos":                  "minutos",
    # Inglês
    "Agent name":                                           "agente",
    "Agent status start time - Day of month":               "dia_mes",
    "Agent status start time - Timestamp":                  "inicio",
    "Agent status end time - Timestamp":                    "fim",
    "State":                                                "estado",
    "Agent time in state / Minutes":                        "minutos",
}


def processar_arquivo(arquivo) -> pd.DataFrame:
    try:
        if arquivo.name.endswith(".csv"):
            df = pd.read_csv(arquivo)
        else:
            df = pd.read_excel(arquivo)
    except Exception as e:
        st.sidebar.error(f"Erro ao ler {arquivo.name}: {e}")
        return pd.DataFrame()

    df.columns = df.columns.str.strip()
    df = df.rename(columns={k: v for k, v in MAPA_COLUNAS.items() if k in df.columns})

    cols_req = ["agente", "inicio", "estado"]
    if not all(c in df.columns for c in cols_req):
        st.sidebar.error(f"Arquivo {arquivo.name} sem colunas esperadas.")
        return pd.DataFrame()

    df["inicio"] = pd.to_datetime(df["inicio"], errors="coerce")
    df["fim"]    = pd.to_datetime(df.get("fim",  pd.NaT), errors="coerce")
    df["data"]   = df["inicio"].dt.date

    if "minutos" not in df.columns:
        df["minutos"] = (df["fim"] - df["inicio"]).dt.total_seconds() / 60

    # Remove estados Unified e similares
    df = df[~df["estado"].isin(ESTADOS_EXCLUIR)]

    # Remove linhas sem início, sem agente ou sem estado
    df = df.dropna(subset=["inicio", "agente", "estado"])

    # Remove linhas sem fim válido ou com fim <= início
    df = df[df["fim"].notna()]
    df = df[df["fim"] > df["inicio"]]

    return df


def get_agentes(df: pd.DataFrame) -> list:
    if df.empty:
        return []
    return sorted(df["agente"].unique().tolist())
