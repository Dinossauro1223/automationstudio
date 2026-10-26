"""Motor de execução: o que cada tipo de comando entrega ao backend (argumentos, ordem e tempos)."""
import pytest

from automationstudio.core import ActionType, Command, InputType
from testsupport.helpers import events_of, join_engine, key, make_map, run_to_end


def _rodar(make_engine, comandos, **kwargs):
    motor, backend = make_engine()
    terminou, erros = run_to_end(motor, make_map(comandos, **kwargs))
    assert terminou and not erros, erros
    return events_of(backend)


def test_mouse_move_absoluto_e_relativo(make_engine):
    eventos = _rodar(make_engine, [
        Command(type=InputType.MOUSE_MOVE, x=10, y=20, start=0.0),
        Command(type=InputType.MOUSE_MOVE, x=5, y=-5, relative=True, start=0.1)])
    assert eventos == [(0.0, "mouse_move", (10, 20, False)), (0.1, "mouse_move", (5, -5, True))]


def test_rolagem_entrega_dx_e_dy_nessa_ordem(make_engine):
    eventos = _rodar(make_engine, [Command(type=InputType.MOUSE_SCROLL, scroll_dx=1, scroll_dy=-3, start=0.2)])
    assert eventos == [(0.2, "mouse_scroll", (1, -3))]


@pytest.mark.parametrize("botao", ["left", "right", "middle", "x1", "x2"])
def test_botao_do_mouse_chega_com_o_nome_cru(make_engine, botao):
    # D1 (25.5): o caminho funcional usa o nome cru; a troca de x1/x2 existe só na exibição do mouse virtual.
    eventos = _rodar(make_engine, [Command(type=InputType.MOUSE_BUTTON, target=botao, start=0.0, duration=0.1)])
    assert eventos == [(0.0, "mouse_down", botao), (0.1, "mouse_up", botao)]


def test_acoes_separadas_pressionar_e_soltar(make_engine):
    eventos = _rodar(make_engine, [
        key("X", 0.1, 0.0, action=ActionType.PRESS),
        key("X", 0.9, 0.0, action=ActionType.RELEASE)])
    assert eventos == [(0.1, "key_down", "X"), (0.9, "key_up", "X")]


def test_movimento_mesclado_envia_um_evento_por_ponto_em_tempo_proporcional(make_engine):
    caminho = [{"t": 0.0, "x": 0, "y": 0}, {"t": 0.5, "x": 5, "y": 5}, {"t": 1.0, "x": 10, "y": 10}]
    comando = Command(type=InputType.MOUSE_MOVE, x=10, y=10, start=1.0, duration=1.0, mouse_path=caminho, merged_move=True)
    assert _rodar(make_engine, [comando]) == [
        (1.0, "mouse_move", (0, 0, False)), (1.5, "mouse_move", (5, 5, False)), (2.0, "mouse_move", (10, 10, False))]


def test_texto_e_enviado_um_caractere_por_vez(make_engine):
    eventos = _rodar(make_engine, [Command(type=InputType.TEXT, text="oi!", start=0.5, duration=0.1)])
    assert eventos == [(0.5, "type_text", "o"), (0.5, "type_text", "i"), (0.5, "type_text", "!")]


def test_texto_com_acentos_chega_inteiro(make_engine):
    eventos = _rodar(make_engine, [Command(type=InputType.TEXT, text="ação é ç", start=0.0, duration=0.1)])
    assert "".join(alvo for _t, _a, alvo in eventos) == "ação é ç"


def test_parada_no_meio_do_texto_interrompe_a_digitacao(make_engine, hook_backend):
    # Item 1.06 do Ponto 1: a parada interrompe o texto entre caracteres, sem esperar o texto inteiro.
    motor, backend = make_engine(backend=hook_backend)
    hook_backend.hooks[2] = motor.stop  # logo depois do 2º caractere
    motor.run(make_map([Command(type=InputType.TEXT, text="abcdef", start=0.0, duration=0.1)]))
    join_engine(motor)
    assert [alvo for _t, _a, alvo in events_of(backend)] == ["a", "b"]


def test_comandos_simultaneos_chegam_na_ordem_da_timeline(make_engine):
    # SHIFT segurado enquanto E é pressionada: o grupo é só visual, o que vale é o tempo de cada comando.
    eventos = _rodar(make_engine, [key("SHIFT", 0.0, 0.5), key("E", 0.1, 0.1)])
    assert eventos == [
        (0.0, "key_down", "SHIFT"), (0.1, "key_down", "E"), (0.2, "key_up", "E"), (0.5, "key_up", "SHIFT")]


def test_tecla_presa_em_comando_press_e_solta_ao_fim_natural(make_engine):
    # Um comando só com PRESS nunca solta sozinho; o fim da execução garante a liberação (item 25 do roteiro).
    motor, backend = make_engine()
    terminou, erros = run_to_end(motor, make_map([key("X", 0.0, 0.0, action=ActionType.PRESS)]))
    assert terminou and not erros
    assert events_of(backend) == [(0.0, "key_down", "X"), (0.0, "key_up", "X")]
