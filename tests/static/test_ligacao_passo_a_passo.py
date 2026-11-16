"""A ligação do passo a passo (F52), conferida no código-fonte.

O Qt de verdade, a janela principal aberta e o Windows só existem na máquina de quem usa. Este teste roda em qualquer lugar e
protege as ligações em si. Se uma destas linhas sumir, o programa continua abrindo e o passo a passo some ou erra em silêncio:

* o editor tem o sinal `passo_a_passo_requested` e os DOIS menus ("Mais…" e o botão direito) o emitem;
* a janela principal cria `self.passo` e liga a tabela de comandos e a ponte do motor a ele, DEPOIS de os dois existirem;
* o motor começa sem gancho (`passo_a_passo = None`, e então nada muda) e o consulta ANTES de esperar o momento de cada
  comando, que é o que faz o intervalo planejado ser pulado;
* a janelinha de controle é sempre por cima e NÃO aceita o foco, e nada nela puxa o foco. Se ela aceitasse, clicar em "Próximo
  passo" tiraria o foco do programa de destino e as teclas do próximo comando cairiam dentro do Automation Studio.

A lógica e o motor de verdade estão em tests/unit/test_passo_a_passo*.py e tests/engine/test_passo_a_passo_motor.py. Aqui há
controles positivo e negativo sobre trechos sintéticos (cada conferência tem de aceitar o certo e acusar cada falta); só depois
vem a conferência do código real.
"""
import ast
import os
import pathlib

ROOT = pathlib.Path(os.environ.get("AS_ROOT") or pathlib.Path(__file__).resolve().parents[2])
PACOTE = ROOT / "automationstudio"
JANELA = PACOTE / "main_window.py"
EDITOR = PACOTE / "command_editor.py"
MOTOR = PACOTE / "input_system.py"
JANELINHA = PACOTE / "passo_a_passo_ui.py"


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
    """Cada chamada do método escrita por inteiro (`ast.unparse`) e as linhas onde aparece; None se o método não existe."""
    corpo = _metodo(fonte, classe, metodo)
    if corpo is None:
        return None
    achadas: dict[str, list[int]] = {}
    for no in ast.walk(corpo):
        if isinstance(no, ast.Call):
            achadas.setdefault(ast.unparse(no), []).append(no.lineno)
    return achadas


def linhas_das_atribuicoes(fonte: str, classe: str, metodo: str) -> dict[str, list[int]] | None:
    """Cada atribuição simples do método escrita por inteiro ("alvo = valor") e as linhas; None se o método não existe."""
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


# ------------------------------------------------------------------------------------------------------ janela principal
def conferir_a_janela(fonte: str, classe: str = "MainWindow") -> list[str]:
    """O que a janela principal perdeu da ligação (lista vazia se está tudo)."""
    problemas = []
    if not importa(fonte, "passo_a_passo_ui", "ControladorPassoAPasso"):
        problemas.append("a janela não importa ControladorPassoAPasso de .passo_a_passo_ui")
    chamadas = linhas_das_chamadas(fonte, classe, "__init__")
    atribuicoes = linhas_das_atribuicoes(fonte, classe, "__init__")
    if chamadas is None or atribuicoes is None:
        return problemas + [f"{classe}.__init__ não existe"]
    criacao = atribuicoes.get("self.passo = ControladorPassoAPasso(self)")
    ligacao = chamadas.get("self.passo.ligar(self.command_table, self.bridge)")
    corpo = chamadas.get("self._build_body()")  # é ele que cria self.command_table
    ponte = atribuicoes.get("self.bridge = EngineBridge()")
    if not criacao:
        problemas.append("o __init__ não cria self.passo = ControladorPassoAPasso(self)")
    if not ligacao:
        problemas.append("o __init__ não chama self.passo.ligar(self.command_table, self.bridge)")
    if not corpo:
        problemas.append("o __init__ não chama self._build_body() (que cria self.command_table)")
    if not ponte:
        problemas.append("o __init__ não cria self.bridge = EngineBridge()")
    if criacao and ligacao and not criacao[0] < ligacao[0]:
        problemas.append("self.passo é criado DEPOIS de ser ligado: o `ligar` encontraria o atributo faltando")
    if corpo and ligacao and not corpo[0] < ligacao[0]:
        problemas.append("o `ligar` vem ANTES de _build_body(): self.command_table ainda não existe")
    if ponte and ligacao and not ponte[0] < ligacao[0]:
        problemas.append("o `ligar` vem ANTES de self.bridge ser criado")
    return problemas


