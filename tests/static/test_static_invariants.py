"""Invariantes estáticos do código (funções puras em testsupport/static_checks.py).

Cada invariante tem três partes:
  * controle NEGATIVO: um trecho sintético com o defeito plantado, que a checagem TEM de acusar;
  * controle POSITIVO: um trecho correto, que ela não pode acusar;
  * a verificação do código REAL do projeto.
Sem os dois primeiros, "o código real passou" poderia significar só "a checagem está quebrada".
Os defeitos plantados são os que o Ponto 1 achou no 25.3 (nome inexistente, método duplicado, sinal sem connect, ...).
"""
import importlib
import json
import os
import pathlib
import re

import pytest

from automationstudio import core
from testsupport import golden
from testsupport import static_checks as sc

ROOT = pathlib.Path(os.environ.get("AS_ROOT") or pathlib.Path(__file__).resolve().parents[2])
PKG = ROOT / "automationstudio"
TESTS = ROOT / "tests"
_CACHE: dict = {}

# Linhas de base dos catracas (ratchets): só podem DIMINUIR. Ao melhorar, baixe o número aqui no mesmo commit.
BASE_IMPORT_ESTRELA = 27
BASE_METODOS_SEM_REFERENCIA = 34


def _fontes() -> dict[str, str]:
    if "fontes" not in _CACHE:
        _CACHE["fontes"] = {p.stem: p.read_text(encoding="utf-8") for p in sorted(PKG.glob("*.py"))}
    return _CACHE["fontes"]


def _bats() -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(ROOT.glob("*.bat"))}


def _fontes_de_teste() -> dict[str, str]:
    return {str(p.relative_to(ROOT)).replace("\\", "/"): p.read_text(encoding="utf-8") for p in sorted(TESTS.rglob("*.py"))
            if "qt_stub" not in p.parts and "qt_double" not in p.parts and "__pycache__" not in p.parts}


# ----------------------------------------------------------------------------------------- nomes inexistentes
def test_nome_global_inexistente_e_detectado():
    fonte = "def abrir():\n    return KeyCode.from_char('a')\n"  # o defeito 1.04: KeyCode nunca foi importado
    assert sc.unresolved_globals(fonte, namespace=set()) == ["abrir (linha 1) usa 'KeyCode', que não existe"]


def test_nome_global_existente_nao_e_acusado():
    fonte = "import os\ndef f():\n    global contador\n    contador = len(os.listdir('.'))\n    return KeyCode\n"
    assert sc.unresolved_globals(fonte, namespace={"os", "KeyCode"}) == []


def test_nenhum_nome_global_indefinido_no_pacote():
    achados = []
    for nome, fonte in _fontes().items():
        modulo = importlib.import_module(f"automationstudio.{nome}")
        achados += [f"{nome}: {a}" for a in sc.unresolved_globals(fonte, set(vars(modulo)), nome)]
    assert achados == []


# ----------------------------------------------------------------------------------------- definições repetidas
def test_metodo_definido_duas_vezes_e_detectado():
    fonte = "class Janela:\n    def resizeEvent(self, e): pass\n    def outro(self): pass\n    def resizeEvent(self, e): pass\n"
    assert sc.duplicate_methods(fonte) == ["Janela.resizeEvent definido nas linhas [2, 4]"]


def test_property_com_setter_nao_conta_como_duplicado():
    fonte = ("class A:\n    @property\n    def x(self): return 1\n    @x.setter\n    def x(self, v): pass\n"
             "    def y(self): pass\n")
    assert sc.duplicate_methods(fonte) == []


def test_nenhuma_classe_do_pacote_define_o_mesmo_metodo_duas_vezes():
    assert {nome: sc.duplicate_methods(f) for nome, f in _fontes().items() if sc.duplicate_methods(f)} == {}


# ----------------------------------------------------------------------------------------- self._metodo() inexistente
def test_chamada_a_metodo_privado_inexistente_e_detectada():
    fontes = {"m": "class A:\n    def a(self):\n        self._sumiu()\n        self._existe()\n    def _existe(self): pass\n"}
    assert sc.unresolved_self_calls(fontes) == ["m.A chama self._sumiu() (linha 3), mas o método não existe"]


