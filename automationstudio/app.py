from __future__ import annotations



from .core import *

from .input_system import *

from .project import *

from .tutorial import *

from .overlays import *

from .command_editor import *

from .timeline import *

from .main_window import *

def _startup_dark_theme(base_dir: Path) -> bool:
    """Resolve o tema salvo antes de a MainWindow existir."""
    try:
        settings = AppSettings(_registered_data_dir(base_dir)).get_visual_settings()
        mode = str(settings.get("theme_mode", "system"))
        if mode == "dark":
            return True
        if mode == "light":
            return False
    except Exception:
        mode = "system"
    if mode == "system":
        try:
            import winreg
            key = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
                return int(winreg.QueryValueEx(k, "AppsUseLightTheme")[0]) == 0
        except Exception:
            pass
    return False

def _acquire_single_instance() -> bool:
    """Impede duas instâncias do Automation Studio no Windows."""
    global _SINGLE_INSTANCE_HANDLE
    if os.name != "nt":
        return True
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        ERROR_ALREADY_EXISTS = 183
        # Mutex exclusivo por instalação. Versões diferentes do programa
        # não podem bloquear umas às outras.
        import hashlib
        instance_key = hashlib.sha256(str(Path(__file__).resolve().parent).encode("utf-8")).hexdigest()[:24]
        mutex_name = f"Local\\AutomationStudio.SingleInstance.{instance_key}"
        handle = kernel32.CreateMutexW(None, False, mutex_name)
        if not handle:
            return True
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            return False
        _SINGLE_INSTANCE_HANDLE = handle
        return True
    except Exception:
        # A proteção é uma segurança extra; se ela falhar, não bloquear o app.
        return True

def _session_log_file(base_dir: Path) -> Path:
    """Retorna o único log operacional da instalação."""
    log_dir = base_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "AutomationStudio.log"

def _build_error_text(exc_type, exc_value, exc_tb, base_dir: Path) -> tuple[str, Path]:
    """Cria diagnóstico completo e atualiza o log único da execução."""
    log_file = _session_log_file(base_dir)
    text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    diagnostic = (
        f"Data/hora: {datetime.now().isoformat()}\n"
        f"Python: {sys.version}\n"
        f"Executável: {sys.executable}\n"
        f"Arquivo: {Path(__file__).resolve()}\n"
        f"Diretório atual: {Path.cwd()}\n"
        f"Argumentos: {sys.argv!r}\n\n"
        f"TRACEBACK COMPLETO\n{'=' * 80}\n{text}"
    )
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n\n===== ERRO {datetime.now().isoformat()} =====\n{diagnostic}\n")
    except OSError:
        pass
    return diagnostic, log_file

def _show_fatal_error(text: str, log_file: Path) -> None:
    """Mostra o traceback completo, sem esconder a causa real do erro."""
    try:
        from PySide6.QtWidgets import QMessageBox
        box = QMessageBox()
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle("Automation Studio — erro fatal")
        box.setText("O Automation Studio não conseguiu iniciar corretamente.")
        box.setInformativeText(f"O erro completo foi salvo em:\n{log_file}")
        box.setDetailedText(text)
        box.setStandardButtons(QMessageBox.Ok)
        box.exec()
    except Exception:
        pass

def main() -> int:
    base_dir = Path(__file__).resolve().parent

    # Um único arquivo por execução. Ele é zerado pelo launcher antes do
    # bootstrap e recebe todas as etapas/erros desta tentativa.
    log_file = _session_log_file(base_dir)
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(
                f"\n===== INICIO DA APLICACAO {datetime.now().isoformat()} =====\n"
                f"Python: {sys.executable}\n"
                f"Arquivo: {Path(__file__).resolve()}\n"
            )
    except OSError:
        pass

    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
    except ImportError as exc:
        log_dir = base_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "automationstudio.log"
        text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write(text)
        print("PySide6 não está instalado. Execute Iniciar.bat novamente.")
        return 1

    app = QApplication(sys.argv)
    if not _acquire_single_instance():
        QMessageBox.information(
            None, "Automation Studio",
            "O Automation Studio já está em execução a partir desta pasta.\n\nFeche a outra janela antes de abrir uma nova.")
        return 0
    dark_startup = _startup_dark_theme(base_dir)
    app.setWindowIcon(QIcon(str(_asset_path("AutomationStudio_dark.ico" if dark_startup else "AutomationStudio_light.ico"))))
    # A logo de inicialização é exibida como um overlay FILHO da janela principal.
    # Assim ela nunca é posicionada como uma janela independente pelo Windows
    # (o que poderia colocá-la em outro monitor ou fora da área da MainWindow).
    splash = None
    splash_started = time.monotonic()
    # Fusion respeita a QPalette de forma consistente no Windows, evitando
    # que o estilo nativo ignore parcialmente a troca entre claro/escuro.
    try:
        if app.style().objectName().lower() != "fusion":
            app.setStyle("Fusion")
    except Exception:
        pass
    app.setApplicationName("Automation Studio")


    def excepthook(exc_type, exc_value, exc_tb):
        text, log_file = _build_error_text(exc_type, exc_value, exc_tb, base_dir)
        _show_fatal_error(text, log_file)

    sys.excepthook = excepthook

    try:
        window = MainWindow(project_dir=base_dir)
        window.show()
        app.processEvents()

        # Splash interno: permanece rigorosamente dentro dos limites da
        # MainWindow, inclusive quando ela está em uma posição não centralizada,
        # dividindo a tela via Win+Setas ou em um monitor secundário.
        try:
            from PySide6.QtWidgets import QLabel
            splash_pix = _load_splash_pixmap(dark_startup)
            if not splash_pix.isNull():
                splash = QLabel(window)
                splash.setAttribute(Qt.WA_TranslucentBackground, True)
                splash.setAlignment(Qt.AlignCenter)
                splash.setPixmap(splash_pix.scaled(760, 184, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                splash.adjustSize()
                splash.move(
                    max(0, (window.width() - splash.width()) // 2),
                    max(0, (window.height() - splash.height()) // 2),
                )
                splash.raise_()
                splash.show()
                app.processEvents()
        except Exception:
            splash = None

        remaining = 0.35 - (time.monotonic() - splash_started)
        if remaining > 0:
            time.sleep(remaining)
            app.processEvents()
        if splash is not None:
            splash.hide()
            splash.deleteLater()
            splash = None
        return app.exec()
    except Exception as exc:
        text, log_file = _build_error_text(type(exc), exc, exc.__traceback__, base_dir)
        _show_fatal_error(text, log_file)
        return 1


# Modular export contract: this project intentionally shares private helpers
# between UI modules via import *. Export them explicitly so runtime names
# such as _PYNPUT_AVAILABLE and _default_backend are not lost.
__all__ = [name for name in globals() if not name.startswith("__")]
