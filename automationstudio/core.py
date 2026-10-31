from __future__ import annotations


from abc import ABC, abstractmethod

from dataclasses import dataclass, field, replace

from datetime import datetime

from enum import Enum

from pathlib import Path

from typing import Any, Optional, Callable

import sys

import os

import traceback

import copy

import re
import threading

import math

import itertools

import time

import json

import sqlite3

import subprocess

from .conditions import WaitCondition, WaitConditionType

from PySide6.QtCore import Qt, QTimer, Signal, QRect, QRectF, QPoint, QEvent, QObject, QPointF, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup

from PySide6.QtGui import QAction, QIcon, QColor, QFont, QPainter, QPainterPath, QPen, QFontMetrics, QMouseEvent, QGuiApplication, QCursor, QKeySequence, QPalette, QPixmap

from PySide6.QtWidgets import QWidget, QPushButton, QVBoxLayout, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QSpinBox, QFormLayout, QLabel, QMessageBox, QLineEdit, QTabWidget, QApplication, QAbstractItemView, QColorDialog, QHBoxLayout, QHeaderView, QInputDialog, QMenu, QTableWidget, QStackedWidget, QTableWidgetItem, QStyledItemDelegate, QListWidget, QListWidgetItem, QTextEdit, QFileDialog, QProgressBar, QToolBar, QScrollArea, QSizePolicy, QMainWindow, QSplitter, QFrame, QStatusBar, QTabBar


# Shared constants and runtime helpers.


TEXT_CHAR_INTERVAL = 0.01

APP_STABLE_DEFAULT_MS = 1000

APP_AFTER_OPEN_DEFAULT = 0.300

class SystemClock:
    """Relógio real. Motor, gravador e backend Mock aceitam outro relógio (os testes usam um virtual)."""

    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class _IdCounter:
    """Contador de IDs seguro entre threads. `next(_id_counter)` continua funcionando em qualquer módulo.

    O gravador cria comandos na thread do pynput enquanto a janela carrega mapas na thread da GUI;
    `advance_past` permite que mapas salvos em sessões anteriores nunca colidam com IDs novos.
    """

    def __init__(self, start: int = 1) -> None:
        self._next = start
        self._lock = threading.Lock()

    def __iter__(self):
        return self

    def __next__(self) -> int:
        with self._lock:
            value = self._next
            self._next += 1
            return value

    def advance_past(self, value: int) -> None:
        with self._lock:
            if value >= self._next:
                self._next = value + 1


_id_counter = _IdCounter(1)

_SPECIAL_KEY_NAMES: dict[str, str] = {
    "shift": "SHIFT", "shift_l": "SHIFT", "shift_r": "SHIFT",
    "ctrl": "CTRL", "ctrl_l": "CTRL", "ctrl_r": "CTRL",
    "alt": "ALT", "alt_l": "ALT", "alt_r": "ALT", "alt_gr": "ALTGR",
    "enter": "ENTER", "esc": "ESC", "tab": "TAB", "space": "SPACE",
    "backspace": "BACKSPACE", "caps_lock": "CAPSLOCK",
    "up": "UP", "down": "DOWN", "left": "LEFT", "right": "RIGHT",
    "print_screen": "PRINTSCREEN", "scroll_lock": "SCROLLLOCK",
    "pause": "PAUSE", "insert": "INSERT", "home": "HOME",
    "page_up": "PAGEUP", "delete": "DELETE", "end": "END",
    "page_down": "PAGEDOWN", "num_lock": "NUMLOCK",
    "cmd": "WIN", "cmd_l": "WIN", "cmd_r": "WIN", "menu": "MENU",
    **{f"f{i}": f"F{i}" for i in range(1, 13)},
}

FORMAT_VERSION = 1
APP_VERSION = "25.6"
COMMAND_EXPORT_VERSION = 1

# O pacote modular fica em <raiz>/automationstudio/, enquanto os recursos
# continuam em <raiz>/resources/. Em versões congeladas (_MEIPASS), os recursos
# ficam diretamente na raiz do bundle.
if getattr(sys, '_MEIPASS', None):
    _RESOURCE_BASE = Path(sys._MEIPASS)
else:
    _RESOURCE_BASE = Path(__file__).resolve().parent.parent

_LAYOUT_PATH = _RESOURCE_BASE / 'resources' / 'keyboard_layout.json'

_F_KEYS = {f"F{i}": [f"F{i}"] for i in range(1, 13)}

_SPECIAL = {
    "SHIFT": ["ShiftLeft", "ShiftRight"], "SHIFTLEFT": ["ShiftLeft"], "SHIFTRIGHT": ["ShiftRight"],
    "CTRL": ["CtrlLeft", "CtrlRight"], "CTRLLEFT": ["CtrlLeft"], "CTRLRIGHT": ["CtrlRight"],
    "ALT": ["Alt"], "ALTGR": ["AltGr"], "ENTER": ["Enter"], "RETURN": ["Enter"],
    "ESC": ["Esc"], "ESCAPE": ["Esc"], "TAB": ["Tab"], "SPACE": ["Space"],
    "BACKSPACE": ["Backspace"], "CAPSLOCK": ["CapsLock"], "UP": ["Up"], "DOWN": ["Down"],
    "LEFT": ["Left"], "RIGHT": ["Right"], "PRINTSCREEN": ["PrintScreen"],
    "SCROLLLOCK": ["ScrollLock"], "PAUSE": ["Pause"], "INSERT": ["Insert"], "HOME": ["Home"],
    "PAGEUP": ["PageUp"], "DELETE": ["Delete"], "END": ["End"], "PAGEDOWN": ["PageDown"],
    "NUMLOCK": ["NumLock"], "WIN": ["Win"], "MENU": ["Menu"], "FN": ["Fn"],
    "VOLUME_UP": [], "VOLUME_DOWN": [], "VOLUME_MUTE": [],
}

_NUMPAD = {f"NUM{i}": [f"Num{i}"] for i in range(10)}

_DISPLAY={"ShiftLeft":"Shift","ShiftRight":"Shift","CtrlLeft":"Ctrl","CtrlRight":"Ctrl","PrintScreen":"PrtSc","ScrollLock":"ScrLk","PageUp":"PgUp","PageDown":"PgDn","Up":"↑","Down":"↓","Left":"←","Right":"→","NumLock":"Num","NumEnter":"Enter","NumDel":",","Ç":"Ç"}

_LONG={"Backspace","CapsLock","ShiftLeft","ShiftRight","CtrlLeft","CtrlRight","Space","Enter","NumEnter","PrintScreen","ScrollLock","PageUp","PageDown","Delete","Insert","NumLock"}

_COLUMNS = ["#", "O que fazer", "Tecla / botão", "Começa em", "Duração"]

_ROW_H = 34.0

_RULER_H = 28.0

_LABEL_W = 160.0

_LEFT_PAD = 8.0

_MIN_SECONDS_VISIBLE = 5.0

_RESIZE_HANDLE_PX = 8.0

_MIN_DURATION = 0.05

# Diferença de tempo abaixo da qual dois inícios são "o mesmo" (1 ns): só serve para não regravar um início que já está certo.
_TIME_EPSILON = 1e-9

_DEFAULT_PPS = 90.0

_MIN_PPS = 12.0

_MAX_PPS = 400.0

_COLOR_BG = QColor("#14171c")

_COLOR_ROW_ALT = QColor("#191d23")

_COLOR_GRID = QColor("#242a32")

_COLOR_GRID_STRONG = QColor("#343c47")

_COLOR_RULER_BG = QColor("#1a1d23")

_COLOR_LABEL = QColor("#c2c9d3")

_COLOR_LABEL_DISABLED = QColor("#5f6977")

_COLOR_UNGROUPED = QColor("#4a525e")

_COLOR_UNGROUPED_BORDER = QColor("#7d8796")

_COLOR_ACTIVE = QColor("#ffc53d")

_COLOR_ACTIVE_BORDER = QColor("#ffdd8a")

_COLOR_SELECTED_BORDER = QColor("#ffffff")

_COLOR_PLAYHEAD = QColor("#ff5f56")

_GROUP_PALETTE = [
    QColor("#4f8fda"), QColor("#57b894"), QColor("#c97fd4"),
    QColor("#e0894f"), QColor("#5fc2c9"), QColor("#9d8cf0"),
    QColor("#d4607f"), QColor("#8bc34a"),
]

class State(str, Enum):
    IDLE = "idle"
    RECORDING = "recording"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"

_STATE_LABELS = {
    State.IDLE: "● PARADO",
    State.RECORDING: "● GRAVANDO",
    State.RUNNING: "● EXECUTANDO",
    State.PAUSED: "● PAUSADO",
    State.STOPPING: "● PARANDO...",
    State.ERROR: "■ ERRO",
}

_SINGLE_INSTANCE_HANDLE = None

