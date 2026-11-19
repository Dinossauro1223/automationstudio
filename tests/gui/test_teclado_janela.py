"""A edição pelo teclado (25.9, T3a) na janela principal, com o PySide6 REAL: o filtro de teclas da tabela, a marca da linha, o editor de texto em
linha, a janela de escolher o programa, a dica e o valor na barra de status, o bip, a suspensão dos atalhos de automação e o Ctrl+Z.

Estes testes foram escritos sem poder rodar o Qt (o ambiente de desenvolvimento não o tem) e são os PRIMEIROS do repositório a depender de a janela
ficar ativa, de o foco mudar de verdade (`QApplication.focusChanged`) e do `QtTest`: usam só nomes conferidos no código e passos simples. Se algum
falhar na sua máquina ou no Actions, a mensagem mostra o estado real (plataforma, janela ativa, widget com o foco, dica e valor da barra): me envie a
saída. NÃO rodam com os dublês (nenhum tem o `QtTest`): cada teste é pulado pela fixture `gui_real`; a falta do `QtTest` com o Qt real é pega em tests/gui/test_teclado_teclas_qt.py.

Como rodam: cada teste abre a janela principal com UM dos três mapas reais (tests/data/legacy_maps.json.gz) gravado numa pasta temporária ("Click
genshin" para tecla, botão do mouse, tempo e espera; "Exemplo" para texto e programa; "Flins combo", com 933 comandos, para rolagem). As teclas são
enviadas com `QTest.keyClick` à tabela (ou ao editor de texto, ou à janela do programa): o mesmo caminho do filtro de eventos de verdade, mas SEM o
sistema operacional no meio. O relógio do teclado e o do gerenciador de atalhos são virtuais (`FakeClock`): ninguém espera tempo de verdade, e o
Enter duplo (0,4 s) e a graça de 0,25 s dos atalhos são decididos pelo teste. O `QApplication.beep` é contado, nunca tocado. A única espera real é a
da seta segurada, que deixa o temporizador de 33 ms do próprio teclado girar.

O que SÓ estes testes provam (e nada mais no repositório): que o filtro do teclado roda antes do da tabela e do Esc do aplicativo; que o Enter, o Esc,
as setas, o `'` e o F2 fazem o que a ficha manda na tabela de verdade; que a marca cai sobre a linha e a rolagem volta depois de gravar; que
`focusChanged` descarta a edição quando o foco sai e mostra a dica quando volta; que o desfazer do Ctrl+Z (pelo atalho da janela ou pelo filtro da
tabela) leva a edição em curso junto; que a gravação passa pelo histórico e pelo arquivo (`map_changed` -> `_on_map_edited`).

O que NENHUM teste daqui prova, porque exige o Windows de verdade (está na conferência da rodada, md/ENTREGA_TECLADO_T3A_25_9.md): o som do bip; a
sensação da seta segurada com a repetição de tecla do dono; a aparência da marca e do editor com o tema e a escala de tela; o apóstrofo em layouts
com tecla morta; o teclado numérico e F13 a F24 físicos; o foco ao voltar de outra janela; e que o monitor global de teclas roda ANTES do Qt a ponto de
a suspensão dos atalhos valer.

Marcador `isolado`: cada teste deste arquivo roda num PROCESSO PRÓPRIO, com tempo limite (ver test_main_window_smoke.py).
"""
import pytest

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtCore import QEvent, QItemSelectionModel, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication, QKeyEvent  # noqa: E402
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QDialog, QFrame, QLabel, QLineEdit, QListWidget,  # noqa: E402
                               QSizePolicy)

from automationstudio import teclado_aplicar, teclado_ui  # noqa: E402
from automationstudio.core import InputType, calculate_text_duration, map_from_json  # noqa: E402
from automationstudio.project import ProjectManager  # noqa: E402
from automationstudio.teclado_edicao import (DICA_NAVEGANDO, DICA_TECLA_DESCONHECIDA, DICA_TEXTO_VAZIO, TEMPO_MINIMO, Estado,  # noqa: E402
                                             dica_do_estado, formatar_segundos, linha_info_de, valor_apos)
from automationstudio.teclado_ligacao import MENSAGEM_DO_ERRO, SEGUNDOS_DA_MENSAGEM  # noqa: E402
from automationstudio.teclado_ui import FRASE_COLUNA_FIXA  # noqa: E402
from testsupport.fake_clock import FakeClock  # noqa: E402
from testsupport.gui_helpers import differences, processar_eventos  # noqa: E402

pytestmark = [pytest.mark.gui, pytest.mark.isolado]


def _qtest():
    """O módulo `QTest`, importado só na hora de usar: nenhum dos dois dublês o tem, e o executor mínimo trata o `importorskip` de um módulo como ERRO de
    coleta (o pytest o trata como pulo). Com os dublês nenhum teste chega a chamá-lo: a fixture `gui_real` o pula antes. Com o Qt REAL um QtTest ausente
    estoura aqui, alto (e em tests/gui/test_teclado_teclas_qt.py), em vez de pular em silêncio."""
    from PySide6.QtTest import QTest
    return QTest

_PASTA = "dados_reais"


# ------------------------------------------------------------------------------------------------ montagem
def _pasta(tmp_path):
    return tmp_path / _PASTA


def _nome_real(legacy_maps, prefixo: str) -> str:
    return next(nome for nome in legacy_maps if nome.startswith(prefixo))   # o "Exemplo — Primeira automação" tem travessão: procura pelo começo


def _abrir(abrir_janela, legacy_maps, tmp_path, prefixo: str):
    """A janela principal, mostrada, com SÓ o mapa real que começa por `prefixo` na pasta de dados, aberto no editor."""
    nome = _nome_real(legacy_maps, prefixo)
    ProjectManager(_pasta(tmp_path)).save_map(map_from_json(legacy_maps[nome]))
    janela = abrir_janela(pasta=_pasta(tmp_path))
    janela.show()
    processar_eventos(60)
    janela._select_map_by_name(nome)
    processar_eventos(120)
    assert janela._current_map is not None and janela._current_map.name == nome, "o mapa real não abriu no editor"
    assert janela.command_table._automation_map is janela._current_map, "a tabela não mostra o mapa aberto"
    return janela


def _contar_bips(monkeypatch) -> list:
    bips: list[int] = []
    monkeypatch.setattr(QApplication, "beep", staticmethod(lambda: bips.append(1)))   # nunca toca de verdade
    return bips


