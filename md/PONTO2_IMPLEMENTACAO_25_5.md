# Ponto 2 — Implementação (AS 25.4 → 25.5): infraestrutura permanente de testes

Este documento acompanha a versão 25.5. O planejamento está em `Relatorio_Auditoria_AS_25_3_Pontos_2_e_3.md`, as mudanças resumidas em `md/CHANGELOG_V25.md` e o guia de uso da suíte em `tests/README.md`.

## Resultado

Medido num ambiente com Python 3.13, pytest 9.1.1 (cópia local, sem rede), sem PySide6 real, sem Windows, sem Python 3.14 e sem coverage.py.
**Não foi validado:** o Windows (`SendInput` real, `.bat`, instância única), o PySide6 real, o Python 3.14 e o hardware. Veja "Hipóteses e limites" e o checklist.

| Verificação | AS 25.4 | AS 25.5 |
|---|---|---|
| Testes em `tests/` | 48: 45 passam, 3 xfail | **1402**. Modo lógica (`rapido`): 1156 passam, 241 pulados (precisam do Qt), 5 xfail. Modo widgets (dublê funcional): 1366 passam, 31 pulados, 5 xfail. **0 falhas** nos dois |
| Executores | só o executor mínimo | pytest 9.1.1 e executor mínimo dão o mesmo resultado, teste a teste (0 diferenças de status) |
| Tempo da suíte (modo lógica) | — | de 18 a 30 s com pytest (2 CPUs); `rapido` pelo lançador: 29 s, saída 0 |
| Cobertura de linhas (indicativa) | 7,7% na 25.3, com 15 testes (medida do planejamento) | **34,3%** (lógica) e **39,3%** (widgets). `core` 89%, `conditions` 99%, `project` 98%, `input_system` 78% (93% sem a prontidão de processo do Windows), interface 10% (lógica) e 17% (widgets) |
| Defeitos plantados que a suíte pega | — | **225 de 225** (0 sobreviveram, 0 inválidos), na árvore extraída do zip entregue |
| Estabilidade (execuções seguidas sem falha) | 6 | **20 de 20** (`repetir 20`; 1366 passam em todas) |
| Regressão do Ponto 1 contra o 25.3 original | — | 25 dos 31 testes falham no 25.3 e os 31 passam na 25.5 (no 25.4 falham 2: os que esperavam as decisões D1 e D3) |
| Regressão do Ponto 2 contra o 25.4 | — | 13 dos 24 falham no 25.4 (e no 25.3) e os 24 passam na 25.5 |

A cobertura foi medida com uma ferramenta própria (`sys.monitoring`, só linhas), não com o `coverage.py`: os números do `coverage.py` (linhas e ramos) vão diferir um pouco. A primeira rodada de `Rodar_Testes.bat cobertura` na sua máquina grava a linha de base.

O código de produção ficou com 11.154 linhas e os testes com 12.421 (mais 833 dos dois dublês de Qt).

## Como usar

```
Rodar_Testes.bat instalar     uma vez; precisa de internet; instala pytest, pytest-timeout e coverage no Python 3.14
Rodar_Testes.bat              duplo clique: suíte completa; o resultado fica em logs\tests_last_run.txt
Rodar_Testes.bat rapido       só a lógica, cerca de 15 s, sem precisar do PySide6
Rodar_Testes.bat windows      ENVIA teclado e mouse de verdade; pede para digitar SIM; cerca de 15 s
```

Os outros modos (`repetir`, `cobertura`, `mutacoes`) e como escrever um teste novo estão em `tests/README.md`. Nenhum modo envia entrada de verdade, exceto `windows`.

## Critérios de conclusão do plano

