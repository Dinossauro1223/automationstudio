"""Suspensão dos atalhos de automação durante a captura de tecla (25.9, T3a; ficha md/FICHA_TECLADO_T3_25_9.md, T3-7).

Quando a pessoa grava a tecla de um comando, ela aperta a tecla de verdade: se essa tecla for o atalho de uma automação, a automação
não pode partir. O gerenciador de atalhos globais ganhou `suspender()` e `retomar(graca)`: enquanto suspenso, os atalhos registrados
como `suspensivel=True` (os das automações; `registrar_plano` marca só os de mapa) não disparam. Os de controle (pausar, continuar,
parada de emergência) e todos os que não foram marcados **seguem valendo**.

O monitor é falso (FakeMonitor) e o relógio também (FakeClock): a "graça" da retomada se prova sem esperar.
"""
import pytest

from automationstudio.input_system import GlobalHotkeyManager, HotkeyConflictError
from testsupport.fake_clock import FakeClock
from testsupport.fakes import FakeMonitor
from testsupport.janela_falsa import abrir as _abrir


def _novo(suspensiveis=(), fixos=(), relogio=None):
    """(gerenciador iniciado, monitor, disparos): os `suspensiveis` registrados com a marca; os `fixos`, sem."""
    monitor, disparos = FakeMonitor(), []
    gerente = GlobalHotkeyManager(monitor) if relogio is None else GlobalHotkeyManager(monitor, relogio=relogio)
    for texto in suspensiveis:
        gerente.register(texto, lambda t=texto: disparos.append(t), suspensivel=True)
    for texto in fixos:
        gerente.register(texto, lambda t=texto: disparos.append(t))
    gerente.start()
    return gerente, monitor, disparos


# ------------------------------------------------------------------------------------------------ o que a suspensão faz
def test_sem_suspender_nada_muda_o_atalho_marcado_dispara_como_sempre():
    _g, mon, disparos = _novo(suspensiveis=["F6"])
    mon.press("F6")
    assert disparos == ["F6"]


def test_suspenso_o_atalho_marcado_nao_dispara():
    g, mon, disparos = _novo(suspensiveis=["F6"])
    g.suspender()
    mon.press("F6")
    assert disparos == []


def test_suspenso_o_atalho_sem_a_marca_continua_disparando():
    """O padrão de `register` é `suspensivel=False`: o gerenciador de antes se comporta igual."""
    g, mon, disparos = _novo(suspensiveis=["F6"], fixos=["F12"])
    g.suspender()
    mon.press("F12")
    assert disparos == ["F12"]


def test_o_atalho_calado_nao_impede_os_outros_da_mesma_apertada():
    """O gerenciador dispara por subconjunto (A5 da especificação): uma mesma apertada pode completar dois atalhos. O de automação, calado, é
    pulado; o outro (aqui o registrado depois, sem a marca) tem de disparar: pular não é parar a procura."""
    g, mon, disparos = _novo(suspensiveis=["X"], fixos=["SHIFT+X"])
    g.suspender()
    mon.press("SHIFT")
    mon.press("X")
    assert disparos == ["SHIFT+X"]


def test_o_botao_calado_nao_impede_os_outros_do_mesmo_botao():
    g, mon, disparos = _novo(suspensiveis=["MOUSE_X1"], fixos=["SHIFT+MOUSE_X1"])
    g.suspender()
    mon.press("SHIFT")
    mon.click("x1", True)
    assert disparos == ["SHIFT+MOUSE_X1"]


def test_a_combinacao_com_modificadores_tambem_fica_suspensa():
    g, mon, disparos = _novo(suspensiveis=["CTRL+SHIFT+ALT+1"])
    g.suspender()
    for nome in ("CTRL", "SHIFT", "ALT", "1"):
        mon.press(nome)
    assert disparos == []


def test_o_botao_do_mouse_tambem_fica_suspenso():
    g, mon, disparos = _novo(suspensiveis=["MOUSE_X1", "CTRL+MOUSE_X2"])
    g.suspender()
    mon.click("x1", True); mon.click("x1", False)
    mon.press("CTRL"); mon.click("x2", True)
    assert disparos == []