def calculate_text_duration(text: str, interval: float | None = None) -> float:
    """Calcula o tempo previsto de uma ação de texto.

    O backend envia cada caractere individualmente e aplica o intervalo
    configurado depois de cada caractere. Portanto, o tempo planejado usa
    len(text) * intervalo. O tempo real pode ser ligeiramente maior devido
    ao custo do sistema/aplicativo receptor, e o executor respeita esse
    tempo real antes de liberar os comandos seguintes.
    """
    value = TEXT_CHAR_INTERVAL if interval is None else float(interval)
    return max(0.0, len(str(text or "")) * max(0.0, value))

def calculate_app_readiness_base(command: "Command") -> float:
    """Atraso mínimo conhecido após a abertura de um aplicativo.

    O tempo de aparecimento do processo é variável e não pode ser conhecido
    antes da execução. Esta função representa somente a parte determinística:
    estabilidade configurada + atraso de segurança. A espera real pelo
    processo continua sendo feita pelo WindowsProcessReadiness.
    """
    return max(0.0, float(getattr(command, "wait_stable_ms", 0)) / 1000.0) + max(0.0, float(getattr(command, "wait_after_open", 0.0)))

def _append_runtime_log(message: str) -> None:
    """Acrescenta uma linha ao log unificado da execução, sem criar outro arquivo."""
    try:
        base=Path(sys.argv[0]).resolve().parent
        log_dir=base/'logs'; log_dir.mkdir(parents=True,exist_ok=True)
        with (log_dir/'AutomationStudio.log').open('a',encoding='utf-8') as f:
            f.write(f"[{datetime.now().isoformat(timespec='seconds')}] {message}\n")
    except Exception:
        pass

class InputType(str, Enum):
    KEY = "key"
    MOUSE_BUTTON = "mouse_button"
    MOUSE_MOVE = "mouse_move"
    MOUSE_SCROLL = "mouse_scroll"
    TEXT = "text"
    APP_OPEN = "app_open"
    WAIT = "wait"

class ActionType(str, Enum):
    PRESS = "press"                    # KEYDOWN e mantém
    RELEASE = "release"                # KEYUP isolado
    PRESS_AND_RELEASE = "press_and_release"

class CommandValidationError(ValueError):
    """Erro de validação de um Command individual."""

def _next_id() -> str:
    return f"cmd_{next(_id_counter):06d}"

_ID_NUMBER = re.compile(r"(?:cmd|grp)_(\d+)")

def _sync_id_counter(ids) -> None:
    """Garante que IDs novos nunca colidam com IDs já existentes (mapa salvo em sessão anterior)."""
    highest = 0
    for raw in ids:
        match = _ID_NUMBER.fullmatch(str(raw or ""))
        if match:
            highest = max(highest, int(match.group(1)))
    if highest:
        _id_counter.advance_past(highest)

def set_runtime_defaults(text_char_interval=None, app_stable_ms=None, app_after_open=None) -> None:
    """Único ponto que altera os padrões de execução em tempo de execução.

    Os demais módulos leem `core.TEXT_CHAR_INTERVAL` etc. no momento do uso. Um `global` em outro módulo
    só rebindaria a cópia local trazida por `import *` e o motor continuaria usando o valor antigo.
    """
    global TEXT_CHAR_INTERVAL, APP_STABLE_DEFAULT_MS, APP_AFTER_OPEN_DEFAULT
    if text_char_interval is not None:
        TEXT_CHAR_INTERVAL = float(text_char_interval)
    if app_stable_ms is not None:
        APP_STABLE_DEFAULT_MS = int(app_stable_ms)
    if app_after_open is not None:
        APP_AFTER_OPEN_DEFAULT = float(app_after_open)

