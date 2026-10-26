"""Ponto 1 — testes de REPRODUÇÃO dos defeitos achados na auditoria do AS 25.3 (suíte de regressão permanente).

Cada teste nasceu de um achado do relatório (itens 1.01 a 1.17). Eles falham no AS 25.3 e passam no 25.4.

Legenda dos comentários
-----------------------
[VERMELHO]  falhava no 25.3 (reproduzia o defeito); agora passa e não pode voltar a falhar.
[VERDE]     já passava no 25.3 e protege comportamento que as correções não podem quebrar.
(25.5) D1, D3 e D6 foram decididos e implementados: não há mais testes marcados como xfail.

Todos rodam sem GUI visível e sem enviar input real (backend Mock).
Execução:  python -m pytest -q    (ou ``AS_ROOT=<pasta do projeto>`` se este arquivo estiver em outro lugar).
"""
from __future__ import annotations

import ast
import builtins
import collections
import importlib
import json
import os
import pathlib
import re
import sqlite3
import subprocess
import symtable
import sys
import threading
import time
import types

import pytest

ROOT = pathlib.Path(os.environ.get("AS_ROOT") or pathlib.Path(__file__).resolve().parents[2])
PKG = ROOT / "automationstudio"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automationstudio import core, input_system, project  # noqa: E402
from automationstudio.conditions import WaitCondition, WaitConditionType  # noqa: E402
from automationstudio.core import (  # noqa: E402
    ActionType, AutomationMap, Command, InputType, State, StateManager, map_from_json, map_to_json,
)
from automationstudio.input_system import (  # noqa: E402
    ExecutionEngine, GlobalHotkeyManager, GlobalInputMonitor, MockInputBackend, Recorder, RecorderFilters,
)


# --------------------------------------------------------------------------- utilitários
def _src(name: str) -> str:
    return (PKG / name).read_text(encoding="utf-8")


def _tree(name: str) -> ast.Module:
    return ast.parse(_src(name))


def _all_modules() -> list[str]:
    return sorted(p.stem for p in PKG.glob("*.py"))


def _run_to_end(engine: ExecutionEngine, automation_map: AutomationMap, timeout: float = 6.0):
    """Roda o mapa e espera o fim natural (ou erro). Retorna (terminou, erros)."""
    done, errors = threading.Event(), []
    engine.on_finished.append(done.set)
    engine.on_error.append(lambda exc: (errors.append(exc), done.set()))
    engine.run(automation_map)
    return done.wait(timeout), errors


def _key(target: str, start: float, duration: float, **kw) -> Command:
    return Command(type=InputType.KEY, target=target, start=start, duration=duration, **kw)


# =========================================================================== 1.1 validate()
def _comandos_sem_duracao() -> dict[str, Command]:
    return {
        "MOUSE_MOVE": Command(type=InputType.MOUSE_MOVE, x=10, y=10),
        "MOUSE_SCROLL": Command(type=InputType.MOUSE_SCROLL, scroll_dy=3),
        "WAIT": Command(type=InputType.WAIT, conditions=[WaitCondition(type=WaitConditionType.DELAY, timeout=0.05)]),
    }


def test_p1_01_comandos_sem_duracao_sao_validos():  # [VERMELHO]
    """Mover mouse, rolar e Esperar não têm duração; validate() não pode tratá-los como erro."""
    for nome, cmd in _comandos_sem_duracao().items():
        assert cmd.validate() == [], f"{nome}: {cmd.validate()}"


def test_p1_01_motor_executa_mapa_com_mover_rolar_e_esperar():  # [VERMELHO]
    cmds = list(_comandos_sem_duracao().values())
    for i, c in enumerate(cmds):
        c.start = i * 0.05
    be = MockInputBackend()
    ok, errors = _run_to_end(ExecutionEngine(be), AutomationMap(name="P1-01", repeat_count=1, commands=cmds))
    assert ok and not errors, errors
    acoes = {e[1] for e in be.events}
    assert {"mouse_move", "mouse_scroll"} <= acoes, acoes


