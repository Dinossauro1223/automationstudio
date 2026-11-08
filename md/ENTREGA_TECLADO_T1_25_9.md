# Teclado em primeiro lugar, ponto T1: atalhos de automação que não colidem com o Windows e nomes de tecla confiáveis (versão 25.9, nova)

Frente de funções, 07 e 08/11/2026. Ramo `funcoes/teclado-atalhos`, empilhado sobre `funcoes/robustez-motor` (c6dcfc2). É o primeiro dos seis pontos em que `md/ESPEC_TECLADO_25_9.md` divide o pedido do dono de 07/11 ("usar o programa todo pelo teclado"): o ponto que **não depende da janela** e já resolve o risco mais caro do pedido, o de uma automação ser colada numa tecla que o Windows ou o navegador também usam, e conserta os nomes de tecla que o monitor entrega (F13 a F24; letras e números com Ctrl, Shift ou Alt apertados). **T2 a T6 não foram construídos e nada aqui os apresenta como disponíveis**: navegar a lista com as setas, Enter para marcar, a captura da tecla com o bip, os tempos com a seta, o Tab e o perfil do mouse continuam só na especificação.

Marcação de versão: os dois commits de função são `Versão: 25.9 (nova)` (a automação nova nasce em outra tecla, teclas passam a ser recusadas ou avisadas, F13 a F24 passam a existir); os de documentos são `25.8 (em aberto)`. `APP_VERSION` continua `"25.6"`: só o dono fecha versão.

## 1. O que muda para quem usa

Quase tudo acontece na hora de **escolher** a tecla de uma automação. O que já está salvo continua funcionando como estava.

| Situação | Antes | Agora |
|---|---|---|
| Criar uma automação nova (botão de novo mapa) | Nasce com a tecla `=`. A tela diz "Tecla para iniciar/parar: =", mas o monitor não entrega símbolos e a tecla **nunca dispara** (achado A1); só o botão ▶ Executar funciona. | Nasce com a primeira combinação livre de `Ctrl+Shift+Alt+1`, `+2` … `+9`, `+0`, depois `+F1` a `+F12` e `+A` a `+Z` (48 ao todo; contam as teclas de todas as automações, ativas ou não, e as dos atalhos de controle). Só se as 48 estiverem em uso sobra o `=`. |
| A automação de demonstração do primeiro uso | Tecla `=`; o diálogo do fim da demonstração também vinha com `=`. | Nasce em `Ctrl+Shift+Alt+1`; o diálogo do fim vem preenchido com a sugestão e a tecla escolhida passa pela mesma regra (se for recusada, fica a da demonstração). |
| Trocar a tecla de uma automação ("Como iniciar/parar esta automação") | Valia qualquer combinação que o programa consegue ler (inclusive `=`, que nunca dispara), menos uma já ocupada por outra automação ativa ou por um atalho de controle. | **Recusa** a tecla que dispararia junto com algo que o Windows, o navegador ou a digitação já usam (`Ctrl+T`, `Alt+F4`, `Win+D`, `F5`, `A`, `Enter`, botão esquerdo do mouse sozinho…). A mensagem diz o motivo, qual tecla a automação continua usando e a próxima combinação livre. **Avisa, sem recusar**: dois modificadores (`Ctrl+Shift+F9`), botão lateral do mouse sozinho (os navegadores o usam como Voltar e Avançar), Pause e Scroll Lock. **Livres**: `Ctrl+Shift+Alt+tecla`, F13 a F24 e os botões laterais com modificador. |
| A pergunta da tecla | Vinha com a tecla atual (ou `=`); a resposta em branco virava `=`. | Vem com a tecla atual ou com a sugestão; em branco, diz "Nenhuma tecla foi digitada" e mantém a atual. |
| Automação que já existe com uma tecla que a regra recusaria (`Ctrl+T`, `F6`, botão esquerdo) | Funciona. | **Continua funcionando**, sem aviso: salvar sem mexer na tecla (ou com ela escrita de outro jeito, `ctrl+t` em vez de `CTRL+T`) nunca é bloqueado. A regra vale quando a tecla é **trocada**. |
| Automação que já existe com a tecla `=` (todo mapa criado até a 25.8; entre os três mapas reais de teste, o "Exemplo — Primeira automação") | Mostra "Tecla para iniciar/parar: =" e a tecla nunca dispara, sem nada que avise. | Funciona como antes (continua sem disparar), mas a faixa do mapa diz que a tecla não é reconhecida, sugere outra e lembra que o ▶ Executar funciona; o rótulo da tecla ganha "(com aviso)". É o **único** alerta permanente (D12b): só para a tecla que nunca dispara. |
| Teclas F13 a F24 (teclados e mouses de muitos botões) | O monitor as descartava (a tabela de nomes ia até F12): não valiam como atalho nem eram gravadas. | São lidas, valem como atalho de automação e como tecla gravada, e o `SendInput` do Windows as reproduz (códigos 0x7C a 0x87). O fallback pynput envia F13 a F20 e **recusa** F21 a F24 com erro claro (o pynput só garante até F20): nunca envia outra tecla no lugar. |
| Letra ou número com Ctrl, Shift ou Alt apertados (hipótese A3) | Se o pynput entrega o caractere alterado (um caractere de controle com Ctrl, `!` no lugar de `1` com Shift), a tecla era descartada: `Ctrl+Shift+Alt+1` não seria reconhecida como atalho. | Sem caractere que sirva, a tecla é a física, pelo código virtual (só 0 a 9, A a Z e F1 a F24). Quando o caractere já serve, nada muda. **Efeito colateral**: o gravador passa a registrar `Shift+1` e `Ctrl+A` pela tecla física (antes ficavam sem a tecla). |

