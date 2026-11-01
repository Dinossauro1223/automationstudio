# Entrega: pausar e continuar pelas teclas F9 e F10 (achado 2.11)

Registro de entrega (etapa 8 do processo). Não é uma versão do roadmap: é a correção do achado 2.11, o "ponto à parte" que a 25.8 deixou aberto. Como a 25.9 só começa com a 25.8 aprovada, e você me deixou decidir o que estiver pendente (dizendo o que escolhi e por quê), fiz esta correção enquanto isso; o `md/PLANO_FUNCOES.md` (seção 2) a trata como correção de defeito da versão em aberto, a **25.8**. Especificação: `md/ESPEC_PAUSA_TECLAS.md`.

**Onde está:** ramo `funcoes/pausar-continuar-teclas`, publicado no GitHub. Nasceu de `funcoes/ativacao-mapas` e foi **atualizado com a `main` de 31/10/2026** (`b78c7da`, onde a conta de integração já juntou a 25.8 e o tema novo), como pede `md/DELEGACAO.md`. A `main`, o ramo `visual/novo-tema` e a versão (`APP_VERSION = "25.6"`) **não foram tocados**. Nenhum formato de arquivo mudou. A última linha dos commits diz `Versão: 25.8 (em aberto)`.

**Para a integração:** a junção na `main` traz **só os commits desta correção** (a 25.8 já está lá). Tudo rodou nos dublês, sem o Qt de verdade; o que precisa do ambiente de vocês está na seção 5.

## 1. O que muda para quem usa

- **F9 pausa a automação que está executando.** O título mostra "● PAUSADO", nenhuma tecla ou clique novo sai, e o tempo parado não conta na timeline. A barra de status diz: "Automação pausada. Aperte F10 para continuar." (a tecla de continuar que você configurou).
- **F10 continua do ponto onde parou**, sem repetir nem pular nada. A barra diz "Automação retomada.".
- **Sem automação executando** (parado, gravando, parando), as duas teclas não fazem nada, sem mensagem e sem erro.
- **Se a tecla de continuar não estiver ativa** (inválida, ou igual à de pausar ou à de parar tudo, o que a 25.8 já avisa ao abrir), a pausa acontece e a mensagem diz isso: "A tecla de continuar não está ativa; use o botão de parar para encerrar.".
- **O que não muda:** teclas e botões que já estavam apertados continuam apertados durante a pausa (o motor nunca os soltou na pausa; agora há um teste que fixa isso). Parar, a tecla da própria automação e a parada de emergência continuam valendo com a automação pausada.

## 2. Conferência rápida no Windows (uns 3 minutos)

Os testes de janela real foram escritos sem poder rodar o Qt; esta conferência à mão cobre o essencial.

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

- **Testes novos: 44** (36 rodam aqui; 8 só rodam com o Qt de verdade): `engine/test_engine_control.py` (+6, um deles o de estresse: milhares de pausas e retomadas vindas de outra thread enquanto o motor executa, sem perder nem repetir entrada nem travar), `unit/test_controle_execucao.py` (19), `static/test_ligacao_controle.py` (11) e `gui/test_controle_janela.py` (8, janela real: o disparo e a mensagem, e as três formas de parar com a automação pausada). O `xfail` do achado 2.11 saiu: o teste `static/test_lacunas_de_ligacao.py` virou o guarda permanente `static/test_ligacao_controle.py` (os 3 controles do verificador foram junto). Por isso o saldo, na coluna do meio, é +33 passando e -1 `xfail`.
- **As 3 falhas das colunas anteriores** não eram desta correção: dois testes de fim de linha dos `.bat` e a validação do catálogo de defeitos (NET10 e NET83, que plantam defeito em CRLF), por o repositório guardar os `.bat` com LF. **Sumiram na árvore juntada:** a integração criou o `.gitattributes` (`*.bat text eol=crlf`), como eu tinha sugerido na entrega da 25.8. (Antes da junção eu já tinha conferido com os `.bat` convertidos para CRLF à mão: 1666 passam, 0 falham.)
- **Catálogo de funções do usuário** (`md/FUNCOES_DO_USUARIO.md`, da integração): ganhou **F47** "Pausar a automação que está executando" e **F48** "Continuar a automação pausada, do ponto onde parou". Como são funções de tecla, o endereço de cada uma é o teste de janela que a exercita. A linha do catálogo e o documento gerado mudaram no mesmo commit, como manda o `md/PLANO_VISUAL.md`. Se outro ramo tiver usado os mesmos números, é só renumerar na junção.
- **Cobertura do `coverage.py`:** não medida (sem `coverage` no ambiente de desenvolvimento). A catraca ganhou o grupo `controle` para o seu baseline.

## 4. Verificador de mutações (a prova de que os testes pegam defeito)

