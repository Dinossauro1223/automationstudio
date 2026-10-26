"""O editor de ação (CommandDialog).

A regra central, que o item 2.07 da auditoria quebrava: ABRIR UM COMANDO E SALVAR SEM MEXER EM NADA NÃO PODE ALTERAR O
COMANDO. O diálogo reescreve o comando inteiro a partir dos campos da tela (`result_command`), então qualquer campo
que ele não carregue na abertura é perdido ao salvar: comportamento "manter pressionado", teclas fora da lista, grupo,
duração de movimento mesclado, comando desativado, texto-guia "Nenhum aplicativo selecionado" gravado como processo.

Roda com o PySide6 real e, no desenvolvimento (sem Qt), contra o dublê funcional parcial (AS_TEST_QT_STUB=widgets).
O que só o Qt real confirma está em test_qt_semantics.py.
"""
import copy

import pytest

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtWidgets import QFileDialog, QWidget  # noqa: E402

from automationstudio import core  # noqa: E402
from automationstudio.command_editor import CommandDialog  # noqa: E402
from automationstudio.conditions import WaitCondition, WaitConditionType  # noqa: E402
from automationstudio.core import (ActionType, AutomationMap, Command, CommandGroup, InputType, build_timeline,  # noqa: E402
                                   map_from_json)
from testsupport.gui_helpers import differences, write_png  # noqa: E402
from testsupport.helpers import events_of, make_map, run_to_end  # noqa: E402

pytestmark = pytest.mark.gui

K, B, M, S, T, A, W = (InputType.KEY, InputType.MOUSE_BUTTON, InputType.MOUSE_MOVE, InputType.MOUSE_SCROLL,
                       InputType.TEXT, InputType.APP_OPEN, InputType.WAIT)


def _abrir(comando=None, pai=None):
    """Abre o editor como a janela principal faz: com o comando original (a janela passa o objeto do próprio mapa)."""
    return CommandDialog(command=copy.deepcopy(comando) if comando is not None else None, parent=pai)


def _escolher_tipo(dialogo, tipo) -> None:
    dialogo.type_combo.setCurrentIndex(dialogo.type_combo.findData(tipo))


def _aceitar(dialogo, gui):
    """Aperta "Salvar": devolve o comando, ou falha mostrando o aviso que o editor exibiu ao recusar."""
    aceitou = []
    dialogo.accepted.connect(lambda: aceitou.append(True))
    antes = len(gui.calls)
    dialogo._accept()
    assert aceitou, f"o editor recusou o comando e avisou: {gui.calls[antes:]}"
    return dialogo.result_command()


# ------------------------------------------------------------------------------------ 1. cada tipo até o motor
def _preencher_tecla(d):
    d.target_combo.setCurrentText("F")
    d.duration.setValue(0.2)


def _preencher_botao(d):
    d.target_combo.setCurrentIndex(d.target_combo.findData("x1"))  # lateral 1: nome cru do sistema (decisão D1)
    d.duration.setValue(0.1)


def _preencher_mover(d):
    d._move_pos = QPoint(100, 200)  # o seletor de posição na tela é modal; ele só deixa a posição aqui


def _preencher_rolar(d):
    d.scroll_direction.setCurrentIndex(d.scroll_direction.findData("down"))
    d.scroll_lines.setValue(3)


def _preencher_texto(d):
    d.text_edit.setPlainText("olá, mundo")


def _preencher_abrir(d):
    d.target_combo.setCurrentIndex(d.target_combo.findData("notepad.exe"))


def _preencher_esperar(d):
    d.condition_type.setCurrentIndex(d.condition_type.findData(WaitConditionType.DELAY))
    d.condition_timeout.setValue(0.5)
    d.condition_add.click()


POR_TIPO = [
    (K, _preencher_tecla, dict(target="F", duration=0.2, action=ActionType.PRESS_AND_RELEASE)),
    (B, _preencher_botao, dict(target="x1", duration=0.1, action=ActionType.PRESS_AND_RELEASE)),
    (M, _preencher_mover, dict(x=100, y=200, relative=False)),
    (S, _preencher_rolar, dict(target="down", scroll_dy=-3, scroll_dx=0)),
    (T, _preencher_texto, dict(text="olá, mundo")),
    (A, _preencher_abrir, dict(target="notepad.exe")),
    (W, _preencher_esperar, dict()),
]
IDS_POR_TIPO = [t.value for t, _, _ in POR_TIPO]