def test_p1_01_press_release_com_duracao_zero_continua_invalido():  # [VERDE]
    """Proteção contra tecla presa: a timeline ordena UP antes de DOWN no mesmo instante."""
    for tipo, alvo in ((InputType.KEY, "A"), (InputType.MOUSE_BUTTON, "left")):
        assert Command(type=tipo, target=alvo, duration=0.0).validate(), f"{tipo} com duração 0 deveria ser inválido"


# =========================================================================== 1.2 IDs
_CODIGO_IDS = r'''
import sys, json
sys.path[:0] = json.loads(sys.argv[1])
from automationstudio.core import Command, InputType, map_from_json
payload = {"format_version": 1, "map": {"name": "Salvo", "commands": [
    {"id": "cmd_000001", "type": "key", "target": "A", "duration": 0.1, "start": 0.0},
    {"id": "cmd_000003", "type": "key", "target": "B", "duration": 0.1, "start": 0.2},
    {"id": "cmd_000005", "type": "key", "target": "C", "duration": 0.1, "start": 0.4},
    {"id": "cmd_000006", "type": "key", "target": "D", "duration": 0.1, "start": 0.6},
    {"id": "cmd_000007", "type": "key", "target": "E", "duration": 0.1, "start": 0.8}]}}
m = map_from_json(json.dumps(payload))
novos = [Command(type=InputType.KEY, target=t, duration=0.1, start=1.0 + i * 0.2) for i, t in enumerate("XY")]
for c in novos:
    m.add_command(c)
ids = [c.id for c in m.commands]
removidos = m.remove_commands({novos[0].id}, compact=False)
print(json.dumps({"ids": ids, "removidos": [c.target for c in removidos]}))
'''


