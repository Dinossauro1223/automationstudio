from __future__ import annotations



from .core import *
from . import core
from .vision import ImageWaitError, wait_for_image


# Optional pynput integration. This declaration MUST exist before any class
# references it; the Windows execution backend remains USER32/SendInput.
try:
    from pynput.keyboard import Controller as KeyboardController
    from pynput.keyboard import Key
    from pynput.keyboard import KeyCode
    from pynput import keyboard as _pynput_keyboard
    from pynput.mouse import Controller as MouseController
    from pynput.mouse import Button
    from pynput import mouse as _pynput_mouse
    _PYNPUT_AVAILABLE = True
except Exception:
    _PYNPUT_AVAILABLE = False
    KeyboardController = None
    MouseController = None
    Key = None
    KeyCode = None
    Button = None
    _pynput_keyboard = None
    _pynput_mouse = None

# Nomes do Studio -> nomes de `pynput.keyboard.Key`. Usado só pelo backend de fallback (pynput).
_KEY_ALIASES = {
    "ENTER": "enter", "RETURN": "enter", "ESC": "esc", "ESCAPE": "esc", "CTRL": "ctrl", "SHIFT": "shift",
    "ALT": "alt", "ALTGR": "alt_gr", "WIN": "cmd", "MENU": "menu", "SPACE": "space", "TAB": "tab",
    "BACKSPACE": "backspace", "DELETE": "delete", "HOME": "home", "END": "end", "PAGEUP": "page_up",
    "PAGEDOWN": "page_down", "UP": "up", "DOWN": "down", "LEFT": "left", "RIGHT": "right",
    "CAPSLOCK": "caps_lock", "INSERT": "insert",
    # Nomes do editor que o pynput escreve com sublinhado (os mesmos que core._SPECIAL_KEY_NAMES lê no sentido inverso).
    "PRINTSCREEN": "print_screen", "SCROLLLOCK": "scroll_lock", "NUMLOCK": "num_lock",
}


def _resolve_key(name: str):
    """Traduz um nome de tecla do Studio para o objeto do pynput. Nome desconhecido é erro, nunca outra tecla."""
    text = str(name)
    special = getattr(Key, _KEY_ALIASES.get(text.upper(), text.lower()), None) if Key is not None else None
    if special is not None:
        return special
    if len(text) == 1 and KeyCode is not None:
        return KeyCode.from_char(text)
    raise ValueError(f"Tecla não suportada pelo backend pynput: {name}")


def _resolve_mouse_button(name: str):
    """Traduz o nome de botão do Studio para o botão do pynput. Botão desconhecido é erro, nunca clique esquerdo."""
    key = str(name).lower()
    button = getattr(Button, key, None) if (Button is not None and key in {"left", "right", "middle", "x1", "x2"}) else None
    if button is None:
        raise ValueError(f"Botão de mouse não suportado pelo backend pynput: {name}")
    return button


class InputBackend(ABC):
    @abstractmethod
    def key_down(self, key: str) -> None: ...

    @abstractmethod
    def key_up(self, key: str) -> None: ...

    @abstractmethod
    def mouse_down(self, button: str) -> None: ...

    @abstractmethod
    def mouse_up(self, button: str) -> None: ...

    @abstractmethod
    def mouse_move(self, x: int, y: int, relative: bool = False) -> None: ...

    @abstractmethod
    def mouse_scroll(self, dx: int, dy: int) -> None: ...

    @abstractmethod
    def type_text(self, text: str) -> None: ...

    def release_all(self, pressed_keys: set[str], pressed_buttons: set[str]) -> None:
        """
        Rotina de segurança (itens 11 e 25 do roteiro): libera tudo que
        estiver marcado como pressionado. A implementação padrão apenas
        chama key_up/mouse_up para cada item; backends reais podem
        sobrescrever para usar uma chamada de sistema mais direta.
        """
        for key in list(pressed_keys):
            try:
                self.key_up(key)
            except Exception:
                pass
        for button in list(pressed_buttons):
            try:
                self.mouse_up(button)
            except Exception:
                pass

class MockInputBackend(InputBackend):
    def __init__(self, clock=None) -> None:
        # `clock` precisa ter monotonic(); os testes passam um relógio virtual.
        self._clock = clock if clock is not None else core.SystemClock()
        self.events: list[tuple[float, str, Any]] = []
        self._t0 = self._clock.monotonic()

    def _log(self, action: str, target: Any) -> None:
        self.events.append((round(self._clock.monotonic() - self._t0, 3), action, target))

    def key_down(self, key: str) -> None: self._log("key_down", key)
    def key_up(self, key: str) -> None: self._log("key_up", key)
    def type_text(self, text: str) -> None: self._log("type_text", text)
    def mouse_down(self, button: str) -> None: self._log("mouse_down", button)
    def mouse_up(self, button: str) -> None: self._log("mouse_up", button)
    def mouse_move(self, x: int, y: int, relative: bool = False) -> None: self._log("mouse_move", (x, y, relative))
    def mouse_scroll(self, dx: int, dy: int) -> None: self._log("mouse_scroll", (dx, dy))
    def actions(self) -> list[str]: return [e[1] for e in self.events]

class PynputInputBackend(InputBackend):
    def __init__(self) -> None:
        if not _PYNPUT_AVAILABLE:
            raise RuntimeError(
                "pynput não está instalado. Rode: pip install pynput"
            )
        self._keyboard = KeyboardController()
        self._mouse = MouseController()

    def _win_vk(self, key: str):
        if os.name != 'nt':
            return None
        table={
            **{f'NUM{i}':0x60+i for i in range(10)}, 'NUM*':0x6A,'NUM+':0x6B,'NUM-':0x6D,'NUM.':0x6E,'NUM/':0x6F,'NUMENTER':0x0D,
            'Ç':0xBA, '~^':0xC0, 'MENU':0x5D, 'WIN':0x5B,
        }
        return table.get(key.upper())
    def _win_key(self,key,down):
        vk=self._win_vk(key)
        if vk is None:return False
        try:
            import ctypes
            flags=0 if down else 2
            ctypes.windll.user32.keybd_event(vk,0,flags,0); return True
        except Exception:
            return False
    def key_down(self, key: str) -> None:
        if self._win_key(key,True): return
        if key.upper()=='FN': return
        self._keyboard.press(_resolve_key(key))

    def key_up(self, key: str) -> None:
        if self._win_key(key,False): return
        if key.upper()=='FN': return
        self._keyboard.release(_resolve_key(key))

    def type_text(self, text: str) -> None:
        # Evita rajadas de eventos no aplicativo receptor.
        for ch in str(text or ''):
            self._keyboard.type(ch)
            if core.TEXT_CHAR_INTERVAL > 0:
                time.sleep(core.TEXT_CHAR_INTERVAL)

    def mouse_down(self, button: str) -> None:
        self._mouse.press(_resolve_mouse_button(button))

    def mouse_up(self, button: str) -> None:
        self._mouse.release(_resolve_mouse_button(button))

    def mouse_move(self, x: int, y: int, relative: bool = False) -> None:
        if relative:
            self._mouse.move(x, y)
        else:
            self._mouse.position = (x, y)

    def mouse_scroll(self, dx: int, dy: int) -> None:
        # No Windows, uma unidade do comando representa uma linha/entalhe
        # de roda (WHEEL_DELTA = 120). Isso torna a configuração de
        # "quantas linhas" previsível para aplicativos Windows.
        if os.name == 'nt':
            try:
                import ctypes
                if dy:
                    ctypes.windll.user32.mouse_event(0x0800, 0, 0, int(dy) * 120, 0)
                if dx:
                    ctypes.windll.user32.mouse_event(0x01000, 0, 0, int(dx) * 120, 0)
                return
            except Exception:
                pass
        self._mouse.scroll(dx, dy)

class _SemKernel32:
    """kernel32 mínimo para quando um user32 falso é injetado fora do Windows."""

    def GetLastError(self) -> int:  # noqa: N802
        return 0


