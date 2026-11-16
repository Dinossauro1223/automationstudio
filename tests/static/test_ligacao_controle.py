"""A ligação das teclas de controle com a janela principal, conferida no código-fonte de main_window.py (achado 2.11).

O defeito: até a 25.8 as teclas "Pausar automação" (F9) e "Continuar automação" (F10) eram registradas e apareciam em
Configurações, mas `_on_hotkey_triggered` só atendia `map:`, `control:emergency`, `record:toggle` e `record:cancel`. O disparo de
`control:pause` e `control:resume` chegava, não casava com ramo nenhum e sumia, e nada na janela chamava `engine.pause()` nem
`resume()`. Este arquivo era o teste `xfail` do defeito (static/test_lacunas_de_ligacao.py); com a correção (md/ESPEC_PAUSA_TECLAS.md)
o marcador saiu e ele virou o guarda permanente, como se pede ("reproduzir, falhar, corrigir, passar, regressão permanente").

Os testes de janela (tests/gui/test_controle_janela.py) provam o comportamento, mas só rodam com o PySide6 de verdade. Este roda
em qualquer lugar e protege a ligação em si: se numa fusão de ramos ou numa refatoração um ramo sumir, ou uma ação de controle
nova for registrada sem ramo, o teste diz qual.

O verificador (`chamadas_do_ramo`, `ramo_chama`) é testado à parte com trechos sintéticos (controles negativo e positivo): sem
eles um teste "falharia" por qualquer motivo, inclusive por o verificador não achar o método.
"""
import ast
import os
import pathlib

from automationstudio.ativacao import ACAO_DO_CONTROLE

ROOT = pathlib.Path(os.environ.get("AS_ROOT") or pathlib.Path(__file__).resolve().parents[2])
JANELA = ROOT / "automationstudio" / "main_window.py"


# ------------------------------------------------------------------------------------------------ o verificador
def _metodo(fonte: str, classe: str, nome: str):
    for no in ast.walk(ast.parse(fonte)):
        if isinstance(no, ast.ClassDef) and no.name == classe:
            for item in no.body:
                if isinstance(item, ast.FunctionDef) and item.name == nome:
                    return item
    return None


def _compara_com(teste, texto: str) -> bool:
    return any(isinstance(c, ast.Constant) and c.value == texto for c in ast.walk(teste))


def _nome_da_chamada(no) -> str | None:
    """"self.controle.pausar" para a chamada `self.controle.pausar(...)`; None se `no` não é uma chamada de atributos
    encadeados a partir de um nome."""
    if not isinstance(no, ast.Call):
        return None
    partes, atual = [], no.func
    while isinstance(atual, ast.Attribute):
        partes.append(atual.attr)
        atual = atual.value
    if not isinstance(atual, ast.Name) or not partes:
        return None
    return ".".join([atual.id, *reversed(partes)])


def _ramo(fonte: str, acao: str):
    """O `if`/`elif` de `MainWindow._on_hotkey_triggered` cujo teste compara com `acao`; None se não há (ou se não há método)."""
    metodo = _metodo(fonte, "MainWindow", "_on_hotkey_triggered")
    for no in ast.walk(metodo) if metodo is not None else ():
        if isinstance(no, ast.If) and _compara_com(no.test, acao):
            return no
    return None


def chamadas_do_ramo(fonte: str, acao: str) -> set[str] | None:
    """As chamadas (como "self.controle.pausar") que o ramo de `acao` faz; None se a janela não tem ramo para `acao`."""
    ramo = _ramo(fonte, acao)
    if ramo is None:
        return None
    corpo = ast.Module(body=ramo.body, type_ignores=[])
    return {nome for sub in ast.walk(corpo) if (nome := _nome_da_chamada(sub)) is not None}


def ramo_chama(fonte: str, acao: str, chamada: str) -> bool:
    """True se o ramo de `acao` chega a chamar `.chamada()`, direto ou por um método da própria janela (`self.metodo()`, um
    nível). Serve para a emergência (`self._on_emergency()` → `engine.emergency_stop()`)."""
    ramo = _ramo(fonte, acao)
    if ramo is None:
        return False
    janela = next(n for n in ast.walk(ast.parse(fonte)) if isinstance(n, ast.ClassDef) and n.name == "MainWindow")
    metodos = {n.name: n for n in janela.body if isinstance(n, ast.FunctionDef)}
    corpo = ast.Module(body=ramo.body, type_ignores=[])

    def chama(no) -> bool:
        return any((nome := _nome_da_chamada(c)) is not None and nome.rsplit(".", 1)[-1] == chamada for c in ast.walk(no))

    if chama(corpo):
        return True
    return any(nome is not None and nome.startswith("self.") and nome.count(".") == 1 and nome[5:] in metodos
               and chama(metodos[nome[5:]]) for nome in (_nome_da_chamada(c) for c in ast.walk(corpo)))


