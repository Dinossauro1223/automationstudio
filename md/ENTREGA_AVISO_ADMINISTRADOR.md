# Entrega: aviso de janela de administrador (função F51)

Registro de entrega de uma função da frente de funções (item 1 da fase 1 do plano de funções, "Aviso de elevação e regras de segurança": aqui só a primeira metade, o **aviso**).

**Onde está:** ramo `funcoes/aviso-administrador`, a partir da `main` atualizada. A `main`, a versão (`APP_VERSION`) e o changelog **não foram tocados**; a entrega é da versão 25.9 (nova), como manda o plano de versões. Nenhum formato de arquivo mudou. O ramo **não depende** de nenhum outro: dá para juntar em qualquer ordem.

## 1. O que muda para quem usa

- **O problema que isto resolve:** quando a janela que recebe a automação foi aberta **como administrador** e o Automation Studio não, o Windows **bloqueia** o teclado e o mouse simulados nessa janela e **não mostra erro nenhum**. A automação parece rodar, mas nada acontece na janela. Até agora o programa não avisava.
- **Agora, durante a execução,** o programa olha qual janela está na frente (para o teclado) e qual está sob o mouse (para o mouse). Se uma delas for de administrador e o Automation Studio não, aparece à direita da barra de status um aviso, por exemplo: **"⚠ Janela de administrador (Taskmgr.exe): o Windows bloqueia a entrada"**.
- Passando o mouse sobre o aviso, a dica explica o que está acontecendo e como resolver: fechar o Automation Studio e abrir de novo pelo arquivo **`Iniciar como administrador.bat`** (que já existe na pasta do programa). A dica também avisa que as teclas de atalho, inclusive a de parar, **podem não funcionar** com essa janela na frente.
- O botão do programa na barra de tarefas do Windows **pisca**, sem tirar o foco da janela onde a automação está trabalhando. Serve para quem está com outro programa na frente.
- A mesma explicação vai para o log (`logs\AutomationStudio.log`, linha que começa com `AVISO ELEVACAO`).
- Quando o Windows **nega a leitura** do nível da janela (acontece com janelas de administrador), o aviso é mais fraco: **"⚠ Pode ser janela de administrador (...): a entrada pode ser bloqueada"**.
- Se o Automation Studio **já está aberto como administrador**, nunca aparece aviso: nesse caso a entrada passa em qualquer janela.
- **A automação não muda em nada.** O aviso nunca bloqueia nem interrompe a execução.
- O aviso fica na tela até começar a **próxima execução**. Continuar depois de uma pausa não conta como execução nova. Cada programa avisa **uma vez por execução**.
- Fora do Windows o recurso não existe: o programa não faz nada (isso só serve para os testes rodarem em outro sistema).

## 2. Decisões que você pode querer mudar

1. **Só avisa.** Não impede a execução, não pergunta nada, não para a automação. Parar ao achar a janela de administrador seria uma mudança no motor, fora desta função.
2. **Sem caixa de mensagem.** Uma caixa de diálogo roubaria o foco da janela onde a automação está trabalhando e estragaria a própria execução. Por isso o aviso é o rótulo, a dica, o log e a barra de tarefas piscando.
3. **Aparência.** O rótulo usa as cores padrão da barra de status. Não pus cor, tamanho nem ícone no código da função (regra do `md/DIVISAO_DE_TRABALHO.md`). O rótulo tem o nome de objeto `AvisoElevacao`, para a frente visual poder estilizar.
4. **Quando olha.** Só durante a execução, a cada evento do motor, no máximo **umas 4 vezes por segundo**. Se uma janela de administrador vier para a frente no meio de uma espera longa, o aviso só aparece no próximo evento do motor.
5. **Uma vez por programa e por execução.** O rótulo some quando começa outra execução. Voltar de uma pausa não zera.
6. **O "Pode ser"** (o Windows negou a leitura) avisa mais fraco em vez de ficar calado. Se você achar que isso dá alarme falso, dá para deixar só no log: é uma linha na regra.
7. **Só olha o que a automação alcança durante a execução.** Não confere programas que a própria automação abre e não avisa antes de executar.
8. **A outra metade do item do plano não foi feita:** "limitar as pastas que a macro pode mexer". É outra função, e preferi não misturar as duas.
9. **O motor não foi tocado.** O vigia só escuta os sinais que a janela principal já recebe do motor.

## 3. O que foi mexido

