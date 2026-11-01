"""Sonda de diagnóstico (TEMPORÁRIA, ramo zz-diag): desliga o GC automático e coleta o lixo só onde mandarem.
AS_DIAG_COLETA=cada               -> no início de CADA teste de janela (dentro da fixture `gui`, depois do isolamento)
AS_DIAG_COLETA=primeiro_dialogo   -> uma vez só, no início do primeiro teste de janela de test_command_dialog.py"""
import gc
import os
import sys

_MODO = os.environ.get("AS_DIAG_COLETA", "")
_feito = {"primeiro": False}


def _reg(texto):
    with open(os.path.join("logs", "diag_coleta.txt"), "a", encoding="utf-8") as f:
        f.write(texto + "\n")
        f.flush()


def pytest_configure(config):
    os.makedirs("logs", exist_ok=True)
    gc.disable()
    if "tests" not in sys.path:
        sys.path.insert(0, "tests")
    from testsupport import diagnostico_qt
    original = diagnostico_qt.iniciar

    def iniciar(nome, *args, **kwargs):
        quer = _MODO == "cada" or (_MODO == "primeiro_dialogo" and "test_command_dialog.py" in str(nome) and not _feito["primeiro"])
        if quer:
            _feito["primeiro"] = True
            _reg(f"vou coletar no início de {nome}")
            coletados = gc.collect()
            _reg(f"coletou {coletados} no início de {nome}")
        return original(nome, *args, **kwargs)

    diagnostico_qt.iniciar = iniciar
