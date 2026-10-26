"""Contrato Qt: o que os testes de janela ASSUMEM sobre o Qt.

Os testes de `CommandDialog` rodam no desenvolvimento contra um dublê parcial do PySide6 (testsupport/qt_double), que
reproduz o que a documentação do Qt diz. Este arquivo afirma, UMA vez, cada uma dessas crenças, e roda dos dois lados:
no dublê (ele precisa cumprir o contrato) e no PySide6 real (o contrato precisa ser verdadeiro).

SE UM TESTE DESTE ARQUIVO FALHAR NO PySide6 REAL, o dublê estava errado e qualquer conclusão que os testes de janela
tiraram com ele precisa ser revista. Não "conserte" o teste: me envie a saída (o que o Qt real fez é a informação).
Cada teste diz, no nome e no comentário, que decisão do código ou do teste depende dele.
"""
import pytest

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtGui import QPixmap  # noqa: E402
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QLabel, QListWidget,  # noqa: E402
                               QListWidgetItem, QPushButton, QSpinBox)

from automationstudio.conditions import WaitCondition, WaitConditionType  # noqa: E402
from automationstudio.core import ActionType, InputType  # noqa: E402
from testsupport.gui_helpers import write_png  # noqa: E402

pytestmark = pytest.mark.gui


def _combo(*textos, editavel=False):
    combo = QComboBox()
    combo.setEditable(editavel)
    for texto in textos:
        combo.addItem(texto, texto.lower())
    return combo


# ------------------------------------------------------------------------------------------------- QComboBox
def test_o_primeiro_item_adicionado_vira_o_atual_e_avisa(gui):
    # `target_combo` e `action_combo` dependem disto: depois de `addItems`, o combo já tem uma tecla válida escolhida.
    combo, avisos = QComboBox(), []
    combo.currentIndexChanged.connect(lambda indice: avisos.append(indice))
    combo.addItem("A", "a")
    assert combo.currentIndex() == 0 and combo.currentText() == "A" and combo.currentData() == "a"
    assert avisos == [0]
    combo.addItem("B", "b")
    assert combo.currentIndex() == 0 and avisos == [0], "o segundo item não muda a seleção"


def test_find_text_e_exato_e_diferencia_maiusculas(gui):
    # `_update_form` acha a tecla do comando por `findText`: "a" não pode achar "A" (o código já põe o alvo em maiúsculas).
    combo = _combo("A", "SPACE", ";")
    assert (combo.findText("A"), combo.findText("SPACE"), combo.findText(";")) == (0, 1, 2)
    assert combo.findText("a") == -1 and combo.findText("SPAC") == -1 and combo.findText("X") == -1


def test_find_data_compara_o_dado_inclusive_enum_de_texto(gui):
    # `type_combo`, `action_combo` e `scroll_direction` guardam Enum(str)/texto como dado e são buscados por `findData`.
    combo = QComboBox()
    combo.addItem("tecla", InputType.KEY)
    combo.addItem("botão", InputType.MOUSE_BUTTON)
    assert combo.findData(InputType.MOUSE_BUTTON) == 1 and combo.findData(InputType.TEXT) == -1
    combo.setCurrentIndex(1)
    assert combo.currentData() == InputType.MOUSE_BUTTON  # igualdade: o PySide pode devolver o texto "mouse_button"
    acoes = QComboBox()
    acoes.addItem("soltar", ActionType.RELEASE)
    acoes.addItem("manter", ActionType.PRESS)
    assert acoes.findData(ActionType.PRESS) == 1
    textos = QComboBox()
    textos.addItem("para baixo", "down")
    assert textos.findData("down") == 0 and textos.findData("up") == -1