def test_metodo_herdado_de_outra_classe_nao_e_acusado():
    fontes = {"base": "class Base:\n    def _comum(self): pass\n",
              "filha": "class Filha(Base):\n    def a(self):\n        self._comum()\n"}
    assert sc.unresolved_self_calls(fontes) == []


def test_nenhuma_chamada_self_metodo_privado_sem_definicao_no_pacote():
    assert sc.unresolved_self_calls(_fontes()) == []


# ----------------------------------------------------------------------------------------- sinais sem connect
def test_sinal_de_ponte_sem_connect_e_detectado():
    fontes = {"m": "class MotorBridge(QObject):\n    chain_requested = Signal(str)\n    pronto = Signal()\n",
              "n": "ponte.pronto.connect(self.ao_ficar_pronto)\n"}
    assert sc.signals_without_connect(fontes) == ["MotorBridge.chain_requested"]


def test_sinal_com_connect_nao_e_acusado():
    fontes = {"m": "class MotorBridge(QObject):\n    pronto = Signal()\n", "n": "x.pronto.connect(f)\n"}
    assert sc.signals_without_connect(fontes) == []


def test_todo_sinal_das_pontes_tem_connect_no_pacote():
    assert sc.signals_without_connect(_fontes()) == []


# ----------------------------------------------------------------------------------------- constantes de execução
_CONSTANTES = {"TEXT_CHAR_INTERVAL", "APP_STABLE_DEFAULT_MS", "APP_AFTER_OPEN_DEFAULT"}


def test_constante_do_core_copiada_ou_rebindada_fora_do_core_e_detectada():
    fontes = {"core": "TEXT_CHAR_INTERVAL = 0.01\n",
              "input_system": "def f():\n    global TEXT_CHAR_INTERVAL\n    TEXT_CHAR_INTERVAL = 1\n",
              "outro": "def g():\n    return APP_STABLE_DEFAULT_MS\n"}
    achados = sc.rebound_core_constants(fontes, _CONSTANTES)
    assert len(achados) >= 2 and any("global TEXT_CHAR_INTERVAL" in a for a in achados) and any("APP_STABLE_DEFAULT_MS" in a for a in achados)


def test_leitura_pelo_modulo_core_nao_e_acusada():
    assert sc.rebound_core_constants({"core": "X = 1", "m": "def f():\n    return core.TEXT_CHAR_INTERVAL\n"}, _CONSTANTES) == []


def test_constantes_de_execucao_tem_fonte_unica_no_core():
    assert sc.rebound_core_constants(_fontes(), _CONSTANTES) == []


# ----------------------------------------------------------------------------------------- texto
def test_barra_n_literal_e_detectada_e_quebra_de_linha_real_nao():
    assert sc.literal_backslash_n('x = "a\\\\nb"\n') == [1]
    assert sc.literal_backslash_n('x = "a\\nb"\n') == []


def test_nenhuma_string_do_pacote_tem_barra_n_literal():
    assert {n: sc.literal_backslash_n(f) for n, f in _fontes().items() if sc.literal_backslash_n(f)} == {}


# ----------------------------------------------------------------------------------------- catracas
def test_contagem_de_import_estrela_funciona():
    assert sc.star_import_count({"a": "from .core import *\nfrom os import path\n", "b": "from x import *\n"}) == 2


def test_import_estrela_nao_aumenta():
    # `from .core import *` copia constantes por valor (a raiz dos achados 1.04 e 1.05). Reduzir é bem-vindo.
    assert sc.star_import_count(_fontes()) <= BASE_IMPORT_ESTRELA


def test_deteccao_de_metodo_sem_referencia_funciona():
    fontes = {"m": "class A:\n    def usado(self): pass\n    def orfao(self): pass\n    def b(self):\n        self.usado()\n"}
    assert sc.unreferenced_methods(fontes) == ["m:3 orfao", "m:4 b"]
    assert sc.unreferenced_methods(fontes, extra_text="orfao b") == []


def test_codigo_sem_referencia_nao_aumenta():
    # Muitos destes são ações da interface que ainda não têm botão (exportar/excluir mapa: Ponto 3). Reduzir é bem-vindo.
    assert len(sc.unreferenced_methods(_fontes())) <= BASE_METODOS_SEM_REFERENCIA


