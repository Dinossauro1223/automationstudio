# Ficha do ponto T2 do teclado (25.9): o controlador de edição pelo teclado e a curva da seta segurada

Escrita **antes** do código, como combinado na seção 6 de `md/ESPEC_TECLADO_25_9.md`. Fixa o que o T2 entrega, o desenho e os números que os testes vão cobrar. Tudo o que está nas tabelas abaixo vive num lugar só do código e pode ser trocado depois sem refazer a lógica. Ramo: `funcoes/teclado-edicao`, empilhado sobre `funcoes/teclado-atalhos` (T1).

## 1. O que o T2 entrega e o que não entrega

**Entrega**: lógica sem janelas, provada aqui com relógio falso: (a) `automationstudio/teclado_edicao.py`, o estado da edição por teclado, que recebe teclas abstratas e devolve efeitos; (b) a curva da seta segurada (D5); (c) as dicas didáticas de cada estado; (d) a conversão de um comando do mapa na ficha que o controlador lê (`LinhaInfo`); (e) duas operações novas do modelo para a **espera** entre comandos (`AutomationMap.gap_before` e `set_gap_before`), em `core.py`.

**Não entrega**: nenhuma tecla muda na janela. Ligar o controlador à tabela, a captura da tecla com o som, o seletor de aplicativo, Insert, F2, Shift+Enter e a barra de status são o **T3**. Quem usa o programa não percebe nada com o T2; por isso ele é marcado `Versão: 25.8 (em aberto)` (lógica e testes, nenhum comportamento visível). A frase "o programa se usa pelo teclado" só vale depois do T3.

## 2. O que o código de hoje diz (conferido na leitura)

1. A tabela já trata teclas em `command_editor.py` (`eventFilter`, linhas 2562 a 2607): Delete, Ctrl+A/C/X/V/Z/Y, **Enter** (edita a célula atual e, ao confirmar, desce uma linha e edita a próxima) e **Tab** (próxima coluna). O T3 muda o Enter e o Tab (D2); o T2 não mexe nisso.
2. A edição de **duração** na tabela é `cmd.duration = max(0, valor)` para **qualquer** tipo, sem mover os seguintes (`_cell_changed`, coluna 5). Mas a duração só vale (`computed_delay_after`, `effective_end`) quando a ação é `press_and_release`; texto tem duração **calculada** pelo comprimento, abrir aplicativo tem a espera do programa, e `Command.validate` trata duração 0 em tecla ou botão como erro.
3. A **espera** (D4) é a "lacuna" do modelo: `início do comando − (início do anterior + computed_delay_after do anterior)`. **Tem sinal**: negativa é sobreposição, o normal num mapa gravado (comentário em `core.py`, "Reencadeamento dos inícios"). Já existem `_gaps_before` e `_retime`, que refazem os inícios em cascata mantendo as lacunas; falta só uma operação pública que mude **uma** lacuna.
4. Os tipos de comando são `key`, `mouse_button`, `mouse_move`, `mouse_scroll`, `text`, `app_open` e `wait`.

## 3. Decisões do T2 (vetáveis; as de número D vêm da especificação)