class Win32InputBackend(InputBackend):
    """InputBackend baseado em USER32.SendInput/movimento de cursor."""

    def __init__(self, user32=None, kernel32=None) -> None:
        # user32/kernel32 podem ser injetados: os testes usam um SendInput falso, em qualquer sistema.
        if user32 is None and os.name != "nt":
            raise RuntimeError("Win32InputBackend só está disponível no Windows.")
        import ctypes
        from ctypes import wintypes
        self.ctypes = ctypes
        self.wintypes = wintypes
        self.user32 = user32 if user32 is not None else ctypes.windll.user32
        if kernel32 is not None:
            self.kernel32 = kernel32
        elif user32 is None:
            self.kernel32 = ctypes.windll.kernel32
        else:
            self.kernel32 = _SemKernel32()

        ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR),
            ]

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [
                ("dx", wintypes.LONG),
                ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR),
            ]

        class HARDWAREINPUT(ctypes.Structure):
            _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]

        class INPUTUNION(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]

        class INPUT(ctypes.Structure):
            _anonymous_ = ("u",)
            _fields_ = [("type", wintypes.DWORD), ("u", INPUTUNION)]

        self.KEYBDINPUT = KEYBDINPUT
        self.MOUSEINPUT = MOUSEINPUT
        self.INPUT = INPUT
        self.INPUTUNION = INPUTUNION
        self.INPUT_KEYBOARD = 1
        self.INPUT_MOUSE = 0
        self.KEYEVENTF_KEYUP = 0x0002
        self.KEYEVENTF_EXTENDEDKEY = 0x0001
        self.KEYEVENTF_UNICODE = 0x0004
        self.MOUSEEVENTF_MOVE = 0x0001
        self.MOUSEEVENTF_LEFTDOWN = 0x0002
        self.MOUSEEVENTF_LEFTUP = 0x0004
        self.MOUSEEVENTF_RIGHTDOWN = 0x0008
        self.MOUSEEVENTF_RIGHTUP = 0x0010
        self.MOUSEEVENTF_MIDDLEDOWN = 0x0020
        self.MOUSEEVENTF_MIDDLEUP = 0x0040
        self.MOUSEEVENTF_XDOWN = 0x0080
        self.MOUSEEVENTF_XUP = 0x0100
        self.MOUSEEVENTF_WHEEL = 0x0800
        self.MOUSEEVENTF_HWHEEL = 0x1000
        self.XBUTTON1 = 0x0001
        self.XBUTTON2 = 0x0002

        self._vk = {
            "BACKSPACE":0x08,"TAB":0x09,"ENTER":0x0D,"SHIFT":0x10,"CTRL":0x11,"ALT":0x12,"ALTGR":0xA5,
            "PAUSE":0x13,"CAPSLOCK":0x14,"ESC":0x1B,"SPACE":0x20,"PAGEUP":0x21,"PAGEDOWN":0x22,
            "END":0x23,"HOME":0x24,"LEFT":0x25,"UP":0x26,"RIGHT":0x27,"DOWN":0x28,
            "PRINTSCREEN":0x2C,"INSERT":0x2D,"DELETE":0x2E,"WIN":0x5B,"LWIN":0x5B,"RWIN":0x5C,
            "MENU":0x5D,"NUMLOCK":0x90,"SCROLLLOCK":0x91,"NUMENTER":0x0D,"NUM*":0x6A,
            "NUM+":0x6B,"NUM-":0x6D,"NUM.":0x6E,"NUM/":0x6F,"VOLUME_MUTE":0xAD,
            "VOLUME_DOWN":0xAE,"VOLUME_UP":0xAF,"MEDIA_NEXT":0xB0,"MEDIA_PREV":0xB1,
            "MEDIA_STOP":0xB2,"MEDIA_PLAY_PAUSE":0xB3,"Ç":0xBA,"~^":0xC0,
        }
        self._vk.update({f"F{i}":0x6F+i for i in range(1,13)})
        self._vk.update({f"NUM{i}":0x60+i for i in range(10)})
        self._vk.update({chr(ord('A')+i):0x41+i for i in range(26)})
        self._vk.update({str(i):0x30+i for i in range(10)})
        self._vk.update({
            "NUM0":0x60,"NUM1":0x61,"NUM2":0x62,"NUM3":0x63,"NUM4":0x64,
            "NUM5":0x65,"NUM6":0x66,"NUM7":0x67,"NUM8":0x68,"NUM9":0x69,
        })

        # X1/X2 são deliberadamente definidos pela convenção física do Studio:
        # X1 = botão lateral superior; X2 = botão lateral inferior.
        self._xbutton = {"x1": self.XBUTTON1, "x2": self.XBUTTON2}

    @property
    def name(self) -> str:
        return "Windows USER32.SendInput"

    def _send(self, inp) -> None:
        sent = self.user32.SendInput(1, self.ctypes.byref(inp), self.ctypes.sizeof(self.INPUT))
        if sent != 1:
            err = self.kernel32.GetLastError()
            raise OSError(err, f"SendInput falhou (GetLastError={err}).")

    def _send_many(self, inputs) -> None:
        """Envia uma sequência inteira de INPUTs em uma única chamada.

        Para texto Unicode isso evita que centenas de chamadas individuais
        sejam intercaladas pelo sistema com outros eventos de teclado e reduz
        a janela para duplicações/fragmentações observadas em automações longas.
        O mecanismo continua sendo USER32.SendInput.
        """
        items = list(inputs)
        if not items:
            return
        ArrayType = self.INPUT * len(items)
        arr = ArrayType(*items)
        sent = self.user32.SendInput(len(items), self.ctypes.byref(arr), self.ctypes.sizeof(self.INPUT))
        if sent != len(items):
            err = self.kernel32.GetLastError()
            raise OSError(err, f"SendInput enviou {sent}/{len(items)} eventos (GetLastError={err}).")

    def _keyboard_input(self, vk: int, flags: int = 0, scan: int = 0):
        inp = self.INPUT()
        inp.type = self.INPUT_KEYBOARD
        inp.ki = self.KEYBDINPUT(vk, scan, flags, 0, 0)
        return inp

    def _resolve_vk(self, key: str):
        k = str(key).upper()
        if k == "FN":
            return None
        if k in self._vk:
            return self._vk[k]
        # Para caracteres dependentes do layout, peça ao Windows o VK da
        # tecla correspondente. Para letras, normalizamos para minúscula
        # para não introduzir SHIFT implicitamente.
        text = str(key)
        if len(text) == 1:
            code = self.user32.VkKeyScanW(ord(text))
            if code == -1:
                code = self.user32.VkKeyScanW(ord(text.lower()))
            if code != -1:
                return code & 0xFF
        return None

    def _send_vk_character(self, ch: str, hkl=None) -> bool:
        """Envia um caractere como teclas reais usando o layout ativo do Windows.

        VkKeyScanExW converte o caractere para VK + estado de SHIFT/CTRL/ALT
        segundo o layout de entrada atual. Isso faz com que o comando TEXT use
        a mesma cadeia de eventos de teclado usada pelos demais comandos, em
        vez de depender de ``pynput.keyboard.type``.
        """
        if not ch or len(ch) != 1:
            return False
        if hkl is None:
            hkl = self.user32.GetKeyboardLayout(0)
        result = self.user32.VkKeyScanExW(ord(ch), hkl)
        if result == -1:
            return False
        vk = result & 0xFF
        shift_state = (result >> 8) & 0xFF
        modifier_vks = []
        if shift_state & 1:
            modifier_vks.append(0x10)  # SHIFT
        if shift_state & 2:
            modifier_vks.append(0x11)  # CTRL
        if shift_state & 4:
            modifier_vks.append(0x12)  # ALT
        inputs = []
        for mod in modifier_vks:
            inputs.append(self._keyboard_input(mod, 0))
        extended = vk in {0x21,0x22,0x23,0x24,0x25,0x26,0x27,0x28,0x2D,0x2E,0x5B,0x5C,0x5D,0x6F,0xA5}
        vk_flags = self.KEYEVENTF_EXTENDEDKEY if extended else 0
        inputs.append(self._keyboard_input(vk, vk_flags))
        inputs.append(self._keyboard_input(vk, self.KEYEVENTF_KEYUP | vk_flags))
        for mod in reversed(modifier_vks):
            inputs.append(self._keyboard_input(mod, self.KEYEVENTF_KEYUP))
        self._send_many(inputs)
        return True

    def _send_unicode_character(self, ch: str) -> None:
        """Fallback Unicode da própria API USER32 para caracteres sem VK."""
        units = ch.encode('utf-16-le', 'surrogatepass')
        inputs = []
        for i in range(0, len(units), 2):
            unit = int.from_bytes(units[i:i+2], 'little')
            inputs.append(self._keyboard_input(0, self.KEYEVENTF_UNICODE, unit))
            inputs.append(self._keyboard_input(0, self.KEYEVENTF_UNICODE | self.KEYEVENTF_KEYUP, unit))
        if inputs:
            self._send_many(inputs)

    def _send_brazilian_composed(self, ch: str, hkl) -> bool:
        """Tenta composição de acentos comuns do teclado brasileiro ABNT2.

        O Windows trata ``~``, ``´``, ````` e ``^`` como teclas mortas no
        layout brasileiro. Para ã/õ/á/é/í/ó/ú/à/â/ê/ô e variantes maiúsculas,
        decompondo o caractere e enviando primeiro a tecla morta, preservamos
        o comportamento de uma digitação física. Se o layout atual não
        reconhecer a tecla morta, retornamos False para usar o fallback Unicode.
        """
        import unicodedata
        normalized = unicodedata.normalize('NFD', ch)
        if len(normalized) != 2:
            return False
        base, combining = normalized[0], normalized[1]
        dead_key = {
            '\u0301': '´',  # acute
            '\u0300': '`',  # grave
            '\u0302': '^',  # circumflex
            '\u0303': '~',  # tilde
            '\u0308': '¨',  # diaeresis
        }.get(combining)
        if not dead_key:
            return False
        if not self._send_vk_character(dead_key, hkl):
            return False
        if not self._send_vk_character(base, hkl):
            return False
        return True

    def type_text(self, text: str) -> None:
        """Digita texto via USER32.SendInput, respeitando o layout ativo.

        A rota principal gera VK/SHIFT/CTRL/ALT reais a partir do layout atual
        do Windows. Isso é especialmente importante para ABNT2 (ç, acentos,
        símbolos e teclas mortas). Quando um caractere não possui representação
        no layout ativo, usamos KEYEVENTF_UNICODE, ainda dentro da API USER32,
        em vez de recorrer ao controlador de teclado do pynput.
        """
        value = str(text or '')
        if not value:
            return
        hkl = self.user32.GetKeyboardLayout(0)
        for ch in value:
            sent = self._send_vk_character(ch, hkl)
            if not sent:
                sent = self._send_brazilian_composed(ch, hkl)
            if not sent:
                self._send_unicode_character(ch)
            if core.TEXT_CHAR_INTERVAL > 0:
                time.sleep(core.TEXT_CHAR_INTERVAL)

    def key_down(self, key: str) -> None:
        vk = self._resolve_vk(key)
        if vk is None:
            if str(key).upper() == "FN":
                return
            raise ValueError(f"Tecla não suportada pelo backend Win32: {key}")
        flags = self.KEYEVENTF_EXTENDEDKEY if vk in {0x21,0x22,0x23,0x24,0x25,0x26,0x27,0x28,0x2D,0x2E,0x5B,0x5C,0x5D,0x6F,0xA5} else 0
        self._send(self._keyboard_input(vk, flags))

    def key_up(self, key: str) -> None:
        vk = self._resolve_vk(key)
        if vk is None:
            return
        flags = self.KEYEVENTF_KEYUP | (self.KEYEVENTF_EXTENDEDKEY if vk in {0x21,0x22,0x23,0x24,0x25,0x26,0x27,0x28,0x2D,0x2E,0x5B,0x5C,0x5D,0x6F,0xA5} else 0)
        self._send(self._keyboard_input(vk, flags))

    def _mouse(self, flags: int, data: int = 0, dx: int = 0, dy: int = 0) -> None:
        inp = self.INPUT()
        inp.type = self.INPUT_MOUSE
        inp.mi = self.MOUSEINPUT(dx, dy, data, flags, 0, 0)
        self._send(inp)

    def mouse_down(self, button: str) -> None:
        b = str(button).lower()
        flags = {"left":self.MOUSEEVENTF_LEFTDOWN,"right":self.MOUSEEVENTF_RIGHTDOWN,"middle":self.MOUSEEVENTF_MIDDLEDOWN}.get(b)
        if flags is not None:
            self._mouse(flags); return
        if b in self._xbutton:
            self._mouse(self.MOUSEEVENTF_XDOWN, self._xbutton[b]); return
        raise ValueError(f"Botão de mouse não suportado: {button}")

    def mouse_up(self, button: str) -> None:
        b = str(button).lower()
        flags = {"left":self.MOUSEEVENTF_LEFTUP,"right":self.MOUSEEVENTF_RIGHTUP,"middle":self.MOUSEEVENTF_MIDDLEUP}.get(b)
        if flags is not None:
            self._mouse(flags); return
        if b in self._xbutton:
            self._mouse(self.MOUSEEVENTF_XUP, self._xbutton[b]); return
        raise ValueError(f"Botão de mouse não suportado: {button}")

    def mouse_move(self, x: int, y: int, relative: bool = False) -> None:
        if relative:
            self._mouse(self.MOUSEEVENTF_MOVE, 0, int(x), int(y))
        else:
            self.user32.SetCursorPos(int(x), int(y))

    def mouse_scroll(self, dx: int, dy: int) -> None:
        if dy:
            self._mouse(self.MOUSEEVENTF_WHEEL, int(dy) * 120)
        if dx:
            self._mouse(self.MOUSEEVENTF_HWHEEL, int(dx) * 120)

