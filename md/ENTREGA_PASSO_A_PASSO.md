# Entrega: executar passo a passo (função F52)

Registro de entrega de uma função da frente de funções (item 1 da fase 1 do plano de funções, "Desativar passo, executar daqui, pausa e passo a passo": aqui a quarta parte, o **passo a passo**. As outras são a F49 desativar comandos, a F50 executar a partir daqui e a pausa, que está no ramo `funcoes/pausar-continuar-teclas`).

**Onde está:** ramo `funcoes/passo-a-passo`, a partir da `main` atualizada (b78c7da). A `main`, a versão (`APP_VERSION`) e o changelog **não foram tocados**; a entrega é da versão 25.9 (nova), como manda o plano de versões. Nenhum formato de arquivo mudou. O ramo **não depende** de nenhum outro: dá para juntar em qualquer ordem (ensaiado na seção 4).

## 1. O que muda para quem usa

- **O problema que isto resolve:** para testar ou consertar uma automação, hoje só dá para rodá-la inteira ou testar uma seleção de uma vez. Quando algo dá errado no meio, fica difícil ver qual comando fez o quê. Com o passo a passo a automação roda **um comando por vez**, e você manda o próximo quando quiser.
- **Como começar:** no editor, botão **"Mais…"** e **"⏭ Executar passo a passo"** (sem nenhuma linha escolhida começa pelo primeiro comando; com linhas escolhidas começa pela primeira delas), ou botão direito num comando e **"⏭ Executar passo a passo a partir daqui"**.
- Abre uma **janelinha** sempre por cima, no canto de baixo à direita da tela principal (acima da barra de tarefas, longe dos botões de fechar e minimizar do programa de destino). Ela diz em que passo a execução está parada, por exemplo **"Passo 2 de 5: Digitar "olá""**, e tem três botões: **Próximo passo**, **Continuar sem parar** e **Parar**.
- **A janelinha não aceita o foco.** Clicar nos botões não tira o foco do programa onde a automação trabalha. Sem isso, as teclas do próximo comando iriam para o próprio Automation Studio e poderiam mudar a sua automação.
- O passo a passo **começa parado, antes do primeiro comando**: dá tempo de trazer para a frente o programa onde a automação vai trabalhar. Nada é enviado até o primeiro "Próximo passo".
- **Um passo é um comando.** Apertar e soltar uma tecla é um passo só, e um percurso de mouse gravado também. Comandos desativados são pulados e não contam como passo.
- **A espera planejada entre os comandos não é cumprida:** quem escolhe a hora do próximo passo é você. As esperas que fazem parte do **próprio comando continuam valendo** e acontecem quando o passo roda: o comando "Esperar", as condições de um comando (atraso, imagem, aplicativo pronto) e o aguardo do aplicativo que acabou de abrir. Quando o passo é uma espera, a janelinha diz qual, por exemplo "Passo 3 de 5: Esperar 2 s".
- **Continuar sem parar** roda o resto de uma vez, no tempo de sempre (com as esperas planejadas dali em diante). **Parar** encerra a execução, o mesmo que o **■ Parar** da barra, e solta a tecla que estiver segurada. Fechar a janelinha pelo **X** também para a execução, para ela nunca ficar parada sem ninguém para liberá-la.
- Ao terminar, ou ao parar por qualquer meio (botão, tecla, erro), a janelinha some e a barra de status mostra **"Passo a passo encerrado."** por 5 segundos.
- **É uma volta só:** a repetição da automação e o encadeamento de outra automação não valem no passo a passo.
- **A sua automação não muda.** O passo a passo roda uma cópia, do mesmo jeito que o "Testar selecionados" já faz. A cópia se chama `__passo__ ` mais o nome da sua automação e não entra na sua lista de automações.
- Se já há uma automação rodando ou uma gravação em andamento, o passo a passo avisa e não começa ("Pare a automação em execução antes de usar o passo a passo." ou "Termine ou cancele a gravação antes de usar o passo a passo."). Sem nenhum comando ativo, avisa "Não há nenhum comando ativo para executar passo a passo."
- Quem não usa o passo a passo **não nota nada**: a execução normal (▶ Executar) é a mesma de antes, e há teste para isso.