def _preparar(abrir_janela, legacy_maps, tmp_path, monkeypatch, prefixo: str):
    """A janela com os relógios virtuais ligados (o do teclado e o do gerenciador de atalhos, o MESMO) e o bip contado. Devolve (janela, relogio, bips)."""
    bips = _contar_bips(monkeypatch)
    janela = _abrir(abrir_janela, legacy_maps, tmp_path, prefixo)
    relogio = FakeClock(1000.0)
    janela.teclado._ligacao._relogio = relogio
    janela.hotkey_manager._relogio = relogio
    return janela, relogio, bips


# ------------------------------------------------------------------------------------------------ o que o teste lê da janela
def _visivel(widget) -> bool:
    """`isVisible()` de um widget que pode já ter sido destruído (o `deleteLater` só roda no laço de eventos): destruído ou ausente = não visível."""
    if widget is None:
        return False
    try:
        return bool(widget.isVisible())
    except RuntimeError:
        return False


def _rotulo(janela, nome: str):
    rotulo = janela.findChild(QLabel, nome)
    assert rotulo is not None, f"a barra de status não tem o rótulo {nome}"
    return rotulo


def _dica(janela) -> str:
    return _rotulo(janela, "dicaDoTeclado").text()


def _valor(janela) -> str:
    """O valor em edição da barra de status; vazio se o rótulo está escondido (o que o teclado faz ao terminar)."""
    rotulo = _rotulo(janela, "valorDoTeclado")
    return "" if rotulo.isHidden() else rotulo.text()


def _mensagem(janela) -> str:
    return janela.status_bar.currentMessage()


def _moldura(janela):
    return janela.command_table.table.viewport().findChild(QFrame, "marcaDeEdicao")


def _editor_de_texto(janela):
    """O editor de texto em linha, se está aberto (visível); None se não."""
    for editor in janela.command_table.table.viewport().findChildren(QLineEdit, "editorDeTextoEmLinha"):
        if _visivel(editor):
            return editor
    return None


def _seletor(janela):
    return janela.findChild(QDialog, "seletorDePrograma")


def _estado(janela) -> str:
    """Uma linha com o que o teclado mostra agora: vai na mensagem das conferências que falham."""
    try:
        return (f"editando={janela.teclado.editando()} dica={_dica(janela)!r} valor={_valor(janela)!r} mensagem={_mensagem(janela)!r} "
                f"página={janela.pages.currentIndex()}")
    except AssertionError as erro:
        return f"(sem rótulos do teclado: {erro})"


def _diagnostico_de_foco(janela) -> str:
    return (f"plataforma={QGuiApplication.platformName()!r} janela_ativa={janela.isActiveWindow()} "
            f"janela_ativa_do_app={QApplication.activeWindow()!r} widget_com_foco={QApplication.focusWidget()!r}")


def _esperar(condicao, limite: float = 5.0) -> bool:
    import time
    fim = time.monotonic() + limite
    while time.monotonic() < fim:
        processar_eventos(20)
        if condicao():
            return True
    return False


# ------------------------------------------------------------------------------------------------ o que o teste faz na janela
def _focar(janela, linha: int, coluna: int = 0):
    """Seleciona a linha e dá o foco à tabela com a janela ATIVA, como o usuário que clica nela: `focusChanged` dispara de verdade."""
    tabela = janela.command_table.table
    janela.show()
    janela.raise_()
    janela.activateWindow()
    processar_eventos(80)
    tabela.clearFocus()
    tabela.selectRow(linha)
    tabela.setCurrentCell(linha, coluna)
    tabela.setFocus(Qt.OtherFocusReason)
    processar_eventos(40)
    assert tabela.currentRow() == linha, f"a linha {linha} não ficou atual (atual={tabela.currentRow()})"
    assert janela.teclado.quantas_linhas_selecionadas() == 1, f"a linha {linha} não é a única selecionada"
    assert tabela.hasFocus(), "a tabela não ficou com o foco: " + _diagnostico_de_foco(janela)
    return tabela


def _tirar_o_foco(janela):
    """Leva o foco para um campo de texto QUALQUER de fora da tabela (o usuário que clica noutro lugar da janela)."""
    outro = QLineEdit(janela)
    outro.setObjectName("focoDeTeste")
    outro.move(0, 0)
    outro.show()
    outro.setFocus(Qt.OtherFocusReason)
    processar_eventos(40)
    assert outro.hasFocus(), "o campo de teste não ficou com o foco: " + _diagnostico_de_foco(janela)
    return outro


def _apertar(janela, tecla, modificadores=Qt.NoModifier, alvo=None):
    """Aperta e solta `tecla` (um `Qt.Key_*` ou um caractere) em `alvo` (a tabela, se não vier). O QtTest manda o modificador antes da tecla."""
    _qtest().keyClick(alvo if alvo is not None else janela.command_table.table, tecla, modificadores)
    processar_eventos(0)


def _linha_de(mapa, tipo, a_partir_de: int = 0) -> int:
    return next(i for i in range(a_partir_de, len(mapa.commands)) if linha_info_de(mapa, i).tipo == tipo)


def _gravado(tmp_path, nome: str):
    """O mapa como está no ARQUIVO, lido por um gerenciador novo."""
    gerente = ProjectManager(_pasta(tmp_path))
    gerente.load_all()
    return gerente.maps[nome]


# ================================================================================================ a ligação
def test_a_janela_tem_o_teclado_ligado_e_os_dois_rotulos_na_barra_de_status(sem_erro_do_teclado, abrir_janela, legacy_maps, tmp_path, monkeypatch):
    janela, _relogio, _bips = _preparar(abrir_janela, legacy_maps, tmp_path, monkeypatch, "Click")
    assert isinstance(janela.teclado, teclado_ui.TecladoDaJanela)
    assert not janela.teclado.editando()
    assert _rotulo(janela, "valorDoTeclado").isHidden(), "o valor só aparece enquanto há um valor em edição"
    assert _rotulo(janela, "dicaDoTeclado").sizePolicy().horizontalPolicy() == QSizePolicy.Ignored, "uma dica comprida não pode alargar a janela"


def test_ao_ganhar_o_foco_a_tabela_mostra_a_dica_da_navegacao_e_ao_perder_a_dica_some(sem_erro_do_teclado, abrir_janela, legacy_maps, tmp_path, monkeypatch):
    janela, _relogio, _bips = _preparar(abrir_janela, legacy_maps, tmp_path, monkeypatch, "Click")
    _focar(janela, 0)
    assert _dica(janela) == DICA_NAVEGANDO, _estado(janela)
    _tirar_o_foco(janela)
    assert _dica(janela) == "", "o foco saiu da tabela: a dica some. " + _estado(janela)
    janela.command_table.table.setFocus(Qt.OtherFocusReason)
    processar_eventos(40)
    assert _dica(janela) == DICA_NAVEGANDO, "o foco voltou para a tabela: a dica volta. " + _estado(janela)


