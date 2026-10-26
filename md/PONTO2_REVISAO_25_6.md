# Ponto 2 — Revisão (AS 25.5 → 25.6): a primeira rodada no Windows

Este documento acompanha a versão 25.6 e responde à rodada de testes que você fez em 18/10/2026. O que a 25.5 entregou está em `md/PONTO2_IMPLEMENTACAO_25_5.md`; as mudanças resumidas, em `md/CHANGELOG_V25.md`; o guia da suíte, em `tests/README.md`; o planejamento do que vem (incluindo o seu pedido de espera por imagem), em `md/ROADMAP.md`.

## Resultado

**O programa não mudou.** Em `automationstudio/` a única diferença para a 25.5 é o número da versão (conferido por comparação arquivo a arquivo). Os três problemas da rodada eram da infraestrutura de testes e dos `.bat`.

| O que a sua rodada mostrou | Conclusão | O que a 25.6 faz |
|---|---|---|
| 653 testes antes do primeiro problema: **644 passaram** e 9 foram pulados de propósito (os e2e com entrada real) | Contratos dos backends, e2e simulado, motor, gravador, atalhos e as 193 verificações do editor de comandos **passaram no Windows, com Python 3.14 e PySide6 de verdade**. É a primeira confirmação real de que a suíte serve | — |
| O 654º teste falhou (`F`) | Erro **do teste** (esperava a versão no título da janela), não do programa | Corrige o teste (R2) |
| Do 655º ao 674º: 20 testes da janela principal **passaram** | A janela principal foi construída no Qt de verdade e as fixtures de isolamento funcionam | — |
| O 675º (o 22º da janela principal) **travou 180 s** dentro de `QApplication.processEvents()` e o pytest-timeout encerrou a rodada inteira | **Causa desconhecida.** Não reproduzida aqui | Não deixa mais um travamento derrubar a rodada e faz o próximo deixar provas (R3) |
| Nenhum detalhe da falha no log | A rodada nunca chegou ao fim, que é onde o pytest imprime os detalhes | Imprime cada falha na hora e termina com um RESUMO (R4) |
| `Iniciar.bat`: "pythonw.exe não encontrado" e o log com letras trocadas | O programa abriu e rodou normalmente; o problema era o `.bat` (R1) | Reescreve o início do programa sem copiar caminhos |

Medido no ambiente de desenvolvimento (Python 3.13, pytest 9.1.1, **sem Windows e sem PySide6 de verdade**):

| Verificação | AS 25.5 | AS 25.6 |
|---|---|---|
| Testes em `tests/` | 1402 | **1514** (+112: 51 do diagnóstico, 49 do lançador, 11 das verificações estáticas e 1 do verificador de defeitos) |
| Modo lógica (`rapido`) | 1156 passam, 241 pulados, 5 xfail | **1267 passam, 242 pulados, 5 xfail**, 0 falhas |
| Modo widgets (dublê funcional) | 1366 passam, 31 pulados, 5 xfail | **1478 passam, 31 pulados, 5 xfail**, 0 falhas |
| Executores | pytest e executor mínimo idênticos | idênticos, teste a teste (0 diferenças em 853 funções de teste) |
| Defeitos plantados que a suíte pega | 225 de 225 | **292 de 292** (rodada completa, 46,6 min: 0 sobreviveram, 0 inválidos) |
| Defeitos plantados novos da 25.6 (67: lançador, diagnóstico, higiene das janelas, relato de falhas e `.bat`) | — | **67 de 67 mortos**, 0 sobreviveram, 0 inválidos |

**Não verificado** (precisa do seu computador): o `.bat` no `cmd.exe`, o `pyw.exe -3.14`, o comportamento no PySide6 de verdade das fixtures e do diagnóstico novos, a medição de cobertura com o `coverage.py` e, sobretudo, **a causa do travamento**. Veja "Verificado × não verificado".

## O que a sua rodada mostrou, ponto a ponto

### R1 — `Iniciar.bat` com a pasta de usuário acentuada

**Problema.** O log do `Iniciar.bat` avisava "pythonw.exe nao encontrado ao lado do Python selecionado" embora o Python estivesse na pasta indicada, e as linhas do log mostravam o nome acentuado de duas maneiras diferentes. Você concluiu que o programa "não está conseguindo ler a minha pasta".

