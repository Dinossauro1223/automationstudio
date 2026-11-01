"""TEMPORÁRIO (ramo zz-diag): faz o pytest guardar a captura (stdout e stderr) em arquivos de verdade, em logs/, para que
sobrem depois de um abort do processo (o `TemporaryFile` do pytest some junto com o processo). Perturba o mínimo possível:
só troca uma função. AS_DIAG_EMPURRAO=N segura N listas vivas (desloca de N alocações o ponto em que o coletor roda)."""
import os
import sys
import tempfile

os.makedirs("logs", exist_ok=True)
with open(os.path.join("logs", "zz_pids.txt"), "a", encoding="utf-8") as _f:
    _f.write(f"{os.getpid()} {' '.join(sys.argv[:8])}\n")

_empurrao = int(os.environ.get("AS_DIAG_EMPURRAO", "0") or 0)
_SEGURAR = [[] for _ in range(_empurrao)]

_original = tempfile.TemporaryFile
_n = [0]


def _arquivo(*args, **kwargs):
    try:
        chamador = sys._getframe(1).f_globals.get("__name__", "")
    except Exception:  # noqa: BLE001
        chamador = ""
    if chamador != "_pytest.capture":
        return _original(*args, **kwargs)
    _n[0] += 1
    return open(os.path.join("logs", f"zz_captura_{os.getpid()}_{_n[0]}.txt"), "w+b", buffering=0)


tempfile.TemporaryFile = _arquivo
try:
    import _pytest.capture as _cap
    if hasattr(_cap, "TemporaryFile"):
        _cap.TemporaryFile = _arquivo
except Exception:  # noqa: BLE001
    pass
