# Ficha do ponto T3 do teclado (25.9): ligar o controlador à tabela de comandos e à barra de status

Escrita **antes** do código, como combinado na seção 6 de `md/ESPEC_TECLADO_25_9.md`. Fixa o que o T3 entrega, o desenho e o que os testes vão cobrar. Ramo: `funcoes/teclado-tabela`, empilhado sobre `funcoes/teclado-edicao` (T2). É o primeiro ponto em que **o que o usuário vê na janela muda**; por isso os commits dele são `Versão: 25.9 (nova)`.

## 1. O que o T3 entrega e o que não entrega

O ponto T3 da especificação reúne seis coisas (ligação, captura com bip, seletor de aplicativo, `Insert`, F2 e Shift+Enter, atalhos de janela). Junto numa entrega só, não cabe numa revisão que se confira de verdade. **Decisão (autonomia concedida pelo dono): o T3 se divide em dois, e esta ficha é só da primeira metade, o T3a.**

**T3a (esta ficha) entrega**, com a tabela de comandos em foco e a janela em primeiro plano:

- ↑ ↓ continuam navegando (é o Qt); **Enter** marca a linha e abre a edição pelo tipo do comando (tecla: captura com bip e confirmação apertando a mesma de novo; texto: editor na própria linha; programa: janela para escolher; botão do mouse: ← →); **Enter, Enter** em até 0,4 s edita o tempo apertado; **`'`** edita a espera antes do comando; ← → com o tempo ou a espera aberto mudam o valor (toque = 0,01 s; segurando acelera, com os 3 primeiros segundos bem lentos); Enter aceita, Esc descarta.
- **F2** edita a célula atual como a planilha de hoje (era o papel do Enter); **Shift+Enter** abre a barra lateral do comando.
- A **barra de status** diz, a cada momento, o que as teclas fazem (TEC-09) e mostra o valor em edição.
- Durante a captura de tecla, os **atalhos globais das automações** ficam suspensos (apertar `A` para gravá-la não pode disparar a automação que tem `A`).
- Cada edição gravada é **um passo do histórico** (Ctrl+Z desfaz), com o nome da ação.

**T3a não entrega** (fica registrado para não se passar por pronto):

- `Insert` com o seletor de tipo e o comando novo já em edição, `Ctrl+,` (configurações): **T3b**, ficha própria.
- **Tab** sair da tabela, Tab nas guias e na barra do alto, `F1` com a lista de atalhos, entradas no catálogo `FUNCOES_DO_USUARIO` e o roteiro de aceitação sem mouse: **T4**.
- Botões do mouse como disparadores: **T5**. A rodada no Windows: **T6**.
- Até o T3b e o T4, "o programa se usa pelo teclado" **ainda não vale**: falta criar comando e sair da tabela.

## 2. O que o código de hoje diz (conferido na leitura)

