"""Atalho para rodar a suíte de testes. É o que o Rodar_Testes.bat chama, mas funciona em qualquer sistema:

    py tests/testsupport/rodar_testes.py [modo] [argumentos extras para o pytest]

Modos:
    rapido       só a lógica (Qt de mentira, não precisa do PySide6): cerca de 15 s
    completo     tudo, com o PySide6 de verdade se estiver instalado (padrão). Com o PySide6, os testes da janela principal
                 (marcador `isolado`) rodam UM POR PROCESSO, cada um com tempo limite: um travamento do Qt reprova só aquele
                 teste e a rodada continua (a rodada de 18/10/2026 parou inteira num deles)
    windows      e2e NO WINDOWS DE VERDADE: ENVIA teclado e mouse de verdade (pede confirmação)
    repetir [N]  roda a suíte N vezes seguidas (padrão 10) para achar teste instável
    cobertura    mede a cobertura de linhas e de ramos do pacote (precisa do `coverage`) e confere a catraca: a cobertura
                 de cada parte não pode cair em relação a tests/coverage_baseline.json (gravado na primeira rodada)
    mutacoes     planta defeitos de propósito e confere que os testes os pegam (cerca de 45 min; `--retomar` continua se parar)
    instalar     instala o que falta para os testes completos: pytest, pytest-timeout e coverage (precisa de internet)
    ajuda        mostra isto

Tudo o que vem depois do modo vai para o executor de testes (ex.: `completo -k atalho -x`). A saída também é gravada em
logs/ (tests_last_run.txt; no pytest também tests_last_run.xml). Sem o pytest instalado usa o executor mínimo do projeto.

No fim há um RESUMO (o que passou, o que falhou, o que travou). Uma falha é impressa NA HORA, não só no fim. Se algum teste
travar, o relatório fica em logs/travamento_qt.txt (testsupport/diagnostico_qt.py): é o arquivo a me enviar.
"""
from __future__ import annotations

import dataclasses
import importlib.metadata
import importlib.util
import os
import pathlib
import re
import subprocess
import sys
import threading
import time

try:
    from testsupport import diagnostico_qt as diag
except ImportError:  # rodando como script: a pasta deste arquivo (e não a tests/) é a primeira do sys.path
    import diagnostico_qt as diag

RAIZ = pathlib.Path(__file__).resolve().parents[2]
MODOS = ("rapido", "completo", "windows", "repetir", "cobertura", "mutacoes", "instalar", "ajuda")
LIMITE_ISOLADO_S = 120        # tempo máximo de UM teste isolado (o vigia de dentro do teste dispara antes, aos 60 s)
TENTATIVAS_DE_RETOMADA = 3    # quantas vezes roda de novo, sem o teste que travou, antes de desistir
LIMITE_DE_TRAVAMENTOS_SEGUIDOS = 3   # o passo isolado desiste dos testes que faltam depois de tantos travamentos SEGUIDOS
LIMITE_DA_COLETA_S = 180
AVISO_WINDOWS = """
============================================================
  TESTE NO WINDOWS DE VERDADE (cerca de 15 segundos)
============================================================
  Este teste ENVIA teclado e mouse de verdade ao Windows.
  Ele abre uma janela própria, traz para a frente e só envia
  entrada depois de confirmar que ela está em primeiro plano;
  se outro programa tomar o foco, o teste é PULADO.

  Durante a rodada NÃO MEXA no teclado nem no mouse.
  Feche programas importantes antes de começar.
============================================================
"""


@dataclasses.dataclass
class PassoIsolado:
    """Roda cada teste marcado como `isolado` num processo só dele, com tempo limite.

    `comando` é o executor SEM seleção de testes (o nodeid entra no fim); `coleta` lista os testes, uma linha
    `caminho::nome` por teste. Um travamento ou uma queda do Qt reprova ESSE teste; os outros seguem."""
    comando: list
    coleta: list
    limite_s: int = LIMITE_ISOLADO_S
    titulo: str = "janela principal, um processo por teste"