**Evidência (do seu log).**
- A linha "Python selecionado pelo Launcher:" mostra a letra acentuada correta (por exemplo, `ç`). As linhas "Pasta:", "Python:" e "Arquivo:" mostram a mesma letra como **dois caracteres** (`Ã§`). Isso é o padrão de texto gravado em UTF-8 e lido como cp1252: o arquivo tinha **duas codificações misturadas**.
- O aviso do `pythonw.exe` apareceu e o programa abriu pelo `py.exe` mesmo assim.
- O programa abriu, executou um mapa (esperou o Bloco de Notas ficar pronto, digitou 186 caracteres com o `Win32InputBackend`) e terminou com código 0. Ou seja: **a pasta foi lida normalmente**; o que falhou foi só a detecção do `pythonw.exe` e a legibilidade do log.

**Causa.** O `.bat` fazia `chcp 65001` (o `echo` passa a gravar UTF-8) e copiava o caminho que o Python imprimia (`sys.executable`) para uma variável com `for /f`. O Python, quando escreve num arquivo ou num pipe sem `PYTHONUTF8`, usa a página de código do sistema (cp1252): as linhas que ele gravou direto no log ficaram em cp1252 e as do `echo`, em UTF-8, o que explica a mistura. E o `for /f` recebia bytes cp1252 com o `cmd` esperando UTF-8: o caminho copiado ficava errado e o `if not exist` falhava. **Confiança: a mistura de codificações é confirmada pelo seu log; que o `for /f` quebrou a detecção do `pythonw.exe` é altamente provável** (decorre do funcionamento do `cmd`, mas o `cmd.exe` não roda no ambiente de desenvolvimento).

**Correção.**
- `Iniciar.bat` e `Iniciar - Limpar e Abrir.bat` abrem o programa direto por `pyw.exe -3.14` (o mesmo Python que o `py.exe -3.14` escolhe, sem janela de terminal), sem copiar caminho nenhum. Sem o `pyw.exe`, usam o `py.exe` e registram um aviso (a janela de terminal fica aberta enquanto o programa roda).
- Os Pythons auxiliares que escrevem no log (`Iniciar.bat`, `Iniciar - Limpar e Abrir.bat`, `Instalar_Dependencias_Global.bat`, `Rodar_Testes.bat`) rodam com `PYTHONUTF8=1`: o log fica **todo em UTF-8**.
- A variável `PYTHONUTF8` é **limpa antes de abrir o programa**: ele rodava sem ela e continua assim.

**Impactos.** Só os `.bat`. Quem usa o `Iniciar.bat` não vê diferença, exceto o log (sem o aviso e sem letras trocadas). O `Iniciar como administrador.bat` não mudou (chama o `Iniciar.bat`).

**Testes.** Três verificações estáticas novas, cada uma com controle negativo: os `.bat` só têm ASCII; os `.bat` que gravam saída de Python no log usam o modo UTF-8; nenhum `.bat` copia texto que o Python imprimiu com `for /f`. Mais três defeitos plantados (NET83 a NET85: `for /f` de volta, uma letra acentuada, o modo UTF-8 removido), todos mortos.

**Automação.** Tudo acima roda no `Rodar_Testes.bat`. O `.bat` em si só se confirma no `cmd.exe`.

**Critério de conclusão.** O `logs\AutomationStudio.log` de uma execução do `Iniciar.bat` na sua máquina **sem** o aviso do `pythonw.exe` e com todas as letras acentuadas iguais em todas as linhas.

### R2 — o `F` (o 654º teste)

**Problema.** O primeiro teste da janela principal falhou.

**Evidência.** A posição do `F` no log: 653 testes antes (contratos 291, e2e 16, motor, gravador e atalhos 153, editor de comandos 193); o arquivo seguinte na ordem do pytest é `tests/gui/test_main_window_smoke.py`, cujo primeiro teste é `test_a_janela_abre_na_escolha_de_automacao`. Esse teste esperava `Automation Studio — AS <versão>` no título. No código (`main_window.py`), o `__init__` põe esse título (linha 106), mas `_build_status_bar()` chama `_update_status_label()` (linhas 1144 e 2265), que o troca por `Automation Studio — ● PARADO`. Já era assim na 25.3 (o título da 25.3 também era trocado pelo estado).

**Causa.** Erro do teste: ele afirmava uma coisa que o programa nunca fez.