# ----------------------------------------------------------------------------------------- scripts e versão
def test_py_menos_3_nos_scripts_e_detectado():
    assert sc.hardcoded_python3({"a.bat": "echo oi\r\npy.exe -3 app.py\r\n"}) == ["a.bat:2"]
    assert sc.hardcoded_python3({"a.bat": "py.exe -%AS_PY% app.py\r\n"}) == []


def test_scripts_nao_escolhem_py_menos_3():
    textos = {nome: dados.decode("utf-8", "replace") for nome, dados in _bats().items()}
    assert textos and sc.hardcoded_python3(textos) == []


def test_fim_de_linha_lf_no_bat_e_detectado():
    assert sc.bat_with_lf_only({"ruim.bat": b"a\nb\n", "bom.bat": b"a\r\nb\r\n", "vazio.bat": b""}) == ["ruim.bat"]


def test_scripts_bat_tem_fim_de_linha_do_windows():
    assert _bats() and sc.bat_with_lf_only(_bats()) == []


# Pastas com acento no nome do usuário (C:\\Users\\João): o Iniciar.bat da 25.5 dizia "pythonw.exe nao encontrado" e o log misturava
# duas codificações. O trecho abaixo é o do script antigo, com o defeito.
_INICIAR_ANTIGO = (
    'set "PYTHON="\r\n'
    '>>"%LOG%" echo Python selecionado pelo Launcher:\r\n'
    'py.exe -%AS_PY% -c "import sys; print(sys.executable)" >>"%LOG%" 2>&1\r\n'
    'if errorlevel 1 (\r\n'
    '    >>"%LOG%" echo ERRO: py.exe nao encontrado.\r\n'
    ')\r\n'
    'for /f "delims=" %%P in (\'py.exe -%AS_PY% -c "import sys; print(sys.executable)"\') do set "PYTHON=%%P"\r\n'
)


def test_python_que_grava_no_log_sem_modo_utf8_e_detectado():
    assert sc.bat_python_sem_utf8({"a.bat": _INICIAR_ANTIGO}) == ["a.bat:3"]


def test_python_em_modo_utf8_ou_sem_gravar_no_log_nao_e_acusado():
    com_utf8 = 'set "PYTHONUTF8=1"\r\n' + _INICIAR_ANTIGO
    assert sc.bat_python_sem_utf8({"a.bat": com_utf8}) == []
    assert sc.bat_python_sem_utf8({"a.bat": 'py.exe -3.14 -c "import sys" >nul 2>&1\r\n'}) == []
    assert sc.bat_python_sem_utf8({"a.bat": "rem py.exe -3.14 -c x >> log.txt\r\n"}) == []


def test_o_modo_utf8_desligado_de_novo_volta_a_ser_cobrado():
    texto = 'set "PYTHONUTF8=1"\r\nset "PYTHONUTF8="\r\npy.exe -3.14 -c "x" >>"%LOG%" 2>&1\r\n'
    assert sc.bat_python_sem_utf8({"a.bat": texto}) == ["a.bat:3"]


def test_scripts_bat_rodam_o_python_em_modo_utf8_quando_gravam_no_log():
    textos = {nome: dados.decode("utf-8") for nome, dados in _bats().items()}
    assert textos and sc.bat_python_sem_utf8(textos) == []


def test_for_f_sobre_a_saida_do_python_e_detectado():
    assert sc.bat_captura_texto_do_python({"a.bat": _INICIAR_ANTIGO}) == ["a.bat:7"]
    assert sc.bat_captura_texto_do_python({"a.bat": 'for /f "tokens=1,2 delims=." %%A in ("%AS_PY%") do echo %%A\r\n'}) == []


def test_scripts_bat_nao_copiam_o_caminho_do_python_com_for_f():
    textos = {nome: dados.decode("utf-8") for nome, dados in _bats().items()}
    assert textos and sc.bat_captura_texto_do_python(textos) == []


def test_bat_com_acento_e_detectado():
    assert sc.bat_with_non_ascii({"a.bat": "rem usu\u00e1rio\r\n".encode("utf-8")}) == ["a.bat"]
    assert sc.bat_with_non_ascii({"a.bat": b"rem usuario\r\n"}) == []


def test_scripts_bat_so_tem_ascii():
    assert _bats() and sc.bat_with_non_ascii(_bats()) == []