| # | Decisão | Por quê |
|---|---|---|
| T2-1 | **Refina a D3.** O apóstrofo (`'`, pelo caractere digitado) edita a **espera** do comando da linha atual quando a lista está em navegação. No ajuste do tempo ele só passa para a espera se o valor **ainda não mudou** e nenhuma seta está apertada; senão é recusado com um aviso ("aceite com Enter ou descarte com Esc"), para nunca perder nem gravar nada sem o Enter. Na espera é engolido. **Nunca** durante a edição do conteúdo (lá ele é um caractere do texto ou uma tecla a capturar). | A D3 dizia "linha marcada", mas o primeiro Enter já abre a edição do conteúdo; o pedido ("a tecla `'` seleciona o comando para editar o cooldown") é uma alternativa ao Enter, não uma etapa depois dele. |
| T2-2 | **Enter** abre a edição do **conteúdo** pelo tipo: `key` captura a tecla; `text` edita o texto; `app_open` escolhe o programa; `mouse_button` escolhe o botão com ← →. Tipos sem conteúdo simples (`mouse_move`, `mouse_scroll`, `wait`): o Enter **não marca**; a dica manda usar Shift+Enter (barra lateral). | O pedido só descreve app, tecla e texto; o botão do mouse completa os comandos de entrada comuns, e o resto tem editor próprio na barra lateral. |
| T2-3 | **Enter de novo em até 0,4 s** do primeiro, sem nenhuma outra tecla no meio, abandona o conteúdo e abre o **tempo** (D1). Depois de 0,4 s, o Enter é do conteúdo (confirma o texto, é a tecla Enter na captura). | Dois Enter rápidos não podem se confundir com "confirmar" nem com "capturar Enter". |
| T2-4 | **O tempo só é editável** em `key` e `mouse_button` com ação `press_and_release` (mínimo 0,01 s, porque 0 é erro do modelo). Nos outros tipos o Enter duplo mostra a razão ("o tempo do texto é calculado pelo comprimento", "o programa define quanto demora para abrir", "só aperta ou só solta") e não muda nada. | Mexer na duração de um comando em que ela não vale seria silencioso e inútil. |
| T2-5 | **Refina a D4.** A espera tem mínimo **igual ao menor valor que mantém o início em 0 ou mais** (`−fim do anterior`; para o primeiro comando, 0), não 0. A dica diz "começa X s antes do fim do anterior" quando é negativa. | Num mapa gravado a lacuna costuma ser negativa; travar em 0 apagaria a sobreposição na primeira seta. |
| T2-6 | O valor em edição só vai para o mapa no **Enter**. Durante o ajuste fica no controlador (a janela mostra na barra de status). Esc, o foco que sai da janela, a linha que muda ou o mapa que muda por outro caminho (`descartar()`) **descartam**. Sem mudança, o Enter não grava nada; ir e voltar ao valor do início (já arredondado ao milissegundo) vale como não mudar. Teto 3600 s (ou o valor de hoje, se ele já passa disso); resolução 1 ms. | Nunca gravar pela metade; o desfazer do editor (Ctrl+Z) já guarda o mapa inteiro a cada alteração. |
| T2-7 | **Toque** (apertar e soltar em menos de 0,3 s) = um passo de 0,01 s, aplicado ao apertar. A rampa só começa depois de 0,3 s segurando e usa o relógio, **não** a repetição de tecla do sistema (que a janela ignora). | Toque exato e preciso; a repetição do sistema varia de máquina para máquina. |
| T2-8 | Só **uma** seta ativa por vez: apertar a outra troca a direção e zera a contagem. ← diminui, → aumenta. | Evita valor que anda sozinho quando as duas estão apertadas. |
| T2-9 | O controlador devolve `consumida`: a tecla que ele não usa naquele estado **volta** para o Qt (texto no editor, setas na navegação, atalhos de Ctrl). Na captura de tecla ele consome tudo o que tem nome. Nos ajustes (botão, tempo, espera) ele **engole** (consome sem efeito) o que não usa, inclusive ↑ ↓, menos as teclas com Ctrl ou Alt, que seguem para os atalhos da janela. | TEC-08: não atrapalhar quem digita nem quem navega; sem engolir, a tabela abriria um editor de célula a cada letra digitada no meio de um ajuste. |
| T2-10 | Cada estado tem uma **dica** (TEC-09) e um teste confere as duas pontas: o estado faz **exatamente** as teclas da tabela `TECLAS_DO_ESTADO` (testando 396 teclas e combinações) e **cada uma aparece na dica**. | O "didático" vira regra testável, não promessa. |
| T2-11 | **Esc cancela; Shift+Esc (ou Ctrl/Alt+Esc) grava a tecla Esc** na captura, e a dica da captura diz isso. O Enter como tecla do comando se grava esperando 0,4 s antes de apertá-lo (T2-3). | Sem isso a automação nunca poderia apertar Esc nem Enter pela captura. |
| T2-12 | **Mantém a D4.** O tempo apertado aplicado **não empurra os comandos seguintes**: é igual a editar a célula "Duração" da tabela (`_cell_changed`). Só a **espera** empurra (`set_gap_before`). | Mantém o que funciona hoje. A D4 já dizia isto; aqui vira regra escrita do controlador. |
| T2-13 | A edição usa a **ficha da linha de quando ela abriu**; o argumento `linha` das teclas seguintes só é lido em navegação. | O que está em edição não muda sozinho se a tabela atualizar no meio. |

