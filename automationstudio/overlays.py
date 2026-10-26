from __future__ import annotations



from .core import *


class KeyboardWidget(QWidget):
    """Teclado visual com dois modos:

    - compacto: mostra apenas a combinação atualmente pressionada. Ao soltar
      todas as teclas, conserva somente a última combinação por alguns segundos.
    - completo: desenha o teclado ABNT2 inteiro e permite clicar nas teclas.
    """
    keyClicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = _load_keyboard_layout()
        self._ref_w = float(self._layout.get("ref_w", 1100))
        self._ref_h = float(self._layout.get("ref_h", 410))
        self._active: list[str] = []
        self._last_chord: list[str] = []
        self._last_release = 0.0
        self._mode = "compact"
        self._timeout = 3.0
        self._base_opacity = 1.0
        self._clickable = True
        self._flash_labels: set[str] = set()
        self._flash_until = 0.0
        self._dark_theme=True; self._virtual_accent=QColor('#ffc53d'); self._virtual_surface=QColor('#4a4f57'); self._virtual_text=QColor('#ffc53d')
        self._timer = QTimer(self)
        self._timer.setInterval(60)
        self._timer.timeout.connect(self._expire)
        self._timer.start()
        self.setMinimumSize(260, 90)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

    def set_theme(self, dark: bool, accent: str, surface: str, text: str) -> None:
        self._dark_theme=bool(dark); self._virtual_accent=_normalized_color(accent)
        self._virtual_surface=_normalized_color(surface); self._virtual_text=_normalized_color(text)
        self.update()

    def set_display(self, mode="compact", timeout=3, opacity=1, clickable=True):
        self._mode = mode if mode in ("compact", "full") else "compact"
        self._timeout = max(.2, float(timeout))
        self._base_opacity = max(0., min(1., float(opacity)))
        self._clickable = bool(clickable)
        self.update()

    def _canonical_label(self, label: str) -> str:
        # Windows/ABNT2 possui dois Shift e dois Ctrl físicos, mas na
        # representação de combinação eles são uma única tecla lógica.
        return {
            'ShiftLeft': 'Shift', 'ShiftRight': 'Shift',
            'CtrlLeft': 'Ctrl', 'CtrlRight': 'Ctrl',
            'AltLeft': 'Alt', 'AltRight': 'Alt',
            'WinLeft': 'Win', 'WinRight': 'Win',
        }.get(label, label)

    def _visual_chord(self, labels) -> list[str]:
        result=[]
        for label in labels:
            canonical=self._canonical_label(label)
            if canonical and canonical not in result:
                result.append(canonical)
        # Ordem convencional: modificadores primeiro, tecla principal por último.
        priority={'Ctrl':0,'Alt':1,'AltGr':2,'Shift':3,'Win':4}
        return sorted(result, key=lambda x:(priority.get(x,10), x.upper()))

    def press(self, target):
        labels = resolve_key_labels(target)
        if not labels:
            return
        for label in labels:
            if label not in self._active:
                self._active.append(label)
        # O chord atual representa somente teclas simultaneamente pressionadas.
        # Nunca acumulamos sequências antigas.
        self._last_chord = []
        self._last_release = 0.0
        self.update()

    def release(self, target):
        labels = resolve_key_labels(target)
        if not labels:
            return
        # Capturamos o chord COMPLETO antes de remover a última tecla. Assim,
        # Shift+A termina como "Shift + A", e não apenas "A" ou "Shift".
        before = list(self._active)
        for label in labels:
            if label in self._active:
                self._active.remove(label)
        if not self._active and before:
            self._last_chord = self._visual_chord(before)
            self._last_release = __import__('time').monotonic()
        self.update()

    def clear(self):
        self._active.clear()
        self._last_chord.clear()
        self._last_release = 0.0
        self._flash_labels.clear()
        self._flash_until = 0.0
        self.update()

    def _expire(self):
        now = __import__('time').monotonic()
        if self._flash_labels and now >= self._flash_until:
            self._flash_labels.clear()
            self._flash_until = 0.0
        if not self._active and self._last_release and now - self._last_release >= self._timeout:
            self._last_chord.clear()
            self._last_release = 0.0
        if self._flash_labels or self._last_release:
            self.update()

    def _transform(self):
        scale = min(self.width()/self._ref_w, self.height()/self._ref_h)
        return scale, (self.width()-self._ref_w*scale)/2, (self.height()-self._ref_h*scale)/2

    def _compact_items(self):
        if self._active:
            return self._visual_chord(self._active), self._base_opacity
        if self._last_chord and self._last_release:
            rem = max(0., 1.-(__import__('time').monotonic()-self._last_release)/self._timeout)
            return list(self._last_chord), self._base_opacity*rem
        return [], 0.0

    def _label_text(self, label):
        return _DISPLAY.get(label, label)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # Fundo translúcido visível: o guia não fica invisível sobre vídeos
        # claros, mas também não cria um grande retângulo preto opaco.
        # Área externa totalmente transparente: somente as teclas são destacadas.
        if self._mode == "compact":
            items, alpha = self._compact_items()
            if not items or alpha <= 0:
                return
            texts = [self._label_text(x) for x in items]
            # Uma combinação fica visualmente explícita: CTRL + SHIFT + E.
            parts = []
            for i, text in enumerate(texts):
                if i:
                    parts.append(("+", False))
                parts.append((text, True))
            widths = []
            for text, is_key in parts:
                widths.append(max(32., min(100., len(text)*9+24)) if is_key else 18.)
            total = sum(widths) + max(0, len(widths)-1)*4
            x = max(6., (self.width()-total)/2)
            h = min(42., max(30., self.height()-12)); y = (self.height()-h)/2
            for (text, is_key), w in zip(parts, widths):
                if not is_key:
                    p.setPen(QColor(self._virtual_accent.red(), self._virtual_accent.green(), self._virtual_accent.blue(), int(255*alpha)))
                    p.setFont(QFont("Segoe UI", max(10, int(h*.34)), QFont.Weight.Bold))
                    p.drawText(QRectF(x, y, w, h), Qt.AlignCenter, text)
                else:
                    rect=QRectF(x,y,w,h)
                    p.setPen(QPen(QColor(self._virtual_accent.red(),self._virtual_accent.green(),self._virtual_accent.blue(),int(255*alpha)), max(1.,1.5*alpha)))
                    is_active = (bool(self._active) and text in [self._label_text(x) for x in self._visual_chord(self._active)]) or text in [self._label_text(x) for x in self._visual_chord(self._flash_labels)]
                    fill = self._virtual_accent if is_active else self._virtual_surface
                    txt = QColor("#111111") if is_active else self._virtual_text
                    border = self._virtual_accent
                    p.setBrush(QColor(fill.red(),fill.green(),fill.blue(),int(245*alpha)))
                    p.setPen(QPen(QColor(border.red(),border.green(),border.blue(),int(255*alpha)), max(1.,1.5*alpha)))
                    p.drawRoundedRect(rect,8,8)
                    p.setPen(QColor(txt.red(),txt.green(),txt.blue(),int(255*alpha)))
                    p.setFont(QFont("Segoe UI", max(8,int(h*.32)), QFont.Weight.Bold))
                    p.drawText(rect,Qt.AlignCenter,text)
                x += w+4
            return

        scale, ox, oy = self._transform()
        for k in self._layout["keys"]:
            label=k["label"]
            active=(label in self._active or label in self._flash_labels)
            # No modo completo, as teclas continuam visíveis mesmo sem atividade.
            alpha=1.0
            rect=QRectF(ox+k["x"]*scale,oy+k["y"]*scale,k["w"]*scale,k["h"]*scale)
            # Teclas inativas: cinza com contorno/texto dourados.
            # Teclas pressionadas: amarelas com texto preto.
            fill = self._virtual_accent if active else self._virtual_surface
            border = self._virtual_accent
            txt = QColor("#111111") if active else self._virtual_text
            fill = QColor(fill.red(), fill.green(), fill.blue(), 245 if active else 225)
            border = QColor(border.red(), border.green(), border.blue(), 255)
            txt = QColor(txt.red(), txt.green(), txt.blue(), 255)
            p.setPen(QPen(border,max(1.,1.2*scale))); p.setBrush(fill)
            p.drawRoundedRect(rect,max(3,5*scale),max(3,5*scale))
            label_text=_DISPLAY.get(label,label)
            p.setPen(txt)
            p.setFont(QFont("Segoe UI",max(5,int((7 if label in _LONG else 10)*scale)),QFont.Weight.Bold if active else QFont.Weight.Normal))
            p.drawText(rect,Qt.AlignCenter,label_text)

    def mousePressEvent(self,e):
        if self._mode != "full" or not self._clickable or e.button() != Qt.LeftButton:
            return super().mousePressEvent(e)
        scale,ox,oy=self._transform(); px=(e.position().x()-ox)/scale; py=(e.position().y()-oy)/scale
        for k in self._layout["keys"]:
            if k["x"] <= px <= k["x"]+k["w"] and k["y"] <= py <= k["y"]+k["h"]:
                self.keyClicked.emit(k["label"])
                self.press(k["label"]); self.release(k["label"])
                self._flash_labels = set(resolve_key_labels(k["label"])) or {k["label"]}
                self._flash_until = __import__('time').monotonic() + 0.16
                self.update()
                return
        super().mousePressEvent(e)

