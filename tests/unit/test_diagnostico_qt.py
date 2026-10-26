"""O diagnóstico de travamento (testsupport/diagnostico_qt.py) e os auxiliares de janela (testsupport/gui_helpers.py).

Nada aqui precisa do Qt: o diagnóstico é Python puro, e a parte que fala com o Qt (filtro de eventos, tratador de mensagens)
recebe a classe base, o aplicativo e o módulo QtCore por argumento, então aqui entram objetos de mentira. O que SÓ o Qt de
verdade confirma (que o filtro recebe os eventos de uma janela de verdade) é verificado na máquina de quem roda a rodada
completa: um travamento de verdade grava logs/travamento_qt.txt com os eventos.
"""
import enum
import io
import os
import sys
import threading
import types

import pytest

from testsupport import diagnostico_qt as dq
from testsupport import gui_helpers as gh
from testsupport.fake_clock import FakeClock


# ------------------------------------------------------------------------------------------------ o anel de eventos
def _anel(relogio=None, capacidade=500):
    return dq.AnelDeEventos(capacidade, relogio=relogio or FakeClock())


def test_o_anel_guarda_os_eventos_na_ordem_com_o_instante_e_conta_todos():
    relogio = FakeClock(10.0)
    anel = _anel(relogio)
    anel.registrar("QTimer", 1, "relogio")
    relogio.advance(0.5)
    anel.registrar("QPushButton", 12)
    assert anel.ultimos() == [(10.0, "QTimer", "relogio", 1), (10.5, "QPushButton", "", 12)]
    assert anel.total == 2 and anel.ultimo == 10.5


def test_o_anel_esquece_os_mais_antigos_mas_os_totais_nao():
    anel = _anel(capacidade=3)
    for numero in range(10):
        anel.registrar("QTimer", numero % 2)
    assert len(anel.ultimos(100)) == 3 and anel.total == 10
    assert dict(anel.totais()) == {("QTimer", 0): 5, ("QTimer", 1): 5}


def test_os_mais_frequentes_so_contam_a_janela_de_tempo_e_ignoram_marcos():
    relogio = FakeClock()
    anel = _anel(relogio)
    anel.registrar("QWidget", 12)          # há 9 s: fora da janela de 5 s
    relogio.advance(9.0)
    for _ in range(3):
        anel.registrar("QTimer", 1, "a")
    anel.registrar("QLabel", 77)
    anel.marcar("antes do show()")
    assert anel.mais_frequentes(relogio.monotonic(), 5.0) == [(("QTimer", 1), 3), (("QLabel", 77), 1)]
    assert anel.total == 5, "o marco não é um evento do Qt"


def test_o_silencio_diz_ha_quanto_tempo_nenhum_evento_passou():
    relogio = FakeClock()
    anel = _anel(relogio)
    assert anel.silencio_s(relogio.monotonic()) is None
    anel.registrar("QTimer", 1)
    relogio.advance(4.0)
    assert anel.silencio_s(relogio.monotonic()) == pytest.approx(4.0)


# ------------------------------------------------------------------------------------------------ diagnóstico e relatório
def test_diagnostico_sem_anel_sem_eventos_bloqueado_e_laco():
    relogio = FakeClock()
    assert "Sem registro" in dq.diagnosticar(None, 0.0)
    anel = _anel(relogio)
    assert "NUNCA" in dq.diagnosticar(anel, relogio.monotonic())
    anel.registrar("QTimer", 1)
    relogio.advance(10.0)
    bloqueio = dq.diagnosticar(anel, relogio.monotonic())
    assert bloqueio.startswith("BLOQUEIO") and "10.0 s" in bloqueio
    anel.registrar("QTimer", 1)
    relogio.advance(0.05)
    assert dq.diagnosticar(anel, relogio.monotonic()).startswith("LAÇO DE EVENTOS")


