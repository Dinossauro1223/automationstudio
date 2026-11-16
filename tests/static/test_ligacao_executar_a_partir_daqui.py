"""A ligação do "▶ Executar a partir daqui" na tabela de comandos, conferida no código-fonte.

Os menus da tabela (clique direito e "Mais…") só existem com o Qt de verdade e uma janela. Este teste roda em qualquer lugar e
protege a ligação em si. A função não tem caminho próprio de execução: ela entrega os comandos de "daqui" ao `test_requested`,
o sinal do "Testar selecionados", que a janela principal liga a `_test_selected_commands`. Por isso há duas coisas a proteger:

* os dois menus escolhem os comandos pela regra `_ids_a_partir_daqui`, deixam o item cinza quando não há o que rodar e emitem
  `test_requested` com o resultado;
* a janela principal continua ligando `test_requested` ao teste. Se essa linha sumir, o item continuaria no menu e não faria nada.

A lógica (quais comandos entram, o que roda de ponta a ponta) é provada em tests/unit/test_executar_a_partir_daqui.py. Aqui há
controles negativo e positivo sobre um trecho sintético; só depois vem a conferência do código real.
"""
import ast
import os
import pathlib

ROOT = pathlib.Path(os.environ.get("AS_ROOT") or pathlib.Path(__file__).resolve().parents[2])
EDITOR = ROOT / "automationstudio" / "command_editor.py"
JANELA = ROOT / "automationstudio" / "main_window.py"
TABELA = "CommandTableWidget"

# método da tabela -> chamadas (escritas por inteiro) que ele precisa fazer
LIGACOES = {
    "_context_menu": (
        "_ids_a_partir_daqui(self._automation_map.commands, context_ids)",
        "from_a.setEnabled(bool(daqui))",
        "self.test_requested.emit(set(daqui))",
    ),
    "_show_more_actions": (
        "_ids_a_partir_daqui(self._automation_map.commands, ids)",
        "from_a.setEnabled(bool(daqui))",
        "self.test_requested.emit(set(daqui))",
    ),
}
LIGACAO_DA_JANELA = "self.command_table.test_requested.connect(self._test_selected_commands)"


def _classe(fonte: str, nome: str):
    for no in ast.walk(ast.parse(fonte)):
        if isinstance(no, ast.ClassDef) and no.name == nome:
            return no
    return None


def chamadas_do_metodo(fonte: str, classe: str, metodo: str) -> set[str] | None:
    """Cada chamada do método escrita por inteiro (`ast.unparse`); None se a classe ou o método não existe."""
    dono = _classe(fonte, classe)
    if dono is None:
        return None
    for item in dono.body:
        if isinstance(item, ast.FunctionDef) and item.name == metodo:
            return {ast.unparse(no) for no in ast.walk(item) if isinstance(no, ast.Call)}
    return None


def chamadas_da_classe(fonte: str, classe: str) -> set[str]:
    """Todas as chamadas de todos os métodos da classe (para achar uma ligação sem saber em qual método ela mora)."""
    dono = _classe(fonte, classe)
    if dono is None:
        return set()
    return {ast.unparse(no) for no in ast.walk(dono) if isinstance(no, ast.Call)}


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
    "        daqui = _ids_a_partir_daqui(self._automation_map.commands, context_ids)\n"
    "        from_a = menu.addAction('x')\n"
    "        from_a.setEnabled(bool(daqui))\n"
    "        from_a.triggered.connect(lambda: self.test_requested.emit(set(daqui)))\n"
)
_SINTETICO_LIGACOES = {
    "_context_menu": (
        "_ids_a_partir_daqui(self._automation_map.commands, context_ids)",
        "from_a.setEnabled(bool(daqui))",
        "self.test_requested.emit(set(daqui))",
    ),
}


def test_controle_positivo_o_trecho_completo_nao_perde_nada():
    assert faltando(_SINTETICO, "Tabela", _SINTETICO_LIGACOES) == []


def test_controle_negativo_a_conferencia_aponta_o_que_sumiu():
    sem_o_emit = _SINTETICO.replace("        from_a.triggered.connect(lambda: self.test_requested.emit(set(daqui)))\n", "")
    assert faltando(sem_o_emit, "Tabela", _SINTETICO_LIGACOES) == ["_context_menu: self.test_requested.emit(set(daqui))"]
    sem_o_cinza = _SINTETICO.replace("        from_a.setEnabled(bool(daqui))\n", "")
    assert faltando(sem_o_cinza, "Tabela", _SINTETICO_LIGACOES) == ["_context_menu: from_a.setEnabled(bool(daqui))"]
    sem_a_regra = _SINTETICO.replace("_ids_a_partir_daqui(self._automation_map.commands, context_ids)", "list(context_ids)")
    assert faltando(sem_a_regra, "Tabela", _SINTETICO_LIGACOES) == [
        "_context_menu: _ids_a_partir_daqui(self._automation_map.commands, context_ids)"]
    assert faltando("class Tabela:\n    pass\n", "Tabela", _SINTETICO_LIGACOES) == ["_context_menu: não existe"]
    assert chamadas_do_metodo(_SINTETICO, "OutraClasse", "_context_menu") is None


def test_controle_negativo_a_ligacao_da_janela_e_achada_em_qualquer_metodo():
    com = "class J:\n    def a(self):\n        pass\n    def b(self):\n        self.t.x.connect(self.f)\n"
    sem = "class J:\n    def a(self):\n        pass\n    def b(self):\n        self.t.x.connect(self.g)\n"
    assert "self.t.x.connect(self.f)" in chamadas_da_classe(com, "J")
    assert "self.t.x.connect(self.f)" not in chamadas_da_classe(sem, "J")
    assert chamadas_da_classe(com, "OutraClasse") == set()


# ------------------------------------------------------------------------------------------- o código real
def test_os_dois_menus_da_tabela_escolhem_os_comandos_de_daqui_e_entregam_ao_teste():
    assert faltando(EDITOR.read_text(encoding="utf-8"), TABELA, LIGACOES) == []


def test_a_janela_principal_continua_ligando_o_teste_de_selecao_ao_sinal_da_tabela():
    chamadas = chamadas_da_classe(JANELA.read_text(encoding="utf-8"), "MainWindow")
    assert LIGACAO_DA_JANELA in chamadas, "sem esta ligação o item do menu não faz nada: " + LIGACAO_DA_JANELA
