from __future__ import annotations



from .core import *


class _TutorialLink(QLabel):
    """Link visual clicável; não é um botão Qt e não altera a geometria ao passar o mouse."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText("Pular tutorial")
        self.setCursor(Qt.PointingHandCursor)
        self.setTextInteractionFlags(Qt.NoTextInteraction)
        self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.setStyleSheet(
            "QLabel{color:#2F6FED;font-size:9pt;font-weight:400;background:transparent;"
            "padding:0px;margin:0px;}"
            "QLabel:hover{color:#165DCE;font-weight:700;}"
        )
        self.setFixedHeight(22)
        self.setMinimumWidth(90)
        self.setFocusPolicy(Qt.NoFocus)
        self._clicked = None

    def set_clicked_handler(self, handler):
        self._clicked = handler

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._clicked:
            self._clicked()
            event.accept()
            return
        super().mousePressEvent(event)

class ContextTutorialOverlay(QWidget):
    """Tutorial contextual interno, responsivo e sem janela popup do Windows."""
    _OUTER_MARGIN = 18
    _BUBBLE_GAP = 26
    _SKIP_GAP = 4
    _SKIP_HEIGHT = 22

    def __init__(self, host, steps, on_finish=None):
        super().__init__(host)
        self.host = host
        self.steps = steps or []
        self.index = 0
        self.on_finish = on_finish
        self.skip = _TutorialLink(self)
        self.skip.hide()
        self.skip.set_clicked_handler(self._skip)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self._bubble_rect = QRectF()
        self._refresh()

    def _refresh(self):
        # O overlay ocupa exatamente a área lógica da janela principal.
        # O alvo é convertido por coordenadas globais, evitando erros quando
        # o widget está em toolbar, stacked widget ou outro nível da hierarquia.
        self.setGeometry(self.host.rect())
        self._reposition()
        self.update()
        self.setFocus()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition()
        self.update()

    def _target_widget(self, target):
        if target is None:
            return None
        if isinstance(target, QAction):
            parent = target.parent()
            if isinstance(parent, QToolBar):
                return parent.widgetForAction(target)
            for bar in self.host.findChildren(QToolBar):
                w = bar.widgetForAction(target)
                if w is not None:
                    return w
            return None
        return target if isinstance(target, QWidget) else None

    def _target_rect(self):
        if not self.steps or self.index >= len(self.steps):
            return QRectF()
        target = self._target_widget(self.steps[self.index].get('target'))
        if target is None or not target.isVisible():
            return QRectF()

        # mapToGlobal/mapFromGlobal é mais robusto que mapTo(self) quando o
        # alvo está em QToolBar/QStackedWidget ou em uma subárvore diferente.
        tl = target.mapToGlobal(QPoint(0, 0))
        br = target.mapToGlobal(QPoint(target.width(), target.height()))
        rect = QRectF(
            self.mapFromGlobal(tl).x(),
            self.mapFromGlobal(tl).y(),
            br.x() - tl.x(),
            br.y() - tl.y(),
        )
        # Se parte do alvo estiver fora da janela, aponta para a parte realmente
        # visível, nunca para uma coordenada fora do overlay.
        visible = rect.intersected(QRectF(self.rect()))
        if visible.width() <= 0 or visible.height() <= 0:
            return QRectF()
        return visible

    def _bubble_size(self):
        margin = self._OUTER_MARGIN
        bw = min(430, max(300, self.width() - 2 * margin))
        text = self.steps[self.index].get('text', '') if self.steps else ''
        hint = 'Clique em qualquer lugar ou pressione qualquer tecla para continuar'
        fm = QFontMetrics(QFont('Segoe UI', 11))
        th = fm.boundingRect(QRect(0, 0, max(1, int(bw - 32)), 1000), Qt.TextWordWrap, text).height()
        navfm = QFontMetrics(QFont('Segoe UI', 9, QFont.Weight.DemiBold))
        nh = navfm.boundingRect(QRect(0, 0, max(1, int(bw - 32)), 1000), Qt.TextWordWrap, hint).height()
        bh = max(142, min(300, th + nh + 58))
        return bw, min(bh, max(100, self.height() - 2 * margin))

    def _clamp_rect(self, rect):
        margin = self._OUTER_MARGIN
        max_x = max(margin, self.width() - rect.width() - margin)
        max_y = max(margin, self.height() - rect.height() - margin)
        return QRectF(
            max(margin, min(rect.x(), max_x)),
            max(margin, min(rect.y(), max_y)),
            rect.width(), rect.height(),
        )

    def _bubble_geometry(self, target_rect):
        bw, bh = self._bubble_size()
        margin = self._OUTER_MARGIN
        if target_rect.isNull():
            # Reserva espaço para o link acima do balão.
            y = margin + self._SKIP_HEIGHT + self._SKIP_GAP
            return self._clamp_rect(QRectF(margin, y, bw, bh))

        cx = target_rect.center().x()
        cy = target_rect.center().y()
        candidates = [
            QRectF(cx - bw / 2, target_rect.bottom() + self._BUBBLE_GAP, bw, bh),
            QRectF(cx - bw / 2, target_rect.top() - self._BUBBLE_GAP - bh, bw, bh),
            QRectF(target_rect.right() + self._BUBBLE_GAP, cy - bh / 2, bw, bh),
            QRectF(target_rect.left() - self._BUBBLE_GAP - bw, cy - bh / 2, bw, bh),
        ]

        # Primeiro escolhemos uma posição que não sobreponha o alvo e caiba na
        # janela. Só depois aplicamos clamp. Isso evita setas que atravessem o balão.
        bounds = QRectF(margin, margin, self.width() - 2 * margin, self.height() - 2 * margin)
        valid = [r for r in candidates if bounds.contains(r)]
        if valid:
            bubble = valid[0]
        else:
            # A janela pode ser pequena. Nesse caso, clamp controlado.
            bubble = min(candidates, key=lambda r: max(0, -r.x()) + max(0, -r.y()) +
                         max(0, r.right() - self.width()) + max(0, r.bottom() - self.height()))
            bubble = self._clamp_rect(bubble)

        # Precisamos de uma faixa acima do balão para o link. Se não houver
        # espaço, deslocamos o balão para baixo dentro da janela.
        min_y_for_skip = margin + self._SKIP_HEIGHT + self._SKIP_GAP
        if bubble.y() < min_y_for_skip:
            bubble.moveTop(min_y_for_skip)
            bubble = self._clamp_rect(bubble)
        return bubble

    def _reposition(self):
        r = self._target_rect()
        b = self._bubble_geometry(r)
        self._bubble_rect = b
        self.skip.adjustSize()
        # O link permanece inteiro dentro do overlay, acima do balão.
        x = max(self._OUTER_MARGIN, min(
            int(b.right() - self.skip.width()),
            self.width() - self._OUTER_MARGIN - self.skip.width()
        ))
        y = max(2, int(b.top() - self._SKIP_HEIGHT - self._SKIP_GAP))
        self.skip.setGeometry(x, y, self.skip.width(), self._SKIP_HEIGHT)
        self.skip.show()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(0, 0, 0, 42))
        r = self._target_rect()
        b = self._bubble_rect if not self._bubble_rect.isNull() else self._bubble_geometry(r)
        if not r.isNull():
            p.setPen(QPen(QColor('#E53935'), 3))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(r.adjusted(-5, -5, 5, 5), 6, 6)
            bc = QPoint(int(b.center().x()), int(b.center().y()))
            tc = QPoint(int(r.center().x()), int(r.center().y()))
            # Linha ortogonal curta, terminando no centro da área visível do alvo.
            elbow = QPoint(tc.x(), bc.y())
            p.setPen(QPen(QColor('#E53935'), 2))
            p.drawLine(bc, elbow)
            p.drawLine(elbow, tc)
            p.setBrush(QColor('#E53935'))
            p.drawEllipse(tc, 4, 4)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor('#FFFFFF'))
        p.drawRoundedRect(b, 12, 12)
        text = self.steps[self.index].get('text', '') if self.steps else ''
        p.setPen(QColor('#20242A'))
        p.setFont(QFont('Segoe UI', 11))
        p.drawText(b.adjusted(16, 14, -16, -48), Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop, text)
        p.setPen(QColor('#2F6FED'))
        p.setFont(QFont('Segoe UI', 9, QFont.Weight.DemiBold))
        p.drawText(
            b.adjusted(16, b.height() - 40, -16, -10),
            Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignVCenter,
            'Clique em qualquer lugar ou pressione qualquer tecla para continuar'
        )

    def mousePressEvent(self, event):
        if self.skip.geometry().contains(event.position().toPoint()):
            return
        self._next()
        event.accept()

    def keyPressEvent(self, event):
        self._next()
        event.accept()

    def _skip(self):
        self._finish(True)

    def _next(self):
        if self.index >= len(self.steps) - 1:
            self._finish(False)
        else:
            self.index += 1
            self._refresh()

    def _finish(self, skipped=False):
        self.close()
        if self.on_finish:
            # O coordenador global precisa saber se foi avanço normal ou
            # "Pular tutorial" para poder encerrar toda a jornada, e não
            # somente a página/etapa atual.
            self.on_finish(bool(skipped))

    def closeEvent(self, event):
        self.skip.hide()
        super().closeEvent(event)


# Modular export contract: this project intentionally shares private helpers
# between UI modules via import *. Export them explicitly so runtime names
# such as _PYNPUT_AVAILABLE and _default_backend are not lost.
__all__ = [name for name in globals() if not name.startswith("__")]
