"""
Módulo de configurações da simulação urbana.

Este módulo centraliza todas as constantes usadas pela simulação:
- Parâmetros de tela
- Definições de cores
- Dimensões e assets
- Parâmetros de comportamento (carros/pedestres)
- Pontos de passagem (waypoints), zonas de passadeira e mapas de rota

As constantes aqui permitam ajustar facilmente a simulação sem tocar no
código dos agentes ou da parte gráfica.
"""

# --- CONFIGURAções DA TELA ---
"""Dimensões da janela de simulação (largura, altura) em pixels."""
LARGURA_TELA = 720
ALTURA_TELA = 720

# --- CORES (Padrão RGB) ---
"""Paleta de cores usada para veículos, semáforos e elementos gráficos."""
COR_CARRO_1 = (255, 0, 0)
COR_SEMAFORO_VERMELHO = (255, 0, 0)
COR_SEMAFORO_VERDE = (0, 255, 0)
COR_SEMAFORO_AMARELO = (255, 255, 0)
COR_SEMAFORO_DESLIGADO = (50, 50, 50)
COR_LINHA_PARADA = (255, 255, 0)

# --- ASSETS (IMAGENS E OBJETOS) ---
"""Dimensões visuais dos veículos (largura, altura) em pixels."""
LARGURA_CARRO = 40
ALTURA_CARRO = 80

# --- CONSTANTES PARA COMPORTAMENTO COOPERATIVO ---
"""Parâmetros que regem decisões de parada e troca de faixa."""
DISTANCIA_SEGURA_SEMAFORO = ALTURA_CARRO * 0.5
DISTANCIA_VERIFICACAO_TROCA_FAIXA = ALTURA_CARRO * 2.5
TEMPO_ESPERA_TROCA_FAIXA = 0.5

# --- CONFIGURAÇÕES PARA PEDESTRES ---
"""Parâmetros visuais e de colisão dos pedestres."""
RAIO_PESSOA = 8
COR_PESSOA_1 = (50, 150, 255)
COR_PESSOA_2 = (255, 105, 180)
COR_COLISAO_PESSOA = (255, 255, 0)
COR_PESSOA_ESPERANDO = (200, 200, 200)

# --- CORES PARA VISUALIZAÇÃO (MODO DEBUG) ---
"""Cores auxiliares para desenhar pontos, textos e caminhos em modo debug."""
COR_PONTO_PASSAGEM = (255, 255, 255)
COR_TEXTO_PONTO_PASSAGEM = (255, 200, 200)
COR_CAMINHO = (100, 100, 100)

# --- CORES PARA VISUALIZAÇÃO DAS ROTAS DOS CARROS ---
"""Cores usadas para exibir pontos e caminhos específicos dos carros."""
COR_PONTO_CARRO = (173, 216, 230)
COR_TEXTO_PONTO_CARRO = (200, 255, 200)
COR_CAMINHO_CARRO = (70, 70, 130)

# --- POSIÇÕES FIXAS NO MAPA ---
"""Posições (x, y) fixas dos semáforos no mapa da simulação."""
POSICAO_SEMAFORO_VERTICAL = (470, 420)
POSICAO_SEMAFORO_HORIZONTAL = (470, 280)

# --- PONTOS DE ESPERA / INTERESSE ---
"""Lista de pontos de espera de pedestres (nomes de waypoints)."""
PONTOS_ESPERA_PEDESTRE = ["P1", "P4", "P2", "P3"]

# --- ZONAS DE PASSADEIRA (RECT: Xmin, Xmax, Ymin, Ymax) ---
"""Definição das zonas de passadeira com coordenadas retangulares.
Cada zona é usada para que agentes avaliem se há pedestres numa faixa de travessia.
"""
ZONA_PASSADEIRA_1 = (195 - 15, 195 + 15, 243, 449)
ZONA_PASSADEIRA_2 = (520 - 15, 520 + 15, 235, 449)
ZONA_PASSADEIRA_3 = (195, 520, 449 - 15, 449 + 15)
ZONA_PASSADEIRA_4 = (195, 520, 235 - 15, 243 + 15)