def test_texto_com_acento_em_cp1252_nao_e_utf8_valido():
    # O mecanismo do achado: o Python sem modo UTF-8 escreve cp1252; o cmd.exe com chcp 65001 lê UTF-8.
    assert "jo\u00e3o".encode("cp1252") == b"jo\xe3o"
    with pytest.raises(UnicodeDecodeError):
        b"jo\xe3o".decode("utf-8")
    assert "jo\u00e3o".encode("utf-8").decode("utf-8") == "jo\u00e3o"


def test_versoes_diferentes_sao_detectadas():
    assert sc.version_mismatches({"a": "25.5", "b": "25.4"}) == ["a = 25.5", "b = 25.4"]
    assert sc.version_mismatches({"a": "25.5", "b": "25.5"}) == []


def test_versao_e_a_mesma_no_codigo_no_readme_e_no_changelog():
    import automationstudio
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    changelog = (ROOT / "md" / "CHANGELOG_V25.md").read_text(encoding="utf-8")
    primeira_secao = re.search(r"^## (\d+\.\d+)", changelog, re.MULTILINE)
    cabecalho_readme = re.search(r"^# .*AS (\d+\.\d+)", readme, re.MULTILINE)
    versoes = {"__init__": automationstudio.__version__, "core.APP_VERSION": core.APP_VERSION,
               "README (título)": cabecalho_readme.group(1) if cabecalho_readme else "?",
               "CHANGELOG_V25 (1ª seção)": primeira_secao.group(1) if primeira_secao else "?"}
    assert sc.version_mismatches(versoes) == [], versoes


def test_titulo_da_janela_nao_tem_versao_escrita_a_mao():
    assert not re.search(r"AS \d+\.\d+", _fontes()["main_window"])


def test_instalador_que_esquece_um_pacote_e_detectado():
    instalador = 'py -3.14 -m pip install "PySide6>=6.6"\r\n'
    assert sc.installer_requirements_mismatch(instalador, "PySide6>=6.6\npynput>=1.7\n") == [
        "pynput está no requirements.txt mas o instalador não o instala"]
    assert sc.installer_requirements_mismatch(instalador, "PySide6>=6.6\n") == []


def test_instalador_instala_tudo_o_que_o_requirements_pede():
    instalador = (ROOT / "Instalar_Dependencias_Global.bat").read_text(encoding="utf-8", errors="replace")
    assert sc.installer_requirements_mismatch(instalador, (ROOT / "requirements.txt").read_text(encoding="utf-8")) == []


# ----------------------------------------------------------------------------------------- Python 3.14
def test_import_de_modulo_removido_da_biblioteca_padrao_e_detectado():
    achados = sc.removed_stdlib_imports({"m": "import imp\nfrom cgi import escape\nimport os\nfrom .x import cgi\n"})
    assert achados == ["m:1 import imp", "m:2 from cgi import ..."]


def test_pacote_nao_importa_modulos_removidos_do_python():
    assert sc.removed_stdlib_imports(_fontes()) == []


def test_aviso_de_sintaxe_e_detectado():
    assert len(sc.syntax_warnings({"m": "padrao = '\\d+'\n"})) == 1 and sc.syntax_warnings({"m": "padrao = r'\\d+'\n"}) == []


def test_pacote_compila_sem_avisos_de_sintaxe():
    assert sc.syntax_warnings(_fontes()) == []


def test_saida_de_bloco_finally_e_detectada_e_o_finally_comum_nao():
    ruim = {"a": "def f():\n    try:\n        pass\n    finally:\n        return 1\n",
            "b": "for x in y:\n    try:\n        pass\n    finally:\n        continue\n",
            "c": "while True:\n    try:\n        pass\n    finally:\n        if x:\n            break\n",
            "d": "def g():\n    try:\n        pass\n    finally:\n        try:\n            pass\n        finally:\n            return 2\n"}
    assert sc.saidas_de_finally(ruim) == ["a:5 return sai de um bloco finally", "b:5 continue sai de um bloco finally",
                                          "c:6 break sai de um bloco finally", "d:8 return sai de um bloco finally"]
    bom = {"a": "def f():\n    try:\n        return 1\n    finally:\n        limpar()\n",
           "b": "try:\n    pass\nfinally:\n    for i in range(3):\n        if i:\n            break\n        continue\n",
           "c": "try:\n    pass\nfinally:\n    def interna():\n        return 1\n    outra = lambda: 2\n",
           "d": "try:\n    pass\nexcept ValueError:\n    pass\nelse:\n    pass\n"}
    assert sc.saidas_de_finally(bom) == []