def _relatorio(**mudancas):
    relogio = FakeClock()
    anel = _anel(relogio)
    anel.registrar("QTimer", 1, "relogio-da-interface")
    anel.marcar("antes do show()")
    relogio.advance(8.0)
    mensagens = dq.RegistroDeMensagens(relogio=relogio)
    mensagens.registrar("Warning", "QObject::startTimer: Timers can only be used with threads started with QThread")
    argumentos = dict(nome="tests/gui/test_x.py::test_y (call)", decorrido_s=61.2, limite_s=60, anel=anel, mensagens=mensagens,
                      pilhas="--- thread MainThread\n  File x.py, line 1", ambiente="Python 3.14.0", agora=relogio.monotonic(),
                      quando="2026-10-19 07:00:00", nome_do_tipo=lambda tipo: {1: "Timer", 12: "Paint"}.get(tipo, str(tipo)))
    argumentos.update(mudancas)
    return dq.montar_relatorio(**argumentos)


def test_o_relatorio_tem_o_teste_o_diagnostico_os_eventos_as_mensagens_as_pilhas_e_o_ambiente():
    texto = _relatorio()
    for trecho in ("TESTE: tests/gui/test_x.py::test_y (call)", "DECORRIDO: 61.2 s (limite 60 s)", "DIAGNOSTICO: BLOQUEIO",
                   "QTimer 'relogio-da-interface'  Timer", "marco", "antes do show()", "MENSAGENS DO QT", "startTimer",
                   "PILHAS DO PYTHON", "--- thread MainThread", "AMBIENTE:", "Python 3.14.0", dq.MARCA_DE_FIM):
        assert trecho in texto, trecho


def test_o_relatorio_sem_anel_nem_mensagens_continua_valido():
    texto = _relatorio(anel=None, mensagens=None)
    assert "Sem registro de eventos" in texto and "EVENTOS DO QT" not in texto and "MENSAGENS DO QT" not in texto
    assert dq.MARCA_DE_FIM in texto


def test_o_relatorio_mostra_os_instantes_relativos_ao_alarme():
    assert "-8.000 s  QTimer" in _relatorio()


@pytest.mark.parametrize("texto,esperado", [
    ("TESTE: a.py::t (call)\n", "a.py::t"),
    ("TESTE: a.py::t[x (y)] (setup)\n", "a.py::t[x (y)]"),
    ("TESTE: velho.py::a (call)\nlixo\nTESTE: novo.py::b (teardown)\n", "novo.py::b"),
    ("TESTE: sem_fase.py::c\n", "sem_fase.py::c"),
    ("nada aqui\n", ""),
    ("", "")],
    ids=["simples", "parametro-com-parenteses", "ultimo-vale", "sem-fase", "sem-teste", "vazio"])
def test_o_teste_que_travou_e_lido_do_relatorio(texto, esperado):
    assert dq.teste_que_travou(texto) == esperado


def test_o_relatorio_montado_e_lido_de_volta_pelo_lancador():
    assert dq.teste_que_travou(_relatorio()) == "tests/gui/test_x.py::test_y"


def test_as_pilhas_mostram_esta_funcao_e_marcam_a_thread_principal():
    pilhas = dq.pilhas_das_threads()
    assert "test_as_pilhas_mostram_esta_funcao_e_marcam_a_thread_principal" in pilhas and "[PRINCIPAL]" in pilhas


def test_o_ambiente_descreve_python_e_a_plataforma_do_qt():
    ambiente = dq.descrever_ambiente()
    assert "Python " in ambiente and "QT_QPA_PLATFORM=" in ambiente


@pytest.mark.parametrize("valor,esperado", [("90", 90.0), ("0.5", 0.5), ("", 60.0), ("abc", 60.0), ("0", 60.0), ("-5", 60.0)],
                         ids=["inteiro", "fracao", "vazio", "texto", "zero", "negativo"])
def test_o_limite_vem_do_ambiente_ou_do_padrao(valor, esperado):
    assert dq.limite_do_ambiente(60.0, {"AS_LIMITE_TESTE_JANELA": valor}) == esperado
    assert dq.limite_do_ambiente(60.0, {}) == 60.0


class _Tipo(enum.IntEnum):
    Timer = 1
    Paint = 12


