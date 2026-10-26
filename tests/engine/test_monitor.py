"""GlobalInputMonitor: tradução dos eventos do pynput e ciclo de vida dos listeners (sem pynput e sem hooks globais)."""
import types

import pytest

from automationstudio import input_system
from automationstudio.core import key_to_name
from automationstudio.input_system import GlobalInputMonitor
from testsupport.fakes import FakeListeners


def _tecla(**atributos):
    return types.SimpleNamespace(**atributos)


@pytest.mark.parametrize("tecla,nome", [
    (_tecla(name="enter"), "ENTER"), (_tecla(name="shift_r"), "SHIFT"), (_tecla(name="ctrl_l"), "CTRL"),
    (_tecla(name="alt_gr"), "ALTGR"), (_tecla(name="cmd"), "WIN"), (_tecla(name="page_down"), "PAGEDOWN"),
    (_tecla(name="f12"), "F12"), (_tecla(name=None, char="a"), "A"), (_tecla(name=None, char="ç"), "Ç"),
    (_tecla(name=None, char="7"), "7")])
def test_key_to_name_traduz_teclas_conhecidas(tecla, nome):
    assert key_to_name(tecla) == nome


@pytest.mark.parametrize("tecla", [
    _tecla(name="media_volume_up"), _tecla(name=None, char="@"), _tecla(name=None, char=None), _tecla(name=None, char=""),
    _tecla(name=None, char="ab")])
def test_key_to_name_ignora_o_que_o_studio_nao_modela(tecla):
    assert key_to_name(tecla) == ""


def test_emit_key_entrega_nomes_normalizados_e_ignora_teclas_desconhecidas():
    monitor, vistos = GlobalInputMonitor(), []
    monitor.on_key.append(lambda nome, apertada: vistos.append((nome, apertada)))
    monitor._emit_key(_tecla(name="shift_l"), True)
    monitor._emit_key(_tecla(name=None, char="e"), True)
    monitor._emit_key(_tecla(name="media_volume_up"), True)  # desconhecida: não chega aos observadores
    monitor._emit_key(_tecla(name="shift_l"), False)
    assert vistos == [("SHIFT", True), ("E", True), ("SHIFT", False)]


def test_emit_click_usa_o_nome_cru_do_botao_em_minusculas():
    # D1 (25.5): sem troca de x1/x2 no monitor; quem exibe é que decide como desenhar.
    monitor, vistos = GlobalInputMonitor(), []
    monitor.on_mouse_button.append(lambda nome, apertado: vistos.append((nome, apertado)))
    for nome in ("x1", "X2", "Left"):
        monitor._emit_click(0, 0, _tecla(name=nome), True)
    assert vistos == [("x1", True), ("x2", True), ("left", True)]


def test_emit_scroll_e_move_repassam_os_valores():
    monitor, rolagens, movimentos = GlobalInputMonitor(), [], []
    monitor.on_mouse_scroll.append(lambda dx, dy: rolagens.append((dx, dy)))
    monitor.on_mouse_move.append(lambda x, y: movimentos.append((x, y)))
    monitor._emit_scroll(1, -2)
    monitor._emit_move(30, 40)
    assert rolagens == [(1, -2)] and movimentos == [(30, 40)]


def test_observador_defeituoso_nunca_derruba_os_outros(monkeypatch):
    monkeypatch.setattr(input_system.traceback, "print_exc", lambda *a, **k: None)  # sem ruído no log do teste
    monitor, vistos = GlobalInputMonitor(), []

    def quebra(*_args):
        raise RuntimeError("observador defeituoso")

    for lista in (monitor.on_key, monitor.on_mouse_button, monitor.on_mouse_scroll, monitor.on_mouse_move):
        lista.append(quebra)
        lista.append(lambda *args: vistos.append(args))
    monitor._emit_key(_tecla(name="enter"), True)
    monitor._emit_click(0, 0, _tecla(name="left"), True)
    monitor._emit_scroll(0, 1)
    monitor._emit_move(1, 2)
    assert vistos == [("ENTER", True), ("left", True), (0, 1), (1, 2)]


# ----------------------------------------------------------------------------------------- ciclo de vida
def test_sem_pynput_o_monitor_nao_inicia_e_explica_como_instalar(monkeypatch):
    monkeypatch.setattr(input_system, "_PYNPUT_AVAILABLE", False)
    monitor = GlobalInputMonitor()
    assert not monitor.available
    with pytest.raises(RuntimeError, match="pip install pynput"):
        monitor.start()
    assert not monitor.is_running()


def test_start_cria_e_inicia_os_dois_listeners_uma_unica_vez(monkeypatch):
    escutas = FakeListeners().install(monkeypatch)
    monitor = GlobalInputMonitor()
    monitor.start()
    monitor.start()  # já rodando: não cria listeners novos
    assert monitor.is_running()
    assert len(escutas.keyboard) == len(escutas.mouse) == 1
    assert escutas.keyboard[0].started and escutas.mouse[0].started


def test_callbacks_do_pynput_chegam_aos_observadores(monkeypatch):
    escutas = FakeListeners().install(monkeypatch)
    monitor, vistos = GlobalInputMonitor(), []
    monitor.on_key.append(lambda *a: vistos.append(("tecla",) + a))
    monitor.on_mouse_button.append(lambda *a: vistos.append(("botao",) + a))
    monitor.on_mouse_scroll.append(lambda *a: vistos.append(("rolagem",) + a))
    monitor.on_mouse_move.append(lambda *a: vistos.append(("mover",) + a))
    monitor.start()
    teclado, mouse = escutas.keyboard[0].callbacks, escutas.mouse[0].callbacks
    teclado["on_press"](_tecla(name="enter")); teclado["on_release"](_tecla(name="enter"))
    mouse["on_click"](5, 6, _tecla(name="x1"), True)
    mouse["on_scroll"](5, 6, 1, -1)  # o pynput manda (x, y, dx, dy); o monitor repassa só (dx, dy)
    mouse["on_move"](7, 8)
    assert vistos == [("tecla", "ENTER", True), ("tecla", "ENTER", False), ("botao", "x1", True), ("rolagem", 1, -1), ("mover", 7, 8)]


def test_stop_para_os_dois_listeners_e_pode_ser_repetido(monkeypatch):
    escutas = FakeListeners().install(monkeypatch)
    monitor = GlobalInputMonitor()
    monitor.start()
    monitor.stop()
    monitor.stop()
    assert not monitor.is_running()
    assert escutas.keyboard[0].stopped and escutas.mouse[0].stopped
    monitor.start()  # pode religar
    assert len(escutas.keyboard) == 2 and monitor.is_running()