# ================================================================================================ tecla
def test_enter_na_linha_de_tecla_abre_a_captura_com_a_marca_a_dica_e_os_atalhos_calados(sem_erro_do_teclado, abrir_janela, legacy_maps, tmp_path, monkeypatch):
    janela, _relogio, bips = _preparar(abrir_janela, legacy_maps, tmp_path, monkeypatch, "Click")
    linha = linha_info_de(janela._current_map, 0)
    assert linha.tipo == InputType.KEY and linha.alvo == "F"
    tabela = _focar(janela, 0)
    assert not janela.hotkey_manager.suspenso
    _apertar(janela, Qt.Key_Return)
    assert janela.teclado.editando(), _estado(janela)
    assert _dica(janela) == dica_do_estado(Estado.TECLA, linha), _estado(janela)
    moldura = _moldura(janela)
    assert _visivel(moldura), "a marca da linha em edição não apareceu"
    assert moldura.geometry().top() == tabela.rowViewportPosition(0) and moldura.geometry().height() == tabela.rowHeight(0)
    assert janela.hotkey_manager.suspenso, "enquanto a tecla é capturada, as teclas de ativação das automações calam"
    assert _valor(janela) == "" and not bips
    assert janela._current_map.commands[0].target == "F", "abrir a captura não grava nada"


def test_apertar_a_mesma_tecla_duas_vezes_grava_com_um_bip_a_mensagem_o_historico_e_o_arquivo(sem_erro_do_teclado, abrir_janela, legacy_maps, tmp_path, monkeypatch):
    janela, _relogio, bips = _preparar(abrir_janela, legacy_maps, tmp_path, monkeypatch, "Click")
    nome = janela._current_map.name
    antes = [comando.to_dict() for comando in janela._current_map.commands]
    _focar(janela, 0)
    _apertar(janela, Qt.Key_Return)
    _apertar(janela, Qt.Key_G)
    assert _valor(janela) == "Tecla proposta: G", _estado(janela)
    assert len(bips) == 1, "a proposta apita uma vez"
    assert janela.teclado.editando() and janela._current_map.commands[0].target == "F", "uma tecla só é proposta: nada gravado ainda"
    _apertar(janela, Qt.Key_G)
    assert not janela.teclado.editando(), _estado(janela)
    assert len(bips) == 1, "a confirmação não apita"
    mapa = janela._current_map
    assert differences(antes[0], mapa.commands[0]) == {"target": ("F", "G")}, "só a tecla do comando mudou"
    mudaram = {i: differences(antes[i], comando) for i, comando in enumerate(mapa.commands) if i and differences(antes[i], comando)}
    assert not mudaram, f"os outros comandos não mudaram: {mudaram}"
    mensagem = _mensagem(janela)
    assert mensagem.startswith("Tecla trocada para G.") and mensagem.endswith("Ctrl+Z desfaz."), mensagem
    assert _dica(janela) == DICA_NAVEGANDO and _valor(janela) == ""
    assert not _visivel(_moldura(janela)), "a marca some ao gravar"
    assert janela.act_undo.text() == "↶ Desfazer: Editar tecla"
    assert _gravado(tmp_path, nome).commands[0].target == "G", "a tecla nova chegou ao arquivo"


def test_desfazer_e_refazer_pelos_comandos_da_janela_levam_a_tecla_e_trazem_de_volta(sem_erro_do_teclado, abrir_janela, legacy_maps, tmp_path, monkeypatch):
    janela, _relogio, _bips = _preparar(abrir_janela, legacy_maps, tmp_path, monkeypatch, "Click")
    _focar(janela, 0)
    _apertar(janela, Qt.Key_Return)
    _apertar(janela, Qt.Key_G)
    _apertar(janela, Qt.Key_G)
    assert janela._current_map.commands[0].target == "G"
    janela.act_undo.trigger()
    processar_eventos(40)
    assert janela._current_map.commands[0].target == "F", "o Ctrl+Z desfaz a edição pelo teclado"
    assert janela.act_redo.text() == "↷ Refazer: Editar tecla"
    janela.act_redo.trigger()
    processar_eventos(40)
    assert janela._current_map.commands[0].target == "G"


def test_esc_cancela_a_captura_sem_mudar_de_pagina_e_o_segundo_esc_volta_uma_pagina(sem_erro_do_teclado, abrir_janela, legacy_maps, tmp_path, monkeypatch):
    janela, relogio, _bips = _preparar(abrir_janela, legacy_maps, tmp_path, monkeypatch, "Click")
    _focar(janela, 0)
    assert janela.pages.currentIndex() == 2
    _apertar(janela, Qt.Key_Return)
    assert janela.teclado.editando()
    _apertar(janela, Qt.Key_Escape)
    assert not janela.teclado.editando(), _estado(janela)
    assert janela.pages.currentIndex() == 2, "o Esc era da edição: o Esc do aplicativo cede"
    assert janela._current_map.commands[0].target == "F"
    assert _dica(janela) == DICA_NAVEGANDO and not _visivel(_moldura(janela))
    relogio.advance(1.0)
    assert not janela.hotkey_manager.suspenso, "cancelar devolve os atalhos de automação (depois da graça)"
    _apertar(janela, Qt.Key_Escape)
    assert janela.pages.currentIndex() != 2, "sem edição, o Esc volta a ser o do aplicativo"


def test_tecla_que_o_studio_nao_conhece_diz_que_nao_pode_ser_usada_e_a_captura_continua(sem_erro_do_teclado, abrir_janela, legacy_maps, tmp_path, monkeypatch):
    janela, _relogio, bips = _preparar(abrir_janela, legacy_maps, tmp_path, monkeypatch, "Click")
    _focar(janela, 0)
    _apertar(janela, Qt.Key_Return)
    _apertar(janela, Qt.Key_Semicolon)
    assert _dica(janela) == DICA_TECLA_DESCONHECIDA, _estado(janela)
    assert janela.teclado.editando() and not bips
    assert janela._current_map.commands[0].target == "F"


