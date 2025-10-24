"""
Script principal que inicializa a simulação gráfica com Pygame e a camada de agentes.

Funcionalidades:
- Instancia o Admin do maspy e cria uma thread dedicada ao sistema de agentes.
- Carrega recursos gráficos (plano de fundo, sprites de carro).
- Cria representações visuais (VisualCarro, VisualPessoa, VisualSemaforo).
- Sincroniza o estado compartilhado (posições, semáforos) entre threads.
- Loop principal de renderização e atualização, com verificação de colisões visuais.
"""

import pygame
import threading
import os
import time
import random
from maspy import *
from src.settings import *
from src.agents_graphical import ControladorDeCruzamento, AgenteCarro, AgentePessoa

# --- ESTADO COMPARTILHADO ENTRE THREADS ---
"""Dicionário e lock usados para compartilhar posições e estados entre a thread MAS e o loop gráfico."""
estado_compartilhado = {
    "estado_semaforo_v": "red",
    "estado_semaforo_h": "red",
}
lock_estado = threading.Lock()

# --- PARÂMETROS DE SIMULAÇÃO (NÚMERO DE AGENTES) ---
"""Número de carros e pedestres a instanciar no sistema de agentes."""
NUM_CARROS = 3
NUM_PESSOAS = 2

def executar_sistema_de_agentes(admin_instance):
    """
    Função a ser executada na thread de lógica (MASPY).
    Cria o ambiente controlador, canais e instâncias de agentes (carros e pessoas),
    conecta-os ao Admin e inicia o sistema.
    """
    ambiente_cruzamento = ControladorDeCruzamento("Cruzamento")
    ambiente_cruzamento.setup(estado_compartilhado=estado_compartilhado, lock=lock_estado)
    canal_travessia = Channel("Travessia")

    carros = []
    pontos_inicio_carro = PONTOS_INICIAIS_VERTICAIS + PONTOS_INICIAIS_HORIZONTAIS
    for i in range(NUM_CARROS):
        ponto_inicial = random.choice(pontos_inicio_carro)
        while ponto_inicial not in PONTOS_DE_PASSAGEM_CARROS:
            print(f"Ponto inicial de carro '{ponto_inicial}' inválido. Escolhendo outro.")
            ponto_inicial = random.choice(pontos_inicio_carro)
        
        carro = AgenteCarro(
            name="Carro", ponto_inicial=ponto_inicial, velocidade=random.uniform(4, 6),
            estado_compartilhado=estado_compartilhado, lock=lock_estado
        )
        
        carros.append(carro)
        admin_instance.connect_to(carro, ambiente_cruzamento)
        admin_instance.connect_to(carro, canal_travessia)

    pessoas = []
    pontos_inicio_pessoa = ["P1", "P6", "P9", "P11"]
    for i in range(NUM_PESSOAS):
        ponto_inicial = random.choice(pontos_inicio_pessoa)
        while ponto_inicial not in PONTOS_DE_PASSAGEM_PEDESTRES:
            print(f"Ponto inicial de pessoa '{ponto_inicial}' inválido. Escolhendo outro.")
            ponto_inicial = random.choice(pontos_inicio_pessoa)
            
        pessoa = AgentePessoa(
            name="Pessoa", ponto_inicial=ponto_inicial, velocidade=random.uniform(1.5, 2.5),
            estado_compartilhado=estado_compartilhado, lock=lock_estado
        )
        
        pessoas.append(pessoa)
        admin_instance.connect_to(pessoa, canal_travessia)
        admin_instance.connect_to(pessoa, ambiente_cruzamento)

    admin_instance.start_system()

