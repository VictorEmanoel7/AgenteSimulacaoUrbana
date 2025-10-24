"""
Implementação dos agentes gráficos e da lógica da simulação.

Este módulo contém:
- Funções utilitárias (por exemplo, cálculo de distância)
- A classe Environment ControladorDeCruzamento que gerencia o semáforo
  e publica percepções sobre o estado dos sinais.
- AgenteCarro: agente que implementa comportamento de condução,
  filas em semáforo, troca de faixa e negociação com pedestres.
- AgentePessoa: agente pedestre que decide caminhos, solicita travessia
  e negocia com carros.

As classes usam a API do `maspy` (Agent, Environment, Belief, Goal, Percept, etc.)
e compartilham um dicionário thread-safe com posições e estados.
"""

import time
import threading
import random
import math
from maspy import Agent, Environment, Belief, Goal, pl, gain, lose, Any, Percept, tell, achieve
from . import settings

# --- FUNÇÕES AUXILIARES ---
"""Funções utilitárias pequenas usadas pelos agentes (mantêm-se puras e simples)."""
def calcular_distancia(pos1, pos2):
    """
    Calcula a distância Euclidiana entre duas posições (pos1, pos2).

    Retorna infinito se os argumentos forem inválidos, prevenindo exceções
    quando valores inesperados forem lidos do estado compartilhado.
    """
    if not pos1 or not pos2 or not isinstance(pos1, (tuple, list)) or not isinstance(pos2, (tuple, list)) or len(pos1) != 2 or len(pos2) != 2:
        return float('inf')
    try:
        return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)
    except (TypeError, IndexError):
        return float('inf')

# --- CONTROLADOR DE CRUZAMENTO (AMBIENTE) ---
"""Environment que controla o ciclo dos semáforos e publica percepções."""
class ControladorDeCruzamento(Environment):
    def __init__(self, name, full_log=False):
        super().__init__(name, full_log)
        self.estado_compartilhado = None
        self.lock = None

    def setup(self, estado_compartilhado, lock):
        """
        Inicializa o ambiente: registra percepções iniciais e
        configura o estado compartilhado usado por agentes.
        """
        self.estado_compartilhado = estado_compartilhado
        self.lock = lock
        self.create(Percept("semaforo_v", "verde"))
        self.create(Percept("semaforo_h", "vermelho"))
        if self.estado_compartilhado and self.lock:
            with self.lock:
                self.estado_compartilhado['estado_semaforo_v'] = "verde"
                self.estado_compartilhado['estado_semaforo_h'] = "vermelho"
        threading.Thread(target=self.trocar_sinal, daemon=True).start()

    def trocar_sinal(self):
        """
        Loop contínuo que altera os estados dos semáforos seguindo uma
        sequência temporal predefinida (verde -> amarelo -> vermelho -> ...).
        Atualiza tanto as percepções do ambiente quanto o estado compartilhado.
        """
        estados = [("verde", "vermelho"), ("amarelo", "vermelho"), ("vermelho", "verde"), ("vermelho", "amarelo")]
        tempos = [5, 2, 5, 2]
        indice_estado_atual = 0
        while True:
            try:
                estado_v, estado_h = estados[indice_estado_atual]
                tempo_espera = tempos[indice_estado_atual]
                percep_semaforo_v = self.get(Percept("semaforo_v", Any))
                percep_semaforo_h = self.get(Percept("semaforo_h", Any))
                if percep_semaforo_v and percep_semaforo_h:
                    self.change(percep_semaforo_v, estado_v)
                    self.change(percep_semaforo_h, estado_h)
                    if self.estado_compartilhado and self.lock:
                        with self.lock:
                            self.estado_compartilhado['estado_semaforo_v'] = estado_v
                            self.estado_compartilhado['estado_semaforo_h'] = estado_h
                time.sleep(tempo_espera)
                indice_estado_atual = (indice_estado_atual + 1) % len(estados)
            except Exception:
                break

