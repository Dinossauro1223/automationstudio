"""A faixa de ativação (PainelAtivacao) e as marcas da lista de automações (ControladorAtivacao.decorar_lista).

Roda com o PySide6 real e, no desenvolvimento (sem Qt), contra o dublê funcional parcial (AS_TEST_QT_STUB=widgets). A janela
principal é de mentira (testsupport/janela_falsa.py); o encaixe da faixa no editor de verdade está em test_ativacao_janela.py.

Critério da ficha (md/ESPEC_ATIVACAO_25_8.md): ATV-05, mais o contrato com a frente visual: os papéis de dados 257 e 258 da
lista e a faixa como o único seletor funcional da ativação.
"""
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget  # noqa: E402

import automationstudio.ativacao_ui as ativacao_ui  # noqa: E402
from automationstudio.ativacao import (ESTADO_DESATIVADO as DESAT, ESTADO_SEMPRE as SEMPRE,  # noqa: E402
                                       ESTADO_SESSAO as SESSAO, ESTADOS, ROTULOS)
from automationstudio.ativacao_ui import PAPEL_CONFLITO, PAPEL_ESTADO, PainelAtivacao  # noqa: E402
from testsupport.janela_falsa import abrir  # noqa: E402

pytestmark = pytest.mark.gui

DICA = "Abrir esta automação para editar."


def _com_lista(janela, nomes):
    janela.map_list = QListWidget()
    for nome in nomes:
        janela.map_list.addItem(QListWidgetItem(nome))
    return janela.map_list


def _com_novo_em_conflito(pasta):
    """Janela com o Exemplo ativo (tecla "=") e o Novo (mesma tecla) desativado, que é como ele nasce."""
    janela = abrir(pasta, {"Exemplo": "="})
    janela.project_manager.maps["Novo"] = SimpleNamespace(name="Novo", hotkey="=")
    janela.ativacao.sincronizar()
    return janela


# ------------------------------------------------------------------------------------------------ a lista
def test_a_lista_recebe_o_estado_e_o_conflito_em_cada_item(gui, tmp_path):
    janela = abrir(tmp_path, {"A": "=", "B": "=", "C": "F7"})
    janela.ativacao.definir_estado("C", DESAT)
    lista = _com_lista(janela, ["A", "B", "C"])
    janela.ativacao.decorar_lista(DICA)
    assert [lista.item(i).data(PAPEL_ESTADO) for i in range(3)] == [SEMPRE, SEMPRE, DESAT]
    assert [lista.item(i).data(PAPEL_CONFLITO) for i in range(3)] == ["", "A tecla “=” de “B” já é usada pela automação ativa “A”.", ""]


def test_a_dica_de_cada_item_diz_a_situacao_e_mantem_a_frase_de_abrir(gui, tmp_path):
    janela = abrir(tmp_path, {"A": "=", "B": "F7"})
    janela.ativacao.definir_estado("B", DESAT)
    lista = _com_lista(janela, ["A", "B"])
    janela.ativacao.decorar_lista(DICA)
    assert lista.item(0).toolTip() == DICA + "\n\nSempre ativo ao iniciar\nA tecla “=” inicia e para esta automação."
    assert lista.item(1).toolTip() == (DICA + "\n\nDesativado\nA tecla “F7” não inicia esta automação. "
                                       "O botão ▶ Executar continua funcionando.")


def test_os_papeis_de_dados_da_lista_sao_os_combinados_com_a_frente_visual(gui):
    # Qt.UserRole vale 256; o texto do item (o nome do mapa) continua sendo a chave que a janela usa para achar o mapa.
    assert (PAPEL_ESTADO, PAPEL_CONFLITO) == (257, 258)


def test_decorar_a_lista_nao_muda_o_texto_dos_itens(gui, tmp_path):
    janela = abrir(tmp_path, {"A": "=", "B": "F7"})
    lista = _com_lista(janela, ["A", "B"])
    janela.ativacao.decorar_lista(DICA)
    assert [lista.item(i).text() for i in range(2)] == ["A", "B"]


# ------------------------------------------------------------------------------------------------ a faixa
def test_a_faixa_oferece_os_tres_estados_na_ordem_da_ficha(gui, tmp_path):
    painel = PainelAtivacao(abrir(tmp_path).ativacao)
    assert [painel.combo.itemText(i) for i in range(painel.combo.count())] == [ROTULOS[e] for e in ESTADOS]
    assert [painel.combo.itemData(i) for i in range(painel.combo.count())] == list(ESTADOS)


def test_a_faixa_mostra_o_estado_a_tecla_e_a_frase_da_automacao(gui, tmp_path):
    painel = PainelAtivacao(abrir(tmp_path).ativacao)
    painel.mostrar("Flins combo")
    assert painel.combo.currentData() == SEMPRE
    assert painel.situacao.text() == "A tecla “MOUSE_X2” inicia e para esta automação."
    assert not painel.isHidden()


def test_a_faixa_se_esconde_sem_automacao_e_volta_com_uma(gui, tmp_path):
    painel = PainelAtivacao(abrir(tmp_path).ativacao)
    painel.mostrar(None)
    assert painel.isHidden()
    painel.mostrar("Flins combo")
    assert not painel.isHidden()


def test_escolher_um_estado_na_faixa_aplica_grava_e_refaz_os_atalhos(gui, tmp_path):                                  # ATV-05
    janela = abrir(tmp_path)
    painel = PainelAtivacao(janela.ativacao)
    painel.mostrar("Flins combo")
    registros = janela.registros
    painel.combo.setCurrentIndex(ESTADOS.index(DESAT))
    assert janela.ativacao.descrever("Flins combo").estado == DESAT
    assert janela.registros == registros + 1
    assert painel.combo.currentData() == DESAT
    assert painel.situacao.text() == "A tecla “MOUSE_X2” não inicia esta automação. O botão ▶ Executar continua funcionando."
    janela.clicar("x2")
    assert janela.disparos == []


