"""Dublê FUNCIONAL e PARCIAL do PySide6 (AS_TEST_QT_STUB=widgets). Existe só para EXECUTAR, no ambiente de
desenvolvimento (sem Qt), a lógica Python dos diálogos — `CommandDialog` em especial. Não desenha nada.

Fidelidade: cada comportamento aqui reproduz o que a documentação do Qt diz, e `tests/gui/test_qt_semantics.py`
afirma os MESMOS comportamentos contra o PySide6 real. Se um deles falhar na sua máquina, o dublê estava errado
e qualquer conclusão tirada dele precisa ser revista. O dublê é ESTRITO: método que ele não implementa levanta
AttributeError (de propósito: assim um erro de digitação no teste ou no diálogo aparece em vez de passar calado).
Os nomes que o dublê não implementa (QMessageBox, QMenu, Qt, ...) caem num marcador permissivo, como no qt_stub.
"""
from __future__ import annotations

import inspect
import os
import struct


# --------------------------------------------------------------------------------------------- marcador permissivo
class _Meta(type):
    def __getattr__(cls, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return placeholder(name)

    def __or__(cls, other): return cls
    def __ror__(cls, other): return cls
    def __and__(cls, other): return cls
    def __rand__(cls, other): return cls
    def __invert__(cls): return cls


class _Any(metaclass=_Meta):
    def __init__(self, *a, **k): pass

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _Any()

    def __call__(self, *a, **k):
        if len(a) == 1 and callable(a[0]) and not k:  # uso como decorator (@Slot(...))
            return a[0]
        return _Any()

    def __or__(self, o): return self
    __ror__ = __and__ = __rand__ = __or__
    def __iter__(self): return iter(())
    def __int__(self): return 0
    def __index__(self): return 0
    def __float__(self): return 0.0
    def __bool__(self): return True


_placeholders: dict[str, type] = {}


def placeholder(name: str) -> type:
    if name not in _placeholders:
        _placeholders[name] = _Meta(name, (_Any,), {})
    return _placeholders[name]


# ---------------------------------------------------------------------------------------------------- sinais
def _max_positional(slot, available: int) -> int:
    """O Qt chama o slot só com os argumentos que ele aceita (um slot sem parâmetros liga a um sinal com int)."""
    try:
        signature = inspect.signature(slot)
    except (TypeError, ValueError):
        return available
    count = 0
    for parameter in signature.parameters.values():
        if parameter.kind is parameter.VAR_POSITIONAL:
            return available
        if parameter.kind in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD):
            count += 1
    return min(available, count)


class BoundSignal:
    def __init__(self) -> None:
        self._slots: list = []
        self.emitted: list[tuple] = []  # histórico, útil para os testes do dublê

    def connect(self, slot, *_args, **_kwargs):
        self._slots.append(slot)

    def disconnect(self, slot=None) -> None:
        if slot is None:
            self._slots.clear()
        else:
            self._slots.remove(slot)

    def emit(self, *args) -> None:
        self.emitted.append(args)
        for slot in list(self._slots):
            slot(*args[:_max_positional(slot, len(args))])


class Signal:
    """Declaração no corpo da classe: `evento = Signal(int)`. Cada instância ganha o seu sinal."""

    def __init__(self, *_types, **_kwargs) -> None:
        self._name = "_sinal"

    def __set_name__(self, owner, name) -> None:
        self._name = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return obj.__dict__.setdefault("_sinal_" + self._name, BoundSignal())

    # Quando `Signal(...)` é usado fora de uma classe (como no qt_stub), continua inofensivo.
    def connect(self, *_a, **_k): pass
    def emit(self, *_a, **_k): pass


# -------------------------------------------------------------------------------------------------------- objetos
class _QtMeta(type):
    """Constantes do Qt (QComboBox.NoInsert, QSizePolicy.Expanding...) viram marcadores; MÉTODO inexistente continua
    sendo erro. Nome com maiúscula inicial = constante; minúscula = método."""

    def __getattr__(cls, name):
        if name[:1].isupper() and not name.startswith("__"):
            return placeholder(name)
        raise AttributeError(f"type object {cls.__name__!r} has no attribute {name!r}")