| Arquivo | Mudança |
|---|---|
| `automationstudio/elevacao.py` (novo) | Sem Qt. A regra (quando avisar), os textos, a leitura do Windows (`ctypes`, só leitura, pedindo o mínimo de acesso e fechando tudo o que abre) e o vigia (guarda o que já leu de cada programa, olha no máximo 4 vezes por segundo e nunca derruba a execução: se algo inesperado acontecer, desliga sozinho e registra no log). |
| `automationstudio/elevacao_ui.py` (novo) | A parte com Qt: o rótulo na barra de status, a dica, o piscar da barra de tarefas e a ligação com os dois sinais do motor (evento e mudança de estado). |
| `automationstudio/main_window.py` | **3 linhas.** (a) `from .elevacao_ui import ControladorElevacao`, logo depois de `from .timeline import *`. (b) Em `MainWindow.__init__`, `self.elevacao = ControladorElevacao(self)`, logo depois de `self._position_error_notice()` e antes de `self._build_status_bar()`. (c) No fim de `_connect_bridge`, `self.elevacao.ligar(self.status_bar, self.bridge)`. |
| `tests/testsupport/funcoes_do_usuario.py` e `md/FUNCOES_DO_USUARIO.md` | Função **F51** no catálogo (o documento foi regenerado). Pus a linha entre a F12 e a F13, no grupo Execução. |
| `tests/testsupport/catraca_cobertura.py` | Uma linha: o grupo `elevacao` (os dois módulos novos). A catraca exige que todo módulo do pacote pertença a um grupo. |
| Testes novos | `tests/unit/test_aviso_administrador.py`, `tests/unit/test_aviso_administrador_ui.py`, `tests/static/test_ligacao_aviso_administrador.py` e o apoio `tests/testsupport/fakes_elevacao.py` (um "Windows de mentira" para os testes). |

Escolhi esses pontos do `main_window.py` e dos dois arquivos de catálogo para **não ficarem colados** nas linhas que os outros ramos mexem (importação, criação dos controles, catálogo). Não toquei em `core.py`, no motor, no tema nem em `APP_VERSION`.

## 4. Testes

| | Base (`main`) | Esta função |
|---|---|---|
| Dublê de widgets (`rodar_testes.py completo`) | 1651 passam, 77 pulados, 6 xfail | **1769** passam, 77 pulados, 6 xfail |
| Dublê de lógica (`rodar_testes.py rapido`) | 1424 passam, 304 pulados, 6 xfail | **1542** passam, 304 pulados, 6 xfail |

- **118 testes novos.** 82 cobrem a regra (as 16 combinações), os textos, a leitura do Windows e o vigia; 27 cobrem o controlador; 9 são estáticos e conferem a ligação na janela principal (com controle positivo e negativo, para provar que o teste enxerga o defeito).
- **A leitura do Windows foi testada contra um Windows de mentira** (funções de DLL falsas): 8 situações de processo (normal, de administrador, acesso negado, processo que sumiu e outras), alças abertas sempre fechadas, só o acesso mínimo pedido, assinaturas de 64 bits (sem elas o `ctypes` corta ponteiros em silêncio), janela sob o mouse com uma "isca" em (0, 0).
- **De ponta a ponta, com o motor de verdade:** o motor real, teclado de mentira, relógio virtual e o Windows de mentira. O aviso aparece quando a automação chega na janela de administrador, não aparece com o programa elevado, aparece uma vez só e some na execução seguinte.
- **Defeitos plantados à mão (91),** um de cada vez: **todos foram pegos.** Eram 7 nos textos, 5 na regra, 19 na leitura do Windows, 20 no vigia, 4 na criação do vigia, 31 no controlador e 5 na ligação da janela. Na primeira rodada um escapou (o texto curto do aviso forte podia ficar comprido demais); reforcei o teste e agora ele pega. Foi uma conferência minha, com um script fora do repositório; não entrou no catálogo de mutações do projeto.
- **Junção real com os outros ramos.** Com o histórico completo do GitHub, juntei o commit desta função com cada um dos 9 ramos que ainda não entraram na `main` (`desativar-comandos`, `diagnostico-abort-windows`, `executar-a-partir-daqui`, `pausar-continuar-teclas`, `plano-25-7`, `robustez-modelo`, `robustez-motor`, `teclado-atalhos` e `validacao-lacunas`): **nenhum conflito**. Para provar que a conferência enxerga conflito, fiz um commit de teste que mexe numa linha vizinha da minha: deu conflito, como devia. Os ramos `ativacao-mapas` e `visual/novo-tema` já estão na `main`.
- **Junção com as funções F49 e F50** (cópia descartável): sem conflito, e a suíte inteira passou com as três juntas: 1825 passam, 77 pulados, 6 xfail (widgets) e 1598 passam, 304 pulados, 6 xfail (lógica).
- **A suíte inteira, em cada uma dessas 9 junções** (cópia descartável, nos dois modos), **passou sem nenhuma falha**. Quantos testes passaram em cada uma (os pulados e os xfail ficam como cada ramo já tinha):