- **25 de 25 mortos** nos defeitos desta correção: 23 novos (`PAU01` a `PAU23`: o motor devolvendo o resultado errado, não tratando a corrida, soltando as teclas na pausa; o controlador mostrando mensagem sem ter pausado, citando a tecla errada ou uma tecla inativa; a janela com o ramo trocado, sem ramo ou criando o controlador tarde demais), o `MOT32` (mesmo defeito de antes, trecho atualizado) e o `EST13` (conferido de novo, agora pelo teste novo).
- **O verificador achou um buraco nos meus testes e eu o fechei:** na primeira rodada, o defeito `PAU08` ("pausar solta as teclas apertadas") só foi pego por um teste que não era o que o protege. O meu teste de "o que não muda" pausava no instante do envio da própria tecla, quando o motor ainda não a tinha registrado como apertada, então não teria visto nada. Mudei o ponto da pausa (depois do envio de uma segunda tecla, com a primeira já registrada) e o `PAU08` passou a ser pego pelo teste certo.
- **Rodada completa do catálogo (378 defeitos), numa cópia da árvore commitada com os `.bat` em CRLF (como ficam no seu Windows): 378 de 378 mortos, 0 sobreviventes, 0 inválidos.** O ambiente interrompeu a rodada e ela foi retomada com `--retomar`, que só aceita continuar sobre o mesmo código e os mesmos testes: 75 resultados vieram do progresso gravado e o trecho final, de 303 defeitos, levou 50,2 min (a rodada inteira costuma levar perto de uma hora).
- **O que a cópia da rodada não tem do commit:** o teste de estresse entre threads (`engine/test_engine_control.py`, o último que acrescentei) e a versão final dos testes de janela real (`gui/test_controle_janela.py`, que não rodam aqui). Acrescentar teste só pode pegar mais defeitos, nunca menos, então os 378 valem para o commit. A contagem de referência dessa rodada (1664 passam com a interface, 1437 com a lógica) bate com a do commit (1663 e 1436) depois de descontar esse teste, somar os 2 de fim de linha dos `.bat` (que passam em CRLF) e tirar o de validação do catálogo (que a própria rodada pula).

- **Depois da junção com a `main` de 31/10:** o verificador confirma que os 378 defeitos ainda se aplicam ao código juntado (`--validar`), e os 25 desta correção foram rodados de novo na árvore juntada, já com os testes novos de janela e o catálogo de funções: **25 de 25 mortos**, em 4,7 min. A rodada completa (uma hora de máquina) **não foi refeita** depois da junção.

## 5. O que **não** foi verificado

1. **Qt de verdade.** Os 8 testes de `gui/test_controle_janela.py` (o disparo da tecla pela janela real, o título "● PAUSADO", a barra de status e as três formas de parar com a automação pausada: tecla de parar tudo, botão ■ Parar e tecla da própria automação) foram escritos sem poder rodar o Qt e **foram pulados aqui**. Só se confirmam no ambiente da integração (Linux, display virtual), no GitHub Actions (Actions > Testes > Run workflow, escolhendo este ramo) ou na sua máquina. O `tests/gui/test_funcoes_acessiveis.py`, que a integração exige verde, também precisa do Qt de verdade: esta correção não cria nem move nenhum controle e só acrescentou as funções F47 e F48 (endereço de teste), que a parte sem Qt do catálogo (`unit/test_funcoes_do_usuario_catalogo.py`) já confere.
2. **Windows de verdade:** o atalho global F9/F10 pelo `pynput` e a pausa com outro programa em foco nunca rodaram aqui. A lógica é testada com um gerenciador de atalhos e um monitor falsos e com o motor de verdade (relógio virtual).
3. **Python 3.14:** o ambiente tem o 3.13. O módulo novo não usa nada específico do 3.14 e passa nas checagens estáticas.
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
- O diálogo de atalhos de controle só tem os campos de pausar, continuar e parar tudo; as teclas de gravar (F8) e cancelar gravação (F11) não podem ser mudadas por ele. Também não mexi.

## 8. O processo de 8 etapas

| Etapa | Feito |
|---|---|
| 1. Especificação | `md/ESPEC_PAUSA_TECLAS.md` (atualizada ao que foi construído) |
| 2. Testes primeiro | os testes saíram da ficha (PAU-01 a PAU-06) antes do código e falharam pelo motivo certo (17 vermelhos), depois verdes |
| 3. Implementação isolada | `controle_ui.py` (sem Qt) e o retorno de `pause()`/`resume()` no motor |
| 4. Testes isolados e regressão | `engine/test_engine_control.py`, `unit/test_controle_execucao.py`; o motor já tinha os testes de pausa, todos continuam passando |
| 5. Integração no ramo de desenvolvimento, com a estável intacta | 3 pontos em `main_window.py` (import, criação, dois ramos), protegidos por `static/test_ligacao_controle.py`; ramo `funcoes/pausar-continuar-teclas` |
| 6. Regressão | suíte inteira contra a 25.8 e juntada com a `main` de 31/10 (seção 3); verificador de mutações (seção 4) |
| 7. Aprovação | **sua**: use a conferência da seção 2 e me diga |
| 8. Registro de entrega | este arquivo |

## 9. O que preciso de você

1. **Integração:** juntar `funcoes/pausar-continuar-teclas` na `main`, pelo protocolo de `md/DELEGACAO.md`, seção 2. Eu mesmo publiquei o ramo, com a autorização do dono de 31/10/2026 para publicar nos meus ramos; a `main` continua sendo da integração.
2. **Aval ou veto** das decisões da seção 6.
3. **A conferência da seção 2 e a da 25.8** (`md/ENTREGA_25_8.md`, seção 2), quando puder; e a rodada de testes no Windows, que pode esperar as duas frentes.
