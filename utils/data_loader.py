# utils/data_loader.py
import pandas as pd
from datetime import datetime, timedelta
from config import ESTADOS_EXCLUIR, DIAS_SEMANA_ORDEM, ESTADOS_INTERESSE

def processar_arquivo(uploaded_file) -> pd.DataFrame:
    if uploaded_file is None:
        return pd.DataFrame()

    try:
        # Tenta ler o arquivo Excel
        df = pd.read_excel(uploaded_file)
    except Exception as e:
        raise ValueError(f"Erro ao ler o arquivo Excel: {e}")

    # Padronizar nomes das colunas removendo espaços e convertendo para minúsculas
    df.columns = df.columns.str.strip()

    # Mapeamento exato das colunas do arquivo para nomes padronizados
    col_mapping = {
        "Nome do agente": "agente",
        "Hora de início do estado - Carimbo de data/hora": "inicio",
        "Hora de término do estado - Carimbo de data/hora": "fim",
        "Estado": "estado",
        "Tempo do agente no estado / Minutos": "minutos",
    }

    # Verificar se todas as colunas esperadas estão presentes no DataFrame
    missing_cols = [col for col in col_mapping.keys() if col not in df.columns]
    if missing_cols:
        raise KeyError(f"As seguintes colunas esperadas não foram encontradas no arquivo: {missing_cols}. "
                       f"Colunas disponíveis: {list(df.columns)}")

    # Renomear colunas para padronizar
    df = df.rename(columns=col_mapping)

    # Selecionar apenas as colunas de interesse após a renomeação
    cols_interesse = list(col_mapping.values())
    df = df[cols_interesse]

    # Converter colunas de tempo para datetime, tratando erros
    # Usamos errors='coerce' para transformar valores inválidos em NaT (Not a Time)
    df["inicio"] = pd.to_datetime(df["inicio"], errors='coerce')
    df["fim"]    = pd.to_datetime(df["fim"], errors='coerce')

    # Remover linhas onde 'inicio' ou 'fim' não puderam ser convertidos
    df.dropna(subset=["inicio", "fim"], inplace=True)

    # Tratar valores NaN na coluna 'minutos' (por exemplo, preencher com 0 ou remover)
    df.dropna(subset=["minutos"], inplace=True)

    # Remover estados que não são de interesse (se ESTADOS_EXCLUIR não estiver vazia)
    # Como ESTADOS_EXCLUIR agora está vazia, este filtro não removerá nada.
    if ESTADOS_EXCLUIR:
        df = df[~df["estado"].isin(ESTADOS_EXCLUIR)]

    # Filtrar para incluir apenas os estados definidos em ESTADOS_INTERESSE
    df = df[df["estado"].isin(ESTADOS_INTERESSE)]

    # Adicionar coluna de duração em segundos para cálculos futuros
    df["duracao_segundos"] = (df["fim"] - df["inicio"]).dt.total_seconds()

    # Adicionar coluna de dia da semana
    df["dia_semana"] = df["inicio"].dt.day_name(locale='pt_BR')
    df["dia_semana"] = pd.Categorical(df["dia_semana"], categories=DIAS_SEMANA_ORDEM, ordered=True)

    # Adicionar coluna de data para facilitar o agrupamento por dia
    df["data"] = df["inicio"].dt.date

    # Ajustar o fim do estado para o dia seguinte se passar da meia-noite
    # Isso é importante para visualização em gráficos de Gantt que precisam de um fim no mesmo dia
    # Ou para calcular a duração correta em um dia específico
    df['fim_ajustado'] = df.apply(
        lambda row: row['fim'] if row['fim'].date() == row['inicio'].date()
                    else row['inicio'].replace(hour=23, minute=59, second=59, microsecond=999999),
        axis=1
    )

    return df
