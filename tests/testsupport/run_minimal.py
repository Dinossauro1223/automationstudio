"""Executor de testes sem dependências: alternativa ao pytest quando ele não está instalado.

    py run_minimal.py [caminhos...] [-m "not slow"] [-k texto] [-x] [-q] [--relatorio arquivo.txt]

Aceita só o subconjunto portátil descrito em minipytest.py. Se o pytest real estiver instalado,
este script simplesmente repassa os argumentos para ele (`pytest.main`).
"""
from __future__ import annotations

import argparse
import importlib
import importlib.util
import inspect
import itertools
import os
import pathlib
import re
import shutil
import sys
import tempfile
import time
import traceback

TESTS = pathlib.Path(__file__).resolve().parents[1]
ROOT = pathlib.Path(os.environ.get("AS_ROOT") or TESTS.parent)

_MISSING = object()


class MonkeyPatch:
    """Subconjunto do monkeypatch do pytest: setattr, delattr, setenv, delenv, setitem, delitem."""

    def __init__(self) -> None:
        self._undo: list[tuple] = []

    @staticmethod
    def _resolve(path: str):
        parts = path.split(".")
        obj = importlib.import_module(parts[0])
        for i, part in enumerate(parts[1:], 1):
            try:
                obj = getattr(obj, part)
            except AttributeError:
                obj = importlib.import_module(".".join(parts[: i + 1]))
        return obj

    def setattr(self, target, name, value=_MISSING, raising: bool = True) -> None:
        if value is _MISSING:  # forma "pacote.modulo.atributo", valor
            path, value = target, name
            module_path, _, name = path.rpartition(".")
            target = self._resolve(module_path)
        old = getattr(target, name, _MISSING)
        if old is _MISSING and raising:
            raise AttributeError(f"{target!r} não tem o atributo {name!r}")
        self._undo.append(("attr", target, name, old))
        setattr(target, name, value)

    def delattr(self, target, name, raising: bool = True) -> None:
        old = getattr(target, name, _MISSING)
        if old is _MISSING:
            if raising:
                raise AttributeError(name)
            return
        self._undo.append(("attr", target, name, old))
        delattr(target, name)

    def setenv(self, name: str, value: str) -> None:
        self._undo.append(("env", name, os.environ.get(name, _MISSING)))
        os.environ[name] = str(value)

    def delenv(self, name: str, raising: bool = True) -> None:
        if name not in os.environ:
            if raising:
                raise KeyError(name)
            return
        self._undo.append(("env", name, os.environ[name]))
        del os.environ[name]

    def setitem(self, mapping, key, value) -> None:
        self._undo.append(("item", mapping, key, mapping.get(key, _MISSING)))
        mapping[key] = value

    def delitem(self, mapping, key, raising: bool = True) -> None:
        if key not in mapping:
            if raising:
                raise KeyError(key)
            return
        self._undo.append(("item", mapping, key, mapping[key]))
        del mapping[key]

    def undo(self) -> None:
        for entry in reversed(self._undo):
            kind = entry[0]
            if kind == "attr":
                _, target, name, old = entry
                if old is _MISSING:
                    if hasattr(target, name):
                        delattr(target, name)
                else:
                    setattr(target, name, old)
            elif kind == "env":
                _, name, old = entry
                if old is _MISSING:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = old
            else:
                _, mapping, key, old = entry
                if old is _MISSING:
                    mapping.pop(key, None)
                else:
                    mapping[key] = old
        self._undo.clear()


def _marks_of(obj) -> list[tuple]:
    marks = list(getattr(obj, "__marks__", []))
    return marks


def _module_marks(module) -> list[tuple]:
    """Marcadores de `pytestmark = pytest.mark.x` (ou lista deles) no nível do módulo."""
    pm = getattr(module, "pytestmark", None)
    if pm is None:
        return []
    items = pm if isinstance(pm, (list, tuple)) else [pm]
    return [(i.name, i.args, i.kwargs) for i in items if hasattr(i, "name")]


def _expand_parametrize(fn):
    combos = [{}]
    labels = [""]
    for name, args, kwargs in _marks_of(fn):
        if name != "parametrize":
            continue
        argnames = args[0] if args else kwargs["argnames"]
        argvalues = args[1] if len(args) > 1 else kwargs["argvalues"]
        ids = kwargs.get("ids")
        names = [n.strip() for n in argnames.split(",")] if isinstance(argnames, str) else list(argnames)
        new_combos, new_labels = [], []
        for (combo, label), (i, value) in itertools.product(list(zip(combos, labels)), list(enumerate(argvalues))):
            values = value if len(names) > 1 else (value,)
            tag = str(ids[i]) if ids else "-".join(str(v)[:30] for v in values)
            new_combos.append({**combo, **dict(zip(names, values))})
            new_labels.append(f"{label}-{tag}" if label else tag)
        combos, labels = new_combos, new_labels
    return list(zip(combos, labels))


