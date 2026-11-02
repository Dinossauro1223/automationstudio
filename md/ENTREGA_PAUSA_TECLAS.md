# Entrega: pausar e continuar pelas teclas F9 e F10 (achado 2.11)

Registro de entrega (etapa 8 do processo). Não é uma versão do roadmap: é a correção do achado 2.11, o "ponto à parte" que a 25.8 deixou aberto. Como a 25.9 só começa com a 25.8 aprovada, e você me deixou decidir o que estiver pendente (dizendo o que escolhi e por quê), fiz esta correção enquanto isso; o `md/PLANO_FUNCOES.md` (seção 2) a trata como correção de defeito da versão em aberto, a **25.8**. Especificação: `md/ESPEC_PAUSA_TECLAS.md`.

**Onde está:** ramo `funcoes/pausar-continuar-teclas`, publicado no GitHub. Nasceu de `funcoes/ativacao-mapas` e foi **atualizado com a `main` de 31/10/2026** (`b78c7da`, onde a conta de integração já juntou a 25.8 e o tema novo), como pede `md/DELEGACAO.md`. A `main`, o ramo `visual/novo-tema` e a versão (`APP_VERSION = "25.6"`) **não foram tocados**. Nenhum formato de arquivo mudou. A última linha dos commits diz `Versão: 25.8 (em aberto)`.

**Para a integração:** a junção na `main` traz **só os commits desta correção** (a 25.8 já está lá). A suíte rodou nos dublês aqui e, com o Qt de verdade, no GitHub Actions (Linux e Windows): seção 10. **Um dos commits não é da pausa e merece a sua atenção:** o `Infra:` que corrige a limpeza do fim dos testes de janela. O job do Windows do Actions abortava neste ramo por uma fragilidade dessa limpeza (objetos do Qt que um teste deixa para trás são destruídos pelo coletor de lixo do Python num momento imprevisível), que o ramo apenas deslocou de lugar (seção 10). O commit é independente dos outros e pode ser juntado antes, ou separado, se preferirem. O que ainda precisa do ambiente de vocês está na seção 5.

## 1. O que muda para quem usa

- **F9 pausa a automação que está executando.** O título mostra "● PAUSADO", nenhuma tecla ou clique novo sai, e o tempo parado não conta na timeline. A barra de status diz: "Automação pausada. Aperte F10 para continuar." (a tecla de continuar que você configurou).
- **F10 continua do ponto onde parou**, sem repetir nem pular nada. A barra diz "Automação retomada.".
- **Sem automação executando** (parado, gravando, parando), as duas teclas não fazem nada, sem mensagem e sem erro.
- **Se a tecla de continuar não estiver ativa** (inválida, ou igual à de pausar ou à de parar tudo, o que a 25.8 já avisa ao abrir), a pausa acontece e a mensagem diz isso: "A tecla de continuar não está ativa; use o botão de parar para encerrar.".
- **O que não muda:** teclas e botões que já estavam apertados continuam apertados durante a pausa (o motor nunca os soltou na pausa; agora há um teste que fixa isso). Parar, a tecla da própria automação e a parada de emergência continuam valendo com a automação pausada.

## 2. Conferência rápida no Windows (uns 3 minutos)

Os testes de janela real rodaram no GitHub Actions (seção 10), mas sem teclado e mouse de verdade e sem outro programa em foco; esta conferência à mão cobre o que o Actions não cobre.

| # | Faça | Deve acontecer |
|---|---|---|
| 1 | Use uma automação com uma espera longa entre duas teclas (uns 10 s) e aperte ▶ Executar | Título "● EXECUTANDO" |
| 2 | Aperte **F9** (pode estar com outro programa em foco) | Título "● PAUSADO"; barra: "Automação pausada. Aperte F10 para continuar."; nenhuma tecla nova sai |
| 3 | Espere mais que o tempo que faltava para a próxima tecla e aperte **F10** | Título "● EXECUTANDO"; barra: "Automação retomada."; a próxima tecla só sai agora, e a automação termina normalmente |
| 4 | Pause de novo e aperte ■ Parar (ou a tecla da própria automação) | "● PARADO"; nada fica apertado |
| 5 | Sem nada executando, aperte F9 e F10 | Nada acontece (sem mensagem) |
| 6 | Em ⚙ Configurações troque "Continuar automação" para `CTRL+F10`, execute e pause | A mensagem cita `CTRL+F10` |