| Junção (esta função mais o ramo) | Dublê de widgets | Dublê de lógica |
|---|---|---|
| `desativar-comandos` (F49) | 1805 passam | 1578 passam |
| `diagnostico-abort-windows` | 1769 passam | 1542 passam |
| `executar-a-partir-daqui` (F50) | 1789 passam | 1562 passam |
| `pausar-continuar-teclas` | 1805 passam | 1578 passam |
| `plano-25-7` | 1769 passam | 1542 passam |
| `robustez-modelo` | 2087 passam | 1828 passam |
| `robustez-motor` | 2107 passam | 1848 passam |
| `teclado-atalhos` | 2502 passam | 2229 passam |
| `validacao-lacunas` | 1894 passam | 1666 passam |

## 5. O que NÃO foi conferido

- **Nada com o Windows de verdade nem com o Qt de verdade.** Esta sessão não tem Windows nem PySide6. Os testes rodaram com o dublê de widgets, com o de lógica, com o Windows de mentira e com relógio virtual.
- **O Windows de mentira segue o que eu acredito sobre o Windows.** Se o Windows se comportar diferente, os testes podem passar e a função falhar. O que só o Windows de verdade mostra:
  - se um programa comum consegue **ler o nível** de um programa de administrador ou recebe "acesso negado" (o desenho aceita os dois: no primeiro aparece o aviso forte, no segundo o "Pode ser");
  - se as **teclas de atalho** ficam mesmo mudas com a janela de administrador na frente (a dica diz "podem não funcionar", não afirma);
  - a **aparência** do rótulo na barra de status e a **barra de tarefas piscando**;
  - se o sinal do motor chega ao controlador na thread certa (é o mesmo padrão do rótulo de estado que já existe, mas não vi no Qt de verdade).
- Os testes de janela real (`tests/gui`) não rodaram. O GitHub Actions não foi disparado (esta sessão não tem como). Dá para rodar o fluxo **Tests** à mão (workflow_dispatch) no ramo.
- **Um teste pulado a mais, uma vez:** na primeira rodada numa cópia recém-criada da `main`, saiu 1650 passam e 78 pulados (um a menos passando e um a mais pulado). Nas rodadas seguintes, na mesma cópia e em outras novas, deu sempre 1651 e 77. Não consegui repetir nem descobrir qual teste foi.

## 6. Conferência rápida no Windows (de 2 a 5 minutos)

| # | Faça | Deve acontecer |
|---|---|---|
| 1 | Abra o Automation Studio **do jeito normal** (`Iniciar.bat`). Abra também um **Prompt de Comando como administrador** (botão direito, "Executar como administrador") e deixe aberto. | Nada de diferente ainda. |
| 2 | Monte uma automação com uma espera de uns 5 segundos e depois uma tecla (por exemplo, digitar a letra a). Clique em **▶ Executar** e, antes dos 5 segundos, traga o Prompt de administrador para a frente. | Quando a tecla for enviada, aparece à direita da barra de status **"⚠ Janela de administrador (...)"**, o botão do programa na barra de tarefas **pisca** e a letra **não aparece** no Prompt (é o bloqueio do Windows que o aviso explica). |
| 3 | Passe o mouse sobre o aviso. | A dica explica o bloqueio, cita o `Iniciar como administrador.bat` e diz que as teclas de atalho podem não funcionar. |
| 4 | Abra o arquivo `logs\AutomationStudio.log`. | Há uma linha `ELEVACAO programa=nao` e uma linha `AVISO ELEVACAO situacao=...` com o nome do programa. |
| 5 | Repita o passo 2 com um **Prompt comum** (sem administrador) ou o Bloco de Notas na frente. | **Nenhum aviso**, e a letra aparece. |
| 6 | Com o aviso na tela, clique em **▶ Executar** de novo (com o Bloco de Notas na frente). | O aviso **some** ao começar a nova execução. |
| 7 | Feche o Automation Studio e abra pelo **`Iniciar como administrador.bat`** (o Windows pede confirmação). Repita o passo 2 com o Prompt de administrador na frente. | **Nenhum aviso**, e a letra **aparece** no Prompt. No log, `ELEVACAO programa=sim`. |
| 8 | Opcional, de segurança: no passo 2, com o Prompt de administrador na frente, tente parar pela tecla de parada. | Pode não funcionar (o aviso diz isso). O botão **■ Parar** na janela do programa sempre funciona. |

Se aparecer no log alguma linha `ELEVACAO INCERTA`, `ELEVACAO VIGIA DESLIGADO` ou `ELEVACAO PISCAR FALHOU`, ou se o aviso aparecer onde não devia, o mais útil é me mandar o `logs\AutomationStudio.log` e a descrição do que você viu.
