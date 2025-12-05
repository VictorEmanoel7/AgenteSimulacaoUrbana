"""
Script principal de inicialização da simulação.

Este módulo é responsável por:
1. Inicializar a interface gráfica com Pygame.
2. Gerenciar a thread lógica dos agentes (MASPY).
3. Sincronizar o estado dos agentes (posições, semáforos) com a visualização.
4. Gerenciar o loop principal de renderização e eventos.
"""

import pygame
import threading
import os
import time
import random
import math
from maspy import *
from src.settings import *
from src.agents_graphical import ControladorDeCruzamento, AgenteCarro, AgentePessoa

estado_compartilhado = {
    "estado_semaforo_v": "red",
    "estado_semaforo_h": "red",
    "simulacao_ativa": True
}
lock_estado = threading.Lock()

NUM_CARROS = 3
NUM_PESSOAS = 2

class VisualCarro:
    """
    Representação gráfica de um veículo.
    Gerencia o carregamento de sprites, interpolação de movimento suave e
    rotação da imagem baseada na direção.
    """
    def __init__(self, x, y, cor=COR_CARRO_1, caminho_imagem='assets/carro_vermelho.png'):
        try:
            self.imagem_original = pygame.image.load(os.path.join(caminho_imagem)).convert_alpha()
            self.imagem_original = pygame.transform.scale(self.imagem_original, (LARGURA_CARRO, ALTURA_CARRO))
        except Exception:
            self.imagem_original = pygame.Surface((LARGURA_CARRO, ALTURA_CARRO), pygame.SRCALPHA)
            self.imagem_original.fill(cor)
            
        self.imagem = self.imagem_original.copy()
        self.rect = self.imagem.get_rect(center=(x, y))
        self.id_agente_completo = ""
        self.angulo_atual = 0.0
        self.angulo_alvo = 0.0

    def set_angulo_inicial(self, angulo):
        """Define o ângulo inicial do veículo sem interpolação."""
        if angulo is None: angulo = 0.0
        self.angulo_atual = float(angulo)
        self.angulo_alvo = float(angulo)

    def update(self, nova_posicao, novo_angulo_alvo):
        """
        Atualiza a posição do retângulo e calcula a interpolação (Lerp) 
        para suavizar a rotação visual do veículo.
        """
        if nova_posicao and isinstance(nova_posicao, (tuple, list)) and len(nova_posicao) == 2:
            self.rect.center = tuple(map(int, nova_posicao))
        
        if novo_angulo_alvo is not None:
            self.angulo_alvo = float(novo_angulo_alvo)
        
        curr = self.angulo_atual if self.angulo_atual is not None else 0.0
        targ = self.angulo_alvo if self.angulo_alvo is not None else 0.0
        
        diff = (targ - curr + 180) % 360 - 180
        taxa_rotacao = 0.15 
        if abs(diff) < 0.5: self.angulo_atual = targ
        else:
            self.angulo_atual = curr + diff * taxa_rotacao
            self.angulo_atual %= 360

    def draw(self, tela):
        """Desenha a imagem rotacionada na tela."""
        self.imagem = pygame.transform.rotate(self.imagem_original, self.angulo_atual)
        novo_rect = self.imagem.get_rect(center=self.rect.center)
        tela.blit(self.imagem, novo_rect)

class VisualSemaforo:
    """
    Representação gráfica de um semáforo.
    Desenha a caixa e as luzes coloridas baseadas no estado atual.
    """
    def __init__(self, x, y):
        self.estado = 'red'
        self.rect = pygame.Rect(x, y, 15, 40)
        self.cores = {"vermelho": COR_SEMAFORO_VERMELHO, "amarelo": COR_SEMAFORO_AMARELO, "verde": COR_SEMAFORO_VERDE}

    def update(self, novo_estado):
        """Atualiza a cor ativa do semáforo."""
        if novo_estado: self.estado = novo_estado

    def draw(self, tela):
        """Renderiza o corpo do semáforo e as luzes ativas/inativas."""
        pygame.draw.rect(tela, (30, 30, 30), self.rect)
        cor_vermelha = self.cores["vermelho"] if self.estado == "vermelho" else COR_SEMAFORO_DESLIGADO
        cor_amarela = self.cores["amarelo"] if self.estado == "amarelo" else COR_SEMAFORO_DESLIGADO
        cor_verde = self.cores["verde"] if self.estado == "verde" else COR_SEMAFORO_DESLIGADO
        pygame.draw.circle(tela, cor_vermelha, (self.rect.centerx, self.rect.y + 10), 5)
        pygame.draw.circle(tela, cor_amarela, (self.rect.centerx, self.rect.y + 20), 5)
        pygame.draw.circle(tela, cor_verde, (self.rect.centerx, self.rect.y + 30), 5)

