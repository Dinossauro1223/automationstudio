"""GlobalInputMonitor: tradução dos eventos do pynput e ciclo de vida dos listeners (sem pynput e sem hooks globais)."""
import types

import pytest

from automationstudio import input_system
from automationstudio.core import AutomationMap, InputType, StateManager, key_to_name
from automationstudio.input_system import GlobalHotkeyManager, GlobalInputMonitor, Recorder
from testsupport.fakes import FakeListeners
from testsupport.helpers import events_of, run_to_end


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


# --------------------------------------------------------------------------- 25.9 (T1): nomes de tecla confiáveis
# A2: F13 a F24 eram descartadas (a tabela de nomes só ia até F12). A3: com Ctrl, Shift ou Alt apertados, o `char` que o pynput
# entrega pode vir alterado pelos modificadores (um caractere de controle com Ctrl, "!" no lugar de "1" com Shift); o código virtual
# (`vk`) é o da tecla física e não muda. O nome vem do `char` quando ele serve, como sempre, e do `vk` quando não serve.
@pytest.mark.parametrize("n", range(13, 25))
def test_f13_a_f24_pelo_nome_que_o_pynput_da(n):
    assert key_to_name(_tecla(name=f"f{n}")) == f"F{n}"


@pytest.mark.parametrize("n", range(1, 25))
def test_f1_a_f24_pelo_codigo_virtual_quando_a_tecla_chega_so_com_o_vk(n):
    # No Windows o pynput tem Key.f1 a Key.f20; F21 a F24 chegam como KeyCode só com o vk (VK_F1 = 0x70 ... VK_F24 = 0x87).
    assert key_to_name(_tecla(name=None, char=None, vk=0x6F + n)) == f"F{n}"


@pytest.mark.parametrize("char,vk,nome", [
    ("\x01", 0x41, "A"), ("\x1a", 0x5A, "Z"), ("\x13", 0x53, "S"),          # Ctrl+letra: caractere de controle
    ("!", 0x31, "1"), ("@", 0x32, "2"), ("(", 0x39, "9"), (")", 0x30, "0"),   # Shift+dígito: o símbolo
    (None, 0x35, "5"), ("", 0x45, "E"), ("\x00", 0x31, "1")],
    ids=["ctrl+A", "ctrl+Z", "ctrl+S", "shift+1", "shift+2", "shift+9", "shift+0", "sem-char-5", "char-vazio-E", "char-nulo-1"])
def test_letra_e_numero_pelo_codigo_virtual_quando_o_char_nao_serve(char, vk, nome):
    assert key_to_name(_tecla(name=None, char=char, vk=vk)) == nome


@pytest.mark.parametrize("char,vk,nome", [("a", 0x41, "A"), ("A", 0x41, "A"), ("7", 0x37, "7"), ("ç", 0xBA, "Ç"), ("Ç", 0xBA, "Ç"),
                                          ("b", 0x41, "B")])
def test_o_char_continua_valendo_quando_serve_mesmo_que_o_vk_discorde(char, vk, nome):
    # O último caso é de propósito: com o char utilizável, o vk nem é olhado (nada muda para quem digita normalmente).
    assert key_to_name(_tecla(name=None, char=char, vk=vk)) == nome


@pytest.mark.parametrize("tecla", [
    _tecla(name=None, char="@", vk=0xBA), _tecla(name=None, char=";", vk=0xBA), _tecla(name=None, char=None, vk=0xBA),
    _tecla(name=None, char=None, vk=0x60), _tecla(name=None, char=None, vk=0x69),   # teclado numérico: não é letra nem número do alto
    _tecla(name=None, char=None, vk=0x7F + 0x10), _tecla(name=None, char=None, vk=0x6F), _tecla(name=None, char=None, vk=0x2F),
    _tecla(name=None, char=None, vk=0x3A), _tecla(name=None, char=None, vk=0x40), _tecla(name=None, char=None, vk=0x5B),
    _tecla(name=None, char=None, vk=None), _tecla(name=None, char=None, vk="A"), _tecla(name=None, char=None, vk=True),
    _tecla(name=None, char=None, vk=-1), _tecla(name=None, char=None, vk=65.0), _tecla(name=None, char="ab", vk=None)])
