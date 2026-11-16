"""Regras das teclas de automação (automationstudio/atalhos_reservados.py): o que NÃO pode iniciar uma automação.

Lógica pura, sem Qt. Especificação: md/ESPEC_TECLADO_25_9.md, seção 5.3 (T1). O atalho de automação é global e PASSIVO: a
tecla continua chegando ao programa em foco. Uma automação em Ctrl+T abriria uma aba no navegador E começaria ao mesmo tempo;
em "A", dispararia a cada letra digitada. Por isso estas regras são de segurança, não de gosto.

A tabela de casos é a própria regra: cada linha é (tecla, nível, regra que decidiu). Se uma regra mudar, a linha mostra qual.
"""
import itertools
import types

import pytest

from automationstudio import atalhos_reservados as ar
from automationstudio.atalhos_reservados import (CATALOGO, NIVEL_AVISO, NIVEL_LIVRE, NIVEL_RECUSADA, Avaliacao, avaliar,
                                                 sugerir)
from automationstudio.core import _SPECIAL_KEY_NAMES, key_to_name, parse_combo

TRES = "CTRL+SHIFT+ALT+"  # a base das combinações sugeridas (TEC-12)


# ------------------------------------------------------------------------------------------------ as regras, uma a uma
@pytest.mark.parametrize("tecla,regra", [
    ("=", "desconhecida"), (",", "desconhecida"), (";", "desconhecida"), ("CTRL+SHIFT+ALT+=", "desconhecida"),
    ("CRTL+F13", "desconhecida"), ("RETURN", "desconhecida"), ("FN+F13", "desconhecida"), ("NUM7", "desconhecida"),
    ("MOUSE_X3", "desconhecida"), ("F25", "desconhecida"), ("F0", "desconhecida"), ("ABC", "desconhecida"),
    ("CTRL+SHIFT+ALT+1+=", "desconhecida")])
def test_o_que_o_monitor_nunca_produz_e_recusado_porque_nunca_dispararia(tecla, regra):
    # A1: a tecla "=" (padrão de todo mapa antigo) nunca chega ao gerente de atalhos, porque o monitor descarta símbolos.
    # Aceitar uma tecla assim seria prometer um atalho que não funciona, mesmo com três modificadores.
    resultado = avaliar(tecla)
    assert (resultado.nivel, resultado.regra) == (NIVEL_RECUSADA, regra), resultado
    assert resultado.motivo


@pytest.mark.parametrize("tecla", ["CTRL", "CTRL+SHIFT", "ALT+SHIFT+CTRL", "ALTGR", "SHIFT", "WIN", "CTRL+WIN"])
def test_so_modificadores_e_recusado(tecla):
    assert (avaliar(tecla).nivel, avaliar(tecla).regra) == (NIVEL_RECUSADA, "sem_tecla")


@pytest.mark.parametrize("tecla", ["WIN+E", "WIN+1", "CTRL+WIN+1", "CTRL+SHIFT+ALT+WIN+1", "WIN+F13", "WIN+MOUSE_X1"])
def test_qualquer_combinacao_com_a_tecla_windows_e_recusada(tecla):
    assert (avaliar(tecla).nivel, avaliar(tecla).regra) == (NIVEL_RECUSADA, "win")


@pytest.mark.parametrize("tecla", ["MOUSE_LEFT", "MOUSE_RIGHT", "MOUSE_MIDDLE", "SHIFT+MOUSE_RIGHT", "F13+MOUSE_MIDDLE",
                                   "BOTAOESQUERDO", "right_mouse"])
def test_esquerdo_direito_e_meio_do_mouse_sem_modificador_ou_so_com_shift_sao_recusados(tecla):
    # São clicados o tempo todo, e o clique da própria automação seria visto pelo atalho e a dispararia de novo.
    assert (avaliar(tecla).nivel, avaliar(tecla).regra) == (NIVEL_RECUSADA, "mouse")
    assert "clicado" in avaliar(tecla).motivo