| # | Critério | Situação |
|---|---|---|
| 1 | `Rodar_Testes.bat rapido`: saída 0 em até 60 s, com log | **Verificado só em parte.** O lançador em Python rodou de ponta a ponta aqui (29 s, saída 0, log gravado em `logs\tests_last_run.txt` e `.xml`). O `.bat` em si nunca rodou no `cmd.exe`: **confirme no seu Windows** |
| 2 | Suíte padrão verde no Windows; no ambiente de desenvolvimento, a lógica verde | Verde aqui (nos 4 modos: dois executores × dois dublês de Qt). No Windows e com o PySide6 real: **não verificado** |
| 3 | Volume mínimo | Atendido: ver abaixo |
| 4 | Cobertura por módulo, com linha de base e catraca | **Parcial.** Metas de `core`, `conditions`, `project` e `input_system` atendidas; **a de interface (25%) não**: 17% no dublê de widgets, e o PySide6 real não foi medido. A catraca existe e está testada (por grupo de módulos, tolerância de 1 ponto), mas a linha de base só é gravada na sua máquina, com o `coverage.py` |
| 5 | 20 execuções seguidas sem falha | Atendido: 20 de 20 com `Rodar_Testes.bat repetir 20` (aqui, pelo lançador em Python), cerca de 10 minutos |
| 6 | Cada achado do Ponto 1 tem teste que falha no 25.3 e passa depois | Atendido, provado com `AS_ROOT` apontando para o 25.3 original: 25 dos 31 testes falham nele e os 31 passam na 25.5. Os 6 que passam no 25.3 são os `[VERDE]`, que protegem o que já funcionava |
| 7 | Defeitos plantados (`KeyCode` indefinido, `resizeEvent` duplicado, sinal sem `connect`) derrubam a suíte estática | Atendido (EST01, EST02 e EST04), dentro dos 225 defeitos plantados |

Volume (mínimo do plano → entregue):

| Suíte | Mínimo | Entregue |
|---|---|---|
| unitários (`unit/`) | 40 | 394 (3 xfail), dos quais 134 são do modelo do mapa; o resto inclui os testes do próprio lançador, da catraca e do verificador de defeitos |
| motor (`engine/`) | 25 | 62 (barreiras, comandos, controle, tempo) |
| gravador + atalhos | 15 | 91 (gravador 29, atalhos 26, monitor 23, botões laterais 13) |
| persistência | 15 | 177 (2 xfail) |
| invariantes estáticos, cada um com controle negativo | 10 | 62 testes |
| contrato dos backends | 8 verificações × cada backend | 291 (Mock, pynput falso e Win32 com `user32` falso) |
| interface | 12 | 240: o diálogo de comando (193) e o Qt de mentira (25) rodam no dublê; **os 22 da janela principal só rodam com o PySide6 real e nunca rodaram** |
| golden | 6 | 8 arquivos golden e 14 testes de cenário (mais os simulados do e2e) |
| Windows opt-in | 5 | 9 testes reais (pulados sem `AS_ALLOW_REAL_INPUT`) e 7 testes simulados do próprio framework |

## O que a infraestrutura encontrou

Escala de confiança: **confirmada** (reproduzida em teste ou medida), **altamente provável** (decorre do código e do comportamento documentado do Qt, mas depende de uma execução real que não tive) e **hipótese**. Os números seguem a ordem em que os achados apareceram; as hipóteses sem número estão em "Hipóteses e limites".