def test_p1_02_ids_novos_nao_colidem_com_ids_carregados_de_sessao_anterior():  # [VERMELHO]
    """Processo novo (contador zerado) + mapa salvo antes: comando novo não pode herdar ID existente."""
    out = subprocess.run([sys.executable, "-c", _CODIGO_IDS, json.dumps(sys.path)], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    r = json.loads(out.stdout.strip().splitlines()[-1])
    duplicados = sorted({i for i in r["ids"] if r["ids"].count(i) > 1})
    assert not duplicados, f"IDs duplicados no mapa: {duplicados}"
    assert r["removidos"] == ["X"], f"remover 1 comando removeu {r['removidos']}"


def test_p1_02_ids_sao_unicos_dentro_da_mesma_sessao():  # [VERDE]
    ids = [Command(type=InputType.KEY, target="A", duration=0.1).id for _ in range(200)]
    assert len(ids) == len(set(ids))


# =========================================================================== 1.3 encadeamento
def test_p1_03_todo_sinal_das_pontes_da_janela_tem_connect():  # [VERMELHO]
    """EngineBridge.chain_requested é emitido pelo motor mas nunca ligado a _on_chain_requested."""
    declarados = []
    for cls in [n for n in ast.walk(_tree("main_window.py")) if isinstance(n, ast.ClassDef) and n.name.endswith("Bridge")]:
        for b in cls.body:
            if isinstance(b, ast.Assign) and isinstance(b.value, ast.Call) and ast.unparse(b.value.func) == "Signal":
                declarados += [(cls.name, t.id) for t in b.targets]
    todo_codigo = "\n".join(_src(f"{m}.py") for m in _all_modules())
    sem_connect = [f"{c}.{s}" for c, s in declarados if not re.search(rf"\.{s}\s*\.\s*connect\s*\(", todo_codigo)]
    assert not sem_connect, f"sinais sem connect(): {sem_connect}"


def test_p1_03_motor_pede_encadeamento_so_no_fim_natural():  # [VERDE]
    be, chain = MockInputBackend(), []
    eng = ExecutionEngine(be)
    eng.on_chain_requested.append(chain.append)
    ok, errors = _run_to_end(eng, AutomationMap(name="A", repeat_count=1, next_map="B", commands=[_key("A", 0.0, 0.05)]))
    assert ok and not errors
    time.sleep(0.1)
    assert chain == ["B"]
    chain.clear()
    eng.run(AutomationMap(name="A2", repeat_count=-1, next_map="B", commands=[_key("A", 0.0, 0.05)]))
    time.sleep(0.2)
    eng.stop(wait=True)
    time.sleep(0.1)
    assert chain == [], "parada manual não deve encadear o próximo mapa"


# =========================================================================== 1.4 nomes inexistentes
def _globais_nao_resolvidos() -> list[str]:
    achados = []
    for nome in _all_modules():
        caminho = PKG / f"{nome}.py"
        mod = importlib.import_module(f"automationstudio.{nome}")
        ns = set(vars(mod))
        topo = symtable.symtable(caminho.read_text(encoding="utf-8"), str(caminho), "exec")

        def percorre(t):
            yield t
            for filho in t.get_children():
                yield from percorre(filho)

        declarados = {s.get_name() for t in percorre(topo) for s in t.get_symbols() if s.is_declared_global() and s.is_assigned()}
        for t in percorre(topo):
            if t.get_type() == "module":
                continue
            for s in t.get_symbols():
                n = s.get_name()
                if s.is_global() and s.is_referenced() and not s.is_assigned():
                    if n not in ns and n not in set(dir(builtins)) and n not in declarados:
                        achados.append(f"{nome}.{t.get_name()}(L{t.get_lineno()}) usa '{n}' inexistente")
    return achados


def test_p1_04_nenhum_nome_global_indefinido_no_pacote():  # [VERMELHO]
    """Pega KeyCode e _MOUSE_BUTTONS (backend pynput) e shutil (editor de comandos)."""
    achados = _globais_nao_resolvidos()
    assert not achados, "\n".join(achados)


def _chamadas_self_inexistentes() -> list[str]:
    classes = {}
    for nome in _all_modules():
        for n in ast.walk(_tree(f"{nome}.py")):
            if isinstance(n, ast.ClassDef):
                membros = set()
                for b in n.body:
                    if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        membros.add(b.name)
                    elif isinstance(b, ast.Assign):
                        membros |= {x.id for t in b.targets for x in ast.walk(t) if isinstance(x, ast.Name)}
                    elif isinstance(b, ast.AnnAssign) and isinstance(b.target, ast.Name):
                        membros.add(b.target.id)
                for x in ast.walk(n):
                    if isinstance(x, ast.Attribute) and isinstance(x.value, ast.Name) and x.value.id == "self" and isinstance(x.ctx, ast.Store):
                        membros.add(x.attr)
                classes[n.name] = (nome, n, membros, [ast.unparse(b) for b in n.bases])

    def todos(nome, visto=None):
        visto = visto or set()
        if nome in visto or nome not in classes:
            return set()
        visto.add(nome)
        out = set(classes[nome][2])
        for b in classes[nome][3]:
            out |= todos(b, visto)
        return out

    achados = []
    for nome_cls, (mod, no, _m, _b) in classes.items():
        definidos = todos(nome_cls)
        for x in ast.walk(no):
            if isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute) and isinstance(x.func.value, ast.Name) and x.func.value.id == "self":
                a = x.func.attr
                if ("_" in a.strip("_") or a.startswith("_")) and not a.startswith("__") and a not in definidos:
                    achados.append(f"{mod}.{nome_cls} chama self.{a}() (L{x.lineno}) mas o método não existe")
    return achados


def test_p1_04_toda_chamada_self_metodo_resolve_para_um_metodo_existente():  # [VERMELHO]
    """Pega CommandDialog._update_condition_preview (miniatura da condição de imagem)."""
    achados = _chamadas_self_inexistentes()
    assert not achados, "\n".join(achados)


# =========================================================================== 1.5 constantes de runtime
_CONSTANTES_RUNTIME = {"TEXT_CHAR_INTERVAL", "APP_STABLE_DEFAULT_MS", "APP_AFTER_OPEN_DEFAULT"}


