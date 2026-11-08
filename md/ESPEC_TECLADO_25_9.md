# Especificação: o teclado em primeiro lugar (versão 25.9)

Etapa 1 do processo de 8 etapas: a ficha vem antes do código. **Estado: proposta.** A origem é a mensagem do dono de 07/11/2026. O que ele escreveu está entre aspas; o que ele deixou em aberto virou uma **decisão da seção 4**, cada uma com a alternativa, para ele vetar antes de o ponto correspondente começar. O pedido é grande e se divide em pontos (seção 6); o primeiro (T1) é o único que não depende da janela e já vem construído neste ramo, com a entrega registrada em `md/ENTREGA_TECLADO_T1_25_9.md`.

## 1. O pedido em requisitos

| ID | O que o dono pediu | Ponto |
|---|---|---|
| TEC-01 | Navegar pelas linhas de comando com as setas. | T2, T3 |
| TEC-02 | Enter "marca" a linha ("confirmar que estou mexendo nela") e abre a edição do comando conforme o tipo: **aplicativo**, escolher outro programa; **tecla**, apertar a tecla (um "bip" e apertar **a mesma de novo** para confirmar); **texto**, digitar o novo texto e Enter confirma e **tira a seleção da linha**, para voltar a navegar rápido. | T2, T3 |
| TEC-03 | "Se eu clicar duas vezes", editar o **tempo que o comando leva**. | T2, T3 |
| TEC-04 | A tecla `'` seleciona o comando para editar o **cooldown depois do comando anterior**. | T2, T3 |
| TEC-05 | Nos dois tempos, segurar a seta esquerda reduz o valor **cada vez mais depressa**; os **3 primeiros segundos bem lentos**, para dar precisão; **Enter** aceita a mudança. | T2 |
| TEC-06 | Teclas para abrir as configurações do programa, adicionar comandos e editar comandos. | T3, T4 |
| TEC-07 | **Tab** anda entre as guias das configurações e entre as opções do alto da tela. | T4 |
| TEC-08 | Só com o programa em primeiro plano; **não atrapalha** quem digita um texto nem quem usa o mouse normalmente. | T2, T3 |
| TEC-09 | Teclas **didáticas**: o programa diz o que cada tecla faz naquele momento. | T3, T4 |
| TEC-10 | Dá para usar o programa **só com o teclado**, no dia a dia e para criar automações. | T4 (aceitação) |
| TEC-11 | Automação **não pode** ser colada em tecla que já abre comando do Windows ou de navegador. | **T1** |
| TEC-12 | Atalho padrão composto: **Ctrl+Shift+Alt+1** para a primeira automação; os números seguintes como primeira sugestão das outras. | **T1** |
| TEC-13 | Também valem botões do mouse e teclas adicionais do teclado como disparadores. | T1 (F13 a F24), T5 |
| TEC-14 | **Identificar a quantidade** de botões do mouse e a **entrada de cada um** (há mouses com até 18 botões laterais). | T5 |
| TEC-15 | Esses botões valem como disparadores e **aparecem junto das demais teclas** quando pressionados. | T5 |
| TEC-16 | Não precisa desenhar os laterais; "até 4 botões" no mouse virtual mantém o visual e a imersão. | T5 |

## 2. Como o código está hoje (conferido na leitura)

