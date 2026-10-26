"""O isolamento de GUI (testsupport/qt_isolation.py) precisa funcionar ANTES de qualquer teste de janela depender dele.

Sem o isolamento, construir a MainWindow na máquina do usuário abriria a pasta de dados REAL (o registro do Windows
tem prioridade) e ligaria hooks globais de teclado e mouse. Estes testes só chamam métodos estáticos e não criam
widgets, então rodam com o Qt real e também com o stub de lógica.
"""
import sys

import pytest

from testsupport import qt_isolation


def _instalar(monkeypatch, tmp_path):
    log = qt_isolation.install(monkeypatch, tmp_path)
    assert log.install_errors == [], log.install_errors
    return log


def test_o_registro_do_windows_fica_bloqueado(monkeypatch, tmp_path):
    _instalar(monkeypatch, tmp_path)
    winreg = sys.modules["winreg"]
    for nome in ("OpenKey", "CreateKey", "SetValueEx", "QueryValueEx"):
        with pytest.raises(OSError, match="bloqueado"):
            getattr(winreg, nome)()


def test_a_pasta_de_dados_registrada_vira_a_pasta_pedida(monkeypatch, tmp_path):
    from automationstudio import main_window
    log = _instalar(monkeypatch, tmp_path)
    assert main_window._registered_data_dir(tmp_path / "dados") == (tmp_path / "dados").resolve()
    main_window._set_registered_data_dir(tmp_path / "outra")
    assert log.calls == [("registro", str(tmp_path / "outra"))], "gravar no registro só fica anotado"


def test_o_monitor_global_nao_liga_hooks_reais(monkeypatch, tmp_path):
    from automationstudio.input_system import GlobalInputMonitor
    _instalar(monkeypatch, tmp_path)
    monitor = GlobalInputMonitor()
    monitor.start()
    assert not monitor.is_running()


def test_a_janela_usa_o_backend_mock_e_nunca_o_de_input_real(monkeypatch, tmp_path):
    from automationstudio import main_window
    from automationstudio.input_system import MockInputBackend
    _instalar(monkeypatch, tmp_path)
    assert isinstance(main_window._default_backend(), MockInputBackend)


def test_dialogos_de_mensagem_respondem_sem_bloquear_e_ficam_registrados(monkeypatch, tmp_path):
    from PySide6.QtWidgets import QInputDialog, QMessageBox
    log = _instalar(monkeypatch, tmp_path)
    QMessageBox.warning(None, "Título", "Mensagem")
    QMessageBox.question(None, "Confirmar", "Tem certeza?")
    QInputDialog.getText(None, "Nome", "Digite")
    assert log.kinds() == ["warning", "question", "getText"]
    assert log.calls[0] == ("warning", "Título", "Mensagem")


def test_a_pergunta_de_confirmacao_responde_sim_e_a_de_texto_cancela(monkeypatch, tmp_path):
    from PySide6.QtWidgets import QInputDialog, QMessageBox
    _instalar(monkeypatch, tmp_path)
    assert QMessageBox.question(None, "x", "y") == QMessageBox.StandardButton.Yes
    assert QInputDialog.getText(None, "x", "y") == ("", False)


def test_seletores_de_arquivo_nao_abrem_janela(monkeypatch, tmp_path):
    from PySide6.QtWidgets import QFileDialog
    log = _instalar(monkeypatch, tmp_path)
    assert QFileDialog.getOpenFileName(None, "Abrir") == ("", "")
    assert QFileDialog.getSaveFileName(None, "Salvar") == ("", "")
    assert QFileDialog.getExistingDirectory(None, "Pasta") == ""
    assert log.kinds() == ["getOpenFileName", "getSaveFileName", "getExistingDirectory"]


def test_exec_de_dialogo_modal_inesperado_derruba_o_teste(monkeypatch, tmp_path):
    from PySide6.QtWidgets import QDialog, QMenu
    _instalar(monkeypatch, tmp_path)
    for classe in (QDialog, QMenu):
        with pytest.raises(AssertionError, match="diálogo modal inesperado"):
            classe.exec(None)  # a função instalada é a mesma para qualquer instância: não precisa criar widget