class _TipoSimples(enum.Enum):
    Timer = 1


def test_o_enum_do_pyside_vira_inteiro_seja_intenum_ou_enum_simples():
    assert dq.inteiro_do_enum(_Tipo.Paint) == 12 and dq.inteiro_do_enum(_TipoSimples.Timer) == 1
    assert dq.inteiro_do_enum(7) == 7 and dq.inteiro_do_enum(object()) == -1


def test_os_nomes_dos_tipos_vem_do_qevent_quando_ha_qt_e_sao_o_numero_quando_nao_ha(monkeypatch):
    monkeypatch.delitem(sys.modules, "PySide6.QtCore", raising=False)
    assert dq.nome_do_tipo_de_evento()(12) == "12"
    falso = types.ModuleType("PySide6.QtCore")
    falso.QEvent = types.SimpleNamespace(Type=_Tipo)
    monkeypatch.setitem(sys.modules, "PySide6.QtCore", falso)
    nome = dq.nome_do_tipo_de_evento()
    assert nome(12) == "Paint" and nome(1) == "Timer" and nome(999) == "999"


# ------------------------------------------------------------------------------------------------ o vigia
def _vigia(tmp_path, relogio=None, limite_s=60.0, **kw):
    saidas = []
    kw.setdefault("alarme_nativo", False)
    vigia = dq.Vigia("tests/x.py::teste", limite_s, tmp_path / "logs" / dq.ARQUIVO_DO_RELATORIO, relogio=relogio or FakeClock(),
                     sair=saidas.append, ambiente="ambiente de mentira", agora_em_texto=lambda: "2026-10-19 07:00:00", **kw)
    return vigia, saidas


def _stderr(monkeypatch):
    saida = io.StringIO()
    monkeypatch.setattr(sys, "__stderr__", saida)
    return saida


def test_disparar_grava_o_relatorio_avisa_e_encerra_o_processo_com_o_codigo_86(tmp_path, monkeypatch):
    erro = _stderr(monkeypatch)
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tests/gui/test_a.py::test_b (call)")
    relogio = FakeClock()
    vigia, saidas = _vigia(tmp_path, relogio)
    relogio.advance(61.0)
    vigia.disparar()
    texto = (tmp_path / "logs" / dq.ARQUIVO_DO_RELATORIO).read_text(encoding="utf-8")
    assert "TESTE: tests/gui/test_a.py::test_b (call)" in texto, "a fase atual do pytest, lida no momento do alarme"
    assert "DECORRIDO: 61.0 s" in texto and "ambiente de mentira" in texto and "PILHAS DO PYTHON" in texto
    assert saidas == [dq.CODIGO_DE_TRAVAMENTO] == [86] and vigia.disparou
    assert "TRAVAMENTO" in erro.getvalue() and "travamento_qt.txt" in erro.getvalue()


def test_sem_pytest_o_relatorio_usa_o_nome_dado_na_criacao(tmp_path, monkeypatch):
    _stderr(monkeypatch)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    vigia, _ = _vigia(tmp_path)
    vigia.disparar()
    assert "TESTE: tests/x.py::teste" in (tmp_path / "logs" / dq.ARQUIVO_DO_RELATORIO).read_text(encoding="utf-8")


def test_a_thread_do_vigia_dispara_sozinha_quando_o_tempo_passa(tmp_path, monkeypatch):
    _stderr(monkeypatch)
    relogio = FakeClock()
    avisado = threading.Event()
    saidas = []
    vigia = dq.Vigia("tests/x.py::teste", 30.0, tmp_path / "logs" / dq.ARQUIVO_DO_RELATORIO, relogio=relogio, passo_s=0.01,
                     sair=lambda codigo: (saidas.append(codigo), avisado.set()), ambiente="a", alarme_nativo=False).iniciar()
    try:
        relogio.advance(31.0)
        assert avisado.wait(10.0), "o vigia não disparou depois do limite"
    finally:
        vigia.encerrar()
    assert saidas == [86] and (tmp_path / "logs" / dq.ARQUIVO_DO_RELATORIO).exists()


