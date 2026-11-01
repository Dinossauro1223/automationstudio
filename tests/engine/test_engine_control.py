"""Motor de execução: pausa, parada, parada de emergência, erros, execução exclusiva e encadeamento.

Pausa e parada são injetadas de DENTRO do backend (HookBackend) ou dos observadores do motor, na thread do motor,
em pontos exatos da execução. Assim não há `sleep` para "esperar o motor chegar lá" e os testes não dependem de timing.
"""
import threading
import time

import pytest

from automationstudio.core import AutomationMap, InvalidStateTransition, State
from automationstudio.input_system import MockInputBackend
from testsupport.fakes import HookBackend
from testsupport.helpers import events_of, join_engine, key, make_map, pressed_balance, run_to_end


# --------------------------------------------------------------------------------------------- pausa
def test_pausa_congela_a_timeline_e_a_retomada_continua_do_ponto(make_engine, hook_backend, fake_clock):
    motor, backend = make_engine(backend=hook_backend)
    pausou, terminou = threading.Event(), threading.Event()
    hook_backend.hooks[1] = lambda: (motor.pause(), pausou.set())  # logo depois do key_down de A
    motor.on_finished.append(terminou.set)
    motor.run(make_map([key("A", 0.0, 0.2), key("B", 0.5, 0.2)]))

    assert pausou.wait(10)
    assert motor.state.state == State.PAUSED
    time.sleep(0.1)  # um motor que ignorasse a pausa já teria terminado (o relógio é virtual)
    assert events_of(backend) == [(0.0, "key_down", "A")]

    fake_clock.advance(10.0)  # 10 s de pausa: não podem contar como tempo da timeline
    motor.resume()
    assert terminou.wait(10)
    assert events_of(backend) == [
        (0.0, "key_down", "A"), (10.2, "key_up", "A"), (10.5, "key_down", "B"), (10.7, "key_up", "B")]
    assert motor.state.state == State.IDLE


def test_pausa_e_retomada_fora_de_execucao_sao_ignoradas(make_engine):
    motor, _backend = make_engine()
    motor.pause()
    motor.resume()
    assert motor.state.state == State.IDLE


# Achado 2.11 (md/ESPEC_PAUSA_TECLAS.md): as teclas F9 e F10 chamam pause() e resume() de OUTRA thread (a da janela) e
# precisam saber se algo mudou (para dizer ao usuário) e sobreviver a uma corrida com o fim da execução.
def test_pause_e_resume_dizem_se_mudaram_o_estado(make_engine, hook_backend):                                        # PAU-01 / PAU-02
    motor, _backend = make_engine(backend=hook_backend)
    pausou, terminou, da_thread = threading.Event(), threading.Event(), []
    hook_backend.hooks[1] = lambda: (da_thread.append(motor.pause()), pausou.set())  # logo depois do key_down de A
    motor.on_finished.append(terminou.set)
    motor.run(make_map([key("A", 0.0, 0.2), key("B", 0.5, 0.2)]))

    assert pausou.wait(10)
    assert da_thread == [True], "pause() em execução devolve True"
    assert motor.pause() is False, "já pausado: nada a pausar"
    assert motor.state.state == State.PAUSED
    assert motor.resume() is True
    assert terminou.wait(10)
    assert motor.resume() is False, "terminou: nada a retomar"
    assert motor.state.state == State.IDLE


def test_pause_e_resume_fora_de_execucao_devolvem_falso_e_nao_mexem_em_nada(make_engine):                          # PAU-03
    motor, _backend = make_engine()
    assert motor.pause() is False and motor.resume() is False
    assert motor.state.state == State.IDLE and motor._pause_event.is_set()
    motor.state.transition_to(State.RECORDING)  # gravando também não é "executando"
    assert motor.pause() is False and motor.resume() is False
    assert motor.state.state == State.RECORDING and motor._pause_event.is_set()


