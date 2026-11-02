"""Sonda de diagnóstico (TEMPORÁRIA): desliga a coleta automática de lixo cíclico."""
import gc


def pytest_configure(config):
    gc.disable()
