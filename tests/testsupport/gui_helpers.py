"""Auxiliares dos testes de janela. Funcionam com o PySide6 real e com o dublê (testsupport/qt_double)."""
from __future__ import annotations

import gc
import struct
import sys
import time
import zlib

_QAPP = None  # a QApplication precisa viver tanto quanto o processo: o Python é o dono do objeto


def ensure_qapp():
    """Garante a QApplication (uma por processo) quando o Qt é o real; devolve None com o dublê, o stub ou sem PySide6.

    Só olha `sys.modules`: quem ainda não importou o Qt não paga nada. O Qt real ABORTA O PROCESSO se um widget for criado
    sem aplicação, e isso derrubaria uma rodada inteira por causa de UM teste rodado fora da ordem (por exemplo com -k).
    """
    global _QAPP
    pyside, widgets = sys.modules.get("PySide6"), sys.modules.get("PySide6.QtWidgets")
    if pyside is None or widgets is None or getattr(pyside, "__as_stub__", False):
        return None
    if _QAPP is None:
        _QAPP = widgets.QApplication.instance() or widgets.QApplication([])
    return _QAPP

DELETE_LATER = 52   # QEvent::DeferredDelete (o valor é estável desde o Qt 4)


def processar_eventos(ms: int = 0, *, app=None, relogio=time.monotonic, dormir=time.sleep, passadas_minimas: int = 2,
                      marcar=None) -> int:
    """Processa os eventos pendentes por, no mínimo, `ms` milissegundos e no mínimo `passadas_minimas` passadas. Devolve
    o número de passadas.

    Existe no lugar de `QApplication.processEvents()` solto nos testes por três motivos: (1) uma passada só não basta
    (um evento trata e posta outro; o primeiro `processEvents` de uma janela recém-mostrada deixa o layout pela metade);
    (2) o laço termina por TEMPO, então um evento que se reativa sem parar não prende o teste; (3) cada passada vira um
    marco no anel de eventos do diagnóstico (testsupport/diagnostico_qt.py), que separa o que aconteceu em cada uma.
    Uma chamada nativa que NÃO volta, esta função não resolve: quem resolve é o vigia do diagnóstico."""
    app = app if app is not None else ensure_qapp()
    if app is None:
        return 0
    if marcar is None:
        from testsupport import diagnostico_qt
        marcar = diagnostico_qt.marcar
    fim = relogio() + ms / 1000.0
    passadas = 0
    while True:
        marcar(f"processEvents, passada {passadas + 1}")
        app.processEvents()
        passadas += 1
        if passadas >= passadas_minimas and relogio() >= fim:
            return passadas
        if relogio() < fim:
            dormir(0.002)


def esvaziar_fila(app=None, *, enviar_exclusoes=None, relogio=time.monotonic, dormir=time.sleep) -> None:
    """Esvazia a fila de eventos: processa, executa os `deleteLater()` pendentes e processa de novo.

    Pela documentação do Qt, um `processEvents()` chamado fora de um laço de eventos NÃO executa os `deleteLater()`
    pendentes (a alternativa documentada é `sendPostedEvents()`). Sem isto, as janelas dos testes anteriores ficam vivas
    e o que deixaram na fila (temporizadores de intervalo zero, animações, sinais enfileirados) é processado de uma só vez
    no primeiro `processEvents()` do teste SEGUINTE. Na rodada de 18/10/2026 os 21 primeiros testes da janela nunca
    processaram eventos e o 22º travou no primeiro `processEvents()`; que o acúmulo seja a causa é só uma HIPÓTESE
    (a causa não foi confirmada): esta limpeza elimina a possibilidade e é a higiene de qualquer suíte de Qt."""
    app = app if app is not None else ensure_qapp()
    if app is None:
        return
    processar_eventos(0, app=app, relogio=relogio, dormir=dormir)
    if enviar_exclusoes is None:
        def enviar_exclusoes():
            qtcore = sys.modules["PySide6.QtCore"]
            qtcore.QCoreApplication.sendPostedEvents(None, DELETE_LATER)
    try:
        enviar_exclusoes()
    except Exception:  # noqa: BLE001  (higiene: se esta versão do Qt recusar, os testes seguem como antes)
        pass
    processar_eventos(0, app=app, relogio=relogio, dormir=dormir)


def descartar_janelas(janelas: list, *, app=None, coletar=gc.collect, **opcoes) -> None:
    """Fim de um teste que abriu janelas principais: para o relógio da interface e o motor, fecha, manda destruir,
    esvazia a fila de eventos e deixa o coletor de lixo do Python soltar o que sobrou, AGORA (e não no meio do próximo
    teste: as janelas formam ciclos de referência por causa dos lambdas ligados a sinais)."""
    for janela in janelas:
        janela._ui_refresh_timer.stop()
        janela.engine.emergency_stop()
        janela.close()
    for janela in janelas:
        janela.deleteLater()
    janelas.clear()
    esvaziar_fila(app, **opcoes)
    coletar()


# Campos que o editor recalcula de propósito e que, por isso, não entram na comparação "abrir e salvar não altera":
#  - delay_suggested: o editor grava o mesmo valor do atraso (to_dict já devolve o atraso quando ele é 0);
#  - wait_min_ram_mb: campo legado, o editor sempre grava 0.0 e a execução o ignora.
CAMPOS_RECALCULADOS = ("delay_suggested", "wait_min_ram_mb")

# Os campos numéricos passam por caixas de número com 3 casas decimais: 0,7041708999995535 vira 0,704.
TOLERANCIA_DO_EDITOR = 5e-4


def write_png(path, width: int = 8, height: int = 6, rgb: tuple[int, int, int] = (200, 30, 30)) -> str:
    """Grava um PNG válido (RGB 8 bits) sem depender de Qt nem de Pillow. Devolve o caminho como texto."""
    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    row = b"\x00" + bytes(rgb) * width  # filtro 0 + pixels
    pixels = zlib.compress(row * height)
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", pixels) + chunk(b"IEND", b""))
    with open(path, "wb") as handle:
        handle.write(png)
    return str(path)


def _differ(a, b, tolerance: float) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a != b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) > tolerance
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() != b.keys() or any(_differ(a[k], b[k], tolerance) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) != len(b) or any(_differ(x, y, tolerance) for x, y in zip(a, b))
    return a != b


def differences(before, after, ignore=(), tolerance: float = TOLERANCIA_DO_EDITOR) -> dict:
    """Campos de dois Command (ou dicts) que mudaram: {campo: (antes, depois)}. Vazio = idênticos."""
    a = before.to_dict() if hasattr(before, "to_dict") else dict(before)
    b = after.to_dict() if hasattr(after, "to_dict") else dict(after)
    skipped = set(CAMPOS_RECALCULADOS) | set(ignore)
    return {key: (a.get(key), b.get(key)) for key in sorted(set(a) | set(b))
            if key not in skipped and _differ(a.get(key), b.get(key), tolerance)}