@pytest.mark.parametrize("tipo, preencher, esperado", POR_TIPO, ids=IDS_POR_TIPO)
def test_cada_tipo_de_acao_sai_do_editor_como_comando_valido(gui, tipo, preencher, esperado):
    # O defeito 1.01 (mover, rolar e esperar bloqueados) teria sido pego aqui: monta cada tipo pelo formulário,
    # salva, e exige que o comando seja válido.
    dialogo = _abrir()
    _escolher_tipo(dialogo, tipo)
    preencher(dialogo)
    comando = _aceitar(dialogo, gui)
    assert comando.type == tipo
    assert comando.validate() == []
    for campo, valor in esperado.items():
        assert getattr(comando, campo) == valor, campo


@pytest.mark.parametrize("tipo, preencher, esperado", POR_TIPO, ids=IDS_POR_TIPO)
def test_o_comando_do_editor_vira_linha_do_tempo_e_o_motor_o_aceita(gui, make_engine, tipo, preencher, esperado):
    dialogo = _abrir()
    _escolher_tipo(dialogo, tipo)
    preencher(dialogo)
    comando = _aceitar(dialogo, gui)
    mapa = make_map([comando])
    assert mapa.validate() == [] and build_timeline(mapa), "o motor não receberia nenhum evento deste comando"
    if tipo == A:
        return  # abrir aplicativo só existe no Windows: o motor recusa em outros sistemas
    motor, backend = make_engine()
    try:
        terminou, erros = run_to_end(motor, mapa, timeout=5.0)
    finally:
        motor.emergency_stop()  # se o comando prendesse o motor (espera por processo), a thread não fica para trás
    assert terminou and erros == [], (terminou, [repr(e) for e in erros], f"wait_process={comando.wait_process!r}")
    if tipo != W:
        assert events_of(backend), "o motor aceitou o comando mas não enviou nenhuma entrada"


def test_recusas_do_editor_avisam_e_nao_aceitam(gui):
    # Cada tipo incompleto precisa ser recusado COM um aviso: sem isso, o botão "Salvar" pareceria quebrado.
    casos = [(M, "Posição não definida"), (W, "Espera incompleta"), (T, "Texto vazio"), (A, "Ação incompleta")]
    for tipo, titulo in casos:
        dialogo = _abrir()
        _escolher_tipo(dialogo, tipo)
        aceitou = []
        dialogo.accepted.connect(lambda: aceitou.append(True))
        antes = len(gui.calls)
        dialogo._accept()
        assert not aceitou, tipo
        assert [c for c in gui.calls[antes:] if c[0] == "warning" and c[1] == titulo], (tipo, gui.calls[antes:])


def test_tecla_sem_tempo_e_recusada(gui):
    dialogo = _abrir()
    dialogo.duration.setValue(0)
    aceitou = []
    dialogo.accepted.connect(lambda: aceitou.append(True))
    dialogo._accept()
    assert not aceitou and gui.calls[-1][:2] == ("warning", "Tempo inválido")


