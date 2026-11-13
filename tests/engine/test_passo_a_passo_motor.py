"""Passo a passo (F52) no motor de verdade: relógio virtual, backend simulado, sem Windows e sem dormir.

Cada teste conduz o passo a passo como a janela faria (`ControleDePassos`: iniciar, próximo, continuar, parar) e espera cada
parada pelo aviso de mudança de estado do próprio motor, sem `sleep`. Com o motor parado num passo (PAUSED) a thread dele está
bloqueada, então os eventos do backend já são os definitivos até ali e dá para conferir sem corrida. `fake_clock.advance`
faz o papel do tempo que o usuário leva olhando a tela antes de clicar em "Próximo passo".

O que fica de fora: o Qt (a janelinha e os sinais) e o Windows de verdade. Ver tests/unit/test_passo_a_passo_ui.py e
tests/gui/test_passo_a_passo_janela.py.
"""
import contextlib
import queue

import pytest

from automationstudio.conditions import WaitCondition, WaitConditionType
from automationstudio.core import ActionType, Command, InputType, InvalidStateTransition, State, StateManager
from automationstudio.passo_a_passo import ControleDePassos, PassoAPasso
from testsupport.helpers import events_of, join_engine, key, make_map, pressed_balance, run_to_end


class Roteiro:
    """Um passo a passo de verdade, conduzido como a janela o conduz."""

    def __init__(self, make_engine, mapa, backend=None) -> None:
        self.motor, self.backend = make_engine(backend)
        self.mapa = mapa
        self.log: list[str] = []
        self.controle = ControleDePassos(self.motor, registrar=self.log.append)
        self._estados: queue.Queue = queue.Queue()
        self.motor.state.on_change(lambda _anterior, novo: self._estados.put(novo))

    def iniciar(self, ids=()) -> "Roteiro":
        motivo = self.controle.iniciar(self.mapa, ids)
        assert motivo == "", motivo
        return self

    def parada(self) -> State:
        """Espera o motor parar num passo (PAUSED) ou terminar (IDLE) e diz qual dos dois. Trava em 10 s, não para sempre."""
        while True:
            novo = self._estados.get(timeout=10)
            if novo in (State.PAUSED, State.IDLE):
                return novo

    def proximo(self) -> State:
        assert self.controle.proximo(), "o botão Próximo passo não fez nada"
        return self.parada()

    def ate_o_fim(self) -> None:
        """Espera o motor terminar (IDLE), passando por quantas paradas houver no caminho."""
        while self.parada() != State.IDLE:
            pass

    def eventos(self) -> list[tuple]:
        return events_of(self.backend)


@contextlib.contextmanager
def roteiro(make_engine, mapa, backend=None):
    """`with roteiro(make_engine, mapa) as r:` Ao sair (passando ou falhando) o motor é parado: nenhum teste deixa a thread dele
    presa numa pausa para trás. (Não é fixture: o projeto só aceita fixtures no conftest.py.)"""
    r = Roteiro(make_engine, mapa, backend)
    try:
        yield r
    finally:
        r.motor.stop(wait=True)


def tres_teclas(**kwargs):
    """A, B e C, cada uma apertada por 0,2 s, com 5 s de espera planejada entre uma e outra."""
    return make_map([key("A", 0.0, 0.2), key("B", 5.0, 0.2), key("C", 10.0, 0.2)], **kwargs)


A_DOWN, A_UP = "key_down", "key_up"


# ------------------------------------------------------------------------------------------ fora do passo a passo
def test_sem_passo_a_passo_o_motor_executa_como_sempre(make_engine, runtime_log):
    motor, backend = make_engine()
    assert motor.passo_a_passo is None
    estados = []
    motor.state.on_change(lambda _anterior, novo: estados.append(novo))
    terminou, erros = run_to_end(motor, tres_teclas())
    assert terminou and not erros
    # a espera planejada de 5 s entre os comandos é cumprida e nada para no meio
    assert events_of(backend) == [(0.0, "key_down", "A"), (0.2, "key_up", "A"), (5.0, "key_down", "B"), (5.2, "key_up", "B"),
                                  (10.0, "key_down", "C"), (10.2, "key_up", "C")]
    assert State.PAUSED not in estados
    assert not [linha for linha in runtime_log if "PASSO A PASSO" in linha], "uma execução normal não escreve nada do passo a passo no log"


