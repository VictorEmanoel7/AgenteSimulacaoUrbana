"""
Módulo responsável pelos agentes (Carros e Pedestres) e o ambiente de controle de tráfego,
integrando lógica de movimento, colisão e aprendizado por reforço (MASPY).
"""

import time
import threading
import random
import math
from maspy import *
from maspy.learning import * 
from . import settings

MAPA_SEMAFOROS_TRAVESSIA = {
    ("P1", "P2"): "semaforo_v", 
    ("P2", "P1"): "semaforo_v",
    ("P2", "P3"): "semaforo_h", 
    ("P3", "P2"): "semaforo_h",
}

def calcular_distancia(pos1, pos2):
    """
    Calcula a distância euclidiana entre dois pontos (coordenadas x, y).
    """
    if not pos1 or not pos2: return float('inf')
    try:
        return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)
    except:
        return float('inf')

class ControladorDeCruzamento(Environment):
    """
    Ambiente que gerencia os estados dos semáforos e define as regras 
    de recompensa (SART) para o aprendizado dos agentes.
    """
    def __init__(self, name, full_log=False):
        super().__init__(name, full_log)
        self.estado_compartilhado = None
        self.lock = None

    def setup(self, estado_compartilhado, lock):
        """
        Inicializa os percepts do ambiente, estados iniciais e inicia 
        a thread de controle dos semáforos.
        """
        self.estado_compartilhado = estado_compartilhado
        self.lock = lock
        
        self.create(Percept("sinal_visual", ("verde", "vermelho"), listed)) 
        self.create(Percept("sinal_pedestre", ("livre", "fechado"), listed)) 
        
        self.possible_starts = {"sinal_visual": "vermelho", "sinal_pedestre": "livre"}
        
        self.create(Percept("semaforo_v", "verde"))
        self.create(Percept("semaforo_h", "vermelho"))
        self._up_visual("verde", "vermelho")
        threading.Thread(target=self.trocar_sinal, daemon=True).start()

    def transicao_trafego(self, state: dict, action: str):
        """
        Função de transição para o aprendizado dos carros. 
        Define recompensas baseadas na obediência ao sinal.
        """
        cor_sinal = state["sinal_visual"]
        reward = 0
        terminated = True
        
        if action == "andar":
            if cor_sinal == "vermelho": reward = -20
            elif cor_sinal == "verde": reward = 10
        elif action == "parar":
            if cor_sinal == "vermelho": reward = 10
            elif cor_sinal == "verde": reward = -5
        return state, reward, terminated

    @action(listed, ("parar", "andar"), transicao_trafego)
    def decidir_movimento_carro(self, agent, acao_escolhida: str):
        """
        Ação abstrata decorada para o aprendizado do carro (SART).
        """
        pass

    def transicao_pedestre(self, state: dict, action: str):
        """
        Função de transição para o aprendizado dos pedestres. 
        Define recompensas baseadas na segurança da travessia.
        """
        status_sinal = state["sinal_pedestre"]
        reward = 0
        terminated = True

        if action == "atravessar":
            if status_sinal == "fechado": reward = -50 
            elif status_sinal == "livre": reward = 20 
        elif action == "esperar":
            if status_sinal == "fechado": reward = 10 
            elif status_sinal == "livre": reward = -5 
        return state, reward, terminated

    @action(listed, ("esperar", "atravessar"), transicao_pedestre)
    def decidir_travessia(self, agent, acao_escolhida: str):
        """
        Ação abstrata decorada para o aprendizado do pedestre (SART).
        """
        pass

    def _up_visual(self, v, h):
        """
        Atualiza o estado compartilhado com a interface gráfica de forma segura.
        """
        if self.estado_compartilhado and self.lock:
            with self.lock:
                self.estado_compartilhado['estado_semaforo_v'] = v
                self.estado_compartilhado['estado_semaforo_h'] = h

    def trocar_sinal(self):
        """
        Loop infinito que alterna as cores dos semáforos e atualiza os percepts dos agentes.
        Verifica a flag 'simulacao_ativa' para encerrar a thread corretamente.
        """
        ciclo = [
            ("verde", "vermelho", 4),
            ("amarelo", "vermelho", 2),
            ("vermelho", "verde", 4),
            ("vermelho", "amarelo", 2)
        ]
        idx = 0
        while True:
            if self.estado_compartilhado and not self.estado_compartilhado.get("simulacao_ativa", True):
                break 
            
            v, h, t = ciclo[idx]
            pv = self.get(Percept("semaforo_v", Any))
            ph = self.get(Percept("semaforo_h", Any))
            
            try: p_carro = self.get(Percept("sinal_visual", Any))
            except: p_carro = None
            try: p_pedestre = self.get(Percept("sinal_pedestre", Any))
            except: p_pedestre = None
            
            if pv and ph:
                self.change(pv, v)
                self.change(ph, h)
                self._up_visual(v, h)
                if p_carro:
                    novo_estado_carro = "verde" if v == "verde" else "vermelho"
                    self.change(p_carro, novo_estado_carro)
                if p_pedestre:
                    novo_estado_pedestre = "fechado" if v in ["verde", "amarelo"] else "livre"
                    self.change(p_pedestre, novo_estado_pedestre)
            time.sleep(t)
            idx = (idx + 1) % len(ciclo)