@dataclasses.dataclass
class Plano:
    passos: list = dataclasses.field(default_factory=list)  # um passo é uma lista de argumentos ou um PassoIsolado
    env: dict = dataclasses.field(default_factory=dict)
    log: str = "tests_last_run.txt"
    descricao: str = ""
    avisos: list = dataclasses.field(default_factory=list)
    confirmar: str = ""   # texto mostrado antes de pedir a confirmação ("" = não pede)
    erro: str = ""        # o modo não pode rodar aqui (mensagem)
    apagar_antes: list = dataclasses.field(default_factory=list)  # padrões (glob) relativos à raiz, apagados antes de começar


@dataclasses.dataclass
class ResultadoDePasso:
    titulo: str
    estado: str                                        # OK, FALHOU, TRAVOU ou VAZIO
    resumo: str = ""
    detalhes: list = dataclasses.field(default_factory=list)


def ha_modulo(nome: str) -> bool:
    return importlib.util.find_spec(nome) is not None


def versao(pacote: str) -> str:
    try:
        return importlib.metadata.version(pacote)
    except importlib.metadata.PackageNotFoundError:
        return "?"


def comando_do_executor(extras: list[str], *, tem_pytest: bool, tem_timeout: bool, junit: bool = True,
                        raiz: pathlib.Path = RAIZ, timeout_s: int = 180) -> list[str]:
    """O executor de testes: pytest se houver, senão o executor mínimo que acompanha o projeto.

    `--tb=line`: a falha completa já foi impressa NA HORA pelo conftest.py (pytest_runtest_logreport); no fim sobra só a
    linha de cada uma."""
    if tem_pytest:
        comando = [sys.executable, "-m", "pytest", "-q", "-o", "cache_dir=logs/.pytest_cache", "--tb=line"]
        if tem_timeout:
            comando.append(f"--timeout={timeout_s}")
        if junit:
            comando.append("--junitxml=logs/tests_last_run.xml")
        return comando + list(extras)
    return [sys.executable, str(raiz / "tests" / "testsupport" / "run_minimal.py"), "-q"] + list(extras)


def combinar_marcador(extras: list[str], expressao: str) -> list[str]:
    """Acrescenta a seleção `-m <expressao>` aos argumentos. Um `-m` que o usuário já tenha passado é PRESERVADO: vira
    `(dele) and (nossa)`. (Com dois `-m` o pytest só vale o último: um `-m "not slow"` do usuário derrubaria a nossa
    seleção e o passo isolado tentaria rodar a suíte inteira, um teste por processo.)"""
    saida: list[str] = []
    achou = False
    i = 0
    while i < len(extras):
        atual = extras[i]
        if atual == "-m" and i + 1 < len(extras):
            saida += ["-m", f"({extras[i + 1]}) and ({expressao})"]
            achou = True
            i += 2
            continue
        if atual.startswith("-m") and not atual.startswith("--") and len(atual) > 2:
            saida += ["-m", f"({atual[2:]}) and ({expressao})"]
            achou = True
            i += 1
            continue
        saida.append(atual)
        i += 1
    if not achou:
        saida += ["-m", expressao]
    return saida


