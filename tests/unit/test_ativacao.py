"""Ativação por mapa (25.8, item 2.3 do plano 25.7): estados, conflito de tecla, migração e registro dos atalhos.

Especificação: md/ESPEC_ATIVACAO_25_8.md. Critérios do plano: MAP-01 a MAP-04 e HK-01, mais os ATV-01 a ATV-04 desta ficha.
É lógica pura (`automationstudio/ativacao.py`): nenhum teste daqui precisa do Qt, e os atalhos são "apertados" num monitor
falso, como em tests/engine/test_hotkeys.py.

O que cada grupo trava:
  * planos: quem leva cada tecla (mapa ativo, atalho de controle), equivalência de escrita, ordem e mensagens;
  * estados: as três situações, o que é gravado, o que só vale na sessão, a migração dos mapas que já existem;
  * recusas: ativar ou mudar a tecla para uma tecla ocupada nunca muda nada e diz de quem é a tecla;
  * leitor tolerante: lixo no banco de configurações nunca derruba a abertura do programa.
"""
import json
import sqlite3

import pytest

from automationstudio import ativacao as atv
from automationstudio.ativacao import AtivacaoMapas, montar_plano, registrar_plano
from automationstudio.core import map_from_json, parse_combo
from automationstudio.input_system import GlobalHotkeyManager, HotkeyConflictError
from testsupport.fakes import FakeMonitor

SESSAO, SEMPRE, DESAT = atv.ESTADO_SESSAO, atv.ESTADO_SEMPRE, atv.ESTADO_DESATIVADO
# Os padrões de AppSettings.get_control_hotkeys().
CONTROLES = {"pause": "F9", "resume": "F10", "emergency": "F12", "record_toggle": "F8", "record_cancel": "F11"}
ACOES_DE_CONTROLE = {"control:emergency": "F12", "control:pause": "F9", "control:resume": "F10",
                     "record:toggle": "F8", "record:cancel": "F11"}
# Os 3 mapas reais (tests/data/legacy_maps.json.gz): nome -> tecla.
REAIS = {"Click genshin": "MOUSE_X1", "Exemplo — Primeira automação": "=", "Flins combo": "MOUSE_X2"}
JA_MIGRADO = {"migrated": True, "prefs": {}}


def _acoes(plano) -> dict[str, str]:
    """ação -> tecla, como o plano manda registrar."""
    return {r.acao: r.tecla for r in plano.registros}


def _migrada(mapas=None) -> AtivacaoMapas:
    """Estado depois da primeira abertura da 25.8: todos os mapas dados já existiam (viram "sempre")."""
    estado = AtivacaoMapas()
    estado.sincronizar(REAIS if mapas is None else mapas, CONTROLES)
    return estado


# ------------------------------------------------------------------------------------------------ textos e constantes
def test_ha_tres_estados_exclusivos_cada_um_com_rotulo_e_ajuda():
    assert atv.ESTADOS == (SESSAO, SEMPRE, DESAT)
    assert [atv.ROTULOS[e] for e in atv.ESTADOS] == ["Ativo nesta sessão", "Sempre ativo ao iniciar", "Desativado"]
    assert all(atv.AJUDAS[e].strip() for e in atv.ESTADOS)
    assert len({atv.AJUDAS[e] for e in atv.ESTADOS}) == 3


def test_os_cinco_atalhos_de_controle_tem_rotulo_e_a_acao_que_a_janela_entende():
    assert atv.ORDEM_CONTROLE == ("emergency", "pause", "resume", "record_toggle", "record_cancel")
    assert atv.ACAO_DO_CONTROLE == {"emergency": "control:emergency", "pause": "control:pause", "resume": "control:resume",
                                    "record_toggle": "record:toggle", "record_cancel": "record:cancel"}
    assert set(atv.ROTULOS_CONTROLE) == set(atv.ORDEM_CONTROLE) == set(CONTROLES)
    assert atv.ROTULOS_CONTROLE["emergency"] == "Parar tudo agora"


def test_a_ordem_dos_nomes_e_a_do_banco_sem_distincao_de_maiusculas_ascii():
    # `ORDER BY name COLLATE NOCASE` (project.py): só A-Z são igualadas às minúsculas; "Á" vem depois de "z". É a ordem em que
    # os mapas chegam à janela, e portanto a ordem em que, até a 25.6, o primeiro mapa a registrar levava a tecla repetida.
    # "Éb" e "éa": o SQLite NÃO iguala "É" a "é", então "Éb" vem antes (o Python, com casefold, poria "éa" antes).
    nomes = ["zebra", "Ágata", "Abacate", "banana", "Exemplo — Primeira automação", "Click genshin", "_x", "10", "Flins combo",
             "Éb", "éa", "ÁB", "áa"]
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE maps (name TEXT PRIMARY KEY)")
    con.executemany("INSERT INTO maps(name) VALUES (?)", [(n,) for n in nomes])
    do_banco = [linha[0] for linha in con.execute("SELECT name FROM maps ORDER BY name COLLATE NOCASE")]
    con.close()
    assert sorted(nomes, key=atv.ordem_dos_nomes) == do_banco