| Achado | Problema | Prova | Confiança | Correção na 25.5 | Teste permanente |
|---|---|---|---|---|---|
| 2.01 | Parada que chega entre o envio de uma tecla (ou botão) e o seu registro como "pressionada" deixava a tecla presa | Parada injetada de dentro do backend falso, em tempo virtual; o defeito plantado MOT01 derruba a suíte | **Confirmada** em tempo virtual (a janela real é de microssegundos) | A thread do motor solta o que sobrou quando sai por parada (`finally`) | `engine/test_engine_control.py`; cenário do mapa "Click genshin" ligado e desligado pelo atalho X1 |
| 2.03 | A migração do JSON antigo roda sempre que o banco está vazio: apagar o último mapa e reabrir traz de volta os mapas antigos da pasta | Teste estrito | **Confirmada** | **Adiada para o Ponto 3** | `persistence/test_project_manager.py` (xfail) |
| 2.04 | `load_map(nome)` usa `Path(nome).stem`: "Mapa v1.2" vira "Mapa v1" | Teste estrito | **Confirmada**, mas **latente**: a interface não usa essa rota | **Adiada para o Ponto 3** | `persistence/test_project_manager.py` (xfail) |
| 2.05 | Não há como desligar um atalho de controle: o campo em branco volta ao padrão | Teste de caracterização | **Confirmada** | **Adiada para o Ponto 3** (o formato novo precisa de um "sem atalho") | `persistence/test_app_settings.py` |
| 2.06 | O backend de fallback (pynput) não conhecia PRINTSCREEN, SCROLLLOCK e NUMLOCK, que o editor oferece | Teste de contrato: 4 falham no 25.4 | **Confirmada** | Os três nomes entram no mapa de teclas | `contract/test_backend_pynput.py` |
| 2.07 | O editor de comandos reescrevia o comando inteiro sem carregar vários campos: abrir e salvar sem mexer o alterava (lista abaixo) | No 25.4, 85 dos 193 testes do editor falham: 42 por asserções que mostram o defeito, 37 pelo `TypeError` do `QPoint` (hipótese) e 6 só porque o 25.4 não tem o relógio injetável. Mais a leitura do código (`currentData() or currentText()`) | **Confirmada** pela leitura do código e no dublê; **altamente provável** no PySide6 real. O item do `QPoint` é **hipótese** | `_load_fields` é a única fonte dos valores iniciais; vale na abertura e na troca de comando | `gui/test_command_dialog.py`, `gui/test_main_window_smoke.py` |
| 2.09 | A pré-visualização (`timeline_rows`) reencadeava os inícios do mapa aberto | Medido nos seus mapas | **Confirmada** | `timeline_rows` só lê | `regression/test_ponto2_achados.py` |
| 2.10 | Mover, reordenar e reencadear cortavam em zero a distância entre comandos sobrepostos | Medido nos seus mapas | **Confirmada** | A distância tem sinal; só muda o trecho que trocou de lugar | `regression/test_ponto2_achados.py` |

### 2.07 em detalhe: o que mudava ao abrir e salvar sem mexer (25.4)

Resultado de rodar os testes do editor contra o código da 25.4 (todos passam na 25.5):

- Todo comando passava a ter "Nenhum aplicativo selecionado" como **processo a esperar**. No código, `result_command` gravava `currentData() or currentText()`, e o item-guia tem dado vazio, então o texto-guia virava valor. No motor, o evento de soltar uma tecla ou botão e o de texto carregam esse processo, e o motor espera um processo com esse nome (sem limite de tempo, porque o tempo limite padrão é 0). Pela leitura do código, um comando criado ou salvo pelo editor travaria a execução no Windows. **Não reproduzi no Windows**, e os seus 3 mapas não servem de contraprova: todos vêm do gravador ou da demonstração (o processo deles é vazio ou `notepad.exe`).
- "Manter pressionado" e "Soltar" viravam "Pressionar e soltar".
- A tecla Espaço e as teclas que a lista fixa não tem (o gravador produz, por exemplo, ";") viravam "A": no combo não editável, `setCurrentText` com um texto que não existe não muda nada, e o item 0 é "A".
- Um aplicativo a abrir fora da lista (escolhido em "Procurar executável…") virava o texto-guia.
- Um comando desativado voltava a ficar ativo.
- O grupo era apagado quando o painel lateral não conhece o mapa (é o caso do painel lateral: `parent._automation_map` não existe lá).
- Um início ou tempo de espera maior que 1 hora era cortado em 3600 s.
- Um movimento mesclado (o que o gravador cria) tinha a duração do trajeto zerada, e o trajeto inteiro seria executado de uma vez.
- Trocar de comando com o painel aberto deixava campos do anterior (início, atraso, duração, rolagem, grupo, condições, processo) para serem gravados no novo.
- **Hipótese (2.07-c):** o editor lia `self._move_pos[0]` num `QPoint`. Se o `QPoint` do PySide6 não aceita índice, abrir o editor de um "Mover o mouse" falhava com `TypeError`. O teste `test_qpoint_tem_x_e_y_mas_nao_e_subscritivel` (em `tests/gui/test_qt_semantics.py`) responde isso na sua primeira rodada completa: se ele falhar, era um alarme falso, e a correção (`x()` e `y()`) continua válida e inofensiva.

### 2.09 e 2.10 em detalhe (medido nos seus mapas)