class QObject(metaclass=_QtMeta):
    def __init__(self, parent=None) -> None:
        self._qparent = None
        self._qchildren: list = []
        self._set_parent(parent)

    def _set_parent(self, parent) -> None:
        if self._qparent is not None and self in self._qparent._qchildren:
            self._qparent._qchildren.remove(self)
        self._qparent = parent
        if parent is not None and isinstance(parent, QObject):
            parent._qchildren.append(self)

    def parent(self):
        return self._qparent

    def setObjectName(self, name) -> None: self._object_name = str(name)
    def objectName(self) -> str: return getattr(self, "_object_name", "")

    def findChildren(self, cls, *_args, **_kwargs) -> list:
        found = []
        for child in self._qchildren:
            if isinstance(child, cls):
                found.append(child)
            if isinstance(child, QObject):
                found.extend(child.findChildren(cls))
        return found

    def deleteLater(self) -> None:
        self._deleted = True


class QPoint:
    """O QPoint do PySide6 NÃO é subscritível (não tem __getitem__): só x() e y(). Hipótese 2.07-c do relatório."""

    def __init__(self, x: int = 0, y: int = 0) -> None:
        self._x, self._y = int(x), int(y)

    def x(self) -> int: return self._x
    def y(self) -> int: return self._y
    def setX(self, x: int) -> None: self._x = int(x)
    def setY(self, y: int) -> None: self._y = int(y)
    def isNull(self) -> bool: return self._x == 0 and self._y == 0
    def __eq__(self, other): return isinstance(other, QPoint) and (self._x, self._y) == (other._x, other._y)
    def __hash__(self): return hash((self._x, self._y))
    def __repr__(self): return f"PySide6.QtCore.QPoint({self._x}, {self._y})"


class QPixmap:
    def __init__(self, *args) -> None:
        self._w = self._h = 0
        if len(args) == 2 and all(isinstance(a, int) for a in args):
            self._w, self._h = args
        elif len(args) == 1 and isinstance(args[0], str):
            self._read_png_size(args[0])

    def _read_png_size(self, path: str) -> None:
        try:
            with open(path, "rb") as handle:
                head = handle.read(24)
        except OSError:
            return
        if head[:8] == b"\x89PNG\r\n\x1a\n" and head[12:16] == b"IHDR":
            self._w, self._h = struct.unpack(">II", head[16:24])

    def isNull(self) -> bool: return self._w == 0 or self._h == 0
    def width(self) -> int: return self._w
    def height(self) -> int: return self._h

    def scaled(self, width: int, height: int, *_args) -> "QPixmap":
        if self.isNull():
            return QPixmap()
        ratio = min(width / self._w, height / self._h)
        return QPixmap(max(1, round(self._w * ratio)), max(1, round(self._h * ratio)))


# ------------------------------------------------------------------------------------------------------ widgets
class QWidget(QObject):
    def __init__(self, parent=None, *_flags) -> None:
        super().__init__(parent)
        self._hidden = parent is None  # janela de topo nasce escondida; filho só some se alguém o esconder
        self._enabled = True
        self._layout = None
        self._tooltip = ""
        self._stylesheet = ""
        self._window_title = ""
        self._modal = False

    # ---- cosméticos (sem efeito nos testes, mas guardam o valor)
    def setToolTip(self, text) -> None: self._tooltip = str(text)
    def toolTip(self) -> str: return self._tooltip
    def setStyleSheet(self, text) -> None: self._stylesheet = str(text)
    def setSizePolicy(self, *_a) -> None: pass
    def setMinimumWidth(self, _w) -> None: pass
    def setMaximumWidth(self, _w) -> None: pass
    def setMinimumHeight(self, _h) -> None: pass
    def setMaximumHeight(self, _h) -> None: pass
    def updateGeometry(self) -> None: pass
    def setAttribute(self, *_a) -> None: pass
    def setWindowFlags(self, *_a) -> None: pass
    def setWindowTitle(self, text) -> None: self._window_title = str(text)
    def windowTitle(self) -> str: return self._window_title
    def setModal(self, flag) -> None: self._modal = bool(flag)
    def width(self) -> int: return 100
    def height(self) -> int: return 30

    # ---- visibilidade e habilitação
    def setVisible(self, flag) -> None: self._hidden = not bool(flag)
    def show(self) -> None: self.setVisible(True)
    def hide(self) -> None: self.setVisible(False)
    def isHidden(self) -> bool: return self._hidden

    def isVisible(self) -> bool:
        return (not self._hidden) and (self._qparent is None or self._qparent.isVisible())

    def isVisibleTo(self, ancestor) -> bool:
        widget = self
        while widget is not None:
            if widget is ancestor:
                return True
            if widget._hidden:
                return False
            widget = widget._qparent
        return False

    def setEnabled(self, flag) -> None: self._enabled = bool(flag)
    def isEnabled(self) -> bool: return self._enabled

    def layout(self):
        return self._layout

    def parentWidget(self):
        """O widget pai (None se não há ou se o pai não é um widget), como no Qt."""
        return self._qparent if isinstance(self._qparent, QWidget) else None

    def _attach_layout(self, layout) -> None:
        self._layout = layout
        layout._attach(self)


