"""O controlador de pausar e continuar (automationstudio/controle_ui.py) com uma janela de mentira e o motor de verdade.

Achado 2.11 (md/ESPEC_PAUSA_TECLAS.md): as teclas F9 e F10 eram registradas e nada as atendia. O controlador é o que a janela
chama quando elas disparam: pede ao motor para pausar ou continuar e diz ao usuário, na barra de status, o que aconteceu. O
motor é o verdadeiro (com o backend e o relógio virtual dos testes de motor); a janela só tem o que o controlador usa
(testsupport/janela_falsa.py). Nada aqui precisa do Qt.

Critérios da ficha: PAU-01, PAU-02, PAU-03 e PAU-04 (o lado da janela). A ligação do disparo da tecla a estes métodos está em
tests/static/test_ligacao_controle.py (sem Qt) e em tests/gui/test_controle_janela.py (Qt de verdade).
"""
import threading
import time

import pytest

from automationstudio.core import InvalidStateTransition, State
from automationstudio.project import AppSettings
from testsupport.helpers import events_of, key, make_map
from testsupport.janela_falsa import abrir

# Como levar um motor parado (IDLE) a cada estado, só por transições permitidas e sem thread nenhuma: o controlador só olha o estado.
CAMINHOS = {
    State.IDLE: (), State.RECORDING: (State.RECORDING,), State.RUNNING: (State.RUNNING,),
    State.PAUSED: (State.RUNNING, State.PAUSED), State.STOPPING: (State.RUNNING, State.STOPPING),
}
PAUSADA = "Automação pausada. Aperte F10 para continuar."
RETOMADA = "Automação retomada."


def _janela(pasta, motor, estado=State.IDLE):
    janela = abrir(pasta, engine=motor)
    for passo in CAMINHOS[estado]:
        motor.state.transition_to(passo)
    return janela


def _perde_a_corrida(motor, monkeypatch):
    """A troca de estado falha como falharia se a execução terminasse (ou fosse parada) entre a conferência e a troca."""
    def troca(alvo):
        raise InvalidStateTransition(State.STOPPING, alvo)
    monkeypatch.setattr(motor.state, "transition_to", troca)


# ------------------------------------------------------------------------------------------------ PAU-01 e PAU-02
def test_f9_pausa_a_execucao_e_f10_a_continua_do_ponto_sem_repetir_nem_pular(tmp_path, make_engine, hook_backend, fake_clock):   # PAU-01 / PAU-02
    motor, backend = make_engine(backend=hook_backend)
    janela = abrir(tmp_path, engine=motor)
    pausou, terminou, devolvido = threading.Event(), threading.Event(), []
    hook_backend.hooks[1] = lambda: (devolvido.append(janela.controle.pausar()), pausou.set())  # F9 logo depois do key_down de A
    motor.on_finished.append(terminou.set)
    motor.run(make_map([key("A", 0.0, 0.2), key("B", 0.5, 0.2)]))

    assert pausou.wait(10)
    assert devolvido == [True]
    assert motor.state.state == State.PAUSED
    assert janela.status == [PAUSADA]
    time.sleep(0.1)  # um motor que ignorasse a pausa já teria terminado (o relógio é virtual)
    assert events_of(backend) == [(0.0, "key_down", "A")], "nenhuma entrada nova durante a pausa"

    fake_clock.advance(10.0)  # 10 s de pausa: não contam como tempo da timeline
    assert janela.controle.retomar() is True
    assert terminou.wait(10)
    assert events_of(backend) == [
        (0.0, "key_down", "A"), (10.2, "key_up", "A"), (10.5, "key_down", "B"), (10.7, "key_up", "B")], \
        "a retomada segue do ponto onde parou: nada repetido, nada pulado"
    assert janela.status == [PAUSADA, RETOMADA]
    assert motor.state.state == State.IDLE


def test_a_mensagem_cita_a_tecla_de_continuar_que_esta_configurada(tmp_path, make_engine):                                # PAU-01
    motor, _backend = make_engine()
    janela = _janela(tmp_path, motor, State.RUNNING)
    janela.settings.set_control_hotkeys({"resume": "CTRL+F10"})
    assert janela.controle.pausar() is True
    assert janela.status == ["Automação pausada. Aperte CTRL+F10 para continuar."]


@pytest.mark.parametrize("tecla", ["+", "F9", "F12"])
def test_se_a_tecla_de_continuar_nao_esta_ativa_a_mensagem_nao_manda_aperta_la(tmp_path, make_engine, tecla):               # PAU-01
    """Inválida ("+"), igual à de pausar (F9) ou igual à de emergência (F12, que tem prioridade): a 25.8 deixa a tecla de
    continuar sem registro e avisa na abertura. A pausa acontece mesmo assim (pausar é inofensivo), mas a mensagem não pode
    mandar apertar uma tecla que não faz nada: aponta o botão de parar."""
    motor, _backend = make_engine()
    janela = _janela(tmp_path, motor, State.RUNNING)
    janela.settings.set_control_hotkeys({"resume": tecla})
    janela._register_all_hotkeys()
    assert janela.controle.pausar() is True
    assert motor.state.state == State.PAUSED
    (texto,) = janela.status
    assert texto.startswith("Automação pausada.") and "não está ativa" in texto and "botão de parar" in texto, texto
    assert "Aperte" not in texto, texto