@dataclass
class Command:
    # Identidade
    id: str = field(default_factory=_next_id)

    # O que é: tecla ("E", "SHIFT", "VOLUME_UP") ou botão do mouse
    # ("left", "right", "middle", "x1", "x2") ou, para mouse_move/scroll,
    # não se aplica (target pode ficar vazio).
    type: InputType = InputType.KEY
    target: str = ""
    # Texto literal a ser digitado pelo backend; usado pelo tutorial/demo e
    # disponível para automações que precisam inserir frases com acentos.
    text: str = ""

    # O que fazer com ela
    action: ActionType = ActionType.PRESS_AND_RELEASE

    # Tempo, em segundos, relativo ao início da execução do mapa
    start: float = 0.0
    duration: float = 0.0   # usado em PRESS_AND_RELEASE; ignorado em RELEASE puro
    # Na V20, delay é apenas referência/sugestão do editor; não altera start.
    delay: float = 0.0
    delay_suggested: float = 0.0
    description: str = ""

    # Para mouse_move / mouse_scroll
    x: Optional[int] = None
    y: Optional[int] = None
    relative: bool = False
    # Movimento de mouse mesclado: lista de pontos normalizados {t,x,y}.
    # t varia de 0 a 1 para que a duração do bloco possa ser alterada
    # sem perder o percurso capturado.
    mouse_path: list[dict[str, float | int]] = field(default_factory=list)
    merged_move: bool = False
    scroll_dx: int = 0
    scroll_dy: int = 0

    # Agrupamento lógico/visual. group mantém compatibilidade com V19;
    # group_id identifica o grupo de forma estável na V20.
    group: str = ""
    group_id: str = ""

    enabled: bool = True

    # Barreira opcional de sincronização após uma ação de abertura de aplicativo.
    # Compatibilidade: wait_min_ram_mb permanece no formato dos mapas antigos,
    # mas não é mais usado nem exibido. A prontidão depende de processo + estabilidade.
    wait_process: str = ""
    # 0 = sem limite; a prontidão é determinada pelo estado real do aplicativo.
    wait_timeout: float = 0.0
    wait_min_ram_mb: float = 0.0  # legado; ignorado pela execução atual
    wait_stable_ms: int = 1000
    wait_after_open: float = 0.30

    # Condições de sincronização da V24. Cada condição é executada uma única
    # vez, antes do primeiro evento produzido por este comando.
    conditions: list[WaitCondition] = field(default_factory=list)

    def __post_init__(self) -> None:
        # PySide pode converter Enum(str) em texto (por exemplo
        # "InputType.KEY"). Normalize todos os formatos conhecidos.
        if not isinstance(self.type, InputType):
            raw = str(self.type)
            raw = raw.split(".")[-1].lower()
            try:
                self.type = InputType(raw)
            except ValueError:
                self.type = InputType.KEY
        if not isinstance(self.action, ActionType):
            raw = str(self.action)
            raw = raw.split(".")[-1].lower()
            try:
                self.action = ActionType(raw)
            except ValueError:
                self.action = ActionType.PRESS_AND_RELEASE

    # ---- Cálculo de tempos absolutos -----------------------------------

    @property
    def effective_start(self) -> float:
        """Início real. V20: o atraso sugerido não altera o tempo real."""
        return self.start

    @property
    def computed_duration(self) -> float:
        """Duração efetiva usada pelo editor, timeline e executor."""
        if self.type == InputType.TEXT:
            return calculate_text_duration(self.text)
        return max(0.0, float(self.duration))

    @property
    def total_duration(self) -> float:
        """Alias de compatibilidade para a duração efetiva deste comando.

        O modelo sempre expôs a duração do mapa como ``effective_end``;
        alguns componentes de UX da V22.1 esperavam, incorretamente, uma
        propriedade ``total_duration`` no Command. Mantemos este alias no
        próprio modelo para que qualquer componente consulte a mesma fonte
        de verdade, inclusive comandos de texto com duração calculada.
        """
        return self.computed_duration

    @property
    def computed_delay_after(self) -> float:
        """Atraso determinístico que precisa ser respeitado antes do próximo comando.

        Para texto, a própria duração calculada é a janela ocupada pelo envio
        dos caracteres. Para abertura de aplicativo, somente a parte conhecida
        (estabilidade + segurança) é retornada; o tempo variável de carregamento
        é acrescentado naturalmente pelo executor quando ele aguarda o processo.
        """
        if self.type == InputType.TEXT:
            return self.computed_duration + max(0.0, float(self.delay))
        if self.type == InputType.APP_OPEN:
            return calculate_app_readiness_base(self) + max(0.0, float(self.delay))
        return max(0.0, float(self.duration if self.action == ActionType.PRESS_AND_RELEASE else 0.0)) + max(0.0, float(self.delay))

    @property
    def effective_end(self) -> float:
        """Instante planejado de término; texto usa duração calculada."""
        if self.type == InputType.TEXT:
            return self.effective_start + self.computed_duration
        if self.type == InputType.APP_OPEN:
            # Abertura não tem uma duração fixa de execução, mas a timeline
            # precisa representar a barreira determinística: estabilidade +
            # atraso de segurança. O tempo variável de carregamento é indicado
            # pela própria execução, que só libera o próximo input após o PID
            # estar pronto.
            return self.effective_start + self.computed_delay_after
        if self.action == ActionType.PRESS_AND_RELEASE:
            return self.effective_start + self.duration
        return self.effective_start

    # ---- Validação -------------------------------------------------------

    def validate(self) -> list[str]:
        """Retorna uma lista de mensagens de erro. Lista vazia = válido."""
        errors: list[str] = []

        if self.type in (InputType.KEY, InputType.MOUSE_BUTTON) and not self.target:
            errors.append(f"[{self.id}] comando do tipo '{self.type}' sem tecla/botão definido.")
        if self.type == InputType.TEXT and not self.text:
            errors.append(f"[{self.id}] comando de texto sem conteúdo definido.")

        if self.type == InputType.MOUSE_MOVE:
            if self.merged_move and self.mouse_path:
                pass
            elif self.x is None or self.y is None:
                errors.append(f"[{self.id}] movimento do mouse sem posição definida.")

        if self.type == InputType.MOUSE_SCROLL and self.scroll_dx == 0 and self.scroll_dy == 0:
            errors.append(f"[{self.id}] rolagem do mouse sem direção ou quantidade definida.")

        if self.type == InputType.WAIT and not self.conditions:
            errors.append(f"[{self.id}] comando de espera sem nenhuma condição definida.")

        if self.start < 0:
            errors.append(f"[{self.id}] início negativo ({self.start}).")

        if self.delay < 0:
            errors.append(f"[{self.id}] atraso negativo ({self.delay}).")

        if self.action == ActionType.PRESS_AND_RELEASE and self.duration < 0:
            errors.append(f"[{self.id}] duração negativa ({self.duration}).")

        if self.wait_process:
            if self.wait_timeout < 0:
                errors.append(f"[{self.id}] timeout de espera do processo não pode ser negativo.")
            if self.wait_stable_ms < 0:
                errors.append(f"[{self.id}] estabilidade do processo não pode ser negativa.")
            if self.wait_after_open < 0:
                errors.append(f"[{self.id}] atraso após abertura não pode ser negativo.")

        for condition in self.conditions:
            errors.extend(f"[{self.id}] {message}" for message in condition.validate())

        if self.action == ActionType.PRESS_AND_RELEASE and self.duration == 0 and self.type in (InputType.KEY, InputType.MOUSE_BUTTON):
            # Só teclas e botões têm "tempo pressionado". A timeline ordena SOLTAR antes de PRESSIONAR no
            # mesmo instante, então duração 0 deixaria a tecla/botão presa; por isso continua sendo erro.
            # Mover, rolar, esperar, texto e abrir aplicativo não têm duração e não passam por esta regra.
            errors.append(
                f"[{self.id}] duração igual a 0 em um comando 'pressionar e soltar' "
                f"(a tecla será solta instantaneamente)."
            )

        return errors

    # ---- Serialização ------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value if isinstance(self.type, InputType) else str(self.type),
            "target": self.target,
            "text": self.text,
            "action": self.action.value if isinstance(self.action, ActionType) else str(self.action),
            "start": self.start,
            "duration": self.duration,
            "delay": self.delay,
            "delay_suggested": self.delay_suggested if self.delay_suggested else self.delay,
            "description": self.description,
            "x": self.x,
            "y": self.y,
            "relative": self.relative,
            "mouse_path": copy.deepcopy(self.mouse_path),
            "merged_move": self.merged_move,
            "scroll_dx": self.scroll_dx,
            "scroll_dy": self.scroll_dy,
            "group": self.group,
            "group_id": self.group_id,
            "enabled": self.enabled,
            "wait_process": self.wait_process,
            "wait_timeout": self.wait_timeout,
            "wait_min_ram_mb": self.wait_min_ram_mb,
            "wait_stable_ms": self.wait_stable_ms,
            "wait_after_open": self.wait_after_open,
            "conditions": [c.to_dict() for c in self.conditions],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Command":
        raw_type = str(data.get("type", InputType.KEY.value))
        raw_type = raw_type.split(".")[-1].lower()
        try:
            command_type = InputType(raw_type)
        except ValueError:
            command_type = InputType.KEY
        raw_action = str(data.get("action", ActionType.PRESS_AND_RELEASE.value))
        raw_action = raw_action.split(".")[-1].lower()
        try:
            command_action = ActionType(raw_action)
        except ValueError:
            command_action = ActionType.PRESS_AND_RELEASE
        # Mapas criados automaticamente nas versões anteriores gravavam
        # 250 ms + 375 ms como padrão. Atualiza somente essa combinação exata,
        # evitando alterar configurações personalizadas.
        _stable_raw = data.get('wait_stable_ms', 1000)
        _after_raw = data.get('wait_after_open', 0.30)
        try:
            _stable_value = int(_stable_raw)
        except Exception:
            _stable_value = 1000
        try:
            _after_value = float(_after_raw)
        except Exception:
            _after_value = 0.30
        if _stable_value == 250 and abs(_after_value - 0.375) < 1e-9:
            _stable_value = 1000
            _after_value = 0.30
        return cls(
            id=data.get("id") or _next_id(),
            type=command_type,
            target=data.get("target", ""),
            text=str(data.get("text", "")),
            action=command_action,
            start=float(data.get("start", 0.0)),
            duration=float(data.get("duration", 0.0)),
            delay=float(data.get("delay", 0.0)),
            delay_suggested=float(data.get("delay_suggested", data.get("delay", 0.0))),
            description=str(data.get("description", "")),
            x=data.get("x"),
            y=data.get("y"),
            relative=bool(data.get("relative", False)),
            mouse_path=list(data.get("mouse_path", []) or []),
            merged_move=bool(data.get("merged_move", False)),
            scroll_dx=int(data.get("scroll_dx", 0)),
            scroll_dy=int(data.get("scroll_dy", 0)),
            group=data.get("group", ""),
            group_id=data.get("group_id", ""),
            enabled=bool(data.get("enabled", True)),
            wait_process=str(data.get("wait_process", "")),
            wait_timeout=float(data.get("wait_timeout", 0.0)),
            wait_min_ram_mb=float(data.get("wait_min_ram_mb", 8.0)),
            wait_stable_ms=_stable_value,
            wait_after_open=_after_value,
            conditions=[c for raw in data.get("conditions", []) if (c := WaitCondition.from_dict(raw)) is not None],
        )

# Mapa de transições permitidas: estado atual -> estados destino válidos.
# Definido depois de State para que os membros do Enum existam em tempo de importação.
_ALLOWED_TRANSITIONS: dict[State, set[State]] = {
    State.IDLE: {State.RECORDING, State.RUNNING},
    State.RECORDING: {State.IDLE, State.ERROR},
    State.RUNNING: {State.PAUSED, State.STOPPING, State.ERROR},
    State.PAUSED: {State.RUNNING, State.STOPPING, State.ERROR},
    State.STOPPING: {State.IDLE, State.ERROR},
    State.ERROR: {State.IDLE},
}

class InvalidStateTransition(RuntimeError):
    def __init__(self, current: State, target: State):
        super().__init__(f"Transição inválida: {current.value} -> {target.value}")
        self.current = current
        self.target = target

class StateManager:
    """
    Controla o estado atual do programa e notifica observadores (a UI,
    por exemplo) sempre que ele muda. Thread-safety básica é garantida
    porque as transições são operações atômicas simples em Python, mas
    quem chama `transition_to` a partir de threads diferentes (executor,
    recorder, hotkeys) deve estar ciente disso.
    """

    def __init__(self, initial: State = State.IDLE) -> None:
        self._state = initial
        self._listeners: list[Callable[[State, State], None]] = []
        self._lock = threading.RLock()

    @property
    def state(self) -> State:
        return self._state

    def can_transition_to(self, target: State) -> bool:
        with self._lock:
            return target in _ALLOWED_TRANSITIONS.get(self._state, set())

    def transition_to(self, target: State) -> None:
        with self._lock:
            if not self.can_transition_to(target):
                raise InvalidStateTransition(self._state, target)
            previous = self._state
            self._state = target
            listeners = list(self._listeners)
        for listener in listeners:
            try:
                listener(previous, target)
            except Exception:
                pass

    def force_to_idle(self) -> None:
        """Usado apenas pela rotina de emergência/erro (item 25)."""
        with self._lock:
            previous = self._state
            self._state = State.IDLE
            listeners = list(self._listeners)
        for listener in listeners:
            try:
                listener(previous, State.IDLE)
            except Exception:
                pass

    def on_change(self, callback: Callable[[State, State], None]) -> None:
        """Registra um observador: callback(estado_anterior, estado_novo)."""
        with self._lock:
            self._listeners.append(callback)

def key_to_name(key) -> str:
    """Normaliza apenas teclas reconhecidas pelo modelo visual do Studio.

    Eventos desconhecidos do pynput são ignorados em vez de virar uma tecla
    arbitrária na interface. Isso evita símbolos fantasmas causados por nomes
    internos/driver que não fazem parte do teclado suportado.
    """
    name = getattr(key, "name", None)
    if name is not None:
        normalized = _SPECIAL_KEY_NAMES.get(name)
        return normalized or ""
    char = getattr(key, "char", None)
    if char:
        up = char.upper()
        if len(up) == 1 and (up.isalnum() or up in "Ç"):
            return up
        return ""
    return ""