def test_na_captura_a_tecla_de_ativacao_igual_nao_dispara_e_a_de_controle_continua_valendo(sem_erro_do_teclado, abrir_janela, legacy_maps, tmp_path, monkeypatch):
    janela, relogio, _bips = _preparar(abrir_janela, legacy_maps, tmp_path, monkeypatch, "Click")
    gerente = janela.hotkey_manager
    ativacoes, controles = [], []
    gerente.register("G", lambda: ativacoes.append("G"), suspensivel=True)   # uma "automação" ativada pela mesma tecla que se vai gravar
    gerente.register("F7", lambda: controles.append("F7"))                   # uma tecla de controle: não é suspensível
    _focar(janela, 0)
    _apertar(janela, Qt.Key_Return)
    assert gerente.suspenso
    gerente._on_key("G", True)
    gerente._on_key("G", False)
    gerente._on_key("F7", True)
    gerente._on_key("F7", False)
    assert ativacoes == [] and controles == ["F7"], "calada a de automação, de pé a de controle"
    _apertar(janela, Qt.Key_G)
    _apertar(janela, Qt.Key_G)
    assert not janela.teclado.editando() and janela._current_map.commands[0].target == "G"
    assert gerente.suspenso, "a graça: o monitor global pode ver o segundo G depois da janela"
    gerente._on_key("G", True)
    gerente._on_key("G", False)
    assert ativacoes == []
    relogio.advance(0.3)
    assert not gerente.suspenso
    gerente._on_key("G", True)
    gerente._on_key("G", False)
    assert ativacoes == ["G"], "passada a graça, a automação volta a disparar"


# ================================================================================================ texto
def test_o_texto_se_edita_no_editor_em_linha_e_enter_grava_com_a_duracao_nova(sem_erro_do_teclado, abrir_janela, legacy_maps, tmp_path, monkeypatch):
    janela, _relogio, _bips = _preparar(abrir_janela, legacy_maps, tmp_path, monkeypatch, "Exemplo")
    nome = janela._current_map.name
    original = janela._current_map.commands[1].text
    assert janela._current_map.commands[1].type == InputType.TEXT and original
    tabela = _focar(janela, 1)
    _apertar(janela, Qt.Key_Return)
    editor = _editor_de_texto(janela)
    assert editor is not None, "o editor de texto em linha não abriu. " + _estado(janela)
    assert editor.text() == original and editor.selectedText() == original, "abre com o texto de agora, todo selecionado"
    assert _dica(janela) == dica_do_estado(Estado.TEXTO), _estado(janela)
    assert editor.geometry().top() == tabela.rowViewportPosition(1)
    assert editor.hasFocus(), "o editor não ficou com o foco: " + _diagnostico_de_foco(janela)
    assert _visivel(_moldura(janela))
    _qtest().keyClicks(editor, "abc")
    assert editor.text() == "abc", "digitar é do editor: o teclado não consome as letras"
    assert janela.teclado.editando()
    _apertar(janela, Qt.Key_Return, alvo=editor)
    comando = janela._current_map.commands[1]
    assert comando.text == "abc" and comando.duration == pytest.approx(calculate_text_duration("abc"))
    assert not janela.teclado.editando() and _editor_de_texto(janela) is None, _estado(janela)
    mensagem = _mensagem(janela)
    assert mensagem.startswith("Texto trocado.") and mensagem.endswith("Ctrl+Z desfaz."), mensagem
    assert janela.act_undo.text() == "↶ Desfazer: Editar texto"
    assert tabela.hasFocus(), "o foco volta para a tabela: " + _diagnostico_de_foco(janela)
    assert _gravado(tmp_path, nome).commands[1].text == "abc"


def test_esc_no_editor_de_texto_cancela_sem_mudar_o_texto_nem_a_pagina(sem_erro_do_teclado, abrir_janela, legacy_maps, tmp_path, monkeypatch):
    janela, _relogio, _bips = _preparar(abrir_janela, legacy_maps, tmp_path, monkeypatch, "Exemplo")
    original = janela._current_map.commands[1].text
    _focar(janela, 1)
    _apertar(janela, Qt.Key_Return)
    editor = _editor_de_texto(janela)
    assert editor is not None
    _qtest().keyClicks(editor, "xyz")
    _apertar(janela, Qt.Key_Escape, alvo=editor)
    assert not janela.teclado.editando() and _editor_de_texto(janela) is None, _estado(janela)
    assert janela._current_map.commands[1].text == original
    assert janela.pages.currentIndex() == 2, "o Esc era da edição"
    assert _dica(janela) == DICA_NAVEGANDO and not _visivel(_moldura(janela))


def test_texto_vazio_nao_grava_e_a_edicao_continua_com_a_dica(sem_erro_do_teclado, abrir_janela, legacy_maps, tmp_path, monkeypatch):
    janela, _relogio, _bips = _preparar(abrir_janela, legacy_maps, tmp_path, monkeypatch, "Exemplo")
    original = janela._current_map.commands[1].text
    _focar(janela, 1)
    _apertar(janela, Qt.Key_Return)
    editor = _editor_de_texto(janela)
    assert editor is not None
    _qtest().keyClick(editor, Qt.Key_Delete)   # o texto de abertura está todo selecionado
    assert editor.text() == ""
    _apertar(janela, Qt.Key_Return, alvo=editor)
    assert janela.teclado.editando() and _dica(janela) == DICA_TEXTO_VAZIO, _estado(janela)
    assert _editor_de_texto(janela) is not None
    assert janela._current_map.commands[1].text == original


def test_enter_duplo_no_texto_explica_por_que_nao_ha_tempo_e_o_enter_lento_fecha_sem_gravar(sem_erro_do_teclado, abrir_janela, legacy_maps, tmp_path, monkeypatch):
    janela, relogio, _bips = _preparar(abrir_janela, legacy_maps, tmp_path, monkeypatch, "Exemplo")
    motivo = linha_info_de(janela._current_map, 1).tempo_motivo
    assert motivo
    _focar(janela, 1)
    rotulo_antes = janela.act_undo.text()
    _apertar(janela, Qt.Key_Return)
    editor = _editor_de_texto(janela)
    assert editor is not None
    _apertar(janela, Qt.Key_Return, alvo=editor)   # o relógio não andou: dentro da janela de 0,4 s
    assert janela.teclado.editando() and _dica(janela) == motivo, "o Enter duplo diz por que o texto não tem tempo apertado. " + _estado(janela)
    assert _editor_de_texto(janela) is not None
    relogio.advance(1.0)
    _apertar(janela, Qt.Key_Return, alvo=editor)   # devagar, com o texto igual: só fecha
    assert not janela.teclado.editando(), _estado(janela)
    assert janela.act_undo.text() == rotulo_antes, "texto igual: nenhum passo novo no histórico"
    assert _mensagem(janela) == ""


