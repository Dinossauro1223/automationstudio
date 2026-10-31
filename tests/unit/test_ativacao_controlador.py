"""O controlador da ativação (automationstudio/ativacao_ui.py) com uma janela de mentira.

O controlador é a cola entre a lógica (ativacao.py) e a janela principal: lê os mapas e as configurações NA HORA (a pasta de
dados pode ser trocada e a janela recria o gerenciador de configurações), grava a preferência no banco, refaz os atalhos
globais e mostra os avisos. Aqui a janela é um objeto simples com só o que o controlador usa, o gerenciador de atalhos é o
verdadeiro (com um monitor falso) e as configurações são as de verdade (AppSettings numa pasta temporária). Os diálogos
saem por `avisar`, que o teste troca por uma lista.

Critérios da ficha (md/ESPEC_ATIVACAO_25_8.md): MAP-01 a MAP-03, HK-01, ATV-01, ATV-03, ATV-05 (a parte sem widgets).
"""
import json
from types import SimpleNamespace

from automationstudio.ativacao import ESTADO_DESATIVADO as DESAT, ESTADO_SEMPRE as SEMPRE, ESTADO_SESSAO as SESSAO
from automationstudio.project import AppSettings
from testsupport.janela_falsa import REAIS, JanelaFalsa, abrir as _abrir


def _janela(pasta, mapas=None):
    return JanelaFalsa(pasta, REAIS if mapas is None else mapas)


def _gravado(pasta) -> dict:
    return AppSettings(pasta).get_map_activation()


# ------------------------------------------------------------------------------------------------ abertura
def test_a_primeira_abertura_grava_a_migracao_uma_unica_vez(tmp_path, monkeypatch):
    janela = _janela(tmp_path)
    gravacoes, original = [], janela.settings.set_map_activation
    monkeypatch.setattr(janela.settings, "set_map_activation", lambda dados: (gravacoes.append(dados), original(dados)))
    janela.ativacao.sincronizar()
    assert len(gravacoes) == 1
    assert _gravado(tmp_path) == {"migrated": True, "prefs": {n: SEMPRE for n in REAIS}}
    janela.ativacao.sincronizar()
    assert len(gravacoes) == 1, "sincronizar de novo não regrava nada"
    assert janela.avisos == []


def test_os_tres_mapas_reais_abrem_sempre_ativos_e_cada_tecla_dispara_o_seu_mapa(tmp_path):                       # MAP-04
    janela = _abrir(tmp_path)
    assert {n: janela.ativacao.descrever(n).estado for n in REAIS} == {n: SEMPRE for n in REAIS}
    janela.clicar("x1"); janela.apertar("="); janela.clicar("x2")
    janela.apertar("F12")
    assert janela.disparos == ["map:Click genshin", "map:Exemplo — Primeira automação", "map:Flins combo", "control:emergency"]
    assert janela.avisos == []


def test_mapa_novo_nasce_ativo_na_sessao_e_ao_reabrir_volta_desativado(tmp_path):                                  # MAP-02
    janela = _abrir(tmp_path)
    janela.project_manager.maps["Novo"] = SimpleNamespace(name="Novo", hotkey="F6")
    janela.ativacao.sincronizar()
    janela._register_all_hotkeys()
    assert janela.ativacao.descrever("Novo").estado == SESSAO
    janela.apertar("F6")
    assert janela.disparos == ["map:Novo"]
    assert _gravado(tmp_path)["prefs"]["Novo"] == DESAT
    reaberta = _abrir(tmp_path, {**REAIS, "Novo": "F6"})
    assert reaberta.ativacao.descrever("Novo").estado == DESAT
    reaberta.apertar("F6")
    assert reaberta.disparos == [], "o mapa que só valia na sessão anterior abre desativado"


def test_registrar_sozinho_ja_trata_o_mapa_que_chegou_depois_da_abertura(tmp_path):                                  # MAP-02
    janela = _abrir(tmp_path)
    janela.project_manager.maps["Novo"] = SimpleNamespace(name="Novo", hotkey="F6")
    janela._register_all_hotkeys()  # sem `sincronizar` antes: `registrar` alinha o estado por conta própria
    assert janela.ativacao.descrever("Novo").estado == SESSAO and _gravado(tmp_path)["prefs"]["Novo"] == DESAT
    janela.apertar("F6")
    assert janela.disparos == ["map:Novo"]


