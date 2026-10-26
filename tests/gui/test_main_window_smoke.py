"""Fumaça da janela principal (MainWindow) com o PySide6 REAL.

Estes testes foram escritos sem poder rodar o Qt (o ambiente de desenvolvimento não o tem): usam só nomes conferidos no
código e passos simples. Se algum falhar na sua máquina, a mensagem mostra o estado real; me envie a saída. Eles NÃO
rodam com o dublê (a janela principal não cabe nele): são pulados.

Isolamento (testsupport/qt_isolation.py): sem registro do Windows, sem hooks globais de teclado/mouse, backend de input
falso e diálogos modais respondidos sem bloquear. A fábrica `abrir_janela` está no conftest.py.

Marcador `isolado`: o Rodar_Testes.bat roda cada teste deste arquivo num PROCESSO PRÓPRIO, com tempo limite. Na rodada de
18/10/2026 o 22º teste travou dentro do Qt e levou a rodada inteira junto; assim, um travamento reprova só o teste que
travou e grava o diagnóstico em logs/travamento_qt.txt (testsupport/diagnostico_qt.py).
"""
import copy

import pytest

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtGui import QCloseEvent  # noqa: E402
from PySide6.QtWidgets import QInputDialog  # noqa: E402

from automationstudio import core  # noqa: E402
from automationstudio.core import (ActionType, AutomationMap, Command, CommandGroup, InputType, State,  # noqa: E402
                                   map_from_json)
from automationstudio.project import ProjectManager  # noqa: E402
from testsupport.gui_helpers import differences, processar_eventos  # noqa: E402
from testsupport.helpers import events_of, join_engine, key  # noqa: E402

pytestmark = [pytest.mark.gui, pytest.mark.isolado]

K, M, S, T, A = InputType.KEY, InputType.MOUSE_MOVE, InputType.MOUSE_SCROLL, InputType.TEXT, InputType.APP_OPEN


def _responder_nome(monkeypatch, texto, confirmou=True):
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: (texto, confirmou)))


def _no_banco(janela) -> dict:
    """O que está GRAVADO no banco (lido por um gerenciador novo), por nome de mapa."""
    leitor = ProjectManager(janela.project_manager.project_dir)
    leitor.load_all()
    return leitor.maps


def _nova_automacao(janela, monkeypatch, nome="Mapa"):
    _responder_nome(monkeypatch, nome)
    janela._new_map()
    assert janela._current_map is not None and janela._current_map.name == nome, janela._current_map
    return janela._current_map


# ------------------------------------------------------------------------------------------------ abrir e fechar
def test_a_janela_abre_na_escolha_de_automacao(abrir_janela):
    janela = abrir_janela()
    # O título mostra o ESTADO, não a versão: `__init__` põe "Automation Studio — AS <versão>", mas `_update_status_label`
    # o troca por "Automation Studio — ● PARADO" ainda na construção (já era assim na 25.3). Na 25.5 este teste esperava
    # a versão no título e foi o `F` da rodada de 18/10/2026.
    assert janela.windowTitle() == f"Automation Studio — {core._STATE_LABELS[State.IDLE]}", janela.windowTitle()
    assert janela.pages.currentIndex() == 1, "a primeira tela é a escolha da automação"
    assert janela.map_list.count() == 0 and "Nenhuma automação salva" in janela.map_list_info.text()
    assert janela._current_map is None and janela.state.state == State.IDLE


def test_primeiro_uso_prepara_a_demonstracao_sem_executar_nada(abrir_janela):
    janela = abrir_janela(pular_tutorial=False)
    assert janela._tutorial_first_run is True
    assert list(janela.project_manager.maps) == ["Exemplo — Primeira automação"], list(janela.project_manager.maps)
    assert janela._current_map is not None and janela._current_map.name == "Exemplo — Primeira automação"
    assert janela.engine._backend.events == [], "a demonstração não pode enviar entradas sozinha"
    assert janela.state.state == State.IDLE


def test_fechar_a_janela_para_o_motor_e_o_relogio_da_interface(abrir_janela, monkeypatch):
    janela = abrir_janela()
    paradas = []
    monkeypatch.setattr(janela.engine, "emergency_stop", lambda: paradas.append(True))
    assert janela._ui_refresh_timer.isActive()
    janela.closeEvent(QCloseEvent())
    assert paradas == [True], "fechar a janela precisa parar a execução (teclas presas)"
    assert not janela._ui_refresh_timer.isActive()