@pytest.mark.parametrize("texto,valida", [("F6", True), ("=", True), ("CTRL+F6", True), ("mouse_x1", True), (" F6 ", True),
                                          ("+", False), ("++", False), (" + ", False), ("", False), ("   ", False),
                                          (None, False), (7, False)],
                         ids=["f6", "igual", "combinacao", "mouse", "espacos", "mais", "dois-mais", "mais-espacos", "vazio",
                              "em-branco", "none", "numero"])
def test_tecla_valida_so_aceita_texto_que_vira_uma_combinacao(texto, valida):
    assert atv.tecla_valida(texto) is valida


# ------------------------------------------------------------------------------------------------ plano: quem leva a tecla
def test_so_mapas_ativos_registram_cada_um_com_a_sua_tecla_e_os_controles_vem_junto():
    plano = montar_plano({"A": "F6", "B": "F7", "C": "F5"}, {"A": SESSAO, "B": SEMPRE, "C": DESAT}, CONTROLES)
    assert _acoes(plano) == {"map:A": "F6", "map:B": "F7", **ACOES_DE_CONTROLE}
    assert plano.conflitos == [] and plano.invalidos == [] and plano.sem_tecla == []


def test_mapa_desativado_nao_ocupa_a_tecla_de_ninguem():
    plano = montar_plano({"A": "=", "B": "="}, {"A": DESAT, "B": SESSAO}, CONTROLES)
    assert _acoes(plano)["map:B"] == "=" and "map:A" not in _acoes(plano)
    assert plano.conflitos == []


def test_mapa_sem_estado_informado_conta_como_desativado():
    plano = montar_plano({"A": "F6", "B": "F7"}, {"B": SEMPRE, "C": SEMPRE}, CONTROLES)
    assert "map:A" not in _acoes(plano) and _acoes(plano)["map:B"] == "F7"
    assert "map:C" not in _acoes(plano), "um estado sem mapa correspondente não registra nada"


@pytest.mark.parametrize("tecla", [None, "", "   ", 123, ["F6"]], ids=["none", "vazia", "em-branco", "numero", "lista"])
def test_mapa_ativo_sem_tecla_nao_ocupa_nada_nem_conflita(tecla):
    plano = montar_plano({"A": tecla, "B": "F6"}, {"A": SESSAO, "B": SESSAO}, CONTROLES)
    assert plano.sem_tecla == ["A"] and plano.conflitos == [] and plano.invalidos == []
    assert _acoes(plano)["map:B"] == "F6" and "map:A" not in _acoes(plano)


@pytest.mark.parametrize("tecla", ["+", "++", " + "], ids=["mais", "dois-mais", "mais-com-espacos"])
def test_tecla_invalida_nao_derruba_o_plano_e_e_apontada(tecla):
    # Até a 25.6, uma tecla assim levantava ValueError dentro de `_register_all_hotkeys` e a janela nem abria.
    plano = montar_plano({"Novo": tecla, "B": "F6"}, {"Novo": SESSAO, "B": SESSAO}, CONTROLES)
    assert [(i.nome, i.e_mapa) for i in plano.invalidos] == [("Novo", True)]
    assert plano.invalidos[0].mensagem == "A tecla “" + tecla.strip() + "” de “Novo” não é válida; a automação ficou sem atalho."
    assert "map:Novo" not in _acoes(plano) and _acoes(plano)["map:B"] == "F6"


def test_atalho_de_controle_com_tecla_invalida_e_apontado_e_os_outros_seguem():
    plano = montar_plano({}, {}, {**CONTROLES, "pause": "+"})
    assert [(i.nome, i.e_mapa) for i in plano.invalidos] == [("Pausar automação", False)]
    assert plano.invalidos[0].mensagem == "O atalho de controle “Pausar automação” tem uma tecla inválida (“+”) e não foi ativado."
    assert "control:pause" not in _acoes(plano) and _acoes(plano)["control:emergency"] == "F12"


def test_atalho_de_controle_vazio_ou_desconhecido_e_ignorado():
    plano = montar_plano({}, {}, {"pause": "", "resume": None, "emergency": "F12", "inexistente": "F1"})
    assert _acoes(plano) == {"control:emergency": "F12"} and plano.invalidos == [] and plano.conflitos == []


@pytest.mark.parametrize("a,b", [("ctrl+f6", "CTRL+F6"), ("F6+Ctrl", "ctrl+f6"), ("CTRL + F6", "ctrl+f6"),
                                 ("X1", "MOUSE_X1"), ("mouse_x2", "X2"), ("x1", "lateral1"), ("F6", " f6 ")],
                         ids=["caixa", "ordem", "espacos", "x1", "x2", "apelido", "bordas"])