@pytest.mark.parametrize("tecla,nivel,regra", [
    ("CTRL+MOUSE_LEFT", NIVEL_RECUSADA, "um_modificador"), ("ALT+MOUSE_RIGHT", NIVEL_RECUSADA, "um_modificador"),
    ("CTRL+SHIFT+MOUSE_LEFT", NIVEL_AVISO, "dois_modificadores"), ("CTRL+ALT+MOUSE_MIDDLE", NIVEL_AVISO, "dois_modificadores"),
    ("CTRL+SHIFT+ALT+MOUSE_LEFT", NIVEL_LIVRE, "livre"), ("CTRL+SHIFT+ALT+MOUSE_RIGHT", NIVEL_LIVRE, "livre"),
    ("CTRL+SHIFT+ALT+MOUSE_MIDDLE", NIVEL_LIVRE, "livre")])
def test_o_mouse_principal_com_modificadores_segue_as_regras_das_teclas_comuns(tecla, nivel, regra):
    # Com três modificadores o clique deixa de ser um clique comum: é uma combinação deliberada, como Ctrl+Shift+Alt+1.
    assert (avaliar(tecla).nivel, avaliar(tecla).regra) == (nivel, regra)


@pytest.mark.parametrize("tecla", [
    "A", "Z", "0", "9", "Ç", "SPACE", "ENTER", "TAB", "ESC", "BACKSPACE", "UP", "DOWN", "LEFT", "RIGHT", "INSERT", "DELETE",
    "HOME", "END", "PAGEUP", "PAGEDOWN", "SHIFT+A", "SHIFT+5", "SHIFT+SPACE", "SHIFT+DELETE", "A+B"])
def test_tecla_de_digitar_ou_navegar_sem_modificador_ou_so_com_shift_e_recusada(tecla):
    assert (avaliar(tecla).nivel, avaliar(tecla).regra) == (NIVEL_RECUSADA, "digitar")


@pytest.mark.parametrize("tecla,motivo", [
    ("PRINTSCREEN", "captur"), ("MENU", "menu de contexto"), ("CAPSLOCK", "maiúsculas"), ("NUMLOCK", "Num Lock"),
    ("SHIFT+PRINTSCREEN", "captur")])
def test_teclas_com_efeito_proprio_no_windows_sao_recusadas_com_o_motivo_certo(tecla, motivo):
    resultado = avaliar(tecla)
    assert (resultado.nivel, resultado.regra) == (NIVEL_RECUSADA, "isolada") and motivo in resultado.motivo, resultado


@pytest.mark.parametrize("tecla", ["PAUSE", "SCROLLLOCK", "SHIFT+PAUSE"])
def test_pause_e_scrolllock_sozinhos_valem_com_aviso(tecla):
    assert (avaliar(tecla).nivel, avaliar(tecla).regra) == (NIVEL_AVISO, "isolada") and avaliar(tecla).motivo


@pytest.mark.parametrize("tecla", [f"F{n}" for n in range(1, 13)] + ["SHIFT+F1", "SHIFT+F5", "SHIFT+F12", "F6+F7"])
def test_f1_a_f12_sem_modificador_ou_so_com_shift_sao_recusadas(tecla):
    resultado = avaliar(tecla)
    assert (resultado.nivel, resultado.regra) == (NIVEL_RECUSADA, "f1_f12"), resultado


def test_shift_f10_e_o_clique_direito_do_teclado_e_vem_do_catalogo():
    resultado = avaliar("SHIFT+F10")
    assert (resultado.nivel, resultado.regra) == (NIVEL_RECUSADA, "catalogo") and "contexto" in resultado.motivo


@pytest.mark.parametrize("tecla", [f"F{n}" for n in range(13, 25)] + ["CTRL+F13", "SHIFT+F20", "ALT+F24", "CTRL+SHIFT+F15",
                                                                      "CTRL+SHIFT+ALT+F13", "F13+MOUSE_X1"])
def test_f13_a_f24_sao_livres_com_qualquer_combinacao_que_passou_das_regras_anteriores(tecla):
    # São as teclas que mouses e teclados de muitos botões costumam enviar: justamente as livres (A2).
    resultado = avaliar(tecla)
    assert (resultado.nivel, resultado.regra, resultado.motivo) == (NIVEL_LIVRE, "f13_f24", ""), resultado


@pytest.mark.parametrize("tecla", ["CTRL+K", "ALT+K", "CTRL+1", "CTRL+SPACE", "CTRL+F6", "ALT+F6", "CTRL+HOME", "ALT+UP",
                                   "CTRL+PRINTSCREEN", "ALT+PAUSE"])