1. **Lista de comandos** (`CommandTable`, em `command_editor.py`): colunas `# | Ordem dos comandos | Tipo | Tecla / botão | Começa em | Duração | Grupo`. Teclado de hoje (filtro de eventos da tabela): Enter edita a célula e desce para a mesma coluna da linha de baixo (edição "de planilha"), Tab vai à próxima coluna, Delete remove, Ctrl+A, C, X, V, Z e Y. **Não existe** captura da tecla apertada.
2. **Editar um comando** abre a barra lateral (`CommandDialog`): a tecla vem de uma lista fechada (`target_combo`); o botão do mouse, de uma lista de 5 itens (esquerdo, direito, meio, lateral 1 e 2); o aplicativo, de uma lista de programas conhecidos com "procurar".
3. **Tempos.** `Command.start` é absoluto (desde o começo do mapa) e `Command.duration` é a duração. A **lacuna** de um comando é `start − (início do anterior + tempo programado do anterior)` e pode ser negativa: é a sobreposição que o 'Flins combo' usa. `_retime` refaz os inícios em cascata, mantendo as lacunas, e é o que mover e remover comandos já usam. As edições de início e de duração (tabela, timeline, barra lateral) mudam só o comando; não empurram os seguintes.
4. **Barra do alto:** um `QToolBar` dentro de uma `QScrollArea`. Pelo que sei do Qt, os botões que o `QToolBar` cria nascem sem foco de teclado (`Qt::NoFocus`); isso **ainda não foi conferido aqui** (o teste com Qt de verdade do ponto T4 confere antes de qualquer mudança). Se for assim, Tab não alcança ▶ Executar, ⚙ Configurações e os outros.
5. **Configurações do programa** (`AppSettingsDialog`): um `ScrollableTabWidget` com várias guias.
6. **Teclas já em uso na janela:** Ctrl+Z e Ctrl+Y (barra), Esc (fecha as barras laterais e volta uma tela), as da tabela (item 1) e as da timeline (Ctrl+A, C, X, V, Delete, Enter para editar o bloco).
7. **O atalho de automação é global e passivo** (pynput): a tecla **continua chegando** ao programa em foco. O `GlobalHotkeyManager` dispara quando todas as teclas da combinação estão apertadas, em qualquer ordem, mesmo com teclas a mais. Uma automação em `Ctrl+T` abriria uma aba no navegador **e** começaria ao mesmo tempo: por isso TEC-11 é uma regra de segurança, não de gosto.
8. **Nome da tecla** (`core.key_to_name`): F1 a F12, modificadores, navegação e **só letras e números** (mais o Ç). Ver os achados A1 a A3.
9. **Mouse virtual** (`MouseWidget`): esquerdo, direito, roda e **dois** laterais (x1 e x2). O monitor repassa o nome cru do botão (D1 da 25.5: sem troca de x1 e x2 no caminho funcional, só no desenho).
10. **Catálogo de funções** (`tests/testsupport/funcoes_do_usuario.py`, F01 a F48): o contrato de que nenhuma função da janela se perde. Função que só se aciona por tecla entra com o endereço `("teste", ...)`.
11. **Frente visual** (`md/PLANO_VISUAL.md`): prevê duplo clique ou **Enter na linha** para editar um comando (P4, `visual/lista`, F21), Ctrl+F (busca), Ctrl+K (paleta) e atalhos nas dicas dos botões. `main_window.py`, `command_editor.py`, `timeline.py` e `tutorial.py` são arquivos **compartilhados** (`md/DIVISAO_DE_TRABALHO.md`, seção 3).

## 3. Achados que o pedido expôs

Todos vêm da leitura do código e de execução em cópia de teste; nenhum foi observado no Windows.

| ID | Achado | Confiança |
|---|---|---|
| A1 | A tecla `=`, que é a **padrão de todo mapa novo**, **nunca chega** ao gerente de atalhos: `key_to_name` devolve vazio para qualquer símbolo e o monitor descarta o evento. A tela diz "Tecla para iniciar/parar: =" e a tecla não faz nada (o botão ▶ Executar funciona). | Alta no código; efeito no Windows não observado |
| A2 | **F13 a F24 são descartadas** (a tabela de nomes só tem F1 a F12). É a tecla que mouses e teclados de muitos botões costumam enviar, ou seja, justamente as teclas livres que o dono quer usar. | Alta no código |
| A3 | Com **Ctrl, Shift e Alt** apertados, o `char` que o pynput entrega pode refletir os modificadores (por exemplo `'!'` no lugar de `'1'`): a documentação dele cita o `canonical()` "para remover qualquer estado de modificador dos eventos de tecla". Se acontecer, `Ctrl+Shift+Alt+1` **não seria reconhecido**, e é o padrão pedido. A correção (usar o código virtual `vk` quando o `char` não serve) não muda nada quando o `char` já é uma letra ou um número. | Média: a causa vem da documentação; só o Windows do dono confirma |
| A4 | Pontuação e símbolos também não são **gravados** nem **acendem no teclado virtual** (mesma causa de A1). Fora do escopo deste pedido: vai para o backlog, com o cuidado de que isso muda o que o gravador grava. | Alta no código |