class VisualPessoa:
    """
    Representação gráfica de um pedestre.
    Gerencia a animação de sprite (troca de passos), rotação baseada no vetor
    de movimento e indicação visual de colisão.
    """
    def __init__(self, x, y, cor):
        self.cor_original = cor
        self.raio = RAIO_PESSOA
        self.colidiu = False
        self.tempo_colisao = 0
        self.id_agente_completo = ""
        self.esta_esperando = False
        self.sprites = []
        self.index_atual = 0
        self.tempo_ultimo_frame = time.time()
        self.intervalo_troca = 0.5
        self.angulo = 0
        
        try:
            caminho_parado = os.path.join('assets', 'pedestre_parado.png')
            caminho_andando = os.path.join('assets', 'pedestre_andando.png')
            img_parado = pygame.image.load(caminho_parado).convert_alpha()
            img_andando = pygame.image.load(caminho_andando).convert_alpha()
            tamanho = int(self.raio * 2.5)
            img_parado = pygame.transform.scale(img_parado, (tamanho, tamanho))
            img_andando = pygame.transform.scale(img_andando, (tamanho, tamanho))
            self.sprites = [img_parado, img_andando]
            self.tem_animacao = True
            
        except Exception as e:
            print(f"Erro ao carregar sprites do pedestre: {e}. Usando modo simples.")
            self.tem_animacao = False
            self.sprites = []

        self.rect = pygame.Rect(x - self.raio, y - self.raio, self.raio * 2, self.raio * 2)
        self.x_anterior = x
        self.y_anterior = y

    def update(self, nova_posicao, esta_esperando=False):
        """
        Calcula a nova posição, determina se houve movimento para ativar a animação
        e calcula o ângulo de rotação do sprite.
        """
        if nova_posicao and isinstance(nova_posicao, (tuple, list)) and len(nova_posicao) == 2:
            novo_x, novo_y = map(int, nova_posicao)
            self.rect.center = (novo_x, novo_y)
            
            if self.tem_animacao:
                dx = novo_x - self.x_anterior
                dy = novo_y - self.y_anterior
                movendo = (abs(dx) > 0 or abs(dy) > 0)
                
                if movendo:
                    self.angulo = math.degrees(math.atan2(-dy, dx)) - 90
                    agora = time.time()
                    if agora - self.tempo_ultimo_frame > self.intervalo_troca:
                        self.index_atual = 1 if self.index_atual == 0 else 0
                        self.tempo_ultimo_frame = agora
                else:
                    self.index_atual = 0
                    
                self.x_anterior = novo_x
                self.y_anterior = novo_y

        self.esta_esperando = esta_esperando
        if self.colidiu:
            self.tempo_colisao -= 1
            if self.tempo_colisao <= 0: self.colidiu = False

    def draw(self, tela):
        """Desenha o sprite animado ou um círculo de fallback caso a imagem falhe."""
        if self.tem_animacao:
            img_original = self.sprites[self.index_atual]
            img_rotacionada = pygame.transform.rotate(img_original, self.angulo)
            rect_draw = img_rotacionada.get_rect(center=self.rect.center)
            tela.blit(img_rotacionada, rect_draw)
            if self.colidiu:
                pygame.draw.circle(tela, COR_COLISAO_PESSOA, self.rect.center, self.raio, 2)
        else:
            cor_actual = COR_COLISAO_PESSOA if self.colidiu else COR_PESSOA_ESPERANDO if self.esta_esperando else self.cor_original
            pygame.draw.circle(tela, cor_actual, self.rect.center, self.raio)

    def registrar_colisao(self):
        """Marca o pedestre como colidido para feedback visual."""
        self.colidiu = True
        self.tempo_colisao = 60