**Confiança.** Que a causa do `F` seja esta: **altamente provável** (a posição bate com o primeiro teste do arquivo; a asserção é falsa por leitura do código; o detalhe da falha não está no log, ver R4). Que o título nunca mostrou a versão: **confirmada** pela leitura do código.

**Correção.** O teste confere o título que o programa de fato mostra (`f"Automation Studio — {core._STATE_LABELS[State.IDLE]}"`). O programa não mudou. Se você quiser a versão no título, é uma mudança do programa a decidir à parte (veja "Observações").

**Impactos.** Só o teste. **Testes.** O próprio teste; a verificação estática do título (a versão não pode estar escrita à mão no `main_window.py`) continua valendo. **Critério.** O teste passa na sua próxima rodada.

### R3 — o travamento do 22º teste da janela principal

**Problema.** `test_a_timeline_abre_com_os_mapas_reais` ficou 180 s sem terminar e o pytest-timeout matou o processo; os testes que viriam depois (e o resumo) nunca rodaram.

**Evidência (do seu log).**
- O teste está parado em `QApplication.processEvents()` (`tests/gui/test_main_window_smoke.py`, linha 242 na 25.5): a chamada nativa **não voltou**.
- O despejo de pilhas mostra **só duas threads do Python**: a principal (parada nessa linha) e a do próprio pytest-timeout. Não havia outra thread do Python viva (nem a do motor, nem a dos atalhos globais), o que descarta impasse entre threads do Python.
- A pilha do Python **não tem nenhum quadro acima da linha do teste**: nenhum slot Python estava em execução dentro do `processEvents()` (um slot preso, por exemplo num diálogo modal, apareceria na pilha). O que não volta está em código nativo do Qt. É uma amostra só; o vigia novo coleta mais.
- Depois do banner do timeout aparece `Windows fatal exception: access violation`, com a thread do pytest-timeout como "Current thread". O pytest-timeout (método `thread`, o padrão no Windows) imprime as pilhas e depois encerra o processo à força com `os._exit()`, sem desmontar nada. Minha leitura é que a violação de acesso vem desse encerramento forçado com a thread principal presa dentro do Qt, e **não** é a causa do travamento. **Hipótese**.
- É o primeiro teste que faz `janela.show()` e processa eventos de verdade; os 21 anteriores nunca processaram eventos nem destruíram as janelas que criaram.

**Causa: desconhecida.** Há quatro hipóteses (**nenhuma foi confirmada**; a ordem abaixo é a de explicação, **não** de probabilidade: não tenho base para ordená-las). Para cada uma, o que ela explica e como se encaixa na pilha do seu log:
1. **Acúmulo.** Pela documentação do Qt, `processEvents()` chamado fora de um laço de eventos não executa os `deleteLater()` pendentes; as 21 janelas dos testes anteriores continuaram vivas, com o que deixaram na fila (temporizadores de intervalo zero, animações, sinais enfileirados), e o 22º processaria tudo de uma vez. Explica por que o travamento é exatamente no primeiro `processEvents()` e só nesse teste. Não explica sozinha por que travaria em vez de só demorar.
2. **Custo do primeiro `show()`.** A primeira exibição de uma janela principal (estilo, polimento e layout das páginas), com os 3 mapas reais carregados (o 21º teste tinha aberto os 3 em tabelas de até 933 linhas, e essa janela continuava viva). Explicaria lentidão, não um travamento de 180 s sem fim.
3. **Laço de eventos que se reativa** (um temporizador que se reagenda sem parar). O código tem candidatos (por exemplo, a função interna `size_toolbar`, que nunca é chamada, mas se reagendaria com `QTimer.singleShot(0, ...)`), nenhum comprovado. A pilha sem quadros Python (acima) não favorece esta hipótese, porque um laço de temporizadores Python costuma aparecer nela; uma amostra só não a exclui.
4. **Problema nativo** do Qt `offscreen` no Windows com Python 3.14, independente do programa. É a que melhor combina com a pilha sem quadros Python.

**Confiança.** Todas são **hipóteses**; nenhuma chega a "provável". O que é **confirmado** é o que está em "Evidência".