def test_um_unico_modificador_ctrl_ou_alt_com_uma_tecla_e_recusado(tecla):
    resultado = avaliar(tecla)
    assert (resultado.nivel, resultado.regra) == (NIVEL_RECUSADA, "um_modificador"), resultado
    assert "Ctrl" in resultado.motivo and "Alt" in resultado.motivo


@pytest.mark.parametrize("tecla", ["CTRL+ALT+Q", "ALTGR+Q", "ALTGR+1", "CTRL+ALT+Ç", "ALT+CTRL+7"])
def test_ctrl_alt_com_letra_ou_numero_e_recusado_porque_e_o_altgr(tecla):
    # No teclado ABNT2, o AltGr é Ctrl+Alt e digita caracteres (/, ?, ¹...). A regra vale para o AltGr que o pynput informa.
    resultado = avaliar(tecla)
    assert (resultado.nivel, resultado.regra) == (NIVEL_RECUSADA, "altgr") and "AltGr" in resultado.motivo, resultado


@pytest.mark.parametrize("tecla", ["CTRL+SHIFT+K", "ALT+SHIFT+K", "CTRL+ALT+F5", "CTRL+SHIFT+F5", "CTRL+ALT+LEFT", "ALTGR+F5",
                                   "CTRL+SHIFT+SPACE", "ALT+SHIFT+1"])
def test_dois_modificadores_com_tecla_fora_do_catalogo_valem_com_aviso(tecla):
    resultado = avaliar(tecla)
    assert (resultado.nivel, resultado.regra) == (NIVEL_AVISO, "dois_modificadores") and "três" in resultado.motivo, resultado


@pytest.mark.parametrize("tecla", ["MOUSE_X1", "MOUSE_X2", "x1", "X2", "LATERAL1", "lateral2", "MOUSE_X1+MOUSE_X2"])
def test_botao_lateral_do_mouse_sozinho_vale_com_aviso(tecla):
    # D14: os navegadores usam os laterais como Voltar e Avançar, mas o dono quer o mouse como disparador.
    resultado = avaliar(tecla)
    assert (resultado.nivel, resultado.regra) == (NIVEL_AVISO, "lateral") and "Voltar" in resultado.motivo, resultado


@pytest.mark.parametrize("tecla", ["CTRL+MOUSE_X1", "SHIFT+MOUSE_X2", "CTRL+SHIFT+ALT+MOUSE_X1", "ALT+X2"])
def test_botao_lateral_com_um_modificador_e_livre(tecla):
    resultado = avaliar(tecla)
    assert (resultado.nivel, resultado.regra, resultado.motivo) == (NIVEL_LIVRE, "livre", ""), resultado


@pytest.mark.parametrize("tecla", [TRES + t for t in list("1234567890") + [f"F{n}" for n in range(1, 13)] + list("ABCZ")] + [
    TRES + "SPACE", TRES + "ENTER", TRES + "ESC", TRES + "TAB", TRES + "UP", TRES + "DELETE", TRES + "PRINTSCREEN",
    "ALTGR+SHIFT+CTRL+1", "SHIFT+CTRL+ALT+Ç", "ctrl + shift + alt + 1"])
def test_tres_modificadores_com_uma_tecla_sao_livres(tecla):
    # TEC-12: Ctrl+Shift+Alt+1 é o padrão pedido; nenhum programa comum usa três modificadores com um dígito.
    resultado = avaliar(tecla)
    assert (resultado.nivel, resultado.regra, resultado.motivo, resultado.sugestao) == (NIVEL_LIVRE, "livre", "", ""), resultado


def test_o_motivo_da_tecla_desconhecida_diz_qual_parte_e_o_que_fazer():
    assert avaliar("=").motivo == "usa “=”, que o programa ainda não reconhece como tecla de atalho (símbolos e pontuação ainda não funcionam)"
    assert avaliar("CRTL+F13").motivo == "usa “CRTL”, que o programa não reconhece como tecla de atalho (confira a escrita)"
    assert avaliar("CTRL+SHIFT+ALT+=").motivo.startswith("usa “=”, que o programa ainda não reconhece")
    assert avaliar("ZZ+AA+CTRL").motivo.startswith("usa “AA”"), "com várias, a primeira em ordem alfabética: o texto não depende do conjunto"


