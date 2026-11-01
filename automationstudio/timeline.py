from __future__ import annotations



from .core import *
from .overlays import *
from .command_editor import *


class TimelineCanvas(QWidget):
    """Área de desenho da timeline. Ver docstring do módulo."""

    map_changed = Signal()               # start/duration mudou (arrasto ou edição)
    selection_changed = Signal(object)   # Command | None

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._map: AutomationMap | None = None
        self._pps = _DEFAULT_PPS
        self._playhead: float | None = None
        self._selected_id: str | None = None
        self._selected_ids: set[str] = set()
        self._selection_anchor_row: int | None = None
        self._simple_mode = True
        self._snap_enabled = True
        self._snap_step = 0.05
        self._group_colors: dict[str, QColor] = {}
        self._dark_theme = True
        self._theme_accent = QColor('#ffc53d')
        self._apply_theme_colors()

        self._drag_mode: str | None = None   # None | "move" | "resize" | "reorder"
        self._drag_command: Command | None = None
        self._drag_start_x = 0.0
        self._drag_start_y = 0.0
        self._reorder_target_row: int | None = None
        self._reorder_selected_commands: list[Command] = []
        self._drag_orig_start = 0.0
        self._drag_orig_duration = 0.0

        # Seleção por área, no padrão visual do Windows. O retângulo é
        # desenhado diretamente sobre a timeline e a seleção é atualizada
        # em tempo real enquanto o botão esquerdo permanece pressionado.
        self._selection_dragging = False
        self._selection_press_pos = QPoint()
        self._selection_current_pos = QPoint()
        self._selection_band = SelectionRubberBand(self)
        self._selection_band.set_theme(False, '#2F6FED')

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_InputMethodEnabled, True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self.setMinimumSize(int(_LABEL_W + _MIN_SECONDS_VISIBLE * self._pps), int(_RULER_H + _ROW_H))

    # ---- API pública -------------------------------------------------

    def set_map(self, automation_map: AutomationMap | None) -> None:
        self._map = automation_map
        self._selected_id = None
        self._selected_ids = set()
        self._selection_anchor_row = None
        self._assign_group_colors()
        self._recompute_size()
        self.update()

    def refresh(self) -> None:
        self._assign_group_colors()
        self._recompute_size()
        self.update()

    def set_zoom(self, pixels_per_second: float) -> None:
        self._pps = max(_MIN_PPS, min(_MAX_PPS, pixels_per_second))
        self._recompute_size()
        self.update()

    def zoom_in(self) -> None:
        self.set_zoom(self._pps * 1.25)

    def zoom_out(self) -> None:
        self.set_zoom(self._pps / 1.25)

    def set_theme(self, dark: bool, accent: str = '#ffc53d') -> None:
        self._dark_theme = bool(dark)
        self._theme_accent = _normalized_color(accent)
        self._selection_band.set_theme(bool(dark), accent)
        self._apply_theme_colors()
        self.update()

    def _apply_theme_colors(self) -> None:
        if self._dark_theme:
            self._bg = QColor('#14171c'); self._row_alt = QColor('#191d23')
            self._grid = QColor('#242a32'); self._grid_strong = QColor('#343c47')
            self._ruler_bg = QColor('#1a1d23'); self._label = QColor('#c2c9d3')
            self._label_disabled = QColor('#5f6977'); self._ungrouped = QColor('#4a525e')
            self._ungrouped_border = QColor('#7d8796')
        else:
            self._bg = QColor('#ffffff'); self._row_alt = QColor('#f6f7f9')
            self._grid = QColor('#e4e7eb'); self._grid_strong = QColor('#cbd0d7')
            self._ruler_bg = QColor('#f3f4f6'); self._label = QColor('#454a52')
            self._label_disabled = QColor('#8b919a'); self._ungrouped = QColor('#e3e6ea')
            self._ungrouped_border = QColor('#a3a9b2')
        self._active = self._theme_accent
        self._active_border = self._theme_accent.lighter(135)
        self._selected_border = self._theme_accent
        self._playhead_color = self._theme_accent

    def fit_to_viewport(self, viewport_width: int) -> None:
        usable = max(80, int(viewport_width) - int(_LABEL_W) - 50)
        total = max(self._total_seconds(), 0.1)
        self.set_zoom(usable / total)

    def set_playhead(self, seconds: float | None) -> None:
        self._playhead = None if seconds is None else max(0.0, float(seconds))
        self.update()

    def set_snap_enabled(self, enabled: bool) -> None:
        self._snap_enabled = bool(enabled)

    def _snap_time(self, value: float) -> float:
        if not self._snap_enabled or self._snap_step <= 0:
            return value
        return round(value / self._snap_step) * self._snap_step

    def set_simple_mode(self, simple: bool) -> None:
        self._simple_mode = bool(simple)
        self.update()

    # ---- internos: layout/cores ---------------------------------------

    def _assign_group_colors(self) -> None:
        self._group_colors = {}
        if not self._map:
            return
        idx = 0
        for cmd in self._map.commands:
            gid = getattr(cmd, 'group_id', '')
            gobj = self._map.groups.get(gid) if gid else None
            g = gobj.name if gobj else cmd.group.strip()
            if g and g not in self._group_colors:
                self._group_colors[g] = _normalized_color(gobj.color) if gobj else _GROUP_PALETTE[idx % len(_GROUP_PALETTE)]
                idx += 1

    def _total_seconds(self) -> float:
        if not self._map or not self._map.commands:
            return _MIN_SECONDS_VISIBLE
        longest = max((c.effective_end for c in self._map.commands), default=0.0)
        return max(_MIN_SECONDS_VISIBLE, longest + 1.5)

    def _recompute_size(self) -> None:
        rows = len(self._map.commands) if self._map else 0
        width = _LABEL_W + self._total_seconds() * self._pps + 40
        height = _RULER_H + max(rows, 1) * _ROW_H + 10
        self.setMinimumSize(int(width), int(height))
        self.resize(int(width), int(height))

    def _x_for_time(self, t: float) -> float:
        return _LABEL_W + t * self._pps

    def _row_rect(self, row: int) -> QRectF:
        y = _RULER_H + row * _ROW_H
        return QRectF(0, y, max(self.width(), _LABEL_W), _ROW_H)

    def _bar_rect(self, cmd: Command, row: int) -> QRectF:
        x0 = self._x_for_time(cmd.effective_start)
        x1 = self._x_for_time(cmd.effective_end)
        w = max(6.0, x1 - x0)
        y = _RULER_H + row * _ROW_H + 5
        return QRectF(x0, y, w, _ROW_H - 10)

    def _color_for(self, cmd: Command) -> tuple[QColor, QColor]:
        g = cmd.group.strip()
        if g in self._group_colors:
            base = self._group_colors[g]
            return base, base.lighter(150)
        return self._ungrouped, self._ungrouped_border

    def _text_color_for_cmd(self, cmd: Command) -> QColor:
        fill, _ = self._color_for(cmd)
        return _text_color_for_background(fill)

    def _is_active(self, cmd: Command) -> bool:
        if self._playhead is None or not cmd.enabled:
            return False
        end = max(cmd.effective_end, cmd.effective_start + 0.001)
        return cmd.effective_start <= self._playhead <= end

    # ---- desenho -------------------------------------------------------

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), self._bg)

        if not self._map:
            painter.setPen(self._label)
            painter.drawText(self.rect(), Qt.AlignCenter, "Selecione um mapa para ver a timeline")
            return

        rows = self._map.commands
        for row in range(len(rows)):
            if row % 2 == 1:
                painter.fillRect(self._row_rect(row), self._row_alt)

        self._draw_ruler(painter)

        for row, cmd in enumerate(rows):
            self._draw_row_label(painter, row, cmd)
            self._draw_bar(painter, row, cmd)

        if not rows:
            painter.setPen(self._label_disabled)
            painter.drawText(
                QRectF(_LABEL_W, _RULER_H, self.width() - _LABEL_W, _ROW_H),
                Qt.AlignVCenter, "Nenhum comando ainda -- adicione um na aba Tabela.",
            )

        if self._playhead is not None:
            self._draw_playhead(painter)

        # Indicador de posição durante a reordenação vertical. A linha é
        # apenas visual até o mouse ser solto; a lista real é alterada no release.
        if self._drag_mode == "reorder" and self._reorder_target_row is not None:
            row = max(0, min(self._reorder_target_row, len(rows)))
            y = _RULER_H + row * _ROW_H
            painter.setPen(QPen(self._theme_accent, 3))
            painter.drawLine(int(_LEFT_PAD), int(y), int(self.width() - 8), int(y))

    def _draw_ruler(self, painter: QPainter) -> None:
        total = self._total_seconds()
        painter.fillRect(QRectF(0, 0, self.width(), _RULER_H), self._ruler_bg)
        step = 1.0 if self._pps >= 40 else (2.0 if self._pps >= 20 else 5.0)
        t = 0.0
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        while t <= total + step:
            x = self._x_for_time(t)
            strong = abs((t / step) % 5) < 1e-6
            painter.setPen(QPen(self._grid_strong if strong else self._grid))
            painter.drawLine(int(x), int(_RULER_H), int(x), self.height())
            painter.setPen(self._label)
            painter.drawText(QRectF(x + 2, 0, 60, _RULER_H), Qt.AlignVCenter, f"{t:g}s")
            t += step
        painter.setPen(QPen(self._grid_strong))
        painter.drawLine(0, int(_RULER_H), self.width(), int(_RULER_H))
        painter.drawLine(int(_LABEL_W), 0, int(_LABEL_W), self.height())

    def _draw_row_label(self, painter: QPainter, row: int, cmd: Command) -> None:
        rect = QRectF(_LEFT_PAD, _RULER_H + row * _ROW_H, _LABEL_W - _LEFT_PAD - 4, _ROW_H)
        painter.setPen(self._label if cmd.enabled else self._label_disabled)
        label = str(self._map.commands.index(cmd)+1) if self._simple_mode else (cmd.target or cmd.type.value)
        if (not self._simple_mode) and cmd.group.strip():
            label = f"{label}  [{cmd.group.strip()}]"
        painter.drawText(rect, Qt.AlignVCenter, label)

    def _draw_bar(self, painter: QPainter, row: int, cmd: Command) -> None:
        rect = self._bar_rect(cmd, row)
        active = self._is_active(cmd)
        if active:
            fill, border = self._active, self._active_border
        else:
            fill, border = self._color_for(cmd)
        if not cmd.enabled:
            fill = QColor(fill)
            fill.setAlpha(90)
        painter.setBrush(fill)
        selected = cmd.id in self._selected_ids
        pen_color = self._selected_border if selected else border
        pen_width = 2.2 if selected else 1.2
        painter.setPen(QPen(pen_color, pen_width))
        painter.drawRoundedRect(rect, 5, 5)
        painter.setPen(self._text_color_for_cmd(cmd))
        if cmd.merged_move and cmd.mouse_path:
            label = f"Movimento do mouse • {len(cmd.mouse_path)} pontos"
        else:
            label = cmd.description.strip() or cmd.target or cmd.type.value
        painter.drawText(rect.adjusted(7, 0, -10, 0), Qt.AlignVCenter | Qt.AlignLeft, label)

        # alça de redimensionar (só um indício visual discreto)
        handle = QRectF(rect.right() - _RESIZE_HANDLE_PX, rect.top(), _RESIZE_HANDLE_PX, rect.height())
        painter.fillRect(handle, QColor(255, 255, 255, 40))

        # Atraso sugerido: referência visual, nunca altera a execução.
        if cmd.delay_suggested > 0:
            sx = self._x_for_time(cmd.effective_end)
            ex = self._x_for_time(cmd.effective_end + cmd.delay_suggested)
            if ex > sx + 2:
                guide = QRectF(sx, rect.top()+2, ex-sx, rect.height()-4)
                painter.setBrush(QColor(255, 193, 7, 45))
                painter.setPen(QPen(QColor(255, 193, 7, 120), 1, Qt.DashLine))
                painter.drawRect(guide)
                painter.setPen(self._text_color_for_cmd(cmd))
                if ex-sx > 45:
                    painter.drawText(guide, Qt.AlignCenter, f'+{cmd.delay_suggested:.2f}s')

    def _draw_playhead(self, painter: QPainter) -> None:
        x = self._x_for_time(self._playhead)
        painter.setPen(QPen(self._playhead_color, 2))
        painter.drawLine(int(x), 0, int(x), self.height())

    # ---- interação: seleção e arrastar (item 30/31) --------------------

    def _command_row_at(self, pos) -> tuple[int, Command] | None:
        if not self._map or not self._map.commands:
            return None
        row = int((pos.y() - _RULER_H) // _ROW_H)
        if 0 <= row < len(self._map.commands):
            return row, self._map.commands[row]
        return None

    def _context_menu(self, pos) -> None:
        hit = self._command_row_at(pos)
        if not hit:
            return
        _row, cmd = hit
        host = self._host_main_window()
        menu = QMenu(self)

        if cmd.type == InputType.MOUSE_MOVE and cmd.merged_move and cmd.mouse_path:
            a = menu.addAction("✎ Editar linhas mescladas")
            a.triggered.connect(lambda: self.window()._open_editor_for_merged(cmd) if hasattr(self.window(), "_open_editor_for_merged") else None)
            menu.addSeparator()

        edit = menu.addAction("Editar comando")
        edit.triggered.connect(lambda: self.mouseDoubleClickEvent(QMouseEvent(QEvent.MouseButtonDblClick, pos, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)))

        # A Timeline deve oferecer as mesmas operações de grupo do editor.
        # O conjunto selecionado continua sendo a fonte da operação; clicar
        # com o botão direito sobre qualquer item do conjunto não reduz a seleção.
        if host is not None and self._map is not None:
            # Faça uma cópia imutável do conjunto neste instante. O menu
            # permanece aberto enquanto a ação é escolhida e nenhum evento
            # posterior deve trocar a seleção usada pela operação.
            selected_ids = set(self._selected_ids)
            if cmd.id in selected_ids:
                # O clique direito ocorreu sobre uma das linhas selecionadas:
                # todas as linhas selecionadas participam da operação.
                selected_ids = set(selected_ids)
            else:
                selected_ids = {cmd.id}
            menu.addSeparator()
            groups = menu.addMenu("Adicionar ao grupo")

            create = groups.addAction("＋ Criar novo grupo")
            def create_group():
                self._selected_ids = selected_ids
                self._selected_id = cmd.id if cmd.id in selected_ids else next(iter(selected_ids), None)
                host._sync_command_table_selection_from_timeline()
                host.command_table._create_group_from_selection()
                self.refresh()
            create.triggered.connect(create_group)

            if self._map.groups:
                groups.addSeparator()
                for g in self._map.groups.values():
                    action = groups.addAction(f"● {g.name}")
                    action.triggered.connect(lambda checked=False, gid=g.id: self._assign_group_from_context(gid, selected_ids, host))

        menu.exec(self.mapToGlobal(pos))

    def _assign_group_from_context(self, gid: str, selected_ids: set[str], host) -> None:
        if not self._map or gid not in self._map.groups:
            return
        g = self._map.groups[gid]
        for c in self._map.commands:
            if c.id in selected_ids:
                c.group_id = gid
                c.group = g.name
        self._selected_ids = set(selected_ids)
        self._selected_id = next(iter(self._selected_ids), None)
        self._assign_group_colors()
        host._sync_command_table_selection_from_timeline()
        host._on_timeline_edited()
        self.refresh()

    def _update_area_selection(self, current: QPoint) -> None:
        """Seleciona as linhas tocadas pelo retângulo, em tempo real."""
        if not self._map or not self._map.commands:
            return
        rect = QRect(self._selection_press_pos, current).normalized()
        self._selection_current_pos = current
        self._selection_band.set_rect(rect)
        self._selection_band.show()
        self._selection_band.raise_()

        selected = set()
        for row, _cmd in enumerate(self._map.commands):
            row_rect = QRect(0, int(_RULER_H + row * _ROW_H), self.width(), int(_ROW_H))
            if row_rect.intersects(rect):
                selected.add(self._map.commands[row].id)

        self._selected_ids = selected
        self._selected_id = next(iter(selected), None)
        cmd = self._map.get_command(self._selected_id) if (self._map and self._selected_id) else None
        self.selection_changed.emit(cmd)
        self.update()

    def _finish_area_selection(self) -> None:
        if not self._selection_dragging:
            return
        self._update_area_selection(self._selection_current_pos)
        self._selection_dragging = False
        self._selection_band.hide()
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        # Botão direito: preserve a seleção múltipla para o menu contextual.
        # O item sob o cursor só substitui a seleção quando ele próprio não
        # fazia parte dela, mantendo o comportamento esperado de editores.
        if event.button() == Qt.RightButton:
            hit = self._command_row_at(event.position())
            if hit is not None:
                _row, cmd = hit
                if cmd.id not in self._selected_ids:
                    self._selected_ids = {cmd.id}
                    self._selected_id = cmd.id
                    self.selection_changed.emit(cmd)
                    self.update()
                # Se já estiver selecionado, não tocamos na seleção: ela é
                # exatamente o conjunto que as ações de grupo devem usar.
            return
        if event.button() != Qt.LeftButton:
            return
        hit = self._command_row_at(event.position())
        x = event.position().x()
        mods = event.modifiers()

        # Clique na régua posiciona o playhead sem iniciar seleção de comandos.
        if event.position().y() <= _RULER_H and x >= _LABEL_W:
            self.set_playhead(self._snap_time(max(0.0, (x - _LABEL_W) / self._pps)))
            event.accept()
            return

        # O gesto de seleção começa em uma área vazia. Dentro de uma barra,
        # preservamos o gesto existente de mover/redimensionar/reordenar.
        if hit is None or not self._bar_rect(hit[1], hit[0]).contains(event.position()):
            self._selection_dragging = True
            self._selection_press_pos = event.position().toPoint()
            self._selection_current_pos = self._selection_press_pos
            self._selected_ids = set()
            self._selected_id = None
            self._selection_anchor_row = None
            self._selection_band.set_rect(QRect(self._selection_press_pos, self._selection_press_pos))
            self._selection_band.show()
            self._selection_band.raise_()
            self.selection_changed.emit(None)
            self.update()
            return

        row, cmd = hit
        bar = self._bar_rect(cmd, row)
        already_selected = cmd.id in self._selected_ids
        if mods & Qt.ShiftModifier and self._selection_anchor_row is not None:
            lo, hi = sorted((int(self._selection_anchor_row), row))
            self._selected_ids = {c.id for c in self._map.commands[lo:hi+1]}
            self._selected_id = cmd.id
        elif mods & Qt.ControlModifier:
            if already_selected:
                self._selected_ids.remove(cmd.id)
            else:
                self._selected_ids.add(cmd.id)
            self._selected_id = cmd.id if cmd.id in self._selected_ids else next(iter(self._selected_ids), None)
            self._selection_anchor_row = row
        elif not already_selected:
            # Clicar em um item que já faz parte da seleção deve preservar o
            # bloco inteiro para que o arraste temporal mova todos juntos.
            self._selected_ids = {cmd.id}
            self._selected_id = cmd.id
            self._selection_anchor_row = row
        else:
            self._selected_id = cmd.id
        self.selection_changed.emit(cmd)
        self.update()

        self._drag_command = cmd
        self._drag_commands = [c for c in self._map.commands if c.id in self._selected_ids] if self._map else [cmd]
        self._drag_start_x = x
        self._drag_start_y = event.position().y()
        self._drag_orig_start = cmd.start
        self._drag_orig_duration = cmd.duration
        self._drag_orig_starts = {c.id:c.start for c in self._drag_commands}
        self._drag_orig_durations = {c.id:c.duration for c in self._drag_commands}
        self._reorder_target_row = row
        self._reorder_selected_commands = list(self._drag_commands)
        self._drag_mode = "resize" if x >= bar.right() - _RESIZE_HANDLE_PX else "move"

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._selection_dragging:
            self._update_area_selection(event.position().toPoint())
            return
        if self._drag_mode is None or self._drag_command is None or not self._map:
            return
        dx = event.position().x() - self._drag_start_x
        dy = event.position().y() - self._drag_start_y

        # Arrastar verticalmente um bloco da Timeline altera a ORDEM dos
        # comandos. O gesto só entra neste modo depois de um deslocamento
        # vertical perceptível, evitando transformar pequenos movimentos
        # normais de edição temporal em reordenação acidental.
        if self._drag_mode in ("move", "resize") and abs(dy) >= max(10, _ROW_H * 0.35):
            if self._drag_mode == "resize":
                pass
            else:
                self._drag_mode = "reorder"

        if self._drag_mode == "reorder":
            target = int((event.position().y() - _RULER_H + _ROW_H / 2) // _ROW_H)
            self._reorder_target_row = max(0, min(target, len(self._map.commands)))
            self.update()
            return

        dt = self._snap_time(dx / self._pps)
        cmd = self._drag_command
        if self._drag_mode == "move":
            for c in self._drag_commands:
                c.start = max(0.0, self._drag_orig_starts[c.id] + dt)
        else:
            cmd.duration = max(_MIN_DURATION, self._drag_orig_duration + dt)
        self._recompute_size()
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._selection_dragging and event.button() == Qt.LeftButton:
            self._selection_current_pos = event.position().toPoint()
            self._finish_area_selection()
            return
        if self._drag_mode == "reorder" and self._map:
            moving_ids = {c.id for c in self._reorder_selected_commands}
            result = self._map.move_commands(
                moving_ids,
                self._reorder_target_row if self._reorder_target_row is not None else len(self._map.commands),
            )
            if result is None:
                self._drag_mode = None
                self._drag_command = None
                self._drag_commands = []
                self._reorder_target_row = None
                self._reorder_selected_commands = []
                return
            first, _last = result
            moving = [c for c in self._map.commands if c.id in moving_ids]
            self._assign_group_colors()
            self._recompute_size()
            self._selected_ids = moving_ids
            self._selected_id = moving[0].id if moving else None
            self._reorder_target_row = None
            self._reorder_selected_commands = []
            self._drag_mode = None
            self._drag_command = None
            self._drag_commands = []
            self.map_changed.emit()
            self.update()
            return

        if self._drag_mode is not None:
            self._drag_mode = None
            self._drag_command = None
            self._drag_commands = []
            self._reorder_target_row = None
            self._reorder_selected_commands = []
            self.map_changed.emit()

    def select_all(self) -> None:
        if not self._map:
            return
        self._selected_ids = {c.id for c in self._map.commands}
        self._selected_id = next(iter(self._selected_ids), None)
        self.selection_changed.emit(self._map.get_command(self._selected_id) if self._selected_id else None)
        self.update()

    def _host_main_window(self):
        host = self.window()
        return host if hasattr(host, 'command_table') else None

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        host = self._host_main_window()
        mods = event.modifiers()
        key = event.key()
        if key == Qt.Key_A and mods & Qt.ControlModifier:
            self.select_all(); event.accept(); return
        if key == Qt.Key_C and mods & Qt.ControlModifier:
            if host:
                host._sync_command_table_selection_from_timeline()
                host.command_table._copy_selected()
            event.accept(); return
        if key == Qt.Key_X and mods & Qt.ControlModifier:
            if host:
                host._sync_command_table_selection_from_timeline()
                host.command_table._copy_selected()
                host.command_table._remove_selected()
            event.accept(); return
        if key == Qt.Key_V and mods & Qt.ControlModifier:
            if host:
                host._sync_command_table_selection_from_timeline()
                host.command_table._paste()
            event.accept(); return
        if key == Qt.Key_Delete:
            if host:
                host._sync_command_table_selection_from_timeline()
                host.command_table._remove_selected()
            event.accept(); return
        if key == Qt.Key_Z and mods & Qt.ControlModifier:
            if host:
                host._undo_map()
            event.accept(); return
        if key == Qt.Key_Y and mods & Qt.ControlModifier:
            if host:
                host._redo_map()
            event.accept(); return
        if key in (Qt.Key_Return, Qt.Key_Enter) and self._selected_id and host:
            cmd = self._map.get_command(self._selected_id) if self._map else None
            if cmd is not None:
                idx = self._map.commands.index(cmd)
                host._open_command_sidebar(cmd, idx)
            event.accept(); return
        if key == Qt.Key_Escape:
            self._selected_ids.clear(); self._selected_id = None; self._selection_anchor_row = None
            self.selection_changed.emit(None); self.update(); event.accept(); return
        super().keyPressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        # Item 30: edição rápida por duplo clique, igual à tabela --
        # mesmo diálogo (`CommandDialog`), nenhuma lógica duplicada.
        hit = self._command_row_at(event.position())
        if hit is None or not self._map:
            return
        _row, cmd = hit
        index = next((i for i, c in enumerate(self._map.commands) if c is cmd), None)
        if index is None:
            return
        host = self._host_main_window()
        if host is not None:
            self._selected_ids = {cmd.id}
            self._selected_id = cmd.id
            self.selection_changed.emit(cmd)
            host._sync_command_table_selection_from_timeline()
            self.window().timeline_panel.open_command_sidebar(cmd, index)
        else:
            # Fallback seguro somente quando o canvas for usado sem MainWindow.
            dialog = CommandDialog(command=cmd, parent=self)
            if dialog.exec():
                self._map.commands[index] = dialog.result_command()
                self.refresh()
                self.map_changed.emit()

    def _select(self, command_id: str | None) -> None:
        self._selected_id = command_id
        self._selected_ids = {command_id} if command_id else set()
        cmd = self._map.get_command(command_id) if (self._map and command_id) else None
        self.selection_changed.emit(cmd)
        self.update()

class MouseTrajectoryCanvas(QWidget):
    """Visualização leve da trajetória capturada, sem criar um widget por ponto."""
    def __init__(self, command: Command, parent=None):
        super().__init__(parent)
        self.command = command
        self.setMinimumHeight(240)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setToolTip("Trajetória capturada. Os pontos continuam armazenados no comando.")

    def paintEvent(self, _event):
        painter=QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#17181b"))
        path=self.command.mouse_path or []
        if len(path)<2:
            painter.setPen(QColor("#bfc3ca")); painter.drawText(self.rect(), Qt.AlignCenter, "Nenhuma trajetória detalhada disponível")
            return
        xs=[float(pt.get('x',0)) for pt in path]; ys=[float(pt.get('y',0)) for pt in path]
        minx,maxx=min(xs),max(xs); miny,maxy=min(ys),max(ys)
        spanx=max(1.0,maxx-minx); spany=max(1.0,maxy-miny)
        margin=24; w=max(1,self.width()-2*margin); h=max(1,self.height()-2*margin)
        def tr(x,y): return QPointF(margin+(x-minx)/spanx*w, margin+(y-miny)/spany*h)
        painter.setPen(QPen(QColor("#4f8fda"),2))
        prev=tr(xs[0],ys[0])
        for pt in path[1:]:
            cur=tr(float(pt.get('x',0)),float(pt.get('y',0))); painter.drawLine(prev,cur); prev=cur
        painter.setBrush(QColor("#57b894")); painter.setPen(Qt.NoPen); painter.drawEllipse(tr(xs[0],ys[0]),5,5)
        painter.setBrush(QColor("#ffc53d")); painter.drawEllipse(tr(xs[-1],ys[-1]),5,5)
        painter.setPen(QColor("#c7c7cc")); painter.drawText(8,18,f"{len(path)} pontos • duração {self.command.duration:.3f}s")

class MergedMouseEditor(QWidget):
    """Editor interno de um bloco de movimento do mouse mesclado.

    O usuário edita os pontos individuais, enquanto o comando continua sendo
    uma única linha no mapa. Os tempos são relativos ao início do bloco e a
    última linha determina a duração; o percurso é normalizado para que o
    redimensionamento na timeline continue funcionando.
    """
    map_changed = Signal()
    def __init__(self, command: Command, parent=None):
        super().__init__(parent)
        self.command = command
        self.table = QTableWidget(0,4)
        self.table.setHorizontalHeaderLabels(["#", "Tempo relativo", "X", "Y"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.duration = QDoubleSpinBox(); self.duration.setRange(0.001,3600); self.duration.setDecimals(3); self.duration.setSingleStep(.05); self.duration.setSuffix(" s"); self.duration.setValue(max(.001, command.duration))
        self.info = QLabel("Edite os pontos individuais. O tempo relativo é convertido para uma fração do bloco; ao alterar a duração, o percurso é preservado e apenas fica mais rápido ou mais lento.")
        self.info.setWordWrap(True)
        lay=QVBoxLayout(self); lay.addWidget(QLabel("<b>Editar linhas mescladas do movimento do mouse</b>")); lay.addWidget(self.info)
        row=QHBoxLayout(); row.addWidget(QLabel("Duração total do movimento:")); row.addWidget(self.duration); row.addWidget(QLabel("Velocidade:")); self.speed=QDoubleSpinBox(); self.speed.setRange(0.10,10.0); self.speed.setDecimals(2); self.speed.setSingleStep(.10); self.speed.setValue(1.0); self.speed.setSuffix("×"); self.speed.setToolTip("1,00× mantém a duração atual. 2,00× deixa o movimento duas vezes mais rápido."); row.addWidget(self.speed); row.addStretch(); lay.addLayout(row)
        self.trajectory=MouseTrajectoryCanvas(command,self); lay.addWidget(self.trajectory)
        lay.addWidget(QLabel("Pontos individuais (edição de precisão):")); lay.addWidget(self.table)
        buttons=QHBoxLayout(); self.apply_btn=QPushButton("✓ Aplicar alterações"); back=QPushButton("← Voltar"); self.apply_btn.clicked.connect(self._apply); back.clicked.connect(lambda:self._go_back()); buttons.addStretch(); buttons.addWidget(back); buttons.addWidget(self.apply_btn); lay.addLayout(buttons)
        self._populate()
    def _populate(self):
        self.table.setRowCount(0)
        path=self.command.mouse_path or [{"t":0.0,"x":self.command.x or 0,"y":self.command.y or 0},{"t":1.0,"x":self.command.x or 0,"y":self.command.y or 0}]
        for i,p in enumerate(path):
            self.table.insertRow(i)
            vals=[str(i+1), f'{float(p.get("t",0))*self.command.duration:.3f}', str(int(p.get("x",0))), str(int(p.get("y",0)))]
            for col,val in enumerate(vals):
                it=QTableWidgetItem(val); self.table.setItem(i,col,it)
                if col==0: it.setFlags(it.flags() & ~Qt.ItemIsEditable)
    def _apply(self):
        try:
            dur=max(.001,float(self.duration.value()))
            raw=[]
            for r in range(self.table.rowCount()):
                t=float(self.table.item(r,1).text().replace(',','.'))
                x=int(float(self.table.item(r,2).text().replace(',','.'))); y=int(float(self.table.item(r,3).text().replace(',','.')))
                raw.append((max(0.0,t),x,y))
            if not raw: return
            raw.sort(key=lambda q:q[0]); max_t=max(raw[-1][0],0.001)
            speed=max(0.10,float(self.speed.value()))
            # A velocidade é uma transformação temporal: 2x reduz a duração à metade;
            # 0,5x dobra a duração. A trajetória geométrica permanece idêntica.
            dur = max(.001, dur / speed)
            self.command.duration=dur
            self.command.mouse_path=[{"t":max(0.0,min(1.0,t/max_t)),"x":x,"y":y} for t,x,y in raw]
            self.command.x=self.command.mouse_path[0]["x"]; self.command.y=self.command.mouse_path[0]["y"]; self.command.merged_move=True
            self.trajectory.update()
            self.map_changed.emit()
        except (ValueError,TypeError):
            QMessageBox.warning(self,"Valor inválido","Confira os tempos e posições dos pontos.")
    def _go_back(self):
        self.parent()._open_editor_for_merged(None) if self.parent() and hasattr(self.parent(), '_open_editor_for_merged') else None

class TimelinePanel(QWidget):
    """
    Painel completo da Fase 3: barra de dica + zoom, e o `TimelineCanvas`
    dentro de um `QScrollArea` (a timeline pode ficar bem mais larga que
    a janela, dependendo da duração do mapa e do zoom).

    É isto que a `MainWindow` instancia -- uma segunda aba/visão do mesmo
    `AutomationMap` já editado por `ui/command_table.py` (nenhum dado
    duplicado: mesma lista `automation_map.commands`, dois jeitos de
    olhar/editar).
    """

    map_changed = Signal()
    selection_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.canvas = TimelineCanvas()
        self.canvas.map_changed.connect(self.map_changed.emit)
        self.canvas.selection_changed.connect(self.selection_changed.emit)

        self._scroll = QScrollArea()
        self._scroll.setWidget(self.canvas)
        self._scroll.setWidgetResizable(True)

        self.hint_label = QLabel(
            "Arraste para mover; use a borda direita para alterar a duração. "
            "Movimentos mesclados preservam todos os pontos. Botão direito → editar linhas mescladas."
        )
        self.hint_label.setStyleSheet("color: #9a9a9e;")

        self.btn_add = QPushButton("＋ Adicionar comando")
        self.btn_edit = QPushButton("Editar comando")
        self.btn_remove = QPushButton("Excluir selecionados")
        self.btn_add.clicked.connect(self._request_add)
        self.btn_edit.clicked.connect(self._request_edit)
        self.btn_remove.clicked.connect(self._request_remove)

        self.btn_simple = QPushButton("Simples")
        self.btn_advanced = QPushButton("Avançada")
        self.btn_simple.setCheckable(True); self.btn_advanced.setCheckable(True); self.btn_simple.setChecked(True)
        self.btn_simple.clicked.connect(lambda: (self.btn_simple.setChecked(True), self.btn_advanced.setChecked(False), self.canvas.set_simple_mode(True)))
        self.btn_advanced.clicked.connect(lambda: (self.btn_advanced.setChecked(True), self.btn_simple.setChecked(False), self.canvas.set_simple_mode(False)))

        btn_zoom_out = QPushButton("−")
        btn_zoom_in = QPushButton("+")
        btn_fit = QPushButton("Ajustar")
        self.lbl_total = QLabel("Total: 0.00 s")
        self.btn_snap = QPushButton("Snap")
        self.btn_snap.setCheckable(True); self.btn_snap.setChecked(True)
        self.btn_snap.setToolTip("Quando ativo, mover e redimensionar usa passos de 0,05 s.")
        self.btn_snap.toggled.connect(self.canvas.set_snap_enabled)
        for b in (btn_zoom_out, btn_zoom_in):
            b.setFixedWidth(28)
        btn_zoom_out.clicked.connect(self.canvas.zoom_out)
        btn_zoom_in.clicked.connect(self.canvas.zoom_in)
        btn_fit.setToolTip("Ajusta o zoom para preencher a área disponível, como em editores de vídeo.")
        btn_fit.clicked.connect(lambda: self.fit_to_viewport())

        toolbar = QHBoxLayout()
        toolbar.addWidget(self.hint_label, stretch=1)
        toolbar.addWidget(self.btn_add)
        toolbar.addWidget(self.btn_edit)
        toolbar.addWidget(self.btn_remove)
        toolbar.addWidget(QLabel("Visualização:"))
        toolbar.addWidget(self.btn_simple)
        toolbar.addWidget(self.btn_advanced)
        toolbar.addSpacing(10)
        toolbar.addWidget(QLabel("Zoom:"))
        toolbar.addWidget(btn_zoom_out)
        toolbar.addWidget(btn_zoom_in)
        toolbar.addWidget(btn_fit)
        toolbar.addWidget(self.btn_snap)
        toolbar.addWidget(self.lbl_total)

        # Sidebar interno da Timeline: editar/adicionar nunca abre QDialog modal.
        self.sidebar = QFrame(self)
        self.sidebar.setObjectName("TimelineCommandSidebar")
        self.sidebar.setFrameShape(QFrame.StyledPanel)
        self.sidebar.setFixedWidth(340)
        self.sidebar.hide()
        sb=QVBoxLayout(self.sidebar); sb.setContentsMargins(8,6,8,6); sb.setSpacing(5)
        head=QHBoxLayout(); self.sidebar_title=QLabel("Editar comando"); self.sidebar_title.setStyleSheet("font-size:15px;font-weight:700;padding:2px 3px;")
        close=QPushButton("×"); close.setFixedSize(24,24); close.setStyleSheet("QPushButton { border:0; background:transparent; font-size:22px; }")
        close.clicked.connect(self.close_sidebar); head.addWidget(self.sidebar_title); head.addStretch(); head.addWidget(close); sb.addLayout(head)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.sidebar_host=QWidget(); self.sidebar_host.setMinimumWidth(160); self.sidebar_host_layout=QVBoxLayout(self.sidebar_host); self.sidebar_host_layout.setContentsMargins(0,0,0,0); self.sidebar_host_layout.setSpacing(6)
        scroll.setWidget(self.sidebar_host); sb.addWidget(scroll,1)
        self.sidebar_footer=QWidget(); self.sidebar_footer_layout=QHBoxLayout(self.sidebar_footer); self.sidebar_footer_layout.setContentsMargins(0,5,0,0); self.sidebar_footer_layout.addStretch()
        sb.addWidget(self.sidebar_footer); self.sidebar_footer.hide()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        main_col=QVBoxLayout(); main_col.setContentsMargins(0,0,0,0); main_col.addLayout(toolbar); main_col.addWidget(self._scroll)
        layout.addLayout(main_col, 1)
        layout.addWidget(self.sidebar)

    def _clear_sidebar_host(self):
        while self.sidebar_host_layout.count():
            item=self.sidebar_host_layout.takeAt(0); w=item.widget()
            if w: w.deleteLater()
        while self.sidebar_footer_layout.count():
            item=self.sidebar_footer_layout.takeAt(0); w=item.widget()
            if w: w.deleteLater()
        self.sidebar_footer_layout.addStretch()
        self.sidebar_footer.hide()

    def close_sidebar(self):
        self._clear_sidebar_host(); self.sidebar.hide()

    def open_command_sidebar(self, command: Command | None, index: int) -> None:
        host=self._host_main_window()
        if host is None or not self.canvas._map:
            return
        self._clear_sidebar_host()
        editor=CommandDialog(command=command, parent=self.sidebar_host)
        editor.setWindowFlags(Qt.Widget); editor.setModal(False); editor._command_index=index
        if command is None and 0 <= index <= len(self.canvas._map.commands):
            editor.start.setValue(self.canvas._map.commands[index-1].effective_end if index > 0 else 0.0)
        self.sidebar_title.setText("Editar comando" if command is not None else "Adicionar comando")
        try:
            editor.layout().removeWidget(editor.buttons); editor.buttons.hide()
        except Exception:
            pass
        self.sidebar_host_layout.addWidget(editor)
        cancel=QPushButton("Cancelar"); action=QPushButton("Salvar" if command is not None else "Adicionar")
        cancel.clicked.connect(self.close_sidebar)
        def save():
            new_cmd=editor.result_command(); idx=getattr(editor,'_command_index',index)
            if command is None:
                insert_at=max(0,min(int(idx) if idx is not None and int(idx)>=0 else len(self.canvas._map.commands), len(self.canvas._map.commands)))
                if insert_at > 0: new_cmd.start=self.canvas._map.commands[insert_at-1].effective_end
                self.canvas._map.insert_command(new_cmd, insert_at)
            elif 0 <= int(idx) < len(self.canvas._map.commands):
                self.canvas._map.commands[int(idx)]=new_cmd
            host._on_timeline_edited(); self.close_sidebar(); self.refresh()
        action.clicked.connect(save)
        self.sidebar_footer_layout.addWidget(cancel); self.sidebar_footer_layout.addWidget(action); self.sidebar_footer.show(); self.sidebar.show(); self.sidebar.raise_(); editor.setFocus()

    def _host_main_window(self):
        host = self.window()
        return host if hasattr(host, 'command_table') else None

    def _selected_index(self) -> int | None:
        if not self.canvas._map or not self.canvas._selected_ids:
            return None
        rows = [i for i,c in enumerate(self.canvas._map.commands) if c.id in self.canvas._selected_ids]
        return max(rows) if rows else None

    def _request_add(self) -> None:
        host = self._host_main_window()
        if host is not None:
            host._sync_command_table_selection_from_timeline()
            idx = self._selected_index()
            self.open_command_sidebar(None, idx + 1 if idx is not None else -1)

    def _request_edit(self) -> None:
        host = self._host_main_window()
        if host is not None and self.canvas._selected_id and self.canvas._map:
            cmd = self.canvas._map.get_command(self.canvas._selected_id)
            if cmd is not None:
                host._sync_command_table_selection_from_timeline()
                self.open_command_sidebar(cmd, self.canvas._map.commands.index(cmd))

    def _request_remove(self) -> None:
        host = self._host_main_window()
        if host is not None:
            host._sync_command_table_selection_from_timeline()
            host.command_table._remove_selected()

    # ---- API delegada para o canvas -----------------------------------

    def fit_to_viewport(self) -> None:
        self.canvas.fit_to_viewport(self._scroll.viewport().width())

    def set_theme(self, dark: bool, accent: str) -> None:
        self.canvas.set_theme(dark, accent)

    def set_map(self, automation_map: AutomationMap | None) -> None:
        self.canvas.set_map(automation_map)
        self._update_total_label()

    def open_merged_editor(self, command: Command) -> None:
        # A MainWindow troca para a página interna; o método existe também
        # aqui para manter a Timeline independente de popups.
        host=self.window()
        if hasattr(host, "_open_editor_for_merged"):
            host._open_editor_for_merged(command)

    def refresh(self) -> None:
        self.canvas.refresh()
        self._update_total_label()

    def _update_total_label(self) -> None:
        """Mantém o rótulo "Total" da barra da Timeline igual à duração efetiva do mapa."""
        label = getattr(self, 'lbl_total', None)
        if label is None:
            return
        automation_map = getattr(self.canvas, '_map', None)
        total = automation_map.total_duration() if automation_map else 0.0
        label.setText(f"Total: {total:.2f} s")

    def set_playhead(self, seconds: float | None) -> None:
        self.canvas.set_playhead(seconds)

class InputVisualizerPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.keyboard = KeyboardWidget()
        self.mouse = MouseWidget()

        mouse_col = QVBoxLayout()
        mouse_col.addWidget(QLabel("MOUSE"), alignment=Qt.AlignHCenter)
        mouse_col.addWidget(self.mouse, stretch=1)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self.keyboard, stretch=4)
        layout.addLayout(mouse_col, stretch=1)

    # ---- Ligação com eventos do motor / captura real -------------------

    def apply_event(self, event: Event) -> None:
        """Alimenta o visualizador com um Event real do ExecutionEngine
        (via ui/engine_bridge.py -> bridge.event_fired)."""
        if event.kind == EventKind.KEY_DOWN:
            self.keyboard.press(event.target)
        elif event.kind == EventKind.KEY_UP:
            self.keyboard.release(event.target)
        elif event.kind == EventKind.MOUSE_DOWN:
            self.mouse.press(event.target)
        elif event.kind == EventKind.MOUSE_UP:
            self.mouse.release(event.target)
        elif event.kind == EventKind.MOUSE_SCROLL:
            self.mouse.scroll(event.scroll_dx, event.scroll_dy)

    def apply_raw_key(self, target: str, pressed: bool) -> None:
        """Alimenta o visualizador a partir de captura real de input
        (ui/input/input_capture.py) -- teclas do usuário, não do motor."""
        if pressed:
            self.keyboard.press(target)
        else:
            self.keyboard.release(target)

    def apply_raw_mouse(self, button: str, pressed: bool) -> None:
        if pressed:
            self.mouse.press(button)
        else:
            self.mouse.release(button)

    def clear_all(self) -> None:
        """Item 11/25: ao parar/emergência, nunca deixar tecla "presa"
        visualmente, mesmo que o evento de liberação tenha se perdido."""
        self.keyboard.clear()
        self.mouse.clear()


# Modular export contract: this project intentionally shares private helpers
# between UI modules via import *. Export them explicitly so runtime names
# such as _PYNPUT_AVAILABLE and _default_backend are not lost.
__all__ = [name for name in globals() if not name.startswith("__")]