def test_um_gancho_de_outra_automacao_nao_para_a_execucao(make_engine):
    # O gancho é de UMA cópia. Se outra automação roda enquanto ele ainda está preso (um atalho, por exemplo), não para.
    with roteiro(make_engine, tres_teclas()) as r:
        sessao_de_outra = PassoAPasso(tres_teclas(name="Outra"))
        r.motor.passo_a_passo = sessao_de_outra
        terminou, erros = run_to_end(r.motor, r.mapa)
        assert terminou and not erros
        assert [e[1:] for e in r.eventos()] == [("key_down", "A"), ("key_up", "A"), ("key_down", "B"), ("key_up", "B"),
                                                ("key_down", "C"), ("key_up", "C")]
        assert sessao_de_outra.numero == 0


# ------------------------------------------------------------------------------------------ um passo por comando
def test_comeca_parado_antes_do_primeiro_comando_sem_enviar_nada(make_engine):
    with roteiro(make_engine, tres_teclas()) as r:
        r.iniciar()
        assert r.parada() == State.PAUSED
        assert r.eventos() == []
        assert r.controle.parado_num_passo()
        assert r.controle.texto() == "Passo 1 de 3: Apertar e soltar a tecla A"


def test_cada_proximo_executa_um_comando_inteiro_e_para_antes_do_seguinte(make_engine):
    with roteiro(make_engine, tres_teclas()) as r:
        r.iniciar()
        assert r.parada() == State.PAUSED
        assert r.proximo() == State.PAUSED
        assert r.eventos() == [(0.0, A_DOWN, "A"), (0.2, A_UP, "A")]
        assert r.controle.texto() == "Passo 2 de 3: Apertar e soltar a tecla B"
        assert r.proximo() == State.PAUSED
        assert [e[1:] for e in r.eventos()] == [(A_DOWN, "A"), (A_UP, "A"), (A_DOWN, "B"), (A_UP, "B")]
        assert r.controle.texto() == "Passo 3 de 3: Apertar e soltar a tecla C"
        assert r.proximo() == State.IDLE
        assert [e[1:] for e in r.eventos()] == [(A_DOWN, "A"), (A_UP, "A"), (A_DOWN, "B"), (A_UP, "B"), (A_DOWN, "C"), (A_UP, "C")]
        assert pressed_balance(r.backend) == {}


def test_a_espera_planejada_entre_os_comandos_nao_e_cumprida(make_engine):
    with roteiro(make_engine, tres_teclas()) as r:
        r.iniciar()
        r.parada()
        r.proximo()
        r.proximo()
        r.proximo()
        # sem o passo a passo seriam B em 5,0 s e C em 10,0 s; aqui cada comando sai na hora em que o usuário clica
        assert r.eventos() == [(0.0, A_DOWN, "A"), (0.2, A_UP, "A"), (0.2, A_DOWN, "B"), (0.4, A_UP, "B"),
                               (0.4, A_DOWN, "C"), (0.6, A_UP, "C")]


def test_o_comando_sai_na_hora_do_clique_nao_na_hora_planejada(make_engine, fake_clock):
    with roteiro(make_engine, tres_teclas()) as r:
        r.iniciar()
        r.parada()
        fake_clock.advance(100.0)  # o usuário ficou 100 s olhando a tela antes do primeiro clique
        r.proximo()
        fake_clock.advance(30.0)
        r.proximo()
        assert r.eventos() == [(100.0, A_DOWN, "A"), (100.2, A_UP, "A"), (130.2, A_DOWN, "B"), (130.4, A_UP, "B")]


def test_o_tempo_dentro_do_comando_continua_o_planejado(make_engine):
    # um comando segurado por 3 s continua segurado por 3 s: o passo a passo só tira a espera ENTRE comandos
    with roteiro(make_engine, make_map([key("A", 0.0, 3.0), key("B", 9.0, 0.2)])) as r:
        r.iniciar()
        r.parada()
        assert r.proximo() == State.PAUSED
        assert r.eventos() == [(0.0, A_DOWN, "A"), (3.0, A_UP, "A")]


def test_o_fim_de_um_comando_ja_comecado_acontece_no_caminho_para_o_proximo_passo(make_engine):
    # A é apertada em 0 e solta em 3; B começa em 1 (no meio de A). Passos: A, B. Soltar A não é um passo.
    with roteiro(make_engine, make_map([key("A", 0.0, 3.0), key("B", 1.0, 0.5)])) as r:
        r.iniciar()
        assert r.parada() == State.PAUSED
        assert r.proximo() == State.PAUSED  # parado antes de B: A está apertada, ainda não foi solta
        assert r.eventos() == [(0.0, A_DOWN, "A")]
        assert r.controle.texto() == "Passo 2 de 2: Apertar e soltar a tecla B"
        assert r.proximo() == State.IDLE
        assert [e[1:] for e in r.eventos()] == [(A_DOWN, "A"), (A_DOWN, "B"), (A_UP, "B"), (A_UP, "A")]
        assert pressed_balance(r.backend) == {}