## 2. Como cada achado foi provado

Os achados vêm da leitura do código e de execução em cópia de teste. **Nenhum foi observado no Windows**; a coluna de confiança está na seção 3 da especificação.

**2.1. A1: o `=` nunca dispara.** `key_to_name` devolvia vazio para qualquer símbolo, o monitor descarta o evento de nome vazio e o gerente de atalhos só vê o que o monitor entrega; um `=` registrado não dispara com nenhum evento possível. Não corrigi de propósito: se o `=` passasse a funcionar, todo mapa antigo com a tecla padrão começaria a rodar a cada `=` digitado em qualquer programa. A saída foi trocar o padrão dos mapas **novos** (D11) e avisar nos antigos (D12b).

**2.2. A2: F13 a F24 descartadas.** Primeiro os testes, contra o código antigo: em `tests/engine/test_monitor.py`, **46 passavam e 51 falhavam** (12 de F13 a F24 pelo nome do pynput, 24 de F1 a F24 só pelo código virtual, 10 de letra ou número com o caractere alterado e 5 testes isolados: o código virtual só vale quando o pynput não deu nome à tecla; o monitor entrega F13 e a letra com o caractere alterado aos observadores; `Ctrl+Shift+Alt+1` dispara com o caractere alterado; F13 e `Ctrl+F24` disparam; o gravador grava F13 e o motor reproduz a mesma tecla). Os 46 que já passavam são os antigos e os que protegem o que funcionava, de propósito (o caractere utilizável vence o código virtual, mesmo que ele discorde; o que o Studio não modela continua ignorado). Depois da correção, todos passam.

**2.3. A3: o caractere alterado.** A documentação do pynput trata o `canonical()` como o meio de tirar o estado dos modificadores dos eventos de tecla (não reli o texto exato nesta rodada), o que indica que o `char` reflete os modificadores. É **hipótese** (confiança média): se for assim, o atalho que o dono pediu como padrão não seria reconhecido; se não for, a correção é inofensiva. O nome sai do `char` quando ele serve, como sempre, e do código virtual só quando não serve (`_name_from_vk`: 0x30 a 0x39, 0x41 a 0x5A e 0x70 a 0x87; qualquer outra coisa, inclusive um valor que não é inteiro, não tem nome e é ignorada).