def test_o_controlador_le_as_configuracoes_na_hora_mesmo_depois_de_trocarem_o_objeto(tmp_path, make_engine):               # PAU-01
    """O editor de configurações troca `janela.settings` por outro objeto quando a pasta de dados muda (como no controlador da
    ativação): uma referência guardada na criação mostraria a tecla da pasta antiga."""
    motor, _backend = make_engine()
    janela = _janela(tmp_path / "a", motor, State.RUNNING)
    outras = AppSettings(tmp_path / "b")
    outras.set_control_hotkeys({"resume": "F7"})
    janela.settings = outras
    assert janela.controle.pausar() is True
    assert janela.status == ["Automação pausada. Aperte F7 para continuar."]


def test_o_controlador_usa_o_motor_que_a_janela_tem_na_hora(tmp_path, make_engine):                                       # PAU-01
    primeiro, _ = make_engine()
    segundo, _ = make_engine()
    janela = _janela(tmp_path, primeiro)
    janela.engine = segundo
    segundo.state.transition_to(State.RUNNING)
    assert janela.controle.pausar() is True
    assert segundo.state.state == State.PAUSED and primeiro.state.state == State.IDLE


def test_pausar_e_continuar_de_novo_cada_vez_diz_o_que_aconteceu(tmp_path, make_engine):                                  # PAU-02
    motor, _backend = make_engine()
    janela = _janela(tmp_path, motor, State.RUNNING)
    for _ in range(2):
        assert janela.controle.pausar() is True and motor.state.state == State.PAUSED
        assert janela.controle.retomar() is True and motor.state.state == State.RUNNING
    assert janela.status == [PAUSADA, RETOMADA, PAUSADA, RETOMADA]


def test_a_mensagem_de_pausa_some_sozinha_e_nao_fica_na_barra_depois_de_parar(tmp_path, make_engine):                   # PAU-01
    """A barra de status só tem mensagem permanente se o prazo for 0: uma "Automação pausada" que ficasse lá depois de o
    usuário parar a automação seria falsa."""
    motor, _backend = make_engine()
    janela = _janela(tmp_path, motor, State.RUNNING)
    prazos = []
    janela.status_bar.showMessage = lambda texto, ms=0: prazos.append(ms)
    janela.controle.pausar()
    janela.controle.retomar()
    assert len(prazos) == 2 and all(ms > 0 for ms in prazos), prazos


# ------------------------------------------------------------------------------------------------ PAU-03
@pytest.mark.parametrize("estado", [State.IDLE, State.RECORDING, State.PAUSED, State.STOPPING])
def test_f9_so_pausa_quando_a_automacao_esta_executando(tmp_path, make_engine, estado):                                   # PAU-03
    motor, _backend = make_engine()
    janela = _janela(tmp_path, motor, estado)
    assert janela.controle.pausar() is False
    assert motor.state.state == estado and motor._pause_event.is_set(), "uma pausa recusada não mexe no motor"
    assert janela.status == [], "nada a pausar: sem mensagem"


@pytest.mark.parametrize("estado", [State.IDLE, State.RECORDING, State.RUNNING, State.STOPPING])
def test_f10_so_continua_quando_a_automacao_esta_pausada(tmp_path, make_engine, estado):                                   # PAU-03
    motor, _backend = make_engine()
    janela = _janela(tmp_path, motor, estado)
    assert janela.controle.retomar() is False
    assert motor.state.state == estado
    assert janela.status == [], "nada a continuar: sem mensagem"


# ------------------------------------------------------------------------------------------------ PAU-04
def test_f9_no_instante_em_que_a_execucao_termina_nao_levanta_erro_nem_mostra_mensagem(tmp_path, make_engine, monkeypatch):   # PAU-04
    motor, _backend = make_engine()
    janela = _janela(tmp_path, motor, State.RUNNING)
    _perde_a_corrida(motor, monkeypatch)
    assert janela.controle.pausar() is False
    assert janela.status == []
    assert motor._pause_event.is_set(), "uma pausa que não aconteceu não pode deixar a thread do motor parada"


def test_f10_no_instante_em_que_a_execucao_e_parada_nao_levanta_erro_nem_mostra_mensagem(tmp_path, make_engine, monkeypatch):   # PAU-04
    motor, _backend = make_engine()
    janela = _janela(tmp_path, motor, State.PAUSED)
    motor._pause_event.clear()  # como `pause()` deixa
    _perde_a_corrida(motor, monkeypatch)
    assert janela.controle.retomar() is False
    assert janela.status == []
    assert not motor._pause_event.is_set(), "uma retomada que não aconteceu não pode soltar a pausa (quem para é `stop`)"