# --- CLASSES VISUAIS ---
"""Representações gráficas simples usadas pelo loop Pygame."""
class VisualCarro:
    """Representação gráfica de um carro (sprite ou retângulo fallback)."""
    def __init__(self, x, y, cor=COR_CARRO_1, caminho_imagem='assets/carro_vermelho.png'):
        try:
            self.imagem = pygame.image.load(os.path.join(caminho_imagem)).convert_alpha()
            self.imagem = pygame.transform.scale(self.imagem, (LARGURA_CARRO, ALTURA_CARRO))
        except Exception:
            self.imagem = pygame.Surface((LARGURA_CARRO, ALTURA_CARRO), pygame.SRCALPHA)
            self.imagem.fill(cor)
        self.rect = self.imagem.get_rect(center=(x, y))
        self.id_agente_completo = ""

    def update(self, nova_posicao):
        """Atualiza a posição visual com base nas coordenadas fornecidas."""
        if nova_posicao:
            if isinstance(nova_posicao, (tuple, list)) and len(nova_posicao) == 2 and all(isinstance(coord, (int, float)) for coord in nova_posicao):
                self.rect.center = tuple(map(int, nova_posicao))

    def draw(self, tela):
        """Desenha o sprite do carro na tela."""
        tela.blit(self.imagem, self.rect)

class VisualSemaforo:
    """Representação gráfica de um semáforo com três luzes (r, y, g)."""
    def __init__(self, x, y):
        self.estado = 'red'
        self.rect = pygame.Rect(x, y, 15, 40)
        self.cores = {"vermelho": COR_SEMAFORO_VERMELHO, "amarelo": COR_SEMAFORO_AMARELO, "verde": COR_SEMAFORO_VERDE}

    def update(self, novo_estado):
        """Atualiza o estado interno do semáforo para renderização."""
        if novo_estado:
            self.estado = novo_estado

    def draw(self, tela):
        """Desenha a carcaça do semáforo e as três luzes conforme o estado atual."""
        pygame.draw.rect(tela, (30, 30, 30), self.rect)
        cor_vermelha = self.cores["vermelho"] if self.estado == "vermelho" else COR_SEMAFORO_DESLIGADO
        cor_amarela = self.cores["amarelo"] if self.estado == "amarelo" else COR_SEMAFORO_DESLIGADO
        cor_verde = self.cores["verde"] if self.estado == "verde" else COR_SEMAFORO_DESLIGADO
        pygame.draw.circle(tela, cor_vermelha, (self.rect.centerx, self.rect.y + 10), 5)
        pygame.draw.circle(tela, cor_amarela, (self.rect.centerx, self.rect.y + 20), 5)
        pygame.draw.circle(tela, cor_verde, (self.rect.centerx, self.rect.y + 30), 5)

class VisualPessoa:
    """Representação gráfica de um pedestre (círculo) com estado de colisão/espera."""
    def __init__(self, x, y, cor):
        self.cor_original = cor
        self.raio = RAIO_PESSOA
        self.rect = pygame.Rect(x - self.raio, y - self.raio, self.raio * 2, self.raio * 2)
        self.colidiu = False
        self.tempo_colisao = 0
        self.id_agente_completo = ""
        self.esta_esperando = False

    def update(self, nova_posicao, esta_esperando=False):
        """Atualiza posição e estado de espera; decrementa temporizador de colisão."""
        if nova_posicao:
            if isinstance(nova_posicao, (tuple, list)) and len(nova_posicao) == 2 and all(isinstance(coord, (int, float)) for coord in nova_posicao):
                self.rect.center = tuple(map(int, nova_posicao))
        self.esta_esperando = esta_esperando
        if self.colidiu:
            self.tempo_colisao -= 1
            if self.tempo_colisao <= 0:
                self.colidiu = False

    def draw(self, tela):
        """Desenha o pedestre (cor muda se colisão/espera)."""
        cor_actual = COR_COLISAO_PESSOA if self.colidiu else COR_PESSOA_ESPERANDO if self.esta_esperando else self.cor_original
        pygame.draw.circle(tela, cor_actual, self.rect.center, self.raio)

    def registrar_colisao(self):
        """Marca o pedestre como colidido e define o tempo de exibição do estado."""
        self.colidiu = True
        self.tempo_colisao = 60