def test_pacote_e_testes_nao_saem_de_um_bloco_finally_com_return_break_ou_continue():
    # No Python 3.14 isso é um SyntaxWarning (PEP 765). O ambiente de desenvolvimento deste projeto é o 3.13, que não avisa.
    assert sc.saidas_de_finally({**_fontes(), **_fontes_de_teste()}) == []


def test_caminho_de_usuario_escrito_no_codigo_e_detectado():
    assert sc.hardcoded_user_paths({"m": "p = 'C:\\\\Users\\\\Yuri\\\\x'\nq = '/home/yuri/y'\nr = 'ok'\n"}) == [
        "m:1 'C:\\\\Users\\\\Yuri\\\\x'", "m:2 '/home/yuri/y'"]


def test_pacote_nao_tem_caminho_de_usuario_escrito_no_codigo():
    assert sc.hardcoded_user_paths(_fontes()) == []


def test_arquivos_de_texto_com_bom_sao_detectados():
    assert sc.has_bom({"a.py": b"\xef\xbb\xbfx = 1", "b.py": b"x = 1"}) == ["a.py"]


def test_nenhum_arquivo_python_do_projeto_tem_bom():
    brutos = {str(p.relative_to(ROOT)): p.read_bytes() for p in list(PKG.glob("*.py")) + list(TESTS.rglob("*.py"))}
    assert sc.has_bom(brutos) == []


# ----------------------------------------------------------------------------------------- decisão D1 (botões laterais)
def test_uso_fora_dos_modulos_permitidos_e_detectado():
    fontes = {"core": "def display_mouse_button_name(n): pass\n", "main_window": "display_mouse_button_name(x)\n",
              "recorder": "y = display_mouse_button_name(b)\n", "outro": "from .core import DISPLAY_SWAPS_SIDE_BUTTONS\n"}
    achados = sc.names_used_outside(fontes, {"display_mouse_button_name", "DISPLAY_SWAPS_SIDE_BUTTONS"}, {"core", "main_window"})
    assert [a.split()[0] for a in achados] == ["outro:1", "recorder:1"]


def test_troca_de_botoes_laterais_so_existe_para_desenhar_o_mouse_virtual():
    # D1: o caminho funcional (monitor, atalhos, gravador, motor, backends) usa SEMPRE o nome cru do sistema.
    # Quem aplica a troca visual é a ponte do mouse virtual em main_window; nenhum outro módulo pode chamar.
    achados = sc.names_used_outside(_fontes(), {"display_mouse_button_name", "DISPLAY_SWAPS_SIDE_BUTTONS"}, {"core", "main_window"})
    assert achados == [], achados


# ----------------------------------------------------------------------------------------- higiene dos testes
def test_funcao_de_teste_repetida_no_mesmo_arquivo_e_detectada():
    assert sc.duplicate_toplevel_functions("def test_a(): pass\ndef test_a(): pass\ndef test_b(): pass\n") == ["test_a nas linhas [1, 2]"]


def test_nenhum_arquivo_de_teste_repete_nome_de_funcao():
    # Python deixa a segunda definição apagar a primeira: o teste "some" e ninguém vê.
    achados = {nome: sc.duplicate_toplevel_functions(fonte) for nome, fonte in _fontes_de_teste().items()
               if sc.duplicate_toplevel_functions(fonte)}
    assert achados == {}


def test_nome_de_arquivo_de_teste_repetido_e_detectado():
    assert sc.duplicate_basenames(["tests/a/test_x.py", "tests/b/test_x.py", "tests/b/test_y.py"]) == [
        "test_x.py: ['tests/a/test_x.py', 'tests/b/test_x.py']"]


def test_arquivos_de_teste_tem_nomes_unicos_no_projeto():
    # Sem __init__.py nas pastas, o pytest importa cada arquivo pelo nome simples: dois iguais colidem.
    arquivos = [c for c in _fontes_de_teste() if pathlib.PurePosixPath(c).name.startswith("test_")]
    assert arquivos and sc.duplicate_basenames(arquivos) == []