def test_p1_05_constantes_de_runtime_tem_fonte_unica_no_core():  # [VERMELHO]
    """`global X` em outro módulo só rebinda a cópia local; o motor continua lendo o valor antigo."""
    ofensas = []
    for nome in _all_modules():
        if nome == "core":
            continue
        for n in ast.walk(_tree(f"{nome}.py")):
            if isinstance(n, ast.Global):
                ofensas += [f"{nome}.py:{n.lineno} 'global {x}'" for x in n.names if x in _CONSTANTES_RUNTIME]
            elif isinstance(n, ast.Name) and n.id in _CONSTANTES_RUNTIME and isinstance(n.ctx, ast.Load):
                ofensas.append(f"{nome}.py:{n.lineno} lê a cópia local de {n.id} (use core.{n.id})")
    assert not ofensas, "\n".join(ofensas[:12])


# =========================================================================== 1.6 parada durante TEXT
class _DigitacaoLenta(MockInputBackend):
    """Backend cujo type_text não consulta o 'stop' — como os backends reais (loop interno + sleep)."""

    def __init__(self) -> None:
        super().__init__()
        self.digitados = 0

    def type_text(self, text: str) -> None:
        for _ in text:
            self.digitados += 1
            time.sleep(0.02)


def test_p1_06_parada_de_emergencia_interrompe_digitacao_e_nao_trava_o_chamador():  # [VERMELHO]
    be = _DigitacaoLenta()
    eng = ExecutionEngine(be)
    eng.run(AutomationMap(name="P1-06", repeat_count=1, commands=[Command(type=InputType.TEXT, text="x" * 300, duration=6.0)]))
    time.sleep(0.3)
    t0 = time.monotonic()
    eng.emergency_stop()
    bloqueou = time.monotonic() - t0
    ao_retornar = be.digitados
    time.sleep(0.4)
    assert bloqueou < 1.5, f"emergency_stop() bloqueou {bloqueou:.1f}s (join fixo de 5 s na thread da GUI)"
    assert be.digitados == ao_retornar, "o texto continuou sendo digitado depois da parada"


def test_p1_06_parada_libera_teclas_presas():  # [VERDE]
    be = MockInputBackend()
    eng = ExecutionEngine(be)
    eng.run(AutomationMap(name="P1-06b", repeat_count=1, commands=[_key("A", 0.0, 3.0)]))
    time.sleep(0.2)
    eng.emergency_stop()
    assert ("key_down", "A") in [(e[1], e[2]) for e in be.events]
    assert ("key_up", "A") in [(e[1], e[2]) for e in be.events]
    assert eng.state.state == State.IDLE


# =========================================================================== 1.7 pausa x barreira
def test_p1_07_pausa_durante_barreira_de_imagem_nao_envia_input():  # [VERMELHO]
    liberar, original, eng = threading.Event(), input_system.wait_for_image, None

    def espera_falsa(path, **kw):  # a real também ignora a pausa
        liberar.wait(5)
        return types.SimpleNamespace(found=True, similarity=1.0, elapsed=0.0)

    input_system.wait_for_image = espera_falsa
    try:
        cond = WaitCondition(type=WaitConditionType.IMAGE, timeout=5, parameters={"image_path": "x.png"})
        be = MockInputBackend()
        eng = ExecutionEngine(be)
        eng.run(AutomationMap(name="P1-07", repeat_count=1, commands=[_key("A", 0.0, 0.05, conditions=[cond])]))
        time.sleep(0.15)
        eng.pause()
        assert eng.state.state == State.PAUSED
        liberar.set()
        time.sleep(0.3)
        enviados = [e for e in be.events if e[1] == "key_down"]
        assert not enviados, f"input enviado com o motor PAUSADO: {enviados}"
        eng.resume()
        time.sleep(0.5)
        assert any(e[1] == "key_down" for e in be.events), "deveria executar após retomar"
    finally:
        input_system.wait_for_image = original
        liberar.set()
        if eng is not None:
            eng.emergency_stop()