**2.4. A5: o gerente dispara por subconjunto.** `GlobalHotkeyManager` dispara quando `combinação <= teclas apertadas`: uma automação em `1` também dispara com `Ctrl+Shift+Alt+1` apertada. A conferência de conflito da 25.8 compara combinações **iguais** e não vê isso. Nesta entrega só a **sugestão** respeita o subconjunto (ela nunca oferece uma combinação que dispararia junto com uma em uso); o conflito segue como está (backlog).

**2.5. As regras.** `atalhos_reservados.avaliar(tecla, usadas)` devolve `livre`, `aviso` ou `recusada`, com o motivo e, na recusa, a sugestão. Nove regras em ordem (o primeiro item que se aplica decide; a lista completa está na seção 5.3 da especificação): entrada que não é tecla; parte que o monitor nunca produz (`=`, `CRTL`); só modificadores; com Win; combinação do catálogo (51), comparada por **igualdade**; tecla sozinha ou só com Shift; F13 a F24; Ctrl, Alt ou AltGr com tecla; botões laterais do mouse. Amostra do que sai (rodada em cópia de teste):

| Tecla | Nível | Regra | Motivo |
|---|---|---|---|
| `CTRL+SHIFT+ALT+1` | livre | `livre` | |
| `CTRL+SHIFT+ALT+T` | livre | `livre` | (não colide com `Ctrl+T`: o catálogo é por igualdade) |
| `F13`, `CTRL+F24` | livre | `f13_f24` | |
| `CTRL+T` | recusada | `catalogo` | abre uma nova aba do navegador |
| `CTRL+SHIFT+ESC` | recusada | `catalogo` | abre o Gerenciador de Tarefas |
| `WIN+D` | recusada | `win` | usa a tecla Windows, que o próprio Windows usa para os atalhos dele |
| `F5`, `F8` | recusada | `f1_f12` | usa uma das teclas F1 a F12 sem modificador |
| `A`, `ENTER` | recusada | `digitar` | é uma tecla de digitar ou navegar: a automação começaria sempre que ela fosse usada |
| `MOUSE_LEFT` | recusada | `mouse` | usa um botão principal do mouse, que é clicado o tempo todo |
| `CTRL+ALT+A` | recusada | `altgr` | usa Ctrl+Alt, que é o AltGr: em alguns teclados (como o ABNT2) isso digita caracteres |
| `=`, `CTRL+SHIFT+ALT+=` | recusada | `desconhecida` | o programa ainda não reconhece símbolos e pontuação como tecla de atalho |
| `CRTL+1` | recusada | `desconhecida` | "CRTL" não é reconhecida (confira a escrita) |
| `CTRL+SHIFT+ALT` | recusada | `sem_tecla` | só tem teclas modificadoras |
| `MOUSE_X1` | aviso | `lateral` | os navegadores usam o botão lateral como Voltar e Avançar |
| `PAUSE` | aviso | `isolada` | é usada por alguns programas e jogos (pausa) |

Exemplo da mensagem de recusa, trocando a tecla do 'Click genshin' (hoje em `MOUSE_X1`) para `CTRL+T`: "A tecla “CTRL+T” não foi aceita para “Click genshin” porque abre uma nova aba do navegador. A tecla de “Click genshin” continua “MOUSE_X1”. Sugestão: CTRL+SHIFT+ALT+2."

## 3. O que mudou no código