Se algo não bater, o mais útil é `logs\AutomationStudio.log` e a descrição do que viu.

## 3. Números

| | 25.8 (`29e9a8c`) | Esta correção sobre a 25.8 | Esta correção juntada com a `main` (`b78c7da`) |
|---|---|---|---|
| Testes, dublê de lógica (`AS_TEST_QT_STUB=1`) | 1403 passam, 3 falham, 6 xfail | 1436 passam, 3 falham, 5 xfail | **1457** passam, **0 falham**, 312 pulados, 5 xfail |
| Testes, dublê de widgets (`AS_TEST_QT_STUB=widgets`) | 1630 passam, 3 falham, 6 xfail | 1663 passam, 3 falham, 5 xfail | **1684** passam, **0 falham**, 85 pulados, 5 xfail |
| Defeitos plantados (verificador de mutações) | 355 | 378 (23 novos, mais 1 atualizado) | 378, todos aplicados ao código juntado |

- **Depois da correção da limpeza dos testes de janela (seção 10: +3 testes e +3 defeitos plantados):** dublê de lógica **1460** passam, 0 falham, 312 pulados, 5 xfail; dublê de widgets **1687** passam, 0 falham, 85 pulados, 5 xfail; defeitos plantados **381**. Com o **Qt de verdade, no GitHub Actions** (árvore final, Python 3.14.9, PySide6 6.12.0): **Linux** 1716 passam, 11 pulados, 6 xfail, mais a janela principal, 44 de 44; **Windows** (informativo) 1715 passam, 12 pulados, 6 xfail, mais a janela principal, 44 de 44. Os mesmos números, com código de saída 0 nos dois jobs, no commit publicado `f73765f`, que é o último antes deste texto.
- **Testes novos da pausa: 44** (36 rodam aqui; 8 só rodam com o Qt de verdade): `engine/test_engine_control.py` (+6, um deles o de estresse: milhares de pausas e retomadas vindas de outra thread enquanto o motor executa, sem perder nem repetir entrada nem travar), `unit/test_controle_execucao.py` (19), `static/test_ligacao_controle.py` (11) e `gui/test_controle_janela.py` (8, janela real: o disparo e a mensagem, e as três formas de parar com a automação pausada). O `xfail` do achado 2.11 saiu: o teste `static/test_lacunas_de_ligacao.py` virou o guarda permanente `static/test_ligacao_controle.py` (os 3 controles do verificador foram junto). Por isso o saldo, na coluna do meio, é +33 passando e -1 `xfail`.
- **As 3 falhas das colunas anteriores** não eram desta correção: dois testes de fim de linha dos `.bat` e a validação do catálogo de defeitos (NET10 e NET83, que plantam defeito em CRLF), por o repositório guardar os `.bat` com LF. **Sumiram na árvore juntada:** a integração criou o `.gitattributes` (`*.bat text eol=crlf`), como eu tinha sugerido na entrega da 25.8. (Antes da junção eu já tinha conferido com os `.bat` convertidos para CRLF à mão: 1666 passam, 0 falham.)
- **Catálogo de funções do usuário** (`md/FUNCOES_DO_USUARIO.md`, da integração): ganhou **F47** "Pausar a automação que está executando" e **F48** "Continuar a automação pausada, do ponto onde parou". Como são funções de tecla, o endereço de cada uma é o teste de janela que a exercita. A linha do catálogo e o documento gerado mudaram no mesmo commit, como manda o `md/PLANO_VISUAL.md`. Se outro ramo tiver usado os mesmos números, é só renumerar na junção.
- **Cobertura do `coverage.py`:** não medida (sem `coverage` no ambiente de desenvolvimento). A catraca ganhou o grupo `controle` para o seu baseline.

## 4. Verificador de mutações (a prova de que os testes pegam defeito)