def test_teclas_escritas_de_jeitos_diferentes_mas_equivalentes_sao_a_mesma_tecla(a, b):
    plano = montar_plano({"A": a, "B": b}, {"A": SESSAO, "B": SESSAO}, {})
    assert [r.acao for r in plano.registros] == ["map:A"]
    assert [(c.perdedor, c.vencedor) for c in plano.conflitos] == [("B", "A")]


def test_teclas_diferentes_nao_conflitam_nem_quando_uma_contem_a_outra():
    # Observação registrada na ficha (seção 6): F8 e CTRL+F8 disparam juntas, e hoje já é assim; o plano não as chama de iguais.
    plano = montar_plano({"A": "F8", "B": "CTRL+F8"}, {"A": SESSAO, "B": SESSAO}, {})
    assert _acoes(plano) == {"map:A": "F8", "map:B": "CTRL+F8"} and plano.conflitos == []


def test_conflito_antigo_entre_mapas_ativos_a_ordem_do_nome_decide_e_nao_a_do_dicionario():
    estados = {"Banana": SEMPRE, "abacate": SEMPRE, "Cereja": SEMPRE}
    for ordem in (["Banana", "abacate", "Cereja"], ["Cereja", "Banana", "abacate"], ["abacate", "Cereja", "Banana"]):
        plano = montar_plano({n: "=" for n in ordem}, estados, {})
        assert [r.acao for r in plano.registros] == ["map:abacate"], ordem
        assert [(c.perdedor, c.vencedor) for c in plano.conflitos] == [("Banana", "abacate"), ("Cereja", "abacate")], ordem


def test_o_plano_diz_quem_tem_cada_tecla_e_o_que_cada_mapa_ganhou_ou_perdeu():
    plano = montar_plano({"A": "ctrl+f6", "B": "F6+CTRL", "C": "+", "D": ""},
                         {"A": SESSAO, "B": SESSAO, "C": SESSAO, "D": SESSAO}, CONTROLES)
    assert plano.dono("F6+CTRL").acao == "map:A" and plano.dono("F12").acao == "control:emergency"
    assert plano.dono("F7") is None and plano.dono("+") is None and plano.dono("") is None and plano.dono(None) is None
    assert plano.registro_do_mapa("A").tecla == "ctrl+f6" and plano.registro_do_mapa("B") is None
    assert plano.conflito_do_mapa("B").vencedor == "A" and plano.conflito_do_mapa("A") is None
    assert plano.invalido_do_mapa("C").tecla == "+" and plano.invalido_do_mapa("A") is None
    assert plano.sem_tecla == ["D"]


# ------------------------------------------------------------------------------------------------ HK-01: as mensagens
def test_a_mensagem_de_conflito_entre_mapas_nomeia_as_duas_automacoes_e_a_tecla():                          # HK-01
    plano = montar_plano({"Exemplo": "=", "Novo": "="}, {"Exemplo": SEMPRE, "Novo": SEMPRE}, {})
    assert [c.mensagem for c in plano.conflitos] == ["A tecla “=” de “Novo” já é usada pela automação ativa “Exemplo”."]
    assert plano.mensagens() == [plano.conflitos[0].mensagem]


def test_a_mensagem_de_conflito_com_atalho_de_controle_nomeia_o_mapa_a_tecla_e_o_atalho():                   # HK-01
    plano = montar_plano({"Novo": "F12"}, {"Novo": SESSAO}, CONTROLES)
    assert [c.mensagem for c in plano.conflitos] == ["A tecla “F12” de “Novo” é a do atalho de controle “Parar tudo agora”."]


def test_a_mensagem_usa_a_tecla_como_o_perdedor_a_escreveu():                                                  # HK-01
    plano = montar_plano({"Exemplo": "ctrl+f6", "Novo": "F6 + CTRL"}, {"Exemplo": SEMPRE, "Novo": SEMPRE}, {})
    assert plano.conflitos[0].mensagem == "A tecla “F6 + CTRL” de “Novo” já é usada pela automação ativa “Exemplo”."


def test_o_atalho_de_controle_nunca_perde_a_tecla_para_um_mapa_mesmo_com_nome_que_vem_antes():                # ATV-01
    plano = montar_plano({"A": "F12", "B": "f9"}, {"A": SEMPRE, "B": SEMPRE}, CONTROLES)
    assert _acoes(plano)["control:emergency"] == "F12" and _acoes(plano)["control:pause"] == "F9"
    assert "map:A" not in _acoes(plano) and "map:B" not in _acoes(plano)
    assert [(c.perdedor, c.perdedor_e_mapa, c.vencedor, c.vencedor_e_mapa) for c in plano.conflitos] == \
        [("A", True, "Parar tudo agora", False), ("B", True, "Pausar automação", False)]