- `automationstudio/atalhos_reservados.py` (**novo**, lógica sem janelas): `avaliar`, `sugerir` (série de 48 combinações, pulando o que dispararia junto com uma em uso), `CATALOGO` (51 combinações do Windows e dos navegadores, cada uma com o que faz) e o resultado imutável `Avaliacao(nivel, regra, motivo, sugestao)`. Nunca levanta: o que não é tecla é recusado como `invalida`.
- `automationstudio/core.py` (**arquivo compartilhado**, três trechos pequenos): `_SPECIAL_KEY_NAMES` vai até F24; `key_to_name` cai em `_name_from_vk` (novo) quando o `char` não serve; um comentário junto do `"="` do modelo, que **não muda** (arquivos e testes antigos ficam idênticos).
- `automationstudio/input_system.py` (uma linha): a tabela de códigos virtuais do `SendInput` vai até F24 (`VK_F13` a `VK_F24` = 0x7C a 0x87).
- `automationstudio/ativacao.py` (lógica sem janelas): `usadas_de`, `recusa_de_reservada`, `aviso_de_reservada`, `alerta_de_tecla`, o campo `Descricao.alerta`, `AtivacaoMapas.sugerir_tecla` e o texto da descrição do mapa com a tecla que nunca dispara.
- `automationstudio/ativacao_ui.py`: `sugerir_tecla`; `validar_tecla` confere a regra depois da conferência de tecla ocupada; `mudar_tecla` mostra o aviso na barra de status (12 s) e a tecla vale; o rótulo ganha "(com aviso)".
- `automationstudio/main_window.py` (**arquivo compartilhado**, 4 pontos, 10 linhas a mais e 7 a menos): a demonstração e o mapa novo nascem com a sugestão; a tecla escolhida no fim da demonstração passa por `mudar_tecla`; a pergunta da tecla vem preenchida e vazio não vira `=`. Nenhuma linha de layout, estilo ou widget.

## 4. Testes e números

Cada número abaixo vem de uma cópia limpa do próprio commit.

| Árvore | Dublê de lógica | Dublê de widgets | Pulados (lógica / widgets) | Defeitos plantados |
|---|---|---|---|---|
| Base `c6dcfc2` | 1730 | 1989 | 344 / 85 | 426 |
| Commit 1 `6609453`: nomes de tecla do monitor e do SendInput | 1817 | 2088 | 356 / 85 | 433 |
| Commit 2 `864d20a`: regras, catálogo e ligação na janela | 2111 | 2384 | 362 / 89 | 478 |

Em todas: 0 falham, 2 xfail esperados, 0 xpass. Na árvore final o pytest 9.1.1 de verdade dá os mesmos números (2111 e 2384 passam, 362 e 89 pulados, 2 xfail). `mutacoes.py --validar`: os 433 e os 478 se aplicam.

Os pulados a mais: no commit 1, 12 casos de um teste que **já existia** (`gui/test_command_dialog.py`, "toda tecla que o gravador produz sobrevive ao abrir no editor"): ele lê a tabela de nomes do monitor, então F13 a F24 entraram sozinhas e passaram a conferir que uma tecla gravada abre no editor sem virar outra. O dublê de lógica os pula; o de widgets **os roda e passa**. No commit 2, testes de `gui/test_ativacao_janela.py` (a janela principal só abre com o Qt de verdade: 4 novos e 1 reescrito) e, no dublê de lógica, 2 de `test_ativacao_painel.py` (o dublê de widgets os roda).