def test_comandos_desativados_nao_sao_passos(make_engine):
    desativado = key("B", 5.0, 0.2, enabled=False)
    with roteiro(make_engine, make_map([key("A", 0.0, 0.2), desativado, key("C", 10.0, 0.2)])) as r:
        r.iniciar()
        assert r.parada() == State.PAUSED
        assert r.controle.sessao.total == 2
        r.proximo()
        assert r.controle.texto() == "Passo 2 de 2: Apertar e soltar a tecla C"
        r.proximo()
        assert [e[1:] for e in r.eventos()] == [(A_DOWN, "A"), (A_UP, "A"), (A_DOWN, "C"), (A_UP, "C")]


def test_a_velocidade_da_automacao_vale_dentro_do_comando(make_engine):
    with roteiro(make_engine, tres_teclas(speed=2.0)) as r:
        r.iniciar()
        r.parada()
        r.proximo()
        r.proximo()
        # com o dobro da velocidade, apertar por 0,2 s dura 0,1 s; o intervalo de 5 s (2,5 s na velocidade 2) continua pulado
        assert r.eventos() == [(0.0, A_DOWN, "A"), (0.1, A_UP, "A"), (0.1, A_DOWN, "B"), (0.2, A_UP, "B")]


def test_comecar_do_meio_executa_so_do_comando_escolhido_em_diante(make_engine):
    mapa = tres_teclas()
    with roteiro(make_engine, mapa) as r:
        r.iniciar({mapa.commands[1].id})
        assert r.parada() == State.PAUSED
        assert r.controle.sessao.total == 2
        r.proximo()
        r.proximo()
        assert [e[1:] for e in r.eventos()] == [(A_DOWN, "B"), (A_UP, "B"), (A_DOWN, "C"), (A_UP, "C")]


# ------------------------------------------------------------------------------------------ esperas e repetição
def test_o_comando_esperar_continua_esperando_quando_o_passo_roda(make_engine):
    espera = Command(type=InputType.WAIT, start=1.0, conditions=[WaitCondition(type=WaitConditionType.DELAY, timeout=0.5)])
    with roteiro(make_engine, make_map([key("A", 0.0, 0.2), espera, key("B", 5.0, 0.2)])) as r:
        r.iniciar()
        assert r.parada() == State.PAUSED
        r.proximo()  # A
        assert r.controle.texto() == "Passo 2 de 3: Esperar 0,5 s"
        assert r.proximo() == State.PAUSED  # a espera: o motor faz os 0,5 s e para antes de B
        assert r.proximo() == State.IDLE
        # B sai 0,5 s depois de A (a espera do comando), e não 5 s depois (a espera planejada, que o passo a passo pula)
        assert r.eventos() == [(0.0, A_DOWN, "A"), (0.2, A_UP, "A"), (0.7, A_DOWN, "B"), (0.9, A_UP, "B")]


def test_a_condicao_de_um_comando_vale_quando_o_passo_roda(make_engine):
    atrasada = key("A", 0.0, 0.2, conditions=[WaitCondition(type=WaitConditionType.DELAY, timeout=0.5)])
    with roteiro(make_engine, make_map([atrasada, key("B", 5.0, 0.2)])) as r:
        r.iniciar()
        r.parada()
        r.proximo()
        assert r.eventos() == [(0.5, A_DOWN, "A"), (0.7, A_UP, "A")]


def test_e_uma_volta_so_mesmo_com_repeticao_infinita_e_automacao_encadeada(make_engine):
    mapa = tres_teclas(repeat_count=-1, next_map="Outra automação")
    encadeamentos = []
    with roteiro(make_engine, mapa) as r:
        r.motor.on_chain_requested.append(encadeamentos.append)
        r.iniciar()
        assert r.parada() == State.PAUSED
        r.proximo()
        r.proximo()
        assert r.proximo() == State.IDLE  # depois do terceiro comando acabou: sem segunda volta e sem encadear
        join_engine(r.motor)
        assert [e[1:] for e in r.eventos()] == [(A_DOWN, "A"), (A_UP, "A"), (A_DOWN, "B"), (A_UP, "B"), (A_DOWN, "C"), (A_UP, "C")]
        assert encadeamentos == []
        assert r.motor.state.state == State.IDLE
        # a automação do usuário não mudou
        assert mapa.repeat_count == -1 and mapa.next_map == "Outra automação" and len(mapa.commands) == 3