def test_retomar_devolve_o_disparo():
    g, mon, disparos = _novo(suspensiveis=["F6"])
    g.suspender(); mon.press("F6"); mon.release("F6")
    g.retomar()
    mon.press("F6")
    assert disparos == ["F6"]


# ------------------------------------------------------------------------------------------------ a tecla ainda apertada na retomada
def test_a_combinacao_completada_suspensa_nao_dispara_ao_retomar_com_a_tecla_ainda_apertada():
    """Apertou F6 para gravá-la, confirmou (retomou) sem soltar, e aperta outra tecla: F6 ainda está apertada e já "contou"."""
    g, mon, disparos = _novo(suspensiveis=["F6"])
    g.suspender()
    mon.press("F6")
    g.retomar()
    mon.press("X")
    assert disparos == []


def test_depois_de_soltar_a_combinacao_volta_ao_normal():
    g, mon, disparos = _novo(suspensiveis=["F6"])
    g.suspender(); mon.press("F6"); g.retomar(); mon.press("X")
    mon.release("F6"); mon.release("X")
    mon.press("F6")
    assert disparos == ["F6"]


def test_soltar_so_uma_tecla_da_combinacao_ja_rearma_como_no_gerenciador_de_antes():
    g, mon, disparos = _novo(suspensiveis=["CTRL+F6"])
    g.suspender()
    mon.press("CTRL"); mon.press("F6")
    g.retomar()
    mon.release("F6"); mon.press("F6")
    assert disparos == ["CTRL+F6"]


def test_o_botao_apertado_na_suspensao_tambem_conta_como_disparado():
    g, mon, disparos = _novo(suspensiveis=["MOUSE_X1"])
    g.suspender()
    mon.click("x1", True)
    g.retomar()
    mon.press("X")
    assert disparos == []
    mon.click("x1", False); mon.click("x1", True)
    assert disparos == ["MOUSE_X1"]


# ------------------------------------------------------------------------------------------------ a graça da retomada
def test_a_graca_mantem_a_suspensao_por_um_instante_depois_de_retomar():
    """Se o Qt processar a tecla de confirmação antes do monitor, a automação não parte na tecla que confirmou."""
    relogio = FakeClock(100.0)
    g, mon, disparos = _novo(suspensiveis=["F6"], relogio=relogio.monotonic)
    g.suspender()
    g.retomar(graca=0.25)
    assert g.suspenso
    relogio.advance(0.1)
    mon.press("F6")
    assert disparos == [] and g.suspenso
    mon.release("F6")
    relogio.advance(0.14)  # 0,24 s depois da retomada: a graça é de 0,25 s, então ainda vale
    assert g.suspenso
    relogio.advance(0.02)  # 0,26 s: acabou
    assert not g.suspenso
    mon.press("F6")
    assert disparos == ["F6"]


def test_a_graca_termina_no_instante_combinado_e_nao_um_instante_depois():
    relogio = FakeClock(100.0)
    g, _mon, _disparos = _novo(suspensiveis=["F6"], relogio=relogio.monotonic)
    g.suspender(); g.retomar(graca=0.25)
    relogio.advance(0.25)
    assert not g.suspenso


def test_a_graca_nao_atrapalha_o_que_nao_e_suspensivel():
    relogio = FakeClock(100.0)
    g, mon, disparos = _novo(suspensiveis=["F6"], fixos=["F12"], relogio=relogio.monotonic)
    g.suspender(); g.retomar(graca=0.25)
    mon.press("F12")
    assert disparos == ["F12"]


def test_retomar_sem_graca_vale_na_hora_e_suspender_de_novo_cancela_a_graca():
    relogio = FakeClock(100.0)
    g, _mon, _disparos = _novo(suspensiveis=["F6"], relogio=relogio.monotonic)
    g.suspender(); g.retomar()
    assert not g.suspenso
    g.suspender(); g.retomar(graca=5.0)
    assert g.suspenso
    g.suspender()
    relogio.advance(10.0)
    assert g.suspenso, "suspendeu de novo: só `retomar` solta"
    g.retomar()
    assert not g.suspenso