O A1 não é corrigido **de propósito**: se a tecla `=` passasse a funcionar, todo mapa antigo com a tecla padrão começaria a rodar a cada `=` digitado em qualquer programa. A decisão D11 troca o padrão dos mapas novos e a T1 avisa nos antigos.

## 4. Decisões (vetáveis)

| # | Decisão | Por quê | Alternativa |
|---|---|---|---|
| D1 | "Clicar duas vezes" é **Enter duas vezes** em até 0,4 s: o primeiro Enter já abre a edição do conteúdo; o segundo troca para o tempo, sem perder nada. O duplo clique do mouse segue como hoje. | O dono usa "clicar" para tecla ("clicando com a seta esquerda"). Não gasta espera nenhuma no primeiro Enter. | Uma tecla própria para o tempo (por exemplo `T`). |
| D2 | **Enter** na lista passa a ser a edição rápida do pedido; a edição de célula "de planilha" vai para **F2** (e o duplo clique do mouse continua). **Shift+Enter** abre a barra lateral completa. **Tab** sai da tabela em vez de ir à próxima coluna; ←→ escolhem a coluna da célula (padrão do Qt). | O pedido redefine o Enter; F2 é a tecla de editar célula de qualquer planilha; Tab precisa sair da tabela para o TEC-07. | Manter o Enter de planilha e usar outra tecla para marcar. |
| D3 | A tecla `'` vale pelo caractere digitado (cobre ABNT2 e o teclado dos EUA) e **só** quando a linha está marcada e o foco é a lista. | Não pode atrapalhar quem digita (TEC-08). | — |
| D4 | **Espera** (`'`): os comandos seguintes **andam junto**, mantendo as lacunas deles (`_retime`); mínimo 0. **Tempo** (Enter duas vezes): os seguintes **não** se movem (igual à edição de duração que a tabela e a timeline já têm). | Aumentar a espera de um comando sem empurrar os seguintes o sobreporia ao próximo. Já a duração de uma tecla segurada sobrepõe de propósito em mapas como o 'Flins combo'. | Os dois em cascata, ou nenhum. |
| D5 | **Curva do tempo** (valores iniciais): um toque muda **0,01 s**; segurando, de 0 a 3 s a velocidade é **0,1 s por segundo**; depois **dobra a cada 2 s**, até o teto de 60 s por segundo. ← diminui, → aumenta; Enter aceita, Esc desfaz. O tempo é contado pelo relógio, não pela repetição de tecla do sistema. | "Bem lento nos 3 primeiros segundos" e "cada vez mais rápido". Os números ficam numa tabela única, fáceis de mudar. | Outras constantes. |
| D6 | O "bip" é o som do sistema (`QApplication.beep()`) **mais** a proposta escrita na barra de status; vira opção "Som de confirmação" nas configurações. | O som sozinho falha em máquina muda. | Só visual. |
| D7 | Depois de **qualquer** confirmação (texto, tecla, tempo, espera) a linha **é desmarcada** e o foco volta à lista; **Esc** cancela e também desmarca. | É o que o dono descreveu para o texto, estendido ao resto para ser uma regra só. | Voltar à linha marcada. |
| D8 | **Adicionar comando:** `Insert` abre um seletor de uma tecla (cada tipo mostra a sua letra, por exemplo T para tecla, E para escrever um texto, M para mouse, A para aplicativo), cria o comando já na linha de baixo e entra direto na edição. Teclas de janela propostas: `Ctrl+,` configurações do programa, `F1` lista de atalhos. | Dois toques para criar e editar, sem a barra lateral. As teclas escolhidas não colidem com as da janela (seção 2, item 6) nem com Ctrl+F e Ctrl+K do plano visual. | Outras teclas: é só trocar na tabela única da T3. |
| D9 | Os botões da barra do alto passam a ser **parada de Tab** (`Qt::TabFocus`, que **não** dá foco ao clique do mouse). Nas configurações, a **barra de guias** é a primeira parada: ←→ trocam de guia, Tab ou ↓ entram na página. | Não muda nada para quem usa o mouse. | `Qt::StrongFocus`. |
| D10 | **Regras de atalho de automação** (seção 5.3): recusadas as colisões certas; **aviso** nas prováveis; livres as compostas com três modificadores, as teclas F13 a F24 e os botões extras. | É a regra do dono (TEC-11, TEC-12), com um catálogo explicável. | Aceitar só três modificadores. |
| D11 | Mapa novo criado pela tela nasce com a **primeira combinação livre** de `Ctrl+Shift+Alt+1, 2 … 9, 0, depois F1 a F12 e A a Z`. O padrão do **modelo** (`AutomationMap.hotkey = "="`) **não muda**: arquivos e testes antigos ficam idênticos. | Pedido do dono (TEC-12) sem mexer no formato. | Mudar o padrão do modelo. |
| D12 | Mapa antigo com tecla que a regra recusa **continua funcionando** como está: só aparece um aviso ao lado da tecla. Só **trocar** a tecla passa pela regra, e salvar a automação sem mexer na tecla nunca é bloqueado. | Preservar o que funciona. | Trocar à força. |
| D13 | Os **atalhos de controle** (F8 a F12) ficam como estão; a regra vale para as **automações**. | O dono falou de automações. A mesma regra recusaria as teclas de controle de hoje. | Aplicar aos dois e propor trocar. |
| D14 | **Botões laterais do mouse X1 e X2 sozinhos** valem como disparadores com um **aviso** (os navegadores os usam como Voltar e Avançar); com um modificador ou como botão extra aprendido, ficam livres. Esquerdo, direito e meio são **sempre recusados**. | O dono quer botões do mouse como disparadores. | Recusar X1 e X2 sozinhos. |
| D15 | "Até 4 botões" é lido como **até 4 botões laterais desenhados** no mouse virtual (hoje são 2); os demais valem como disparadores e aparecem entre as teclas, sem desenho. | É o que a frase indica. | 4 botões no total. |
| D16 | Como o Windows só expõe cinco botões de forma padrão, a **quantidade** vem do sistema (quando informa) e a **entrada de cada botão** vem de um **assistente de aprendizado** ("aperte o botão que quer cadastrar"), guardado nas configurações. | Botões além do 5º costumam chegar como teclas (F13 a F24, combinações) pelo software do fabricante; só apertando se descobre. | Digitar a lista à mão. |