def montar_plano(modo: str, extras: list[str], *, ambiente: dict | None = None, tem=ha_modulo,
                 sistema: str | None = None, raiz: pathlib.Path = RAIZ) -> Plano:
    """O que rodar, com que variáveis de ambiente e onde gravar o log. Função pura: não executa nada."""
    sistema = sistema or sys.platform
    env = dict(os.environ if ambiente is None else ambiente)
    env.setdefault("PYTHONUTF8", "1")
    env["PYTHONIOENCODING"] = "utf-8"
    for nome in ("AS_ROOT", "AS_ALLOW_REAL_INPUT", "AS_ATUALIZAR_GOLDEN", "AS_MUTACAO_EM_CURSO"):
        env.pop(nome, None)  # só o modo `windows` liga a entrada real; o resto nunca herda isso do terminal
    plano = Plano(env=env)
    extras = list(extras)
    tem_pytest, tem_timeout = tem("pytest"), tem("pytest_timeout")
    if not tem_pytest:
        plano.avisos.append("pytest não está instalado: usando o executor mínimo do projeto. "
                            "Para o pytest de verdade: py -m pip install -r requirements-dev.txt")

    def executor(args, **kw):
        return comando_do_executor(args, tem_pytest=tem_pytest, tem_timeout=tem_timeout, raiz=raiz, **kw)

    if modo in ("rapido", "completo", "repetir", "cobertura"):
        if modo == "rapido":
            env["AS_TEST_QT_STUB"] = "1"
            plano.descricao = "só a lógica (Qt de mentira); os testes de interface são pulados"
        elif tem("PySide6"):
            env.pop("AS_TEST_QT_STUB", None)
            plano.descricao = f"suíte completa com o PySide6 {versao('PySide6')} de verdade"
        else:
            env["AS_TEST_QT_STUB"] = "widgets"
            plano.descricao = "suíte completa com o dublê de widgets (o PySide6 não está instalado)"
            plano.avisos.append("PySide6 não está instalado: os testes da janela principal serão pulados.")
        # Os testes marcados `isolado` (janela principal) rodam um por processo. Só faz sentido com o Qt de verdade e o
        # pytest (o executor mínimo não seleciona por nodeid); sem o PySide6 eles são pulados de qualquer jeito.
        isolar = modo != "rapido" and tem_pytest and tem("PySide6")
        selecionados = combinar_marcador(extras, "not isolado") if isolar else extras
        coleta = [sys.executable, "-m", "pytest", "-q", "-o", "cache_dir=logs/.pytest_cache", "--collect-only"] + combinar_marcador(extras, "isolado")
        plano.apagar_antes = [f"logs/{diag.ARQUIVO_DO_RELATORIO}", f"logs/{diag.ARQUIVO_DO_ALARME_NATIVO}"]
        if isolar:
            plano.descricao += "; a janela principal roda um teste por processo, com tempo limite"
        if modo == "cobertura":
            if not tem("coverage"):
                plano.erro = "o `coverage` não está instalado. Rode: py -m pip install -r requirements-dev.txt"
                return plano
            env["COVERAGE_FILE"] = str(raiz / "logs" / ".coverage")
            # `-p`: cada processo grava o seu arquivo de dados (.coverage.<máquina>.<pid>.<n>) e o `combine` junta todos.
            cobrir = [sys.executable, "-m", "coverage", "run", "-p", "--branch", "--source=automationstudio"]
            base = (cobrir + ["-m", "pytest", "-q", "-o", "cache_dir=logs/.pytest_cache", "--tb=line"] if tem_pytest else
                    cobrir + [str(raiz / "tests" / "testsupport" / "run_minimal.py"), "-q"])
            plano.passos = [base + selecionados]
            if isolar:
                plano.passos.append(PassoIsolado(comando=base, coleta=coleta))
            plano.passos += [[sys.executable, "-m", "coverage", "combine"], [sys.executable, "-m", "coverage", "report", "-m"]]
            plano.apagar_antes += ["logs/.coverage*", "logs/coverage.json"]
            plano.descricao += "; medindo a cobertura de linhas e de ramos"
            if extras:
                plano.avisos.append("com argumentos extras a medição é parcial: a catraca de cobertura não roda.")
            else:
                relatorio_json = raiz / "logs" / "coverage.json"
                plano.passos += [[sys.executable, "-m", "coverage", "json", "-o", str(relatorio_json)],
                                 [sys.executable, str(raiz / "tests" / "testsupport" / "catraca_cobertura.py"), "--json", str(relatorio_json)]]
                plano.descricao += " e conferindo a catraca (a cobertura de cada parte não pode cair)"
            plano.log = "coverage_last_run.txt"
        else:
            plano.passos = [executor(selecionados)]
            if isolar:
                plano.passos.append(PassoIsolado(
                    comando=executor([], junit=False, timeout_s=LIMITE_ISOLADO_S - 30), coleta=coleta))
    elif modo == "windows":
        if sistema != "win32":
            plano.erro = "este modo só funciona no Windows (ele usa o SendInput do Windows de verdade)."
            return plano
        env.pop("AS_TEST_QT_STUB", None)
        env["AS_ALLOW_REAL_INPUT"] = "1"
        plano.passos = [executor(["tests/e2e_windows"] + extras, junit=False, timeout_s=120)]
        plano.log = "tests_windows_last_run.txt"
        plano.descricao = "e2e no Windows de verdade (entrada real)"
        plano.confirmar = AVISO_WINDOWS
    elif modo == "mutacoes":
        plano.passos = [[sys.executable, str(raiz / "tests" / "testsupport" / "mutacoes.py")] + extras]
        plano.log = "mutacoes_last_run_console.txt"
        plano.descricao = "verificador de mutações (planta defeitos de propósito e confere que a suíte os pega)"
    elif modo == "instalar":
        plano.passos = [[sys.executable, "-m", "pip", "install", "-r", "requirements-dev.txt"] + extras]
        plano.log = "instalar_last_run.txt"
        plano.descricao = "instalando as dependências de teste (requirements-dev.txt)"
        plano.avisos = [aviso for aviso in plano.avisos if "pytest não está instalado" not in aviso]
    else:
        plano.erro = f"modo desconhecido: {modo!r}. Modos: {', '.join(MODOS)}"
    return plano