| Operação | Mapa | AS 25.4 | AS 25.5 |
|---|---|---|---|
| Abrir a pré-visualização | Flins combo (933 comandos) | 932 inícios alterados; duração de 64,871 s para 94,307 s | 0 alterados; 64,871 s |
| Abrir a pré-visualização | Exemplo — Primeira automação | 1 de 2 alterado; de 1,960 s para 3,160 s | 0 alterados |
| Abrir a pré-visualização | Click genshin | 0 alterados | 0 alterados |
| Arrastar uma linha (do comando 300 para o 305) | Flins combo | 932 alterados; de 64,871 s para 94,307 s | 5 alterados (o trecho movido); 64,871 s |
| Soltar uma linha no mesmo lugar | Flins combo | 932 alterados | 0 alterados |

Causa: cada comando guarda um início absoluto, e o reencadeamento recalculava os inícios a partir da sequência cortando em zero a distância entre dois comandos. Num mapa gravado, 568 dos 932 pares consecutivos do "Flins combo" se sobrepõem (o mouse se move enquanto uma tecla está pressionada), então qualquer arraste de linha desfazia as sobreposições do mapa inteiro. Correção: a distância de cada comando para o fim programado do anterior passa a ter sinal (negativa é sobreposição), os inícios são recalculados em cascata só no trecho que mudou, e um início que já está certo (diferença abaixo de 1 ns) não é regravado.

## O que mudou (arquivos)

Produção (5 arquivos):

- `core.py`: `SystemClock`; `display_mouse_button_name` e `DISPLAY_SWAPS_SIDE_BUTTONS` no lugar de `_normalize_mouse_button_name` (D1); `_gaps_before` e `_retime`, usados por `reflow_timeline`, `reorder_to_ids` e `move_commands` (2.10, D6); `timeline_rows` só lê (2.09); versão 25.5.
- `input_system.py`: `clock=` no `ExecutionEngine` e no `MockInputBackend`; `user32=` e `kernel32=` no `Win32InputBackend`; tecla e botão soltos pela thread do motor ao sair por parada (2.01); três nomes de tecla no pynput (2.06); a troca de X1 e X2 sai do monitor, do gravador e dos atalhos (D1); amostragem do mouse do gravador (D3).
- `command_editor.py`: `_load_fields` e auxiliares (2.07); `_friendly_target` removido.
- `main_window.py`: o mouse virtual usa `display_mouse_button_name` (única troca de X1 e X2 que sobra).
- `__init__.py`: versão.

Em todos os seams novos o comportamento padrão é idêntico ao anterior (D9).

Projeto e testes:

- `Rodar_Testes.bat` (fim de linha do Windows) e `tests/testsupport/rodar_testes.py`; `requirements-dev.txt` (pytest, pytest-timeout, coverage); `pytest.ini` com `--strict-markers`.
- `tests/`: `unit`, `engine`, `contract`, `persistence`, `static`, `gui`, `scenarios`, `regression`, `e2e_windows`, `data` (3 mapas reais e 8 golden) e `testsupport` (relógio virtual, fakes, dois Qt de mentira, verificador de defeitos, catraca de cobertura, verificações estáticas, executor mínimo). O plano chamava a pasta de `tests/support/`; usei `tests/testsupport/`, um nome mais específico que não colide com outros módulos chamados `support`.
- `README.md` e `tests/README.md` novos; `md/CHANGELOG_V25.md` e este documento.

## Decisões tomadas por mim (você pode vetar)

Você autorizou decidir o que estava pendente, avisando o que escolhi e por quê.