# =========================================================================== 1.8 barreira x relógio
def test_p1_08_barreira_desloca_o_relogio_e_preserva_a_duracao_do_comando():  # [VERMELHO]
    espera = WaitCondition(type=WaitConditionType.DELAY, timeout=0.4)
    cmds = [_key("A", 0.0, 0.2), _key("B", 0.5, 0.2, conditions=[espera]), _key("C", 1.0, 0.2)]
    be = MockInputBackend()
    ok, errors = _run_to_end(ExecutionEngine(be), AutomationMap(name="P1-08", repeat_count=1, commands=cmds))
    assert ok and not errors
    t = {(e[1], e[2]): e[0] for e in be.events}
    seguro_b = t[("key_up", "B")] - t[("key_down", "B")]
    lacuna_bc = t[("key_down", "C")] - t[("key_up", "B")]
    assert abs(seguro_b - 0.2) < 0.08, f"B ficou pressionada {seguro_b:.3f}s (planejado 0.200s)"
    assert abs(lacuna_bc - 0.3) < 0.08, f"C começou {lacuna_bc:.3f}s após B (planejado 0.300s)"


# =========================================================================== 1.9 instância única
def test_p1_09_main_aplica_a_protecao_de_instancia_unica():  # [VERMELHO]
    main = next(n for n in _tree("app.py").body if isinstance(n, ast.FunctionDef) and n.name == "main")
    chamadas = [n for n in ast.walk(main) if isinstance(n, ast.Call) and ast.unparse(n.func).endswith("_acquire_single_instance")]
    assert chamadas, "_acquire_single_instance() existe em app.py mas main() nunca o chama"


# =========================================================================== 1.10 ALTGR no backend Win32
def _vk_win32() -> set[str]:
    init = next(n for c in _tree("input_system.py").body if isinstance(c, ast.ClassDef) and c.name == "Win32InputBackend"
                for n in c.body if isinstance(n, ast.FunctionDef) and n.name == "__init__")
    ns, chaves = {"chr": chr, "ord": ord, "range": range, "str": str, "dict": dict}, set()

    def chaves_de(expr):
        if isinstance(expr, ast.Dict):
            for k in expr.keys:
                try:
                    chaves.add(str(ast.literal_eval(k)).upper())
                except Exception:
                    pass
        else:
            try:
                chaves.update(str(k).upper() for k in eval(ast.unparse(expr), ns))
            except Exception:
                pass

    for no in ast.walk(init):
        if isinstance(no, ast.Assign):
            for t in no.targets:
                if isinstance(t, ast.Attribute) and t.attr == "_vk":
                    chaves_de(no.value)
                elif isinstance(t, ast.Subscript) and isinstance(t.value, ast.Attribute) and t.value.attr == "_vk":
                    try:
                        chaves.add(str(eval(ast.unparse(t.slice), ns)).upper())
                    except Exception:
                        pass
        elif isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute) and no.func.attr == "update" \
                and isinstance(no.func.value, ast.Attribute) and no.func.value.attr == "_vk" and no.args:
            chaves_de(no.args[0])
    return chaves


def test_p1_10_teclas_que_o_gravador_e_o_editor_oferecem_sao_enviaveis_no_win32():  # [VERMELHO]
    from automationstudio import command_editor
    vk = _vk_win32()
    assert len(vk) > 40, "não consegui ler a tabela _vk do backend Win32 (estrutura mudou?)"
    oferecidas = set(map(str.upper, command_editor.CommandDialog._key_options())) | {v.upper() for v in core._SPECIAL_KEY_NAMES.values()}
    faltando = sorted(k for k in oferecidas if k not in vk and k != "FN" and len(k) != 1)
    assert not faltando, f"nomes sem VK no backend Win32 (key_down levanta ValueError): {faltando}"


# =========================================================================== 1.11 botões laterais
class _Botao:
    def __init__(self, name: str) -> None:
        self.name = name


def test_p1_11_mesmo_evento_fisico_tem_o_mesmo_nome_em_todos_os_consumidores():  # [VERMELHO]
    mon = GlobalInputMonitor()
    mon._keyboard_listener = object()  # finge listener ativo: não inicia hook global real
    visual = []
    mon.on_mouse_button.append(lambda nome, pressionado: visual.append(nome))
    rec = Recorder(mon, StateManager(), clock=lambda: 0.0)
    disparados = []
    hk = GlobalHotkeyManager(mon)
    for token in ("MOUSE_X1", "MOUSE_X2"):
        hk.register(token, lambda t=token: disparados.append(t))
    hk.start()
    rec.start()
    mon._emit_click(0, 0, _Botao("x1"), True)
    mon._emit_click(0, 0, _Botao("x1"), False)
    comandos = rec.stop()
    assert visual and comandos and disparados
    nome_visual, nome_gravado = visual[0], comandos[0].target
    assert nome_visual == nome_gravado == disparados[0].replace("MOUSE_", "").lower(), (
        f"visualizador='{nome_visual}', gravador='{nome_gravado}', atalho='{disparados[0]}'")


