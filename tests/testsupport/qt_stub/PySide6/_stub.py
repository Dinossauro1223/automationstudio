"""Stub mínimo de PySide6 — SOMENTE para importar módulos neste sandbox (sem GUI real)."""
class _Meta(type):
    def __getattr__(cls, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _make(name)
    def __or__(cls, other): return cls
    def __ror__(cls, other): return cls
    def __and__(cls, other): return cls
    def __rand__(cls, other): return cls
    def __invert__(cls): return cls

class _Any(metaclass=_Meta):
    def __init__(self, *a, **k): pass
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _Any()
    def __call__(self, *a, **k):
        # permite uso como decorator (@Slot(...)) devolvendo a própria função
        if len(a) == 1 and callable(a[0]) and not k:
            return a[0]
        return _Any()
    def __or__(self, o): return self
    __ror__ = __and__ = __rand__ = __or__
    def __iter__(self): return iter(())
    def __int__(self): return 0
    def __index__(self): return 0
    def __float__(self): return 0.0
    def __bool__(self): return True

_cache = {}
def _make(name):
    if name not in _cache:
        _cache[name] = _Meta(name, (_Any,), {})
    return _cache[name]

class Signal:
    def __init__(self, *a, **k): pass
    def connect(self, *a, **k): pass
    def emit(self, *a, **k): pass
    def disconnect(self, *a, **k): pass