- **D1, botões laterais.** O caminho funcional (monitor, gravador, atalhos, backends) usa só o nome cru do sistema: `x1` é o XBUTTON1 do Windows. Só o mouse virtual troca X1 e X2, para desenhar o botão "superior" como X1. *Por quê:* na 25.4 a troca era aplicada duas vezes no caminho funcional (no monitor e de novo no gravador e nos atalhos), uma desfazendo a outra, e só o mouse virtual via a troca simples. Ou seja, o comportamento que você tinha já era o dos nomes crus; agora isso é explícito, está testado, e a troca existe num só lugar. **Para vetar:** diga o que o mouse virtual mostra quando você aperta o botão lateral mais próximo da frente do mouse; se o desenho estiver invertido, mude `DISPLAY_SWAPS_SIDE_BUTTONS` para `False`.
- **D3, amostragem do mouse.** O intervalo do gravador (padrão 8 ms) passa a valer, e a última amostra descartada pelo intervalo é mantida. *Por quê:* o controle existe na tela de configurações; no código antigo a primeira condição era inútil (a segunda já a cobria). Efeito: gravações novas têm menos pontos quando o mouse manda mais de 125 amostras por segundo, e o trajeto sempre termina onde o cursor parou. Os seus mapas existentes não mudam.
- **D6, reflow.** Com `preserve_gaps=True` o reencadeamento é a identidade: cada distância, inclusive a negativa (sobreposição), é mantida. *Por quê:* sobreposição é o normal num mapa gravado (2.10), e um reencadeamento que preserva distâncias não pode mudar um mapa coerente.
- **Pré-visualização pura.** `timeline_rows` não altera o mapa. *Por quê:* uma pré-visualização que muda os dados que mostra (2.09) não é uma pré-visualização.
- **D9, seams de teste.** Implementados como você autorizou, com comportamento padrão idêntico.
- **D16, os 3 mapas como fixtures permanentes.** Sim: `tests/data/legacy_maps.json.gz` (41 KB). *Por quê:* são os únicos dados reais e serão a garantia de equivalência do Ponto 3.
- **D11 a D15 (formato do Ponto 3).** Não decidi agora; decido no Ponto 3, sob a mesma autorização. As recomendações do planejamento continuam valendo: TOML, banco mantido com exportar e importar, milissegundos adaptativos, grupos regenerados na leitura, tempo absoluto.
- **O lançador só liga o input real no modo `windows`**, e só depois de você digitar SIM. Todos os outros modos removem `AS_ALLOW_REAL_INPUT` do ambiente. As verificações e2e reais conferem que a janela de teste está em primeiro plano antes do primeiro clique ou texto, e a verificação estática exige que essa guarda venha antes do envio, na ordem do código.
- **Dois dublês de Qt, nunca por acaso.** `AS_TEST_QT_STUB=1` (só a lógica) e `widgets` (executa o código Python dos diálogos). Sem a variável, o PySide6 real é o padrão, e um teste garante que os dublês nunca ligam sozinhos.
- **Verificador de defeitos retomável**, porque a rodada completa leva de 25 a 30 minutos. O progresso só vale para o mesmo projeto (impressão digital), para não misturar resultados de suítes diferentes.
- **Catraca de cobertura por grupo de módulos** (core, conditions, project, input_system, vision, interface, outros e total), tolerância de 1 ponto, linhas e ramos do `coverage.py`. Uma queda nunca reescreve a linha de base; subir é com `--gravar`. Uma rodada parcial (com `-k`, por exemplo) não mexe na catraca. *Por quê:* a meta por módulo do plano exigia uma medida que só o `coverage.py` dá, na sua máquina.
- **Não mexi no caminho do registro** (`r'Software\\AutomationStudio'`, com barra dupla): é hipótese, e mudar poderia deixar para trás uma pasta de dados já salva. Veja as hipóteses.
- **Teste de contrato com todos os nomes de tecla**: todo nome que o gravador produz ou o editor oferece precisa ser aceito por todos os backends (generaliza o item 1.10 do Ponto 1). As teclas do teclado numérico ficam de fora no pynput, fora do Windows.

## Hipóteses e limites

Hipóteses (não confirmadas; nenhuma foi corrigida sem prova):