# ------------------------------------------------------------------- 2. abrir e salvar sem mexer não altera nada
def _casos_de_ida_e_volta() -> list[tuple[str, Command]]:
    caminho = {"t": 0.0, "x": 961, "y": 540}, {"t": 0.5, "x": 960, "y": 536}, {"t": 1.0, "x": 959, "y": 540}
    condicoes = [
        WaitCondition(type=WaitConditionType.PROCESS, target="notepad.exe", timeout=10.0, stable_ms=800, after=0.2,
                      parameters={"command_id": "cmd_000001"}),
        WaitCondition(type=WaitConditionType.DELAY, timeout=1.5),
        WaitCondition(type=WaitConditionType.IMAGE, timeout=5.0, parameters={
            "image_path": "C:/imagens/botao.png", "confidence": 0.9, "interval": 0.25, "search": True,
            "region": {"x": 10, "y": 20, "w": 300, "h": 200}}),
    ]
    return [
        ("tecla", Command(type=K, target="F", start=0.5, duration=0.2, delay=0.1, description="atacar")),
        ("tecla-manter-pressionada", Command(type=K, target="A", action=ActionType.PRESS, start=1.0, duration=0.1)),
        ("tecla-soltar", Command(type=K, target="A", action=ActionType.RELEASE, start=2.0, duration=0.1)),
        ("tecla-espaco", Command(type=K, target="SPACE", start=0.0, duration=0.1)),
        ("tecla-ponto-e-virgula", Command(type=K, target=";", start=0.0, duration=0.1)),
        ("botao-esquerdo", Command(type=B, target="left", start=0.25, duration=0.1)),
        ("botao-lateral-1", Command(type=B, target="x1", start=0.25, duration=0.1)),
        ("botao-lateral-2", Command(type=B, target="x2", start=0.25, duration=0.1)),
        ("mover", Command(type=M, x=100, y=200, start=0.3)),
        ("mover-para-a-origem", Command(type=M, x=0, y=0, start=0.3)),
        ("mover-mesclado", Command(type=M, x=961, y=540, start=0.704, duration=0.497, merged_move=True,
                                   mouse_path=[dict(p) for p in caminho], description="Movimento do mouse (mesclado)")),
        ("rolar-para-cima", Command(type=S, target="up", scroll_dy=3, start=1.0)),
        ("rolar-para-baixo", Command(type=S, target="down", scroll_dy=-4, start=1.0)),
        ("rolar-para-a-esquerda", Command(type=S, target="left", scroll_dx=-2, start=1.0)),
        ("rolar-para-a-direita", Command(type=S, target="right", scroll_dx=5, start=1.0)),
        ("texto", Command(type=T, text="olá, mundo", start=0.1)),
        ("abrir-aplicativo-da-lista", Command(type=A, target="notepad.exe", wait_process="notepad.exe", wait_timeout=30.0,
                                              wait_stable_ms=1500, wait_after_open=0.5, description="Abrir o Bloco de Notas")),
        ("abrir-aplicativo-fora-da-lista", Command(type=A, target="C:\\Jogos\\jogo.exe", wait_process="jogo.exe")),
        ("esperar-com-tres-condicoes", Command(type=W, conditions=condicoes, start=2.0)),
        ("comando-desativado", Command(type=K, target="E", start=0.5, duration=0.1, enabled=False)),
        ("comando-de-um-grupo", Command(type=K, target="D", start=0.5, duration=0.1, group="D", group_id="grp_001315")),
        ("grupo-so-pelo-nome", Command(type=K, target="D", start=0.5, duration=0.1, group="D", group_id="")),
        ("tecla-esperando-processo-da-lista", Command(type=K, target="E", start=0.5, duration=0.1, wait_process="notepad.exe")),
        ("texto-esperando-processo-digitado", Command(type=T, text="oi", start=0.1, wait_process="meuapp.exe", wait_timeout=12.0)),
        # As caixas de número do editor vão até 3600 s (1 h). Um mapa longo tem comandos além disso.
        ("comando-depois-de-duas-horas", Command(type=K, target="E", start=7300.5, duration=0.1)),
        ("espera-de-processo-de-duas-horas", Command(type=A, target="notepad.exe", wait_process="notepad.exe", wait_timeout=7200.0)),
    ]


CASOS = _casos_de_ida_e_volta()
IDS_CASOS = [nome for nome, _ in CASOS]


def _sem_o_que_o_editor_recalcula(comando, mudancas: dict) -> dict:
    # Texto: a duração gravada vale `caracteres × intervalo` (o editor a recalcula; o conftest zera o intervalo).
    if comando.type == T:
        mudancas.pop("duration", None)
    return mudancas


@pytest.mark.parametrize("nome, comando", CASOS, ids=IDS_CASOS)
def test_abrir_e_salvar_sem_mexer_nao_altera_o_comando(gui, nome, comando):
    resultado = _abrir(comando).result_command()
    mudancas = _sem_o_que_o_editor_recalcula(comando, differences(comando, resultado))
    assert mudancas == {}, mudancas


def test_o_editor_novo_comeca_por_uma_tecla_valida(gui):
    comando = _aceitar(_abrir(), gui)
    assert comando.type == K and comando.target and comando.validate() == []


@pytest.mark.parametrize("nome", sorted(set(core._SPECIAL_KEY_NAMES.values())))
def test_toda_tecla_que_o_gravador_produz_sobrevive_ao_abrir_no_editor(gui, nome):
    # Antes, o editor só sabia mostrar as teclas da sua lista fixa e trocava as demais por "A" sem avisar.
    comando = Command(type=K, target=nome, start=0.0, duration=0.1)
    obtido = _abrir(comando).result_command().target
    assert obtido == nome, f"a tecla {nome!r} virou {obtido!r}"


@pytest.mark.parametrize("nome", list("ABCDEFGHIJKLMNOPQRSTUVWXYZÇ0123456789"))
def test_letras_e_digitos_sobrevivem_ao_abrir_no_editor(gui, nome):
    obtido = _abrir(Command(type=K, target=nome, start=0.0, duration=0.1)).result_command().target
    assert obtido == nome, f"a tecla {nome!r} virou {obtido!r}"


@pytest.mark.parametrize("acao", [ActionType.PRESS, ActionType.RELEASE, ActionType.PRESS_AND_RELEASE])
def test_o_comportamento_da_tecla_e_carregado_e_salvo(gui, acao):
    comando = Command(type=K, target="A", action=acao, start=1.0, duration=0.1)
    dialogo = _abrir(comando)
    assert dialogo.action_combo.currentData() == acao, dialogo.action_combo.currentData()
    assert dialogo.result_command().action == acao, dialogo.result_command().action