**Correção.** Não corrigi o que não entendo. Em vez disso, a 25.6 faz duas coisas: impede que um travamento derrube a rodada e faz o próximo deixar provas.
- **Um processo por teste, com tempo limite.** Os testes da janela principal ganham o marcador `isolado` e o `Rodar_Testes.bat` roda cada um num processo só dele (passo isolado); um travamento ou uma queda do Qt reprova só aquele teste, e os outros seguem. Os demais testes continuam no mesmo processo (passo comum, `-m "not isolado"`). Uma verificação estática reprova qualquer teste que abra a janela principal e não seja `isolado`.
- **Nada de um teste sobra para o seguinte.** No fim de cada teste de janela: parar o relógio da interface e o motor, fechar, `deleteLater()`, esvaziar a fila (processar, executar as exclusões pendentes, processar de novo) e deixar o coletor de lixo do Python soltar os ciclos. `processar_eventos` (passadas mínimas e limite de tempo) substitui o `processEvents()` solto.
- **Vigia em cada teste de janela.** Aos 60 s (`AS_LIMITE_TESTE_JANELA`) uma thread grava `logs\travamento_qt.txt` com: o teste e a fase, os **últimos eventos que o Qt entregou** (receptor, tipo, nome) e os contadores, as **mensagens que o próprio Qt imprimiu**, as pilhas das threads, o ambiente e um **diagnóstico**: "bloqueado" (nenhum evento passa: provável impasse nativo) ou "laço de eventos" (eventos passam sem parar: algo se reativa, com o culpado nomeado). Em seguida encerra o processo com o código 86. Um alarme **nativo** (`faulthandler`) dispara 15 s depois, caso a thread do Python não consiga rodar (por exemplo, GIL preso numa chamada nativa), e grava `logs\travamento_qt_nativo.txt`. A thread do vigia **nunca chama o Qt** (só lê estruturas do Python).
- **Hierarquia de tempos**: vigia 60 s < pytest-timeout do teste isolado 90 s < o lançador mata o processo aos 120 s. Cada um é a reserva do anterior; quem dispara primeiro deixa a prova mais completa.
- **Se um teste travar fora do isolamento**, o passo comum roda de novo **sem ele** (até 3 vezes) e a rodada termina com o código 86: um travamento nunca esconde os testes que viriam depois, e **nunca** conta como rodada limpa.
- **Se 3 testes isolados travarem em sequência**, o passo isolado **para** e o RESUMO diz quantos testes `NÃO RODOU`. Três travamentos seguidos indicam um problema do ambiente e não de um teste; esperar o tempo limite de cada um dos que faltam (cerca de 1 minuto por teste, até 19 testes) só repetiria o mesmo relatório. Um teste que passa zera a contagem. A rodada não conta como limpa.
- **Código de saída.** Dentro de um passo, uma falha de teste (1) vale mais do que um travamento (86), seja qual for a ordem; entre passos vale o primeiro que não terminou limpo. O RESUMO lista tudo, qualquer que seja o número.

**Impactos.** Só testes e o lançador; o programa não mudou. O passo isolado cria um processo Python por teste (22): a rodada completa fica mais lenta que a de 18/10; não consigo medir quanto aqui (precisa do PySide6).

**Testes.** 51 testes novos do diagnóstico (com Qt falso e relógio falso) e 49 novos do lançador (inclusive com processos filhos de verdade: tempo estourado, código do vigia, queda, a parada depois de 3 travamentos seguidos e a regra do código de saída); 67 defeitos plantados novos (ver o quadro do início). Os testes do diagnóstico **não** provam como o Qt de verdade se comporta (veja "Verificado × não verificado").

**Automação.** `Rodar_Testes.bat` (modos `completo`, `repetir` e `cobertura` usam os dois passos; o `rapido` não precisa do Qt e não os usa).

**Critério de conclusão.** Na sua próxima rodada: (a) todos os testes da janela principal passam, **ou** (b) o travamento volta e deixa `logs\travamento_qt.txt`, que diz o que o Qt fazia. O R3 só fecha quando a causa estiver entendida e corrigida.

**Um limite que vale dizer.** Como `processar_eventos` termina por tempo, se a causa for o caso 3 (um temporizador que se reagenda sem parar), o teste **passa em vez de travar**, e o problema fica escondido. Mantive assim porque um teste que nunca termina não ensina nada; para olhar de perto, o RESUMO mostra a duração de cada teste isolado (um teste que gasta o tempo inteiro da passada é suspeito) e o experimento abaixo isola o teste 22.

### R4 — falhas só no fim e nenhum resumo