# =========================================================================== 1.12 código duplicado/morto
def test_p1_12_nenhuma_classe_define_o_mesmo_metodo_duas_vezes():  # [VERMELHO]
    achados = []
    for nome in _all_modules():
        for cls in [n for n in ast.walk(_tree(f"{nome}.py")) if isinstance(n, ast.ClassDef)]:
            vistos = collections.defaultdict(list)
            for b in cls.body:
                if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if any(any(s in ast.unparse(d) for s in (".setter", ".getter", ".deleter", "overload")) for d in b.decorator_list):
                        continue
                    vistos[b.name].append(b.lineno)
            achados += [f"{nome}.{cls.name}.{m} definido em {ls}" for m, ls in vistos.items() if len(ls) > 1]
    assert not achados, "\n".join(achados)


# =========================================================================== 1.13 log de início
def test_p1_13_log_de_inicio_nao_grava_barra_n_literal():  # [VERMELHO]
    ruins = [n.lineno for n in ast.walk(_tree("app.py")) if isinstance(n, ast.Constant) and isinstance(n.value, str) and "\\n" in n.value]
    assert not ruins, f"app.py grava '\\n' literal (backslash+n) no log nas linhas {sorted(set(ruins))}"


# =========================================================================== 1.14 SQLite
def test_p1_14_conexoes_sqlite_sao_fechadas_explicitamente(tmp_path):  # [VERMELHO]
    abertas, real = [], sqlite3.connect

    def espiao(*a, **k):
        con = real(*a, **k)
        abertas.append(con)
        return con

    sqlite3.connect = espiao
    try:
        pm, st = project.ProjectManager(tmp_path), project.AppSettings(tmp_path)
        pm.save_map(AutomationMap(name="x", commands=[_key("A", 0.0, 0.1)]))
        st.set_visual_settings({"a": 1})
        pm.load_all()
        pm.delete_map("x")
    finally:
        sqlite3.connect = real

    def fechada(con) -> bool:
        try:
            con.execute("select 1")
            return False
        except sqlite3.ProgrammingError:
            return True

    assert abertas, "o espião não viu nenhuma conexão"
    abertas_ainda = sum(1 for c in abertas if not fechada(c))
    assert abertas_ainda == 0, f"{abertas_ainda} de {len(abertas)} conexões ficaram abertas até o coletor de lixo"


# =========================================================================== 1.15 amostragem do mouse
def test_p1_15_gravador_respeita_o_intervalo_de_amostragem_do_mouse():  # [VERMELHO] [DECISÃO]
    mon = GlobalInputMonitor()
    mon._keyboard_listener = object()
    relogio = [0.0]
    rec = Recorder(mon, StateManager(), RecorderFilters(mouse_jitter_px=3, mouse_sample_interval_ms=100), clock=lambda: relogio[0])
    rec.start()
    for i, x in enumerate([0, 50, 100, 150, 200]):
        relogio[0] = i * 0.001  # 1 ms entre amostras, bem abaixo dos 100 ms configurados
        for cb in list(mon.on_mouse_move):
            cb(x, 0)
    pontos = len(rec._active_mouse_move["points"])
    rec.cancel()
    assert pontos <= 2, f"{pontos} pontos gravados com amostras a cada 1 ms e intervalo configurado de 100 ms"