def test_mudar_o_tipo_de_botao_para_tecla_nao_leva_o_nome_do_botao_junto(gui):
    # O alvo "x1" de um botão do mouse não é uma tecla: ao trocar o tipo, a lista de teclas continua só com teclas.
    dialogo = _abrir(Command(type=B, target="x1", start=0.0, duration=0.1))
    _escolher_tipo(dialogo, K)
    teclas = [dialogo.target_combo.itemText(i) for i in range(dialogo.target_combo.count())]
    assert "X1" not in teclas and "LEFT" not in teclas[:1]
    assert dialogo.result_command().type == K


@pytest.mark.parametrize("original", [Command(type=K, target="A", start=0.0, duration=0.1),
                                      Command(type=B, target="x1", start=0.0, duration=0.1)], ids=["tecla", "botao"])
def test_mudar_o_tipo_para_abrir_aplicativo_nao_leva_o_alvo_de_tecla_ou_botao_junto(gui, original):
    # O alvo "A" de uma tecla (ou "x1" de um botão) não é um aplicativo. Sem essa guarda o combo ganharia um item extra
    # ("A — A") já escolhido e, ao salvar, o comando abriria um aplicativo chamado "A".
    dialogo = _abrir(original)
    _escolher_tipo(dialogo, A)
    dados = [dialogo.target_combo.itemData(i) for i in range(dialogo.target_combo.count())]
    assert original.target not in dados, dados
    assert dialogo.target_combo.currentData() == "", dialogo.target_combo.currentData()


def test_movimento_existente_mostra_a_posicao_na_tela(gui):
    dialogo = _abrir(Command(type=M, x=961, y=540, start=0.0))
    assert dialogo.position_label.text() == "Posição definida: X=961, Y=540", dialogo.position_label.text()


def test_movimento_na_origem_conta_como_posicao_definida(gui):
    dialogo = _abrir(Command(type=M, x=0, y=0, start=0.0))
    assert dialogo.position_label.text() == "Posição definida: X=0, Y=0"
    assert (dialogo.result_command().x, dialogo.result_command().y) == (0, 0)


def test_movimento_mesclado_mantem_duracao_e_trajeto_ao_salvar(gui):
    # Antes: result_command zerava a duração. O trajeto gravado (t de 0 a 1) passava a ser executado de uma vez só.
    comando = Command(type=M, x=961, y=540, start=0.704, duration=0.497, merged_move=True,
                      mouse_path=[{"t": 0.0, "x": 961, "y": 540}, {"t": 1.0, "x": 959, "y": 540}])
    resultado = _abrir(comando).result_command()
    assert resultado.duration == pytest.approx(0.497) and resultado.merged_move
    assert resultado.mouse_path == comando.mouse_path


def test_rolagem_gravada_e_normalizada_ao_salvar_sem_mudar_o_efeito(gui):
    # O gravador cria a rolagem com ação "pressionar" e sem alvo; o editor grava "pressionar e soltar" e a direção.
    # Não muda a execução (a rolagem não tem duração), então isto só documenta a normalização.
    comando = Command(type=S, action=ActionType.PRESS, start=1.0, scroll_dy=3)
    resultado = _abrir(comando).result_command()
    assert (resultado.action, resultado.target, resultado.scroll_dy, resultado.scroll_dx, resultado.start) == (
        ActionType.PRESS_AND_RELEASE, "up", 3, 0, 1.0)


def test_comando_desativado_continua_desativado_depois_de_editado(gui):
    resultado = _abrir(Command(type=K, target="E", start=0.0, duration=0.1, enabled=False)).result_command()
    assert resultado.enabled is False, "editar um comando desativado o reativou"


def test_comando_novo_nasce_ativado(gui):
    assert _abrir().result_command().enabled is True


def test_o_grupo_do_comando_nao_some_quando_o_painel_nao_conhece_o_mapa(gui):
    # O painel lateral não entrega o mapa ao editor; antes, o grupo caía em "Sem grupo" e era apagado ao salvar.
    comando = Command(type=K, target="D", start=0.0, duration=0.1, group="D", group_id="grp_001315")
    resultado = _abrir(comando).result_command()
    assert (resultado.group, resultado.group_id) == ("D", "grp_001315"), (resultado.group, resultado.group_id)


def test_tirar_o_comando_do_grupo_continua_possivel_pelo_editor(gui):
    dialogo = _abrir(Command(type=K, target="D", start=0.0, duration=0.1, group="D", group_id="grp_001315"))
    dialogo.group_combo.setCurrentIndex(0)  # "Sem grupo"
    resultado = dialogo.result_command()
    assert (resultado.group, resultado.group_id) == ("", "")