- **25 de 25 mortos** nos defeitos desta correção: 23 novos (`PAU01` a `PAU23`: o motor devolvendo o resultado errado, não tratando a corrida, soltando as teclas na pausa; o controlador mostrando mensagem sem ter pausado, citando a tecla errada ou uma tecla inativa; a janela com o ramo trocado, sem ramo ou criando o controlador tarde demais), o `MOT32` (mesmo defeito de antes, trecho atualizado) e o `EST13` (conferido de novo, agora pelo teste novo).
- **O verificador achou um buraco nos meus testes e eu o fechei:** na primeira rodada, o defeito `PAU08` ("pausar solta as teclas apertadas") só foi pego por um teste que não era o que o protege. O meu teste de "o que não muda" pausava no instante do envio da própria tecla, quando o motor ainda não a tinha registrado como apertada, então não teria visto nada. Mudei o ponto da pausa (depois do envio de uma segunda tecla, com a primeira já registrada) e o `PAU08` passou a ser pego pelo teste certo.
- **Rodada completa do catálogo (378 defeitos), numa cópia da árvore commitada com os `.bat` em CRLF (como ficam no seu Windows): 378 de 378 mortos, 0 sobreviventes, 0 inválidos.** O ambiente interrompeu a rodada e ela foi retomada com `--retomar`, que só aceita continuar sobre o mesmo código e os mesmos testes: 75 resultados vieram do progresso gravado e o trecho final, de 303 defeitos, levou 50,2 min (a rodada inteira costuma levar perto de uma hora).
- **O que a cópia da rodada não tem do commit:** o teste de estresse entre threads (`engine/test_engine_control.py`, o último que acrescentei) e a versão final dos testes de janela real (`gui/test_controle_janela.py`, que não rodam aqui). Acrescentar teste só pode pegar mais defeitos, nunca menos, então os 378 valem para o commit. A contagem de referência dessa rodada (1664 passam com a interface, 1437 com a lógica) bate com a do commit (1663 e 1436) depois de descontar esse teste, somar os 2 de fim de linha dos `.bat` (que passam em CRLF) e tirar o de validação do catálogo (que a própria rodada pula).

- **Depois da junção com a `main` de 31/10:** o verificador confirma que os 378 defeitos ainda se aplicam ao código juntado (`--validar`), e os 25 desta correção foram rodados de novo na árvore juntada, já com os testes novos de janela e o catálogo de funções: **25 de 25 mortos**, em 4,7 min. A rodada completa (uma hora de máquina) não foi refeita nesse momento; foi refeita na árvore final, abaixo.

- **Limpeza dos testes de janela (seção 10):** 3 defeitos novos (`NET93`, `NET94` e `NET95`: a limpeza que não esvazia a fila, a que não coleta o lixo e a fixture `gui` que não a chama) e 2 vizinhos (`NET79` e `NET80`, da mesma fixture): **5 de 5 mortos**. **Rodada completa do catálogo (381 defeitos) na árvore final, numa cópia com os `.bat` em CRLF: 381 de 381 mortos, 0 sobreviventes, 0 inválidos.** O ambiente reiniciou no meio da rodada (com 44 resultados já gravados) e ela foi retomada com `--retomar`; o trecho final, de 337 defeitos, levou 56,8 min. A cópia testada difere do que está commitado só no texto de uma docstring (`gui_helpers.py`, que eu corrigi depois para não afirmar o que não sei), nos documentos e nos `.bat` (CRLF), conferido com `diff`. A árvore commitada, numa cópia nova, foi rodada em seguida nos dois dublês (1460 e 1687 passam, 0 falham) e o `--validar` confirmou que os 381 defeitos se aplicam a ela.

## 5. O que **não** foi verificado

1. **Qt de verdade no seu Windows.** No GitHub Actions (Linux e Windows, Python 3.14.9, PySide6 6.12.0) a suíte inteira passa, inclusive os 8 testes de `gui/test_controle_janela.py` (o disparo da tecla pela janela real, o título "● PAUSADO", a barra de status e as três formas de parar com a automação pausada) e o `tests/gui/test_funcoes_acessiveis.py` que a integração exige verde (seção 10). O que o Actions não tem é o teclado e o mouse de verdade nem outro programa em foco: isso é o item 2.
2. **Windows de verdade:** o atalho global F9/F10 pelo `pynput` e a pausa com outro programa em foco nunca rodaram aqui. A lógica é testada com um gerenciador de atalhos e um monitor falsos e com o motor de verdade (relógio virtual).
3. **Python 3.14:** o ambiente de desenvolvimento daqui tem o 3.13, mas o Actions roda o 3.14.9 (o de `python_version.txt`) e a suíte passa nele.
4. **A rodada de testes da 25.6 no Windows ainda não chegou** (`logs\tests_last_run.txt`, `logs\travamento_qt.txt`, `logs\AutomationStudio.log`). Esta correção, como a 25.8, foi construída sobre uma base que o seu Windows ainda não confirmou. Pode esperar: a rodada com as duas frentes vale para tudo.

## 6. Decisões que tomei (você pode vetar qualquer uma)

