import pandas as pd
from datetime import datetime, timedelta
from config import ESTADOS_ADMISSAO, ESTADOS_EXCLUIR # Importar ESTADOS_ADMISSAO

def processar_arquivo(uploaded_file) -> pd.DataFrame:
    if uploaded_file is not None:
        try:
            # Determinar o tipo de arquivo e ler
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            elif uploaded_file.name.endswith(('.xls', '.xlsx')):
                df = pd.read_excel(uploaded_file)
            else:
                raise ValueError("Formato de arquivo não suportado. Por favor, envie um arquivo CSV ou Excel.")

            # Limpar nomes das colunas: remover espaços extras e caracteres especiais, converter para minúsculas
            df.columns = df.columns.str.strip()
            df.columns = df.columns.str.replace(r'[^\w\s]', '', regex=True) # Remove special chars
            df.columns = df.columns.str.replace(r'\s+', ' ', regex=True) # Replace multiple spaces with single space
            df.columns = df.columns.str.lower() # Convert to lowercase

            # Mapeamento dos nomes originais das colunas para nomes padronizados
            # Usando os nomes exatos do arquivo Excel fornecido pelo usuário
            col_mapping = {
                "nome do agente": "agente",
                "hora de início do estado  carimbo de datahora": "inicio", # Note: double space in original column name
                "hora de término do estado  carimbo de datahora": "fim",   # Note: double space in original column name
                "estado": "estado",
                "tempo do agente no estado  minutos": "minutos", # Note: double space in original column name
            }

            # Verificar se todas as colunas esperadas estão no DataFrame após a limpeza
            colunas_esperadas_originais = list(col_mapping.keys())
            if not all(col in df.columns for col in colunas_esperadas_originais):
                missing_cols = [col for col in colunas_esperadas_originais if col not in df.columns]
                raise KeyError(f"Uma ou mais colunas esperadas não foram encontradas no arquivo: {missing_cols}. "
                               f"Colunas disponíveis: {list(df.columns)}")

            # Renomear colunas
            df = df.rename(columns=col_mapping)

            # Selecionar apenas as colunas de interesse após renomear
            cols_interesse = ["agente", "inicio", "fim", "estado", "minutos"]
            df = df[cols_interesse]

            # Converter colunas de data/hora
            # Usar errors='coerce' para transformar valores inválidos em NaT (Not a Time)
            df["inicio"] = pd.to_datetime(df["inicio"], errors='coerce')
            df["fim"]    = pd.to_datetime(df["fim"], errors='coerce')

            # Preencher NaT na coluna 'fim' para o final do dia ou o momento atual
            # Se 'fim' for NaT, significa que o estado ainda está ativo.
            # Para esses casos, podemos usar a data de 'inicio' + 1 dia (se for o último registro do dia)
            # ou o timestamp atual se for o último registro geral.
            # Para simplificar, vamos preencher com o 'inicio' + 1 minuto para evitar duração zero
            # ou, melhor, com o momento atual se for o último registro do agente.
            # Para o propósito do Gantt, se o fim for NaT, podemos assumir que o estado continua até o final do dia de início.
            # Ou, para ser mais preciso, se for o último registro de um agente, assumir que vai até o momento atual.
            # Por enquanto, vamos preencher com o início + 1 minuto para evitar erros de cálculo de duração.
            # Uma abordagem mais robusta seria tratar isso no contexto do Gantt, mas para o processamento inicial:
            df['fim'] = df['fim'].fillna(df['inicio'] + pd.Timedelta(minutes=1)) # Temporário para evitar NaT

            # Remover linhas onde 'inicio' ou 'fim' são NaT após a conversão
            df.dropna(subset=["inicio", "fim"], inplace=True)

            # Filtrar estados conforme a lista ESTADOS_ADMISSAO
            df = df[df["estado"].isin(ESTADOS_ADMISSAO)]

            # Garantir que 'minutos' é numérico e preencher NaNs com 0
            df["minutos"] = pd.to_numeric(df["minutos"], errors='coerce').fillna(0)

            # Calcular a duração em minutos a partir das colunas 'inicio' e 'fim'
            # Isso é útil para verificar a consistência com a coluna 'minutos' original
            df["duracao_calculada"] = (df["fim"] - df["inicio"]).dt.total_seconds() / 60

            # Ajustar a duração para estados que passam da meia-noite
            # Esta lógica pode ser mais complexa dependendo de como você quer visualizar.
            # Para o Gantt, cada segmento deve estar dentro de um único dia.
            # Se um estado começa em um dia e termina no outro, ele deve ser dividido.
            df_split = []
            for _, row in df.iterrows():
                start = row['inicio']
                end = row['fim']
                current_day = start.normalize() # Midnight of the start day

                while current_day < end.normalize():
                    next_day = current_day + timedelta(days=1)
                    segment_end = min(end, next_day)
                    segment_duration = (segment_end - start).total_seconds() / 60
                    df_split.append(row.drop(['inicio', 'fim', 'minutos', 'duracao_calculada']).to_dict() | {
                        'inicio': start,
                        'fim': segment_end,
                        'minutos': segment_duration,
                        'dia': start.day # Adiciona a coluna 'dia' para o dia do segmento
                    })
                    start = next_day
                    current_day = next_day

                # Adicionar o segmento final (ou o único segmento se não houver passagem de dia)
                segment_duration = (end - start).total_seconds() / 60
                df_split.append(row.drop(['inicio', 'fim', 'minutos', 'duracao_calculada']).to_dict() | {
                    'inicio': start,
                    'fim': end,
                    'minutos': segment_duration,
                    'dia': start.day # Adiciona a coluna 'dia' para o dia do segmento
                })
            df = pd.DataFrame(df_split)

            # Adicionar coluna 'dia_semana' para facilitar a ordenação e filtragem
            df["dia_semana"] = df["inicio"].dt.day_name(locale='pt_BR')

            return df

        except Exception as e:
            st.error(f"Erro ao processar o arquivo: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

def get_agentes(df: pd.DataFrame) -> list:
    """
    Retorna uma lista de nomes de agentes únicos do DataFrame.
    """
    if not df.empty and "agente" in df.columns:
        return sorted(df["agente"].unique().tolist())
    return []