- `tests/unit/test_atalhos_reservados.py` (novo, 45 funções): cada regra, o catálogo inteiro (51), o AltGr, a normalização (caixa, espaços, ordem, apelidos), a sugestão (ordem, o que pular, subconjunto, esgotar as 48) e uma varredura exaustiva de combinações contra invariantes (nenhuma combinação só de modificadores é livre, nada com Win é livre, toda sugestão é livre pelas próprias regras).
- `tests/engine/test_monitor.py` (+10 funções, seção 2.2), `tests/contract/test_backend_win32.py` (F13 a F24 nos códigos 0x7C a 0x87), `tests/contract/test_backend_pynput.py` (F13 e F20 traduzidas; F21 a F24 recusadas e nunca viram outra tecla), `tests/testsupport/fakes.py` (o `Key` falso do pynput passa a ter F1 a F20, como o de verdade).
- `tests/unit/test_ativacao.py` (+14) e `tests/unit/test_ativacao_controlador.py` (+13, 1 reescrito): a regra só na troca, a tecla que o mapa já tem nunca recusada (nem escrita de outro jeito), o aviso só quando a tecla muda, o alerta só para a que nunca dispara, a sugestão contando as teclas de todos os mapas e dos atalhos de controle.
- `tests/gui/test_ativacao_painel.py` (+2) e `tests/gui/test_ativacao_janela.py` (4 novos e 1 reescrito, inclusive a resposta em branco): os da janela rodam de verdade **só com o Qt real** (seção 8) e os do painel também com o dublê de widgets. `tests/static/test_ligacao_ativacao.py` confere que quatro métodos da janela chamam o controlador (a sugestão e a validação) e que duas rotas, as Configurações da automação e o fim da demonstração, não atribuem `.hotkey` direto.
- **Defeitos plantados** (`tests/testsupport/mutacoes.py`): 52 novos (426 para 478): `TEC01` a `TEC29` (área nova `teclas`: cada regra, a sugestão e os nomes de tecla), `ATV63` a `ATV84` (a ligação na ativação, no controlador e na janela) e `W3223` (a tabela do Win32 voltar a F12). Mudaram de forma com o código novo: `W3218`, `ATV34`, `ATV35`. Os 55 (52 novos e 3 reescritos) rodaram contra a suíte inteira e o código final: **55 mortos, 0 sobreviventes, 0 inválidos**, em 9,7 min (`--paralelo 2`); os 8 do commit 1 também rodaram contra a árvore do próprio commit: 8 mortos em 1,6 min. Rodei também os 147 defeitos das áreas que o código tocou (`ativacao`, `win32`, `gravador`, `atalhos`, `botoes`, `pynput`, `estatico` e `controle`) contra a árvore do commit 2: **147 mortos, 0 sobreviventes, 0 inválidos**, em 24 min. Somando, 202 dos 478 foram rodados na árvore final; os 276 restantes (`redes`, `modelo`, `motor`, `editor` e `persistencia`) são de áreas que este ramo não tocou e **não foram refeitos** (a rodada inteira leva cerca de 1 h 25 min).
- Um deles, o `TEC19` (a sugestão que repete sempre a mesma), travava a rodada: o teste da ordem das sugestões tinha um laço sem fim. O laço ganhou limite e o defeito agora é morto em menos de um minuto, pelo teste que o mira.

## 5. Decisões (você pode vetar qualquer uma)

1. **O catálogo é comparado por igualdade (D10).** `Ctrl+Shift+Alt+T` não é `Ctrl+T`. Recusar tudo o que *contém* um atalho conhecido recusaria o padrão que você pediu (o defeito `TEC02` planta exatamente isso). A garantia de que nada colide vem de usar três modificadores, que quase nenhum programa usa; o catálogo é uma lista curada (Windows e navegadores, como você pediu), **não exaustiva**: atalhos de um programa específico fora dela não são conhecidos.
2. **O padrão do modelo não muda (D11).** `AutomationMap.hotkey = "="` fica; só o mapa novo criado pela tela e a demonstração recebem a sugestão. Mudar o padrão do modelo mexeria no que um arquivo sem tecla significa.
3. **O mapa antigo continua funcionando e só a troca passa pela regra (D12).** A comparação é de combinação, não de texto. O alerta permanente é só para a tecla que nunca dispara (D12b): `F6` ou `Ctrl+T` num mapa antigo funcionam e podem ter sido escolhidos de propósito; avisar a cada abertura seria barulho.
4. **Os atalhos de controle (F8 a F12) ficam como estão (D13).** A regra vale para as automações; a mesma regra recusaria as teclas de controle de hoje. Elas entram na conta da sugestão.
5. **Botões do mouse (D14, D14b).** Esquerdo, direito e do meio, sozinhos ou só com Shift, são recusados (clicam o tempo todo, até nos cliques que a própria automação faz). **Consequência a conhecer**: o diálogo "Como iniciar/parar esta automação" ainda lista esses três; escolhê-los agora devolve a recusa com o motivo, e a tecla anterior fica. Um mapa antigo que já usa um deles continua funcionando. O diálogo será refeito no T5 (perfil do mouse). Os laterais X1 e X2 sozinhos valem com aviso. Com Ctrl ou Alt valem as regras dos modificadores (um só é recusado, dois dão aviso, três são livres).
6. **A resposta em branco deixa de virar `=`.** Era a única rota que gravava uma tecla que a regra recusa. Agora diz "Nenhuma tecla foi digitada" e mantém a atual.
7. **No fallback pynput, F21 a F24 são recusadas em vez de aproximadas.** Enviar outra tecla no lugar executaria algo que ninguém gravou. Só o `SendInput` do Windows (o backend de produção) as envia.
8. **O efeito colateral no gravador é aceito** (seção 1, última linha): gravar `Shift+1` e `Ctrl+A` pela tecla física é o que se espera de um gravador e é o preço da correção do A3.
9. **Versão 25.9 (nova)** nos commits de função (percepção do usuário e comportamento novo). Se preferir contar como correção da 25.8, é só o changelog tratar assim: a marcação está nos commits, que já foram publicados e não serão reescritos.