def _linha_da_criacao(fonte: str, atributo: str, classe: str) -> int | None:
    """A linha de `self.<atributo> = <classe>(self)` em `MainWindow.__init__`, ou None."""
    metodo = _metodo(fonte, "MainWindow", "__init__")
    for no in ast.walk(metodo) if metodo is not None else ():
        if (isinstance(no, ast.Assign) and isinstance(no.value, ast.Call) and isinstance(no.value.func, ast.Name)
                and no.value.func.id == classe and len(no.targets) == 1 and isinstance(no.targets[0], ast.Attribute)
                and isinstance(no.targets[0].value, ast.Name) and no.targets[0].value.id == "self"
                and no.targets[0].attr == atributo):
            return no.lineno
    return None


def _linha_da_chamada(fonte: str, nome: str) -> int | None:
    """A primeira linha, em `MainWindow.__init__`, que chama `nome` (como "self._register_all_hotkeys"), ou None."""
    metodo = _metodo(fonte, "MainWindow", "__init__")
    linhas = [no.lineno for no in ast.walk(metodo) if _nome_da_chamada(no) == nome] if metodo is not None else []
    return min(linhas) if linhas else None


# ------------------------------------------------------------------------------------------------ controles do verificador
_MOLDE = '''
class MainWindow:
    def __init__(self):
        self.controle = ControladorDeExecucao(self)
        self._register_all_hotkeys()
    def _on_hotkey_triggered(self, action_id):
        if action_id.startswith("map:"):
            self.rodar()
        elif action_id == "control:emergency":
            self._on_emergency()
{extra}
    def _on_emergency(self):
        self.engine.emergency_stop()
    def _pausar(self):
        self.engine.pause()
'''
_COM_O_CONTROLADOR = ('        elif action_id == "control:pause":\n            self.controle.pausar()\n'
                      '        elif action_id == "control:resume":\n            self.controle.retomar()\n')


def test_o_verificador_acha_as_chamadas_de_cada_ramo_e_so_as_dele():
    fonte = _MOLDE.format(extra=_COM_O_CONTROLADOR)
    assert chamadas_do_ramo(fonte, "control:pause") == {"self.controle.pausar"}
    assert chamadas_do_ramo(fonte, "control:resume") == {"self.controle.retomar"}
    assert chamadas_do_ramo(fonte, "control:emergency") == {"self._on_emergency"}


def test_o_verificador_diz_que_nao_ha_ramo_quando_nao_ha():
    sem_ramo = _MOLDE.format(extra="")
    assert chamadas_do_ramo(sem_ramo, "control:pause") is None, "um método que chama pause() mas sem ramo para a tecla não conta"
    assert chamadas_do_ramo("class Outra:\n    pass\n", "control:pause") is None
    assert chamadas_do_ramo(_MOLDE.replace("_on_hotkey_triggered", "outro_nome").format(extra=_COM_O_CONTROLADOR), "control:pause") is None


def test_o_verificador_enxerga_um_ramo_vazio_ou_que_chama_outra_coisa():
    vazio = _MOLDE.format(extra='        elif action_id == "control:pause":\n            self.status("pausou")\n')
    assert chamadas_do_ramo(vazio, "control:pause") == {"self.status"}
    assert "self.controle.pausar" not in chamadas_do_ramo(vazio, "control:pause")
    so_pass = _MOLDE.format(extra='        elif action_id == "control:pause":\n            pass\n')
    assert chamadas_do_ramo(so_pass, "control:pause") == set(), "ramo existe e não chama nada"


def test_o_verificador_ramo_chama_segue_um_nivel_pelos_metodos_da_janela_e_recusa_o_resto():
    direto = _MOLDE.format(extra='        elif action_id == "control:pause":\n            self.engine.pause()\n')
    por_metodo = _MOLDE.format(extra='        elif action_id == "control:pause":\n            self._pausar()\n')
    assert ramo_chama(direto, "control:pause", "pause")
    assert ramo_chama(por_metodo, "control:pause", "pause")
    assert ramo_chama(por_metodo, "control:emergency", "emergency_stop"), "a emergência chama por um método (um nível)"
    assert not ramo_chama(_MOLDE.format(extra=""), "control:pause", "pause"), "sem ramo não conta"
    assert not ramo_chama(por_metodo, "control:emergency", "pause"), "chamar outra coisa no ramo certo não conta"