def interpretar_argumentos(argv: list[str]) -> tuple[str, list[str], dict]:
    """(modo, extras, opções). `repetir 20` vira vezes=20; `--sim` pula a confirmação do modo windows."""
    argv = list(argv)
    opcoes = {"sim": False, "vezes": 10}
    if argv and argv[0].lower() in ("-h", "--help", "-?", "/?", "help", "?"):
        return "ajuda", [], opcoes
    modo = argv.pop(0).lower() if argv and not argv[0].startswith("-") else "completo"
    if "--sim" in argv:
        argv.remove("--sim")
        opcoes["sim"] = True
    if modo == "repetir" and argv and argv[0].isdigit():
        opcoes["vezes"] = max(1, int(argv.pop(0)))
    return modo, argv, opcoes


# ------------------------------------------------------------------------------------------------ classificação
_RESUMO_DO_PYTEST = re.compile(r"((\d+ (passed|failed|skipped|errors?|xfailed|xpassed|deselected|warnings?))|no tests ran).* in [\d.]+s")
_ID_DE_TESTE = re.compile(r"^\S+\.py::\S.*$")


def ultima_linha_de_resumo(linhas: list[str]) -> str:
    """A última linha de resumo do pytest ("1353 passed, 31 skipped in 61.2s"), sem os `=` de enfeite; vazia se não houver."""
    for linha in reversed(linhas):
        achado = _RESUMO_DO_PYTEST.search(linha)
        if achado:
            return linha.strip().strip("=").strip()
    return ""


def classificar(codigo: int | None, estourou: bool, deixou_relatorio: bool, linhas: list[str]) -> str:
    """OK, PULADO, FALHOU, TRAVOU ou QUEDA para a execução de UM teste isolado.

    TRAVOU: passou do tempo (o lançador matou), saiu com o código do vigia (86) ou deixou relatório de travamento.
    QUEDA: o processo morreu sem falha de teste (código estranho, como o 0xC0000005 do Windows: o Qt derrubou o Python)."""
    if estourou or deixou_relatorio or codigo == diag.CODIGO_DE_TRAVAMENTO:
        return "TRAVOU"
    if codigo == 0:
        resumo = ultima_linha_de_resumo(linhas)
        return "PULADO" if resumo and "skipped" in resumo and "passed" not in resumo else "OK"
    if codigo == 1:
        return "FALHOU"
    return "QUEDA"


