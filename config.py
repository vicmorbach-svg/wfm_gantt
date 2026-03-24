# config.py
import pandas as pd

# Ordem dos dias da semana para exibição
DIAS_SEMANA_ORDEM = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]

# Estados de interesse para o relatório
ESTADOS_INTERESSE = [
    "Unified online",
    "Unified away",
    "Unified offline",
    "Unified transfers only",
]

# Estados a serem excluídos (agora vazia, conforme solicitado)
ESTADOS_EXCLUIR = []

# Mapeamento de cores para os estados
CORES_STATUS = {
    "Unified online":         "#28a745", # Verde
    "Unified away":           "#ffc107", # Amarelo
    "Unified offline":        "#dc3545", # Vermelho
    "Unified transfers only": "#17a2b8", # Azul claro
    # Adicione outras cores se necessário para estados que possam aparecer mas não são de interesse principal
}

# Limite de alerta para o tempo em "away" (em minutos)
LIMITE_ALERTA_AWAY = 30
