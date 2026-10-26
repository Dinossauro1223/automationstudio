"""Dublê funcional parcial: ver _fake.py."""
from . import _fake


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    if hasattr(_fake, name) and name in _fake.__all__:
        return getattr(_fake, name)
    return _fake.placeholder(name)