## 4. Desenho

Entrada: `Tecla(nome, texto, ctrl, shift, alt)` com `nome` no vocabulário do Studio (`ENTER`, `ESC`, `LEFT`, `RIGHT`, `UP`, `DOWN`, `TAB`, `F2`, `A`…) e `texto` o caractere digitado (para o `'`). Quem converte a tecla do Qt é o T3.

`EdicaoPorTeclado` (sem Qt):

| Método | Faz |
|---|---|
| `pressionar(tecla, agora, linha=None, texto=None)` | `linha` é a ficha da linha atual (só lida em navegação); `texto` é o que está no editor de texto agora (só lido ao confirmar o texto). Devolve `Resposta(consumida, efeitos)`. |
| `soltar(nome, agora)` | Fecha a contagem da seta segurada, com o valor da curva no instante da soltura. |
| `tique(agora)` | Chamado pela janela uns 30 vezes por segundo enquanto há seta segurada; integra a curva. |
| `conteudo_resolvido(valor)` | A janela avisa o resultado do seletor de aplicativo (`None` = cancelou). |
| `descartar()` | O foco saiu, a linha mudou ou o mapa mudou por outro caminho: descarta o que estiver em edição. |

Estados: `NAVEGANDO`, `TECLA`, `TEXTO`, `APLICATIVO`, `BOTAO`, `TEMPO`, `ESPERA`.

Efeitos: `Marcar(linha)`, `IniciarCaptura(linha, atual)`, `ProporTecla(nome)`, `Bip()`, `AbrirTexto(linha, atual)`, `AbrirAplicativo(linha, atual)`, `FecharEditor()` (fecha o editor ou a captura sem aplicar e **mantém a marca**: a edição passa para outro campo), `AplicarAlvo(linha, valor)` (tecla, botão ou programa), `AplicarTexto(linha, texto)`, `AplicarTempo(linha, valor)`, `AplicarEspera(linha, valor)` (a janela chama `AutomationMap.set_gap_before`), `Desmarcar()` (fim da edição **com** o resultado aplicado: fecha tudo e tira a marca), `Cancelar()` (fim **sem** aplicar), `Dica(texto)`, `MostrarValor(texto)`, `AbrirBarraLateral(linha)`, `EditarCelula(linha)`.

| Estado | Teclas que trata | Resultado |
|---|---|---|
| `NAVEGANDO` | Enter; Shift+Enter; F2; `'` | Enter marca e abre o conteúdo pelo tipo (T2-2); Shift+Enter abre a barra lateral; F2 edita a célula; `'` abre a espera. Todo o resto volta para o Qt. |
| `TECLA` | todas | A primeira tecla vira proposta (com `Bip` e dica "aperte X de novo"); a **mesma** de novo confirma (`AplicarAlvo`, `Desmarcar`; a modificadores ignorados); outra tecla troca a proposta; Esc cancela (T2-11); Enter em até 0,4 s do primeiro Enter abre o tempo (ou explica por que não, e a captura continua); tecla sem nome no Studio não vira proposta. |
| `TEXTO` | Enter, Esc | Enter (depois de 0,4 s) confirma (`AplicarTexto`, `Desmarcar`); em até 0,4 s abre o tempo; Esc cancela. O resto é do editor de texto. |
| `APLICATIVO` | (nenhuma) | O seletor é da janela; ao voltar, `conteudo_resolvido` aplica ou cancela. |
| `BOTAO` | ←, →, Enter, Esc | ← → percorrem os botões da lista do modelo e **param nas pontas**; Enter confirma (igual ao de hoje: só desmarca); Esc cancela; Enter duplo abre o tempo. O resto é engolido (T2-9). |
| `TEMPO`, `ESPERA` | ←, →, Enter, Esc, `'` (só no tempo, T2-1) | ← → ajustam (T2-7, T2-8); Enter aceita; Esc descarta. O resto é engolido (T2-9). |

## 5. A curva da seta segurada (D5, constantes numa tabela só)

Com `T` os segundos desde que a seta foi apertada:

