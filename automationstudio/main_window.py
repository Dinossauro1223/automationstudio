from __future__ import annotations

from PySide6.QtCore import QTimer, QSize



from . import core
from .core import *
from .input_system import *
from .project import *
from .ativacao_ui import ControladorAtivacao
from .controle_ui import ControladorDeExecucao
from .tutorial import *
from .overlays import *
from .command_editor import *
from .timeline import *


class EngineBridge(QObject):
    event_fired = Signal(object)          # Event
    progress_changed = Signal(float, float)  # (tempo_atual, tempo_total)
    error_occurred = Signal(object)       # Exception
    finished = Signal()
    chain_requested = Signal(str)  # nome do próximo mapa
    state_changed = Signal(object, object)  # (State anterior, State novo)

    def attach(self, engine) -> None:
        """Registra esta ponte nos callbacks do engine informado."""
        engine.on_event.append(lambda ev: self.event_fired.emit(ev))
        engine.on_progress.append(lambda cur, total: self.progress_changed.emit(cur, total))
        engine.on_error.append(lambda exc: self.error_occurred.emit(exc))
        engine.on_finished.append(lambda: self.finished.emit())
        engine.on_chain_requested.append(lambda name: self.chain_requested.emit(name))
        engine.state.on_change(lambda prev, new: self.state_changed.emit(prev, new))

class HotkeyBridge(QObject):
    triggered = Signal(str)  # identificador da ação, ex.: "map:Volume +"

    def make_callback(self, action_id: str) -> Callable[[], None]:
        """Devolve um callback pronto para `GlobalHotkeyManager.register`
        que só enfileira `action_id` via Signal -- seguro para ser
        chamado a partir de qualquer thread."""
        return lambda: self.triggered.emit(action_id)

class InputCaptureBridge(QObject):
    key_changed = Signal(str, bool)            # (nome da tecla, pressionada?)
    mouse_button_changed = Signal(str, bool)    # (botão, pressionado?)
    mouse_scrolled = Signal(int, int)           # (dx, dy)
    mouse_moved = Signal(int, int)              # (x, y) absoluto

    def attach(self, monitor) -> None:
        monitor.on_key.append(lambda name, pressed: self.key_changed.emit(name, pressed))
        monitor.on_mouse_button.append(lambda name, pressed: self.mouse_button_changed.emit(display_mouse_button_name(name), pressed))
        monitor.on_mouse_scroll.append(lambda dx, dy: self.mouse_scrolled.emit(dx, dy))
        monitor.on_mouse_move.append(lambda x, y: self.mouse_moved.emit(x, y))

class InAppErrorNotice(QFrame):
    """Aviso de erro não-modal, contido dentro da janela principal."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("InAppErrorNotice")
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            QFrame#InAppErrorNotice { background: palette(base); border:1px solid #b94a48; border-radius:8px; }
            QLabel { color: palette(text); }
            QTextEdit { background: palette(base); color: palette(text); border:1px solid #b94a48; border-radius:5px; font-family:Consolas; font-size:10px; }
            QPushButton { background: palette(button); color: palette(button-text); border:1px solid #b94a48; border-radius:5px; padding:5px 10px; }
        """)
        self.setMinimumWidth(320)
        self.setMaximumWidth(560)
        self.setMaximumHeight(420)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.hide()
        lay=QVBoxLayout(self); lay.setContentsMargins(12,10,12,10); lay.setSpacing(7)
        head=QHBoxLayout()
        self.title=QLabel("Erro")
        self.title.setStyleSheet("font-size:15px;font-weight:700;")
        head.addWidget(self.title,1)
        close=QPushButton("×"); close.setFixedSize(28,28); close.clicked.connect(self.hide); head.addWidget(close)
        lay.addLayout(head)
        self.message=QLabel(); self.message.setWordWrap(True); lay.addWidget(self.message)
        self.details=QTextEdit(); self.details.setReadOnly(True); self.details.setMinimumHeight(150); lay.addWidget(self.details)
        row=QHBoxLayout(); row.addStretch()
        self.copy=QPushButton("📋 Copiar log completo"); self.copy.clicked.connect(self._copy); row.addWidget(self.copy)
        self.close_btn=QPushButton("Fechar"); self.close_btn.clicked.connect(self.hide); row.addWidget(self.close_btn)
        lay.addLayout(row)
        self._full_log=""
    def show_error(self,title,message,full_log):
        self.title.setText(title); self.message.setText(message); self.details.setPlainText(full_log); self._full_log=full_log
        self.adjustSize(); self.raise_(); self.show(); self.activateWindow()
    def _copy(self):
        try:
            QApplication.clipboard().setText(self._full_log)
            self.copy.setText("✓ Log copiado")
            self.copy.setEnabled(False)
            QTimer.singleShot(1600, self._reset_copy_button)
        except Exception:
            self.copy.setText("Não foi possível copiar")
            QTimer.singleShot(1800, self._reset_copy_button)

    def _reset_copy_button(self):
        self.copy.setText("📋 Copiar log completo")
        self.copy.setEnabled(True)

