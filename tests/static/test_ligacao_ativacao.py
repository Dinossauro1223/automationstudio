"""A ligação da ativação por mapa com a janela principal, conferida no código-fonte de main_window.py.

Os testes de janela (tests/gui/test_ativacao_janela.py) provam o comportamento, mas só rodam com o PySide6 de verdade. Este
roda em qualquer lugar e protege a ligação em si: se numa fusão de ramos (ou numa refatoração da janela) uma chamada a
`self.ativacao.*` sumir de onde precisa estar, ou for parar na ordem errada, o teste diz qual.

A checagem é uma função pura (`chamadas_da_ativacao`), com controles negativo e positivo sobre um trecho sintético; só depois
vem a conferência do código real.
"""
import ast
import os
import pathlib

ROOT = pathlib.Path(os.environ.get("AS_ROOT") or pathlib.Path(__file__).resolve().parents[2])
JANELA = ROOT / "automationstudio" / "main_window.py"

# método da janela -> o que o controlador (`self.ativacao`) precisa receber nele
LIGACOES = {
    "__init__": ("montar_painel",),
    "_reload_map_list": ("sincronizar", "decorar_lista"),
    "_register_all_hotkeys": ("registrar",),
    "_on_hotkey_triggered": ("acao_permitida",),
    "_delete_current_map": ("esquecer",),
    "_refresh_map_config_labels": ("atualizar_painel", "rotulo_da_tecla"),
    "_configure_current_map": ("mudar_tecla",),
}


def _metodo(fonte: str, classe: str, nome: str):
    for no in ast.walk(ast.parse(fonte)):
        if isinstance(no, ast.ClassDef) and no.name == classe:
            for item in no.body:
                if isinstance(item, ast.FunctionDef) and item.name == nome:
                    return item
    return None


def _chamada(no) -> tuple[str, int] | None:
    """("self.ativacao.X", linha) se `no` é a chamada `self.ativacao.X(...)`; ("self.Y", linha) se é `self.Y(...)`."""
    if not (isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)):
        return None
    dono = no.func.value
    if isinstance(dono, ast.Attribute) and isinstance(dono.value, ast.Name) and dono.value.id == "self" and dono.attr == "ativacao":
        return f"self.ativacao.{no.func.attr}", no.lineno
    if isinstance(dono, ast.Name) and dono.id == "self":
        return f"self.{no.func.attr}", no.lineno
    return None


def chamadas_da_ativacao(fonte: str, classe: str, nome: str) -> dict[str, int] | None:
    """{chamada: linha da primeira vez} das chamadas `self.ativacao.X(...)` e `self.Y(...)` do método `nome` de `classe`;
    None se o método não existe."""
    metodo = _metodo(fonte, classe, nome)
    if metodo is None:
        return None
    achadas: dict[str, int] = {}
    for no in ast.walk(metodo):
        chamada = _chamada(no)
        if chamada is not None and (chamada[0] not in achadas or chamada[1] < achadas[chamada[0]]):
            achadas[chamada[0]] = chamada[1]
    return achadas


def linhas_que_atribuem(fonte: str, classe: str, nome: str, atributo: str) -> list[int]:
    """As linhas, no método `nome` de `classe`, em que algum objeto recebe `.atributo = ...`."""
    metodo = _metodo(fonte, classe, nome)
    if metodo is None:
        return []
    return sorted(no.lineno for no in ast.walk(metodo) if isinstance(no, ast.Assign)
                  for alvo in no.targets if isinstance(alvo, ast.Attribute) and alvo.attr == atributo)


def _cria_o_controlador(fonte: str) -> int | None:
    """A linha de `self.ativacao = ControladorAtivacao(self)` em `MainWindow.__init__`, ou None."""
    metodo = _metodo(fonte, "MainWindow", "__init__")
    for no in ast.walk(metodo) if metodo is not None else ():
        if (isinstance(no, ast.Assign) and isinstance(no.value, ast.Call) and isinstance(no.value.func, ast.Name)
                and no.value.func.id == "ControladorAtivacao" and len(no.targets) == 1 and isinstance(no.targets[0], ast.Attribute)
                and no.targets[0].attr == "ativacao"):
            return no.lineno
    return None


# ------------------------------------------------------------------------------------------- a função de conferência
_SINTETICO = (
    "class Janela:\n"
    "    def __init__(self):\n"
    "        self.ativacao = ControladorAtivacao(self)\n"
    "        self._build_body()\n"
    "        self.ativacao.montar_painel(self.instrucao)\n"
    "    def _on_hotkey_triggered(self, acao):\n"
    "        if not self.ativacao.acao_permitida(acao):\n"
    "            return\n"
    "        self._run_map_via_hotkey(acao)\n"
    "    def outro(self):\n"
    "        pass\n"
)


