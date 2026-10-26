"""Relógio virtual para os testes do motor.

O motor, o gravador e o MockInputBackend aceitam um relógio com monotonic() e sleep(). Este relógio não
espera de verdade: sleep() só avança o tempo. Um mapa de 10 s roda em milissegundos e com tempos exatos.
"""
from __future__ import annotations

import threading


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self._ns = round(float(start) * 1e9)
        self._lock = threading.Lock()
        self.sleeps: list[float] = []  # esperas pedidas, em segundos (útil para afirmar o que o motor esperou)

    def monotonic(self) -> float:
        with self._lock:
            return self._ns / 1e9

    __call__ = monotonic  # o Recorder recebe `clock=` como função sem argumentos

    def sleep(self, seconds: float) -> None:
        # Nanossegundos INTEIROS e progresso mínimo de 1 ns: com float, sleep(1e-17) não mudaria o tempo
        # e o laço do motor giraria para sempre.
        with self._lock:
            self._ns += max(1, round(float(seconds) * 1e9))
            self.sleeps.append(float(seconds))

    def advance(self, seconds: float) -> None:
        with self._lock:
            self._ns += round(float(seconds) * 1e9)