def montar_resumo(resultados: list[ResultadoDePasso], log: str, codigo: int) -> str:
    """O quadro final da rodada. Função pura."""
    barra = "=" * 60
    linhas = ["", barra, "RESUMO DA RODADA", barra]
    for resultado in resultados:
        linhas.append(f" [{resultado.estado:<6}] {resultado.titulo}" + (f": {resultado.resumo}" if resultado.resumo else ""))
        linhas += [f"             {detalhe}" for detalhe in resultado.detalhes]
    linhas.append(f"Código de saída: {codigo}")
    linhas.append(f"Para me enviar: logs{os.sep}{log}")
    if any(r.estado == "TRAVOU" for r in resultados):
        linhas.append(f"Houve travamento: envie também logs{os.sep}{diag.ARQUIVO_DO_RELATORIO}, se ele existir (últimos eventos do Qt e pilhas).")
    linhas.append(barra)
    return "\n".join(linhas)


# ------------------------------------------------------------------------------------------------ execução
def _tamanho(caminho: pathlib.Path) -> int:
    try:
        return caminho.stat().st_size
    except OSError:
        return 0


def _rodar(comando: list, raiz: pathlib.Path, env: dict, arquivo, limite_s: float | None = None) -> tuple[int, list[str], bool]:
    """Roda `comando` mostrando a saída AO VIVO e gravando no log. Devolve (código, linhas, estourou_o_tempo).
    Com `limite_s`, o processo é encerrado à força quando o tempo acaba."""
    estourou = threading.Event()
    linhas: list[str] = []
    with subprocess.Popen([str(parte) for parte in comando], cwd=raiz, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, encoding="utf-8", errors="replace") as processo:
        temporizador = None
        if limite_s:
            def matar() -> None:
                estourou.set()
                try:
                    processo.kill()
                except OSError:
                    pass

            temporizador = threading.Timer(limite_s, matar)
            temporizador.daemon = True
            temporizador.start()
        try:
            for linha in processo.stdout:
                print(linha, end="", flush=True)
                arquivo.write(linha)
                arquivo.flush()
                linhas.append(linha.rstrip("\n"))
            codigo = processo.wait()
        finally:
            if temporizador is not None:
                temporizador.cancel()
    return codigo, linhas, estourou.is_set()


def _recolher_relatorios(raiz: pathlib.Path, tamanho_antes: int) -> str:
    """O texto NOVO do relatório de travamento desde `tamanho_antes` ("" se não houve). Se o alarme NATIVO disparou, o
    arquivo dele é anexado ao relatório e apagado: o próximo teste o recria."""
    relatorio = raiz / "logs" / diag.ARQUIVO_DO_RELATORIO
    nativo = raiz / "logs" / diag.ARQUIVO_DO_ALARME_NATIVO
    if _tamanho(nativo):
        try:
            texto = nativo.read_text(encoding="utf-8", errors="replace")
            with open(relatorio, "a", encoding="utf-8") as saida:
                saida.write("\n" + "=" * 78 + "\nALARME NATIVO (a thread do vigia não conseguiu rodar: provável impasse entre o GIL e o Qt)\n"
                            + "=" * 78 + "\n" + texto + "\n")
            nativo.unlink()
        except OSError:
            pass
    if _tamanho(relatorio) <= tamanho_antes:
        return ""
    with open(relatorio, "r", encoding="utf-8", errors="replace") as entrada:
        entrada.seek(tamanho_antes)
        return entrada.read()


def _apagar_antes(plano: Plano, raiz: pathlib.Path) -> None:
    for padrao in plano.apagar_antes:
        for caminho in raiz.glob(padrao):
            try:
                caminho.unlink()
            except OSError:
                pass