- passo do toque: **0,01 s**, aplicado ao apertar;
- se segurou **0,3 s** ou mais, a rampa passa a mudar o valor com a velocidade `v(T)`: **0,1 s por segundo** até `T = 3 s`; depois **dobra a cada 2 s** (`0,1 × 2^((T − 3) / 2)`, contínua) até o teto de **60 s por segundo**, que chega em `T ≈ 21,46 s`;
- a mudança acumulada é `0,01 + (D(T) − D(0,3))`, com `D` a integral de `v`, e o valor é arredondado ao milissegundo e limitado ao mínimo e ao teto de 3600 s.

| Segurando (s) | Velocidade (s por s) | Mudança acumulada (s) |
|---|---|---|
| 0 a 0,29 | 0,1 | 0,01 (só o toque) |
| 1 | 0,1 | 0,08 |
| 3 | 0,1 | 0,28 |
| 5 | 0,2 | 0,57 |
| 7 | 0,4 | 1,15 |
| 9 | 0,8 | 2,30 |
| 11 | 1,6 | 4,61 |
| 15 | 6,4 | 18,46 |
| 21,46 | 60 | 173,11 |
| 30 | 60 | 685,66 |

## 6. As duas operações novas do modelo (`core.py`, só somam)

- `AutomationMap.gap_before(i)`: a lacuna (com sinal) do comando `i`; para o primeiro, o próprio início.
- `AutomationMap.set_gap_before(i, valor)`: muda **só** essa lacuna e refaz os inícios dali em diante por `_retime`; os anteriores não mudam, as lacunas e as durações dos seguintes ficam como estavam; recusa o valor que deixaria o início negativo. Provadas nos três mapas reais, linha por linha.

## 7. Como se prova

- **Curva** (função pura): os valores da tabela, monotonia, o toque, a continuidade em 3 s e no teto, mínimo e teto.
- **Controlador** com relógio falso: cada transição da tabela de estados, o Enter duplo na fronteira dos 0,4 s (0,39 vale, 0,41 não), a captura com confirmação, o texto, o botão, o tempo e a espera com toque e com seta segurada, Esc, foco perdido, `consumida` em todo estado, a dica de cada estado e a regra "toda tecla tratada aparece na dica".
- **Fichas das linhas** (`linha_info_de`): os três mapas reais, todos os comandos; o tempo só em tecla e botão `press_and_release`; a espera igual a `gap_before`.
- **Modelo**: `set_gap_before` com o mesmo valor não muda nada; com mais 0,5 s todos os inícios depois dele andam exatamente 0,5 s e os anteriores ficam; a ordem e as durações não mudam; o mínimo é respeitado.
- **Defeitos plantados**: área nova `teclado` (`TKE01` em diante), cada regra acima.
- **Suítes e Actions**: as duas locais (lógica e widgets), pytest de verdade, e o Actions do ramo.

## 8. O que o T2 não prova

Que a janela entrega as teclas certas ao controlador, o som, o foco, a aparência das dicas e a sensação da curva na mão. Isso é do T3 (Qt de verdade no Actions) e do seu Windows: a curva é a parte que só se aprova **sentindo**; se achar lenta ou rápida, são três números numa tabela.

## 9. O que mudou da ficha na construção (para a conferência)

Escrita antes do código, a ficha foi ajustada em seis pontos quando os testes e a implementação a puseram à prova; o texto acima já é o que foi construído.

1. **`'` no tempo** (T2-1): da primeira versão ("vale no tempo") para "vale se nada mudou, senão é recusado com aviso". A primeira versão descartaria em silêncio um valor ajustado.
2. **Engolir** (T2-9): a primeira versão só engolia ↑ ↓; os testes mostraram que qualquer letra digitada no meio de um ajuste faria o Qt abrir um editor de célula (a tabela tem "qualquer tecla edita"). Agora engole tudo que não usa, menos Ctrl e Alt.
3. **Esc** (T2-11): novo. A captura não tinha como gravar a tecla Esc.
4. **Tempo não empurra** (T2-12): é a D4 da especificação, mantida; só passou a estar escrita também na ficha e no controlador.
5. **Ficha da linha congelada** (T2-13) e **`descartar()`** no lugar de `foco_perdido()` (cobre também a linha e o mapa que mudam).
6. **Valor que já passa do teto** (3600 s): o teto vira o valor de hoje, para a primeira tecla apertada não encolher um valor legítimo.