# ------------------------------------------------------------------------------------------------ MAP-03
def test_a_tecla_de_um_mapa_desativado_nao_dispara_nada_e_a_dos_outros_continua(tmp_path):                         # MAP-03
    janela = _abrir(tmp_path)
    assert janela.ativacao.definir_estado("Flins combo", DESAT) is True
    janela.clicar("x2")
    assert janela.disparos == []
    janela.clicar("x1")
    assert janela.disparos == ["map:Click genshin"]
    assert _gravado(tmp_path)["prefs"]["Flins combo"] == DESAT
    assert janela.registros >= 2, "mudar o estado refaz os atalhos globais"


def test_a_guarda_da_janela_ignora_um_disparo_que_ja_estava_na_fila_de_um_mapa_desativado(tmp_path):              # MAP-03
    janela = _abrir(tmp_path)
    janela.ativacao.definir_estado("Click genshin", DESAT)
    assert janela.ativacao.acao_permitida("map:Click genshin") is False
    assert janela.ativacao.acao_permitida("map:Flins combo") is True
    assert janela.ativacao.acao_permitida("map:Nunca existiu") is False
    for acao in ("control:emergency", "control:pause", "record:toggle", "record:cancel"):
        assert janela.ativacao.acao_permitida(acao) is True


def test_de_sempre_para_so_nesta_sessao_avisa_na_barra_de_status_e_grava_desativado(tmp_path):                      # MAP-01
    janela = _abrir(tmp_path)
    assert janela.ativacao.definir_estado("Flins combo", SESSAO) is True
    assert janela.status == ["Na próxima abertura do programa esta automação ficará desativada."]
    assert janela.ativacao.descrever("Flins combo").estado == SESSAO and _gravado(tmp_path)["prefs"]["Flins combo"] == DESAT
    janela.clicar("x2")
    assert janela.disparos == ["map:Flins combo"], "na sessão atual a tecla continua funcionando"


def test_mudar_o_estado_atualiza_o_rotulo_e_o_painel_da_janela(tmp_path):
    janela = _abrir(tmp_path)
    antes = janela.rotulos
    janela.ativacao.definir_estado("Flins combo", DESAT)
    assert janela.rotulos == antes + 1


# ------------------------------------------------------------------------------------------------ HK-01 e ATV-01
def test_um_conflito_antigo_e_avisado_uma_unica_vez_e_volta_a_ser_avisado_se_reaparecer(tmp_path):                   # HK-01
    janela = _abrir(tmp_path, {"A": "=", "B": "="})  # dados de uma versão antiga: os dois viram "sempre"
    assert janela.avisos == [("Conflito de atalhos", "Alguns atalhos não foram ativados por conflito:\n\n"
                              "A tecla “=” de “B” já é usada pela automação ativa “A”.")]
    janela._register_all_hotkeys(); janela._register_all_hotkeys()
    assert len(janela.avisos) == 1, "o mesmo conflito não é avisado de novo a cada registro"
    janela.apertar("=")
    assert janela.disparos == ["map:A"], "o primeiro pelo nome fica com a tecla, como sempre foi"
    janela.project_manager.maps["B"].hotkey = "F6"
    janela._register_all_hotkeys()
    assert len(janela.avisos) == 1
    janela.project_manager.maps["B"].hotkey = "="
    janela._register_all_hotkeys()
    assert len(janela.avisos) == 2, "o conflito sumiu e voltou: é um aviso novo"


def test_o_atalho_de_controle_fica_com_a_tecla_mesmo_quando_um_mapa_usa_a_mesma(tmp_path):                          # ATV-01
    janela = _abrir(tmp_path, {"A": "F12", "B": "F6"})
    janela.apertar("F12"); janela.apertar("F6")
    assert janela.disparos == ["control:emergency", "map:B"], "a parada de emergência nunca pode ser engolida por um mapa"
    assert janela.avisos[0][1].endswith("A tecla “F12” de “A” é a do atalho de controle “Parar tudo agora”.")


def test_ativar_com_tecla_ocupada_e_recusado_com_a_mensagem_e_sem_gravar_nada(tmp_path):                            # HK-01
    janela = _abrir(tmp_path, {"Exemplo": "="})
    janela.project_manager.maps["Novo"] = SimpleNamespace(name="Novo", hotkey="=")
    janela.ativacao.sincronizar()  # Novo nasce desativado: a tecla é do Exemplo
    assert janela.avisos[-1] == ("Atalho em conflito", "A tecla “=” de “Novo” já é usada pela automação ativa “Exemplo”. "
                                 "Por isso “Novo” começou desativada.")
    antes, registros = _gravado(tmp_path), janela.registros
    assert janela.ativacao.definir_estado("Novo", SESSAO) is False
    assert janela.avisos[-1] == ("Não foi possível ativar", "A tecla “=” de “Novo” já é usada pela automação ativa “Exemplo”. "
                                 "Desative “Exemplo” ou mude uma das teclas em ⚙ Configurações da automação.")
    assert janela.ativacao.descrever("Novo").estado == DESAT and _gravado(tmp_path) == antes and janela.registros == registros
    janela.apertar("=")
    assert janela.disparos == ["map:Exemplo"]


