# config.py
import os

# Define o diretório base para os arquivos de dados
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True) # Garante que o diretório 'data' existe

# Caminhos para os arquivos de armazenamento
HISTORICO_PATH = os.path.join(DATA_DIR, "historico_agentes.parquet")
ESCALA_PATH = os.path.join(DATA_DIR, "escala_agentes.parquet")

# Estados a serem considerados para o cálculo de aderência e exibição
# Mantendo ESTADOS_INTERESSE como a lista principal de estados a serem processados
ESTADOS_INTERESSE = [
    "Unified online",
    "Unified away",
    "Unified offline",
    "Unified transfers only"
]

# Estados a serem excluídos (lista vazia conforme solicitado)
ESTADOS_EXCLUIR = []

# Mapeamento de estados para categorias (usado para cores e agrupamento)
ESTADOS_PRODUTIVOS = ["Unified online", "Unified transfers only"]
ESTADOS_PAUSA = ["Unified away"]
ESTADOS_IMPRODUTIVOS = ["Unified offline"] # Considerado improdutivo para aderência

# Ordem dos dias da semana para gráficos e mapeamento de weekday()
DIAS_SEMANA_ORDEM = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
# Mapeamento para garantir que o weekday() do Python (0=seg, 6=dom) corresponda aos nomes em português
MAP_WEEKDAY_TO_NAME = {
    0: "Segunda-feira",
    1: "Terça-feira",
    2: "Quarta-feira",
    3: "Quinta-feira",
    4: "Sexta-feira",
    5: "Sábado",
    6: "Domingo"
}

# Cores para os status no gráfico de Gantt e outras visualizações (renomeado para CORES_ESTADOS)
CORES_ESTADOS = {
    "Unified online":         "#28a745", # Verde
    "Unified away":           "#ffc107", # Amarelo
    "Unified offline":        "#dc3545", # Vermelho
    "Unified transfers only": "#17a2b8", # Azul claro (ou outro para diferenciar)
    # Adicione outras cores se houver outros estados que possam aparecer e você queira colorir
    # "Outro Estado": "#6c757d", # Cinza
}

# Limite de minutos para alerta de "Unified away" no dashboard
LIMITE_ALERTA_AWAY_MINUTOS = 30 # Exemplo: 30 minutos

# Cores para o tema claro e escuro (se aplicável, para consistência)
CORES_TEMA = {
    "fundo_claro": "#ffffff",
    "fundo_escuro": "#343a40",
    "texto_claro": "#212529",
    "texto_escuro": "#f8f9fa",
}