def test_escolher_so_nesta_sessao_a_partir_de_sempre_avisa_na_barra_de_status(gui, tmp_path):                           # MAP-01
    janela = abrir(tmp_path)
    painel = PainelAtivacao(janela.ativacao)
    painel.mostrar("Flins combo")
    painel.combo.setCurrentIndex(ESTADOS.index(SESSAO))
    assert janela.status == ["Na próxima abertura do programa esta automação ficará desativada."]
    assert painel.combo.currentData() == SESSAO


def test_a_faixa_recusa_a_escolha_em_conflito_e_volta_ao_estado_real(gui, tmp_path):                                      # ATV-05 / HK-01
    janela = _com_novo_em_conflito(tmp_path)
    painel = PainelAtivacao(janela.ativacao)
    painel.mostrar("Novo")
    assert painel.combo.currentData() == DESAT
    painel.combo.setCurrentIndex(ESTADOS.index(SEMPRE))
    assert janela.avisos[-1][0] == "Não foi possível ativar" and "“Exemplo”" in janela.avisos[-1][1]
    assert painel.combo.currentData() == DESAT, "a faixa volta a mostrar o estado verdadeiro"
    assert janela.ativacao.descrever("Novo").estado == DESAT


def test_mostrar_na_faixa_nao_conta_como_uma_escolha_do_usuario(gui, tmp_path, monkeypatch):
    janela = abrir(tmp_path)
    escolhas = []
    monkeypatch.setattr(janela.ativacao, "definir_estado", lambda nome, estado: escolhas.append((nome, estado)))
    painel = PainelAtivacao(janela.ativacao)
    for nome in ("Click genshin", "Flins combo", None, "Exemplo — Primeira automação"):
        painel.mostrar(nome)
    assert escolhas == []


def test_a_faixa_acompanha_a_automacao_aberta_pelo_controlador(gui, tmp_path):
    janela = abrir(tmp_path)
    janela.ativacao.painel = PainelAtivacao(janela.ativacao)
    janela._current_map = janela.project_manager.maps["Click genshin"]
    janela.ativacao.atualizar_painel()
    assert janela.ativacao.painel.situacao.text() == "A tecla “MOUSE_X1” inicia e para esta automação."
    janela._current_map = None
    janela.ativacao.atualizar_painel()
    assert janela.ativacao.painel.isHidden()


# ------------------------------------------------------------------------------------------------ o encaixe no editor
def _editor_de_mentira():
    """Um editor mínimo, na forma do verdadeiro: um widget com layout vertical, a etiqueta de instrução e a tabela depois."""
    editor = QWidget()
    layout = QVBoxLayout(editor)
    instrucao, tabela = QLabel("instrução"), QLabel("tabela")
    layout.addWidget(instrucao)
    layout.addWidget(tabela)
    return editor, layout, instrucao, tabela


def test_a_faixa_se_encaixa_no_editor_logo_abaixo_da_ancora(gui, tmp_path):
    janela = abrir(tmp_path)
    _editor, layout, instrucao, tabela = _editor_de_mentira()
    janela.ativacao.montar_painel(instrucao)
    faixa = janela.ativacao.painel
    assert faixa is not None
    assert (layout.indexOf(instrucao), layout.indexOf(faixa), layout.indexOf(tabela)) == (0, 1, 2)
    assert faixa.isHidden(), "a faixa só aparece quando há uma automação aberta"


def test_se_a_ancora_foi_para_dentro_de_outro_layout_a_faixa_vai_para_o_fim_e_o_motivo_vai_para_o_log(gui, tmp_path, monkeypatch):
    janela = abrir(tmp_path)
    _editor, layout, instrucao, _tabela = _editor_de_mentira()
    layout.removeWidget(instrucao)
    linha = QHBoxLayout()
    linha.addWidget(instrucao)
    layout.addLayout(linha)  # a âncora agora está num layout filho: o `indexOf` do editor não a acha
    registros = []
    monkeypatch.setattr(ativacao_ui, "_append_runtime_log", registros.append)
    janela.ativacao.montar_painel(instrucao)
    faixa = janela.ativacao.painel
    assert faixa is not None and layout.indexOf(faixa) == layout.count() - 1
    assert len(registros) == 1 and registros[0].startswith("FAIXA DE ATIVACAO NO FIM DO EDITOR"), registros


def test_se_o_editor_mudou_de_forma_a_faixa_nao_derruba_a_janela(gui, tmp_path, monkeypatch):
    janela = abrir(tmp_path)
    registros = []
    monkeypatch.setattr(ativacao_ui, "_append_runtime_log", registros.append)
    janela.ativacao.montar_painel(object())  # sem `parentWidget`: não há onde encaixar
    assert janela.ativacao.painel is None
    assert len(registros) == 1 and registros[0].startswith("FAIXA DE ATIVACAO NAO MONTADA"), registros
    janela.ativacao.atualizar_painel()  # sem faixa, atualizar não faz nada


def test_uma_ancora_sem_pai_tambem_nao_derruba_a_janela(gui, tmp_path, monkeypatch):
    janela = abrir(tmp_path)
    monkeypatch.setattr(ativacao_ui, "_append_runtime_log", lambda texto: None)
    janela.ativacao.montar_painel(QLabel("solta"))  # uma etiqueta sem widget pai nem layout
    assert janela.ativacao.painel is None
