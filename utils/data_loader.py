# utils/data_loader.py
import pandas as pd
import streamlit as st
from config import ESTADOS_EXCLUIR

MAPA_COLUNAS = {
    # Português
    "Nome do agente":                                   "agente",
    "Hora de início do estado - Dia do mês":           "dia_mes",
    "Hora de início do estado - Carimbo de data/hora": "inicio",
    "Hora de término do estado - Carimbo de data/hora":"fim",
    "Estado":                                          "estado",
    "Tempo do agente no estado / Minutos":             "minutos",
    # Inglês
    "Agent name":                                      "agente",
    "Agent status start time - Day of month":          "dia_mes",
    "Agent status start time - Timestamp":             "inicio",
    "Agent status end time - Timestamp":               "fim",
    "State":                                           "estado",
    "Agent time in state / Minutes":                   "minutos",
}


def _split_cross_midnight(df: pd.DataFrame) -> pd.DataFrame:
    """
    Divide linhas em que inicio e fim são em dias diferentes.
    Garante que cada linha fique totalmente contida em um único dia.
    """
    if df.empty:
        return df

    rows = []
    for _, r in df.iterrows():
        ini = r["inicio"]
        fim = r["fim"]

        # linhas já inválidas foram removidas antes
        if ini.date() == fim.date():
            rows.append(r)
            continue

        # há passagem de dia: dividir
        atual_ini = ini
        while atual_ini.date() < fim.date():
            meia_noite_seg_dia = (
                (atual_ini + pd.Timedelta(days=1))
                .replace(hour=0, minute=0, second=0, microsecond=0)
            )

            parte = r.copy()
            parte["inicio"] = atual_ini
            parte["fim"]    = min(meia_noite_seg_dia, fim)
            parte["data"]   = parte["inicio"].date()
            parte["minutos"] = (parte["fim"] - parte["inicio"]).total_seconds() / 60
            rows.append(parte)

            atual_ini = meia_noite_seg_dia

        # se ainda sobrar algo no último dia (por segurança)
        # (em prática, o loop acima já cobre até 'fim')
    df2 = pd.DataFrame(rows)
    return df2


def processar_arquivo(arquivo) -> pd.DataFrame:
    try:
        if arquivo.name.endswith(".csv"):
            df = pd.read_csv(arquivo)
        else:
            df = pd.read_excel(arquivo)
    except Exception as e:
        st.sidebar.error(f"Erro ao ler {arquivo.name}: {e}")
        return pd.DataFrame()

    # Normaliza nomes de colunas e renomeia
    df.columns = df.columns.str.strip()
    df = df.rename(columns={k: v for k, v in MAPA_COLUNAS.items() if k in df.columns})

    cols_req = ["agente", "inicio", "estado"]
    if not all(c in df.columns for c in cols_req):
        st.sidebar.error(f"Arquivo {arquivo.name} sem colunas esperadas.")
        return pd.DataFrame()

    df["inicio"] = pd.to_datetime(df["inicio"], errors="coerce")
    df["fim"]    = pd.to_datetime(df.get("fim", pd.NaT), errors="coerce")

    # Remove linhas sem início, sem fim, sem agente ou sem estado
    df = df.dropna(subset=["inicio", "fim", "agente", "estado"])

    # Remove linhas com fim <= início (dados inconsistentes)
    df = df[df["fim"] > df["inicio"]]

    # Calcula minutos, mesmo se a coluna não veio
    if "minutos" not in df.columns:
        df["minutos"] = (df["fim"] - df["inicio"]).dt.total_seconds() / 60
    else:
        # se existe, garante numérico
        df["minutos"] = pd.to_numeric(df["minutos"], errors="coerce")
        faltando = df["minutos"].isna()
        if faltando.any():
            df.loc[faltando, "minutos"] = (
                (df.loc[faltando, "fim"] - df.loc[faltando, "inicio"])
                .dt.total_seconds() / 60
            )

    # Remove apenas estados que realmente não queremos
    df = df[~df["estado"].isin(ESTADOS_EXCLUIR)]

    # Aqui NÃO removemos mais "Unified" (você quer considerar)

    # Agora tratamos a passagem de dia
    df = _split_cross_midnight(df)

    # Garante a coluna 'data' coerente com 'inicio' após split
    df["data"] = df["inicio"].dt.date

    return df


def get_agentes(df: pd.DataFrame) -> list:
    if df.empty:
        return []
    return sorted(df["agente"].unique().tolist())