def desenhar_pontos_de_passagem(tela, fonte):
    """Desenha as linhas de rota e os pontos de passagem dos pedestres para debug."""
    for ponto_inicio, conexoes in CAMINHOS_PEDESTRES.items():
        if ponto_inicio not in PONTOS_DE_PASSAGEM_PEDESTRES: continue
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
    """Desenha as linhas de rota e os pontos de passagem dos carros para debug."""
    for ponto_inicio, conexoes in CAMINHOS_CARROS.items():
        if ponto_inicio not in PONTOS_DE_PASSAGEM_CARROS: continue
        pos_inicio = PONTOS_DE_PASSAGEM_CARROS[ponto_inicio]
        for ponto_fim in conexoes:
            if ponto_fim in PONTOS_DE_PASSAGEM_CARROS:
                pos_fim = PONTOS_DE_PASSAGEM_CARROS[ponto_fim]
                pygame.draw.line(tela, COR_CAMINHO_CARRO, pos_inicio, pos_fim, 1)
    for nome, pos in PONTOS_DE_PASSAGEM_CARROS.items():
        pygame.draw.circle(tela, COR_PONTO_CARRO, pos, 4)
        texto = fonte.render(nome, True, COR_TEXTO_PONTO_CARRO)
        tela.blit(texto, (pos[0] + 8, pos[1] - 8))