def test_a_emergencia_vem_primeiro_entre_os_atalhos_de_controle():                                             # ATV-01
    plano = montar_plano({}, {}, {**CONTROLES, "pause": "F12"})
    assert _acoes(plano)["control:emergency"] == "F12" and "control:pause" not in _acoes(plano)
    assert [c.mensagem for c in plano.conflitos] == [
        "Os atalhos de controle “Pausar automação” e “Parar tudo agora” usam a mesma tecla “F12”; só “Parar tudo agora” foi ativado."]


def test_a_prioridade_entre_os_atalhos_de_controle_e_a_ordem_da_lista():                                       # ATV-01
    plano = montar_plano({}, {}, {chave: "F1" for chave in CONTROLES})
    assert [r.acao for r in plano.registros] == ["control:emergency"]
    assert [c.perdedor for c in plano.conflitos] == ["Pausar automação", "Continuar automação",
                                                     "Iniciar/finalizar gravação", "Cancelar gravação"]


# ------------------------------------------------------------------------------------------------ registro no gerente
def test_so_o_mapa_ativo_dispara_pela_tecla_e_o_desativado_nao_dispara_nada():                                  # MAP-03 (lógica)
    monitor, disparos = FakeMonitor(), []
    gerente = GlobalHotkeyManager(monitor)
    plano = montar_plano({"Ligado": "F7", "Desligado": "F6"}, {"Ligado": SESSAO, "Desligado": DESAT}, CONTROLES)
    assert registrar_plano(plano, gerente, lambda acao: (lambda: disparos.append(acao))) == []
    gerente.start()
    monitor.press("F6"); monitor.release("F6")
    assert disparos == [], "a tecla de um mapa desativado não pode iniciar nada"
    monitor.press("F7"); monitor.release("F7")
    monitor.press("F12"); monitor.release("F12")
    assert disparos == ["map:Ligado", "control:emergency"]


def test_registrar_o_plano_refaz_tudo_do_zero_sem_atalho_fantasma():
    monitor, disparos = FakeMonitor(), []
    gerente = GlobalHotkeyManager(monitor)
    gerente.register("F6", lambda: disparos.append("sobra"))  # de um registro anterior
    gerente.start()
    registrar_plano(montar_plano({}, {}, {"emergency": "F12"}), gerente, lambda acao: (lambda: disparos.append(acao)))
    monitor.press("F6"); monitor.release("F6")
    monitor.press("F12")
    assert disparos == ["control:emergency"]


def test_registrar_o_plano_nao_levanta_quando_o_gerente_recusa_e_devolve_a_mensagem():
    class GerenteQueRecusa:
        def __init__(self):
            self.aceitas = []

        def clear(self):
            self.aceitas.clear()

        def register(self, tecla, callback):
            if tecla == "F7":
                raise HotkeyConflictError("recusado de propósito")
            self.aceitas.append(tecla)

    gerente = GerenteQueRecusa()
    plano = montar_plano({"A": "F6", "B": "F7"}, {"A": SESSAO, "B": SESSAO}, {})
    erros = registrar_plano(plano, gerente, lambda acao: (lambda: None))
    assert gerente.aceitas == ["F6"]
    assert erros == ["Não foi possível ativar a tecla “F7” de “B”: recusado de propósito"]


# ------------------------------------------------------------------------------------------------ MAP-04: os mapas reais
def test_os_tres_mapas_reais_abrem_sempre_ativos_e_registram_os_mesmos_atalhos_de_antes(legacy_maps):          # MAP-04
    mapas = {m.name: m.hotkey for m in map(map_from_json, legacy_maps.values())}
    assert mapas == REAIS, "os mapas reais mudaram: confira os testes de compatibilidade antes de seguir"
    estado = AtivacaoMapas()
    resultado = estado.sincronizar(mapas, CONTROLES)
    assert resultado.mudou and resultado.avisos == ()
    assert {n: estado.estado(n) for n in mapas} == {n: SEMPRE for n in mapas}
    plano = estado.plano(mapas, CONTROLES)
    # O que a `_register_all_hotkeys` da 25.6 registrava: todo mapa com tecla, depois os cinco atalhos de controle.
    de_antes = {parse_combo(t): f"map:{n}" for n, t in mapas.items()}
    de_antes.update({parse_combo(CONTROLES[chave]): acao for chave, acao in (
        ("pause", "control:pause"), ("resume", "control:resume"), ("emergency", "control:emergency"),
        ("record_toggle", "record:toggle"), ("record_cancel", "record:cancel"))})
    assert {parse_combo(r.tecla): r.acao for r in plano.registros} == de_antes
    assert plano.conflitos == [] and plano.invalidos == [] and plano.sem_tecla == []


# ------------------------------------------------------------------------------------------------ estados: migração e nascimento
def test_primeira_abertura_marca_todos_os_mapas_existentes_como_sempre_ativos():
    estado = AtivacaoMapas()
    resultado = estado.sincronizar(REAIS, CONTROLES)
    assert resultado.mudou and resultado.avisos == ()
    assert estado.dados() == {"migrated": True, "prefs": {n: SEMPRE for n in REAIS}}


