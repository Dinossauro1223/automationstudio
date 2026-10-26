"""Motor de execução: barreiras (condições de atraso, imagem e processo) e a ordem entre barreira e input.

A espera de imagem e o lançamento/prontidão de aplicativos dependem do sistema; aqui entram dublês no lugar
(`wait_for_image` e os métodos privados do motor), para testar a LÓGICA de sincronização sem Windows nem tela.
"""
import threading
import time
import types

import pytest

from automationstudio import input_system
from automationstudio.conditions import WaitCondition, WaitConditionType
from automationstudio.core import Command, InputType, State
from automationstudio.input_system import ProcessReadinessError
from testsupport.fakes import pretend_not_windows, pretend_windows
from testsupport.helpers import events_of, join_engine, key, make_map, pressed_balance, run_to_end


def _espera(segundos: float) -> Command:
    return Command(type=InputType.WAIT, start=0.0, conditions=[WaitCondition(type=WaitConditionType.DELAY, timeout=segundos)])


def _imagem(caminho="alvo.png", **params) -> WaitCondition:
    return WaitCondition(type=WaitConditionType.IMAGE, timeout=3.0, parameters={"image_path": caminho, **params})


def _resultado(achou: bool, similaridade: float = 1.0):
    return types.SimpleNamespace(found=achou, similarity=similaridade, elapsed=0.1)


# ------------------------------------------------------------------------------------------ atraso
def test_condicao_de_atraso_em_comando_wait_desloca_a_timeline(make_engine):
    motor, backend = make_engine()
    terminou, erros = run_to_end(motor, make_map([_espera(0.5), key("A", 0.1, 0.2)]))
    assert terminou and not erros
    # a barreira de 0,5 s vem antes; o comando mantém a duração planejada (0,2 s) e a lacuna (0,1 s)
    assert events_of(backend) == [(0.6, "key_down", "A"), (0.8, "key_up", "A")]


def test_condicao_de_atraso_anexada_a_tecla_desloca_tambem_os_seguintes(make_engine):
    atrasada = key("A", 0.0, 0.2, conditions=[WaitCondition(type=WaitConditionType.DELAY, timeout=0.5)])
    motor, backend = make_engine()
    terminou, erros = run_to_end(motor, make_map([atrasada, key("B", 0.3, 0.2)]))
    assert terminou and not erros
    assert events_of(backend) == [
        (0.5, "key_down", "A"), (0.7, "key_up", "A"), (0.8, "key_down", "B"), (1.0, "key_up", "B")]


def test_comando_wait_nao_envia_nenhum_input(make_engine):
    motor, backend = make_engine()
    terminou, erros = run_to_end(motor, make_map([_espera(0.25)]))
    assert terminou and not erros
    assert backend.events == []


def test_parada_durante_a_espera_por_atraso_nao_espera_o_atraso_acabar(make_engine, fake_clock, monkeypatch):
    # O atraso dorme em pedaços de 20 ms e consulta a parada a cada um. O relógio é virtual, então o número de
    # pedaços mede a pressa do motor: parando no 3º pedaço, um sono que ouve a parada dorme 3 vezes; um que a
    # ignorasse dormiria os 250 pedaços dos 5 s inteiros e só então perceberia (o `_checkpoint` seguinte ainda
    # impediria o input, por isso o que se mede aqui é o tempo, não o input).
    motor, backend = make_engine()
    dormir, pedacos = fake_clock.sleep, []

    def dormir_e_parar(segundos):
        dormir(segundos)
        pedacos.append(segundos)
        if len(pedacos) == 3:
            motor.stop()  # o usuário para no meio da espera (aqui, na thread do motor, em ponto exato)

    monkeypatch.setattr(fake_clock, "sleep", dormir_e_parar)
    motor.run(make_map([_espera(5.0), key("A", 0.1, 0.1)]))
    join_engine(motor)
    assert len(pedacos) == 3, f"o motor continuou dormindo depois do pedido de parada ({len(pedacos)} pedaços)"
    assert backend.events == [] and motor.state.state == State.IDLE


# ------------------------------------------------------------------------------------------ imagem
def test_imagem_encontrada_libera_o_comando_e_repassa_os_parametros(make_engine, monkeypatch):
    chamadas = []

    def falsa(caminho, **kwargs):
        chamadas.append((caminho, kwargs))
        return _resultado(True)

    monkeypatch.setattr(input_system, "wait_for_image", falsa)
    espera = Command(type=InputType.WAIT, start=0.0,
                     conditions=[_imagem("botao.png", confidence=0.9, interval=0.25)])
    motor, backend = make_engine()
    terminou, erros = run_to_end(motor, make_map([espera, key("A", 0.1, 0.1)]))
    assert terminou and not erros
    assert [a for _t, a, _x in events_of(backend)] == ["key_down", "key_up"]
    (caminho, kwargs), = chamadas
    assert caminho == "botao.png"
    assert kwargs["confidence"] == 0.9 and kwargs["interval"] == 0.25 and kwargs["timeout"] == 3.0
    assert kwargs["stop_event"] is motor._stop_requested, "a espera precisa enxergar o pedido de parada do motor"