def _normalize_hotkey_token(token: str) -> str:
    t = token.strip().upper().replace(" ", "")
    aliases = {
        "MOUSE_LEFT": "MOUSE_LEFT", "LEFT_MOUSE": "MOUSE_LEFT", "BOTAOESQUERDO": "MOUSE_LEFT",
        "MOUSE_RIGHT": "MOUSE_RIGHT", "RIGHT_MOUSE": "MOUSE_RIGHT", "BOTAODIREITO": "MOUSE_RIGHT",
        "MOUSE_MIDDLE": "MOUSE_MIDDLE", "MIDDLE_MOUSE": "MOUSE_MIDDLE", "BOTAO_MEIO": "MOUSE_MIDDLE",
        "MOUSE_X1": "MOUSE_X1", "X1": "MOUSE_X1", "LATERAL1": "MOUSE_X1",
        "MOUSE_X2": "MOUSE_X2", "X2": "MOUSE_X2", "LATERAL2": "MOUSE_X2",
    }
    return aliases.get(t, t)

def parse_combo(hotkey: str) -> frozenset[str]:
    parts = [_normalize_hotkey_token(p) for p in hotkey.split("+") if p.strip()]
    if not parts:
        raise ValueError("Atalho vazio.")
    return frozenset(parts)

# Botões laterais do mouse (decisão D1, 25.5).
# TODO o caminho funcional (monitor -> gravador -> atalhos -> backends) usa o nome cru do sistema:
# "x1" é o XBUTTON1 do Windows / Button.x1 do pynput. Antes, a troca x1<->x2 era aplicada uma vez no
# monitor e de novo no gravador e nos atalhos, de modo que o mouse virtual via um nome e o gravador outro.
# Agora só o mouse virtual troca os nomes, para desenhar o botão "superior" como X1. Se a conferência
# no hardware mostrar que o desenho está invertido, mude esta constante para False.
DISPLAY_SWAPS_SIDE_BUTTONS = True


def display_mouse_button_name(name: str) -> str:
    """Nome do botão para o mouse virtual. SOMENTE exibição: nunca use no caminho funcional."""
    raw = str(name).lower()
    if DISPLAY_SWAPS_SIDE_BUTTONS and raw in ("x1", "x2"):
        return "x2" if raw == "x1" else "x1"
    return raw

@dataclass
class CommandGroup:
    """Grupo lógico/visual de comandos da V20."""
    id: str = field(default_factory=lambda: f"grp_{next(_id_counter):06d}")
    name: str = "Novo grupo"
    color: str = "#5B8DEF"
    description: str = ""
    use_for_delay_suggestions: bool = True
    delay_profiles: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "color": self.color,
            "description": self.description,
            "use_for_delay_suggestions": self.use_for_delay_suggestions,
            "delay_profiles": dict(self.delay_profiles),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CommandGroup":
        return cls(
            id=str(data.get("id") or f"grp_{next(_id_counter):06d}"),
            name=str(data.get("name", "Novo grupo")),
            color=str(data.get("color", "#5B8DEF")),
            description=str(data.get("description", "")),
            use_for_delay_suggestions=bool(data.get("use_for_delay_suggestions", True)),
            delay_profiles={str(k): float(v) for k, v in dict(data.get("delay_profiles", {})).items()},
        )

