"""A ativação por mapa na janela principal (MainWindow) com o PySide6 REAL.

Estes testes foram escritos sem poder rodar o Qt (o ambiente de desenvolvimento não o tem), como os de test_main_window_smoke.py:
usam só nomes conferidos no código e passos simples. Se algum falhar na sua máquina, a mensagem mostra o estado real; me envie
a saída. Não rodam com o dublê (a janela principal não cabe nele): são pulados.

O que eles confirmam e nenhum outro teste confirma: o encaixe da faixa no editor, a ligação da janela com o controlador
(`_reload_map_list`, `_register_all_hotkeys`, `_on_hotkey_triggered`, `_configure_current_map`, `_delete_current_map`) e o
registro dos atalhos no gerente verdadeiro. A lógica, os textos e as regras estão em tests/unit/test_ativacao*.py.

Critérios da ficha (md/ESPEC_ATIVACAO_25_8.md): MAP-03 e MAP-04 (a parte com a janela), HK-01, ATV-01 a ATV-05.
Isolamento e marcador `isolado`: como em test_main_window_smoke.py.
"""
import pytest

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtWidgets import QFileDialog, QInputDialog  # noqa: E402

from automationstudio.ativacao import ESTADOS  # noqa: E402
from automationstudio.ativacao_ui import PAPEL_ESTADO  # noqa: E402
from automationstudio.core import AutomationMap, State, map_from_json, map_to_json, parse_combo  # noqa: E402
from automationstudio.project import AppSettings, ProjectManager  # noqa: E402
from testsupport.helpers import events_of, join_engine, key, raw_exec  # noqa: E402

pytestmark = [pytest.mark.gui, pytest.mark.isolado]

CONTROLES = ("F9", "F10", "F12", "F8", "F11")  # os padrões de AppSettings.get_control_hotkeys()


def _exigir_atalhos(janela):
    """Os atalhos globais só são registrados quando o pynput está disponível (a janela pula o registro sem ele)."""
    if not janela.hotkey_manager.available:
        pytest.skip("o gerenciador de atalhos não está disponível (pynput não instalado): nada é registrado")


def _combos(janela) -> set:
    return set(janela.hotkey_manager._bindings)


def _nova_automacao(janela, monkeypatch, nome):
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: (nome, True)))
    janela._new_map()
    assert janela._current_map is not None and janela._current_map.name == nome, janela._current_map
    return janela._current_map


def _gravar_mapas_reais(pasta, legacy_maps) -> list[str]:
    gerente = ProjectManager(pasta)
    for texto in legacy_maps.values():
        gerente.save_map(map_from_json(texto))
    return sorted(gerente.maps)


def _responder_configuracao(monkeypatch, tecla):
    """Responde a todas as perguntas de "⚙ Configurações da automação" mantendo tudo como está, menos a tecla."""
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(lambda parent, titulo, rotulo, itens, atual=0, editavel=False: (itens[atual], True)))
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: (tecla, True)))
    monkeypatch.setattr(QInputDialog, "getInt", staticmethod(lambda parent, titulo, rotulo, valor=0, *a, **k: (valor, True)))
    monkeypatch.setattr(QInputDialog, "getDouble", staticmethod(lambda parent, titulo, rotulo, valor=0.0, *a, **k: (valor, True)))


def _avisos(gui, desde=0):
    return [c for c in gui.calls[desde:] if c[0] == "warning"]


# ------------------------------------------------------------------------------------------------ abertura
def test_os_tres_mapas_reais_abrem_sempre_ativos_e_registram_os_mesmos_atalhos(abrir_janela, legacy_maps, tmp_path, gui):   # MAP-04
    pasta = tmp_path / "dados_reais"
    nomes = _gravar_mapas_reais(pasta, legacy_maps)
    janela = abrir_janela(pasta=pasta)
    _exigir_atalhos(janela)
    assert {n: janela.ativacao.descrever(n).estado for n in nomes} == {n: "sempre" for n in nomes}
    assert _combos(janela) == {parse_combo(t) for t in ("MOUSE_X1", "=", "MOUSE_X2") + CONTROLES}
    assert AppSettings(pasta).get_map_activation() == {"migrated": True, "prefs": {n: "sempre" for n in nomes}}
    assert _avisos(gui) == [], "abrir os mapas de sempre não pode avisar de conflito nenhum"


def test_a_janela_abre_mesmo_com_a_ativacao_corrompida_no_banco(abrir_janela, legacy_maps, tmp_path):                       # ATV-04
    pasta = tmp_path / "dados_reais"
    nomes = _gravar_mapas_reais(pasta, legacy_maps)
    raw_exec(AppSettings(pasta).db_path, "INSERT INTO settings(key,value) VALUES(?,?)", ("map_activation", '"lixo"'))
    janela = abrir_janela(pasta=pasta)
    assert {n: janela.ativacao.descrever(n).estado for n in nomes} == {n: "sempre" for n in nomes}