## 2. Decisões que você pode querer mudar

1. **Um passo é um comando, não um evento do motor.** Apertar e soltar uma tecla é um passo; o "soltar" acontece no tempo planejado, no caminho até o próximo passo. Se quiser parar entre apertar e soltar, a automação precisa ter dois comandos (segurar a tecla e soltar a tecla), que já existem.
2. **A espera planejada entre comandos é pulada.** Eu entendi que, no passo a passo, a hora do próximo passo é sua, então esperar 5 segundos por ele seria só atrapalhar. Se você preferir o contrário, é uma mudança pequena no motor (o acerto do relógio logo depois da parada).
3. **Uma volta só.** A repetição e o encadeamento da automação ficam de fora, senão o passo a passo nunca terminaria numa automação que repete sem parar.
4. **Começa parado.** O primeiro comando só roda no primeiro "Próximo passo". Assim dá tempo de pôr o programa de destino na frente.
5. **Sem tecla de atalho própria.** A janelinha não aceita foco, então um atalho teria que ser uma tecla global nova, e os atalhos globais estão sendo mexidos por outros ramos (`pausar-continuar-teclas` e `teclado-atalhos`), por isso deixei isso para depois. Veja a conversa com a pausa na seção 4: com o ramo da pausa junto, a tecla de continuar (F10) já funciona como "Próximo passo" quando a execução está parada num passo.
6. **Sem "voltar um passo" nem "repetir o passo".** O motor não desfaz o que já foi enviado; seria outra função.
7. **O botão Parar e o X da janelinha encerram tudo**, não só o passo.
8. **Não começa com uma execução ou uma gravação em andamento.** Avisa e não faz nada.
9. **Os textos dos passos** usam palavras simples ("Apertar e soltar a tecla A", "Clicar com o botão esquerdo do mouse", "Mover o mouse para (100, 200)"). O texto digitado aparece cortado em 40 caracteres, com "…". A descrição que você escreveu no comando vai entre parênteses no fim.
10. **Aparência.** Não pus cor, tamanho nem ícone no código da função (regra do `md/DIVISAO_DE_TRABALHO.md`). A janelinha tem o nome de objeto `PainelPassoAPasso` e o texto do passo `PassoRotulo`, para a frente visual poder estilizar.
11. **O motor ganhou um gancho.** `ExecutionEngine.passo_a_passo` é `None` na execução normal e então nada muda. O arquivo `input_system.py` é da frente de funções (`md/DIVISAO_DE_TRABALHO.md`, seção 2), por isso mexi nele.

## 3. O que foi mexido

| Arquivo | Mudança |
|---|---|
| `automationstudio/input_system.py` | **41 linhas, só em `ExecutionEngine`.** O atributo `passo_a_passo` (começa `None`); 4 linhas em `_play_timeline`, antes de esperar o primeiro evento de cada comando (pergunta ao gancho e, se for para parar, usa a pausa que já existe e depois acerta o relógio para o comando sair na hora); e dois métodos: `_pede_passo` (consulta o gancho; se ele der erro, o gancho se desliga, o erro vai para o log e a execução segue) e `_parar_para_o_passo` (pausa de um jeito que um "próximo" que chegue no mesmo instante não se perde: apaga o sinal de pausa antes de mudar o estado). |
| `automationstudio/passo_a_passo.py` (novo) | Sem Qt. Os textos dos passos, a regra de "a partir daqui" (a mesma da F50: do primeiro escolhido até o fim, sem os desativados), a cópia da automação, `PassoAPasso` (o que o motor consulta e a janelinha mostra) e `ControleDePassos` (o que os três botões chamam). |
| `automationstudio/passo_a_passo_ui.py` (novo) | A parte com Qt: a janelinha `PainelPassoAPasso` e o `ControladorPassoAPasso`, que a liga ao pedido do editor e ao aviso de mudança de estado do motor. |
| `automationstudio/command_editor.py` | **7 linhas, só em `CommandTableWidget`:** o sinal `passo_a_passo_requested` e uma entrada em cada menu (botão direito, no fim, e "Mais…", depois de "Pré-visualizar automação"). |
| `automationstudio/main_window.py` | **3 linhas:** a importação (depois de `from .overlays import *`) e, no fim de `MainWindow.__init__`, depois de `self._connect_capture_bridge()`, a criação do controlador e a chamada de `ligar`. |
| `tests/testsupport/funcoes_do_usuario.py` e `md/FUNCOES_DO_USUARIO.md` | Função **F52** no catálogo (o documento foi regenerado). Pus a linha entre a F10 e a F11, no grupo Execução. |
| `tests/testsupport/catraca_cobertura.py` | Uma linha: o grupo `passo_a_passo` (os dois módulos novos). A catraca exige que todo módulo do pacote pertença a um grupo. |
| Testes novos | `tests/engine/test_passo_a_passo_motor.py`, `tests/unit/test_passo_a_passo.py`, `tests/unit/test_passo_a_passo_ui.py`, `tests/static/test_ligacao_passo_a_passo.py`, `tests/gui/test_passo_a_passo_janela.py` (janela de verdade, pulado aqui) e o apoio `tests/testsupport/fakes_passo_a_passo.py` (motor, sinais, tabela e janelinha de mentira). |