def test_sincronizar_de_novo_nao_muda_nada():
    estado = _migrada()
    antes = estado.dados()
    resultado = estado.sincronizar(REAIS, CONTROLES)
    assert not resultado.mudou and resultado.avisos == () and estado.dados() == antes


def test_a_migracao_nao_atropela_uma_preferencia_ja_gravada():
    estado = AtivacaoMapas({"prefs": {"Flins combo": DESAT}})  # sem a marca de migração (dado incompleto)
    estado.sincronizar(REAIS, CONTROLES)
    assert estado.estado("Flins combo") == DESAT and estado.estado("Click genshin") == SEMPRE


def test_mapa_novo_nasce_ativo_so_nesta_sessao_e_a_preferencia_gravada_e_desativado():                         # ATV-03 / MAP-02
    estado = _migrada()
    mapas = {**REAIS, "Novo": "F6"}
    resultado = estado.sincronizar(mapas, CONTROLES)
    assert resultado.mudou and resultado.avisos == () and estado.estado("Novo") == SESSAO
    assert estado.dados()["prefs"]["Novo"] == DESAT
    reaberto = AtivacaoMapas(json.loads(json.dumps(estado.dados())))
    reaberto.sincronizar(mapas, CONTROLES)
    assert reaberto.estado("Novo") == DESAT and reaberto.estado("Click genshin") == SEMPRE


def test_mapa_novo_com_tecla_ocupada_por_mapa_ativo_nasce_desativado_e_avisa():                                  # ATV-03 / HK-01
    estado = _migrada()
    resultado = estado.sincronizar({**REAIS, "Novo": "="}, CONTROLES)
    assert estado.estado("Novo") == DESAT and estado.dados()["prefs"]["Novo"] == DESAT
    assert resultado.avisos == ("A tecla “=” de “Novo” já é usada pela automação ativa “Exemplo — Primeira automação”. "
                                "Por isso “Novo” começou desativada.",)


def test_mapa_novo_com_tecla_de_controle_nasce_desativado_e_avisa():                                             # ATV-03 / HK-01
    estado = _migrada()
    resultado = estado.sincronizar({**REAIS, "Novo": "F12"}, CONTROLES)
    assert estado.estado("Novo") == DESAT
    assert resultado.avisos == ("A tecla “F12” de “Novo” é a do atalho de controle “Parar tudo agora”. "
                                "Por isso “Novo” começou desativada.",)


def test_varios_mapas_novos_de_uma_vez_o_primeiro_pelo_nome_fica_com_a_tecla():                                  # ATV-03
    estado = _migrada()
    resultado = estado.sincronizar({**REAIS, "Zeta": "F6", "Alfa": "F6"}, CONTROLES)
    assert (estado.estado("Alfa"), estado.estado("Zeta")) == (SESSAO, DESAT)
    assert len(resultado.avisos) == 1 and "“Zeta”" in resultado.avisos[0] and "“Alfa”" in resultado.avisos[0]


def test_mapa_novo_sem_tecla_nasce_ativo_na_sessao_sem_aviso():                                                  # ATV-03
    estado = _migrada()
    resultado = estado.sincronizar({**REAIS, "Novo": ""}, CONTROLES)
    assert estado.estado("Novo") == SESSAO and resultado.avisos == ()


def test_a_tecla_de_um_mapa_desativado_nao_impede_o_nascimento_de_outro():
    estado = _migrada()
    estado.definir("Exemplo — Primeira automação", DESAT, REAIS, CONTROLES)
    resultado = estado.sincronizar({**REAIS, "Novo": "="}, CONTROLES)
    assert estado.estado("Novo") == SESSAO and resultado.avisos == ()


def test_sincronizar_nao_apaga_a_preferencia_de_um_mapa_que_nao_carregou_desta_vez():
    estado = _migrada()
    estado.sincronizar({"Exemplo — Primeira automação": "="}, CONTROLES)  # os outros dois estão no banco mas não abriram
    assert estado.dados()["prefs"] == {n: SEMPRE for n in REAIS}


# ------------------------------------------------------------------------------------------------ estados: transições
def test_ativar_so_nesta_sessao_a_partir_de_desativado_nao_toca_na_preferencia_gravada():                        # MAP-01
    estado = _migrada()
    estado.definir("Flins combo", DESAT, REAIS, CONTROLES)
    antes = estado.dados()
    resultado = estado.definir("Flins combo", SESSAO, REAIS, CONTROLES)
    assert resultado.ok and resultado.mensagem == "" and estado.estado("Flins combo") == SESSAO
    assert estado.dados() == antes and estado.dados()["prefs"]["Flins combo"] == DESAT


def test_de_sempre_para_so_nesta_sessao_a_preferencia_vira_desativado_e_o_usuario_e_avisado():                   # MAP-01 / D26
    estado = _migrada()
    resultado = estado.definir("Flins combo", SESSAO, REAIS, CONTROLES)
    assert resultado.ok and resultado.mensagem == "Na próxima abertura do programa esta automação ficará desativada."
    assert estado.estado("Flins combo") == SESSAO and estado.dados()["prefs"]["Flins combo"] == DESAT


