"""Invariantes estáticos do código-fonte, como funções puras: recebem texto-fonte e devolvem os problemas.

Por serem puras, cada invariante é testado contra trechos sintéticos com defeito plantado (controle negativo)
e contra o código real. Isso evita o risco de uma verificação que "nunca reclama" por estar quebrada.
"""
from __future__ import annotations

import ast
import builtins
import collections
import re
import symtable


# --------------------------------------------------------------------------------------------- nomes
def _tables(table):
    yield table
    for child in table.get_children():
        yield from _tables(child)


def unresolved_globals(source: str, namespace: set[str], filename: str = "<fonte>") -> list[str]:
    """Nomes usados como globais que não existem no módulo (nem nos builtins). Pega KeyCode, shutil etc."""
    top = symtable.symtable(source, filename, "exec")
    declared = {s.get_name() for t in _tables(top) for s in t.get_symbols() if s.is_declared_global() and s.is_assigned()}
    builtin_names = set(dir(builtins))
    found = set()
    for table in _tables(top):
        if table is top:  # a tabela do módulo se chama "top" em todas as versões (get_type() mudou na 3.13)
            continue
        for symbol in table.get_symbols():
            name = symbol.get_name()
            if symbol.is_global() and symbol.is_referenced() and not symbol.is_assigned():
                if name not in namespace and name not in builtin_names and name not in declared:
                    found.add(f"{table.get_name()} (linha {table.get_lineno()}) usa '{name}', que não existe")
    return sorted(found)


def duplicate_methods(source: str) -> list[str]:
    """Métodos definidos duas vezes na mesma classe: o segundo apaga o primeiro em silêncio."""
    found = []
    for cls in (n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.ClassDef)):
        seen = collections.defaultdict(list)
        for item in cls.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                decorators = [ast.unparse(d) for d in item.decorator_list]
                if any(s in d for d in decorators for s in (".setter", ".getter", ".deleter", "overload")):
                    continue
                seen[item.name].append(item.lineno)
        found += [f"{cls.name}.{name} definido nas linhas {lines}" for name, lines in seen.items() if len(lines) > 1]
    return sorted(found)


def unresolved_self_calls(sources: dict[str, str]) -> list[str]:
    """Chamadas self._metodo() (nomes do projeto, com sublinhado) para métodos que não existem na classe."""
    classes = {}
    for module, source in sources.items():
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ClassDef):
                members = set()
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        members.add(item.name)
                    elif isinstance(item, ast.Assign):
                        members |= {x.id for t in item.targets for x in ast.walk(t) if isinstance(x, ast.Name)}
                    elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                        members.add(item.target.id)
                for x in ast.walk(node):
                    if isinstance(x, ast.Attribute) and isinstance(x.value, ast.Name) and x.value.id == "self" and isinstance(x.ctx, ast.Store):
                        members.add(x.attr)
                classes[node.name] = (module, node, members, [ast.unparse(b) for b in node.bases])

    def all_members(name, seen=None):
        seen = seen or set()
        if name in seen or name not in classes:
            return set()
        seen.add(name)
        out = set(classes[name][2])
        for base in classes[name][3]:
            out |= all_members(base, seen)
        return out

    found = []
    for name, (module, node, _members, _bases) in classes.items():
        defined = all_members(name)
        for x in ast.walk(node):
            if isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute) and isinstance(x.func.value, ast.Name) and x.func.value.id == "self":
                attr = x.func.attr
                if ("_" in attr.strip("_") or attr.startswith("_")) and not attr.startswith("__") and attr not in defined:
                    found.append(f"{module}.{name} chama self.{attr}() (linha {x.lineno}), mas o método não existe")
    return sorted(found)


# --------------------------------------------------------------------------------------------- sinais
def signals_without_connect(sources: dict[str, str], class_suffix: str = "Bridge") -> list[str]:
    """Signal declarado nas pontes (classes *Bridge) sem nenhum .connect(...) no código: o evento se perde."""
    declared = []
    for source in sources.values():
        for cls in (n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.ClassDef) and n.name.endswith(class_suffix)):
            for item in cls.body:
                if isinstance(item, ast.Assign) and isinstance(item.value, ast.Call) and ast.unparse(item.value.func) == "Signal":
                    declared += [(cls.name, t.id) for t in item.targets if isinstance(t, ast.Name)]
    everything = "\n".join(sources.values())
    return sorted(f"{cls}.{sig}" for cls, sig in declared if not re.search(rf"\.{sig}\s*\.\s*connect\s*\(", everything))