def test_espera_real_longa_e_detectada():
    assert sc.long_real_sleeps("import time\ntime.sleep(2)\ntime.sleep(0.1)\n") == ["linha 2: sleep(2)"]


def test_espera_real_e_detectada_mesmo_com_apelido_do_modulo_ou_da_funcao():
    assert sc.long_real_sleeps("import time as t\nt.sleep(3)\n") == ["linha 2: sleep(3)"]
    assert sc.long_real_sleeps("from time import sleep as dormir\ndormir(4)\n") == ["linha 2: sleep(4)"]


def test_espera_do_relogio_virtual_nao_e_espera_real():
    # relogio.sleep(1.0) só avança o tempo virtual: não pode ser apontado como teste lento.
    assert sc.long_real_sleeps("relogio.sleep(1.0)\nfake_clock.sleep(9)\nself.clock.sleep(2)\n") == []
    assert sc.long_real_sleeps("import time\nrelogio.sleep(5)\n") == []


def test_nenhum_teste_dorme_mais_de_meio_segundo_em_tempo_real():
    achados = {nome: sc.long_real_sleeps(fonte) for nome, fonte in _fontes_de_teste().items() if sc.long_real_sleeps(fonte)}
    assert achados == {}


# ----------------------------------------------------------------------------------------- testes escritos às cegas
def test_atributo_que_nenhuma_classe_define_e_detectado_nos_testes_de_janela():
    # Os testes da janela principal exigem o Qt real e foram escritos sem poder rodá-los: um nome errado só apareceria
    # na máquina do usuário. Controle negativo (nome inventado) e positivo (nome real e nome herdado do Qt).
    definidos = sc.names_defined_by_classes({"m": "class J:\n    pagina = 1\n    def abrir(self):\n        self.lista = []\n"})
    assert definidos == {"pagina", "abrir", "lista"}
    fonte = "def test_x(janela):\n    janela.abrir()\n    janela.listta\n    janela.show()\n"
    assert sc.unknown_attributes_on(fonte, {"janela"}, definidos, frozenset({"show"})) == ["linha 3: janela.listta"]
    assert sc.unknown_attributes_on("janela.abrir()\njanela.lista\n", {"janela"}, definidos) == []


def test_os_testes_de_janela_so_usam_nomes_que_existem_no_codigo():
    definidos = sc.names_defined_by_classes(_fontes())
    herdados = frozenset({"windowTitle", "show", "close", "isVisible"})  # métodos da própria QMainWindow/QWidget
    achados = {}
    for caminho, fonte in _fontes_de_teste().items():
        if caminho.endswith("tests/gui/test_main_window_smoke.py"):
            achados[caminho] = sc.unknown_attributes_on(fonte, {"janela", "painel"}, definidos, herdados)
    assert achados and all(v == [] for v in achados.values()), achados


def test_teste_de_janela_sem_isolamento_e_detectado():
    fonte = "def test_a(gui):\n    pass\ndef test_b(abrir_janela, x):\n    pass\ndef test_c(x):\n    pass\ndef ajuda(y):\n    pass\n"
    assert sc.tests_without_fixture(fonte, {"gui", "abrir_janela"}) == ["test_c"]
    assert sc.tests_without_fixture("def test_a(gui):\n    pass\n", {"gui"}) == []


def test_todo_teste_de_janela_pede_o_isolamento_de_gui():
    # `gui` instala o bloqueio de diálogos modais e do registro do Windows e, com o stub de lógica, faz o teste ser PULADO
    # (um teste de janela que não a pedisse rodaria contra uma casca vazia ou, no Qt real, poderia travar num QMessageBox).
    achados = {}
    for caminho, fonte in _fontes_de_teste().items():
        if caminho.startswith("tests/gui/") and not caminho.endswith("test_qt_isolation.py"):
            achados[caminho] = sc.tests_without_fixture(fonte, {"gui", "abrir_janela"})
    assert achados and all(v == [] for v in achados.values()), {k: v for k, v in achados.items() if v}