# ---------------------------------------------------------------- 3. o processo a esperar (campo "Aplicativo")
def test_o_texto_guia_nunca_e_gravado_como_processo_a_esperar(gui):
    # Antes: "Nenhum aplicativo selecionado" ia parar em wait_process de TODO comando novo, e o motor esperaria
    # para sempre por um processo com esse nome antes de soltar a tecla.
    for tipo in (K, B, S, T):
        dialogo = _abrir()
        _escolher_tipo(dialogo, tipo)
        assert dialogo.result_command().wait_process == "", (tipo.value, dialogo.result_command().wait_process)


def test_processo_escolhido_na_lista_grava_o_executavel_e_nao_o_rotulo(gui):
    dialogo = _abrir()
    _escolher_tipo(dialogo, A)
    dialogo.target_combo.setCurrentIndex(dialogo.target_combo.findData("notepad.exe"))
    dialogo.wait_process_edit.setCurrentIndex(dialogo.wait_process_edit.findData("notepad.exe"))
    assert dialogo.result_command().wait_process == "notepad.exe", dialogo.result_command().wait_process


def test_processo_digitado_a_mao_e_mantido(gui):
    dialogo = _abrir()
    _escolher_tipo(dialogo, A)
    dialogo.target_combo.setCurrentIndex(dialogo.target_combo.findData("notepad.exe"))
    dialogo.wait_process_edit.setCurrentText("meuapp.exe")
    assert dialogo.result_command().wait_process == "meuapp.exe", dialogo.result_command().wait_process


def test_voltar_para_nenhum_aplicativo_limpa_o_processo(gui):
    dialogo = _abrir(Command(type=K, target="E", start=0.0, duration=0.1, wait_process="notepad.exe"))
    dialogo.wait_process_edit.setCurrentIndex(0)  # "Nenhum aplicativo selecionado"
    assert dialogo.result_command().wait_process == "", dialogo.result_command().wait_process


def test_texto_digitado_por_cima_de_um_item_da_lista_vence_o_item(gui):
    # Num combo editável o índice atual NÃO acompanha o que a pessoa digita: lê-se o texto do campo, não o dado do item.
    dialogo = _abrir()
    _escolher_tipo(dialogo, A)
    dialogo.wait_process_edit.setCurrentIndex(dialogo.wait_process_edit.findData("notepad.exe"))
    dialogo.wait_process_edit.setCurrentText("meuapp.exe")
    assert dialogo.result_command().wait_process == "meuapp.exe", dialogo.result_command().wait_process


def test_apagar_o_texto_do_processo_limpa_o_processo(gui):
    dialogo = _abrir(Command(type=K, target="E", start=0.0, duration=0.1, wait_process="notepad.exe"))
    dialogo.wait_process_edit.setCurrentText("")
    assert dialogo.result_command().wait_process == "", dialogo.result_command().wait_process


def test_o_aplicativo_a_abrir_nunca_vira_o_texto_guia(gui):
    # Mesmo chamando result_command sem passar pela validação (que recusaria), o texto-guia não pode virar o alvo.
    dialogo = _abrir()
    _escolher_tipo(dialogo, A)
    assert dialogo.result_command().target == "", dialogo.result_command().target


# --------------------------------------------------- 4. trocar de comando com o painel aberto (load_command)
PARES = [
    ("tecla-para-rolagem", Command(type=K, target="A", start=1.0, duration=0.3, delay=0.2),
     Command(type=S, target="down", scroll_dy=-4, start=5.0, delay=0.7)),
    ("espera-para-tecla", Command(type=W, conditions=[WaitCondition(type=WaitConditionType.DELAY, timeout=0.5)], start=2.0),
     Command(type=K, target="B", start=3.0, duration=0.1)),
    ("abrir-aplicativo-para-tecla", Command(type=A, target="notepad.exe", wait_process="notepad.exe", wait_timeout=30.0,
                                            wait_stable_ms=1500, wait_after_open=0.5),
     Command(type=K, target="B", start=3.0, duration=0.1)),
    ("movimento-para-tecla", Command(type=M, x=100, y=200, start=0.3), Command(type=K, target="B", start=3.0, duration=0.1)),
    ("texto-para-botao", Command(type=T, text="olá", start=0.1, description="saudação"),
     Command(type=B, target="right", start=4.0, duration=0.25)),
    ("grupo-para-sem-grupo", Command(type=K, target="D", start=0.5, duration=0.1, group="D", group_id="grp_001315"),
     Command(type=K, target="E", start=0.6, duration=0.1)),
    ("sem-grupo-para-grupo", Command(type=K, target="E", start=0.6, duration=0.1),
     Command(type=K, target="D", start=0.5, duration=0.1, group="D", group_id="grp_001315")),
    ("tecla-para-movimento", Command(type=K, target="B", start=3.0, duration=0.1), Command(type=M, x=7, y=9, start=0.3)),
    ("rolagem-para-rolagem", Command(type=S, target="up", scroll_dy=3, start=1.0),
     Command(type=S, target="left", scroll_dx=-2, start=2.0)),
    ("processo-da-lista-para-nenhum", Command(type=K, target="E", start=0.5, duration=0.1, wait_process="notepad.exe"),
     Command(type=K, target="F", start=0.9, duration=0.1)),
    ("tecla-fora-da-lista-para-tecla", Command(type=K, target=";", start=0.5, duration=0.1),
     Command(type=K, target="F", start=0.9, duration=0.1)),
    ("movimento-mesclado-para-tecla", Command(type=M, x=961, y=540, start=0.7, duration=0.5, merged_move=True,
                                              mouse_path=[{"t": 0.0, "x": 961, "y": 540}, {"t": 1.0, "x": 959, "y": 540}]),
     Command(type=K, target="F", start=0.9, duration=0.1)),
]