class AgenteCarro(Agent):
    """
    Agente que representa um veículo. Possui sistema de prevenção de colisão
    e aprendizado por reforço para respeitar semáforos.
    """
    def __init__(self, name, ponto_inicial, velocidade, estado_compartilhado, lock, env_ref=None):
        super().__init__(name)
        self.ponto_atual = ponto_inicial
        self.velocidade_base = velocidade
        self.estado_compartilhado = estado_compartilhado
        self.lock = lock
        self.env_ref = env_ref
        self.delay = 0.02
        try: self.posicao = settings.PONTOS_DE_PASSAGEM_CARROS[ponto_inicial]
        except: self.posicao = (0,0)
        self.configurar_orientacao()
        self.pontos_verificacao = ["H_MID_R", "H_MID_L", "V_MID_L", "V_MID_C", "V_MID_R"]
        with self.lock:
            self.estado_compartilhado[f'{self.my_name}_pos'] = self.posicao
            self.estado_compartilhado[f'{self.my_name}_angle'] = self.angulo
        self.modelo_transito = None
        self.add(Goal("dirigir_e_treinar"))

    def configurar_orientacao(self):
        """
        Define o ângulo e o eixo de movimento do carro com base no seu ponto de partida.
        """
        if self.ponto_atual.startswith("H_"):
            self.sinal_nome = "semaforo_h"
            self.linha_parada = 470
            self.eixo_mov = 'x'
            self.angulo = 90.0
        else:
            self.sinal_nome = "semaforo_v"
            self.linha_parada = 420
            self.eixo_mov = 'y'
            self.angulo = 0.0

    def verificar_frente_livre(self, pos_alvo):
        """
        Verifica se há risco de colisão com outro veículo à frente na mesma faixa de direção.
        """
        distancia_frenagem = 70 
        largura_faixa = 20       
        dx_move = pos_alvo[0] - self.posicao[0]
        dy_move = pos_alvo[1] - self.posicao[1]

        with self.lock:
            snapshot = self.estado_compartilhado.copy()
            
        for key, pos_outro in snapshot.items():
            if key.endswith("_pos") and "Carro" in key and self.my_name not in key:
                if pos_outro:
                    dx_rel = pos_outro[0] - self.posicao[0]
                    dy_rel = pos_outro[1] - self.posicao[1]
                    distancia_real = math.sqrt(dx_rel**2 + dy_rel**2)

                    if distancia_real > distancia_frenagem: continue

                    if abs(dx_move) > abs(dy_move):
                        if abs(dy_rel) < largura_faixa:
                            if (dx_move > 0 and dx_rel > 0) or (dx_move < 0 and dx_rel < 0):
                                return False
                    else:
                        if abs(dx_rel) < largura_faixa:
                            if (dy_move > 0 and dy_rel > 0) or (dy_move < 0 and dy_rel < 0):
                                return False
        return True

    def mover_fisicamente(self, acao):
        """
        Calcula a nova posição do carro, aplicando restrições de colisão
        e atualizando o estado visual.
        """
        if self.ponto_atual not in settings.CAMINHOS_CARROS: return
        proximos = settings.CAMINHOS_CARROS.get(self.ponto_atual, [])
        if not proximos:
            starts = settings.PONTOS_INICIAIS_HORIZONTAIS if self.ponto_atual.startswith("H_") else settings.PONTOS_INICIAIS_VERTICAIS
            self.ponto_atual = random.choice(starts)
            self.posicao = settings.PONTOS_DE_PASSAGEM_CARROS[self.ponto_atual]
            self.configurar_orientacao()
            return

        ponto_alvo_nome = proximos[0] 
        pos_alvo = settings.PONTOS_DE_PASSAGEM_CARROS[ponto_alvo_nome]
        
        caminho_livre = self.verificar_frente_livre(pos_alvo)
        
        if acao == "parar" or not caminho_livre: vel = 0
        else: vel = self.velocidade_base
        
        d_alvo = calcular_distancia(self.posicao, pos_alvo)
        
        if d_alvo < self.velocidade_base:
            self.posicao = pos_alvo
            self.ponto_atual = ponto_alvo_nome
            return

        if vel > 0:
            dx = pos_alvo[0] - self.posicao[0]
            dy = pos_alvo[1] - self.posicao[1]
            dt = math.sqrt(dx**2 + dy**2)
            if dt > 0:
                mx = (dx/dt) * vel
                my = (dy/dt) * vel
                self.posicao = (self.posicao[0] + mx, self.posicao[1] + my)
                self.angulo = math.degrees(math.atan2(-dy, dx)) - 90
        
        with self.lock:
            self.estado_compartilhado[f'{self.my_name}_pos'] = self.posicao
            self.estado_compartilhado[f'{self.my_name}_angle'] = self.angulo

    @pl(gain, Goal("dirigir_e_treinar"))
    def plano_dirigir_treinando(self, src):
        """
        Plano principal do carro: executa o treinamento (Q-Learning) em background
        e depois assume o controle inteligente.
        """
        env = self.env_ref
        if not env: return
        self.modelo_transito = EnvModel(env)
        
        def thread_treino(modelo):
            modelo.learn(qlearning, num_episodes=500)
        
        t_treino = threading.Thread(target=thread_treino, args=(self.modelo_transito,))
        t_treino.start()

        while t_treino.is_alive():
            if not self.estado_compartilhado.get("simulacao_ativa", True): return True
            
            deve_pensar = self.ponto_atual in self.pontos_verificacao
            pos_atual = self.posicao[0] if self.eixo_mov == 'x' else self.posicao[1]
            
            if (pos_atual - self.linha_parada) < 10: 
                deve_pensar = False
            
            acao = "andar"
            if deve_pensar: acao = random.choice(["andar", "parar"])
            self.mover_fisicamente(acao)
            time.sleep(self.delay)

        while True:
            if not self.estado_compartilhado.get("simulacao_ativa", True): return True

            deve_pensar = self.ponto_atual in self.pontos_verificacao
            pos_atual = self.posicao[0] if self.eixo_mov == 'x' else self.posicao[1]
            
            if (pos_atual - self.linha_parada) < 10: 
                deve_pensar = False
            
            acao = "andar"
            if deve_pensar:
                sinal_alvo = "semaforo_v" if self.ponto_atual.startswith("V_") else "semaforo_h"
                percep = self.get(Belief(sinal_alvo, Any, "Cruzamento"))
                cor_real = "verde"
                if percep:
                    v = percep.values
                    cor_real = v[0] if isinstance(v, tuple) else v
                cor_consulta = cor_real.lower() if cor_real else "verde" 
                if cor_consulta == "amarelo": cor_consulta = "vermelho"
                estado_str = str(cor_consulta)
                if hasattr(self.modelo_transito, 'q_table') and estado_str in self.modelo_transito.q_table:
                    q_vals = self.modelo_transito.q_table[estado_str]
                    acao = max(q_vals, key=q_vals.get)
                else: acao = "parar" if cor_consulta == "vermelho" else "andar"
            self.mover_fisicamente(acao)
            time.sleep(self.delay)
        return True