def test_combo_nao_editavel_set_current_text_so_seleciona_item_existente(gui):
    # `_preencher_tecla` e o código de teclas dependem disto: texto que não existe NÃO muda nada.
    combo = _combo("A", "B", "C")
    combo.setCurrentText("C")
    assert combo.currentIndex() == 2
    combo.setCurrentText("Z")
    assert combo.currentIndex() == 2 and combo.currentText() == "C"
    combo.setCurrentText("b")  # diferença de maiúsculas: não é o mesmo texto
    assert combo.currentIndex() == 2


def test_combo_editavel_set_current_text_so_muda_o_texto_do_campo(gui):
    # Base do defeito G4b do achado 2.07: num combo editável o índice atual NÃO acompanha o que se digita, então
    # `currentData()` fica com o dado do item antigo. Por isso o código lê o texto do campo antes do dado do item.
    combo = _combo("Nenhum", "Bloco", editavel=True)
    combo.setCurrentIndex(1)
    assert combo.currentText() == "Bloco" and combo.currentData() == "bloco"
    combo.setCurrentText("meuapp.exe")
    assert combo.currentText() == "meuapp.exe"
    assert combo.currentIndex() == 1, "o índice não acompanha o texto digitado"
    assert combo.currentData() == "bloco", "o dado continua sendo o do item antigo"


def test_combo_editavel_trocar_o_indice_troca_o_texto_do_campo(gui):
    combo = _combo("Nenhum", "Bloco", editavel=True)
    combo.setCurrentText("digitado")
    combo.setCurrentIndex(0)
    assert combo.currentText() == "Nenhum"


def test_clear_deixa_o_combo_sem_selecao(gui):
    # `_update_form` e `_select_group` esvaziam e refazem a lista a cada troca de tipo ou de comando.
    combo = _combo("A", "B")
    combo.clear()
    assert (combo.count(), combo.currentIndex(), combo.currentText(), combo.currentData()) == (0, -1, "", None)
    combo.addItem("C", "c")
    assert combo.currentIndex() == 0 and combo.currentText() == "C"


def test_indice_fora_da_faixa_deixa_o_combo_sem_selecao(gui):
    # `setCurrentIndex(max(0, findData(...)))` em combo vazio não pode quebrar nem selecionar nada.
    vazio = QComboBox()
    vazio.setCurrentIndex(0)
    assert vazio.currentIndex() == -1 and vazio.currentText() == ""
    combo = _combo("A", "B")
    combo.setCurrentIndex(5)
    assert combo.currentIndex() == -1


# --------------------------------------------------------------------------------------------- caixas de número
def test_caixa_decimal_arredonda_nas_casas_e_limita_ao_intervalo(gui):
    # O editor mostra segundos com 3 casas: abrir e salvar arredonda 0,7041708999995535 para 0,704 (tolerância de 0,5 ms).
    spin = QDoubleSpinBox()
    spin.setRange(0, 3600)
    spin.setDecimals(3)
    spin.setValue(0.7041708999995535)
    assert spin.value() == 0.704
    spin.setValue(5000.0)
    assert spin.value() == 3600.0, "o intervalo corta quem passa do máximo"
    spin.setValue(-1.0)
    assert spin.value() == 0.0


def test_novo_maximo_antes_do_valor_evita_o_corte(gui):
    # Base do `_load_number`: o que o mapa já tem (comando depois de 1 h) não pode ser cortado em silêncio ao abrir.
    spin = QDoubleSpinBox()
    spin.setRange(0, 3600)
    spin.setDecimals(3)
    spin.setMaximum(7300.5)
    spin.setValue(7300.5)
    assert spin.value() == 7300.5 and spin.maximum() == 7300.5
    inteiro = QSpinBox()
    inteiro.setRange(0, 10000)
    inteiro.setMaximum(20000)
    inteiro.setValue(15000)
    assert inteiro.value() == 15000


