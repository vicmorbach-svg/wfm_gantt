# utils/data_loader.py
import pandas as pd
from datetime import datetime, timedelta
from config import ESTADOS_EXCLUIR, DIAS_SEMANA_ORDEM, ESTADOS_PRODUTIVOS, ESTADOS_PAUSA, ESTADOS_FORA

def processar_arquivo(uploaded_file) -> pd.DataFrame:
    """
    Processa um arquivo de upload (Excel ou CSV) do Zendesk Explore,
    padroniza colunas, converte tipos e trata a passagem de dia.
    """
    try:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else: # Assume xlsx ou xls
            df = pd.read_excel(uploaded_file)
    except Exception as e:
        st.error(f"Erro ao ler o arquivo {uploaded_file.name}: {e}")
        return pd.DataFrame()

    # Renomear colunas para padronizar
    df = df.rename(columns={
        "Nome do agente":                      "agente",
        "Hora de início do estado - Carimbo de data/hora": "inicio",
        "Hora de fim do estado - Carimbo de data/hora":    "fim",
        "Nome do estado":                      "estado",
        "Tempo do agente no estado / Minutos": "minutos",
    })

    # Selecionar e reordenar colunas de interesse
    cols_interesse = ["agente", "inicio", "fim", "estado", "minutos"]
    df = df[cols_interesse]

    # Converter para datetime, tratando erros
    df["inicio"] = pd.to_datetime(df["inicio"], errors='coerce')
    df["fim"]    = pd.to_datetime(df["fim"], errors='coerce') # <-- CORREÇÃO AQUI

    # Remover linhas com valores NaT após a conversão
    df.dropna(subset=["inicio", "fim"], inplace=True)

    # Remover estados que devem ser excluídos (ex: "Invisible")
    df = df[~df["estado"].isin(ESTADOS_EXCLUIR)]

    # Garantir que 'minutos' seja numérico, preenchendo NaN com 0
    df["minutos"] = pd.to_numeric(df["minutos"], errors='coerce').fillna(0)

    # Filtrar eventos com duração zero ou negativa (após conversão)
    df = df[df["minutos"] > 0]

    # --- Lógica para tratar eventos que atravessam a meia-noite ---
    df_split = []
    for _, row in df.iterrows():
        inicio_dia = row["inicio"].normalize()
        fim_dia    = row["fim"].normalize()

        if inicio_dia == fim_dia:
            # Evento no mesmo dia
            df_split.append(row)
        else:
            # Evento atravessa a meia-noite
            # Parte 1: do início até o fim do primeiro dia
            row1 = row.copy()
            row1["fim"] = inicio_dia + timedelta(days=1) - timedelta(microseconds=1)
            row1["minutos"] = (row1["fim"] - row1["inicio"]).total_seconds() / 60
            df_split.append(row1)

            # Parte 2: do início do segundo dia até o fim original
            row2 = row.copy()
            row2["inicio"] = fim_dia
            row2["minutos"] = (row2["fim"] - row2["inicio"]).total_seconds() / 60
            df_split.append(row2)

    df = pd.DataFrame(df_split)

    # Recalcular minutos para garantir consistência após split
    df["minutos"] = (df["fim"] - df["inicio"]).dt.total_seconds() / 60
    df = df[df["minutos"] > 0] # Remover eventos com duração zero após split

    # Adicionar coluna de data para facilitar filtros
    df["data"] = df["inicio"].dt.normalize()

    # Adicionar dia da semana
    df["dia_semana"] = df["inicio"].dt.day_name(locale='pt_BR.utf8')
    df["dia_semana_num"] = df["inicio"].dt.dayofweek

    return df

def get_agentes(df_hist: pd.DataFrame) -> list:
    """Retorna a lista de agentes únicos do histórico."""
    if df_hist.empty:
        return []
    return sorted(df_hist["agente"].unique().tolist())