def test_primeiro_uso_a_automacao_de_demonstracao_nasce_ativa_so_nesta_sessao(abrir_janela):                                # ATV-03
    janela = abrir_janela(pular_tutorial=False)
    assert janela.ativacao.descrever("Exemplo — Primeira automação").estado == "sessao"
    assert janela.project_manager.maps["Exemplo — Primeira automação"].hotkey == "CTRL+SHIFT+ALT+1", "25.9: a primeira automação nasce na combinação padrão"
    assert AppSettings(janela.project_manager.project_dir).get_map_activation()["prefs"] == {"Exemplo — Primeira automação": "desativado"}


def test_a_lista_marca_cada_automacao_com_o_estado_e_a_dica(abrir_janela, legacy_maps, tmp_path):
    pasta = tmp_path / "dados_reais"
    nomes = _gravar_mapas_reais(pasta, legacy_maps)
    janela = abrir_janela(pasta=pasta)
    itens = {janela.map_list.item(i).text(): janela.map_list.item(i) for i in range(janela.map_list.count())}
    assert sorted(itens) == nomes
    assert {n: i.data(PAPEL_ESTADO) for n, i in itens.items()} == {n: "sempre" for n in nomes}
    dica = itens["Flins combo"].toolTip()
    assert dica.startswith("Abrir esta automação para editar") and "Sempre ativo ao iniciar" in dica, dica


# ------------------------------------------------------------------------------------------------ criar, importar, excluir
def test_automacao_criada_nasce_ativa_so_nesta_sessao_com_a_primeira_combinacao_livre_e_a_proxima_recebe_a_seguinte(abrir_janela, monkeypatch, gui):   # ATV-03 / TEC-12
    janela = abrir_janela()
    _exigir_atalhos(janela)
    um = _nova_automacao(janela, monkeypatch, "Um")  # 25.9: a tecla de uma automação nova é a primeira combinação livre
    assert um.hotkey == "CTRL+SHIFT+ALT+1"
    assert janela.ativacao.descrever("Um").estado == "sessao" and parse_combo("CTRL+SHIFT+ALT+1") in _combos(janela)
    antes = len(gui.calls)
    dois = _nova_automacao(janela, monkeypatch, "Dois")
    assert dois.hotkey == "CTRL+SHIFT+ALT+2", "a segunda não repete a tecla da primeira"
    assert janela.ativacao.descrever("Dois").estado == "sessao" and parse_combo("CTRL+SHIFT+ALT+2") in _combos(janela)
    assert _avisos(gui, antes) == [], "sem conflito: nenhuma das duas nasce desativada"
    assert {parse_combo("CTRL+SHIFT+ALT+1"), parse_combo("CTRL+SHIFT+ALT+2")} <= _combos(janela)


def test_importar_automacao_com_tecla_ocupada_nasce_desativada_e_avisa(abrir_janela, monkeypatch, gui, tmp_path):             # ATV-03 / HK-01
    janela = abrir_janela()
    um = _nova_automacao(janela, monkeypatch, "Um")
    arquivo = tmp_path / "externo.json"
    arquivo.write_text(map_to_json(AutomationMap(name="Externo", hotkey=um.hotkey, repeat_count=1)), encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(arquivo), "")))
    antes = len(gui.calls)
    janela._import_map()
    assert "Externo" in janela.project_manager.maps and janela.ativacao.descrever("Externo").estado == "desativado"
    assert any(c[1] == "Atalho em conflito" and "“Externo”" in c[2] for c in _avisos(gui, antes)), gui.calls[antes:]


def test_excluir_a_automacao_apaga_a_preferencia_gravada(abrir_janela, monkeypatch):                                          # ATV-03
    janela = abrir_janela()
    _nova_automacao(janela, monkeypatch, "Descartável")
    pasta = janela.project_manager.project_dir
    assert "Descartável" in AppSettings(pasta).get_map_activation()["prefs"]
    janela._delete_current_map()
    assert "Descartável" not in AppSettings(pasta).get_map_activation()["prefs"]


# ------------------------------------------------------------------------------------------------ a faixa no editor
def test_a_faixa_fica_no_editor_logo_abaixo_do_titulo_e_muda_o_estado(abrir_janela, monkeypatch):                              # ATV-05
    janela = abrir_janela()
    _exigir_atalhos(janela)
    mapa = _nova_automacao(janela, monkeypatch, "Mapa")
    faixa = janela.ativacao.painel
    layout = janela._editor_page.layout()
    assert faixa is not None and layout.indexOf(faixa) == layout.indexOf(janela.map_instruction) + 1
    assert janela.map_instruction.parentWidget() is janela._editor_page, "a âncora da faixa é filha direta da página do editor"
    assert faixa.combo.currentData() == "sessao"
    faixa.combo.setCurrentIndex(ESTADOS.index("desativado"))
    assert parse_combo(mapa.hotkey) not in _combos(janela), "desativar tira a tecla do gerente de atalhos"
    assert AppSettings(janela.project_manager.project_dir).get_map_activation()["prefs"]["Mapa"] == "desativado"
    assert janela.hotkey_label.text() == f"Tecla para iniciar/parar: {mapa.hotkey} (desativada)"


