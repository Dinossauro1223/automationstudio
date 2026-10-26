"""Tema visual (core._theme_tokens / core._build_app_stylesheet).

A folha de estilo é só texto, então dá para vigiá-la SEM Qt: as cores têm de ser válidas, cada @token@ do modelo tem de
existir, as chaves têm de fechar (um erro de sintaxe faz o Qt ignorar a folha inteira, sem aviso) e o texto tem de ter
contraste legível em qualquer acento que o usuário escolher. O que depende de ver a janela de verdade (alinhamento,
tamanho dos botões) continua sendo conferido abrindo o programa.
"""
import re

from automationstudio import core

HEX = re.compile(r"^#[0-9a-f]{6}$")
ACENTOS = ["#ffc53d", "#2f6fed", "#d62828", "#2ea043", "#8957e5", "#e67e22", "#00bcd4", "#111111", "#ffffff"]
SUPERFICIES_CLARAS = [("#ffffff", "#2f343b"), ("#fff8e7", "#2f343b"), ("#f2f4f7", "#1b1f24")]


def _lum(cor: str) -> float:
    def canal(v: int) -> float:
        v = v / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = core._hex_rgb(cor)
    return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b)


def _contraste(a: str, b: str) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _todos_os_temas():
    for acento in ACENTOS:
        yield True, core._theme_tokens(True, acento)
        for superficie, contraste in SUPERFICIES_CLARAS:
            yield False, core._theme_tokens(False, acento, superficie, contraste)


def test_mistura_de_cores_nos_extremos_e_no_meio():
    assert core._mix_hex("#000000", "#ffffff", 0) == "#000000"
    assert core._mix_hex("#000000", "#ffffff", 1) == "#ffffff"
    assert core._mix_hex("#000000", "#ffffff", 0.5) == "#808080"
    assert core._mix_hex("#102030", "#102030", 0.7) == "#102030"
    assert core._mix_hex("#000000", "#ffffff", 7) == "#ffffff"  # fora de 0..1 é limitado


def test_todo_token_e_uma_cor_valida():
    for _escuro, tokens in _todos_os_temas():
        for nome, valor in tokens.items():
            assert HEX.match(valor), (nome, valor)


def test_o_acento_do_usuario_e_respeitado_e_derivados_existem():
    for _escuro, tokens in _todos_os_temas():
        for nome in ("accent", "accent_hover", "accent_press", "accent_soft", "on_accent"):
            assert nome in tokens
    assert core._theme_tokens(True, "#2f6fed")["accent"] == "#2f6fed"
    assert core._theme_tokens(False, "#d62828")["accent"] == "#d62828"


def test_tema_claro_usa_a_superficie_e_o_contraste_do_usuario():
    t = core._theme_tokens(False, "#2f6fed", "#fff8e7", "#1b1f24")
    assert t["window"] == "#fff8e7" and t["base"] == "#fff8e7"
    assert t["text"] == "#1b1f24"


def test_todo_token_usado_no_modelo_existe():
    usados = set(re.findall(r"@([a-z_]+)@", core._APP_QSS))
    assert usados, "o modelo deveria usar tokens"
    for _escuro, tokens in _todos_os_temas():
        assert usados <= set(tokens), usados - set(tokens)


def test_folha_final_nao_deixa_token_sem_trocar_e_tem_chaves_balanceadas():
    for _escuro, tokens in _todos_os_temas():
        qss = core._build_app_stylesheet(tokens)
        assert "@" not in qss
        assert qss.count("{") == qss.count("}")
        depth = 0
        for ch in qss:
            depth += (ch == "{") - (ch == "}")
            assert 0 <= depth <= 1, "chaves aninhadas ou fechadas a mais"
        assert depth == 0


def test_toda_regra_termina_declaracoes_com_ponto_e_virgula():
    qss = core._build_app_stylesheet(core._theme_tokens(True, "#ffc53d"))
    for corpo in re.findall(r"\{([^{}]*)\}", qss):
        for decl in [d for d in corpo.split(";") if d.strip()]:
            assert re.match(r"^\s*[a-z-]+\s*:\s*\S", decl), decl
        assert corpo.rstrip().endswith(";"), corpo