def test_imagem_nao_encontrada_gera_erro_e_nenhum_input(make_engine, monkeypatch):
    monkeypatch.setattr(input_system, "wait_for_image", lambda *a, **k: _resultado(False, 0.42))
    espera = Command(type=InputType.WAIT, start=0.0, conditions=[_imagem()])
    motor, backend = make_engine()
    terminou, erros = run_to_end(motor, make_map([espera, key("A", 0.1, 0.1)]))
    assert terminou
    assert len(erros) == 1 and isinstance(erros[0], ProcessReadinessError)
    assert "42.0%" in str(erros[0])
    assert backend.events == [] and motor.state.state == State.IDLE


def test_parada_durante_a_espera_de_imagem_nao_e_erro(make_engine, monkeypatch):
    erros = []
    motor, backend = make_engine()
    motor.on_error.append(erros.append)

    def espera_interrompida(caminho, **kwargs):
        motor.stop()  # o usuário para a automação enquanto a imagem é procurada
        return _resultado(False, 0.0)

    monkeypatch.setattr(input_system, "wait_for_image", espera_interrompida)
    motor.run(make_map([Command(type=InputType.WAIT, start=0.0, conditions=[_imagem()]), key("A", 0.1, 0.1)]))
    join_engine(motor)
    assert erros == [] and backend.events == []
    assert motor.state.state == State.IDLE


def test_pausa_durante_a_espera_de_imagem_nao_envia_input(make_engine, fake_clock, monkeypatch):
    # Item 1.07 do Ponto 1, com relógio virtual: enquanto pausado, NENHUM input pode sair.
    motor, backend = make_engine()
    vistos_na_retomada = []

    def espera_com_pausa(caminho, **kwargs):
        motor.pause()

        def retomar():
            time.sleep(0.05)
            vistos_na_retomada.append(len(backend.events))
            fake_clock.advance(5.0)  # 5 s parado
            motor.resume()

        threading.Thread(target=retomar, daemon=True).start()
        return _resultado(True)

    monkeypatch.setattr(input_system, "wait_for_image", espera_com_pausa)
    mapa = make_map([Command(type=InputType.WAIT, start=0.0, conditions=[_imagem()]), key("A", 0.1, 0.2)])
    terminou, erros = run_to_end(motor, mapa)
    assert terminou and not erros
    assert vistos_na_retomada == [0], "saiu input enquanto o motor estava pausado"
    # o tempo parado é tempo de barreira: depois da retomada o comando mantém o início e a duração planejados
    assert events_of(backend) == [(5.1, "key_down", "A"), (5.3, "key_up", "A")]


# ------------------------------------------------------------------------------------------ processo
def test_condicao_de_processo_sem_aplicativo_de_referencia_gera_erro_claro(make_engine):
    referencia = Command(id="ref1", type=InputType.TEXT, text="oi", start=0.0, duration=0.1)  # sem processo definido
    condicao = WaitCondition(type=WaitConditionType.PROCESS, parameters={"command_id": "ref1"})
    espera = Command(type=InputType.WAIT, start=0.2, conditions=[condicao])
    motor, backend = make_engine()
    terminou, erros = run_to_end(motor, make_map([referencia, espera, key("A", 0.5, 0.1)]))
    assert terminou and len(erros) == 1 and isinstance(erros[0], ProcessReadinessError)
    assert "Comando de referência" in str(erros[0])
    assert motor.state.state == State.IDLE
    assert pressed_balance(backend) == {}


