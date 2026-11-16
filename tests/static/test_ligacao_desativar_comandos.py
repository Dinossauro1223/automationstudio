"""A ligação do "Desativar selecionados / Ativar selecionados" na tabela de comandos, conferida no código-fonte de command_editor.py.

Os menus da tabela (clique direito e "Mais…") só existem com o Qt de verdade e uma janela. Este teste roda em qualquer lugar e
protege a ligação em si: se numa fusão de ramos (ou numa refatoração da tabela) o item sumir de um dos menus, deixar de usar a
regra do texto, ou o "Testar selecionados" voltar a ficar ligado quando todos os selecionados estão desativados, o teste diz
qual método perdeu o quê. A lógica por trás (rótulos, ordem das chamadas, pintura da linha) é provada em
tests/unit/test_comandos_desativados.py.

A conferência é uma função pura (`chamadas_do_metodo`), com controles negativo e positivo sobre um trecho sintético; só depois
vem a conferência do código real.
"""
import ast
import os
import pathlib

ROOT = pathlib.Path(os.environ.get("AS_ROOT") or pathlib.Path(__file__).resolve().parents[2])
EDITOR = ROOT / "automationstudio" / "command_editor.py"
CLASSE = "CommandTableWidget"

# método da tabela -> chamadas que ele precisa fazer ("self.x" é um método da tabela; nome solto é função do módulo)
LIGACOES = {
    "_context_menu": ("_acao_ativar_desativar", "self._estados_ligados", "self._set_enabled_ids"),
    "_show_more_actions": ("_acao_ativar_desativar", "self._estados_ligados", "self._set_enabled_ids"),
    "_fill_row": ("_tipo_com_estado",),
    "_set_enabled_ids": ("self._automation_map.set_commands_enabled", "self.refresh", "self._select_ids", "self.map_changed.emit"),
}
# no "Mais…": com todos os selecionados desativados não há o que testar, e o item fica cinza
TESTAR_SO_COM_ATIVO = "test_a.setEnabled(any(ligados))"


def _metodo(fonte: str, classe: str, nome: str):
    for no in ast.walk(ast.parse(fonte)):
        if isinstance(no, ast.ClassDef) and no.name == classe:
            for item in no.body:
                if isinstance(item, ast.FunctionDef) and item.name == nome:
                    return item
    return None


def _nome_da_chamada(no) -> str | None:
    """"f" para `f(...)`; "self.a.b" para `self.a.b(...)`; None para qualquer outra forma de chamada."""
    if not isinstance(no, ast.Call):
        return None
    partes, atual = [], no.func
    while isinstance(atual, ast.Attribute):
        partes.append(atual.attr)
        atual = atual.value
    if not isinstance(atual, ast.Name):
        return None
    return ".".join([atual.id, *reversed(partes)])


def chamadas_do_metodo(fonte: str, classe: str, nome: str) -> dict[str, int] | None:
    """{chamada: linha da primeira vez} das chamadas do método `nome` de `classe`; None se o método não existe."""
    metodo = _metodo(fonte, classe, nome)
    if metodo is None:
        return None
    achadas: dict[str, int] = {}
    for no in ast.walk(metodo):
        chamada = _nome_da_chamada(no)
        if chamada is not None and (chamada not in achadas or no.lineno < achadas[chamada]):
            achadas[chamada] = no.lineno
    return achadas


def chamadas_em_texto(fonte: str, classe: str, nome: str) -> set[str]:
    """Cada chamada do método escrita por inteiro (`ast.unparse`), para conferir um argumento exato."""
    metodo = _metodo(fonte, classe, nome)
    return {ast.unparse(no) for no in ast.walk(metodo) if isinstance(no, ast.Call)} if metodo is not None else set()


def faltando(fonte: str, classe: str, ligacoes: dict[str, tuple[str, ...]]) -> list[str]:
    """O que a tabela perdeu: "método: chamada" para cada chamada esperada que não está lá (ou "método: não existe")."""
    perdidos = []
    for metodo, esperadas in ligacoes.items():
        achadas = chamadas_do_metodo(fonte, classe, metodo)
        if achadas is None:
            perdidos.append(f"{metodo}: não existe")
            continue
        perdidos += [f"{metodo}: {c}" for c in esperadas if c not in achadas]
    return perdidos