# ------------------------------------------------------------------------------------------ parar e continuar
def test_parar_no_meio_encerra_solta_a_tecla_segurada_e_volta_ao_repouso(make_engine):
    segura = key("A", 0.0, 0.0, action=ActionType.PRESS)
    with roteiro(make_engine, make_map([segura, key("B", 5.0, 0.2)])) as r:
        r.iniciar()
        r.parada()
        assert r.proximo() == State.PAUSED  # A está segurada, parado antes de B
        assert pressed_balance(r.backend) == {"key:A": 1}
        r.controle.parar()
        join_engine(r.motor)
        assert pressed_balance(r.backend) == {}, "a tecla segurada ficou presa"
        assert r.motor.state.state == State.IDLE
        assert "B" not in [alvo for _t, _acao, alvo in r.eventos()]


def test_parar_antes_do_primeiro_passo_nao_envia_nada(make_engine):
    with roteiro(make_engine, tres_teclas()) as r:
        r.iniciar()
        r.parada()
        r.controle.parar()
        join_engine(r.motor)
        assert r.eventos() == [] and r.motor.state.state == State.IDLE


def test_continuar_sem_parar_roda_o_resto_de_uma_vez_cumprindo_as_esperas_entre_os_proximos(make_engine):
    with roteiro(make_engine, tres_teclas()) as r:
        r.iniciar()
        r.parada()
        r.proximo()  # parado antes de B
        assert r.controle.continuar_sem_parar()
        assert r.parada() == State.IDLE
        # B sai na hora (a espera até ele já tinha sido pulada), mas de B para C a espera planejada de 5 s volta a valer
        assert r.eventos() == [(0.0, A_DOWN, "A"), (0.2, A_UP, "A"), (0.2, A_DOWN, "B"), (0.4, A_UP, "B"),
                               (5.2, A_DOWN, "C"), (5.4, A_UP, "C")]


def test_continuar_sem_parar_desde_o_primeiro_passo_roda_a_automacao_toda(make_engine):
    with roteiro(make_engine, tres_teclas()) as r:
        r.iniciar()
        r.parada()
        assert r.controle.continuar_sem_parar()
        assert r.parada() == State.IDLE
        assert [e[1:] for e in r.eventos()] == [(A_DOWN, "A"), (A_UP, "A"), (A_DOWN, "B"), (A_UP, "B"), (A_DOWN, "C"), (A_UP, "C")]


def test_o_clique_em_continuar_que_chega_um_instante_antes_da_parada_nao_deixa_o_motor_preso(make_engine):
    # A janela marca "continuar sem parar" (sessao.ativo = False) quando o motor ainda está RUNNING e já decidiu parar.
    # Ele fica PAUSED mesmo assim; ao receber o aviso, a janela chama `ao_ficar_pausado`, que o libera de novo.
    class ClicouDepoisDeDecidir:
        """Mesma sessão, mas o clique em "Continuar sem parar" chega logo depois da decisão de parar no passo 2."""

        def __init__(self, sessao, controle) -> None:
            self.sessao, self.controle = sessao, controle

        def parar_antes(self, evento, mapa):
            resposta = self.sessao.parar_antes(evento, mapa)
            if resposta and self.sessao.numero == 2:
                self.controle.continuar_sem_parar()  # o motor ainda está RUNNING aqui: só marca a sessão
            return resposta

    with roteiro(make_engine, tres_teclas()) as r:
        r.iniciar()
        assert r.parada() == State.PAUSED
        sessao = r.controle.sessao
        r.motor.passo_a_passo = ClicouDepoisDeDecidir(sessao, r.controle)
        assert r.proximo() == State.PAUSED  # parou antes de B, embora o usuário já tenha pedido para continuar
        assert sessao.ativo is False
        assert not r.controle.parado_num_passo()
        assert r.controle.ao_ficar_pausado() is True
        assert r.parada() == State.IDLE
        assert [e[1:] for e in r.eventos()][-2:] == [(A_DOWN, "C"), (A_UP, "C")]


def test_o_clique_em_proximo_que_chega_no_mesmo_instante_em_que_o_motor_para_nao_se_perde(make_engine):
    # O aviso de estado roda na thread do motor, logo depois de ele virar PAUSED. Um "Próximo passo" disparado aí dentro
    # chama `resume()` antes de o motor chegar ao `wait()`. Se o motor sinalizasse a pausa DEPOIS de mudar o estado, apagaria
    # esse "continuar" e ficaria parado para sempre com o estado RUNNING.
    with roteiro(make_engine, tres_teclas()) as r:
        r.motor.state.on_change(lambda _anterior, novo: r.controle.proximo() if novo == State.PAUSED else None)
        r.iniciar()
        r.ate_o_fim()  # os três passos andaram sozinhos, sem travar
        assert [e[1:] for e in r.eventos()] == [(A_DOWN, "A"), (A_UP, "A"), (A_DOWN, "B"), (A_UP, "B"), (A_DOWN, "C"), (A_UP, "C")]