@pytest.mark.parametrize("nome, antes, depois", PARES, ids=[p[0] for p in PARES])
def test_trocar_de_comando_com_o_painel_aberto_recarrega_todos_os_campos(gui, nome, antes, depois):
    # O painel lateral reaproveita o mesmo editor (`load_command`). O que ele não relê vaza do comando anterior para o
    # novo na hora de salvar: início, atraso, duração, rolagem, grupo, condições, processo, posição.
    dialogo = _abrir(antes)
    dialogo.load_command(copy.deepcopy(depois))
    mudancas = _sem_o_que_o_editor_recalcula(depois, differences(depois, dialogo.result_command()))
    assert mudancas == {}, mudancas


def test_recarregar_o_mesmo_comando_nao_muda_nada(gui):
    comando = Command(type=K, target="F", start=0.5, duration=0.2, delay=0.1, description="atacar")
    dialogo = _abrir(comando)
    dialogo.load_command(copy.deepcopy(comando))
    mudancas = differences(comando, dialogo.result_command())
    assert mudancas == {}, mudancas


def test_recarregar_atualiza_o_rotulo_da_posicao(gui):
    dialogo = _abrir(Command(type=M, x=1, y=2, start=0.0))
    dialogo.load_command(Command(type=M, x=30, y=40, start=0.0))
    assert dialogo.position_label.text() == "Posição definida: X=30, Y=40", dialogo.position_label.text()
    dialogo.load_command(Command(type=K, target="A", start=0.0, duration=0.1))
    assert dialogo.position_label.text() == "Nenhuma posição escolhida.", dialogo.position_label.text()


def test_recarregar_substitui_a_lista_de_condicoes(gui):
    dialogo = _abrir(Command(type=W, conditions=[WaitCondition(type=WaitConditionType.DELAY, timeout=0.5)]))
    assert dialogo.condition_list.count() == 1
    dialogo.load_command(Command(type=W, conditions=[WaitCondition(type=WaitConditionType.DELAY, timeout=2.0),
                                                     WaitCondition(type=WaitConditionType.DELAY, timeout=3.0)]))
    assert [c.timeout for c in dialogo._current_conditions()] == [2.0, 3.0], [c.timeout for c in dialogo._current_conditions()]


def test_recarregar_nao_acumula_grupos_fantasma(gui):
    # O grupo que o editor só conhece pelo comando entra como item extra; ao trocar de comando o item do anterior sai.
    dialogo = _abrir(Command(type=K, target="D", start=0.0, duration=0.1, group="D", group_id="grp_1"))
    dialogo.load_command(Command(type=K, target="E", start=0.0, duration=0.1, group="E", group_id="grp_2"))
    textos = [dialogo.group_combo.itemText(i) for i in range(dialogo.group_combo.count())]
    assert textos == ["Sem grupo", "E"], textos
    dialogo.load_command(Command(type=K, target="F", start=0.0, duration=0.1))
    assert [dialogo.group_combo.itemText(i) for i in range(dialogo.group_combo.count())] == ["Sem grupo"]
    assert dialogo.group_combo.currentIndex() == 0


def _itens(combo):
    return [(combo.itemText(i), combo.itemData(i)) for i in range(combo.count())]