1. **A tabela já trata teclas** em `CommandTableWidget.eventFilter` (`command_editor.py:2539`): Delete, Ctrl+A/C/X/V/Z/Y, **Enter** (se há célula atual: edita a célula; ao confirmar, desce uma linha e edita a próxima) e **Tab** (próxima coluna). Só vê teclas quando **nenhum editor de célula está aberto**; com ele aberto, as teclas vão para o editor.
2. As colunas são `["#", "Ordem dos comandos", "Tipo", "Tecla / botão", "Começa em", "Duração", "Grupo"]` (`:1838`). Só **1, 4, 5 e 6** se editam na planilha (`_begin_edit`, `:2706`; `_fill_row`, `:2661`); a coluna **3**, a que mostra a tecla, o botão, o texto ou o programa, **não** se edita na lista: hoje só pela barra lateral. O T3a é a primeira vez que se edita esse conteúdo na lista.
3. `refresh()` (`:2634`) apaga e refaz todas as linhas e **não preserva** seleção nem rolagem; quem muda o mapa por fora (`_move_selected`, `:2760`) faz `refresh(); selectRow(j); setCurrentCell(j, 0); map_changed.emit(rótulo)`. O T3a faz o mesmo e **também** guarda e devolve a rolagem.
4. `MainWindow._on_map_edited(rótulo)` (`main_window.py:1361`) normaliza os tipos, chama `validate()` e, **se houver erro fatal, mostra aviso e não salva nem registra histórico** (o modelo em memória já mudou: é assim hoje também para a célula da planilha). Sem erro, salva o mapa, atualiza a linha do tempo e faz `history.commit(mapa, rótulo)`, **um passo por chamada, sem juntar** (`project.py`, `MapHistory.remember`). Por isso valor igual ao de antes **não emite nada** (regra do T2) e o T3a nunca chama com um mapa que ganhou erro (o T2 já prova que `validate()` não ganha erro com as saídas do controlador).
5. **A barra lateral grava de outro jeito** (`CommandDialog.result_command`, `command_editor.py:717`): tecla vai em **maiúsculas**; texto recalcula a **duração** com `calculate_text_duration`; programa grava o item escolhido na lista (um dos conhecidos, ou o que "Procurar executável…" devolveu; a lista **não aceita texto digitado**) e o campo **"processo que deve aparecer"** (`wait_process`) é separado e **só acompanha** o programa quando se usa "Procurar" (`_browse_app_executable`, `:637`). Trocar só o alvo, sem cuidado, deixa a automação **esperando o processo antigo** até o tempo limite. A edição pelo teclado tem de tratar disso (T3-6).
6. O vocabulário de teclas que a **barra lateral** oferece (`_key_options`, `:447`): letras A a Z e Ç, dígitos 0 a 9, F1 a F12, ESC, TAB, CAPSLOCK, SHIFT, CTRL, ALT, ALTGR, ENTER, BACKSPACE, SPACE, WIN, MENU, FN, INSERT, HOME, PAGEUP, DELETE, END, PAGEDOWN, UP, DOWN, LEFT, RIGHT, PRINTSCREEN, SCROLLLOCK, PAUSE, NUMLOCK, NUM/, NUM*, NUM-, NUM+, NUM0 a NUM9, NUM. e NUMENTER. O que o **motor do Windows** sabe apertar (`Win32InputBackend._vk`, `input_system.py:273`) inclui todas e F13 a F24 (T1). Tecla fora disso não pode ser gravada.
7. O Esc tem um **tratador no nível do aplicativo** (`MainWindow.eventFilter`, `main_window.py:341`, instalado em `QApplication`): fecha a barra de execução, depois a barra lateral, depois volta uma página. Ele roda **antes** de qualquer filtro de widget: sem ceder, o Esc que cancela uma edição também voltaria de página.
8. O gerenciador de atalhos globais (`GlobalHotkeyManager`, `input_system.py:599`) registra **tudo no mesmo lugar**: automações (`Registro.e_mapa`) e as teclas de controle e de gravação. Hoje não há como suspendê-lo. O monitor (pynput) roda numa linha própria e, **pela documentação do Windows** (gancho `WH_KEYBOARD_LL`, chamado de forma síncrona antes de a tecla ser entregue à janela), decide **antes** de o Qt ver a tecla. Isto é uma **premissa**, não algo provado aqui: por isso a suspensão fica no gerenciador (não numa fatia da janela que roda depois) **e** a retomada tem uma graça (T3-7), para o caso de a ordem ser outra.
9. **Este ambiente não tem Qt**: o dublê `qt_stub` devolve marcadores para tudo e o `qt_double` só modela diálogos (`CommandDialog`), sem `QTableWidget`, sem `QKeyEvent`, sem filtro de eventos. O PyPI está bloqueado pela política de rede (erro 403, testado de novo hoje): não dá para instalar o PySide6. O que tem Qt de verdade roda **só no Actions**.

## 3. Decisões do T3a (vetáveis; as de número D vêm da especificação)