def test_o_vigia_nao_dispara_se_o_teste_terminar_a_tempo(tmp_path):
    relogio = FakeClock()
    vigia, saidas = _vigia(tmp_path, relogio, limite_s=30.0, passo_s=0.01)
    vigia.iniciar()
    vigia.encerrar()
    relogio.advance(100.0)
    vigia.disparar()   # um disparo atrasado, depois de encerrar, não faz nada
    assert saidas == [] and not vigia.disparou and not (tmp_path / "logs").exists()


def test_falha_ao_gravar_o_relatorio_nao_impede_de_encerrar_e_o_texto_vai_para_o_stderr(tmp_path, monkeypatch):
    erro = _stderr(monkeypatch)
    ocupado = tmp_path / "logs"
    ocupado.write_text("sou um arquivo, não uma pasta", encoding="utf-8")   # mkdir e open vão falhar
    vigia, saidas = _vigia(tmp_path)
    vigia.disparar()
    assert saidas == [86] and "não consegui gravar" in erro.getvalue() and "TESTE:" in erro.getvalue()


def test_o_alarme_nativo_e_armado_depois_do_vigia_e_desarmado_e_apagado_ao_encerrar(tmp_path, monkeypatch):
    chamadas = []
    falso = types.SimpleNamespace(dump_traceback_later=lambda *a, **k: chamadas.append(("armar", a, k)),
                                  cancel_dump_traceback_later=lambda: chamadas.append(("cancelar",)))
    monkeypatch.setattr(dq, "faulthandler", falso)
    vigia, _ = _vigia(tmp_path, limite_s=60.0, alarme_nativo=True)
    vigia.iniciar()
    nativo = tmp_path / "logs" / dq.ARQUIVO_DO_ALARME_NATIVO
    assert nativo.exists()
    (armar,) = [c for c in chamadas if c[0] == "armar"]
    assert armar[1] == (60.0 + dq.FOLGA_DO_ALARME_NATIVO_S,) and armar[2]["exit"] is True and armar[2]["file"] is not None
    vigia.encerrar()
    assert ("cancelar",) in chamadas and not nativo.exists(), "o teste acabou a tempo: o arquivo do alarme não sobra"


def test_o_vigia_sem_alarme_nativo_nao_cria_arquivo_nenhum(tmp_path):
    vigia, _ = _vigia(tmp_path)
    vigia.iniciar()
    vigia.encerrar()
    assert not (tmp_path / "logs").exists()


def test_a_thread_do_vigia_nao_consulta_o_qt_o_ambiente_e_descrito_antes_na_thread_que_criou_o_vigia(tmp_path, monkeypatch):
    # Regra de ouro do módulo: chamar o Qt fora da thread da interface pode travar ou derrubar o processo, e o alarme só
    # dispara quando o Qt já está em apuros. `descrever_ambiente` pergunta ao Qt (versão e plataforma): só pode rodar ao
    # criar o vigia (thread do teste), nunca no disparo (thread do vigia).
    _stderr(monkeypatch)
    quem_chamou = []
    original = dq.descrever_ambiente

    def espiao():
        quem_chamou.append(threading.current_thread())
        return original()

    monkeypatch.setattr(dq, "descrever_ambiente", espiao)
    relogio = FakeClock()
    avisado = threading.Event()
    vigia = dq.Vigia("tests/x.py::teste", 30.0, tmp_path / "logs" / dq.ARQUIVO_DO_RELATORIO, relogio=relogio, passo_s=0.01,
                     sair=lambda codigo: avisado.set(), alarme_nativo=False).iniciar()   # sem `ambiente=`: descreve ao criar
    try:
        relogio.advance(31.0)
        assert avisado.wait(10.0), "o vigia não disparou depois do limite"
    finally:
        vigia.encerrar()
    assert quem_chamou == [threading.current_thread()], "o ambiente é descrito uma vez só, na thread que criou o vigia"