Escolhi esses pontos de `main_window.py`, `command_editor.py` e dos dois arquivos de catálogo para **não ficarem colados** nas linhas que os outros ramos mexem. Não toquei em `core.py`, no tema, em `APP_VERSION` nem no changelog.

## 4. Testes

| | Base (`main`) | Esta função |
|---|---|---|
| Dublê de widgets (`rodar_testes.py completo`) | 1651 passam, 77 pulados, 6 xfail | **1787** passam, 86 pulados, 6 xfail |
| Dublê de lógica (`rodar_testes.py rapido`) | 1424 passam, 304 pulados, 6 xfail | **1560** passam, 313 pulados, 6 xfail |

- **136 testes novos rodam aqui** (30 no motor, 64 na lógica, 28 no controlador e na janelinha, 14 estáticos). Há mais **9 testes de janela de verdade** (`tests/gui/test_passo_a_passo_janela.py`) que ficam pulados nesta sessão: são os 9 pulados a mais.
- **Motor de verdade, teclado e mouse de mentira, relógio virtual.** Os testes do motor conferem: começa parado sem enviar nada; cada "próximo" executa um comando inteiro e para antes do seguinte; a espera planejada entre comandos não é cumprida e a de dentro do comando é; o comando "Esperar" e as condições valem quando o passo roda; a velocidade da automação vale dentro do comando; desativados não são passos; começar do meio; uma volta só mesmo com repetição infinita e automação encadeada; parar no meio solta a tecla segurada e volta ao repouso; **"continuar" ou "próximo" que chegam no mesmo instante em que o motor para não travam nem se perdem** (a corrida entre a janela e o motor); e um defeito no gancho desliga o passo a passo e a execução segue.
- **A janelinha e o controlador** foram testados com uma janela de mentira e, em 4 testes, **de ponta a ponta com o motor de verdade**: andar um comando por vez até o fim, parar no meio, continuar sem parar e começar do meio.
- **Defeitos plantados à mão (139),** um de cada vez: **todos foram pegos.** Eram 18 no motor, 64 na lógica, 20 na janelinha, 25 no controlador, 7 no editor e 5 na ligação da janela principal. A primeira rodada deixou escapar 18; reforcei os testes e tirei do código uma linha que não fazia nada. A segunda deixou escapar 2 (o texto e o botão habilitado da janelinha); reforcei com conferências estáticas. A terceira pegou todos. Depois do ajuste de junção descrito abaixo, plantei mais um defeito e rodei tudo de novo: todos pegos. Foi uma conferência minha, com um script fora do repositório; não entrou no catálogo de mutações do projeto.
- **Junção real com os 11 ramos que ainda não entraram na `main`** (`aviso-administrador`, `desativar-comandos`, `diagnostico-abort-windows`, `executar-a-partir-daqui`, `pausar-continuar-teclas`, `plano-25-7`, `robustez-modelo`, `robustez-motor`, `teclado-atalhos`, `teclado-edicao` e `validacao-lacunas`): **nenhum conflito**. Para provar que a conferência enxerga conflito, um controle (um commit de teste que mexe numa linha vizinha da minha) deu conflito, como devia. Os ramos `ativacao-mapas` e `visual/novo-tema` já estão na `main`.
- **A suíte inteira, em cada uma dessas 11 junções** (cópia descartável, nos dois modos), **passou sem nenhuma falha**. Quantos testes passaram em cada uma (os pulados e os xfail ficam como cada ramo já tinha):

