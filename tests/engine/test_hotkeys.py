"""Atalhos globais (GlobalHotkeyManager): registro, conflitos, combinações e disparo único por pressão.

O monitor é falso (FakeMonitor): os testes "apertam" teclas e botões chamando os mesmos callbacks que o pynput chamaria.
"""
import pytest

from automationstudio.core import _normalize_hotkey_token, parse_combo
from automationstudio.input_system import GlobalHotkeyManager, GlobalInputMonitor, HotkeyConflictError
from testsupport.fakes import FakeListeners, FakeMonitor


def _novo(*atalhos):
    """(gerenciador iniciado, monitor, disparos) com os atalhos dados, cada um registrado com seu próprio callback."""
    monitor, disparos = FakeMonitor(), []
    gerente = GlobalHotkeyManager(monitor)
    for texto in atalhos:
        gerente.register(texto, lambda t=texto: disparos.append(t))
    gerente.start()
    return gerente, monitor, disparos


def test_atalho_simples_dispara_uma_vez_por_pressao():
    _g, mon, disparos = _novo("F8")
    mon.press("F8"); mon.press("F8"); mon.press("F8")  # repetição automática do sistema
    assert disparos == ["F8"]
    mon.release("F8"); mon.press("F8")
    assert disparos == ["F8", "F8"]


def test_combinacao_exige_todas_as_teclas_em_qualquer_ordem():
    _g, mon, disparos = _novo("CTRL+F8")
    mon.press("CTRL")
    assert disparos == []
    mon.press("F8")
    assert disparos == ["CTRL+F8"]
    mon.release("F8"); mon.release("CTRL")
    mon.press("F8")  # a outra ordem
    assert disparos == ["CTRL+F8"]
    mon.press("CTRL")
    assert disparos == ["CTRL+F8", "CTRL+F8"]


def test_soltar_uma_tecla_da_combinacao_rearma_sem_soltar_todas():
    _g, mon, disparos = _novo("CTRL+F8")
    mon.press("CTRL"); mon.press("F8")
    mon.release("F8"); mon.press("F8")
    assert disparos == ["CTRL+F8", "CTRL+F8"]


def test_teclas_extras_pressionadas_nao_impedem_o_disparo():
    _g, mon, disparos = _novo("F8")
    mon.press("SHIFT"); mon.press("F8")
    assert disparos == ["F8"]


def test_combinacao_incompleta_nao_dispara():
    _g, mon, disparos = _novo("CTRL+SHIFT+F8")
    mon.press("CTRL"); mon.press("F8")
    assert disparos == []


def test_sem_start_nada_dispara_e_stop_remove_os_callbacks():
    monitor, disparos = FakeMonitor(), []
    gerente = GlobalHotkeyManager(monitor)
    gerente.register("F8", lambda: disparos.append(1))
    monitor.press("F8")
    assert disparos == [] and not monitor.on_key
    gerente.start()
    assert len(monitor.on_key) == 1 and len(monitor.on_mouse_button) == 1
    gerente.start()  # idempotente
    assert len(monitor.on_key) == 1
    gerente.stop()
    assert not monitor.on_key and not monitor.on_mouse_button
    monitor.release("F8"); monitor.press("F8")
    assert disparos == []


def test_stop_limpa_as_teclas_pressionadas():
    gerente, mon, disparos = _novo("CTRL+F8")
    mon.press("CTRL")
    gerente.stop(); gerente.start()
    mon.press("F8")  # CTRL "esquecido": a combinação não pode completar
    assert disparos == []


# ----------------------------------------------------------------------------------------- registro
def test_conflito_entre_acoes_diferentes_levanta_erro():
    gerente = GlobalHotkeyManager(FakeMonitor())
    gerente.register("CTRL+F8", lambda: None)
    with pytest.raises(HotkeyConflictError, match="já em uso"):
        gerente.register("CTRL+F8", lambda: None)


def test_conflito_ignora_ordem_e_caixa():
    gerente = GlobalHotkeyManager(FakeMonitor())
    gerente.register("ctrl+f8", lambda: None)
    with pytest.raises(HotkeyConflictError):
        gerente.register("F8 + CTRL", lambda: None)


def test_registrar_de_novo_o_mesmo_callback_e_idempotente():
    gerente, callback = GlobalHotkeyManager(FakeMonitor()), (lambda: None)
    gerente.register("F8", callback)
    gerente.register("F8", callback)  # recarregar os atalhos não pode conflitar consigo mesmo


def test_remover_e_limpar_liberam_o_atalho():
    gerente = GlobalHotkeyManager(FakeMonitor())
    gerente.register("F8", lambda: None)
    gerente.unregister("f8")
    gerente.register("F8", lambda: None)  # livre de novo
    gerente.clear()
    gerente.register("F8", lambda: None)
    gerente.unregister("F9")  # remover o que não existe é inofensivo


# ----------------------------------------------------------------------------------------- mouse
@pytest.mark.parametrize("token,botao", [
    ("MOUSE_LEFT", "left"), ("MOUSE_RIGHT", "right"), ("MOUSE_MIDDLE", "middle"), ("MOUSE_X1", "x1"), ("MOUSE_X2", "x2")])
def test_botoes_do_mouse_disparam_atalhos_pelo_nome_cru(token, botao):
    _g, mon, disparos = _novo(token)
    mon.click(botao, True)
    mon.click(botao, True)  # sem soltar: não repete
    assert disparos == [token]
    mon.click(botao, False); mon.click(botao, True)
    assert disparos == [token, token]


@pytest.mark.parametrize("apelido,canonico", [("X1", "MOUSE_X1"), ("lateral1", "MOUSE_X1"), ("LATERAL2", "MOUSE_X2"),
                                                ("botao esquerdo", "MOUSE_LEFT"), ("mouse_middle", "MOUSE_MIDDLE")])
def test_apelidos_de_botao_viram_o_token_canonico(apelido, canonico):
    assert _normalize_hotkey_token(apelido) == canonico
    assert parse_combo(apelido) == frozenset({canonico})


def test_combinacao_de_teclado_com_botao_do_mouse():
    _g, mon, disparos = _novo("CTRL+MOUSE_X2")
    mon.click("x2", True)
    assert disparos == []
    mon.press("CTRL")
    assert disparos == ["CTRL+MOUSE_X2"]


# ----------------------------------------------------------------------------------------- análise do texto
def test_atalho_vazio_e_invalido():
    for texto in ("", "   ", "+", " + "):
        with pytest.raises(ValueError, match="vazio"):
            parse_combo(texto)


def test_analise_de_combinacao_ignora_espacos_e_caixa():
    assert parse_combo(" ctrl + Shift+f8 ") == frozenset({"CTRL", "SHIFT", "F8"})


# ----------------------------------------------------------------------------------------- dono do monitor
def test_monitor_emprestado_nao_e_ligado_nem_desligado_pelo_gerenciador():
    monitor = FakeMonitor()
    gerente = GlobalHotkeyManager(monitor)
    gerente.start()
    assert not monitor.running
    gerente.stop()


def test_monitor_proprio_e_ligado_e_desligado_pelo_gerenciador(monkeypatch):
    escutas = FakeListeners().install(monkeypatch)
    gerente = GlobalHotkeyManager()  # cria o próprio monitor
    assert isinstance(gerente.monitor, GlobalInputMonitor) and gerente.available
    gerente.start()
    assert gerente.is_running() and escutas.keyboard[0].started and escutas.mouse[0].started
    gerente.stop()
    assert not gerente.is_running() and escutas.keyboard[0].stopped and escutas.mouse[0].stopped