def main():
    """
    Função principal.
    Inicializa o sistema MASPY em uma thread separada e executa o loop
    principal do Pygame para renderização e controle.
    """
    admin = Admin()
    agentes_carros_ref = []
    agentes_pessoas_ref = []

    def wrapper_executar(admin_inst):
        """Configura e inicia os agentes MASPY."""
        ambiente_cruzamento = ControladorDeCruzamento("Cruzamento")
        ambiente_cruzamento.setup(estado_compartilhado=estado_compartilhado, lock=lock_estado)
        canal_travessia = Channel("Travessia")
        pontos_inicio_carro = PONTOS_INICIAIS_VERTICAIS + PONTOS_INICIAIS_HORIZONTAIS
        for i in range(NUM_CARROS):
            ponto_inicial = random.choice(pontos_inicio_carro)
            while ponto_inicial not in PONTOS_DE_PASSAGEM_CARROS:
                ponto_inicial = random.choice(pontos_inicio_carro)
            c = AgenteCarro(
                name=f"Carro_{i+1}", 
                ponto_inicial=ponto_inicial, 
                velocidade=random.uniform(4, 6),
                estado_compartilhado=estado_compartilhado, 
                lock=lock_estado,
                env_ref=ambiente_cruzamento
            )
            agentes_carros_ref.append(c)
            admin_inst.connect_to(c, ambiente_cruzamento)
            admin_inst.connect_to(c, canal_travessia)

        pontos_inicio_pessoa = ["P1", "P3"]
        for i in range(NUM_PESSOAS):
            ponto_inicial = random.choice(pontos_inicio_pessoa)
            while ponto_inicial not in PONTOS_DE_PASSAGEM_PEDESTRES:
                ponto_inicial = random.choice(pontos_inicio_pessoa)
            p = AgentePessoa(
                name=f"Pessoa_{i+1}", 
                ponto_inicial=ponto_inicial, 
                velocidade=random.uniform(4.0, 6.0),
                estado_compartilhado=estado_compartilhado, 
                lock=lock_estado,
                env_ref=ambiente_cruzamento
            )
            agentes_pessoas_ref.append(p)
            admin_inst.connect_to(p, ambiente_cruzamento)
            admin_inst.connect_to(p, canal_travessia)
        
        admin_inst.start_system()

    thread_agentes = threading.Thread(target=wrapper_executar, args=(admin,), daemon=False, name='Thread-Agentes')
    thread_agentes.start()

    print("DEBUG: Esperando inicialização dos agentes...")
    while len(agentes_carros_ref) < NUM_CARROS or len(agentes_pessoas_ref) < NUM_PESSOAS:
        time.sleep(0.1)
    print(f"DEBUG: Agentes criados! Nomes: {[a.my_name for a in agentes_carros_ref + agentes_pessoas_ref]}")

    pygame.init()
    fonte_debug = pygame.font.Font(None, 16)
    tela = pygame.display.set_mode((LARGURA_TELA, ALTURA_TELA))
    pygame.display.set_caption("Simulação Urbana: Aprendizado Carros e Pedestres")
    clock = pygame.time.Clock()

    try:
        imagem_fundo = pygame.image.load('assets/mapa_cidade.jpg').convert()
        imagem_fundo = pygame.transform.scale(imagem_fundo, (LARGURA_TELA, ALTURA_TELA))
    except Exception:
        imagem_fundo = pygame.Surface((LARGURA_TELA, ALTURA_TELA))
        imagem_fundo.fill((25, 25, 25))

    visuais_carros = []
    cores_carros = [(0,0,255), (0,150,150), (150,0,150)]
    with lock_estado: estado_temp = estado_compartilhado.copy()

    for i, agente_carro in enumerate(agentes_carros_ref):
        id_real = agente_carro.my_name 
        pos_inicial = estado_temp.get(f"{id_real}_pos")
        angulo_inicial = estado_temp.get(f"{id_real}_angle", 0.0)
        cor = cores_carros[i % 3]
        if pos_inicial: vc = VisualCarro(pos_inicial[0], pos_inicial[1], cor=cor)
        else: vc = VisualCarro(-100, -100, cor=cor)
        vc.id_agente_completo = id_real 
        vc.set_angulo_inicial(angulo_inicial)
        visuais_carros.append(vc)

    visuais_pessoas = []
    cores_pessoas = [COR_PESSOA_1, COR_PESSOA_2]
    for i, agente_pessoa in enumerate(agentes_pessoas_ref):
        id_real = agente_pessoa.my_name
        pos_inicial = estado_temp.get(f"{id_real}_pos")
        cor = cores_pessoas[i % 2]
        if pos_inicial: vp = VisualPessoa(pos_inicial[0], pos_inicial[1], cor=cor)
        else: vp = VisualPessoa(-100, -100, cor=cor)
        vp.id_agente_completo = id_real
        visuais_pessoas.append(vp)

    visual_semaforo_v = VisualSemaforo(*POSICAO_SEMAFORO_VERTICAL)
    visual_semaforo_h = VisualSemaforo(*POSICAO_SEMAFORO_HORIZONTAL)

    executando = True
    while executando:
        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                executando = False
                with lock_estado:
                    estado_compartilhado["simulacao_ativa"] = False
                print("DEBUG: Encerrando simulação...")

        estado_actual = {}
        with lock_estado: estado_actual = estado_compartilhado.copy()

        visual_semaforo_v.update(estado_actual.get("estado_semaforo_v"))
        visual_semaforo_h.update(estado_actual.get("estado_semaforo_h"))

        for vis_carro in visuais_carros:
            posicao = estado_actual.get(f"{vis_carro.id_agente_completo}_pos")
            angulo = estado_actual.get(f"{vis_carro.id_agente_completo}_angle")
            vis_carro.update(posicao, angulo)

        for vis_pessoa in visuais_pessoas:
            posicao = estado_actual.get(f"{vis_pessoa.id_agente_completo}_pos")
            vis_pessoa.update(posicao)

        for vc in visuais_carros:
            for vp in visuais_pessoas:
                if vc.rect.colliderect(vp.rect) and not vp.colidiu:
                    vp.registrar_colisao()

        tela.blit(imagem_fundo, (0, 0))
        desenhar_pontos_de_passagem(tela, fonte_debug)
        desenhar_pontos_de_passagem_carros(tela, fonte_debug)
        visual_semaforo_v.draw(tela)
        visual_semaforo_h.draw(tela)
        for c in visuais_carros: c.draw(tela)
        for p in visuais_pessoas: p.draw(tela)
        pygame.display.flip()
        clock.tick(60)

    try:
        if hasattr(admin, 'stop_system'): admin.stop_system()
        elif hasattr(admin, 'stop_all_agents'): admin.stop_all_agents()
        thread_agentes.join(timeout=1)
    except Exception as e:
        print(f"Erro ao encerrar: {e}")
    finally:
        pygame.quit()
        import sys
        sys.exit()

if __name__ == '__main__':
    if not os.path.exists('assets'): os.makedirs('assets')
    if not os.path.exists('src'): os.makedirs('src')
    main()