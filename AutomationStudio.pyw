# Bootstrap do Automation Studio.
# Este arquivo deliberadamente não importa o pacote no topo: qualquer falha
# de importação precisa ser registrada e apresentada ao usuário, em vez de
# desaparecer silenciosamente quando o arquivo é executado por pythonw.exe.
from pathlib import Path
import sys
import traceback
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "AutomationStudio.log"

def _write_startup(text: str) -> None:
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(text + "\n")
            f.flush()
    except Exception:
        pass

def _show_error(text: str) -> None:
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        app = QApplication.instance() or QApplication(sys.argv)
        box = QMessageBox()
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle("Automation Studio — erro ao iniciar")
        box.setText("O Automation Studio não conseguiu iniciar.")
        box.setInformativeText("O diagnóstico completo foi salvo em:\n" + str(LOG_FILE))
        box.setDetailedText(text)
        box.exec()
    except Exception:
        pass

_write_startup("\n===== BOOTSTRAP {0} =====".format(datetime.now().isoformat()))
_write_startup("Python: " + sys.executable)
_write_startup("Arquivo: " + str(Path(__file__).resolve()))
_write_startup("Diretório: " + str(Path.cwd()))

try:
    from automationstudio.app import main
    _write_startup("Importação do núcleo modular: OK")
    rc = main()
    _write_startup("main() finalizado com código: " + str(rc))
    raise SystemExit(rc)
except SystemExit:
    raise
except BaseException as exc:
    diagnostic = (
        "Data/hora: " + datetime.now().isoformat() + "\n"
        "Python: " + sys.version + "\n"
        "Executável: " + sys.executable + "\n"
        "Arquivo: " + str(Path(__file__).resolve()) + "\n"
        "Diretório atual: " + str(Path.cwd()) + "\n"
        "Argumentos: " + repr(sys.argv) + "\n\n"
        "TRACEBACK COMPLETO\n" + "=" * 80 + "\n" +
        "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    )
    _write_startup(diagnostic)
    _show_error(diagnostic)
    raise SystemExit(1)