## 6. Por que o ramo está empilhado

Como os da rodada anterior: o catálogo de defeitos (`mutacoes.py`) e a contagem do `tests/README.md` mudam em todos os ramos. Na `main` entra assim: este ramo já **contém**, nesta ordem, `funcoes/pausar-continuar-teclas`, `funcoes/validacao-lacunas`, `funcoes/robustez-modelo` e `funcoes/robustez-motor`; `funcoes/plano-25-7` (só documentos) é independente e os dois ramos novos de outra sessão (`funcoes/desativar-comandos`, F49, e `funcoes/executar-a-partir-daqui`, F50) também. Juntar este primeiro leva os quatro junto; juntando em ordem, cada um entra por cima do anterior. Testei por `git merge-tree` que este ramo se junta **sem conflito** a cada um dos dois ramos novos (eles mexem em `command_editor.py`, em `core.py` e no catálogo de funções, e o T3 vai mexer na tabela de comandos de novo: lá o conflito é provável). Entre os ramos empilhados, os conflitos esperados são só do catálogo de defeitos e do README (trechos de contagem).

## 7. O que ainda aguarda o Windows do dono

- **`Ctrl+Shift+Alt+1` de verdade.** A prova daqui usa o monitor e o gerente com eventos falsos (inclusive com o `char` alterado). Falta ver, no seu teclado, a tecla acender no teclado virtual e a automação iniciar. No ABNT2, o Alt da **direita** é o AltGr (chega como `ALTGR` e como Ctrl falso); use o Alt da **esquerda**. Se o AltGr aparecer, a regra `altgr` recusa `Ctrl+Alt+letra`, mas `Ctrl+Shift+Alt+1` só se confirma com o seu teclado.
- **A3 é hipótese.** Se o `char` já chega certo com os modificadores apertados, a correção do código virtual é inofensiva; se chega alterado, é o que faz o padrão funcionar.
- **F13 a F24 de verdade.** Os testes provam a tradução (nome e código virtual) e o contrato do backend com um `user32` de mentira; se o teclado ou o mouse do dono as envia, e se a janela de destino as recebe, só o Windows mostra.
- **A tela.** Os testes da janela rodaram com o Qt real no Actions e passaram (seção 8). O que o Actions não vê é como fica na sua tela: a mensagem de recusa, o aviso na barra de status por 12 s, a faixa do mapa com a tecla que não dispara e o "(com aviso)" no rótulo, e se o texto cabe e se lê bem.
- **O catálogo de 51 combinações é conhecimento meu sobre o Windows e os navegadores**, não uma medição: se uma combinação listada não faz o que o motivo diz na sua versão, a entrada é uma linha para trocar.

## 8. Resultado do Actions