@dataclass
class AutomationMap:
    name: str
    description: str = ""
    hotkey: Optional[str] = "="  # tecla padrão para iniciar a automação

    commands: list[Command] = field(default_factory=list)
    groups: dict[str, CommandGroup] = field(default_factory=dict)

    # Repetição (item 29)
    repeat_count: int = -1         # padrão: repete sem parar; use 1 ou N para limitar
    repeat_interval: float = 0.0   # segundos entre repetições

    # Velocidade (item 29): 1.0 = normal, 0.5 = 50%, 2.0 = 200%
    speed: float = 1.0

    # Comportamento ao ser acionado enquanto outro mapa executa (item 28)
    # "replace" (padrão, conforme item 28) ou "block"
    conflict_behavior: str = "replace"

    # Automação opcional a iniciar quando esta terminar naturalmente.
    # None = não encadear.
    next_map: Optional[str] = None
    confirm_delete_commands: bool = True

    def __post_init__(self) -> None:
        # IDs novos nunca podem colidir com os IDs deste mapa (salvo em outra sessão).
        _sync_id_counter([c.id for c in self.commands] + list(self.groups))
        # Toda automação nova começa com "=" como tecla de iniciação.
        # Também migra mapas antigos que foram salvos sem tecla definida.
        if not self.hotkey:
            self.hotkey = "="
        # Corrige silenciosamente IDs duplicados herdados de versões anteriores.
        # O primeiro comando mantém sua identidade; os seguintes recebem IDs novos.
        self.repair_duplicate_command_ids()
        self.ensure_legacy_groups()

    def repair_duplicate_command_ids(self) -> int:
        """Garante IDs únicos dentro do mapa, sem interromper o usuário.

        Mapas antigos podem conter IDs repetidos (por exemplo, após duplicações
        feitas em versões anteriores). Como o ID é apenas identidade interna do
        comando, a correção segura é manter a primeira ocorrência e gerar uma
        nova identidade para cada repetição. Retorna quantos IDs foram reparados.
        """
        seen: set[str] = set()
        repaired = 0
        for cmd in self.commands:
            cid = str(cmd.id or "").strip()
            if not cid or cid in seen:
                new_id = _next_id()
                while new_id in seen:
                    new_id = _next_id()
                cmd.id = new_id
                repaired += 1
            seen.add(cmd.id)
        return repaired

    # ---- Validação ------------------------------------------------------

    def validate(self) -> list[str]:
        # A validação também é uma barreira de compatibilidade: se um mapa
        # antigo ainda tiver IDs repetidos, corrige-os antes de validar.
        self.repair_duplicate_command_ids()
        errors: list[str] = []

        if not self.name or not self.name.strip():
            errors.append("Mapa sem nome.")

        self.ensure_legacy_groups()
        for cmd in self.commands:
            errors.extend(cmd.validate())

        if self.repeat_count == 0:
            errors.append(f"Mapa '{self.name}': repeat_count não pode ser 0 (use 1, N ou -1 para infinito).")

        if self.repeat_interval < 0:
            errors.append(f"Mapa '{self.name}': repeat_interval negativo.")

        if self.speed <= 0:
            errors.append(f"Mapa '{self.name}': speed deve ser maior que 0.")

        return errors

    def is_valid(self) -> bool:
        return len(self.validate()) == 0

    # ---- Conveniências ----------------------------------------------

    def total_duration(self) -> float:
        """Instante em que o último comando termina (útil para a timeline)."""
        if not self.commands:
            return 0.0
        return max((c.effective_end for c in self.commands if c.enabled), default=0.0)

    def add_command(self, command: Command) -> None:
        """Adiciona um comando ao final da sequência."""
        self.commands.append(command)

    def command_ids_in_order(self) -> list[str]:
        return [str(c.id) for c in self.commands]

    def get_commands_by_ids(self, command_ids: set[str] | list[str] | tuple[str, ...]) -> list[Command]:
        ids = {str(x) for x in command_ids}
        return [c for c in self.commands if c.id in ids]

    def copy_commands(self, command_ids: set[str] | list[str]) -> list[Command]:
        """Cria uma cópia serializável preservando a ordem e os offsets temporais."""
        selected = self.get_commands_by_ids(command_ids)
        if not selected:
            return []
        base = min(float(c.start) for c in selected)
        copied = []
        for original in selected:
            c = copy.deepcopy(original)
            c.id = _next_id()
            c.start = max(0.0, float(original.start) - base)
            copied.append(c)
        return copied

    def insert_commands(self, commands: list[Command], index: int | None = None, anchor_to_previous: bool = True) -> list[Command]:
        """Insere um bloco de comandos em uma posição e devolve os comandos inseridos."""
        if not commands:
            return []
        index = len(self.commands) if index is None else max(0, min(int(index), len(self.commands)))
        base = self.commands[index - 1].effective_end if anchor_to_previous and index > 0 else 0.0
        inserted=[]
        for original in commands:
            c=copy.deepcopy(original)
            c.id=_next_id()
            c.start=max(0.0, base + float(original.start))
            inserted.append(c)
        self.commands[index:index]=inserted
        return inserted

    def validate_structure(self) -> list[str]:
        """Valida invariantes do mapa sem alterar dados do usuário."""
        errors=[]
        ids=[str(c.id or '') for c in self.commands]
        if any(not x for x in ids): errors.append('Existe comando sem ID.')
        if len(ids) != len(set(ids)): errors.append('Existem IDs de comandos duplicados.')
        valid_types={x.value for x in InputType}; valid_actions={x.value for x in ActionType}
        for i,c in enumerate(self.commands,1):
            raw_type=c.type.value if isinstance(c.type,InputType) else str(c.type).split('.')[-1].lower()
            raw_action=c.action.value if isinstance(c.action,ActionType) else str(c.action).split('.')[-1].lower()
            if raw_type not in valid_types: errors.append(f'Linha {i}: tipo desconhecido ({raw_type}).')
            if raw_action not in valid_actions: errors.append(f'Linha {i}: ação desconhecida ({raw_action}).')
            if not math.isfinite(float(c.start)) or float(c.start)<0: errors.append(f'Linha {i}: início inválido.')
            if not math.isfinite(float(c.duration)) or float(c.duration)<0: errors.append(f'Linha {i}: duração inválida.')
            if getattr(c,'group_id','') and c.group_id not in self.groups: errors.append(f'Linha {i}: grupo inexistente.')
        errors.extend(self.validate())
        # validate() pode reparar IDs herdados; a segunda verificação confirma o resultado.
        ids=[str(c.id or '') for c in self.commands]
        if len(ids) != len(set(ids)): errors.append('IDs continuam duplicados após reparo.')
        return list(dict.fromkeys(errors))

    def export_commands(self, command_ids: set[str] | list[str]) -> dict[str, Any]:
        selected=[copy.deepcopy(c) for c in self.get_commands_by_ids(command_ids)]
        if selected:
            base=min(float(c.start) for c in selected)
            for c in selected: c.start=max(0.0,float(c.start)-base)
        groups={}
        gids={c.group_id for c in selected if c.group_id}
        for gid in gids:
            if gid in self.groups: groups[gid]=self.groups[gid].to_dict()
        return {
            'format':'AutomationStudio commands', 'version':COMMAND_EXPORT_VERSION,
            'commands':[c.to_dict() for c in selected], 'groups':groups,
        }

    @staticmethod
    def import_commands(payload: dict[str, Any]) -> tuple[list[Command], dict[str, CommandGroup]]:
        if not isinstance(payload,dict) or payload.get('format')!='AutomationStudio commands':
            raise ValueError('Arquivo de comandos incompatível.')
        commands=[Command.from_dict(x) for x in payload.get('commands',[]) if isinstance(x,dict)]
        groups={str(k):CommandGroup.from_dict(v) for k,v in dict(payload.get('groups',{})).items() if isinstance(v,dict)}
        return commands, groups

    def timeline_rows(self) -> list[dict[str, Any]]:
        """Linhas da pré-visualização: o que cada comando ativo fará, nos mesmos tempos que o motor e a Timeline usam.

        Só lê o mapa. Até a 25.4 chamava `reflow_timeline` antes de montar as linhas e, com isso, reescrevia o início dos
        comandos do mapa aberto (achado 2.09 da auditoria).
        """
        return [{'id':c.id,'start':round(float(c.effective_start),6),'duration':round(float(c.computed_duration),6),'end':round(float(c.effective_end),6)} for c in self.commands if c.enabled]

    def insert_command(self, command: Command, index: int | None = None) -> int:
        """Insere um comando na ordem de execução e retorna o índice final."""
        if index is None:
            self.commands.append(command)
            return len(self.commands) - 1
        index = max(0, min(int(index), len(self.commands)))
        self.commands.insert(index, command)
        return index

    # ---- Reencadeamento dos inícios (reflow, mover, reordenar) -----------
    #
    # Cada comando carrega a sua "lacuna": a distância entre o fim programado do comando anterior
    # (`anterior.start + anterior.computed_delay_after`) e o seu próprio início. O primeiro carrega o próprio início.
    # A lacuna TEM SINAL: negativa quer dizer sobreposição, que é o normal num mapa gravado (o mouse se move enquanto uma
    # tecla está pressionada). Até a 25.4 ela era cortada em zero, o que desfazia as sobreposições de TODO o mapa a cada
    # arraste de linha (achado 2.10 da auditoria).

    @staticmethod
    def _gaps_before(commands: list[Command]) -> dict[int, float]:
        """Lacuna de cada comando para o anterior, na ordem dada. A chave é o próprio objeto (`id()`), não o ID do comando,
        para que IDs repetidos de um mapa legado não se confundam."""
        gaps: dict[int, float] = {}
        previous = None
        for cmd in commands:
            if previous is None:
                gaps[id(cmd)] = max(0.0, float(cmd.start))
            else:
                gaps[id(cmd)] = float(cmd.start) - (float(previous.start) + float(previous.computed_delay_after))
            previous = cmd
        return gaps

    @staticmethod
    def _retime(commands: list[Command], gap_before: dict[int, float]) -> None:
        """Recalcula os inícios em cascata, na ordem dada: cada comando fica a `gap_before` do fim programado do anterior.

        Nenhum início fica negativo. Um início que já está certo (diferença abaixo de 1 ns) não é regravado: o que a
        operação não mudou continua idêntico, sem o ruído de ponto flutuante de somar a sequência inteira de novo.
        """
        previous = None
        for cmd in commands:
            gap = gap_before.get(id(cmd), 0.0)
            if previous is None:
                new_start = max(0.0, gap)
            else:
                new_start = max(0.0, float(previous.start) + float(previous.computed_delay_after) + gap)
            if abs(new_start - float(cmd.start)) > _TIME_EPSILON:
                cmd.start = new_start
            previous = cmd

    def reflow_timeline(self, preserve_gaps: bool = True) -> None:
        """Reconstrói os inícios a partir da sequência do mapa.

        Com `preserve_gaps=True` cada lacuna, inclusive a negativa (a sobreposição), é mantida: um mapa coerente não muda.
        Com `False` cada comando começa quando o anterior termina.
        """
        if not self.commands:
            return
        gaps = self._gaps_before(self.commands) if preserve_gaps else {id(c): 0.0 for c in self.commands}
        self._retime(self.commands, gaps)

    def remove_commands(self, command_ids: set[str] | list[str], compact: bool = True) -> list[Command]:
        """Remove comandos pela identidade e opcionalmente compacta o tempo."""
        ids = {str(x) for x in command_ids}
        removed = [c for c in self.commands if c.id in ids]
        if not removed:
            return []
        if compact:
            intervals = sorted((c.effective_start, c.effective_end) for c in removed)
            merged: list[list[float]] = []
            for a, b in intervals:
                b = max(a, b)
                if not merged or a > merged[-1][1]:
                    merged.append([a, b])
                else:
                    merged[-1][1] = max(merged[-1][1], b)
            remaining = [c for c in self.commands if c.id not in ids]
            for c in remaining:
                shift = sum(max(0.0, b - a) for a, b in merged if b <= c.start)
                if shift:
                    c.start = max(0.0, c.start - shift)
            self.commands = remaining
        else:
            self.commands = [c for c in self.commands if c.id not in ids]
        return removed

    def duplicate_commands(self, command_ids: set[str] | list[str], insert_at: int | None = None) -> list[Command]:
        """Duplica um bloco, atribuindo IDs novos e preservando espaçamentos."""
        ids = {str(x) for x in command_ids}
        selected = [c for c in self.commands if c.id in ids]
        if not selected:
            return []
        base = min(float(c.start) for c in selected)
        copies = [copy.deepcopy(c) for c in selected]
        for c in copies:
            c.id = _next_id()
            c.start = max(0.0, float(c.start) - base)
        index = len(self.commands) if insert_at is None else max(0, min(int(insert_at), len(self.commands)))
        anchor = self.commands[index - 1].effective_end if index > 0 else 0.0
        for c in copies:
            c.start += anchor
        self.commands[index:index] = copies
        return copies

    def reorder_to_ids(self, ordered_ids: list[str]) -> bool:
        """Aplica exatamente a ordem visual indicada pelos IDs e recalcula os tempos.

        Usado pelo editor no término de um arraste: a tabela visual já representa
        a ordem pretendida, portanto não fazemos uma segunda conversão por índice.
        Cada comando preserva a distância temporal que tinha para o anterior (inclusive a negativa, a sobreposição) e
        os inícios são recalculados em cascata. Só muda o início dos comandos do trecho que trocou de lugar: quem está
        antes e quem está depois dele continua exatamente como estava.
        """
        if not ordered_ids or len(ordered_ids) != len(self.commands):
            return False
        by_id = {c.id: c for c in self.commands}
        if set(ordered_ids) != set(by_id):
            return False

        gap_before = self._gaps_before(self.commands)
        reordered = [by_id[cid] for cid in ordered_ids]
        self._retime(reordered, gap_before)
        self.commands = reordered
        return True

    def move_commands(self, command_ids: set[str] | list[str], target_index: int) -> tuple[int, int] | None:
        """Move comandos preservando a ordem relativa e reconstruindo os tempos.

        Cada comando carrega implicitamente a sua *distância temporal* para o
        comando anterior: ``start - (anterior.start + anterior.computed_delay_after)``.
        Ao reordenar,
        essa distância acompanha o comando. Assim, mover um comando para outro
        ponto da sequência desloca o seu início para depois do comando anterior
        mantendo o mesmo intervalo, e os comandos afetados depois dele também
        têm os seus horários recalculados em cascata pela mesma regra.

        Isso evita deixar ``start`` absoluto preso à posição antiga, que era o
        motivo de a Timeline/editor mostrarem tempos incoerentes após mover um
        comando.
        """
        ids = set(command_ids)
        if not ids or not self.commands:
            return None

        original = list(self.commands)
        moving = [c for c in original if c.id in ids]
        if not moving:
            return None

        # Captura os intervalos temporais ANTES da reordenação.
        #
        # O ponto importante aqui é usar o FIM PROGRAMADO do comando anterior,
        # incluindo o seu atraso (`computed_delay_after`), e não apenas
        # `effective_end`. Para texto/app-open, `effective_end` não representa
        # toda a janela até o próximo comando quando existe atraso configurado.
        # A distância tem sinal: negativa é sobreposição (ver `_gaps_before`).
        gap_before = self._gaps_before(original)

        target_index = max(0, min(int(target_index), len(original)))
        before_target = sum(1 for i, c in enumerate(original) if c.id in ids and i < target_index)
        remaining = [c for c in original if c.id not in ids]
        target_index -= before_target
        target_index = max(0, min(target_index, len(remaining)))
        remaining[target_index:target_index] = moving

        # Reconstrói os tempos na nova ordem preservando, para CADA comando,
        # o mesmo intervalo que existia entre o término programado do anterior
        # e o início deste comando. Só os comandos do trecho que trocou de lugar
        # mudam de início; quem está antes ou depois desse trecho não é tocado.
        self._retime(remaining, gap_before)

        self.commands = remaining
        return target_index, target_index + len(moving) - 1

    def latest_end(self, exclude_ids: set[str] | None = None) -> float:
        excluded = exclude_ids or set()
        ends = [c.effective_end for c in self.commands if c.enabled and c.id not in excluded]
        return max(ends, default=0.0)

    def ensure_legacy_groups(self) -> None:
        """Converte grupos textuais da V19 em grupos estáveis da V20."""
        for cmd in self.commands:
            if cmd.group and not cmd.group_id:
                existing = next((g for g in self.groups.values() if g.name == cmd.group), None)
                if existing is None:
                    existing = CommandGroup(name=cmd.group)
                    self.groups[existing.id] = existing
                cmd.group_id = existing.id
            elif cmd.group_id and cmd.group_id not in self.groups:
                self.groups[cmd.group_id] = CommandGroup(id=cmd.group_id, name=cmd.group or "Grupo")

    def group_name(self, group_id: str) -> str:
        return self.groups.get(group_id).name if group_id in self.groups else ""

    def remove_command(self, command_id: str) -> bool:
        before = len(self.commands)
        self.commands = [c for c in self.commands if c.id != command_id]
        return len(self.commands) != before

    def get_command(self, command_id: str) -> Optional[Command]:
        for c in self.commands:
            if c.id == command_id:
                return c
        return None

    # ---- Serialização -------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "hotkey": self.hotkey,
            "repeat_count": self.repeat_count,
            "repeat_interval": self.repeat_interval,
            "speed": self.speed,
            "conflict_behavior": self.conflict_behavior,
            "next_map": self.next_map,
            "confirm_delete_commands": self.confirm_delete_commands,
            "groups": {gid: g.to_dict() for gid, g in self.groups.items()},
            "commands": [c.to_dict() for c in self.commands],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AutomationMap":
        return cls(
            name=data.get("name", "Sem nome"),
            description=data.get("description", ""),
            hotkey=data.get("hotkey") or "=",
            repeat_count=(lambda n: 1 if n == 0 else n)(int(data.get("repeat_count", -1))),
            repeat_interval=max(0.0, float(data.get("repeat_interval", 0.0))),
            speed=float(data.get("speed", 1.0)),
            conflict_behavior=data.get("conflict_behavior", "replace"),
            next_map=data.get("next_map") or None,
            confirm_delete_commands=bool(data.get("confirm_delete_commands", True)),
            groups={str(k): CommandGroup.from_dict(v) for k, v in dict(data.get("groups", {})).items()},
            commands=[Command.from_dict(c) for c in data.get("commands", [])],
        )