def test_teste_da_janela_principal_sem_o_marcador_isolado_e_detectado():
    no_modulo = "import pytest\npytestmark = [pytest.mark.gui, pytest.mark.isolado]\ndef test_a(abrir_janela):\n    pass\n"
    no_teste = "import pytest\n@pytest.mark.isolado\ndef test_a(abrir_janela):\n    pass\n"
    sem = "import pytest\npytestmark = pytest.mark.gui\ndef test_a(abrir_janela):\n    pass\ndef test_b(gui):\n    pass\n"
    assert sc.testes_sem_marcador(no_modulo, "abrir_janela", "isolado") == []
    assert sc.testes_sem_marcador(no_teste, "abrir_janela", "isolado") == []
    assert sc.testes_sem_marcador(sem, "abrir_janela", "isolado") == ["test_a"], "test_b não pede a janela principal"
    assert sc.testes_sem_marcador("def test_a(abrir_janela):\n    pass\n", "abrir_janela", "isolado") == ["test_a"]
    assert sc.testes_com_fixture(sem, "abrir_janela") == ["test_a"]


def test_todo_teste_da_janela_principal_e_marcado_isolado():
    # A janela principal só roda sem risco para a rodada se cada teste for isolado num processo com tempo limite (o lançador
    # roda `-m isolado` um por processo e o resto com `-m "not isolado"`): o travamento de 18/10/2026 derrubou a rodada inteira.
    achados, examinados = {}, 0
    for caminho, fonte in _fontes_de_teste().items():
        if "/testsupport/" in caminho or caminho.endswith("conftest.py") or "abrir_janela" not in fonte:
            continue
        if sc.testes_com_fixture(fonte, "abrir_janela"):
            examinados += 1
            achados[caminho] = sc.testes_sem_marcador(fonte, "abrir_janela", "isolado")
    assert examinados >= 1, "nenhum arquivo de teste pede a fixture abrir_janela: a checagem não está olhando nada"
    assert {k: v for k, v in achados.items() if v} == {}


# ----------------------------------------------------------------------------------------- subconjunto portátil do pytest
def _checar_portatil(fonte, conftest=False):
    from testsupport import minipytest
    return sc.fora_do_subconjunto_portatil(
        fonte, {"fake_clock", "gui"}, {"slow", "gui"}, {n for n in dir(minipytest) if not n.startswith("_")}, conftest=conftest)


def test_o_que_o_executor_minimo_nao_entende_e_detectado():
    assert _checar_portatil("import pytest\n@pytest.fixture\ndef f():\n    pass\n") == ["linha 3: fixture f definida fora do conftest.py"]
    assert _checar_portatil("def test_a(capsys):\n    pass\n") == ["linha 1: test_a pede 'capsys', que não é fixture do projeto nem parâmetro"]
    assert _checar_portatil("import pytest\n@pytest.mark.lento\ndef test_a():\n    pass\n") == ["linha 2: marcador pytest.mark.lento não declarado em pytest.ini"]
    assert _checar_portatil("import pytest\n@pytest.mark.usefixtures('gui')\ndef test_a():\n    pass\n") == ["linha 2: marcador pytest.mark.usefixtures não declarado em pytest.ini"]
    assert _checar_portatil("import pytest\nx = pytest.param(1)\n") == ["linha 2: pytest.param não existe no executor mínimo"]


def test_o_subconjunto_portatil_aceita_o_que_os_dois_executores_entendem():
    certo = ("import pytest\n\n"
             "@pytest.mark.slow\n@pytest.mark.parametrize('a,b', [(1, 2)], ids=['x'])\n"
             "def test_a(fake_clock, monkeypatch, tmp_path, a, b):\n    with pytest.raises(ValueError):\n        pass\n\n"
             "@pytest.mark.parametrize(['c'], [(1,)], ids=['y'])\n@pytest.mark.xfail(strict=True)\ndef test_b(gui, c):\n    pytest.skip('x')\n")
    assert _checar_portatil(certo) == []
    assert _checar_portatil("import pytest\n@pytest.fixture\ndef f():\n    pass\n", conftest=True) == []
    assert sc.marcadores_declarados("[pytest]\nmarkers =\n    slow: lento\n    gui: janela\naddopts = -ra\n") == {"slow", "gui"}
    assert sc.fixtures_definidas("import pytest\n@pytest.fixture(scope='session')\ndef a():\n    pass\n@pytest.fixture\ndef b():\n    pass\ndef c():\n    pass\n") == {"a", "b"}