class GlobalInputMonitor:
    """
    Observador passivo de teclado/mouse do sistema operacional inteiro
    (não só desta janela) -- é o que permite ao teclado/mouse virtual
    reagir ao que o usuário realmente pressiona, e não só ao que a
    automação está injetando.

    Não injeta nada, não grava nada em disco: só notifica observadores.
    """

    def __init__(self) -> None:
        self.on_key: list[Callable[[str, bool], None]] = []          # (nome, pressionada?)
        self.on_mouse_button: list[Callable[[str, bool], None]] = []  # (botão, pressionado?)
        self.on_mouse_scroll: list[Callable[[int, int], None]] = []   # (dx, dy)
        self.on_mouse_move: list[Callable[[int, int], None]] = []     # (x, y)

        self._keyboard_listener: Optional["_pynput_keyboard.Listener"] = None
        self._mouse_listener: Optional["_pynput_mouse.Listener"] = None
        self._last_mouse_pos: Optional[tuple[int,int]] = None

    @property
    def available(self) -> bool:
        return _PYNPUT_AVAILABLE

    def start(self) -> None:
        if not _PYNPUT_AVAILABLE:
            raise RuntimeError(
                "pynput não está instalado -- captura global de input indisponível. "
                "Rode: pip install pynput"
            )
        if self._keyboard_listener is not None:
            return  # já rodando

        self._keyboard_listener = _pynput_keyboard.Listener(
            on_press=lambda k: self._emit_key(k, True),
            on_release=lambda k: self._emit_key(k, False),
        )
        self._mouse_listener = _pynput_mouse.Listener(
            on_click=self._emit_click,
            on_scroll=lambda x, y, dx, dy: self._emit_scroll(dx, dy),
            on_move=self._emit_move,
        )
        self._keyboard_listener.start()
        self._mouse_listener.start()

    def stop(self) -> None:
        if self._keyboard_listener is not None:
            self._keyboard_listener.stop()
            self._keyboard_listener = None
        if self._mouse_listener is not None:
            self._mouse_listener.stop()
            self._mouse_listener = None

    def is_running(self) -> bool:
        return self._keyboard_listener is not None

    # ---- Callbacks internos do pynput (rodam na thread do listener) ---

    def _emit_key(self, key, pressed: bool) -> None:
        name = key_to_name(key)
        if not name:
            return
        for cb in list(self.on_key):
            try:
                cb(name, pressed)
            except Exception:
                traceback.print_exc()

    def _emit_click(self, x, y, button, pressed) -> None:
        name = str(getattr(button, "name", str(button))).lower()
        for cb in list(self.on_mouse_button):
            try:
                cb(name, pressed)
            except Exception:
                # Um observador defeituoso nunca pode matar o listener global.
                traceback.print_exc()

    def _emit_scroll(self, dx: int, dy: int) -> None:
        for cb in list(self.on_mouse_scroll):
            try:
                cb(dx, dy)
            except Exception:
                traceback.print_exc()

    def _emit_move(self, x: int, y: int) -> None:
        for cb in list(self.on_mouse_move):
            try:
                cb(x, y)
            except Exception:
                traceback.print_exc()

class HotkeyConflictError(RuntimeError):
    """Uma combinação de teclas já está registrada para outra ação.

    Complementa a validação de nível de projeto que já existe em
    `storage/project_manager.py` (item 24: atalhos duplicados entre
    mapas) cobrindo também o caso novo da Fase 5: um atalho de mapa
    colidindo com um atalho global de controle (pausar/continuar/
    emergência), ou dois atalhos de controle usando a mesma tecla.
    """

class GlobalHotkeyManager:
    def __init__(self, monitor: Optional[GlobalInputMonitor] = None) -> None:
        self.monitor = monitor if monitor is not None else GlobalInputMonitor()
        # Só é dono do ciclo de vida (start/stop) do monitor quando foi ELE
        # quem o criou -- se alguém injetar um monitor compartilhado (ex.:
        # nos testes, ou futuramente se fizer sentido reusar o mesmo da UI),
        # quem ligou o monitor é responsável por desligá-lo também.
        self._owns_monitor = monitor is None

        # combo -> (texto original do atalho, callback)
        self._bindings: dict[frozenset[str], tuple[str, Callable[[], None]]] = {}
        self._pressed: set[str] = set()
        self._fired: set[frozenset[str]] = set()
        self._key_cb = lambda name, pressed: self._on_key(name, pressed)
        self._mouse_cb = lambda name, pressed: self._on_mouse_button(name, pressed)

    @property
    def available(self) -> bool:
        return self.monitor.available

    def is_running(self) -> bool:
        return self.monitor.is_running()

    # ---- Registro ---------------------------------------------------

    def register(self, hotkey: str, callback: Callable[[], None]) -> None:
        """Registra `callback` para disparar quando `hotkey` for
        pressionada. Levanta `HotkeyConflictError` se a MESMA combinação
        de teclas já estiver associada a um callback DIFERENTE (ou seja,
        a uma ação diferente) -- registrar de novo o mesmo callback para
        o mesmo atalho é idempotente e não conflita (útil ao recarregar
        os atalhos a partir dos mapas + configurações)."""
        combo = parse_combo(hotkey)
        existing = self._bindings.get(combo)
        if existing is not None and existing[1] is not callback:
            raise HotkeyConflictError(
                f"O atalho '{hotkey}' usa a(s) mesma(s) tecla(s) que "
                f"'{existing[0]}', já em uso."
            )
        self._bindings[combo] = (hotkey, callback)

    def unregister(self, hotkey: str) -> None:
        self._bindings.pop(parse_combo(hotkey), None)

    def clear(self) -> None:
        """Remove todos os atalhos registrados (ex.: antes de recarregar
        a partir dos mapas + configurações, na MainWindow)."""
        self._bindings.clear()
        self._pressed.clear()
        self._fired.clear()

    # ---- Ciclo de vida ------------------------------------------------

    def start(self) -> None:
        if self._key_cb not in self.monitor.on_key:
            self.monitor.on_key.append(self._key_cb)
        if self._mouse_cb not in self.monitor.on_mouse_button:
            self.monitor.on_mouse_button.append(self._mouse_cb)
        if self._owns_monitor and not self.monitor.is_running():
            self.monitor.start()

    def stop(self) -> None:
        if self._key_cb in self.monitor.on_key:
            self.monitor.on_key.remove(self._key_cb)
        if self._mouse_cb in self.monitor.on_mouse_button:
            self.monitor.on_mouse_button.remove(self._mouse_cb)
        if self._owns_monitor and self.monitor.is_running():
            self.monitor.stop()
        self._pressed.clear()
        self._fired.clear()

    # ---- Callback (roda na thread do listener do pynput) ----------------

    def _on_key(self, name: str, pressed: bool) -> None:
        if pressed:
            self._pressed.add(name)
            # dict pequeno (poucos atalhos configurados) -- laço simples
            # é suficiente, sem precisar de índice extra.
            for combo, (_hotkey, callback) in self._bindings.items():
                if combo <= self._pressed and combo not in self._fired:
                    self._fired.add(combo)
                    callback()
        else:
            self._pressed.discard(name)
            # Soltar qualquer tecla de uma combinação já disparada "arma"
            # essa combinação de novo -- só precisa apertar tudo junto
            # outra vez, não precisa soltar TODAS as teclas.
            self._fired = {c for c in self._fired if name not in c}


    def _on_mouse_button(self, name: str, pressed: bool) -> None:
        normalized = str(name).lower()
        token_map = {
            "left": "MOUSE_LEFT", "right": "MOUSE_RIGHT", "middle": "MOUSE_MIDDLE",
            "x1": "MOUSE_X1", "x2": "MOUSE_X2",
        }
        token = token_map.get(normalized, f"MOUSE_{normalized.upper()}")
        if pressed:
            self._pressed.add(token)
            for combo, (_hotkey, callback) in self._bindings.items():
                if combo <= self._pressed and combo not in self._fired:
                    self._fired.add(combo)
                    callback()
        else:
            self._pressed.discard(token)
            self._fired = {c for c in self._fired if token not in c}

class ProcessReadinessError(RuntimeError):
    """Falha em aguardar um processo alvo ficar pronto."""

