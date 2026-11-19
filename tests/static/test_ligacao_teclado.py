"""A ligação da edição pelo teclado com a janela principal e com a tabela, conferida no código-fonte (25.9, T3a; ficha T3-2, T3-5, T3-9, T3-11).

Os testes de janela (tests/gui/test_teclado_janela.py) provam o COMPORTAMENTO, mas só rodam com o PySide6 de verdade (no Actions). Este arquivo
roda em qualquer lugar e protege a ligação em si: se numa fusão de ramos ou numa refatoração alguma peça sumir, o teste diz qual. O que ele
cobra:

- `MainWindow.__init__` cria `self.teclado = TecladoDaJanela(self)` DEPOIS de a tabela e a barra de status existirem (a janela do teclado
  escreve na barra e filtra a tabela);
- o Esc do aplicativo (`MainWindow.eventFilter`, que roda antes de qualquer filtro de widget) CEDE enquanto há uma edição: sem isso, cancelar
  uma edição com Esc também voltaria de página (T3-9);
- `CommandTableWidget.editar_celula_atual` existe e o Enter antigo da tabela passa por ela (a F2 e o Enter são o mesmo caminho: T3-11);
- `TecladoDaJanela` oferece TODOS os métodos da `Porta` que a ligação (`teclado_ligacao.py`) chama: uma porta incompleta só falharia na hora de
  uma tecla, com o Qt de verdade;
- o filtro de eventos é instalado na tabela (T3-2) e a janela do teclado NUNCA abre um laço aninhado (`exec`): a janela do programa é
  `open()` não bloqueante (T3-5), porque um laço dentro do filtro reentraria no controlador.

O verificador (as funções `_...` abaixo) é testado à parte com trechos sintéticos (controles negativo e positivo): sem eles um teste "falharia"
por qualquer motivo, inclusive por o verificador não achar o método.
"""
import ast
import os
import pathlib

ROOT = pathlib.Path(os.environ.get("AS_ROOT") or pathlib.Path(__file__).resolve().parents[2])
PACOTE = ROOT / "automationstudio"
JANELA = PACOTE / "main_window.py"
TABELA = PACOTE / "command_editor.py"
TECLADO_UI = PACOTE / "teclado_ui.py"
LIGACAO = PACOTE / "teclado_ligacao.py"


# ------------------------------------------------------------------------------------------------ o verificador
def _classe(fonte: str, nome: str):
    return next((no for no in ast.walk(ast.parse(fonte)) if isinstance(no, ast.ClassDef) and no.name == nome), None)


def _metodo(fonte: str, classe: str, nome: str):
    alvo = _classe(fonte, classe)
    return next((item for item in (alvo.body if alvo is not None else ()) if isinstance(item, ast.FunctionDef) and item.name == nome), None)


def _metodos(fonte: str, classe: str) -> set[str]:
    """Os nomes dos métodos definidos no corpo da classe (vazio se a classe não existe)."""
    alvo = _classe(fonte, classe)
    return {item.name for item in (alvo.body if alvo is not None else ()) if isinstance(item, ast.FunctionDef)}


def _nome_pontuado(no) -> str | None:
    """"self.teclado.editando" para o acesso `self.teclado.editando`; None se `no` não é uma cadeia de atributos que parte de um nome."""
    partes = []
    while isinstance(no, ast.Attribute):
        partes.append(no.attr)
        no = no.value
    if not isinstance(no, ast.Name):
        return None
    return ".".join([no.id, *reversed(partes)])


def _nome_da_chamada(no) -> str | None:
    return _nome_pontuado(no.func) if isinstance(no, ast.Call) else None


def _chamadas(no) -> set[str]:
    return {nome for sub in ast.walk(no) if (nome := _nome_da_chamada(sub)) is not None}


def _linha_da_criacao(fonte: str, atributo: str, classe: str) -> int | None:
    """A linha de `self.<atributo> = <classe>(self)` em `MainWindow.__init__`, ou None."""
    metodo = _metodo(fonte, "MainWindow", "__init__")
    for no in ast.walk(metodo) if metodo is not None else ():
        if (isinstance(no, ast.Assign) and isinstance(no.value, ast.Call) and isinstance(no.value.func, ast.Name)
                and no.value.func.id == classe and len(no.targets) == 1 and _nome_pontuado(no.targets[0]) == f"self.{atributo}"):
            return no.lineno
    return None