# ------------------------------------------------------------------------------------------------------ editor de comandos
EMITE = "self.passo_a_passo_requested.emit("
ENTRADA = "menu.addAction('⏭ Executar passo a passo"


def _ids_emitidos(emissoes: list[str]) -> str | None:
    """`ids` em `self.passo_a_passo_requested.emit(set(ids))`. None se a emissão tem outro formato (um `set()` vazio, por exemplo)."""
    achados = set()
    for texto in emissoes:
        argumento = texto[len(EMITE):-1]
        if argumento.startswith("set(") and argumento.endswith(")") and argumento[4:-1].isidentifier():
            achados.add(argumento[4:-1])
    return achados.pop() if len(achados) == 1 else None


def _variavel_da_entrada(fonte: str, classe: str, metodo: str) -> str | None:
    """O nome da variável que guarda a entrada do passo a passo no menu (`passo_a = menu.addAction('⏭ Executar passo a passo...')`)."""
    corpo = _metodo(fonte, classe, metodo)
    for no in ast.walk(corpo) if corpo is not None else []:
        if (isinstance(no, ast.Assign) and len(no.targets) == 1 and isinstance(no.targets[0], ast.Name)
                and ast.unparse(no.value).startswith(ENTRADA)):
            return no.targets[0].id
    return None


def conferir_o_editor(fonte: str, classe: str = "CommandTableWidget") -> list[str]:
    problemas = []
    dono = _classe(fonte, classe)
    if dono is None:
        return [f"{classe} não existe"]
    sinais = [ast.unparse(no.value) for no in dono.body
              if isinstance(no, ast.Assign) and len(no.targets) == 1 and ast.unparse(no.targets[0]) == "passo_a_passo_requested"]
    if sinais != ["Signal(object)"]:
        problemas.append(f"{classe} não declara `passo_a_passo_requested = Signal(object)` (achei {sinais})")
    for metodo in ("_context_menu", "_show_more_actions"):
        chamadas = linhas_das_chamadas(fonte, classe, metodo)
        if chamadas is None:
            problemas.append(f"{metodo}: não existe")
            continue
        emissoes = [c for c in chamadas if c.startswith(EMITE)]
        if not emissoes:
            problemas.append(f"{metodo}: não emite passo_a_passo_requested")
        if not any(c.startswith(ENTRADA) for c in chamadas):
            problemas.append(f"{metodo}: não tem a entrada de menu '⏭ Executar passo a passo...'")
        ids = _ids_emitidos(emissoes)
        if emissoes and ids is None:
            problemas.append(f"{metodo}: o passo a passo não emite os ids escolhidos (`set(<ids>)`): começaria sempre pelo primeiro comando")
        elif ids is not None and metodo == "_context_menu":
            entrada = _variavel_da_entrada(fonte, classe, metodo)
            if f"{entrada}.setEnabled(bool({ids}))" not in chamadas:
                problemas.append(f"{metodo}: a entrada não fica desabilitada sem linha escolhida (`{entrada}.setEnabled(bool({ids}))`)")
        elif ids is not None and f"self.test_requested.emit(set({ids}))" not in chamadas:
            problemas.append(f"{metodo}: o passo a passo não usa os mesmos ids do 'Testar selecionados' (`self.test_requested.emit(set({ids}))`)")
    return problemas