def _estado(d) -> dict:
    """Tudo o que a tela mostra do comando, inclusive os campos que o tipo atual esconde."""
    return {
        "tipo": d.type_combo.currentData(), "comportamento": d.action_combo.currentData(),
        "alvo": (d.target_combo.currentText(), d.target_combo.currentData(), _itens(d.target_combo)),
        "texto": d.text_edit.toPlainText(), "descricao": d.description.text(),
        "inicio": d.start.value(), "atraso": d.delay.value(), "duracao": d.duration.value(),
        "rolagem": (d.scroll_direction.currentData(), d.scroll_lines.value()),
        "posicao": (None if d._move_pos is None else (d._move_pos.x(), d._move_pos.y()), d.position_label.text()),
        "grupo": (d.group_combo.currentText(), d.group_combo.currentData(), _itens(d.group_combo)),
        "processo": (d.wait_process_edit.currentText(), d._wait_process_value()),
        "espera": (d.wait_timeout.value(), d.wait_stable.value(), d.wait_after.value()),
        "condicoes": [(c.type, c.timeout, c.target) for c in d._current_conditions()],
    }


def _comando_sujo() -> Command:
    """Um comando com TODOS os campos fora do padrão: o que `load_command` esquecer de reler aparece na comparação."""
    return Command(type=A, target="C:\\x\\sujo.exe", start=9.0, delay=3.0, duration=2.0, description="sujo", group="G",
                   group_id="grp_sujo", wait_process="sujo.exe", wait_timeout=7.0, wait_stable_ms=1234, wait_after_open=1.5,
                   scroll_dy=7, x=5, y=6, enabled=False,
                   conditions=[WaitCondition(type=WaitConditionType.DELAY, timeout=9.0)])


@pytest.mark.parametrize("nome, comando", CASOS, ids=IDS_CASOS)
def test_trocar_de_comando_deixa_a_tela_igual_a_abrir_o_comando(gui, nome, comando):
    # `load_command` e o construtor passam pelo mesmo carregamento. Este teste impede que os dois caminhos voltem a se
    # separar: o editor reaproveitado (partindo de um comando todo fora do padrão) tem de ficar idêntico ao editor novo.
    novo = _abrir(comando)
    reaproveitado = _abrir(_comando_sujo())
    reaproveitado.load_command(copy.deepcopy(comando))
    assert _estado(reaproveitado) == _estado(novo)


# ----------------------------------------------------------------------------- 5. mapas reais e mapa do pai
def _formas_dos_mapas_reais(legacy_maps) -> list[tuple[str, Command]]:
    escolhidos, vistos = [], set()
    for nome in sorted(legacy_maps):
        for comando in map_from_json(legacy_maps[nome]).commands:
            forma = (nome, comando.type.value, comando.target, comando.action.value, bool(comando.group_id), comando.merged_move)
            if forma not in vistos:
                vistos.add(forma)
                escolhidos.append((f"{nome}:{comando.id}", comando))
    return escolhidos


def test_abrir_e_salvar_os_mapas_reais_nao_altera_os_comandos(gui, legacy_maps):
    # Um comando de cada "forma" (tipo, tecla, ação, grupo, mesclado) dos 3 mapas reais. O editor arredonda início e
    # duração para milissegundos (caixas de número com 3 casas): é a única mudança aceita.
    escolhidos = _formas_dos_mapas_reais(legacy_maps)
    assert len(escolhidos) >= 10, "poucas formas: o teste não estaria cobrindo os mapas reais"
    erros = {}
    for rotulo, comando in escolhidos:
        mudancas = _sem_o_que_o_editor_recalcula(comando, differences(comando, _abrir(comando).result_command()))
        if mudancas:
            erros[rotulo] = mudancas
    assert erros == {}, erros


def test_o_arredondamento_do_editor_nao_passa_de_meio_milissegundo(gui, legacy_maps):
    # O editor mostra segundos com 3 casas; os mapas gravados têm 16. A diferença nunca passa de 0,5 ms.
    comando = next(c for c in map_from_json(legacy_maps["Flins combo"]).commands if c.merged_move)
    resultado = _abrir(comando).result_command()
    assert abs(resultado.start - comando.start) <= 5e-4 and abs(resultado.duration - comando.duration) <= 5e-4


def _mapa_com_grupo():
    grupo = CommandGroup(id="grp_x", name="Ataque", delay_profiles={"F": 0.25})
    comandos = [Command(type=K, target="F", start=0.0, duration=0.1, group="Ataque", group_id="grp_x"),
                Command(type=A, target="notepad.exe", start=1.0)]
    return AutomationMap(name="Teste", commands=comandos, groups={"grp_x": grupo}), comandos


def test_com_o_mapa_do_pai_o_editor_oferece_os_grupos_e_os_comandos(gui):
    mapa, comandos = _mapa_com_grupo()
    pai = QWidget()
    pai._automation_map = mapa
    dialogo = _abrir(comandos[0], pai)
    assert dialogo.group_combo.count() == 2 and dialogo.group_combo.currentData() == "grp_x"
    assert dialogo.condition_command.count() == 1 + len(comandos)