# =========================================================================== 1.16 estado inválido na UI
def test_p1_16_chamadas_engine_run_da_janela_tratam_transicao_de_estado_invalida():  # [VERMELHO]
    arvore = _tree("main_window.py")
    pai = {filho: no for no in ast.walk(arvore) for filho in ast.iter_child_nodes(no)}
    aceitos = {"Exception", "BaseException", "RuntimeError", "InvalidStateTransition"}
    ruins = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Call) and ast.unparse(no.func).endswith("engine.run"):
            atual, tratado = no, False
            while atual in pai:
                anterior, atual = atual, pai[atual]
                if isinstance(atual, ast.Try) and anterior in atual.body:
                    for h in atual.handlers:
                        nomes = {ast.unparse(e) for e in (h.type.elts if isinstance(h.type, ast.Tuple) else [h.type])} if h.type else {"Exception"}
                        tratado = tratado or bool(nomes & aceitos)
                    break
            if not tratado:
                ruins.append(no.lineno)
    assert not ruins, f"engine.run() só captura ValueError nas linhas {ruins}; InvalidStateTransition (RuntimeError) escapa para o excepthook"


# =========================================================================== regressão geral
def test_roundtrip_completo_de_comando_e_mapa():  # [VERDE]
    from automationstudio.core import CommandGroup
    cond = WaitCondition(type=WaitConditionType.IMAGE, timeout=4, parameters={
        "image_path": "a.png", "confidence": 0.9, "interval": 0.3, "region": {"x": 1, "y": 2, "w": 3, "h": 4}, "search": True})
    c = Command(type=InputType.MOUSE_MOVE, text="t", action=ActionType.PRESS_AND_RELEASE, start=1.5, duration=2.0, delay=0.3,
                description="d", x=10, y=20, relative=True, mouse_path=[{"t": 0.0, "x": 1, "y": 2}, {"t": 1.0, "x": 3, "y": 4}],
                merged_move=True, scroll_dx=1, scroll_dy=-2, group="G", group_id="grp_1", enabled=False, wait_process="a.exe",
                wait_timeout=3.0, wait_stable_ms=700, wait_after_open=0.2, conditions=[cond])
    m = AutomationMap(name="RT", description="x", hotkey="F6", repeat_count=3, repeat_interval=0.5, speed=1.5, conflict_behavior="block",
                      next_map="Outro", commands=[c], groups={"grp_1": CommandGroup(id="grp_1", name="G", color="#123456")})
    assert map_from_json(map_to_json(m)).to_dict() == m.to_dict()


# =========================================================================== acrescentados na implementação (25.4)
def test_p1_01_texto_e_abrir_app_continuam_validos():  # [VERDE]
    assert Command(type=InputType.TEXT, text="olá", duration=0.0).validate() == []
    assert Command(type=InputType.APP_OPEN, target="notepad.exe").validate() == []


def test_p1_02_contador_de_ids_ignora_ids_nao_numericos_e_avanca_alem_do_maior():  # [VERMELHO]
    core._sync_id_counter(["abrir-bloco", None, "", "cmd_000900", "grp_000950"])
    assert int(core._next_id().split("_")[1]) > 950


def test_p1_04_backend_pynput_traduz_teclas_e_botoes_e_recusa_o_desconhecido():  # [VERMELHO]
    class _Key:  # imita pynput.keyboard.Key
        enter = "<enter>"
        alt_gr = "<alt_gr>"
        f5 = "<f5>"

    class _KeyCode:
        @staticmethod
        def from_char(char):
            return f"<char {char}>"

    class _Button:  # sem x1/x2, como em plataformas que não têm botões laterais
        left = "<left>"

    nomes = ("Key", "KeyCode", "Button")
    salvo = {n: getattr(input_system, n, None) for n in nomes}
    try:
        input_system.Key, input_system.KeyCode, input_system.Button = _Key, _KeyCode, _Button
        assert input_system._resolve_key("A") == "<char A>"
        assert input_system._resolve_key("ENTER") == "<enter>"
        assert input_system._resolve_key("ALTGR") == "<alt_gr>"
        assert input_system._resolve_key("F5") == "<f5>"
        assert input_system._resolve_mouse_button("left") == "<left>"
        with pytest.raises(ValueError):
            input_system._resolve_key("TECLA_INEXISTENTE")
        for nome in ("x1", "botao_inexistente", ""):
            with pytest.raises(ValueError):  # nunca vira clique esquerdo em silêncio
                input_system._resolve_mouse_button(nome)
    finally:
        for nome, valor in salvo.items():
            setattr(input_system, nome, valor)


