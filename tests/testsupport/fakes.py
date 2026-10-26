"""Dublês de teste: user32 falso (SendInput), pynput falso, monitor falso e backend com ganchos."""
from __future__ import annotations

import os
import types
from typing import Callable

from automationstudio import input_system


class FakeKernel32:
    def __init__(self, last_error: int = 0) -> None:
        self.last_error = last_error

    def GetLastError(self) -> int:  # noqa: N802
        return self.last_error


class FakeUser32:
    """Imita o trecho do USER32 que o Win32InputBackend usa e registra cada INPUT enviado.

    Layout fictício: letras, dígitos e espaço têm código de tecla; o resto devolve -1, o que faz o
    backend cair no caminho Unicode (como acontece com símbolos que o layout não tem).
    """

    def __init__(self, fail_sends: bool = False, layout: int = 0x0416) -> None:
        self.sent: list[tuple] = []  # ("key", vk, flags, scan) | ("mouse", flags, data, dx, dy) | ("cursor", x, y)
        self.fail_sends = fail_sends
        self.layout = layout
        self.send_calls = 0

    # -- API do USER32 ---------------------------------------------------------------------------
    def SendInput(self, count, pointer, size):  # noqa: N802
        self.send_calls += 1
        if self.fail_sends:
            return 0
        target = getattr(pointer, "_obj", None)
        assert target is not None, "FakeUser32: o argumento de SendInput não expõe _obj; adapte o fake"
        items = list(target) if hasattr(target, "__len__") else [target]
        for item in items[:count]:
            if item.type == 1:
                self.sent.append(("key", item.ki.wVk, item.ki.dwFlags, item.ki.wScan))
            else:
                self.sent.append(("mouse", item.mi.dwFlags, item.mi.mouseData, item.mi.dx, item.mi.dy))
        return count

    @staticmethod
    def _scan(code: int) -> int:
        char = chr(code)
        if "a" <= char <= "z":
            return ord(char.upper())
        if "A" <= char <= "Z":
            return (1 << 8) | ord(char)  # o byte alto é o estado do Shift
        if "0" <= char <= "9":
            return ord(char)
        if char == " ":
            return 0x20
        return -1

    def VkKeyScanW(self, code):  # noqa: N802
        return self._scan(code)

    def VkKeyScanExW(self, code, hkl):  # noqa: N802
        return self._scan(code)

    def GetKeyboardLayout(self, thread):  # noqa: N802
        return self.layout

    def SetCursorPos(self, x, y):  # noqa: N802
        self.sent.append(("cursor", int(x), int(y)))
        return 1

    # -- consultas de teste ------------------------------------------------------------------------
    def keys(self) -> list[tuple[int, int]]:
        """(código de tecla, flags) de cada evento de teclado enviado, na ordem."""
        return [(vk, flags) for kind, vk, flags, _scan in (s for s in self.sent if s[0] == "key")]

    def mouse(self) -> list[tuple]:
        return [s[1:] for s in self.sent if s[0] == "mouse"]


class FakePynput:
    """Nomes do pynput trocados por dublês dentro de input_system (backend de fallback)."""

    class Key:  # imita pynput.keyboard.Key: o valor é só um rótulo
        enter, esc, ctrl, shift, alt, alt_gr, cmd, menu, space, tab = (f"<{n}>" for n in ("enter", "esc", "ctrl", "shift", "alt", "alt_gr", "cmd", "menu", "space", "tab"))
        backspace, delete, home, end, page_up, page_down = (f"<{n}>" for n in ("backspace", "delete", "home", "end", "page_up", "page_down"))
        up, down, left, right, caps_lock, insert = (f"<{n}>" for n in ("up", "down", "left", "right", "caps_lock", "insert"))
        f1, f2, f3, f4, f5, f6, f7, f8, f9, f10, f11, f12 = (f"<f{i}>" for i in range(1, 13))
        pause, print_screen, scroll_lock, num_lock = (f"<{n}>" for n in ("pause", "print_screen", "scroll_lock", "num_lock"))

    class KeyCode:
        @staticmethod
        def from_char(char: str) -> str:
            return f"<char {char}>"

    class Button:
        left, right, middle, x1, x2 = "<left>", "<right>", "<middle>", "<x1>", "<x2>"

    def __init__(self) -> None:
        self.log: list[tuple] = []
        outer = self

        class KeyboardController:
            def press(self, key): outer.log.append(("press", key))
            def release(self, key): outer.log.append(("release", key))
            def type(self, text): outer.log.append(("type", text))

        class MouseController:
            def __init__(self): self._position = (0, 0)
            @property
            def position(self): return self._position
            @position.setter
            def position(self, value):
                self._position = tuple(value); outer.log.append(("position", self._position))
            def press(self, button): outer.log.append(("mouse_press", button))
            def release(self, button): outer.log.append(("mouse_release", button))
            def move(self, dx, dy): outer.log.append(("move", dx, dy))
            def scroll(self, dx, dy): outer.log.append(("scroll", dx, dy))

        self.KeyboardController = KeyboardController
        self.MouseController = MouseController

    def install(self, monkeypatch) -> "FakePynput":
        """Aponta o backend pynput para estes dublês e desliga os atalhos que injetariam input REAL no Windows."""
        names = {"_PYNPUT_AVAILABLE": True, "Key": self.Key, "KeyCode": self.KeyCode, "Button": self.Button,
                 "KeyboardController": self.KeyboardController, "MouseController": self.MouseController}
        for name, value in names.items():
            monkeypatch.setattr(input_system, name, value, raising=False)
        pretend_not_windows(monkeypatch)
        return self