class EventKind(str, Enum):
    KEY_DOWN = "key_down"
    KEY_UP = "key_up"
    MOUSE_DOWN = "mouse_down"
    MOUSE_UP = "mouse_up"
    MOUSE_MOVE = "mouse_move"
    MOUSE_SCROLL = "mouse_scroll"
    TEXT = "text"
    APP_OPEN = "app_open"
    WAIT = "wait"

@dataclass
class Event:
    time: float           # segundos, relativo ao início da execução (antes de aplicar `speed`)
    kind: EventKind
    target: str
    command_id: str
    text: str = ""
    # payload extra para mouse_move / mouse_scroll
    x: int | None = None
    y: int | None = None
    relative: bool = False
    # Movimento de mouse mesclado: lista de pontos normalizados {t,x,y}.
    # t varia de 0 a 1 para que a duração do bloco possa ser alterada
    # sem perder o percurso capturado.
    mouse_path: list[dict[str, float | int]] = field(default_factory=list)
    merged_move: bool = False
    scroll_dx: int = 0
    scroll_dy: int = 0
    # Barreira de processo associada ao evento.
    wait_process: str = ""
    # 0 = sem limite.
    wait_timeout: float = 0.0
    wait_min_ram_mb: float = 8.0
    wait_stable_ms: int = 1000
    wait_after_open: float = 0.30
    # Condições independentes do legado de espera por processo.
    wait_conditions: list[WaitCondition] = field(default_factory=list)

def build_timeline(automation_map: AutomationMap) -> list[Event]:
    """
    Constrói e retorna a timeline de eventos ordenada por tempo.
    Comandos desabilitados (enabled=False) são ignorados.
    Em caso de empate de horário, a ordem é: *_UP antes de *_DOWN,
    para que "soltar uma tecla e apertar a mesma tecla no mesmo
    instante" nunca gere um down-sem-up perdido.
    """
    events: list[Event] = []

    for cmd in automation_map.commands:
        if not cmd.enabled:
            continue
        events.extend(_command_to_events(cmd))

    def sort_key(ev: Event):
        # UP (1) antes de DOWN (0)? Não: queremos UP antes para liberar
        # primeiro. Damos peso menor a eventos "*_UP".
        is_up = ev.kind in (EventKind.KEY_UP, EventKind.MOUSE_UP)
        return (ev.time, 0 if is_up else 1)

    events.sort(key=sort_key)
    return events


def _attach_conditions(events: list[Event], cmd: Command) -> list[Event]:
    """Anexa precondições do comando somente ao primeiro evento da sequência."""
    if events and getattr(cmd, "conditions", None):
        events[0].wait_conditions = copy.deepcopy(cmd.conditions)
    return events

def _command_to_events(cmd: Command) -> list[Event]:
    start = cmd.effective_start

    if cmd.type == InputType.WAIT:
        return _attach_conditions([Event(time=start, kind=EventKind.WAIT, target="", command_id=cmd.id)], cmd)

    if cmd.type == InputType.KEY:
        down_kind, up_kind = EventKind.KEY_DOWN, EventKind.KEY_UP
    elif cmd.type == InputType.MOUSE_BUTTON:
        down_kind, up_kind = EventKind.MOUSE_DOWN, EventKind.MOUSE_UP
    elif cmd.type == InputType.TEXT:
        return _attach_conditions([Event(
            time=start, kind=EventKind.TEXT, target="", command_id=cmd.id, text=cmd.text,
            wait_process=cmd.wait_process, wait_timeout=cmd.wait_timeout,
            wait_min_ram_mb=cmd.wait_min_ram_mb, wait_stable_ms=cmd.wait_stable_ms,
            wait_after_open=cmd.wait_after_open,
        )], cmd)
    elif cmd.type == InputType.APP_OPEN:
        return _attach_conditions([Event(
            time=start, kind=EventKind.APP_OPEN, target=cmd.target, command_id=cmd.id,
            wait_process=cmd.wait_process or cmd.target, wait_timeout=cmd.wait_timeout,
            wait_min_ram_mb=0.0, wait_stable_ms=cmd.wait_stable_ms, wait_after_open=cmd.wait_after_open,
        )], cmd)
    elif cmd.type == InputType.MOUSE_MOVE:
        if cmd.merged_move and cmd.mouse_path:
            events=[]
            for point in cmd.mouse_path:
                try:
                    frac=max(0.0,min(1.0,float(point.get("t",0.0))))
                    px=int(point.get("x",cmd.x or 0)); py=int(point.get("y",cmd.y or 0))
                except Exception:
                    continue
                events.append(Event(time=start + cmd.duration*frac, kind=EventKind.MOUSE_MOVE, target=cmd.target, command_id=cmd.id, x=px, y=py, relative=False))
            if events:
                return _attach_conditions(events, cmd)
        return _attach_conditions([Event(time=start, kind=EventKind.MOUSE_MOVE, target=cmd.target, command_id=cmd.id, x=cmd.x, y=cmd.y, relative=cmd.relative)], cmd)
    elif cmd.type == InputType.MOUSE_SCROLL:
        return _attach_conditions([Event(
            time=start, kind=EventKind.MOUSE_SCROLL, target=cmd.target,
            command_id=cmd.id, scroll_dx=cmd.scroll_dx, scroll_dy=cmd.scroll_dy,
        )], cmd)
    else:
        return []

    if cmd.action == ActionType.PRESS:
        return _attach_conditions([Event(time=start, kind=down_kind, target=cmd.target, command_id=cmd.id)], cmd)
    if cmd.action == ActionType.RELEASE:
        return _attach_conditions([Event(time=start, kind=up_kind, target=cmd.target, command_id=cmd.id, wait_process=cmd.wait_process, wait_timeout=cmd.wait_timeout, wait_min_ram_mb=cmd.wait_min_ram_mb, wait_stable_ms=cmd.wait_stable_ms, wait_after_open=cmd.wait_after_open)], cmd)

    # PRESS_AND_RELEASE
    end = cmd.effective_end
    return _attach_conditions([
        Event(time=start, kind=down_kind, target=cmd.target, command_id=cmd.id),
        Event(time=end, kind=up_kind, target=cmd.target, command_id=cmd.id, wait_process=cmd.wait_process, wait_timeout=cmd.wait_timeout, wait_min_ram_mb=cmd.wait_min_ram_mb, wait_stable_ms=cmd.wait_stable_ms, wait_after_open=cmd.wait_after_open),
    ], cmd)

