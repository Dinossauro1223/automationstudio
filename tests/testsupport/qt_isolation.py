"""Isolamento para testes de GUI: nada de registro real, hooks globais, input real ou diálogos modais.

Sem isto, construir a MainWindow na sua máquina abriria a SUA pasta de dados (o registro do Windows
tem prioridade sobre o argumento project_dir) e ligaria hooks globais de teclado e mouse.
"""
from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path


class DialogLog:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.install_errors: list[str] = []

    def record(self, kind: str, *details) -> None:
        self.calls.append((kind, *details))

    def kinds(self) -> list[str]:
        return [c[0] for c in self.calls]


def install(monkeypatch, tmp_path) -> DialogLog:
    from PySide6.QtWidgets import QDialog, QFileDialog, QInputDialog, QMenu, QMessageBox

    log = DialogLog()

    # 1) Registro do Windows: bloqueado. As funções que o leem passam a devolver o argumento padrão.
    fake_winreg = types.ModuleType("winreg")

    def blocked(*args, **kwargs):
        raise OSError("registro do Windows bloqueado durante os testes")

    for name in ("OpenKey", "CreateKey", "SetValueEx", "QueryValueEx"):
        setattr(fake_winreg, name, blocked)
    fake_winreg.HKEY_CURRENT_USER, fake_winreg.REG_SZ = 0, 1
    monkeypatch.setitem(sys.modules, "winreg", fake_winreg)
    for name in ("core", "main_window", "app", "command_editor"):
        module = importlib.import_module(f"automationstudio.{name}")
        if hasattr(module, "_registered_data_dir"):
            monkeypatch.setattr(module, "_registered_data_dir", lambda default_dir: Path(default_dir).resolve())
        if hasattr(module, "_set_registered_data_dir"):
            monkeypatch.setattr(module, "_set_registered_data_dir", lambda folder, _log=log: _log.record("registro", str(folder)))

    # 2) Hooks globais e backend de input real: trocados por versões inertes.
    input_system = importlib.import_module("automationstudio.input_system")
    monkeypatch.setattr(input_system.GlobalInputMonitor, "start", lambda self: None)
    monkeypatch.setattr(input_system.GlobalInputMonitor, "stop", lambda self: None)
    main_window = importlib.import_module("automationstudio.main_window")
    monkeypatch.setattr(main_window, "_default_backend", lambda: input_system.MockInputBackend(), raising=False)

    # 3) Diálogos modais: respondem sem bloquear e ficam registrados. Um exec() inesperado derruba o teste.
    def answer(kind, result):
        def fake(*args, **kwargs):
            log.record(kind, *[a for a in args if isinstance(a, str)])
            return result
        return staticmethod(fake)

    def forbidden(self, *args, **kwargs):
        raise AssertionError(f"diálogo modal inesperado: {type(self).__name__}.exec()")

    patches = [
        (QMessageBox, "warning", answer("warning", QMessageBox.StandardButton.Ok)),
        (QMessageBox, "information", answer("information", QMessageBox.StandardButton.Ok)),
        (QMessageBox, "critical", answer("critical", QMessageBox.StandardButton.Ok)),
        (QMessageBox, "question", answer("question", QMessageBox.StandardButton.Yes)),
        (QInputDialog, "getText", answer("getText", ("", False))),
        (QInputDialog, "getItem", answer("getItem", ("", False))),
        (QInputDialog, "getInt", answer("getInt", (0, False))),
        (QInputDialog, "getDouble", answer("getDouble", (0.0, False))),
        (QFileDialog, "getOpenFileName", answer("getOpenFileName", ("", ""))),
        (QFileDialog, "getSaveFileName", answer("getSaveFileName", ("", ""))),
        (QFileDialog, "getExistingDirectory", answer("getExistingDirectory", "")),
        (QDialog, "exec", forbidden),
        (QMenu, "exec", forbidden),
    ]
    for owner, name, replacement in patches:
        try:
            monkeypatch.setattr(owner, name, replacement)
        except Exception as exc:  # noqa: BLE001
            log.install_errors.append(f"{owner.__name__}.{name}: {exc}")
    return log