def test_a_conferencia_acha_as_chamadas_do_controlador_e_as_da_propria_janela():
    achadas = chamadas_da_ativacao(_SINTETICO, "Janela", "_on_hotkey_triggered")
    assert achadas == {"self.ativacao.acao_permitida": 7, "self._run_map_via_hotkey": 9}


def test_a_conferencia_nao_confunde_outro_metodo_nem_inventa_chamada():
    assert chamadas_da_ativacao(_SINTETICO, "Janela", "outro") == {}
    assert chamadas_da_ativacao(_SINTETICO, "Janela", "nao_existe") is None
    assert chamadas_da_ativacao(_SINTETICO, "OutraClasse", "outro") is None


def test_a_conferencia_acusa_a_chamada_que_sumiu():
    sem_a_guarda = _SINTETICO.replace("if not self.ativacao.acao_permitida(acao):", "if False:")
    assert "self.ativacao.acao_permitida" not in chamadas_da_ativacao(sem_a_guarda, "Janela", "_on_hotkey_triggered")


def test_a_conferencia_acha_as_atribuicoes_de_um_atributo_e_ignora_as_de_outro():
    fonte = "class J:\n    def f(self, m):\n        m.hotkey = 1\n        m.speed = 2\n        if m:\n            m.hotkey = 3\n"
    assert linhas_que_atribuem(fonte, "J", "f", "hotkey") == [3, 6]
    assert linhas_que_atribuem(fonte, "J", "f", "repeat_count") == []
    assert linhas_que_atribuem(fonte, "J", "nao_existe", "hotkey") == []


def test_a_conferencia_acha_onde_o_controlador_e_criado():
    assert _cria_o_controlador(_SINTETICO.replace("Janela", "MainWindow")) == 3
    assert _cria_o_controlador(_SINTETICO.replace("Janela", "MainWindow").replace("ControladorAtivacao(self)", "Outro(self)")) is None


# ------------------------------------------------------------------------------------------- o código real
def _fonte() -> str:
    return JANELA.read_text(encoding="utf-8")


def test_cada_ponto_da_janela_chama_o_que_a_ativacao_precisa():
    faltando = []
    for metodo, esperadas in LIGACOES.items():
        achadas = chamadas_da_ativacao(_fonte(), "MainWindow", metodo)
        if achadas is None:
            faltando.append(f"MainWindow.{metodo} não existe mais (se foi renomeado, leve `self.ativacao.*` junto e atualize LIGACOES)")
            continue
        faltando += [f"MainWindow.{metodo} não chama self.ativacao.{nome}" for nome in esperadas
                     if f"self.ativacao.{nome}" not in achadas]
    assert faltando == []


def test_o_controlador_e_criado_antes_de_qualquer_coisa_que_o_use_no_init():
    # `__init__` monta o corpo, recarrega a lista e registra os atalhos; todos usam `self.ativacao`.
    criacao = _cria_o_controlador(_fonte())
    achadas = chamadas_da_ativacao(_fonte(), "MainWindow", "__init__")
    assert criacao is not None, "MainWindow.__init__ não cria `self.ativacao = ControladorAtivacao(self)`"
    for usa in ("self._build_body", "self._reload_map_list", "self._register_all_hotkeys", "self.ativacao.montar_painel"):
        assert usa in achadas, f"{usa} não é chamado em MainWindow.__init__"
        assert criacao < achadas[usa], f"`self.ativacao` é criado depois de {usa} em MainWindow.__init__"


def test_a_faixa_e_montada_depois_do_corpo_da_janela_que_cria_a_ancora_dela():
    achadas = chamadas_da_ativacao(_fonte(), "MainWindow", "__init__")
    assert achadas["self._build_body"] < achadas["self.ativacao.montar_painel"]


def test_a_guarda_vem_antes_de_executar_o_mapa_pela_tecla():
    achadas = chamadas_da_ativacao(_fonte(), "MainWindow", "_on_hotkey_triggered")
    assert achadas["self.ativacao.acao_permitida"] < achadas["self._run_map_via_hotkey"]


def test_a_janela_nao_grava_a_tecla_no_mapa_sem_passar_pelo_controlador():
    # Quem valida, recusa (com aviso) e grava a tecla é `ControladorAtivacao.mudar_tecla` (testado sem Qt em
    # tests/unit/test_ativacao_controlador.py). Uma atribuição direta `m.hotkey = ...` na janela pularia a validação.
    gravacoes = linhas_que_atribuem(_fonte(), "MainWindow", "_configure_current_map", "hotkey")
    assert gravacoes == [], f"`_configure_current_map` atribui `.hotkey` direto (linhas {gravacoes}); use self.ativacao.mudar_tecla"