def test_suspender_duas_vezes_e_retomar_sem_ter_suspendido_nao_quebram_nada():
    g, mon, disparos = _novo(suspensiveis=["F6"])
    g.retomar()
    g.suspender(); g.suspender()
    mon.press("F6")
    assert disparos == []
    g.retomar()
    mon.release("F6"); mon.press("F6")
    assert disparos == ["F6"]


def test_o_relogio_padrao_e_o_monotonico():
    import time
    assert GlobalHotkeyManager(FakeMonitor())._relogio is time.monotonic


# ------------------------------------------------------------------------------------------------ registro, remoção e limpeza
def test_remover_o_atalho_apaga_a_marca_e_registrar_de_novo_sem_marca_dispara_suspenso():
    g, mon, disparos = _novo(suspensiveis=["F6"])
    g.unregister("F6")
    g.register("F6", lambda: disparos.append("sem marca"))
    g.suspender()
    mon.press("F6")
    assert disparos == ["sem marca"]


def test_limpar_apaga_as_marcas_mas_nao_a_suspensao():
    g, mon, disparos = _novo(suspensiveis=["F6"])
    g.suspender()
    g.clear()
    assert g.suspenso, "refazer os atalhos no meio de uma captura não pode acabar com ela"
    g.register("F6", lambda: disparos.append("novo"))
    mon.press("F6")
    assert disparos == ["novo"], "a marca de antes foi embora com o clear: o atalho novo sem marca dispara"


def test_registrar_o_mesmo_callback_de_novo_atualiza_a_marca():
    monitor, disparos = FakeMonitor(), []
    g = GlobalHotkeyManager(monitor)
    def cb():
        disparos.append("F6")
    g.register("F6", cb, suspensivel=True)
    g.register("F6", cb)  # idempotente, e agora sem a marca
    g.start(); g.suspender()
    monitor.press("F6")
    assert disparos == ["F6"]


def test_registrar_outro_callback_na_mesma_combinacao_continua_sendo_conflito():
    g = GlobalHotkeyManager(FakeMonitor())
    g.register("F6", lambda: None, suspensivel=True)
    with pytest.raises(HotkeyConflictError):
        g.register("F6", lambda: None, suspensivel=True)


def test_parar_o_gerenciador_nao_muda_a_suspensao():
    g, _mon, _disparos = _novo(suspensiveis=["F6"])
    g.suspender(); g.stop()
    assert g.suspenso


# ------------------------------------------------------------------------------------------------ a janela: só as automações são suspensas
def test_registrar_o_plano_marca_so_os_atalhos_de_mapa_e_os_de_controle_seguem_valendo(tmp_path):
    janela = _abrir(tmp_path)  # os 3 mapas reais (MOUSE_X1, "=", MOUSE_X2) e as teclas de controle
    janela.hotkey_manager.suspender()
    janela.clicar("x1"); janela.apertar("="); janela.clicar("x2")
    assert janela.disparos == [], "as três automações ficam quietas"
    janela.apertar("F12")
    assert janela.disparos == ["control:emergency"], "a parada de emergência não pode sumir"
    janela.hotkey_manager.retomar()
    janela.clicar("x1")
    assert janela.disparos == ["control:emergency", "map:Click genshin"]


def test_refazer_os_atalhos_com_a_suspensao_ligada_mantem_a_suspensao(tmp_path):
    janela = _abrir(tmp_path)
    janela.hotkey_manager.suspender()
    janela._register_all_hotkeys()  # a janela refaz tudo (ex.: o dono mudou uma tecla durante a captura)
    janela.apertar("=")
    assert janela.disparos == []
    janela.hotkey_manager.retomar()
    janela.apertar("=")
    assert janela.disparos == ["map:Exemplo — Primeira automação"]