def executar_comum(comando: list, raiz: pathlib.Path, env: dict, arquivo) -> tuple[int, list[str], list[str]]:
    """Um passo comum. Se um teste TRAVAR dentro dele (o vigia grava o relatório e encerra o processo), roda de novo SEM esse
    teste, até `TENTATIVAS_DE_RETOMADA` vezes: um travamento não pode esconder os testes que viriam depois dele.
    Devolve (código, linhas da última rodada, testes que travaram)."""
    travados: list[str] = []
    adicionais: list[str] = []
    relatorio = raiz / "logs" / diag.ARQUIVO_DO_RELATORIO
    for tentativa in range(TENTATIVAS_DE_RETOMADA + 1):
        antes = _tamanho(relatorio)
        codigo, linhas, _estourou = _rodar(comando + adicionais, raiz, env, arquivo)
        novo = _recolher_relatorios(raiz, antes)
        if not novo:
            break
        nodeid = diag.teste_que_travou(novo)
        travados.append(nodeid or "(teste desconhecido)")
        if not nodeid or "pytest" not in comando or tentativa == TENTATIVAS_DE_RETOMADA:
            break
        mensagem = f"\n>>> O teste {nodeid} TRAVOU (relatório em logs{os.sep}{diag.ARQUIVO_DO_RELATORIO}). Rodando de novo, sem ele...\n"
        print(mensagem, flush=True)
        arquivo.write(mensagem)
        adicionais += ["--deselect", nodeid]
    if travados and codigo == 0:
        codigo = diag.CODIGO_DE_TRAVAMENTO   # o que sobrou passou, mas houve travamento: a rodada NÃO está limpa
    return codigo, linhas, travados


def executar_isolado(passo: PassoIsolado, raiz: pathlib.Path, env: dict, arquivo) -> tuple[int, list[dict]]:
    """Roda cada teste do passo num processo próprio. Devolve (código, um registro por teste)."""
    cabecalho = f"\n--- {passo.titulo} ---"
    print(cabecalho, flush=True)
    arquivo.write(cabecalho + "\n")
    codigo, linhas, estourou = _rodar(passo.coleta, raiz, env, arquivo, LIMITE_DA_COLETA_S)
    ids = [linha.strip() for linha in linhas if _ID_DE_TESTE.match(linha.strip())]
    if not ids:
        if codigo not in (0, 5) or estourou:
            return codigo or 1, [{"nodeid": "(coleta)", "estado": "FALHOU", "segundos": 0.0}]
        mensagem = "Nenhum teste isolado para rodar."
        print(mensagem, flush=True)
        arquivo.write(mensagem + "\n")
        return 0, []
    registros: list[dict] = []
    seguidos = 0
    relatorio = raiz / "logs" / diag.ARQUIVO_DO_RELATORIO
    for numero, nodeid in enumerate(ids, 1):
        titulo = f"\n[{numero}/{len(ids)}] {nodeid}"
        print(titulo, flush=True)
        arquivo.write(titulo + "\n")
        antes = _tamanho(relatorio)
        inicio = time.monotonic()
        codigo_do_teste, saida, estourou = _rodar(passo.comando + [nodeid], raiz, env, arquivo, passo.limite_s)
        segundos = time.monotonic() - inicio
        deixou_relatorio = bool(_recolher_relatorios(raiz, antes))
        estado = classificar(codigo_do_teste, estourou, deixou_relatorio, saida)
        registros.append({"nodeid": nodeid, "estado": estado, "segundos": segundos, "codigo": codigo_do_teste})
        linha = f"      -> {estado} ({segundos:.1f} s)" + (f" [código {codigo_do_teste}]" if estado == "QUEDA" else "")
        print(linha, flush=True)
        arquivo.write(linha + "\n")
        seguidos = seguidos + 1 if estado == "TRAVOU" else 0
        if seguidos >= LIMITE_DE_TRAVAMENTOS_SEGUIDOS and numero < len(ids):
            # Se o Qt trava em todo teste de janela, esperar o tempo limite de cada um dos que faltam só gasta o seu tempo:
            # o relatório do primeiro travamento já diz o que o Qt fazia.
            restantes = ids[numero:]
            aviso = (f"\n>>> {seguidos} travamentos seguidos: o passo isolado parou aqui e {len(restantes)} testes NÃO RODARAM. "
                     f"O relatório do travamento (logs{os.sep}{diag.ARQUIVO_DO_RELATORIO}, se existir) diz o que o Qt fazia; para rodar um dos que "
                     "faltam, use `Rodar_Testes.bat completo -k <parte do nome>`.")
            print(aviso, flush=True)
            arquivo.write(aviso + "\n")
            registros += [{"nodeid": restante, "estado": "NAO_RODOU", "segundos": 0.0, "codigo": None} for restante in restantes]
            break
    ruins = [r for r in registros if r["estado"] not in ("OK", "PULADO")]
    if not ruins:
        return 0, registros
    # Como no passo comum, uma falha (1) vale mais do que um travamento (86), seja qual for a ordem: o RESUMO lista os dois.
    so_travamentos = all(r["estado"] in ("TRAVOU", "NAO_RODOU") for r in ruins)
    return (diag.CODIGO_DE_TRAVAMENTO if so_travamentos else 1), registros