# ------------------------------------------------------------------------------------------ criar e excluir mapas
def test_criar_automacao_pelo_botao_grava_no_banco_e_abre_o_editor(abrir_janela, monkeypatch):
    janela = abrir_janela()
    _responder_nome(monkeypatch, "Minha automação")
    janela.btn_create_map.click()
    assert list(janela.project_manager.maps) == ["Minha automação"]
    assert janela._current_map is not None and janela._current_map.name == "Minha automação"
    assert janela.pages.currentIndex() == 2, "criar uma automação abre o editor"
    assert "Minha automação" in _no_banco(janela), "o mapa novo precisa estar gravado no banco"


def test_nome_repetido_avisa_e_nao_duplica(abrir_janela, monkeypatch, gui):
    janela = abrir_janela()
    _nova_automacao(janela, monkeypatch, "Repetida")
    antes = len(gui.calls)
    janela._new_map()
    avisos = [c[:2] for c in gui.calls[antes:] if c[0] == "warning"]
    assert avisos == [("warning", "Nome duplicado")], gui.calls[antes:]
    assert list(janela.project_manager.maps) == ["Repetida"]


def test_nome_vazio_ou_cancelar_nao_cria_nada(abrir_janela, monkeypatch):
    janela = abrir_janela()
    _responder_nome(monkeypatch, "   ")
    janela._new_map()
    _responder_nome(monkeypatch, "Nome", confirmou=False)
    janela._new_map()
    assert janela.project_manager.maps == {} and _no_banco(janela) == {}


def test_excluir_automacao_pede_confirmacao_e_remove_do_banco(abrir_janela, monkeypatch, gui):
    janela = abrir_janela()
    _nova_automacao(janela, monkeypatch, "Descartável")
    janela._delete_current_map()
    assert [c[:2] for c in gui.calls if c[0] == "question"] == [("question", "Excluir mapa")], gui.calls
    assert janela.project_manager.maps == {} and _no_banco(janela) == {}
    assert janela._current_map is None and janela.pages.currentIndex() == 1


# ------------------------------------------------------------------------- painel lateral: adicionar e editar
def test_adicionar_comando_pelo_painel_lateral_grava_e_da_para_desfazer_e_refazer(abrir_janela, monkeypatch):
    janela = abrir_janela()
    mapa = _nova_automacao(janela, monkeypatch)
    janela._open_command_sidebar()  # sem comando: modo "adicionar"
    painel = janela._command_sidebar_dialog
    assert painel is not None and janela._command_sidebar_mode == "add"
    painel.target_combo.setCurrentText("F")
    painel.duration.setValue(0.2)
    painel._accept()  # é o que o botão "Adicionar" do rodapé faz
    assert [(c.type, c.target, c.duration) for c in mapa.commands] == [(K, "F", 0.2)], mapa.commands
    # Defeito 2.07 (G4): antes, o texto-guia "Nenhum aplicativo selecionado" era gravado como processo a esperar.
    assert mapa.commands[0].wait_process == "", mapa.commands[0].wait_process
    assert [c.target for c in _no_banco(janela)["Mapa"].commands] == ["F"], "o comando precisa estar gravado no banco"
    assert janela.act_undo.isEnabled() and not janela.act_redo.isEnabled()
    janela._close_command_sidebar(immediate=True)
    assert janela._command_sidebar_dialog is None

    janela._undo_map()
    assert mapa.commands == [] and janela.act_redo.isEnabled()
    janela._redo_map()
    assert [c.target for c in mapa.commands] == ["F"]


FORMAS = [
    ("tecla-manter-pressionada", Command(type=K, target="A", action=ActionType.PRESS, start=1.0, duration=0.1)),
    ("tecla-fora-da-lista", Command(type=K, target=";", start=0.5, duration=0.1)),
    ("tecla-desativada", Command(type=K, target="E", start=0.5, duration=0.1, enabled=False)),
    ("tecla-de-um-grupo", Command(type=K, target="D", start=0.5, duration=0.1, group="D", group_id="grp_d")),
    ("movimento", Command(type=M, x=100, y=200, start=0.3)),
    ("movimento-mesclado", Command(type=M, x=961, y=540, start=0.704, duration=0.497, merged_move=True,
                                   mouse_path=[{"t": 0.0, "x": 961, "y": 540}, {"t": 0.5, "x": 960, "y": 536},
                                               {"t": 1.0, "x": 959, "y": 540}])),
    ("rolagem", Command(type=S, target="down", scroll_dy=-3, start=1.0)),
    ("texto", Command(type=T, text="olá, mundo", start=0.1)),
    ("abrir-aplicativo-fora-da-lista", Command(type=A, target="C:\\Jogos\\jogo.exe", wait_process="jogo.exe")),
]