# ------------------------------------------------------------------------------------------ cuidados do motor
def test_um_defeito_no_gancho_desliga_o_passo_a_passo_e_a_execucao_segue(make_engine, runtime_log):
    class Quebrado:
        def parar_antes(self, evento, mapa):
            raise RuntimeError("falhou de propósito")

    motor, backend = make_engine()
    motor.passo_a_passo = Quebrado()
    terminou, erros = run_to_end(motor, make_map([key("A", 0.0, 0.2)]))
    assert terminou and not erros
    assert events_of(backend) == [(0.0, "key_down", "A"), (0.2, "key_up", "A")]
    assert motor.passo_a_passo is None
    assert any("PASSO A PASSO gancho desligado erro=RuntimeError: falhou de propósito" in linha for linha in runtime_log), runtime_log


def test_parar_pedido_dentro_da_decisao_de_parar_nao_trava_o_motor(make_engine):
    # O usuário aperta Parar justo quando o motor decide parar no passo: o motor sai, sem esperar um "próximo" que não virá.
    motor, backend = make_engine()

    class ParaNaDecisao:
        def parar_antes(self, evento, mapa):
            motor.stop()  # na thread do motor, em ponto exato
            return True

    motor.passo_a_passo = ParaNaDecisao()
    motor.run(make_map([key("A", 0.0, 0.2)]))
    join_engine(motor)
    assert backend.events == [] and motor.state.state == State.IDLE


# As quatro respostas de `_parar_para_o_passo`, uma por situação do motor. É o ponto em que a thread do motor decide parar
# e depende de outra thread (o usuário), então cada situação é conferida direto, sem depender de quem chega primeiro.
def test_parar_para_o_passo_com_o_motor_rodando_apaga_o_sinal_antes_de_avisar_a_pausa(make_engine):
    motor, _ = make_engine()
    motor.state.transition_to(State.RUNNING)
    vistos = []
    motor.state.on_change(lambda _anterior, novo: vistos.append((novo, motor._pause_event.is_set())))
    assert motor._parar_para_o_passo() is True
    # quando o aviso de PAUSED sai, o sinal de pausa já está apagado: um "continuar" feito a partir do aviso não se perde
    assert vistos == [(State.PAUSED, False)]
    assert motor.state.state == State.PAUSED and not motor._pause_event.is_set()


def test_parar_para_o_passo_com_o_motor_ja_pausado_devolve_true_e_nao_muda_nada(make_engine):
    motor, _ = make_engine()
    motor.state.transition_to(State.RUNNING)
    motor.pause()  # a pausa do motor, feita por outro caminho
    vistos = []
    motor.state.on_change(lambda _anterior, novo: vistos.append(novo))
    assert motor._parar_para_o_passo() is True
    assert vistos == [] and motor.state.state == State.PAUSED and not motor._pause_event.is_set()


@pytest.mark.parametrize("estado", [State.IDLE, State.STOPPING, State.ERROR, State.RECORDING])
def test_parar_para_o_passo_nao_para_um_motor_que_nao_esta_rodando(make_engine, estado):
    motor, _ = make_engine(state=StateManager(estado))
    assert motor._parar_para_o_passo() is False
    assert motor.state.state == estado and motor._pause_event.is_set()


def test_parar_para_o_passo_devolve_false_e_solta_o_sinal_se_o_estado_mudou_no_meio(make_engine, monkeypatch):
    # O usuário apertou Parar entre o motor ler "RUNNING" e tentar virar PAUSED: a transição é recusada.
    motor, _ = make_engine()
    motor.state.transition_to(State.RUNNING)

    def recusa(alvo):
        raise InvalidStateTransition(State.STOPPING, alvo)

    monkeypatch.setattr(motor.state, "transition_to", recusa)
    assert motor._parar_para_o_passo() is False
    assert motor._pause_event.is_set(), "o sinal ficou apagado e a thread do motor travaria na próxima pausa"


def test_pede_passo_sem_gancho_e_sempre_falso(make_engine):
    motor, _ = make_engine()
    assert motor.passo_a_passo is None
    assert motor._pede_passo(object()) is False