def test_durante_a_pausa_as_teclas_seguradas_continuam_seguradas_e_o_fim_da_execucao_as_solta(make_engine, hook_backend):   # PAU-01 (o que NÃO muda)
    """Pausar não solta o que estava apertado (md/ESPEC_PAUSA_TECLAS.md, seção 2): quem quiser soltar usa Parar. Fixa o
    comportamento de hoje para que uma mudança nele seja decidida, não acidental."""
    motor, backend = make_engine(backend=hook_backend)
    pausou, terminou = threading.Event(), threading.Event()
    # A fica apertada de 0 a 0,5 s e B de 0,1 a 0,3 s. O gancho roda DENTRO do envio de B, quando A já está registrada como
    # apertada (com um gancho no envio de A, o motor ainda não a teria registrado e uma pausa que soltasse tudo não soltaria nada).
    hook_backend.hooks[2] = lambda: (motor.pause(), pausou.set())
    motor.on_finished.append(terminou.set)
    motor.run(make_map([key("A", 0.0, 0.5), key("B", 0.1, 0.2)]))

    assert pausou.wait(10)
    time.sleep(0.1)
    assert events_of(backend) == [(0.0, "key_down", "A"), (0.1, "key_down", "B")], "nada novo durante a pausa"
    assert pressed_balance(backend) == {"key:A": 1, "key:B": 1}, "pausar não solta o que estava apertado"
    assert motor.resume() is True
    assert terminou.wait(10)
    assert pressed_balance(backend) == {}, "no fim, nada fica apertado"


def _perde_a_corrida(motor, monkeypatch):
    """Faz a troca de estado falhar como falharia se a execução terminasse entre a conferência e a troca."""
    def troca(alvo):
        raise InvalidStateTransition(State.STOPPING, alvo)
    monkeypatch.setattr(motor.state, "transition_to", troca)


def test_pausa_no_instante_em_que_a_execucao_termina_nao_levanta_erro_nem_prende_a_thread(make_engine, monkeypatch):   # PAU-04
    motor, _backend = make_engine()
    motor.state.transition_to(State.RUNNING)  # como se a thread do motor estivesse executando
    _perde_a_corrida(motor, monkeypatch)
    assert motor.pause() is False
    assert motor._pause_event.is_set(), "uma pausa que não aconteceu não pode deixar a thread do motor parada"


def test_retomada_no_instante_em_que_a_execucao_e_parada_nao_levanta_erro_nem_solta_a_pausa(make_engine, monkeypatch):   # PAU-04
    motor, _backend = make_engine()
    motor.state.transition_to(State.RUNNING)
    motor.state.transition_to(State.PAUSED)
    motor._pause_event.clear()  # como `pause()` deixa
    _perde_a_corrida(motor, monkeypatch)
    assert motor.resume() is False
    assert not motor._pause_event.is_set(), "uma retomada que não aconteceu não pode soltar a pausa (quem para é `stop`)"


# --------------------------------------------------------------------------------------------- parada
def test_parada_pelo_observador_solta_a_tecla_e_volta_a_idle(make_engine):
    motor, backend = make_engine()
    fim, chamadas = [], []
    motor.on_finished.append(lambda: fim.append(1))
    motor.on_progress.append(lambda atual, total: chamadas.append(1) or motor.stop())  # para logo após o 1º evento
    motor.run(make_map([key("A", 0.0, 0.5), key("B", 0.6, 0.1)]))
    join_engine(motor)
    assert events_of(backend) == [(0.0, "key_down", "A"), (0.0, "key_up", "A")]
    assert pressed_balance(backend) == {}
    assert motor.state.state == State.IDLE
    assert len(chamadas) == 1 and fim == []  # contrato atual: on_finished só no fim natural


def test_parada_nao_dispara_fim_nem_encadeamento(make_engine):
    motor, _backend = make_engine()
    sinais = []
    motor.on_finished.append(lambda: sinais.append("fim"))
    motor.on_chain_requested.append(lambda nome: sinais.append(f"encadear:{nome}"))
    motor.on_progress.append(lambda *_: motor.stop())
    motor.run(make_map([key("A", 0.0, 0.2), key("B", 0.5, 0.2)], next_map="Outro"))
    join_engine(motor)
    assert sinais == []


def test_encadeamento_vem_depois_do_fim_natural(make_engine):
    motor, _backend = make_engine()
    sinais = []
    motor.on_finished.append(lambda: sinais.append("fim"))
    motor.on_chain_requested.append(lambda nome: sinais.append(f"encadear:{nome}"))
    terminou, erros = run_to_end(motor, make_map([key("A", 0.0, 0.1)], next_map="Outro"))
    assert terminou and not erros
    join_engine(motor)
    assert sinais == ["fim", "encadear:Outro"]