# ------------------------------------------------------------------------------------------------------ motor
def conferir_o_motor(fonte: str, classe: str = "ExecutionEngine") -> list[str]:
    problemas = []
    iniciais = linhas_das_atribuicoes(fonte, classe, "__init__")
    if iniciais is None or "self.passo_a_passo = None" not in iniciais:
        problemas.append("o motor não começa com `self.passo_a_passo = None` (sem gancho nada pode mudar)")
    corpo = _metodo(fonte, classe, "_play_timeline")
    if corpo is None:
        return problemas + ["_play_timeline não existe"]
    pergunta = [no for no in ast.walk(corpo)
                if isinstance(no, ast.If) and ast.unparse(no.test) == "self._pede_passo(event) and self._parar_para_o_passo()"]
    if len(pergunta) != 1:
        problemas.append("_play_timeline não pergunta ao gancho (`if self._pede_passo(event) and self._parar_para_o_passo():`)")
    else:
        passos = {ast.unparse(no) for no in pergunta[0].body}
        if "self._pause_event.wait()" not in passos:
            problemas.append("a parada do passo não espera o `_pause_event` (o motor não ficaria parado)")
        if "engine_start = self._clock.monotonic() - target_elapsed" not in passos:
            problemas.append("depois da parada o evento não é feito na hora (o intervalo planejado voltaria a ser cumprido)")
        # a pergunta e o laço de espera do evento (`while True:`) são vizinhos no corpo do `for`: a pergunta vem primeiro
        vizinhos = next((no.body for no in ast.walk(corpo) if pergunta[0] in getattr(no, "body", [])), [])
        esperas = [i for i, no in enumerate(vizinhos)
                   if isinstance(no, ast.While) and isinstance(no.test, ast.Constant) and no.test.value is True]
        if not esperas:
            problemas.append("não achei o laço de espera `while True:` ao lado da pergunta (o código mudou? ajustar esta conferência)")
        elif not vizinhos.index(pergunta[0]) < esperas[0]:
            problemas.append("a pergunta ao gancho vem DEPOIS do laço de espera do evento: o intervalo já teria sido cumprido")
    parar = linhas_das_chamadas(fonte, classe, "_parar_para_o_passo")
    if parar is None:
        problemas.append("_parar_para_o_passo não existe")
    else:
        apagar = parar.get("self._pause_event.clear()")
        pausar = parar.get("self.state.transition_to(State.PAUSED)")
        if not apagar or not pausar:
            problemas.append("_parar_para_o_passo não apaga o sinal e muda o estado para PAUSED")
        elif not apagar[0] < pausar[0]:
            problemas.append("_parar_para_o_passo muda o estado ANTES de apagar o sinal: um 'continuar' que chegue no meio se perde")
        if "self._pause_event.set()" not in parar:
            problemas.append("_parar_para_o_passo não solta o sinal quando a transição é recusada (a thread travaria)")
    return problemas


# ------------------------------------------------------------------------------------------------------ janelinha
CHAMADAS_QUE_ROUBAM_O_FOCO = ("activateWindow", "setFocus", "grabKeyboard", "grabMouse")