class WindowsProcessReadiness:
    """Barreira de prontidão para aplicativos Windows.

    A prontidão não exige que o usuário conheça ou configure uma quantidade
    mínima de RAM. Em vez disso, observa o próprio processo recém-aberto e
    considera-o pronto quando:

      1. o PID existe e continua sendo o mesmo;
      2. o processo permanece vivo;
      3. o Working Set (RAM ocupada pelo processo) deixa de variar de forma
         significativa durante o período de estabilidade configurado;
      4. existe uma janela top-level visível;
      5. a janela correta permanece em primeiro plano por uma pequena margem;
      6. depois disso, aplica-se o atraso de segurança configurado.

    O usuário controla apenas o tempo de estabilidade e o atraso de segurança.
    A tolerância de variação de memória é interna e serve apenas como sinal de
    acomodação do carregamento; não é um requisito de RAM mínima.
    """
    TH32CS_SNAPPROCESS = 0x00000002
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    _MEMORY_TOLERANCE_BYTES = 2 * 1024 * 1024
    _MEMORY_TOLERANCE_RATIO = 0.02
    _SAMPLE_INTERVAL = 0.10
    _FOREGROUND_STABLE = 0.15
    # O Windows pode impedir que uma thread de segundo plano force o foco em
    # determinados aplicativos (jogos, UWP, processos elevados etc.). Não
    # devemos transformar essa limitação em espera infinita: depois que a
    # janela do alvo existe e o processo atingiu estabilidade, damos uma
    # pequena janela adicional para ativação e seguimos com o input.
    _FOREGROUND_GRACE_AFTER_STABLE = 3.0

    def __init__(self) -> None:
        if os.name != "nt":
            raise RuntimeError("A espera por processo está disponível somente no Windows.")
        import ctypes
        from ctypes import wintypes
        self.ctypes = ctypes
        self.wintypes = wintypes
        self.kernel32 = ctypes.windll.kernel32
        self.user32 = ctypes.windll.user32
        self.SW_RESTORE = 9
        # Histórico de prontidão é mantido pelo ExecutionEngine. O watcher
        # recebe uma cópia/visão desse histórico apenas para otimizar a
        # frequência de amostragem; nunca é requisito para a detecção.
        self._readiness_history: dict[str, dict[str, float | int]] = {}
        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_void_p),
                ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260),
            ]
        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
            ]
        self.PROCESSENTRY32W = PROCESSENTRY32W
        self.PROCESS_MEMORY_COUNTERS = PROCESS_MEMORY_COUNTERS
        try:
            self._psapi = ctypes.WinDLL("psapi.dll")
            self._psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
            self._psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        except Exception:
            self._psapi = None

    def _find(self, exe_name: str) -> list[tuple[int, str]]:
        wanted = {Path(part.strip().strip('"')).name.lower() for part in str(exe_name).split(';') if part.strip()}
        wanted.discard('')
        if not wanted:
            return []
        snap = self.kernel32.CreateToolhelp32Snapshot(self.TH32CS_SNAPPROCESS, 0)
        invalid = self.ctypes.c_void_p(-1).value
        if snap == invalid:
            return []
        found=[]
        entry=self.PROCESSENTRY32W(); entry.dwSize=self.ctypes.sizeof(entry)
        try:
            ok=self.kernel32.Process32FirstW(snap, self.ctypes.byref(entry))
            while ok:
                exe=str(entry.szExeFile).lower()
                if exe in wanted:
                    found.append((int(entry.th32ProcessID), exe))
                ok=self.kernel32.Process32NextW(snap, self.ctypes.byref(entry))
        finally:
            self.kernel32.CloseHandle(snap)
        return found

    def _memory_bytes(self, pid: int) -> int | None:
        if not self._psapi or not pid:
            return None
        handle = self.kernel32.OpenProcess(self.PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not handle:
            return None
        counters = self.PROCESS_MEMORY_COUNTERS()
        counters.cb = self.ctypes.sizeof(counters)
        try:
            ok = self._psapi.GetProcessMemoryInfo(handle, self.ctypes.byref(counters), counters.cb)
            return int(counters.WorkingSetSize) if ok else None
        finally:
            self.kernel32.CloseHandle(handle)

    def _foreground_pid(self) -> int:
        hwnd = self.user32.GetForegroundWindow()
        if not hwnd:
            return 0
        pid = self.wintypes.DWORD(0)
        self.user32.GetWindowThreadProcessId(hwnd, self.ctypes.byref(pid))
        return int(pid.value)

    def _visible_window_for_pid(self, pid: int) -> int:
        found = {'hwnd': 0}
        WNDENUMPROC = self.ctypes.WINFUNCTYPE(self.wintypes.BOOL, self.wintypes.HWND, self.wintypes.LPARAM)
        def callback(hwnd, _lparam):
            if not self.user32.IsWindowVisible(hwnd):
                return True
            owner = self.wintypes.DWORD(0)
            self.user32.GetWindowThreadProcessId(hwnd, self.ctypes.byref(owner))
            if int(owner.value) != int(pid):
                return True
            # Não rejeitar janelas com owner: alguns aplicativos Windows modernos
            # usam uma cadeia de janelas/hosts durante a inicialização.
            if not self.user32.IsWindowEnabled(hwnd):
                return True
            found['hwnd'] = int(hwnd)
            return False
        self.user32.EnumWindows(WNDENUMPROC(callback), 0)
        return found['hwnd']

    def _try_activate(self, hwnd: int) -> bool:
        """Tenta transferir o foco de forma robusta no Windows.

        SetForegroundWindow sozinho pode ser recusado pelo Foreground Lock
        Timeout. Como a automação precisa enviar teclado globalmente, não
        basta a janela existir: ela precisa realmente receber foco.
        """
        if not hwnd:
            return False
        try:
            user32 = self.user32
            ctypes = self.ctypes
            user32.ShowWindow(hwnd, self.SW_RESTORE)
            try:
                user32.AllowSetForegroundWindow(0xFFFFFFFF)  # ASFW_ANY
            except Exception:
                pass
            try:
                user32.LockSetForegroundWindow(2)  # LSFW_UNLOCK
            except Exception:
                pass

            fg = user32.GetForegroundWindow()
            fg_tid = user32.GetWindowThreadProcessId(fg, None) if fg else 0
            target_tid = user32.GetWindowThreadProcessId(hwnd, None)
            attached = False
            if fg_tid and target_tid and fg_tid != target_tid:
                try:
                    attached = bool(user32.AttachThreadInput(fg_tid, target_tid, True))
                except Exception:
                    attached = False
            try:
                user32.BringWindowToTop(hwnd)
                user32.SetForegroundWindow(hwnd)
                user32.SetFocus(hwnd)
            finally:
                if attached:
                    try:
                        user32.AttachThreadInput(fg_tid, target_tid, False)
                    except Exception:
                        pass

            if self._foreground_pid() != 0:
                return self._foreground_pid() == self._window_pid(hwnd)
        except Exception:
            pass

        # Pequeno fallback conhecido para vencer o bloqueio de foreground:
        # simula um toque de ALT e tenta novamente.
        try:
            user32.keybd_event(0x12, 0, 0, 0)
            user32.keybd_event(0x12, 0, 2, 0)
            user32.ShowWindow(hwnd, self.SW_RESTORE)
            user32.SetForegroundWindow(hwnd)
        except Exception:
            pass
        return self._foreground_pid() == self._window_pid(hwnd)

    def _window_pid(self, hwnd: int) -> int:
        if not hwnd:
            return 0
        pid = self.wintypes.DWORD(0)
        try:
            self.user32.GetWindowThreadProcessId(hwnd, self.ctypes.byref(pid))
            return int(pid.value)
        except Exception:
            return 0

    def wait(self, exe_name: str, timeout: float, stable_ms: int, stop_event: threading.Event, expected_pid: int | None = None) -> tuple[int, str, float]:
        """Aguarda o aplicativo realmente ficar utilizável.

        Importante: o PID retornado por CreateProcess/Popen nem sempre é o
        processo que termina hospedando a janela de aplicativos modernos do
        Windows. Por isso, o PID esperado é uma preferência inicial, não uma
        prisão permanente. Se ele não possuir uma janela utilizável, fazemos
        fallback para outro processo com o mesmo executável.
        """
        started_at = time.monotonic()
        timeout_value = max(0.0, float(timeout))
        deadline = float("inf") if timeout_value <= 0 else started_at + timeout_value
        profile_key = Path(str(exe_name).split(";")[0].strip().strip(chr(34))).name.lower()
        learned = self._readiness_history.get(profile_key, {}) if isinstance(getattr(self, "_readiness_history", {}), dict) else {}
        stable_needed = max(0, int(stable_ms)) / 1000.0
        stable_since = None
        last_pid = 0
        last_exe = ''
        last_memory = None
        last_activation = 0.0
        foreground_since = None
        expected_grace_until = time.monotonic() + 2.0 if expected_pid else 0.0

        while time.monotonic() < deadline:
            if stop_event.is_set():
                raise ProcessReadinessError("Espera pelo aplicativo interrompida pelo usuário.")

            processes = self._find(exe_name)
            if not processes:
                stable_since = None; last_pid = 0; last_exe = ''; last_memory = None
                foreground_since = None; last_activation = 0.0
                stop_event.wait(self._SAMPLE_INTERVAL)
                continue

            # Prioriza o PID criado pelo Popen enquanto ele tiver uma janela;
            # caso contrário, permite escolher outro processo correspondente.
            ordered = []
            if expected_pid:
                ordered.extend([(p,e) for p,e in processes if p == int(expected_pid)])
            ordered.extend([(p,e) for p,e in processes if not expected_pid or p != int(expected_pid)])

            selected = None
            for candidate_pid, candidate_exe in ordered:
                hwnd = self._visible_window_for_pid(candidate_pid)
                if hwnd:
                    selected = (candidate_pid, candidate_exe, hwnd)
                    break
            if selected is None:
                # Ainda não há janela; mantemos o primeiro processo para que
                # a estabilidade de memória possa começar a ser observada.
                pid, exe = ordered[0]
                hwnd = 0
            else:
                pid, exe, hwnd = selected

            memory = self._memory_bytes(pid)
            memory_stable = True
            if last_pid != pid:
                stable_since = time.monotonic()
                last_pid = pid; last_exe = exe; last_memory = memory
                foreground_since = None; last_activation = 0.0
            else:
                if memory is not None and last_memory is not None:
                    delta = abs(memory - last_memory)
                    tolerance = max(self._MEMORY_TOLERANCE_BYTES, int(max(memory, last_memory) * self._MEMORY_TOLERANCE_RATIO))
                    memory_stable = delta <= tolerance
                if not memory_stable:
                    stable_since = time.monotonic()
                elif stable_since is None:
                    stable_since = time.monotonic()
                last_memory = memory

            stable_ok = bool(stable_since is not None and time.monotonic() - stable_since >= stable_needed and memory_stable)
            if stable_ok and hwnd:
                now = time.monotonic()
                fg_hwnd = self.user32.GetForegroundWindow()
                fg_ok = bool(fg_hwnd and (int(fg_hwnd) == int(hwnd) or self._foreground_pid() == pid))
                if not fg_ok:
                    if now - last_activation >= 0.20:
                        self._try_activate(hwnd)
                        last_activation = now
                    fg_hwnd = self.user32.GetForegroundWindow()
                    fg_ok = bool(fg_hwnd and (int(fg_hwnd) == int(hwnd) or self._foreground_pid() == pid))

                if fg_ok:
                    if foreground_since is None:
                        foreground_since = now
                    if now - foreground_since >= self._FOREGROUND_STABLE:
                        return pid, exe, max(0.0, now - started_at)
                else:
                    # Não exigir foco para sempre. A finalidade da barreira é
                    # detectar que o aplicativo está pronto; a tentativa de
                    # foco é uma etapa de segurança para entregar os inputs.
                    # Se o Windows negar SetForegroundWindow durante alguns
                    # segundos, uma janela visível + processo estável já é uma
                    # condição melhor do que deixar a automação aparentemente
                    # travada indefinidamente.
                    if foreground_since is None:
                        foreground_since = now
                    if now - foreground_since >= self._FOREGROUND_GRACE_AFTER_STABLE:
                        _append_runtime_log(
                            f"PROCESS_READY_FOREGROUND_FALLBACK exe={exe} pid={pid} "
                            f"grace={self._FOREGROUND_GRACE_AFTER_STABLE:.2f}s"
                        )
                        return pid, exe, max(0.0, now - started_at)
            else:
                foreground_since = None

            # Se o PID esperado não corresponde à janela real do aplicativo,
            # não ficamos presos nele: após uma pequena margem procuramos
            # qualquer instância do mesmo executável.
            if expected_pid and time.monotonic() >= expected_grace_until and pid == int(expected_pid) and not hwnd:
                expected_pid = None

            # Para aplicativos pesados, reduzimos a frequência de amostragem
            # quando já existe uma estimativa histórica. Não bloqueamos por
            # essa estimativa: a detecção continua ativa até a prontidão real.
            learned_seconds = float(learned.get("avg_ready_seconds", 0.0) or 0.0)
            sample = 0.10 if learned_seconds < 10 else (0.25 if learned_seconds < 60 else 0.50)
            stop_event.wait(sample)

        raise ProcessReadinessError(
            f"O aplicativo '{exe_name}' não ficou pronto para receber input dentro do limite de espera "
            f"de {timeout_value:.1f}s (estabilidade: {int(stable_ms)} ms + atraso de segurança configurado; "
            "janela ativa exigida)."
        )



class ExecutionEngine:
    def __init__(self, backend: InputBackend, state_manager: Optional[StateManager] = None, clock=None) -> None:
        self._backend = backend
        # `clock` precisa ter monotonic() e sleep(); os testes passam um relógio virtual.
        self._clock = clock if clock is not None else core.SystemClock()
        self.state = state_manager or StateManager()

        self._thread: Optional[threading.Thread] = None
        self._pause_event = threading.Event()
        self._pause_event.set()  # set = não pausado
        self._stop_requested = threading.Event()

        self._pressed_keys: set[str] = set()
        self._pressed_buttons: set[str] = set()
        self._lock = threading.RLock()

        self._current_map: Optional[AutomationMap] = None
        self._current_repeat: int = 0
        # Processos já considerados prontos nesta execução. Isso evita que um
        # comando TEXT imediatamente posterior a APP_OPEN repita a barreira de
        # 1s + 300ms desnecessariamente.
        self._ready_processes: dict[str, int] = {}
        # AS 21.1: perfil de inicialização por executável. Guarda somente
        # estatísticas; nunca substitui a detecção real de prontidão.
        self._readiness_history: dict[str, dict[str, float | int]] = {}
        self._adaptive_learning = True
        self._default_wait_timeout = 0.0
        self._readiness_save_callback: Callable[[dict], None] | None = None

        # Observadores (a UI se pluga aqui)
        self.on_event: list[Callable[[Event], None]] = []
        self.on_progress: list[Callable[[float, float], None]] = []  # (tempo_atual, tempo_total)
        self.on_error: list[Callable[[Exception], None]] = []
        self.on_finished: list[Callable[[], None]] = []
        # Emitido somente quando a automação chega ao fim naturalmente.
        # Nunca é emitido em STOP/EMERGENCY/erro.
        self.on_chain_requested: list[Callable[[str], None]] = []
        # Tempo (s) que o evento atual passou em barreiras; _play_timeline o soma ao relógio da timeline.
        self._barrier_elapsed = 0.0

    def configure_readiness(self, history: dict | None = None, default_timeout: float = 0.0, adaptive_learning: bool = True, save_callback: Callable[[dict], None] | None = None) -> None:
        """Configura a espera adaptativa sem impor RAM mínima."""
        self._readiness_history = dict(history) if isinstance(history, dict) else {}
        self._default_wait_timeout = max(0.0, float(default_timeout))
        self._adaptive_learning = bool(adaptive_learning)
        self._readiness_save_callback = save_callback

    # ---- API pública -----------------------------------------------------

    def run(self, automation_map: AutomationMap) -> None:
        """
        Inicia a execução de um mapa em uma nova thread.
        Se outro mapa já estiver rodando, ele é parado com segurança
        primeiro (execução exclusiva — item 9).
        """
        if not automation_map.commands:
            return
        errors = automation_map.validate()
        if errors:
            raise ValueError("Mapa inválido:\n" + "\n".join(errors))

        if self.state.state in (State.RUNNING, State.PAUSED):
            self.stop(wait=True)

        with self._lock:
            self._current_map = automation_map
        self._current_repeat = 0
        self._ready_processes.clear()
        self._stop_requested.clear()
        self._pause_event.set()

        self.state.transition_to(State.RUNNING)
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def pause(self) -> bool:
        """Pausa a execução. Devolve True se pausou; False se não havia execução em andamento (parado, gravando, parando ou
        já pausado) ou se ela terminou ou foi parada no mesmo instante (a tecla vem da thread da janela, o motor corre em
        outra). Nunca levanta `InvalidStateTransition`; uma pausa que não aconteceu não mexe na thread do motor."""
        if self.state.state != State.RUNNING:
            return False
        try:
            self.state.transition_to(State.PAUSED)
        except core.InvalidStateTransition:
            return False
        self._pause_event.clear()
        return True

    def resume(self) -> bool:
        """Continua a execução pausada, do ponto onde parou. Devolve True se continuou; False se não havia pausa ou se a
        execução foi parada no mesmo instante (quem para uma pausa é `stop`, que acorda a thread por conta própria)."""
        if self.state.state != State.PAUSED:
            return False
        try:
            self.state.transition_to(State.RUNNING)
        except core.InvalidStateTransition:
            return False
        self._pause_event.set()
        return True

    def stop(self, wait: bool = False) -> None:
        """
        Para a execução imediatamente e libera todas as teclas/botões
        pressionados (item 11: botão de emergência / item 25: erro
        nunca deixa a automação "morrer" com input preso).
        """
        if self.state.state in (State.IDLE,):
            return
        if self.state.state in (State.RUNNING, State.PAUSED):
            self.state.transition_to(State.STOPPING)
        self._stop_requested.set()
        self._pause_event.set()  # libera thread caso esteja pausada, para ela poder checar o stop

        if wait and self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=5)

        self._release_all()
        if self.state.state == State.STOPPING:
            self.state.transition_to(State.IDLE)

    def emergency_stop(self) -> None:
        """Botão/atalho de emergência (item 11): mesmo comportamento de
        stop(), mas nunca levanta exceção e sempre força volta a IDLE."""
        try:
            self.stop(wait=True)
        finally:
            self._release_all()
            if self.state.state != State.IDLE:
                self.state.force_to_idle()

    def is_running(self) -> bool:
        return self.state.state in (State.RUNNING, State.PAUSED)

    # ---- Loop interno (roda na thread de execução) -----------------------

    def _run_loop(self) -> None:
        assert self._current_map is not None
        automation_map = self._current_map
        timeline = build_timeline(automation_map)
        total_time = automation_map.total_duration()
        speed = automation_map.speed if automation_map.speed > 0 else 1.0

        try:
            while True:
                self._current_repeat += 1
                finished_cleanly = self._play_timeline(timeline, total_time, speed)
                if not finished_cleanly:
                    return  # stop foi pedido no meio da execução

                if automation_map.repeat_count != -1 and self._current_repeat >= automation_map.repeat_count:
                    break

                if self._stop_requested.is_set():
                    return

                if automation_map.repeat_interval > 0:
                    if not self._sleep_interruptible(automation_map.repeat_interval):
                        return

            self._finish(natural_end=True)

        except ProcessReadinessError as exc:
            # Interrupção solicitada pelo usuário durante uma barreira de
            # prontidão é um encerramento normal, não uma falha da automação.
            # A exceção é usada internamente para escapar imediatamente do
            # watcher, mas não deve chegar ao painel de erro quando o stop foi
            # realmente solicitado.
            self._release_all()
            if self._stop_requested.is_set():
                self.state.force_to_idle()
                return
            self.state.transition_to(State.ERROR)
            for cb in list(self.on_error):
                try:
                    cb(exc)
                except Exception:
                    pass
            self.state.force_to_idle()
        except Exception as exc:  # noqa: BLE001 - precisamos capturar qualquer erro de execução
            self._release_all()
            self.state.transition_to(State.ERROR)
            for cb in list(self.on_error):
                try:
                    cb(exc)
                except Exception:
                    pass
            self.state.force_to_idle()
        finally:
            # `stop()` solta só o que estava registrado como pressionado NAQUELE instante. Se a parada chegou
            # quando esta thread já tinha enviado a tecla mas ainda não a registrara, ela ficaria presa.
            # Ao sair por parada, esta thread solta o que sobrou (soltar de novo o que já foi solto é inofensivo).
            if self._stop_requested.is_set():
                try:
                    self._release_all()
                except Exception:
                    pass

    def _play_timeline(self, timeline: list[Event], total_time: float, speed: float) -> bool:
        """Executa uma passada pela timeline. Retorna False se foi interrompida."""
        engine_start = self._clock.monotonic()

        for event in timeline:
            target_elapsed = event.time / speed

            while True:
                if self._stop_requested.is_set():
                    return False

                # Pausa: congela o "relógio" da automação até ser retomada.
                if not self._pause_event.is_set():
                    pause_started = self._clock.monotonic()
                    self._pause_event.wait()
                    engine_start += (self._clock.monotonic() - pause_started)
                    continue

                now_elapsed = self._clock.monotonic() - engine_start
                remaining = target_elapsed - now_elapsed
                if remaining <= 0:
                    break
                self._clock.sleep(min(remaining, 0.02))  # granularidade fina, sem travar

            self._barrier_elapsed = 0.0
            self._apply_event(event)
            # A espera em barreira (condições V24, pausa durante a espera) desloca o relógio da timeline:
            # o comando mantém a duração planejada e os seguintes mantêm as lacunas planejadas.
            engine_start += self._barrier_elapsed
            for cb in list(self.on_progress):
                try:
                    cb(event.time, total_time)
                except Exception:
                    pass

        return True

    def _checkpoint(self) -> bool:
        """Ponto de pausa/parada antes de enviar input. Bloqueia enquanto pausado; False significa parar."""
        while not self._pause_event.is_set():
            if self._stop_requested.is_set():
                return False
            self._pause_event.wait(0.05)
        return not self._stop_requested.is_set()

    def _checkpoint_counted(self) -> bool:
        """Como `_checkpoint`, somando o tempo bloqueado ao relógio da timeline."""
        started = self._clock.monotonic()
        released = self._checkpoint()
        self._barrier_elapsed += self._clock.monotonic() - started
        return released

    def _apply_event(self, event: Event) -> None:
        # Condições V24: o tempo gasto nelas (e numa pausa feita durante a espera) é somado ao relógio da
        # timeline. A espera legada de processo (wait_process) NÃO é somada: o tempo previsto dela já está
        # embutido na timeline (ver decisão D2 do plano, Ponto 5).
        started = self._clock.monotonic()
        released = self._apply_wait_conditions(event) and self._checkpoint()
        self._barrier_elapsed += self._clock.monotonic() - started
        if not released:
            return
        if self._stop_requested.is_set():
            return
        # Barreiras de prontidão devem ocorrer ANTES do input dependente do alvo.
        # A implementação anterior esperava o processo depois de enviar o texto,
        # tornando a sincronização inócua para comandos TEXT.
        if event.kind == EventKind.WAIT:
            return
        if event.kind == EventKind.APP_OPEN:
            pid = self._launch_application(event.target)
            if event.wait_process:
                self._wait_for_process(event, expected_pid=pid)
                if not self._checkpoint_counted():
                    return
        elif event.wait_process:
            self._wait_for_process(event)
            if not self._checkpoint_counted():
                return

        if event.kind == EventKind.KEY_DOWN:
            self._backend.key_down(event.target)
            self._pressed_keys.add(event.target)
        elif event.kind == EventKind.KEY_UP:
            self._backend.key_up(event.target)
            self._pressed_keys.discard(event.target)
        elif event.kind == EventKind.MOUSE_DOWN:
            self._backend.mouse_down(event.target)
            self._pressed_buttons.add(event.target)
        elif event.kind == EventKind.MOUSE_UP:
            self._backend.mouse_up(event.target)
            self._pressed_buttons.discard(event.target)
        elif event.kind == EventKind.MOUSE_MOVE:
            self._backend.mouse_move(event.x or 0, event.y or 0, event.relative)
        elif event.kind == EventKind.MOUSE_SCROLL:
            self._backend.mouse_scroll(event.scroll_dx, event.scroll_dy)
        elif event.kind == EventKind.TEXT:
            _append_runtime_log(f"TEXT_INPUT chars={len(str(event.text or ''))} calculated_duration={calculate_text_duration(event.text):.3f}s char_interval={core.TEXT_CHAR_INTERVAL:.3f}s backend={type(self._backend).__name__}")
            # Um caractere por vez, consultando a parada entre eles: a parada de emergência interrompe
            # a digitação e `stop()` não precisa esperar o texto inteiro terminar.
            for char in str(event.text or ""):
                if self._stop_requested.is_set():
                    break
                self._backend.type_text(char)

        for cb in list(self.on_event):
            try:
                cb(event)
            except Exception:
                pass

    def _apply_wait_conditions(self, event: Event) -> bool:
        """Executa precondições V24 uma única vez antes do primeiro evento."""
        for condition in getattr(event, "wait_conditions", []) or []:
            if self._stop_requested.is_set():
                return False
            if condition.type == WaitConditionType.DELAY:
                seconds = max(0.0, float(condition.timeout or condition.after or 0.0))
                if seconds and not self._sleep_interruptible(seconds):
                    return False
            elif condition.type == WaitConditionType.PROCESS:
                process = str(condition.target or '').strip()
                command_id=str(condition.parameters.get('command_id','')).strip() if getattr(condition,'parameters',None) else ''
                if command_id and getattr(self, '_current_map', None) is not None:
                    target_cmd=next((c for c in self._current_map.commands if c.id==command_id), None)
                    if target_cmd is not None:
                        process=str(target_cmd.wait_process or target_cmd.target or process).strip()
                synthetic = Event(
                    time=event.time, kind=event.kind, target=event.target, command_id=event.command_id,
                    wait_process=process, wait_timeout=condition.timeout,
                    wait_stable_ms=condition.stable_ms, wait_after_open=condition.after,
                )
                if not process:
                    raise ProcessReadinessError('Comando de referência não possui um aplicativo/processo definido.')
                self._wait_for_process(synthetic)
            elif condition.type == WaitConditionType.IMAGE:
                params=getattr(condition,'parameters',{}) or {}
                result=wait_for_image(str(params.get('image_path','')), confidence=float(params.get('confidence',0.95) or 0.95), interval=float(params.get('interval',0.5) or 0.5), timeout=float(condition.timeout or 0.0), region=params.get('region') or None, stop_event=self._stop_requested, search=bool(params.get('search',False)))
                if not result.found:
                    if self._stop_requested.is_set():
                        return False
                    raise ProcessReadinessError(f'Imagem não encontrada dentro do tempo limite (similaridade final {result.similarity:.1%}).')
                try:
                    _append_runtime_log(f'IMAGE_READY path={params.get("image_path")} similarity={result.similarity:.3f} elapsed={result.elapsed:.3f}s')
                except Exception:
                    pass
        return True

    def _launch_application(self, target: str) -> int | None:
        if os.name != "nt":
            raise RuntimeError("Abertura de aplicativos está disponível nesta versão somente no Windows.")
        exe = str(target or "").strip().strip('"')
        if not exe:
            raise RuntimeError("Nenhum aplicativo foi definido para abrir.")
        try:
            # startfile respeita associações/atalhos do Windows quando o alvo é
            # um caminho ou recurso conhecido. Para executáveis simples,
            # Popen permite lançar sem criar um console adicional.
            proc = subprocess.Popen([exe], close_fds=True)
            return int(proc.pid)
        except Exception as exc:
            raise RuntimeError(f"Não foi possível abrir o aplicativo '{exe}': {exc}") from exc

    def _wait_for_process(self, event: Event, expected_pid: int | None = None) -> None:
        if os.name != "nt":
            raise ProcessReadinessError("Aguardo por processo só é suportado no Windows.")
        key = str(event.wait_process or '').strip().lower()
        # Se este mesmo processo já passou pela barreira nesta execução, não
        # reinicia o cronômetro. Isso é especialmente importante para
        # APP_OPEN -> TEXT, em que o texto deve aproveitar a prontidão já
        # confirmada do aplicativo.
        cached_pid = self._ready_processes.get(key) if key else None
        if cached_pid and expected_pid is None:
            try:
                watcher = WindowsProcessReadiness()
                current = watcher._find(event.wait_process)
                if any(pid == cached_pid for pid, _ in current):
                    return
            except Exception:
                self._ready_processes.pop(key, None)

        watcher=WindowsProcessReadiness()
        # O histórico pertence ao engine (onde é persistido). Entregamos ao
        # watcher somente a referência atual para que a amostragem adaptativa
        # funcione sem duplicar o estado.
        watcher._readiness_history = self._readiness_history
        requested_timeout = float(event.wait_timeout or self._default_wait_timeout or 0.0)
        # 0 significa sem limite. Isso é deliberado para aplicativos que
        # podem levar minutos para iniciar.
        pid,exe,ready_seconds=watcher.wait(event.wait_process, requested_timeout, event.wait_stable_ms, self._stop_requested, expected_pid=expected_pid)
        self._ready_processes[key] = pid if key else pid
        if self._adaptive_learning and key:
            old = self._readiness_history.get(key, {})
            samples = int(old.get("samples", 0) or 0)
            avg = float(old.get("avg_ready_seconds", 0.0) or 0.0)
            new_avg = ready_seconds if samples <= 0 else ((avg * min(samples, 19)) + ready_seconds) / (min(samples, 19) + 1)
            self._readiness_history[key] = {"avg_ready_seconds": round(new_avg, 3), "last_ready_seconds": round(ready_seconds, 3), "samples": min(samples + 1, 20)}
            if self._readiness_save_callback:
                try: self._readiness_save_callback(dict(self._readiness_history))
                except Exception: pass
        if event.wait_after_open > 0 and not self._sleep_interruptible(event.wait_after_open):
            raise ProcessReadinessError("Espera pós-abertura interrompida pelo usuário.")
        try:
            _append_runtime_log(f"PROCESS_READY requested={event.wait_process} matched={exe} pid={pid} stable_ms={event.wait_stable_ms} post_delay={event.wait_after_open:.2f}s ready_seconds={ready_seconds:.3f}s cached=no")
        except Exception:
            pass

    def _sleep_interruptible(self, seconds: float) -> bool:
        """Dorme em pequenos pedaços checando stop/pause. Retorna False se interrompido."""
        end = self._clock.monotonic() + seconds
        while self._clock.monotonic() < end:
            if self._stop_requested.is_set():
                return False
            if not self._pause_event.is_set():
                self._pause_event.wait()
                continue
            remaining = end - self._clock.monotonic()
            if remaining > 0:
                self._clock.sleep(min(0.02, remaining))
        return True

    def _finish(self, natural_end: bool) -> None:
        self._release_all()
        if self.state.state in (State.RUNNING, State.PAUSED, State.STOPPING):
            if self.state.state != State.STOPPING:
                self.state.transition_to(State.STOPPING)
            self.state.transition_to(State.IDLE)
        for cb in list(self.on_finished):
            try:
                cb()
            except Exception:
                pass

        # O encadeamento só acontece após um término natural. Guardamos o
        # nome antes de liberar a referência para evitar efeitos de corrida.
        if natural_end and self._current_map is not None and self._current_map.next_map:
            next_name = self._current_map.next_map
            for cb in list(self.on_chain_requested):
                try:
                    cb(next_name)
                except Exception:
                    pass

    def _release_all(self) -> None:
        self._backend.release_all(self._pressed_keys, self._pressed_buttons)
        self._pressed_keys.clear()
        self._pressed_buttons.clear()

