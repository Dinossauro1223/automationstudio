"""A ligação do aviso de administrador (F51) com a janela principal, conferida no código-fonte.

O rótulo na barra de status e os sinais do motor só existem com o Qt de verdade e uma janela aberta. Este teste roda em qualquer
lugar e protege a ligação em si. Se uma destas linhas sumir, o programa continua abrindo e o aviso nunca aparece:

* a janela principal cria `self.elevacao` e chama `self.elevacao.ligar(self.status_bar, self.bridge)` em `_connect_bridge`.
  A ordem importa: `ligar` usa `self.status_bar` e `self.bridge`, que precisam existir antes (se não existirem, o programa nem
  abre: AttributeError na partida);
* o controlador põe o rótulo na barra, esconde (depois de adicionar) e liga os dois sinais do motor.

A lógica (regra, textos, leitura do Windows, vigia, controlador, uma execução de verdade) é provada em
tests/unit/test_aviso_administrador.py e test_aviso_administrador_ui.py. Aqui há controles positivo e negativo sobre trechos
sintéticos; só depois vem a conferência do código real.
"""
import ast
import os
import pathlib

ROOT = pathlib.Path(os.environ.get("AS_ROOT") or pathlib.Path(__file__).resolve().parents[2])
PACOTE = ROOT / "automationstudio"
JANELA = PACOTE / "main_window.py"
CONTROLADOR = PACOTE / "elevacao_ui.py"
REGRA = PACOTE / "elevacao.py"


def _classe(fonte: str, nome: str):
    for no in ast.walk(ast.parse(fonte)):
        if isinstance(no, ast.ClassDef) and no.name == nome:
            return no
    return None


def _metodo(fonte: str, classe: str, nome: str):
    dono = _classe(fonte, classe)
    if dono is None:
        return None
    for item in dono.body:
        if isinstance(item, ast.FunctionDef) and item.name == nome:
            return item
    return None


def linhas_das_chamadas(fonte: str, classe: str, metodo: str) -> dict[str, list[int]] | None:
    """Cada chamada do método escrita por inteiro (`ast.unparse`) e as linhas onde aparece; None se não existe."""
    corpo = _metodo(fonte, classe, metodo)
    if corpo is None:
        return None
    achadas: dict[str, list[int]] = {}
    for no in ast.walk(corpo):
        if isinstance(no, ast.Call):
            achadas.setdefault(ast.unparse(no), []).append(no.lineno)
    return achadas


def linhas_das_atribuicoes(fonte: str, classe: str, metodo: str) -> dict[str, list[int]] | None:
    """Cada atribuição simples do método escrita por inteiro ("alvo = valor") e as linhas; None se não existe."""
    corpo = _metodo(fonte, classe, metodo)
    if corpo is None:
        return None
    achadas: dict[str, list[int]] = {}
    for no in ast.walk(corpo):
        if isinstance(no, ast.Assign) and len(no.targets) == 1:
            achadas.setdefault(f"{ast.unparse(no.targets[0])} = {ast.unparse(no.value)}", []).append(no.lineno)
    return achadas


def importa(fonte: str, modulo: str, nome: str) -> bool:
    """O arquivo tem `from .<modulo> import ..., <nome>, ...`?"""
    for no in ast.walk(ast.parse(fonte)):
        if isinstance(no, ast.ImportFrom) and no.level == 1 and no.module == modulo:
            return any(alias.name == nome for alias in no.names)
    return False


def conferir_a_janela(fonte: str, classe: str) -> list[str]:
    """O que a janela perdeu da ligação (lista vazia se está tudo)."""
    problemas = []
    iniciar = linhas_das_chamadas(fonte, classe, "__init__")
    criar = linhas_das_atribuicoes(fonte, classe, "__init__")
    ligar = linhas_das_chamadas(fonte, classe, "_connect_bridge")
    if iniciar is None or criar is None:
        return [f"{classe}.__init__ não existe"]
    criacao = criar.get("self.elevacao = ControladorElevacao(self)")
    barra = iniciar.get("self._build_status_bar()")
    ponte = iniciar.get("self._connect_bridge()")
    ponte_criada = criar.get("self.bridge = EngineBridge()")
    if not criacao:
        problemas.append("o __init__ não cria self.elevacao = ControladorElevacao(self)")
    if not barra:
        problemas.append("o __init__ não chama self._build_status_bar()")
    if not ponte:
        problemas.append("o __init__ não chama self._connect_bridge()")
    if not ponte_criada:
        problemas.append("o __init__ não cria self.bridge = EngineBridge()")
    if criacao and ponte and not criacao[0] < ponte[0]:
        problemas.append("self.elevacao é criado DEPOIS de _connect_bridge(): o `ligar` encontraria o atributo faltando")
    if barra and ponte and not barra[0] < ponte[0]:
        problemas.append("a barra de status é criada DEPOIS de _connect_bridge(): o `ligar` precisa de self.status_bar")
    if ponte_criada and ponte and not ponte_criada[0] < ponte[0]:
        problemas.append("self.bridge é criado DEPOIS de _connect_bridge()")
    if ligar is None:
        problemas.append("_connect_bridge não existe")
    elif "self.elevacao.ligar(self.status_bar, self.bridge)" not in ligar:
        problemas.append("_connect_bridge não chama self.elevacao.ligar(self.status_bar, self.bridge)")
    return problemas


