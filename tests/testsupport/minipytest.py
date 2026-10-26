"""Substituto mínimo de `pytest`, só para o executor sem dependências (run_minimal.py).

Subconjunto PORTÁTIL suportado (o que os testes do projeto usam):
  funções test_*; fixtures de função/sessão (@pytest.fixture, autouse, yield); tmp_path e monkeypatch;
  marcadores skip, skipif, xfail, parametrize e marcadores livres (slow, gui, windows_only, hardware);
  pytest.raises, pytest.approx, pytest.skip, pytest.importorskip.
Com o pytest real instalado este módulo não é usado.
"""
from __future__ import annotations

import importlib


class Skipped(Exception):
    pass


def skip(reason: str = "") -> None:
    raise Skipped(reason)


def importorskip(name: str, reason: str | None = None):
    try:
        return importlib.import_module(name)
    except ImportError:
        raise Skipped(reason or f"módulo {name} indisponível") from None


def fail(reason: str = "") -> None:
    raise AssertionError(reason)


class MarkDecorator:
    """Aceita @pytest.mark.x, @pytest.mark.x(...) e `pytestmark = pytest.mark.x`, como o pytest real."""

    def __init__(self, name: str, args: tuple = (), kwargs: dict | None = None) -> None:
        self.name, self.args, self.kwargs = name, args, kwargs or {}

    def __call__(self, *args, **kwargs):
        if len(args) == 1 and callable(args[0]) and not kwargs:
            fn = args[0]  # aplicação do marcador à função: @pytest.mark.slow  ou  @pytest.mark.xfail(strict=True)
            fn.__dict__.setdefault("__marks__", []).append((self.name, self.args, self.kwargs))
            return fn
        return MarkDecorator(self.name, args, kwargs)


class _Mark:
    def __getattr__(self, name: str) -> MarkDecorator:
        return MarkDecorator(name)


mark = _Mark()


def fixture(*args, **kwargs):
    def decorate(fn):
        fn.__fixture_meta__ = {"autouse": bool(kwargs.get("autouse", False)), "scope": kwargs.get("scope", "function")}
        return fn
    if args and callable(args[0]) and not kwargs:
        return decorate(args[0])
    return decorate


class raises:
    """`with pytest.raises(E, match=...) as info:` -> info.value, info.type e info.match(padrão), como no pytest."""

    def __init__(self, expected, match: str | None = None):
        self.expected, self.match_pattern = expected, match
        self.value = None
        self.type = None

    def __enter__(self):
        return self

    def match(self, pattern: str) -> bool:
        import re
        assert re.search(pattern, str(self.value)), f"mensagem {str(self.value)!r} não casa com {pattern!r}"
        return True

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            raise AssertionError(f"não levantou {self.expected}")
        if not issubclass(exc_type, self.expected):
            return False
        self.value, self.type = exc, exc_type
        if self.match_pattern is not None:
            self.match(self.match_pattern)
        return True


class approx:
    def __init__(self, expected, rel: float = 1e-6, abs: float = 1e-12):
        self.expected, self.rel, self.abs = expected, rel, abs

    def __eq__(self, other):
        if isinstance(self.expected, (list, tuple)):
            return len(other) == len(self.expected) and all(approx(e, self.rel, self.abs) == o for e, o in zip(self.expected, other))
        return abs(other - self.expected) <= max(self.rel * abs(self.expected), self.abs)

    def __repr__(self):
        return f"approx({self.expected!r})"