def test_so_usa_propriedades_que_o_qss_do_qt_entende():
    # Lista fechada: CSS de navegador (box-shadow, transition, gap, cursor...) o Qt ignora; um deslize aqui passaria
    # despercebido porque o Qt só avisa no console. Para usar uma propriedade nova, confira na documentação do Qt e inclua.
    permitidas = {
        "background", "color", "padding", "margin", "border", "border-radius", "border-color", "border-top",
        "border-bottom", "border-right", "width", "height", "min-width", "min-height", "font-weight", "spacing",
        "outline", "gridline-color", "text-align",
    }
    usadas = set()
    for corpo in re.findall(r"\{([^{}]*)\}", core._APP_QSS):
        usadas |= set(re.findall(r"(?:^|;)\s*([a-z-]+)\s*:", corpo))
    assert usadas <= permitidas, usadas - permitidas
    for proibido in ("var(", "calc(", "!important", "rgba(", "url("):
        assert proibido not in core._APP_QSS, proibido


def test_nao_define_selection_background_color_global():
    # A tabela de comandos pinta a própria seleção (Highlight sem pincel); essa propriedade global a sobrescreveria.
    assert "selection-background-color" not in core._APP_QSS


def test_nao_mexe_em_subcontroles_nativos_que_somem_sem_imagem():
    for sub in ("::indicator", "::down-arrow", "::up-arrow", "::drop-down", "::up-button", "::down-button"):
        assert sub not in core._APP_QSS, sub


def test_tamanho_dos_controles_continua_o_de_sempre():
    # Os paddings da folha antiga: botão 6/10, campos 4/6, aba 7/12, cabeçalho 6. A barra de ferramentas tem altura fixa.
    qss = core._APP_QSS
    assert re.search(r"QPushButton \{ padding: 6px 10px;", qss)
    assert re.search(r"QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox \{ padding: 4px 6px;", qss)
    assert "QTabBar::tab { padding: 7px 12px; }" in qss
    assert re.search(r"QHeaderView::section \{ padding: 6px;", qss)
    assert "QScrollBar:vertical { width: 6px;" in qss and "QScrollBar:horizontal { height: 6px;" in qss
    assert re.search(r"QToolBar QToolButton \{[^}]*padding: 3px 8px;", qss)


def test_texto_sobre_o_acento_e_legivel_para_qualquer_acento():
    for acento in ACENTOS:
        t = core._theme_tokens(True, acento)
        assert _contraste(t["accent"], t["on_accent"]) >= 3.0, (acento, t["on_accent"])


def test_contraste_do_texto_nos_dois_temas():
    for escuro, t in _todos_os_temas():
        assert _contraste(t["window"], t["text"]) >= 7.0, (escuro, t["window"], t["text"])
        assert _contraste(t["window"], t["muted"]) >= 4.5, (escuro, t["window"], t["muted"])
        assert _contraste(t["base"], t["text"]) >= 7.0


def test_tema_escuro_tem_tres_camadas_distintas():
    t = core._theme_tokens(True, "#ffc53d")
    assert len({t["base"], t["window"], t["button"], t["hover"]}) == 4
    assert _lum(t["base"]) < _lum(t["window"]) < _lum(t["button"]) < _lum(t["hover"])


def test_cores_da_timeline_escura_acompanham_o_tema():
    # Lê o texto dos arquivos (QColor não é confiável nos dublês de Qt) e confere as duas cópias das cores.
    t = core._theme_tokens(True, "#ffc53d")
    esperado = {"BG": t["base"], "ROW_ALT": t["alt"], "RULER_BG": t["window"]}
    fonte_core = open(core.__file__, encoding="utf-8").read()
    for nome, cor in esperado.items():
        achou = re.search(r'^_COLOR_%s = QColor\("(#[0-9a-fA-F]{6})"\)' % nome, fonte_core, re.M)
        assert achou and achou.group(1).lower() == cor, (nome, achou and achou.group(1), cor)
    fonte_timeline = open(core.__file__.replace("core.py", "timeline.py"), encoding="utf-8").read()
    for atributo, cor in (("_bg", t["base"]), ("_row_alt", t["alt"]), ("_ruler_bg", t["window"])):
        achou = re.search(r"self\.%s = QColor\('(#[0-9a-fA-F]{6})'\)" % atributo, fonte_timeline)
        assert achou and achou.group(1).lower() == cor, (atributo, achou and achou.group(1), cor)