def test_vk_fora_das_teclas_que_o_studio_modela_e_ignorado(tecla):
    assert key_to_name(tecla) == ""


def test_o_vk_so_vale_quando_a_tecla_nao_tem_nome_do_pynput():
    # Uma tecla que o pynput batizou e o Studio não modela continua ignorada, mesmo com vk de letra ou de F.
    assert key_to_name(_tecla(name="media_volume_up", vk=0x41)) == ""
    assert key_to_name(_tecla(name="media_volume_up", char=None, vk=0x7C)) == ""
    assert key_to_name(_tecla(name="f13", vk=0x41)) == "F13"


def test_emit_key_entrega_f13_e_letra_com_char_alterado_aos_observadores():
    monitor, vistos = GlobalInputMonitor(), []
    monitor.on_key.append(lambda nome, apertada: vistos.append((nome, apertada)))
    monitor._emit_key(_tecla(name="f13"), True)
    monitor._emit_key(_tecla(name=None, char="\x14", vk=0x54), True)   # Ctrl+T
    monitor._emit_key(_tecla(name=None, char=None, vk=0x87), True)       # F24: só o vk
    monitor._emit_key(_tecla(name=None, char="@", vk=0xBA), True)        # símbolo: continua ignorado
    assert vistos == [("F13", True), ("T", True), ("F24", True)]


def test_ctrl_shift_alt_1_dispara_mesmo_quando_o_char_chega_alterado_pelos_modificadores():
    # TEC-12 / A3: o atalho composto que o dono pediu como padrão. No teclado dos EUA e no ABNT2, Shift+1 produz "!".
    for char in ("1", "!", "\x31", None):
        monitor = GlobalInputMonitor()
        gerente = GlobalHotkeyManager(monitor)
        disparos = []
        gerente.register("CTRL+SHIFT+ALT+1", lambda: disparos.append("um"))
        gerente.start()  # o monitor é injetado: o gerente não liga hook nenhum
        for modificador in ("ctrl_l", "shift", "alt_l"):
            monitor._emit_key(_tecla(name=modificador), True)
        monitor._emit_key(_tecla(name=None, char=char, vk=0x31), True)
        assert disparos == ["um"], f"char={char!r}"


def test_f13_dispara_um_atalho_de_automacao_e_nao_mexe_nos_outros():
    monitor = GlobalInputMonitor()
    gerente = GlobalHotkeyManager(monitor)
    disparos = []
    gerente.register("F13", lambda: disparos.append("f13"))
    gerente.register("CTRL+F24", lambda: disparos.append("ctrl+f24"))
    gerente.start()
    monitor._emit_key(_tecla(name="f13"), True)
    monitor._emit_key(_tecla(name="f13"), False)
    monitor._emit_key(_tecla(name="ctrl_r"), True)
    monitor._emit_key(_tecla(name=None, char=None, vk=0x87), True)
    assert disparos == ["f13", "ctrl+f24"]


def test_o_gravador_grava_f13_e_o_motor_reproduz_a_mesma_tecla(fake_clock, make_engine):
    # F13 a F24 passam a ser gravadas (antes eram descartadas): o que foi gravado tem de poder ser reproduzido. Que o Windows aceite
    # o código virtual de cada uma (0x7C a 0x87) é conferido em tests/contract/test_backend_win32.py.
    monitor = GlobalInputMonitor()
    monitor._keyboard_listener = object()  # finge listener ativo: nenhum hook global é iniciado
    gravador = Recorder(monitor, StateManager(), clock=fake_clock)
    gravador.start()
    monitor._emit_key(_tecla(name="f13"), True)
    fake_clock.advance(0.2)
    monitor._emit_key(_tecla(name="f13"), False)
    comandos = gravador.stop()
    assert [(c.type, c.target) for c in comandos] == [(InputType.KEY, "F13")], comandos
    motor, backend = make_engine()
    terminou, erros = run_to_end(motor, AutomationMap(name="F13", commands=comandos, repeat_count=1))
    assert terminou and not erros
    assert [(a, alvo) for _t, a, alvo in events_of(backend)] == [("key_down", "F13"), ("key_up", "F13")]


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