def test_o_rotulo_da_tecla_no_editor_continua_curto_enquanto_a_tecla_funciona(abrir_janela, monkeypatch):
    janela = abrir_janela()
    _nova_automacao(janela, monkeypatch, "Mapa")
    assert janela.hotkey_label.text() == "Tecla para iniciar/parar: CTRL+SHIFT+ALT+1"


# ------------------------------------------------------------------------------------------------ MAP-03 com o motor
def test_mapa_desativado_nao_executa_pela_tecla_mas_o_botao_executar_continua_funcionando(abrir_janela, monkeypatch):       # MAP-03
    janela = abrir_janela()
    mapa = _nova_automacao(janela, monkeypatch, "Mapa")
    mapa.repeat_count = 1  # o mapa criado pelo botão repete para sempre
    mapa.add_command(key("F", 0.0, 0.05))
    janela._on_map_edited()
    janela.ativacao.definir_estado("Mapa", "desativado")
    janela._on_hotkey_triggered("map:Mapa")
    assert janela.engine._backend.events == [] and janela.state.state == State.IDLE, "a tecla de um mapa desativado não executa"
    janela._run_current_map()
    join_engine(janela.engine, timeout=10.0)
    assert [(acao, alvo) for _t, acao, alvo in events_of(janela.engine._backend)] == [("key_down", "F"), ("key_up", "F")]
    janela.engine._backend.events.clear()
    janela.ativacao.definir_estado("Mapa", "sessao")
    janela._on_hotkey_triggered("map:Mapa")
    join_engine(janela.engine, timeout=10.0)
    assert [(acao, alvo) for _t, acao, alvo in events_of(janela.engine._backend)] == [("key_down", "F"), ("key_up", "F")], \
        "controle positivo: ativado de novo, a mesma tecla executa"


# ------------------------------------------------------------------------------------------------ ATV-01
def test_a_parada_de_emergencia_continua_com_a_tecla_mesmo_que_um_mapa_use_a_mesma(abrir_janela, monkeypatch, gui):             # ATV-01
    janela = abrir_janela()
    _exigir_atalhos(janela)
    mapa = _nova_automacao(janela, monkeypatch, "Mapa")
    mapa.hotkey = "F12"  # como um dado antigo: a tela nova recusaria esta tecla
    paradas = []
    monkeypatch.setattr(janela.engine, "emergency_stop", lambda: paradas.append(True))
    antes = len(gui.calls)
    janela._register_all_hotkeys()
    janela.hotkey_manager._bindings[parse_combo("F12")][1]()  # o que o gerente faz ao apertar F12
    assert paradas == [True], "a tecla F12 precisa continuar sendo a parada de emergência"
    assert any("Parar tudo agora" in c[2] and "“Mapa”" in c[2] for c in _avisos(gui, antes)), gui.calls[antes:]


# ------------------------------------------------------------------------------------------------ mudar a tecla (HK-01)
def test_mudar_a_tecla_para_uma_ocupada_e_recusado_mas_o_resto_da_configuracao_segue(abrir_janela, monkeypatch, gui):             # HK-01
    janela = abrir_janela()
    _exigir_atalhos(janela)
    um = _nova_automacao(janela, monkeypatch, "Um")  # CTRL+SHIFT+ALT+1
    dois = _nova_automacao(janela, monkeypatch, "Dois")  # CTRL+SHIFT+ALT+2
    dois.hotkey = "F6"  # como um dado antigo: a tela nova recusaria esta tecla, mas ela continua valendo
    janela.project_manager.save_map(dois)
    assert janela.ativacao.definir_estado("Dois", "sessao") is True
    _responder_configuracao(monkeypatch, um.hotkey)
    antes = len(gui.calls)
    janela._configure_current_map()
    assert dois.hotkey == "F6", "a tecla anterior permanece"
    avisos = _avisos(gui, antes)
    assert avisos and avisos[0][1] == "Tecla não alterada" and "“Um”" in avisos[0][2] and "continua “F6”" in avisos[0][2], gui.calls[antes:]
    _responder_configuracao(monkeypatch, "CTRL+SHIFT+ALT+7")
    janela._configure_current_map()
    assert dois.hotkey == "CTRL+SHIFT+ALT+7" and parse_combo("CTRL+SHIFT+ALT+7") in _combos(janela) and parse_combo("F6") not in _combos(janela)