# ------------------------------------------------------------------------------- constantes e textos
def rebound_core_constants(sources: dict[str, str], names: set[str], core_module: str = "core") -> list[str]:
    """`global X` (ou leitura direta de X) fora do core: só rebinda/lê uma cópia local e o motor não vê a mudança."""
    found = []
    for module, source in sources.items():
        if module == core_module:
            continue
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Global):
                found += [f"{module}:{node.lineno} 'global {n}'" for n in node.names if n in names]
            elif isinstance(node, ast.Name) and node.id in names and isinstance(node.ctx, ast.Load):
                found.append(f"{module}:{node.lineno} lê a cópia local de {node.id} (use core.{node.id})")
    return sorted(found)


def literal_backslash_n(source: str) -> list[int]:
    """Strings que contêm barra invertida + n literal (quase sempre um '\\\\n' escrito por engano em f-string)."""
    return sorted({n.lineno for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Constant) and isinstance(n.value, str) and "\\n" in n.value})


def star_import_count(sources: dict[str, str]) -> int:
    return sum(1 for s in sources.values() for n in ast.walk(ast.parse(s)) if isinstance(n, ast.ImportFrom) and any(a.name == "*" for a in n.names))


def unreferenced_methods(sources: dict[str, str], extra_text: str = "") -> list[str]:
    """Métodos/funções snake_case definidos e nunca citados em lugar nenhum (candidatos a código morto)."""
    everything = "\n".join(sources.values()) + "\n" + extra_text
    counts = collections.Counter(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", everything))
    found = []
    for module, source in sources.items():
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = node.name
                if name.startswith("__") or not re.fullmatch(r"_?[a-z][a-z0-9_]*", name):
                    continue
                if counts[name] <= 1:
                    found.append(f"{module}:{node.lineno} {name}")
    return sorted(found)


# ------------------------------------------------------------------------------ scripts e versões
def hardcoded_python3(bat_texts: dict[str, str]) -> list[str]:
    """Scripts que escolhem 'py -3' em vez da versão definida em python_version.txt."""
    return sorted(f"{name}:{i}" for name, text in bat_texts.items() for i, line in enumerate(text.splitlines(), 1)
                  if re.search(r"\bpyw?\.exe\s+-3\b", line))


def bat_with_lf_only(bat_bytes: dict[str, bytes]) -> list[str]:
    """Scripts .bat com fim de linha LF: o cmd.exe pode falhar em 'goto' e rótulos."""
    return sorted(name for name, data in bat_bytes.items() if data.count(b"\n") != data.count(b"\r\n"))


def bat_with_non_ascii(bat_bytes: dict[str, bytes]) -> list[str]:
    """Scripts .bat com algum byte fora do ASCII. Com `chcp 65001` o cmd.exe lê o arquivo na página de código ativa, e um
    acento dentro de um `rem` ou de um `echo` pode quebrar a leitura da linha. Os textos dos .bat são escritos sem acento."""
    return sorted(name for name, data in bat_bytes.items() if any(byte > 127 for byte in data))


_PREFIXO_DE_REDIRECIONAMENTO = re.compile(r'^(?:\d?>>?\s*(?:"[^"]*"|\S+)\s*)+')
_ALVO_DE_REDIRECIONAMENTO = re.compile(r'(?<![0-9&])>>?\s*(?!&)("[^"]*"|\S+)')
_COMANDO_PYTHON = re.compile(r"^(?:pyw?|python|pythonw)\.exe(?=\s)|^%PYEXE%(?=\s)", re.IGNORECASE)


def bat_python_sem_utf8(bat_texts: dict[str, str]) -> list[str]:
    """Chamadas ao Python que gravam num arquivo (o log) sem `set "PYTHONUTF8=1"` antes, na ordem do script.

    O cmd.exe com `chcp 65001` grava os `echo` em UTF-8, mas o Python redirecionado para um arquivo escreve na página de código
    ANSI (cp1252). O mesmo log mistura as duas e uma pasta com acento no nome fica ilegível. `set "PYTHONUTF8="` desliga de novo
    (o programa em si não deve herdar o modo UTF-8). Redirecionar para `nul` não conta."""
    achados = []
    for nome, texto in bat_texts.items():
        utf8 = False
        for numero, linha in enumerate(texto.splitlines(), 1):
            limpa = linha.strip()
            if re.match(r"(?i)(rem\b|::)", limpa):
                continue
            definicao = re.match(r'(?i)set\s+"?PYTHONUTF8=([^"\s]*)"?\s*$', limpa)
            if definicao:
                utf8 = definicao.group(1) == "1"
                continue
            comando = _PREFIXO_DE_REDIRECIONAMENTO.sub("", limpa, count=1).lstrip()
            if not _COMANDO_PYTHON.match(comando) or utf8:
                continue
            alvos = [alvo.strip('"').lower() for alvo in _ALVO_DE_REDIRECIONAMENTO.findall(limpa)]
            if any(alvo != "nul" for alvo in alvos):
                achados.append(f"{nome}:{numero}")
    return sorted(achados)


def bat_captura_texto_do_python(bat_texts: dict[str, str]) -> list[str]:
    """`for /f` sobre a saída do Python. O caminho do interpretador copiado para uma variável do cmd.exe chegava errado quando
    o nome do usuário tinha acento (o Python escreve cp1252, o cmd lê a página de código ativa) e `if exist` falhava."""
    return sorted(f"{nome}:{numero}" for nome, texto in bat_texts.items() for numero, linha in enumerate(texto.splitlines(), 1)
                  if re.search(r"(?i)\bfor\s+/f\b.*\bin\s*\(\s*'[^']*\b(?:pyw?|python|pythonw)\.exe\b", linha))


def version_mismatches(versions: dict[str, str]) -> list[str]:
    """Todas as origens de versão precisam ser iguais (ex.: __init__, core, README)."""
    distinct = {v for v in versions.values()}
    return [] if len(distinct) <= 1 else [f"{k} = {v}" for k, v in sorted(versions.items())]


def installer_requirements_mismatch(installer_text: str, requirements_text: str) -> list[str]:
    """Pacotes do requirements.txt que o instalador .bat não instala (e vice-versa), por nome."""
    def names_from_requirements(text):
        out = set()
        for line in text.splitlines():
            line = line.split("#")[0].strip()
            if line and not line.startswith("-"):
                out.add(re.split(r"[<>=!~\[ ;]", line, maxsplit=1)[0].lower())
        return out

    installed = {m.lower() for m in re.findall(r'"([A-Za-z0-9_.-]+)\s*(?:[<>=!~][^"]*)?"', installer_text)}
    wanted = names_from_requirements(requirements_text)
    problems = [f"{n} está no requirements.txt mas o instalador não o instala" for n in sorted(wanted - installed) if n]
    return problems


# ------------------------------------------------------------------------------ compatibilidade (Python 3.14)
REMOVED_STDLIB = frozenset({
    "distutils", "imp", "asyncore", "asynchat", "smtpd", "cgi", "cgitb", "pipes", "telnetlib", "nntplib", "crypt", "imghdr",
    "sndhdr", "mailcap", "audioop", "aifc", "chunk", "sunau", "uu", "xdrlib", "msilib", "nis", "ossaudiodev", "spwd", "lib2to3"})


def removed_stdlib_imports(sources: dict[str, str], removed: frozenset[str] = REMOVED_STDLIB) -> list[str]:
    """Imports de módulos que saíram da biblioteca padrão até o Python 3.13 (o projeto roda no 3.14)."""
    found = []
    for module, source in sources.items():
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                found += [f"{module}:{node.lineno} import {a.name}" for a in node.names if a.name.split(".")[0] in removed]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0 and node.module.split(".")[0] in removed:
                found.append(f"{module}:{node.lineno} from {node.module} import ...")
    return sorted(found)


def syntax_warnings(sources: dict[str, str]) -> list[str]:
    """SyntaxWarning de compilação (escape inválido em string, etc.): viram erro em versões futuras do Python."""
    import warnings
    found = []
    for module, source in sources.items():
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            compile(source, f"{module}.py", "exec")
        found += [f"{module}:{w.lineno} {w.message}" for w in caught if issubclass(w.category, (SyntaxWarning, DeprecationWarning))]
    return sorted(found)


def saidas_de_finally(sources: dict[str, str]) -> list[str]:
    """`return`, `break` ou `continue` que SAI de um bloco `finally` (PEP 765): o Python 3.14 já emite SyntaxWarning e uma versão
    futura deve recusar o código. O `syntax_warnings` só enxerga isso rodando na própria 3.14; esta checagem enxerga em qualquer
    versão. Um `break`/`continue` dentro de um laço que está DENTRO do finally não sai dele, e uma função definida lá dentro tem
    o próprio `return`: nenhum dos dois é acusado."""
    achados = []

    def procurar(no: ast.AST, dentro_de_laco: bool, modulo: str) -> None:
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            return
        if isinstance(no, ast.Return):
            achados.append(f"{modulo}:{no.lineno} return sai de um bloco finally")
        elif isinstance(no, (ast.Break, ast.Continue)) and not dentro_de_laco:
            achados.append(f"{modulo}:{no.lineno} {type(no).__name__.lower()} sai de um bloco finally")
        laco = dentro_de_laco or isinstance(no, (ast.For, ast.AsyncFor, ast.While))
        for filho in ast.iter_child_nodes(no):
            procurar(filho, laco, modulo)

    tipos_de_try = tuple(t for t in (ast.Try, getattr(ast, "TryStar", None)) if t is not None)
    for modulo, fonte in sources.items():
        for no in ast.walk(ast.parse(fonte)):
            if isinstance(no, tipos_de_try):
                for instrucao in no.finalbody:
                    procurar(instrucao, False, modulo)
    return sorted(set(achados))


_USER_PATH = re.compile(r"(?:[A-Za-z]:[\\/]+Users[\\/]+\w|/home/\w|/Users/\w)")


def hardcoded_user_paths(sources: dict[str, str]) -> list[str]:
    """Caminhos de usuário escritos no código (C:\\Users\\fulano, /home/fulano): quebram em qualquer outra máquina."""
    found = []
    for module, source in sources.items():
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and _USER_PATH.search(node.value):
                found.append(f"{module}:{node.lineno} {node.value[:40]!r}")
    return sorted(found)


def has_bom(raw: dict[str, bytes]) -> list[str]:
    """Arquivos de texto que começam com BOM UTF-8 (o Python aceita; ferramentas e diffs reclamam)."""
    return sorted(name for name, data in raw.items() if data.startswith(b"\xef\xbb\xbf"))


# ------------------------------------------------------------------------------ decisões de projeto
def names_used_outside(sources: dict[str, str], names: set[str], allowed_modules: set[str]) -> list[str]:
    """Uso (leitura, chamada ou atributo) de `names` fora dos módulos permitidos. Mantém uma decisão de projeto no lugar."""
    found = []
    for module, source in sources.items():
        if module in allowed_modules:
            continue
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Name) and node.id in names:
                found.append(f"{module}:{node.lineno} {node.id}")
            elif isinstance(node, ast.Attribute) and node.attr in names:
                found.append(f"{module}:{node.lineno} .{node.attr}")
            elif isinstance(node, ast.alias) and node.name in names:
                found.append(f"{module}:{getattr(node, 'lineno', 0)} import {node.name}")
    return sorted(found)