class AgentePessoa(Agent):
    """
    Agente que representa um pedestre. Navega entre pontos seguros
    e aprende a respeitar o sinal de travessia.
    """
    def __init__(self, name, ponto_inicial, velocidade, estado_compartilhado, lock, env_ref=None):
        super().__init__(name)
        self.ponto_atual = ponto_inicial
        try: self.posicao = settings.PONTOS_DE_PASSAGEM_PEDESTRES[ponto_inicial]
        except: self.posicao = (0,0)
        self.velocidade = velocidade
        self.estado_compartilhado = estado_compartilhado
        self.lock = lock
        self.env_ref = env_ref
        self.delay = 0.1
        self.proximo_destino_nome = None 
        self.atravessando = False 
        with self.lock:
            self.estado_compartilhado[f"{self.my_name}_pos"] = self.posicao
        self.modelo_pedestre = None
        self.add(Goal("andar_e_treinar"))

    def escolher_proximo_destino(self):
        """
        Seleciona aleatoriamente o próximo ponto de passagem válido no grafo de caminhos.
        """
        proximos = settings.CAMINHOS_PEDESTRES.get(self.ponto_atual, [])
        if not proximos: return None
        return random.choice(proximos)

    def mover_fisicamente(self, acao):
        """
        Controla o movimento do pedestre, impedindo paradas no meio da rua 
        após iniciar a travessia (lógica de trava).
        """
        if acao == "esperar" and not self.atravessando: return
        if not self.proximo_destino_nome:
            self.proximo_destino_nome = self.escolher_proximo_destino()
            if not self.proximo_destino_nome: 
                self.wait(1)
                return
        self.atravessando = True
        pos_alvo = settings.PONTOS_DE_PASSAGEM_PEDESTRES[self.proximo_destino_nome]
        dist = calcular_distancia(self.posicao, pos_alvo)
        if dist > self.velocidade:
            mx = ((pos_alvo[0]-self.posicao[0])/dist)*self.velocidade
            my = ((pos_alvo[1]-self.posicao[1])/dist)*self.velocidade
            self.posicao = (self.posicao[0]+mx, self.posicao[1]+my)
        else:
            self.posicao = pos_alvo
            self.ponto_atual = self.proximo_destino_nome
            self.proximo_destino_nome = None
            self.atravessando = False 
        with self.lock:
            self.estado_compartilhado[f"{self.my_name}_pos"] = self.posicao

    @pl(gain, Goal("andar_e_treinar"))
    def plano_pedestre_treinando(self, src):
        """
        Plano principal do pedestre: executa o treinamento e controla a decisão
        de atravessar ou esperar com base no aprendizado.
        """
        env = self.env_ref
        if not env: return
        self.modelo_pedestre = EnvModel(env)
        def thread_treino(modelo):
            modelo.learn(qlearning, num_episodes=400)
        t_treino = threading.Thread(target=thread_treino, args=(self.modelo_pedestre,))
        t_treino.start()

        while t_treino.is_alive():
            if not self.estado_compartilhado.get("simulacao_ativa", True): return True
            if not self.atravessando: acao = random.choice(["esperar", "atravessar"])
            else: acao = "atravessar"
            self.mover_fisicamente(acao)
            time.sleep(self.delay)
            
        while True:
            if not self.estado_compartilhado.get("simulacao_ativa", True): return True
            acao = "atravessar" 
            if not self.atravessando:
                if not self.proximo_destino_nome:
                    self.proximo_destino_nome = self.escolher_proximo_destino()
                chave_travessia = (self.ponto_atual, self.proximo_destino_nome)
                if chave_travessia in MAPA_SEMAFOROS_TRAVESSIA:
                    nome_semaforo_carro = MAPA_SEMAFOROS_TRAVESSIA[chave_travessia]
                    percep = self.get(Belief(nome_semaforo_carro, Any, "Cruzamento"))
                    cor_carro = "verde"
                    if percep:
                        v = percep.values
                        cor_carro = v[0] if isinstance(v, tuple) else v
                    sinal_pedestre_local = "fechado" if cor_carro in ["verde", "amarelo"] else "livre"
                    if hasattr(self.modelo_pedestre, 'q_table'):
                        q_vals = self.modelo_pedestre.q_table.get(sinal_pedestre_local)
                        if q_vals: acao = max(q_vals, key=q_vals.get)
                        else: acao = "esperar" if sinal_pedestre_local == "fechado" else "atravessar"
            self.mover_fisicamente(acao)
            time.sleep(self.delay)
        return True