def test_desativar_o_outro_mapa_libera_a_tecla_para_ativar(tmp_path):
    janela = _abrir(tmp_path, {"Exemplo": "="})
    janela.project_manager.maps["Novo"] = SimpleNamespace(name="Novo", hotkey="=")
    janela.ativacao.sincronizar()
    assert janela.ativacao.definir_estado("Exemplo", DESAT) is True
    assert janela.ativacao.definir_estado("Novo", SEMPRE) is True
    janela.apertar("=")
    assert janela.disparos == ["map:Novo"] and _gravado(tmp_path)["prefs"] == {"Exemplo": DESAT, "Novo": SEMPRE}


# ------------------------------------------------------------------------------------------------ mudar a tecla
def test_validar_tecla_recusa_tecla_ocupada_de_mapa_ativo_e_mantem_a_atual(tmp_path):                                # HK-01
    janela = _abrir(tmp_path, {"Exemplo": "=", "Outro": "F6"})
    assert janela.ativacao.validar_tecla("Outro", "=") == ("A tecla “=” de “Outro” já é usada pela automação ativa “Exemplo”. "
                                                          "A tecla de “Outro” continua “F6”. Escolha outra tecla ou desative “Exemplo”.")
    assert janela.ativacao.validar_tecla("Outro", "F12") == ("A tecla “F12” de “Outro” é a do atalho de controle “Parar tudo agora”. "
                                                            "A tecla de “Outro” continua “F6”. Escolha outra tecla.")
    assert janela.ativacao.validar_tecla("Outro", "F7") == ""
    assert janela.ativacao.validar_tecla("Outro", "f6") == "", "a própria tecla, escrita de outro jeito, não é conflito"


def test_validar_tecla_recusa_tecla_que_nao_existe_em_qualquer_estado(tmp_path):
    janela = _abrir(tmp_path, {"Exemplo": "=", "Outro": "F6"})
    janela.ativacao.definir_estado("Outro", DESAT)
    esperado = ("A tecla “+” não é válida. Digite uma tecla ou uma combinação, como F6 ou CTRL+F6. "
                "A tecla de “Outro” continua “F6”.")
    assert janela.ativacao.validar_tecla("Outro", "+") == esperado
    assert janela.ativacao.validar_tecla("Exemplo", "") != "", "uma tecla vazia também não é uma tecla"


def test_mudar_a_tecla_de_um_mapa_ativo_para_uma_tecla_livre_muda(tmp_path):                                          # HK-01
    janela = _abrir(tmp_path, {"Exemplo": "=", "Outro": "F6"})
    outro = janela.project_manager.maps["Outro"]
    assert janela.ativacao.mudar_tecla(outro, "F7") is True
    assert outro.hotkey == "F7" and janela.avisos == []


def test_mudar_a_tecla_para_uma_ocupada_avisa_o_motivo_e_o_mapa_fica_com_a_que_tinha(tmp_path):                      # HK-01
    janela = _abrir(tmp_path, {"Exemplo": "=", "Outro": "F6"})
    outro = janela.project_manager.maps["Outro"]
    assert janela.ativacao.mudar_tecla(outro, "=") is False
    assert outro.hotkey == "F6"
    assert janela.avisos == [("Tecla não alterada", "A tecla “=” de “Outro” já é usada pela automação ativa “Exemplo”. "
                                                    "A tecla de “Outro” continua “F6”. Escolha outra tecla ou desative “Exemplo”.")]
    assert janela.ativacao.mudar_tecla(outro, "F12") is False and outro.hotkey == "F6", "F12 é a parada de emergência"
    assert len(janela.avisos) == 2


def test_mudar_a_tecla_para_uma_que_nao_existe_avisa_e_mantem_a_anterior(tmp_path):
    janela = _abrir(tmp_path, {"Outro": "F6"})
    outro = janela.project_manager.maps["Outro"]
    assert janela.ativacao.mudar_tecla(outro, "+") is False and outro.hotkey == "F6"
    assert janela.avisos[0][0] == "Tecla não alterada" and "não é válida" in janela.avisos[0][1]