# ------------------------------------------------------------------------------ higiene dos próprios testes
def duplicate_toplevel_functions(source: str) -> list[str]:
    """Funções de topo com o mesmo nome no mesmo arquivo: a segunda apaga a primeira e o teste some sem aviso."""
    seen = collections.defaultdict(list)
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            seen[node.name].append(node.lineno)
    return sorted(f"{name} nas linhas {lines}" for name, lines in seen.items() if len(lines) > 1)


def duplicate_basenames(paths: list[str]) -> list[str]:
    """Arquivos de teste com o mesmo nome em pastas diferentes (o pytest sem pacotes não consegue importar os dois)."""
    by_name = collections.defaultdict(list)
    for path in paths:
        by_name[path.replace("\\", "/").rsplit("/", 1)[-1]].append(path)
    return sorted(f"{name}: {sorted(where)}" for name, where in by_name.items() if len(where) > 1)


def long_real_sleeps(source: str, limit: float = 0.5) -> list[str]:
    """time.sleep(<número literal>) acima do limite: o teste deveria usar o relógio virtual ou um evento.

    Só conta a espera REAL: `time.sleep` (ou um apelido do módulo `time`) e o `sleep` importado de `time`.
    Um `relogio.sleep(2)` do relógio virtual não dorme de verdade e não é achado."""
    tree = ast.parse(source)
    modulos_time: set[str] = set()
    funcoes_sleep: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modulos_time.update(alias.asname or alias.name for alias in node.names if alias.name == "time")
        elif isinstance(node, ast.ImportFrom) and node.module == "time":
            funcoes_sleep.update(alias.asname or alias.name for alias in node.names if alias.name == "sleep")
    found = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and node.args):
            continue
        func = node.func
        espera_real = (
            (isinstance(func, ast.Attribute) and func.attr == "sleep" and isinstance(func.value, ast.Name)
             and func.value.id in modulos_time)
            or (isinstance(func, ast.Name) and func.id in funcoes_sleep))
        arg = node.args[0]
        if espera_real and isinstance(arg, ast.Constant) and isinstance(arg.value, (int, float)) and arg.value > limit:
            found.append(f"linha {node.lineno}: sleep({arg.value})")
    return found