class QDialog(QWidget):
    Accepted, Rejected = 1, 0

    def __init__(self, parent=None, *_flags) -> None:
        super().__init__(parent)
        self.accepted, self.rejected, self.finished = BoundSignal(), BoundSignal(), BoundSignal()
        self._result = 0

    def accept(self) -> None:
        self._result = QDialog.Accepted
        self.accepted.emit()
        self.finished.emit(self._result)

    def reject(self) -> None:
        self._result = QDialog.Rejected
        self.rejected.emit()
        self.finished.emit(self._result)

    def result(self) -> int: return self._result

    def exec(self):
        raise NotImplementedError("o dublê não tem laço de eventos: use accept()/reject() ou _accept()")


class QFrame(QWidget):
    pass


class QLabel(QWidget):
    def __init__(self, text="", parent=None) -> None:
        if isinstance(text, QWidget):  # QLabel(parent)
            text, parent = "", text
        super().__init__(parent)
        self._text, self._pixmap = str(text), None

    def setText(self, text) -> None:
        self._text, self._pixmap = str(text), None  # setText apaga a imagem (documentação do QLabel)

    def text(self) -> str: return self._text

    def setPixmap(self, pixmap) -> None:
        self._pixmap, self._text = pixmap, ""  # setPixmap apaga o texto

    def pixmap(self):
        return self._pixmap if self._pixmap is not None else QPixmap()

    def setWordWrap(self, _flag) -> None: pass
    def setAlignment(self, _alignment) -> None: pass


class QAbstractButton(QWidget):
    def __init__(self, text="", parent=None) -> None:
        if isinstance(text, QWidget):
            text, parent = "", text
        super().__init__(parent)
        self._text = str(text)
        self.clicked = BoundSignal()

    def setText(self, text) -> None: self._text = str(text)
    def text(self) -> str: return self._text


class QPushButton(QAbstractButton):
    def click(self) -> None:
        if self._enabled:
            self.clicked.emit(False)


class QCheckBox(QAbstractButton):
    def __init__(self, text="", parent=None) -> None:
        super().__init__(text, parent)
        self._checked = False
        self.toggled = BoundSignal()

    def isChecked(self) -> bool: return self._checked

    def setChecked(self, flag) -> None:
        flag = bool(flag)
        if flag != self._checked:
            self._checked = flag
            self.toggled.emit(flag)

    def click(self) -> None:
        if self._enabled:
            self.setChecked(not self._checked)
            self.clicked.emit(self._checked)


class QLineEdit(QWidget):
    def __init__(self, text="", parent=None) -> None:
        if isinstance(text, QWidget):
            text, parent = "", text
        super().__init__(parent)
        self._text = str(text)
        self._placeholder = ""
        self.textChanged = BoundSignal()

    def text(self) -> str: return self._text

    def setText(self, text) -> None:
        text = str(text)
        if text != self._text:
            self._text = text
            self.textChanged.emit(text)

    def clear(self) -> None: self.setText("")
    def setPlaceholderText(self, text) -> None: self._placeholder = str(text)
    def placeholderText(self) -> str: return self._placeholder