def test_com_o_mapa_do_pai_o_perfil_de_atraso_do_grupo_preenche_o_atraso(gui):
    mapa, comandos = _mapa_com_grupo()
    pai = QWidget()
    pai._automation_map = mapa
    assert _abrir(comandos[0], pai).result_command().delay == pytest.approx(0.25)


def test_caracterizacao_o_perfil_do_grupo_sobrescreve_o_atraso_gravado(gui):
    # CARACTERIZAÇÃO (desenho atual, não decisão): com o mapa do pai, o perfil de atraso do grupo substitui o atraso que o
    # comando já tinha, sem aviso. O atraso é só uma sugestão (não muda o início real), por isso não foi tratado como
    # defeito no Ponto 2. Se o Ponto 3 mudar a regra, este teste muda junto.
    mapa, comandos = _mapa_com_grupo()
    comandos[0].delay = 0.9
    pai = QWidget()
    pai._automation_map = mapa
    assert _abrir(comandos[0], pai).result_command().delay == pytest.approx(0.25)


# --------------------------------------------------------------------- 6. miniatura da condição "esperar por imagem"
def _rotulo_sem_imagem(dialogo) -> bool:
    imagem = dialogo.condition_image_preview.pixmap()
    return imagem is None or imagem.isNull()


def test_sem_imagem_a_miniatura_diz_que_nao_ha_imagem(gui):
    dialogo = _abrir()
    dialogo._update_condition_preview("")
    assert dialogo.condition_image_preview.text() == "Nenhuma imagem selecionada" and _rotulo_sem_imagem(dialogo)


def test_imagem_inexistente_mostra_o_motivo_e_o_nome_do_arquivo(gui, tmp_path):
    dialogo = _abrir()
    dialogo._update_condition_preview(str(tmp_path / "sumiu.png"))
    texto = dialogo.condition_image_preview.text()
    assert texto.startswith("Não foi possível abrir a imagem") and "sumiu.png" in texto and _rotulo_sem_imagem(dialogo)


def test_imagem_valida_mostra_a_miniatura(gui, tmp_path):
    dialogo = _abrir()
    dialogo._update_condition_preview(write_png(tmp_path / "botao.png", 40, 30))
    assert dialogo.condition_image_preview.text() == "" and not _rotulo_sem_imagem(dialogo)


def test_escolher_a_imagem_pelo_botao_preenche_o_caminho_e_a_miniatura(gui, monkeypatch, tmp_path):
    imagem = write_png(tmp_path / "botao.png", 40, 30)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (imagem, "")))
    dialogo = _abrir()
    dialogo._browse_condition_image()
    assert dialogo.condition_image_path.text() == imagem and not _rotulo_sem_imagem(dialogo)


def test_condicao_de_imagem_montada_pelo_formulario_chega_ao_comando(gui, tmp_path):
    imagem = write_png(tmp_path / "botao.png", 40, 30)
    dialogo = _abrir()
    _escolher_tipo(dialogo, W)
    dialogo.condition_type.setCurrentIndex(dialogo.condition_type.findData(WaitConditionType.IMAGE))
    dialogo.condition_image_path.setText(imagem)
    dialogo.condition_confidence.setValue(0.9)
    dialogo.condition_timeout.setValue(5.0)
    dialogo.condition_add.click()
    comando = _aceitar(dialogo, gui)
    (condicao,) = comando.conditions
    assert condicao.type == WaitConditionType.IMAGE and condicao.timeout == 5.0
    assert condicao.parameters["image_path"] == imagem and condicao.parameters["confidence"] == pytest.approx(0.9)
    assert comando.validate() == []


def test_condicao_incompleta_e_recusada_com_aviso(gui):
    dialogo = _abrir()
    _escolher_tipo(dialogo, W)
    dialogo.condition_type.setCurrentIndex(dialogo.condition_type.findData(WaitConditionType.IMAGE))
    dialogo.condition_add.click()  # sem escolher imagem
    assert dialogo.condition_list.count() == 0 and gui.calls[-1][:2] == ("warning", "Condição incompleta")


def test_condicao_adicionada_pode_ser_removida(gui):
    dialogo = _abrir()
    _escolher_tipo(dialogo, W)
    dialogo.condition_type.setCurrentIndex(dialogo.condition_type.findData(WaitConditionType.DELAY))
    dialogo.condition_timeout.setValue(0.5)
    dialogo.condition_add.click()
    assert dialogo.condition_list.count() == 1
    dialogo.condition_list.setCurrentRow(0)
    dialogo.condition_remove.click()
    assert dialogo.condition_list.count() == 0 and dialogo._current_conditions() == []