def names_defined_by_classes(sources: dict[str, str]) -> set[str]:
    """Nomes que as classes do pacote definem: `def x`, `self.x = ...` e atributos/sinais declarados no corpo da classe."""
    names: set[str] = set()
    for source in sources.values():
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names.add(node.name)
            elif (isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store)
                  and isinstance(node.value, ast.Name) and node.value.id == "self"):
                names.add(node.attr)
            elif isinstance(node, ast.ClassDef):
                for stmt in node.body:
                    alvos = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target] if isinstance(stmt, ast.AnnAssign) else []
                    names.update(alvo.id for alvo in alvos if isinstance(alvo, ast.Name))
    return names


def unknown_attributes_on(test_source: str, variables: set[str], defined: set[str], inherited: frozenset[str] = frozenset()) -> list[str]:
    """Atributos que um teste lê numa variável (por exemplo `janela.pages`) e que NENHUMA classe do pacote define.

    Serve aos testes escritos sem poder rodá-los (janela principal, que exige o Qt real): um nome errado só apareceria na
    máquina do usuário. `inherited` lista o que vem da própria classe do Qt (windowTitle, show, ...)."""
    achados = []
    vistos: set[tuple[str, str]] = set()
    for node in ast.walk(ast.parse(test_source)):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in variables:
            chave = (node.value.id, node.attr)
            if node.attr not in defined and node.attr not in inherited and chave not in vistos:
                vistos.add(chave)
                achados.append(f"linha {node.lineno}: {node.value.id}.{node.attr}")
    return sorted(achados)