def conferir_a_janelinha(fonte: str, classe: str = "PainelPassoAPasso") -> list[str]:
    problemas = []
    chamadas = linhas_das_chamadas(fonte, classe, "__init__")
    corpo = _metodo(fonte, classe, "__init__")
    if chamadas is None or corpo is None:
        return [f"{classe}.__init__ não existe"]
    if "super().__init__(None, Qt.Tool | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus)" not in chamadas:
        problemas.append("a janelinha não é criada como Tool, sempre por cima e SEM aceitar o foco")
    if "self.setAttribute(Qt.WA_ShowWithoutActivating, True)" not in chamadas:
        problemas.append("a janelinha não usa WA_ShowWithoutActivating (abrir tomaria o foco do programa de destino)")
    sem_foco = False
    for no in ast.walk(corpo):
        if isinstance(no, ast.For) and any(ast.unparse(c) == "botao.setFocusPolicy(Qt.NoFocus)" for c in ast.walk(no) if isinstance(c, ast.Call)):
            sem_foco = all(f"self.{nome}" in ast.unparse(no.iter) for nome in ("botao_proximo", "botao_continuar", "botao_parar"))
    if not sem_foco:
        problemas.append("os três botões não ficam com setFocusPolicy(Qt.NoFocus)")
    fechar = linhas_das_chamadas(fonte, classe, "closeEvent")
    if fechar is None or "self._ao_parar()" not in fechar:
        problemas.append("fechar a janelinha pelo X não para a execução (ficaria parada sem ninguém para liberá-la)")
    # os botões: cada um liga o clique ao que a janela principal pediu para ele
    pares = None
    for no in ast.walk(corpo):
        if isinstance(no, ast.For) and isinstance(no.iter, ast.Tuple):
            pares = [(ast.unparse(p.elts[0]), ast.unparse(p.elts[1])) for p in no.iter.elts if isinstance(p, ast.Tuple) and len(p.elts) == 2]
    if pares != [("self.botao_proximo", "ao_proximo"), ("self.botao_continuar", "ao_continuar"), ("self.botao_parar", "ao_parar")]:
        problemas.append(f"os botões não estão ligados cada um ao seu pedido (proximo, continuar, parar); achei {pares}")
    if not any(c.startswith("botao.clicked.connect(") for c in chamadas):
        problemas.append("os botões não ligam o clique ao que fazer (`botao.clicked.connect(...)`)")
    # os nomes de objeto: é por eles que a frente visual estiliza a janelinha
    constantes = {no.targets[0].id: no.value.value for no in ast.parse(fonte).body
                  if isinstance(no, ast.Assign) and len(no.targets) == 1 and isinstance(no.targets[0], ast.Name) and isinstance(no.value, ast.Constant)}
    if constantes.get("NOME_DA_JANELINHA") != classe:
        problemas.append(f"NOME_DA_JANELINHA não é '{classe}' (achei {constantes.get('NOME_DA_JANELINHA')!r})")
    if constantes.get("NOME_DO_ROTULO") != "PassoRotulo":
        problemas.append(f"NOME_DO_ROTULO não é 'PassoRotulo' (achei {constantes.get('NOME_DO_ROTULO')!r})")
    if "self.setObjectName(NOME_DA_JANELINHA)" not in chamadas:
        problemas.append("a janelinha não recebe o nome de objeto (`self.setObjectName(NOME_DA_JANELINHA)`)")
    if "self.rotulo.setObjectName(NOME_DO_ROTULO)" not in chamadas:
        problemas.append("o rótulo não recebe o nome de objeto (`self.rotulo.setObjectName(NOME_DO_ROTULO)`)")
    # aparecer e ir para o canto de baixo à direita da área útil (sem a barra de tarefas)
    mostrar = linhas_das_chamadas(fonte, classe, "mostrar_passo") or {}
    if "self.rotulo.setText(texto)" not in mostrar:
        problemas.append("a janelinha não mostra o texto do passo (`self.rotulo.setText(texto)`)")
    if "self.botao_proximo.setEnabled(bool(pode_avancar))" not in mostrar:
        problemas.append("a janelinha não libera nem trava o 'Próximo passo' conforme o pedido (`self.botao_proximo.setEnabled(bool(pode_avancar))`)")
    if not (mostrar.get("self.show()") and mostrar.get("self._ir_para_o_canto()") and mostrar["self.show()"][0] < mostrar["self._ir_para_o_canto()"][0]):
        problemas.append("a janelinha não vai para o canto depois de aparecer (`self.show()` e então `self._ir_para_o_canto()`)")
    canto = linhas_das_chamadas(fonte, classe, "_ir_para_o_canto") or {}
    if "tela.availableGeometry()" not in canto:
        problemas.append("o canto não é o da ÁREA ÚTIL da tela (`tela.availableGeometry()`): a janelinha cobriria a barra de tarefas")
    if "self.frameGeometry()" not in canto:
        problemas.append("o canto não conta a moldura da janela (`self.frameGeometry()`): a barra de título ficaria fora da tela")
    if "self.move(*posicao_no_canto(area.right(), area.bottom(), moldura.width(), moldura.height()))" not in canto:
        problemas.append("a janelinha não é movida para o canto de baixo à direita (`self.move(*posicao_no_canto(...))`)")
    chamados = {no.func.attr for no in ast.walk(ast.parse(fonte)) if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)}
    roubam = sorted(chamados & set(CHAMADAS_QUE_ROUBAM_O_FOCO))
    if roubam:
        problemas.append(f"o módulo chama {', '.join(roubam)}: isso tira o foco do programa de destino")
    return problemas


# ------------------------------------------------------------------------------------------------------ controles
PONTE = "self.bridge = EngineBridge()"
CORPO = "self._build_body()"
CRIA = "self.passo = ControladorPassoAPasso(self)"
LIGA = "self.passo.ligar(self.command_table, self.bridge)"
IMPORTA = "from .passo_a_passo_ui import ControladorPassoAPasso\n"


def _janela(*linhas: str, importa: str = IMPORTA) -> str:
    """Uma janela sintética: o import e um __init__ com as linhas dadas, na ordem dada."""
    return importa + "class J:\n    def __init__(self):\n" + "".join(f"        {linha}\n" for linha in linhas)


_JANELA_SINTETICA = _janela(PONTE, CORPO, CRIA, LIGA)

