HISTORICO_PATH = "historico_status.parquet"
ESCALA_PATH    = "escala_agentes.parquet"

PALETA_STATUS = {
    "Online":                        "#2ecc71",
    "Away":                          "#e67e22",
    "Offline":                       "#95a5a6",
    "Disconnected":                  "#e74c3c",
    "Descanso 1":                    "#9b59b6",
    "Descanso 2":                    "#8e44ad",
    "Almoço":                        "#f39c12",
    "Lanche":                        "#e67e22",
    "Pausa Pessoal":                 "#3498db",
    "Feedback":                      "#1abc9c",
    "Categorização de atendimentos": "#16a085",
    "Transfers only":                "#27ae60",
    "Unified online":                "#27ae60",
    "Unified away":                  "#d35400",
    "Unified offline":               "#7f8c8d",
    "Invisible":                     "#bdc3c7",
}

ESTADOS_PRODUTIVOS = ["Online", "Transfers only", "Unified online"]
ESTADOS_PAUSA = [
    "Away", "Descanso 1", "Descanso 2", "Almoço",
    "Lanche", "Pausa Pessoal", "Feedback",
    "Categorização de atendimentos","Unified away",
]
ESTADOS_FORA    = ["Unified offline","Offline", "Disconnected"]
ESTADOS_EXCLUIR = [
    "Invisible",
]

DIAS_SEMANA_ORDEM = [
    "Segunda-feira", "Terça-feira", "Quarta-feira",
    "Quinta-feira",  "Sexta-feira", "Sábado", "Domingo",
]