def test_mudar_a_tecla_de_um_mapa_desativado_aceita_a_ocupada_e_o_conflito_aparece_ao_ativar(tmp_path):
    janela = _abrir(tmp_path, {"Exemplo": "=", "Outro": "F6"})
    janela.ativacao.definir_estado("Outro", DESAT)
    outro = janela.project_manager.maps["Outro"]
    assert janela.ativacao.mudar_tecla(outro, "=") is True and outro.hotkey == "=" and janela.avisos == []
    assert janela.ativacao.definir_estado("Outro", SESSAO) is False


def test_um_mapa_desativado_pode_receber_qualquer_tecla_e_o_conflito_so_vale_ao_ativar(tmp_path):
    janela = _abrir(tmp_path, {"Exemplo": "=", "Outro": "F6"})
    janela.ativacao.definir_estado("Outro", DESAT)
    assert janela.ativacao.validar_tecla("Outro", "=") == ""
    janela.project_manager.maps["Outro"].hotkey = "="
    assert janela.ativacao.definir_estado("Outro", SESSAO) is False, "o conflito aparece quando for ativar"


# ------------------------------------------------------------------------------------------------ excluir
def test_excluir_um_mapa_apaga_a_preferencia_do_banco(tmp_path):                                                      # ATV-03
    janela = _abrir(tmp_path)
    janela.ativacao.esquecer("Flins combo")
    assert "Flins combo" not in _gravado(tmp_path)["prefs"] and set(_gravado(tmp_path)["prefs"]) == {"Click genshin", "Exemplo — Primeira automação"}
    janela.ativacao.esquecer("Nunca existiu")  # não é erro nem regrava
    assert set(_gravado(tmp_path)["prefs"]) == {"Click genshin", "Exemplo — Primeira automação"}


# ------------------------------------------------------------------------------------------------ pasta de dados trocada
def test_trocar_a_pasta_de_dados_passa_a_usar_o_estado_do_banco_novo(tmp_path):
    janela = _abrir(tmp_path / "a")
    janela.ativacao.definir_estado("Flins combo", DESAT)
    antigo = _gravado(tmp_path / "a")
    # O editor de configurações troca `settings` e `project_manager` por objetos novos (command_editor.py).
    janela.settings = AppSettings(tmp_path / "b")
    janela.project_manager = SimpleNamespace(maps={"Outro": SimpleNamespace(name="Outro", hotkey="F6")})
    janela.ativacao.sincronizar()
    assert janela.ativacao.descrever("Outro").estado == SEMPRE, "banco novo sem registro: os mapas dele são os de antes e valem 'sempre'"
    assert janela.ativacao.descrever("Flins combo").estado == DESAT and "Flins combo" not in _gravado(tmp_path / "b")["prefs"]
    assert _gravado(tmp_path / "a") == antigo, "o banco da pasta anterior não é tocado"


# ------------------------------------------------------------------------------------------------ rótulo
def test_o_rotulo_da_tecla_no_editor_fica_curto_e_so_diz_o_motivo_quando_a_tecla_nao_inicia_a_automacao(tmp_path):
    # A linha de baixo do editor é estreita: no caso normal o rótulo é o de sempre; o detalhe fica na faixa de ativação.
    janela = _abrir(tmp_path, {"A": "=", "B": "=", "C": "", "D": "F7", "E": "+"})
    janela.ativacao.definir_estado("D", DESAT)
    rotulo = {n: janela.ativacao.rotulo_da_tecla(janela.project_manager.maps[n]) for n in "ABCDE"}
    assert rotulo == {
        "A": "Tecla para iniciar/parar: =",
        "B": "Tecla para iniciar/parar: = (em conflito)",
        "C": "Tecla para iniciar/parar: —",
        "D": "Tecla para iniciar/parar: F7 (desativada)",
        "E": "Tecla para iniciar/parar: + (inválida)"}


def test_o_rotulo_de_um_mapa_ativo_so_nesta_sessao_e_o_de_sempre(tmp_path):
    janela = _abrir(tmp_path, {"A": "="})
    janela.ativacao.definir_estado("A", SESSAO)
    assert janela.ativacao.rotulo_da_tecla(janela.project_manager.maps["A"]) == "Tecla para iniciar/parar: ="


# ------------------------------------------------------------------------------------------------ o que vai ao banco
def test_o_banco_so_recebe_json_com_sempre_ou_desativado(tmp_path):
    janela = _abrir(tmp_path)
    janela.project_manager.maps["Novo"] = SimpleNamespace(name="Novo", hotkey="F6")
    janela.ativacao.sincronizar()
    janela.ativacao.definir_estado("Flins combo", SESSAO)
    dados = json.loads(json.dumps(_gravado(tmp_path)))
    assert set(dados["prefs"].values()) <= {SEMPRE, DESAT} and dados["migrated"] is True