def test_sempre_e_desativado_voltam_iguais_e_so_nesta_sessao_volta_desativado():                                 # MAP-02
    mapas = {**REAIS, "Outro": "F6", "Terceiro": "F7", "Quarto": "F5"}
    estado = _migrada()
    estado.sincronizar(mapas, CONTROLES)  # Outro, Terceiro e Quarto nascem "só nesta sessão"
    estado.definir("Outro", SEMPRE, mapas, CONTROLES)
    estado.definir("Click genshin", DESAT, mapas, CONTROLES)
    assert estado.estado("Terceiro") == SESSAO and estado.estado("Quarto") == SESSAO
    reaberto = AtivacaoMapas(json.loads(json.dumps(estado.dados(), ensure_ascii=False)))
    reaberto.sincronizar(mapas, CONTROLES)
    assert {n: reaberto.estado(n) for n in mapas} == {
        "Click genshin": DESAT, "Exemplo — Primeira automação": SEMPRE, "Flins combo": SEMPRE,
        "Outro": SEMPRE, "Terceiro": DESAT, "Quarto": DESAT}


def test_definir_o_mesmo_estado_nao_muda_nada_e_nao_avisa():
    estado = _migrada()
    antes = estado.dados()
    resultado = estado.definir("Flins combo", SEMPRE, REAIS, CONTROLES)
    assert resultado.ok and resultado.mensagem == "" and estado.dados() == antes


def test_de_so_nesta_sessao_para_sempre_grava_sempre_sem_aviso():
    mapas = {**REAIS, "Novo": "F6"}
    estado = _migrada()
    estado.sincronizar(mapas, CONTROLES)
    resultado = estado.definir("Novo", SEMPRE, mapas, CONTROLES)
    assert resultado.ok and resultado.mensagem == "" and estado.dados()["prefs"]["Novo"] == SEMPRE


def test_desativar_grava_desativado_de_qualquer_estado_e_nunca_e_recusado():
    mapas = {**REAIS, "Novo": "F6"}
    estado = _migrada()
    estado.sincronizar(mapas, CONTROLES)
    for nome in ("Novo", "Flins combo"):  # um "só nesta sessão" e um "sempre"
        resultado = estado.definir(nome, DESAT, mapas, CONTROLES)
        assert resultado.ok and resultado.mensagem == "" and estado.estado(nome) == DESAT
        assert estado.dados()["prefs"][nome] == DESAT


def test_definir_um_estado_que_nao_existe_e_erro_de_programacao():
    with pytest.raises(ValueError, match="estado"):
        _migrada().definir("Flins combo", "talvez", REAIS, CONTROLES)


# ------------------------------------------------------------------------------------------------ recusas (HK-01)
def test_ativar_com_tecla_ocupada_e_recusado_nomeando_as_duas_automacoes_e_nada_muda():                           # HK-01
    mapas = {"Exemplo": "=", "Novo": "="}
    estado = AtivacaoMapas(JA_MIGRADO)
    estado.sincronizar({"Exemplo": "="}, CONTROLES)  # Exemplo nasce ativo na sessão
    estado.definir("Exemplo", SEMPRE, mapas, CONTROLES)
    estado.sincronizar(mapas, CONTROLES)  # Novo: tecla ocupada, nasce desativado
    antes = estado.dados()
    for pedido in (SESSAO, SEMPRE):
        resultado = estado.definir("Novo", pedido, mapas, CONTROLES)
        assert not resultado.ok
        assert resultado.mensagem == ("A tecla “=” de “Novo” já é usada pela automação ativa “Exemplo”. "
                                      "Desative “Exemplo” ou mude uma das teclas em ⚙ Configurações da automação.")
        assert estado.estado("Novo") == DESAT and estado.dados() == antes


def test_ativar_com_tecla_de_atalho_de_controle_e_recusado():                                                     # HK-01
    mapas = {"Novo": "F12"}
    estado = AtivacaoMapas(JA_MIGRADO)
    estado.sincronizar(mapas, CONTROLES)
    resultado = estado.definir("Novo", SEMPRE, mapas, CONTROLES)
    assert not resultado.ok and estado.estado("Novo") == DESAT
    assert resultado.mensagem == ("A tecla “F12” de “Novo” é a do atalho de controle “Parar tudo agora”. "
                                  "Mude a tecla de “Novo” em ⚙ Configurações da automação.")


def test_ativar_um_mapa_nao_rouba_a_tecla_de_quem_ja_a_usa_mesmo_que_o_nome_venha_antes():                         # HK-01
    mapas = {"Zeta": "=", "Alfa": "="}
    estado = AtivacaoMapas({"migrated": True, "prefs": {"Zeta": SEMPRE, "Alfa": DESAT}})
    resultado = estado.definir("Alfa", SESSAO, mapas, CONTROLES)
    assert not resultado.ok and "“Zeta”" in resultado.mensagem and estado.estado("Alfa") == DESAT
    assert estado.plano(mapas, CONTROLES).registro_do_mapa("Zeta") is not None