# --- PONTOS DE AVALIAÇÃO (antes da passadeira) ---
"""Waypoints que os carros usam para verificar presença de pedestres."""
PONTOS_AVALIACAO_CARRO_V = ["V_MID_L", "V_MID_C", "V_MID_R", "V_EVAL_C", "V_EVAL_R"]
PONTOS_AVALIACAO_CARRO_H = ["H_MID_L", "H_MID_R", "PX1_EVAL_H", "PX1_EVAL_V"]
PONTOS_AVALIACAO_CARRO = PONTOS_AVALIACAO_CARRO_V + PONTOS_AVALIACAO_CARRO_H

# --- MAPEAMENTO ENTRE PONTOS DE AVALIAÇÃO E ZONAS ---
"""Dicionário que associa cada ponto de avaliação à zona de passadeira relevante."""
MAPA_AVALIACAO_PASSADEIRA = {
    "PX1_EVAL_H": ZONA_PASSADEIRA_1,
    "PX1_EVAL_V": ZONA_PASSADEIRA_1,
    "H_MID_L": ZONA_PASSADEIRA_2,
    "H_MID_R": ZONA_PASSADEIRA_2,
    "V_MID_L": ZONA_PASSADEIRA_3,
    "V_MID_C": ZONA_PASSADEIRA_3,
    "V_MID_R": ZONA_PASSADEIRA_3,
    "V_EVAL_C": ZONA_PASSADEIRA_4,
    "V_EVAL_R": ZONA_PASSADEIRA_4,
}

# --- DISTÂNCIAS DE SEGURANÇA ---
"""Distâncias usadas para avaliação de risco entre carros e pedestres."""
# CORREÇÃO: Aumentado de 100 para 150.
# Os 100 originais eram muito curtos; o pedestre em X=195
# nunca via o carro em X=300 (distância de 105).
DISTANCIA_SEGURA_CARRO_PEDESTRE = 150
DISTANCIA_PARAR_CARRO = 15

# --- NOMES CONSISTENTES PARA CREDENCIAS / GOALS ---
"""Strings constantes usadas como nomes de crenças e objetivos (mantém consistência)."""
NOME_OBJECTIVO_PEDESTRE_ATRAVESSAR = "objectivo_atravessar_em_seguranca"
NOME_CRENCA_PEDESTRE_PODE_ATRAVESSAR = "crenca_passagem_segura"
NOME_GOAL_PEDESTRE_PEDE_PASSAGEM = "pedido_travessia_pedestre"
NOME_CRENCA_CARRO_PEDESTRE_PEDINDO = "crenca_pedestre_pedindo_travessia"
NOME_CRENCA_CARRO_CEDENDO = "crenca_cedendo_passagem_a"
NOME_CRENCA_RESPOSTA_CARRO = "resposta_carro_travessia"

# --- PONTOS DE PASSAGEM PARA PEDESTRES (WAYPOINTS) ---
"""Mapa de nomes -> coordenadas para pontos utilizados por pedestres no grafo."""
PONTOS_DE_PASSAGEM_PEDESTRES = {
    "P1": (195, 449), "P2": (520, 449), "P3": (520, 235),
    "P4": (195, 243), "P5": (5, 244),   "P6": (195, 10),
    "P7": (711, 248), "P8": (510, 10),  "P9": (195, 690),
    "P10": (5, 449),  "P11": (715, 449),"P12": (520, 689),
}

# --- CAMINHOS (GRAFO) PARA PEDESTRES ---
"""Define, para cada waypoint de pedestre, os destinos possíveis (arestas do grafo)."""
CAMINHOS_PEDESTRES = {
    "P1": ["P4", "P2", "P9", "P10"],
    "P2": ["P3", "P1", "P11", "P12"],
    "P3": ["P2", "P4", "P7", "P8"],
    "P4": ["P1", "P3", "P5", "P6"],
    "P5": ["P4"], "P6": ["P4"], "P7": ["P3"], "P8": ["P3"],
    "P9": ["P1"], "P10": ["P1"], "P11": ["P2"], "P12": ["P2"],
}