def calcular_aderencia(df_hist: pd.DataFrame, df_escala: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula a aderência de cada agente à sua escala para cada dia.
    Considera o tempo produtivo dentro do turno planejado, excluindo intervalos.
    """
    if df_hist.empty or df_escala.empty:
        return pd.DataFrame()

    df_aderencia_rows = []

    for _, escala_row in df_escala.iterrows():
        agente = escala_row["agente"]
        dia_semana_num = escala_row["dia_semana_num"]
        turno_inicio_str = escala_row["turno_inicio"]
        turno_fim_str = escala_row["turno_fim"]
        intervalos = json.loads(escala_row["intervalos_json"])

        # Filtrar histórico para o agente e dias da semana da escala
        df_agente_dias = df_hist[
            (df_hist["agente"] == agente) &
            (df_hist["dia_semana_num"] == dia_semana_num)
        ].copy()

        if df_agente_dias.empty:
            continue

        for data_dia in df_agente_dias["data"].unique():
            df_dia_agente = df_agente_dias[df_agente_dias["data"] == data_dia].copy()

            # Converter horas do turno para datetime no dia específico
            try:
                turno_inicio_dt = pd.to_datetime(f"{data_dia.strftime('%Y-%m-%d')} {turno_inicio_str}")
                turno_fim_dt = pd.to_datetime(f"{data_dia.strftime('%Y-%m-%d')} {turno_fim_str}")
            except ValueError:
                continue # Pular se a hora da escala for inválida

            # Calcular minutos planejados no turno (sem intervalos)
            minutos_planejados_turno = (turno_fim_dt - turno_inicio_dt).total_seconds() / 60

            minutos_intervalos_planejados = 0
            for intervalo in intervalos:
                try:
                    int_ini_dt = pd.to_datetime(f"{data_dia.strftime('%Y-%m-%d')} {intervalo['inicio']}")
                    int_fim_dt = pd.to_datetime(f"{data_dia.strftime('%Y-%m-%d')} {intervalo['fim']}")
                    # Garantir que o intervalo esteja dentro do turno
                    int_ini_dt = max(int_ini_dt, turno_inicio_dt)
                    int_fim_dt = min(int_fim_dt, turno_fim_dt)
                    if int_fim_dt > int_ini_dt:
                        minutos_intervalos_planejados += (int_fim_dt - int_ini_dt).total_seconds() / 60
                except ValueError:
                    continue # Pular se a hora do intervalo for inválida

            minutos_esperados_produtivos = minutos_planejados_turno - minutos_intervalos_planejados
            if minutos_esperados_produtivos <= 0:
                minutos_esperados_produtivos = 1 # Evitar divisão por zero, mas indicar que não há tempo produtivo esperado

            # Calcular minutos produtivos reais dentro do turno
            minutos_produtivos_reais = 0
            for _, status_row in df_dia_agente.iterrows():
                if status_row["estado"] in ESTADOS_PRODUTIVOS:
                    # Interseção do status real com o turno planejado
                    real_ini = status_row["inicio"]
                    real_fim = status_row["fim"]

                    # Interseção com o turno
                    inter_ini = max(real_ini, turno_inicio_dt)
                    inter_fim = min(real_fim, turno_fim_dt)

                    if inter_fim > inter_ini:
                        minutos_no_turno = (inter_fim - inter_ini).total_seconds() / 60

                        # Subtrair minutos de intervalos planejados
                        for intervalo in intervalos:
                            try:
                                int_ini_dt = pd.to_datetime(f"{data_dia.strftime('%Y-%m-%d')} {intervalo['inicio']}")
                                int_fim_dt = pd.to_datetime(f"{data_dia.strftime('%Y-%m-%d')} {intervalo['fim']}")
                                # Interseção do status com o intervalo
                                int_status_ini = max(inter_ini, int_ini_dt)
                                int_status_fim = min(inter_fim, int_fim_dt)
                                if int_status_fim > int_status_ini:
                                    minutos_no_turno -= (int_status_fim - int_status_ini).total_seconds() / 60
                            except ValueError:
                                continue

                        if minutos_no_turno > 0:
                            minutos_produtivos_reais += minutos_no_turno

            aderencia_pct = (minutos_produtivos_reais / minutos_esperados_produtivos) * 100 if minutos_esperados_produtivos > 0 else 0

            df_aderencia_rows.append({
                "Agente": agente,
                "Data": data_dia,
                "Dia Semana": DIAS_SEMANA_ORDEM[dia_semana_num],
                "Minutos Produtivos Reais": minutos_produtivos_reais,
                "Minutos Esperados Produtivos": minutos_esperados_produtivos,
                "% Aderência": aderencia_pct,
            })

    return pd.DataFrame(df_aderencia_rows)