def test_caixa_so_avisa_quando_o_valor_muda(gui):
    # `_refresh_delay_suggestion` é ligado a `delay.valueChanged`: gravar o mesmo valor não pode disparar de novo.
    spin, avisos = QDoubleSpinBox(), []
    spin.setRange(0, 10)
    spin.setDecimals(3)
    spin.valueChanged.connect(lambda valor: avisos.append(valor))
    spin.setValue(0.25)
    spin.setValue(0.25)
    spin.setValue(0.3)
    assert avisos == [0.25, 0.3]


# ----------------------------------------------------------------------------------- QLabel, QPixmap e QPoint
def test_texto_e_imagem_do_rotulo_se_excluem(gui):
    # `_update_condition_preview` mostra ou a miniatura ou o motivo, nunca os dois.
    rotulo = QLabel("sem imagem")
    rotulo.setPixmap(QPixmap(40, 30))
    assert rotulo.text() == ""
    rotulo.setText("Nenhuma imagem selecionada")
    imagem = rotulo.pixmap()
    assert rotulo.text() == "Nenhuma imagem selecionada" and (imagem is None or imagem.isNull())


def test_pixmap_de_arquivo_invalido_e_nulo_e_o_de_png_valido_nao(gui, tmp_path):
    assert QPixmap(str(tmp_path / "nao_existe.png")).isNull()
    (tmp_path / "lixo.png").write_bytes(b"isto nao e uma imagem")
    assert QPixmap(str(tmp_path / "lixo.png")).isNull()
    valida = QPixmap(write_png(tmp_path / "botao.png", 40, 30))
    assert not valida.isNull() and (valida.width(), valida.height()) == (40, 30)
    reduzida = valida.scaled(20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    assert (reduzida.width(), reduzida.height()) == (20, 15)


def test_qpoint_tem_x_e_y_mas_nao_e_subscritivel(gui):
    # Base do defeito G3 do achado 2.07: o editor lia `self._move_pos[0]` num QPoint. Se este teste FALHAR no seu PySide6
    # (isto é, se QPoint aceitar `ponto[0]`), o G3 era um falso alarme: a correção (x() e y()) continua válida e inofensiva,
    # mas o relatório precisa corrigir a classificação do achado.
    ponto = QPoint(961, 540)
    assert (ponto.x(), ponto.y()) == (961, 540)
    with pytest.raises(TypeError):
        ponto[0]


# ----------------------------------------------------------------------------------------- lista, botões, diálogo
def test_a_lista_guarda_o_objeto_python_no_item(gui):
    # `_current_conditions` lê `item.data(Qt.UserRole)` e exige `isinstance(..., WaitCondition)`.
    lista = QListWidget()
    condicao = WaitCondition(type=WaitConditionType.DELAY, timeout=1.5)
    item = QListWidgetItem()
    item.setData(Qt.UserRole, condicao)
    item.setText("Aguardar 1.5s")
    lista.addItem(item)
    guardada = lista.item(0).data(Qt.UserRole)
    assert isinstance(guardada, WaitCondition) and guardada.timeout == 1.5
    lista.setCurrentRow(0)
    assert lista.currentRow() == 0
    assert lista.takeItem(0) is not None and lista.count() == 0
    lista.addItem(QListWidgetItem("x"))
    lista.clear()
    assert lista.count() == 0 and lista.currentRow() == -1


def test_botao_click_emite_clicked_e_checkbox_alterna(gui):
    botao, cliques = QPushButton("ok"), []
    botao.clicked.connect(lambda *_: cliques.append(True))
    botao.click()
    assert cliques == [True]
    botao.setEnabled(False)
    botao.click()
    assert cliques == [True], "botão desabilitado não emite"
    caixa = QCheckBox("x")
    caixa.click()
    assert caixa.isChecked()


def test_dialogo_accept_e_reject_emitem_os_sinais(gui):
    dialogo, vistos = QDialog(), []
    dialogo.accepted.connect(lambda: vistos.append("accepted"))
    dialogo.rejected.connect(lambda: vistos.append("rejected"))
    dialogo.accept()
    dialogo.reject()
    assert vistos == ["accepted", "rejected"]