def test_parada_durante_o_envio_de_uma_tecla_nao_deixa_a_tecla_presa(make_engine, hook_backend):
    # `stop()` chega DEPOIS de key_down ser enviado e ANTES de o motor registrar a tecla como pressionada. É a janela
    # que o botão "Parar" tem quando é clicado no instante em que o motor envia uma tecla. Achado 2.01 (25.5):
    # no 25.4 a tecla ficava presa porque stop() só soltava o que já estava registrado.
    motor, backend = make_engine(backend=hook_backend)
    hook_backend.hooks[1] = motor.stop
    motor.run(make_map([key("A", 0.0, 0.5)]))
    join_engine(motor)
    assert pressed_balance(backend) == {}, backend.events
    assert motor.state.state == State.IDLE


def test_parada_com_o_motor_pausado_acorda_a_thread_e_solta_tudo(make_engine, hook_backend):
    motor, backend = make_engine(backend=hook_backend)
    pausou = threading.Event()
    hook_backend.hooks[2] = lambda: (motor.pause(), pausou.set())  # pausa logo depois do 2º evento (A solta)
    motor.run(make_map([key("A", 0.0, 0.1), key("B", 0.2, 5.0)]))  # o motor para antes de pressionar B
    assert pausou.wait(10)
    motor.stop(wait=True)
    assert not motor._thread.is_alive()
    assert motor.state.state == State.IDLE
    assert pressed_balance(backend) == {}


def test_parada_de_emergencia_funciona_com_o_motor_pausado(make_engine, hook_backend):
    motor, backend = make_engine(backend=hook_backend)
    pausou = threading.Event()
    hook_backend.hooks[1] = lambda: (motor.pause(), pausou.set())  # pausa com A pressionada
    motor.run(make_map([key("A", 0.0, 5.0)]))
    assert pausou.wait(10)
    motor.emergency_stop()
    assert not motor._thread.is_alive()
    assert motor.state.state == State.IDLE
    assert pressed_balance(backend) == {}


def test_parada_de_emergencia_nao_levanta_quando_o_backend_falha_ao_soltar(make_engine, fake_clock):
    class FalhaAoSoltar(HookBackend):
        def key_up(self, key):  # noqa: A002
            raise RuntimeError("driver não respondeu")

    backend = FalhaAoSoltar(clock=fake_clock)
    motor, _ = make_engine(backend=backend)
    pausou = threading.Event()
    backend.hooks[1] = lambda: (motor.pause(), pausou.set())
    motor.run(make_map([key("A", 0.0, 5.0)]))
    assert pausou.wait(10)
    motor.emergency_stop()  # não pode levantar
    assert motor.state.state == State.IDLE


def test_parar_com_o_motor_ocioso_nao_faz_nada(make_engine):
    motor, backend = make_engine()
    motor.stop()
    motor.stop(wait=True)
    assert not motor._stop_requested.is_set(), "um stop() ocioso deixou a parada armada para a próxima execução"
    motor.emergency_stop()
    assert motor.state.state == State.IDLE and backend.events == []


def test_parada_durante_o_intervalo_entre_repeticoes_encerra_a_execucao(make_engine, fake_clock, monkeypatch):
    # O intervalo entre repetições dorme em pedaços de 20 ms consultando a parada. Com o relógio virtual, o número
    # de pedaços mede a pressa: parando no 3º pedaço do intervalo de 5 s, o motor dorme 3 vezes (e não 250).
    motor, backend = make_engine()
    dormir, depois_da_passada = fake_clock.sleep, []

    def dormir_e_parar(segundos):
        dormir(segundos)
        if any(acao == "key_up" for _t, acao, _x in backend.events):  # a 1ª passada já terminou: é o intervalo
            depois_da_passada.append(segundos)
            if len(depois_da_passada) == 3:
                motor.stop()

    monkeypatch.setattr(fake_clock, "sleep", dormir_e_parar)
    fins = []
    motor.on_finished.append(lambda: fins.append(1))
    motor.run(make_map([key("A", 0.0, 0.1)], repeat_count=-1, repeat_interval=5.0))
    join_engine(motor)
    assert len(depois_da_passada) == 3, f"o motor seguiu dormindo depois da parada ({len(depois_da_passada)} pedaços)"
    assert events_of(backend) == [(0.0, "key_down", "A"), (0.1, "key_up", "A")], "só a 1ª passada pode ter rodado"
    assert motor.state.state == State.IDLE and fins == []