| # | Decisão | Por quê |
|---|---|---|
| T3-1 | **Quatro peças, só uma com Qt.** `teclado_aplicar.py` (grava no mapa; sem Qt), `teclado_teclas.py` (do evento do Qt para `Tecla`; sem Qt), `teclado_ligacao.py` (o controlador + uma **porta** + um relógio; sem Qt) e `teclado_ui.py` (`TecladoDaJanela`: filtro, marca, editor de texto, janela do programa, barra de status, bip, relógio de 30 Hz; é a **única** que só roda no Actions). | Tudo o que decide (ordem dos efeitos, suspensão, relógio, o que gravar, qual tecla vira qual nome) fica testável aqui, com a `JanelaFalsa` e um relógio falso. O Qt fica numa camada fina, provada no Actions. |
| T3-2 | **Uma instância por janela** (`MainWindow.teclado`), criada depois da tabela, que instala **um filtro extra** na tabela e no viewport. Filtros instalados depois rodam antes (regra do Qt), então o `eventFilter` da tabela **não é editado**. A única mudança em `command_editor.py` é **extrair** o que o Enter faz hoje para `editar_celula_atual()` (a F2 chama o mesmo; o Enter antigo continua valendo quando o controlador não age). | Zero conflito com a frente visual (que mexe em `command_editor.py`) e comportamento antigo preservado. |
| T3-3 | **Quando o filtro age.** Só com a tabela em foco e sem editor de célula aberto. A **repetição do sistema** (`isAutoRepeat`) nunca chega ao controlador: é consumida se a tecla é uma que o controlador trata naquele estado (e sempre fora da navegação), e segue para o Qt nas demais (segurar ↓ rola as linhas). A soltura da tecla vai ao controlador (`soltar`). O relógio de ~30 Hz (33 ms) roda **só** nos estados TEMPO e ESPERA. Teclas com Ctrl ou Alt voltam inteiras para a janela (Ctrl+Z desfaz mesmo no meio de uma edição, e isso a descarta: T3-8). | TEC-08 (não atrapalhar) e D5 (a rampa usa o relógio, não a repetição). |
| T3-4 | **"Linha atual" = exatamente uma linha selecionada.** Com zero linhas o controlador não age e o Enter segue o caminho antigo. Com **duas ou mais**, as quatro teclas da navegação (Enter, Shift+Enter, F2, `'`) são consumidas com a dica "Escolha um só comando para editar com o teclado (há N selecionados)". | Editar o conteúdo de vários comandos de uma vez não tem sentido, e o silêncio seria o pior jeito de dizer isso. |
| T3-5 | **O que cada efeito faz na tela.** `Marcar`/`Desmarcar`/`Cancelar`: uma moldura própria sobre a linha (objeto `marcaDeEdicao`, contorno de 2 px e fundo translúcido, **trocável pela frente visual** porque não toca em nenhum painter dela); `AbrirTexto`: um `QLineEdit` sobre as colunas 3 a 6 da linha, com o texto atual selecionado; `AbrirAplicativo`: uma janela **não bloqueante** (`open()`, sem laço aninhado) com a lista de programas conhecidos, "Procurar executável…" e Esc; `ProporTecla`+`Bip`: a proposta na barra de status e `QApplication.beep()` (D6); `MostrarValor`/`Dica`: `showMessage`; `AbrirBarraLateral`: o mesmo sinal do duplo clique (`command_editor_requested`); `EditarCelula`: `editar_celula_atual()` (T3-11). `IniciarCaptura` e `FecharEditor` não pedem widget (a captura **não tem** campo: é a tabela mesma que recebe a tecla). | O desenho do T2 (efeitos) mapeia 1 para 1 numa porta de uns 15 métodos. Janela não bloqueante porque um laço aninhado dentro do filtro reentraria no controlador e deixaria as dicas atrasadas. |
| T3-6 | **Gravar = as regras da barra lateral, com conferência.** Tecla: maiúsculas. Botão: um dos cinco nomes. Texto: `texto` e `duração = calculate_text_duration(texto)`. Programa: alvo normalizado e **`wait_process` acompanha só se estava igual ao processo do alvo antigo** (comparação sem maiúsculas, pelo nome do arquivo); se estava vazio, **continua vazio** (nunca criar uma espera que o dono não tinha); se era outro nome, **continua** e a barra de status avisa que o processo esperado é aquele. Tempo: `duração` direto (D4: não empurra os seguintes, como a célula "Duração"). Espera: `set_gap_before`. **Antes de mudar qualquer coisa** confere que o índice existe, que o `id` do comando é o da hora em que a linha foi marcada e que o tipo é o mesmo; senão não grava nada e avisa. | A conferência evita gravar no comando errado quando o mapa muda por outro caminho durante a edição; as regras iguais evitam duas verdades sobre "o que é editar uma tecla". |
| T3-7 | **Suspensão dos atalhos de automação durante a captura.** `GlobalHotkeyManager.suspender()` e `retomar()`, **só** para as combinações registradas com `suspensivel=True` (`registrar_plano` passa `registro.e_mapa`); as de controle (pausar, continuar, emergência) e de gravação **seguem valendo**, porque a parada de emergência não pode sumir. Enquanto suspenso, a combinação que se completa **conta como disparada** (não dispara na retomada com a tecla ainda apertada) e volta ao normal quando solta. A retomada tem uma **graça de 0,25 s** (`retomar(graca=0.25)`, relógio injetável) em que ainda não dispara: se o Qt processar a tecla de confirmação antes do monitor (a premissa da seção 2, item 8, falhar), a automação **não** parte na própria tecla que confirmou. A ligação suspende ao **entrar** no estado TECLA e retoma ao **sair** dele por qualquer caminho (confirmar, Esc, Enter duplo, descartar): é o estado que manda, não o efeito. | Apertar `A` para gravá-la não pode iniciar a automação cujo atalho é `A`. Decidir pelo estado cobre todas as saídas, inclusive as que ninguém previu. |
| T3-8 | **O que descarta a edição (`descartar()`).** A seleção da tabela mudar (inclui `refresh()` por desfazer, abrir outro mapa, a linha do tempo selecionando); a tabela perder o foco **exceto** para o editor de texto ou para a janela do programa (que são do próprio T3a); a janela ser desativada fora desses dois estados; o editor de texto perder o foco. As mudanças que o próprio T3a faz na tabela (`refresh` depois de gravar) ficam **atrás de uma guarda** para não se descartarem. | T2-6. |
| T3-9 | **Esc do aplicativo cede.** `MainWindow.eventFilter` só trata o Esc quando `self.teclado.editando()` é falso. Fora da edição o Esc faz exatamente o que fazia. | Sem isso, cancelar uma edição voltaria de página. |
| T3-10 | **De evento do Qt para tecla** (seção 5): letras, dígitos, F1 a F24, as teclas nomeadas e, **só na captura**, as do teclado numérico (`NUM0`…, `NUMENTER`). Fora da captura o Enter do teclado numérico é Enter. Dígitos com Shift ou AltGr (que o Qt entrega como símbolo) são resolvidos pelo código virtual do Windows quando ele existe. Tecla sem nome no Studio (pontuação, acentos mortos, teclas de mídia) vira `nome=""`: o controlador responde "essa tecla não pode ser usada". O caractere digitado vai em `texto` (é por ele que o `'` é reconhecido). | A captura só pode gravar o que a barra lateral mostra **e** o motor aperta; um teste cruza as duas listas. |
| T3-11 | **F2** chama `editar_celula_atual()`: se a célula atual se edita (colunas 1, 4, 5, 6), abre o editor como o Enter de hoje; se não (colunas 0, 2, 3), mostra "Esta coluna não se edita na lista: use ← → para outra coluna ou Enter para editar o comando" e **não** deixa a marca de "editando" presa (hoje o Enter numa coluna fixa deixa; a F2 não herda isso). **Shift+Enter** abre a barra lateral do comando atual. | O Enter de planilha vai para a F2 (D2); herdar o defeito do Enter seria criar um novo. |
| T3-12 | **Barra de status didática.** Com a tabela em foco: `DICA_NAVEGANDO`, permanente enquanto o foco estiver lá; a cada estado, a dica dele (`dica_do_estado`); depois de gravar, a frase do que mudou mais "Ctrl+Z desfaz", por 6 s; ao cancelar, volta a dica da navegação. Ao perder o foco, a barra só é limpa se a mensagem atual ainda for a nossa. | TEC-09. Não apagar mensagem de outra parte do programa. |
| T3-13 | **Erro dentro de um efeito** (qualquer exceção na gravação ou na tela): registra no log, **descarta** a edição, tira a marca, mostra "Algo deu errado na edição pelo teclado; nada foi gravado." e consome a tecla. A gravação no modelo é feita em **uma chamada** que valida antes de mudar, então não sobra mudança pela metade. | Uma exceção num filtro de eventos não pode deixar a tabela presa num estado de edição. |
| T3-14 | **Rótulos do histórico:** "Editar tecla", "Editar botão", "Editar texto", "Editar programa", "Editar tempo apertado" e "Editar espera". | Aparecem em Desfazer/Refazer: dizem o que se desfaz. |
| T3-15 | **A lista de programas conhecidos vira uma só.** `command_editor.py` ganha a constante `PROGRAMAS_COMUNS` (os seis de hoje: Edge, Bloco de Notas, Explorador, Calculadora, Outlook clássico e novo) e a função `programas_conhecidos()` (os comuns mais `python`, `cmd`, `powershell` e `wt` que estiverem no PATH); a barra lateral passa a usar as duas e a janela do teclado também. | Duas listas copiadas divergiriam; a barra lateral e o teclado têm de oferecer os mesmos programas. |