def map_to_json(automation_map: AutomationMap, *, indent: int = 4) -> str:
    payload = {
        "format_version": FORMAT_VERSION,
        "map": automation_map.to_dict(),
    }
    return json.dumps(payload, indent=indent, ensure_ascii=False)

def map_from_json(text: str) -> AutomationMap:
    payload = json.loads(text)
    # Compatibilidade: aceita tanto {"format_version":..,"map":{...}} quanto
    # um dict de mapa "cru" (sem envelope), para facilitar edição manual.
    map_data = payload["map"] if "map" in payload else payload
    return AutomationMap.from_dict(map_data)

def _normalized_color(value: str | QColor) -> QColor:
    """Converte uma cor salva pelo usuário em QColor válida e opaca."""
    if isinstance(value, QColor):
        c = QColor(value)
    else:
        c = QColor(str(value or '').strip())
    if not c.isValid():
        c = QColor('#5C626C')
    c.setAlpha(255)
    return c

def _text_color_for_background(background: QColor | str) -> QColor:
    """Escolhe preto/branco por luminância para manter contraste AA aproximado."""
    c = _normalized_color(background)
    # QColor.redF etc. já estão no espaço RGB; a fórmula abaixo é uma
    # aproximação perceptual suficientemente estável para UI pequena.
    lum = (0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()) / 255.0
    return QColor('#FFFFFF' if lum < 0.55 else '#17191D')

def resolve_key_labels(target: str) -> list[str]:
    if not target:
        return []
    raw = str(target).strip()
    upper = raw.upper()
    if upper in _SPECIAL:
        return list(_SPECIAL[upper])
    if upper in _NUMPAD:
        return list(_NUMPAD[upper])
    if len(upper) == 1:
        return [upper]
    if raw in (",", ".", ";", "/", "-", "=", "[", "]", "'", "`", "\\", "^~", "Ç"):
        return [raw]
    return []

def _load_keyboard_layout() -> dict:
    try:
        return json.loads(_LAYOUT_PATH.read_text(encoding="utf-8"))
    except Exception:
        # Fallback ABNT2 mínimo: nunca impedir a abertura do programa.
        rows=[
            (["Esc","F1","F2","F3","F4","F5","F6","F7","F8","F9","F10","F11","F12"],0),
            (["`","1","2","3","4","5","6","7","8","9","0","-","=","Backspace"],0),
            (["Tab","Q","W","E","R","T","Y","U","I","O","P","[","]","\\"],0),
            (["CapsLock","A","S","D","F","G","H","J","K","L",";","'","Ç","Enter"],0),
            (["ShiftLeft","Z","X","C","V","B","N","M",",",".","/","ShiftRight"],0),
            (["CtrlLeft","Win","Alt","Space","AltGr","Fn","Menu","CtrlRight"],0),
        ]
        keys=[]; unit=48.; gap=5.; y=0.
        for labels,off in rows:
            x=off
            for label in labels:
                mult={"Backspace":2,"Tab":1.5,"CapsLock":1.75,"Enter":1.75,"ShiftLeft":2.25,"ShiftRight":2.25,"Space":6}.get(label,1)
                w=unit*mult; keys.append({"label":label,"x":x,"y":y,"w":w,"h":42}); x+=w+gap
            y+=47
        return {"ref_w":900,"ref_h":290,"keys":keys}

def _registered_data_dir(default_dir: Path) -> Path:
    """Obtém a pasta de dados escolhida no instalador/usuário sem exigir arquivo de configuração."""
    if os.name == 'nt':
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\\AutomationStudio') as key:
                raw, _ = winreg.QueryValueEx(key, 'DataDir')
                if raw:
                    p = Path(raw).expanduser()
                    p.mkdir(parents=True, exist_ok=True)
                    return p.resolve()
        except Exception:
            pass
    return default_dir.resolve()

def _set_registered_data_dir(folder: Path) -> None:
    if os.name == 'nt':
        try:
            import winreg
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'Software\\AutomationStudio') as key:
                winreg.SetValueEx(key, 'DataDir', 0, winreg.REG_SZ, str(folder.resolve()))
        except Exception:
            pass

def _system_prefers_dark() -> bool:
    """Retorna a preferência de aparência do Windows/Qt quando disponível."""
    try:
        scheme = QApplication.styleHints().colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return True
        if scheme == Qt.ColorScheme.Light:
            return False
    except Exception:
        pass
    # Se o estilo atual for Fusion, a paleta aplicada pelo próprio programa
    # não pode ser usada para inferir a preferência real do Windows: isso
    # criaria um ciclo (tema escolhido -> paleta -> tema detectado).
    try:
        import winreg
        key=r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            value=int(winreg.QueryValueEx(k, "AppsUseLightTheme")[0])
            return value == 0
    except Exception:
        pass
    try:
        c = QApplication.palette().color(QPalette.Window)
        return c.lightness() < 128
    except Exception:
        return False

def _resolve_theme_mode(settings: dict[str, Any]) -> tuple[bool, str]:
    mode = str(settings.get("theme_mode", "system"))
    dark = _system_prefers_dark() if mode == "system" else mode == "dark"
    accent = settings.get("accent_dark" if dark else "accent_light", "#FFC53D" if dark else "#2F6FED")
    return dark, str(accent)

def _hex_rgb(value: str) -> tuple[int, int, int]:
    """Converte '#RRGGBB' em (r, g, b)."""
    v = str(value).lstrip("#")
    return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)

def _mix_hex(a: str, b: str, amount: float) -> str:
    """Mistura duas cores '#RRGGBB': amount=0 devolve `a`, amount=1 devolve `b`."""
    t = max(0.0, min(1.0, float(amount)))
    ca, cb = _hex_rgb(a), _hex_rgb(b)
    r, g, bl = (round(x + (y - x) * t) for x, y in zip(ca, cb))
    return f"#{r:02x}{g:02x}{bl:02x}"

def _relative_luminance(color: str) -> float:
    """Luminância relativa (WCAG) de '#RRGGBB'."""
    def channel(v: int) -> float:
        x = v / 255.0
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    r, g, b = _hex_rgb(color)
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)

def _on_color_hex(background: str) -> str:
    """Texto legível sobre `background`: o que der mais contraste entre branco e quase preto."""
    lum = _relative_luminance(background)
    white_contrast = 1.05 / (lum + 0.05)
    dark_contrast = (lum + 0.05) / (_relative_luminance("#17191d") + 0.05)
    return "#ffffff" if white_contrast >= dark_contrast else "#17191d"

def _theme_tokens(dark: bool, accent: str, light_surface: str = "#ffffff", light_contrast: str = "#2f343b") -> dict[str, str]:
    """Cores do tema (tokens). Todo o visual do tema nasce daqui.

    O acento (`accent`) e, no tema claro, a superfície e o contraste vêm das configurações do usuário;
    as demais cores são derivadas delas. No tema escuro há três camadas: janela (`window`), áreas de
    conteúdo rebaixadas (`base`) e controles elevados (`button`/`hover`).
    """
    if dark:
        t = {
            "window": "#1a1d23", "base": "#14171c", "alt": "#191d23",
            "button": "#262b33", "hover": "#2e343e", "pressed": "#1f242b",
            "border": "#2b313a", "border_strong": "#3b4350",
            "text": "#e8ebf0", "muted": "#9aa4b2", "disabled": "#5f6977",
            "danger": "#ff6b63", "tooltip": "#262b33",
        }
        soft = 0.22
    else:
        s, c = light_surface, light_contrast
        t = {
            "window": s, "base": s, "alt": _mix_hex(s, c, 0.035),
            "button": _mix_hex(s, c, 0.05), "hover": _mix_hex(s, c, 0.10), "pressed": _mix_hex(s, c, 0.15),
            "border": _mix_hex(s, c, 0.16), "border_strong": _mix_hex(s, c, 0.30),
            "text": c, "muted": _mix_hex(s, c, 0.72), "disabled": "#9a9ea5",
            "danger": "#c9302c", "tooltip": "#ffffff",
        }
        soft = 0.14
    t["accent"] = accent
    t["accent_hover"] = _mix_hex(accent, "#ffffff", 0.14)
    t["accent_press"] = _mix_hex(accent, "#000000", 0.14)
    t["accent_soft"] = _mix_hex(t["base"], accent, soft)
    t["on_accent"] = _on_color_hex(accent)
    return t