## 5. Desenho

### 5.1 Controlador puro e ligação fina

Como na ativação e no Parar/Pausar: a lógica fica em módulos **sem Qt**, testáveis aqui com relógio falso, e a janela só liga os eventos.

| Módulo novo | Papel | Ponto |
|---|---|---|
| `atalhos_reservados.py` | Catálogo e regras das teclas de automação; sugestão da próxima tecla livre. | T1 |
| `teclado_edicao.py` | O estado da edição por teclado (navegando, linha marcada, tecla, texto, aplicativo, tempo, espera), a curva de D5 e o que mostrar na dica. Recebe teclas abstratas, devolve efeitos. | T2 |
| `teclado_ui.py` | A ligação com a tabela e a barra de status (filtro de eventos, bip, desmarcar), no molde de `ativacao_ui.py`. | T3 |
| `perfil_mouse.py` | Contagem e entrada de cada botão, aprendizado, o que o mouse virtual desenha. | T5 |

Arquivos compartilhados que serão tocados, sempre em mudança pequena e localizada: `command_editor.py` (o início do filtro de eventos da tabela delega ao controlador), `main_window.py` (criar o controlador, a política de foco da barra, a sugestão de tecla do mapa novo), `overlays.py` (T5). Cada commit diz o que tocou.

### 5.2 Teclas na lista de comandos (proposta; vale só com o foco na lista)