| Decisão | Por quê | Se você discordar |
|---|---|---|
| Fazer isto agora, antes da 25.9 | A 25.9 só começa com a 25.8 aprovada; o achado é pequeno, independente e a tecla que não funciona é a que mais se nota | Descartar o ramo |
| Ramo nascido da 25.8 (`funcoes/ativacao-mapas`) e depois atualizado com a `main` | A mensagem usa o plano de atalhos da 25.8 para saber qual tecla de continuar está de fato ativa; com a 25.8 já na `main`, a junção traz só esta correção | Posso refazer sobre a `main` sem a mensagem personalizada |
| F9 e F10 entram no catálogo de funções (F47 e F48) | O catálogo é a lista do que o programa faz e agora a pausa existe de verdade; o teste que a exercita é o endereço, como em F15 e F16 | Tirar as duas linhas do catálogo e regenerar o documento |
| A barra de status diz como continuar, com a tecla configurada | Você não precisa lembrar qual é | Trocar o texto é uma linha em `controle_ui.py` |
| Tecla de continuar inativa: a pausa acontece e a mensagem aponta o botão de parar | Recusar a pausa seria pior (a tecla apertada "não faz nada"), e mandar apertar uma tecla morta seria enganoso | Recusar a pausa nesse caso é uma linha |
| As teclas seguradas **continuam seguradas** na pausa | É o que o motor faz hoje; soltar e reapertar ao retomar muda o comportamento do motor e é decisão sua | Posso implementar "soltar ao pausar e reapertar ao continuar" como opção |
| F9 só pausa e F10 só continua (F9 não alterna) | Em Configurações são dois atalhos separados, "Pausar" e "Continuar" | Alternar é uma linha |
| Pausa durante a espera por abrir um aplicativo vale a partir do ponto de controle seguinte | O motor já é assim (a espera só olha a parada); é o comportamento conservador que o `md/PLANO_FUNCOES.md` (seção 2, item 2) manda escolher enquanto o dono não decide: nada que já foi enviado é desfeito. Mexer nisso é outra função | Dizer o que a pausa deve fazer nessa espera |
| Mensagem de pausa por 8 s, de retomada por 3 s | A de pausa precisa dar tempo de ler e não pode sobrar se a automação for parada; o título mostra o estado o tempo todo | — |

## 7. Limitações conhecidas e observações

- Uma mensagem de evento já em trânsito (a linha "[0.20s] key_up A" que a barra mostra a cada tecla ou clique executado) pode, numa corrida rara, aparecer logo depois do aviso de pausa e cobri-lo. O título continua "● PAUSADO". Não mexi em `_on_engine_event` por isso.
- **Observação (confirmada pela leitura do código, não é desta correção):** em ⚙ Configurações > atalhos de controle, **apagar o campo de uma tecla não a desativa, devolve o padrão** (F9, F10 ou F12): o diálogo descarta campos vazios, `set_control_hotkeys` também, e `get_control_hotkeys` preenche com o padrão. Se for intencional, vale um texto no diálogo; se não, é um ponto à parte. Não mexi.
- O abort do Windows no Actions (seção 10) foi corrigido pela higiene do fim dos testes de janela e validado por 13 execuções no Windows, **não** pela identificação do objeto do Qt que o causava. Se um `Fatal Python error: Aborted` voltar, o roteiro está no fim da seção 10.
- O diálogo de atalhos de controle só tem os campos de pausar, continuar e parar tudo; as teclas de gravar (F8) e cancelar gravação (F11) não podem ser mudadas por ele. Também não mexi.

## 8. O processo de 8 etapas

| Etapa | Feito |
|---|---|
| 1. Especificação | `md/ESPEC_PAUSA_TECLAS.md` (atualizada ao que foi construído) |
| 2. Testes primeiro | os testes saíram da ficha (PAU-01 a PAU-06) antes do código e falharam pelo motivo certo (17 vermelhos), depois verdes |
| 3. Implementação isolada | `controle_ui.py` (sem Qt) e o retorno de `pause()`/`resume()` no motor |
| 4. Testes isolados e regressão | `engine/test_engine_control.py`, `unit/test_controle_execucao.py`; o motor já tinha os testes de pausa, todos continuam passando |
| 5. Integração no ramo de desenvolvimento, com a estável intacta | 3 pontos em `main_window.py` (import, criação, dois ramos), protegidos por `static/test_ligacao_controle.py`; ramo `funcoes/pausar-continuar-teclas` |
| 6. Regressão | suíte inteira contra a 25.8 e juntada com a `main` de 31/10 (seção 3); verificador de mutações (seção 4); Qt de verdade no GitHub Actions, Linux e Windows (seção 10) |
| 7. Aprovação | **sua**: use a conferência da seção 2 e me diga |
| 8. Registro de entrega | este arquivo |