def test_os_testes_do_projeto_so_usam_o_que_o_executor_minimo_e_o_pytest_estrito_entendem():
    # O executor mínimo roda a suíte sem instalar nada; o pytest roda a mesma suíte com --strict-markers. Um teste que usasse
    # `capsys`, `request`, `pytest.param` ou um marcador não declarado falharia em um dos dois, e só nele.
    from testsupport import minipytest
    fixtures = sc.fixtures_definidas((TESTS / "conftest.py").read_text(encoding="utf-8"))
    marcadores = sc.marcadores_declarados((ROOT / "pytest.ini").read_text(encoding="utf-8"))
    suportados = {n for n in dir(minipytest) if not n.startswith("_")}
    assert fixtures and marcadores, "não consegui ler as fixtures do conftest ou os marcadores do pytest.ini"
    achados, examinados = {}, 0
    for caminho, fonte in _fontes_de_teste().items():
        nome = caminho.rsplit("/", 1)[-1]
        if not (nome.startswith("test_") or nome == "conftest.py") or "/testsupport/" in caminho:
            continue
        examinados += 1
        problemas = sc.fora_do_subconjunto_portatil(fonte, fixtures, marcadores, suportados, conftest=nome == "conftest.py")
        if problemas:
            achados[caminho] = problemas
    assert examinados > 20, f"só {examinados} arquivos examinados: a checagem não está olhando os testes"
    assert achados == {}, achados


# ----------------------------------------------------------------------------------------- arquivos de referência (golden)
def test_golden_sem_cenario_e_detectado_como_orfao():
    assert sc.golden_orfaos(["a", "b"], 'golden.comparar("a", x)') == ["b"]
    assert sc.golden_orfaos(["a"], 'NOMES = {"x": "a"}') == []
    assert sc.golden_orfaos([], "") == []


def test_todo_golden_e_usado_por_algum_cenario():
    # Um golden que nenhum cenário compara é lixo que parece garantia (ou o resto de um cenário apagado).
    fontes = "\n".join(fonte for caminho, fonte in _fontes_de_teste().items() if caminho.startswith("tests/scenarios/"))
    nomes = golden.nomes_existentes()
    assert nomes, "nenhum golden: os cenários não teriam com o que comparar"
    assert sc.golden_orfaos(nomes, fontes) == []


def test_todo_golden_esta_no_formato_que_o_programa_grava():
    # Se alguém editar um golden à mão (ou o gerar por outro caminho) o arquivo deixa de ser o que `serializar` produz:
    # o diff de uma atualização futura ficaria cheio de ruído e esconderia a mudança real.
    fora_do_formato = []
    for nome in golden.nomes_existentes():
        texto = golden.caminho_do(nome).read_text(encoding="utf-8")
        if texto != golden.serializar(json.loads(texto)):  # read_text já traduz CRLF: um checkout do Windows não reprova
            fora_do_formato.append(nome)
    assert fora_do_formato == []


def test_a_rodada_de_atualizacao_dos_golden_nunca_passa_como_verificacao():
    # `comparar` grava o arquivo e REPROVA o teste quando AS_ATUALIZAR_GOLDEN=1: quem atualiza sem ler o diff precisa
    # rodar de novo sem a variável para ver verde. Aqui o teste prova que o mecanismo existe, sem gravar nada em golden/.
    texto = (pathlib.Path(golden.__file__)).read_text(encoding="utf-8")
    assert "raise AssertionError" in texto.split("def comparar", 1)[1].split("esperado = json.loads", 1)[0]


def test_o_qt_de_mentira_so_existe_quando_foi_pedido():
    # AS_TEST_QT_STUB=1 troca o PySide6 por um stub que só serve aos testes de lógica. Se ele estiver ativo SEM o pedido,
    # um teste de interface passaria contra uma casca vazia e daria falsa segurança.
    try:
        pyside = importlib.import_module("PySide6")
    except ImportError:
        pytest.skip("PySide6 não instalado")
    marca = getattr(pyside, "__as_stub__", False)
    if marca:
        assert os.environ.get("AS_TEST_QT_STUB") == ("widgets" if marca == "widgets" else "1")
