from ._stub import _make, Signal, _Any
def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    if name == "Signal":
        return Signal
    return _make(name)