def _resultado_do_isolado(passo: PassoIsolado, registros: list[dict]) -> ResultadoDePasso:
    contagem = {estado: sum(1 for r in registros if r["estado"] == estado) for estado in ("OK", "PULADO", "FALHOU", "TRAVOU", "QUEDA", "NAO_RODOU")}
    rotulos = {"NAO_RODOU": "NÃO RODOU"}
    partes = [f"{contagem['OK']} OK"] + [f"{contagem[e]} {rotulos.get(e, e)}" for e in ("PULADO", "FALHOU", "TRAVOU", "QUEDA", "NAO_RODOU") if contagem[e]]
    ruins = [r for r in registros if r["estado"] not in ("OK", "PULADO")]
    estado = "OK" if not ruins else ("TRAVOU" if any(r["estado"] == "TRAVOU" for r in ruins) else "FALHOU")
    detalhes = [f"{r['estado']:<7} {r['nodeid']}  ({r['segundos']:.1f} s)" for r in ruins if r["estado"] != "NAO_RODOU"]
    if contagem["NAO_RODOU"]:
        detalhes.append(f"{contagem['NAO_RODOU']} testes NÃO RODARAM: o passo parou depois de {LIMITE_DE_TRAVAMENTOS_SEGUIDOS} travamentos seguidos")
    resumo = (", ".join(partes) + f" (de {len(registros)})") if registros else "nenhum teste isolado"
    return ResultadoDePasso(passo.titulo, estado if registros else "VAZIO", resumo, detalhes)


