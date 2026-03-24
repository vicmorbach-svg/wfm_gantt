# config.py

# Estados a serem considerados para o cálculo de aderência e exibição
ESTADOS_ADMISSAO = [
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

# Ordem dos dias da semana para gráficos
DIAS_SEMANA_ORDEM = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]

# Cores para os status no gráfico de Gantt e outras visualizações
CORES_STATUS = {
    "Unified online":         "#28a745", # Verde
    "Unified away":           "#ffc107", # Amarelo
    "Unified offline":        "#dc3545", # Vermelho
    "Unified transfers only": "#17a2b8", # Azul claro (ou outro para diferenciar)
    # Adicione outras cores se houver outros estados que possam aparecer e você queira colorir
    # "Outro Estado": "#6c757d", # Cinza
}

# Cores para o tema claro e escuro (se aplicável, para consistência)
CORES_TEMA = {
    "fundo_claro": "#ffffff",
    "fundo_escuro": "#343a40",
    "texto_claro": "#212529",
    "texto_escuro": "#f8f9fa",
}