# ------------------------------------------------------------------------------------------- a função de conferência
_SINTETICO = (
    "class Tabela:\n"
    "    def _context_menu(self):\n"
    "        ligados = self._estados_ligados(ids)\n"
    "        texto, valor = _acao_ativar_desativar(ligados)\n"
    "        acao = menu.addAction(texto)\n"
    "        acao.triggered.connect(lambda: self._set_enabled_ids(ids, valor))\n"
    "    def _set_enabled_ids(self, ids, enabled):\n"
    "        self._automation_map.set_commands_enabled(ids, enabled)\n"
    "        self.refresh()\n"
    "        self._select_ids(ids)\n"
    "        self.map_changed.emit('x')\n"
)
_SINTETICO_LIGACOES = {
    "_context_menu": ("_acao_ativar_desativar", "self._estados_ligados", "self._set_enabled_ids"),
    "_set_enabled_ids": ("self._automation_map.set_commands_enabled", "self.refresh", "self._select_ids", "self.map_changed.emit"),
}


def test_controle_positivo_o_trecho_completo_nao_perde_nada():
    assert faltando(_SINTETICO, "Tabela", _SINTETICO_LIGACOES) == []


def test_controle_negativo_a_conferencia_aponta_o_que_sumiu():
    sem_o_item_de_menu = _SINTETICO.replace("        acao.triggered.connect(lambda: self._set_enabled_ids(ids, valor))\n", "")
    assert faltando(sem_o_item_de_menu, "Tabela", _SINTETICO_LIGACOES) == ["_context_menu: self._set_enabled_ids"]
    sem_a_regra_do_texto = _SINTETICO.replace("_acao_ativar_desativar(ligados)", "('Desativar selecionados', False)")
    assert faltando(sem_a_regra_do_texto, "Tabela", _SINTETICO_LIGACOES) == ["_context_menu: _acao_ativar_desativar"]
    sem_o_aviso = _SINTETICO.replace("        self.map_changed.emit('x')\n", "")
    assert faltando(sem_o_aviso, "Tabela", _SINTETICO_LIGACOES) == ["_set_enabled_ids: self.map_changed.emit"]
    sem_o_metodo = _SINTETICO.split("    def _set_enabled_ids")[0]
    assert faltando(sem_o_metodo, "Tabela", _SINTETICO_LIGACOES) == ["_set_enabled_ids: não existe"]
    assert chamadas_do_metodo(_SINTETICO, "OutraClasse", "_context_menu") is None


def test_controle_negativo_o_argumento_exato_e_conferido():
    assert "test_a.setEnabled(any(ligados))" in chamadas_em_texto("class T:\n    def m(self):\n        test_a.setEnabled(any(ligados))\n", "T", "m")
    assert "test_a.setEnabled(any(ligados))" not in chamadas_em_texto("class T:\n    def m(self):\n        test_a.setEnabled(bool(ids))\n", "T", "m")
    assert chamadas_em_texto("class T:\n    def m(self):\n        pass\n", "T", "outro") == set()


def test_chamadas_de_forma_estranha_nao_quebram_a_conferencia():
    # `f()()`: a chamada de fora não tem nome, a de dentro (`f`) tem. `x[0].y()` não tem nome. Nenhuma das duas derruba a conferência.
    fonte = "class T:\n    def m(self):\n        f()()\n        x[0].y()\n        self.a.b.c()\n"
    assert chamadas_do_metodo(fonte, "T", "m") == {"f": 3, "self.a.b.c": 5}


# ------------------------------------------------------------------------------------------- o código real
def test_a_tabela_de_comandos_liga_desativar_e_ativar_nos_dois_menus_e_na_pintura():
    fonte = EDITOR.read_text(encoding="utf-8")
    assert faltando(fonte, CLASSE, LIGACOES) == []


def test_o_set_enabled_ids_muda_o_mapa_antes_de_refazer_a_tabela_e_avisa_por_ultimo():
    achadas = chamadas_do_metodo(EDITOR.read_text(encoding="utf-8"), CLASSE, "_set_enabled_ids")
    assert achadas is not None
    ordem = [achadas[c] for c in ("self._automation_map.set_commands_enabled", "self.refresh", "self._select_ids", "self.map_changed.emit")]
    assert ordem == sorted(ordem), "a ordem tem de ser: mudar o mapa, refazer a tabela, marcar a seleção, avisar a janela"


def test_o_testar_selecionados_so_fica_ligado_se_algum_selecionado_esta_ativo():
    fonte = EDITOR.read_text(encoding="utf-8")
    assert TESTAR_SO_COM_ATIVO in chamadas_em_texto(fonte, CLASSE, "_show_more_actions")
    assert "test_a.setEnabled(bool(ids))" not in chamadas_em_texto(fonte, CLASSE, "_show_more_actions")