"""Funções utilitárias para desenhar os grafos de waypoints e ajudar no debug visual."""
def desenhar_pontos_de_passagem(tela, fonte):
    for ponto_inicio, conexoes in CAMINHOS_PEDESTRES.items():
        if ponto_inicio not in PONTOS_DE_PASSAGEM_PEDESTRES:
            continue
        pos_inicio = PONTOS_DE_PASSAGEM_PEDESTRES[ponto_inicio]
        for ponto_fim in conexoes:
            if ponto_fim in PONTOS_DE_PASSAGEM_PEDESTRES:
                pos_fim = PONTOS_DE_PASSAGEM_PEDESTRES[ponto_fim]
                pygame.draw.line(tela, COR_CAMINHO, pos_inicio, pos_fim, 1)
    for nome, pos in PONTOS_DE_PASSAGEM_PEDESTRES.items():
        pygame.draw.circle(tela, COR_PONTO_PASSAGEM, pos, 5)
        texto = fonte.render(nome, True, COR_TEXTO_PONTO_PASSAGEM)
        tela.blit(texto, (pos[0] + 8, pos[1] - 8))

def desenhar_pontos_de_passagem_carros(tela, fonte):
    for ponto_inicio, conexoes in CAMINHOS_CARROS.items():
        if ponto_inicio not in PONTOS_DE_PASSAGEM_CARROS:
            continue
        pos_inicio = PONTOS_DE_PASSAGEM_CARROS[ponto_inicio]
        for ponto_fim in conexoes:
            if ponto_fim in PONTOS_DE_PASSAGEM_CARROS:
                pos_fim = PONTOS_DE_PASSAGEM_CARROS[ponto_fim]
                pygame.draw.line(tela, COR_CAMINHO_CARRO, pos_inicio, pos_fim, 1)
    for nome, pos in PONTOS_DE_PASSAGEM_CARROS.items():
        pygame.draw.circle(tela, COR_PONTO_CARRO, pos, 4)
        texto = fonte.render(nome, True, COR_TEXTO_PONTO_CARRO)
        tela.blit(texto, (pos[0] + 8, pos[1] - 8))