class QTextEdit(QWidget):
    def __init__(self, text="", parent=None) -> None:
        if isinstance(text, QWidget):
            text, parent = "", text
        super().__init__(parent)
        self._text = str(text)
        self._placeholder = ""
        self.textChanged = BoundSignal()

    def toPlainText(self) -> str: return self._text

    def setPlainText(self, text) -> None:
        text = str(text)
        if text != self._text:
            self._text = text
            self.textChanged.emit()

    def setPlaceholderText(self, text) -> None: self._placeholder = str(text)
    def setReadOnly(self, _flag) -> None: pass


class _SpinBase(QWidget):
    _integer = True

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._min, self._max = (0, 99) if self._integer else (0.0, 99.99)
        self._decimals, self._value = 2, 0 if self._integer else 0.0
        self._suffix = ""
        self.valueChanged = BoundSignal()

    def _fit(self, value):
        value = max(self._min, min(self._max, value))
        return int(round(value)) if self._integer else round(float(value), self._decimals)

    def setRange(self, low, high) -> None:
        self._min, self._max = (int(low), int(high)) if self._integer else (float(low), float(high))
        self.setValue(self._value)

    def setMaximum(self, high) -> None: self.setRange(self._min, high)
    def setMinimum(self, low) -> None: self.setRange(low, self._max)
    def setSingleStep(self, _step) -> None: pass
    def setSuffix(self, text) -> None: self._suffix = str(text)

    def setValue(self, value) -> None:
        value = self._fit(value)
        if value != self._value:
            self._value = value
            self.valueChanged.emit(value)

    def value(self): return self._value
    def minimum(self): return self._min
    def maximum(self): return self._max


class QSpinBox(_SpinBase):
    _integer = True


class QDoubleSpinBox(_SpinBase):
    _integer = False

    def setDecimals(self, digits) -> None:
        self._decimals = int(digits)
        self._value = round(self._value, self._decimals)

    def decimals(self) -> int: return self._decimals