# ================================================================================================ programa
def test_o_programa_abre_a_janela_sem_bloquear_e_enter_troca_o_programa_e_o_processo_esperado(sem_erro_do_teclado, abrir_janela, legacy_maps, tmp_path, monkeypatch):
    janela, _relogio, _bips = _preparar(abrir_janela, legacy_maps, tmp_path, monkeypatch, "Exemplo")
    nome = janela._current_map.name
    comando = janela._current_map.commands[0]
    assert comando.type == InputType.APP_OPEN and comando.target == "notepad.exe" and comando.wait_process == "notepad.exe"
    _focar(janela, 0)
    _apertar(janela, Qt.Key_Return)
    dialogo = _seletor(janela)
    assert dialogo is not None and _visivel(dialogo), "a janela do programa não abriu. " + _estado(janela)
    assert janela.teclado.editando(), "a edição sobrevive a o foco ir para a janela do programa. " + _estado(janela)
    assert _dica(janela) == dica_do_estado(Estado.APLICATIVO), _estado(janela)
    lista = dialogo.findChild(QListWidget, "listaDeProgramas")
    assert lista is not None and lista.currentItem().data(Qt.UserRole) == "notepad.exe", "abre com o programa de agora escolhido"
    posicao = next(i for i in range(lista.count()) if lista.item(i).data(Qt.UserRole) == "msedge.exe")
    lista.setCurrentRow(posicao)
    _qtest().keyClick(lista, Qt.Key_Return)
    processar_eventos(40)
    assert not _visivel(dialogo), "Enter confirma e fecha a janela do programa"
    assert not janela.teclado.editando(), _estado(janela)
    comando = janela._current_map.commands[0]
    assert comando.target == "msedge.exe" and comando.wait_process == "msedge.exe", "o processo esperado acompanhou o programa"
    mensagem = _mensagem(janela)
    assert mensagem.startswith("Programa trocado para msedge.exe.") and mensagem.endswith("Ctrl+Z desfaz."), mensagem
    assert janela.act_undo.text() == "↶ Desfazer: Editar programa"
    assert _gravado(tmp_path, nome).commands[0].target == "msedge.exe"


def test_esc_na_janela_do_programa_cancela_sem_gravar_nem_mudar_de_pagina(sem_erro_do_teclado, abrir_janela, legacy_maps, tmp_path, monkeypatch):
    janela, _relogio, _bips = _preparar(abrir_janela, legacy_maps, tmp_path, monkeypatch, "Exemplo")
    _focar(janela, 0)
    _apertar(janela, Qt.Key_Return)
    dialogo = _seletor(janela)
    assert dialogo is not None and _visivel(dialogo)
    _qtest().keyClick(dialogo, Qt.Key_Escape)
    processar_eventos(40)
    assert not _visivel(dialogo)
    assert not janela.teclado.editando(), _estado(janela)
    assert janela._current_map.commands[0].target == "notepad.exe"
    assert janela.pages.currentIndex() == 2, "o Esc era da janela do programa"
    assert _dica(janela) == DICA_NAVEGANDO


def test_se_o_processo_esperado_era_outro_a_troca_avisa_e_o_deixa_como_estava(sem_erro_do_teclado, abrir_janela, legacy_maps, tmp_path, monkeypatch):
    janela, _relogio, _bips = _preparar(abrir_janela, legacy_maps, tmp_path, monkeypatch, "Exemplo")
    janela._current_map.commands[0].wait_process = "outro.exe"
    _focar(janela, 0)
    _apertar(janela, Qt.Key_Return)
    dialogo = _seletor(janela)
    assert dialogo is not None
    lista = dialogo.findChild(QListWidget, "listaDeProgramas")
    lista.setCurrentRow(next(i for i in range(lista.count()) if lista.item(i).data(Qt.UserRole) == "msedge.exe"))
    _qtest().keyClick(lista, Qt.Key_Return)
    processar_eventos(40)
    comando = janela._current_map.commands[0]
    assert comando.target == "msedge.exe" and comando.wait_process == "outro.exe"
    assert "outro.exe" in _mensagem(janela) and _mensagem(janela).endswith("Ctrl+Z desfaz."), _mensagem(janela)


# ================================================================================================ botão do mouse
def test_o_botao_do_mouse_troca_com_as_setas_e_enter_grava(sem_erro_do_teclado, abrir_janela, legacy_maps, tmp_path, monkeypatch):
    janela, _relogio, _bips = _preparar(abrir_janela, legacy_maps, tmp_path, monkeypatch, "Click")
    nome = janela._current_map.name
    linha = linha_info_de(janela._current_map, 1)
    assert linha.tipo == InputType.MOUSE_BUTTON and linha.alvo == "left"
    _focar(janela, 1)
    _apertar(janela, Qt.Key_Return)
    assert _valor(janela) == "Botão do mouse: esquerdo (left)", _estado(janela)
    assert _dica(janela) == dica_do_estado(Estado.BOTAO, linha)
    _apertar(janela, Qt.Key_Right)
    assert _valor(janela) == "Botão do mouse: direito (right)", _estado(janela)
    assert janela._current_map.commands[1].target == "left", "escolher não grava"
    _apertar(janela, Qt.Key_Return)
    assert not janela.teclado.editando(), _estado(janela)
    assert janela._current_map.commands[1].target == "right"
    mensagem = _mensagem(janela)
    assert mensagem.startswith("Botão do mouse trocado para direito.") and mensagem.endswith("Ctrl+Z desfaz."), mensagem
    assert janela.act_undo.text() == "↶ Desfazer: Editar botão"
    assert _gravado(tmp_path, nome).commands[1].target == "right"


# ================================================================================================ tempo apertado e espera
def test_enter_duplo_abre_o_tempo_apertado_e_uma_seta_muda_so_a_duracao(sem_erro_do_teclado, abrir_janela, legacy_maps, tmp_path, monkeypatch):
    janela, _relogio, _bips = _preparar(abrir_janela, legacy_maps, tmp_path, monkeypatch, "Click")
    nome = janela._current_map.name
    linha = linha_info_de(janela._current_map, 0)
    assert linha.tempo_editavel
    inicios = [comando.start for comando in janela._current_map.commands]
    _focar(janela, 0)
    _apertar(janela, Qt.Key_Return)
    _apertar(janela, Qt.Key_Return)   # o relógio não andou: Enter, Enter
    assert janela.teclado.editando()
    assert _valor(janela) == f"Tempo apertado: {formatar_segundos(linha.tempo)}", _estado(janela)
    assert _dica(janela) == dica_do_estado(Estado.TEMPO, linha)
    assert janela.teclado._relogio.isActive(), "o relógio de 33 ms roda enquanto se ajusta um valor"
    esperado = valor_apos(linha.tempo, -1, 0.0, TEMPO_MINIMO)
    _apertar(janela, Qt.Key_Left)
    assert _valor(janela) == f"Tempo apertado: {formatar_segundos(esperado)}", _estado(janela)
    assert janela._current_map.commands[0].duration == pytest.approx(linha.tempo), "mudar o valor não grava; só o Enter grava"
    _apertar(janela, Qt.Key_Return)
    assert not janela.teclado.editando() and not janela.teclado._relogio.isActive(), _estado(janela)
    mapa = janela._current_map
    assert mapa.commands[0].duration == pytest.approx(esperado)
    assert [comando.start for comando in mapa.commands] == inicios, "o tempo apertado não empurra nenhum comando"
    mensagem = _mensagem(janela)
    assert mensagem == f"Tempo apertado: {formatar_segundos(esperado)}. Ctrl+Z desfaz.", mensagem
    assert janela.act_undo.text() == "↶ Desfazer: Editar tempo apertado"
    assert _gravado(tmp_path, nome).commands[0].duration == pytest.approx(esperado)


