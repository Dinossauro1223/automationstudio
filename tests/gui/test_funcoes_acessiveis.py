"""Nenhuma função do usuário se perde nem fica inacessível na janela principal.

Abre a janela de verdade (Qt real, isolada como nos outros testes de janela), navega pelas telas (lista, editor com uma
automação aberta e timeline) e confere, contra o catálogo tests/testsupport/funcoes_do_usuario.py:
  1. em cada tela em que o catálogo diz que a função está, pelo menos um endereço dela está VISÍVEL (ação da barra,
     botão ou painel). Os endereços de menu de contexto, diálogo e tecla são conferidos em
     tests/unit/test_funcoes_do_usuario_catalogo.py;
  2. nenhum controle da janela ficou de fora do catálogo (função nova entra no catálogo; senão uma remoção futura passaria
     despercebida).
Quem simplifica a interface (md/PLANO_VISUAL.md) muda a linha da função no mesmo commit: o teste só exige que a função
continue tendo um endereço visível onde o catálogo diz. Os textos conferidos são os visíveis (sem o "&" de atalho de menu).
"""
import pytest

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtGui import QAction  # noqa: E402
from PySide6.QtWidgets import QAbstractButton, QToolBar, QWidget  # noqa: E402

from automationstudio.core import map_from_json  # noqa: E402
from automationstudio.project import ProjectManager  # noqa: E402
from testsupport import funcoes_do_usuario as catalogo  # noqa: E402
from testsupport.gui_helpers import processar_eventos  # noqa: E402

pytestmark = [pytest.mark.gui, pytest.mark.isolado]

TELAS_DA_JANELA = ("lista", "editor", "timeline")


def _limpar(texto):
    return texto.replace("&", "").strip()


def _visiveis(janela):
    """Textos de ações da barra e de botões, e nomes de widgets, que o usuário enxerga AGORA."""
    acoes = set()
    for barra in janela.findChildren(QToolBar):
        if barra.isVisible():
            acoes |= {_limpar(a.text()) for a in barra.actions() if a.text() and a.isVisible()}
    botoes = {_limpar(b.text()) for b in janela.findChildren(QAbstractButton) if b.text() and b.isVisible()}
    nomes = {w.objectName() for w in janela.findChildren(QWidget) if w.objectName() and w.isVisible()}
    return acoes, botoes, nomes


def _enderecos_para(tela):
    """Para cada função, os endereços de janela que valem nesta tela (os de 'sempre' valem em lista, editor e timeline)."""
    resultado = []
    for funcao in catalogo.FUNCOES:
        validos = [a for a in funcao.acessos if a[0] in ("acao", "botao", "painel")
                   and (a[2] == tela or (a[2] == "sempre" and tela in TELAS_DA_JANELA))]
        if validos:
            resultado.append((funcao, validos))
    return resultado


def _faltando_na_tela(janela, tela):
    acoes, botoes, nomes = _visiveis(janela)
    faltando = []
    for funcao, enderecos in _enderecos_para(tela):
        achou = any((a[0] == "acao" and a[1] in acoes) or (a[0] == "botao" and a[1] in botoes)
                    or (a[0] == "painel" and a[1] in nomes) for a in enderecos)
        if not achou:
            faltando.append(f"[tela {tela}] {funcao.id} {funcao.nome}: procurado {[a[:2] for a in enderecos]}")
    return faltando


def _janela_com_mapas(abrir_janela, legacy_maps, tmp_path):
    pasta = tmp_path / "dados_reais"
    gerente = ProjectManager(pasta)
    for texto in legacy_maps.values():
        gerente.save_map(map_from_json(texto))
    janela = abrir_janela(pasta=pasta)
    janela.resize(1366, 800)
    janela.show()  # visibilidade só existe com a janela mostrada
    processar_eventos(50)
    return janela, sorted(gerente.maps)


def test_toda_funcao_do_catalogo_esta_visivel_na_tela_certa(abrir_janela, legacy_maps, tmp_path):
    janela, nomes = _janela_com_mapas(abrir_janela, legacy_maps, tmp_path)
    faltando = []
    janela.pages.setCurrentIndex(1)
    processar_eventos(20)
    faltando += _faltando_na_tela(janela, "lista")
    janela._select_map_by_name(nomes[0])
    processar_eventos(20)
    assert janela.pages.currentIndex() == 2
    faltando += _faltando_na_tela(janela, "editor")
    janela._open_timeline()
    processar_eventos(20)
    assert janela.pages.currentIndex() == 3
    faltando += _faltando_na_tela(janela, "timeline")
    assert not faltando, ("função sem endereço visível na tela do catálogo. Se o controle mudou de lugar ou de nome, atualize "
                          "a linha da função em tests/testsupport/funcoes_do_usuario.py e regenere md/FUNCOES_DO_USUARIO.md:\n  "
                          + "\n  ".join(faltando))


def test_nenhum_controle_da_janela_esta_fora_do_catalogo(abrir_janela):
    janela = abrir_janela()
    acoes = {_limpar(a.text()) for a in janela.findChildren(QAction) if a.text()}
    botoes = {_limpar(b.text()) for b in janela.findChildren(QAbstractButton) if b.text()}
    conhecidos = {a[1] for f in catalogo.FUNCOES for a in f.acessos if a[0] in ("acao", "botao")}
    fora = sorted((acoes | botoes) - conhecidos - catalogo.CONTROLES_QUE_NAO_SAO_FUNCOES)
    assert not fora, (f"controle novo sem função no catálogo: {fora}. Acrescente a função em "
                      "tests/testsupport/funcoes_do_usuario.py (ID novo) e regenere md/FUNCOES_DO_USUARIO.md; se não for uma "
                      "função do usuário, ponha o texto em CONTROLES_QUE_NAO_SAO_FUNCOES.")