def test_o_executor_informa_o_teste_atual_no_ambiente_como_o_pytest_faz():
    # O vigia lê PYTEST_CURRENT_TEST NO MOMENTO do alarme para dizer QUAL teste travou. O pytest define a variável; o
    # executor mínimo do projeto precisa definir a mesma coisa, na mesma forma "<nodeid> (fase)", que o lançador sabe ler.
    atual = os.environ.get("PYTEST_CURRENT_TEST", "")
    nome = "test_o_executor_informa_o_teste_atual_no_ambiente_como_o_pytest_faz"
    assert atual.endswith(f"::{nome} (call)"), atual
    assert dq.teste_que_travou(f"{dq.MARCA_DO_TESTE}{atual}\n").endswith(f"::{nome}")


# ------------------------------------------------------------------------------------------------ a cola com o Qt
class _QObjectDeMentira:
    pass


class _AppDeMentira:
    def __init__(self, recusa=False):
        self.filtros, self.removidos, self.recusa = [], [], recusa

    def installEventFilter(self, filtro):  # noqa: N802
        if self.recusa:
            raise RuntimeError("recusado")
        self.filtros.append(filtro)

    def removeEventFilter(self, filtro):  # noqa: N802
        self.removidos.append(filtro)


class QPushButton:   # o nome da classe é o que vai para o anel
    def __init__(self, nome="botao"):
        self._nome = nome

    def objectName(self):  # noqa: N802
        return self._nome


class _EventoDeMentira:
    def __init__(self, tipo):
        self._tipo = tipo

    def type(self):
        if isinstance(self._tipo, Exception):
            raise self._tipo
        return self._tipo


def test_o_filtro_anota_receptor_tipo_e_nome_e_nunca_consome_o_evento():
    anel, app = _anel(), _AppDeMentira()
    filtro, remover = dq.instalar_filtro_de_eventos(app, anel, _QObjectDeMentira)
    assert app.filtros == [filtro]
    assert filtro.eventFilter(QPushButton("ok"), _EventoDeMentira(_Tipo.Paint)) is False
    assert [(r, t, n) for _i, r, n, t in anel.ultimos()] == [("QPushButton", 12, "ok")]
    remover()
    assert app.removidos == [filtro]


def test_o_filtro_sobrevive_a_um_evento_ou_receptor_defeituoso():
    anel = _anel()
    filtro, _ = dq.instalar_filtro_de_eventos(_AppDeMentira(), anel, _QObjectDeMentira)
    assert filtro.eventFilter(QPushButton(), _EventoDeMentira(RuntimeError("objeto C++ já destruído"))) is False
    ruim = types.SimpleNamespace(objectName=lambda: 1 / 0)
    assert filtro.eventFilter(ruim, _EventoDeMentira(5)) is False
    assert [(r, t, n) for _i, r, n, t in anel.ultimos()] == [("SimpleNamespace", 5, "")], "o nome falhou, o evento foi anotado"


class _QtCoreDeMentira:
    def __init__(self, anterior=None):
        self.instalado, self.anterior, self.historico = None, anterior, []

    def qInstallMessageHandler(self, tratador):  # noqa: N802
        antes, self.instalado = self.instalado or self.anterior, tratador
        self.historico.append(tratador)
        return antes


def test_o_tratador_de_mensagens_anota_imprime_e_restaura_o_anterior(monkeypatch):
    erro = _stderr(monkeypatch)
    registro = dq.RegistroDeMensagens(relogio=FakeClock())
    anterior = object()
    qtcore = _QtCoreDeMentira(anterior)
    restaurar = dq.instalar_mensagens_do_qt(registro, qtcore)
    qtcore.instalado(types.SimpleNamespace(name="QtWarningMsg"), None, "QFont::setPointSize: Point size <= 0 (0), must be greater than 0")
    assert [(nivel, texto) for _i, nivel, texto in registro.ultimas()] == [("QtWarningMsg", "QFont::setPointSize: Point size <= 0 (0), must be greater than 0")]
    assert "Point size" in erro.getvalue(), "o Qt continua imprimindo o que imprimia"
    restaurar()
    assert qtcore.historico[-1] is anterior