_EDITOR_SINTETICO = (
    "class T:\n"
    "    passo_a_passo_requested = Signal(object)\n"
    "    def _context_menu(self, pos):\n"
    "        passo_a = menu.addAction('⏭ Executar passo a passo a partir daqui')\n"
    "        passo_a.setEnabled(bool(context_ids))\n"
    "        passo_a.triggered.connect(lambda: self.passo_a_passo_requested.emit(set(context_ids)))\n"
    "    def _show_more_actions(self):\n"
    "        test_a = menu.addAction('Testar selecionados')\n"
    "        test_a.triggered.connect(lambda: self.test_requested.emit(set(ids)))\n"
    "        passo_a = menu.addAction('⏭ Executar passo a passo')\n"
    "        passo_a.triggered.connect(lambda: self.passo_a_passo_requested.emit(set(ids)))\n"
)

_MOTOR_SINTETICO = (
    "class ExecutionEngine:\n"
    "    def __init__(self):\n"
    "        self.passo_a_passo = None\n"
    "    def _play_timeline(self, timeline):\n"
    "        for event in timeline:\n"
    "            target_elapsed = event.time / speed\n"
    "            if self._pede_passo(event) and self._parar_para_o_passo():\n"
    "                self._pause_event.wait()\n"
    "                engine_start = self._clock.monotonic() - target_elapsed\n"
    "            while True:\n"
    "                pass\n"
    "    def _parar_para_o_passo(self):\n"
    "        self._pause_event.clear()\n"
    "        try:\n"
    "            self.state.transition_to(State.PAUSED)\n"
    "        except core.InvalidStateTransition:\n"
    "            self._pause_event.set()\n"
    "            return False\n"
    "        return True\n"
)

_JANELINHA_SINTETICA = (
    "NOME_DA_JANELINHA = 'PainelPassoAPasso'\n"
    "NOME_DO_ROTULO = 'PassoRotulo'\n"
    "class PainelPassoAPasso:\n"
    "    def __init__(self, ao_proximo, ao_continuar, ao_parar):\n"
    "        super().__init__(None, Qt.Tool | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus)\n"
    "        self.setObjectName(NOME_DA_JANELINHA)\n"
    "        self.setAttribute(Qt.WA_ShowWithoutActivating, True)\n"
    "        self._ao_parar = ao_parar\n"
    "        self.rotulo.setObjectName(NOME_DO_ROTULO)\n"
    "        for botao, acao in ((self.botao_proximo, ao_proximo), (self.botao_continuar, ao_continuar), (self.botao_parar, ao_parar)):\n"
    "            botao.setFocusPolicy(Qt.NoFocus)\n"
    "            botao.clicked.connect(lambda _marcado=False, fazer=acao: fazer())\n"
    "    def mostrar_passo(self, texto, pode_avancar):\n"
    "        self.rotulo.setText(texto)\n"
    "        self.botao_proximo.setEnabled(bool(pode_avancar))\n"
    "        if not self.isVisible():\n"
    "            self.show()\n"
    "            self._ir_para_o_canto()\n"
    "    def closeEvent(self, evento):\n"
    "        self._ao_parar()\n"
    "    def _ir_para_o_canto(self):\n"
    "        tela = QGuiApplication.primaryScreen()\n"
    "        area = tela.availableGeometry()\n"
    "        moldura = self.frameGeometry()\n"
    "        self.move(*posicao_no_canto(area.right(), area.bottom(), moldura.width(), moldura.height()))\n"
)


def test_controle_positivo_o_trecho_certo_nao_acusa_nada():
    assert conferir_a_janela(_JANELA_SINTETICA, "J") == []
    assert conferir_o_editor(_EDITOR_SINTETICO, "T") == []
    assert conferir_o_motor(_MOTOR_SINTETICO) == []
    assert conferir_a_janelinha(_JANELINHA_SINTETICA) == []


def _sem(fonte: str, trecho: str, por: str = "") -> str:
    assert trecho in fonte, f"o controle está desatualizado: {trecho!r} não aparece no trecho sintético"
    return fonte.replace(trecho, por, 1)