# Folha de estilo global. Os @tokens@ são trocados por _theme_tokens(); as chaves ficam literais de propósito.
# Regras de ouro: não mudar o tamanho dos controles (os paddings abaixo são os de sempre) e não mexer em
# sub-controles nativos (setas de combo/spinbox, indicadores de checkbox) que o Qt desenha sozinho.
# Botões com visual próprio (estilo inline no widget) continuam valendo: o estilo do widget vence o global.
_APP_QSS = """
QWidget { background: @window@; color: @text@; }
QLabel { background: transparent; }
QCheckBox, QRadioButton { background: transparent; }
QToolTip { padding: 5px 8px; border: 1px solid @border_strong@; border-radius: 4px; background: @tooltip@; color: @text@; }
QGroupBox { font-weight: 600; }
QTabBar::tab { padding: 7px 12px; }

QScrollBar:vertical { width: 6px; background: transparent; margin: 0; }
QScrollBar:horizontal { height: 6px; background: transparent; margin: 0; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0px; height: 0px; border: 0; background: transparent; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; border: 0; }
QScrollBar::handle:vertical, QScrollBar::handle:horizontal { background: @border_strong@; border-radius: 3px; min-height: 28px; min-width: 28px; }
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover { background: @muted@; }
QScrollBar::handle:vertical:pressed, QScrollBar::handle:horizontal:pressed { background: @accent@; }

QTableWidget { gridline-color: @border@; background: @base@; }
QListWidget { background: @base@; border: 1px solid @border@; outline: 0; }
QListWidget::item { padding: 5px 8px; margin: 0px 2px 1px 2px; border-radius: 5px; }
QListWidget::item:hover { background: @hover@; }
QListWidget::item:selected, QListWidget::item:selected:!active { background: @accent_soft@; color: @text@; }
QHeaderView::section { padding: 6px; font-weight: 600; background: @button@; color: @muted@; border: 0; border-bottom: 1px solid @border@; border-right: 1px solid @border@; }

QPushButton { padding: 6px 10px; background: @button@; color: @text@; border: 1px solid @border_strong@; border-radius: 6px; }
QPushButton:hover { background: @hover@; border-color: @muted@; }
QPushButton:pressed { background: @pressed@; }
QPushButton:checked { background: @accent_soft@; border-color: @accent@; }
QPushButton:flat { background: transparent; border-color: transparent; }
QPushButton:focus { border-color: @accent@; }
QPushButton:disabled { background: @window@; color: @disabled@; border-color: @border@; }
QPushButton:default, QPushButton[primary="true"] { background: @accent@; color: @on_accent@; border-color: @accent@; }
QPushButton:default:hover, QPushButton[primary="true"]:hover { background: @accent_hover@; border-color: @accent_hover@; }
QPushButton:default:pressed, QPushButton[primary="true"]:pressed { background: @accent_press@; border-color: @accent_press@; }
QPushButton:default:disabled, QPushButton[primary="true"]:disabled { background: @window@; color: @disabled@; border-color: @border@; }

QToolBar { background: @window@; border: 0; spacing: 2px; padding: 0px; }
QToolBar::separator { background: @border@; width: 1px; margin: 5px 6px; }
QToolBar QToolButton { background: transparent; color: @text@; border: 1px solid transparent; border-radius: 6px; padding: 3px 8px; margin: 0px; }
QToolBar QToolButton:hover { background: @hover@; border-color: @border@; }
QToolBar QToolButton:pressed { background: @pressed@; }
QToolBar QToolButton:checked { background: @accent_soft@; border-color: @accent@; }
QToolBar QToolButton:disabled { color: @disabled@; }
QToolBar QToolButton[danger="true"] { color: @danger@; }
QToolBar QToolButton[danger="true"]:disabled { color: @disabled@; }
QToolBar QToolButton[primary="true"] { background: @accent@; color: @on_accent@; border-color: @accent@; font-weight: 600; }
QToolBar QToolButton[primary="true"]:hover { background: @accent_hover@; border-color: @accent_hover@; }
QToolBar QToolButton[primary="true"]:pressed { background: @accent_press@; border-color: @accent_press@; }
QToolBar QToolButton[primary="true"]:disabled { background: @button@; color: @disabled@; border-color: @border@; }

QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox { padding: 4px 6px; background: @base@; color: @text@; border: 1px solid @border_strong@; border-radius: 5px; }
QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover { border-color: @muted@; }
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:on { border-color: @accent@; }
QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled { color: @disabled@; background: @window@; border-color: @border@; }
QAbstractSpinBox QLineEdit, QComboBox QLineEdit { background: transparent; border: 0; border-radius: 0; padding: 0px; }
QComboBox QAbstractItemView { background: @base@; color: @text@; border: 1px solid @border_strong@; outline: 0; }

QMenu { background: @base@; color: @text@; border: 1px solid @border_strong@; padding: 4px; }
QMenu::item { padding: 6px 24px 6px 12px; border-radius: 4px; }
QMenu::item:selected { background: @accent@; color: @on_accent@; }
QMenu::item:disabled { color: @disabled@; }
QMenu::separator { height: 1px; background: @border@; margin: 4px 6px; }

QProgressBar { background: @base@; color: @text@; border: 1px solid @border_strong@; border-radius: 5px; text-align: center; }
QProgressBar::chunk { background: @accent@; border-radius: 4px; }
QSplitter::handle { background: @border@; }
QStatusBar { background: @window@; color: @muted@; border-top: 1px solid @border@; }
QStatusBar::item { border: 0; }
QStatusBar QLabel { color: @muted@; }
"""

def _build_app_stylesheet(tokens: dict[str, str]) -> str:
    """Monta a folha de estilo global trocando cada @token@ pelo valor correspondente."""
    qss = _APP_QSS
    for key, value in tokens.items():
        qss = qss.replace(f"@{key}@", value)
    return qss

def _apply_application_palette(app: QApplication, dark: bool, accent: str, settings: dict[str, Any] | None = None) -> None:
    settings = settings or {}
    t = _theme_tokens(
        dark,
        _normalized_color(accent).name(),
        _normalized_color(settings.get("light_surface", "#FFFFFF")).name(),
        _normalized_color(settings.get("light_contrast", "#2F343B")).name(),
    )
    pal = QPalette()
    for role, key in (
        (QPalette.Window, "window"), (QPalette.WindowText, "text"),
        (QPalette.Base, "base"), (QPalette.AlternateBase, "alt"), (QPalette.Text, "text"),
        (QPalette.Button, "button"), (QPalette.ButtonText, "text"),
        (QPalette.ToolTipBase, "tooltip"), (QPalette.ToolTipText, "text"),
        (QPalette.Highlight, "accent"), (QPalette.HighlightedText, "on_accent"),
        # Mid é a cor das bordas que o código antigo pede como palette(mid).
        (QPalette.Mid, "border_strong"),
    ):
        pal.setColor(role, QColor(t[key]))
    # Cores desabilitadas também acompanham o tema para evitar resíduos do
    # esquema anterior após a troca ao vivo.
    for role in (QPalette.Text, QPalette.WindowText, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, QColor(t["disabled"]))
    placeholder = getattr(QPalette, "PlaceholderText", None)
    if placeholder is not None:
        pal.setColor(placeholder, QColor(_mix_hex(t["base"], t["text"], 0.45)))
    # Fusion respeita integralmente QPalette em Windows; o estilo nativo pode
    # conservar partes do tema anterior em widgets complexos.
    try:
        app.setStyle("Fusion")
    except Exception:
        pass
    app.setPalette(pal)
    app.setStyleSheet(_build_app_stylesheet(t))

def _asset_path(name: str) -> Path:
    """Localiza um recurso distribuído junto ao Automation Studio."""
    return _RESOURCE_BASE / "resources" / name

def _load_brand_pixmap(dark: bool, size: int | None = None) -> QPixmap:
    # PNG é o caminho principal; SVG é fallback para instalações em que o
    # recurso rasterizado não tenha sido copiado pelo pacote.
    names = (
        ("as_icon_dark.png", "as_icon_dark.svg") if dark
        else ("as_icon_light.png", "as_icon_light.svg")
    )
    pix = QPixmap()
    for name in names:
        candidate = QPixmap(str(_asset_path(name)))
        if not candidate.isNull():
            pix = candidate
            break
    if size and not pix.isNull():
        pix = pix.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return pix

def _load_splash_pixmap(dark: bool) -> QPixmap:
    path = _asset_path("logo_dark.png" if dark else "logo_light.png")
    pix = QPixmap(str(path))
    if pix.isNull():
        pix = QPixmap(str(_asset_path("logo_dark.svg" if dark else "logo_light.svg")))
    return pix


# Export underscore-prefixed shared symbols too; UI modules intentionally use these.
__all__ = [name for name in globals() if not name.startswith("__")]
