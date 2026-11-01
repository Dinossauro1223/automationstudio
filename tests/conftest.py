"""Configuração comum e fixtures dos testes (ver tests/README.md).

Subconjunto portátil: as fixtures ficam SÓ aqui, têm escopo de função ou de sessão e não usam `request`.
Assim o mesmo código roda no pytest e no executor mínimo (tests/testsupport/run_minimal.py).
"""
import importlib
import os
import pathlib
import subprocess
import sys
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # Qt sem janela real
TESTS_DIR = pathlib.Path(__file__).resolve().parent
ROOT = pathlib.Path(os.environ.get("AS_ROOT") or TESTS_DIR.parent)
for _path in (str(ROOT), str(TESTS_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)
_QT_STUB = os.environ.get("AS_TEST_QT_STUB", "")
if _QT_STUB == "1":
    # Só a lógica (modelo, motor, gravador, persistência). Os testes de GUI são pulados com o stub.
    sys.path.insert(0, str(TESTS_DIR / "testsupport" / "qt_stub"))
elif _QT_STUB == "widgets":
    # Dublê funcional parcial (testsupport/qt_double): executa a lógica Python dos DIÁLOGOS sem o Qt.
    sys.path.insert(0, str(TESTS_DIR / "testsupport" / "qt_double"))

import pytest  # noqa: E402

from testsupport.fake_clock import FakeClock  # noqa: E402


def _import_package():
    try:
        return importlib.import_module("automationstudio.core")
    except ImportError as exc:
        raise RuntimeError(
            "Não foi possível importar o Automation Studio: " + str(exc) + "\n"
            "Instale as dependências para este Python (Instalar_Dependencias_Global.bat) ou, para validar só a lógica, "
            "defina AS_TEST_QT_STUB=1.") from exc


def _definir_constantes_de_execucao(core, valores) -> None:
    """(TEXT_CHAR_INTERVAL, APP_STABLE_DEFAULT_MS, APP_AFTER_OPEN_DEFAULT). Tolera o 25.3, que ainda não tinha
    `set_runtime_defaults` (necessário para rodar a regressão do Ponto 1 contra o código original com AS_ROOT)."""
    definir = getattr(core, "set_runtime_defaults", None)
    if definir is not None:
        definir(*valores)
    else:
        core.TEXT_CHAR_INTERVAL, core.APP_STABLE_DEFAULT_MS, core.APP_AFTER_OPEN_DEFAULT = valores


@pytest.fixture(autouse=True)
def runtime_log(monkeypatch):
    """Nenhum teste escreve em logs reais (o log de execução grava ao lado de sys.argv[0], que sob o pytest
    seria a pasta do próprio Python) e as constantes de execução voltam ao valor original ao fim do teste."""
    core = _import_package()
    for name in ("input_system", "project", "vision", "conditions"):
        importlib.import_module(f"automationstudio.{name}")
    captured = []

    def fake_log(message):
        captured.append(str(message))

    for module_name, module in list(sys.modules.items()):
        if (module_name == "automationstudio" or module_name.startswith("automationstudio.")) and hasattr(module, "_append_runtime_log"):
            monkeypatch.setattr(module, "_append_runtime_log", fake_log)
    saved = (core.TEXT_CHAR_INTERVAL, core.APP_STABLE_DEFAULT_MS, core.APP_AFTER_OPEN_DEFAULT)
    _definir_constantes_de_execucao(core, (0.0, saved[1], saved[2]))  # nenhum teste dorme em tempo real digitando
    yield captured
    _definir_constantes_de_execucao(core, saved)


@pytest.fixture(autouse=True)
def nenhum_aplicativo_real(monkeypatch):
    """Rede de segurança: nenhum teste abre um aplicativo de verdade. No Windows o motor lança o alvo de um comando
    "abrir aplicativo" com `subprocess.Popen`; um teste que esquecesse de trocar `_launch_application` abriria o Bloco de Notas
    na máquina de quem roda a suíte. Só o `subprocess` visto pelo motor é trocado (o resto dos testes usa o módulo de verdade)."""
    from automationstudio import input_system

    def bloqueado(*args, **kwargs):
        raise AssertionError("um teste tentou abrir um aplicativo de verdade: " + repr(args[:1]))

    copia = types.SimpleNamespace(**{nome: getattr(subprocess, nome) for nome in dir(subprocess) if not nome.startswith("__")})
    copia.Popen = bloqueado
    monkeypatch.setattr(input_system, "subprocess", copia)


@pytest.fixture(autouse=True)
def qt_estrito(monkeypatch):
    """Com o Qt real: (1) a QApplication existe antes de qualquer widget, qualquer que seja a ordem ou a seleção dos
    testes; (2) uma exceção dentro de um slot reprova o teste. O Qt só IMPRIME a exceção de um slot e segue em frente,
    então sem isto um clique que falha por dentro passaria despercebido (o dublê, que chama os slots direto, já propaga)."""
    from testsupport.gui_helpers import ensure_qapp
    ensure_qapp()
    erros = []
    monkeypatch.setattr(sys, "excepthook", lambda tipo, valor, rastro: erros.append((tipo, valor)))
    yield
    assert not erros, "exceção dentro de um slot do Qt: " + "; ".join(f"{t.__name__}: {v}" for t, v in erros)


@pytest.fixture
def fake_clock():
    return FakeClock()


@pytest.fixture
def mock_backend(fake_clock):
    from automationstudio.input_system import MockInputBackend
    return MockInputBackend(clock=fake_clock)


@pytest.fixture
def hook_backend(fake_clock):
    """Mock que chama ganchos logo depois do N-ésimo evento (roda na thread do motor)."""
    from testsupport.fakes import HookBackend
    return HookBackend(clock=fake_clock)


@pytest.fixture
def gravar(fake_clock):
    """Fábrica de gravador com relógio virtual e monitor falso: gravar(filtros=None, estado=None) -> (gravador, monitor, estado)."""
    def fabrica(filtros=None, estado=None):
        from automationstudio.core import StateManager
        from automationstudio.input_system import Recorder
        from testsupport.fakes import FakeMonitor
        monitor, estado = FakeMonitor(), estado or StateManager()
        return Recorder(monitor, estado, filtros, clock=fake_clock), monitor, estado
    return fabrica


@pytest.fixture
def make_engine(fake_clock):
    """Fábrica de motor com relógio virtual: make_engine(backend=None, state=None) -> (engine, backend)."""
    def factory(backend=None, state=None):
        from automationstudio.input_system import ExecutionEngine, MockInputBackend
        backend = backend if backend is not None else MockInputBackend(clock=fake_clock)
        return ExecutionEngine(backend, state, clock=fake_clock), backend
    return factory


@pytest.fixture
def ambiente_simulado():
    """Ambiente e2e simulado (USER32 falso + janela de mentira): roda em qualquer sistema. Ver testsupport/e2e_windows.py."""
    from testsupport import e2e_windows
    ambiente = e2e_windows.criar(e2e_windows.SIMULADO)
    yield ambiente
    ambiente.encerrar()


@pytest.fixture
def ambiente_real():
    """Ambiente e2e do Windows de verdade: PULA, sem enviar nada, fora do Windows ou sem AS_ALLOW_REAL_INPUT=1."""
    from testsupport import e2e_windows
    motivo = e2e_windows.motivo_para_pular(e2e_windows.WINDOWS)
    if motivo:
        pytest.skip(motivo)
    ambiente = e2e_windows.criar(e2e_windows.WINDOWS)
    yield ambiente
    ambiente.encerrar()


@pytest.fixture(scope="session")
def legacy_maps():
    """Os 3 mapas reais (formato v1) usados nos testes de compatibilidade."""
    from testsupport.helpers import load_legacy_maps
    return load_legacy_maps()


@pytest.fixture(scope="session")
def qapp():
    qtwidgets = pytest.importorskip("PySide6.QtWidgets")
    marca = getattr(importlib.import_module("PySide6"), "__as_stub__", False)
    if marca == "widgets":
        return object()  # o dublê não tem QApplication nem laço de eventos
    if marca:
        pytest.skip("PySide6 é o stub de lógica: testes de GUI exigem o Qt real")
    from testsupport.gui_helpers import ensure_qapp
    return ensure_qapp() or qtwidgets.QApplication([])


@pytest.fixture
def gui(qapp, monkeypatch, tmp_path):
    """Isolamento de GUI (ver testsupport/qt_isolation.py). Devolve o registro de diálogos chamados.

    Também liga o VIGIA de travamento (testsupport/diagnostico_qt.py): se o teste passar do limite (60 s; mude com
    AS_LIMITE_TESTE_JANELA), grava `logs/travamento_qt.txt` e encerra o processo, em vez de deixar a rodada parada.

    No fim esvazia a fila de eventos e coleta o lixo (`gui_helpers.encerrar_teste_de_janela`): sem isso o lixo de um teste
    era destruído pelo coletor automático no meio de um teste POSTERIOR, e no Windows o Qt abortava nessa hora."""
    from testsupport import diagnostico_qt, gui_helpers, qt_isolation
    log = qt_isolation.install(monkeypatch, tmp_path)
    assert not log.install_errors, log.install_errors
    diagnostico_qt.iniciar(os.environ.get("PYTEST_CURRENT_TEST", "teste de janela"), ROOT / "logs")
    yield log
    try:
        gui_helpers.encerrar_teste_de_janela()   # o lixo do teste é solto AGORA, e não no meio de um teste posterior
    finally:
        diagnostico_qt.encerrar_atual()


@pytest.fixture
def gui_real(gui):
    """Como `gui`, mas só roda com o PySide6 de verdade: a janela principal não cabe no dublê."""
    if getattr(importlib.import_module("PySide6"), "__as_stub__", False):
        pytest.skip("este teste exige o Qt real (janela principal)")
    return gui


@pytest.fixture
def abrir_janela(gui_real, tmp_path):
    """Fábrica da janela principal, isolada (registro, hooks globais, input real e diálogos modais bloqueados: ver
    testsupport/qt_isolation.py). Só roda com o Qt real.

    abrir_janela(pular_tutorial=True, pasta=None) -> MainWindow. Mapas e configurações vão para uma pasta temporária. O
    tutorial de primeiro uso é dispensado de antemão (a menos que o teste peça o contrário). Ao fim do teste cada janela tem
    o motor parado, o relógio da interface desligado, é fechada e DESTRUÍDA, e a fila de eventos é esvaziada (nada de um
    teste sobra para o seguinte: ver `descartar_janelas`).

    Também liga o diagnóstico de eventos do Qt (anel de eventos e mensagens do Qt no relatório de travamento); desligue
    com AS_DIAGNOSTICO_QT=0 se desconfiar que ele atrapalha.
    """
    from testsupport import diagnostico_qt, gui_helpers
    vigia = diagnostico_qt.atual()
    if vigia is not None and os.environ.get("AS_DIAGNOSTICO_QT", "1") != "0":
        vigia.anexar_qt(gui_helpers.ensure_qapp())
    janelas = []

    def fabrica(pular_tutorial=True, pasta=None):
        from automationstudio.main_window import MainWindow
        from automationstudio.project import AppSettings
        pasta = pasta if pasta is not None else tmp_path / "dados"
        if pular_tutorial:
            ajustes = AppSettings(pasta)
            visuais = ajustes.get_visual_settings()
            visuais["onboarding_seen"] = True
            ajustes.set_visual_settings(visuais)
        janela = MainWindow(project_dir=pasta)
        janelas.append(janela)
        return janela

    yield fabrica
    gui_helpers.descartar_janelas(janelas)


def pytest_runtest_logreport(report):
    """Mostra a falha NA HORA. O pytest só imprime o detalhe das falhas no FIM da rodada, e uma rodada que trava ou é
    encerrada (como a de 18/10/2026) nunca chega lá: o resultado era um `F` e nenhuma explicação. Hook do pytest; o
    executor mínimo não o usa (ele já imprime cada teste ao terminar)."""
    if not getattr(report, "failed", False):
        return
    try:
        partes = [f"\n=== FALHOU: {report.nodeid} ({report.when}) ===", str(report.longreprtext).rstrip()]
        for titulo, conteudo in getattr(report, "sections", None) or []:
            if str(conteudo).strip():
                partes += [f"--- {titulo} ---", str(conteudo).rstrip()]
        partes.append("=== fim da falha ===")
        print("\n".join(partes), flush=True)
    except Exception:  # noqa: BLE001  (um defeito aqui jamais pode esconder a falha do teste)
        pass
