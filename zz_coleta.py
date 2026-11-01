"""Sonda de diagnóstico (TEMPORÁRIA, ramo zz-diag): desliga o GC automático e coleta o lixo só onde mandarem.
AS_DIAG_COLETA=cada               -> em CADA teste de janela
AS_DIAG_COLETA=primeiro_dialogo   -> uma vez só, no início do primeiro teste de janela de test_command_dialog.py
AS_DIAG_GERACAO=0|1|2             -> até que geração coletar (padrão 2 = tudo)
AS_DIAG_ONDE=setup|teardown       -> no início (dentro da fixture `gui`, depois do isolamento) ou no fim do teste"""
import gc
import os
import sys

_MODO = os.environ.get("AS_DIAG_COLETA", "")
_GER = int(os.environ.get("AS_DIAG_GERACAO", "2") or 2)
_ONDE = os.environ.get("AS_DIAG_ONDE", "setup")
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
    original_fim = diagnostico_qt.encerrar_atual

    def iniciar(nome, *args, **kwargs):
        quer = _ONDE == "setup" and (_MODO == "cada" or (_MODO == "primeiro_dialogo" and "test_command_dialog.py" in str(nome) and not _feito["primeiro"]))
        if quer:
            _feito["primeiro"] = True
            _reg(f"vou coletar (ger {_GER}) no início de {nome}")
            coletados = gc.collect(_GER)
            _reg(f"coletou {coletados} no início de {nome}")
        return original(nome, *args, **kwargs)

    def encerrar_atual(*args, **kwargs):
        resultado = original_fim(*args, **kwargs)
        if _ONDE == "teardown" and _MODO == "cada":
            _reg(f"vou coletar (ger {_GER}) no fim de {os.environ.get('PYTEST_CURRENT_TEST', '?')}")
            coletados = gc.collect(_GER)
            _reg(f"coletou {coletados}")
        return resultado

    diagnostico_qt.iniciar = iniciar
    diagnostico_qt.encerrar_atual = encerrar_atual