def test_parada_durante_a_espera_por_aplicativo_nao_e_erro(make_engine):
    # O watcher real sai da espera levantando ProcessReadinessError quando vê o pedido de parada (é o jeito de
    # escapar imediatamente); o motor não pode mostrar isso no painel de erro, porque quem pediu foi o usuário.
    # `stop(wait=True)` fixa a ordem real da parada de emergência: o motor trata a exceção com o estado ainda em
    # STOPPING, quando `transition_to(ERROR)` seria aceito e o erro apareceria.
    motor, backend = make_engine()
    erros, dentro = [], threading.Event()
    motor.on_error.append(erros.append)

    def espera_do_watcher(evento, expected_pid=None):
        dentro.set()
        assert motor._stop_requested.wait(10), "o teste nunca pediu a parada"
        raise ProcessReadinessError("Espera pelo aplicativo interrompida pelo usuário.")

    motor._wait_for_process = espera_do_watcher
    texto = Command(type=InputType.TEXT, text="oi", start=0.0, duration=0.1, wait_process="bloco.exe")
    motor.run(make_map([texto]))
    assert dentro.wait(10)
    motor.stop(wait=True)
    join_engine(motor)
    assert erros == [], f"a parada do usuário apareceu como erro: {erros}"
    assert backend.events == [] and motor.state.state == State.IDLE


def test_falha_da_espera_por_aplicativo_sem_parada_e_reportada_como_erro(make_engine):
    # O par do teste anterior: a MESMA exceção, sem pedido de parada, é uma falha de verdade e chega ao painel.
    motor, backend = make_engine()

    def espera_que_falha(evento, expected_pid=None):
        raise ProcessReadinessError("O aplicativo não ficou pronto a tempo.")

    motor._wait_for_process = espera_que_falha
    texto = Command(type=InputType.TEXT, text="oi", start=0.0, duration=0.1, wait_process="bloco.exe")
    terminou, erros = run_to_end(motor, make_map([texto, key("A", 0.5, 0.1)]))
    assert terminou and [str(e) for e in erros] == ["O aplicativo não ficou pronto a tempo."]
    assert backend.events == [] and motor.state.state == State.IDLE


def test_abrir_aplicativo_e_barreira_de_processo_vem_antes_do_texto(make_engine):
    motor, backend = make_engine()
    ordem = []
    motor._launch_application = lambda alvo: (ordem.append(("abrir", alvo)), 777)[1]
    motor._wait_for_process = lambda evento, expected_pid=None: ordem.append(("esperar", evento.kind.value, expected_pid))
    abrir = Command(type=InputType.APP_OPEN, target="bloco.exe", start=0.0, duration=0.1)
    texto = Command(type=InputType.TEXT, text="ab", start=0.5, duration=0.1, wait_process="bloco.exe")
    terminou, erros = run_to_end(motor, make_map([abrir, texto]))
    assert terminou and not erros
    # a barreira de prontidão acontece ANTES do texto dependente do aplicativo (item de V24 / 1.08)
    assert ordem == [("abrir", "bloco.exe"), ("esperar", "app_open", 777), ("esperar", "text", None)]
    assert [a for _t, a, _x in events_of(backend)] == ["type_text", "type_text"]


def test_abrir_aplicativo_fora_do_windows_vira_erro_de_execucao_sem_abrir_nada(make_engine, monkeypatch):
    pretend_not_windows(monkeypatch)  # mesmo no Windows: nunca abre um aplicativo de verdade neste teste
    abrir = Command(type=InputType.APP_OPEN, target="bloco.exe", start=0.0, duration=0.1)
    motor, backend = make_engine()
    terminou, erros = run_to_end(motor, make_map([abrir, key("A", 0.5, 0.1)]))
    assert terminou and len(erros) == 1 and isinstance(erros[0], RuntimeError)
    assert "Windows" in str(erros[0])
    assert backend.events == []


def test_a_rede_de_seguranca_dos_testes_impede_abrir_um_aplicativo_de_verdade(make_engine, monkeypatch):
    # No Windows o motor lança o alvo com subprocess.Popen. O conftest troca o Popen visto pelo motor por um bloqueio:
    # um teste que esquecesse de trocar `_launch_application` abriria o Bloco de Notas na máquina de quem roda a suíte.
    pretend_windows(monkeypatch)
    abrir = Command(type=InputType.APP_OPEN, target="bloco.exe", start=0.0, duration=0.1)
    motor, backend = make_engine()
    terminou, erros = run_to_end(motor, make_map([abrir]))
    assert terminou and len(erros) == 1 and isinstance(erros[0], RuntimeError)
    assert "um teste tentou abrir um aplicativo de verdade" in str(erros[0]), erros[0]
    assert backend.events == []


def test_espera_de_processo_fora_do_windows_e_erro_de_prontidao(make_engine, monkeypatch):
    pretend_not_windows(monkeypatch)
    texto = Command(type=InputType.TEXT, text="oi", start=0.0, duration=0.1, wait_process="bloco.exe")
    motor, backend = make_engine()
    terminou, erros = run_to_end(motor, make_map([texto]))
    assert terminou and len(erros) == 1 and isinstance(erros[0], ProcessReadinessError)
    assert backend.events == []