# ------------------------------------------------------------------------------------------------ o catálogo
ESPECIFICADAS = ["CTRL+ALT+DELETE", "CTRL+SHIFT+ESC", "ALT+F4", "ALT+TAB", "CTRL+SHIFT+T", "CTRL+SHIFT+N", "CTRL+SHIFT+W",
                 "CTRL+SHIFT+DELETE", "CTRL+SHIFT+I", "CTRL+SHIFT+J", "CTRL+SHIFT+C", "CTRL+SHIFT+R", "CTRL+SHIFT+TAB",
                 "CTRL+ESC", "ALT+ESC", "ALT+SPACE", "CTRL+ALT+TAB", "ALT+SHIFT+TAB", "SHIFT+F10"]


@pytest.mark.parametrize("tecla", ESPECIFICADAS)
def test_as_combinacoes_da_ficha_vem_do_catalogo_com_o_motivo_proprio(tecla):
    resultado = avaliar(tecla)
    assert (resultado.nivel, resultado.regra) == (NIVEL_RECUSADA, "catalogo"), resultado
    assert len(resultado.motivo) > 8 and "modificador" not in resultado.motivo, "o motivo é o da combinação, não o genérico"


@pytest.mark.parametrize("tecla,palavra", [
    ("CTRL+T", "aba"), ("CTRL+SHIFT+T", "aba"), ("CTRL+ALT+DELETE", "segurança"), ("CTRL+SHIFT+ESC", "Tarefas"),
    ("ALT+F4", "fecha"), ("CTRL+SHIFT+I", "desenvolvedor"), ("CTRL+C", "copia"), ("ALT+TAB", "janela")])
def test_o_motivo_diz_o_que_a_combinacao_faz(tecla, palavra):
    assert palavra.lower() in avaliar(tecla).motivo.lower()


@pytest.mark.parametrize("escrita", ["ctrl+shift+t", "SHIFT+CTRL+T", "Ctrl + Shift + T", "T+SHIFT+CTRL", " CTRL+SHIFT+T "])
def test_o_catalogo_vale_para_qualquer_jeito_de_escrever_a_combinacao(escrita):
    assert avaliar(escrita).regra == "catalogo"


def test_o_altgr_conta_como_ctrl_mais_alt_no_catalogo():
    assert avaliar("ALTGR+DELETE").regra == "catalogo"  # = Ctrl+Alt+Delete


def test_o_catalogo_vale_so_para_a_combinacao_igual_e_nao_rotula_as_menores_com_o_motivo_das_maiores():
    # "A" está dentro de Ctrl+A, mas dizer que a tecla A "seleciona tudo" seria um motivo falso: A é recusada por ser de digitar.
    assert avaliar("ALT+TAB").regra == "catalogo" and avaliar("ALT+SHIFT+TAB").regra == "catalogo"
    assert avaliar("SHIFT+TAB").regra == "digitar" and avaliar("A").regra == "digitar" and avaliar("TAB").regra == "digitar"
    assert avaliar("CTRL+SHIFT+A").regra == "catalogo" and avaliar("CTRL+A").regra == "catalogo"


def test_uma_combinacao_com_mais_teclas_que_a_entrada_nao_colide_com_ela():
    # Ctrl+Shift+Alt+T não é Ctrl+Shift+T: o programa em foco vê os três modificadores. É por isso que três modificadores valem.
    assert avaliar("CTRL+SHIFT+ALT+T").nivel == NIVEL_LIVRE


def test_o_catalogo_e_uma_tabela_de_combinacao_e_motivo_sem_repeticao():
    assert len(CATALOGO) >= 40
    combos = [parse_combo(c) for c, _motivo in CATALOGO]
    assert len(set(combos)) == len(combos), "combinação repetida no catálogo"
    for (texto, motivo), combo in zip(CATALOGO, combos):
        assert texto == texto.upper() and "WIN" not in combo, f"{texto}: a regra do Windows já cuida de todas as de Win"
        assert motivo and motivo == motivo.strip() and not motivo.endswith("."), f"{texto}: motivo sem ponto final, em minúsculas"
        assert motivo[0].islower() or not motivo[0].isalpha(), f"{texto}: o motivo é um predicado ('abre...', 'fecha...')"


def test_toda_entrada_do_catalogo_e_recusada_e_nenhuma_e_livre_por_engano():
    for texto, _motivo in CATALOGO:
        resultado = avaliar(texto)
        assert (resultado.nivel, resultado.regra) == (NIVEL_RECUSADA, "catalogo"), (texto, resultado)