1. **`VkKeyScanW`, `VkKeyScanExW` e `GetKeyboardLayout` são chamadas sem `restype` nem `argtypes`** (`input_system.py`, backend Win32). O padrão do ctypes é `int` de 32 bits, e essas funções devolvem `SHORT` ou um `HKL` de 64 bits. O código compara o resultado com `-1`; se "caractere sem tecla" chegar como 65535, a comparação falha e o texto enviaria `0xFF` com SHIFT, CTRL e ALT. O teste real do modo `windows` (digitação com o layout ativo) pode revelar. A correção é pequena, mas não a fiz sem poder verificar no Windows. Fica para o Ponto 5.
2. **Caminho do registro com barra dupla.** `winreg.OpenKey` e `CreateKey` recebem `r'Software\\AutomationStudio'`. Se o Windows não tolerar a barra dupla, a pasta de dados escolhida não persiste (o código ignora a exceção). Confira no `regedit`, depois de escolher uma pasta nas configurações: a chave `DataDir` deve estar em `HKEY_CURRENT_USER\Software\AutomationStudio`.
3. **Movimento relativo do mouse e aceleração do ponteiro.** `SendInput` relativo passa pela aceleração do Windows. Mapas com movimento absoluto não são afetados.
4. **`mouse_up` repetido na parada.** Se a parada chega no meio da soltura, o motor solta o botão de novo (um `mouse_up` a mais). É inofensivo e está registrado como caracterização em `scenarios/test_cenarios_mapas_reais.py`; muda junto se o Ponto 5 evitar a repetição.
5. **`resources/keyboard_layout.json` não existe** no pacote: o programa usa sempre o ABNT2 embutido.
6. **`Command.from_dict` usa 8,0 como padrão de `wait_min_ram_mb`** (a dataclass usa 0,0). O campo é legado e ignorado pela execução atual.
7. **Guarda redundante no motor.** A guarda de parada dentro de `_apply_wait_conditions` é redundante com a do laço (`except ProcessReadinessError`): tirar só ela não muda nada observável. É o único defeito plantado "equivalente" que documentei; candidato a limpeza no Ponto 5.
8. **Comportamentos que a suíte só descreve** (caracterização, não decisão): o perfil de atraso do grupo sobrescreve o atraso gravado quando o editor tem o mapa do pai (`gui/test_command_dialog.py`); e o leitor do formato v1 aceita sem avisar um tipo de comando desconhecido (vira tecla), o texto "false" como verdadeiro, um nome que não é texto e um `conflict_behavior` desconhecido (`persistence/test_reader_tolerance.py`). O Ponto 3 troca o leitor, e cada mudança desses comportamentos precisa ser uma decisão.

Limites da verificação:

- **Windows:** o `Rodar_Testes.bat`, os 9 testes e2e reais e o backend Win32 real nunca rodaram. Os testes do Win32 usam um `user32` falso que confere vk, scan code e flags.
- **PySide6 real:** a janela principal (22 testes de fumaça) nunca foi construída em lugar nenhum; o diálogo de comando rodou só no dublê. `tests/gui/test_qt_semantics.py` existe para confrontar as suposições do dublê com o seu PySide6: **se ele falhar, é informação sobre o dublê**, não necessariamente um defeito do programa.
- **Python 3.14:** a suíte nunca rodou nele. A verificação estática emula o que a 3.14 recusa (PEP 765: `return`, `break` e `continue` dentro de `finally`; escapes inválidos em strings; módulos removidos), e o código está limpo nesses pontos.
- **`coverage.py` e `pytest-timeout`:** não rodaram aqui. O pytest 9.1.1 é o que o cache local tinha; o `requirements-dev.txt` pede `pytest>=8`.
- **Prontidão de processo no Windows** (`WindowsProcessReadiness`, 235 linhas, 17 cobertas) não tem teste: Ponto 5. **Captura e comparação de imagem** (`vision.py`, 24%): Ponto 6.
- **Cobertura da interface:** 17% no dublê de widgets, abaixo da meta de 25%. A janela principal (1.823 linhas executáveis) tem 8%.
- O relógio virtual modela o tempo, não o agendador do sistema: poucos testes usam tempo real (marcados `slow`).

## Checklist manual no Windows

Primeiro, a rodada automatizada (cerca de 10 minutos). Os logs de qualquer falha são o que eu preciso: `logs\tests_last_run.txt` e `logs\tests_windows_last_run.txt`.

1. `Rodar_Testes.bat instalar` (precisa de internet). Se falhar, `logs\instalar_last_run.txt` mostra qual pacote não existe para a 3.14.
2. `Rodar_Testes.bat rapido`: esperado, saída 0 e algo como 1156 passed, 241 skipped, 5 xfailed, em menos de 1 minuto.
3. `Rodar_Testes.bat` (completo, com o seu PySide6): **é a primeira vez que a interface roda contra o Qt real**. Falhas em `gui/` são esperadas como possibilidade; envie o log.
4. `Rodar_Testes.bat cobertura`: a primeira rodada grava `tests\coverage_baseline.json`.
5. `Rodar_Testes.bat repetir 5`: nenhuma falha em nenhuma das 5.
6. `Rodar_Testes.bat windows`: digite SIM, **não mexa no teclado nem no mouse por cerca de 15 s**. Um teste pulado não é um teste aprovado: ele pula quando a janela de teste não conseguiu o primeiro plano.