def test_a_seta_segurada_anda_pelo_relogio_e_a_repeticao_do_sistema_nao_conta(sem_erro_do_teclado, abrir_janela, legacy_maps, tmp_path, monkeypatch):
    janela, relogio, _bips = _preparar(abrir_janela, legacy_maps, tmp_path, monkeypatch, "Click")
    linha = linha_info_de(janela._current_map, 0)
    tabela = _focar(janela, 0)
    _apertar(janela, Qt.Key_Return)
    _apertar(janela, Qt.Key_Return)
    assert janela.teclado.editando() and janela.teclado._relogio.isActive()
    _qtest().keyPress(tabela, Qt.Key_Right)
    processar_eventos(0)
    assert _valor(janela) == f"Tempo apertado: {formatar_segundos(valor_apos(linha.tempo, 1, 0.0, TEMPO_MINIMO))}", "o toque vale na hora de apertar"
    relogio.advance(2.0)   # dois segundos de seta apertada, sem nenhuma repetição do sistema
    processar_eventos(150)   # ~4 voltas do temporizador de 33 ms
    esperado = valor_apos(linha.tempo, 1, 2.0, TEMPO_MINIMO)
    assert _valor(janela) == f"Tempo apertado: {formatar_segundos(esperado)}", "a rampa anda pelo relógio. " + _estado(janela)
    mostrado = _valor(janela)
    for _ in range(3):   # a repetição de tecla do sistema: ignorada (a contagem é a do primeiro aperto)
        QApplication.sendEvent(tabela, QKeyEvent(QEvent.KeyPress, Qt.Key_Right, Qt.NoModifier, "", True))
    processar_eventos(0)
    assert _valor(janela) == mostrado
    _qtest().keyRelease(tabela, Qt.Key_Right)
    processar_eventos(0)
    _apertar(janela, Qt.Key_Return)
    assert not janela.teclado.editando(), _estado(janela)
    assert janela._current_map.commands[0].duration == pytest.approx(esperado)


def test_o_apostrofo_abre_a_espera_e_o_comando_e_os_seguintes_andam_juntos(sem_erro_do_teclado, abrir_janela, legacy_maps, tmp_path, monkeypatch):
    janela, _relogio, _bips = _preparar(abrir_janela, legacy_maps, tmp_path, monkeypatch, "Click")
    nome = janela._current_map.name
    mapa = janela._current_map
    linha = linha_info_de(mapa, 1)
    espera_antes = mapa.gap_before(1)
    inicios = [comando.start for comando in mapa.commands]
    _focar(janela, 1)
    _apertar(janela, "'")
    assert janela.teclado.editando(), _estado(janela)
    assert _valor(janela).startswith("Espera antes deste comando: "), _estado(janela)
    assert _dica(janela) == dica_do_estado(Estado.ESPERA, linha)
    assert _visivel(_moldura(janela))
    esperado = valor_apos(linha.espera, 1, 0.0, linha.espera_minima)
    _apertar(janela, Qt.Key_Right)
    assert formatar_segundos(esperado) in _valor(janela), _estado(janela)
    _apertar(janela, Qt.Key_Return)
    assert not janela.teclado.editando(), _estado(janela)
    mapa = janela._current_map
    assert mapa.gap_before(1) == pytest.approx(esperado, abs=1e-9)
    mudanca = mapa.gap_before(1) - espera_antes
    assert mapa.commands[0].start == inicios[0], "o comando anterior não se mexe"
    for indice in range(1, len(mapa.commands)):
        assert mapa.commands[indice].start == pytest.approx(inicios[indice] + mudanca, abs=1e-9), f"o comando {indice} andou junto"
    mensagem = _mensagem(janela)
    assert mensagem.startswith("Espera antes do comando: ") and mensagem.endswith("Ctrl+Z desfaz."), mensagem
    assert janela.act_undo.text() == "↶ Desfazer: Editar espera"
    assert _gravado(tmp_path, nome).gap_before(1) == pytest.approx(esperado, abs=1e-9)


def test_nos_ajustes_as_setas_para_cima_e_para_baixo_nao_andam_pela_tabela(sem_erro_do_teclado, abrir_janela, legacy_maps, tmp_path, monkeypatch):
    janela, _relogio, _bips = _preparar(abrir_janela, legacy_maps, tmp_path, monkeypatch, "Click")
    tabela = _focar(janela, 0)
    _apertar(janela, Qt.Key_Return)
    _apertar(janela, Qt.Key_Return)
    _apertar(janela, Qt.Key_Down)
    _apertar(janela, Qt.Key_Up)
    assert janela.teclado.editando() and tabela.currentRow() == 0, "dentro de um ajuste a seta que não é dele é consumida: " + _estado(janela)


# ================================================================================================ o que não é do teclado
def test_na_navegacao_as_setas_seguem_para_a_tabela_e_segurar_a_seta_continua_rolando(sem_erro_do_teclado, abrir_janela, legacy_maps, tmp_path, monkeypatch):
    janela, _relogio, _bips = _preparar(abrir_janela, legacy_maps, tmp_path, monkeypatch, "Click")
    tabela = _focar(janela, 0)
    _apertar(janela, Qt.Key_Down)
    assert tabela.currentRow() == 1 and not janela.teclado.editando()
    _qtest().keyPress(tabela, Qt.Key_Down)   # segurada: o aperto + duas repetições do sistema
    for _ in range(2):
        QApplication.sendEvent(tabela, QKeyEvent(QEvent.KeyPress, Qt.Key_Down, Qt.NoModifier, "", True))
    _qtest().keyRelease(tabela, Qt.Key_Down)
    processar_eventos(0)
    assert tabela.currentRow() == 4, "a repetição de uma tecla que o teclado não usa segue para a tabela"


def test_enter_sem_linha_selecionada_segue_o_caminho_antigo_e_nao_deixa_a_tabela_travada(sem_erro_do_teclado, abrir_janela, legacy_maps, tmp_path, monkeypatch):
    janela, _relogio, _bips = _preparar(abrir_janela, legacy_maps, tmp_path, monkeypatch, "Click")
    tabela = _focar(janela, 1, coluna=1)
    tabela.clearSelection()
    tabela.setCurrentCell(-1, -1)
    processar_eventos(0)
    assert janela.teclado.quantas_linhas_selecionadas() == 0
    _apertar(janela, Qt.Key_Return)
    assert not janela.teclado.editando()
    assert janela.command_table._editing_cell is False, "Enter sem célula atual não pode deixar a tabela 'editando'"