# ------------------------------------------------------------------------------------------------ 25.9 (T1): teclas reservadas
def _capturar_pergunta_da_tecla(monkeypatch, resposta):
    """Responde "⚙ Configurações da automação" como `_responder_configuracao`, mas escolhendo "Teclado" em "Como iniciar/parar"
    (para a pergunta da tecla aparecer) e guardando o que ela mostrou."""
    _responder_configuracao(monkeypatch, resposta)
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(
        lambda parent, titulo, rotulo, itens, atual=0, editavel=False: (itens[0] if titulo.startswith("Como iniciar") else itens[atual], True)))
    vistos = []
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: (vistos.append((a, k)), (resposta, True))[1]))
    return vistos


def test_uma_tecla_reservada_digitada_na_configuracao_e_recusada_com_o_motivo_e_o_resto_segue(abrir_janela, monkeypatch, gui):   # TEC-11
    janela = abrir_janela()
    mapa = _nova_automacao(janela, monkeypatch, "Mapa")
    antes_da_tecla = mapa.hotkey
    _responder_configuracao(monkeypatch, "CTRL+T")
    antes = len(gui.calls)
    janela._configure_current_map()
    assert mapa.hotkey == antes_da_tecla, "a tecla anterior permanece"
    avisos = _avisos(gui, antes)
    assert avisos and avisos[0][1] == "Tecla não alterada" and "abre uma nova aba do navegador" in avisos[0][2], gui.calls[antes:]
    assert "Sugestão: CTRL+SHIFT+ALT+2." in avisos[0][2], "a sugestão pula a combinação que o próprio mapa já usa"


def test_deixar_a_pergunta_da_tecla_em_branco_diz_que_nenhuma_tecla_foi_digitada_e_mantem_a_do_mapa(abrir_janela, monkeypatch, gui):  # D11
    janela = abrir_janela()
    mapa = _nova_automacao(janela, monkeypatch, "Mapa")
    antes_da_tecla = mapa.hotkey
    _responder_configuracao(monkeypatch, "")
    antes = len(gui.calls)
    janela._configure_current_map()
    assert mapa.hotkey == antes_da_tecla, 'vazio não vira "=" (tecla que nunca dispara): a tecla anterior permanece'
    avisos = _avisos(gui, antes)
    assert avisos and avisos[0][1] == "Tecla não alterada" and "Nenhuma tecla foi digitada" in avisos[0][2], gui.calls[antes:]


def test_a_pergunta_da_tecla_sugere_uma_combinacao_livre_e_nao_o_sinal_de_igual(abrir_janela, monkeypatch):       # D11
    janela = abrir_janela()
    mapa = _nova_automacao(janela, monkeypatch, "Mapa")
    mapa.hotkey = "MOUSE_X1"  # sem tecla de teclado: a pergunta abre com o que for sugerido
    janela.project_manager.save_map(mapa)
    vistos = _capturar_pergunta_da_tecla(monkeypatch, "CTRL+SHIFT+ALT+5")
    janela._configure_current_map()
    assert vistos, "a pergunta da tecla foi feita"
    argumentos, nomeados = vistos[0]
    assert nomeados.get("text") == "CTRL+SHIFT+ALT+1" and "CTRL+SHIFT+ALT+1" in argumentos[2], vistos
    assert "=, F6 ou CTRL+F6" not in argumentos[2], "o exemplo antigo é de teclas que a regra recusa"


def test_o_botao_lateral_do_mouse_escolhido_na_configuracao_vale_com_o_aviso_na_barra_de_status(abrir_janela, monkeypatch):
    janela = abrir_janela()
    mapa = _nova_automacao(janela, monkeypatch, "Mapa")
    # Só a pergunta "Como iniciar/parar" muda de resposta (o lateral 1 do mouse); nas outras vale o que já estava.
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(
        lambda parent, titulo, rotulo, itens, atual=0, editavel=False:
        (next(i for i in itens if "(X1)" in i) if titulo.startswith("Como iniciar") else itens[atual], True)))
    monkeypatch.setattr(QInputDialog, "getInt", staticmethod(lambda parent, titulo, rotulo, valor=0, *a, **k: (valor, True)))
    monkeypatch.setattr(QInputDialog, "getDouble", staticmethod(lambda parent, titulo, rotulo, valor=0.0, *a, **k: (valor, True)))
    mensagens, original = [], janela.status_bar.showMessage
    monkeypatch.setattr(janela.status_bar, "showMessage", lambda texto, prazo=0: (mensagens.append(texto), original(texto, prazo))[1])
    janela._configure_current_map()
    assert mapa.hotkey == "MOUSE_X1"
    assert any("Voltar e Avançar" in m for m in mensagens), mensagens
