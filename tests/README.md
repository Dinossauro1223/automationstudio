# Testes do Automation Studio

Infraestrutura permanente de testes (Ponto 2 da auditoria, versão 25.5; revisada na 25.6 depois da primeira rodada no Windows). Este guia diz **como rodar**, **o que cada pasta protege**, **como escrever um teste novo** e **o que a suíte não prova**.

## Em um minuto

| Quero… | Faço… | Leva |
|---|---|---|
| Saber se algo quebrou | duplo clique em `Rodar_Testes.bat` (ou `Rodar_Testes.bat completo`) | cerca de 25 s sem o PySide6; com ele, alguns minutos (a janela principal roda um processo por teste) |
| Só a lógica, sem janelas | `Rodar_Testes.bat rapido` | cerca de 20 s |
| Instalar o que falta para testar | `Rodar_Testes.bat instalar` (precisa de internet) | cerca de 1 min |
| Achar teste instável | `Rodar_Testes.bat repetir 20` | cerca de 10 min |
| Testar o Windows de verdade | `Rodar_Testes.bat windows` (digite `SIM`; **não toque no teclado nem no mouse**) | cerca de 15 s |
| Ver a cobertura | `Rodar_Testes.bat cobertura` | 1 a 3 min |
| Provar que os testes pegam defeitos | `Rodar_Testes.bat mutacoes` | cerca de 55 min |

(Os tempos foram medidos no ambiente de desenvolvimento, que não tem o PySide6 de verdade: o passo de um processo por teste, abaixo, não pôde ser medido. Na sua máquina variam.)