def test_controle_negativo_a_janela_acusa_cada_falta():
    casos = [
        (_janela(PONTE, CORPO, LIGA), "não cria self.passo"),
        (_janela(PONTE, CORPO, CRIA), "não chama self.passo.ligar"),
        (_janela(PONTE, CORPO, CRIA, "self.passo.ligar(self.bridge, self.command_table)"), "não chama self.passo.ligar"),
        (_janela(PONTE, CRIA, LIGA), "não chama self._build_body()"),
        (_janela(CORPO, CRIA, LIGA), "não cria self.bridge"),
        (_janela(PONTE, CORPO, CRIA, LIGA, importa=""), "não importa ControladorPassoAPasso"),
        (_janela(PONTE, CORPO, "self.passo = Outra(self)", LIGA), "não cria self.passo"),
    ]
    for fonte, trecho in casos:
        problemas = conferir_a_janela(fonte, "J")
        assert any(trecho in p for p in problemas), (trecho, problemas)


def test_controle_negativo_a_janela_acusa_a_ordem_errada():
    casos = [
        (_janela(PONTE, CORPO, LIGA, CRIA), "DEPOIS de ser ligado"),
        (_janela(PONTE, CRIA, LIGA, CORPO), "ANTES de _build_body()"),
        (_janela(CORPO, CRIA, LIGA, PONTE), "ANTES de self.bridge"),
    ]
    for fonte, trecho in casos:
        problemas = conferir_a_janela(fonte, "J")
        assert any(trecho in p for p in problemas), (trecho, problemas)
    # a mesma janela na ordem certa não acusa nada (o controle positivo do outro lado da balança)
    assert conferir_a_janela(_janela(PONTE, CORPO, CRIA, LIGA), "J") == []
    assert conferir_a_janela(_janela(CORPO, PONTE, CRIA, LIGA), "J") == []


def test_controle_negativo_o_editor_acusa_cada_falta():
    sem_sinal = _sem(_EDITOR_SINTETICO, "    passo_a_passo_requested = Signal(object)\n")
    assert any("não declara" in p for p in conferir_o_editor(sem_sinal, "T"))
    sinal_errado = _sem(_EDITOR_SINTETICO, "Signal(object)", "Signal()")
    assert any("não declara" in p for p in conferir_o_editor(sinal_errado, "T"))
    sem_emissao_no_botao_direito = _EDITOR_SINTETICO.replace("self.passo_a_passo_requested.emit(set(context_ids))", "None", 1)
    assert any(p.startswith("_context_menu: não emite") for p in conferir_o_editor(sem_emissao_no_botao_direito, "T"))
    sem_emissao_no_mais = _EDITOR_SINTETICO.replace("self.passo_a_passo_requested.emit(set(ids))", "None", 1)
    assert any(p.startswith("_show_more_actions: não emite") for p in conferir_o_editor(sem_emissao_no_mais, "T"))
    sem_entrada = _EDITOR_SINTETICO.replace("passo_a = menu.addAction('⏭ Executar passo a passo a partir daqui')", "passo_a = None", 1)
    assert any(p.startswith("_context_menu: não tem a entrada") for p in conferir_o_editor(sem_entrada, "T"))
    sem_metodo = _sem(_EDITOR_SINTETICO, "_show_more_actions", "_outro")
    assert any(p == "_show_more_actions: não existe" for p in conferir_o_editor(sem_metodo, "T"))


def test_controle_negativo_o_editor_acusa_os_ids_e_a_habilitacao():
    # sem linha escolhida a entrada do botão direito tem de ficar desabilitada
    sem_habilitacao = _sem(_EDITOR_SINTETICO, "        passo_a.setEnabled(bool(context_ids))\n")
    assert any("não fica desabilitada" in p for p in conferir_o_editor(sem_habilitacao, "T"))
    habilitacao_de_outro = _sem(_EDITOR_SINTETICO, "passo_a.setEnabled(bool(context_ids))", "passo_a.setEnabled(bool(outros))")
    assert any("não fica desabilitada" in p for p in conferir_o_editor(habilitacao_de_outro, "T"))
    # o pedido tem de levar os ids escolhidos
    vazio_no_botao_direito = _sem(_EDITOR_SINTETICO, "emit(set(context_ids))", "emit(set())")
    assert any(p.startswith("_context_menu: o passo a passo não emite os ids") for p in conferir_o_editor(vazio_no_botao_direito, "T"))
    vazio_no_mais = _sem(_EDITOR_SINTETICO, "passo_a_passo_requested.emit(set(ids))", "passo_a_passo_requested.emit(set())")
    assert any(p.startswith("_show_more_actions: o passo a passo não emite os ids") for p in conferir_o_editor(vazio_no_mais, "T"))
    # no "Mais...", os mesmos ids do "Testar selecionados" (a mesma seleção)
    outros_ids = _sem(_EDITOR_SINTETICO, "passo_a_passo_requested.emit(set(ids))", "passo_a_passo_requested.emit(set(todos))")
    assert any("mesmos ids do 'Testar selecionados'" in p for p in conferir_o_editor(outros_ids, "T"))