def test_ativar_mapa_sem_tecla_ou_com_tecla_invalida_e_permitido():
    mapas = {"Sem": "", "Estranho": "+"}
    estado = AtivacaoMapas({"migrated": True, "prefs": {"Sem": DESAT, "Estranho": DESAT}})
    assert estado.definir("Sem", SESSAO, mapas, CONTROLES).ok and estado.definir("Estranho", SEMPRE, mapas, CONTROLES).ok


def test_mudar_a_tecla_de_um_mapa_para_uma_tecla_ocupada_e_apontado():                                            # HK-01
    mapas = {"Exemplo": "=", "Outro": "F6"}
    estado = _migrada(mapas)
    conflito = estado.verificar_tecla("Outro", "=", mapas, CONTROLES)
    assert conflito.mensagem == "A tecla “=” de “Outro” já é usada pela automação ativa “Exemplo”."
    assert estado.verificar_tecla("Outro", "F12", mapas, CONTROLES).vencedor == "Parar tudo agora"
    assert estado.verificar_tecla("Outro", "F7", mapas, CONTROLES) is None
    assert estado.verificar_tecla("Outro", "f6", mapas, CONTROLES) is None, "a própria tecla do mapa nunca conflita com ele"
    assert estado.verificar_tecla("Outro", "MOUSE_X1", mapas, CONTROLES) is None
    assert estado.verificar_tecla("Outro", "", mapas, CONTROLES) is None and estado.verificar_tecla("Outro", "+", mapas, CONTROLES) is None


def test_mapa_desativado_nao_e_considerado_dono_da_tecla_ao_verificar():
    mapas = {"Exemplo": "=", "Outro": "F6"}
    estado = _migrada(mapas)
    estado.definir("Exemplo", DESAT, mapas, CONTROLES)
    assert estado.verificar_tecla("Outro", "=", mapas, CONTROLES) is None


# ------------------------------------------------------------------------------------------------ conflito antigo e descrição
def test_conflito_antigo_deixa_o_segundo_mapa_ativo_mas_sem_a_tecla_e_sem_mexer_na_preferencia():                  # D27.6
    mapas = {"A": "=", "B": "="}
    estado = _migrada(mapas)  # dados de uma versão antiga: os dois viram "sempre"
    plano = estado.plano(mapas, CONTROLES)
    assert estado.dados()["prefs"] == {"A": SEMPRE, "B": SEMPRE}
    assert [r.acao for r in plano.registros if r.e_mapa] == ["map:A"]
    perdeu = estado.descrever("B", mapas, CONTROLES)
    assert perdeu.estado == SEMPRE and not perdeu.funcionando and perdeu.conflito.vencedor == "A"
    assert perdeu.situacao == "Sempre ativo ao iniciar (sem a tecla: conflito)"
    assert perdeu.resumo == ("A tecla “=” de “B” já é usada pela automação ativa “A”. "
                             "Esta automação continua ativa, mas sem a tecla enquanto o conflito durar.")


def test_descrever_cada_situacao():
    mapas = {"Ativo": "F6", "Perdeu": "F6", "Desligado": "F7", "SemTecla": "", "Estranho": "+", "Sessao": "F5"}
    estado = AtivacaoMapas({"migrated": True, "prefs": {n: SEMPRE for n in ("Ativo", "Perdeu", "SemTecla", "Estranho")}
                            | {"Desligado": DESAT, "Sessao": DESAT}})
    estado.definir("Sessao", SESSAO, mapas, CONTROLES)
    d = {n: estado.descrever(n, mapas, CONTROLES) for n in mapas}
    assert (d["Ativo"].funcionando, d["Ativo"].situacao, d["Ativo"].rotulo) == (True, "Sempre ativo ao iniciar", "Sempre ativo ao iniciar")
    assert d["Ativo"].resumo == "A tecla “F6” inicia e para esta automação."
    assert (d["Sessao"].funcionando, d["Sessao"].situacao) == (True, "Ativo nesta sessão")
    assert (d["Desligado"].funcionando, d["Desligado"].situacao, d["Desligado"].tecla) == (False, "Desativado", "F7")
    assert d["Desligado"].resumo == "A tecla “F7” não inicia esta automação. O botão ▶ Executar continua funcionando."
    assert (d["SemTecla"].funcionando, d["SemTecla"].situacao) == (False, "Sempre ativo ao iniciar (sem tecla)")
    assert d["SemTecla"].resumo == "Não há tecla para iniciar esta automação. Defina uma em ⚙ Configurações da automação."
    assert (d["Estranho"].funcionando, d["Estranho"].situacao) == (False, "Sempre ativo ao iniciar (tecla inválida)")
    assert d["Estranho"].invalido.startswith("A tecla “+” de “Estranho” não é válida")
    assert not d["Perdeu"].funcionando and d["Perdeu"].conflito is not None
    assert estado.descrever("Fantasma", mapas, CONTROLES).estado == DESAT, "um nome que não existe nos mapas conta como desativado"