class MouseWidget(QWidget):
    """Mouse visual limpo. Setas amarelas ao redor indicam MOVIMENTO;
    scroll usa somente um indicador discreto na roda, sem reaproveitar as setas.
    """
    def __init__(self,parent=None):
        super().__init__(parent)
        self._pressed=set(); self._scroll_dir=None; self._move_dirs=set()
        self._timeout=3.; self._base_opacity=1.; self._last_activity=0.; self._scroll_until=0.; self._move_until=0.
        self._dark_theme=True; self._virtual_accent=QColor('#ffc53d'); self._virtual_surface=QColor('#4a4f57'); self._virtual_text=QColor('#ffc53d')
        self._timer=QTimer(self); self._timer.setInterval(50); self._timer.timeout.connect(self.update); self._timer.start()
        self.setMinimumSize(80,110); self.setAttribute(Qt.WA_TranslucentBackground,True)

    def set_theme(self, dark: bool, accent: str, surface: str, text: str) -> None:
        self._dark_theme=bool(dark); self._virtual_accent=_normalized_color(accent)
        self._virtual_surface=_normalized_color(surface); self._virtual_text=_normalized_color(text)
        self.update()

    def set_display(self,timeout=3,opacity=1):
        self._timeout=max(.2,float(timeout)); self._base_opacity=max(0.,min(1.,float(opacity))); self.update()
    def _touch(self): self._last_activity=__import__('time').monotonic(); self.update()
    def press(self,b): self._pressed.add(b); self._touch()
    def release(self,b): self._pressed.discard(b); self._touch()
    def scroll(self,dx,dy):
        self._scroll_dir = 'up' if dy>0 else ('down' if dy<0 else ('right' if dx>0 else 'left' if dx<0 else None))
        self._scroll_until=__import__('time').monotonic()+.55; self._touch()
    def move_direction(self,dx,dy):
        dirs=set()
        if abs(dx)+abs(dy)>0:
            if dy < 0: dirs.add('up')
            if dy > 0: dirs.add('down')
            if dx < 0: dirs.add('left')
            if dx > 0: dirs.add('right')
        if dirs:
            self._move_dirs=dirs; self._move_until=__import__('time').monotonic()+.75; self._touch()
    def clear(self):
        self._pressed.clear(); self._scroll_dir=None; self._move_dirs.clear(); self._last_activity=0; self.update()
    def _alpha(self):
        if not self._last_activity:return 0
        return self._base_opacity*max(0.,1.-(__import__('time').monotonic()-self._last_activity)/self._timeout)
    def paintEvent(self,e):
        import time
        a=self._alpha()
        if a<=0:return
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        # Área externa totalmente transparente: somente o mouse e seus indicadores aparecem.
        s=min((self.width()-16)/190.,(self.height()-16)/270.); ox=(self.width()-190*s)/2; oy=(self.height()-270*s)/2; p.translate(ox,oy); p.scale(s,s)
        # Corpo escuro translúcido, mas claramente visível sobre fundos claros.
        body=QPainterPath(); body.addRoundedRect(QRectF(55,45,80,155),30,30)
        p.setBrush(QColor(self._virtual_surface.red(),self._virtual_surface.green(),self._virtual_surface.blue(),int(245*a))); p.setPen(QPen(QColor(self._virtual_accent.red(),self._virtual_accent.green(),self._virtual_accent.blue(),int(245*a)),2)); p.drawPath(body)
        # Divisão dos botões frontais também usa o dourado do guia.
        p.setPen(QPen(QColor(self._virtual_accent.red(),self._virtual_accent.green(),self._virtual_accent.blue(),int(190*a)),1.5)); p.drawLine(95,48,95,92); p.drawLine(57,92,133,92)
        # Botões laterais X1/X2 integrados ao corpo, sem criar caixas soltas.
        for name, rect in [('x1', QRectF(46,105,12,28)), ('x2', QRectF(46,139,12,28))]:
            active = name in self._pressed
            p.setBrush(QColor(self._virtual_accent.red(),self._virtual_accent.green(),self._virtual_accent.blue(),int(245*a)) if active else QColor(self._virtual_surface.red(),self._virtual_surface.green(),self._virtual_surface.blue(),int(220*a)))
            p.setPen(QPen(self._virtual_accent.lighter(135) if active else self._virtual_accent,1.2))
            p.drawRoundedRect(rect,4,4)
        # Roda: brilho amarelo somente em scroll.
        wheel_active = time.monotonic() < self._scroll_until and self._scroll_dir is not None
        p.setBrush(QColor(self._virtual_accent.red(),self._virtual_accent.green(),self._virtual_accent.blue(),int(235*a)) if wheel_active else QColor(self._virtual_surface.red(),self._virtual_surface.green(),self._virtual_surface.blue(),int(170*a)))
        p.setPen(QPen(self._virtual_accent.lighter(120) if wheel_active else self._virtual_accent,1.2))
        p.drawRoundedRect(QRectF(88,72,14,38),7,7)
        # Clique: destaca a metade correspondente, sem criar quadrados extras.
        for name,rect in [('left',QRectF(58,48,36,42)),('right',QRectF(96,48,36,42))]:
            if name in self._pressed:
                p.setBrush(QColor(self._virtual_accent.red(),self._virtual_accent.green(),self._virtual_accent.blue(),int(245*a))); p.setPen(QPen(self._virtual_accent.lighter(135),1.6)); p.drawRoundedRect(rect,7,7)
        now=time.monotonic()
        def arrow(dx,dy,active,alpha=1.):
            if not active:return
            cx,cy=95,122; length=42; ex=cx+dx*length; ey=cy+dy*length
            color=QColor(self._virtual_accent.red(),self._virtual_accent.green(),self._virtual_accent.blue(),int(255*a*alpha)); p.setPen(QPen(color,3)); p.drawLine(cx,cy,ex,ey)
            ang=math.atan2(dy,dx); ah=10
            path=QPainterPath(); path.moveTo(ex,ey); path.lineTo(ex-ah*math.cos(ang-.55),ey-ah*math.sin(ang-.55)); path.lineTo(ex-ah*math.cos(ang+.55),ey-ah*math.sin(ang+.55)); path.closeSubpath(); p.setBrush(color); p.drawPath(path)
        for d,vec in [('up',(0,-1)),('down',(0,1)),('left',(-1,0)),('right',(1,0))]:
            arrow(*vec,d in self._move_dirs,max(0.,min(1.,(self._move_until-now)/.75)))
        # Scroll: um pequeno indicador separado ao lado da roda, nunca as setas de movimento.
        if wheel_active:
            symbol={'up':'↑','down':'↓','left':'←','right':'→'}.get(self._scroll_dir,'')
            p.setPen(QColor(self._virtual_accent.red(),self._virtual_accent.green(),self._virtual_accent.blue(),int(240*a))); p.setFont(QFont('Segoe UI',14,QFont.Weight.Bold)); p.drawText(QRectF(142,72,32,38),Qt.AlignCenter,symbol)