# --- PONTOS DE PASSAGEM PARA CARROS ---
"""Mapa de waypoints para rotas de veículos; inclui pontos de início, mudança, avaliação e fim."""
PONTOS_DE_PARADA = ["V_MID_L", "V_MID_C", "V_MID_R", "H_MID_L", "H_MID_R"]
PONTOS_INICIAIS_VERTICAIS = ["V_START_L", "V_START_C", "V_START_R"]
PONTOS_INICIAIS_HORIZONTAIS = ["H_START_R", "H_START_L"]

PONTOS_DE_PASSAGEM_CARROS = {
    "V_START_L": (300, 720), "V_START_C": (360, 720), "V_START_R": (420, 720),
    "V_CHANGE_L": (300, 600), "V_CHANGE_C": (360, 600), "V_CHANGE_R": (420, 600),
    "V_MID_L": (300, 490), "V_MID_C": (360, 490), "V_MID_R": (420, 490),
    "V_INT_L": (300, 387), "V_INT_C": (360, 387), "V_INT_R": (420, 387),
    "V_EVAL_C": (360, 300), "V_EVAL_R": (420, 300),
    "V_END_C": (360, 0), "V_END_R": (420, 0),
    "H_START_R": (720, 348), "H_START_L": (719, 387),
    "H_CHANGE_R": (650, 348), "H_CHANGE_L": (650, 387),
    "H_MID_R": (550, 348), "H_MID_L": (550, 387),
    "H_INT_R": (420, 348), "H_INT_L": (420, 387),
    "PX1_EVAL_H": (240, 387), "PX1_EVAL_V": (240, 387),
    "H_END_L": (0, 387),
}

# --- CAMINHOS (GRAFO) PARA CARROS ---
"""Define as conexões entre waypoints de veículos (direção do fluxo)."""
CAMINHOS_CARROS = {
    "V_START_L": ["V_CHANGE_L"], "V_START_C": ["V_CHANGE_C"], "V_START_R": ["V_CHANGE_R"],
    "V_CHANGE_L": ["V_MID_L", "V_CHANGE_C"],
    "V_CHANGE_C": ["V_MID_C", "V_CHANGE_L", "V_CHANGE_R"],
    "V_CHANGE_R": ["V_MID_R", "V_CHANGE_C"],
    "V_MID_L": ["V_INT_L"], "V_MID_C": ["V_INT_C"], "V_MID_R": ["V_INT_R"],
    "V_INT_L": ["PX1_EVAL_V"],
    "V_INT_C": ["V_EVAL_C"],
    "V_INT_R": ["V_EVAL_R"],
    "V_EVAL_C": ["V_END_C"],
    "V_EVAL_R": ["V_END_R"],
    "H_START_R": ["H_CHANGE_R"], "H_START_L": ["H_CHANGE_L"],
    "H_CHANGE_R": ["H_MID_R", "H_CHANGE_L"],
    "H_CHANGE_L": ["H_MID_L", "H_CHANGE_R"],
    "H_MID_R": ["H_INT_R"],
    "H_MID_L": ["H_INT_L"],
    "H_INT_R": ["V_END_R"],
    "H_INT_L": ["PX1_EVAL_H"],
    "PX1_EVAL_H": ["H_END_L"],
    "PX1_EVAL_V": ["H_END_L"],
    "V_END_C": [], "V_END_R": [], "H_END_L": [],
}

# --- ÁREA GLOBAL DE PASSADEIRAS (PARÂMETROS AUXILIARES) ---
"""Intervalo Y usado por agentes para verificar se um pedestre está na passadeira.
Este valor é calculado a partir das zonas de passadeira definidas acima e serve
como verificação simples (pode ser ajustado conforme o mapa)."""
AREA_PASSADEIRA_Y_MIN = 220
AREA_PASSADEIRA_Y_MAX = 464