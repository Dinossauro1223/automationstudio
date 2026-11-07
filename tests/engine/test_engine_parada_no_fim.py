"""Motor: a parada que chega no mesmo instante em que a execução termina sozinha.

`stop()` roda na thread da janela ou do atalho; o fim natural roda na thread do motor (`_finish`). Os dois decidem pelo
estado que leram um instante antes e mudam o estado em seguida. Se um mudar o estado entre a leitura e a troca do outro, a
troca deixa de ser permitida (`InvalidStateTransition`). Antes desta correção isso aparecia assim, com o Parar apertado
no instante em que o mapa acabava:

  * `stop()` levantava `InvalidStateTransition` para quem o chamou (o botão, a tecla de parada) e `emergency_stop()`,
    que promete nunca levantar, também;
  * `_finish()` levantava dentro da thread do motor; o `except` da thread tentava então a troca para ERROR, que também
    falhava, e a thread morria com a exceção, sem avisar o fim da execução;
  * o mesmo acontecia com o erro de execução de verdade (o backend recusa uma tecla): se a parada terminava no instante
    em que o motor ia registrar o erro, a troca para ERROR falhava, a thread morria e o erro nunca chegava ao usuário.

O defeito foi visto de verdade, sem nenhum artifício no código do motor: 40 mil execuções de um mapa de 1 ms, com o Parar
chegando em instantes aleatórios ao redor do fim, deram 1 thread do motor morta com o intervalo padrão de troca de threads do
Python (5 ms); com o intervalo reduzido a 1 µs, para ampliar a janela, 20 mil execuções deram 7 `stop()` que levantaram e 4
threads mortas. Com operações de controle aleatórias (executar, pausar, continuar, parar) e um backend que falha em 15% das
teclas, 20 mil execuções a 1 µs deram 7 threads mortas no tratador de erro. A janela é de microssegundos; por isso os testes
daqui a abrem de propósito: `_EstadoComGancho` roda uma função EXATAMENTE antes da troca de estado escolhida, e a função faz
a outra ponta terminar o seu trabalho nesse ponto. Nada aqui depende de tempo.
"""
import threading

import pytest

from automationstudio.core import State, StateManager
from automationstudio.input_system import ProcessReadinessError
from testsupport.helpers import events_of, join_engine, key, make_map, pressed_balance


class _EstadoComGancho(StateManager):
    """`StateManager` que roda um gancho UMA vez, logo antes da troca para o estado escolhido (a janela da corrida).

    O gancho roda na thread que pediu a troca, antes de ela ser aplicada; se ele a invalidar (o estado muda para um lugar
    de onde ela não é mais permitida), a troca levanta `InvalidStateTransition` como levantaria na corrida de verdade."""

    def __init__(self):
        super().__init__()
        self.antes_de = {}  # estado de destino -> função que roda uma vez antes da troca

    def transition_to(self, alvo):
        gancho = self.antes_de.pop(alvo, None)
        if gancho is not None:
            gancho()
        super().transition_to(alvo)


def _excecoes_de_threads(monkeypatch) -> list:
    """Guarda o que a thread do motor levantaria sem ninguém ver (o `threading.excepthook` imprime e segue)."""
    vistas: list = []
    monkeypatch.setattr(threading, "excepthook", lambda args: vistas.append(args.exc_value))
    return vistas


def _parada_de_outra_thread(motor):
    """Uma parada completa, feita por outra thread (a janela), enquanto quem chama espera."""
    def parar():
        outra = threading.Thread(target=motor.stop)
        outra.start()
        outra.join(10)
        assert not outra.is_alive()
    return parar


# --------------------------------------------------------------------------------- a parada perde para o fim
@pytest.mark.parametrize("parar", [lambda m: m.stop(), lambda m: m.stop(wait=True), lambda m: m.emergency_stop()],
                         ids=["stop", "stop-esperando", "emergency_stop"])
def test_parar_no_instante_em_que_a_execucao_termina_sozinha_nao_levanta_erro(make_engine, hook_backend, parar):
    estado = _EstadoComGancho()
    motor, backend = make_engine(backend=hook_backend, state=estado)
    dentro, liberar = threading.Event(), threading.Event()
    hook_backend.hooks[1] = lambda: (dentro.set(), liberar.wait(10))  # a thread do motor espera depois do key_down de A
    fins = []
    motor.on_finished.append(lambda: fins.append(1))
    motor.run(make_map([key("A", 0.0, 0.2)]))
    assert dentro.wait(10)
    assert motor.state.state == State.RUNNING

    def a_execucao_termina_aqui():  # na thread que chamou `stop()`, entre a leitura do estado e a troca para STOPPING
        liberar.set()
        join_engine(motor)

    estado.antes_de[State.STOPPING] = a_execucao_termina_aqui
    try:
        parar(motor)  # a troca para STOPPING falha: a execução já tinha acabado. Não pode levantar.
    finally:
        liberar.set()
        motor._stop_requested.set()
    assert estado.antes_de == {}, "o cenário exige que a troca tenha sido tentada"
    assert fins == [1], "a execução terminou sozinha e avisou o fim uma vez"
    assert motor.state.state == State.IDLE
    assert events_of(backend) == [(0.0, "key_down", "A"), (0.2, "key_up", "A")]
    assert pressed_balance(backend) == {}