def test_o_verificador_acha_onde_o_controlador_e_criado_e_quando_o_init_registra_os_atalhos():
    assert _linha_da_criacao(_MOLDE.format(extra=""), "controle", "ControladorDeExecucao") == 4
    assert _linha_da_chamada(_MOLDE.format(extra=""), "self._register_all_hotkeys") == 5
    assert _linha_da_criacao(_MOLDE.format(extra="").replace("ControladorDeExecucao(self)", "Outro(self)"), "controle", "ControladorDeExecucao") is None
    assert _linha_da_criacao(_MOLDE.format(extra="").replace("self.controle =", "self.outro ="), "controle", "ControladorDeExecucao") is None
    assert _linha_da_chamada(_MOLDE.format(extra="").replace("self._register_all_hotkeys()", "pass"), "self._register_all_hotkeys") is None


# ------------------------------------------------------------------------------------------------ o código real
def _fonte() -> str:
    return JANELA.read_text(encoding="utf-8")


def test_no_codigo_real_o_verificador_enxerga_os_ramos_que_ja_existiam():
    """Controle positivo contra o arquivo de verdade: se `_on_hotkey_triggered` mudasse de forma e o verificador deixasse de
    achá-lo, os testes abaixo passariam a falhar (ou, pior, a passar por não achar nada para conferir)."""
    assert ramo_chama(_fonte(), "control:emergency", "emergency_stop")
    assert ramo_chama(_fonte(), "record:toggle", "_toggle_recording")
    assert ramo_chama(_fonte(), "record:cancel", "_cancel_recording")


def test_toda_acao_de_controle_registrada_tem_ramo_em_on_hotkey_triggered():                                             # PAU-05
    """O que teria pego o achado 2.11: uma tecla registrada que ninguém atende. A lista vem de `ativacao.ACAO_DO_CONTROLE`,
    a mesma que registra os atalhos; uma ação nova entra aqui sozinha."""
    sem_ramo = [acao for acao in ACAO_DO_CONTROLE.values() if chamadas_do_ramo(_fonte(), acao) is None]
    assert sem_ramo == [], f"MainWindow._on_hotkey_triggered não tem ramo para: {sem_ramo} (a tecla seria registrada e o disparo sumiria)"


def test_nenhum_ramo_de_acao_de_controle_e_vazio():                                                                       # PAU-05
    vazios = [acao for acao in ACAO_DO_CONTROLE.values() if chamadas_do_ramo(_fonte(), acao) == set()]  # None = sem ramo (outro teste)
    assert vazios == [], f"o ramo de {vazios} existe mas não chama nada"


def test_as_teclas_de_pausar_e_continuar_pausam_e_continuam_pelo_controlador():                                          # PAU-05
    assert "self.controle.pausar" in (chamadas_do_ramo(_fonte(), "control:pause") or set()), "control:pause não chega a self.controle.pausar()"
    assert "self.controle.retomar" in (chamadas_do_ramo(_fonte(), "control:resume") or set()), "control:resume não chega a self.controle.retomar()"


def test_pausar_nao_chama_retomar_nem_o_contrario():                                                                       # PAU-05
    """Os dois ramos trocados (F9 continuando e F10 pausando) passariam no teste acima se cada um chamasse os dois."""
    assert "self.controle.retomar" not in (chamadas_do_ramo(_fonte(), "control:pause") or set())
    assert "self.controle.pausar" not in (chamadas_do_ramo(_fonte(), "control:resume") or set())


def test_o_controlador_de_execucao_e_criado_na_janela_antes_de_registrar_os_atalhos():                                   # PAU-05
    criacao = _linha_da_criacao(_fonte(), "controle", "ControladorDeExecucao")
    registro = _linha_da_chamada(_fonte(), "self._register_all_hotkeys")
    assert criacao is not None, "MainWindow.__init__ não cria `self.controle = ControladorDeExecucao(self)`"
    assert registro is not None, "MainWindow.__init__ não registra os atalhos (self._register_all_hotkeys)"
    assert criacao < registro, "`self.controle` é criado depois de os atalhos serem registrados: um disparo cedo demais não acharia o controlador"