| Tecla | Faz |
|---|---|
| ↑ ↓ ← → | Navegar (padrão do Qt). |
| Enter | Marca a linha e abre a edição pelo tipo: tecla, texto, aplicativo, botão do mouse. |
| Enter, Enter (até 0,4 s) | Edita o tempo do comando (a duração). |
| `'` | Com a linha marcada, edita a espera depois do comando anterior. |
| ← → no tempo e na espera | Diminuem e aumentam; segurando aceleram (D5). |
| Enter, Esc | Aceita ou desfaz, e desmarca a linha (D7). |
| F2 | Edita a célula atual (como a planilha de hoje). |
| Shift+Enter | Abre a barra lateral completa. |
| Insert | Adiciona um comando abaixo (D8). |
| Delete, Ctrl+A, C, X, V, Z, Y | Como hoje. |

Nenhuma dessas teclas age quando o foco está num campo de texto (a barra lateral, as configurações, o editor de texto do comando): lá o teclado é o do campo (TEC-08). O controlador só recebe as teclas quando a lista tem o foco e a janela está ativa.

### 5.3 Regras das teclas de automação (T1)

A combinação é lida por `parse_combo` (maiúsculas, espaços e apelidos já normalizados). O **primeiro** item que se aplicar decide:

1. Sem nenhuma tecla ou botão, só modificadores: **recusada** (dispararia ao usar qualquer atalho).
2. Com **Win**: recusada (atalhos do Windows).
3. Catálogo explícito de combinações do Windows e dos navegadores (Ctrl+Alt+Del, Ctrl+Shift+Esc, Alt+F4, Alt+Tab, Ctrl+Shift+T, Ctrl+Shift+N, Ctrl+Shift+W, Ctrl+Shift+Delete, Ctrl+Shift+I, J e C, Ctrl+Shift+R, Ctrl+Shift+Tab e outras): **recusada**, com o motivo da combinação.
4. Esquerdo, direito ou meio do mouse (com ou sem modificador): recusada.
5. Tecla de digitar ou navegar (letra, número, símbolo, Espaço, Enter, Tab, setas, Delete…) **sem modificador ou só com Shift**: recusada (dispararia ao digitar).
6. F1 a F12 sem modificador ou só com Shift: recusada (ajuda, atualizar, tela cheia, ferramentas do desenvolvedor…).
7. Teclas F13 a F24 (com qualquer combinação que passou das regras 1 a 6): **livre**.
8. Um único modificador, **Ctrl** ou **Alt**: recusada (quase todo programa usa Ctrl+tecla e Alt+tecla).
9. **Ctrl+Alt** (o AltGr) com tecla de digitar: recusada (digita caracteres em vários teclados, como o ABNT2).
10. **Dois** modificadores com uma tecla que o catálogo não cita: **aviso** ("pode colidir com atalhos de alguns programas").
11. **X1 ou X2** sozinho: aviso (D14).
12. Todo o resto: **livre**, em especial **três** modificadores (Ctrl+Shift+Alt) com uma tecla e os botões extras aprendidos (T5).

O AltGr que o pynput informa (`ALTGR`) é lido como Ctrl+Alt, que é o que ele é no Windows.

O resultado é `livre`, `aviso` ou `recusada`, com o texto para mostrar e, na recusa, uma sugestão (a próxima combinação livre da D11). **Quando vale:** ao trocar a tecla de um mapa (recusa, salvo se a tecla não mudou: D12), ao criar um mapa pela tela (D11) e, em mapas que já existem, só como aviso ao lado da tecla.

### 5.4 Curva do tempo (T2)

Uma função pura recebe quanto tempo a seta está segurada e devolve a velocidade em segundos de valor por segundo (D5). O valor muda por integração a cada tique do relógio (cerca de 30 por segundo na janela), arredondado ao milissegundo, nunca abaixo de 0. Um toque (apertar e soltar em menos de 0,3 s) vale um passo de 0,01 s e não conta como segurar. Trocar de seta ou soltar zera a contagem.

## 6. Pontos, ordem e como cada um se prova

