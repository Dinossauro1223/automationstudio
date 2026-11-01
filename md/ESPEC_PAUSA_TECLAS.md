# Especificação: pausar e continuar pelas teclas de controle (achado 2.11)

Etapa 1 do processo de 8 etapas. Não é uma versão do roadmap: é a correção de um defeito achado na 25.8, pedida como "ponto à parte". O registro de entrega está em `md/ENTREGA_PAUSA_TECLAS.md`.

## 1. Problema

Em ⚙ Configurações há os atalhos de controle **Pausar automação** (padrão F9) e **Continuar automação** (padrão F10), e os dois são registrados no gerenciador de atalhos. Mas a janela não fazia nada quando eles disparavam:

- `MainWindow._on_hotkey_triggered` só atendia `map:`, `control:emergency`, `record:toggle` e `record:cancel`. `control:pause` e `control:resume` não casavam com nenhum ramo e o disparo sumia.
- `ExecutionEngine.pause()` e `resume()` existem e funcionam (o motor pausa, congela o relógio da timeline e retoma do ponto; isso já tinha testes), mas **nada na interface os chamava**.

Confirmado pela leitura do código na 25.8 e guardado desde então como teste `xfail` estrito (`static/test_lacunas_de_ligacao.py`). Com esta correção o marcador saiu e o teste virou o guarda permanente `static/test_ligacao_controle.py`.

## 2. Comportamento

| Situação ao apertar | F9 (Pausar) | F10 (Continuar) |
|---|---|---|
| Automação **executando** | Pausa: título "● PAUSADO", nenhuma entrada nova a partir do próximo ponto de controle do motor, o tempo parado não conta na timeline. Barra de status: "Automação pausada. Aperte F10 para continuar." | Nada |
| Automação **pausada** | Nada | Volta a "● EXECUTANDO" e segue do ponto onde parou. Barra de status: "Automação retomada." |
| **Parada**, **gravando**, **parando** | Nada (sem mensagem e sem erro) | Nada (sem mensagem e sem erro) |

- A tecla citada na mensagem é a de **continuar que está ativa** (como o usuário a escreveu, por exemplo `CTRL+F10`), não sempre F10.
- **Tecla de continuar inativa** (inválida, ou repetida e perdida para um atalho de controle de mais prioridade: a 25.8 já avisa isso ao abrir o programa): a pausa acontece do mesmo jeito, mas a mensagem não manda apertar uma tecla que não faz nada. Diz: "Automação pausada. A tecla de continuar não está ativa; use o botão de parar para encerrar."
- **Corrida:** se a execução termina (ou é parada) no mesmo instante em que a tecla é apertada, nada acontece e **nenhum erro** aparece: vale o que aconteceu primeiro.
- **Com a automação pausada** continuam valendo: a tecla da própria automação (que a **para**), o botão ■ Parar e a parada de emergência (o motor já os trata e tem teste).
- **Não muda:** teclas e botões que já estavam apertados quando a pausa começou **continuam apertados** durante a pausa (o motor não os solta; é o comportamento de hoje, agora fixado por teste). Quem quiser soltá-los usa Parar.
- **Não muda:** o motor da timeline, o gravador, o formato dos mapas, a versão e o tema.
- **Mensagens:** a de pausa fica 8 s na barra (o suficiente para ler e finita, para não sobrar lá depois de a automação ser parada); a de retomada, 3 s. O título da janela é quem mostra o estado o tempo todo.

## 3. Como foi feito

- `ExecutionEngine.pause()` e `resume()` passam a **devolver `True` se mudaram o estado** (e `False` se não havia o que pausar ou retomar) e **não levantam** `InvalidStateTransition` numa corrida: a tecla vem da thread da janela e o motor corre em outra. Quem os chamava e ignorava o resultado continua funcionando.
- Módulo novo `automationstudio/controle_ui.py` (sem Qt): `ControladorDeExecucao` com `pausar()`, `retomar()` e `tecla_de_continuar()` (lê o plano de atalhos da ativação por mapa, que sabe qual tecla está de fato registrada). Mesmo desenho do controlador da ativação: a decisão fica fora da janela para poder ser testada sem Qt, e ele lê o motor e as configurações **na hora**, sempre pela janela.
- `MainWindow`: o `import`, `self.controle = ControladorDeExecucao(self)` em `__init__` (logo depois de `self.ativacao`) e os ramos `control:pause` e `control:resume` em `_on_hotkey_triggered`. Nada mais na janela mudou.
- Catálogo de funções do usuário (`tests/testsupport/funcoes_do_usuario.py`, da integração): **F47** "Pausar a automação que está executando" e **F48** "Continuar a automação pausada, do ponto onde parou", com o teste de janela que as exercita como endereço. `md/FUNCOES_DO_USUARIO.md` foi regenerado no mesmo commit.

## 4. Critérios objetivos

| ID | Critério | Nível | Onde |
|---|---|---|---|
| PAU-01 | F9 pausa a execução: estado PAUSADO, nenhuma entrada nova, mensagem com a tecla de continuar (ou o aviso de que ela não está ativa) | L + Q | `unit/test_controle_execucao.py`; `gui/test_controle_janela.py` |
| PAU-02 | F10 retoma do ponto e a execução termina com todos os eventos, sem repetir nem pular | L + Q | idem; `engine/test_engine_control.py` |
| PAU-03 | Fora de execução (parado, gravando, parando) as duas teclas não fazem nada, sem mensagem e sem erro; F10 sem pausa não troca o estado | L + Q | `unit/test_controle_execucao.py`; `engine/test_engine_control.py`; `gui/test_controle_janela.py` |
| PAU-04 | Corrida com o fim ou a parada da execução: sem erro e sem soltar nem prender a thread; pausas e retomadas vindas de outra thread, milhares por execução, não perdem nem repetem entrada | L | `engine/test_engine_control.py` (inclusive o teste de estresse entre threads); `unit/test_controle_execucao.py` |
| PAU-05 | **Toda ação de controle registrada tem ramo** em `_on_hotkey_triggered` (teria pego o achado 2.11); cada tecla chama o seu método; o controlador existe antes de os atalhos serem registrados | L | `static/test_ligacao_controle.py` |
| PAU-06 | Pausada, parar e emergência continuam funcionando, e a tecla que ficou apertada na pausa é solta no fim: o motor (já coberto) e, na janela, as três formas de parar com a automação pausada (tecla de parar tudo, botão ■ Parar, tecla da própria automação), com o botão ■ Parar ativo e o ▶ Executar desativado enquanto pausada | L + Q | `engine/test_engine_control.py`; `gui/test_controle_janela.py` |

L = lógica (roda aqui); Q = janela com o Qt de verdade (só na sua máquina ou no CI).

## 5. O que fica de fora

- Um botão "⏸ Pausar" na barra: é da frente visual.
- Soltar as teclas seguradas ao pausar e apertá-las de novo ao retomar: muda o que o motor faz e pede decisão sua.
- Pausar **a gravação** (o gravador tem `pause()` e `resume()`, mas nenhuma tela os usa; os atalhos de controle são "Pausar/Continuar **automação**").
- Pausa durante a espera por abrir um aplicativo: a espera de prontidão (`WindowsProcessReadiness`) só olha o pedido de parada, então a pausa vale **a partir do ponto de controle seguinte**; o motor já é assim.
- Uma mensagem de evento já em trânsito (a linha "[0.20s] key_up A" que a barra mostra a cada tecla ou clique executado) pode, numa corrida rara, aparecer logo depois do aviso de pausa e cobri-lo; o título continua mostrando "● PAUSADO". Não mexi em `_on_engine_event` para isso.