## 4. Desenho

```
QKeyEvent ─► teclado_teclas.tecla_do_evento ─► Tecla ─┐
                                                      ▼
TecladoDaJanela (Qt) ──► LigacaoDoTeclado ──► EdicaoPorTeclado (T2)
   ▲  filtro da tabela      │   ▲                    │  Resposta(efeitos)
   │  do editor de texto    │   └── relógio ─────────┘
   │  do seletor            ▼
   └── PortaDaTabela (Qt) ◄─ Porta (interface, ~15 métodos)
              │
              └─► teclado_aplicar (mapa) · refresh + reseleção + map_changed(rótulo)
```

`LigacaoDoTeclado` (sem Qt) tem: `editando()`, `tecla_pressionada(tecla, repeticao)`, `tecla_solta(nome)`, `tique()`, `texto_confirmado()`, `aplicativo_resolvido(valor)`, `perdeu_foco()`, `selecao_mudou()`, `descartar()`. Depois de **cada** chamada ao controlador ela (a) executa os efeitos na ordem, (b) compara o estado antes e depois para suspender ou retomar os atalhos e ligar ou desligar o relógio, (c) devolve se a tecla foi consumida. Cada efeito tem **um** tratamento; um teste percorre as 17 classes de efeito do T2 e falha se uma não tiver.