class QComboBox(QWidget):
    """Semântica do QComboBox (documentação do Qt), a que importa para os diálogos do Studio:
    - o primeiro item adicionado vira o atual (índice 0) e currentIndexChanged é emitido;
    - findText() é exato e distingue maiúsculas por padrão; findData() compara o dado; ambos devolvem -1 se não há;
    - num combo NÃO editável, setCurrentText(texto) só seleciona se existir um item com esse texto;
    - num combo editável, setCurrentText()/setEditText() mexe só no texto do campo e NÃO muda o índice atual;
    - currentText() num combo editável é o texto do campo; currentData() é o dado do item de índice atual (None se -1).
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._items: list[list] = []  # [texto, dado]
        self._index = -1
        self._editable = False
        self._edit_text = ""
        self.currentIndexChanged = BoundSignal()
        self.editTextChanged = BoundSignal()

    # ---- conteúdo
    def addItem(self, text, userData=None) -> None:
        self._items.append([str(text), userData])
        if self._index == -1:
            self._set_index(0)

    def addItems(self, texts) -> None:
        for text in texts:
            self.addItem(text)

    def clear(self) -> None:
        self._items.clear()
        self._set_index(-1)

    def count(self) -> int: return len(self._items)
    def itemText(self, index: int) -> str: return self._items[index][0] if 0 <= index < len(self._items) else ""
    def itemData(self, index: int, _role=None): return self._items[index][1] if 0 <= index < len(self._items) else None

    def findText(self, text, _flags=None) -> int:
        for position, (item_text, _data) in enumerate(self._items):
            if item_text == str(text):
                return position
        return -1

    def findData(self, data, *_args) -> int:
        for position, (_text, item_data) in enumerate(self._items):
            if item_data is not None and item_data == data:
                return position
        return -1

    # ---- seleção
    def _set_index(self, index: int) -> None:
        changed = index != self._index
        self._index = index
        if self._editable:
            self._edit_text = self.itemText(index)
        if changed:
            self.currentIndexChanged.emit(index)

    def setCurrentIndex(self, index: int) -> None:
        # No Qt, um índice fora da faixa (inclusive em combo vazio) deixa o combo sem seleção (-1); num editável, o campo é limpo.
        self._set_index(index if 0 <= index < len(self._items) else -1)

    def currentIndex(self) -> int: return self._index

    def setCurrentText(self, text) -> None:
        if self._editable:
            self.setEditText(text)
        else:
            position = self.findText(text)
            if position > -1:
                self.setCurrentIndex(position)

    def currentText(self) -> str:
        return self._edit_text if self._editable else self.itemText(self._index)

    def currentData(self, _role=None):
        return self.itemData(self._index)

    # ---- modo editável
    def setEditable(self, flag) -> None:
        flag = bool(flag)
        if flag and not self._editable:
            self._edit_text = self.itemText(self._index)
        self._editable = flag

    def isEditable(self) -> bool: return self._editable

    def setEditText(self, text) -> None:
        if self._editable:
            self._edit_text = str(text)
            self.editTextChanged.emit(self._edit_text)

    def setInsertPolicy(self, _policy) -> None: pass
    def setPlaceholderText(self, _text) -> None: pass


class QListWidgetItem:
    def __init__(self, text="", *_args) -> None:
        self._text, self._data = str(text), {}

    def setText(self, text) -> None: self._text = str(text)
    def text(self) -> str: return self._text
    def setData(self, role, value) -> None: self._data[role] = value
    def data(self, role): return self._data.get(role)
    def setToolTip(self, text) -> None: self._tooltip = str(text)
    def toolTip(self) -> str: return getattr(self, "_tooltip", "")
    def setHidden(self, flag) -> None: self._hidden = bool(flag)
    def isHidden(self) -> bool: return getattr(self, "_hidden", False)


class QListWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[QListWidgetItem] = []
        self._current = -1

    def addItem(self, item) -> None:
        self._rows.append(item if isinstance(item, QListWidgetItem) else QListWidgetItem(item))

    def count(self) -> int: return len(self._rows)
    def item(self, row: int):
        return self._rows[row] if 0 <= row < len(self._rows) else None
    def currentRow(self) -> int: return self._current

    def setCurrentRow(self, row: int) -> None:
        self._current = row if -1 <= row < len(self._rows) else self._current

    def takeItem(self, row: int):
        if not 0 <= row < len(self._rows):
            return None
        item = self._rows.pop(row)
        if self._current >= len(self._rows):
            self._current = len(self._rows) - 1
        return item

    def clear(self) -> None:
        self._rows.clear()
        self._current = -1


class QGroupBox(QWidget):
    def __init__(self, title="", parent=None) -> None:
        if isinstance(title, QWidget):
            title, parent = "", title
        super().__init__(parent)
        self._title = str(title)

    def title(self) -> str: return self._title


class QDialogButtonBox(QWidget):
    Ok, Save, Close, Cancel = 0x400, 0x800, 0x200000, 0x400000

    def __init__(self, buttons=0, parent=None) -> None:
        super().__init__(parent)
        self.accepted, self.rejected = BoundSignal(), BoundSignal()
        self._buttons = {}
        for flag in (self.Ok, self.Save, self.Close, self.Cancel):
            if int(buttons) & flag:
                button = QPushButton("", self)
                self._buttons[flag] = button
                button.clicked.connect(self.accepted.emit if flag in (self.Ok, self.Save) else self.rejected.emit)

    def button(self, which):
        return self._buttons.get(int(which))


# ------------------------------------------------------------------------------------------------------ layouts
class _Item:
    def __init__(self, widget=None, layout=None) -> None:
        self._widget, self._layout = widget, layout

    def widget(self): return self._widget
    def layout(self): return self._layout


class QLayout(QObject):
    def __init__(self, parent=None) -> None:
        owner = parent if isinstance(parent, QWidget) else None
        super().__init__(None)
        self._owner = None
        self._items: list[_Item] = []
        self._margins, self._spacing = None, None
        if owner is not None:
            owner._attach_layout(self)

    def _attach(self, owner) -> None:
        self._owner = owner
        for item in self._items:
            if item.widget() is not None:
                item.widget()._set_parent(owner)
            if item.layout() is not None:
                item.layout()._attach(owner)

    def _take_widget(self, widget) -> None:
        if widget is not None:
            if self._owner is not None:
                widget._set_parent(self._owner)

    def setContentsMargins(self, *margins) -> None: self._margins = margins
    def setSpacing(self, spacing) -> None: self._spacing = spacing
    def count(self) -> int: return len(self._items)

    def removeWidget(self, widget) -> None:
        self._items = [item for item in self._items if item.widget() is not widget]


class QBoxLayout(QLayout):
    def addWidget(self, widget, stretch=0, alignment=0) -> None:
        self._items.append(_Item(widget=widget))
        self._take_widget(widget)

    def addLayout(self, layout, stretch=0) -> None:
        self._items.append(_Item(layout=layout))
        if self._owner is not None:
            layout._attach(self._owner)

    def addStretch(self, stretch=0) -> None:
        self._items.append(_Item())

    def indexOf(self, widget) -> int:
        """Posição do widget NESTE layout (não olha os layouts filhos, como o Qt); -1 se não está."""
        for position, item in enumerate(self._items):
            if item.widget() is widget:
                return position
        return -1

    def insertWidget(self, index: int, widget, stretch=0, alignment=0) -> None:
        """Índice negativo = no fim. Índice maior que o número de itens o Qt 6 não aceita (comportamento indefinido): aqui é erro."""
        if index > len(self._items):
            raise IndexError(f"insertWidget({index}) com só {len(self._items)} itens: o Qt 6 não aceita")
        self._items.insert(len(self._items) if index < 0 else index, _Item(widget=widget))
        self._take_widget(widget)

    def itemAt(self, index: int):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int):
        return self._items.pop(index) if 0 <= index < len(self._items) else None


class QVBoxLayout(QBoxLayout):
    pass


class QHBoxLayout(QBoxLayout):
    pass


class QFormLayout(QLayout):
    AllNonFixedFieldsGrow, ExpandingFieldsGrow, FieldsStayAtSizeHint = 1, 2, 0
    DontWrapRows, WrapLongRows, WrapAllRows = 0, 1, 2
    LabelRole, FieldRole, SpanningRole = 0, 1, 2

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[dict] = []

    def addRow(self, label, field=None) -> None:
        if field is None:  # addRow(widget) / addRow(layout): ocupa a linha inteira
            self._rows.append({"label": None, "field": label})
        else:
            if isinstance(label, str):
                label = QLabel(label)
            self._rows.append({"label": label, "field": field})
        row = self._rows[-1]
        for part in (row["label"], row["field"]):
            if isinstance(part, QWidget):
                self._take_widget(part)
            elif isinstance(part, QLayout) and self._owner is not None:
                part._attach(self._owner)

    def _attach(self, owner) -> None:
        self._owner = owner
        for row in self._rows:
            for part in (row["label"], row["field"]):
                if isinstance(part, QWidget):
                    part._set_parent(owner)
                elif isinstance(part, QLayout):
                    part._attach(owner)

    def rowCount(self) -> int: return len(self._rows)

    def setRowVisible(self, row: int, visible) -> None:
        if not 0 <= row < len(self._rows):
            raise IndexError(row)
        for part in (self._rows[row]["label"], self._rows[row]["field"]):
            if isinstance(part, QWidget):
                part.setVisible(visible)

    def itemAt(self, row: int, role: int):
        if not 0 <= row < len(self._rows):
            return None
        part = self._rows[row]["label" if role == self.LabelRole else "field"]
        if part is None:
            return None
        return _Item(widget=part if isinstance(part, QWidget) else None, layout=part if isinstance(part, QLayout) else None)

    def setFieldGrowthPolicy(self, _policy) -> None: pass
    def setLabelAlignment(self, _alignment) -> None: pass
    def setRowWrapPolicy(self, _policy) -> None: pass
    def setHorizontalSpacing(self, _n) -> None: pass
    def setVerticalSpacing(self, _n) -> None: pass


__all__ = [
    "BoundSignal", "QAbstractButton", "QBoxLayout", "QCheckBox", "QComboBox", "QDialog", "QDialogButtonBox",
    "QDoubleSpinBox", "QFormLayout", "QFrame", "QGroupBox", "QHBoxLayout", "QLabel", "QLayout", "QLineEdit",
    "QListWidget", "QListWidgetItem", "QObject", "QPixmap", "QPoint", "QPushButton", "QSpinBox", "QTextEdit",
    "QVBoxLayout", "QWidget", "Signal", "placeholder",
]