def tests_without_fixture(source: str, fixtures: set[str]) -> list[str]:
    """Funções `test_*` do arquivo que NÃO pedem nenhuma das fixtures dadas (por exemplo `gui`, que isola os diálogos).

    Serve aos testes de janela: sem o isolamento, um diálogo modal inesperado (QMessageBox, seletor de arquivo) travaria a
    rodada inteira no Qt real, e com o stub de lógica o teste rodaria contra uma casca vazia."""
    return sorted(node.name for node in ast.parse(source).body
                  if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
                  and not ({arg.arg for arg in node.args.args} & fixtures))


def testes_com_fixture(source: str, fixture: str) -> list[str]:
    """Funções `test_*` de nível de módulo que pedem a fixture."""
    return sorted(node.name for node in ast.parse(source).body
                  if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
                  and fixture in {arg.arg for arg in node.args.args})


def testes_sem_marcador(source: str, fixture: str, marcador: str) -> list[str]:
    """Funções `test_*` que pedem `fixture` e NÃO têm o marcador `pytest.mark.<marcador>`: nem no módulo (`pytestmark = ...`)
    nem no próprio teste (decorador).

    Serve à janela principal: ela só roda sem risco para a rodada se cada teste for isolado num processo com tempo limite
    (`Rodar_Testes.bat`, marcador `isolado`). Um teste que abre a janela e esquecesse o marcador rodaria no processo comum,
    onde um travamento do Qt (como o de 18/10/2026) derruba junto todos os testes que vêm depois dele."""
    def marcadores(no: ast.AST) -> set[str]:
        return {n.attr for n in ast.walk(no) if isinstance(n, ast.Attribute) and _e_pytest(n.value, "mark")}

    arvore = ast.parse(source)
    do_modulo: set[str] = set()
    for no in arvore.body:
        if isinstance(no, ast.Assign) and any(isinstance(alvo, ast.Name) and alvo.id == "pytestmark" for alvo in no.targets):
            do_modulo |= marcadores(no.value)
    do_teste = {no.name: set().union(*(marcadores(d) for d in no.decorator_list)) if no.decorator_list else set()
                for no in arvore.body if isinstance(no, ast.FunctionDef)}
    return [nome for nome in testes_com_fixture(source, fixture) if marcador not in do_modulo | do_teste[nome]]