**GitHub Actions** (Qt de verdade, PySide6 6.12.0), execução 42528564756, disparada à mão no commit `864d20a` (a ponta do ramo na hora; a árvore de código é a dos commits 1 e 2, e os demais só alteram documentos) em 08/11/2026:
- **Linux** (Python 3.14.10, pytest 9.2.0): passo comum com **2413 passam, 11 pulados, 3 xfail** (48 s); janela principal, um processo por teste, **48 de 48**; sucesso.
- **Windows** (Python 3.14.10, informativo): passo comum com **2412 passam, 12 pulados, 3 xfail** (76 s); janela principal **48 de 48**; sucesso.
- Em relação à execução do ramo anterior (`funcoes/robustez-motor`: Linux 2018 e 44 da janela, Windows 2017 e 44, 3 xfail nas duas), os passam sobem **395 no passo comum e 4 na janela** (399 ao todo, nos dois sistemas). É a conta exata: os 395 são o aumento do dublê de widgets local (1989 para 2384) e os 4 são os testes novos da janela principal, que o dublê pula e o Qt de verdade roda. Os **pulados não mudaram** (11 e 12): nenhum teste novo foi pulado. Os 3 xfail são os mesmos de antes.
- Rodaram de verdade, com o Qt real, os 5 testes novos ou reescritos de `tests/gui/test_ativacao_janela.py` (a sugestão no mapa novo e a seguinte, a recusa na configuração, a resposta em branco, a pergunta da tecla, o botão lateral com aviso) e os dois de `tests/gui/test_funcoes_acessiveis.py` (o catálogo de funções e a lista de controles da janela continuam batendo). Os 12 casos F13 a F24 do teste do editor entram na mesma conta e não aparecem como pulados.
- A diferença de um teste entre Linux e Windows (2413 contra 2412, 11 contra 12 pulados) já existia: é `tests/unit/test_e2e_ambientes.py`.

## 9. Para a integração

- **Arquivos compartilhados tocados**: `automationstudio/core.py` (três trechos pequenos) e `automationstudio/main_window.py` (quatro pontos, 10 linhas a mais e 7 a menos; a demonstração, o mapa novo, a pergunta da tecla e o fim da demonstração). Nada de visual. Se a frente visual mexeu nesses trechos (por exemplo no tutorial), a resolução é manter as duas mudanças.
- Arquivos: `automationstudio/atalhos_reservados.py` (novo), `ativacao.py`, `ativacao_ui.py`, `core.py`, `input_system.py`, `main_window.py`; `tests/unit/test_atalhos_reservados.py` (novo), `tests/unit/test_ativacao.py`, `tests/unit/test_ativacao_controlador.py`, `tests/unit/test_mutacoes.py`, `tests/engine/test_monitor.py`, `tests/contract/test_backend_win32.py`, `tests/contract/test_backend_pynput.py`, `tests/gui/test_ativacao_painel.py`, `tests/gui/test_ativacao_janela.py`, `tests/static/test_ligacao_ativacao.py`, `tests/testsupport/fakes.py`, `tests/testsupport/catraca_cobertura.py`, `tests/testsupport/mutacoes.py`, `tests/README.md`; `md/ESPEC_TECLADO_25_9.md` e este documento.
- O catálogo de funções do usuário (`tests/testsupport/funcoes_do_usuario.py`) **não mudou**: nenhum controle foi criado, movido ou removido (só o texto de dois diálogos).
- Para o changelog da 25.9: "uma automação nova nasce com `Ctrl+Shift+Alt+1` (e as seguintes com 2, 3…) em vez de `=`, que nunca disparava; teclas que colidem com atalhos do Windows ou do navegador são recusadas ao trocar a tecla de uma automação, com o motivo e uma sugestão; as teclas F13 a F24 passam a valer como atalho, e o gravador reconhece letras e números pela tecla física."
- Fica no backlog da especificação (seção 8): símbolos como tecla (A4), conflito por subconjunto (A5), F21 a F24 no fallback pynput, trocar os atalhos de controle (D13).