**Problema.** O `F` apareceu como um ponto no progresso, mas o motivo nunca foi mostrado: o pytest imprime os detalhes das falhas **no fim da rodada**, e a rodada morreu antes.

**Evidência.** O seu log: nenhuma linha de falha; o fim abortado pelo timeout. **Confiança: confirmada.**

**Correção.** Um gancho no `conftest.py` imprime **na hora** cada falha, com o detalhe e a saída capturada; o resumo do fim fica em uma linha por falha (`--tb=line`); o passo isolado imprime o resultado de cada teste assim que ele termina; o fim da rodada traz um **RESUMO** (OK, PULADO, FALHOU, TRAVOU, QUEDA por passo) e diz quais arquivos enviar. **Testes:** 2 testes do gancho e os de resumo do lançador. **Critério:** na próxima falha, o log mostra o detalhe sem esperar o fim.

## Decisões tomadas por mim (você pode vetar)

| # | O que escolhi | Por quê |
|---|---|---|
| 1 | Abrir o programa por `pyw.exe -3.14` em vez de achar e copiar o caminho do `pythonw.exe` | Elimina a causa (copiar caminho com acento) em vez de contorná-la; é o mesmo Python que o `py.exe -3.14` escolhe; sem o `pyw.exe` há reserva com aviso |
| 2 | Limpar o `PYTHONUTF8` antes de abrir o programa | O programa nunca rodou com essa variável; ligá-la mudaria a codificação dos arquivos que ele abre e dos processos que ele inicia, uma mudança de comportamento que ninguém pediu |
| 3 | Isolar **só** os testes da janela principal | São os que usam o Qt nativo e a tela; os outros 1.492 passam juntos (cerca de 23 s aqui, no dublê). Um processo por teste custaria o início do Python 1.514 vezes |
| 4 | Tempos 60 s < 90 s < 120 s (vigia, pytest-timeout do teste isolado, lançador), e 180 s no passo comum | O primeiro a disparar deixa a prova mais completa; os outros são reservas se aquele não puder rodar |
| 5 | Rodar de novo, sem o teste que travou (até 3 vezes), mas sair com 86 | Um travamento não pode esconder os testes seguintes, e também não pode contar como verde |
| 5b | O passo isolado **para depois de 3 travamentos seguidos** e conta os testes que não rodaram | Se o Qt trava em todo teste de janela, são até 22 minutos para repetir o mesmo relatório; os três primeiros já dizem o que o Qt fazia. Três, e não um, para um travamento isolado não esconder o resto |
| 5c | Dentro de um passo, **falha de teste (1) vale mais que travamento (86)** no código de saída | Era o código do primeiro teste ruim, o que contradizia o README ("86 quando algum teste travou") e dependia da ordem. O RESUMO continua listando os dois |
| 6 | O verificador de defeitos usa o dublê de widgets por padrão (o Qt de verdade só com `AS_MUTACOES_QT_REAL=1`) | Ele roda a suíte inteira por defeito com o executor mínimo, que não isola testes um por processo: com o Qt de verdade, um travamento num teste de janela seguraria cada defeito até o tempo limite |
| 7 | **Não** mudei o programa e **não** aumentei tempos limite para "passar" | Um travamento é informação; mudar o programa sem entender a causa seria chutar. O que eu não sei, eu meço (R3) |
| 8 | `processar_eventos` por tempo e passadas mínimas, no lugar de `processEvents()` solto | Uma passada só não basta (um evento trata e posta outro), e um laço limitado por tempo não prende o teste. Custo conhecido: pode esconder um laço de eventos (R3) |
| 9 | O título da janela e a versão: **não mudei** | Não é defeito dos testes; é uma decisão do programa (abaixo) |

## Observações (não alteradas)

- **O título da janela nunca mostrou a versão** (R2). Se quiser a versão no título ou só na barra de status, diga; é uma mudança pequena do programa.
- **Código morto na janela principal.** `size_toolbar` (função interna que nunca é chamada e se reagendaria sozinha com `QTimer.singleShot(0, ...)`) e `toolbar_hint` (nunca criado). Deixei como estão; limpar no Ponto 4.
- **Diretório atual `C:\Windows\System32`** no seu log (programa aberto como administrador). Não faz diferença: o programa só usa o diretório atual para escrever diagnósticos.
- **Espera por imagem.** Ao ler o código para o planejamento do seu pedido de 18/10, encontrei três armadilhas silenciosas na espera por imagem de hoje (o modo "procurar dentro da região" só funciona com OpenCV, que não está nas dependências; a "similaridade" não percebe diferenças de até 5% da área; a escala do Windows pode quebrar a comparação). Estão em `md/ROADMAP.md` (achados F1 a F9) e entram no Ponto 7. **Não mexi em nada disso na 25.6.**