@dataclass
class RecorderFilters:
    """
    Item 16 do roteiro: "o gravador não deve gravar tudo cegamente".

    Os padrões seguem a lista de checkboxes do roteiro: teclado, mouse
    e cliques ligados por padrão; movimento do mouse e scroll
    desligados por padrão (ligar gera muito ruído na maioria dos
    mapas). `ignored_keys` / `ignored_mouse_buttons` evitam que o
    próprio atalho de gravar/parar ou o atalho de emergência acabem
    virando comandos gravados dentro do mapa.
    """

    capture_keyboard: bool = True
    capture_mouse_buttons: bool = True
    capture_mouse_move: bool = True
    capture_mouse_scroll: bool = True
    record_key_duration: bool = True  # se False, toda duração gravada vira 0.0
    merge_mouse_moves: bool = True
    mouse_jitter_px: int = 3
    mouse_sample_interval_ms: int = 8

    ignored_keys: frozenset[str] = field(default_factory=frozenset)
    ignored_mouse_buttons: frozenset[str] = field(default_factory=frozenset)

@dataclass
class _OpenPress:
    start: float

class RecorderError(RuntimeError):
    """Erro ao tentar iniciar uma gravação em um estado inválido."""

class Recorder:
    """
    Grava, em tempo real, teclas e botões do mouse pressionados pelo
    usuário e os converte em `Command`s com `start`/`duration` já
    calculados e agrupados (item 32: "pensar em eventos temporais").

    Segue a mesma máquina de estados do resto do programa (item 22):
    só é possível começar a gravar a partir de IDLE, e gravar
    transiciona para RECORDING -- o que automaticamente impede
    "gravando + executando" ao mesmo tempo (item 9) quando o mesmo
    `StateManager` é compartilhado com o `ExecutionEngine`.
    """

    def __init__(
        self,
        monitor,
        state_manager: Optional[StateManager] = None,
        filters: Optional[RecorderFilters] = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.monitor = monitor
        self.state = state_manager or StateManager()
        self.filters = filters or RecorderFilters()
        self._clock = clock

        self._recording = False
        self._paused = False
        self._pause_started = 0.0
        self._paused_total = 0.0
        self._lock = threading.RLock()
        self._start_time = 0.0
        self._open_presses: dict[tuple[InputType, str], _OpenPress] = {}
        self._finished_commands: list[Command] = []
        self._active_mouse_move: dict[str, Any] | None = None
        self._event_count = 0

        # Bound closures guardadas para poder remover exatamente as
        # mesmas referências das listas do monitor em stop()/cancel().
        self._key_cb = lambda name, pressed: self._on_key(name, pressed)
        self._mouse_button_cb = lambda name, pressed: self._on_mouse_button(name, pressed)
        self._mouse_scroll_cb = lambda dx, dy: self._on_mouse_scroll(dx, dy)
        self._mouse_move_cb = lambda x, y: self._on_mouse_move(x, y)

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def event_count(self) -> int:
        return self._event_count

    @property
    def is_paused(self) -> bool:
        return self._paused

    def _elapsed(self) -> float:
        now = self._clock()
        paused = self._paused_total
        if self._paused:
            paused += max(0.0, now - self._pause_started)
        return max(0.0, now - self._start_time - paused)

    def pause(self) -> None:
        if not self._recording or self._paused:
            return
        with self._lock:
            self._paused = True
            self._pause_started = self._clock()
            # Fechar pressões abertas no instante da pausa evita registrar
            # acidentalmente o tempo em que a captura estava pausada.
            now = self._elapsed()
            for (input_type, target), open_press in list(self._open_presses.items()):
                self._append_command(input_type, target, open_press.start, now)
            self._open_presses.clear()

    def resume(self) -> None:
        if not self._recording or not self._paused:
            return
        with self._lock:
            self._paused_total += max(0.0, self._clock() - self._pause_started)
            self._pause_started = 0.0
            self._paused = False

    def snapshot_commands(self) -> list[Command]:
        """Retorna uma fotografia segura dos comandos confirmados + pressões ativas."""
        if not self._recording:
            return []
        with self._lock:
            commands = copy.deepcopy(self._finished_commands)
            now = self._elapsed()
            for (input_type, target), open_press in self._open_presses.items():
                commands.append(Command(type=input_type, target=target, action=ActionType.PRESS_AND_RELEASE,
                                        start=open_press.start, duration=max(0.0, now-open_press.start)))
            if self._active_mouse_move and self._active_mouse_move.get("points"):
                seg = self._active_mouse_move
                dur = max(0.001, now - float(seg["start"]))
                pts = self._simplify_mouse_path(self._points_with_pending(seg), float(self.filters.mouse_jitter_px))
                path=[{"t":max(0.0,min(1.0,(float(t)-float(seg["start"])) / dur)),"x":int(x),"y":int(y)} for t,x,y in pts]
                commands.append(Command(type=InputType.MOUSE_MOVE, action=ActionType.PRESS_AND_RELEASE, start=float(seg["start"]), duration=dur, x=path[0]["x"], y=path[0]["y"], mouse_path=path, merged_move=True, description="Movimento do mouse (mesclado)"))
            commands.sort(key=lambda c: c.start)
            return commands

    # ---- Controle ---------------------------------------------------

    def start(self) -> None:
        """Começa a gravar. Levanta `RecorderError` se o programa não
        estiver em IDLE (execução exclusiva -- item 9/22)."""
        if self._recording:
            return
        if self.state.state != State.IDLE:
            raise RecorderError(
                f"Não é possível gravar com o programa em estado "
                f"'{self.state.state.value}' (execução exclusiva -- item 9/22 do roteiro)."
            )
        self.state.transition_to(State.RECORDING)

        self._open_presses.clear()
        self._finished_commands = []
        self._active_mouse_move = None
        self._event_count = 0
        self._start_time = self._clock()
        self._recording = True
        self._paused = False
        self._pause_started = 0.0
        self._paused_total = 0.0

        self.monitor.on_key.append(self._key_cb)
        self.monitor.on_mouse_button.append(self._mouse_button_cb)
        self.monitor.on_mouse_scroll.append(self._mouse_scroll_cb)
        move_list = getattr(self.monitor, "on_mouse_move", None)
        if move_list is not None:
            move_list.append(self._mouse_move_cb)

        if not self.monitor.is_running():
            self.monitor.start()

    def stop(self) -> list[Command]:
        """
        Para a gravação e devolve os `Command`s prontos, já ordenados
        por início e com grupos atribuídos automaticamente por
        sobreposição (item 32).

        Qualquer tecla/botão ainda "pendurado" (pressionado e nunca
        solto até aqui) é fechado no instante da parada -- mesma
        filosofia do item 25 ("nunca deixar tecla presa").
        """
        if not self._recording:
            return []
        with self._lock:
            if self._paused:
                self._paused_total += max(0.0, self._clock() - self._pause_started)
                self._pause_started = 0.0
                self._paused = False
            self._recording = False
        self._detach_callbacks()

        now = self._elapsed()
        self._finalize_mouse_move(now)
        for (input_type, target), open_press in list(self._open_presses.items()):
            self._append_command(input_type, target, open_press.start, now)
        self._open_presses.clear()

        commands = self._finished_commands
        self._finished_commands = []

        self._assign_groups(commands)
        commands.sort(key=lambda c: c.start)

        if self.state.state == State.RECORDING:
            self.state.transition_to(State.IDLE)

        return commands

    def cancel(self) -> None:
        """Descarta a gravação em andamento sem devolver nenhum Command."""
        if not self._recording:
            return
        self._recording = False
        self._paused = False
        self._pause_started = 0.0
        self._paused_total = 0.0
        self._detach_callbacks()
        self._open_presses.clear()
        self._finished_commands = []
        self._active_mouse_move = None
        if self.state.state == State.RECORDING:
            self.state.transition_to(State.IDLE)

    def _detach_callbacks(self) -> None:
        for lst, cb in (
            (self.monitor.on_key, self._key_cb),
            (self.monitor.on_mouse_button, self._mouse_button_cb),
            (self.monitor.on_mouse_scroll, self._mouse_scroll_cb),
        ):
            if cb in lst:
                lst.remove(cb)
        move_list = getattr(self.monitor, "on_mouse_move", None)
        if move_list is not None and self._mouse_move_cb in move_list:
            move_list.remove(self._mouse_move_cb)

    @staticmethod
    def _points_with_pending(seg: dict) -> list:
        """Pontos do trajeto, incluindo a última amostra descartada pelo intervalo (se diferir do último ponto)."""
        points = list(seg.get("points", []))
        pending = seg.get("pending")
        if pending and points and (pending[1], pending[2]) != (points[-1][1], points[-1][2]):
            points.append(pending)
        return points

    def _finalize_mouse_move(self, end_time: float | None = None) -> None:
        """Fecha o bloco de movimento atual e o transforma em um único comando.

        O percurso é armazenado com tempo normalizado (0..1), permitindo que o
        usuário aumente ou reduza a duração do bloco na timeline sem perder a
        trajetória original.
        """
        seg = self._active_mouse_move
        if not seg:
            return
        points = self._points_with_pending(seg)
        if not points:
            self._active_mouse_move = None
            return
        end = self._elapsed() if end_time is None else max(float(end_time), float(seg["start"]))
        duration = max(0.001, end - float(seg["start"]))
        # Sempre conservar o primeiro e último ponto.
        cleaned = self._simplify_mouse_path(points, float(self.filters.mouse_jitter_px))
        path = []
        for t, x, y in cleaned:
            nt = max(0.0, min(1.0, (float(t) - float(seg["start"])) / duration))
            path.append({"t": nt, "x": int(x), "y": int(y)})
        if path[-1]["t"] < 1.0:
            last = path[-1]
            path.append({"t": 1.0, "x": int(last["x"]), "y": int(last["y"])})
        first = path[0]
        self._finished_commands.append(Command(
            type=InputType.MOUSE_MOVE, target="", action=ActionType.PRESS_AND_RELEASE,
            start=float(seg["start"]), duration=duration, x=int(first["x"]), y=int(first["y"]),
            relative=False, mouse_path=path, merged_move=True,
            description="Movimento do mouse (mesclado)",
        ))
        self._active_mouse_move = None

    @staticmethod
    def _simplify_mouse_path(points: list[tuple[float, int, int]], tolerance: float) -> list[tuple[float, int, int]]:
        """Remove jitter e pontos redundantes usando distância + RDP.

        O filtro é deliberadamente conservador: ele só remove pontos que não
        mudam a trajetória perceptivelmente, preservando os extremos para que
        arrastos continuem chegando exatamente ao destino.
        """
        if len(points) <= 2:
            return points
        tol = max(0.0, float(tolerance))
        filtered = [points[0]]
        for p in points[1:-1]:
            prev = filtered[-1]
            if math.hypot(p[1] - prev[1], p[2] - prev[2]) >= tol:
                filtered.append(p)
        filtered.append(points[-1])
        if len(filtered) <= 2 or tol <= 0:
            return filtered

        def perpendicular_distance(p, a, b):
            x, y = p[1], p[2]; ax, ay = a[1], a[2]; bx, by = b[1], b[2]
            dx, dy = bx-ax, by-ay
            if dx == 0 and dy == 0:
                return math.hypot(x-ax, y-ay)
            u = ((x-ax)*dx + (y-ay)*dy) / float(dx*dx + dy*dy)
            u = max(0.0, min(1.0, u))
            qx, qy = ax + u*dx, ay + u*dy
            return math.hypot(x-qx, y-qy)

        def rdp(seq):
            if len(seq) <= 2: return seq
            best_i, best_d = 0, 0.0
            for i in range(1, len(seq)-1):
                d = perpendicular_distance(seq[i], seq[0], seq[-1])
                if d > best_d: best_i, best_d = i, d
            if best_d > tol:
                return rdp(seq[:best_i+1])[:-1] + rdp(seq[best_i:])
            return [seq[0], seq[-1]]
        return rdp(filtered)

    # ---- Callbacks (podem chegar da thread do pynput) -----------------

    def _on_key(self, name: str, pressed: bool) -> None:
        if not self._recording or self._paused or not self.filters.capture_keyboard:
            return
        if name in self.filters.ignored_keys:
            return
        if pressed and self.filters.merge_mouse_moves:
            self._finalize_mouse_move()
        self._handle_press_release(InputType.KEY, name, pressed)

    def _on_mouse_button(self, name: str, pressed: bool) -> None:
        if not self._recording or self._paused or not self.filters.capture_mouse_buttons:
            return
        name = str(name).lower()
        if name in self.filters.ignored_mouse_buttons:
            return
        if pressed and self.filters.merge_mouse_moves:
            self._finalize_mouse_move()
        self._handle_press_release(InputType.MOUSE_BUTTON, name, pressed)

    def _on_mouse_scroll(self, dx: int, dy: int) -> None:
        if not self._recording or self._paused or not self.filters.capture_mouse_scroll:
            return
        t = self._elapsed()
        self._event_count += 1
        self._finished_commands.append(Command(
            type=InputType.MOUSE_SCROLL,
            action=ActionType.PRESS,
            start=t,
            duration=0.0,
            scroll_dx=dx,
            scroll_dy=dy,
        ))

    def _on_mouse_move(self, x: int, y: int) -> None:
        if not self._recording or self._paused or not self.filters.capture_mouse_move:
            return
        t = self._elapsed()
        self._event_count += 1
        if not self.filters.merge_mouse_moves:
            self._finished_commands.append(Command(type=InputType.MOUSE_MOVE, action=ActionType.PRESS, start=t, duration=0.0, x=x, y=y, relative=False))
            return

        seg = self._active_mouse_move
        if seg is None:
            self._active_mouse_move = {"start": t, "last_t": t, "last_x": int(x), "last_y": int(y),
                                       "points": [(t, int(x), int(y))]}
            return
        min_px = max(0, int(self.filters.mouse_jitter_px))
        min_dt = max(0.0, int(self.filters.mouse_sample_interval_ms) / 1000.0)
        dx = int(x) - int(seg["last_x"]); dy = int(y) - int(seg["last_y"])
        dt = t - float(seg["last_t"])
        if math.hypot(dx, dy) < min_px:
            return  # tremor: abaixo do limite de pixels
        if dt < min_dt:
            # Dentro do intervalo de amostragem: guarda só a amostra mais recente. Se o movimento terminar
            # aqui, ela vira o último ponto do trajeto e o cursor não para antes do lugar onde parou.
            seg["pending"] = (t, int(x), int(y))
            return
        seg["points"].append((t, int(x), int(y)))
        seg["last_t"], seg["last_x"], seg["last_y"] = t, int(x), int(y)
        seg.pop("pending", None)

    # ---- Conversão pressionar/soltar -> Command ------------------------

    def _handle_press_release(self, input_type: InputType, target: str, pressed: bool) -> None:
        key = (input_type, target)
        t = self._elapsed()

        if pressed:
            # Auto-repeat do SO manda vários KEYDOWN enquanto a tecla
            # fica presa -- só o primeiro conta como início.
            self._open_presses.setdefault(key, _OpenPress(start=t))
            return

        open_press = self._open_presses.pop(key, None)
        if open_press is None:
            # Soltou algo cuja pressão não foi capturada (começou antes
            # da gravação, por exemplo) -- sem início confiável, ignora.
            return
        self._append_command(input_type, target, open_press.start, t)

    def _append_command(self, input_type: InputType, target: str, start: float, end: float) -> None:
        duration = max(0.0, end - start)
        if not self.filters.record_key_duration:
            duration = 0.0
        self._event_count += 1
        self._finished_commands.append(Command(
            type=input_type,
            target=target,
            action=ActionType.PRESS_AND_RELEASE,
            start=start,
            duration=duration,
        ))

    # ---- Agrupamento automático (item 32) -------------------------------

    @staticmethod
    def _assign_groups(commands: list[Command]) -> None:
        """
        Atribui letras de grupo (A, B, C, ..., Z, AA, AB, ...) a
        comandos cujos intervalos [effective_start, effective_end] se
        sobrepõem -- a mesma ideia do item 5 ("comandos do mesmo grupo
        podem executar simultaneamente"), só que descoberta
        automaticamente a partir do que foi gravado, em vez de
        digitada manualmente pelo usuário.

        Isso não afeta a execução (o `ExecutionEngine`/`scheduler` só
        olham `start`/`duration`) -- é só metadado para a tabela e a
        timeline mostrarem visualmente quais comandos formam um
        "bloco" gravado junto (ex.: SHIFT segurado enquanto E é
        pressionado).
        """
        def letter(n: int) -> str:
            result = ""
            n += 1
            while n > 0:
                n, rem = divmod(n - 1, 26)
                result = chr(ord("A") + rem) + result
            return result

        ordered = sorted(commands, key=lambda c: c.effective_start)
        group_ends: list[float] = []

        for cmd in ordered:
            placed = False
            for idx, end in enumerate(group_ends):
                if cmd.effective_start < end:
                    cmd.group = letter(idx)
                    group_ends[idx] = max(end, cmd.effective_end)
                    placed = True
                    break
            if not placed:
                cmd.group = letter(len(group_ends))
                group_ends.append(cmd.effective_end)

def _default_backend():
    """Seleciona o backend de execução mais adequado.

    No Windows, prioriza USER32.SendInput. O pynput fica como fallback.
    Em outros sistemas, usa pynput e, por último, mock.
    """
    if os.name == "nt":
        try:
            return Win32InputBackend()
        except Exception:
            pass
    try:
        return PynputInputBackend()
    except Exception:
        return MockInputBackend()

# Export shared private helpers used by the UI layer. Python excludes
# underscore-prefixed names from `from .input_system import *` unless __all__
# explicitly includes them. The modular UI historically consumes this helper.
__all__ = [name for name in globals() if not name.startswith("__")]