# método do controlador -> chamadas (escritas por inteiro) que ele precisa fazer
LIGACOES_DO_CONTROLADOR = {
    "ligar": ("barra_de_status.addPermanentWidget(self.rotulo)", "self.rotulo.setVisible(False)",
              "ponte.event_fired.connect(self.olhar)", "ponte.state_changed.connect(self.estado_mudou)"),
    "olhar": ("self.vigia.olhar()", "self._mostrar(aviso)"),
    "estado_mudou": ("self.nova_rodada()",),
    "nova_rodada": ("self.vigia.nova_rodada()", "self.rotulo.setVisible(False)"),
    "_mostrar": ("self.rotulo.setVisible(True)", "self._piscar()", "self.rotulo.setText(aviso.curto)",
                 "self.rotulo.setToolTip(aviso.longo)"),
}


def conferir_o_controlador(fonte: str, classe: str, ligacoes: dict[str, tuple[str, ...]]) -> list[str]:
    problemas = []
    for metodo, esperadas in ligacoes.items():
        achadas = linhas_das_chamadas(fonte, classe, metodo)
        if achadas is None:
            problemas.append(f"{metodo}: não existe")
            continue
        problemas += [f"{metodo}: {chamada}" for chamada in esperadas if chamada not in achadas]
    ligar = linhas_das_chamadas(fonte, classe, "ligar") or {}
    adicionar = ligar.get("barra_de_status.addPermanentWidget(self.rotulo)")
    esconder = ligar.get("self.rotulo.setVisible(False)")
    if adicionar and esconder and not adicionar[0] < esconder[0]:
        problemas.append("ligar: esconde o rótulo ANTES de adicioná-lo à barra (a barra pode mostrá-lo de novo)")
    return problemas


# ------------------------------------------------------------------------------------------- controles
_JANELA_SINTETICA = (
    "class J:\n"
    "    def __init__(self):\n"
    "        self.bridge = EngineBridge()\n"
    "        self.elevacao = ControladorElevacao(self)\n"
    "        self._build_status_bar()\n"
    "        self._connect_bridge()\n"
    "    def _connect_bridge(self):\n"
    "        self.elevacao.ligar(self.status_bar, self.bridge)\n"
)


def test_controle_positivo_a_janela_sintetica_completa_nao_perde_nada():
    assert conferir_a_janela(_JANELA_SINTETICA, "J") == []


def test_controle_negativo_a_conferencia_da_janela_aponta_o_que_sumiu():
    sem_ligar = _JANELA_SINTETICA.replace("        self.elevacao.ligar(self.status_bar, self.bridge)\n", "        pass\n")
    assert conferir_a_janela(sem_ligar, "J") == ["_connect_bridge não chama self.elevacao.ligar(self.status_bar, self.bridge)"]
    ligar_errado = _JANELA_SINTETICA.replace("self.elevacao.ligar(self.status_bar, self.bridge)", "self.elevacao.ligar(self.bridge)")
    assert conferir_a_janela(ligar_errado, "J") == ["_connect_bridge não chama self.elevacao.ligar(self.status_bar, self.bridge)"]
    sem_criar = _JANELA_SINTETICA.replace("        self.elevacao = ControladorElevacao(self)\n", "")
    assert conferir_a_janela(sem_criar, "J") == ["o __init__ não cria self.elevacao = ControladorElevacao(self)"]
    criar_tarde = _JANELA_SINTETICA.replace(
        "        self.elevacao = ControladorElevacao(self)\n        self._build_status_bar()\n        self._connect_bridge()\n",
        "        self._build_status_bar()\n        self._connect_bridge()\n        self.elevacao = ControladorElevacao(self)\n")
    assert [p for p in conferir_a_janela(criar_tarde, "J") if "DEPOIS" in p] == [
        "self.elevacao é criado DEPOIS de _connect_bridge(): o `ligar` encontraria o atributo faltando"]
    barra_tarde = _JANELA_SINTETICA.replace(
        "        self._build_status_bar()\n        self._connect_bridge()\n",
        "        self._connect_bridge()\n        self._build_status_bar()\n")
    assert conferir_a_janela(barra_tarde, "J") == [
        "a barra de status é criada DEPOIS de _connect_bridge(): o `ligar` precisa de self.status_bar"]
    ponte_tarde = _JANELA_SINTETICA.replace(
        "        self.bridge = EngineBridge()\n        self.elevacao = ControladorElevacao(self)\n        self._build_status_bar()\n"
        "        self._connect_bridge()\n",
        "        self.elevacao = ControladorElevacao(self)\n        self._build_status_bar()\n        self._connect_bridge()\n"
        "        self.bridge = EngineBridge()\n")
    assert conferir_a_janela(ponte_tarde, "J") == ["self.bridge é criado DEPOIS de _connect_bridge()"]
    assert conferir_a_janela("class J:\n    pass\n", "J") == ["J.__init__ não existe"]
    assert conferir_a_janela(_JANELA_SINTETICA, "Outra") == ["Outra.__init__ não existe"]