def pretend_not_windows(monkeypatch) -> None:
    """Faz input_system enxergar os.name != 'nt': o backend pynput só usa keybd_event/mouse_event no Windows."""
    proxy = types.SimpleNamespace(**{name: getattr(os, name) for name in dir(os) if not name.startswith("__")})
    proxy.name = "posix"
    monkeypatch.setattr(input_system, "os", proxy, raising=False)


def pretend_windows(monkeypatch) -> None:
    """Faz input_system enxergar os.name == 'nt' (para exercitar os ramos exclusivos do Windows com ctypes falso)."""
    proxy = types.SimpleNamespace(**{name: getattr(os, name) for name in dir(os) if not name.startswith("__")})
    proxy.name = "nt"
    monkeypatch.setattr(input_system, "os", proxy, raising=False)


class FakeWindll:
    """`ctypes.windll` falso: registra keybd_event/mouse_event e entrega os mesmos user32/kernel32 falsos ao backend."""

    def __init__(self, user32: "FakeUser32 | None" = None, kernel32: "FakeKernel32 | None" = None) -> None:
        self.calls: list[tuple] = []
        outer = self

        class _User32Proxy:
            def __getattr__(self, name):  # SendInput, VkKeyScanW, SetCursorPos... vão para o FakeUser32
                if user32 is None:
                    raise AttributeError(name)
                return getattr(user32, name)

            def keybd_event(self, vk, scan, flags, extra):
                outer.calls.append(("keybd_event", vk, flags))

            def mouse_event(self, flags, dx, dy, data, extra):
                outer.calls.append(("mouse_event", flags, data))

        self.user32 = _User32Proxy()
        self.kernel32 = kernel32 if kernel32 is not None else FakeKernel32()

    def install(self, monkeypatch) -> "FakeWindll":
        import ctypes
        monkeypatch.setattr(ctypes, "windll", self, raising=False)
        return self


class FakeUser32Abnt2(FakeUser32):
    """FakeUser32 com as teclas mortas do teclado brasileiro (~ ´ ` ^ ¨), mas sem 'ç' nem 'ã' prontos.

    Assim `type_text("ã")` é obrigado a compor: tecla morta (~) e depois a letra, como numa digitação física.
    """

    DEAD = {"~": 0xDE, "´": 0xDB, "`": (1 << 8) | 0xDB, "^": (1 << 8) | 0xDE, "¨": (1 << 8) | 0x36}

    @classmethod
    def _scan(cls, code: int) -> int:
        char = chr(code)
        return cls.DEAD[char] if char in cls.DEAD else FakeUser32._scan(code)


class FakeMonitor:
    """Mesma superfície que Recorder e GlobalInputMonitor expõem, sem hooks globais."""

    def __init__(self) -> None:
        self.on_key: list[Callable] = []
        self.on_mouse_button: list[Callable] = []
        self.on_mouse_move: list[Callable] = []
        self.on_mouse_scroll: list[Callable] = []
        self.running = False

    @property
    def available(self) -> bool:
        return True

    def is_running(self) -> bool:
        return self.running

    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    # -- eventos de teste ---------------------------------------------------------------------------
    def press(self, name: str) -> None:
        for callback in list(self.on_key):
            callback(name, True)

    def release(self, name: str) -> None:
        for callback in list(self.on_key):
            callback(name, False)

    def click(self, button: str, pressed: bool) -> None:
        for callback in list(self.on_mouse_button):
            callback(button, pressed)

    def move(self, x: int, y: int) -> None:
        for callback in list(self.on_mouse_move):
            callback(x, y)

    def scroll(self, dx: int, dy: int) -> None:
        for callback in list(self.on_mouse_scroll):
            callback(dx, dy)


class HookBackend(input_system.MockInputBackend):
    """Mock que chama um gancho logo depois do N-ésimo evento enviado.

    O gancho roda na thread do motor, então serve para injetar pausa ou parada em pontos exatos
    da execução, sem depender de tempo real.
    """

    def __init__(self, clock=None) -> None:
        super().__init__(clock)
        self.hooks: dict[int, Callable[[], None]] = {}

    def _log(self, action: str, target) -> None:
        super()._log(action, target)
        hook = self.hooks.pop(len(self.events), None)
        if hook is not None:
            hook()


class FakeListeners:
    """Troca os `Listener` do pynput (teclado e mouse) por dublês que só guardam os callbacks e o estado.

    Permite testar `GlobalInputMonitor.start()/stop()` sem pynput instalado e sem hooks globais de verdade.
    """

    def __init__(self) -> None:
        self.keyboard: list = []
        self.mouse: list = []
        outer = self

        class _Base:
            def __init__(self, **callbacks) -> None:
                self.callbacks = callbacks
                self.started = False
                self.stopped = False

            def start(self) -> None:
                self.started = True

            def stop(self) -> None:
                self.stopped = True

        class Keyboard(_Base):
            def __init__(self, **callbacks) -> None:
                super().__init__(**callbacks)
                outer.keyboard.append(self)

        class Mouse(_Base):
            def __init__(self, **callbacks) -> None:
                super().__init__(**callbacks)
                outer.mouse.append(self)

        self.KeyboardListener, self.MouseListener = Keyboard, Mouse

    def install(self, monkeypatch) -> "FakeListeners":
        monkeypatch.setattr(input_system, "_PYNPUT_AVAILABLE", True)
        monkeypatch.setattr(input_system, "_pynput_keyboard", types.SimpleNamespace(Listener=self.KeyboardListener), raising=False)
        monkeypatch.setattr(input_system, "_pynput_mouse", types.SimpleNamespace(Listener=self.MouseListener), raising=False)
        return self