def test_nova_execucao_para_a_anterior_antes_de_comecar(make_engine, hook_backend):
    motor, backend = make_engine(backend=hook_backend)
    comecou, fins = threading.Event(), []
    hook_backend.hooks[1] = comecou.set
    motor.on_finished.append(lambda: fins.append(1))
    motor.run(make_map([key("A", 0.0, 0.1)], repeat_count=-1, name="Infinito"))
    assert comecou.wait(10)

    terminou, erros = run_to_end(motor, make_map([key("Z", 0.0, 0.1)], name="Curto"))
    assert terminou and not erros
    join_engine(motor)
    alvos = [alvo for _t, _a, alvo in events_of(backend)]
    ultimo_a, primeiro_z = len(alvos) - 1 - alvos[::-1].index("A"), alvos.index("Z")
    assert ultimo_a < primeiro_z, "o mapa antigo ainda enviava input depois de o novo começar"
    assert pressed_balance(backend) == {}
    assert len(fins) == 1  # só o mapa curto terminou naturalmente


# --------------------------------------------------------------------------------------------- erros
def test_erro_do_backend_solta_o_que_estava_pressionado_e_volta_a_idle(make_engine, fake_clock):
    class FalhaNoB(MockInputBackend):
        def key_down(self, key):  # noqa: A002
            if key == "B":
                raise RuntimeError("falhou")
            super().key_down(key)

    backend = FalhaNoB(clock=fake_clock)
    motor, _ = make_engine(backend=backend)
    fim = []
    motor.on_finished.append(lambda: fim.append(1))
    terminou, erros = run_to_end(motor, make_map([key("A", 0.0, 0.5), key("B", 0.2, 0.1)]))
    assert terminou and [str(e) for e in erros] == ["falhou"]
    join_engine(motor)
    assert events_of(backend) == [(0.0, "key_down", "A"), (0.2, "key_up", "A")]  # A solta no instante do erro
    assert motor.state.state == State.IDLE and fim == []


def test_tecla_desconhecida_no_backend_vira_erro_de_execucao(make_engine, fake_clock):
    class Rigido(MockInputBackend):
        def key_down(self, key):  # noqa: A002
            raise ValueError(f"Tecla não suportada: {key}")

    motor, _ = make_engine(backend=Rigido(clock=fake_clock))
    terminou, erros = run_to_end(motor, make_map([key("ZZZ", 0.0, 0.5)]))
    assert terminou and len(erros) == 1 and isinstance(erros[0], ValueError)
    assert motor.state.state == State.IDLE


def test_erro_nao_dispara_fim_nem_encadeamento(make_engine, fake_clock):
    class Quebrado(MockInputBackend):
        def key_down(self, key):  # noqa: A002
            raise RuntimeError("x")

    motor, _ = make_engine(backend=Quebrado(clock=fake_clock))
    sinais = []
    motor.on_finished.append(lambda: sinais.append("fim"))
    motor.on_chain_requested.append(lambda nome: sinais.append(nome))
    terminou, erros = run_to_end(motor, make_map([key("A", 0.0, 0.1)], next_map="Outro"))
    assert terminou and erros
    join_engine(motor)
    assert sinais == []


def test_mapa_pode_ser_executado_de_novo_depois_de_um_erro(make_engine, fake_clock):
    falhar = {"ligado": True}

    class Instavel(MockInputBackend):
        def key_down(self, key):  # noqa: A002
            if falhar["ligado"]:
                raise RuntimeError("falha momentânea")
            super().key_down(key)

    backend = Instavel(clock=fake_clock)
    motor, _ = make_engine(backend=backend)
    mapa = make_map([key("A", 0.0, 0.1)])
    terminou, erros = run_to_end(motor, mapa)
    assert terminou and erros
    join_engine(motor)
    falhar["ligado"] = False
    terminou, erros = run_to_end(motor, mapa)
    assert terminou and not erros
    assert [a for _t, a, _x in events_of(backend)] == ["key_down", "key_up"]


def test_estado_compartilhado_com_gravador_impede_execucao(make_engine):
    # A execução exclusiva (item 9 do roteiro) vem da máquina de estados compartilhada.
    from automationstudio.core import InvalidStateTransition, StateManager
    estado = StateManager(State.RECORDING)
    motor, backend = make_engine(state=estado)
    with pytest.raises(InvalidStateTransition):
        motor.run(make_map([key("A", 0.0, 0.1)]))
    assert estado.state == State.RECORDING and backend.events == [] and motor._thread is None