def test_descrever_um_mapa_desativado_sem_tecla():
    mapas = {"A": ""}
    estado = AtivacaoMapas({"migrated": True, "prefs": {"A": DESAT}})
    d = estado.descrever("A", mapas, CONTROLES)
    assert d.resumo == "Sem tecla definida. O botão ▶ Executar continua funcionando." and d.situacao == "Desativado"


def test_descrever_aproveita_um_plano_ja_montado():
    mapas = {"A": "F6", "B": "F7"}
    estado = _migrada(mapas)
    plano = estado.plano(mapas, CONTROLES)
    assert estado.descrever("A", mapas, CONTROLES, plano) == estado.descrever("A", mapas, CONTROLES)


# ------------------------------------------------------------------------------------------------ esquecer
def test_excluir_um_mapa_apaga_a_preferencia_e_o_estado_da_sessao():                                                  # ATV-03
    estado = _migrada()
    estado.sincronizar({**REAIS, "Novo": "F6"}, CONTROLES)
    assert estado.esquecer("Novo") and "Novo" not in estado.dados()["prefs"] and estado.estado("Novo") == DESAT
    assert estado.esquecer("Click genshin") and "Click genshin" not in estado.dados()["prefs"]
    assert not estado.esquecer("Nunca existiu")
    sem_o_primeiro = {n: t for n, t in REAIS.items() if n != "Click genshin"}
    resultado = estado.sincronizar({**sem_o_primeiro, "Novo": "F6"}, CONTROLES)
    assert estado.estado("Novo") == SESSAO and resultado.mudou, "um mapa recriado com o mesmo nome é um mapa novo"


# ------------------------------------------------------------------------------------------------ leitor tolerante (ATV-04)
@pytest.mark.parametrize("lixo", [None, [], "texto", 7, True, {"prefs": []}, {"prefs": "x"}, {"prefs": {"A": "sessao"}},
                                  {"prefs": {"A": 3, "": "sempre", 5: "sempre"}}, {"migrated": "sim", "prefs": None},
                                  {"prefs": {"A": ["sempre"]}}, {"migrated": 1}],
                         ids=["none", "lista", "texto", "numero", "booleano", "prefs-lista", "prefs-texto", "valor-sessao",
                              "valores-ruins", "migrated-texto", "valor-lista", "migrated-um"])
def test_dados_corrompidos_sao_ignorados_sem_erro(lixo):                                                              # ATV-04
    estado = AtivacaoMapas(lixo)
    assert estado.dados() == {"migrated": False, "prefs": {}}
    estado.sincronizar(REAIS, CONTROLES)  # e o programa continua a abrir: tudo vira "sempre", como na primeira abertura
    assert {n: estado.estado(n) for n in REAIS} == {n: SEMPRE for n in REAIS}


def test_dados_parcialmente_validos_aproveitam_o_que_serve():                                                         # ATV-04
    estado = AtivacaoMapas({"migrated": True, "prefs": {"A": SEMPRE, "B": "sessao", "C": DESAT, "D": "xyz"}})
    assert estado.dados() == {"migrated": True, "prefs": {"A": SEMPRE, "C": DESAT}}


def test_o_que_e_gravado_so_tem_sempre_ou_desativado_e_sobrevive_ao_json():                                           # MAP-02
    mapas = {**REAIS, "N1": "F6", "N2": "F7"}
    estado = _migrada()
    estado.sincronizar(mapas, CONTROLES)
    estado.definir("N2", SEMPRE, mapas, CONTROLES)
    gravado = json.loads(json.dumps(estado.dados(), ensure_ascii=False))
    assert gravado == estado.dados() and set(gravado["prefs"].values()) <= {SEMPRE, DESAT}
    assert gravado["migrated"] is True


def test_os_dados_devolvidos_sao_uma_copia():
    estado = _migrada()
    copia = estado.dados()
    copia["prefs"]["Flins combo"] = DESAT
    copia["migrated"] = False
    assert estado.dados()["prefs"]["Flins combo"] == SEMPRE and estado.dados()["migrated"] is True


def test_o_construtor_nao_altera_nem_guarda_o_dicionario_recebido():
    recebido = {"migrated": True, "prefs": {"A": SEMPRE}}
    estado = AtivacaoMapas(recebido)
    estado.definir("A", DESAT, {"A": "F6"}, CONTROLES)
    estado.sincronizar({"A": "F6", "B": "F7"}, CONTROLES)
    assert recebido == {"migrated": True, "prefs": {"A": SEMPRE}}
    assert JA_MIGRADO == {"migrated": True, "prefs": {}}