# ------------------------------------------------------------------------------------------------ normalização
@pytest.mark.parametrize("a,b", [
    ("ctrl+shift+alt+1", "CTRL+SHIFT+ALT+1"), ("ALT+1+SHIFT+CTRL", "CTRL+SHIFT+ALT+1"), ("ctrl + shift + alt + 1", "CTRL+SHIFT+ALT+1"),
    ("  f13 ", "F13"), ("ctrl+t", "CTRL+T"), ("x1", "MOUSE_X1"), ("BOTAOESQUERDO", "MOUSE_LEFT")])
def test_maiusculas_espacos_ordem_e_apelidos_dao_o_mesmo_resultado(a, b):
    assert avaliar(a) == avaliar(b)


@pytest.mark.parametrize("entrada", [None, "", "   ", "+", "++", 5, ["F13"], b"F13"])
def test_entrada_sem_tecla_nunca_levanta_e_e_recusada_como_invalida(entrada):
    resultado = avaliar(entrada)
    assert isinstance(resultado, Avaliacao) and (resultado.nivel, resultado.regra) == (NIVEL_RECUSADA, "invalida")


def test_uma_avaliacao_e_imutavel_e_comparavel():
    resultado = avaliar("CTRL+T")
    with pytest.raises(Exception):
        resultado.nivel = NIVEL_LIVRE  # type: ignore[misc]
    assert resultado == avaliar("ctrl+t")


# ------------------------------------------------------------------------------------------------ as teclas que o monitor produz
def _nomes_que_o_monitor_produz() -> set[str]:
    nomes = {key_to_name(types.SimpleNamespace(name=n)) for n in _SPECIAL_KEY_NAMES}
    nomes |= {key_to_name(types.SimpleNamespace(name=None, char=c)) for c in "AZaz059Çç"}
    nomes |= {f"MOUSE_{b}" for b in ("LEFT", "RIGHT", "MIDDLE", "X1", "X2")}
    nomes.discard("")
    return nomes


def test_toda_tecla_que_o_monitor_produz_e_conhecida_pelas_regras():
    # Se o monitor passar a produzir uma tecla nova (como F13 a F24 nesta versão), as regras precisam saber classificá-la:
    # senão ela seria recusada como "desconhecida" mesmo funcionando.
    desconhecidas = sorted(n for n in _nomes_que_o_monitor_produz() if avaliar(n).regra == "desconhecida")
    assert desconhecidas == []


def test_o_monitor_produz_f13_a_f24():
    produzidas = _nomes_que_o_monitor_produz()
    assert {f"F{n}" for n in range(1, 25)} <= produzidas


# ------------------------------------------------------------------------------------------------ a sugestão (D11)
def test_a_primeira_sugestao_e_ctrl_shift_alt_1():
    assert sugerir([]) == "CTRL+SHIFT+ALT+1" == TRES + "1"


