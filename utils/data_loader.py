# utils/data_loader.py
import pandas as pd
from datetime import timedelta
from config import ESTADOS_EXCLUIR

def processar_arquivo(uploaded_file) -> pd.DataFrame:
    try:
        df = pd.read_excel(uploaded_file)
    except Exception:
        df = pd.read_csv(uploaded_file)

    # Renomear colunas para padronização
    df.columns = [
        "agente", "dia_mes", "inicio", "fim", "estado", "minutos_raw"
    ]

    # Converter tipos
    df["inicio"] = pd.to_datetime(df["inicio"])
    df["fim"]    = pd.to_datetime(df["fim"])
    df["data"]   = df["inicio"].dt.normalize() # Data do início do evento

    # Preencher minutos_raw se estiver faltando (calcula a partir de inicio/fim)
    df["minutos_raw"] = df.apply(
        lambda row: (row["fim"] - row["inicio"]).total_seconds() / 60
        if pd.isna(row["minutos_raw"]) else row["minutos_raw"],
        axis=1
    )

    # Remover estados a serem excluídos (ex: Invisible)
    df = df[~df["estado"].isin(ESTADOS_EXCLUIR)]

    # ── Tratar eventos que atravessam a meia-noite ────────────────────────────
    eventos_split = []
    for _, row in df.iterrows():
        inicio_original = row["inicio"]
        fim_original    = row["fim"]
        data_original   = row["data"]

        # Se o evento termina no dia seguinte
        if fim_original.date() > inicio_original.date():
            # Parte do evento no dia de início
            fim_primeiro_dia = data_original + timedelta(days=1) - timedelta(microseconds=1)
            minutos_primeiro_dia = (fim_primeiro_dia - inicio_original).total_seconds() / 60

            if minutos_primeiro_dia > 0:
                eventos_split.append(row.to_dict())
                eventos_split[-1].update({
                    "inicio": inicio_original,
                    "fim":    fim_primeiro_dia,
                    "minutos_raw": minutos_primeiro_dia,
                    "data":   data_original,
                })

            # Parte do evento no dia seguinte
            inicio_segundo_dia = data_original + timedelta(days=1)
            minutos_segundo_dia = (fim_original - inicio_segundo_dia).total_seconds() / 60

            if minutos_segundo_dia > 0:
                eventos_split.append(row.to_dict())
                eventos_split[-1].update({
                    "inicio": inicio_segundo_dia,
                    "fim":    fim_original,
                    "minutos_raw": minutos_segundo_dia,
                    "data":   inicio_segundo_dia.normalize(), # Data do segundo dia
                })
        else:
            # Evento normal, não atravessa a meia-noite
            eventos_split.append(row.to_dict())

    df_processado = pd.DataFrame(eventos_split)

    # Recalcular minutos após o split
    df_processado["minutos"] = (
        df_processado["fim"] - df_processado["inicio"]
    ).dt.total_seconds() / 60

    # Remover linhas com minutos <= 0 ou NaT
    df_processado = df_processado[df_processado["minutos"] > 0]
    df_processado = df_processado.dropna(subset=["inicio", "fim"])

    return df_processado

def get_agentes(df: pd.DataFrame) -> list:
    if df.empty:
        return []
    return sorted(df["agente"].unique().tolist())