def test_varias_linhas_selecionadas_avisam_e_nao_editam(sem_erro_do_teclado, abrir_janela, legacy_maps, tmp_path, monkeypatch):
    janela, _relogio, _bips = _preparar(abrir_janela, legacy_maps, tmp_path, monkeypatch, "Click")
    tabela = _focar(janela, 0)
    modelo, selecao = tabela.model(), tabela.selectionModel()
    tabela.clearSelection()
    for linha in (0, 2):
        selecao.select(modelo.index(linha, 0), QItemSelectionModel.Select | QItemSelectionModel.Rows)
    processar_eventos(0)
    assert janela.teclado.quantas_linhas_selecionadas() == 2
    _apertar(janela, Qt.Key_Return)
    assert not janela.teclado.editando()
    assert _mensagem(janela) == "Escolha um só comando para editar com o teclado (há 2 selecionados)", _estado(janela)


def test_shift_enter_pede_a_barra_lateral_do_comando_como_o_duplo_clique(sem_erro_do_teclado, abrir_janela, legacy_maps, tmp_path, monkeypatch):
    janela, _relogio, _bips = _preparar(abrir_janela, legacy_maps, tmp_path, monkeypatch, "Click")
    pedidos = []
    janela.command_table.command_editor_requested.connect(lambda comando, indice: pedidos.append(indice))
    _focar(janela, 1)
    _apertar(janela, Qt.Key_Return, Qt.ShiftModifier)
    assert pedidos == [1], _estado(janela)
    assert not janela.teclado.editando()
    assert _esperar(lambda: janela.command_sidebar.isVisible()), "a barra lateral do comando não abriu"


def test_f2_edita_a_celula_atual_e_numa_coluna_fixa_diz_o_que_fazer(sem_erro_do_teclado, abrir_janela, legacy_maps, tmp_path, monkeypatch):
    janela, _relogio, _bips = _preparar(abrir_janela, legacy_maps, tmp_path, monkeypatch, "Click")
    tabela = _focar(janela, 1, coluna=3)   # a coluna do alvo (tecla, botão, texto, programa) não se edita na lista
    _apertar(janela, Qt.Key_F2)
    assert janela.command_table._editing_cell is False
    assert _mensagem(janela) == FRASE_COLUNA_FIXA, _estado(janela)
    assert tabela.state() != QAbstractItemView.EditingState
    tabela.setCurrentCell(1, 1)   # a descrição se edita
    processar_eventos(0)
    _apertar(janela, Qt.Key_F2)
    assert janela.command_table._editing_cell is True
    assert tabela.state() == QAbstractItemView.EditingState, "o editor da célula não abriu. " + _diagnostico_de_foco(janela)
    assert not janela.teclado.editando(), "a F2 é da tabela: não abre edição do teclado"


def test_digitar_num_editor_de_celula_nao_e_tomado_pelo_teclado(sem_erro_do_teclado, abrir_janela, legacy_maps, tmp_path, monkeypatch):
    janela, _relogio, bips = _preparar(abrir_janela, legacy_maps, tmp_path, monkeypatch, "Click")
    tabela = _focar(janela, 1, coluna=1)
    _apertar(janela, Qt.Key_F2)
    editores = [e for e in tabela.viewport().findChildren(QLineEdit) if e.objectName() != "editorDeTextoEmLinha" and _visivel(e)]
    assert editores, "o editor da célula não abriu. " + _diagnostico_de_foco(janela)
    _qtest().keyClicks(editores[0], "xyz")
    assert editores[0].text().endswith("xyz") and not janela.teclado.editando() and not bips


# ================================================================================================ foco, seleção e desfazer no meio da edição
def test_mudar_a_selecao_no_meio_da_edicao_descarta_e_devolve_os_atalhos(sem_erro_do_teclado, abrir_janela, legacy_maps, tmp_path, monkeypatch):
    janela, relogio, _bips = _preparar(abrir_janela, legacy_maps, tmp_path, monkeypatch, "Click")
    tabela = _focar(janela, 0)
    _apertar(janela, Qt.Key_Return)
    assert janela.teclado.editando() and janela.hotkey_manager.suspenso
    tabela.selectRow(2)
    processar_eventos(0)
    assert not janela.teclado.editando(), "outra linha foi selecionada: a edição não vale. " + _estado(janela)
    assert _dica(janela) == DICA_NAVEGANDO and not _visivel(_moldura(janela))
    assert janela._current_map.commands[0].target == "F" and janela._current_map.commands[2].target == "F"
    relogio.advance(1.0)
    assert not janela.hotkey_manager.suspenso


def test_perder_o_foco_no_meio_da_edicao_descarta_limpa_a_dica_e_devolve_os_atalhos(sem_erro_do_teclado, abrir_janela, legacy_maps, tmp_path, monkeypatch):
    janela, relogio, _bips = _preparar(abrir_janela, legacy_maps, tmp_path, monkeypatch, "Click")
    _focar(janela, 0)
    _apertar(janela, Qt.Key_Return)
    _apertar(janela, Qt.Key_G)
    assert janela.teclado.editando() and _valor(janela) == "Tecla proposta: G"
    _tirar_o_foco(janela)
    assert not janela.teclado.editando(), "o foco saiu da tabela: a edição não vale. " + _estado(janela)
    assert _dica(janela) == "" and _valor(janela) == "" and not _visivel(_moldura(janela)), _estado(janela)
    assert janela._current_map.commands[0].target == "F", "o que estava só proposto não vai para o mapa"
    relogio.advance(1.0)
    assert not janela.hotkey_manager.suspenso


def test_ctrl_z_no_meio_da_edicao_leva_a_edicao_junto_e_desfaz_a_anterior(sem_erro_do_teclado, abrir_janela, legacy_maps, tmp_path, monkeypatch):
    janela, relogio, _bips = _preparar(abrir_janela, legacy_maps, tmp_path, monkeypatch, "Click")
    _focar(janela, 0)
    _apertar(janela, Qt.Key_Return)
    _apertar(janela, Qt.Key_G)
    _apertar(janela, Qt.Key_G)
    assert janela._current_map.commands[0].target == "G"
    _focar(janela, 2)
    _apertar(janela, Qt.Key_Return)
    assert janela.teclado.editando()
    # O Ctrl+Z chega pelo atalho da janela (se ela está ativa) ou pelo filtro da tabela: os dois desfazem do mesmo jeito.
    _apertar(janela, Qt.Key_Z, Qt.ControlModifier)
    processar_eventos(60)
    assert not janela.teclado.editando(), "o desfazer mexeu no mapa por baixo da edição: ela não vale. " + _estado(janela)
    assert janela._current_map.commands[0].target == "F", "o Ctrl+Z desfez a edição ANTERIOR, a gravada"
    assert janela._current_map.commands[2].target == "F"
    assert not _visivel(_moldura(janela))
    relogio.advance(1.0)
    assert not janela.hotkey_manager.suspenso