class BaseOverlay(QWidget):
    closed=Signal(); geometryChanged=Signal()
    def __init__(self,title,always_on_top=True):
        flags=Qt.FramelessWindowHint|Qt.Tool|(Qt.WindowStaysOnTopHint if always_on_top else Qt.WindowType(0)); super().__init__(None,flags)
        self.setWindowTitle(title); self.setAttribute(Qt.WA_TranslucentBackground,True); self.setMinimumSize(120,60); self._drag=None; self._resize=False
        self._layout=QVBoxLayout(self); self._layout.setContentsMargins(6,6,6,6); self.content_layout=QVBoxLayout(); self._layout.addLayout(self.content_layout)
        self._close=QPushButton('×',self); self._close.setFixedSize(22,22); self._close.setStyleSheet('QPushButton{background:rgba(0,0,0,0);color:rgba(255,255,255,150);border:0;font-size:18px} QPushButton:hover{color:white}'); self._close.clicked.connect(self.close)
    def resizeEvent(self,e): self._close.move(self.width()-26,2); self.geometryChanged.emit(); super().resizeEvent(e)
    def moveEvent(self,e): self.geometryChanged.emit(); super().moveEvent(e)
    def paintEvent(self,e): pass
    def mousePressEvent(self,e):
        if e.button()==Qt.LeftButton:
            if e.position().x()>self.width()-18 and e.position().y()>self.height()-18:self._resize=True
            else:self._drag=e.globalPosition().toPoint()-self.pos()
        super().mousePressEvent(e)
    def mouseMoveEvent(self,e):
        if self._resize:self.resize(max(self.minimumWidth(),int(e.position().x())),max(self.minimumHeight(),int(e.position().y())))
        elif self._drag is not None:self.move(e.globalPosition().toPoint()-self._drag)
        super().mouseMoveEvent(e)
    def mouseReleaseEvent(self,e): self._drag=None; self._resize=False; super().mouseReleaseEvent(e)
    def closeEvent(self,e): self.geometryChanged.emit(); self.closed.emit(); super().closeEvent(e)

