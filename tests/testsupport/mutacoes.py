"""Verificador de mutações: prova que a suíte de testes PEGA defeitos de verdade.

Uma suíte verde só diz que o código atual passa. Não diz que os testes enxergariam um defeito. Este verificador planta,
um de cada vez e numa CÓPIA do projeto, defeitos parecidos com os que já apareceram (ou que poderiam aparecer) e roda a
suíte inteira contra cada cópia. Um defeito que a suíte pega é "morto"; um que passa despercebido "sobreviveu", e aí o
buraco está nos testes: é preciso escrever o teste que o mataria (ou documentar por que o defeito é inofensivo).

    py tests/testsupport/mutacoes.py --validar         # só confere que cada defeito ainda se aplica ao código (rápido)
    py tests/testsupport/mutacoes.py --listar          # lista os defeitos
    py tests/testsupport/mutacoes.py                   # roda todos (alguns minutos) e grava logs/mutacoes_last_run.txt
    py tests/testsupport/mutacoes.py --so MOT01,GRV08  # só alguns
    py tests/testsupport/mutacoes.py --area gravador   # só uma área
    py tests/testsupport/mutacoes.py --tabela          # tabela em Markdown (para a documentação)
    py tests/testsupport/mutacoes.py --retomar         # continua de onde uma rodada interrompida parou (ver abaixo)

Como funciona e por que dá para confiar:
  * a cópia do projeto é descartável: o código original nunca é tocado;
  * cada defeito é um trecho de texto que precisa aparecer EXATAMENTE o número esperado de vezes: se o código mudar e o
    trecho sumir (ou ficar ambíguo), o defeito é recusado em vez de plantado no lugar errado;
  * o defeito precisa compilar e o pacote precisa importar; senão ele é "inválido" e não conta como morto;
  * "morto" significa: algum teste que PASSAVA na cópia sem defeito passou a FALHAR (compara-se com uma rodada de referência);
  * nunca envia entrada de verdade: AS_ALLOW_REAL_INPUT e AS_ATUALIZAR_GOLDEN são removidos do ambiente das rodadas;
  * a rodada inteira leva cerca de 55 minutos e cada resultado é gravado assim que sai (logs/mutacoes_progresso.jsonl). Se
    ela for interrompida (Ctrl+C, queda de energia, o computador dormiu), `--retomar` continua dali. O progresso só vale
    para o MESMO projeto: ele guarda uma impressão digital de tudo o que as cópias enxergam, e se o código ou os testes
    mudaram desde então a retomada é recusada (misturar resultados de suítes diferentes enganaria).
Defeitos de interface (editor de comandos) rodam com o dublê de widgets. Com AS_MUTACOES_QT_REAL=1 e o PySide6 instalado rodam
com o PySide6 de verdade; não é o padrão porque os testes da janela principal podem travar no Qt de verdade e este verificador
não os isola um por processo (o lançador `Rodar_Testes.bat` isola).
"""
from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import datetime
import fnmatch
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
import warnings
from typing import Callable

RAIZ_PADRAO = pathlib.Path(__file__).resolve().parents[2]
LOGICA, INTERFACE = "logica", "interface"
LIMITE_POR_RODADA_S = 900  # uma rodada que passa disso é considerada travada (o defeito travou o motor)
IGNORAR_NA_COPIA = ("__pycache__", "logs", ".git", ".pytest_cache", "*.pyc", "*.zip", "*.db", "*.db-wal", "*.db-shm")


class ErroDeMutante(Exception):
    """O defeito não pode ser plantado (trecho não encontrado, ambíguo, igual ao original ou código que não compila)."""


@dataclasses.dataclass(frozen=True)
class Mutante:
    id: str
    area: str
    descricao: str            # o defeito plantado
    protege: str              # o que a suíte deveria garantir (achado, decisão ou comportamento)
    arquivo: str              # relativo à raiz do projeto
    antes: str = ""           # trecho exato a trocar...
    depois: str = ""          # ...por este
    ocorrencia: int = 1       # qual ocorrência trocar (1 = a primeira)
    total: int = 1            # quantas vezes `antes` aparece no arquivo (confere-se: protege contra trecho ambíguo)
    acrescentar: str = ""     # alternativa: texto acrescentado ao fim do arquivo
    funcao: Callable | None = None  # alternativa: função texto -> texto (ou bytes -> bytes se `binario`)
    binario: bool = False
    novos_arquivos: tuple = ()  # ((caminho relativo, conteúdo), ...) criados na cópia
    apagar: bool = False      # alternativa: o arquivo é apagado da cópia
    modo: str = LOGICA        # LOGICA (Qt de mentira, só lógica) ou INTERFACE (editor de comandos)


# ------------------------------------------------------------------------------------------------ aplicar um defeito
def _ler(caminho: pathlib.Path) -> tuple[str, str]:
    bruto = caminho.read_bytes().decode("utf-8")
    fim_de_linha = "\r\n" if "\r\n" in bruto else "\n"
    return bruto.replace("\r\n", "\n"), fim_de_linha


def _escrever(caminho: pathlib.Path, texto: str, fim_de_linha: str) -> None:
    caminho.write_bytes(texto.replace("\n", fim_de_linha).encode("utf-8"))


def aplicar_no_texto(texto: str, m: Mutante) -> str:
    """O texto do arquivo com o defeito plantado. Levanta ErroDeMutante se o defeito não pode ser plantado com segurança."""
    if m.funcao is not None:
        novo = m.funcao(texto)
    elif m.acrescentar:
        novo = texto.rstrip("\n") + "\n\n" + m.acrescentar.strip("\n") + "\n"
    else:
        if not m.antes:
            raise ErroDeMutante(f"{m.id}: defeito sem trecho, função nem texto a acrescentar")
        achados = texto.count(m.antes)
        if achados != m.total:
            raise ErroDeMutante(f"{m.id}: o trecho aparece {achados} vez(es) em {m.arquivo}, esperava {m.total}; o código mudou?")
        if not 1 <= m.ocorrencia <= achados:
            raise ErroDeMutante(f"{m.id}: ocorrência {m.ocorrencia} não existe ({achados} no arquivo)")
        posicao = -len(m.antes)
        for _ in range(m.ocorrencia):
            posicao = texto.find(m.antes, posicao + len(m.antes))
        novo = texto[:posicao] + m.depois + texto[posicao + len(m.antes):]
    if novo == texto:
        raise ErroDeMutante(f"{m.id}: o defeito não muda nada no arquivo")
    return novo


def aplicar(raiz: pathlib.Path, m: Mutante) -> None:
    """Planta o defeito na árvore `raiz` (uma cópia!). Confere que o resultado ainda compila."""
    for caminho, conteudo in m.novos_arquivos:
        destino = raiz / caminho
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(conteudo, encoding="utf-8")
    alvo = raiz / m.arquivo
    if m.apagar:
        if not alvo.exists():
            raise ErroDeMutante(f"{m.id}: {m.arquivo} não existe")
        alvo.unlink()
        return
    if m.novos_arquivos and not (m.antes or m.acrescentar or m.funcao):
        return
    if not alvo.exists():
        raise ErroDeMutante(f"{m.id}: {m.arquivo} não existe")
    if m.binario:
        bruto = alvo.read_bytes()
        novo = m.funcao(bruto)
        if novo == bruto:
            raise ErroDeMutante(f"{m.id}: o defeito não muda nada no arquivo")
        alvo.write_bytes(novo)
        return
    texto, fim_de_linha = _ler(alvo)
    novo = aplicar_no_texto(texto, m)
    if alvo.suffix == ".py":
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")  # o defeito EST10 planta de propósito um escape inválido
                compile(novo, str(alvo), "exec")
        except SyntaxError as exc:
            raise ErroDeMutante(f"{m.id}: o código com o defeito não compila: {exc}") from exc
    _escrever(alvo, novo, fim_de_linha)


def validar(raiz: pathlib.Path, catalogo: list[Mutante]) -> list[str]:
    """Problemas do catálogo contra o código em `raiz`, sem rodar nenhum teste. Lista vazia = todo defeito se aplica."""
    problemas, ids = [], set()
    for m in catalogo:
        if m.id in ids:
            problemas.append(f"{m.id}: id repetido")
        ids.add(m.id)
        if m.modo not in (LOGICA, INTERFACE):
            problemas.append(f"{m.id}: modo desconhecido {m.modo!r}")
        with tempfile.TemporaryDirectory(prefix="as_mutval_") as pasta:
            area = pathlib.Path(pasta)
            alvo = raiz / m.arquivo
            if m.apagar or m.novos_arquivos and not (m.antes or m.acrescentar or m.funcao):
                if m.apagar and not alvo.exists():
                    problemas.append(f"{m.id}: {m.arquivo} não existe")
                continue
            if not alvo.exists():
                problemas.append(f"{m.id}: {m.arquivo} não existe")
                continue
            copia = area / alvo.name
            shutil.copy2(alvo, copia)
            try:
                aplicar(area, dataclasses.replace(m, arquivo=alvo.name, novos_arquivos=()))
            except ErroDeMutante as exc:
                problemas.append(str(exc))
    return problemas


# ------------------------------------------------------------------------------------------------ rodar a suíte
def modo_da_interface() -> str:
    """"widgets" (o dublê funcional do editor de comandos) ou "" (o PySide6 de verdade).

    O padrão é o dublê. A rodada de 18/10/2026 no Windows mostrou que um teste da janela principal pode travar no Qt de verdade,
    e este verificador roda a suíte inteira, num processo só e sem o isolamento um-teste-por-processo do lançador, uma vez por
    defeito: o travamento de um teste que nada tem a ver com o defeito faria o defeito parecer "morto". Nenhum defeito do
    catálogo depende da janela principal. Para usar o Qt de verdade: AS_MUTACOES_QT_REAL=1, com o PySide6 instalado."""
    if os.environ.get("AS_MUTACOES_QT_REAL") == "1" and importlib.util.find_spec("PySide6") is not None:
        return ""
    return "widgets"


def ambiente_da_rodada(copia: pathlib.Path, modo: str) -> dict:
    env = dict(os.environ)
    for nome in ("AS_ALLOW_REAL_INPUT", "AS_ATUALIZAR_GOLDEN", "AS_TEST_QT_STUB", "AS_ROOT"):
        env.pop(nome, None)  # nunca enviar entrada de verdade nem regravar referências a partir de uma rodada de defeito
    stub = "1" if modo == LOGICA else modo_da_interface()
    if stub:
        env["AS_TEST_QT_STUB"] = stub
    env.update(AS_ROOT=str(copia), AS_FORCE_MINIMAL_RUNNER="1", AS_MUTACAO_EM_CURSO="1", PYTHONDONTWRITEBYTECODE="1")
    return env


def analisar_saida(saida: str) -> tuple[set[str], dict | None]:
    """(testes que falharam, contagens do RESUMO ou None se a rodada não chegou ao fim) a partir da saída do executor."""
    falhas = {linha[len("FALHOU"):].strip() for linha in saida.splitlines() if linha.startswith("FALHOU ")}
    resumo = re.search(r"RESUMO: (\d+) passou, (\d+) falhou, (\d+) pulado, (\d+) xfail", saida)
    contagens = None
    if resumo:
        contagens = dict(zip(("passou", "falhou", "pulado", "xfail"), map(int, resumo.groups())))
    return falhas, contagens