def test_as_sugestoes_seguem_a_ordem_1_a_9_0_depois_f1_a_f12_depois_a_a_z():
    usadas, vistas = [], []
    for _ in range(60):  # a série tem 48; o limite impede que um defeito que repete a sugestão prenda o teste num laço sem fim
        proxima = sugerir(usadas)
        if not proxima:
            break
        vistas.append(proxima)
        usadas.append(proxima)
    esperadas = [TRES + t for t in list("1234567890") + [f"F{n}" for n in range(1, 13)] + list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")]
    assert vistas == esperadas and len(vistas) == 48


def test_a_sugestao_pula_o_que_ja_esta_em_uso_escrito_de_qualquer_jeito():
    assert sugerir(["ctrl+shift+alt+1"]) == TRES + "2"
    assert sugerir(["ALT+1+SHIFT+CTRL", " Ctrl + Shift + Alt + 2 "]) == TRES + "3"
    assert sugerir([TRES + "2"]) == TRES + "1", "o buraco no começo é o primeiro livre"


def test_a_sugestao_ignora_o_que_nao_e_tecla():
    assert sugerir([None, "", "   ", "+", 5, ["x"], TRES + "1"]) == TRES + "2"


def test_a_sugestao_aceita_qualquer_iteravel_e_nao_consome_alem_do_necessario():
    assert sugerir(iter([TRES + "1"])) == TRES + "2"
    assert sugerir(t for t in (TRES + "1", TRES + "2")) == TRES + "3"
    assert sugerir(()) == TRES + "1"


def test_a_sugestao_pula_a_combinacao_que_dispararia_junto_com_uma_ja_usada():
    # O gerente dispara por SUBCONJUNTO: uma automação em "1" também dispara ao apertar Ctrl+Shift+Alt+1.
    assert sugerir(["1"]) == TRES + "2"
    assert sugerir(["CTRL+SHIFT+ALT+1+2"]) == TRES + "3", "e o contrário: apertar as teclas da usada dispararia a sugerida"
    assert sugerir(["CTRL+SHIFT"]) == "", "uma tecla só de modificadores dispara com qualquer sugestão: não há sugestão segura"


def test_toda_sugestao_e_livre_pelas_proprias_regras():
    usadas = []
    for _ in range(48):
        proxima = sugerir(usadas)
        assert avaliar(proxima).nivel == NIVEL_LIVRE, proxima
        usadas.append(proxima)


def test_esgotadas_as_48_combinacoes_nao_ha_sugestao():
    todas = [TRES + t for t in list("1234567890") + [f"F{n}" for n in range(1, 13)] + list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")]
    assert sugerir(todas) == ""


def test_a_recusa_traz_a_proxima_combinacao_livre_como_sugestao():
    assert avaliar("CTRL+T").sugestao == TRES + "1"
    assert avaliar("CTRL+T", [TRES + "1", TRES + "2"]).sugestao == TRES + "3"
    assert avaliar("=", usadas=[TRES + "1"]).sugestao == TRES + "2"


def test_o_que_vale_nao_precisa_de_sugestao():
    assert avaliar(TRES + "1", [TRES + "1"]).sugestao == "" and avaliar("MOUSE_X1").sugestao == "" and avaliar("CTRL+SHIFT+K").sugestao == ""


# ------------------------------------------------------------------------------------------------ propriedades
def test_toda_combinacao_gerada_tem_um_resultado_coerente():
    """Varre todas as combinações de até 4 teclas dentre um conjunto representativo: nunca levanta, o nível e a regra são
    conhecidos, o motivo existe quando não é livre, e a ordem das teclas e a caixa nunca mudam o resultado."""
    base = ["CTRL", "SHIFT", "ALT", "ALTGR", "WIN", "A", "1", "SPACE", "F5", "F13", "MOUSE_LEFT", "MOUSE_X1", "PAUSE", "=", "DELETE"]
    regras = {"invalida", "desconhecida", "sem_tecla", "win", "catalogo", "mouse", "isolada", "digitar", "f1_f12", "f13_f24",
              "um_modificador", "altgr", "dois_modificadores", "lateral", "livre"}
    total = 0
    for n in range(1, 5):
        for grupo in itertools.combinations(base, n):
            texto = "+".join(grupo)
            resultado = avaliar(texto)
            total += 1
            assert resultado.nivel in (NIVEL_LIVRE, NIVEL_AVISO, NIVEL_RECUSADA) and resultado.regra in regras, (texto, resultado)
            assert bool(resultado.motivo) == (resultado.nivel != NIVEL_LIVRE), (texto, resultado)
            assert avaliar("+".join(reversed(grupo)).lower()) == resultado, texto
    assert total > 1500


def test_nenhuma_combinacao_de_modificadores_so_e_livre_nem_com_aviso():
    for n in range(1, 5):
        for grupo in itertools.combinations(["CTRL", "SHIFT", "ALT", "ALTGR", "WIN"], n):
            assert avaliar("+".join(grupo)).nivel == NIVEL_RECUSADA, grupo


def test_com_win_nada_e_livre_em_nenhuma_combinacao():
    for tecla in ["A", "1", "F13", "MOUSE_X1", "SPACE"]:
        for mods in (["WIN"], ["WIN", "CTRL"], ["WIN", "CTRL", "SHIFT", "ALT"]):
            assert avaliar("+".join(mods + [tecla])).nivel == NIVEL_RECUSADA, (mods, tecla)


def test_os_nomes_publicos_do_modulo():
    assert {"CATALOGO", "NIVEL_LIVRE", "NIVEL_AVISO", "NIVEL_RECUSADA", "Avaliacao", "avaliar", "sugerir"} <= set(dir(ar))
    assert (NIVEL_LIVRE, NIVEL_AVISO, NIVEL_RECUSADA) == ("livre", "aviso", "recusada")