def test_controle_o_import_e_achado_so_do_modulo_certo():
    assert importa("from .elevacao_ui import ControladorElevacao\n", "elevacao_ui", "ControladorElevacao")
    assert importa("from .elevacao_ui import A, ControladorElevacao\n", "elevacao_ui", "ControladorElevacao")
    assert not importa("from .elevacao_ui import Outro\n", "elevacao_ui", "ControladorElevacao")
    assert not importa("from .ativacao_ui import ControladorElevacao\n", "elevacao_ui", "ControladorElevacao")
    assert not importa("from elevacao_ui import ControladorElevacao\n", "elevacao_ui", "ControladorElevacao")  # não é relativo
    assert not importa("x = 1\n", "elevacao_ui", "ControladorElevacao")


_CONTROLADOR_SINTETICO = (
    "class C:\n"
    "    def ligar(self, barra_de_status, ponte):\n"
    "        barra_de_status.addPermanentWidget(self.rotulo)\n"
    "        self.rotulo.setVisible(False)\n"
    "        ponte.event_fired.connect(self.olhar)\n"
    "        ponte.state_changed.connect(self.estado_mudou)\n"
)
_LIGACOES_SINTETICAS = {"ligar": LIGACOES_DO_CONTROLADOR["ligar"]}


def test_controle_positivo_o_controlador_sintetico_completo_nao_perde_nada():
    assert conferir_o_controlador(_CONTROLADOR_SINTETICO, "C", _LIGACOES_SINTETICAS) == []


def test_controle_negativo_a_conferencia_do_controlador_aponta_o_que_sumiu():
    sem_sinal = _CONTROLADOR_SINTETICO.replace("        ponte.event_fired.connect(self.olhar)\n", "")
    assert conferir_o_controlador(sem_sinal, "C", _LIGACOES_SINTETICAS) == ["ligar: ponte.event_fired.connect(self.olhar)"]
    sem_barra = _CONTROLADOR_SINTETICO.replace("        barra_de_status.addPermanentWidget(self.rotulo)\n", "")
    assert conferir_o_controlador(sem_barra, "C", _LIGACOES_SINTETICAS) == [
        "ligar: barra_de_status.addPermanentWidget(self.rotulo)"]
    esconder_antes = _CONTROLADOR_SINTETICO.replace(
        "        barra_de_status.addPermanentWidget(self.rotulo)\n        self.rotulo.setVisible(False)\n",
        "        self.rotulo.setVisible(False)\n        barra_de_status.addPermanentWidget(self.rotulo)\n")
    assert conferir_o_controlador(esconder_antes, "C", _LIGACOES_SINTETICAS) == [
        "ligar: esconde o rótulo ANTES de adicioná-lo à barra (a barra pode mostrá-lo de novo)"]
    assert conferir_o_controlador("class C:\n    pass\n", "C", _LIGACOES_SINTETICAS) == ["ligar: não existe"]
    assert linhas_das_chamadas(_CONTROLADOR_SINTETICO, "Outra", "ligar") is None
    assert linhas_das_atribuicoes(_CONTROLADOR_SINTETICO, "C", "inexistente") is None


# ------------------------------------------------------------------------------------------- o código real
def test_a_janela_principal_importa_o_controlador():
    assert importa(JANELA.read_text(encoding="utf-8"), "elevacao_ui", "ControladorElevacao")


def test_a_janela_principal_cria_o_controlador_e_liga_na_ordem_certa():
    assert conferir_a_janela(JANELA.read_text(encoding="utf-8"), "MainWindow") == []


def test_o_controlador_poe_o_rotulo_na_barra_liga_os_sinais_e_mostra_o_aviso():
    assert conferir_o_controlador(CONTROLADOR.read_text(encoding="utf-8"), "ControladorElevacao", LIGACOES_DO_CONTROLADOR) == []


def test_o_modulo_da_regra_nao_depende_de_qt_nem_do_resto_do_programa():
    """elevacao.py precisa continuar testável sem Qt (e sem psutil, que o programa não usa): só biblioteca padrão."""
    arvore = ast.parse(REGRA.read_text(encoding="utf-8"))
    importados = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            importados |= {alias.name.split(".")[0] for alias in no.names}
        elif isinstance(no, ast.ImportFrom):
            assert no.level == 0, "elevacao.py importa do próprio programa: " + ast.unparse(no)
            importados.add((no.module or "").split(".")[0])
    assert importados <= {"__future__", "enum", "ntpath", "os", "time", "dataclasses", "typing", "ctypes"}, importados