def test_anexar_qt_liga_eventos_e_mensagens_e_encerrar_desfaz_os_dois(tmp_path, monkeypatch):
    _stderr(monkeypatch)
    vigia, _ = _vigia(tmp_path)
    app, qtcore = _AppDeMentira(), _QtCoreDeMentira("padrao")
    vigia.anexar_qt(app, qobject=_QObjectDeMentira, qtcore=qtcore)
    assert vigia.anel is not None and vigia.mensagens is not None and len(app.filtros) == 1
    app.filtros[0].eventFilter(QPushButton(), _EventoDeMentira(12))
    vigia.marcar("passo 1")
    assert [e[1] for e in vigia.anel.ultimos()] == ["QPushButton", "<marco>"]
    vigia.encerrar()
    assert app.removidos == app.filtros and qtcore.historico[-1] == "padrao"


def test_anexar_qt_que_falha_nao_derruba_o_teste_e_diz_por_que_no_ambiente(tmp_path):
    vigia, _ = _vigia(tmp_path)
    vigia.anexar_qt(_AppDeMentira(recusa=True), qobject=_QObjectDeMentira, qtcore=types.SimpleNamespace())
    assert vigia.anel is None and vigia.mensagens is None
    assert "filtro de eventos não pôde ser instalado" in vigia.ambiente and "tratador de mensagens" in vigia.ambiente
    vigia.marcar("sem anel: não faz nada")


def test_o_vigia_do_modulo_e_unico_por_vez_e_encerrar_atual_o_desliga(tmp_path, monkeypatch):
    monkeypatch.setattr(dq, "faulthandler", types.SimpleNamespace(dump_traceback_later=lambda *a, **k: None,
                                                                  cancel_dump_traceback_later=lambda: None))
    assert dq.atual() is None
    dq.marcar("sem vigia: não faz nada")
    primeiro = dq.iniciar("a", tmp_path / "logs", limite_s=1000)
    try:
        assert dq.atual() is primeiro
        segundo = dq.iniciar("b", tmp_path / "logs", limite_s=1000)
        assert dq.atual() is segundo and primeiro._parar.is_set(), "iniciar o seguinte encerra o anterior"
    finally:
        dq.encerrar_atual()
    assert dq.atual() is None


# ------------------------------------------------------------------------------------------------ o relato ao vivo da falha
def _relato(**campos):
    import conftest
    base = dict(failed=True, nodeid="tests/x.py::t", when="call", longreprtext="E   assert 1 == 2", sections=[])
    base.update(campos)
    saida = io.StringIO()
    stdout, sys.stdout = sys.stdout, saida
    try:
        conftest.pytest_runtest_logreport(types.SimpleNamespace(**base))
    finally:
        sys.stdout = stdout
    return saida.getvalue()


def test_a_falha_e_impressa_na_hora_com_o_detalhe_e_a_saida_capturada():
    texto = _relato(sections=[("Captured stderr call", "QFont::setPointSize: aviso do Qt"), ("Captured stdout call", "   ")])
    assert "FALHOU: tests/x.py::t (call)" in texto and "assert 1 == 2" in texto
    assert "Captured stderr call" in texto and "aviso do Qt" in texto
    assert "Captured stdout call" not in texto, "seção vazia não entra"


def test_o_que_nao_falhou_nao_e_impresso():
    assert _relato(failed=False) == ""


def test_um_defeito_no_relato_nunca_levanta_para_nao_esconder_a_falha_do_teste():
    import conftest

    class Quebrado:
        failed, nodeid, when, sections = True, "tests/x.py::t", "call", []

        @property
        def longreprtext(self):
            raise RuntimeError("defeito ao formatar a falha")

    conftest.pytest_runtest_logreport(Quebrado())   # não levanta


# ------------------------------------------------------------------------------------------------ auxiliares de janela
class _AppQueConta:
    def __init__(self):
        self.passadas = 0

    def processEvents(self):  # noqa: N802
        self.passadas += 1