@pytest.mark.parametrize("nome, comando", FORMAS, ids=[n for n, _ in FORMAS])
def test_editar_pelo_painel_lateral_sem_mexer_nao_altera_o_comando(abrir_janela, monkeypatch, nome, comando):
    # O defeito 2.07 de ponta a ponta: janela -> painel lateral -> "Salvar" -> banco. O painel lateral abre o editor SEM o
    # mapa (grupos desconhecidos), que é o caso em que o grupo e as demais características se perdiam.
    janela = abrir_janela()
    mapa = _nova_automacao(janela, monkeypatch)
    mapa.groups["grp_d"] = CommandGroup(id="grp_d", name="D")
    mapa.add_command(copy.deepcopy(comando))
    janela.project_manager.save_map(mapa)
    original = copy.deepcopy(mapa.commands[0]).to_dict()

    janela._open_command_sidebar(mapa.commands[0], 0)
    painel = janela._command_sidebar_dialog
    assert painel is not None and janela._command_sidebar_mode == "edit"
    painel._accept()  # "Salvar"
    janela._close_command_sidebar(immediate=True)

    ignorar = ("duration",) if comando.type == T else ()  # o texto recalcula a duração com o intervalo configurado
    em_memoria = differences(original, mapa.commands[0], ignore=ignorar)
    assert em_memoria == {}, em_memoria
    gravado = _no_banco(janela)["Mapa"].commands[0]
    no_banco = differences(original, gravado, ignore=ignorar)
    assert no_banco == {}, no_banco


# ---------------------------------------------------------------------------- configurações, validar e executar
def test_configuracoes_abrem_no_painel_lateral(abrir_janela, monkeypatch):
    janela = abrir_janela()
    _nova_automacao(janela, monkeypatch)
    janela._open_settings()
    assert janela._command_sidebar_mode == "settings" and janela._command_sidebar_dialog is not None
    assert janela.command_sidebar_title.text() == "Configurações"
    janela._close_command_sidebar(immediate=True)
    assert janela._command_sidebar_dialog is None


def test_validar_e_executar_uma_automacao_vazia_avisam_sem_enviar_nada(abrir_janela, monkeypatch, gui):
    janela = abrir_janela()
    _nova_automacao(janela, monkeypatch)
    antes = len(gui.calls)
    janela._validate_current_map()
    janela._run_current_map()
    avisos = [c[:2] for c in gui.calls[antes:]]
    assert ("information", "Validação da automação") in avisos, gui.calls[antes:]
    assert ("information", "Automação vazia") in avisos, gui.calls[antes:]
    assert janela.engine._backend.events == []


def test_executar_pela_janela_envia_as_entradas_ao_backend(abrir_janela, monkeypatch):
    janela = abrir_janela()
    mapa = _nova_automacao(janela, monkeypatch)
    mapa.repeat_count = 1  # o mapa criado pelo botão repete para sempre
    mapa.add_command(key("F", 0.0, 0.05))
    janela._on_map_edited()
    janela._run_current_map()
    join_engine(janela.engine, timeout=10.0)
    assert [(acao, alvo) for _t, acao, alvo in events_of(janela.engine._backend)] == [("key_down", "F"), ("key_up", "F")]
    assert janela.state.state == State.IDLE


# ------------------------------------------------------------------------------------------------- mapas reais
def _gravar_mapas_reais(pasta, legacy_maps) -> list[str]:
    gerente = ProjectManager(pasta)
    for texto in legacy_maps.values():
        gerente.save_map(map_from_json(texto))
    return sorted(gerente.maps)


def test_a_janela_lista_e_abre_os_tres_mapas_reais(abrir_janela, legacy_maps, tmp_path):
    pasta = tmp_path / "dados_reais"
    nomes = _gravar_mapas_reais(pasta, legacy_maps)
    assert len(nomes) == 3
    janela = abrir_janela(pasta=pasta)
    assert sorted(janela.project_manager.maps) == nomes
    assert janela.map_list.count() == 3
    for nome in nomes:
        janela._select_map_by_name(nome)
        assert janela._current_map is not None and janela._current_map.name == nome
        assert janela.command_table.table.rowCount() == len(janela._current_map.commands), nome
        assert janela.pages.currentIndex() == 2


def test_a_timeline_abre_com_os_mapas_reais(abrir_janela, legacy_maps, tmp_path):
    pasta = tmp_path / "dados_reais"
    nomes = _gravar_mapas_reais(pasta, legacy_maps)
    janela = abrir_janela(pasta=pasta)
    janela.show()  # a timeline calcula o enquadramento pelo tamanho real da área
    processar_eventos(50)  # por tempo e com marcos no diagnóstico (ver gui_helpers.processar_eventos)
    assert janela.isVisible()
    for nome in nomes:
        janela._select_map_by_name(nome)
        janela._open_timeline()
        assert janela.pages.currentIndex() == 3, nome
        janela.pages.setCurrentIndex(2)