def _marker_names(fn, module_marks) -> set[str]:
    return {m[0] for m in _marks_of(fn) + module_marks}


def _matches_expression(expr: str, names: set[str]) -> bool:
    if not expr:
        return True
    env = {tok: (tok in names) for tok in re.findall(r"[A-Za-z_]\w*", expr) if tok not in ("and", "or", "not")}
    return bool(eval(expr, {"__builtins__": {}}, env))


class Runner:
    def __init__(self, args) -> None:
        self.args = args
        self.fixtures: dict = {}
        self.session_cache: dict = {}
        self.session_teardowns: list = []
        self.counts = dict(passou=0, falhou=0, pulado=0, xfail=0, xpass=0)
        self.lines: list[str] = []

    def out(self, text: str) -> None:
        print(text)
        self.lines.append(text)

    def load_conftest(self) -> None:
        path = TESTS / "conftest.py"
        if not path.exists():
            return
        spec = importlib.util.spec_from_file_location("conftest", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["conftest"] = module
        spec.loader.exec_module(module)
        for name, obj in vars(module).items():
            if callable(obj) and hasattr(obj, "__fixture_meta__"):
                self.fixtures[name] = obj

    def resolve(self, name: str, ctx: dict):
        cache = ctx["cache"]
        if name in cache:
            return cache[name]
        if name == "tmp_path":
            path = pathlib.Path(tempfile.mkdtemp(prefix="as_test_"))
            ctx["cleanup"].append(lambda: shutil.rmtree(path, ignore_errors=True))
            value = path
        elif name == "monkeypatch":
            value = MonkeyPatch()
            ctx["cleanup"].append(value.undo)
        elif name in self.fixtures:
            fn = self.fixtures[name]
            scope = fn.__fixture_meta__["scope"]
            if scope == "session" and name in self.session_cache:
                value = self.session_cache[name]
            else:
                kwargs = {p: self.resolve(p, ctx) for p in inspect.signature(fn).parameters}
                result = fn(**kwargs)
                if inspect.isgenerator(result):
                    value = next(result)
                    (self.session_teardowns if scope == "session" else ctx["teardowns"]).append(result)
                else:
                    value = result
                if scope == "session":
                    self.session_cache[name] = value
        else:
            raise LookupError(f"fixture '{name}' não encontrada")
        cache[name] = value
        return value

    def run_item(self, nodeid: str, fn, params: dict, module_marks: list) -> None:
        marks = _marks_of(fn) + module_marks
        for name, args, kwargs in marks:
            if name == "skip":
                return self.record("pulado", nodeid, kwargs.get("reason", args[0] if args else ""))
            if name == "skipif" and args and args[0]:
                return self.record("pulado", nodeid, kwargs.get("reason", ""))
        xfail = next(((kw.get("reason", ""), bool(kw.get("strict", False))) for n, a, kw in marks if n == "xfail" and (not a or a[0])), None)
        ctx = {"cache": dict(params), "teardowns": [], "cleanup": []}
        started = time.time()
        status, detail = "passou", ""
        os.environ["PYTEST_CURRENT_TEST"] = f"{nodeid} (call)"  # como o pytest: o vigia de testes de janela o lê
        try:
            for fname, ffn in self.fixtures.items():
                if ffn.__fixture_meta__["autouse"]:
                    self.resolve(fname, ctx)
            kwargs = {p: self.resolve(p, ctx) for p in inspect.signature(fn).parameters}
            fn(**kwargs)
        except BaseException as exc:  # noqa: BLE001
            skipped = type(exc).__name__ == "Skipped"
            if skipped:
                status, detail = "pulado", str(exc)
            else:
                status, detail = "falhou", f"{type(exc).__name__}: {str(exc).strip()[:300]}".replace("\n", " | ")
                tb = traceback.extract_tb(exc.__traceback__)
                frames = [f for f in tb if "/tests/" in f.filename.replace("\\", "/") or "automationstudio" in f.filename]
                if frames:
                    detail += f"  [{pathlib.Path(frames[-1].filename).name}:{frames[-1].lineno}]"
        finally:
            for gen in reversed(ctx["teardowns"]):
                try:
                    next(gen, None)
                except BaseException as exc:  # noqa: BLE001
                    status, detail = "falhou", f"erro no encerramento de fixture: {exc}"
            for cleanup in reversed(ctx["cleanup"]):
                cleanup()
            os.environ.pop("PYTEST_CURRENT_TEST", None)
        elapsed = time.time() - started
        if xfail and status == "falhou":
            return self.record("xfail", nodeid, f"{detail[:110]}")
        if xfail and status == "passou":
            return self.record("falhou" if xfail[1] else "xpass", nodeid, f"xfail inesperadamente passou: {xfail[0]}")
        self.record(status, nodeid, detail, elapsed)

    def record(self, status: str, nodeid: str, detail: str = "", elapsed: float = 0.0) -> None:
        self.counts[status] += 1
        label = {"passou": "PASSOU ", "falhou": "FALHOU ", "pulado": "PULADO ", "xfail": "XFAIL  ", "xpass": "XPASS  "}[status]
        if status == "passou" and self.args.q:
            return
        self.out(f"{label} {nodeid}" + (f"  ({elapsed:.2f}s)" if status == "passou" else "") + (f"\n          -> {detail}" if detail else ""))
        if status == "falhou" and self.args.x:
            self.finish(exit_now=True)

    def collect(self):
        paths = [pathlib.Path(p) for p in self.args.paths] or [TESTS]
        files = []
        for base in paths:
            base = base if base.is_absolute() else pathlib.Path.cwd() / base
            found = [base] if base.is_file() else sorted(base.rglob("test_*.py"))
            files += [f for f in found if "testsupport" not in f.parts and "__pycache__" not in f.parts]
        return files

    def run(self) -> int:
        self.load_conftest()
        for file in self.collect():
            rel = file.relative_to(TESTS).as_posix() if TESTS in file.parents else file.name
            spec = importlib.util.spec_from_file_location("t_" + re.sub(r"\W", "_", rel[:-3]), file)
            module = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
            except BaseException as exc:  # noqa: BLE001
                self.counts["falhou"] += 1
                self.out(f"FALHOU  {rel} (erro de coleta)\n          -> {type(exc).__name__}: {exc}")
                continue
            module_marks = _module_marks(module)
            for name, fn in list(vars(module).items()):  # cópia: um aviso emitido no teste cria `__warningregistry__` no módulo
                if not (name.startswith("test_") and inspect.isfunction(fn) and fn.__module__ == module.__name__):
                    continue
                if self.args.k and self.args.k not in f"{rel}::{name}":
                    continue
                if not _matches_expression(self.args.m, _marker_names(fn, module_marks)):
                    continue
                for params, label in _expand_parametrize(fn):
                    self.run_item(f"{rel}::{name}" + (f"[{label}]" if label else ""), fn, params, module_marks)
        return self.finish()

    def finish(self, exit_now: bool = False) -> int:
        for gen in reversed(self.session_teardowns):
            try:
                next(gen, None)
            except BaseException:  # noqa: BLE001
                pass
        c = self.counts
        self.out(f"\nRESUMO: {c['passou']} passou, {c['falhou']} falhou, {c['pulado']} pulado, {c['xfail']} xfail (esperado), {c['xpass']} xpass")
        if self.args.relatorio:
            pathlib.Path(self.args.relatorio).write_text("\n".join(self.lines) + "\n", encoding="utf-8")
        code = 1 if c["falhou"] else 0
        if exit_now:
            sys.exit(code)
        return code


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="*")
    parser.add_argument("-m", default="", help='expressão de marcadores, ex.: "not slow and not gui"')
    parser.add_argument("-k", default="", help="só testes cujo nome contém o texto")
    parser.add_argument("-x", action="store_true", help="parar na primeira falha")
    parser.add_argument("-q", action="store_true", help="só mostrar o que não passou")
    parser.add_argument("--relatorio", default="", help="grava a saída neste arquivo")
    args = parser.parse_args(argv)

    for path in (str(ROOT), str(TESTS)):
        if path not in sys.path:
            sys.path.insert(0, path)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if importlib.util.find_spec("pytest") is not None and not os.environ.get("AS_FORCE_MINIMAL_RUNNER"):
        import pytest
        extra = (["-m", args.m] if args.m else []) + (["-k", args.k] if args.k else []) + (["-x"] if args.x else []) + (["-q"] if args.q else [])
        return pytest.main(extra + (args.paths or [str(TESTS)]))
    sys.modules.setdefault("pytest", importlib.import_module("testsupport.minipytest"))
    return Runner(args).run()


if __name__ == "__main__":
    sys.exit(main())