"""Inicializa o Pygame, carrega recursos, cria visuais e executa o loop principal."""
def main():
    admin = Admin()
    thread_agentes = None
    if not any(t.name == 'Thread-Agentes' for t in threading.enumerate()):
        thread_agentes = threading.Thread(target=executar_sistema_de_agentes, args=(admin,), daemon=False, name='Thread-Agentes')
        thread_agentes.start()
    else:
        print("Thread dos agentes já está em execução.")

    print("DEBUG: Esperando agentes inicializarem...")
    time.sleep(1.5)

    pygame.init()
    fonte_debug = pygame.font.Font(None, 16)
    tela = pygame.display.set_mode((LARGURA_TELA, ALTURA_TELA))
    pygame.display.set_caption("Simulação com Negociação Veículo-Pedestre")
    clock = pygame.time.Clock()

    try:
        imagem_fundo = pygame.image.load('assets/mapa_cidade.jpg').convert()
        imagem_fundo = pygame.transform.scale(imagem_fundo, (LARGURA_TELA, ALTURA_TELA))
    except Exception as e:
        print(f"Erro ao carregar imagem: {e}.")
        imagem_fundo = pygame.Surface((LARGURA_TELA, ALTURA_TELA))
        imagem_fundo.fill((25, 25, 25))

    visuais_carros = []
    cores_carros = [(0,0,255), (0,150,150), (150,0,150)]
    with lock_estado:
        estado_inicial_carros = estado_compartilhado.copy()
    for i in range(NUM_CARROS):
        id_agente_completo = f"Carro_{i+1}"
        
        pos_inicial = estado_inicial_carros.get(f"{id_agente_completo}_pos")
        if pos_inicial:
            cor = cores_carros[i % len(cores_carros)]
            vis_carro = VisualCarro(pos_inicial[0], pos_inicial[1], cor=cor)
            vis_carro.id_agente_completo = id_agente_completo
            visuais_carros.append(vis_carro)
        else:
            print(f"Pos inicial NÃO encontrada para {id_agente_completo}!!!")
            vis_carro = VisualCarro(-100, -100, cor=cores_carros[i % len(cores_carros)])
            vis_carro.id_agente_completo = id_agente_completo
            visuais_carros.append(vis_carro)

    visuais_pessoas = []
    cores_pessoas = [COR_PESSOA_1, COR_PESSOA_2]
    with lock_estado:
        estado_inicial_pessoas = estado_compartilhado.copy()
    for i in range(NUM_PESSOAS):
        id_agente_completo = f"Pessoa_{i+1}"
        
        pos_inicial = estado_inicial_pessoas.get(f"{id_agente_completo}_pos")
        if pos_inicial:
            cor = cores_pessoas[i % len(cores_pessoas)]
            vis_pessoa = VisualPessoa(pos_inicial[0], pos_inicial[1], cor)
            vis_pessoa.id_agente_completo = id_agente_completo
            visuais_pessoas.append(vis_pessoa)
        else:
            print(f"Pos inicial NÃO encontrada para {id_agente_completo}!!!")
            vis_pessoa = VisualPessoa(-100,-100, cor=cores_pessoas[i % len(cores_pessoas)])
            vis_pessoa.id_agente_completo = id_agente_completo
            visuais_pessoas.append(vis_pessoa)

    visual_semaforo_v = VisualSemaforo(POSICAO_SEMAFORO_VERTICAL[0], POSICAO_SEMAFORO_VERTICAL[1])
    visual_semaforo_h = VisualSemaforo(POSICAO_SEMAFORO_HORIZONTAL[0], POSICAO_SEMAFORO_HORIZONTAL[1])

    executando = True
    while executando:
        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                executando = False
            if evento.type == pygame.MOUSEBUTTONDOWN:
                print(f"Coordenadas: {pygame.mouse.get_pos()}")

        estado_actual = {}
        with lock_estado:
            estado_actual = estado_compartilhado.copy()

        visual_semaforo_v.update(estado_actual.get("estado_semaforo_v"))
        visual_semaforo_h.update(estado_actual.get("estado_semaforo_h"))

        for vis_carro in visuais_carros:
            posicao = estado_actual.get(f"{vis_carro.id_agente_completo}_pos")
            vis_carro.update(posicao)

        for vis_pessoa in visuais_pessoas:
            posicao = estado_actual.get(f"{vis_pessoa.id_agente_completo}_pos")
            esta_esperando = False
            partes_nome = vis_pessoa.id_agente_completo.split('_')
            
            if len(partes_nome) >= 2:
                nome_base = partes_nome[0]
                try:
                    indice_num = int(partes_nome[1])
                    agente_key = (nome_base, indice_num)
                    if 'admin' in locals() and hasattr(admin, '_agents') and agente_key in admin._agents:
                        agente_pessoa = admin._agents.get(agente_key)
                        if agente_pessoa and isinstance(agente_pessoa, AgentePessoa):
                            esta_esperando = agente_pessoa.has(Belief("crenca_aguardando_resposta_carro")) or \
                                             (agente_pessoa.ponto_atual in PONTOS_ESPERA_PEDESTRE and \
                                              not agente_pessoa.has(Belief(NOME_CRENCA_PEDESTRE_PODE_ATRAVESSAR)) and \
                                              not agente_pessoa.has(Goal("pedir_permissao_travessia")))
                except (ValueError, IndexError):
                    pass
            vis_pessoa.update(posicao, esta_esperando)

        for vis_carro in visuais_carros:
            for vis_pessoa in visuais_pessoas:
                if hasattr(vis_carro, 'rect') and hasattr(vis_pessoa, 'rect') and vis_carro.rect.colliderect(vis_pessoa.rect) and not vis_pessoa.colidiu:
                    print(f"COLISÃO: {vis_carro.id_agente_completo} e {vis_pessoa.id_agente_completo}!")
                    vis_pessoa.registrar_colisao()

        tela.blit(imagem_fundo, (0, 0))
        desenhar_pontos_de_passagem(tela, fonte_debug)
        desenhar_pontos_de_passagem_carros(tela, fonte_debug)
        visual_semaforo_v.draw(tela)
        visual_semaforo_h.draw(tela)
        for vis_carro in visuais_carros:
            vis_carro.draw(tela)
        for vis_pessoa in visuais_pessoas:
            vis_pessoa.draw(tela)
        pygame.display.flip()
        clock.tick(60)

    try:
        admin.stop_all_agents()
        print("Agentes parados.")
        if thread_agentes:
            thread_agentes.join() 
        print("Thread do admin finalizada.")
    except Exception as e:
        print(f"Erro ao parar: {e}")
    finally:
        pygame.quit() 

if __name__ == '__main__':
    if not os.path.exists('assets'):
        os.makedirs('assets')
    if not os.path.exists('src'):
        os.makedirs('src')
    main()