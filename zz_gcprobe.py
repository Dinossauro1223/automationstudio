"""Sonda de diagnóstico (TEMPORÁRIA, só no ramo de teste zz-diag): coleta o lixo depois de cada teste de janela para
descobrir de quem é o objeto que derruba o processo no Windows."""
import gc
import sys

import pytest


def _avisar(texto):
    print(texto, file=sys.__stderr__, flush=True)


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item, nextitem):
    if "gui" not in item.nodeid and "test_engine_control" not in item.nodeid:
        return
    _avisar(f"\n[gcprobe] vou coletar o lixo depois de {item.nodeid}")
    coletados = gc.collect()
    _avisar(f"[gcprobe] coletado ({coletados} objetos) depois de {item.nodeid}")