## 9. O que preciso de você

1. **Integração:** juntar `funcoes/pausar-continuar-teclas` na `main`, pelo protocolo de `md/DELEGACAO.md`, seção 2. Eu mesmo publiquei o ramo, com a autorização do dono de 31/10/2026 para publicar nos meus ramos; a `main` continua sendo da integração. O commit `Infra:` (seção 10) mexe em `tests/conftest.py` e `tests/testsupport/gui_helpers.py`, que são de vocês: podem juntá-lo antes dos outros, ou vetá-lo e resolver o abort do Windows de outro jeito.
2. **Aval ou veto** das decisões da seção 6.
3. **A conferência da seção 2 e a da 25.8** (`md/ENTREGA_25_8.md`, seção 2), quando puder; e a rodada de testes no Windows, que pode esperar as duas frentes.

## 10. O Qt de verdade no GitHub Actions, e o abort do Windows que ele revelou

Em 01/11/2026 rodei este ramo pela primeira vez com o Qt de verdade, no GitHub Actions (workflow "Testes": Linux obrigatório e Windows informativo; Python 3.14.9, pytest 9.2.0, PySide6 6.12.0).

**O que passou.** No Linux, com o ramo como publicado (`5be8056`): 1713 passam, 11 pulados e 6 xfail no passo comum, mais os 44 testes da janela principal (um processo por teste): **44 de 44**. Entre esses 44 estão os 8 de `gui/test_controle_janela.py` (o disparo de F9 e F10 pela janela real, o título "● PAUSADO", a barra de status e as três formas de parar com a automação pausada) e os do `gui/test_funcoes_acessiveis.py`, que a integração exige verde.

**O que não passou.** No Windows, o mesmo ramo **abortou nas 2 vezes em que rodou**: `Fatal Python error: Aborted`, na montagem do primeiro teste de `gui/test_command_dialog.py`, aos 27% do passo "testes comuns", logo depois de `gui/test_ativacao_painel.py` (16 testes, todos passaram). O processo morre inteiro: os 73% restantes do passo comum e os 44 testes da janela principal **não chegam a rodar**, e o executor mostra só `[FALHOU]`, `[VAZIO ]` e o código de saída 3 (a recuperação do `executar_comum` cobre os relatórios do vigia de travamento, não a morte do processo). Mais duas execuções, uma com a listagem `-v` e outra com uma réplica exata do comando, abortaram no mesmo ponto: **4 abortos em 4**. A `main` passou nesse mesmo job em 31/10 (1679 passam), mas, pelo que segue, isso não prova que ela esteja imune.

**De quem era.** Não era do código da pausa, e sim de uma fragilidade que o ramo deslocou até onde o Windows a mostrou. O que os logs sustentam:

- **A bisseção** (ramos temporários, uma execução de cada): com `engine/test_engine_control.py` como na `main` (sem os 6 testes novos: 1706 testes) o Windows passou; sem só o teste de estresse entre threads (1711 testes) também passou. O teste de estresse liga o abort, mas ele não usa o Qt.
- **O gatilho é o coletor de lixo do Python.** O relatório do `faulthandler` mostra a thread principal em `Garbage-collecting`, no meio da montagem da fixture `gui`. Com o teste de estresse incluído, a suíte passou com a coleta automática desligada (`gc.disable()`), com uma coleta forçada ao fim de cada teste de janela e do motor, e com uma só coleta, no primeiro teste de `test_command_dialog.py`. E **só deslocar o ponto em que o coletor roda**, segurando N listas vazias vivas desde o início do processo (o que não toca no Qt nem no motor), liga e desliga o abort: **5 abortos em 8 execuções** (com o plugin de captura: sem deslocamento passou, com 64 e com 512 abortou; com o plugin completo: abortou com 0, 64 e 512 e passou com 200 e 1000). A leitura que cabe nesses fatos é que o teste de estresse (milhares de ciclos de pausa e retomada, que alocam muito) apenas desloca o coletor. Daí a consequência prática: **qualquer teste novo, de qualquer frente, pode trazer o abort de volta ou escondê-lo**.
- **A pilha nativa**, gravada no instante do abort por um tratador de `SIGABRT` instalado por `ctypes` (módulo, deslocamento e símbolo exportado mais próximo), vista do chamador para o chamado: `python314.dll` (o tratador de pendências do interpretador, `Py_HandlePending`, onde o Python 3.14 roda a coleta automática) → `shiboken6.abi3.dll` (2 quadros) → `QtWidgets.pyd` (1) → `Qt6Core.dll` (2) → `VCRUNTIME140.dll!purecall` → `ucrtbase.dll!abort`. `purecall` é uma **chamada de função virtual pura**, o que acontece quando um objeto C++ é destruído numa ordem que a classe não aceita. Ou seja: o coletor do Python estava liberando um objeto do Qt e o Qt abortou no meio da destruição.