# ================================================================================================ a tabela grande: marca, rolagem e seleção
def test_a_marca_cai_sobre_a_linha_funda_e_a_rolagem_e_a_selecao_voltam_depois_de_gravar(sem_erro_do_teclado, abrir_janela, legacy_maps, tmp_path, monkeypatch):
    janela, _relogio, _bips = _preparar(abrir_janela, legacy_maps, tmp_path, monkeypatch, "Flins")
    mapa = janela._current_map
    assert len(mapa.commands) > 900
    linha = _linha_de(mapa, InputType.KEY, 400)
    tabela = _focar(janela, linha)
    barra = tabela.verticalScrollBar()
    assert barra.value() > 0, "a linha escolhida precisa estar longe do topo para o teste valer"
    _apertar(janela, Qt.Key_Return)
    moldura = _moldura(janela)
    assert _visivel(moldura) and moldura.geometry().top() == tabela.rowViewportPosition(linha)
    assert 0 <= moldura.geometry().top() < tabela.viewport().height(), "a marca está fora da área visível da tabela"
    antes = barra.value()
    alvo_antigo = mapa.commands[linha].target
    novo = "J" if alvo_antigo.upper() != "J" else "K"
    nome_da_tecla = getattr(Qt, f"Key_{novo}")
    _apertar(janela, nome_da_tecla)
    _apertar(janela, nome_da_tecla)
    assert not janela.teclado.editando(), _estado(janela)
    assert janela._current_map.commands[linha].target == novo
    assert abs(barra.value() - antes) <= tabela.rowHeight(linha), f"a rolagem não voltou: antes={antes} depois={barra.value()}"
    assert tabela.currentRow() == linha and janela.teclado.quantas_linhas_selecionadas() == 1, "a seleção voltou para a mesma linha"


# ================================================================================================ o tema e os erros
def test_a_marca_usa_a_cor_do_tema_de_agora(sem_erro_do_teclado, abrir_janela, legacy_maps, tmp_path, monkeypatch):
    janela, _relogio, _bips = _preparar(abrir_janela, legacy_maps, tmp_path, monkeypatch, "Click")
    for escuro, cor in ((False, teclado_ui._COR_CLARA), (True, teclado_ui._COR_ESCURA)):
        janela._dark_theme = escuro
        _focar(janela, 0)
        _apertar(janela, Qt.Key_Return)
        assert cor in _moldura(janela).styleSheet(), f"tema escuro={escuro}: a marca não tem a cor {cor}"
        _apertar(janela, Qt.Key_Escape)
        assert not janela.teclado.editando()


def test_um_erro_ao_gravar_mostra_a_frase_do_erro_nada_e_gravado_e_a_tabela_fica_livre(sem_erro_do_teclado, abrir_janela, legacy_maps, tmp_path, monkeypatch, runtime_log):
    janela, relogio, _bips = _preparar(abrir_janela, legacy_maps, tmp_path, monkeypatch, "Click")

    def quebrar(*_args, **_kwargs):
        raise RuntimeError("falha de teste")

    monkeypatch.setattr(teclado_aplicar, "aplicar_alvo", quebrar)
    tabela = _focar(janela, 0)
    _apertar(janela, Qt.Key_Return)
    _apertar(janela, Qt.Key_G)
    _apertar(janela, Qt.Key_G)
    assert not janela.teclado.editando(), _estado(janela)
    assert _mensagem(janela) == MENSAGEM_DO_ERRO, _estado(janela)
    assert janela._current_map.commands[0].target == "F", "nada foi gravado"
    assert _dica(janela) == DICA_NAVEGANDO and not _visivel(_moldura(janela))
    relogio.advance(1.0)
    assert not janela.hotkey_manager.suspenso
    erros = [linha for linha in runtime_log if linha.startswith("TECLADO_EDICAO erro=RuntimeError: falha de teste")]
    assert len(erros) == 1, runtime_log
    runtime_log.clear()   # o erro era o esperado: a conferência de fim de teste não o conta
    _apertar(janela, Qt.Key_Down)
    assert tabela.currentRow() == 1, "depois do erro a tabela anda como sempre"


def test_se_ligar_o_teclado_falha_a_janela_abre_do_mesmo_jeito_e_o_erro_vai_para_o_log(sem_erro_do_teclado, abrir_janela, legacy_maps, tmp_path, monkeypatch, runtime_log):
    def quebrar(*_args, **_kwargs):
        raise RuntimeError("falha de teste")

    monkeypatch.setattr(teclado_ui, "TradutorDeTeclas", quebrar)
    janela = _abrir(abrir_janela, legacy_maps, tmp_path, "Click")
    assert not janela.teclado.editando()
    linhas = [linha for linha in runtime_log if "onde=ligar o teclado à janela" in linha]
    assert len(linhas) == 1 and "falha de teste" in linhas[0], runtime_log
    runtime_log.clear()
    _focar(janela, 1, coluna=1)
    _apertar(janela, Qt.Key_Return)
    assert janela.command_table._editing_cell is True, "sem o teclado novo, o Enter faz o que sempre fez: edita a célula"
    assert not janela.teclado.editando()


def test_a_mensagem_de_o_que_mudou_fica_seis_segundos_na_barra_de_status(sem_erro_do_teclado, abrir_janela, legacy_maps, tmp_path, monkeypatch):
    janela, _relogio, _bips = _preparar(abrir_janela, legacy_maps, tmp_path, monkeypatch, "Click")
    pedidos = []
    original = janela.status_bar.showMessage

    def espiar(texto, tempo=0):
        pedidos.append((texto, tempo))
        original(texto, tempo)

    monkeypatch.setattr(janela.status_bar, "showMessage", espiar)
    _focar(janela, 0)
    _apertar(janela, Qt.Key_Return)
    _apertar(janela, Qt.Key_G)
    _apertar(janela, Qt.Key_G)
    gravacao = [tempo for texto, tempo in pedidos if texto.startswith("Tecla trocada para G.")]
    assert gravacao == [6000], f"a ficha manda 6 segundos (T3-12); a barra recebeu {pedidos}"
    assert SEGUNDOS_DA_MENSAGEM == 6.0