def test_duas_paradas_ao_mesmo_tempo_a_que_chega_depois_nao_levanta_erro(make_engine, hook_backend):
    # No fim de `stop()` ("parando" volta a "ocioso"), a outra parada (ou o fim natural) pode ter chegado ao ocioso antes.
    estado = _EstadoComGancho()
    motor, _backend = make_engine(backend=hook_backend, state=estado)
    dentro, liberar = threading.Event(), threading.Event()
    hook_backend.hooks[1] = lambda: (dentro.set(), liberar.wait(10))
    motor.run(make_map([key("A", 0.0, 5.0)]))
    assert dentro.wait(10)
    estado.antes_de[State.IDLE] = lambda: estado.transition_to(State.IDLE)  # a outra ponta chega ao ocioso primeiro
    try:
        motor.stop()
    finally:
        liberar.set()
        motor._stop_requested.set()
        join_engine(motor)
    assert estado.antes_de == {}, "o cenário exige que a troca final tenha sido tentada"
    assert motor.state.state == State.IDLE


# --------------------------------------------------------------------------------- o fim perde para a parada
@pytest.mark.parametrize("destino", [State.STOPPING, State.IDLE], ids=["antes-de-parando", "antes-de-ocioso"])
def test_fim_natural_no_instante_de_uma_parada_nao_mata_a_thread_do_motor_nem_some_com_o_aviso(make_engine, monkeypatch, destino):
    # A parada (de outra thread) termina inteira entre duas trocas de estado do `_finish`: a execução acabou sozinha,
    # então ela avisa o fim; nenhuma exceção sai da thread e nenhum erro é mostrado ao usuário.
    estado = _EstadoComGancho()
    motor, backend = make_engine(state=estado)
    fins, erros = [], []
    motor.on_finished.append(lambda: fins.append(1))
    motor.on_error.append(erros.append)
    excecoes = _excecoes_de_threads(monkeypatch)
    estado.antes_de[destino] = _parada_de_outra_thread(motor)  # roda na thread do motor, dentro de `_finish`
    motor.run(make_map([key("A", 0.0, 0.1)]))
    join_engine(motor)
    assert estado.antes_de == {}, "o cenário exige que a troca do `_finish` tenha sido tentada"
    assert excecoes == [], f"a thread do motor morreu com {excecoes!r}"
    assert erros == [], "a corrida entre o fim e a parada não é um erro de execução"
    assert fins == [1]
    assert motor.state.state == State.IDLE
    assert events_of(backend) == [(0.0, "key_down", "A"), (0.1, "key_up", "A")]
    assert pressed_balance(backend) == {}


@pytest.mark.parametrize("falha", [RuntimeError("o backend recusou a tecla"), ProcessReadinessError("o aplicativo não abriu")],
                         ids=["erro-de-execucao", "espera-por-aplicativo"])
def test_erro_de_execucao_no_instante_de_uma_parada_nao_mata_a_thread_e_continua_sendo_avisado(make_engine, hook_backend, monkeypatch, falha):
    # A parada (de outra thread) termina inteira entre o erro do backend e a troca do motor para ERROR. O erro é de
    # verdade (o backend recusou, o aplicativo não abriu) e continua indo para quem o escuta; a thread não morre.
    estado = _EstadoComGancho()
    motor, backend = make_engine(backend=hook_backend, state=estado)
    erros = []
    motor.on_error.append(erros.append)
    excecoes = _excecoes_de_threads(monkeypatch)

    def o_backend_falha():
        raise falha

    hook_backend.hooks[2] = o_backend_falha  # logo depois do key_up de A
    estado.antes_de[State.ERROR] = _parada_de_outra_thread(motor)
    motor.run(make_map([key("A", 0.0, 0.2)]))
    join_engine(motor)
    assert estado.antes_de == {}, "o cenário exige que a troca para ERROR tenha sido tentada"
    assert excecoes == [], f"a thread do motor morreu com {excecoes!r}"
    assert erros == [falha]
    assert motor.state.state == State.IDLE
    assert {alvo: n for alvo, n in pressed_balance(backend).items() if n > 0} == {}  # soltar de novo o já solto é inofensivo


def test_parada_pedida_no_instante_do_fim_cancela_o_encadeamento(make_engine, monkeypatch):
    # Quem apertou o Parar no instante em que o mapa acabava não quer que o mapa seguinte comece.
    estado = _EstadoComGancho()
    motor, _backend = make_engine(state=estado)
    encadeados = []
    motor.on_chain_requested.append(encadeados.append)
    excecoes = _excecoes_de_threads(monkeypatch)
    estado.antes_de[State.STOPPING] = _parada_de_outra_thread(motor)
    motor.run(make_map([key("A", 0.0, 0.1)], next_map="Seguinte"))
    join_engine(motor)
    assert excecoes == []
    assert encadeados == [], "o mapa seguinte começou depois de uma parada pedida"
    assert motor.state.state == State.IDLE


def test_fim_natural_sem_parada_continua_encadeando(make_engine):
    # O controle do teste acima: sem parada, o encadeamento acontece, uma vez, com o nome do mapa seguinte.
    motor, _backend = make_engine()
    encadeados = []
    motor.on_chain_requested.append(encadeados.append)
    motor.run(make_map([key("A", 0.0, 0.1)], next_map="Seguinte"))
    join_engine(motor)
    assert encadeados == ["Seguinte"]
