# config.py

HISTORICO_PATH = "historico_status.parquet"
ESCALA_PATH    = "escala_agentes.parquet"

PALETA_STATUS = {
    "Online":                        "#2ecc71", # Verde
    "Unified online":                "#2ecc71", # Verde
    "Away":                          "#e67e22", # Laranja
    "Unified away":                  "#e67e22", # Laranja
    "Offline":                       "#e74c3c", # Vermelho
    "Unified offline":               "#e74c3c", # Vermelho
    "Disconnected":                  "#e74c3c", # Vermelho
    "Break":                         "#f1c40f", # Amarelo
    "Lunch":                         "#f1c40f", # Amarelo
    "Meeting":                       "#3498db", # Azul
    "Training":                      "#9b59b6", # Roxo
    "Backoffice":                    "#1abc9c", # Turquesa
    "Outros":                        "#bdc3c7", # Cinza claro
    "Invisible":                     "#7f8c8d", # Cinza escuro (para ser excluído)
    "Aguardando":                    "#34495e", # Azul escuro
    "Pausa para o café":             "#f1c40f", # Amarelo
    "Pausa para o almoço":           "#f1c40f", # Amarelo
    "Treinamento":                   "#9b59b6", # Roxo
    "Reunião":                       "#3498db", # Azul
    "Ausente":                       "#e67e22", # Laranja
    "Atendimento":                   "#2ecc71", # Verde
    "Disponível":                    "#2ecc71", # Verde
    "Indisponível":                  "#e74c3c", # Vermelho

 
}

# Estados que são considerados produtivos para o cálculo de aderência
ESTADOS_PRODUTIVOS = [
    "Online",
    "Unified online",
    "Atendimento",
    "Disponível",
    "Em atendimento",
    "Em ligação",
    "Em chat",
    "Em email",
    "Em tarefa",
    "Pós-atendimento",
    "Trabalhando",
]

# Estados que são considerados pausas (não produtivos, mas esperados)
ESTADOS_PAUSA = [
    "Away",
    "Unified away",
    "Break",
    "Lunch",
    "Pausa para o café",
    "Pausa para o almoço",
    "Ausente",
    "Em espera",
    "Descanso",
    "Pausa",
]

# Estados que são considerados fora (não produtivos e não esperados)
ESTADOS_FORA = [
    "Offline",
    "Unified offline",
    "Disconnected",
    "Meeting",
    "Training",
    "Backoffice",
    "Outros",
    "Fora do horário",
    "Férias",
    "Feriado",
    "Folga",
    "Licença",
    "Atestado",
    "Desconectado",
    "Logoff",
    "Reunião",
    "Treinamento",
]

# Estados a serem excluídos completamente da análise
ESTADOS_EXCLUIR = [
    "Invisible",
    "Unified transfers only", # Adicionado para excluir estados de transferência
]

DIAS_SEMANA_ORDEM = [
    "Segunda-feira",
    "Terça-feira",
    "Quarta-feira",
    "Quinta-feira",
    "Sexta-feira",
    "Sábado",
    "Domingo",
]