O resultado fica em `logs\`. **Se algo falhar, me envie `logs\tests_last_run.txt`** (no modo `windows`, `logs\tests_windows_last_run.txt`). Ele tem o nome do teste, a diferença esperada × obtida e a linha do código; cada falha é impressa **na hora**, não só no fim. **Se algum teste travar, envie também `logs\travamento_qt.txt`** (o RESUMO do fim da rodada avisa; veja "Se um teste travar").

Código de saída: `0` é tudo certo; qualquer outro valor é falha (o `.bat` mostra o número). O número é o do **primeiro passo** que não terminou limpo: `1` se algum teste falhou nele, **`86` se algum teste travou e nenhum falhou** nele, e `5` se nenhum teste rodou em lugar nenhum. O atalho devolve `2` quando o modo nem chega a rodar (modo desconhecido, falta o `coverage`, confirmação do modo `windows` recusada). A rodada nunca conta como limpa se houve travamento; o RESUMO lista tudo o que aconteceu, qualquer que seja o número.

## Os modos do `Rodar_Testes.bat`

O `.bat` só escolhe o Python (o de `python_version.txt`) e chama `tests\testsupport\rodar_testes.py`; o mesmo script roda em qualquer sistema: `py tests/testsupport/rodar_testes.py <modo>`.

| Modo | O que faz |
|---|---|
| `completo` (padrão) | A suíte inteira. Com o PySide6 de verdade instalado, os testes de interface rodam de verdade (sem janela visível: `QT_QPA_PLATFORM=offscreen`) e a rodada tem **dois passos**: os testes comuns (`-m "not isolado"`) e os da janela principal, **um por processo, com tempo limite** (`isolado`, abaixo). Sem o PySide6, usa o dublê de widgets e avisa. |
| `rapido` | Só a lógica (modelo, motor, gravador, atalhos, persistência, contratos dos backends, cenários, checagens estáticas). Os testes de interface são pulados. Não precisa do PySide6. |
| `windows` | Os testes de `tests/e2e_windows` **com entrada de verdade** (SendInput). É o único modo que liga `AS_ALLOW_REAL_INPUT`. Só no Windows e só depois de você digitar `SIM`. |
| `repetir [N]` | Roda o `completo` (com os dois passos) N vezes seguidas (padrão 10) e para na primeira falha. Serve para achar teste que passa e falha sem motivo. |
| `cobertura` | `coverage run -p` com ramos (os dois passos, inclusive cada processo isolado, gravam os seus dados), `coverage combine`, relatório por arquivo e a **catraca de cobertura** (abaixo). Precisa do `coverage`. Com argumentos extras a medição é parcial e a catraca não roda. |
| `mutacoes` | O verificador de defeitos plantados (abaixo). Usa o dublê de widgets, mesmo com o PySide6 instalado (o Qt de verdade só com `AS_MUTACOES_QT_REAL=1`). |
| `instalar` | `pip install -r requirements-dev.txt` (pytest, pytest-timeout e coverage). |
| `ajuda` | Mostra a ajuda. |

Tudo o que vem depois do modo vai para o executor de testes: `Rodar_Testes.bat completo -k atalho -x` roda só os testes com "atalho" no nome e para na primeira falha.

**Executor.** Com o pytest instalado o atalho usa `pytest` (com `--timeout=180` se o `pytest-timeout` estiver instalado, `--tb=line` e grava também `logs\tests_last_run.xml`, em formato JUnit; o detalhe de cada falha já foi impresso na hora pelo `conftest.py`). Sem o pytest ele usa o executor mínimo do projeto (`tests/testsupport/run_minimal.py`), que entende só o subconjunto portátil descrito abaixo; ele **não** isola testes um por processo (o passo isolado só roda com o pytest e o PySide6). Os dois dão o mesmo resultado, teste a teste.

**Resumo.** A rodada termina com um quadro `RESUMO DA RODADA`: uma linha por passo (OK, FALHOU, TRAVOU ou VAZIO), os testes que falharam ou travaram, o código de saída e quais arquivos enviar. O passo isolado mostra `[n/total]` e o resultado de cada teste (`OK`, `PULADO`, `FALHOU`, `TRAVOU` ou `QUEDA`) assim que ele termina; os testes que ele nem chegou a rodar aparecem como `NÃO RODOU` (próxima seção).

## Se um teste travar (o marcador `isolado`)

Na primeira rodada no Windows (18/10/2026), o 22º teste da janela principal ficou 180 s parado dentro do Qt (`QApplication.processEvents()`), o pytest-timeout encerrou o processo e a rodada acabou sem resumo. A causa **ainda não é conhecida** (`md/PONTO2_REVISAO_25_6.md`, R3). Por isso:

- **Marcador `isolado`.** Todo teste que abre a janela principal (`abrir_janela`) leva o marcador; uma verificação estática reprova a ausência. Com o PySide6 e o pytest, o `Rodar_Testes.bat` roda esses testes **um por processo**, cada um com tempo limite: um travamento ou uma queda do Qt reprova só aquele teste. Os demais rodam juntos (`-m "not isolado"`). Um `-m` que você passar é combinado com o do lançador (`(o seu) and (o do lançador)`), não substituído.
- **Três tempos**, cada um a reserva do anterior: o **vigia** do teste (60 s; mude com `AS_LIMITE_TESTE_JANELA`), o pytest-timeout do processo isolado (90 s) e o lançador, que mata o processo aos 120 s. No passo comum o limite é o do pytest-timeout (180 s).
- **O vigia** grava `logs\travamento_qt.txt` e encerra o processo com o código 86. O relatório tem: o teste e a fase; o **DIAGNÓSTICO** (`BLOQUEIO`: o Qt não entrega nenhum evento há mais de 3 s, parado numa chamada nativa; ou `LAÇO DE EVENTOS`: o Qt continua entregando eventos e algo se reativa); os 60 últimos eventos do Qt (receptor, tipo, nome) e os mais frequentes; as mensagens que o próprio Qt imprimiu; a pilha do Python de todas as threads; e o ambiente (versões e plataforma). A thread do vigia **nunca chama o Qt**. Se ela não conseguir rodar (GIL preso numa chamada nativa), um alarme **nativo** (`faulthandler`) dispara 15 s depois e grava `logs\travamento_qt_nativo.txt`; o lançador o anexa ao relatório.
- **Quando um teste trava no passo comum**, o lançador roda o passo de novo **sem ele** (até 3 vezes), para que um travamento não esconda os testes seguintes, e sai com **86** (se o que sobrou também falhar, o código é o da falha).
- **Quando 3 testes isolados travam em sequência**, o passo isolado **para**: três travamentos seguidos indicam um problema do ambiente, e esperar o tempo limite de cada um dos que faltam (cerca de 1 minuto por teste) só repetiria o mesmo relatório. O RESUMO diz quantos testes `NÃO RODOU`, e a rodada não conta como limpa (código 86, ou 1 se algum teste também falhou). Um teste que passa zera a contagem. Para rodar um dos que faltam: `Rodar_Testes.bat completo -k <parte do nome>`.
- **Estados do RESUMO**: `OK`; `PULADO`; `FALHOU` (o teste falhou: código 1); `TRAVOU` (passou do tempo, saiu com 86 ou deixou relatório); `QUEDA` (o processo morreu sem falha de teste: o Qt derrubou o Python); `NÃO RODOU` (o passo isolado parou depois de 3 travamentos seguidos).
- **Higiene.** No fim de cada teste de janela, a janela é fechada e destruída e a fila de eventos é esvaziada (`descartar_janelas`, em `testsupport/gui_helpers.py`). Nos testes, `processar_eventos(ms)` (do mesmo arquivo) substitui o `QApplication.processEvents()` solto: termina por tempo (e por um mínimo de passadas) e anota cada passada no diagnóstico. Limite conhecido: se algo se reagendar sem parar, o teste termina por tempo em vez de travar.

Para olhar um teste só: `Rodar_Testes.bat completo -k timeline_abre` (ele roda isolado). Para tirar da conta o filtro de eventos e o tratador de mensagens do Qt (o vigia continua): `set AS_DIAGNOSTICO_QT=0`. Para outra plataforma do Qt: `set QT_QPA_PLATFORM=minimal` (o padrão dos testes é `offscreen`; um valor que você definir tem prioridade).

## O que há em `tests/`

| Pasta | O que protege |
|---|---|
| `unit/` | Modelo (`core`, `conditions`, `vision`): validação, linha do tempo, operações de edição (mover, reordenar, copiar, colar, excluir, exportar, importar), máquina de estados, relógio virtual, leitor de mapas antigos, a ativação por mapa (25.8: a lógica de `ativacao.py` e o controlador de `ativacao_ui.py`, com uma janela de mentira em `testsupport/janela_falsa.py`), o controlador de pausar e continuar pelas teclas F9 e F10 (`controle_ui.py`, com o motor de verdade e a mesma janela de mentira), e as próprias ferramentas de teste (atalho, verificador de mutações, catraca de cobertura). |
| `engine/` | Motor de execução (comandos, tempo, pausa, parada, barreiras de espera), gravador, atalhos globais, monitor de entrada, botões laterais do mouse. Tudo com relógio virtual: um mapa de 1 min roda em milissegundos. |
| `contract/` | O mesmo contrato rodado em cada backend de entrada (Mock, pynput falso, Win32 com `user32` falso): nomes de teclas e botões, soltar tudo, rolagem, texto com acento. |
| `persistence/` | Banco SQLite de mapas e configurações, histórico de desfazer, leitor tolerante do formato v1, importação de JSON antigo, vários acessos ao mesmo banco. |
| `regression/` | **Um teste por defeito já corrigido.** `test_ponto1_reproducao.py` (itens 1.01 a 1.17 da 25.3) e `test_ponto2_achados.py` (2.09 e 2.10). |
| `scenarios/` | Fluxos inteiros (mapa → linha do tempo → motor → backend) comparados com arquivos de referência em `data/golden/`. Inclui os 3 mapas reais que você enviou. |
| `gui/` | Editor de comandos, janela principal, a faixa de ativação por mapa e as teclas de pausar e continuar na janela. Roda com o PySide6 de verdade; sem ele, o editor e a faixa rodam no dublê de widgets e a janela principal é pulada. Os testes da janela principal são `isolado` (acima). |
| `static/` | Invariantes do código-fonte (nome inexistente, método duplicado, sinal sem `connect`, `\n` literal, módulo removido do Python, saída de `finally`, versão única, `.bat` com CRLF, instalador × `requirements.txt`, a ligação da ativação por mapa e a das teclas de controle (F9, F10...) com a janela principal...) e as **catracas** (abaixo). Cada invariante tem um controle negativo (um defeito plantado que ela TEM de acusar). |
| `e2e_windows/` | O que só o Windows de verdade responde. Rodam sempre em modo **simulado**; em modo **real** só com `Rodar_Testes.bat windows`. |
| `data/` | `legacy_maps.json.gz` (os 3 mapas reais) e `golden/` (8 resultados de referência). |
| `testsupport/` | Ferramentas: relógio virtual, fakes, helpers, dublês do Qt, diagnóstico de travamento (`diagnostico_qt.py`), verificador de mutações, atalho de execução, catraca de cobertura. Não são testes. |

## Os dois "Qt de mentira"

O ambiente onde esta infraestrutura foi construída não tem PySide6. Para validar a lógica mesmo assim existem dois dublês, ligados por `AS_TEST_QT_STUB` (nunca por padrão: uma checagem garante que o dublê só existe quando foi pedido).

| `AS_TEST_QT_STUB` | O que é | Os testes de interface |
|---|---|---|
| (vazio) | PySide6 de verdade | rodam |
| `widgets` | `testsupport/qt_double`: executa a lógica Python do **editor de comandos** sem o Qt | o editor roda; a janela principal é pulada |
| `1` | `testsupport/qt_stub`: só deixa os módulos importarem | todos pulados |

O dublê não prova nada sobre o Qt. O que só o Qt de verdade confirma está em `gui/test_qt_semantics.py` (por exemplo, que `QPoint` não é indexável e que o índice de um combo editável não acompanha o texto digitado).

## Variáveis de ambiente

| Variável | Efeito |
|---|---|
| `AS_TEST_QT_STUB` | `1` ou `widgets`: ver acima. |
| `AS_ALLOW_REAL_INPUT=1` | Libera os testes que enviam teclado e mouse de verdade. **Só o modo `windows` a define**; os demais modos a removem do ambiente. |
| `AS_ATUALIZAR_GOLDEN=1` | Regrava os arquivos de referência dos cenários (ver "Golden"). |
| `AS_ROOT=<pasta>` | Roda os testes contra OUTRA cópia do pacote (por exemplo, a versão anterior, para provar que um teste de regressão falha nela). Defina e chame `py -3.14 -m pytest` direto: o atalho a remove do ambiente. |
| `AS_FORCE_MINIMAL_RUNNER=1` | Faz o `run_minimal.py` usar o próprio executor mesmo com o pytest instalado (o verificador de mutações depende disso). |
| `AS_MUTACAO_EM_CURSO` | Definida pelo verificador de mutações nas cópias que ele testa. Não defina. |
| `AS_LIMITE_TESTE_JANELA` | Segundos que o vigia espera num teste de janela antes de gravar `logs\travamento_qt.txt` e encerrar o processo (padrão 60; valor menor ou igual a zero é ignorado). |
| `AS_DIAGNOSTICO_QT=0` | Não instala o filtro de eventos nem o tratador de mensagens do Qt nos testes da janela principal (o vigia e as pilhas continuam). |
| `AS_MUTACOES_QT_REAL=1` | O verificador de defeitos usa o PySide6 de verdade (se instalado) em vez do dublê de widgets. Ele não isola testes um por processo: um teste de janela que travar segura o defeito até o tempo limite. |
| `PYTHONUTF8`, `PYTHONIOENCODING` | O atalho os define (`1` e `utf-8`) para os testes e os arquivos de log, independentemente da página de código do Windows. |
| `QT_QPA_PLATFORM` | O `conftest.py` define `offscreen` se você não tiver definido outra. |

## Como escrever um teste novo

**O ciclo (regra do projeto):** reproduzir → o teste falha → corrigir → o teste passa → ele fica para sempre na regressão. Para provar a primeira parte, rode o teste contra a versão antiga:

```
set AS_ROOT=C:\caminho\da\versao_antiga
py -3.14 -m pytest tests\regression\test_meu_achado.py
```

Em `tests/regression/` cada teste leva um rótulo no comentário da linha `def`: `[VERMELHO]` falha na versão anterior e passa na atual; `[VERDE]` já passava e protege o comportamento que a correção não pode quebrar.

**Onde fica:** na pasta do assunto, em `test_*.py`. O nome do arquivo e o nome de cada função de teste são únicos no projeto (uma checagem estática reclama de repetição).

**Ferramentas prontas** (`tests/conftest.py`):

| Fixture | Para quê |
|---|---|
| `fake_clock` | Relógio virtual. `sleep()` só avança o tempo. Nunca use `time.sleep` real acima de 0,5 s (uma checagem estática reprova). |
| `mock_backend`, `hook_backend` | Backend que só registra os eventos; o `hook_backend` chama um gancho depois do N-ésimo evento (para parar ou pausar o motor num ponto exato). |
| `make_engine` | `make_engine(backend=None, state=None)` devolve `(motor, backend)` já com o relógio virtual. |
| `gravar` | `gravar(filtros=None)` devolve `(gravador, monitor_falso, estado)`. |
| `legacy_maps` | Os 3 mapas reais, em texto. |
| `gui`, `gui_real`, `abrir_janela` | Isolamento da interface: registro do Windows, hooks globais, input real e diálogos bloqueados. Um diálogo inesperado reprova o teste em vez de travá-lo. `gui` liga o vigia de travamento; `abrir_janela` liga o diagnóstico de eventos do Qt e, **ao fim do teste, fecha e destrói as janelas e esvazia a fila de eventos**. |
| `ambiente_simulado`, `ambiente_real` | Ambiente dos testes e2e do Windows. |
| `tmp_path`, `monkeypatch` | Os do pytest. |

Já são automáticos em todo teste: o log de execução não escreve em disco, as constantes de execução voltam ao valor original, nenhum aplicativo de verdade é aberto, e uma exceção dentro de um slot do Qt reprova o teste.

Funções úteis em `testsupport/helpers.py`: `key`, `make_map`, `run_to_end`, `events_of`, `pressed_balance`. Em `testsupport/gui_helpers.py`: `processar_eventos(ms)` (use no lugar de `QApplication.processEvents()`), `esvaziar_fila`, `descartar_janelas`, `differences`, `write_png`.

**Subconjunto portátil do pytest.** Os testes do projeto só usam o que o pytest e o executor mínimo entendem igual: fixtures **somente** em `conftest.py` (escopo de função ou de sessão, sem `request`), `tmp_path`, `monkeypatch`, `pytest.raises`, `pytest.approx`, `pytest.skip`, `pytest.importorskip`, os marcadores `skip`, `skipif`, `xfail`, `parametrize` e os declarados no `pytest.ini` (`slow`, `gui`, `windows_only`, `hardware`, `isolado`). Em `parametrize`, **sempre `ids=`**. Não use `capsys`, `pytest.param` nem fixtures dentro do arquivo de teste. Uma checagem estática reprova o que fugir disso, e o `--strict-markers` do `pytest.ini` reprova marcador não declarado.

## Golden (resultados de referência)

Os cenários em `scenarios/` congelam o que o programa produz (cada evento, tempo e alvo) em `data/golden/<nome>.json`. Se qualquer coisa mudar, o teste falha e mostra a **primeira diferença**.

Atualizar um golden é uma decisão, não um conserto: só quando a mudança de comportamento é intencional. Rode `set AS_ATUALIZAR_GOLDEN=1` e `py -3.14 tests\testsupport\run_minimal.py tests\scenarios`, **leia o diff** dos `.json` e rode de novo sem a variável. A rodada de atualização grava os arquivos mas reprova cada cenário de propósito, para que ela nunca conte como verificação.

## Testes no Windows de verdade (`Rodar_Testes.bat windows`)

Respondem à pergunta que nenhum teste sem o Windows consegue responder: o Windows aceita o que o programa envia? Cada verificação declara a premissa que confirma:

| | Premissa |
|---|---|
| P1 | `GetAsyncKeyState` enxerga o que o `SendInput` injeta (teclado e botões do mouse, inclusive os laterais). |
| P2 | `SetCursorPos` é exato; um movimento relativo vai para o lado certo (a aceleração do ponteiro pode ampliá-lo). |
| P3 | O texto digitado pelo backend chega inteiro à janela em primeiro plano (teclas reais, teclas mortas do layout e, para o que o layout não tem, o caminho Unicode). |
| P4 | Clique esquerdo, do meio e direito e a roda chegam à janela sob o cursor, com o sinal e o tamanho certos. |
| P5 | O motor inteiro (mapa → linha do tempo → backend → Windows) produz o efeito esperado na janela. |
| P6 | O monitor global do pynput enxerga a entrada enviada pelo próprio programa e o atalho global dispara. |
| P7 | A leitura da lista de processos (Toolhelp32 + psapi, via ctypes) funciona neste Python de 64 bits. |

Regras de segurança (valem para qualquer teste novo desse tipo): nada é enviado ao mouse sem confirmar que a janela de teste está em primeiro plano **e** sob o cursor; nada é enviado ao teclado sem a janela de teste em primeiro plano (exceto SHIFT e CTRL sozinhos); se o ambiente não permite (sem Tk, foco roubado), o teste é **pulado** e nada é enviado; tudo o que o teste pressiona é solto no `finally` e no encerramento do ambiente.

**Uma falha aqui é informação, não defeito do teste.** Me envie `logs\tests_windows_last_run.txt`: a premissa que falhou diz o que o programa assumia errado. As mesmas verificações rodam sempre em modo simulado (`e2e_windows/test_e2e_simulado.py`), o que impede que o código do e2e apodreça entre uma rodada real e outra.

## Defeitos plantados (verificador de mutações)

Uma suíte verde só diz que o código atual passa; não diz que os testes enxergariam um defeito. O verificador planta, **um de cada vez e numa cópia descartável do projeto**, defeitos parecidos com os que já apareceram (ou que poderiam aparecer) e roda a suíte inteira contra cada cópia.

- **morto**: algum teste que passava na cópia sem defeito passou a falhar. É o resultado esperado.
- **sobreviveu**: nenhum teste notou. O buraco está nos testes: escreva o teste que o mataria ou documente por que o defeito é inofensivo (é o caso da guarda de parada dentro de `_apply_wait_conditions`: ela repete a do laço de execução e tirar só uma das duas não muda nada observável; por isso o defeito plantado `MOT22` mira a que protege de verdade).
- **inválido**: o defeito não compila, o pacote não importa ou o trecho a trocar sumiu do código (o código mudou: atualize o defeito).

```
py tests\testsupport\mutacoes.py --validar        só confere que cada defeito ainda se aplica (rápido)
py tests\testsupport\mutacoes.py --listar         lista os defeitos
py tests\testsupport\mutacoes.py --so MOT01,GRV08 só alguns
py tests\testsupport\mutacoes.py --area motor     só uma área
py tests\testsupport\mutacoes.py --tabela         tabela em Markdown
py tests\testsupport\mutacoes.py --retomar        continua uma rodada interrompida
```

A rodada inteira (378 defeitos) leva perto de uma hora (duas cópias testadas ao mesmo tempo). Foi refeita inteira na correção do achado 2.11 (pausar e continuar pelas teclas F9 e F10), com o código e os testes dela: os 378 do catálogo (292 da base, 62 da ativação por mapa, o `EST13` e 23 da pausa) foram todos mortos, sem sobrevivente nem defeito inválido. A rodada foi retomada uma vez depois de o ambiente interrompê-la (`--retomar`). Por padrão usa o dublê de widgets, também onde o PySide6 está instalado (veja `AS_MUTACOES_QT_REAL`). Cada resultado é gravado assim que sai (`logs\mutacoes_progresso.jsonl`); se o computador dormir ou você interromper, `--retomar` continua dali. O progresso só vale para o **mesmo** projeto (guarda uma impressão digital do código e dos testes): se algo mudou desde então, a retomada é recusada em vez de misturar resultados de suítes diferentes.

**Para acrescentar um defeito**, edite `catalogo()` em `tests/testsupport/mutacoes.py`: `add(_m(ID, área, "o defeito", "o que a suíte deveria garantir", "arquivo", "trecho exato", "trecho trocado"))`. O trecho tem de aparecer exatamente o número de vezes esperado (senão o defeito é recusado em vez de plantado no lugar errado). Rode `--validar` e depois `--so ID`. Todo defeito novo que sobrevive vira um teste novo.

## Catracas (o que só pode melhorar)

| Catraca | Onde | Regra |
|---|---|---|
| `import *` | `static/test_static_invariants.py` (`BASE_IMPORT_ESTRELA`) | o número não pode aumentar |
| Métodos sem referência | idem (`BASE_METODOS_SEM_REFERENCIA`) | o número não pode aumentar |
| Cobertura | `testsupport/catraca_cobertura.py` | a cobertura de cada parte do pacote não pode cair mais de 1 ponto em relação a `tests/coverage_baseline.json` |

Ao melhorar um número, baixe a constante na mesma alteração.

**Catraca de cobertura.** `Rodar_Testes.bat cobertura` mede linhas e ramos com o `coverage.py`, agrupa por parte (`core`, `conditions`, `project`, `input_system`, `vision`, `ativacao`, `controle`, `interface`) e compara com `tests/coverage_baseline.json`. **Esse arquivo não vem no pacote:** o baseline precisa ser medido na sua máquina, com o PySide6 de verdade; a primeira rodada o grava e as seguintes comparam. Uma queda reprova (código 1) e **não** regrava o baseline; para subir a catraca depois de uma melhora, ou para aceitar uma queda de propósito, rode `py tests\testsupport\catraca_cobertura.py --gravar`. Um baseline gravado com o dublê de widgets não serve de régua para o Qt de verdade (a interface cobre muito mais com ele): grave de novo se mudar de ambiente.

## Defeitos conhecidos (5 testes `xfail` estritos)

São comportamentos desejados que o código ainda **não** tem. Quando um deles for corrigido o teste passa, o pytest reclama (`strict`) e o marcador sai.

| Teste | O que falta | Quando |
|---|---|---|
| `persistence/test_project_manager.py::test_json_legado_nao_ressuscita_mapa_apagado` | A migração dos JSON antigos roda sempre que o banco está vazio: apagar o último mapa e reabrir traz de volta os arquivos antigos da pasta (achado 2.03). | Ponto 3 |
| `persistence/test_project_manager.py::test_carregar_por_nome_com_ponto_no_nome` | `load_map("Mapa v1.2")` perde o que vem depois do último ponto (achado 2.04; a interface não usa essa rota). | Ponto 3 |
| `unit/test_validation_gaps.py` (3 testes) | A validação não confere o nome do botão do mouse, aceita "abrir aplicativo" sem alvo e aceita `repeat_count` menor que -1. | Ponto 3 (leitor v2) |

*O sexto, o das teclas F9 e F10 (achado 2.11), foi corrigido: o teste saiu desta lista e virou o guarda permanente `static/test_ligacao_controle.py` (`md/ESPEC_PAUSA_TECLAS.md`).*

## O que a suíte não prova

- **Qt de verdade.** O ambiente de desenvolvimento não tem PySide6. Os testes de interface foram validados contra o dublê; contra o Qt de verdade só rodam na sua máquina. A rodada de 18/10/2026 confirmou no Qt de verdade as 193 verificações do editor de comandos e 20 dos 22 testes da janela principal; um dos 22 falhou por erro do próprio teste (corrigido na 25.6) e outro travou, com causa ainda desconhecida (`md/PONTO2_REVISAO_25_6.md`).
- **O diagnóstico de travamento no Qt de verdade.** O filtro de eventos, o tratador de mensagens, a limpeza das janelas e o vigia foram testados com o Qt falso e relógio falso; como o PySide6 de verdade os trata só se confirma na sua máquina (toda chamada ao Qt do diagnóstico é protegida: o pior caso é um relatório incompleto, nunca um teste derrubado por ele).
- **Windows de verdade.** `SendInput`, instância única, os `.bat` (nenhum rodou no `cmd.exe` aqui, nem o `pyw.exe -3.14` do `Iniciar.bat`) e o AltGr no ABNT2 só se confirmam em `Rodar_Testes.bat windows`, nos `.bat` e no roteiro manual do relatório do Ponto 2.
- **Python 3.14.** O ambiente de desenvolvimento tem o 3.13. O que muda no 3.14 e dá para checar sem rodá-lo está nas checagens estáticas (módulos removidos, avisos de sintaxe, `return`/`break`/`continue` dentro de `finally`).
- **Espera de aplicativo no Windows** (`WindowsProcessReadiness`): o laço de espera real não tem teste (Ponto 5).
- **Visão** (`vision.py`): captura de tela e comparação de imagens não têm teste (Ponto 6; os achados sobre a espera por imagem de hoje estão em `md/ROADMAP.md`, F1 a F9).
- **Cobertura medida pelo `coverage.py`:** os números do relatório do Ponto 2 foram medidos com uma ferramenta do próprio ambiente (indicativos). O `coverage.py` na sua máquina vai dar números um pouco diferentes; por isso o baseline é gravado lá.
- **Tempo do agendador.** O relógio virtual modela o tempo, não o agendador do sistema; por isso poucos testes (`slow`) usam relógio real.
