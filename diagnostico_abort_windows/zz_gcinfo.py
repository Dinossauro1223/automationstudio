"""Sonda de diagnóstico (TEMPORÁRIA, ramo zz-diag): registra em logs/diag_gcinfo.txt cada coleta de lixo do Python (a
geração, o teste em andamento e quais objetos do Qt estão na geração coletada), para saber o que o GC estava coletando
quando o processo aborta. Grava e dá flush a cada linha: sobrevive ao abort."""
import collections
import gc
import os
import sys

_ARQ = os.path.join("logs", "diag_gcinfo.txt")
_estado = {"n": 0}


def _reg(texto):
    with open(_ARQ, "a", encoding="utf-8") as f:
        f.write(texto + "\n")
        f.flush()


def _qt_na_geracao(geracao):
    qtcore = sys.modules.get("PySide6.QtCore")
    if qtcore is None:
        return ""
    qobject = qtcore.QObject
    contagem = collections.Counter()
    try:
        objetos = gc.get_objects(geracao)
    except Exception as exc:  # noqa: BLE001
        return f"(get_objects falhou: {exc!r})"
    for obj in objetos:
        try:
            if isinstance(obj, qobject):
                contagem[type(obj).__name__] += 1
        except Exception:  # noqa: BLE001
            pass
    del objetos
    return ", ".join(f"{k}={v}" for k, v in contagem.most_common(8))


def _callback(fase, info):
    if fase == "start":
        _estado["n"] += 1
        atual = os.environ.get("PYTEST_CURRENT_TEST", "-")[-110:]
        geracao = info.get("generation", -1)
        qt = _qt_na_geracao(geracao) if "gui" in atual else ""
        _reg(f"#{_estado['n']} START gen={geracao} contagem={gc.get_count()} teste={atual} qt=[{qt}]")
    else:
        _reg(f"#{_estado['n']} STOP  gen={info.get('generation', -1)} coletados={info.get('collected')} incoletaveis={info.get('uncollectable')}")


def pytest_configure(config):
    os.makedirs("logs", exist_ok=True)
    gc.callbacks.append(_callback)