def _linha_da_chamada(fonte: str, nome: str) -> int | None:
    """A primeira linha, em `MainWindow.__init__`, que chama `nome` (como "self._build_status_bar"), ou None."""
    metodo = _metodo(fonte, "MainWindow", "__init__")
    linhas = [no.lineno for no in ast.walk(metodo) if _nome_da_chamada(no) == nome] if metodo is not None else []
    return min(linhas) if linhas else None


def _ramo_do_esc(fonte: str):
    """O primeiro `if` de `MainWindow.eventFilter` cujo teste fala da tecla `Key_Escape`; None se não há."""
    metodo = _metodo(fonte, "MainWindow", "eventFilter")
    for no in ast.walk(metodo) if metodo is not None else ():
        if isinstance(no, ast.If) and any(isinstance(sub, ast.Attribute) and sub.attr == "Key_Escape" for sub in ast.walk(no.test)):
            return no
    return None


_PERGUNTAS_DE_EDICAO = ("editando", "_teclado_editando")


def esc_cede_a_edicao(fonte: str) -> bool:
    """O ramo do Esc só vale quando NÃO há edição: o teste do `if` tem um `not` sobre uma chamada de `editando`/`_teclado_editando`."""
    ramo = _ramo_do_esc(fonte)
    if ramo is None:
        return False
    for no in ast.walk(ramo.test):
        if isinstance(no, ast.UnaryOp) and isinstance(no.op, ast.Not):
            if any(nome.rsplit(".", 1)[-1] in _PERGUNTAS_DE_EDICAO for nome in _chamadas(no.operand)):
                return True
    return False


def _instalacoes_do_filtro(fonte: str, classe: str) -> set[str]:
    """Os receptores de `.installEventFilter(...)` dentro da classe ("self._tabela.table"). Um apelido simples (`tabela = self._tabela.table`) é
    trocado pelo que ele guarda, senão o teste dependeria de o código escrever a cadeia inteira na hora de instalar."""
    alvo = _classe(fonte, classe)
    apelidos = {}
    for no in ast.walk(alvo) if alvo is not None else ():
        if isinstance(no, ast.Assign) and len(no.targets) == 1 and isinstance(no.targets[0], ast.Name):
            valor = _nome_pontuado(no.value)
            if valor is not None:
                apelidos[no.targets[0].id] = valor
    achados = set()
    for no in ast.walk(alvo) if alvo is not None else ():
        nome = _nome_da_chamada(no)
        if nome is not None and nome.endswith(".installEventFilter"):
            receptor = nome[: -len(".installEventFilter")]
            achados.add(apelidos.get(receptor, receptor))
    return achados


def _chama_exec(fonte: str) -> list[str]:
    """As chamadas `.exec(...)`/`.exec_(...)` do módulo: um laço de eventos aninhado."""
    return sorted({nome for no in ast.walk(ast.parse(fonte)) if (nome := _nome_da_chamada(no)) is not None and nome.rsplit(".", 1)[-1] in ("exec", "exec_")})


def _importa(fonte: str, modulo: str, nome: str) -> bool:
    """`from .<modulo> import <nome>` (import relativo do pacote)."""
    return any(isinstance(no, ast.ImportFrom) and no.level == 1 and no.module == modulo and any(a.name == nome for a in no.names)
               for no in ast.walk(ast.parse(fonte)))


# ------------------------------------------------------------------------------------------------ controles do verificador
_JANELA_SINTETICA = '''
from .teclado_ui import TecladoDaJanela

class MainWindow:
    def __init__(self):
        self._build_body()
        self._build_status_bar()
        self.teclado = TecladoDaJanela(self)

    def _teclado_editando(self):
        teclado = getattr(self, 'teclado', None)
        return teclado is not None and teclado.editando()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Resize:
            return False
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape and {condicao}:
            self._voltar()
        return False
'''
_CEDE = "not self._teclado_editando()"


