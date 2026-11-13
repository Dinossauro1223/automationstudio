"""Gravar no mapa o que a edição pelo teclado decidiu (25.9, T3a). Lógica pura, sem Qt.

Ficha: md/FICHA_TECLADO_T3_25_9.md (T3-6 e T3-13). Testes: tests/unit/test_teclado_aplicar.py e, contra a barra lateral de verdade,
tests/gui/test_teclado_aplicar_simetria.py.

O controlador (`teclado_edicao.py`) decide *o que* mudar e devolve um efeito (`AplicarAlvo`, `AplicarTexto`, `AplicarTempo`,
`AplicarEspera`); a janela marca a linha com `marcar` quando a edição começa e chama `aplicar_alvo`, `aplicar_texto`, `aplicar_tempo` ou
`aplicar_espera` quando ela termina. Estas quatro são as únicas que mexem no mapa. Regras:

- **as da barra lateral** (`CommandDialog.result_command`): a tecla em maiúsculas, o botão em minúsculas (como o motor o compara), o texto
  com a duração recalculada por `calculate_text_duration`. A barra reescreve o comando inteiro; aqui só muda o campo editado;
- **tudo ou nada**: o que é recusado devolve `Resultado(ok=False, mensagem=...)` e deixa o mapa exatamente como estava; nada é gravado pela
  metade (cada gravação é uma só atribuição de campos já validados);
- **antes de gravar, conferir** que o comando da linha é o que foi marcado (índice, id e tipo): se a lista mudou por outro caminho no meio da
  edição (apagar, mover, desfazer), não se grava no comando errado;
- **o processo esperado de um programa** (`wait_process`) acompanha o programa só quando era o dele: ver `aplicar_alvo`.

`Resultado.mensagem` é a frase de uma recusa (vai para a barra de status); `Resultado.aviso` é um complemento de uma gravação que deu certo.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import PureWindowsPath

from .core import MOUSE_BUTTON_NAMES, AutomationMap, InputType, calculate_text_duration, normalized_app_target
from .teclado_edicao import TETO, formatar_segundos, linha_info_de

MENSAGEM_MUDOU = "O comando mudou enquanto você editava: nada foi gravado."
_SEM_ALVO = "Este comando não tem tecla, botão nem programa para trocar aqui. Nada foi gravado."
_TECLA_VAZIA = "Escolha uma tecla. Nada foi gravado."
_BOTAO_DESCONHECIDO = "Esse botão do mouse não existe. Nada foi gravado."
_PROGRAMA_VAZIO = "Escolha um programa. Nada foi gravado."
_PROGRAMA_SEM_NOME = "Esse programa não tem nome de arquivo: escolha o executável. Nada foi gravado."
_NAO_E_TEXTO = "Este comando não é de texto. Nada foi gravado."
_TEXTO_VAZIO = "O texto não pode ficar vazio. Nada foi gravado."
_TEMPO_INVALIDO = f"O tempo apertado vai de 0,001 s a {TETO:g} s. Nada foi gravado."
_ESPERA_INVALIDA = "A espera precisa ser um número. Nada foi gravado."
_CASAS = 3  # o tempo apertado é sempre em milissegundos (teclado_edicao.RESOLUCAO)


@dataclass(frozen=True)
class Marca:
    """A linha que está sendo editada, como era quando foi marcada: índice, id do comando e tipo."""
    indice: int
    id: str
    tipo: InputType


@dataclass(frozen=True)
class Resultado:
    """O desfecho de uma gravação. `ok` falso: `mensagem` diz por quê e o mapa não mudou. `ok` verdadeiro: `aviso` (se houver) é um
    complemento para a barra de status, por exemplo que o processo esperado de um programa continua o antigo."""
    ok: bool
    mensagem: str = ""
    aviso: str = ""


_OK = Resultado(True)


def _recusar(mensagem: str) -> Resultado:
    return Resultado(False, mensagem)


def marcar(mapa: AutomationMap, indice: int) -> Marca:
    """Guarda quem é o comando da linha `indice` agora. Índice fora do mapa (inclusive o negativo do Python) é erro (IndexError)."""
    if not 0 <= indice < len(mapa.commands):
        raise IndexError(f"comando {indice} fora do mapa (ele tem {len(mapa.commands)})")
    comando = mapa.commands[indice]
    return Marca(indice=indice, id=comando.id, tipo=comando.type)


def _conferir(mapa: AutomationMap, marca: Marca) -> Resultado | None:
    """None se a marca ainda confere com o mapa; senão a recusa. O índice negativo nunca confere: `commands[-1]` existiria."""
    if not 0 <= marca.indice < len(mapa.commands):
        return _recusar(MENSAGEM_MUDOU)
    comando = mapa.commands[marca.indice]
    if comando.id != marca.id or comando.type != marca.tipo:
        return _recusar(MENSAGEM_MUDOU)
    return None


def _numero(valor) -> float | None:
    """O valor como número finito, ou None (texto que não é número, None, NaN e infinitos)."""
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return numero if math.isfinite(numero) else None


def nome_do_processo(alvo) -> str:
    """O nome do arquivo do programa que um comando de abrir aplicativo abre, que é como o "processo esperado" se escreve ("notepad.exe").
    Vem do alvo já normalizado (sem aspas e sem espaços nas pontas); caminho com `\\` ou `/` fica só com o último pedaço. Vazio se não há."""
    return PureWindowsPath(normalized_app_target(alvo).strip()).name


def aplicar_alvo(mapa: AutomationMap, marca: Marca, valor) -> Resultado:
    """Troca a tecla, o botão do mouse ou o programa do comando marcado.

    Tecla: em maiúsculas. Botão: em minúsculas e um dos que o modelo conhece (`MOUSE_BUTTON_NAMES`). Programa: normalizado (sem aspas nem
    espaços nas pontas) e com nome de arquivo. O processo que a automação espera depois de abrir o programa (`wait_process`) é tratado
    assim, para o comando não ficar esperando o programa antigo até o tempo limite:

    - estava vazio: continua vazio (nunca se cria uma espera que o dono não tinha);
    - era o nome do arquivo do programa antigo (sem diferenciar maiúsculas): passa a ser o do novo;
    - era outro: continua, e `aviso` diz qual é (a decisão de trocá-lo é do dono, na barra lateral).
    """
    recusa = _conferir(mapa, marca)
    if recusa is not None:
        return recusa
    comando = mapa.commands[marca.indice]
    texto = "" if valor is None else str(valor)
    if comando.type == InputType.KEY:
        tecla = texto.strip().upper()
        if not tecla:
            return _recusar(_TECLA_VAZIA)
        comando.target = tecla
        return _OK
    if comando.type == InputType.MOUSE_BUTTON:
        botao = texto.strip().lower()
        if botao not in MOUSE_BUTTON_NAMES:
            return _recusar(_BOTAO_DESCONHECIDO)
        comando.target = botao
        return _OK
    if comando.type == InputType.APP_OPEN:
        return _aplicar_programa(comando, texto)
    return _recusar(_SEM_ALVO)


def _aplicar_programa(comando, texto: str) -> Resultado:
    programa = normalized_app_target(texto).strip()
    if not programa:
        return _recusar(_PROGRAMA_VAZIO)
    nome_novo = nome_do_processo(programa)
    if not nome_novo:
        return _recusar(_PROGRAMA_SEM_NOME)
    esperado = str(comando.wait_process or "").strip()
    nome_antigo = nome_do_processo(comando.target)
    acompanha = bool(esperado) and esperado.casefold() == nome_antigo.casefold()
    aviso = ""
    if esperado and not acompanha:
        aviso = f"A automação continua esperando o processo «{esperado}»: se ele mudou com o programa, troque na barra lateral (Shift+Enter)."
    comando.target = programa
    if acompanha:
        comando.wait_process = nome_novo
    return Resultado(True, aviso=aviso)


def aplicar_texto(mapa: AutomationMap, marca: Marca, texto) -> Resultado:
    """Troca o texto do comando marcado e recalcula a duração (`calculate_text_duration`), como a barra lateral. O texto vai como veio, sem aparar."""
    recusa = _conferir(mapa, marca)
    if recusa is not None:
        return recusa
    comando = mapa.commands[marca.indice]
    if comando.type != InputType.TEXT:
        return _recusar(_NAO_E_TEXTO)
    novo = "" if texto is None else str(texto)
    if not novo:
        return _recusar(_TEXTO_VAZIO)
    comando.text = novo
    comando.duration = calculate_text_duration(novo)
    return _OK


def aplicar_tempo(mapa: AutomationMap, marca: Marca, valor) -> Resultado:
    """Grava o tempo apertado (a duração) de uma tecla ou botão de "apertar e soltar", arredondado ao milissegundo, de 0,001 s até `TETO`.

    Não empurra os seguintes (D4), como a célula "Duração" da tabela. Nos comandos sem tempo apertado a recusa traz o mesmo motivo que
    o controlador mostra (`linha_info_de`)."""
    recusa = _conferir(mapa, marca)
    if recusa is not None:
        return recusa
    info = linha_info_de(mapa, marca.indice)
    if not info.tempo_editavel:
        return _recusar(info.tempo_motivo)
    numero = _numero(valor)
    if numero is None:
        return _recusar(_TEMPO_INVALIDO)
    tempo = round(numero, _CASAS)
    if not 0.0 < tempo <= TETO:
        return _recusar(_TEMPO_INVALIDO)
    mapa.commands[marca.indice].duration = tempo
    return _OK


def aplicar_espera(mapa: AutomationMap, marca: Marca, valor) -> Resultado:
    """Grava a espera antes do comando marcado: `AutomationMap.set_gap_before` (o comando e os seguintes andam juntos). O valor NÃO é
    arredondado: o controlador pode entregar exatamente o mínimo, e arredondá-lo o deixaria abaixo dele."""
    recusa = _conferir(mapa, marca)
    if recusa is not None:
        return recusa
    numero = _numero(valor)
    if numero is None:
        return _recusar(_ESPERA_INVALIDA)
    minimo = mapa.min_gap_before(marca.indice)
    try:
        mapa.set_gap_before(marca.indice, numero)
    except ValueError:  # o modelo recusa antes de mudar qualquer coisa
        return _recusar(f"A espera mínima aqui é {formatar_segundos(minimo)}: abaixo disso um comando começaria antes do instante 0. Nada foi gravado.")
    return _OK