Depois, no programa (cerca de 15 minutos), para o que a 25.5 mudou:

7. Editor: crie um comando de tecla pelo editor, salve, reabra: o aplicativo a esperar deve estar vazio. Rode o mapa: a tecla é enviada sem esperar processo nenhum.
8. Editor: abra um comando "Espaço" e salve sem mexer: continua Espaço. O mesmo com um comando desativado (continua desativado) e com um "Manter pressionado".
9. Editor: abra um comando "Mover o mouse" (inclusive um do gravador): abre sem erro (hipótese do `QPoint`).
10. Pré-visualização do "Flins combo": a duração mostrada continua 64,9 s (antes ficava 94,3 s).
11. Arraste uma linha do "Flins combo": a duração continua 64,9 s.
12. "Click genshin" com atalho X1: ligue e desligue várias vezes, inclusive apertando rápido: o botão esquerdo nunca fica preso.
13. Botões laterais: aperte o mais próximo da frente do mouse e diga como aparece no mouse virtual, no diálogo de atalho e numa gravação (decisão D1).
14. Grave um movimento do mouse e confira que o trajeto termina onde o cursor parou.
15. Configurações: escolha uma pasta de dados, feche e abra o programa: ela persiste; confira a chave no `regedit` (hipótese 2).
16. Do Ponto 1, ainda não conferido: AltGr no ABNT2 (AltGr+Q digita "/") e a instância única (abrir `Iniciar.bat` duas vezes).

## Pendências

Dependem de você:

- **D1** (botões laterais), pelo item 13 do checklist.
- **D11 a D15**, quando começarmos o Ponto 3.

Já encaminhadas:

- **Ponto 3** (formato v2): 2.03, 2.04, 2.05 e as 3 lacunas de validação (botão de mouse desconhecido, "Abrir aplicativo" sem alvo, `repeat_count` menor que −1), todas com teste `xfail` (os cinco que aparecem como "xfailed") ou de caracterização. Excluir e exportar mapa (D5) também.
- **Ponto 5** (motor e barreiras): hipótese 1, o `mouse_up` repetido, a prontidão de processo.
- **Ponto 6** (visão): captura e comparação de imagem.

## Itens menores deixados como estão

- 34 métodos nunca referenciados (código morto candidato; a catraca impede que aumentem) e 27 `import *`. Só removo com a sua confirmação.
- `reflow_timeline` agora só é chamado por `_test_selected_commands`.
- `execution_requested`, `rows_reordered`, `positionSelected` e o `currentChanged` próprio de uma aba continuam sem uso.

## Anexo: defeitos plantados por área

O verificador (`py tests/testsupport/mutacoes.py`) planta um defeito de cada vez numa cópia do projeto e roda a suíte inteira contra ela. Cada defeito é um trecho de texto que precisa aparecer exatamente o número esperado de vezes, compila e importa; "morto" quer dizer que um teste que passava passou a falhar. A tabela completa é gerada por `--tabela`, e `--listar` mostra os defeitos. São 225:

| Área | Defeitos | O que protege |
|---|---:|---|
| modelo | 50 | comandos, mapas, linha do tempo, reencadeamento, validação, leitura e gravação |
| motor | 33 | parada, pausa, velocidade, barreiras, texto, aplicativos, teclas presas |
| editor | 30 | o editor de comandos (2.07): cada campo carregado e salvo |
| redes (e2e Windows) | 25 | o framework de testes reais: guardas de primeiro plano, isolamento, limpeza |
| win32 | 21 | o backend Win32: `SendInput`, teclas, botões, texto, AltGr |
| gravador | 17 | amostragem, mesclagem de movimento, duração de teclas, filtros |
| persistência | 16 | banco, configurações, histórico, leitura tolerante |
| estático | 12 | os invariantes estáticos (incluindo PEP 765) |
| atalhos | 11 | o gerenciador de atalhos globais |
| botões laterais | 6 | D1 |
| pynput | 4 | o backend de fallback |

Resultado da rodada final, feita na árvore extraída do zip: **225 mortos, 0 sobreviveram, 0 inválidos** (100% dos defeitos válidos pegos). A rodada levou cerca de 30 minutos e foi interrompida uma vez, na metade; o `--retomar` continuou dali (114 resultados vieram do progresso gravado, depois de conferir que o projeto era o mesmo).