def test_processar_eventos_faz_no_minimo_duas_passadas_mesmo_com_zero_ms():
    app, marcos = _AppQueConta(), []
    assert gh.processar_eventos(0, app=app, relogio=FakeClock(), dormir=lambda _s: None, marcar=marcos.append) == 2
    assert app.passadas == 2 and marcos == ["processEvents, passada 1", "processEvents, passada 2"]


def test_processar_eventos_termina_por_tempo_e_nao_por_ficar_sem_eventos():
    relogio, app = FakeClock(), _AppQueConta()
    passadas = gh.processar_eventos(50, app=app, relogio=relogio, dormir=relogio.sleep, marcar=lambda _t: None)
    assert passadas == app.passadas >= 25 and relogio.monotonic() >= 0.05
    assert relogio.monotonic() < 0.06, "não passa muito do pedido"


def test_processar_eventos_sem_aplicacao_do_qt_nao_faz_nada(monkeypatch):
    monkeypatch.setattr(gh, "ensure_qapp", lambda: None)
    assert gh.processar_eventos(10, relogio=FakeClock(), dormir=lambda _s: None) == 0


def test_esvaziar_a_fila_processa_executa_os_deletelater_e_processa_de_novo():
    ordem = []

    class App:
        def processEvents(self):  # noqa: N802
            ordem.append("processa")

    gh.esvaziar_fila(App(), enviar_exclusoes=lambda: ordem.append("exclui"), relogio=FakeClock(), dormir=lambda _s: None)
    assert ordem == ["processa", "processa", "exclui", "processa", "processa"]


def test_esvaziar_a_fila_tolera_um_qt_que_recusa_a_exclusao_e_nao_faz_nada_sem_aplicacao(monkeypatch):
    def recusa():
        raise TypeError("esta versão do Qt não aceita")

    app = _AppQueConta()
    gh.esvaziar_fila(app, enviar_exclusoes=recusa, relogio=FakeClock(), dormir=lambda _s: None)
    assert app.passadas == 4
    monkeypatch.setattr(gh, "ensure_qapp", lambda: None)
    gh.esvaziar_fila(None, enviar_exclusoes=recusa)   # não levanta


class _JanelaDeMentira:
    def __init__(self, ordem, nome):
        self.ordem, self.nome = ordem, nome
        self._ui_refresh_timer = types.SimpleNamespace(stop=lambda: ordem.append(f"{nome}: para o relógio"))
        self.engine = types.SimpleNamespace(emergency_stop=lambda: ordem.append(f"{nome}: para o motor"))

    def close(self):
        self.ordem.append(f"{self.nome}: fecha")

    def deleteLater(self):  # noqa: N802
        self.ordem.append(f"{self.nome}: deleteLater")


def test_descartar_janelas_para_fecha_destroi_esvazia_a_fila_e_coleta_o_lixo(monkeypatch):
    ordem = []
    monkeypatch.setattr(gh, "esvaziar_fila", lambda app=None, **kw: ordem.append("esvazia a fila"))
    janelas = [_JanelaDeMentira(ordem, "A"), _JanelaDeMentira(ordem, "B")]
    gh.descartar_janelas(janelas, coletar=lambda: ordem.append("gc"))
    assert ordem == ["A: para o relógio", "A: para o motor", "A: fecha", "B: para o relógio", "B: para o motor", "B: fecha",
                     "A: deleteLater", "B: deleteLater", "esvazia a fila", "gc"]
    assert janelas == [], "a lista é esvaziada: o teste não guarda referência às janelas destruídas"


# ------------------------------------------------------------------------------------------------ a fixture `gui` e o vigia
def test_a_fixture_gui_liga_o_vigia_do_teste_de_janela(gui):
    vigia = dq.atual()
    assert vigia is not None and not vigia.disparou


def test_depois_de_um_teste_de_janela_o_vigia_esta_desligado():
    # Este teste vem logo DEPOIS do anterior (vale a ordem do arquivo, no pytest e no executor mínimo). Um vigia que
    # sobrasse armado mataria o processo (código 86) no meio de um teste qualquer, 60 s depois do último teste de janela.
    assert dq.atual() is None