| Junção (esta função mais o ramo) | Dublê de widgets | Dublê de lógica |
|---|---|---|
| `aviso-administrador` (F51) | 1905 passam | 1678 passam |
| `desativar-comandos` (F49) | 1823 passam | 1596 passam |
| `diagnostico-abort-windows` | 1787 passam | 1560 passam |
| `executar-a-partir-daqui` (F50) | 1807 passam | 1580 passam |
| `pausar-continuar-teclas` | 1823 passam | 1596 passam |
| `plano-25-7` | 1787 passam | 1560 passam |
| `robustez-modelo` | 2105 passam | 1846 passam |
| `robustez-motor` | 2125 passam | 1866 passam |
| `teclado-atalhos` | 2520 passam | 2247 passam |
| `teclado-edicao` | 2854 passam | 2581 passam |
| `validacao-lacunas` | 1912 passam | 1684 passam |

- **Uma colisão achada e resolvida nessas junções.** Na primeira rodada, a junção com os 6 ramos que trazem o catálogo de defeitos da pausa falhou num teste (`test_todo_defeito_do_catalogo_ainda_se_aplica_ao_codigo_atual`): o defeito `PAU03` procura em `input_system.py` duas linhas seguidas (`self.state.transition_to(State.PAUSED)` e `except core.InvalidStateTransition:`) e, depois da junção, encontrava o mesmo par duas vezes, uma no `pause()` e outra no meu `_parar_para_o_passo`. Não era erro de funcionamento. Movi o `return True` do meu método para dentro do `try`, o que separa as duas linhas, e a falha sumiu nas 6 junções. A falha só aparecia na junção: a F52 sozinha passava, e os três ramos que rodei sozinhos para comparar (`pausar-continuar-teclas`, `robustez-modelo` e `robustez-motor`) também passavam.
- **Conversa com a pausa (ramo `pausar-continuar-teclas`).** Numa junção descartável, com o motor de verdade e relógio virtual, conferi 4 situações, e as 4 deram o resultado esperado: (1) com a execução parada num passo, a tecla de continuar (F10) funciona como "Próximo passo"; (2) a tecla de pausar (F9) com a execução já parada num passo não faz nada; (3) F9 no meio de um passo pausa, a janelinha mostra o mesmo passo com o "Próximo passo" liberado, e o "Próximo passo" continua esse passo; (4) "Continuar sem parar" funciona. Esse experimento **não está no repositório** (era descartável).

## 5. O que NÃO foi conferido

- **Nada com o Windows de verdade nem com o Qt de verdade.** Esta sessão não tem Windows nem PySide6. Os testes rodaram com o dublê de widgets, com o de lógica e com relógio virtual. Os 9 testes de `tests/gui` não rodaram.
- **O que só o Windows de verdade mostra:**
  - se a janelinha **não rouba o foco** do programa de destino ao clicar nos botões (é a parte mais importante). Usei o que o Qt manda para isso (janela de ferramenta, sempre por cima, que não aceita foco, não ativa ao abrir, botões sem foco), mas só o Windows confirma;
  - se ela fica **por cima** de programas em tela cheia e de janelas de administrador (o Windows pode esconder);
  - o **canto de baixo à direita**: se a janelinha aparece inteira acima da barra de tarefas, com mais de um monitor e com escala de 125% ou 150%. Não vi nenhum desses casos;
  - se ela **não aparece na barra de tarefas** do Windows;
  - se o **teclado e o mouse de verdade** chegam ao programa de destino em cada passo;
  - se o aviso de mudança de estado do motor chega à janelinha na thread certa (é o mesmo padrão do rótulo de estado que já existe, mas não vi no Qt de verdade).
