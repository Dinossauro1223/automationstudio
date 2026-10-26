"""D1 (25.5): botões laterais do mouse. O caminho funcional usa o nome cru do sistema do começo ao fim;
a troca x1<->x2 existe só para DESENHAR o mouse virtual (core.display_mouse_button_name).

No 25.3 a troca era aplicada em três lugares e o visualizador, o gravador e os atalhos discordavam sobre qual
botão era qual (achado 1.11 do Ponto 1).
"""
import pytest

from automationstudio import core
from automationstudio.core import AutomationMap, Command, InputType, StateManager, build_timeline, display_mouse_button_name
from automationstudio.input_system import GlobalHotkeyManager, GlobalInputMonitor, Recorder
from testsupport.fakes import FakeMonitor
from testsupport.helpers import events_of, run_to_end


class _Botao:
    def __init__(self, nome: str) -> None:
        self.name = nome


def test_o_mesmo_clique_fisico_tem_o_mesmo_nome_no_gravador_nos_atalhos_e_no_motor(fake_clock, make_engine):
    monitor = GlobalInputMonitor()
    visto_pelo_monitor, disparos = [], []
    monitor.on_mouse_button.append(lambda nome, apertado: visto_pelo_monitor.append(nome))
    atalhos = GlobalHotkeyManager(monitor)
    atalhos.register("MOUSE_X1", lambda: disparos.append("X1"))
    atalhos.start()
    rec = Recorder(monitor, StateManager(), clock=fake_clock)
    monitor._keyboard_listener = object()  # finge listener ativo: nenhum hook global é iniciado
    rec.start()
    monitor._emit_click(0, 0, _Botao("x1"), True)
    fake_clock.advance(0.1)
    monitor._emit_click(0, 0, _Botao("x1"), False)
    comandos = rec.stop()

    assert visto_pelo_monitor[0] == "x1" and disparos == ["X1"]
    assert [(c.type, c.target) for c in comandos] == [(InputType.MOUSE_BUTTON, "x1")]
    motor, backend = make_engine()
    terminou, erros = run_to_end(motor, AutomationMap(name="Lateral", commands=comandos, repeat_count=1))
    assert terminou and not erros
    assert [(a, alvo) for _t, a, alvo in events_of(backend)] == [("mouse_down", "x1"), ("mouse_up", "x1")]


@pytest.mark.parametrize("cru,exibido", [("x1", "x2"), ("x2", "x1"), ("X1", "x2"), ("X2", "x1")])
def test_exibicao_troca_os_botoes_laterais(cru, exibido):
    assert core.DISPLAY_SWAPS_SIDE_BUTTONS is True, "a constante é decisão D1: mudar exige conferência no hardware"
    assert display_mouse_button_name(cru) == exibido


@pytest.mark.parametrize("nome", ["left", "right", "middle", "LEFT", "Middle"])
def test_exibicao_nao_mexe_nos_outros_botoes(nome):
    assert display_mouse_button_name(nome) == nome.lower()


def test_com_a_constante_desligada_a_exibicao_nao_troca(monkeypatch):
    monkeypatch.setattr(core, "DISPLAY_SWAPS_SIDE_BUTTONS", False)
    assert [display_mouse_button_name(n) for n in ("x1", "x2")] == ["x1", "x2"]


def test_a_troca_da_exibicao_e_uma_involucao():
    for nome in ("x1", "x2", "left"):
        assert display_mouse_button_name(display_mouse_button_name(nome)) == nome


def test_gravador_nao_aplica_a_troca_da_exibicao(gravar, fake_clock):
    rec, mon, _ = gravar()
    rec.start()
    mon.click("x2", True); fake_clock.advance(0.1); mon.click("x2", False)
    (comando,) = rec.stop()
    assert comando.target == "x2"