def test_controle_negativo_o_motor_acusa_cada_falta():
    sem_inicial = _sem(_MOTOR_SINTETICO, "        self.passo_a_passo = None\n", "        pass\n")
    assert any("não começa com" in p for p in conferir_o_motor(sem_inicial))
    sem_pergunta = _sem(_MOTOR_SINTETICO, "self._pede_passo(event) and self._parar_para_o_passo()", "False")
    assert any("não pergunta ao gancho" in p for p in conferir_o_motor(sem_pergunta))
    sem_espera = _sem(_MOTOR_SINTETICO, "                self._pause_event.wait()\n", "                pass\n")
    assert any("não espera o `_pause_event`" in p for p in conferir_o_motor(sem_espera))
    sem_na_hora = _sem(_MOTOR_SINTETICO, "                engine_start = self._clock.monotonic() - target_elapsed\n", "                pass\n")
    assert any("não é feito na hora" in p for p in conferir_o_motor(sem_na_hora))
    depois_do_laco = _MOTOR_SINTETICO.replace(
        "            if self._pede_passo(event) and self._parar_para_o_passo():\n"
        "                self._pause_event.wait()\n"
        "                engine_start = self._clock.monotonic() - target_elapsed\n"
        "            while True:\n"
        "                pass\n",
        "            while True:\n"
        "                pass\n"
        "            if self._pede_passo(event) and self._parar_para_o_passo():\n"
        "                self._pause_event.wait()\n"
        "                engine_start = self._clock.monotonic() - target_elapsed\n")
    assert any("DEPOIS do laço de espera" in p for p in conferir_o_motor(depois_do_laco))
    estado_antes = _MOTOR_SINTETICO.replace(
        "        self._pause_event.clear()\n        try:\n            self.state.transition_to(State.PAUSED)\n",
        "        try:\n            self.state.transition_to(State.PAUSED)\n            self._pause_event.clear()\n")
    assert any("ANTES de apagar o sinal" in p for p in conferir_o_motor(estado_antes))
    sem_soltar = _sem(_MOTOR_SINTETICO, "            self._pause_event.set()\n", "            pass\n")
    assert any("não solta o sinal" in p for p in conferir_o_motor(sem_soltar))
    sem_metodo = _sem(_MOTOR_SINTETICO, "_parar_para_o_passo(self):", "_outro(self):")
    assert any("_parar_para_o_passo não existe" in p for p in conferir_o_motor(sem_metodo))


def test_controle_negativo_a_janelinha_acusa_cada_falta():
    comum = "Qt.Tool | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus"
    casos = [
        (_sem(_JANELINHA_SINTETICA, comum, "Qt.Tool | Qt.WindowStaysOnTopHint"), "SEM aceitar o foco"),
        (_sem(_JANELINHA_SINTETICA, "Qt.Tool | ", ""), "SEM aceitar o foco"),
        (_sem(_JANELINHA_SINTETICA, "Qt.WindowStaysOnTopHint | ", ""), "SEM aceitar o foco"),
        (_sem(_JANELINHA_SINTETICA, "        self.setAttribute(Qt.WA_ShowWithoutActivating, True)\n"), "WA_ShowWithoutActivating"),
        (_sem(_JANELINHA_SINTETICA, "botao.setFocusPolicy(Qt.NoFocus)", "pass"), "setFocusPolicy(Qt.NoFocus)"),
        (_sem(_JANELINHA_SINTETICA, "(self.botao_parar, ao_parar)", ""), "setFocusPolicy(Qt.NoFocus)"),
        (_sem(_JANELINHA_SINTETICA, "        self._ao_parar()\n", "        pass\n"), "pelo X"),
        (_sem(_JANELINHA_SINTETICA, "    def closeEvent(self, evento):\n        self._ao_parar()\n"), "pelo X"),
    ]
    for fonte, trecho in casos:
        assert any(trecho in p for p in conferir_a_janelinha(fonte)), (trecho, conferir_a_janelinha(fonte))