- **A conversa com a pausa** foi conferida só pelo experimento descartável de 4 situações da seção 4, que não está no repositório. Quando os dois ramos entrarem, vale transformar essas 4 situações em testes (posso fazer).
- **Não rodei o passo a passo com uma automação cujas esperas foram editadas pelo ramo `teclado-edicao`** (`set_gap_before`). Pelo que o código desse ramo diz, a espera editada fica guardada nos inícios dos comandos, que é o que o passo a passo usa, e a suíte inteira passa na junção, mas isso é leitura minha, não um teste.
- A **tecla de parada de emergência** com a execução parada num passo: o caminho é o mesmo `stop()` do botão Parar, que está testado, mas a tecla de verdade não foi apertada.
- Eu não disparei o GitHub Actions. Dá para rodar o fluxo **Testes** à mão no ramo (aba Actions, "Testes", "Run workflow", escolhendo `funcoes/passo-a-passo`), o que daria o Qt de verdade no Linux.

## 6. Conferência rápida no Windows (de 3 a 6 minutos)

| # | Faça | Deve acontecer |
|---|---|---|
| 1 | Abra o Automation Studio (`Iniciar.bat`) e o Bloco de Notas, lado a lado. Monte uma automação com 3 comandos: digitar "a", digitar "b" e digitar "c", com uns 2 segundos entre eles. | Nada de diferente ainda. |
| 2 | Clique no botão **"Mais…"** e em **"⏭ Executar passo a passo"**. | Aparece uma janelinha pequena no **canto de baixo à direita** da tela, acima da barra de tarefas, com o texto **"Passo 1 de 3: Digitar "a""** e os botões "Próximo passo", "Continuar sem parar" e "Parar". Nada foi digitado ainda. |
| 3 | Clique dentro do Bloco de Notas, para ele ficar na frente e com o cursor piscando. Depois clique em **"Próximo passo"** na janelinha. | A letra **a** aparece no Bloco de Notas, e o Bloco de Notas **continua com o foco** (o cursor continua nele e o título da janela dele continua em destaque). A janelinha passa a dizer "Passo 2 de 3". |
| 4 | Espere uns 10 segundos e clique em "Próximo passo" de novo. | A letra **b** aparece **na hora**, sem esperar os 2 segundos planejados. |
| 5 | Clique em **"Continuar sem parar"** (no passo 3). | A letra **c** aparece, a janelinha **some** e a barra de status diz "Passo a passo encerrado." |
| 6 | Repita o passo 2, clique em "Próximo passo" uma vez (digita o **a**) e depois em **"Parar"**. | A execução termina, só o **a** foi digitado, e a janelinha some. |
| 7 | Repita o passo 2 e feche a janelinha pelo **X**. | A execução **para** (nada mais é digitado) e o programa volta ao normal. |
| 8 | Clique com o botão direito no **segundo** comando da lista e em **"⏭ Executar passo a passo a partir daqui"**. | A janelinha diz **"Passo 1 de 2: Digitar "b""**: o passo a passo começou naquele comando. |
| 9 | Ponha uma espera de uns 10 segundos no começo da automação, aperte **▶ Executar** e, enquanto ela espera, tente o passo a passo pelo "Mais…". | O programa avisa "Pare a automação em execução antes de usar o passo a passo." e não abre a janelinha. |
| 10 | Olhe a lista de automações. | **Nenhuma** automação nova (a cópia `__passo__ ...` não aparece) e a sua automação continua igual. |
| 11 | Se tiver dois monitores ou a escala do Windows em 125% ou 150%, repita o passo 2. | A janelinha aparece **inteira**, no canto de baixo à direita do monitor principal. |

Se algo sair diferente, o mais útil é me mandar o `logs\AutomationStudio.log` (as linhas que começam com `PASSO A PASSO`) e a descrição do que você viu.