def golden_orfaos(nomes: list[str], fontes_dos_cenarios: str) -> list[str]:
    """Golden que nenhum cenário cita (o nome entre aspas) no código-fonte dos cenários."""
    return [nome for nome in nomes if f'"{nome}"' not in fontes_dos_cenarios]


def envios_sem_guarda(source: str, isentas: frozenset = frozenset()) -> list[str]:
    """Verificações e2e públicas que mandam botão de mouse, texto ou rodam um mapa ANTES de conferir que a janela de teste
    está em primeiro plano (as guardas são `_ir_para`, `_digitar_e_ler`, `em_primeiro_plano` e `sob_o_cursor_e_na_frente`).

    Envio de entrada de verdade sem essa conferência poderia clicar ou digitar em outro programa do usuário. A guarda
    precisa vir ANTES do primeiro envio, na ordem do código: uma guarda só mais adiante (ou só num caminho posterior)
    não protege o clique do começo. Foi o que o verificador de mutações achou (NET16): a função tinha duas guardas e,
    sem a primeira, a checagem antiga, que só olhava se havia ALGUMA guarda, continuava satisfeita."""
    perigosos = {"mouse_down", "mouse_up", "type_text", "run"}
    guardas = {"_ir_para", "_digitar_e_ler", "em_primeiro_plano", "sob_o_cursor_e_na_frente"}
    achados = []
    for node in ast.parse(source).body:
        if not isinstance(node, ast.FunctionDef) or node.name.startswith("_") or node.name in isentas:
            continue
        chamadas = sorted((n.lineno, n.col_offset, n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", ""))
                          for n in ast.walk(node) if isinstance(n, ast.Call))
        primeira_guarda = next(((linha, coluna) for linha, coluna, nome in chamadas if nome in guardas), None)
        if any(nome in perigosos and (primeira_guarda is None or (linha, coluna) < primeira_guarda)
               for linha, coluna, nome in chamadas):
            achados.append(node.name)
    return sorted(achados)


def chamadas_a_verificacoes(source: str, modulo: str = "v") -> set[str]:
    """Nomes `modulo.funcao` citados no arquivo de testes (as verificações que cada módulo e2e executa)."""
    return {n.attr for n in ast.walk(ast.parse(source))
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == modulo}


def attributes_used_on(source: str, variables: set[str]) -> set[str]:
    """Nomes lidos ou chamados em variáveis com os nomes dados (`amb.cursor`, `janela.texto`...)."""
    return {n.attr for n in ast.walk(ast.parse(source))
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id in variables}


def class_member_names(source: str, class_name: str) -> set[str]:
    """Tudo o que a classe define: métodos, atributos de classe e `self.x = ...`, incluindo o das classes-base escritas NO MESMO arquivo."""
    tree = ast.parse(source)
    classes = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    names: set[str] = set()
    pending = [class_name]
    while pending:
        node = classes.get(pending.pop())
        if node is None:
            continue
        pending.extend(base.id for base in node.bases if isinstance(base, ast.Name))
        for child in ast.walk(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names.add(child.name)
            elif (isinstance(child, ast.Attribute) and isinstance(child.ctx, ast.Store)
                  and isinstance(child.value, ast.Name) and child.value.id == "self"):
                names.add(child.attr)
        for stmt in node.body:
            alvos = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target] if isinstance(stmt, ast.AnnAssign) else []
            names.update(alvo.id for alvo in alvos if isinstance(alvo, ast.Name))
    return names


# ------------------------------------------------------------------------------ subconjunto portátil do pytest
MARCADORES_DO_PYTEST = frozenset({"parametrize", "xfail", "skip", "skipif"})
FIXTURES_DO_EXECUTOR_MINIMO = frozenset({"tmp_path", "monkeypatch"})


def marcadores_declarados(ini_text: str) -> set[str]:
    """Nomes da lista `markers =` do pytest.ini."""
    nomes: set[str] = set()
    dentro = False
    for linha in ini_text.splitlines():
        if re.match(r"\s*markers\s*=", linha):
            dentro = True
            resto = linha.split("=", 1)[1].strip()
            if resto:
                nomes.add(resto.split(":")[0].strip())
        elif dentro and linha.strip() and linha[0] in " \t":
            nomes.add(linha.strip().split(":")[0].strip())
        elif dentro and linha.strip():
            dentro = False
    return nomes


def _e_pytest(no: ast.AST, atributo: str) -> bool:
    return (isinstance(no, ast.Attribute) and no.attr == atributo and isinstance(no.value, ast.Name) and no.value.id == "pytest")


def _decorador_e(decorador: ast.AST, atributo: str) -> bool:
    alvo = decorador.func if isinstance(decorador, ast.Call) else decorador
    return _e_pytest(alvo, atributo)


def fixtures_definidas(source: str) -> set[str]:
    """Funções decoradas com `@pytest.fixture` no arquivo (é o que o conftest.py oferece aos testes)."""
    return {no.name for no in ast.walk(ast.parse(source)) if isinstance(no, ast.FunctionDef)
            and any(_decorador_e(d, "fixture") for d in no.decorator_list)}


def fora_do_subconjunto_portatil(source: str, fixtures: set[str], marcadores: set[str], suportados: set[str],
                                 conftest: bool = False) -> list[str]:
    """O que um arquivo de teste usa e o executor mínimo do projeto (sem pytest) não entende, ou que o pytest com
    `--strict-markers` recusa. Os testes rodam nos dois: o que só um dos dois entende apareceria como falha só em um deles.

    * fixture definida fora do conftest.py (o executor mínimo só lê as do conftest);
    * parâmetro de teste que não é fixture do projeto nem argumento de `parametrize` (capsys, request, tmpdir...);
    * `pytest.<nome>` que o executor mínimo não tem (pytest.param, pytest.warns...);
    * marcador não declarado em pytest.ini (o executor mínimo aceitaria, o pytest estrito recusaria; usefixtures e
      filterwarnings, em particular, ele ignoraria em silêncio)."""
    achados = []
    arvore = ast.parse(source)
    for no in ast.walk(arvore):
        if isinstance(no, ast.Attribute) and isinstance(no.value, ast.Attribute) and _e_pytest(no.value, "mark"):
            if no.attr not in marcadores | MARCADORES_DO_PYTEST:
                achados.append(f"linha {no.lineno}: marcador pytest.mark.{no.attr} não declarado em pytest.ini")
        elif _e_pytest(no, no.attr if isinstance(no, ast.Attribute) else "") and no.attr not in suportados:
            achados.append(f"linha {no.lineno}: pytest.{no.attr} não existe no executor mínimo")
        if isinstance(no, ast.FunctionDef):
            if not conftest and any(_decorador_e(d, "fixture") for d in no.decorator_list):
                achados.append(f"linha {no.lineno}: fixture {no.name} definida fora do conftest.py")
    if not conftest:
        for no in arvore.body:
            if not (isinstance(no, ast.FunctionDef) and no.name.startswith("test_")):
                continue
            parametrizados: set[str] = set()
            for decorador in no.decorator_list:
                if isinstance(decorador, ast.Call) and isinstance(decorador.func, ast.Attribute) and decorador.func.attr == "parametrize" and decorador.args:
                    nomes = decorador.args[0]
                    if isinstance(nomes, ast.Constant) and isinstance(nomes.value, str):
                        parametrizados |= {n.strip() for n in nomes.value.split(",")}
                    elif isinstance(nomes, (ast.List, ast.Tuple)):
                        parametrizados |= {e.value for e in nomes.elts if isinstance(e, ast.Constant)}
            for arg in no.args.args:
                if arg.arg not in fixtures | FIXTURES_DO_EXECUTOR_MINIMO | parametrizados:
                    achados.append(f"linha {no.lineno}: {no.name} pede '{arg.arg}', que não é fixture do projeto nem parâmetro")
    return sorted(achados)