class KeyboardOverlay(BaseOverlay):
    keyClicked=Signal(str)
    def __init__(self):
        super().__init__('Teclado virtual'); self.keyboard=KeyboardWidget(); self.keyboard.keyClicked.connect(self.keyClicked.emit); self.content_layout.addWidget(self.keyboard); self.resize(520,210)
    def set_display(self,mode,timeout,opacity,clickable): self.keyboard.set_display(mode,timeout,opacity,clickable)

class MouseOverlay(BaseOverlay):
    def __init__(self):
        super().__init__('Mouse virtual'); self.mouse=MouseWidget(); self.content_layout.addWidget(self.mouse); self.resize(150,210)
    def set_display(self,timeout,opacity): self.mouse.set_display(timeout,opacity)

class MousePositionPicker(QDialog):
    """Seletor de posição: tela inteira cinza e clique esquerdo define a posição."""
    positionSelected = Signal(QPoint)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Escolher posição do mouse')
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setModal(True)
        self.setStyleSheet('background:#666666;')
        lay=QVBoxLayout(self); lay.setContentsMargins(30,25,30,25)
        label=QLabel('Posicione o mouse na posição desejada, e em seguida clique com o botão esquerdo do mouse 🖱, para definir com precisão a sua localização.')
        label.setAlignment(Qt.AlignHCenter|Qt.AlignTop); label.setWordWrap(True)
        label.setStyleSheet('color:white;font-size:20px;font-weight:600;background:transparent;')
        lay.addWidget(label); lay.addStretch()
        cancel=QPushButton('ESC — Cancelar'); cancel.setFixedWidth(180); cancel.clicked.connect(self.reject); lay.addWidget(cancel,0,Qt.AlignHCenter)
        screen=QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen:
            self.setGeometry(screen.geometry())
    def mousePressEvent(self,e):
        if e.button()==Qt.LeftButton:
            self._selected_position=e.globalPosition().toPoint()
            self.positionSelected.emit(self._selected_position)
            self.accept()
        else:
            super().mousePressEvent(e)
    def keyPressEvent(self,e):
        if e.key()==Qt.Key_Escape:self.reject()
        else:super().keyPressEvent(e)


# Modular export contract: this project intentionally shares private helpers
# between UI modules via import *. Export them explicitly so runtime names
# such as _PYNPUT_AVAILABLE and _default_backend are not lost.
__all__ = [name for name in globals() if not name.startswith("__")]