## Verificado × não verificado

**Verificado aqui** (Python 3.13, pytest 9.1.1, sem Windows e sem PySide6 de verdade):
- A suíte inteira nos dois modos de Qt falso, com o pytest e com o executor mínimo, com resultados idênticos teste a teste.
- A lógica do lançador (plano, passos, classificação, repetição sem o teste que travou, soma dos resultados) com processos filhos de verdade para o que depende de processo: o tempo estourado mata o filho, o código 86 vira TRAVOU, uma queda vira QUEDA.
- O diagnóstico (anel de eventos, vigia, relatório, alarme nativo, filtro de eventos, tratador de mensagens, higiene das janelas) com Qt falso e relógio falso.
- As regras estáticas novas (os `.bat`, o marcador `isolado`).
- O catálogo inteiro de defeitos plantados (292, dos quais 67 novos), todos mortos, numa rodada completa feita com o código e os testes do pacote. Depois dela só mudei documentos e dois textos de instrução (a estimativa da rodada, de 40 para 45 minutos); a suíte inteira rodou de novo no pacote final, extraído numa pasta limpa.
- O programa: idêntico ao da 25.5, exceto o número da versão.

**Não verificado** (precisa da sua máquina):
- **A causa do travamento.** Não reproduzi.
- O comportamento, **no PySide6 de verdade**, de `QCoreApplication.sendPostedEvents(None, 52)`, do filtro de eventos (a iteração dos tipos de `QEvent.Type`), do tratador de mensagens (`qInstallMessageHandler`) e do fechamento de uma `MainWindow` real. Os testes usam o dublê e o Qt falso; se algo se comportar diferente, o diagnóstico foi escrito para **nunca derrubar o teste** (toda chamada ao Qt é protegida), então o pior caso é um diagnóstico incompleto.
- O `.bat` no `cmd.exe` e o comportamento de `pyw.exe -3.14` (o Python install manager do Windows).
- O modo `cobertura` (`coverage run -p` e `coverage combine`): o `coverage.py` não está disponível aqui.
- A parte do verificador de defeitos que exigiria o Qt de verdade (desmontagem de uma `MainWindow` real).
- Se há pacote do OpenCV para o Python 3.14 no Windows (só consegui uma página de terceiros; o PyPI não estava acessível).

## Próxima rodada (o que eu peço de você)

1. Descompacte a `AS_25_6.zip` **numa pasta nova** (por exemplo, ao lado da `AS_25_5`) e rode `Rodar_Testes.bat` (duplo clique). Se o `pytest` ou o `pytest-timeout` não estiverem instalados, `Rodar_Testes.bat instalar` antes (precisa de internet).
2. Me envie `logs\tests_last_run.txt` e, **se existir**, `logs\travamento_qt.txt`. Se tudo passar, só o primeiro.
3. Abra o programa pelo `Iniciar.bat` e me envie `logs\AutomationStudio.log`: ele mostra se o R1 foi resolvido.

A rodada leva alguns minutos quando tudo passa; cada teste que travar custa cerca de 1 minuto (o vigia dispara aos 60 s) e, depois de 3 travamentos seguidos, o passo isolado para e diz quantos testes não rodaram. O passo isolado mostra `[n/22]` e o resultado de cada teste assim que termina, então dá para ver que não parou.

**Se o teste 22 travar de novo** (os experimentos são opcionais e independentes; um de cada vez):
- `set QT_QPA_PLATFORM=minimal` e depois `Rodar_Testes.bat completo -k timeline_abre` (se o travamento some com outra plataforma do Qt, é o plugin `offscreen`);
- `Rodar_Testes.bat completo -k timeline_abre` sozinho (se passa sozinho e travou no conjunto, é acúmulo entre testes; no passo isolado ele já roda sozinho);
- `set AS_DIAGNOSTICO_QT=0` e de novo (descarta como causa o filtro de eventos e o tratador de mensagens do Qt, que são o que o diagnóstico instala; o vigia e as pilhas continuam).