def executar_passos(plano: Plano, raiz: pathlib.Path = RAIZ) -> int:
    """Roda os passos mostrando a saída ao vivo e gravando em logs/. Devolve o código de saída do primeiro passo que falhar.

    Um passo comum que trave (relatório do vigia) é repetido sem o teste que travou; um passo isolado roda um teste por
    processo. No fim, imprime o RESUMO. O código 5 do pytest (nenhum teste coletado) só conta como falha se NENHUM passo
    rodou algum teste: um `-k` que só casa com testes isolados deixa o passo comum vazio."""
    logs = raiz / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    _apagar_antes(plano, raiz)
    codigo = 0
    resultados: list[ResultadoDePasso] = []
    rodou_algum_teste: list[bool] = []   # um item por passo que roda testes
    with open(logs / plano.log, "w", encoding="utf-8") as arquivo:
        for passo in plano.passos:
            if isinstance(passo, PassoIsolado):
                codigo_do_passo, registros = executar_isolado(passo, raiz, plano.env, arquivo)
                resultados.append(_resultado_do_isolado(passo, registros))
                rodou_algum_teste.append(bool(registros))
            else:
                codigo_do_passo, linhas, travados = executar_comum(passo, raiz, plano.env, arquivo)
                vazio = "pytest" in passo and codigo_do_passo == 5
                if "pytest" in passo or "run_minimal.py" in " ".join(str(p) for p in passo):
                    rodou_algum_teste.append(not vazio)
                if vazio:
                    codigo_do_passo = 0
                estado = "TRAVOU" if travados else ("VAZIO" if vazio else ("OK" if codigo_do_passo == 0 else "FALHOU"))
                resultados.append(ResultadoDePasso(_titulo_do_passo(passo), estado, ultima_linha_de_resumo(linhas),
                                                   [f"TRAVOU  {nodeid}" for nodeid in travados]))
            codigo = codigo or codigo_do_passo
        if codigo == 0 and rodou_algum_teste and not any(rodou_algum_teste):
            codigo = 5   # nada rodou em lugar nenhum
        texto = montar_resumo(resultados, plano.log, codigo)
        print(texto, flush=True)
        arquivo.write(texto + "\n")
    print(f"\nLog gravado em logs{os.sep}{plano.log}")
    return codigo


def _titulo_do_passo(passo: list) -> str:
    """Um nome curto para o resumo."""
    partes = [str(p) for p in passo]
    if "pytest" in partes:
        return "testes comuns (sem os da janela principal)" if any("not isolado" in p for p in partes) else "testes"
    if "coverage" in partes:
        resto = [p for p in partes[partes.index("coverage") + 1:] if not p.startswith("-")]
        return "cobertura: " + (resto[0] if resto else "")
    if "pip" in partes:
        return "instalação das dependências"
    return pathlib.Path(partes[1]).name if len(partes) > 1 else (partes[0] if partes else "passo")


def principal(argv: list[str] | None = None) -> int:
    for fluxo in (sys.stdout, sys.stderr):  # o console redirecionado usa cp1252 e o resumo tem acento e símbolos
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass
    modo, extras, opcoes = interpretar_argumentos(sys.argv[1:] if argv is None else argv)
    if modo == "ajuda":
        print(__doc__)
        return 0
    plano = montar_plano(modo, extras)
    if plano.erro:
        print("Não dá para rodar:", plano.erro)
        return 2
    print(f"Python {sys.version.split()[0]} — pytest {versao('pytest') if ha_modulo('pytest') else 'não instalado'} — modo {modo}: {plano.descricao}")
    print(f"Sistema: {sys.platform}; pytest-timeout: {'sim' if ha_modulo('pytest_timeout') else 'não'}; "
          f"PySide6: {versao('PySide6') if ha_modulo('PySide6') else 'não'}; pasta: {RAIZ}")
    for aviso in plano.avisos:
        print("AVISO:", aviso)
    if plano.confirmar and not opcoes["sim"]:
        print(plano.confirmar)
        try:
            resposta = input("Digite SIM e aperte Enter para começar (qualquer outra coisa cancela): ")
        except EOFError:
            resposta = ""
        if resposta.strip().upper() != "SIM":
            print("Cancelado: nada foi enviado ao Windows.")
            return 2
    if modo == "repetir":
        inicio = time.monotonic()
        for n in range(1, opcoes["vezes"] + 1):
            print(f"\n===== rodada {n} de {opcoes['vezes']} =====", flush=True)
            codigo = executar_passos(plano)
            if codigo:
                print(f"\nFALHOU na rodada {n}: teste instável ou defeito. Veja logs{os.sep}{plano.log}")
                return codigo
        print(f"\nOK: {opcoes['vezes']} rodadas seguidas sem falha em {time.monotonic() - inicio:.0f} s")
        return 0
    return executar_passos(plano)


if __name__ == "__main__":
    sys.exit(principal())