def importa_sem_erro(copia: pathlib.Path, modo: str) -> str:
    """"" se todos os módulos do pacote ainda importam na cópia com o defeito; senão a mensagem de erro."""
    codigo = (
        "import importlib, os, pathlib, sys\n"
        "raiz = pathlib.Path(sys.argv[1]); modo = sys.argv[2]\n"
        "sys.path[:0] = [str(raiz), str(raiz / 'tests')]\n"
        "if modo == '1': sys.path.insert(0, str(raiz / 'tests' / 'testsupport' / 'qt_stub'))\n"
        "elif modo == 'widgets': sys.path.insert(0, str(raiz / 'tests' / 'testsupport' / 'qt_double'))\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "for arquivo in sorted((raiz / 'automationstudio').glob('*.py')):\n"
        "    if arquivo.stem != '__init__':\n"
        "        importlib.import_module('automationstudio.' + arquivo.stem)\n"
    )
    env = ambiente_da_rodada(copia, modo)
    modo_stub = env.get("AS_TEST_QT_STUB", "")
    try:
        r = subprocess.run([sys.executable, "-c", codigo, str(copia), modo_stub], cwd=copia, env=env,
                           capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return "a importação do pacote travou"
    return "" if r.returncode == 0 else (r.stderr.strip().splitlines() or ["erro desconhecido"])[-1]


def rodar_suite(copia: pathlib.Path, modo: str) -> tuple[set[str], dict | None, bool, str]:
    """(falhas, contagens, travou, final da saída) de uma rodada completa da suíte na cópia."""
    comando = [sys.executable, str(copia / "tests" / "testsupport" / "run_minimal.py"), "-q"]
    try:
        r = subprocess.run(comando, cwd=copia, env=ambiente_da_rodada(copia, modo), capture_output=True, text=True,
                           timeout=LIMITE_POR_RODADA_S, errors="replace")
    except subprocess.TimeoutExpired as exc:
        parcial = (exc.stdout or b"")
        parcial = parcial.decode("utf-8", "replace") if isinstance(parcial, bytes) else parcial
        return set(), None, True, parcial[-400:]
    falhas, contagens = analisar_saida(r.stdout)
    return falhas, contagens, False, (r.stdout + r.stderr)[-400:]


def classificar(falhas: set[str], referencia: set[str], contagens: dict | None, travou: bool) -> tuple[str, list[str]]:
    """("morto" | "sobreviveu" | "invalido", testes que passaram a falhar)."""
    if travou:
        return "morto", ["(a suíte travou: tempo esgotado)"]
    if contagens is None:
        return "invalido", []
    novas = sorted(falhas - referencia)
    return ("morto" if novas else "sobreviveu"), novas


@dataclasses.dataclass
class Resultado:
    mutante: Mutante
    status: str
    mortos_por: list[str]
    detalhe: str = ""
    segundos: float = 0.0


def executar_um(raiz: pathlib.Path, m: Mutante, referencias: dict, manter: bool = False) -> Resultado:
    inicio = time.monotonic()
    pasta = pathlib.Path(tempfile.mkdtemp(prefix=f"as_mut_{m.id}_"))
    copia = pasta / "projeto"
    try:
        shutil.copytree(raiz, copia, ignore=shutil.ignore_patterns(*IGNORAR_NA_COPIA))
        try:
            aplicar(copia, m)
        except ErroDeMutante as exc:
            return Resultado(m, "invalido", [], str(exc), time.monotonic() - inicio)
        erro = importa_sem_erro(copia, m.modo)
        if erro:
            return Resultado(m, "invalido", [], f"o pacote não importa com o defeito: {erro}", time.monotonic() - inicio)
        falhas, contagens, travou, final = rodar_suite(copia, m.modo)
        status, mortos = classificar(falhas, referencias[m.modo]["falhas"], contagens, travou)
        detalhe = final.strip().splitlines()[-1] if status == "invalido" and final.strip() else ""
        return Resultado(m, status, mortos, detalhe, time.monotonic() - inicio)
    finally:
        if manter:
            print(f"  (cópia mantida em {copia})")
        else:
            shutil.rmtree(pasta, ignore_errors=True)


def rodada_de_referencia(raiz: pathlib.Path, modos: set[str]) -> dict:
    """Roda a suíte SEM defeito em cada modo usado: o que já falha ali não conta como defeito detectado."""
    referencias = {}
    for modo in sorted(modos):
        pasta = pathlib.Path(tempfile.mkdtemp(prefix="as_mut_ref_"))
        try:
            copia = pasta / "projeto"
            shutil.copytree(raiz, copia, ignore=shutil.ignore_patterns(*IGNORAR_NA_COPIA))
            falhas, contagens, travou, final = rodar_suite(copia, modo)
            if contagens is None or travou:
                raise SystemExit(f"A rodada de referência ({modo}) não terminou: a suíte sem defeito já está quebrada.\n{final}")
            referencias[modo] = {"falhas": falhas, "contagens": contagens}
        finally:
            shutil.rmtree(pasta, ignore_errors=True)
    return referencias


# ------------------------------------------------------------------------------------------------ progresso (retomada)
class ProgressoDeOutroEstado(Exception):
    """O progresso gravado é de um projeto diferente do atual (código ou testes mudaram)."""


def _ignorado(nome: str) -> bool:
    return any(fnmatch.fnmatch(nome, padrao) for padrao in IGNORAR_NA_COPIA)


def impressao_digital(raiz: pathlib.Path) -> str:
    """Resumo de TUDO o que as cópias enxergam (o mesmo filtro da cópia: sem logs, caches nem bancos).

    Se o código ou os testes mudarem, resultados guardados de uma rodada anterior deixam de valer.
    """
    resumo = hashlib.sha256()
    for pasta, subpastas, arquivos in os.walk(raiz):
        subpastas[:] = sorted(d for d in subpastas if not _ignorado(d))
        for nome in sorted(arquivos):
            if _ignorado(nome):
                continue
            caminho = pathlib.Path(pasta) / nome
            resumo.update(caminho.relative_to(raiz).as_posix().encode("utf-8") + b"\0")
            resumo.update(caminho.read_bytes() + b"\0")
    return resumo.hexdigest()[:16]


def _linha(dados: dict) -> str:
    return json.dumps(dados, ensure_ascii=False, sort_keys=True) + "\n"


def iniciar_progresso(caminho: pathlib.Path, impressao: str, versao: str) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(_linha({"tipo": "cabecalho", "impressao": impressao, "versao": versao}), encoding="utf-8")


def gravar_no_progresso(caminho: pathlib.Path, dados: dict) -> None:
    with open(caminho, "a", encoding="utf-8") as arquivo:
        arquivo.write(_linha(dados))
        arquivo.flush()
        os.fsync(arquivo.fileno())


def dados_do_resultado(r: Resultado) -> dict:
    return {"tipo": "resultado", "id": r.mutante.id, "status": r.status, "mortos_por": list(r.mortos_por),
            "detalhe": r.detalhe, "segundos": r.segundos}


def dados_da_referencia(modo: str, referencia: dict) -> dict:
    return {"tipo": "referencia", "modo": modo, "falhas": sorted(referencia["falhas"]), "contagens": referencia["contagens"]}


def ler_progresso(caminho: pathlib.Path, impressao: str, por_id: dict[str, Mutante]) -> tuple[list[Resultado], dict]:
    """(resultados, referências) gravados para ESTE projeto. Levanta ProgressoDeOutroEstado se o projeto mudou.

    Uma linha cortada no fim (a rodada foi morta no meio da gravação) é ignorada; um defeito que saiu do catálogo também.
    """
    resultados: dict[str, Resultado] = {}
    referencias: dict[str, dict] = {}
    cabecalho = None
    for texto in caminho.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            dados = json.loads(texto)
        except ValueError:
            continue
        if not isinstance(dados, dict):
            continue
        if dados.get("tipo") == "cabecalho":
            cabecalho = dados
        elif dados.get("tipo") == "referencia":
            referencias[dados["modo"]] = {"falhas": set(dados["falhas"]), "contagens": dados["contagens"]}
        elif dados.get("tipo") == "resultado" and dados.get("id") in por_id and dados.get("status") in ("morto", "sobreviveu", "invalido"):
            resultados[dados["id"]] = Resultado(por_id[dados["id"]], dados["status"], list(dados.get("mortos_por", [])),
                                                dados.get("detalhe", ""), float(dados.get("segundos", 0.0)))
    if cabecalho is None or cabecalho.get("impressao") != impressao:
        raise ProgressoDeOutroEstado(f"o progresso em {caminho} é de outro estado do projeto (o código ou os testes mudaram)")
    return list(resultados.values()), referencias


# ------------------------------------------------------------------------------------------------ relatório
def relatorio(resultados: list[Resultado], referencias: dict, segundos: float, versao: str, retomados: int = 0) -> str:
    linhas = [f"VERIFICADOR DE MUTAÇÕES — Automation Studio {versao}",
              f"Data: {datetime.datetime.now().isoformat(timespec='seconds')}   Python: {sys.version.split()[0]}   "
              f"Interface: {'PySide6 de verdade' if modo_da_interface() == '' else 'dublê de widgets'}",
              ""]
    for modo, dados in sorted(referencias.items()):
        c = dados["contagens"]
        linhas.append(f"Referência ({modo}): {c['passou']} passou, {c['falhou']} falhou, {c['pulado']} pulado, {c['xfail']} xfail"
                      + (f"  — já falhavam: {sorted(dados['falhas'])}" if dados["falhas"] else ""))
    if retomados:
        linhas.append(f"Retomada: {retomados} dos {len(resultados)} resultados vieram do progresso gravado (mesmo projeto).")
    linhas.append("")
    ordem = {"sobreviveu": 0, "invalido": 1, "morto": 2}
    for r in sorted(resultados, key=lambda r: (ordem[r.status], r.mutante.id)):
        marca = {"morto": "MORTO     ", "sobreviveu": "SOBREVIVEU ", "invalido": "INVÁLIDO  "}[r.status]
        linhas.append(f"{marca}{r.mutante.id:<8} [{r.mutante.area}] {r.mutante.descricao}  ({r.segundos:.0f}s)")
        if r.status == "morto":
            mostrados = ", ".join(r.mortos_por[:3]) + (f" (+{len(r.mortos_por) - 3})" if len(r.mortos_por) > 3 else "")
            linhas.append(f"            morto por {len(r.mortos_por)} teste(s): {mostrados}")
        elif r.status == "sobreviveu":
            linhas.append(f"            BURACO NA SUÍTE: nenhum teste falhou. Deveria proteger: {r.mutante.protege}")
        else:
            linhas.append(f"            {r.detalhe}")
    mortos = sum(r.status == "morto" for r in resultados)
    vivos = [r for r in resultados if r.status == "sobreviveu"]
    invalidos = [r for r in resultados if r.status == "invalido"]
    validos = mortos + len(vivos)
    linhas += ["", f"RESUMO: {mortos} mortos, {len(vivos)} sobreviveram, {len(invalidos)} inválidos (de {len(resultados)}) "
                   f"— pontuação {100 * mortos / validos:.1f}% dos defeitos válidos pegos em {segundos / 60:.1f} min" if validos else "RESUMO: nada rodou"]
    if vivos:
        linhas.append("SOBREVIVENTES: " + ", ".join(r.mutante.id for r in vivos))
    if invalidos:
        linhas.append("INVÁLIDOS (o catálogo precisa de conserto): " + ", ".join(r.mutante.id for r in invalidos))
    return "\n".join(linhas) + "\n"


def tabela_markdown(catalogo: list[Mutante]) -> str:
    linhas = ["| Id | Área | Defeito plantado | O que a suíte deve garantir |", "|---|---|---|---|"]
    for m in catalogo:
        linhas.append(f"| {m.id} | {m.area} | {m.descricao} | {m.protege} |")
    return "\n".join(linhas) + "\n"


# ------------------------------------------------------------------------------------------------ catálogo
def L(*linhas: str) -> str:
    """Junta linhas com \\n (deixa os trechos de várias linhas legíveis)."""
    return "\n".join(linhas)


def _m(id: str, area: str, descricao: str, protege: str, arquivo: str, antes: str = "", depois: str = "", **resto) -> Mutante:
    return Mutante(id=id, area=area, descricao=descricao, protege=protege, arquivo=arquivo, antes=antes, depois=depois, **resto)


IS = "automationstudio/input_system.py"
CORE = "automationstudio/core.py"
PRJ = "automationstudio/project.py"
EDI = "automationstudio/command_editor.py"
ATV = "automationstudio/ativacao.py"
ATU = "automationstudio/ativacao_ui.py"
JAN = "automationstudio/main_window.py"
CTL = "automationstudio/controle_ui.py"
GOLD = "tests/data/golden/"


def _motor_guardado(texto: str) -> str:
    """O controlador guarda `janela.engine` ao ser criado e passa a usar a cópia (uma referência que ficaria velha)."""
    guardado = texto.replace("        self.janela = janela\n", "        self.janela = janela\n        self._motor = janela.engine\n", 1)
    return guardado.replace("self.janela.engine.", "self._motor.")


def _controle_depois_dos_atalhos(texto: str) -> str:
    """Tira `self.controle = ...` de onde está e o põe logo depois do primeiro `self._register_all_hotkeys()` (o de `__init__`)."""
    criacao = "        self.controle = ControladorDeExecucao(self)\n"
    sem = texto.replace(criacao, "", 1)
    alvo = "        self._register_all_hotkeys()\n"
    i = sem.find(alvo)
    return sem if i < 0 else sem[: i + len(alvo)] + criacao + sem[i + len(alvo):]


def catalogo() -> list[Mutante]:
    c: list[Mutante] = []
    add = c.append

    # ---------------------------------------------------------------------------------------------- motor de execução
    add(_m("MOT01", "motor", "a parada não solta o que a thread do motor enviou depois do stop()", "achado 2.01: parada no meio do envio deixava tecla presa",
           IS, L("            if self._stop_requested.is_set():", "                try:", "                    self._release_all()"),
           L("            if False:", "                try:", "                    self._release_all()")))
    add(_m("MOT02", "motor", "a pausa não congela o relógio da timeline", "pausa/retomada continua do ponto em que parou",
           IS, "engine_start += (self._clock.monotonic() - pause_started)", "engine_start += 0.0"))
    add(_m("MOT03", "motor", "a velocidade do mapa é ignorada", "velocidade escala todos os tempos",
           IS, "target_elapsed = event.time / speed", "target_elapsed = event.time"))
    add(_m("MOT04", "motor", "o tempo gasto numa barreira não desloca a timeline", "barreira mantém duração e lacunas planejadas",
           IS, "            engine_start += self._barrier_elapsed\n", "            engine_start += 0.0\n"))
    add(_m("MOT05", "motor", "a parada não é consultada entre os caracteres do texto", "parada no meio do texto interrompe a digitação",
           IS, L("                if self._stop_requested.is_set():", "                    break", "                self._backend.type_text(char)"),
           "                self._backend.type_text(char)"))
    add(_m("MOT06", "motor", "o texto é enviado de uma vez só, não um caractere por vez", "texto sai um caractere por vez",
           IS, L('            for char in str(event.text or ""):', "                if self._stop_requested.is_set():", "                    break",
                 "                self._backend.type_text(char)"), '            self._backend.type_text(str(event.text or ""))'))
    add(_m("MOT07", "motor", "soltar uma tecla não a tira do registro de teclas presas", "fim de execução não solta de novo o que já foi solto",
           IS, "            self._pressed_keys.discard(event.target)\n", "            pass\n"))
    add(_m("MOT08", "motor", "tecla pressionada não é registrada (parada não a soltaria)", "parada solta teclas seguradas",
           IS, L("            self._backend.key_down(event.target)", "            self._pressed_keys.add(event.target)"),
           "            self._backend.key_down(event.target)"))
    add(_m("MOT09", "motor", "botão do mouse pressionado não é registrado (parada não o soltaria)", "parada solta botões segurados",
           IS, L("            self._backend.mouse_down(event.target)", "            self._pressed_buttons.add(event.target)"),
           "            self._backend.mouse_down(event.target)"))
    add(_m("MOT10", "motor", "botão do mouse solto não sai do registro", "fim de execução não solta de novo o que já foi solto",
           IS, "            self._pressed_buttons.discard(event.target)\n", "            pass\n"))
    add(_m("MOT11", "motor", "o padrão de release_all esquece os botões do mouse", "parada solta botões segurados",
           IS, "                self.mouse_up(button)", "                pass"))
    add(_m("MOT12", "motor", "o padrão de release_all esquece as teclas", "parada solta teclas seguradas",
           IS, "                self.key_up(key)", "                pass"))
    add(_m("MOT13", "motor", "repetição roda uma passada a mais (>= vira >)", "contagem de repetições exata",
           IS, "self._current_repeat >= automation_map.repeat_count", "self._current_repeat > automation_map.repeat_count"))
    add(_m("MOT14", "motor", "o intervalo entre repetições é ignorado", "intervalo entre as passadas",
           IS, "                if automation_map.repeat_interval > 0:", "                if False:"))
    add(_m("MOT15", "motor", "parar com o motor pausado não o acorda (a thread nunca vê a parada)", "parada com o motor pausado",
           IS, "        self._pause_event.set()  # libera thread caso esteja pausada, para ela poder checar o stop", "        pass"))
    add(_m("MOT16", "motor", "erro de execução não solta o que estava pressionado", "erro do backend solta o que estava pressionado",
           IS, L("            self._release_all()", "            self.state.transition_to(State.ERROR)"), "            self.state.transition_to(State.ERROR)"))
    add(_m("MOT17", "motor", "comando que espera processo só espera quando é abrir-aplicativo", "barreira de processo antes do input",
           IS, "        elif event.wait_process:", "        elif False:"))
    add(_m("MOT18", "motor", "o PID do aplicativo recém-aberto não é repassado à espera", "abrir aplicativo + barreira",
           IS, "self._wait_for_process(event, expected_pid=pid)", "self._wait_for_process(event)"))
    add(_m("MOT19", "motor", "condição de atraso não espera", "condição de atraso desloca a timeline",
           IS, "                if seconds and not self._sleep_interruptible(seconds):", "                if False:"))
    add(_m("MOT20", "motor", "a espera de imagem não enxerga o pedido de parada do motor", "parada durante a espera de imagem",
           IS, "stop_event=self._stop_requested,", "stop_event=None,"))
    add(_m("MOT21", "motor", "imagem não encontrada deixa de ser erro", "imagem não encontrada gera erro e nenhum input",
           IS, "                if not result.found:", "                if False:"))
    # (A guarda de `_apply_wait_conditions` que devolve False quando a parada chega durante a espera de imagem é
    # REDUNDANTE com a do `except ProcessReadinessError` do laço: tirar só uma das duas não muda nada que se possa
    # observar, então o defeito plantado é na que protege de verdade, a do laço, que cobre as duas esperas.)
    add(_m("MOT22", "motor", "parar durante a espera por aplicativo vira erro de execução", "parada durante uma espera de prontidão não é erro",
           IS, L("            if self._stop_requested.is_set():", "                self.state.force_to_idle()", "                return"),
           L("            if False:", "                self.state.force_to_idle()", "                return")))
    add(_m("MOT23", "motor", "pausa feita durante uma barreira não segura o input", "pausa durante a espera não envia input",
           IS, "        released = self._apply_wait_conditions(event) and self._checkpoint()", "        released = self._apply_wait_conditions(event)"))
    add(_m("MOT24", "motor", "uma nova execução não para a anterior", "execução exclusiva",
           IS, L("            self.stop(wait=True)", "", "        with self._lock:"), L("            pass", "", "        with self._lock:")))
    add(_m("MOT25", "motor", "mapa inválido é executado", "mapa inválido levanta e não muda o estado",
           IS, L("        errors = automation_map.validate()", "        if errors:"), L("        errors = automation_map.validate()", "        if False:")))
    add(_m("MOT26", "motor", "mapa sem comandos inicia uma execução", "mapa sem comandos não inicia nada",
           IS, L("        if not automation_map.commands:", "            return"), L("        if False:", "            return")))
    add(_m("MOT27", "motor", "o progresso informa o tempo total errado", "progresso informa tempo do evento e total",
           IS, "                    cb(event.time, total_time)", "                    cb(event.time, event.time)"))
    add(_m("MOT28", "motor", "erro num observador de progresso derruba a execução", "observadores com erro não derrubam a execução",
           IS, L("            for cb in list(self.on_progress):", "                try:", "                    cb(event.time, total_time)", "                except Exception:", "                    pass"),
           L("            for cb in list(self.on_progress):", "                cb(event.time, total_time)")))
    add(_m("MOT29", "motor", "o fim natural não solta o que ficou pressionado", "tecla presa em comando 'manter pressionado' é solta no fim",
           IS, L("    def _finish(self, natural_end: bool) -> None:", "        self._release_all()"), L("    def _finish(self, natural_end: bool) -> None:", "        pass")))
    add(_m("MOT30", "motor", "stop() não devolve o motor a IDLE", "estados depois de parar",
           IS, L("        self._release_all()", "        if self.state.state == State.STOPPING:", "            self.state.transition_to(State.IDLE)"), "        self._release_all()"))
    add(_m("MOT31", "motor", "stop() com o motor ocioso tenta mudar de estado", "parar com o motor ocioso não faz nada",
           IS, L("        if self.state.state in (State.IDLE,):", "            return"), L("        if False:", "            return")))
    add(_m("MOT32", "motor", "pausar fora de execução levanta transição inválida", "pausa e retomada fora de execução são ignoradas",
           IS, L("        if self.state.state != State.RUNNING:", "            return False", "        try:", "            self.state.transition_to(State.PAUSED)",
                 "        except core.InvalidStateTransition:", "            return False", "        self._pause_event.clear()"),
           L("        self.state.transition_to(State.PAUSED)", "        self._pause_event.clear()")))
    add(_m("MOT33", "motor", "o sono interrompível ignora o pedido de parada", "parada durante uma espera por atraso",
           IS, L("        while self._clock.monotonic() < end:", "            if self._stop_requested.is_set():", "                return False"), "        while self._clock.monotonic() < end:"))

    # ---------------------------------------------------------------------------------------------- backend Win32
    add(_m("W3201", "win32", "a roda vertical envia 12 em vez de 120 por entalhe", "WHEEL_DELTA = 120",
           IS, "self._mouse(self.MOUSEEVENTF_WHEEL, int(dy) * 120)", "self._mouse(self.MOUSEEVENTF_WHEEL, int(dy) * 12)"))
    add(_m("W3202", "win32", "a roda horizontal é enviada como vertical", "rolagem horizontal",
           IS, "self._mouse(self.MOUSEEVENTF_HWHEEL, int(dx) * 120)", "self._mouse(self.MOUSEEVENTF_WHEEL, int(dx) * 120)"))
    add(_m("W3203", "win32", "os botões laterais X1 e X2 trocam de lugar no SendInput", "X1 = XBUTTON1, X2 = XBUTTON2",
           IS, '{"x1": self.XBUTTON1, "x2": self.XBUTTON2}', '{"x1": self.XBUTTON2, "x2": self.XBUTTON1}'))
    add(_m("W3204", "win32", "constante KEYEVENTF_UNICODE errada", "caminho Unicode do texto",
           IS, "self.KEYEVENTF_UNICODE = 0x0004", "self.KEYEVENTF_UNICODE = 0x0008"))
    add(_m("W3205", "win32", "SendInput que não enviou nada deixa de ser erro", "falha do SendInput vira exceção",
           IS, "        if sent != 1:", "        if sent < 0:"))
    add(_m("W3206", "win32", "envio parcial em lote deixa de ser erro", "falha do SendInput em lote vira exceção",
           IS, "        if sent != len(items):", "        if sent < 0:"))
    add(_m("W3207", "win32", "key_up de seta não leva a flag de tecla estendida", "teclas estendidas (setas, Delete...) soltas como estendidas",
           IS, "flags = self.KEYEVENTF_KEYUP | (self.KEYEVENTF_EXTENDEDKEY if vk in {0x21,0x22,0x23,0x24,0x25,0x26,0x27,0x28,0x2D,0x2E,0x5B,0x5C,0x5D,0x6F,0xA5} else 0)",
           "flags = self.KEYEVENTF_KEYUP | (self.KEYEVENTF_EXTENDEDKEY if vk in {0x21,0x22,0x23,0x24,0x26,0x27,0x28,0x2D,0x2E,0x5B,0x5C,0x5D,0x6F,0xA5} else 0)"))
    add(_m("W3208", "win32", "key_down de Delete não leva a flag de tecla estendida", "teclas estendidas pressionadas como estendidas",
           IS, "        flags = self.KEYEVENTF_EXTENDEDKEY if vk in {0x21,0x22,0x23,0x24,0x25,0x26,0x27,0x28,0x2D,0x2E,0x5B,0x5C,0x5D,0x6F,0xA5} else 0",
           "        flags = self.KEYEVENTF_EXTENDEDKEY if vk in {0x21,0x22,0x23,0x24,0x25,0x26,0x27,0x28,0x2D,0x5B,0x5C,0x5D,0x6F,0xA5} else 0"))
    add(_m("W3209", "win32", "movimento relativo troca os eixos", "movimento relativo vai para o lado certo",
           IS, "self._mouse(self.MOUSEEVENTF_MOVE, 0, int(x), int(y))", "self._mouse(self.MOUSEEVENTF_MOVE, 0, int(y), int(x))"))
    add(_m("W3210", "win32", "movimento absoluto troca os eixos", "SetCursorPos exato",
           IS, "self.user32.SetCursorPos(int(x), int(y))", "self.user32.SetCursorPos(int(y), int(x))"))
    add(_m("W3211", "win32", "soltar o botão esquerdo envia 'pressionar'", "mouse_up envia a flag UP",
           IS, '"left":self.MOUSEEVENTF_LEFTUP,', '"left":self.MOUSEEVENTF_LEFTDOWN,'))
    add(_m("W3212", "win32", "soltar botão lateral envia 'pressionar'", "mouse_up lateral",
           IS, "self._mouse(self.MOUSEEVENTF_XUP, self._xbutton[b]); return", "self._mouse(self.MOUSEEVENTF_XDOWN, self._xbutton[b]); return"))
    add(_m("W3213", "win32", "texto sem caminho Unicode: caractere fora do layout é descartado", "caractere fora do layout chega pelo caminho Unicode",
           IS, "                self._send_unicode_character(ch)", "                pass"))
    add(_m("W3214", "win32", "caractere fora do plano básico perde a segunda metade (surrogate)", "emoji e símbolos raros chegam inteiros",
           IS, "        for i in range(0, len(units), 2):", "        for i in range(0, min(len(units), 2), 2):"))
    add(_m("W3215", "win32", "SHIFT do layout é enviado como CTRL", "maiúsculas e símbolos usam SHIFT",
           IS, "            modifier_vks.append(0x10)  # SHIFT", "            modifier_vks.append(0x11)  # SHIFT"))
    add(_m("W3216", "win32", "CTRL do layout (ALTGR no ABNT2) é ignorado", "símbolos que o ABNT2 faz com AltGr",
           IS, "        if shift_state & 2:", "        if False:"))
    add(_m("W3221", "win32", "ALT do layout é ignorado", "símbolos que o layout faz com ALT",
           IS, "        if shift_state & 4:", "        if False:"))
    add(_m("W3217", "win32", "til morto vira circunflexo", "ã e õ pela tecla morta do layout brasileiro",
           IS, "'\\u0303': '~',  # tilde", "'\\u0303': '^',  # tilde"))
    add(_m("W3218", "win32", "teclas F deslocadas em um", "tabela de teclas virtuais",
           IS, 'self._vk.update({f"F{i}":0x6F+i for i in range(1,13)})', 'self._vk.update({f"F{i}":0x70+i for i in range(1,13)})'))
    add(_m("W3219", "win32", "SHIFT mapeado para o VK do CTRL", "tabela de teclas virtuais",
           IS, '"BACKSPACE":0x08,"TAB":0x09,"ENTER":0x0D,"SHIFT":0x10,', '"BACKSPACE":0x08,"TAB":0x09,"ENTER":0x0D,"SHIFT":0x11,'))
    add(_m("W3220", "win32", "o intervalo entre caracteres do Win32 não é respeitado", "intervalo de digitação (a constante do core)",
           IS, L("            if core.TEXT_CHAR_INTERVAL > 0:", "                time.sleep(core.TEXT_CHAR_INTERVAL)"),
           L("            if False:", "                time.sleep(core.TEXT_CHAR_INTERVAL)"), ocorrencia=2, total=2))

    # ---------------------------------------------------------------------------------------------- backend pynput
    add(_m("PYN01", "pynput", "os nomes PRINTSCREEN/SCROLLLOCK/NUMLOCK do editor não têm tradução", "achado 2.06: teclas do editor que o pynput escreve com sublinhado",
           IS, '    "PRINTSCREEN": "print_screen", "SCROLLLOCK": "scroll_lock", "NUMLOCK": "num_lock",\n', ""))
    add(_m("PYN02", "pynput", "botão de mouse desconhecido vira clique esquerdo", "botão desconhecido é erro, nunca clique esquerdo",
           IS, '    raise ValueError(f"Botão de mouse não suportado pelo backend pynput: {name}")', '    return getattr(Button, "left", None)'))
    add(_m("PYN03", "pynput", "tecla desconhecida vira 'nada' em vez de erro", "nome desconhecido é erro, nunca outra tecla",
           IS, '    raise ValueError(f"Tecla não suportada pelo backend pynput: {name}")', "    return None"))
    add(_m("PYN04", "pynput", "rolagem horizontal do pynput no Windows usa o código da vertical", "rolagem horizontal",
           IS, "mouse_event(0x01000, 0, 0, int(dx) * 120, 0)", "mouse_event(0x0800, 0, 0, int(dx) * 120, 0)"))

    # ---------------------------------------------------------------------------------------------- atalhos globais
    cond = "                if combo <= self._pressed and combo not in self._fired:"
    add(_m("ATL01", "atalhos", "o atalho de teclado dispara de novo a cada auto-repetição da tecla", "um atalho dispara uma vez por apertada",
           IS, cond, "                if combo <= self._pressed:", ocorrencia=1, total=2))
    add(_m("ATL02", "atalhos", "o atalho de botão do mouse dispara de novo enquanto segurado", "um atalho dispara uma vez por apertada",
           IS, cond, "                if combo <= self._pressed:", ocorrencia=2, total=2))
    add(_m("ATL03", "atalhos", "soltar uma tecla não rearma o atalho de teclado", "atalho dispara de novo depois de soltar",
           IS, "            self._fired = {c for c in self._fired if name not in c}", "            self._fired = set(self._fired)"))
    add(_m("ATL04", "atalhos", "soltar um botão do mouse não rearma o atalho", "atalho de botão dispara de novo depois de soltar",
           IS, "            self._fired = {c for c in self._fired if token not in c}", "            self._fired = set(self._fired)"))
    add(_m("ATL05", "atalhos", "apertar UMA tecla da combinação já dispara o atalho", "a combinação só dispara com todas as teclas",
           IS, cond, "                if (combo & self._pressed) and combo not in self._fired:", ocorrencia=1, total=2))
    add(_m("ATL06", "atalhos", "dois atalhos iguais para ações diferentes são aceitos", "conflito de atalho levanta HotkeyConflictError",
           IS, "        if existing is not None and existing[1] is not callback:", "        if False:"))
    add(_m("ATL07", "atalhos", "registrar de novo o MESMO callback passa a ser conflito", "registro repetido do mesmo atalho é idempotente",
           IS, "        if existing is not None and existing[1] is not callback:", "        if existing is not None:"))
    add(_m("ATL08", "atalhos", "atalho de botão lateral troca X1 e X2", "decisão D1: nome cru do sistema",
           IS, '"x1": "MOUSE_X1", "x2": "MOUSE_X2",', '"x1": "MOUSE_X2", "x2": "MOUSE_X1",'))
    add(_m("ATL09", "atalhos", "o apelido X1 aponta para o botão lateral 2", "apelidos de atalho do mouse",
           CORE, '"MOUSE_X1": "MOUSE_X1", "X1": "MOUSE_X1", "LATERAL1": "MOUSE_X1",', '"MOUSE_X1": "MOUSE_X1", "X1": "MOUSE_X2", "LATERAL1": "MOUSE_X1",'))
    add(_m("ATL10", "atalhos", "parar o gerente de atalhos não remove o ouvinte de teclado", "stop() desliga o gerente",
           IS, "            self.monitor.on_key.remove(self._key_cb)", "            pass"))
    add(_m("ATL11", "atalhos", "atalho vazio é aceito", "atalho vazio é erro",
           CORE, L("    if not parts:", '        raise ValueError("Atalho vazio.")'), L("    if False:", '        raise ValueError("Atalho vazio.")')))

    # ---------------------------------------------------------------------------------------------- ativação por mapa (25.8)
    # A lógica (ativacao.py) e o controlador (ativacao_ui.py) rodam no modo LÓGICA; a faixa e a lista, que são widgets, no dublê.
    # As ligações com a janela principal (main_window.py) não têm teste de comportamento fora do Qt de verdade: quem as protege
    # aqui é tests/static/test_ligacao_ativacao.py.
    add(_m("ATV01", "ativacao", "os atalhos de controle deixam de ter prioridade: um mapa pode engolir a parada de emergência",
           "ATV-01: os atalhos de controle entram no plano antes dos mapas", ATV,
           L("    for chave in ORDEM_CONTROLE:",
             "        _ocupar(plano, controles.get(chave), ROTULOS_CONTROLE[chave], ACAO_DO_CONTROLE[chave], False)",
             "    for nome in sorted(mapas, key=ordem_dos_nomes):",
             "        if estados.get(nome) in (ESTADO_SESSAO, ESTADO_SEMPRE):",
             '            _ocupar(plano, mapas[nome], nome, f"map:{nome}", True)'),
           L("    for nome in sorted(mapas, key=ordem_dos_nomes):",
             "        if estados.get(nome) in (ESTADO_SESSAO, ESTADO_SEMPRE):",
             '            _ocupar(plano, mapas[nome], nome, f"map:{nome}", True)',
             "    for chave in ORDEM_CONTROLE:",
             "        _ocupar(plano, controles.get(chave), ROTULOS_CONTROLE[chave], ACAO_DO_CONTROLE[chave], False)")))
    add(_m("ATV02", "ativacao", "a parada de emergência deixa de vir primeiro entre os atalhos de controle",
           "a ordem de prioridade dos atalhos de controle", ATV,
           'ORDEM_CONTROLE = ("emergency", "pause", "resume", "record_toggle", "record_cancel")',
           'ORDEM_CONTROLE = ("pause", "resume", "record_toggle", "record_cancel", "emergency")'))
    add(_m("ATV03", "ativacao", "um mapa desativado ocupa a tecla e causa conflito", "só mapas ativos ocupam teclas", ATV,
           "        if estados.get(nome) in (ESTADO_SESSAO, ESTADO_SEMPRE):", "        if True:"))
    add(_m("ATV04", "ativacao", "a ordem dos mapas vira a alfabética comum (maiúsculas antes das minúsculas)",
           "a ordem dos nomes é a do banco (COLLATE NOCASE): decide quem fica com a tecla repetida de dados antigos", ATV,
           "    return nome.translate(_MINUSCULAS_ASCII), nome", "    return nome, nome"))
    add(_m("ATV05", "ativacao", "a ordem dos mapas passa a igualar também as letras acentuadas (o SQLite só iguala A-Z)",
           "a ordem dos nomes é a do banco, não a do Python", ATV,
           "    return nome.translate(_MINUSCULAS_ASCII), nome", "    return nome.casefold(), nome"))
    add(_m("ATV06", "ativacao", "quem chega depois rouba a tecla de quem já a usa (se o nome dele vem antes na ordem)",
           "HK-01: quem já usa a tecla nunca a perde para quem chega depois", ATV,
           L("        outros = {n: t for n, t in mapas.items() if n != nome}",
             "        dono = montar_plano(outros, self.estados(outros), controles).dono(tecla)"),
           L("        todos = dict(mapas)",
             "        todos[nome] = tecla",
             "        dono = montar_plano(todos, {**self.estados(todos), nome: ESTADO_SESSAO}, controles).dono(tecla)",
             "        if dono is not None and dono.nome == nome:",
             "            dono = None")))
    add(_m("ATV07", "ativacao", "a migração da primeira abertura deixa os mapas existentes desativados",
           "MAP-04: os mapas que já existiam continuam respondendo à tecla", ATV,
           "                self._prefs.setdefault(nome, ESTADO_SEMPRE)", "                self._prefs.setdefault(nome, ESTADO_DESATIVADO)"))
    add(_m("ATV08", "ativacao", "a migração nunca é dada como feita: todo mapa novo seria tratado como antigo",
           "MAP-02: o mapa criado depois da migração nasce só nesta sessão", ATV,
           "            self._migrado = True", "            self._migrado = False"))
    add(_m("ATV09", "ativacao", "o mapa novo é gravado como 'sempre ativo' em vez de desativado",
           "MAP-02: o mapa novo só vale na sessão (o que se grava é desativado)", ATV,
           L("            self._prefs[nome] = ESTADO_DESATIVADO",
             "            conflito = self.verificar_tecla(nome, mapas[nome], mapas, controles)"),
           L("            self._prefs[nome] = ESTADO_SEMPRE",
             "            conflito = self.verificar_tecla(nome, mapas[nome], mapas, controles)")))
    add(_m("ATV10", "ativacao", "o mapa novo com a tecla ocupada nasce ativo do mesmo jeito",
           "HK-01: mapa novo com tecla ocupada nasce desativado", ATV,
           L("            if conflito is None:", "                self._sessao.add(nome)"),
           L("            if True:", "                self._sessao.add(nome)")))
    add(_m("ATV11", "ativacao", "o mapa novo que nasce desativado por conflito não avisa o motivo",
           "HK-01: o motivo de o mapa ter nascido desativado é dito", ATV,
           '                avisos.append(f"{conflito.mensagem} Por isso “{nome}” começou desativada.")', "                pass"))
    add(_m("ATV12", "ativacao", "o estado 'só nesta sessão' vaza para o banco de configurações",
           "só 'sempre' e 'desativado' são gravados", ATV,
           L("            self._prefs[nome] = ESTADO_DESATIVADO", "            self._sessao.add(nome)"),
           L("            self._prefs[nome] = ESTADO_SESSAO", "            self._sessao.add(nome)")))
    add(_m("ATV13", "ativacao", "passar de 'sempre' para 'só nesta sessão' não avisa que na próxima abertura fica desativada",
           "MAP-01: o aviso da mudança de 'sempre' para 'sessão'", ATV,
           "                aviso = AVISO_DE_SEMPRE_PARA_SESSAO", '                aviso = ""'))
    add(_m("ATV14", "ativacao", "ativar um mapa sobre uma tecla ocupada é aceito",
           "HK-01: a ativação sobre tecla ocupada é recusada", ATV,
           L("            if conflito is not None:", "                return Resultado(False, recusa_de_ativacao(conflito))"),
           L("            if False:", "                return Resultado(False, recusa_de_ativacao(conflito))")))
    add(_m("ATV15", "ativacao", "a mensagem de conflito não diz qual automação ativa usa a tecla",
           "HK-01: a mensagem nomeia quem está com a tecla", ATV,
           '        return f"A tecla “{tecla}” de “{perdedor}” já é usada pela automação ativa “{vencedor}”."',
           '        return f"A tecla “{tecla}” de “{perdedor}” já é usada por outra automação."'))
    add(_m("ATV16", "ativacao", "um estado desconhecido gravado no banco passa a ser aceito como preferência",
           "ATV-04: o leitor ignora o que não é 'sempre' nem 'desativado'", ATV,
           "if isinstance(nome, str) and nome and valor in PREFERENCIAS:", "if isinstance(nome, str) and nome and valor in ESTADOS:"))
    add(_m("ATV17", "ativacao", "dados de ativação corrompidos derrubam a abertura",
           "ATV-04: o programa abre mesmo com a ativação ilegível", ATV,
           "        if isinstance(dados, Mapping):", "        if True:"))
    add(_m("ATV18", "ativacao", "sincronizar apaga a preferência de um mapa que não veio na lista (não carregou)",
           "a preferência só some quando o mapa é excluído, não quando ele falha ao carregar", ATV,
           "        for nome in sorted((n for n in mapas if n not in self._prefs), key=ordem_dos_nomes):",
           L("        self._prefs = {n: v for n, v in self._prefs.items() if n in mapas}",
             "        for nome in sorted((n for n in mapas if n not in self._prefs), key=ordem_dos_nomes):")))
    add(_m("ATV19", "ativacao", "excluir um mapa não apaga a preferência dele", "ATV-03: a preferência some com o mapa", ATV,
           L("        self._prefs.pop(nome, None)", "        self._sessao.discard(nome)", "        return havia"),
           L("        self._sessao.discard(nome)", "        return havia")))
    add(_m("ATV20", "ativacao", "a mesma combinação escrita em outra ordem (CTRL+F6 / F6+CTRL) deixa de contar como a mesma tecla",
           "o conflito compara combinações, não o texto", ATV,
           "        combinacao = parse_combo(texto)", L("        parse_combo(texto)", "        combinacao = texto.upper()")))
    add(_m("ATV21", "ativacao", "refazer os atalhos não limpa os antigos: o de um mapa desativado continua valendo",
           "MAP-03: o mapa desativado não responde à tecla", ATV,
           L("    gerente.clear()", "    erros: list[str] = []"), "    erros: list[str] = []"))
    add(_m("ATV22", "ativacao", "uma tecla inválida levanta erro ao montar o plano em vez de ser apontada",
           "uma tecla que não existe não derruba a janela", ATV,
           L("    except ValueError:", "        plano.invalidos.append(Invalido(nome, texto, e_mapa, _mensagem_de_invalido(nome, texto, e_mapa)))"),
           L("    except KeyError:", "        plano.invalidos.append(Invalido(nome, texto, e_mapa, _mensagem_de_invalido(nome, texto, e_mapa)))")))
    add(_m("ATV23", "ativacao", "o mapa que perdeu a tecla para outro é descrito como se a tecla funcionasse",
           "HK-01: a situação do conflito aparece na tela", ATV,
           L("        conflito = plano.conflito_do_mapa(nome)", "        if conflito is not None:"),
           L("        conflito = plano.conflito_do_mapa(nome)", "        if False:")))
    add(_m("ATV24", "ativacao", "o dono de uma tecla é procurado pelo texto, não pela combinação",
           "a conferência de conflito aceita a tecla escrita de qualquer jeito equivalente", ATV,
           "        return self._donos.get(parse_combo(tecla.strip()))", "        return self._donos.get(tecla)"))

    # controlador (ativacao_ui.py)
    add(_m("ATV25", "ativacao", "o disparo de um mapa desativado que já estava na fila ainda o executa",
           "MAP-03: a guarda de `_on_hotkey_triggered` ignora mapa desativado", ATU,
           '        return self._estado().esta_ativo(acao[len("map:"):])', "        return True"))
    add(_m("ATV26", "ativacao", "registrar os atalhos não alinha antes o estado dos mapas (o mapa novo ficaria sem tecla)",
           "MAP-02: `registrar` é autossuficiente", ATU,
           L("        self.sincronizar()", "        plano = self.plano()"), "        plano = self.plano()"))
    add(_m("ATV27", "ativacao", "o mesmo conflito é avisado a cada registro de atalhos",
           "HK-01: cada conflito é avisado uma vez", ATU,
           "        novos = [mensagem for mensagem in atuais if mensagem not in self._avisados]", "        novos = list(atuais)"))
    add(_m("ATV28", "ativacao", "um conflito que sumiu e voltou não é avisado de novo",
           "HK-01: o aviso volta se o conflito reaparece", ATU,
           "        self._avisados = set(atuais)", "        self._avisados |= set(atuais)"))
    add(_m("ATV29", "ativacao", "mudar o estado de uma automação não refaz os atalhos globais",
           "MAP-03: a tecla do mapa desativado deixa de valer na hora", ATU,
           L("        self._gravar()", "        self.janela._register_all_hotkeys()"), "        self._gravar()"))
    add(_m("ATV30", "ativacao", "mudar o estado de uma automação não grava a preferência no banco",
           "MAP-01: o estado escolhido vale na próxima abertura", ATU,
           L("        self._gravar()", "        self.janela._register_all_hotkeys()"), "        self.janela._register_all_hotkeys()"))
    add(_m("ATV31", "ativacao", "mudar o estado não atualiza o rótulo e a faixa do editor",
           "o editor mostra o estado verdadeiro", ATU,
           "        self.janela._refresh_map_config_labels()", "        pass"))
    add(_m("ATV32", "ativacao", "o aviso de 'sempre' para 'só nesta sessão' não vai para a barra de status",
           "MAP-01: o aviso aparece", ATU,
           L("        if resultado.mensagem:", "            self.janela.status_bar.showMessage(resultado.mensagem, 8000)"),
           L("        if False:", "            self.janela.status_bar.showMessage(resultado.mensagem, 8000)")))
    add(_m("ATV33", "ativacao", "uma tecla que não existe é aceita ao mudar a tecla da automação",
           "HK-01: a tecla inválida é recusada", ATU,
           L("        if not tecla_valida(tecla):", "            return recusa_de_tecla_invalida(tecla, nome, atual)"),
           L("        if False:", "            return recusa_de_tecla_invalida(tecla, nome, atual)")))
    add(_m("ATV34", "ativacao", "mudar a tecla de uma automação desativada para uma tecla ocupada passa a ser recusado",
           "um mapa desativado não conflita: o conflito é conferido ao ativar", ATU,
           L("        if not logica.esta_ativo(nome):", '            return ""'), L("        if False:", '            return ""')))
    add(_m("ATV35", "ativacao", "mudar a tecla de uma automação ativa para uma tecla ocupada é aceito",
           "HK-01: a mudança de tecla para uma tecla ocupada é recusada", ATU,
           '        return recusa_de_tecla(conflito, atual) if conflito is not None else ""', '        return ""'))
    add(_m("ATV36", "ativacao", "o controlador continua com as configurações antigas depois que a pasta de dados muda",
           "o estado é o do banco da pasta de dados atual", ATU,
           "        if self._logica is None or ajustes is not self._ajustes:", "        if self._logica is None:"))
    add(_m("ATV37", "ativacao", "excluir uma automação não apaga a preferência dela no banco",
           "ATV-03: a preferência é apagada junto", ATU,
           L("        if self._estado().esquecer(nome):", "            self._gravar()"),
           L("        if self._estado().esquecer(nome):", "            pass")))
    add(_m("ATV38", "ativacao", "a migração da primeira abertura não é gravada",
           "MAP-04: os mapas de antes ficam 'sempre ativos' também na abertura seguinte", ATU,
           L("        if resultado.mudou:", "            self._gravar()"), L("        if False:", "            self._gravar()")))
    add(_m("ATV39", "ativacao", "o aviso de que um mapa novo nasceu desativado por conflito não é mostrado",
           "HK-01: o usuário é avisado", ATU, "        if resultado.avisos:", "        if False:"))
    add(_m("ATV40", "ativacao", "o rótulo da tecla no editor deixa de dizer que a automação está desativada",
           "o editor mostra que a tecla não inicia a automação", ATU, '            aviso = " (desativada)"', '            aviso = ""'))
    add(_m("ATV41", "ativacao", "o rótulo da tecla no editor deixa de dizer que a tecla está em conflito",
           "o editor mostra que a tecla perdeu o conflito", ATU, '            aviso = " (em conflito)"', '            aviso = ""'))

    # a lista e a faixa (widgets: rodam no dublê)
    add(_m("ATV42", "ativacao", "a lista de automações não recebe o estado de cada item",
           "contrato com a frente visual: papel de dados 257", ATU,
           "            item.setData(PAPEL_ESTADO, descricao.estado)", "            pass", modo=INTERFACE))
    add(_m("ATV43", "ativacao", "a lista de automações não recebe o texto do conflito de cada item",
           "contrato com a frente visual: papel de dados 258", ATU,
           '            item.setData(PAPEL_CONFLITO, descricao.conflito.mensagem if descricao.conflito is not None else "")',
           "            pass", modo=INTERFACE))
    add(_m("ATV44", "ativacao", "a dica de cada item da lista perde a frase de abrir a automação",
           "a dica diz o que o clique faz e a situação da ativação", ATU,
           L("        if dica is not None:", "            self._dica = dica"), L("        if False:", "            self._dica = dica"), modo=INTERFACE))
    add(_m("ATV45", "ativacao", "mostrar a automação na faixa passa a contar como uma escolha do usuário",
           "só o usuário muda o estado: mostrar não mexe em nada", ATU,
           "        self._ajustando = True", "        self._ajustando = False", modo=INTERFACE))
    add(_m("ATV46", "ativacao", "depois de uma escolha recusada a faixa continua mostrando a escolha, não o estado verdadeiro",
           "ATV-05: a faixa nunca mente sobre o estado", ATU,
           "        self.mostrar(self._nome)", "        pass", modo=INTERFACE))
    add(_m("ATV47", "ativacao", "a faixa é encaixada ACIMA da âncora em vez de logo abaixo",
           "a faixa fica logo abaixo da instrução do editor", ATU,
           "            layout.insertWidget(posicao + 1 if posicao >= 0 else layout.count(), painel)",
           "            layout.insertWidget(posicao if posicao >= 0 else layout.count(), painel)", modo=INTERFACE))
    add(_m("ATV48", "ativacao", "uma falha ao encaixar a faixa deixa de ser contida e derruba a abertura da janela",
           "a faixa é um acréscimo: nunca impede o programa de abrir", ATU,
           "        except Exception as exc:  # noqa: BLE001", "        except ZeroDivisionError as exc:  # noqa: BLE001", modo=INTERFACE))

    # ligações com a janela principal e com o banco (protegidas por tests/static/test_ligacao_ativacao.py e pelos testes de persistência)
    add(_m("ATV49", "ativacao", "a janela deixa de consultar a ativação ao receber o atalho de um mapa",
           "MAP-03: a guarda está ligada", JAN, "            if not self.ativacao.acao_permitida(action_id):", "            if False:"))
    add(_m("ATV50", "ativacao", "refazer os atalhos volta a registrar tudo sem passar pela ativação",
           "MAP-03 e ATV-01: quem decide o que é registrado é a ativação", JAN, "        self.ativacao.registrar()", "        pass"))
    add(_m("ATV51", "ativacao", "a lista de automações deixa de receber o estado e a dica",
           "contrato com a frente visual: a lista é decorada a cada recarga", JAN,
           "        self.ativacao.decorar_lista('Abrir esta automação para editar, visualizar a timeline ou executar.')", "        pass"))
    add(_m("ATV52", "ativacao", "recarregar a lista não alinha a ativação: mapa novo ficaria sem estado",
           "MAP-02: a ativação é sincronizada a cada recarga", JAN, "        self.ativacao.sincronizar()", "        pass"))
    add(_m("ATV53", "ativacao", "excluir a automação não esquece a preferência dela",
           "ATV-03: a janela avisa o controlador da exclusão", JAN, "            self.ativacao.esquecer(self._current_map.name)", "            pass"))
    add(_m("ATV54", "ativacao", "a configuração da automação grava a tecla direto no mapa, sem passar pela validação",
           "HK-01: a janela entrega a tecla ao controlador (`mudar_tecla`), que valida", JAN,
           "        self.ativacao.mudar_tecla(m, new_hotkey)", "        m.hotkey = new_hotkey"))
    add(_m("ATV55", "ativacao", "a tecla recusada é gravada no mapa do mesmo jeito",
           "HK-01: a tecla anterior permanece quando a nova é recusada", ATU,
           L("        if motivo:", '            self._mostrar("Tecla não alterada", motivo)', "            return False"),
           L("        if motivo:", '            self._mostrar("Tecla não alterada", motivo)')))
    add(_m("ATV61", "ativacao", "a tecla recusada não é avisada: a pessoa não sabe por que nada mudou",
           "HK-01: o motivo da recusa é mostrado", ATU,
           '            self._mostrar("Tecla não alterada", motivo)', "            pass"))
    add(_m("ATV62", "ativacao", "a tecla aceita não é gravada no mapa",
           "HK-01: a tecla livre é aplicada", ATU, "        mapa.hotkey = tecla", "        pass"))
    add(_m("ATV56", "ativacao", "a janela não monta a faixa de ativação no editor",
           "ATV-05: o seletor de estado existe no editor", JAN, "        self.ativacao.montar_painel(self.map_instruction)", "        pass"))
    add(_m("ATV57", "ativacao", "o rótulo da tecla no editor volta a não mostrar a situação da ativação",
           "o editor mostra que a tecla está desativada ou em conflito", JAN,
           "        self.hotkey_label.setText(self.ativacao.rotulo_da_tecla(m))",
           "        self.hotkey_label.setText(f\"Tecla para iniciar/parar: {m.hotkey or '—'}\")"))
    add(_m("ATV58", "ativacao", "a faixa não é atualizada quando a automação aberta muda",
           "ATV-05: a faixa acompanha a automação aberta", JAN, "        self.ativacao.atualizar_painel()", "        pass"))
    add(_m("ATV59", "ativacao", "gravar a preferência de ativação não chega ao arquivo de configurações",
           "ATV-03: a preferência de ativação persiste", PRJ,
           "        self._data['map_activation'] = copy.deepcopy(values); self.save()",
           "        self._data['map_activation'] = copy.deepcopy(values)"))
    add(_m("ATV60", "ativacao", "ler a preferência de ativação devolve o dicionário interno, não uma cópia",
           "quem altera o resultado não altera a configuração", PRJ,
           "        return copy.deepcopy(saved) if isinstance(saved, dict) else {}", "        return saved if isinstance(saved, dict) else {}"))


    # ---------------------------------------------------------------------------------------------- pausar e continuar pelas teclas (achado 2.11)
    add(_m("PAU01", "motor", "pausar com sucesso diz que não pausou", "PAU-01: `pause()` devolve True quando pausou (a janela só avisa o usuário se mudou)",
           IS, L("        self._pause_event.clear()", "        return True"), L("        self._pause_event.clear()", "        return False")))
    add(_m("PAU02", "motor", "continuar sem pausa troca o estado de parado para executando (e não há thread)", "PAU-03: `resume()` só age em PAUSADO",
           IS, L("        if self.state.state != State.PAUSED:", "            return False", "        try:", "            self.state.transition_to(State.RUNNING)"),
           L("        try:", "            self.state.transition_to(State.RUNNING)")))
    add(_m("PAU03", "motor", "pausar no instante em que a execução termina levanta transição inválida", "PAU-04: a tecla vem de outra thread e perde a corrida sem erro",
           IS, L("            self.state.transition_to(State.PAUSED)", "        except core.InvalidStateTransition:"),
           L("            self.state.transition_to(State.PAUSED)", "        except KeyError:")))
    add(_m("PAU04", "motor", "continuar no instante em que a execução é parada levanta transição inválida", "PAU-04",
           IS, L("            self.state.transition_to(State.RUNNING)", "        except core.InvalidStateTransition:"),
           L("            self.state.transition_to(State.RUNNING)", "        except KeyError:")))
    add(_m("PAU05", "motor", "a pausa que perdeu a corrida diz que pausou", "PAU-04: `pause()` devolve False quando a execução já tinha acabado",
           IS, L("        except core.InvalidStateTransition:", "            return False", "        self._pause_event.clear()"),
           L("        except core.InvalidStateTransition:", "            return True", "        self._pause_event.clear()")))
    add(_m("PAU06", "motor", "continuar muda o estado mas não acorda a thread do motor", "PAU-02: a retomada segue do ponto onde parou",
           IS, L("        self._pause_event.set()", "        return True"), L("        pass", "        return True")))
    add(_m("PAU07", "motor", "pausar muda o estado mas não para a thread do motor", "PAU-01: nenhuma entrada nova durante a pausa",
           IS, L("        self._pause_event.clear()", "        return True"), L("        pass", "        return True")))
    add(_m("PAU08", "motor", "pausar solta as teclas que estavam apertadas", "o que NÃO muda: a pausa mantém o que estava apertado (md/ESPEC_PAUSA_TECLAS.md)",
           IS, L("        self._pause_event.clear()", "        return True"), L("        self._pause_event.clear()", "        self._release_all()", "        return True")))

    add(_m("PAU09", "controle", "F9 diz que pausou mesmo quando não havia nada para pausar", "PAU-03: sem execução, sem mensagem",
           CTL, L("        if not self.janela.engine.pause():", "            return False"), "        self.janela.engine.pause()"))
    add(_m("PAU10", "controle", "F10 diz que continuou mesmo quando não havia pausa", "PAU-03: sem pausa, sem mensagem",
           CTL, L("        if not self.janela.engine.resume():", "            return False"), "        self.janela.engine.resume()"))
    add(_m("PAU11", "controle", "a mensagem de pausa cita sempre F10", "PAU-01: cita a tecla de continuar que está configurada",
           CTL, '            texto = f"Automação pausada. Aperte {tecla} para continuar."', '            texto = "Automação pausada. Aperte F10 para continuar."'))
    add(_m("PAU12", "controle", "a mensagem manda apertar uma tecla de continuar que não está ativa", "PAU-01: tecla inválida ou repetida não é citada",
           CTL, "        if tecla:", "        if True:"))
    add(_m("PAU13", "controle", "a mensagem cita a tecla de pausar, não a de continuar", "PAU-01",
           CTL, 'ACAO_DE_CONTINUAR = "control:resume"', 'ACAO_DE_CONTINUAR = "control:pause"'))
    add(_m("PAU14", "controle", "a mensagem de pausa fica na barra para sempre (prazo 0)", "a mensagem não sobra depois de a automação ser parada",
           CTL, "PRAZO_DA_MENSAGEM_PAUSADA = 8000", "PRAZO_DA_MENSAGEM_PAUSADA = 0"))
    add(_m("PAU15", "controle", "pausar devolve False mesmo tendo pausado", "PAU-01: o retorno diz se mudou",
           CTL, L("        self.janela.status_bar.showMessage(texto, PRAZO_DA_MENSAGEM_PAUSADA)", "        return True"),
           L("        self.janela.status_bar.showMessage(texto, PRAZO_DA_MENSAGEM_PAUSADA)", "        return False")))
    add(_m("PAU16", "controle", "continuar não diz que continuou", "PAU-02: a mensagem de retomada",
           CTL, '        self.janela.status_bar.showMessage("Automação retomada.", PRAZO_DA_MENSAGEM_RETOMADA)', "        pass"))
    add(_m("PAU17", "controle", "a tecla de continuar é lida direto da configuração, sem conferir se está ativa", "PAU-01: o plano de atalhos é quem diz o que está ativo",
           CTL, L("        registro = next((r for r in self.janela.ativacao.plano().registros if r.acao == ACAO_DE_CONTINUAR), None)",
                  '        return registro.tecla if registro is not None else ""'),
           '        return self.janela.settings.get_control_hotkeys().get("resume", "")'))
    add(_m("PAU18", "controle", "o controlador usa o motor que a janela tinha ao ser criado, não o de agora", "o controlador lê o motor na hora, como o da ativação lê as configurações",
           CTL, funcao=_motor_guardado))

    add(_m("PAU19", "controle", "F9 chama continuar e não pausar", "PAU-05: cada tecla chama o seu método do controlador",
           JAN, "            self.controle.pausar()  # F9", "            self.controle.retomar()  # F9"))
    add(_m("PAU20", "controle", "a janela perde o ramo da tecla de pausar (a tecla chega e some)", "PAU-05: toda ação de controle registrada tem ramo",
           JAN, '        elif action_id == "control:pause":\n', '        elif action_id == "control:pausar":\n'))
    add(_m("PAU21", "controle", "a janela perde o ramo da tecla de continuar (a tecla chega e some)", "PAU-05",
           JAN, '        elif action_id == "control:resume":\n', '        elif action_id == "control:retomar":\n'))
    add(_m("PAU22", "controle", "a janela não cria o controlador de execução", "PAU-05: `self.controle` existe antes dos atalhos",
           JAN, "        self.controle = ControladorDeExecucao(self)", "        self.controle = None"))
    add(_m("PAU23", "controle", "o controlador é criado depois de os atalhos serem registrados", "PAU-05: um disparo cedo demais acharia a janela sem controlador",
           JAN, funcao=_controle_depois_dos_atalhos))

    # ---------------------------------------------------------------------------------------------- botões laterais (D1)
    add(_m("BTN01", "botoes", "o monitor volta a trocar X1 e X2 (a troca em dobro do 25.3)", "decisão D1: só o mouse virtual troca os nomes",
           IS, '        name = str(getattr(button, "name", str(button))).lower()', '        name = display_mouse_button_name(str(getattr(button, "name", str(button))).lower())'))
    add(_m("BTN02", "botoes", "o gravador volta a trocar X1 e X2", "decisão D1",
           IS, L("        name = str(name).lower()", "        if name in self.filters.ignored_mouse_buttons:"),
           L("        name = display_mouse_button_name(str(name).lower())", "        if name in self.filters.ignored_mouse_buttons:")))
    add(_m("BTN03", "botoes", "os atalhos voltam a trocar X1 e X2", "decisão D1",
           IS, L("        normalized = str(name).lower()", "        token_map = {"), L("        normalized = display_mouse_button_name(str(name).lower())", "        token_map = {")))
    add(_m("BTN04", "botoes", "o mouse virtual deixa de trocar os nomes para desenhar", "decisão D1: a troca visual existe",
           "automationstudio/main_window.py", "self.mouse_button_changed.emit(display_mouse_button_name(name), pressed)", "self.mouse_button_changed.emit(name, pressed)"))
    add(_m("BTN05", "botoes", "a constante da troca visual é desligada", "decisão D1: constante = True até a conferência no hardware",
           CORE, "DISPLAY_SWAPS_SIDE_BUTTONS = True", "DISPLAY_SWAPS_SIDE_BUTTONS = False"))
    add(_m("BTN06", "botoes", "a exibição troca qualquer botão, não só os laterais", "esquerdo, direito e meio nunca mudam de nome",
           CORE, '    if DISPLAY_SWAPS_SIDE_BUTTONS and raw in ("x1", "x2"):', "    if DISPLAY_SWAPS_SIDE_BUTTONS:"))

    # ---------------------------------------------------------------------------------------------- gravador
    add(_m("GRV01", "gravador", "a auto-repetição do sistema reinicia o início da tecla", "só o primeiro KEYDOWN conta como início",
           IS, "            self._open_presses.setdefault(key, _OpenPress(start=t))", "            self._open_presses[key] = _OpenPress(start=t)"))
    add(_m("GRV02", "gravador", "soltar algo que não foi pressionado durante a gravação quebra o gravador", "soltar sem pressão capturada é ignorado",
           IS, "        if open_press is None:", "        if False:"))
    add(_m("GRV03", "gravador", "a pausa descarta as teclas seguradas em vez de fechá-las", "pausa fecha as pressões abertas",
           IS, L("            now = self._elapsed()", "            for (input_type, target), open_press in list(self._open_presses.items()):",
                 "                self._append_command(input_type, target, open_press.start, now)", "            self._open_presses.clear()"),
           "            self._open_presses.clear()"))
    add(_m("GRV04", "gravador", "parar a gravação descarta as teclas ainda seguradas", "tecla pendurada é fechada no instante da parada",
           IS, L("        self._finalize_mouse_move(now)", "        for (input_type, target), open_press in list(self._open_presses.items()):",
                 "            self._append_command(input_type, target, open_press.start, now)"), "        self._finalize_mouse_move(now)"))
    add(_m("GRV05", "gravador", "a duração das teclas é sempre gravada, mesmo com o filtro desligado", "filtro 'gravar duração'",
           IS, "        if not self.filters.record_key_duration:", "        if False:"))
    add(_m("GRV06", "gravador", "o trajeto do mouse não é fechado em t = 1", "trajeto normalizado termina em 1",
           IS, '        if path[-1]["t"] < 1.0:', "        if False:"))
    add(_m("GRV07", "gravador", "o tremor do mouse (abaixo do limite de pixels) é gravado", "filtro de tremor",
           IS, "        if math.hypot(dx, dy) < min_px:", "        if False:"))
    add(_m("GRV08", "gravador", "a última amostra descartada pelo intervalo se perde (o cursor para antes de onde parou)", "achado 2.0x: última amostra do trajeto",
           IS, '            seg["pending"] = (t, int(x), int(y))\n', ""))
    add(_m("GRV09", "gravador", "a fotografia da gravação ignora a amostra pendente", "snapshot inclui a última amostra",
           IS, 'self._simplify_mouse_path(self._points_with_pending(seg), float(self.filters.mouse_jitter_px))',
           'self._simplify_mouse_path(list(seg["points"]), float(self.filters.mouse_jitter_px))'))
    add(_m("GRV10", "gravador", "fechar o movimento ignora a amostra pendente", "o movimento termina onde o cursor parou",
           IS, L("        points = self._points_with_pending(seg)", "        if not points:"), L('        points = list(seg.get("points", []))', "        if not points:")))
    add(_m("GRV11", "gravador", "o intervalo mínimo de amostragem do mouse é ignorado", "intervalo de amostragem",
           IS, "        if dt < min_dt:", "        if False:"))
    add(_m("GRV12", "gravador", "comandos que apenas se tocam passam a formar um grupo", "agrupamento só por sobreposição de verdade",
           IS, "                if cmd.effective_start < end:", "                if cmd.effective_start <= end:"))
    add(_m("GRV13", "gravador", "gravar é permitido com o motor executando", "execução exclusiva: gravar só a partir de IDLE",
           IS, L("        if self.state.state != State.IDLE:", "            raise RecorderError("), L("        if False:", "            raise RecorderError(")))
    add(_m("GRV14", "gravador", "parar a gravação não remove os ouvintes do monitor", "o gravador solta o monitor ao parar",
           IS, L("            if cb in lst:", "                lst.remove(cb)"), L("            if cb in lst:", "                pass")))
    add(_m("GRV15", "gravador", "cancelar a gravação não devolve o estado a IDLE", "cancelar volta a IDLE",
           IS, L("        self._active_mouse_move = None", "        if self.state.state == State.RECORDING:", "            self.state.transition_to(State.IDLE)"),
           "        self._active_mouse_move = None"))
    add(_m("GRV16", "gravador", "as teclas ignoradas pelo filtro são gravadas", "o atalho de gravar/parar não entra no mapa",
           IS, "        if name in self.filters.ignored_keys:", "        if False:"))
    add(_m("GRV17", "gravador", "retomar a gravação não desconta o tempo parado", "pausa não conta no tempo gravado",
           IS, L("        with self._lock:", "            self._paused_total += max(0.0, self._clock() - self._pause_started)"),
           L("        with self._lock:", "            self._paused_total += 0.0")))

    # ---------------------------------------------------------------------------------------------- modelo (core, conditions)
    add(_m("MOD01", "modelo", "o trajeto do mouse se perde ao salvar", "mapa salvo e relido é idêntico",
           CORE, '"mouse_path": copy.deepcopy(self.mouse_path),', '"mouse_path": [],'))
    add(_m("MOD02", "modelo", "a migração do padrão antigo (250 ms) também altera valores personalizados", "só o par exato 250 ms + 0,375 s é migrado",
           CORE, "        if _stable_value == 250 and abs(_after_value - 0.375) < 1e-9:", "        if _stable_value == 250:"))
    add(_m("MOD03", "modelo", "repeat_count = 0 de mapa antigo continua 0 (inválido)", "mapas antigos com repeat_count 0 viram 1",
           CORE, '(lambda n: 1 if n == 0 else n)(int(data.get("repeat_count", -1)))', 'int(data.get("repeat_count", -1))'))
    add(_m("MOD04", "modelo", "a velocidade do mapa não é lida do arquivo", "velocidade persiste",
           CORE, 'speed=float(data.get("speed", 1.0)),', "speed=1.0,"))
    add(_m("MOD05", "modelo", "a duração calculada do texto conta um caractere a mais", "duração do texto = caracteres x intervalo",
           CORE, '    return max(0.0, len(str(text or "")) * max(0.0, value))', '    return max(0.0, (len(str(text or "")) + 1) * max(0.0, value))'))
    add(_m("MOD06", "modelo", "abrir aplicativo termina no mesmo instante em que começa (sem a barreira planejada)", "a timeline representa a barreira de abertura",
           CORE, "            return self.effective_start + self.computed_delay_after", "            return self.effective_start"))
    add(_m("MOD07", "modelo", "o arquivo de mapa grava a versão de formato 0", "format_version",
           CORE, '"format_version": FORMAT_VERSION,', '"format_version": 0,'))
    add(_m("MOD08", "modelo", "mapa sem envelope (JSON editado à mão) não é lido", "leitor tolerante: aceita o mapa cru",
           CORE, '    map_data = payload["map"] if "map" in payload else payload', '    map_data = payload["map"]'))
    add(_m("MOD09", "modelo", "IDLE passa a poder ir direto para PAUSED", "máquina de estados: transições permitidas",
           CORE, "State.IDLE: {State.RECORDING, State.RUNNING},", "State.IDLE: {State.RECORDING, State.RUNNING, State.PAUSED},"))
    add(_m("MOD10", "modelo", "o instante dos pontos do trajeto não é proporcional à duração", "movimento mesclado: um evento por ponto em tempo proporcional",
           CORE, "time=start + cmd.duration*frac", "time=start + frac"))
    add(_m("MOD11", "modelo", "as condições são anexadas a TODOS os eventos do comando", "condições valem só antes do primeiro evento",
           CORE, L('    if events and getattr(cmd, "conditions", None):', "        events[0].wait_conditions = copy.deepcopy(cmd.conditions)"),
           L('    if events and getattr(cmd, "conditions", None):', "        for _ev in events:", "            _ev.wait_conditions = copy.deepcopy(cmd.conditions)")))
    add(_m("MOD12", "modelo", "tecla/botão com duração 0 passa a ser válido", "duração 0 deixaria a tecla presa: é erro",
           CORE, "self.duration == 0 and self.type in (InputType.KEY, InputType.MOUSE_BUTTON)", "self.duration < 0 and self.type in (InputType.KEY, InputType.MOUSE_BUTTON)"))
    add(_m("MOD13", "modelo", "mover o mouse com duração 0 passa a ser inválido", "só teclas e botões têm tempo pressionado",
           CORE, "self.duration == 0 and self.type in (InputType.KEY, InputType.MOUSE_BUTTON)", "self.duration == 0 and self.type in (InputType.KEY, InputType.MOUSE_BUTTON, InputType.MOUSE_MOVE)"))
    add(_m("MOD14", "modelo", "velocidade 0 passa a ser válida", "speed deve ser maior que 0",
           CORE, "        if self.speed <= 0:", "        if self.speed < 0:"))
    add(_m("MOD15", "modelo", "IDs duplicados não são reparados", "mapas antigos com IDs repetidos são consertados",
           CORE, "            if not cid or cid in seen:", "            if not cid:"))
    add(_m("MOD16", "modelo", "movimento com só um dos eixos definido passa a ser válido", "movimento do mouse sem posição completa é erro",
           CORE, "            elif self.x is None or self.y is None:", "            elif self.x is None and self.y is None:"))
    add(_m("MOD17", "modelo", "o estado RUNNING deixa de poder ir para STOPPING", "máquina de estados: transições permitidas",
           CORE, "State.RUNNING: {State.PAUSED, State.STOPPING, State.ERROR},", "State.RUNNING: {State.PAUSED, State.ERROR},"))
    add(_m("MOD18", "modelo", "movimento mesclado perde a marca merged_move ao carregar", "mapa salvo e relido é idêntico",
           CORE, 'merged_move=bool(data.get("merged_move", False)),', "merged_move=False,"))
    add(_m("MOD19", "modelo", "comando desativado volta ativado ao carregar", "mapa salvo e relido é idêntico",
           CORE, 'enabled=bool(data.get("enabled", True)),', "enabled=True,"))
    add(_m("MOD20", "modelo", "as condições do comando não são lidas do arquivo", "mapa salvo e relido é idêntico",
           CORE, 'conditions=[c for raw in data.get("conditions", []) if (c := WaitCondition.from_dict(raw)) is not None],', "conditions=[],"))
    add(_m("MOD21", "modelo", "o mapa seguinte (encadeamento) não é lido", "mapa salvo e relido é idêntico",
           CORE, 'next_map=data.get("next_map") or None,', "next_map=None,"))
    add(_m("MOD22", "modelo", "a estabilidade de uma condição não é lida", "mapa salvo e relido é idêntico",
           "automationstudio/conditions.py", 'stable_ms=int(data.get("stable_ms", 1000)),', "stable_ms=1000,"))
    add(_m("MOD23", "modelo", "o atraso posterior de uma condição não é gravado", "mapa salvo e relido é idêntico",
           "automationstudio/conditions.py", '            "after": self.after,', '            "after": 0.0,'))
    add(_m("MOD24", "modelo", "a constante de execução do core não muda quando o usuário a muda", "set_runtime_defaults é o único ponto que altera as constantes",
           CORE, "        TEXT_CHAR_INTERVAL = float(text_char_interval)", "        pass"))

    # ---- achados 2.09 e 2.10 (a pré-visualização alterava o mapa; mover/reordenar cortava as sobreposições em zero) e operações de edição
    COND = "automationstudio/conditions.py"
    add(_m("MOD25", "modelo", "a pré-visualização volta a reencadear (e alterar) os inícios do mapa", "achado 2.09: timeline_rows só lê o mapa",
           CORE, "        return [{'id':c.id,'start':round(float(c.effective_start),6)",
           "        self.reflow_timeline(False)\n        return [{'id':c.id,'start':round(float(c.effective_start),6)"))
    add(_m("MOD26", "modelo", "a distância entre comandos sobrepostos volta a ser cortada em zero", "achado 2.10: a sobreposição (lacuna negativa) é preservada",
           CORE, "                gaps[id(cmd)] = float(cmd.start) - (float(previous.start) + float(previous.computed_delay_after))",
           "                gaps[id(cmd)] = max(0.0, float(cmd.start) - (float(previous.start) + float(previous.computed_delay_after)))"))
    add(_m("MOD27", "modelo", "o primeiro comando pode ficar com início negativo depois de mover", "nenhum início fica negativo",
           CORE, "                new_start = max(0.0, gap)", "                new_start = gap"))
    add(_m("MOD28", "modelo", "um comando do meio pode ficar com início negativo depois de mover", "nenhum início fica negativo",
           CORE, "                new_start = max(0.0, float(previous.start) + float(previous.computed_delay_after) + gap)",
           "                new_start = float(previous.start) + float(previous.computed_delay_after) + gap"))
    add(_m("MOD29", "modelo", "reordenar aceita uma lista de IDs que não é a do mapa", "reorder_to_ids recusa o que não é uma permutação dos comandos",
           CORE, L("        if set(ordered_ids) != set(by_id):", "            return False"), L("        if False:", "            return False")))
    add(_m("MOD30", "modelo", "mover devolve a faixa final com um comando a mais", "move_commands devolve (primeiro, último) da faixa movida",
           CORE, "        return target_index, target_index + len(moving) - 1", "        return target_index, target_index + len(moving)"))
    add(_m("MOD31", "modelo", "mover para o mesmo lugar sobe o comando uma posição", "mover para a posição em que o comando já está não muda nada",
           CORE, "        before_target = sum(1 for i, c in enumerate(original) if c.id in ids and i < target_index)",
           "        before_target = sum(1 for i, c in enumerate(original) if c.id in ids and i <= target_index)"))
    add(_m("MOD32", "modelo", "copiar mantém o início absoluto em vez do relativo à seleção", "copiar guarda os inícios relativos à seleção",
           CORE, "            c.start = max(0.0, float(original.start) - base)", "            c.start = float(original.start)"))
    add(_m("MOD33", "modelo", "colar não encosta o bloco no fim do comando anterior", "colar ancora o bloco no fim do comando anterior",
           CORE, "        base = self.commands[index - 1].effective_end if anchor_to_previous and index > 0 else 0.0", "        base = 0.0"))
    add(_m("MOD34", "modelo", "exportar leva todos os grupos do mapa, não só os usados", "o pacote exportado só leva os grupos usados",
           CORE, "        gids={c.group_id for c in selected if c.group_id}", "        gids=set(self.groups)"))
    add(_m("MOD35", "modelo", "importar aceita um arquivo que não é um pacote de comandos", "importar recusa arquivo incompatível",
           CORE, "            raise ValueError('Arquivo de comandos incompatível.')", "            pass"))
    add(_m("MOD36", "modelo", "excluir compactando soma dois trechos removidos que se sobrepõem", "excluir compactando une os trechos sobrepostos",
           CORE, "                if not merged or a > merged[-1][1]:", "                if True:"))
    add(_m("MOD37", "modelo", "excluir compactando desloca também quem começa dentro do trecho removido", "só desloca quem começa depois do trecho removido",
           CORE, "                shift = sum(max(0.0, b - a) for a, b in merged if b <= c.start)", "                shift = sum(max(0.0, b - a) for a, b in merged if a <= c.start)"))
    add(_m("MOD38", "modelo", "o contador de IDs pode recuar", "o contador de IDs só avança",
           CORE, "            if value >= self._next:", "            if True:"))
    add(_m("MOD39", "modelo", "um observador de estado com defeito derruba a transição", "o estado muda mesmo que um observador falhe",
           CORE, L("                listener(previous, target)", "            except Exception:"), L("                listener(previous, target)", "            except ZeroDivisionError:")))
    add(_m("MOD40", "modelo", "um observador de estado com defeito derruba a parada de emergência", "a parada de emergência volta a IDLE mesmo que um observador falhe",
           CORE, L("                listener(previous, State.IDLE)", "            except Exception:"), L("                listener(previous, State.IDLE)", "            except ZeroDivisionError:")))
    add(_m("MOD41", "modelo", "o teclado ABNT2 embutido muda de tamanho", "o substituto do layout do teclado é o ABNT2 de 75 teclas",
           CORE, '        return {"ref_w":900,"ref_h":290,"keys":keys}', '        return {"ref_w":901,"ref_h":290,"keys":keys}'))
    add(_m("MOD42", "modelo", "a pasta de dados gravada no registro é ignorada", "a pasta de dados escolhida pelo usuário vale",
           CORE, "                if raw:", "                if False:"))
    add(_m("MOD43", "modelo", "escolher a pasta de dados não grava nada no registro", "a pasta de dados escolhida é gravada",
           CORE, "                winreg.SetValueEx(key, 'DataDir', 0, winreg.REG_SZ, str(folder.resolve()))", "                pass"))
    add(_m("MOD44", "modelo", "os nomes de teclas em minúsculas deixam de ser reconhecidos", "resolve_key_labels ignora maiúsculas e minúsculas",
           CORE, "    upper = raw.upper()", "    upper = raw"))
    add(_m("MOD45", "modelo", "repeat_count igual a 0 passa na validação do mapa", "o mapa recusa repeat_count 0",
           CORE, "        if self.repeat_count == 0:", "        if False:"))
    add(_m("MOD46", "modelo", "precisão da imagem fora de 0–1 passa na validação", "a condição de imagem recusa precisão fora de 0–1",
           COND, "            if not 0.0 <= confidence <= 1.0:", "            if False:"))
    add(_m("MOD47", "modelo", "uma condição lida de algo que não é objeto vira condição vazia em vez de ser descartada", "WaitCondition.from_dict devolve None para o que não é objeto",
           COND, "        if not isinstance(data, dict):", "        if False:"))
    add(_m("MOD48", "modelo", "o tipo do comando recebido como texto não é normalizado", "Command aceita o tipo escrito como texto",
           CORE, "        if not isinstance(self.type, InputType):", "        if False:"))
    add(_m("MOD49", "modelo", "um ponto ilegível do trajeto derruba a montagem da timeline", "a timeline ignora pontos ilegíveis do trajeto",
           CORE, L('                    px=int(point.get("x",cmd.x or 0)); py=int(point.get("y",cmd.y or 0))', "                except Exception:", "                    continue"),
           L('                    px=int(point.get("x",cmd.x or 0)); py=int(point.get("y",cmd.y or 0))', "                except ZeroDivisionError:", "                    continue")))
    add(_m("MOD50", "modelo", "o log de execução levanta exceção quando não consegue gravar", "o log de execução nunca derruba o programa",
           CORE, L("            f.write(f\"[{datetime.now().isoformat(timespec='seconds')}] {message}\\n\")", "    except Exception:"),
           L("            f.write(f\"[{datetime.now().isoformat(timespec='seconds')}] {message}\\n\")", "    except ZeroDivisionError:")))

    # ---------------------------------------------------------------------------------------------- persistência
    add(_m("PER01", "persistencia", "excluir um mapa que não existe diz que excluiu", "delete_map devolve se algo foi excluído",
           PRJ, "        return cur.rowcount > 0", "        return True"))
    add(_m("PER02", "persistencia", "mapa ilegível some em silêncio (não entra em load_errors)", "mapa que não pôde ser lido fica visível",
           PRJ, '                self.load_errors.append(f"{name}: {reason}")', "                pass"))
    add(_m("PER03", "persistencia", "salvar não repara IDs duplicados", "IDs duplicados são reparados antes de gravar",
           PRJ, "        automation_map.repair_duplicate_command_ids()", "        pass", ocorrencia=1, total=2))
    add(_m("PER04", "persistencia", "salvar um mapa que já existe não atualiza o conteúdo", "salvar duas vezes grava a versão mais nova",
           PRJ, "ON CONFLICT(name) DO UPDATE SET payload=excluded.payload, updated_at=CURRENT_TIMESTAMP", "ON CONFLICT(name) DO NOTHING"))
    add(_m("PER05", "persistencia", "a conexão com o banco não é fechada", "nenhuma conexão SQLite vaza (trava de arquivo no Windows)",
           PRJ, L("        finally:", "            con.close()"), L("        finally:", "            pass"), ocorrencia=1, total=2))
    add(_m("PER06", "persistencia", "a migração dos JSON antigos roda de novo com o banco já preenchido", "migração só na primeira vez",
           PRJ, L("        if count:", "            return"), L("        if False:", "            return")))
    add(_m("PER07", "persistencia", "a migração do padrão antigo ignora o atraso pós-abertura", "só o par exato é migrado",
           PRJ, "            if saved.get('app_stable_ms') == 250 and abs(float(saved.get('app_after_open', -1)) - 0.375) < 1e-9:",
           "            if saved.get('app_stable_ms') == 250:"))
    add(_m("PER08", "persistencia", "as configurações visuais não são gravadas no banco", "configurações persistem",
           PRJ, "        self._data['visual']=dict(values); self.save()", "        self._data['visual']=dict(values)"))
    add(_m("PER09", "persistencia", "atalho de controle vazio é gravado", "atalhos de controle vazios não são gravados",
           PRJ, "{k:v for k,v in hotkeys.items() if v}", "dict(hotkeys)"))
    add(_m("PER10", "persistencia", "carregar um mapa pelo nome sempre tenta ler como arquivo JSON", "load_map lê do banco pelo nome",
           PRJ, "        if p.suffix.lower() == '.json':", "        if True:"))
    add(_m("PER11", "persistencia", "importar um mapa não o salva no banco", "import_map grava o mapa",
           PRJ, L("        automation_map = map_from_json(Path(source).read_text(encoding='utf-8'))", "        self.save_map(automation_map)"),
           "        automation_map = map_from_json(Path(source).read_text(encoding='utf-8'))"))
    add(_m("PER12", "persistencia", "salvar uma alteração do mapa limpa o 'refazer' só às vezes", "uma alteração nova descarta o 'refazer'",
           PRJ, "            self._redo.setdefault(m.name, []).clear()", "            pass"))
    add(_m("PER13", "persistencia", "o limite de memória do histórico não é limitado ao intervalo permitido", "limite de RAM do histórico",
           PRJ, "        self.ram_mb = max(self.MIN_RAM_MB, min(self.MAX_RAM_MB, int(ram_mb)))\n        self._undo", "        self.ram_mb = int(ram_mb)\n        self._undo"))
    add(_m("PER14", "persistencia", "desfazer não restaura os comandos", "desfazer devolve o mapa ao estado anterior",
           PRJ, "            m.commands=restored.commands; m.groups=restored.groups; m.repeat_count=restored.repeat_count",
           "            m.groups=restored.groups; m.repeat_count=restored.repeat_count"))
    add(_m("PER15", "persistencia", "desfazer não guarda o estado para 'refazer'", "refazer depois de desfazer",
           PRJ, 'dst.setdefault(m.name, []).append((current,self._size(current), label or "Alteração"))', "pass"))
    add(_m("PER16", "persistencia", "as configurações antigas (settings.json) migradas não são renomeadas", "migração de settings.json acontece uma vez",
           PRJ, "                legacy.rename(legacy.with_suffix('.json.migrado'))", "                pass"))

    # ---------------------------------------------------------------------------------------------- editor de comandos (2.07)
    i = INTERFACE
    add(_m("EDI01", "editor", "abrir um comando de texto e salvar apaga o texto", "achado 2.07: o editor carrega o texto",
           EDI, "        self.text_edit.setPlainText(str(getattr(c, 'text', '') or ''))\n", "", modo=i))
    add(_m("EDI02", "editor", "abrir e salvar apaga a descrição", "achado 2.07: o editor carrega a descrição",
           EDI, "        self.description.setText(str(getattr(c, 'description', '') or ''))\n", "", modo=i))
    add(_m("EDI03", "editor", "abrir e salvar zera o início do comando", "achado 2.07: o editor carrega o início",
           EDI, "        self._load_number(self.start, float(c.start))\n", "", modo=i))
    add(_m("EDI04", "editor", "abrir e salvar zera o atraso", "achado 2.07: o editor carrega o atraso",
           EDI, "        self._load_number(self.delay, float(c.delay))\n", "", modo=i))
    add(_m("EDI05", "editor", "abrir e salvar troca a duração por 0,1 s", "achado 2.07: o editor carrega a duração",
           EDI, "        self._load_number(self.duration, float(c.duration or .1))\n", "", modo=i))
    add(_m("EDI06", "editor", "abrir e salvar troca a direção e a quantidade da rolagem", "achado 2.07: o editor carrega a rolagem",
           EDI, "        self._load_scroll_widgets()\n", "", modo=i))
    add(_m("EDI07", "editor", "abrir e salvar apaga o grupo do comando", "achado 2.07: o editor carrega o grupo",
           EDI, "        self._select_group()\n", "", modo=i))
    add(_m("EDI08", "editor", "abrir e salvar apaga o processo a esperar", "achado 2.07: o editor carrega o processo",
           EDI, "        self._show_wait_process(getattr(c, 'wait_process', ''))\n", "", modo=i))
    add(_m("EDI09", "editor", "abrir e salvar zera o tempo limite da espera", "achado 2.07: o editor carrega o tempo limite",
           EDI, "        self._load_number(self.wait_timeout, float(getattr(c, 'wait_timeout', 0.0)))\n", "", modo=i))
    add(_m("EDI10", "editor", "abrir e salvar volta a estabilidade ao padrão", "achado 2.07: o editor carrega a estabilidade",
           EDI, "        self._load_number(self.wait_stable, int(getattr(c, 'wait_stable_ms', core.APP_STABLE_DEFAULT_MS)))\n", "", modo=i))
    add(_m("EDI11", "editor", "abrir e salvar volta o atraso pós-abertura ao padrão", "achado 2.07: o editor carrega o atraso pós-abertura",
           EDI, "        self._load_number(self.wait_after, float(getattr(c, 'wait_after_open', core.APP_AFTER_OPEN_DEFAULT)))\n", "", modo=i))
    add(_m("EDI12", "editor", "abrir e salvar apaga as condições do comando", "achado 2.07: o editor carrega as condições",
           EDI, L("        for existing in getattr(c, 'conditions', []) or []:", "            self._append_condition_item(existing)\n"), "", modo=i))
    add(_m("EDI13", "editor", "trocar de comando acumula as condições do anterior", "trocar de comando com o painel aberto recarrega tudo",
           EDI, "        self.condition_list.clear()\n", "", modo=i))
    add(_m("EDI14", "editor", "abrir um movimento e salvar perde a posição", "achado 2.07: o editor carrega a posição",
           EDI, "        self._move_pos = QPoint(int(c.x), int(c.y)) if c.x is not None and c.y is not None else None\n", "        self._move_pos = None\n", modo=i))
    add(_m("EDI15", "editor", "um valor maior que o limite da caixa é cortado ao abrir", "valor já salvo não é cortado no limite da caixa",
           EDI, L("        if value > spin.maximum():", "            spin.setMaximum(value)\n"), "", modo=i))
    add(_m("EDI16", "editor", "'manter pressionado' vira 'pressionar e soltar' ao abrir", "achado 2.07: o editor carrega o comportamento da tecla",
           EDI, "        action = c.action if c.type == InputType.KEY else ActionType.PRESS_AND_RELEASE\n", "        action = ActionType.PRESS_AND_RELEASE\n", modo=i))
    add(_m("EDI17", "editor", "o item-guia 'Nenhum aplicativo selecionado' é gravado como processo", "achado 2.07: o texto-guia nunca é um valor",
           EDI, "                return str(combo.itemData(i) or '')", "                return text", modo=i))
    add(_m("EDI18", "editor", "editar um comando desativado o reativa", "editar não reativa um comando desativado",
           EDI, "c.description=self.description.text().strip()\n", "c.description=self.description.text().strip(); c.enabled=True\n", modo=i))
    add(_m("EDI19", "editor", "editar um movimento mesclado zera a duração do trajeto", "achado 2.07: o trajeto gravado mantém o tempo",
           EDI, "            if not (c.merged_move and c.mouse_path): c.duration=0\n", "            c.duration=0\n", modo=i))
    add(_m("EDI20", "editor", "uma tecla que a lista não tem (ex.: ';') vira 'A' ao abrir", "achado 2.07: tecla fora da lista entra como item extra",
           EDI, "            if wanted and wanted not in vals: vals.append(wanted)\n", "", modo=i))
    add(_m("EDI21", "editor", "um aplicativo fora da lista vira o texto-guia ao abrir", "achado 2.07: executável fora da lista entra como item extra",
           EDI, "            if current and idx < 0:", "            if False:", modo=i))
    add(_m("EDI22", "editor", "o grupo que só o comando conhece perde o nome ao salvar", "achado 2.07: grupo fora da lista é preservado",
           EDI, "c.group=self.group_combo.currentText() if (c.group_id or self.group_combo.currentIndex() > 0) else ''",
           "c.group=self.group_combo.currentText() if c.group_id else ''", modo=i))
    add(_m("EDI23", "editor", "o alvo de um botão do mouse vira 'tecla' ao trocar o tipo", "alvo só é tecla quando o comando é do tipo tecla",
           EDI, "wanted=str(self._command.target or '').strip().upper() if self._command.type == InputType.KEY else ''",
           "wanted=str(self._command.target or '').strip().upper()", modo=i))
    add(_m("EDI24", "editor", "o alvo de uma tecla vira aplicativo ao trocar o tipo", "alvo só é aplicativo quando o comando abre aplicativo",
           EDI, "current=str(self._command.target or '') if self._command.type == InputType.APP_OPEN else ''", "current=str(self._command.target or '')", modo=i))
    add(_m("EDI25", "editor", "abrir aplicativo sem escolha grava o texto-guia como aplicativo", "achado 2.07: o texto-guia nunca é um valor",
           EDI, "c.target=self.target_combo.currentData() or ''; c.text=''; c.action=ActionType.PRESS_AND_RELEASE",
           "c.target=self.target_combo.currentData() or self.target_combo.currentText().strip(); c.text=''; c.action=ActionType.PRESS_AND_RELEASE", modo=i))
    add(_m("EDI26", "editor", "o rótulo da posição troca X e Y", "o rótulo mostra a posição certa",
           EDI, "f'Posição definida: X={self._move_pos.x()}, Y={self._move_pos.y()}'", "f'Posição definida: X={self._move_pos.y()}, Y={self._move_pos.x()}'", modo=i))
    add(_m("EDI27", "editor", "o editor aberto pela primeira vez não carrega os campos do comando", "achado 2.07: abrir e salvar sem mexer não altera o comando",
           EDI, "lay.addStretch(1); self._reload_from_command()", "lay.addStretch(1); self._set_type_from_command(); self._update_form()", modo=i))
    add(_m("EDI28", "editor", "load_command não recarrega os campos (só tipo e alvo)", "achado 2.07: trocar de comando recarrega todos os campos",
           EDI, L("        self._command = copy.deepcopy(command)", "        self._reload_from_command()"),
           L("        self._command = copy.deepcopy(command)", "        self._set_type_from_command(); self._update_form()"), modo=i))
    add(_m("EDI29", "editor", "a direção da rolagem para cima e para baixo é trocada ao abrir", "achado 2.07: o editor carrega a direção",
           EDI, "        direction = 0 if dy > 0 else 1 if dy < 0 else 2 if dx < 0 else 3 if dx > 0 else 0\n",
           "        direction = 1 if dy > 0 else 0 if dy < 0 else 2 if dx < 0 else 3 if dx > 0 else 0\n", modo=i))
    add(_m("EDI30", "editor", "a rolagem para cima é salva com o sinal trocado", "o comando de rolagem sai do editor com o sinal certo",
           EDI, "c.scroll_dy=(lines if direction=='up' else -lines if direction=='down' else 0)", "c.scroll_dy=(-lines if direction=='up' else lines if direction=='down' else 0)", modo=i))

    # ---------------------------------------------------------------------------------------------- redes de segurança dos testes
    add(_m("NET01", "redes", "a rede que bloqueia abrir aplicativo de verdade nos testes é desligada", "nenhum teste abre um aplicativo na máquina de quem roda a suíte",
           "tests/conftest.py", "    copia.Popen = bloqueado\n", "    copia.Popen = subprocess.Popen\n"))
    add(_m("NET02", "redes", "um arquivo de referência (golden) é adulterado: um evento muda de tipo", "os cenários comparam com o golden, evento a evento",
           GOLD + "abrir_aplicativo_esperar_digitar_e_salvar.json", '[3.6, "key_down", "S"]', '[3.6, "key_up", "S"]'))
    add(_m("NET03", "redes", "um arquivo de referência (golden) sem cenário que o use", "golden órfão é lixo que parece garantia",
           "tests/data/golden/orfao_sem_cenario.json", novos_arquivos=(("tests/data/golden/orfao_sem_cenario.json", "{}\n"),),
           antes="", depois="", funcao=None))
    add(_m("NET04", "redes", "um golden é editado à mão e sai do formato que o programa grava", "golden no formato que `serializar` produz",
           GOLD + "abrir_aplicativo_esperar_digitar_e_salvar.json", '"eventos": [', '"eventos":   ['))
    add(_m("NET05", "redes", "um golden é apagado", "todo cenário tem o seu golden",
           GOLD + "mapa_real_click_genshin.json", apagar=True))
    add(_m("NET06", "redes", "um teste de janela deixa de pedir o isolamento de GUI", "todo teste de janela usa a fixture gui",
           "tests/gui/test_command_dialog.py", "def test_comando_novo_nasce_ativado(gui):", "def test_comando_novo_nasce_ativado():"))
    add(_m("NET07", "redes", "um teste dorme 2 s em tempo real", "nenhum teste dorme mais de meio segundo de verdade",
           "tests/engine/test_engine_timing.py", acrescentar=L("def test_dorme_de_verdade():", "    import time", "    time.sleep(2)")))
    add(_m("NET08", "redes", "um arquivo de teste repete o nome de uma função de teste", "a segunda definição apagaria o primeiro teste",
           "tests/engine/test_engine_timing.py",
           funcao=lambda t: t + "\n\ndef test_comando_desativado_nao_chega_ao_backend():\n    assert True\n"))
    add(_m("NET09", "redes", "dois arquivos de teste com o mesmo nome", "nomes de arquivo de teste únicos no projeto",
           "tests/persistence/test_fake_clock.py", novos_arquivos=(("tests/persistence/test_fake_clock.py", "def test_x():\n    assert True\n"),)))
    add(_m("NET10", "redes", "o script .bat passa a ter só LF no fim das linhas", "scripts .bat com CRLF",
           "Iniciar.bat", binario=True, funcao=lambda b: b.replace(b"\r\n", b"\n")))
    add(_m("NET11", "redes", "o script de início volta a escolher 'py -3'", "o Python vem de python_version.txt",
           "Iniciar.bat", binario=True, funcao=lambda b: b.replace(b'py.exe -%AS_PY% -c "import PySide6', b'py.exe -3 -c "import PySide6', 1)))
    add(_m("NET12", "redes", "a versão do pacote diverge do README e do CHANGELOG", "uma versão só em código, README e CHANGELOG",
           "automationstudio/__init__.py", '__version__ = "25.6"', '__version__ = "25.5"'))
    add(_m("NET13", "redes", "o instalador deixa de instalar o pynput", "o instalador instala tudo o que o requirements.txt pede",
           "Instalar_Dependencias_Global.bat", binario=True, funcao=lambda b: b.replace(b"pynput", b"pynputx")))
    add(_m("NET14", "redes", "o título da janela ganha a versão escrita à mão", "a versão vem de um lugar só",
           "automationstudio/main_window.py", acrescentar='_TITULO_ANTIGO = "Automation Studio AS 25.5"'))
    add(_m("NET15", "redes", "o e2e do Windows chama um método que o ambiente não tem (erro de digitação em código cego)", "toda chamada do e2e existe na superfície do ambiente",
           "tests/testsupport/verificacoes_e2e.py", "            backend.key_down(nome)\n", "            backend.key_downn(nome)\n"))
    add(_m("NET16", "redes", "o e2e do Windows clica sem conferir que a janela de teste está na frente", "nenhum envio de entrada de verdade sem a conferência de primeiro plano",
           "tests/testsupport/verificacoes_e2e.py",
           L('        _ir_para(amb, janela, backend, "botao")', '        for botao in ("left", "middle", "right"):'),
           L("        backend.mouse_move(*janela.centro(\"botao\"))", '        for botao in ("left", "middle", "right"):')))

    # ---- a catraca de cobertura e o modo `cobertura` do atalho de testes
    CAT = "tests/testsupport/catraca_cobertura.py"
    add(_m("NET17", "redes", "a catraca aceita uma cobertura que caiu (comparação invertida)", "a cobertura de cada parte não pode cair",
           CAT, 'elif agora["percentual"] < antigo["percentual"] - tolerancia:', 'elif agora["percentual"] > antigo["percentual"] - tolerancia:'))
    add(_m("NET18", "redes", "a catraca ignora uma parte que sumiu da medição", "uma parte que some da medição é problema",
           CAT, '            problemas.append(f"{grupo}: sumiu da medição (o baseline tinha {antigo[\'percentual\']:.1f}%)")', "            pass"))
    add(_m("NET19", "redes", "a catraca esquece os ramos na porcentagem", "a porcentagem é a do coverage.py (linhas e ramos)",
           CAT, ' + int(resumo.get("covered_branches", 0) or 0)', ""))
    add(_m("NET20", "redes", "a primeira rodada não grava o baseline", "o baseline é gravado na primeira rodada",
           CAT, "    if args.gravar or baseline is None:", "    if args.gravar:"))
    add(_m("NET21", "redes", "uma queda regrava o baseline e apaga a prova", "uma queda nunca regrava o baseline sozinha",
           CAT, '        saida("\\nA COBERTURA CAIU (o baseline não foi alterado):")',
           '        gravar_baseline(args.baseline, atual, versao)\n        saida("\\nA COBERTURA CAIU (o baseline não foi alterado):")'))
    add(_m("NET22", "redes", "uma queda de cobertura sai com código 0", "uma queda de cobertura reprova (código 1)",
           CAT, '--gravar")\n        return 1\n', '--gravar")\n        return 0\n'))
    add(_m("NET23", "redes", "um módulo novo do pacote que nenhum grupo da catraca conhece", "todo módulo do pacote pertence a um grupo da catraca",
           "automationstudio/modulo_sem_grupo.py", novos_arquivos=(("automationstudio/modulo_sem_grupo.py", "VALOR = 1\n"),)))
    add(_m("NET24", "redes", "o modo cobertura não chama a catraca", "o modo cobertura confere a catraca",
           "tests/testsupport/rodar_testes.py", '"catraca_cobertura.py"', '"catraca_cobertura_inexistente.py"'))
    add(_m("NET25", "redes", "a catraca roda mesmo com uma medição parcial (argumentos extras)", "medição parcial não passa pela catraca",
           "tests/testsupport/rodar_testes.py", "            if extras:\n                plano.avisos.append", "            if False:\n                plano.avisos.append"))

    # ---- o lançador de testes: isolamento da janela principal, retomada depois de um travamento, resumo (25.6)
    RT = "tests/testsupport/rodar_testes.py"
    add(_m("NET26", "redes", "o `-m` que o usuário passou é descartado e só o do lançador vale",
           "um marcador do usuário é combinado com o do lançador, e não substituído (com dois `-m` só o último vale)",
           RT, '            saida += ["-m", f"({extras[i + 1]}) and ({expressao})"]', '            saida += ["-m", expressao]'))
    add(_m("NET27", "redes", "a coleta dos testes isolados pede justamente os que NÃO são isolados",
           "o passo isolado coleta só os testes marcados `isolado`",
           RT, '+ combinar_marcador(extras, "isolado")', '+ combinar_marcador(extras, "not isolado")'))
    add(_m("NET28", "redes", "o passo comum deixa de excluir os testes isolados",
           "a janela principal não roda também dentro do processo comum",
           RT, '        selecionados = combinar_marcador(extras, "not isolado") if isolar else extras', "        selecionados = extras"))
    add(_m("NET29", "redes", "o tempo do pytest-timeout de um teste isolado passa do tempo do lançador",
           "ordem dos tempos: vigia < pytest-timeout < lançador",
           RT, "timeout_s=LIMITE_ISOLADO_S - 30)", "timeout_s=LIMITE_ISOLADO_S + 30)"))
    add(_m("NET30", "redes", "um teste isolado que estourou o tempo não é dado como travado",
           "estourar o tempo é TRAVOU",
           RT, "    if estourou or deixou_relatorio or codigo == diag.CODIGO_DE_TRAVAMENTO:", "    if deixou_relatorio or codigo == diag.CODIGO_DE_TRAVAMENTO:"))
    add(_m("NET31", "redes", "a saída com o código do vigia (86) não é dada como travamento",
           "o código 86 é TRAVOU",
           RT, "    if estourou or deixou_relatorio or codigo == diag.CODIGO_DE_TRAVAMENTO:", "    if estourou or deixou_relatorio:"))
    add(_m("NET32", "redes", "um teste isolado que só foi PULADO é contado como OK",
           "um teste pulado aparece como PULADO no resumo",
           RT, '        return "PULADO" if resumo and "skipped" in resumo and "passed" not in resumo else "OK"', '        return "OK"'))
    add(_m("NET33", "redes", "o processo que morreu por queda do Qt é chamado de falha de teste",
           "uma queda do Qt (código estranho) é QUEDA, e não FALHOU",
           RT, L('        return "FALHOU"', '    return "QUEDA"'), L('        return "FALHOU"', '    return "FALHOU"')))
    add(_m("NET34", "redes", "depois de um travamento o passo comum não roda de novo",
           "um travamento não esconde os testes que viriam depois dele",
           RT, L('        if not nodeid or "pytest" not in comando or tentativa == TENTATIVAS_DE_RETOMADA:', "            break"),
           L("        if True:", "            break")))
    add(_m("NET35", "redes", "a rodada que travou, mas em que o resto passou, sai com código 0",
           "houve travamento: a rodada não está limpa",
           RT, "    if travados and codigo == 0:", "    if False and codigo == 0:"))
    add(_m("NET36", "redes", "a nova rodada não deixa de fora o teste que travou",
           "a retomada roda SEM o teste que travou (`--deselect`)",
           RT, '        adicionais += ["--deselect", nodeid]', "        adicionais += []"))
    add(_m("NET37", "redes", "os relatórios de travamento da rodada anterior não são apagados antes de começar",
           "um relatório velho não pode acusar um teste da rodada nova",
           RT, "                caminho.unlink()", "                pass"))
    add(_m("NET38", "redes", "o texto do relatório de travamento é lido desde o começo do arquivo",
           "só o texto NOVO do relatório pertence ao teste que acabou de rodar",
           RT, "        entrada.seek(tamanho_antes)", "        entrada.seek(0)"))
    add(_m("NET39", "redes", "o relatório do alarme nativo é anexado mas não apagado",
           "o arquivo do alarme nativo não sobra para o teste seguinte",
           RT, "            nativo.unlink()", "            pass"))
    add(_m("NET40", "redes", "nenhum teste rodou em lugar nenhum e a rodada sai com código 0",
           "nada rodar é falha (código 5)",
           RT, "            codigo = 5   # nada rodou em lugar nenhum", "            codigo = 0   # nada rodou em lugar nenhum"))
    add(_m("NET41", "redes", "o passo comum vazio (código 5) reprova a rodada mesmo com o passo isolado rodando",
           "o passo comum pode ficar vazio quando o `-k` só casa com testes isolados",
           RT, L("                if vazio:", "                    codigo_do_passo = 0"), L("                if False:", "                    codigo_do_passo = 0")))
    add(_m("NET42", "redes", "o passo isolado com uma falha sai com código 0",
           "a falha de um teste isolado reprova a rodada",
           RT, '    return (diag.CODIGO_DE_TRAVAMENTO if so_travamentos else 1), registros', "    return 0, registros"))
    add(_m("NET43", "redes", "o resumo não manda enviar o relatório de travamento",
           "o resumo diz qual arquivo enviar quando algum teste travou",
           RT, '    if any(r.estado == "TRAVOU" for r in resultados):', "    if False:"))
    add(_m("NET44", "redes", "o teste isolado que passa do tempo não é encerrado à força",
           "o lançador mata o processo que passa do tempo e segue para o próximo teste",
           RT, "                    processo.kill()", "                    pass"))
    add(_m("NET45", "redes", "o teste isolado roda sem tempo limite",
           "cada teste isolado tem tempo limite",
           RT, "_rodar(passo.comando + [nodeid], raiz, env, arquivo, passo.limite_s)", "_rodar(passo.comando + [nodeid], raiz, env, arquivo)"))
    add(_m("NET46", "redes", "o relatório de travamento deixado pelo teste não conta como travamento",
           "o relatório do vigia ou do alarme nativo classifica o teste como TRAVOU, mesmo com código de saída 1",
           RT, "        deixou_relatorio = bool(_recolher_relatorios(raiz, antes))", "        deixou_relatorio = False"))
    add(_m("NET47", "redes", "uma coleta que falha é tratada como 'nenhum teste isolado'",
           "uma coleta que falha reprova a rodada",
           RT, "        if codigo not in (0, 5) or estourou:", "        if False:"))
    add(_m("NET48", "redes", "os relatórios de travamento velhos deixam de ser apagados pelo plano",
           "o plano manda apagar os relatórios de travamento antes de começar",
           RT, '        plano.apagar_antes = [f"logs/{diag.ARQUIVO_DO_RELATORIO}", f"logs/{diag.ARQUIVO_DO_ALARME_NATIVO}"]', "        plano.apagar_antes = []"))
    add(_m("NET49", "redes", "o ambiente das rodadas deixa de forçar o modo UTF-8 do Python",
           "o log com acento (pasta de usuário acentuada) sai legível",
           RT, '    env.setdefault("PYTHONUTF8", "1")', "    pass"))
    add(_m("NET50", "redes", "a cobertura deixa de apagar os dados da rodada anterior",
           "dados velhos de cobertura não entram no relatório novo",
           RT, '            plano.apagar_antes += ["logs/.coverage*", "logs/coverage.json"]', "            pass"))
    add(_m("NET51", "redes", "a cobertura roda sem `-p`: cada processo apaga os dados do anterior",
           "cada processo grava o seu arquivo de dados de cobertura",
           RT, '"run", "-p", "--branch"', '"run", "--branch"'))
    add(_m("NET52", "redes", "a cobertura não junta os dados dos vários processos",
           "os dados de todos os processos são combinados antes do relatório",
           RT, '[[sys.executable, "-m", "coverage", "combine"], [sys.executable, "-m", "coverage", "report", "-m"]]',
           '[[sys.executable, "-m", "coverage", "report", "-m"]]'))

    # ---- o diagnóstico de travamento (25.6)
    DQ = "tests/testsupport/diagnostico_qt.py"
    add(_m("NET53", "redes", "o diagnóstico troca BLOQUEIO por LAÇO DE EVENTOS",
           "o diagnóstico diz se o Qt está bloqueado (nenhum evento) ou em laço (eventos sem parar)",
           DQ, "    if silencio >= silencio_minimo_s:", "    if silencio < silencio_minimo_s:"))
    add(_m("NET54", "redes", "o vigia encerra o processo com um código que o lançador não reconhece",
           "o vigia sai com o código 86",
           DQ, "        self._sair(CODIGO_DE_TRAVAMENTO)", "        self._sair(1)"))
    add(_m("NET55", "redes", "o vigia dispara mesmo depois de o teste ter terminado",
           "um teste que terminou a tempo não é encerrado pelo vigia",
           DQ, L("        if self._parar.is_set():", "            return                                   # o teste terminou neste instante"),
           L("        if False:", "            return                                   # o teste terminou neste instante")))
    add(_m("NET56", "redes", "o travamento é atribuído ao PRIMEIRO teste citado no relatório",
           "o relatório vale para o último teste citado",
           DQ, "    ultimo = achados[-1]", "    ultimo = achados[0]"))
    add(_m("NET57", "redes", "o arquivo do alarme nativo sobra quando o teste termina a tempo",
           "o arquivo do alarme nativo só existe se o alarme disparou",
           DQ, "            self.arquivo_nativo.unlink()", "            pass"))
    add(_m("NET58", "redes", "o alarme nativo dispara junto com o vigia, e não depois dele",
           "o alarme nativo é a rede de segurança: dispara DEPOIS do vigia",
           DQ, "faulthandler.dump_traceback_later(self.limite_s + FOLGA_DO_ALARME_NATIVO_S, exit=True,",
           "faulthandler.dump_traceback_later(self.limite_s, exit=True,"))
    add(_m("NET59", "redes", "o alarme nativo despeja as pilhas mas não encerra o processo",
           "o alarme nativo encerra o processo travado",
           DQ, "FOLGA_DO_ALARME_NATIVO_S, exit=True, file=", "FOLGA_DO_ALARME_NATIVO_S, exit=False, file="))
    add(_m("NET60", "redes", "o filtro de eventos CONSOME os eventos",
           "o filtro só observa: nunca consome um evento",
           DQ, L("            return False", "", "    filtro = FiltroDeEventos()"), L("            return True", "", "    filtro = FiltroDeEventos()")))
    add(_m("NET61", "redes", "as mensagens do Qt deixam de ser impressas no console",
           "o tratador de mensagens anota E continua imprimindo",
           DQ, "                print(mensagem, file=sys.__stderr__, flush=True)", "                pass"))
    add(_m("NET62", "redes", "o tratador de mensagens anterior do Qt não é restaurado",
           "ao encerrar, o tratador de mensagens do Qt volta ao anterior",
           DQ, "        qtcore.qInstallMessageHandler(anterior)", "        qtcore.qInstallMessageHandler(None)"))
    add(_m("NET63", "redes", "um limite de tempo zero ou negativo no ambiente é aceito",
           "o limite do ambiente só vale se for um número positivo",
           DQ, "    return valor if valor > 0 else padrao", "    return valor"))
    add(_m("NET64", "redes", "o cabeçalho do relatório de travamento perde a marca que o lançador lê",
           "o lançador lê do relatório QUAL teste travou",
           DQ, '              f"{MARCA_DO_TESTE}{nome}",', '              f"{nome}",'))
    add(_m("NET65", "redes", "o vigia ignora a fase atual do teste que o pytest informa",
           "o relatório diz em que fase (setup, call, teardown) o teste travou",
           DQ, '        return os.environ.get("PYTEST_CURRENT_TEST") or self.nome', "        return self.nome"))
    add(_m("NET66", "redes", "o alarme consulta o Qt (versões e plataforma) na thread do vigia",
           "a thread do vigia só lê estruturas do Python: o ambiente é descrito antes, na thread da interface",
           DQ, "mensagens=self.mensagens, pilhas=pilhas_das_threads(), ambiente=self.ambiente, agora=agora,",
           "mensagens=self.mensagens, pilhas=pilhas_das_threads(), ambiente=descrever_ambiente(), agora=agora,"))
    add(_m("NET67", "redes", "encerrar o vigia deixa o filtro de eventos instalado na aplicação",
           "ao encerrar, o filtro de eventos é removido",
           DQ, "            self._desfazer.append(remover)", "            pass"))
    add(_m("NET68", "redes", "o executor mínimo não informa qual é o teste atual",
           "o vigia sabe qual teste travou também sem o pytest",
           "tests/testsupport/run_minimal.py",
           '        os.environ["PYTEST_CURRENT_TEST"] = f"{nodeid} (call)"  # como o pytest: o vigia de testes de janela o lê', "        pass"))

    # ---- a higiene das janelas e o relato das falhas (25.6)
    GH = "tests/testsupport/gui_helpers.py"
    add(_m("NET69", "redes", "processar os eventos faz uma passada só quando o tempo é zero",
           "uma passada só deixa o layout de uma janela nova pela metade: no mínimo duas",
           GH, "        if passadas >= passadas_minimas and relogio() >= fim:", "        if relogio() >= fim:"))
    add(_m("NET70", "redes", "esvaziar a fila não manda executar os `deleteLater` pendentes",
           "o `processEvents` fora de um laço de eventos não executa os `deleteLater`: é preciso enviá-los",
           GH, L("    try:", "        enviar_exclusoes()"), L("    try:", "        pass")))
    add(_m("NET71", "redes", "esvaziar a fila não processa os eventos que a exclusão deixou",
           "depois das exclusões a fila é processada de novo",
           GH, L("        pass", "    processar_eventos(0, app=app, relogio=relogio, dormir=dormir)"), "        pass"))
    add(_m("NET72", "redes", "descartar as janelas não manda destruí-las",
           "as janelas de um teste não ficam vivas no teste seguinte",
           GH, "        janela.deleteLater()", "        pass"))
    add(_m("NET73", "redes", "descartar as janelas não para o motor",
           "o motor de uma janela descartada não continua rodando",
           GH, "        janela.engine.emergency_stop()", "        pass"))
    add(_m("NET74", "redes", "descartar as janelas não para o relógio da interface",
           "o relógio da interface de uma janela descartada não continua disparando",
           GH, "        janela._ui_refresh_timer.stop()", "        pass"))
    add(_m("NET75", "redes", "descartar as janelas não esvazia a fila de eventos",
           "nada de um teste sobra na fila do seguinte",
           GH, "    esvaziar_fila(app, **opcoes)", "    pass"))
    add(_m("NET76", "redes", "descartar as janelas não deixa o coletor de lixo do Python soltar os ciclos",
           "as janelas formam ciclos de referência: o coletor roda ao fim do teste",
           GH, L("    esvaziar_fila(app, **opcoes)", "    coletar()"), "    esvaziar_fila(app, **opcoes)"))
    add(_m("NET77", "redes", "uma falha de teste não é impressa na hora",
           "a falha aparece no console quando acontece, não só no fim da rodada",
           "tests/conftest.py", '        print("\\n".join(partes), flush=True)', "        pass"))
    add(_m("NET78", "redes", "um teste que passou também é impresso como falha",
           "só o que falhou é impresso na hora",
           "tests/conftest.py", L('    if not getattr(report, "failed", False):', "        return"), L("    if False:", "        return")))
    add(_m("NET79", "redes", "a fixture `gui` não liga o vigia de travamento",
           "todo teste de janela tem o vigia ligado",
           "tests/conftest.py", '    diagnostico_qt.iniciar(os.environ.get("PYTEST_CURRENT_TEST", "teste de janela"), ROOT / "logs")', "    pass", modo=i))
    add(_m("NET80", "redes", "a fixture `gui` deixa o vigia armado depois do teste",
           "um vigia que sobra mataria o processo no meio de outro teste",
           "tests/conftest.py", "    diagnostico_qt.encerrar_atual()", "    pass", modo=i))
    add(_m("NET81", "redes", "o teste da janela principal deixa de ser isolado (marcador `isolado` removido)",
           "todo teste que abre a janela principal roda um por processo",
           "tests/gui/test_main_window_smoke.py", "pytestmark = [pytest.mark.gui, pytest.mark.isolado]", "pytestmark = [pytest.mark.gui]"))
    add(_m("NET82", "redes", "o marcador `isolado` deixa de ser declarado no pytest.ini",
           "todo marcador usado nos testes está declarado (o pytest estrito recusaria)",
           "pytest.ini", "\n    isolado: o Rodar_Testes.bat roda cada um num processo próprio, com tempo limite (janela principal)", ""))

    # ---- os .bat e a pasta de usuário com acento (25.6)
    add(_m("NET83", "redes", "o script de início volta a copiar o caminho do Python com `for /f`",
           "nenhum .bat copia texto do Python para uma variável (o cmd entende errado um caminho com acento)",
           "Iniciar.bat", binario=True,
           funcao=lambda b: b.replace(b'set "PYTHONUTF8="\r\n',
                                      b'for /f "delims=" %%P in (\'py.exe -%AS_PY% -c "import sys; print(sys.executable)"\') do set "PYTHONW=%%P"\r\nset "PYTHONUTF8="\r\n', 1)))
    add(_m("NET84", "redes", "o script de início ganha uma letra acentuada",
           "os .bat só têm ASCII (o cmd lê o arquivo na página de código do console)",
           "Iniciar.bat", binario=True,
           funcao=lambda b: b.replace(b"rem O programa abre pelo pyw.exe", "rem O programa abre pelo pyw.exe, não".encode("utf-8"), 1)))
    add(_m("NET85", "redes", "o script de início grava o log do Python sem o modo UTF-8",
           "o Python que escreve no log roda em modo UTF-8",
           "Iniciar.bat", binario=True, funcao=lambda b: b.replace(b'set "PYTHONUTF8=1"', b'set "PYTHONUTF8="', 1)))
    # --- o passo isolado desiste depois de travamentos SEGUIDOS (poupa o tempo de quem tem uma rodada de 22 travamentos)
    add(_m("NET86", "redes", "o passo isolado não desiste depois de vários travamentos seguidos",
           "depois de 3 travamentos seguidos os testes que faltam não rodam e a rodada diz quantos foram",
           RT, '        if seguidos >= LIMITE_DE_TRAVAMENTOS_SEGUIDOS and numero < len(ids):', "        if False:"))
    add(_m("NET87", "redes", "um teste que passa não zera a contagem de travamentos seguidos",
           "só travamentos SEGUIDOS interrompem o passo isolado",
           RT, '        seguidos = seguidos + 1 if estado == "TRAVOU" else 0', '        seguidos = seguidos + 1 if estado == "TRAVOU" else seguidos'))
    add(_m("NET88", "redes", "o passo isolado desiste no primeiro travamento",
           "o limite de travamentos seguidos é 3",
           RT, "LIMITE_DE_TRAVAMENTOS_SEGUIDOS = 3 ", "LIMITE_DE_TRAVAMENTOS_SEGUIDOS = 1 "))
    add(_m("NET89", "redes", "os testes que não rodaram somem do registro do passo isolado",
           "cada teste que não rodou aparece como NAO_RODOU",
           RT, '            registros += [{"nodeid": restante, "estado": "NAO_RODOU", "segundos": 0.0, "codigo": None} for restante in restantes]',
           "            registros += []"))
    add(_m("NET90", "redes", "o código do passo isolado é o do primeiro teste ruim (um travamento esconde uma falha que veio depois)",
           "uma falha de teste vale mais que um travamento no código de saída do passo isolado",
           RT, '    return (diag.CODIGO_DE_TRAVAMENTO if so_travamentos else 1), registros',
           '    return (diag.CODIGO_DE_TRAVAMENTO if ruins[0]["estado"] == "TRAVOU" else 1), registros'))
    add(_m("NET91", "redes", "um travamento esconde a falha de outro teste no código de saída do passo isolado",
           "uma falha de teste vale mais que um travamento no código de saída do passo isolado",
           RT, '    so_travamentos = all(r["estado"] in ("TRAVOU", "NAO_RODOU") for r in ruins)',
           '    so_travamentos = any(r["estado"] in ("TRAVOU", "NAO_RODOU") for r in ruins)'))
    add(_m("NET92", "redes", "os testes que não rodaram contam como falha no código de saída do passo isolado",
           "depois de 3 travamentos seguidos o código de saída continua sendo o do travamento (86)",
           RT, '    so_travamentos = all(r["estado"] in ("TRAVOU", "NAO_RODOU") for r in ruins)',
           '    so_travamentos = all(r["estado"] in ("TRAVOU",) for r in ruins)'))
    add(_m("NET93", "redes", "encerrar um teste de janela não esvazia a fila de eventos",
           "o que o teste deixou na fila (e as exclusões pendentes) não sobra para o teste seguinte",
           GH, "        esvaziar_fila(app=app, **opcoes)", "        pass"))
    add(_m("NET94", "redes", "encerrar um teste de janela não deixa o coletor de lixo do Python soltar o que sobrou",
           "o lixo de um teste de janela é solto ao fim dele, e não no meio de um teste posterior (abort do Windows de 01/11/2026)",
           GH, L("    finally:", "        coletar()"), L("    finally:", "        pass")))
    add(_m("NET95", "redes", "a fixture `gui` não chama o encerramento do teste de janela",
           "todo teste de janela solta o seu lixo ao terminar",
           "tests/conftest.py", "        gui_helpers.encerrar_teste_de_janela()   # o lixo do teste é solto AGORA, e não no meio de um teste posterior",
           "        pass"))

    # ---------------------------------------------------------------------------------------------- checagens estáticas
    add(_m("EST01", "estatico", "nome inexistente numa função pouco usada (KeyCode digitado errado)", "achado 1.04: nome global inexistente",
           IS, "        return KeyCode.from_char(text)", "        return KeyCodeX.from_char(text)"))
    add(_m("EST02", "estatico", "um método é definido duas vezes na mesma classe", "achado 1.0x: a segunda definição apaga a primeira",
           IS, L("    def is_running(self) -> bool:", "        return self.state.state in (State.RUNNING, State.PAUSED)"),
           L("    def is_running(self) -> bool:", "        return self.state.state in (State.RUNNING, State.PAUSED)", "",
              "    def is_running(self) -> bool:", "        return False")))
    add(_m("EST03", "estatico", "chamada a um método privado que não existe, numa tela que nenhum teste de lógica executa", "chamada self._metodo() sem definição",
           "automationstudio/overlays.py", "scale,ox,oy=self._transform(); px=", "scale,ox,oy=self._transformx(); px="))
    add(_m("EST04", "estatico", "um sinal da ponte do motor perde o connect", "todo sinal das pontes tem connect",
           "automationstudio/main_window.py", "        self.bridge.chain_requested.connect(self._on_chain_requested)\n", ""))
    add(_m("EST05", "estatico", "uma constante de execução é copiada por valor fora do core", "constantes de execução têm fonte única no core",
           PRJ, "class MapHistory:", "_COPIA_DO_PADRAO = APP_STABLE_DEFAULT_MS\n\n\nclass MapHistory:"))
    add(_m("EST06", "estatico", "uma string com \\n literal (barra + n) em vez de quebra de linha", "nenhuma string do pacote tem \\n literal",
           "automationstudio/vision.py", acrescentar="_TEXTO_COM_BARRA_N = 'linha1\\\\nlinha2'"))
    add(_m("EST07", "estatico", "um novo `import *`", "catraca: import * só diminui",
           "automationstudio/vision.py", acrescentar="from .core import *"))
    add(_m("EST08", "estatico", "um método novo que ninguém referencia", "catraca: código sem referência só diminui",
           CORE, acrescentar=L("class _ClasseDeTeste:", "    def metodo_novo_que_ninguem_usa(self):", "        return 1")))
    add(_m("EST09", "estatico", "import de um módulo removido do Python 3.13 (telnetlib)", "o pacote roda no Python 3.14",
           "automationstudio/vision.py", acrescentar=L("def _nunca_chamada():", "    import telnetlib", "    return telnetlib")))
    add(_m("EST10", "estatico", "escape inválido numa string (aviso de sintaxe no Python 3.14)", "o pacote compila sem avisos",
           "automationstudio/vision.py", acrescentar="_PADRAO_COM_ESCAPE_INVALIDO = '\\d+'"))
    add(_m("EST11", "estatico", "caminho de usuário escrito no código", "nenhum caminho de usuário no código",
           "automationstudio/vision.py", acrescentar="_CAMINHO = 'C:\\\\Users\\\\Yuri\\\\x'"))
    add(_m("EST12", "estatico", "um return dentro de um bloco finally (aviso de sintaxe no Python 3.14, que o ambiente de desenvolvimento não tem)",
           "o pacote não sai de um bloco finally",
           "automationstudio/vision.py", acrescentar=L("def _finally_com_retorno():", "    try:", "        return 1", "    finally:", "        return 2")))
    add(_m("EST13", "estatico", "a parada de emergência perde o ramo em `_on_hotkey_triggered` (a tecla chega e some)",
           "o verificador de ligação (static/test_ligacao_controle.py) enxerga os ramos que existem (senão os testes dele falhariam, ou passariam, por qualquer motivo)",
           JAN, '        elif action_id == "control:emergency":\n', '        elif action_id == "control:emergencia":\n'))
    return c


# ------------------------------------------------------------------------------------------------ linha de comando
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raiz", default=str(RAIZ_PADRAO), help="raiz do projeto (padrão: a deste arquivo)")
    ap.add_argument("--listar", action="store_true", help="lista os defeitos e sai")
    ap.add_argument("--tabela", action="store_true", help="imprime a tabela dos defeitos em Markdown e sai")
    ap.add_argument("--validar", action="store_true", help="só confere que cada defeito se aplica ao código, sem rodar testes")
    ap.add_argument("--so", default="", help="ids separados por vírgula")
    ap.add_argument("--area", default="", help="só uma área (motor, win32, pynput, atalhos, botoes, gravador, modelo, persistencia, editor, redes, estatico, ativacao, controle)")
    ap.add_argument("--paralelo", type=int, default=min(2, os.cpu_count() or 1), help="rodadas simultâneas (padrão: 2)")
    ap.add_argument("--relatorio", default="", help="arquivo do relatório (padrão: logs/mutacoes_last_run.txt)")
    ap.add_argument("--manter", action="store_true", help="não apaga as cópias (para investigar um defeito)")
    ap.add_argument("--retomar", action="store_true", help="continua de onde uma rodada interrompida parou (só se o projeto não mudou)")
    ap.add_argument("--progresso", default="", help="arquivo do progresso (padrão: logs/mutacoes_progresso.jsonl)")
    args = ap.parse_args(argv)

    raiz = pathlib.Path(args.raiz).resolve()
    todos = catalogo()
    escolhidos = [m for m in todos if (not args.so or m.id in {s.strip() for s in args.so.split(",")}) and (not args.area or m.area == args.area)]
    if args.tabela:
        print(tabela_markdown(escolhidos))
        return 0
    if args.listar:
        for m in escolhidos:
            print(f"{m.id:<8} {m.area:<13} {m.descricao}")
        print(f"\n{len(escolhidos)} defeitos")
        return 0
    problemas = validar(raiz, escolhidos)
    if problemas:
        print("O catálogo de defeitos não se aplica ao código atual:")
        for p in problemas:
            print("  -", p)
        return 2
    if args.validar:
        print(f"OK: os {len(escolhidos)} defeitos se aplicam ao código em {raiz}")
        return 0
    if not escolhidos:
        print("nenhum defeito selecionado")
        return 2

    versao = re.search(r'__version__ = "([^"]+)"', (raiz / "automationstudio" / "__init__.py").read_text(encoding="utf-8"))
    versao = versao.group(1) if versao else "?"
    inicio = time.monotonic()
    impressao = impressao_digital(raiz)
    progresso = pathlib.Path(args.progresso) if args.progresso else raiz / "logs" / "mutacoes_progresso.jsonl"
    resultados: list[Resultado] = []
    referencias: dict = {}
    if args.retomar and progresso.exists():
        try:
            guardados, referencias = ler_progresso(progresso, impressao, {m.id: m for m in todos})
        except ProgressoDeOutroEstado as exc:
            print(f"Não dá para retomar: {exc}.\nApague {progresso} (ou rode sem --retomar) para começar de novo.")
            return 2
        pedidos = {m.id for m in escolhidos}
        resultados = [r for r in guardados if r.mutante.id in pedidos]
        print(f"Retomando: {len(resultados)} defeitos já tinham resultado gravado ({progresso}).", flush=True)
    else:
        if args.retomar:
            print("Nada a retomar: não há progresso gravado. Começando do zero.", flush=True)
        iniciar_progresso(progresso, impressao, versao)
    retomados = len(resultados)
    feitos = {r.mutante.id for r in resultados}
    pendentes = [m for m in escolhidos if m.id not in feitos]

    faltam = {m.modo for m in pendentes} - set(referencias)
    if faltam:
        print("Rodada de referência (sem defeito)...", flush=True)
        for modo, dados in rodada_de_referencia(raiz, faltam).items():
            referencias[modo] = dados
            gravar_no_progresso(progresso, dados_da_referencia(modo, dados))
    if pendentes:
        print(f"Rodando {len(pendentes)} defeitos, {args.paralelo} por vez...", flush=True)
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.paralelo))
        try:
            futuros = {pool.submit(executar_um, raiz, m, referencias, args.manter): m for m in pendentes}
            for futuro in concurrent.futures.as_completed(futuros):
                r = futuro.result()
                resultados.append(r)
                gravar_no_progresso(progresso, dados_do_resultado(r))
                print(f"  [{len(resultados):>3}/{len(escolhidos)}] {r.status.upper():<10} {r.mutante.id}  {r.mutante.descricao[:70]}", flush=True)
        except KeyboardInterrupt:
            pool.shutdown(wait=False, cancel_futures=True)
            print(f"\nInterrompido. {len(resultados)} de {len(escolhidos)} resultados ficaram gravados em {progresso}.\n"
                  f"Para continuar de onde parou: py tests/testsupport/mutacoes.py --retomar")
            return 130
        finally:
            pool.shutdown(wait=True)
    texto = relatorio(resultados, referencias, time.monotonic() - inicio, versao, retomados)
    destino = pathlib.Path(args.relatorio) if args.relatorio else raiz / "logs" / "mutacoes_last_run.txt"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(texto, encoding="utf-8")
    print("\n" + texto)
    print(f"Relatório gravado em {destino}")
    return 0 if all(r.status == "morto" for r in resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