**O que não sei.** Qual objeto, e deixado por qual teste: os módulos do Qt não trazem símbolos, então a pilha só mostra o módulo e o deslocamento. A hipótese que me parece mais provável é a de objetos do Qt que testes de janela anteriores deixaram para trás (o arquivo imediatamente anterior cria painéis `PainelAtivacao` em 16 testes) e que o coletor só destrói depois. **É hipótese**, e a correção abaixo não depende dela.

**A correção** (commit `Infra:`). A fixture `gui` passa a chamar `gui_helpers.encerrar_teste_de_janela()` no fim de todo teste de janela: esvazia a fila de eventos e **coleta o lixo na hora**, em vez de deixar o coletor automático destruir os objetos no meio de um teste posterior. É a mesma higiene que `descartar_janelas` já aplica à janela principal, agora para todo teste de janela. O vigia de travamento continua ligado durante a limpeza e é desligado mesmo se ela falhar. **Custo:** não consegui separá-lo da variação entre as máquinas do Actions. O passo comum do Linux levou 32 s antes da correção (1 execução) e 44 s, 46 s e 31 s com ela (3 execuções); no Windows levou de 58 a 72 s com ela, e sem ela não há comparação limpa, porque o passo abortava. O que a correção acrescenta é uma coleta de lixo por teste de janela.

**A evidência da correção.** No Windows, **13 de 13 sem abort**: o job original 4 vezes (a última, no commit publicado `f73765f`, que é o último antes deste texto) e 9 deslocamentos do coletor (0, 32, 64, 128, 200, 300, 512, 700 e 1000), entre eles o 0, o 64 e o 512, que abortavam sem a correção. No Linux, passou nas 3 vezes. Em `f73765f`: Linux 1716 + 44 de 44 e Windows 1715 + 44 de 44, código de saída 0 nos dois (seção 3).

**Testes permanentes.** Três em `unit/test_diagnostico_qt.py` (a limpeza esvazia a fila e depois coleta, com o aplicativo e as opções chegando à fila; coleta mesmo que esvaziar a fila falhe; a fixture `gui` a chama com o vigia ainda ligado e desliga o vigia num `finally`) e os defeitos `NET93` a `NET95`, mortos por eles (seção 4).

**O que a correção não é.** Não é a prova de que o abort não volta: é uma higiene que a suíte já aplicava à janela principal, validada pelos números acima. Se um `Fatal Python error: Aborted` com `Garbage-collecting` voltar no Windows, o roteiro que funcionou foi: (1) bisseção por ramo temporário, rodando o workflow com `workflow_dispatch` e `--ref` (o arquivo do workflow precisa existir na `main`; o log de um job só fica disponível quando a rodada inteira termina); (2) desligar ou forçar o coletor para confirmar que é ele; (3) deslocar o coletor segurando N listas vivas, para ter uma reprodução; (4) gravar a pilha nativa num tratador de `SIGABRT` instalado por `ctypes`; e (5) guardar a captura do pytest em arquivo, porque o arquivo temporário dele some com o processo. Os plugins de diagnóstico não entram na `main`: ficaram, só para consulta, no ramo `funcoes/diagnostico-abort-windows` (saído da `main`, com um `LEIA-ME.md` que diz o que cada um faz; **não é para juntar**, e pode ser apagado quando vocês não precisarem mais dele). Se quiserem a sonda de `SIGABRT` como ferramenta permanente de `tests/testsupport/`, eu a transformo num commit à parte. Também vale deixar o executor rodar o passo da janela principal quando o comum morre (hoje ele mostra `[VAZIO ]`); não mexi nisso.