def test_o_verificador_acha_a_criacao_e_a_ordem_no_init():
    fonte = _JANELA_SINTETICA.format(condicao=_CEDE)
    assert _linha_da_criacao(fonte, "teclado", "TecladoDaJanela") == 8
    assert _linha_da_chamada(fonte, "self._build_body") == 6
    assert _linha_da_chamada(fonte, "self._build_status_bar") == 7
    assert _linha_da_criacao(fonte.replace("TecladoDaJanela(self)", "Outra(self)"), "teclado", "TecladoDaJanela") is None
    assert _linha_da_criacao(fonte.replace("self.teclado =", "self.outro ="), "teclado", "TecladoDaJanela") is None
    assert _linha_da_chamada(fonte.replace("self._build_body()", "pass"), "self._build_body") is None
    assert _linha_da_criacao("class Outra:\n    pass\n", "teclado", "TecladoDaJanela") is None


def test_o_verificador_ve_o_esc_ceder_e_nao_ceder():
    assert esc_cede_a_edicao(_JANELA_SINTETICA.format(condicao=_CEDE))
    assert esc_cede_a_edicao(_JANELA_SINTETICA.format(condicao="not self.teclado.editando()"))
    assert not esc_cede_a_edicao(_JANELA_SINTETICA.format(condicao="True")), "sem pergunta nenhuma o Esc não cede"
    assert not esc_cede_a_edicao(_JANELA_SINTETICA.format(condicao="self._teclado_editando()")), "sem o `not` o Esc só valeria durante a edição: o contrário"
    assert not esc_cede_a_edicao(_JANELA_SINTETICA.format(condicao="not self._outra_coisa()")), "um `not` sobre outra pergunta não conta"
    assert not esc_cede_a_edicao("class MainWindow:\n    def eventFilter(self, w, e):\n        return False\n"), "sem ramo do Esc"
    assert not esc_cede_a_edicao("class Outra:\n    pass\n")


def test_o_verificador_acha_os_metodos_os_filtros_e_os_exec():
    fonte = "class A:\n    def a(self): ...\n    def b(self):\n        self.t.table.installEventFilter(self)\n        x.exec()\n    c = 1\n"
    assert _metodos(fonte, "A") == {"a", "b"}
    assert _metodos(fonte, "B") == set()
    assert _instalacoes_do_filtro(fonte, "A") == {"self.t.table"}
    assert _instalacoes_do_filtro(fonte, "B") == set()
    com_apelido = "class A:\n    def a(self):\n        t = self.janela.table\n        t.installEventFilter(self)\n        e = Editor()\n        e.installEventFilter(self)\n"
    assert _instalacoes_do_filtro(com_apelido, "A") == {"self.janela.table", "e"}, "o apelido da tabela vale pelo que guarda; o de uma chamada fica como está"
    assert _chama_exec(fonte) == ["x.exec"]
    assert _chama_exec("a.b()\nc.execute()\n") == [], "`execute` não é `exec`"
    assert _chama_exec("d.exec_()\n") == ["d.exec_"]
    assert _importa(_JANELA_SINTETICA.format(condicao=_CEDE), "teclado_ui", "TecladoDaJanela")
    assert not _importa("import os\n", "teclado_ui", "TecladoDaJanela")
    assert not _importa("from teclado_ui import TecladoDaJanela\n", "teclado_ui", "TecladoDaJanela"), "o pacote usa import relativo"
    assert not _importa("from .outro import TecladoDaJanela\n", "teclado_ui", "TecladoDaJanela")
    assert not _importa("from .teclado_ui import Outra\n", "teclado_ui", "TecladoDaJanela")


# ------------------------------------------------------------------------------------------------ o código real
def _janela() -> str:
    return JANELA.read_text(encoding="utf-8")


def test_no_codigo_real_o_verificador_enxerga_o_ramo_do_esc_e_o_init():
    """Controle positivo contra o arquivo de verdade: se `eventFilter` ou `__init__` mudassem de forma e o verificador deixasse de achá-los, os
    testes abaixo passariam a falhar (ou, pior, a passar por não achar nada para conferir)."""
    assert _ramo_do_esc(_janela()) is not None, "MainWindow.eventFilter não tem o ramo do Esc"
    assert _linha_da_chamada(_janela(), "self._build_status_bar") is not None
    assert _linha_da_chamada(_janela(), "self._build_body") is not None


