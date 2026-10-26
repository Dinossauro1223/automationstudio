"""build_timeline: ordenação e eventos gerados por cada tipo de comando."""
from automationstudio.conditions import WaitCondition, WaitConditionType
from automationstudio.core import ActionType, AutomationMap, Command, InputType, build_timeline


def _eventos(*comandos):
    return [(round(e.time, 3), e.kind.value, e.target) for e in build_timeline(AutomationMap(name="T", commands=list(comandos)))]


def _tecla(alvo, inicio, duracao=0.2, **kw):
    return Command(type=InputType.KEY, target=alvo, start=inicio, duration=duracao, **kw)


def test_sobreposicao_intercala_pressionar_e_soltar_por_tempo():
    assert _eventos(_tecla("A", 0.0, 0.5), _tecla("B", 0.2, 0.5)) == [
        (0.0, "key_down", "A"), (0.2, "key_down", "B"), (0.5, "key_up", "A"), (0.7, "key_up", "B")]


def test_no_mesmo_instante_soltar_vem_antes_de_pressionar():
    # A termina em 0.5 e B começa em 0.5: soltar A primeiro evita "tecla presa" quando o alvo é o mesmo.
    eventos = _eventos(_tecla("A", 0.0, 0.5), _tecla("A", 0.5, 0.2))
    assert eventos[1:3] == [(0.5, "key_up", "A"), (0.5, "key_down", "A")]


def test_comando_desativado_nao_gera_eventos():
    assert _eventos(_tecla("A", 0.0, enabled=False)) == []


def test_pressionar_e_soltar_em_comandos_separados():
    eventos = _eventos(_tecla("X", 0.1, 0.0, action=ActionType.PRESS), _tecla("X", 0.9, 0.0, action=ActionType.RELEASE))
    assert eventos == [(0.1, "key_down", "X"), (0.9, "key_up", "X")]


def test_cada_tipo_gera_o_evento_esperado():
    texto = Command(type=InputType.TEXT, text="ab", start=1.0, duration=0.2)
    abrir = Command(type=InputType.APP_OPEN, target="notepad.exe", start=0.5)
    mover = Command(type=InputType.MOUSE_MOVE, x=5, y=6, start=0.5)
    rolar = Command(type=InputType.MOUSE_SCROLL, scroll_dy=-2, start=0.5)
    botao = Command(type=InputType.MOUSE_BUTTON, target="left", start=0.0, duration=0.1)
    kinds = {c.type: [e.kind.value for e in build_timeline(AutomationMap(name="T", commands=[c]))] for c in (texto, abrir, mover, rolar, botao)}
    assert kinds == {InputType.TEXT: ["text"], InputType.APP_OPEN: ["app_open"], InputType.MOUSE_MOVE: ["mouse_move"],
                     InputType.MOUSE_SCROLL: ["mouse_scroll"], InputType.MOUSE_BUTTON: ["mouse_down", "mouse_up"]}


def test_movimento_mesclado_gera_um_evento_por_ponto_da_trajetoria():
    caminho = [{"t": 0.0, "x": 0, "y": 0}, {"t": 0.5, "x": 5, "y": 5}, {"t": 1.0, "x": 10, "y": 10}]
    comando = Command(type=InputType.MOUSE_MOVE, x=10, y=10, start=2.0, duration=1.0, mouse_path=caminho, merged_move=True)
    eventos = build_timeline(AutomationMap(name="T", commands=[comando]))
    assert [(round(e.time, 3), e.x, e.y) for e in eventos] == [(2.0, 0, 0), (2.5, 5, 5), (3.0, 10, 10)]


def test_condicoes_ficam_so_no_primeiro_evento_do_comando():
    cond = WaitCondition(type=WaitConditionType.DELAY, timeout=0.3)
    eventos = build_timeline(AutomationMap(name="T", commands=[_tecla("A", 0.0, conditions=[cond])]))
    assert [len(e.wait_conditions) for e in eventos] == [1, 0]


def test_total_e_fim_efetivo_acompanham_o_ultimo_comando():
    mapa = AutomationMap(name="T", commands=[_tecla("A", 0.0, 0.5), _tecla("B", 0.2, 0.5)])
    assert round(mapa.total_duration(), 3) == 0.7
    assert [round(c.effective_end, 3) for c in mapa.commands] == [0.5, 0.7]


def test_abrir_aplicativo_ocupa_na_timeline_a_parte_conhecida_da_barreira():
    # A abertura não tem duração fixa (o carregamento é variável), mas a timeline representa a parte determinística
    # da barreira, estabilidade + segurança (+ atraso), e os comandos seguintes se ancoram DEPOIS dela.
    abrir = Command(type=InputType.APP_OPEN, target="bloco.exe", start=1.0, wait_process="bloco.exe",
                    wait_stable_ms=1500, wait_after_open=0.5, delay=0.25)
    mapa = AutomationMap(name="T", commands=[abrir])
    assert round(abrir.computed_delay_after, 3) == 2.25
    assert round(abrir.effective_end, 3) == 3.25   # 1,0 + 1,5 + 0,5 + 0,25
    assert round(mapa.total_duration(), 3) == 3.25