| Ponto | Entrega | Prova | Só o Windows ou o Qt de verdade confirma |
|---|---|---|---|
| **T1** | Regras e catálogo das teclas de automação (TEC-11), sugestão `Ctrl+Shift+Alt+N` (TEC-12), nomes de tecla confiáveis: F13 a F24 e dígitos e letras pelo `vk` (A2, A3), avisos nos mapas antigos. | Testes de unidade (regras, catálogo, normalização, sugestão), do monitor (`key_to_name`) e da ativação; defeitos plantados; Actions. | A3: `Ctrl+Shift+Alt+1` acender e disparar no teclado do dono. |
| T2 | O controlador da edição por teclado e a curva de D5 (TEC-01 a TEC-05, TEC-08). | Testes com relógio falso: cada transição, o toque contra o segurar, a curva por tempo, desfazer, Esc, 0,4 s. Varredura de sequências aleatórias de teclas contra invariantes. Defeitos plantados. | O "feeling" da curva. |
| T3 | A ligação com a tabela e a barra de status; captura da tecla com o bip; seletor de aplicativo; `Insert`; F2; Shift+Enter; atalhos de janela (TEC-02, TEC-06, TEC-09). | Testes com Qt de verdade (`QTest.keyClick`) no Actions: a lista com foco recebe, o campo de texto não; Enter, Enter duas vezes, `'`, ← →; histórico (desfazer) correto. | O bip, o foco depois de confirmar, a sensação no dia a dia. |
| T4 | Tab na barra do alto e nas guias das configurações; `F1` com a lista de atalhos (a mesma tabela do controlador); dicas dos botões com a tecla; catálogo F49 em diante (TEC-07, TEC-09, TEC-10). | Qt de verdade: ordem de Tab, foco inicial, ←→ nas guias; o catálogo confere cada tecla contra o código. Roteiro de aceitação **sem mouse** (cria, edita e executa uma automação). | O roteiro, no Windows. |
| T5 | Perfil do mouse: contagem, aprendizado, desenho de até 4 laterais, botões extras como disparadores e entre as teclas (TEC-13 a TEC-16). | Testes com monitor falso e `user32` falso; Qt de verdade para o desenho. | Quase tudo: depende do mouse do dono. |
| T6 | Rodada do Windows: um roteiro curto de conferência, no formato dos anteriores. | — | Tudo o que ficou na última coluna. |

A ordem é a da dependência e do risco: T1 e T2 são lógica pura e travam o resto; T3 e T4 usam a janela (o ciclo é publicar, esperar o Actions e corrigir); T5 e T6 dependem do hardware. **Cada ponto ganha uma ficha curta com os números exatos antes de ser construído.**

## 7. Riscos

1. **Arquivos compartilhados.** `command_editor.py` e `main_window.py` mudam nas duas frentes. Mitigação: a lógica fica em módulos novos e a mudança nos arquivos compartilhados é uma delegação de poucas linhas; cada commit lista o que tocou.
2. **Enter na lista** tem dois donos: o plano visual (P4) abre a barra lateral; o pedido do dono de 07/11 edita no lugar. A D2 resolve com Shift+Enter para a barra lateral; o duplo clique do mouse segue abrindo a barra. Quem integra decide se quer outro desenho.
3. **AltGr.** `Ctrl+Alt` é o AltGr em teclados como o ABNT2; `Ctrl+Shift+Alt+1` tem Shift junto e provavelmente não digita nada, mas **só o teclado do dono confirma** (por isso a regra 9 recusa `Ctrl+Alt+letra`).
4. **A3 é hipótese.** Se o `char` já vier certo, a correção do `vk` é inofensiva; se vier alterado, ela é o que faz o padrão pedido funcionar.
5. **Botões do mouse.** O Windows só entrega cinco botões de forma padrão; o resto depende do software do fabricante (T5, D16). Sem o mouse do dono, a parte de entrada de cada botão não pode ser provada aqui.
6. **Tab na barra do alto** depende do `Qt::NoFocus` do item 4 da seção 2: é conferido com Qt de verdade antes de mudar.

## 8. Fora do escopo (backlog)

- Gravar e acender no teclado virtual a pontuação e os símbolos (A4).
- Trocar os atalhos de controle (F8 a F12) por combinações compostas (D13).
- Mais teclas de janela (executar, parar, salvar) além das da D8: o dono diz quais quer.
- Multiplicadores de passo no tempo (Shift e Ctrl com ← →).