def test_controle_negativo_a_janelinha_acusa_os_nomes_os_botoes_e_o_canto():
    casos = [
        (_sem(_JANELINHA_SINTETICA, "        self.setObjectName(NOME_DA_JANELINHA)\n"), "setObjectName(NOME_DA_JANELINHA)"),
        (_sem(_JANELINHA_SINTETICA, "        self.rotulo.setObjectName(NOME_DO_ROTULO)\n"), "setObjectName(NOME_DO_ROTULO)"),
        (_sem(_JANELINHA_SINTETICA, "NOME_DA_JANELINHA = 'PainelPassoAPasso'", "NOME_DA_JANELINHA = 'Outro'"), "NOME_DA_JANELINHA não é"),
        (_sem(_JANELINHA_SINTETICA, "NOME_DO_ROTULO = 'PassoRotulo'", "NOME_DO_ROTULO = 'Rotulo'"), "NOME_DO_ROTULO não é"),
        (_sem(_JANELINHA_SINTETICA, "(self.botao_proximo, ao_proximo), (self.botao_continuar, ao_continuar)",
              "(self.botao_proximo, ao_continuar), (self.botao_continuar, ao_proximo)"), "cada um ao seu pedido"),
        (_sem(_JANELINHA_SINTETICA, "            botao.clicked.connect(lambda _marcado=False, fazer=acao: fazer())\n"), "ligam o clique"),
        (_sem(_JANELINHA_SINTETICA, "        self.rotulo.setText(texto)\n"), "não mostra o texto do passo"),
        (_sem(_JANELINHA_SINTETICA, "self.botao_proximo.setEnabled(bool(pode_avancar))", "self.botao_proximo.setEnabled(True)"), "libera nem trava"),
        (_sem(_JANELINHA_SINTETICA, "            self._ir_para_o_canto()\n"), "vai para o canto depois de aparecer"),
        (_sem(_JANELINHA_SINTETICA, "            self.show()\n            self._ir_para_o_canto()\n",
              "            self._ir_para_o_canto()\n            self.show()\n"), "vai para o canto depois de aparecer"),
        (_sem(_JANELINHA_SINTETICA, "tela.availableGeometry()", "tela.geometry()"), "ÁREA ÚTIL"),
        (_sem(_JANELINHA_SINTETICA, "self.frameGeometry()", "self.geometry()"), "moldura"),
        (_sem(_JANELINHA_SINTETICA, "self.move(*posicao_no_canto(area.right(), area.bottom(), moldura.width(), moldura.height()))",
              "self.move(area.left(), area.top())"), "canto de baixo à direita"),
    ]
    for fonte, trecho in casos:
        assert any(trecho in p for p in conferir_a_janelinha(fonte)), (trecho, conferir_a_janelinha(fonte))


def test_controle_negativo_a_janelinha_acusa_quem_puxa_o_foco():
    for chamada in CHAMADAS_QUE_ROUBAM_O_FOCO:
        fonte = _JANELINHA_SINTETICA + f"    def mostrar(self):\n        self.{chamada}()\n"
        assert any(chamada in p and "tira o foco" in p for p in conferir_a_janelinha(fonte)), chamada


def test_controle_a_janela_sem_a_classe_ou_sem_init_acusa():
    assert conferir_a_janela("x = 1\n", "J") != []
    assert conferir_o_editor("x = 1\n", "T") != []
    assert conferir_o_motor("x = 1\n") != []
    assert conferir_a_janelinha("x = 1\n") != []


# ------------------------------------------------------------------------------------------------------ o código real
def _ler(caminho: pathlib.Path) -> str:
    return caminho.read_text(encoding="utf-8")


def test_a_janela_principal_liga_o_passo_a_passo():
    assert conferir_a_janela(_ler(JANELA)) == []


def test_o_editor_tem_o_sinal_e_as_duas_entradas_de_menu():
    assert conferir_o_editor(_ler(EDITOR)) == []


def test_o_motor_consulta_o_gancho_antes_de_esperar_o_momento_do_comando():
    assert conferir_o_motor(_ler(MOTOR)) == []


def test_a_janelinha_nao_aceita_o_foco_e_nada_nela_puxa_o_foco():
    assert conferir_a_janelinha(_ler(JANELINHA)) == []