class MainWindow(QMainWindow):
    def __init__(self, project_dir: str | Path = "./projects") -> None:
        super().__init__()
        self.setWindowTitle(f"Automation Studio — AS {APP_VERSION}")
        self.setMinimumSize(560, 360)
        self._brand_icon_light = QIcon(str(_asset_path("AutomationStudio_light.ico")))
        self._brand_icon_dark = QIcon(str(_asset_path("AutomationStudio_dark.ico")))
        self.setWindowIcon(self._brand_icon_light)
        self.resize(1100, 650)
        self._layout_save_timer = QTimer(self)
        self._layout_save_timer.setSingleShot(True)
        self._layout_save_timer.setInterval(350)
        self._layout_save_timer.timeout.connect(self._save_main_window_layout)

        base_project_root = Path(project_dir).resolve()
        default_data_root = base_project_root
        selected_data_folder = _registered_data_dir(default_data_root)
        self.settings = AppSettings(selected_data_folder)
        # A janela principal NÃO fica mais sempre no topo.
        # Isso permite que outros aplicativos cubram o Automation Studio
        # e preserva o comportamento nativo do Windows para Snap (Win+Setas).
        # A propriedade visual "always_on_top" permanece somente para os
        # overlays de input (teclado/mouse), nunca para a MainWindow.
        self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
        self.project_manager = ProjectManager(selected_data_folder)
        self._default_maps_folder = selected_data_folder

        # Fase 4: um único StateManager compartilhado entre o
        # ExecutionEngine e o Recorder -- é o que garante, na prática,
        # que "gravar" e "executar" nunca acontecem ao mesmo tempo
        # (item 9/22 do roteiro), sem a MainWindow ter que reimplementar
        # essa regra.
        self.state = StateManager()
        self.engine = ExecutionEngine(_default_backend(), state_manager=self.state)
        self.input_backend_name = getattr(self.engine._backend, "name", type(self.engine._backend).__name__)
        self.bridge = EngineBridge()
        self.bridge.attach(self.engine)

        self.input_monitor = GlobalInputMonitor()
        self.capture_bridge = InputCaptureBridge()
        self.capture_bridge.attach(self.input_monitor)

        rec_cfg = self.settings.get_recording_settings()
        rec_filters = RecorderFilters(
            capture_keyboard=rec_cfg.get("capture_keyboard", True),
            capture_mouse_buttons=rec_cfg.get("capture_mouse_buttons", True),
            capture_mouse_move=rec_cfg.get("capture_mouse_move", True),
            capture_mouse_scroll=rec_cfg.get("capture_mouse_scroll", True),
            record_key_duration=rec_cfg.get("record_key_duration", True),
            merge_mouse_moves=rec_cfg.get("merge_mouse_moves", True),
            mouse_jitter_px=int(rec_cfg.get("mouse_jitter_px", 3)),
            mouse_sample_interval_ms=int(rec_cfg.get("mouse_sample_interval_ms", 8)),
            ignored_keys=frozenset(rec_cfg.get("ignored_keys", [])),
            ignored_mouse_buttons=frozenset(rec_cfg.get("ignored_mouse_buttons", [])),
        )
        self.recorder = Recorder(self.input_monitor, state_manager=self.state, filters=rec_filters)
        self._recording_target_map: AutomationMap | None = None
        self._recording_backup_map: AutomationMap | None = None
        self._recording_backup_path: Path | None = None
        self._recording_original_filters = None
        self._last_recorded_commands: list[Command] = []
        self._recording_status_timer = QTimer(self)
        self._recording_status_timer.setInterval(250)
        self._recording_status_timer.timeout.connect(self._update_recording_status)
        # F9: atualizacoes visuais sao agrupadas para evitar redesenhar a tabela/timeline
        # milhares de vezes por segundo durante gravacoes ou trajetorias de mouse.
        self._pending_mouse_event = None
        self._pending_progress = None
        self._ui_refresh_timer = QTimer(self)
        self._ui_refresh_timer.setInterval(40)
        self._ui_refresh_timer.timeout.connect(self._flush_ui_updates)
        self._ui_refresh_timer.start()

        # Fase 5 (item 10): Global Hotkey Manager -- instância própria,
        # separada de `self.input_monitor` (que serve só ao visualizador
        # e ao gravador), para que os atalhos continuem funcionando
        # independentemente desses dois estarem ligados ou não, e mesmo
        # com a janela minimizada. `HotkeyBridge` faz a travessia
        # thread-safe até a GUI thread (mesmo padrão de `EngineBridge`).
        self.hotkey_manager = GlobalHotkeyManager()
        self.hotkey_bridge = HotkeyBridge()
        self.hotkey_bridge.triggered.connect(self._on_hotkey_triggered)
        # 25.8: ativação por mapa (só nesta sessão / sempre / desativado) e conferência de conflitos de tecla. Lê as
        # configurações e os mapas na hora, por isso já pode existir aqui; o que decide é aplicado em `_register_all_hotkeys`.
        self.ativacao = ControladorAtivacao(self)
        # As teclas de pausar e continuar a automação (F9 e F10): o disparo chega em `_on_hotkey_triggered` e vai para aqui.
        self.controle = ControladorDeExecucao(self)

        self.keyboard_overlay: KeyboardOverlay | None = None
        self.mouse_overlay: MouseOverlay | None = None

        self._current_map: AutomationMap | None = None
        self._page_history: list[int] = []
        self.history = MapHistory(int(self.settings.get_visual_settings().get("undo_ram_mb",256)))
        self._restoring_history = False
        self.visual_settings = self.settings.get_visual_settings()
        # Largura da sidebar é tratada como estado próprio da interface.
        # Mantemos a última largura válida mesmo quando o QSplitter fica
        # temporariamente com 0 px enquanto o painel está fechado.
        try:
            saved_manual = self.visual_settings.get('sidebar_last_manual_width', None)
            if saved_manual is None:
                saved_manual = self.visual_settings.get('sidebar_width', 360)
            self._last_sidebar_width = max(180, int(saved_manual or 360))
        except (TypeError, ValueError):
            self._last_sidebar_width = 360
        # Migração visual dos padrões antigos para o novo acabamento dos
        # guias virtuais. Só substitui valores que ainda são os defaults
        # antigos, preservando escolhas feitas explicitamente pelo usuário.
        _legacy_virtual_defaults = {
            'virtual_surface_light': ('#FFFFFF', '#5A6068'),
            'virtual_text_dark': ('#F5F7FA', '#FFC53D'),
            'virtual_text_light': ('#2F343B', '#FFC53D'),
        }
        _migrated = False
        for _key, (_old, _new) in _legacy_virtual_defaults.items():
            if str(self.visual_settings.get(_key, '')).strip().upper() == _old:
                self.visual_settings[_key] = _new; _migrated = True
        if str(self.visual_settings.get('virtual_surface_dark', '')).strip().upper() == '#5C626C':
            self.visual_settings['virtual_surface_dark'] = '#4A4F57'; _migrated = True
        if _migrated:
            self.settings.set_visual_settings(self.visual_settings)
        core.set_runtime_defaults(self.visual_settings.get('text_char_interval'), self.visual_settings.get('app_stable_ms'), self.visual_settings.get('app_after_open'))
        self.engine.configure_readiness(
            history=self.visual_settings.get('app_readiness_history', {}),
            default_timeout=float(self.visual_settings.get('app_wait_timeout', 0.0) or 0.0),
            adaptive_learning=bool(self.visual_settings.get('app_adaptive_learning', True)),
            save_callback=self._save_readiness_history,
        )
        self._dark_theme, self._theme_accent = _resolve_theme_mode(self.visual_settings)
        # Painel interno sempre existe para receber eventos mesmo quando os
        # overlays estão ocultos. Ele não é exibido na janela principal.
        self.visualizer_panel = InputVisualizerPanel()

        self._build_toolbar()
        self._build_body()
        self.ativacao.montar_painel(self.map_instruction)  # 25.8: a faixa de ativação, no editor, logo abaixo da instrução
        self._restore_main_window_layout()
        self.error_notice = InAppErrorNotice(self)
        self._position_error_notice()
        self._build_status_bar()
        self._connect_bridge()
        self._connect_capture_bridge()

        self._apply_visual_settings()
        self._reload_map_list()
        self._register_all_hotkeys()
        self._update_history_actions()
        if self.hotkey_manager.available:
            self.hotkey_manager.start()

        # O visualizador real é um recurso permanente, não depende de um
        # checkbox para funcionar. Assim o teclado/mouse virtual continuam
        # mostrando o que está acontecendo mesmo com a janela minimizada.
        if self.input_monitor.available:
            try:
                self.input_monitor.start()
            except RuntimeError:
                pass

        # HUD só aparece quando solicitado ou quando o editor é minimizado.
        if not self.visual_settings.get('onboarding_seen', False):
            # Primeiro uso: cria uma automação de demonstração com comandos,
            # mas permanece no seletor. O primeiro balão ensina a criar uma
            # automação e, em seguida, conduz o usuário até o exemplo pronto.
            self._tutorial_first_run = True
            self._tutorial_first_run_stage = 'chooser'
            self._ensure_demo_automation_for_tutorial()
            self.pages.setCurrentIndex(1)
            self._start_context_tutorial(first_run=True)
        else:
            self.pages.setCurrentIndex(1)

    def _show_hud_overlays(self) -> None:
        self._toggle_keyboard_overlay(True); self._toggle_mouse_overlay(True)
        self._apply_visual_settings()
        if self.keyboard_overlay: self.keyboard_overlay.show(); self.keyboard_overlay.raise_()
        if self.mouse_overlay: self.mouse_overlay.show(); self.mouse_overlay.raise_()
        screen=QGuiApplication.primaryScreen(); area=screen.availableGeometry() if screen else None
        if area:
            if self.keyboard_overlay and self.keyboard_overlay.pos()==QPoint(0,0): self.keyboard_overlay.move(area.right()-self.keyboard_overlay.width()-18,area.top()+18)
            if self.mouse_overlay and self.mouse_overlay.pos()==QPoint(0,0): self.mouse_overlay.move(area.right()-self.mouse_overlay.width()-18,area.top()+240)
        if self.keyboard_overlay:self.keyboard_overlay.raise_()
        if self.mouse_overlay:self.mouse_overlay.raise_()
    def _ensure_overlays_for_minimized(self):
        if self.visual_settings.get('show_on_minimize',True): self._show_hud_overlays()
        self.status_bar.showMessage('Editor minimizado — guia visual ativo.',3000)
    def changeEvent(self,event):
        super().changeEvent(event)
        if event.type()==QEvent.WindowStateChange:
            if self.isMinimized(): self._ensure_overlays_for_minimized()
            else:
                # Ao voltar ao editor, o HUD fica oculto para não obstruir a tela.
                if self.keyboard_overlay and self.keyboard_overlay.isVisible() and not self.btn_toggle_keyboard.isChecked(): self.keyboard_overlay.hide()
                if self.mouse_overlay and self.mouse_overlay.isVisible() and not self.btn_toggle_mouse.isChecked(): self.mouse_overlay.hide()

    def _restore_main_window_layout(self) -> None:
        """Restaura tamanho, posição e estado nativos do Windows, sem forçar Always-on-Top."""
        try:
            g=self.visual_settings.get('main_window_geometry')
            if isinstance(g,str) and g:
                self.restoreGeometry(bytes.fromhex(g))
            st=self.visual_settings.get('main_window_state')
            if isinstance(st,str) and st:
                self.restoreState(bytes.fromhex(st))
        except Exception:
            pass
        # Nunca reabrir uma janela completamente fora de uma tela.
        try:
            center=self.frameGeometry().center()
            screen=QGuiApplication.screenAt(center) or QGuiApplication.primaryScreen()
            if screen:
                area=screen.availableGeometry()
                r=self.frameGeometry()
                x=max(area.left(), min(r.x(), area.right()-r.width()+1))
                y=max(area.top(), min(r.y(), area.bottom()-r.height()+1))
                self.move(x,y)
        except Exception:
            pass

    def _save_main_window_layout(self) -> None:
        try:
            self.visual_settings['main_window_geometry']=bytes(self.saveGeometry()).hex()
            self.visual_settings['main_window_state']=bytes(self.saveState()).hex()
            if hasattr(self,'workspace_splitter'):
                sizes=self.workspace_splitter.sizes()
                if len(sizes)==2:
                    left=int(sizes[0]); right=int(sizes[1])
                    if left > 20 or self.command_sidebar.isVisible():
                        self.visual_settings['workspace_splitter_sizes']=[left,right]
                        if left > 20:
                            self.visual_settings['sidebar_width']=left
            self.settings.set_visual_settings(self.visual_settings)
        except Exception:
            pass

    def eventFilter(self, watched, event):  # noqa: N802
        if watched is getattr(self, 'toolbar_scroll', None) and event.type() == QEvent.Resize:
            if hasattr(self, 'toolbar_hint') and hasattr(self, 'main_toolbar'):
                self.toolbar_hint.setVisible(self.main_toolbar.width() > self.toolbar_scroll.viewport().width() + 4)
        if watched in (getattr(self, 'toolbar_scroll', None), getattr(getattr(self, 'toolbar_scroll', None), 'viewport', lambda: None)()) and event.type() == QEvent.Wheel:
            delta=event.angleDelta().x()
            if not delta:
                delta=event.angleDelta().y()
            bar=self.toolbar_scroll.horizontalScrollBar()
            bar.setValue(bar.value()-delta)
            event.accept(); return True
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
            # ESC funciona mesmo quando o foco está em um widget filho da
            # janela principal (incluindo a barra lateral).
            if getattr(self, '_execution_sidebar', None) is not None and self._execution_sidebar.isVisible():
                self._close_execution_settings_sidebar()
                event.accept()
                return True
            if self.command_sidebar.isVisible():
                self._close_command_sidebar()
                event.accept()
                return True
            if self._navigate_back_page():
                event.accept(); return True
        return super().eventFilter(watched,event)

    def _navigate_page(self, index: int, remember: bool = True) -> None:
        current = self.pages.currentIndex()
        if current == index:
            return
        if remember and current >= 0:
            self._page_history.append(current)
            if len(self._page_history) > 24:
                self._page_history = self._page_history[-24:]
        self.pages.setCurrentIndex(index)

    def _navigate_back_page(self) -> bool:
        current = self.pages.currentIndex()
        while self._page_history:
            previous = self._page_history.pop()
            if previous != current:
                self.pages.setCurrentIndex(previous)
                return True
        # Fallback para páginas que ainda usam navegação direta internamente.
        # Mantemos a hierarquia natural do editor mesmo sem histórico explícito.
        fallback = {4: 3, 3: 2, 2: 1, 1: 1, 5: 2}
        previous = fallback.get(current)
        if previous is not None and previous != current:
            self.pages.setCurrentIndex(previous)
            return True
        return False

    def _schedule_layout_save(self) -> None:
        if hasattr(self, '_layout_save_timer'):
            self._layout_save_timer.start()

    def closeEvent(self, event) -> None:  # noqa: N802
        self._save_main_window_layout()
        # Item 25/11: fechar a janela principal nunca deve deixar a
        # automação rodando com teclas presas, nem os overlays órfãos.
        if hasattr(self, "_ui_refresh_timer"):
            self._ui_refresh_timer.stop()
        self.engine.emergency_stop()
        if self.recorder.is_recording:
            self._cancel_recording()
        else:
            self._discard_recording_backup()
        if self.input_monitor.is_running():
            self.input_monitor.stop()
        if self.hotkey_manager.is_running():
            self.hotkey_manager.stop()
        if self.keyboard_overlay is not None:
            self._save_overlay_geometry('keyboard', self.keyboard_overlay)
            self.keyboard_overlay.close()
        if self.mouse_overlay is not None:
            self._save_overlay_geometry('mouse', self.mouse_overlay)
            self.mouse_overlay.close()
        super().closeEvent(event)

    # ---- Construção da UI ------------------------------------------------

    def _save_readiness_history(self, history: dict) -> None:
        self.visual_settings['app_readiness_history'] = dict(history)
        try:
            self.settings.set_visual_settings(self.visual_settings)
        except Exception:
            pass

    def _build_toolbar(self) -> None:
        # O topo agora usa uma área horizontal rolável. O usuário não precisa
        # clicar em "..." para revelar ações escondidas: basta rolar horizontalmente
        # ou usar a barra inferior, como em uma faixa de abas do navegador.
        toolbar=QToolBar('Principal')
        toolbar.setMovable(False); toolbar.setFloatable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextOnly)
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setIconSize(QSize(15, 15))
        self.main_toolbar=toolbar
        self.brand_logo_label = QLabel('AS')
        self.brand_logo_label.setFixedSize(36, 30)
        self.brand_logo_label.setAlignment(Qt.AlignCenter)
        self.brand_logo_label.setStyleSheet('font-size:20px;font-weight:800;padding:0;margin:0;')
        pix = _load_brand_pixmap(getattr(self, "_dark_theme", False), 27)
        if not pix.isNull():
            self.brand_logo_label.setPixmap(pix)
        else:
            self.brand_logo_label.setText('AS')
        self.brand_logo_label.setToolTip("Automation Studio")
        actions=[]
        for label,handler in [('＋ Nova automação',self._new_map),('💾 Salvar',self._save_current_map),('▶ Executar',self._run_current_map)]:
            a=toolbar.addAction(label); a.triggered.connect(handler); actions.append(a)
        self.btn_run=actions[2]
        self.btn_record=toolbar.addAction('● Iniciar gravação')
        self.btn_record.setEnabled(self.input_monitor.available); self.btn_record.triggered.connect(self._toggle_recording)
        self.btn_cancel_record=toolbar.addAction('✕ Cancelar gravação')
        self.btn_cancel_record.setEnabled(False); self.btn_cancel_record.triggered.connect(self._cancel_recording)
        self.btn_stop=toolbar.addAction('■ Parar'); self.btn_stop.triggered.connect(lambda:self.engine.stop()); self.btn_stop.setEnabled(False)
        self.btn_preview_record=toolbar.addAction('▶ Pré-visualizar gravação'); self.btn_preview_record.triggered.connect(self._preview_recording); self.btn_preview_record.setEnabled(False)
        toolbar.addSeparator(); emergency=toolbar.addAction('🛑 Parar tudo'); emergency.triggered.connect(self._on_emergency)
        toolbar.addSeparator()
        self.act_undo=toolbar.addAction('↶ Desfazer'); self.act_undo.setShortcut(QKeySequence('Ctrl+Z')); self.act_undo.triggered.connect(self._undo_map)
        self.act_redo=toolbar.addAction('↷ Refazer'); self.act_redo.setShortcut(QKeySequence('Ctrl+Y')); self.act_redo.triggered.connect(self._redo_map)
        self.btn_settings=toolbar.addAction('⚙ Configurações'); self.btn_settings.triggered.connect(self._open_settings)
        self.btn_monitor=toolbar.addAction('▣ Monitor de execução'); self.btn_monitor.triggered.connect(self._open_execution_monitor)
        self.btn_tutorial=toolbar.addAction('❔ Tutorial'); self.btn_tutorial.triggered.connect(self._open_tutorial)
        self.btn_toggle_keyboard=toolbar.addAction('⌨ Mostrar teclado'); self.btn_toggle_keyboard.setCheckable(True); self.btn_toggle_keyboard.triggered.connect(self._toggle_keyboard_overlay)
        self.btn_toggle_mouse=toolbar.addAction('🖱 Mostrar mouse'); self.btn_toggle_mouse.setCheckable(True); self.btn_toggle_mouse.triggered.connect(self._toggle_mouse_overlay)

        scroll=QScrollArea()
        # Faixa superior compacta: a barra horizontal fica imediatamente
        # abaixo dos comandos, sem reservar uma área vertical desnecessária.
        scroll.setWidgetResizable(False); scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded); scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFixedHeight(31)
        scroll.setStyleSheet('''
            QScrollArea { border: none; padding: 0px; margin: 0px; }
            QScrollBar:horizontal { height: 5px; margin: 0px; padding: 0px; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { margin: 0px; }
        ''')
        scroll.setWidget(toolbar)
        self.toolbar_scroll=scroll
        scroll.installEventFilter(self)
        # Mantém a barra inteira em uma única linha, deixando a rolagem para
        # a área externa em vez do botão de extensão "..." do QToolBar.
        def size_toolbar():
            total=18
            for action in toolbar.actions():
                if action.isSeparator(): total += 12
                else:
                    w=toolbar.widgetForAction(action)
                    total += (w.sizeHint().width() if w else 90) + 4
            toolbar.setFixedWidth(max(total, toolbar.sizeHint().width(), 320))
            toolbar.setFixedHeight(max(toolbar.sizeHint().height(), 28))
            QTimer.singleShot(0, size_toolbar)
        # Indicador não clicável: comunica que existem mais ações à direita.
        # O acesso é feito por rolagem, nunca por menu de três pontos.
        container=QWidget(); top_lay=QHBoxLayout(container); top_lay.setContentsMargins(4,0,4,0); top_lay.setSpacing(2)
        top_lay.addWidget(self.brand_logo_label, 0, Qt.AlignVCenter)
        top_lay.addWidget(scroll,1)
        scroll.viewport().installEventFilter(self)
        self.setMenuWidget(container)


    def _build_body(self) -> None:
        self.pages=QStackedWidget()

        # Página 0: mini tutorial de primeira utilização. É uma página interna,
        # não um popup, para não interromper o usuário nem parecer uma janela externa.
        tutorial=QWidget(); tlay=QVBoxLayout(tutorial); tlay.setContentsMargins(24,18,24,18); tlay.setSpacing(7)
        self.tutorial_title=QLabel("Bem-vindo ao Automation Studio")
        self.tutorial_title.setStyleSheet("font-size:30px;font-weight:700;")
        tlay.addWidget(self.tutorial_title)
        self.tutorial_sub=QLabel("Em menos de um minuto você entenderá o fluxo básico para criar, gravar e ajustar uma automação.")
        self.tutorial_sub.setWordWrap(True); tlay.addWidget(self.tutorial_sub); tlay.addSpacing(15)
        steps=[
            ("1. Escolha uma automação","Abra uma automação existente ou crie uma nova. Cada automação é um mapa independente."),
            ("2. Adicione comandos","Na tabela, use “Adicionar comando” para teclas, cliques, movimentos e scroll. Os tempos podem ser ajustados diretamente."),
            ("3. Use a Timeline","A Timeline é uma visão visual dos tempos. Arraste os blocos para mover ações, ajuste a duração e use “Ajustar” para enquadrar toda a automação."),
            ("4. Grave o que você faz","“Iniciar gravação” começa a captura; o mesmo botão finaliza. “Cancelar gravação” descarta a captura e restaura o mapa anterior."),
            ("5. Configure seu ambiente","Em Configurações você controla aparência, gravação, mapas, atalhos, Undo/Redo e os guias visuais de teclado e mouse.")
        ]
        for title,desc in steps:
            card=QFrame(); card.setFrameShape(QFrame.StyledPanel); lay=QVBoxLayout(card)
            h=QLabel(title); h.setStyleSheet("font-size:16px;font-weight:700;"); d=QLabel(desc); d.setWordWrap(True); lay.addWidget(h); lay.addWidget(d)
            tlay.addWidget(card)
        tlay.addStretch()
        tut_buttons=QHBoxLayout(); tut_buttons.addStretch()
        self.tutorial_start=QPushButton("Começar a usar")
        self.tutorial_start.setMinimumHeight(42); self.tutorial_start.clicked.connect(self._finish_tutorial)
        tut_buttons.addStretch(); tut_buttons.addWidget(self.tutorial_start); tlay.addLayout(tut_buttons)

        # Página 1: escolha do mapa — nada de editor técnico antes disso.
        chooser=QWidget(); cl=QVBoxLayout(chooser); cl.setContentsMargins(24,18,24,18); cl.setSpacing(7)
        title=QLabel('Qual automação você quer usar?'); title.setStyleSheet('font-size:28px;font-weight:700'); cl.addWidget(title)
        sub=QLabel('Escolha uma automação existente ou crie uma nova para começar.'); sub.setStyleSheet('color:#9aa0aa;font-size:15px'); cl.addWidget(sub)
        self.map_search=QLineEdit(); self.map_search.setPlaceholderText('Pesquisar automações…'); self.map_search.setClearButtonEnabled(True); self.map_search.setToolTip('Digite para filtrar a lista. Ctrl+F leva o foco para esta pesquisa.'); self.map_search.textChanged.connect(self._filter_map_list); cl.addWidget(self.map_search)
        self.map_list=QListWidget(); self.map_list.setMinimumHeight(260); self.map_list.currentItemChanged.connect(self._on_map_selected); cl.addWidget(self.map_list)
        self.map_list_info=QLabel(''); self.map_list_info.setStyleSheet('color:#8f96a3;font-size:12px;'); cl.addWidget(self.map_list_info)
        self.btn_create_map=QPushButton('＋ CRIAR NOVA AUTOMAÇÃO'); self.btn_create_map.setMinimumHeight(48); self.btn_create_map.clicked.connect(self._new_map); cl.addWidget(self.btn_create_map)
        self.btn_import_external=QPushButton('📂 ABRIR / IMPORTAR MAPA EXTERNO'); self.btn_import_external.setMinimumHeight(42); self.btn_import_external.setToolTip('Selecione um mapa .json ou um banco AutomationStudio.db/.sqlite de outra instalação, incluindo mapas da V19.'); self.btn_import_external.clicked.connect(self._import_external_from_chooser); cl.addWidget(self.btn_import_external)
        self.btn_open_editor=QPushButton('ABRIR AUTOMAÇÃO SELECIONADA'); self.btn_open_editor.setMinimumHeight(42); self.btn_open_editor.clicked.connect(lambda:self.pages.setCurrentIndex(2) if self._current_map else None); cl.addWidget(self.btn_open_editor)
        # Página 2: editor.
        editor=QWidget(); el=QVBoxLayout(editor); el.setContentsMargins(12,7,12,7); el.setSpacing(5); top=QHBoxLayout(); top.setContentsMargins(0,0,0,0); top.setSpacing(4); self.editor_map_title=QLabel(''); self.editor_map_title.setStyleSheet('font-size:24px;font-weight:700'); top.addWidget(self.editor_map_title); top.addStretch(); back=QPushButton('← Escolher outra automação'); back.clicked.connect(lambda:self.pages.setCurrentIndex(1)); top.addWidget(back); el.addLayout(top)
        self.map_instruction=QLabel(''); self.map_instruction.setStyleSheet('color:#9aa0aa'); self.map_instruction.setContentsMargins(0,0,0,2); el.addWidget(self.map_instruction)
        self.command_table=CommandTableWidget(); self.command_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding); self.command_table.map_changed.connect(self._on_map_edited)
        self.command_table.test_requested.connect(self._test_selected_commands)
        self.command_table.preview_requested.connect(self._preview_automation)
        self.command_table.validate_requested.connect(self._validate_current_map)
        self.command_sidebar=QFrame(); self.command_sidebar.setObjectName('CommandSidebar'); self.command_sidebar.setFrameShape(QFrame.StyledPanel)
        self.command_sidebar.setMinimumWidth(0); self.command_sidebar.setMaximumWidth(1000); self.command_sidebar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding); self.command_sidebar.hide()
        self.command_sidebar_layout=QVBoxLayout(self.command_sidebar); self.command_sidebar_layout.setContentsMargins(8,6,8,6); self.command_sidebar_layout.setSpacing(5)
        self.command_sidebar_title=QLabel('Painel lateral')
        self.command_sidebar_title.setStyleSheet('font-size:15px;font-weight:700;padding:2px 3px;')
        self.command_sidebar_close=QPushButton('×')
        self.command_sidebar_close.setFixedSize(24,24)
        self.command_sidebar_close.setCursor(Qt.PointingHandCursor)
        self.command_sidebar_close.setToolTip('Fechar painel lateral (Esc)')
        self.command_sidebar_close.setStyleSheet('QPushButton { border: 0; background: transparent; color: #111111; font-size: 22px; font-weight: 400; padding: 0; } QPushButton:hover { color: #D62828; font-weight: 900; }')
        self.command_sidebar_close.clicked.connect(self._close_command_sidebar)
        title_row=QHBoxLayout(); title_row.setContentsMargins(0,0,0,0); title_row.setSpacing(2); title_row.addWidget(self.command_sidebar_title); title_row.addStretch(); title_row.addWidget(self.command_sidebar_close)
        self.command_sidebar_layout.addLayout(title_row)
        # O conteúdo do painel também é rolável. Em telas 800x600, nenhum
        # campo precisa escapar pela parte inferior; se a largura ficar
        # insuficiente, a rolagem horizontal revela os controles sem aumentar
        # a janela principal.
        self.command_sidebar_scroll=DragScrollArea(horizontal_drag=True, vertical_scroll=True); self.command_sidebar_scroll.setWidgetResizable(True)
        self.command_sidebar_host=QWidget(); self.command_sidebar_host.setMinimumWidth(0)
        self.command_sidebar_host_layout=QVBoxLayout(self.command_sidebar_host); self.command_sidebar_host_layout.setContentsMargins(0,0,0,0); self.command_sidebar_host_layout.setSpacing(6)
        self.command_sidebar_scroll.setWidget(self.command_sidebar_host); self.command_sidebar_layout.addWidget(self.command_sidebar_scroll,1)
        self.command_sidebar_footer=QWidget(); self.command_sidebar_footer.setObjectName('CommandSidebarFooter'); self.command_sidebar_footer.setMinimumHeight(42); self.command_sidebar_footer.setStyleSheet('#CommandSidebarFooter { border-top: 1px solid palette(mid); padding-top: 5px; }'); self.command_sidebar_footer_layout=QHBoxLayout(self.command_sidebar_footer); self.command_sidebar_footer_layout.setContentsMargins(0,5,0,0); self.command_sidebar_footer_layout.setSpacing(6); self.command_sidebar_layout.addWidget(self.command_sidebar_footer); self.command_sidebar_footer.hide()
        workspace=QSplitter(Qt.Horizontal); workspace.setChildrenCollapsible(False); workspace.setHandleWidth(7); workspace.addWidget(self.command_sidebar); workspace.addWidget(self.command_table); self.command_table.setMinimumWidth(180)
        self.command_sidebar.setMinimumWidth(0)
        # A sidebar jamais deve exigir que o usuário arraste o divisor até a
        # borda da janela. O limite efetivo é a área do workspace, preservando
        # sempre o mínimo necessário para o quadro de comandos.
        workspace.setStretchFactor(0,0); workspace.setStretchFactor(1,1); workspace.setMinimumWidth(1)
        workspace.setHandleWidth(7)
        workspace.setStyleSheet("QSplitter::handle { background: palette(mid); margin: 2px 0; } QSplitter::handle:hover { background: #FFC53D; }")
        self.workspace_splitter=workspace
        self._last_sidebar_width = max(180, int(self._last_sidebar_width))
        self._sidebar_layout_guard = False
        # A geometria da janela ainda pode ser restaurada logo depois deste
        # método. Portanto a largura persistida da sidebar é aplicada em dois
        # tempos: primeiro como estado seguro, depois novamente após o layout
        # da janela estar estabilizado. Isso evita que o Qt substitua a posição
        # salva ao recalcular o splitter após restoreGeometry().
        workspace.setSizes([0, max(180, self.width()-20)])
        workspace.splitterMoved.connect(self._on_workspace_splitter_moved)
        QTimer.singleShot(0, self._restore_workspace_splitter)
        el.addWidget(workspace,stretch=1)
        self.command_table.command_editor_requested.connect(self._open_command_sidebar)
        self._command_sidebar_dialog=None; self._command_sidebar_animation=None
        self._command_sidebar_mode=None; self._pending_sidebar_request=None
        self._execution_sidebar=None
        self.timeline_panel=TimelinePanel(); self.timeline_panel.map_changed.connect(self._on_timeline_edited); self.timeline_panel.selection_changed.connect(self._on_timeline_selection_changed)
        # Timeline é uma página interna do aplicativo, nunca uma janela/popup.
        timeline_page=QWidget(); tl=QVBoxLayout(timeline_page); tl.setContentsMargins(14,10,14,14)
        tl_top=QHBoxLayout(); back_tl=QPushButton('← Voltar ao editor'); back_tl.clicked.connect(lambda:self.pages.setCurrentIndex(2)); tl_top.addWidget(back_tl); tl_top.addWidget(QLabel('Timeline da automação'),1); tl.addLayout(tl_top); tl.addWidget(self.timeline_panel,1)
        bottom=QHBoxLayout(); bottom.setContentsMargins(0,2,0,0); bottom.setSpacing(6); cfg=QPushButton('⚙ Configurações da automação'); cfg.clicked.connect(self._configure_current_map); bottom.addWidget(cfg); self.btn_timeline=QPushButton('▣ Abrir Timeline'); self.btn_timeline.clicked.connect(self._open_timeline); bottom.addWidget(self.btn_timeline); bottom.addStretch(); self.hotkey_label=QLabel('Tecla para iniciar/parar: —'); self.repeat_label=QLabel('Repetição: —'); self.speed_label=QLabel('Velocidade: —'); bottom.addWidget(self.hotkey_label); bottom.addWidget(self.repeat_label); bottom.addWidget(self.speed_label); el.addLayout(bottom)
        self.pages.addWidget(tutorial); self.pages.addWidget(chooser); self.pages.addWidget(editor); self.pages.addWidget(timeline_page)
        self.merged_editor_page=QWidget(); self.merged_editor_layout=QVBoxLayout(self.merged_editor_page); self.pages.addWidget(self.merged_editor_page)

        # Página interna de monitoramento da execução (V20F8). Não é popup:
        # serve para acompanhar a automação sem disputar espaço com janelas externas.
        self.execution_page=QWidget(); ex=QVBoxLayout(self.execution_page); ex.setContentsMargins(22,18,22,18)
        ex_head=QHBoxLayout(); back_ex=QPushButton('← Voltar ao editor'); back_ex.clicked.connect(lambda:self.pages.setCurrentIndex(2)); ex_head.addWidget(back_ex); ex_head.addWidget(QLabel('Monitor de execução'),1); ex.addLayout(ex_head)
        self.exec_state_label=QLabel('Estado: parado'); self.exec_map_label=QLabel('Automação: —'); self.exec_event_label=QLabel('Último evento: —'); self.exec_progress=QProgressBar(); self.exec_progress.setRange(0,1000); self.exec_progress.setValue(0); self.exec_progress.setTextVisible(True)
        ex.addWidget(self.exec_state_label); ex.addWidget(self.exec_map_label); ex.addWidget(self.exec_event_label); ex.addWidget(self.exec_progress)
        self.exec_chain_label=QLabel('Próxima automação: —'); ex.addWidget(self.exec_chain_label)
        ex.addWidget(QLabel('Este painel acompanha a execução em tempo real. A automação continua funcionando mesmo se o painel for fechado ou o programa for minimizado.'))
        self.pages.addWidget(self.execution_page)
        self.setCentralWidget(self.pages)
        QApplication.instance().installEventFilter(self)
        self._editor_page=editor
        self._chooser_page=chooser
        self._timeline_page=timeline_page

    def _update_sidebar_limits(self) -> None:
        # Recalcula o limite do splitter conforme o workspace real. O editor
        # interno recebe a largura efetiva da sidebar, sem depender da largura
        # total da janela para decidir quando pode quebrar as linhas.
        if hasattr(self, 'workspace_splitter') and hasattr(self, 'command_sidebar'):
            sizes=self.workspace_splitter.sizes()
            total=max(1, sum(sizes))
            max_sidebar=max(160, total-180)
            self.command_sidebar.setMaximumWidth(max_sidebar if self.command_sidebar.isVisible() else 1000)
        if hasattr(self, '_command_sidebar_dialog') and self._command_sidebar_dialog is not None:
            try:
                self._command_sidebar_dialog.updateGeometry()
            except Exception:
                pass

    def _sync_command_table_selection_from_timeline(self) -> None:
        if not hasattr(self, 'command_table') or not self._current_map:
            return
        ids=set(getattr(self.timeline_panel.canvas,'_selected_ids',set())) if hasattr(self,'timeline_panel') else set()
        table=self.command_table.table
        table.blockSignals(True)
        try:
            table.clearSelection()
            for row,c in enumerate(self._current_map.commands):
                if c.id in ids:
                    table.selectRow(row)
            if ids:
                rows=[i for i,c in enumerate(self._current_map.commands) if c.id in ids]
                if rows: table.setCurrentCell(rows[-1],0)
        finally:
            table.blockSignals(False)
        self.command_table._update_selection_summary()

    def _on_timeline_selection_changed(self, _command) -> None:
        self._sync_command_table_selection_from_timeline()

    def _open_command_sidebar(self, command: Command | None = None, index: int = -1) -> None:
        if not self._current_map:
            return
        if hasattr(self, '_timeline_page') and self.pages.currentIndex() == 3 and hasattr(self, 'timeline_panel'):
            self.timeline_panel.open_command_sidebar(command, index)
            return
        requested_mode = 'add' if command is None else 'edit'
        current_mode = getattr(self, '_command_sidebar_mode', None)
        # Se o painel já está aberto para o mesmo propósito, não reinicie a
        # animação. Isso evita o efeito visual de "fechar/abrir" a cada clique.
        if self.command_sidebar.isVisible() and current_mode == requested_mode and self._command_sidebar_dialog is not None:
            if requested_mode == 'edit' and index >= 0:
                self._command_sidebar_dialog.load_command(command)
                self._command_sidebar_dialog._command_index = index
            return
        if self.command_sidebar.isVisible():
            # Troca de edição → adição (ou vice-versa): saída completa e só
            # depois entrada do novo editor.
            self._pending_sidebar_request = (command, index, requested_mode)
            self._animate_command_sidebar(False)
            return
        self._show_command_sidebar(command, index, requested_mode)

    def _show_command_sidebar(self, command: Command | None, index: int, mode: str) -> None:
        editor=CommandDialog(command=command, parent=self.command_sidebar_host)
        editor.setWindowFlags(Qt.Widget); editor.setModal(False)
        editor._command_index = index
        if command is None:
            if 0 <= index <= len(self._current_map.commands):
                # Ao inserir no meio da automação, o início sugerido fica logo
                # após o comando anterior, sem deslocar automaticamente os
                # demais tempos; a posição de execução é controlada pela lista.
                previous_end = self._current_map.commands[index - 1].effective_end if index > 0 else 0.0
                editor.start.setValue(previous_end)
            elif self._current_map.commands:
                editor.start.setValue(self._current_map.latest_end())
        self.command_sidebar_host_layout.addWidget(editor)
        # O rodapé de ação fica fora da área rolável. O editor mantém seus sinais,
        # mas o QDialogButtonBox original não deve ocupar espaço dentro da rolagem.
        try:
            editor.layout().removeWidget(editor.buttons)
            editor.buttons.hide()
        except Exception:
            pass
        while self.command_sidebar_footer_layout.count():
            item=self.command_sidebar_footer_layout.takeAt(0); w=item.widget()
            if w: w.deleteLater()
        btn_cancel=QPushButton('Cancelar'); btn_action=QPushButton('Adicionar' if command is None else 'Salvar')
        btn_cancel.clicked.connect(editor.reject); btn_action.clicked.connect(editor._accept)
        self.command_sidebar_footer_layout.addStretch(); self.command_sidebar_footer_layout.addWidget(btn_cancel); self.command_sidebar_footer_layout.addWidget(btn_action)
        self.command_sidebar_footer.show()
        self._command_sidebar_dialog=editor
        self._command_sidebar_mode=mode
        self.command_sidebar_title.setText('Editar comando' if mode == 'edit' else 'Adicionar comando')
        def save():
            new_cmd=editor.result_command()
            active_index = getattr(editor, '_command_index', index)
            if mode == 'add':
                # Adição nunca substitui o comando da linha de referência.
                # A seleção determina a posição de inserção e a tabela central
                # é atualizada como uma inserção real na lista de execução.
                if active_index < 0:
                    active_index = len(self._current_map.commands)
                insert_at = max(0, min(int(active_index), len(self._current_map.commands)))
                if insert_at > 0 and insert_at <= len(self._current_map.commands):
                    new_cmd.start = self._current_map.commands[insert_at - 1].effective_end
                elif not self._current_map.commands:
                    new_cmd.start = 0.0
                self._current_map.insert_command(new_cmd, insert_at)
            elif 0 <= active_index < len(self._current_map.commands):
                self._current_map.commands[active_index]=new_cmd
            else:
                new_cmd.start=self._current_map.latest_end(); self._current_map.add_command(new_cmd)
            self.command_table.refresh(); self._on_map_edited(); self._close_command_sidebar()
        editor.accepted.connect(save); editor.rejected.connect(self._close_command_sidebar)
        self.command_sidebar.show(); self._animate_command_sidebar(True)

    def _restore_workspace_splitter(self) -> None:
        """Restaura a última largura realmente escolhida pelo usuário."""
        if not hasattr(self, 'workspace_splitter'):
            return
        self._sidebar_layout_guard = True
        try:
            sizes = self.workspace_splitter.sizes()
            total = max(1, sum(sizes))
            try:
                candidate = int(self.visual_settings.get('sidebar_width', 360) or 360)
            except (TypeError, ValueError):
                candidate = 360
            if candidate <= 20:
                saved = self.visual_settings.get('workspace_splitter_sizes')
                candidate = int(saved[0]) if isinstance(saved, list) and len(saved) == 2 and int(saved[0] or 0) > 20 else 360
            left = max(160, min(candidate, max(160, total - 180)))
            self.workspace_splitter.setSizes([left, total - left])
            self._last_sidebar_width = int(left)
            self.visual_settings['sidebar_width'] = int(left)
        except Exception:
            pass
        finally:
            self._sidebar_layout_guard = False

    def _animate_command_sidebar(self, opening: bool) -> None:
        sizes=self.workspace_splitter.sizes()
        current_width=int(sizes[0]) if sizes else int(self.command_sidebar.width())
        saved=max(160, int(getattr(self, '_last_sidebar_width', self.visual_settings.get('sidebar_last_manual_width', self.visual_settings.get('sidebar_width', 360))) or 360))
        sizes=self.workspace_splitter.sizes()
        workspace_total=max(1, sum(sizes))
        available=workspace_total
        target=min(saved, max(160, available - 180)) if opening else 0
        if opening and self.command_sidebar.isVisible() and current_width >= max(1, target - 2):
            return
        if (not opening) and current_width <= 1 and not self.command_sidebar.isVisible():
            return
        if getattr(self, '_command_sidebar_animation', None):
            try: self._command_sidebar_animation.stop()
            except Exception: pass
        self._sidebar_layout_guard = True
        self.command_sidebar.setMinimumWidth(current_width if opening else 0)
        self.command_sidebar.setMaximumWidth(max(current_width, target, 280) if opening else max(current_width, 1000))
        group=QParallelAnimationGroup(self)
        for prop in (b'minimumWidth', b'maximumWidth'):
            a=QPropertyAnimation(self.command_sidebar, prop, group)
            a.setDuration(180)
            a.setEasingCurve(QEasingCurve.OutCubic)
            a.setStartValue(current_width)
            a.setEndValue(target)
            group.addAnimation(a)
        self._command_sidebar_animation=group
        if opening:
            self.command_sidebar.show()
        def done():
            # A largura persistida representa somente uma escolha real do
            # usuário; nunca gravamos os 0 px do fechamento nem a largura
            # intermediária da animação.
            if opening:
                self.command_sidebar.setMinimumWidth(160)
                self.command_sidebar.setMaximumWidth(max(220, int(self.width() * 0.78)))
                self._set_sidebar_width(target)
                self._last_sidebar_width = int(target)
                self.visual_settings['sidebar_width'] = int(target)
                self.visual_settings['sidebar_last_manual_width'] = int(target)
                self._sidebar_layout_guard = False
                self.settings.set_visual_settings(self.visual_settings)
            else:
                self.command_sidebar.hide()
                while self.command_sidebar_host_layout.count():
                    item=self.command_sidebar_host_layout.takeAt(0); w=item.widget()
                    if w: w.deleteLater()
                self._command_sidebar_dialog=None; self._command_sidebar_mode=None
                self.command_sidebar_footer.hide()
                self.command_sidebar.setMinimumWidth(0); self.command_sidebar.setMaximumWidth(1000)
                # Não persistimos o estado fechado (0 px).
                self._sidebar_layout_guard = False
                pending=getattr(self, '_pending_sidebar_request', None); self._pending_sidebar_request=None
                if pending:
                    command, index, mode = pending
                    if mode == 'settings': QTimer.singleShot(20, self._show_settings_sidebar)
                    else: QTimer.singleShot(20, lambda c=command, i=index, m=mode: self._show_command_sidebar(c, i, m))
        group.finished.connect(done)
        group.start()

    def _set_sidebar_width(self, width: int) -> None:
        sizes=self.workspace_splitter.sizes(); total=max(1, sum(sizes))
        if len(sizes)!=2: return
        width=max(0,min(int(width), max(0,total-180)))
        self._sidebar_layout_guard = True
        try:
            self.workspace_splitter.setSizes([width,total-width])
        finally:
            # splitterMoved pode ser emitido de forma síncrona; o estado deve
            # continuar protegido até a próxima chamada do ciclo de eventos.
            QTimer.singleShot(0, lambda: setattr(self, '_sidebar_layout_guard', False))

    def _on_workspace_splitter_moved(self, _pos: int, _index: int) -> None:
        if getattr(self, '_sidebar_layout_guard', False):
            return
        # Este sinal é considerado a fonte oficial de alterações manuais.
        # Somente uma largura positiva e visível pode substituir a largura
        # persistida; fechar a sidebar jamais transforma a memória em 0.
        try:
            sizes=self.workspace_splitter.sizes()
            if len(sizes)!=2 or not self.command_sidebar.isVisible():
                return
            left=int(sizes[0])
            if left <= 20:
                return
            self._last_sidebar_width=max(160,left)
            self.visual_settings['sidebar_width']=self._last_sidebar_width
            self.visual_settings['sidebar_last_manual_width']=self._last_sidebar_width
            self.visual_settings['workspace_splitter_sizes']=[left,int(sizes[1])]
            self.settings.set_visual_settings(self.visual_settings)
        except Exception:
            pass

    def _save_workspace_layout(self) -> None:
        """Persiste imediatamente a largura da barra lateral e a divisão do workspace.

        Esta rotina é deliberadamente apenas de persistência. A animação da
        barra lateral pertence a _animate_command_sidebar(); manter as duas
        responsabilidades separadas evita referências residuais a `group` ou
        `opening` e impede que um simples arraste do divisor tente executar uma
        animação inexistente.
        """
        if not hasattr(self, 'workspace_splitter') or getattr(self, '_sidebar_layout_guard', False): return
        try:
            sizes=self.workspace_splitter.sizes()
            if len(sizes)==2 and self.command_sidebar.isVisible():
                left=max(0,int(sizes[0])); right=max(0,int(sizes[1]))
                if left > 20:
                    self.visual_settings['workspace_splitter_sizes']=[left,right]
                    self.visual_settings['sidebar_width']=left
                    self._last_sidebar_width=max(160,left)
                    self.visual_settings['sidebar_last_manual_width']=self._last_sidebar_width
                    self.settings.set_visual_settings(self.visual_settings)
        except Exception:
            pass

    def _close_command_sidebar(self, immediate: bool = False) -> None:
        if getattr(self, '_execution_sidebar', None) is not None:
            self._close_execution_settings_sidebar()
        if immediate:
            if self._command_sidebar_animation: self._command_sidebar_animation.stop()
            self.command_sidebar.hide(); self._set_sidebar_width(0); self.command_sidebar.setMinimumWidth(0); self.command_sidebar.setMaximumWidth(1000)
            while self.command_sidebar_host_layout.count():
                item=self.command_sidebar_host_layout.takeAt(0); w=item.widget()
                if w: w.deleteLater()
            self._command_sidebar_dialog=None; self._command_sidebar_mode=None; self._pending_sidebar_request=None; self.command_sidebar_footer.hide(); return
        if self.command_sidebar.isVisible(): self._animate_command_sidebar(False)

    def _open_editor_for_merged(self, command: Command | None) -> None:
        if command is None:
            self.pages.setCurrentIndex(3); return
        while self.merged_editor_layout.count():
            item=self.merged_editor_layout.takeAt(0); w=item.widget()
            if w: w.deleteLater()
        editor=MergedMouseEditor(command, self)
        editor.map_changed.connect(self._on_timeline_edited)
        top=QHBoxLayout(); back=QPushButton("← Voltar à timeline"); back.clicked.connect(lambda:self.pages.setCurrentIndex(3)); top.addWidget(back); top.addWidget(QLabel("Editar linhas mescladas")); top.addStretch(); self.merged_editor_layout.addLayout(top); self.merged_editor_layout.addWidget(editor)
        self.pages.setCurrentIndex(4)

    def _open_timeline(self) -> None:
        if not self._current_map:
            self.status_bar.showMessage('Selecione uma automação primeiro.', 3000)
            return
        self.timeline_panel.set_map(self._current_map)
        self.timeline_panel.btn_simple.setChecked(True)
        self.timeline_panel.btn_advanced.setChecked(False)
        self.timeline_panel.canvas.set_simple_mode(True)
        self.timeline_panel.refresh()
        self.pages.setCurrentIndex(3)
        self.timeline_panel.fit_to_viewport()

    def _ensure_demo_automation_for_tutorial(self) -> None:
        """Cria uma automação demonstrativa completa apenas no primeiro onboarding."""
        if self.project_manager.maps:
            return
        demo=AutomationMap(name="Exemplo — Primeira automação", hotkey="=", repeat_count=1)
        message=("Já pensou nas possibilidades? Esse programa pode te ajudar a deixar seu "
                 "fluxo de trabalho mais confortável, te dando mais tempo para o que realmente "
                 "importa. A sua criatividade, em ação!")
        commands=[
            Command(type=InputType.APP_OPEN, target="notepad.exe", action=ActionType.PRESS_AND_RELEASE, start=0.0, duration=0.0, description="Abrir o Bloco de Notas", wait_process="notepad.exe", wait_timeout=float(self.visual_settings.get('app_wait_timeout', 0.0) or 0.0), wait_min_ram_mb=0.0, wait_stable_ms=int(self.visual_settings.get('app_stable_ms', core.APP_STABLE_DEFAULT_MS)), wait_after_open=float(self.visual_settings.get('app_after_open', core.APP_AFTER_OPEN_DEFAULT))),
            Command(type=InputType.TEXT, text=message, action=ActionType.PRESS_AND_RELEASE, start=0.10, duration=0.0, description="Mensagem de demonstração", wait_process="notepad.exe", wait_timeout=float(self.visual_settings.get('app_wait_timeout', 0.0) or 0.0), wait_min_ram_mb=0.0, wait_stable_ms=int(self.visual_settings.get('app_stable_ms', core.APP_STABLE_DEFAULT_MS)), wait_after_open=float(self.visual_settings.get('app_after_open', core.APP_AFTER_OPEN_DEFAULT))),
        ]
        demo.commands=commands
        self.project_manager.save_map(demo)
        self._reload_map_list()
        self._select_map_by_name(demo.name)

    def _tutorial_steps_for_current_page(self):
        """Retorna os passos do tutorial contextual da tela atual.

        No primeiro uso, o tutorial é uma jornada única: seletor → editor →
        timeline → editor/configurações. Em uso posterior, o botão Tutorial
        continua abrindo apenas a parte contextual da tela atual.
        """
        idx=self.pages.currentIndex()
        first_run=getattr(self, '_tutorial_first_run', False)
        stage=getattr(self, '_tutorial_first_run_stage', '')

        if idx == 1:  # seletor de mapas
            return [
                {"target": self.map_list,
                 "text":"Aqui ficam suas automações. Escolha uma existente para continuar ou use o botão de criar uma nova."},
                {"target": self.btn_create_map,
                 "text":"“Criar nova automação” começa um mapa vazio. Cada mapa possui seus próprios comandos, atalho, repetição, grupos e configurações."},
                {"target": self.btn_import_external,
                 "text":"“Abrir / importar mapa externo” permite trazer um mapa JSON ou banco compatível de outra instalação."},
                {"target": self.btn_open_editor,
                 "text":"Com uma automação selecionada, use este botão para entrar no editor. No primeiro uso, o exemplo já vem preparado para você explorar o programa."},
            ]

        if idx == 2:  # editor
            base = [
                {"target": self.command_table.btn_add,
                 "text":"“Adicionar comando” cria ações de teclado, mouse, movimento, rolagem e texto. Cada ação pode ser posicionada e ajustada na sequência."},
                {"target": self.command_sidebar,
                 "text":"A edição e a adição de comandos acontecem nesta barra lateral interna. Ela pode ser redimensionada arrastando a divisória e, quando necessário, o conteúdo pode ser rolado para revelar opções que não cabem na largura disponível."},
                {"target": self.command_table.table,
                 "text":"A tabela mostra a ordem, tipo, alvo, início, duração e grupo de cada comando. É possível editar os valores diretamente e reorganizar a sequência."},
                {"target": self.btn_record,
                 "text":"“Iniciar gravação” captura o que você faz com teclado e mouse. O mesmo botão encerra a gravação; “Cancelar gravação” descarta a captura em andamento."},
                {"target": self.btn_timeline,
                 "text":"A Timeline apresenta a automação visualmente no tempo. Ela será aberta automaticamente na próxima etapa deste primeiro tutorial."},
                {"target": self.btn_settings,
                 "text":"“Configurações” abre as preferências gerais do programa, incluindo aparência, guias virtuais, gravação, atalhos e comportamento do ambiente."},
                {"target": self.btn_monitor,
                 "text":"“Monitor de execução” mostra estado, automação ativa, último evento e progresso enquanto uma automação é executada."},
                {"target": self.btn_toggle_keyboard,
                 "text":"“Mostrar teclado” ativa o guia visual do teclado. Ele pode acompanhar as teclas reais usadas ou mostrar o teclado completo."},
                {"target": self.btn_toggle_mouse,
                 "text":"“Mostrar mouse” ativa o guia visual do mouse. Os dois guias também podem aparecer quando o programa é minimizado, conforme as configurações."},
                {"target": self.btn_run,
                 "text":"“Executar” inicia a automação selecionada. Durante a execução, os controles de pausa, parada e emergência protegem contra comandos presos ou execução indesejada."},
                {"target": self.hotkey_label,
                 "text":"Último passo: escolha a tecla que iniciará e parará esta automação. Ao concluir, o exemplo será executado uma vez para você ver o fluxo funcionando."},
            ]
            # No primeiro uso, a jornada já abriu Adicionar, Editar e
            # Configurações separadamente. Depois da Timeline, mostramos apenas
            # o atalho final para não repetir explicações anteriores.
            if first_run and stage == 'after_timeline':
                return [base[-1]]
            return base[:4] if first_run and stage == 'editor_before_timeline' else base

        if idx == 3:  # timeline
            return [
                {"target": self.timeline_panel,
                 "text":"A Timeline mostra cada comando como uma ação ao longo do tempo. A posição representa quando começa e a extensão representa sua duração."},
                {"target": self.timeline_panel.btn_simple,
                 "text":"A visão simples é a leitura recomendada para começar. Ela mantém a sequência fácil de entender e permite enquadrar toda a automação."},
                {"target": self.timeline_panel.btn_advanced,
                 "text":"A visão avançada expõe controles para ajustes mais precisos de tempos, sobreposições, grupos e movimentos."},
            ]

        if idx == 5:  # monitor
            return [{"target": self.exec_progress,
                     "text":"O Monitor acompanha a execução em tempo real: estado, automação ativa, último evento e progresso. A automação continua mesmo que este painel seja fechado."}]

        return [{"target": self.btn_settings,
                 "text":"As configurações gerais personalizam o ambiente do Automation Studio. O tutorial contextual pode ser reaberto a qualquer momento pelo botão “Tutorial”."}]

    def _start_context_tutorial(self, first_run=False):
        old=getattr(self, "_context_tutorial", None)
        if old:
            old.close()
        steps=self._tutorial_steps_for_current_page()
        if not steps:
            return
        self._context_tutorial=ContextTutorialOverlay(self, steps, on_finish=(lambda skipped=False: self._finish_tutorial(first_run, skipped)))
        self._context_tutorial.show()
        self._context_tutorial.raise_()
        self._context_tutorial.setFocus()

    def _open_tutorial(self) -> None:
        if self.command_sidebar.isVisible() and self._command_sidebar_dialog is not None:
            target=self._command_sidebar_dialog
            text=("Esta barra lateral concentra a edição sem abrir outra janela. "
                  "Arraste a divisória para aumentar ou reduzir sua largura. "
                  "Se algum controle não couber, use a rolagem do painel para acessar o restante das opções.")
            self._context_tutorial=ContextTutorialOverlay(self,[{"target":target,"text":text}],on_finish=lambda skipped=False: self._finish_tutorial(getattr(self, '_tutorial_first_run', False), skipped))
            self._context_tutorial.show(); self._context_tutorial.raise_(); self._context_tutorial.setFocus()
            return
        self._start_context_tutorial()

    def _tutorial_overlay_for_target(self, target, text):
        old=getattr(self, '_context_tutorial', None)
        if old: old.close()
        self._context_tutorial=ContextTutorialOverlay(self,[{"target":target,"text":text}],on_finish=lambda skipped=False: self._finish_tutorial(getattr(self, '_tutorial_first_run', False), skipped))
        self._context_tutorial.show(); self._context_tutorial.raise_(); self._context_tutorial.setFocus()

    def _open_tutorial_add_sidebar(self):
        self._open_command_sidebar(None, -1)
        QTimer.singleShot(220, lambda: self._tutorial_overlay_for_target(
            self.command_sidebar,
            "Esta é a barra lateral de Adicionar comando. Primeiro escolha o tipo de ação: tecla, mouse, movimento, scroll, texto ou abertura de aplicativo. Depois preencha somente os dados necessários para aquele tipo. Por exemplo, em Abrir aplicativo você escolhe um programa ou procura seu .exe; em Digitar texto você fornece o conteúdo; em Pressionar tecla você escolhe a tecla. Os campos avançados controlam início, atraso, grupos e sincronização. A barra não aumenta a janela: ela comprime o editor e pode ser redimensionada pela divisória. Use a rolagem quando a proporção da tela esconder controles. As explicações curtas aparecem por tooltip ao passar o mouse sobre os rótulos das opções, para não ocupar espaço permanentemente. As explicações curtas das opções aparecem ao passar o mouse sobre os rótulos, mantendo a sidebar limpa."))

    def _open_tutorial_edit_sidebar(self):
        command=self._current_map.commands[0] if self._current_map and self._current_map.commands else None
        if command is not None:
            self._open_command_sidebar(command, 0)
            QTimer.singleShot(220, lambda: self._tutorial_overlay_for_target(
                self.command_sidebar,
                "Esta é a barra lateral de Editar comando. Ela carrega exatamente o comando selecionado, preservando seus valores. Você pode trocar o tipo de ação, substituir o aplicativo, alterar texto, tecla, posição, duração, início e sincronização. Se faltar uma informação obrigatória, salvar não altera o mapa e uma mensagem discreta informa o que faltou. Assim, editar um comando não cria uma nova ação por engano."))
        else:
            self._tutorial_first_run_stage='settings_sidebar'
            self._open_tutorial_settings_sidebar()

    def _open_tutorial_settings_sidebar(self):
        self._show_settings_sidebar()
        QTimer.singleShot(220, lambda: self._tutorial_overlay_for_target(
            self.command_sidebar,
            "Configurações ficam nesta mesma barra lateral. Você pode ajustar aparência, teclado e mouse virtuais, gravação, atalhos, histórico e execução. Na guia Execução, o intervalo entre caracteres controla a velocidade da digitação; a estabilidade do aplicativo define quanto tempo o processo deve permanecer presente antes de liberar o próximo comando; e o atraso após o aplicativo estar pronto acrescenta uma margem final. Essas opções permitem equilibrar velocidade e confiabilidade sem editar cada automação individualmente. Quando uma explicação não é necessária, ela permanece oculta e aparece apenas ao passar o mouse sobre o rótulo correspondente."))

    def _finish_tutorial(self, first_run=False, skipped=False) -> None:
        # Feche PRIMEIRO o overlay que disparou este callback. A implementação
        # anterior criava o próximo overlay e depois fechava self._context_tutorial,
        # o que podia fechar acidentalmente o tutorial recém-criado.
        current=getattr(self, '_context_tutorial', None)
        if current:
            self._context_tutorial=None
            current.close()

        if first_run:
            if skipped:
                # "Pular tutorial" encerra a jornada inteira, inclusive as
                # páginas tutoriais que seriam abertas nas etapas seguintes.
                # Não avançamos para nenhuma etapa posterior nem abrimos a
                # demonstração automaticamente.
                self._tutorial_first_run=False
                self._tutorial_first_run_stage='done'
                self.visual_settings['onboarding_seen']=True
                self.settings.set_visual_settings(self.visual_settings)
                if self.command_sidebar.isVisible():
                    self._close_command_sidebar(immediate=True)
                self.pages.setCurrentIndex(1 if hasattr(self, '_chooser_page') else self.pages.currentIndex())
                return
            stage=getattr(self, '_tutorial_first_run_stage', 'chooser')
            if stage == 'chooser':
                self._tutorial_first_run_stage='editor_before_timeline'
                self.pages.setCurrentIndex(2)
                self.command_table.set_map(self._current_map)
                self.timeline_panel.set_map(self._current_map)
                QTimer.singleShot(80, lambda: self._start_context_tutorial(first_run=True))
                return
            if stage == 'editor_before_timeline':
                self._tutorial_first_run_stage='add_sidebar'
                self.pages.setCurrentIndex(2)
                self.command_table.set_map(self._current_map)
                QTimer.singleShot(120, self._open_tutorial_add_sidebar)
                return
            if stage == 'add_sidebar':
                self._tutorial_first_run_stage='edit_sidebar'
                self._close_command_sidebar(immediate=True)
                QTimer.singleShot(120, self._open_tutorial_edit_sidebar)
                return
            if stage == 'edit_sidebar':
                self._tutorial_first_run_stage='settings_sidebar'
                self._close_command_sidebar(immediate=True)
                QTimer.singleShot(120, self._open_tutorial_settings_sidebar)
                return
            if stage == 'settings_sidebar':
                self._tutorial_first_run_stage='timeline'
                self._close_command_sidebar(immediate=True)
                QTimer.singleShot(120, self._open_timeline)
                QTimer.singleShot(260, lambda: self._start_context_tutorial(first_run=True))
                return
            if stage == 'timeline':
                self._tutorial_first_run_stage='after_timeline'
                self.pages.setCurrentIndex(2)
                self.command_table.set_map(self._current_map)
                self.timeline_panel.set_map(self._current_map)
                QTimer.singleShot(80, lambda: self._start_context_tutorial(first_run=True))
                return
            if stage == 'after_timeline':
                self._tutorial_first_run=False
                self._tutorial_first_run_stage='done'
                self.visual_settings["onboarding_seen"] = True
                self.settings.set_visual_settings(self.visual_settings)
                QTimer.singleShot(120, self._finish_tutorial_demo)
                return

        # Tutorial contextual normal ou conclusão do primeiro uso.
        if getattr(self, '_context_tutorial', None):
            current=getattr(self, '_context_tutorial', None)
            self._context_tutorial=None
            if current:
                current.close()
    def _finish_tutorial_demo(self) -> None:
        demo=self._current_map
        if demo is None: return
        hotkey,ok=QInputDialog.getText(self,'Escolha a tecla da demonstração','Escolha uma tecla ou combinação para iniciar/parar esta automação.\nEx.: F6, = ou CTRL+F6.',text=demo.hotkey or '=')
        if ok and hotkey.strip(): demo.hotkey=hotkey.strip().upper()
        self.project_manager.save_map(demo); self._refresh_map_config_labels(); self._register_all_hotkeys(); self.pages.setCurrentIndex(2)
        QTimer.singleShot(250,lambda:self._run_map_via_hotkey(demo))

    def _update_branding(self) -> None:
        """Atualiza o ícone da janela e a marca AS conforme o tema."""
        dark = bool(getattr(self, "_dark_theme", False))
        try:
            self.setWindowIcon(self._brand_icon_dark if dark else self._brand_icon_light)
        except Exception:
            pass
        if hasattr(self, "brand_logo_label"):
            pix = _load_brand_pixmap(dark, 27)
            if pix.isNull():
                self.brand_logo_label.setPixmap(QPixmap())
                self.brand_logo_label.setText('AS')
            else:
                self.brand_logo_label.setText('')
                self.brand_logo_label.setPixmap(pix)

    def _build_status_bar(self) -> None:
        self.status_bar = QStatusBar()
        self.status_bar.setSizeGripEnabled(False)
        self.status_bar.setFixedHeight(26)
        self.status_bar.setContentsMargins(6, 0, 6, 0)
        self.setStatusBar(self.status_bar)
        self._update_status_label(State.IDLE)
        self.status_bar.showMessage(f"Backend de execução: {self.input_backend_name}", 5000)

    def _connect_bridge(self) -> None:
        self.bridge.state_changed.connect(lambda prev, new: self._update_status_label(new))
        self.bridge.event_fired.connect(self._on_engine_event)
        self.bridge.progress_changed.connect(self._on_engine_progress)
        self.bridge.error_occurred.connect(self._on_engine_error)
        self.bridge.finished.connect(self._on_engine_finished)
        self.bridge.chain_requested.connect(self._on_chain_requested)

    def _open_execution_monitor(self) -> None:
        self._update_execution_monitor()
        self.pages.setCurrentIndex(5)

    def _update_execution_monitor(self) -> None:
        state=self.state.state
        self.exec_state_label.setText(f"Estado: {state.value if hasattr(state, 'value') else state}")
        running=self.engine._current_map
        self.exec_map_label.setText(f"Automação: {running.name if running else '—'}")
        self.exec_chain_label.setText(f"Próxima automação: {running.next_map if running and running.next_map else '—'}")

    def _on_engine_progress(self, current: float, total: float) -> None:
        # O motor pode produzir milhares de eventos por segundo. Guardamos
        # apenas o ultimo progresso e a GUI o aplica no proximo ciclo de 40 ms.
        self._pending_progress = (current, total)

    def _flush_ui_updates(self) -> None:
        """Consolida atualizacoes de alta frequencia sem sobrecarregar a GUI."""
        if self._pending_progress is not None and not self.isMinimized():
            current, total = self._pending_progress
            self._pending_progress = None
            self._update_execution_monitor()
            pct = 0 if total <= 0 else max(0, min(1000, int((current / total) * 1000)))
            self.exec_progress.setValue(pct)
            self.exec_progress.setFormat(f"{current:.2f} s / {total:.2f} s   ({pct/10:.1f}%)")
        if self._pending_mouse_event is not None:
            event = self._pending_mouse_event
            self._pending_mouse_event = None
            self._apply_engine_event_visuals(event)

    def _apply_engine_event_visuals(self, event: Event) -> None:
        if hasattr(self, 'exec_event_label'):
            self.exec_event_label.setText(f"Último evento: [{event.time:.2f}s] {event.kind.value} {event.target}")
            if not self.isMinimized():
                self._update_execution_monitor()
        self.visualizer_panel.apply_event(event)
        self._feed_overlays_from_event(event)
        if not self.isMinimized():
            self.timeline_panel.set_playhead(event.time)

    def _on_engine_finished(self) -> None:
        self.status_bar.showMessage("Execução finalizada.", 3000)
        self._update_execution_monitor()
        if hasattr(self, 'exec_progress') and self.engine._current_map:
            self.exec_progress.setValue(1000)
        # Item 7/22: parado = sem playhead na timeline (nada "ativo agora").
        self.timeline_panel.set_playhead(None)

    def _on_chain_requested(self, next_name: str) -> None:
        """Inicia a próxima automação somente após término natural da anterior."""
        next_map = self.project_manager.maps.get(next_name)
        if next_map is None:
            self.status_bar.showMessage(f"Encadeamento ignorado: automação '{next_name}' não existe.", 5000)
            return
        if not next_map.commands:
            self.status_bar.showMessage(f"Encadeamento ignorado: automação '{next_name}' está vazia.", 5000)
            return
        errors = next_map.validate()
        if errors:
            self.status_bar.showMessage(f"Encadeamento ignorado: automação '{next_name}' é inválida.", 5000)
            return
        try:
            self._current_map = next_map
            self.command_table.set_map(next_map)
            self.timeline_panel.set_map(next_map)
            self.history.prime(next_map)
            self.editor_map_title.setText(next_map.name)
            self._refresh_map_config_labels()
            self.engine.run(next_map)
            self._update_execution_monitor()
        except Exception as exc:
            self._show_detailed_error("Erro ao iniciar automação encadeada", exc)

    def _connect_capture_bridge(self) -> None:
        # Item 12: o teclado/mouse virtual também reage ao input REAL do
        # usuário, não só ao que a automação injeta -- útil para
        # conferir visualmente o que está sendo pressionado a qualquer
        # momento, mesmo sem nenhum mapa em execução.
        self.capture_bridge.key_changed.connect(self._on_real_key)
        self.capture_bridge.mouse_button_changed.connect(self._on_real_mouse_button)
        self.capture_bridge.mouse_scrolled.connect(self._on_real_mouse_scroll)
        self.capture_bridge.mouse_moved.connect(self._on_real_mouse_move)
        self._last_mouse_pos = None

    # ---- Mapas: CRUD ----------------------------------------------------

    def _reload_map_list(self) -> None:
        self.project_manager.load_all()
        self.ativacao.sincronizar()  # 25.8: mapas novos nascem com o estado certo e a migração da primeira abertura é gravada
        self.map_list.clear()
        for name in sorted(self.project_manager.maps.keys()):
            self.map_list.addItem(QListWidgetItem(name))
        # A dica de cada item (a frase de abrir + o estado da ativação) e os papéis de dados do estado e do conflito.
        self.ativacao.decorar_lista('Abrir esta automação para editar, visualizar a timeline ou executar.')
        self._filter_map_list(getattr(self, 'map_search', None).text() if hasattr(self, 'map_search') else '')
        # Não abrir automaticamente um mapa: primeiro a pessoa escolhe o que deseja usar.
        self.map_list.clearSelection()
        self.map_list.setCurrentRow(-1)
        self._update_map_list_info()
        QTimer.singleShot(0, self._notify_load_errors)

    def _notify_load_errors(self) -> None:
        """Avisa (uma vez por problema) sobre automações salvas que não puderam ser lidas."""
        errors = list(getattr(self.project_manager, 'load_errors', []) or [])
        if not hasattr(self, '_shown_load_errors'):
            self._shown_load_errors = set()
        fresh = [item for item in errors if item not in self._shown_load_errors]
        if not fresh:
            return
        self._shown_load_errors.update(fresh)
        details = '\n\n'.join(fresh[:5]) + (f'\n\n… e mais {len(fresh) - 5}.' if len(fresh) > 5 else '')
        QMessageBox.warning(
            self, 'Automações que não puderam ser carregadas',
            'Estas automações estão no banco, mas não puderam ser lidas e não aparecem na lista. '
            'Nada foi apagado.\n\n' + details + '\n\nDetalhes em logs\\AutomationStudio.log.')

    def _filter_map_list(self, text: str) -> None:
        query=(text or '').strip().casefold()
        visible=0
        for row in range(self.map_list.count()):
            item=self.map_list.item(row)
            show=(not query) or query in item.text().casefold()
            item.setHidden(not show)
            if show: visible += 1
        self._update_map_list_info(visible)

    def _update_map_list_info(self, visible: int | None = None) -> None:
        total=self.map_list.count() if hasattr(self, 'map_list') else 0
        if visible is None:
            visible=sum(1 for row in range(total) if not self.map_list.item(row).isHidden())
        if total == 0:
            self.map_list_info.setText('Nenhuma automação salva ainda. Crie uma nova para começar.')
        elif visible == 0:
            self.map_list_info.setText('Nenhuma automação corresponde à pesquisa.')
        elif visible == total:
            self.map_list_info.setText(f'{total} automação(ões) disponível(is)')
        else:
            self.map_list_info.setText(f'{visible} de {total} automação(ões)')

    def _new_map(self) -> None:
        name, ok = QInputDialog.getText(self, "Novo mapa", "Nome do mapa:")
        if not ok or not name.strip():
            return
        if name in self.project_manager.maps:
            QMessageBox.warning(self, "Nome duplicado", "Já existe um mapa com esse nome.")
            return
        new_map = AutomationMap(name=name.strip(), hotkey="=", repeat_count=-1)
        self.project_manager.save_map(new_map)
        self._reload_map_list()
        self._select_map_by_name(new_map.name)
        self._register_all_hotkeys()

    def _delete_current_map(self) -> None:
        if not self._current_map:
            return
        confirm = QMessageBox.question(
            self, "Excluir mapa", f"Excluir o mapa '{self._current_map.name}'?"
        )
        if confirm == QMessageBox.Yes:
            self.project_manager.delete_map(self._current_map.name)
            self.ativacao.esquecer(self._current_map.name)  # 25.8: a preferência de ativação some junto com a automação
            self._current_map = None
            self.command_table.set_map(None)
            self.timeline_panel.set_map(None)
            self._reload_map_list()
            self.pages.setCurrentIndex(1)
            self._register_all_hotkeys()

    def _select_map_by_name(self, name: str) -> None:
        for i in range(self.map_list.count()):
            if self.map_list.item(i).text() == name:
                self.map_list.setCurrentRow(i)
                return

    def _on_map_selected(self,current,_previous) -> None:
        if current is None:
            self._current_map=None
            return
        self._current_map=self.project_manager.maps.get(current.text())
        if self._current_map:
            self.editor_map_title.setText(self._current_map.name)
            self.map_instruction.setText('Adicione ações na lista abaixo. Cada ação é uma coisa que o programa fará, na ordem em que você definir.')
            self.command_table.set_map(self._current_map)
            self.timeline_panel.set_map(self._current_map)
            self.history.prime(self._current_map)
            self._refresh_map_config_labels()
            if not getattr(self, '_tutorial_first_run', False):
                self.pages.setCurrentIndex(2)

    def _on_map_edited(self, label: str = "Alteração") -> None:
        # Comandos mudaram na tabela -> normaliza tipos antes de salvar.
        if not self._current_map:
            return
        if self._recording_backup_map is not None and not self.recorder.is_recording:
            # A primeira alteração manual após uma gravação finalizada
            # torna o backup obsoleto e ele é removido.
            self._discard_recording_backup()
        try:
            for c in self._current_map.commands:
                if not isinstance(c.type, InputType): c.type=InputType(str(c.type).split(".")[-1].lower())
                if not isinstance(c.action, ActionType): c.action=ActionType(str(c.action).split(".")[-1].lower())
            errors=self._current_map.validate()
            fatal=[e for e in errors if 'duração igual a 0' not in e]
            if fatal:
                QMessageBox.warning(self,'Comando inválido','Não foi possível salvar a automação:\n\n'+'\n'.join(fatal))
                return
            self.project_manager.save_map(self._current_map)
            self.timeline_panel.set_map(self._current_map)
            self.history.commit(self._current_map, label)
            self._update_history_actions()
        except Exception as exc:
            self._show_detailed_error('Erro ao salvar a automação',exc)

    def _on_timeline_edited(self) -> None:
        # Início/duração mudou por arrasto ou edição na timeline -> salva
        # e mantém a tabela (outra visão do mesmo mapa) sincronizada.
        if self._current_map and not self._restoring_history:
            self.project_manager.save_map(self._current_map)
            self.command_table.refresh()
            self.timeline_panel.refresh()
            self.history.commit(self._current_map, "Edição temporal")
            self._update_history_actions()

    def _update_history_actions(self) -> None:
        if hasattr(self,'act_undo'):
            can_undo = self.history.can_undo(self._current_map)
            can_redo = self.history.can_redo(self._current_map)
            self.act_undo.setEnabled(can_undo)
            self.act_redo.setEnabled(can_redo)
            undo_label = self.history.undo_label(self._current_map)
            redo_label = self.history.redo_label(self._current_map)
            self.act_undo.setText(f"↶ Desfazer: {undo_label}" if can_undo else "↶ Desfazer")
            self.act_redo.setText(f"↷ Refazer: {redo_label}" if can_redo else "↷ Refazer")

    def _restore_history_view(self) -> None:
        if not self._current_map: return
        self._restoring_history=True
        try:
            self.command_table.set_map(self._current_map)
            self.timeline_panel.set_map(self._current_map)
            self.timeline_panel.refresh()
            self.project_manager.save_map(self._current_map)
            self._refresh_map_config_labels()
            self._register_all_hotkeys()
        finally:
            self._restoring_history=False
            self._update_history_actions()

    def _undo_map(self) -> None:
        if self._current_map and self.history.undo(self._current_map):
            self._restore_history_view(); self.status_bar.showMessage('Alteração desfeita.', 1800)

    def _redo_map(self) -> None:
        if self._current_map and self.history.redo(self._current_map):
            self._restore_history_view(); self.status_bar.showMessage('Alteração refeita.', 1800)

    def _refresh_map_config_labels(self) -> None:
        self.ativacao.atualizar_painel()  # 25.8: a faixa de ativação mostra a automação aberta (ou se esconde sem nenhuma)
        if not self._current_map:
            return
        m = self._current_map
        self.hotkey_label.setText(self.ativacao.rotulo_da_tecla(m))  # "Tecla para iniciar/parar: =", + (desativada) etc.
        repeat_text = "∞" if m.repeat_count == -1 else str(m.repeat_count)
        self.repeat_label.setText(f"Repetição: {repeat_text}x")
        self.speed_label.setText(f"Velocidade: {int(m.speed * 100)}%")

    def _configure_current_map(self) -> None:
        if not self._current_map:
            return
        m = self._current_map

        trigger_options = [
            "Teclado — digitar uma tecla ou combinação",
            "Mouse — botão esquerdo",
            "Mouse — botão direito",
            "Mouse — botão do meio",
            "Mouse — botão lateral 1 (X1)",
            "Mouse — botão lateral 2 (X2)",
        ]
        current = m.hotkey or "="
        if current.upper().startswith("MOUSE_"):
            mapping = {
                "MOUSE_LEFT":"Mouse — botão esquerdo", "MOUSE_RIGHT":"Mouse — botão direito",
                "MOUSE_MIDDLE":"Mouse — botão do meio", "MOUSE_X1":"Mouse — botão lateral 1 (X1)",
                "MOUSE_X2":"Mouse — botão lateral 2 (X2)"
            }
            current_label = mapping.get(current.upper(), trigger_options[0])
        else:
            current_label = trigger_options[0]
        idx = next((i for i,x in enumerate(trigger_options) if x == current_label), 0)
        choice, ok = QInputDialog.getItem(
            self, "Como iniciar/parar esta automação",
            "Escolha o que deve iniciar e, se pressionado novamente, parar esta automação:",
            trigger_options, idx, False
        )
        if not ok:
            return

        if choice == trigger_options[0]:
            hotkey, ok = QInputDialog.getText(
                self, "Tecla para iniciar/parar",
                "Digite uma tecla ou combinação. Exemplo: =, F6 ou CTRL+F6.",
                text=m.hotkey if m.hotkey and not m.hotkey.upper().startswith("MOUSE_") else "="
            )
            if not ok:
                return
            new_hotkey = hotkey.strip() or "="
        else:
            mouse_map = {
                trigger_options[1]:"MOUSE_LEFT", trigger_options[2]:"MOUSE_RIGHT",
                trigger_options[3]:"MOUSE_MIDDLE", trigger_options[4]:"MOUSE_X1",
                trigger_options[5]:"MOUSE_X2"
            }
            new_hotkey = mouse_map[choice]

        # 25.8: uma tecla que não existe, ou que já é de outra automação ativa ou de um atalho de controle, é recusada
        # (com aviso) e a tecla anterior fica. As demais perguntas seguem, para não perder o resto do que a pessoa configura.
        self.ativacao.mudar_tecla(m, new_hotkey)

        repeat, ok = QInputDialog.getInt(
            self, "Repetição", "Quantas vezes a automação deve repetir? (-1 = infinito):",
            m.repeat_count, -1, 9999
        )
        if ok:
            m.repeat_count = repeat

        interval, ok = QInputDialog.getDouble(
            self, "Intervalo entre repetições", "Espera entre uma repetição e a próxima (segundos):",
            float(m.repeat_interval), 0.0, 3600.0, 3
        )
        if ok:
            m.repeat_interval = interval

        speed_pct, ok = QInputDialog.getInt(
            self, "Velocidade", "Velocidade da automação em porcentagem (25-400):",
            int(m.speed * 100), 25, 400
        )
        if ok:
            m.speed = speed_pct / 100.0

        names = ["Nenhuma"] + [name for name in sorted(self.project_manager.maps) if name != m.name]
        current_next = m.next_map if m.next_map in names else "Nenhuma"
        next_name, ok = QInputDialog.getItem(
            self, "Próxima automação",
            "Opcional: ao terminar normalmente, iniciar outra automação.",
            names, names.index(current_next), False
        )
        if ok:
            m.next_map = None if next_name == "Nenhuma" else next_name

        conflict, ok = QInputDialog.getItem(
            self, "Quando outro mapa for acionado",
            "Escolha o comportamento:",
            ["Substituir a automação atual", "Bloquear o novo acionamento"],
            0 if m.conflict_behavior == "replace" else 1, False
        )
        if ok:
            m.conflict_behavior = "replace" if conflict.startswith("Substituir") else "block"

        self.project_manager.save_map(m)
        self._refresh_map_config_labels()
        self._register_all_hotkeys()

    # ---- Atalhos globais (Fase 5, item 10/11) ----------------------------

    def _register_all_hotkeys(self) -> None:
        """Reconstrói TODOS os atalhos globais a partir do zero: um por
        mapa ATIVO (item 8/28; 25.8) + os de controle (item 10/11: pausar/
        continuar/emergência). Chamado sempre que algo que afeta atalhos
        muda -- mapa criado/importado/excluído, atalho de mapa editado,
        estado de ativação mudado, ou atalhos de controle reconfigurados.

        Quem decide o que entra, e avisa dos conflitos, é `self.ativacao`
        (ativacao.py / ativacao_ui.py): os atalhos de controle têm
        prioridade sobre os de mapa, e um mapa desativado não registra tecla.

        Roda de novo do zero (em vez de só diff'ar o que mudou) porque é
        simples, barato (poucas dezenas de atalhos no máximo) e evita
        qualquer atalho "fantasma" esquecido de uma configuração antiga.
        """
        if not self.hotkey_manager.available:
            return
        self.ativacao.registrar()

    def _open_settings(self) -> None:
        """Abre Configurações no mesmo painel lateral do editor de comandos."""
        if not self._current_map:
            self.status_bar.showMessage("Selecione uma automação primeiro.", 3000)
            self.pages.setCurrentIndex(1)
            return
        self.pages.setCurrentIndex(2)
        if self.command_sidebar.isVisible() and getattr(self, "_command_sidebar_mode", None) == "settings":
            return
        if self.command_sidebar.isVisible():
            self._pending_sidebar_request = ("__SETTINGS__", -1, "settings")
            self._animate_command_sidebar(False)
            return
        self._show_settings_sidebar()

    def _show_settings_sidebar(self) -> None:
        panel = AppSettingsDialog(self, self.command_sidebar_host, embedded=True)
        panel.setWindowFlags(Qt.Widget)
        self.command_sidebar_host_layout.addWidget(panel)
        self._command_sidebar_dialog = panel
        self._command_sidebar_mode = "settings"
        self.command_sidebar_title.setText('Configurações')
        # O botão de salvar/cancelar fica sempre visível fora da rolagem,
        # exatamente como no editor de comandos.
        try:
            panel.layout().removeWidget(panel.buttons)
            panel.buttons.hide()
        except Exception:
            pass
        while self.command_sidebar_footer_layout.count():
            item=self.command_sidebar_footer_layout.takeAt(0); w=item.widget()
            if w: w.deleteLater()
        self.command_sidebar_footer_layout.addWidget(panel.buttons)
        panel.buttons.show()
        self.command_sidebar_footer.show()
        panel.saved.connect(self._on_settings_sidebar_saved)
        panel.cancelled.connect(self._close_command_sidebar)
        self.command_sidebar.show()
        self._animate_command_sidebar(True)

    def _open_execution_settings_sidebar(self) -> None:
        """Abre os tempos em uma camada interna sobre a sidebar de configurações."""
        if self._execution_sidebar is not None and self._execution_sidebar.isVisible():
            return
        panel=ExecutionSettingsSidebar(self, self.command_sidebar)
        panel.setGeometry(self.command_sidebar.rect())
        panel.setMinimumWidth(0); panel.setMinimumHeight(0)
        panel.saved.connect(self._close_execution_settings_sidebar)
        panel.cancelled.connect(self._close_execution_settings_sidebar)
        self._execution_sidebar=panel
        panel.show(); panel.raise_(); panel.setFocus()

    def _close_execution_settings_sidebar(self) -> None:
        panel=getattr(self,'_execution_sidebar',None)
        if panel is not None:
            panel.hide(); panel.deleteLater(); self._execution_sidebar=None
        if self.command_sidebar.isVisible() and self._command_sidebar_dialog is not None:
            self._command_sidebar_dialog.setFocus()

    def _on_settings_sidebar_saved(self) -> None:
        self.status_bar.showMessage("Configurações salvas.", 3000)
        self._close_command_sidebar()

    def _configure_control_hotkeys(self) -> None:
        dialog = HotkeySettingsDialog(self.settings.get_control_hotkeys(), self)
        if dialog.exec() == QDialog.Accepted:
            self.settings.set_control_hotkeys(dialog.values())
            self._register_all_hotkeys()

    def _on_hotkey_triggered(self, action_id: str) -> None:
        # Já estamos de volta na GUI thread aqui (Signal/slot do Qt) --
        # seguro tocar widgets, StateManager, ExecutionEngine, etc.
        if action_id.startswith("map:"):
            if not self.ativacao.acao_permitida(action_id):
                return  # 25.8: a tecla de uma automação desativada não a executa (mesmo que o disparo já estivesse na fila)
            automation_map = self.project_manager.maps.get(action_id[len("map:"):])
            if automation_map is not None:
                self._run_map_via_hotkey(automation_map)
        elif action_id == "control:emergency":
            self._on_emergency()
        elif action_id == "control:pause":
            self.controle.pausar()  # F9 (achado 2.11: o disparo era registrado e sumia)
        elif action_id == "control:resume":
            self.controle.retomar()  # F10
        elif action_id == "record:toggle":
            self._toggle_recording()
        elif action_id == "record:cancel":
            self._cancel_recording()

    def _run_map_via_hotkey(self, automation_map: AutomationMap) -> None:
        # A tecla de iniciação também é a tecla de PARADA da mesma automação.
        # Isso torna repetições infinitas (-1) sempre interrompíveis: pressionar
        # '=' novamente nunca inicia uma segunda thread da mesma automação.
        if self.state.state == State.RECORDING:
            return
        if self.state.state in (State.RUNNING, State.PAUSED):
            running_map = self.engine._current_map
            same_map = (running_map is automation_map) or (
                running_map is not None and running_map.name == automation_map.name
            )
            if same_map:
                self.engine.stop(wait=True)
                self.status_bar.showMessage(
                    f"Automação '{automation_map.name}' parada pela tecla de iniciação.", 3000
                )
                return
            # Outro mapa acionado: substitui o mapa atual, salvo se o mapa novo
            # estiver configurado para bloquear a substituição.
            if automation_map.conflict_behavior == "block":
                return
            self.engine.stop(wait=True)

        if not automation_map.commands:
            self.status_bar.showMessage(f"Automação '{automation_map.name}' está vazia.", 4000)
            return
        errors = automation_map.validate()
        if errors:
            self.status_bar.showMessage(
                f"Atalho ignorado: mapa '{automation_map.name}' inválido.", 5000
            )
            return
        try:
            self.engine.run(automation_map)
        except (ValueError, InvalidStateTransition):
            return
        if self._current_map is not automation_map:
            self._select_map_by_name(automation_map.name)

    # ---- Import / Export --------------------------------------------

    def _save_current_map(self) -> None:
        if self._current_map:
            self.project_manager.save_map(self._current_map)
            if self._recording_backup_map is not None and not self.recorder.is_recording:
                self._discard_recording_backup()
            self.status_bar.showMessage(f"Mapa '{self._current_map.name}' salvo.", 3000)

    def _import_external_from_chooser(self) -> None:
        """Abre um mapa externo sem exigir que o usuário exporte novamente.

        Aceita JSON exportado e bancos SQLite de outra instalação/V19.
        O mapa escolhido é copiado para o banco interno atual e aberto no editor.
        """
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Abrir mapa externo",
            "",
            "Mapas e bancos do Automation Studio (*.json *.db *.sqlite *.sqlite3);;Mapa JSON (*.json);;Banco SQLite (*.db *.sqlite *.sqlite3);;Todos os arquivos (*)",
        )
        if not path:
            return
        try:
            source = Path(path)
            imported: list[AutomationMap] = []
            if source.suffix.lower() == '.json':
                imported = [map_from_json(source.read_text(encoding='utf-8'))]
            elif source.suffix.lower() in ('.db', '.sqlite', '.sqlite3'):
                imported = self._read_external_sqlite_maps(source)
            else:
                # Tenta JSON primeiro para arquivos sem extensão conhecida.
                try:
                    imported = [map_from_json(source.read_text(encoding='utf-8'))]
                except Exception:
                    imported = self._read_external_sqlite_maps(source)

            if not imported:
                raise ValueError('Nenhuma automação compatível foi encontrada no arquivo selecionado.')

            chosen = imported[0]
            if len(imported) > 1:
                names = [m.name for m in imported]
                selected, ok = QInputDialog.getItem(
                    self, 'Escolher automação externa',
                    'O arquivo contém várias automações. Qual deseja importar?',
                    names, 0, False,
                )
                if not ok:
                    return
                chosen = next(m for m in imported if m.name == selected)

            # Evita substituir silenciosamente um mapa existente.
            if chosen.name in self.project_manager.maps:
                base = chosen.name
                n = 2
                while f'{base} ({n})' in self.project_manager.maps:
                    n += 1
                answer = QMessageBox.question(
                    self, 'Mapa já existente',
                    f'A automação “{base}” já existe neste programa.\n\n'
                    f'Escolha “Sim” para substituir o mapa existente ou “Não” para importar como “{base} ({n})”.',
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                    QMessageBox.No,
                )
                if answer == QMessageBox.Cancel:
                    return
                if answer == QMessageBox.No:
                    chosen.name = f'{base} ({n})'
                else:
                    self.project_manager.delete_map(base)

            self.project_manager.save_map(chosen)
            self._reload_map_list()
            self._select_map_by_name(chosen.name)
            self._register_all_hotkeys()
            self.status_bar.showMessage(f'Automação externa “{chosen.name}” importada.', 5000)
        except Exception as exc:
            self._show_detailed_error('Erro ao abrir mapa externo', exc)

    @staticmethod
    def _read_external_sqlite_maps(path: Path) -> list[AutomationMap]:
        """Lê somente a tabela de mapas, sem modificar o banco externo."""
        con = sqlite3.connect(f'file:{path.resolve().as_posix()}?mode=ro', uri=True, timeout=3)
        try:
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            if 'maps' not in tables:
                raise ValueError('O banco selecionado não possui a tabela de automações “maps”.')
            rows = con.execute('SELECT name,payload FROM maps ORDER BY name COLLATE NOCASE').fetchall()
            result: list[AutomationMap] = []
            for name, payload in rows:
                try:
                    m = map_from_json(payload)
                    if not m.name:
                        m.name = str(name)
                    result.append(m)
                except Exception:
                    continue
            return result
        finally:
            con.close()

    def _import_map(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Importar automação externa", "",
            "Automação (*.json *.db *.sqlite *.sqlite3);;JSON (*.json);;Banco SQLite (*.db *.sqlite *.sqlite3);;Todos os arquivos (*)"
        )
        if not path:
            return
        try:
            src = Path(path)
            if src.suffix.lower() == '.json':
                imported = map_from_json(src.read_text(encoding='utf-8'))
                base = imported.name
                if base in self.project_manager.maps:
                    answer = QMessageBox.question(
                        self, "Mapa já existe",
                        f'O mapa "{base}" já existe. Deseja substituir o mapa atual pelo arquivo externo?\n\n'
                        'Sim = substituir\nNão = importar com outro nome',
                        QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.No)
                    if answer == QMessageBox.Cancel:
                        return
                    if answer == QMessageBox.No:
                        n = 2
                        while f"{base} ({n})" in self.project_manager.maps: n += 1
                        imported.name = f"{base} ({n})"
                self.project_manager.save_map(imported)
            else:
                # Banco externo é lido em somente leitura; nenhum arquivo
                # do projeto atual é alterado até o usuário confirmar a importação.
                uri = f"file:{src.resolve().as_posix()}?mode=ro"
                con = sqlite3.connect(uri, uri=True)
                rows = con.execute("SELECT name,payload FROM maps ORDER BY name COLLATE NOCASE").fetchall()
                con.close()
                if not rows:
                    raise ValueError("O banco externo não contém mapas reconhecíveis.")
                choices = [name for name, _ in rows]
                selected, ok = QInputDialog.getItem(self, "Escolher automação", "Qual automação deseja importar?", choices, 0, False)
                if not ok: return
                payload = dict(rows)[selected]
                imported = map_from_json(payload)
                base = imported.name
                if base in self.project_manager.maps:
                    n = 2
                    while f"{base} ({n})" in self.project_manager.maps: n += 1
                    imported.name = f"{base} ({n})"
                self.project_manager.save_map(imported)
            self._reload_map_list()
            self._select_map_by_name(imported.name)
            self._register_all_hotkeys()
        except Exception as exc:
            self._show_detailed_error("Erro ao importar automação externa", exc)

    def _export_current_map(self) -> None:
        if not self._current_map:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar mapa", f"{self._current_map.name}.json", "JSON (*.json)"
        )
        if path:
            self.project_manager.export_map(self._current_map.name, path)

    # ---- Ferramentas do editor V23 --------------------------------------

    def _validate_current_map(self) -> None:
        if not self._current_map:
            return
        errors=self._current_map.validate_structure()
        if errors:
            QMessageBox.warning(self,'Validação da automação',f'{len(errors)} problema(s) encontrado(s):\n\n'+'\n'.join(f'• {e}' for e in errors))
            return
        QMessageBox.information(self,'Validação da automação','✓ Nenhum problema estrutural encontrado.\n\nIDs, tipos, ações, grupos e tempos estão válidos.')

    def _test_selected_commands(self, command_ids) -> None:
        if not self._current_map:
            return
        ids=set(command_ids or [])
        if not ids:
            return
        selected=self._current_map.get_commands_by_ids(ids)
        if not selected:
            return
        if self.state.state in (State.RUNNING, State.PAUSED):
            QMessageBox.information(self,'Teste de comandos','Pare a automação em execução antes de testar uma seleção.')
            return
        test_map=AutomationMap(name=f'__teste__ {self._current_map.name}', hotkey=None, repeat_count=1, speed=self._current_map.speed)
        base=min(float(c.start) for c in selected)
        test_map.commands=[copy.deepcopy(c) for c in selected]
        for c in test_map.commands:
            c.id=_next_id(); c.start=max(0.0,float(c.start)-base)
        # O teste é isolado do mapa persistido e sempre começa em t=0.
        test_map.reflow_timeline(preserve_gaps=True)
        errors=test_map.validate()
        if errors:
            QMessageBox.warning(self,'Teste de comandos','A seleção não pode ser executada:\n\n'+'\n'.join(errors))
            return
        try:
            self.engine.run(test_map)
            self.status_bar.showMessage(f'Testando {len(test_map.commands)} comando(s) selecionado(s).',3000)
        except Exception as exc:
            self._show_detailed_error('Erro ao testar comandos selecionados',exc)

    def _preview_automation(self, automation_map=None) -> None:
        m=automation_map or self._current_map
        if not m:
            return
        rows=m.timeline_rows()
        dialog=QDialog(self); dialog.setWindowTitle(f'Pré-visualização — {m.name}'); dialog.resize(680,430)
        layout=QVBoxLayout(dialog)
        title=QLabel(f'<b>{m.name}</b><br>Pré-visualização — nenhum teclado ou mouse será enviado.')
        layout.addWidget(title)
        table=QTableWidget(len(rows),5); table.setHorizontalHeaderLabels(['#','Início','Duração','Fim','Comando'])
        table.setEditTriggers(QAbstractItemView.NoEditTriggers); table.horizontalHeader().setStretchLastSection(True)
        for r,row in enumerate(rows):
            cmd=next((c for c in m.commands if c.id==row['id']),None)
            vals=[str(r+1),f"{row['start']:.2f} s",f"{row['duration']:.2f} s",f"{row['end']:.2f} s",(cmd.description or cmd.target or cmd.type.value) if cmd else row['id']]
            for c,v in enumerate(vals): table.setItem(r,c,QTableWidgetItem(str(v)))
        layout.addWidget(table,1)
        total=m.total_duration(); layout.addWidget(QLabel(f'Duração total prevista: <b>{total:.2f} s</b>'))
        buttons=QHBoxLayout(); buttons.addStretch(); close=QPushButton('Fechar'); close.clicked.connect(dialog.accept); buttons.addWidget(close); layout.addLayout(buttons)
        dialog.exec()

    # ---- Execução --------------------------------------------------------

    def _run_current_map(self) -> None:
        if not self._current_map:
            return
        if not self._current_map.commands:
            QMessageBox.information(self, "Automação vazia", "Esta automação ainda não possui comandos. Adicione pelo menos uma ação antes de executar.")
            return
        errors = self._current_map.validate()
        if errors:
            QMessageBox.warning(self, "Não é possível executar", "\n".join(errors))
            return
        try:
            self.engine.run(self._current_map)
        except (ValueError, InvalidStateTransition) as exc:
            QMessageBox.warning(self, "Não é possível executar", str(exc))

    def _on_emergency(self) -> None:
        # Item 11/25: o botão de emergência interrompe TUDO, não só a
        # execução -- incluindo uma gravação em andamento, sem tentar
        # aproveitar o que já foi capturado.
        self.engine.emergency_stop()
        if self.recorder.is_recording:
            self._cancel_recording()

    # ---- Gravação ----------------------------------------------------------

    def _create_recording_backup(self, automation_map: AutomationMap) -> None:
        self._recording_backup_map = copy.deepcopy(automation_map)
        self._recording_backup_path = None

    def _discard_recording_backup(self) -> None:
        self._recording_backup_path = None
        self._recording_backup_map = None

    def _toggle_recording(self) -> None:
        """Um único comando: iniciar quando parado; finalizar quando gravando."""
        if not self.recorder.is_recording:
            self._start_recording()
        else:
            self._finalize_recording()

    def _start_recording(self) -> None:
        if not self._current_map:
            QMessageBox.warning(self, 'Gravar automação', 'Selecione (ou crie) uma automação antes de gravar.')
            return
        if self.state.state != State.IDLE:
            QMessageBox.warning(self, 'Não é possível gravar', 'Finalize ou pare a execução atual antes de iniciar uma gravação.')
            return
        try:
            self._create_recording_backup(self._current_map)
            self._recording_original_filters = self.recorder.filters
            controls = self.settings.get_control_hotkeys()
            ignored = set(self.recorder.filters.ignored_keys)
            for key in (controls.get("record_toggle"), controls.get("record_cancel")):
                if key: ignored.add(key.upper())
            self.recorder.filters = replace(self.recorder.filters, ignored_keys=frozenset(ignored))
            self.recorder.start()
        except Exception as exc:
            if self._recording_original_filters is not None:
                self.recorder.filters = self._recording_original_filters
                self._recording_original_filters = None
            self._discard_recording_backup()
            self._show_detailed_error('Erro ao iniciar a gravação', exc)
            return
        self._recording_target_map = self._current_map
        self._recording_status_timer.start()
        self.btn_record.setText('✓ Finalizar gravação')
        self.btn_cancel_record.setEnabled(True)
        self._last_recording_preview_signature = None
        self.command_table.set_recording_preview([])
        self.status_bar.showMessage('🔴 GRAVANDO — os comandos aparecerão na tabela em tempo real.')

    def _update_recording_status(self) -> None:
        if not self.recorder.is_recording:
            return
        commands = self.recorder.snapshot_commands()
        signature = tuple((c.id, c.start, c.duration, c.type.value if hasattr(c.type,'value') else str(c.type)) for c in commands)
        if getattr(self, '_last_recording_preview_signature', None) != signature:
            self.command_table.set_recording_preview(commands)
            self._last_recording_preview_signature = signature
        elapsed = self.recorder._elapsed()
        state = 'GRAVANDO'
        self.status_bar.showMessage(f'🔴 {state} — {self.recorder.event_count} eventos capturados • {len(commands)} blocos/comandos visíveis • {elapsed:.1f}s')

    def _preview_recording(self) -> None:
        """Executa somente a última captura, sem alterar ou salvar o mapa atual."""
        if not self._last_recorded_commands:
            self.status_bar.showMessage("Nenhuma gravação disponível para pré-visualização.", 3000)
            return
        if self.engine.is_running():
            self.status_bar.showMessage("Finalize a execução atual antes de pré-visualizar.", 3000)
            return
        preview=AutomationMap(name="Pré-visualização da gravação", commands=copy.deepcopy(self._last_recorded_commands), repeat_count=1, speed=1.0)
        try:
            self.engine.run(preview)
            self.status_bar.showMessage("▶ Pré-visualizando a última gravação — o mapa não foi alterado.", 4000)
        except Exception as exc:
            self._show_detailed_error("Não foi possível pré-visualizar a gravação", exc)

    def _finalize_recording(self) -> None:
        if not self.recorder.is_recording:
            return
        commands = self.recorder.stop()
        target_map = self._recording_target_map
        self._recording_status_timer.stop()
        self._recording_target_map = None
        if self._recording_original_filters is not None:
            self.recorder.filters = self._recording_original_filters
            self._recording_original_filters = None
        self.btn_record.setText('● Iniciar gravação')
        self.btn_cancel_record.setEnabled(False)
        self._last_recording_preview_signature = None
        if target_map is not None:
            target_map.commands.extend(commands)
            try:
                self.project_manager.save_map(target_map)
            except Exception as exc:
                self._show_detailed_error('Erro ao salvar gravação', exc)
                return
            self.command_table.set_map(target_map)
            self.timeline_panel.set_map(target_map)
            self._select_map_by_name(target_map.name)
        self.status_bar.showMessage(f'Gravação finalizada: {len(commands)} comando(s) adicionados ao final do mapa. O backup será descartado na próxima alteração manual.')

    def _cancel_recording(self) -> None:
        if not self.recorder.is_recording:
            return
        self.recorder.cancel()
        target_map = self._recording_target_map
        backup = self._recording_backup_map
        self._recording_status_timer.stop()
        self._recording_target_map = None
        if self._recording_original_filters is not None:
            self.recorder.filters = self._recording_original_filters
            self._recording_original_filters = None
        self.btn_record.setText('● Iniciar gravação')
        self.btn_cancel_record.setEnabled(False)
        if target_map is not None and backup is not None:
            restored = copy.deepcopy(backup)
            self.project_manager.maps[restored.name] = restored
            try:
                self.project_manager.save_map(restored)
            except Exception as exc:
                self._show_detailed_error('Erro ao restaurar o backup da gravação', exc)
                return
            self._current_map = restored
            self.command_table.set_map(restored)
            self.timeline_panel.set_map(restored)
            self._refresh_map_config_labels()
            self._register_all_hotkeys()
        self._discard_recording_backup()
        self.status_bar.showMessage('Gravação cancelada. O mapa foi restaurado para a versão anterior à gravação.', 5000)

    def _on_engine_event(self, event: Event) -> None:
        # Movimentos de mouse podem conter milhares de pontos. Eles continuam
        # sendo executados integralmente pelo motor, mas a interface só precisa
        # desenhar o ponto mais recente por ciclo de GUI. Teclas/cliques seguem
        # imediatamente para preservar feedback visual.
        if event.kind == EventKind.MOUSE_MOVE:
            self._pending_mouse_event = event
            return
        self.status_bar.showMessage(f"[{event.time:.2f}s] {event.kind.value} {event.target}")
        self._apply_engine_event_visuals(event)

    def _feed_overlays_from_event(self, event: Event) -> None:

        if self.keyboard_overlay is not None:
            if event.kind == EventKind.KEY_DOWN:
                self.keyboard_overlay.keyboard.press(event.target)
            elif event.kind == EventKind.KEY_UP:
                self.keyboard_overlay.keyboard.release(event.target)
        if self.mouse_overlay is not None:
            if event.kind == EventKind.MOUSE_DOWN:
                self.mouse_overlay.mouse.press(event.target)
            elif event.kind == EventKind.MOUSE_UP:
                self.mouse_overlay.mouse.release(event.target)
            elif event.kind == EventKind.MOUSE_SCROLL:
                self.mouse_overlay.mouse.scroll(event.scroll_dx, event.scroll_dy)
            elif event.kind == EventKind.MOUSE_MOVE:
                if event.relative:
                    dx, dy = event.x or 0, event.y or 0
                else:
                    # Para posição absoluta, compare com a posição atual do cursor.
                    try:
                        pos=QCursor.pos()
                        dx,dy=(event.x or pos.x())-pos.x(),(event.y or pos.y())-pos.y()
                    except Exception:
                        dx,dy=0,0
                self.mouse_overlay.mouse.move_direction(dx, dy)

    def _show_detailed_error(self, title: str, exc: Exception) -> None:
        details=traceback.format_exc()
        if details.strip() == 'NoneType: None':
            details=''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        try:
            log_dir=Path(self.project_manager.project_dir)/'logs'; log_dir.mkdir(parents=True,exist_ok=True)
            (log_dir/'AutomationStudio.log').write_text(details,encoding='utf-8')
        except Exception:
            pass
        # Erros de execução permanecem dentro dos limites da janela principal:
        # nenhum QMessageBox modal pode ficar escondido atrás do modo sempre-no-topo.
        if hasattr(self, 'error_notice'):
            self.error_notice.show_error(title, str(exc) or type(exc).__name__, details)
        else:
            # Fallback apenas durante falha muito precoce da construção da UI.
            box=QMessageBox(self); box.setIcon(QMessageBox.Critical); box.setWindowTitle(title); box.setText(str(exc) or type(exc).__name__); box.setDetailedText(details); box.exec()

    def _position_error_notice(self) -> None:
        if not hasattr(self, 'error_notice'): return
        margin=12
        width=min(560,max(320,self.width()-2*margin)); self.error_notice.setFixedWidth(width); self.error_notice.adjustSize(); self.error_notice.move(max(margin,self.width()-self.error_notice.width()-margin),margin+35)
        self.error_notice.raise_()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_sidebar_limits()
        self._position_error_notice()
        self._schedule_layout_save()

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        self._schedule_layout_save()

    def _force_main_window_not_topmost(self) -> None:
        # Guard rail: settings legadas não podem reativar Always-on-Top
        # na janela principal. Os overlays são tratados separadamente.
        try:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
        except Exception:
            pass

    def _on_engine_error(self, exc: Exception) -> None:
        self._show_detailed_error('Erro durante a execução',exc)
        self._clear_all_visualizers()

    def _on_real_key(self, name: str, pressed: bool) -> None:
        self.visualizer_panel.apply_raw_key(name, pressed)
        if self.keyboard_overlay is not None:
            if pressed:
                self.keyboard_overlay.keyboard.press(name)
            else:
                self.keyboard_overlay.keyboard.release(name)

    def _on_real_mouse_button(self, name: str, pressed: bool) -> None:
        self.visualizer_panel.apply_raw_mouse(name, pressed)
        if self.mouse_overlay is not None:
            if pressed:
                self.mouse_overlay.mouse.press(name)
            else:
                self.mouse_overlay.mouse.release(name)

    def _on_real_mouse_scroll(self, dx: int, dy: int) -> None:
        self.visualizer_panel.mouse.scroll(dx, dy)
        if self.mouse_overlay is not None:
            self.mouse_overlay.mouse.scroll(dx, dy)

    def _on_real_mouse_move(self, x: int, y: int) -> None:
        if self._last_mouse_pos is not None:
            dx = x - self._last_mouse_pos[0]
            dy = y - self._last_mouse_pos[1]
            if self.mouse_overlay is not None:
                self.mouse_overlay.mouse.move_direction(dx, dy)
            self.visualizer_panel.mouse.move_direction(dx, dy)
        self._last_mouse_pos = (x, y)

    def _clear_all_visualizers(self) -> None:
        self.visualizer_panel.clear_all()
        if self.keyboard_overlay is not None:
            self.keyboard_overlay.keyboard.clear()
        if self.mouse_overlay is not None:
            self.mouse_overlay.mouse.clear()

    def _configure_visual_settings(self):
        dlg=VisualSettingsDialog(self.visual_settings,self)
        if dlg.exec()==QDialog.Accepted:
            self.visual_settings=dlg.values(); self.settings.set_visual_settings(self.visual_settings); self._apply_visual_settings()
    def _apply_visual_settings(self, settings_override=None):
        # A MainWindow deve permanecer uma janela normal do Windows.
        # Isso permite cobrir/ser coberta por outros aplicativos e usar
        # Snap com Win+Setas. Somente overlays de input ficam no topo.
        self._force_main_window_not_topmost()
        s = dict(settings_override) if settings_override is not None else self.visual_settings
        self._dark_theme, self._theme_accent = _resolve_theme_mode(s)
        self._update_branding()
        app=QApplication.instance()
        _apply_application_palette(app, self._dark_theme, self._theme_accent, s)
        # Reaplica a paleta/stylesheet aos widgets já existentes. Isso é
        # necessário principalmente para sidebars hospedadas e controles
        # criados antes da troca de tema.
        for widget in app.allWidgets():
            try:
                widget.style().unpolish(widget); widget.style().polish(widget); widget.update()
            except Exception:
                pass
        if hasattr(self, "timeline_panel"):
            self.timeline_panel.set_theme(self._dark_theme, self._theme_accent)
        if hasattr(self, "command_table"):
            self.command_table.set_theme(self._dark_theme, str(self._theme_accent))
        surface = s.get("virtual_surface_dark" if self._dark_theme else "virtual_surface_light", "#4A4F57" if self._dark_theme else "#5A6068")
        text_color = s.get("virtual_text_dark" if self._dark_theme else "virtual_text_light", "#FFC53D")
        v_accent = s.get("virtual_accent") or str(self._theme_accent)
        if isinstance(v_accent, QColor):
            v_accent = v_accent.name()
        self.visualizer_panel.keyboard.set_theme(self._dark_theme, v_accent, surface, text_color)
        self.visualizer_panel.mouse.set_theme(self._dark_theme, v_accent, surface, text_color)
        if self.keyboard_overlay:
            self.keyboard_overlay.set_display(s.get('keyboard_mode','compact'),s.get('keyboard_timeout',3),s.get('keyboard_opacity',1),s.get('click_virtual_keyboard',True))
            self.keyboard_overlay.keyboard.set_theme(self._dark_theme, v_accent, surface, text_color)
            # O teclado virtual é um overlay de input: permanece acima das
            # demais janelas, independentemente do estado da MainWindow.
            self.keyboard_overlay.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        if self.mouse_overlay:
            self.mouse_overlay.set_display(s.get('mouse_timeout',3),s.get('mouse_opacity',1))
            self.mouse_overlay.mouse.set_theme(self._dark_theme, v_accent, surface, text_color)
            # O mouse virtual é um overlay de input: permanece acima das
            # demais janelas, independentemente do estado da MainWindow.
            self.mouse_overlay.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    def _on_virtual_key_clicked(self,label):
        target={'ShiftLeft':'SHIFT','ShiftRight':'SHIFT','CtrlLeft':'CTRL','CtrlRight':'CTRL','AltGr':'ALTGR','NumEnter':'NUMENTER','NumLock':'NUMLOCK','NumDel':'NUMDEL','Fn':'FN','Ç':'Ç','~^':'~^'}.get(label,label)
        if label.startswith('Num') and label not in ('NumLock','NumEnter','NumDel'):
            target=label.upper()
        if target=='FN':
            self.status_bar.showMessage('A tecla Fn depende do hardware e não pode ser simulada de forma universal no Windows.',4000); return
        try:
            backend=self.engine._backend
            backend.key_down(target); backend.key_up(target)
        except Exception as exc:
            self.status_bar.showMessage(f'Não foi possível enviar {target}: {exc}',4000)
    # ---- Teclado/mouse virtual (overlays independentes — item 13) -------

    def _toggle_keyboard_overlay(self,checked):
        if checked:
            if self.keyboard_overlay is None:
                self.keyboard_overlay=KeyboardOverlay(); self.keyboard_overlay.closed.connect(self._on_keyboard_overlay_closed); self.keyboard_overlay.keyClicked.connect(self._on_virtual_key_clicked); self._restore_overlay_geometry(self.keyboard_overlay,'keyboard')
            self._apply_visual_settings(); self.keyboard_overlay.show(); self.keyboard_overlay.raise_()
        elif self.keyboard_overlay is not None: self.keyboard_overlay.hide()

    def _on_keyboard_overlay_closed(self) -> None:
        self.btn_toggle_keyboard.blockSignals(True); self.btn_toggle_keyboard.setChecked(False); self.btn_toggle_keyboard.blockSignals(False)

    def _toggle_mouse_overlay(self,checked):
        if checked:
            if self.mouse_overlay is None:
                self.mouse_overlay=MouseOverlay(); self.mouse_overlay.closed.connect(self._on_mouse_overlay_closed); self._restore_overlay_geometry(self.mouse_overlay,'mouse')
            self._apply_visual_settings(); self.mouse_overlay.show(); self.mouse_overlay.raise_()
        elif self.mouse_overlay is not None: self.mouse_overlay.hide()
    def _restore_overlay_geometry(self,overlay,key):
        g=self.visual_settings.get(key+'_geometry')
        if isinstance(g,list) and len(g)==4: overlay.setGeometry(*[int(x) for x in g])
        else:
            screen=QGuiApplication.primaryScreen(); area=screen.availableGeometry() if screen else QRect(0,0,1920,1080)
            overlay.move(area.right()-overlay.width()-20,area.top()+20)
        overlay.geometryChanged.connect(lambda k=key,o=overlay:self._save_overlay_geometry(k,o))
    def _save_overlay_geometry(self,key,overlay):
        r=overlay.geometry(); self.visual_settings[key+'_geometry']=[r.x(),r.y(),r.width(),r.height()]; self.settings.set_visual_settings(self.visual_settings)

    def _on_mouse_overlay_closed(self) -> None:
        self.btn_toggle_mouse.blockSignals(True); self.btn_toggle_mouse.setChecked(False); self.btn_toggle_mouse.blockSignals(False)

    def _update_status_label(self, state: State) -> None:
        label = _STATE_LABELS.get(state, state.value)
        self.setWindowTitle(f"Automation Studio — {label}")
        running = state in (State.RUNNING, State.PAUSED)
        recording = state == State.RECORDING
        # Execução exclusiva (item 9/22): nunca gravar e executar juntos.
        self.btn_run.setEnabled(not running and not recording)
        self.btn_stop.setEnabled(running)
        self.btn_record.setEnabled((not running) and (recording or self.input_monitor.available))
        self.btn_cancel_record.setEnabled(recording)
        if recording:
            self.btn_record.setText('✓ Finalizar gravação')
        else:
            self.btn_record.setText('● Iniciar gravação')
        if state == State.IDLE:
            # Item 7/22: parado (inclusive por Parar/Emergência, que não
            # passam por `on_finished`) = sem playhead na timeline.
            self.timeline_panel.set_playhead(None)


# Modular export contract: this project intentionally shares private helpers
# between UI modules via import *. Export them explicitly so runtime names
# such as _PYNPUT_AVAILABLE and _default_backend are not lost.
__all__ = [name for name in globals() if not name.startswith("__")]