# --- AGENTE: CARRO ---
"""Agente que representa um veículo com lógica de fila, troca de faixa,
avaliação de pedidos de pedestres e prevenção de colisões."""
class AgenteCarro(Agent):
    def __init__(self, name, ponto_inicial, velocidade, estado_compartilhado, lock):
        """
        Inicializa um carro:
        - name: identificador do agente
        - ponto_inicial: nome do waypoint inicial (chave em PONTOS_DE_PASSAGEM_CARROS)
        - velocidade: magnitude de deslocamento por passo
        - estado_compartilhado, lock: dicionário thread-safe compartilhado com posições/estados
        """
        super().__init__(name)
        self.ponto_atual = ponto_inicial
        self.ponto_anterior = None
        try:
            self.posicao = settings.PONTOS_DE_PASSAGEM_CARROS[ponto_inicial]
        except KeyError:
            print(f"Ponto inicial '{ponto_inicial}' não encontrado para {self.my_name} !!!")
            self.posicao = (settings.LARGURA_TELA // 2, settings.ALTURA_TELA // 2)
        self.velocidade = velocidade
        self.estado_compartilhado = estado_compartilhado
        self.lock = lock
        self.delay = 0.05
        self.ponto_alvo_atual = None
        with self.lock:
            self.estado_compartilhado[f'{self.my_name}_pos'] = self.posicao
        self.add(Goal("dirigir_para_proximo_ponto"))
        self.id_pedestre_cedendo = None

    def encontrar_carro_a_frente(self, ponto_parada_nome):
        """
        Localiza (se existir) a posição do carro mais próximo na fila à frente
        entre a posição atual e o waypoint de parada especificado.

        Retorna a posição do carro à frente ou None se não houver.
        """
        carro_frente_pos = None
        min_dist_frente_parada = float('inf')

        pos_parada_waypoint = settings.PONTOS_DE_PASSAGEM_CARROS.get(ponto_parada_nome)
        if not pos_parada_waypoint:
            return None

        dist_atual_parada_waypoint = calcular_distancia(self.posicao, pos_parada_waypoint)

        with self.lock:
            estado_copia = self.estado_compartilhado.copy()

        for key, pos_outro in estado_copia.items():
            if key.startswith("Carro") and key.endswith("_pos") and key != f'{self.my_name}_pos':
                mesma_faixa = False
                if ponto_parada_nome.startswith("V_") and abs(pos_outro[0] - self.posicao[0]) < settings.LARGURA_CARRO * 0.5:
                    if pos_outro[1] < self.posicao[1] and pos_outro[1] >= pos_parada_waypoint[1]:
                        mesma_faixa = True
                elif ponto_parada_nome.startswith("H_") and abs(pos_outro[1] - self.posicao[1]) < settings.ALTURA_CARRO * 0.25:
                    if pos_outro[0] < self.posicao[0] and pos_outro[0] >= pos_parada_waypoint[0]:
                        mesma_faixa = True

                if mesma_faixa:
                    dist_outro_parada_waypoint = calcular_distancia(pos_outro, pos_parada_waypoint)
                    if dist_outro_parada_waypoint < dist_atual_parada_waypoint and dist_outro_parada_waypoint < min_dist_frente_parada:
                        min_dist_frente_parada = dist_outro_parada_waypoint
                        carro_frente_pos = pos_outro

        return carro_frente_pos

    def encontrar_obstaculo_imediato(self):
        """
        Detecta se existe um outro carro perigosamente perto na direção de movimento.
        Retorna a posição do obstáculo se ele estiver dentro da distância de segurança,
        caso contrário retorna None.
        """
        if not self.ponto_alvo_atual:
            return None

        pos_alvo = settings.PONTOS_DE_PASSAGEM_CARROS.get(self.ponto_alvo_atual)
        if not pos_alvo:
            return None

        dx = pos_alvo[0] - self.posicao[0]
        dy = pos_alvo[1] - self.posicao[1]

        is_vertical = abs(dy) > abs(dx)
        is_horizontal = abs(dx) > abs(dy)

        dist_segura_frente = settings.ALTURA_CARRO * 0.9
        dist_segura_lado = settings.LARGURA_CARRO * 0.5

        if is_horizontal:
            dist_segura_frente = settings.LARGURA_CARRO * 0.9
            dist_segura_lado = settings.ALTURA_CARRO * 0.5

        pos_obstaculo_proximo = None
        menor_distancia = float('inf')

        with self.lock:
            estado_copia = self.estado_compartilhado.copy()

        for key, pos_outro in estado_copia.items():
            if key.startswith("Carro") and key.endswith("_pos") and key != f'{self.my_name}_pos':
                dist_outro = calcular_distancia(self.posicao, pos_outro)
                if dist_outro > dist_segura_frente * 2:
                    continue

                esta_a_frente = False
                na_mesma_faixa = False

                if is_vertical:
                    na_mesma_faixa = abs(pos_outro[0] - self.posicao[0]) < dist_segura_lado
                    if dy < 0:
                        esta_a_frente = (pos_outro[1] < self.posicao[1])
                    else:
                        esta_a_frente = (pos_outro[1] > self.posicao[1])
                elif is_horizontal:
                    na_mesma_faixa = abs(pos_outro[1] - self.posicao[1]) < dist_segura_lado
                    if dx < 0:
                        esta_a_frente = (pos_outro[0] < self.posicao[0])
                    else:
                        esta_a_frente = (pos_outro[0] > self.posicao[0])

                if esta_a_frente and na_mesma_faixa:
                    if dist_outro < menor_distancia:
                        menor_distancia = dist_outro
                        pos_obstaculo_proximo = pos_outro

        if pos_obstaculo_proximo and menor_distancia < dist_segura_frente:
            return pos_obstaculo_proximo

        return None

    def verificar_faixa_alvo(self, ponto_atual, ponto_alvo_troca):
        """
        Verifica se a faixa alvo está livre para troca de faixa.
        Retorna True se livre, False se ocupada.
        """
        faixa_actual_x = settings.PONTOS_DE_PASSAGEM_CARROS[ponto_atual][0]
        faixa_alvo_x = settings.PONTOS_DE_PASSAGEM_CARROS[ponto_alvo_troca][0]
        faixa_actual_y = settings.PONTOS_DE_PASSAGEM_CARROS[ponto_atual][1]
        faixa_alvo_y = settings.PONTOS_DE_PASSAGEM_CARROS[ponto_alvo_troca][1]
        with self.lock:
            estado_copia = self.estado_compartilhado.copy()
        for key, pos_outro in estado_copia.items():
            if key.startswith("Carro") and key.endswith("_pos") and key != f'{self.my_name}_pos':
                distancia_relativa = calcular_distancia(self.posicao, pos_outro)
                if distancia_relativa < settings.DISTANCIA_VERIFICACAO_TROCA_FAIXA:
                    if ponto_atual.startswith("V_") and abs(pos_outro[0] - faixa_alvo_x) < settings.LARGURA_CARRO / 2:
                        if pos_outro[1] > self.posicao[1] - settings.ALTURA_CARRO and pos_outro[1] < self.posicao[1] + settings.DISTANCIA_VERIFICACAO_TROCA_FAIXA:
                            return False
                    elif ponto_atual.startswith("H_") and abs(pos_outro[1] - faixa_alvo_y) < settings.ALTURA_CARRO / 2:
                        if pos_outro[0] > self.posicao[0] - settings.LARGURA_CARRO and pos_outro[0] < self.posicao[0] + settings.DISTANCIA_VERIFICACAO_TROCA_FAIXA:
                            return False
        return True

    def verificar_pedestre_na_passadeira(self, ponto_avaliacao_nome):
        """
        Verifica se há *qualquer* pedestre fisicamente dentro da zona de 
        passadeira associada ao 'ponto_avaliacao_nome'.
        Retorna True se um pedestre for encontrado, False caso contrário.
        """
        zona_relevante = settings.MAPA_AVALIACAO_PASSADEIRA.get(ponto_avaliacao_nome)
        if not zona_relevante:
            return False 

        xmin, xmax, ymin, ymax = zona_relevante
        
        with self.lock:
            estado_copia = self.estado_compartilhado.copy()

        for key, pos in estado_copia.items():
            if key.startswith("Pessoa") and key.endswith("_pos"):
                if (xmin <= pos[0] <= xmax and ymin <= pos[1] <= ymax):
                    return True 

        return False 

    @pl(gain, Goal("dirigir_para_proximo_ponto"))
    def plano_dirigir(self, src):
        """
        Plano principal que faz o carro:
        - avaliar semáforo e fila
        - lidar com obstáculos imediatos
        - negociar com pedestres (receber pedidos, ceder, monitorar)
        - verificar segurança da passadeira (NOVO)
        - escolher e percorrer o próximo waypoint
        """
        crenca_cedendo = self.get(Belief(settings.NOME_CRENCA_CARRO_CEDENDO, Any))
        if crenca_cedendo:
            self.add(Goal("monitorar_pedestre_cedendo", crenca_cedendo.args))
            return True

        parar_no_semaforo = False
        ponto_de_parada_alvo = None
        ponto_parada_waypoint_nome = None

        if self.ponto_atual in settings.PONTOS_DE_PARADA:
            ponto_parada_waypoint_nome = self.ponto_atual
        elif self.ponto_alvo_atual in settings.PONTOS_DE_PARADA:
            ponto_parada_waypoint_nome = self.ponto_alvo_atual

        if ponto_parada_waypoint_nome:
            semaforo_a_verificar = None
            if ponto_parada_waypoint_nome.startswith("V_"):
                semaforo_a_verificar = "semaforo_v"
            elif ponto_parada_waypoint_nome.startswith("H_"):
                semaforo_a_verificar = "semaforo_h"

            if semaforo_a_verificar:
                crenca_semaforo = self.get(Belief(semaforo_a_verificar, Any, "Cruzamento"))
                cor_sinal = "desconhecido"
                if crenca_semaforo:
                    cor_sinal = crenca_semaforo.args

                pos_carro_frente_fila = self.encontrar_carro_a_frente(ponto_parada_waypoint_nome)

                if pos_carro_frente_fila:
                    parar_no_semaforo = True
                    if ponto_parada_waypoint_nome.startswith("V_"):
                        ponto_de_parada_alvo = (pos_carro_frente_fila[0], pos_carro_frente_fila[1] + settings.ALTURA_CARRO + settings.DISTANCIA_SEGURA_SEMAFORO)
                    elif ponto_parada_waypoint_nome.startswith("H_"):
                        ponto_de_parada_alvo = (pos_carro_frente_fila[0] + settings.LARGURA_CARRO + settings.DISTANCIA_SEGURA_SEMAFORO, pos_carro_frente_fila[1])
                elif cor_sinal in ["vermelho", "amarelo"]:
                    parar_no_semaforo = True
                    ponto_de_parada_alvo = settings.PONTOS_DE_PASSAGEM_CARROS[ponto_parada_waypoint_nome]

                if parar_no_semaforo:
                    if ponto_de_parada_alvo and calcular_distancia(self.posicao, ponto_de_parada_alvo) < self.velocidade * 0.5:
                        self.add(Goal("dirigir_para_proximo_ponto"))
                        return True

        proximos_pontos_possiveis = settings.CAMINHOS_CARROS.get(self.ponto_atual, [])[:]
        if not proximos_pontos_possiveis:
            novo_ponto_inicial = None
            if self.ponto_atual.startswith("V_END"):
                novo_ponto_inicial = random.choice(settings.PONTOS_INICIAIS_VERTICAIS)
            elif self.ponto_atual.startswith("H_END"):
                novo_ponto_inicial = random.choice(settings.PONTOS_INICIAIS_HORIZONTAIS)
            else:
                todos_inicios = settings.PONTOS_INICIAIS_VERTICAIS + settings.PONTOS_INICIAIS_HORIZONTAIS
                novo_ponto_inicial = random.choice(todos_inicios)
            self.ponto_anterior = self.ponto_atual
            self.ponto_atual = novo_ponto_inicial
            self.ponto_alvo_atual = None
            try:
                self.posicao = settings.PONTOS_DE_PASSAGEM_CARROS[novo_ponto_inicial]
            except KeyError:
                print(f"Novo ponto inicial '{novo_ponto_inicial}' não encontrado !!!")
                self.posicao = (settings.LARGURA_TELA/2, settings.ALTURA_TELA/2)
                self.stop_cycle()
                return True
            with self.lock:
                self.estado_compartilhado[f'{self.my_name}_pos'] = self.posicao
            self.add(Goal("dirigir_para_proximo_ponto"))
            return True

        ponto_alvo_nome = None
        opcoes_validas = proximos_pontos_possiveis[:]
        if self.ponto_anterior in opcoes_validas and len(opcoes_validas) > 1:
            opcoes_validas.remove(self.ponto_anterior)
        if not opcoes_validas:
            opcoes_validas = proximos_pontos_possiveis

        if not ponto_de_parada_alvo:
            if not opcoes_validas:
                self.add(Goal("dirigir_para_proximo_ponto"))
                return True
            ponto_alvo_nome = random.choice(opcoes_validas)
            self.ponto_alvo_atual = ponto_alvo_nome
        else:
            ponto_alvo_nome = ponto_parada_waypoint_nome

        if not ponto_alvo_nome:
            self.add(Goal("dirigir_para_proximo_ponto"))
            return True

        e_troca_faixa = False
        if len(self.ponto_atual) > 2 and len(ponto_alvo_nome) > 2:
            if self.ponto_atual[:-1] == ponto_alvo_nome[:-1] and self.ponto_atual[-1] != ponto_alvo_nome[-1]:
                e_troca_faixa = True
            elif self.ponto_atual.startswith("H_") and ponto_alvo_nome.startswith("H_") and self.ponto_atual[-1] != ponto_alvo_nome[-1]:
                e_troca_faixa = True
        if e_troca_faixa:
            faixa_livre = self.verificar_faixa_alvo(self.ponto_atual, ponto_alvo_nome)
            if not faixa_livre:
                self.wait(settings.TEMPO_ESPERA_TROCA_FAIXA)
                self.ponto_alvo_atual = None
                self.add(Goal("dirigir_para_proximo_ponto"))
                return True

        if ponto_de_parada_alvo:
            posicao_alvo = ponto_de_parada_alvo
        else:
            try:
                posicao_alvo = settings.PONTOS_DE_PASSAGEM_CARROS[ponto_alvo_nome]
            except KeyError:
                print(f"ERRO: {self.my_name} alvo inválido '{ponto_alvo_nome}'.")
                self.ponto_alvo_atual = None
                self.add(Goal("dirigir_para_proximo_ponto"))
                return True

        LIMIAR_CHEGADA = self.velocidade * 0.5
        while True:
            distancia = calcular_distancia(self.posicao, posicao_alvo)

            if distancia < LIMIAR_CHEGADA:
                self.posicao = posicao_alvo
                break

            if self.encontrar_obstaculo_imediato():
                self.add(Goal("dirigir_para_proximo_ponto"))
                return True

            if self.has(Belief(settings.NOME_CRENCA_CARRO_CEDENDO, Any)):
                self.add(Goal("monitorar_pedestre_cedendo", self.get(Belief(settings.NOME_CRENCA_CARRO_CEDENDO, Any)).args))
                self.ponto_alvo_atual = None
                return True

            # --- INÍCIO DA CORREÇÃO (LÓGICA DO USUÁRIO) ---
            
            # 1. O carro está se aproximando de uma zona de avaliação?
            estamos_na_zona_de_avaliacao = (self.ponto_atual in settings.PONTOS_AVALIACAO_CARRO or 
                                             ponto_alvo_nome in settings.PONTOS_AVALIACAO_CARRO)

            if estamos_na_zona_de_avaliacao and distancia < settings.DISTANCIA_SEGURA_CARRO_PEDESTRE:
                
                # 2. Descobrir qual é a zona relevante
                ponto_de_avaliacao_relevante = ponto_alvo_nome if ponto_alvo_nome in settings.PONTOS_AVALIACAO_CARRO else self.ponto_atual
                zona_relevante = settings.MAPA_AVALIACAO_PASSADEIRA.get(ponto_de_avaliacao_relevante)

                if zona_relevante:
                    x_carro, y_carro = self.posicao
                    xmin, xmax, ymin, ymax = zona_relevante
                    
                    # 3. O carro JÁ PASSOU da zona?
                    carro_ainda_nao_passou = False
                    if ponto_de_avaliacao_relevante.startswith("H_") or ponto_de_avaliacao_relevante.startswith("PX1_EVAL_H"):
                        # Carro Horizontal (direita->esquerda), só para se X_carro >= X_min_zona
                        if x_carro >= xmin:
                            carro_ainda_nao_passou = True
                    elif ponto_de_avaliacao_relevante.startswith("V_") or ponto_de_avaliacao_relevante.startswith("PX1_EVAL_V"):
                        # Carro Vertical (baixo->cima, Y decrescente), só para se Y_carro >= Y_min_zona
                        if y_carro >= ymin:
                            carro_ainda_nao_passou = True

                    # 4. Só ativa a lógica de parada se o carro AINDA NÃO PASSOU
                    if carro_ainda_nao_passou:
                        
                        # Checagem 1: Pedido de Negociação
                        pedido_pendente = self.get(Belief(settings.NOME_CRENCA_CARRO_PEDESTRE_PEDINDO, Any))
                        if pedido_pendente:
                            id_pedestre = pedido_pendente.args
                            self.add(Goal("avaliar_pedido_travessia", (id_pedestre, ponto_de_avaliacao_relevante))) 
                            self.ponto_alvo_atual = None 
                            return True # Para para negociar

                        # Checagem 2: Radar de Segurança
                        if self.verificar_pedestre_na_passadeira(ponto_de_avaliacao_relevante):
                            self.wait(0.2) 
                            self.add(Goal("dirigir_para_proximo_ponto")) 
                            return True # Para por segurança
            
            # --- FIM DA CORREÇÃO ---


            # Se passou por tudo, move o carro
            x_atual, y_atual = self.posicao
            x_alvo, y_alvo = posicao_alvo
            if distancia == 0:
                break
            fator_mov_x = ((x_alvo - x_atual) / distancia) * self.velocidade
            fator_mov_y = ((y_alvo - y_atual) / distancia) * self.velocidade
            self.posicao = (x_atual + fator_mov_x, y_atual + fator_mov_y)

            with self.lock:
                self.estado_compartilhado[f'{self.my_name}_pos'] = self.posicao
            time.sleep(self.delay)

        with self.lock:
            self.estado_compartilhado[f'{self.my_name}_pos'] = self.posicao

        if parar_no_semaforo:
            self.add(Goal("dirigir_para_proximo_ponto"))
        else:
            self.ponto_anterior = self.ponto_atual
            self.ponto_atual = ponto_alvo_nome
            self.ponto_alvo_atual = None
            self.add(Goal("dirigir_para_proximo_ponto"))
        return True

    # --- Planos de negociação com pedestre ---
    @pl(gain, Goal(settings.NOME_GOAL_PEDESTRE_PEDE_PASSAGEM, Any))
    def plano_receber_pedido_travessia(self, src_pedestre, id_pedestre):
        if self.has(Belief(settings.NOME_CRENCA_CARRO_PEDESTRE_PEDINDO, Any)) or self.has(Belief(settings.NOME_CRENCA_CARRO_CEDENDO, Any)):
            return True
        self.add(Belief(settings.NOME_CRENCA_CARRO_PEDESTRE_PEDINDO, id_pedestre))
        return True

    @pl(gain, Goal("avaliar_pedido_travessia", (Any, Any)))
    def plano_avaliar_pedido(self, src, args):
        id_pedestre, ponto_avaliacao = args 
        
        decisao_ceder = True
        if decisao_ceder:
            self.add(Belief(settings.NOME_CRENCA_CARRO_CEDENDO, (id_pedestre, ponto_avaliacao)))
            self.send(id_pedestre, tell, Belief(settings.NOME_CRENCA_RESPOSTA_CARRO, ("concedida", self.my_name)))
            self.add(Goal("monitorar_pedestre_cedendo", (id_pedestre, ponto_avaliacao)))
        else:
            self.send(id_pedestre, tell, Belief(settings.NOME_CRENCA_RESPOSTA_CARRO, ("negada", self.my_name)))
            self.add(Goal("dirigir_para_proximo_ponto"))
        
        pedido = self.get(Belief(settings.NOME_CRENCA_CARRO_PEDESTRE_PEDINDO, id_pedestre))
        if pedido:
            self.rm(pedido)
        return True

    @pl(gain, Goal("monitorar_pedestre_cedendo", (Any, Any)))
    def plano_monitorar_pedestre(self, src, args):
        id_pedestre, ponto_avaliacao = args 
        
        pos_pedestre = None
        with self.lock:
            pos_pedestre = self.estado_compartilhado.get(f'{id_pedestre}_pos')
        
        cedendo = self.get(Belief(settings.NOME_CRENCA_CARRO_CEDENDO, (id_pedestre, ponto_avaliacao)))
        
        if pos_pedestre:
            zona_relevante = settings.MAPA_AVALIACAO_PASSADEIRA.get(ponto_avaliacao)
            esta_na_passadeira_relevante = False
            
            if zona_relevante:
                xmin, xmax, ymin, ymax = zona_relevante
                esta_na_passadeira_relevante = (xmin <= pos_pedestre[0] <= xmax and ymin <= pos_pedestre[1] <= ymax)
            else:
                if cedendo:
                    self.rm(cedendo)
                self.add(Goal("dirigir_para_proximo_ponto"))
                return True

            if not esta_na_passadeira_relevante:
                if cedendo:
                    self.rm(cedendo)
                self.add(Goal("dirigir_para_proximo_ponto"))
                return True
            else:
                self.wait(0.5)
                self.add(Goal("monitorar_pedestre_cedendo", (id_pedestre, ponto_avaliacao))) 
                return True
        else:
            if cedendo:
                self.rm(cedendo)
            self.add(Goal("dirigir_para_proximo_ponto"))
            return True
        return True

# --- AGENTE: PESSOA ---
"""Agente que representa um pedestre com capacidade de:
- decidir movimentos
- solicitar travessia
- aguardar resposta do carro e reagir ao resultado
"""
class AgentePessoa(Agent):
    def __init__(self, name, ponto_inicial, velocidade, estado_compartilhado, lock):
        """
        Inicializa um pedestre:
        - name: identificador do agente
        - ponto_inicial: waypoint inicial em PONTOS_DE_PASSAGEM_PEDESTRES
        - velocidade: passo de deslocamento
        - estado_compartilhado, lock: dicionário compartilhado para posições/estados
        """
        super().__init__(name)
        self.ponto_atual = ponto_inicial
        try:
            self.posicao = settings.PONTOS_DE_PASSAGEM_PEDESTRES[ponto_inicial]
        except KeyError:
            print(f"Ponto inicial '{ponto_inicial}' não encontrado para {self.my_name} !!!")
            self.posicao = (settings.LARGURA_TELA // 4, settings.ALTURA_TELA // 4)
        self.velocidade = abs(velocidade)
        self.chave_estado_compartilhado = f"{self.my_name}_pos"
        self.estado_compartilhado = estado_compartilhado
        self.lock = lock
        self.delay = 0.1
        self.carro_negociando = None
        with self.lock:
            self.estado_compartilhado[self.chave_estado_compartilhado] = self.posicao
        self.add(Goal("decidir_movimento"))

    @pl(gain, Goal("decidir_movimento"))
    def plano_decidir_movimento(self, src):
        """
        Decide o próximo movimento do pedestre:
        - se aguarda resposta de carro, continua aguardando
        - se tem permissão para atravessar, inicia travessia
        - caso contrário, escolhe um próximo waypoint aleatório
        """
        if self.has(Belief("crenca_aguardando_resposta_carro")):
            self.add(Goal("aguardar_resposta"))
            return True

        tem_permissao = self.has(Belief(settings.NOME_CRENCA_PEDESTRE_PODE_ATRAVESSAR))
        em_ponto_espera = self.ponto_atual in settings.PONTOS_ESPERA_PEDESTRE

        if tem_permissao and em_ponto_espera:
            caminho_travessia = []
            if self.ponto_atual == "P1": caminho_travessia = ["P4"]
            elif self.ponto_atual == "P4": caminho_travessia = ["P1"]
            elif self.ponto_atual == "P2": caminho_travessia = ["P3"]
            elif self.ponto_atual == "P3": caminho_travessia = ["P2"]
            elif self.ponto_atual == "P4": caminho_travessia = ["P3"]
            elif self.ponto_atual == "P3": caminho_travessia = ["P4"]
            elif self.ponto_atual == "P1": caminho_travessia = ["P2"]
            elif self.ponto_atual == "P2": caminho_travessia = ["P1"]

            if caminho_travessia:
                ponto_alvo_nome = random.choice(caminho_travessia) 
                self.add(Goal("executar_movimento", ponto_alvo_nome))
                return True
            else:
                permissao = self.get(Belief(settings.NOME_CRENCA_PEDESTRE_PODE_ATRAVESSAR))
                if permissao:
                    self.rm(permissao)
                self.add(Goal("decidir_movimento")) 
                return True

        proximos_pontos = settings.CAMINHOS_PEDESTRES.get(self.ponto_atual, [])[:]
        if not proximos_pontos:
            self.wait(random.uniform(2.0, 5.0))
            self.add(Goal("decidir_movimento"))
            return True

        ponto_alvo_nome = random.choice(proximos_pontos)
        try:
            posicao_alvo = settings.PONTOS_DE_PASSAGEM_PEDESTRES[ponto_alvo_nome]
        except KeyError:
            self.add(Goal("decidir_movimento"))
            return True

        tentando_atravessar = False
        if em_ponto_espera:
            if (self.ponto_atual == "P1" and ponto_alvo_nome == "P4") or \
               (self.ponto_atual == "P4" and ponto_alvo_nome == "P1") or \
               (self.ponto_atual == "P2" and ponto_alvo_nome == "P3") or \
               (self.ponto_atual == "P3" and ponto_alvo_nome == "P2"):
                tentando_atravessar = True


        if tentando_atravessar and em_ponto_espera:
            carro_proximo = self.encontrar_carro_proximo()
            if carro_proximo:
                id_carro, dist = carro_proximo
                self.carro_negociando = id_carro
                self.add(Goal("pedir_permissao_travessia", id_carro))
                self.add(Belief("crenca_aguardando_resposta_carro"))
                self.add(Goal("aguardar_resposta"))
                return True
            else:
                self.add(Belief(settings.NOME_CRENCA_PEDESTRE_PODE_ATRAVESSAR))
                self.add(Goal("executar_movimento", ponto_alvo_nome))
                return True
        else:
            self.add(Goal("executar_movimento", ponto_alvo_nome))
            return True

    @pl(gain, Goal("executar_movimento", Any))
    def plano_executar_movimento(self, src, ponto_alvo_nome):
        """
        Move o pedestre até o waypoint alvo. Se é uma passadeira (PX) e não possui
        permissão, cancela o movimento.
        """
        try:
            posicao_alvo = settings.PONTOS_DE_PASSAGEM_PEDESTRES[ponto_alvo_nome]
        except KeyError:
            self.add(Goal("decidir_movimento"))
            return True
            
        em_ponto_espera = self.ponto_atual in settings.PONTOS_ESPERA_PEDESTRE
        e_travessia = False
        if em_ponto_espera:
            if (self.ponto_atual == "P1" and ponto_alvo_nome == "P4") or \
               (self.ponto_atual == "P4" and ponto_alvo_nome == "P1") or \
               (self.ponto_atual == "P2" and ponto_alvo_nome == "P3") or \
               (self.ponto_atual == "P3" and ponto_alvo_nome == "P2"):
                e_travessia = True

        if e_travessia and not self.has(Belief(settings.NOME_CRENCA_PEDESTRE_PODE_ATRAVESSAR)):
            self.add(Goal("decidir_movimento"))
            return True

        DISTANCIA_CHEGADA = self.velocidade * 0.5
        while calcular_distancia(self.posicao, posicao_alvo) > DISTANCIA_CHEGADA:
            x_atual, y_atual = self.posicao
            x_alvo, y_alvo = posicao_alvo
            dx, dy = x_alvo - x_atual, y_alvo - y_atual
            distancia_actual = calcular_distancia(self.posicao, posicao_alvo)
            if distancia_actual == 0:
                break
            passo_x = (dx / distancia_actual) * self.velocidade
            passo_y = (dy / distancia_actual) * self.velocidade
            self.posicao = (x_atual + passo_x, y_atual + passo_y)
            with self.lock:
                self.estado_compartilhado[self.chave_estado_compartilhado] = self.posicao
            time.sleep(self.delay)

        self.posicao = posicao_alvo
        with self.lock:
            self.estado_compartilhado[self.chave_estado_compartilhado] = self.posicao
        self.ponto_atual = ponto_alvo_nome

        permissao = self.get(Belief(settings.NOME_CRENCA_PEDESTRE_PODE_ATRAVESSAR))
        if permissao:
            self.rm(permissao)

        self.add(Goal("decidir_movimento"))
        return True

    @pl(gain, Goal("aguardar_sinal_pedestre"))
    def plano_aguardar_sinal(self, src):
        """
        Plano auxiliar para aguardar semáforo de pedestres (mantido por compatibilidade).
        Verifica o estado do semáforo relevante e decide quando prosseguir.
        """
        semaforo_relevante = "semaforo_h"
        crenca_semaforo = self.get(Belief(semaforo_relevante, Any, "Cruzamento"))
        cor_semaforo = "desconhecido"
        if crenca_semaforo:
            cor_semaforo = crenca_semaforo.args
        if cor_semaforo == "vermelho":
            self.add(Goal("decidir_movimento"))
            return True
        else:
            self.wait(0.5)
            self.add(Goal("aguardar_sinal_pedestre"))
            return True

    @pl(gain, Goal("pedir_permissao_travessia", Any))
    def plano_pedir_permissao(self, src, id_carro):
        """
        Envia um pedido de travessia (Goal) ao carro identificado.
        """
        self.send(id_carro, achieve, Goal(settings.NOME_GOAL_PEDESTRE_PEDE_PASSAGEM, self.my_name))
        return True

    @pl(gain, Belief(settings.NOME_CRENCA_RESPOSTA_CARRO, (Any, Any)))
    def plano_processar_resposta_carro(self, src_carro, resposta_tupla):
        """
        Processa a resposta do carro à solicitação de travessia.
        Atualiza crenças e objetivos do pedestre conforme a resposta.
        """
        resposta, id_carro_resp = resposta_tupla
        if id_carro_resp != self.carro_negociando:
            return True

        aguardando = self.get(Belief("crenca_aguardando_resposta_carro"))
        if aguardando:
            self.rm(aguardando)

        self.carro_negociando = None
        if resposta == "concedida":
            self.add(Belief(settings.NOME_CRENCA_PEDESTRE_PODE_ATRAVESSAR))
        else:
            self.add(Goal("aguardar_antes_de_tentar_novamente"))
            return True

        self.add(Goal("decidir_movimento"))
        return True

    @pl(gain, Goal("aguardar_resposta"))
    def plano_aguardar_resposta(self, src):
        """
        Aguarda por uma resposta do carro por um tempo máximo; se o tempo expirar,
        cancela a espera e volta a decidir.
        """
        if not self.has(Belief("crenca_aguardando_resposta_carro")):
            self.add(Goal("decidir_movimento"))
            return True

        tempo_espera_max = 3.0
        self.wait(tempo_espera_max)

        aguardando = self.get(Belief("crenca_aguardando_resposta_carro"))
        if aguardando:
            self.rm(aguardando)
            self.carro_negociando = None
            self.add(Goal("decidir_movimento"))
        return True

    @pl(gain, Goal("aguardar_antes_de_tentar_novamente"))
    def plano_espera_curta(self, src):
        """
        Espera um tempo aleatório curto antes de tentar negociar novamente.
        """
        tempo_espera = random.uniform(1.0, 3.0)
        self.wait(tempo_espera)
        self.add(Goal("decidir_movimento"))
        return True

    def encontrar_carro_proximo(self):
        """
        Retorna (id_carro, distancia) do carro mais próximo dentro da distância segura.
        Retorna None se não houver carro próximo.
        """
        carro_mais_proximo = None
        menor_distancia = settings.DISTANCIA_SEGURA_CARRO_PEDESTRE
        with self.lock:
            estado_copia = self.estado_compartilhado.copy()

        for key, pos in estado_copia.items():
            if key.startswith("Carro") and key.endswith("_pos"):
                dist = calcular_distancia(self.posicao, pos)
                if dist < menor_distancia:
                    menor_distancia = dist
                    id_carro = key.replace("_pos", "")
                    carro_mais_proximo = (id_carro, dist)

        return carro_mais_proximo