A `Porta` tem métodos de leitura (`linha_atual`, `linhas_selecionadas`, `texto_do_editor`) e de ação (`marcar`, `desmarcar`, `abrir_texto`, `abrir_aplicativo`, `fechar_editor`, `propor_tecla`, `bip`, `aplicar_alvo`, `aplicar_texto`, `aplicar_tempo`, `aplicar_espera`, `dica`, `mostrar_valor`, `abrir_barra_lateral`, `editar_celula`, `suspender_atalhos`, `ligar_relogio`). As quatro `aplicar_*` devolvem `Resultado(ok, mensagem)`.

## 5. De evento do Qt para tecla (T3-10)

| Evento | `nome` | Observação |
|---|---|---|
| `Key_A`…`Key_Z`; `Key_Ccedilla` | "A"…"Z"; "Ç" | |
| `Key_0`…`Key_9` | "0"…"9" | com Shift/AltGr o Qt entrega símbolo: vale o código virtual (0x30 a 0x39) quando existir |
| `Key_F1`…`Key_F24` | "F1"…"F24" | |
| `Key_Escape`, `Key_Tab`/`Key_Backtab`, `Key_CapsLock`, `Key_Shift`, `Key_Control`, `Key_Alt`, `Key_AltGr` | "ESC", "TAB", "CAPSLOCK", "SHIFT", "CTRL", "ALT", "ALTGR" | |
| `Key_Return`; `Key_Enter` (numérico) | "ENTER"; "ENTER" (navegação) ou "NUMENTER" (captura) | |
| `Key_Backspace`, `Key_Space`, `Key_Meta`, `Key_Menu` | "BACKSPACE", "SPACE", "WIN", "MENU" | |
| `Key_Insert`, `Key_Home`, `Key_PageUp`, `Key_Delete`, `Key_End`, `Key_PageDown` | "INSERT", "HOME", "PAGEUP", "DELETE", "END", "PAGEDOWN" | |
| `Key_Up`, `Key_Down`, `Key_Left`, `Key_Right` | "UP", "DOWN", "LEFT", "RIGHT" | com ou sem o modificador numérico |
| `Key_Print`, `Key_ScrollLock`, `Key_Pause`, `Key_NumLock` | "PRINTSCREEN", "SCROLLLOCK", "PAUSE", "NUMLOCK" | |
| Teclado numérico (só na captura): `Key_0`…`Key_9`, `Key_Slash`, `Key_Asterisk`, `Key_Minus`, `Key_Plus`, `Key_Period`/`Key_Comma` | "NUM0"…"NUM9", "NUM/", "NUM*", "NUM-", "NUM+", "NUM." | o ponto decimal vem como vírgula em layouts brasileiros |
| Qualquer outra | "" | pontuação, acentos mortos, mídia |