def test_p1_05_set_runtime_defaults_chega_ao_calculo_e_a_digitacao():  # [VERMELHO]
    original = (core.TEXT_CHAR_INTERVAL, core.APP_STABLE_DEFAULT_MS, core.APP_AFTER_OPEN_DEFAULT)

    class _Teclado:
        def __init__(self):
            self.digitados = []

        def type(self, char):
            self.digitados.append(char)

        def press(self, *args):
            pass

        def release(self, *args):
            pass

    class _Mouse:
        position = (0, 0)

        def press(self, *args):
            pass

        def release(self, *args):
            pass

        def move(self, *args):
            pass

    pausas = []
    nomes = ("_PYNPUT_AVAILABLE", "KeyboardController", "MouseController", "time")
    salvo = {n: getattr(input_system, n, None) for n in nomes}
    try:
        core.set_runtime_defaults(text_char_interval=0.05)
        assert abs(core.calculate_text_duration("0123456789") - 0.5) < 1e-9
        input_system._PYNPUT_AVAILABLE = True
        input_system.KeyboardController = _Teclado
        input_system.MouseController = _Mouse
        input_system.time = types.SimpleNamespace(sleep=pausas.append, monotonic=time.monotonic)
        input_system.PynputInputBackend().type_text("abc")
        assert pausas == [0.05, 0.05, 0.05]
    finally:
        for nome, valor in salvo.items():
            setattr(input_system, nome, valor)
        core.set_runtime_defaults(*original)


def test_p1_17_registro_invalido_nao_some_em_silencio(tmp_path):  # [VERMELHO]
    pm = project.ProjectManager(tmp_path)
    pm.save_map(AutomationMap(name="Bom", commands=[_key("A", 0.0, 0.1)]))
    ruim = json.dumps({"format_version": 1, "map": {"name": "Ruim", "commands": [
        {"id": "cmd_000001", "type": "key", "target": "A", "duration": 0.1, "start": None}]}})
    con = sqlite3.connect(str(tmp_path / "AutomationStudio.db"))
    try:
        with con:
            con.execute("INSERT INTO maps(name, payload) VALUES(?, ?)", ("Ruim", ruim))
    finally:
        con.close()
    pm2 = project.ProjectManager(tmp_path)
    assert [m.name for m in pm2.load_all()] == ["Bom"]
    assert len(pm2.load_errors) == 1 and pm2.load_errors[0].startswith("Ruim:"), pm2.load_errors
    con = sqlite3.connect(str(tmp_path / "AutomationStudio.db"))
    try:  # nada é apagado: o registro continua no banco
        assert con.execute("SELECT COUNT(*) FROM maps WHERE name='Ruim'").fetchone()[0] == 1
    finally:
        con.close()


def test_versao_unica_entre_codigo_readme_e_titulo():  # [VERMELHO]
    import automationstudio
    assert automationstudio.__version__ == core.APP_VERSION
    assert core.APP_VERSION in (ROOT / "README.md").read_text(encoding="utf-8")
    assert not re.search(r"AS \d+\.\d+", _src("main_window.py")), "o título da janela não pode ter a versão escrita à mão"


def test_python_do_projeto_e_definido_em_um_unico_arquivo():  # [VERMELHO]
    assert (ROOT / "python_version.txt").read_text(encoding="utf-8").strip() == "3.14"
    for bat in sorted(ROOT.glob("*.bat")):
        texto = bat.read_text(encoding="utf-8")
        assert not re.search(r"\bpyw?\.exe\s+-3\b", texto), f"{bat.name} escolhe 'py -3' em vez da versão de python_version.txt"


def test_scripts_bat_usam_fim_de_linha_do_windows():  # [VERMELHO]
    for bat in sorted(ROOT.glob("*.bat")):
        dados = bat.read_bytes()
        assert dados.count(b"\n") == dados.count(b"\r\n"), f"{bat.name} tem fim de linha LF; o cmd.exe pode falhar em 'goto' e rótulos"