def test_a_janela_importa_a_janela_do_teclado_pelo_nome():
    assert _importa(_janela(), "teclado_ui", "TecladoDaJanela"), "main_window.py não faz `from .teclado_ui import TecladoDaJanela`"


def test_a_janela_cria_o_teclado_depois_da_tabela_e_da_barra_de_status():                                                # T3-2
    criacao = _linha_da_criacao(_janela(), "teclado", "TecladoDaJanela")
    assert criacao is not None, "MainWindow.__init__ não cria `self.teclado = TecladoDaJanela(self)`"
    corpo, barra = _linha_da_chamada(_janela(), "self._build_body"), _linha_da_chamada(_janela(), "self._build_status_bar")
    assert corpo is not None and corpo < criacao, "`self.teclado` é criado antes de a tabela existir (`_build_body`): não teria o que filtrar"
    assert barra is not None and barra < criacao, "`self.teclado` é criado antes de a barra de status existir: não teria onde escrever"


def test_o_esc_do_aplicativo_cede_enquanto_ha_edicao_pelo_teclado():                                                      # T3-9
    assert esc_cede_a_edicao(_janela()), "o ramo do Esc de MainWindow.eventFilter não tem `and not self._teclado_editando()`: cancelar uma edição voltaria de página"


def test_a_pergunta_da_janela_chega_ao_teclado():                                                                         # T3-9
    metodo = _metodo(_janela(), "MainWindow", "_teclado_editando")
    assert metodo is not None, "MainWindow não tem `_teclado_editando`"
    assert any(nome.rsplit(".", 1)[-1] == "editando" for nome in _chamadas(metodo)), "`_teclado_editando` não pergunta ao `teclado.editando()`"


def test_a_tabela_tem_editar_celula_atual_e_o_enter_antigo_passa_por_ela():                                                # T3-2 / T3-11
    fonte = TABELA.read_text(encoding="utf-8")
    assert _metodo(fonte, "CommandTableWidget", "editar_celula_atual") is not None, "CommandTableWidget não tem `editar_celula_atual`"
    filtro = _metodo(fonte, "CommandTableWidget", "eventFilter")
    assert filtro is not None and "self.editar_celula_atual" in _chamadas(filtro), "o Enter antigo da tabela não chama `editar_celula_atual`: F2 e Enter teriam dois caminhos"


def test_o_teclado_da_janela_oferece_toda_a_porta():
    """A `Porta` (a lista do que a ligação chama) lida do código-fonte, sem importar nada: um método a menos só falharia numa tecla, com o Qt."""
    porta = _metodos(LIGACAO.read_text(encoding="utf-8"), "Porta")
    assert porta >= {"marcar", "desmarcar", "dica", "aplicar_alvo", "suspender_atalhos", "ligar_relogio"}, f"o verificador não leu a Porta: {sorted(porta)}"
    assert TECLADO_UI.exists(), "automationstudio/teclado_ui.py não existe"
    oferece = _metodos(TECLADO_UI.read_text(encoding="utf-8"), "TecladoDaJanela")
    assert sorted(porta - oferece) == [], f"TecladoDaJanela não oferece o que a ligação chama: {sorted(porta - oferece)}"
    assert "editando" in oferece, "TecladoDaJanela não oferece `editando()` (a janela pergunta por ele)"


def test_o_filtro_de_eventos_e_instalado_na_tabela():                                                                      # T3-2
    instalacoes = _instalacoes_do_filtro(TECLADO_UI.read_text(encoding="utf-8"), "TecladoDaJanela")
    assert any(receptor.endswith(".table") for receptor in instalacoes), f"nenhum filtro na tabela de comandos: {sorted(instalacoes)}"


def test_o_teclado_da_janela_nunca_abre_um_laco_aninhado():                                                                 # T3-5
    achados = _chama_exec(TECLADO_UI.read_text(encoding="utf-8"))
    assert achados == [], f"teclado_ui.py chama {achados}: um laço aninhado dentro do filtro reentraria no controlador (use `open()`)"


def test_o_teclado_da_janela_registra_os_erros_no_log_de_execucao():                                                       # T3-13
    assert _importa(TECLADO_UI.read_text(encoding="utf-8"), "core", "_append_runtime_log"), "teclado_ui.py não importa `_append_runtime_log` (erro de Qt sem rastro)"