Total de nomes que a captura pode produzir: **103** (26 letras + Ç, 10 dígitos, 24 F, 26 nomeadas, 16 do teclado numérico). Todos precisam estar em `Win32InputBackend._vk` (teste).

## 6. Como se prova

**Aqui, sem Qt** (com `JanelaFalsa`, relógio falso, mapas reais como acessório fixo):

- `test_teclado_aplicar.py`: as seis gravações, as regras do `wait_process`, a conferência de índice, `id` e tipo, a **simetria com a barra lateral** (mesmo comando editado pelos dois caminhos dá o mesmo resultado), `validate()` sem erro novo e os 3 mapas reais.
- `test_teclado_teclas.py`: cada nome da seção 5, o cruzamento com `_key_options` e com `_vk`, as 103, o código virtual, o numérico só na captura.
- `test_teclado_ligacao.py`: os fluxos do pedido de ponta a ponta com porta falsa (tecla com bip e confirmação; texto; programa; botão; Enter duplo; `'`; segurar a seta; descartar pelos oito caminhos), a ordem dos efeitos, **suspensão e relógio decididos pelo estado**, repetição do sistema, várias linhas selecionadas, exceção dentro de um efeito, e cada classe de efeito tratada.
- `test_hotkeys_suspensao.py`: o gerenciador de verdade com o `FakeMonitor`: não dispara suspenso, controle segue valendo, combinação que se completa suspensa não dispara na retomada, volta ao normal ao soltar, `registrar_plano` marca só os mapas.
- `tests/static/test_ligacao_teclado.py`: `MainWindow` cria `self.teclado`, o Esc cede, `command_editor.py` tem `editar_celula_atual`, o filtro é instalado na tabela.
- Mutantes novos (área `teclado`/`ligacao`) e a catraca de cobertura.

**No Actions, com Qt de verdade** (`tests/gui/test_teclado_janela.py`, `QTest.keyClick`, marcadores `gui` e `isolado`): Enter na linha de tecla abre a captura e a barra de status muda; tecla + a mesma de novo grava e o histórico ganha um passo "Editar tecla" que o Ctrl+Z desfaz; texto no editor em linha (Enter confirma, Esc cancela, o campo de texto recebe as letras e a tabela não); janela do programa abre sem laço aninhado e grava; Enter duplo vai ao tempo; ← → mudam o valor; `'` abre a espera e os seguintes se movem; F2 abre o editor de célula; Shift+Enter emite o pedido da barra lateral; Esc **não** volta de página durante a edição e volta fora dela; a marca aparece sobre a linha e some; trocar a seleção descarta; os 3 mapas reais.

## 7. O que o T3a não prova (vai para o roteiro do T6)

O **som** do bip (depende do esquema de sons do Windows), a **sensação** de segurar a seta com a repetição de tecla do dono, a **aparência** da marca e do editor em linha com o tema e com a escala de tela do Windows, layouts com **acento morto** (o `'` pode não chegar como caractere), teclado numérico e teclas F13 a F24 reais, e o foco ao voltar de outra janela.

## 8. Arquivos compartilhados que o T3a toca (e como)

- `command_editor.py`: só **extrai** `editar_celula_atual()` do ramo do Enter (comportamento igual) e o Enter passa a chamá-lo.
- `main_window.py`: cria `self.teclado` e cede o Esc (duas pequenas mudanças).
- `input_system.py` e `ativacao.py`: `suspensivel`, `suspender`, `retomar` e a marca em `registrar_plano` (só somam; o padrão `suspensivel=False` deixa todo o resto igual).

## 9. Correção do T2 (registrada aqui porque o T2 já está publicado)

Os registros do T2 (`FICHA_TECLADO_T2`, decisão T2-9 e seção 9, item 2; `ENTREGA_TECLADO_T2`, seção 5, item 8) e comentários do código justificam consumir o que o controlador não usa nos ajustes dizendo que "a tabela abriria um editor de célula a cada letra digitada". **Isso está errado**: a tabela tem `NoEditTriggers`, e uma letra não abre editor. O motivo verdadeiro, lido agora no `QAbstractItemView`, é que, sem consumir, a tabela **moveria a linha atual** (↑ ↓, Home, End, PageUp, PageDown), faria a **busca por letra digitada** e trataria o Espaço. A regra do código está certa e os testes continuam valendo; só a explicação muda. A correção entra no primeiro commit do T3a.
