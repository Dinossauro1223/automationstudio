# Teclado em primeiro lugar, ponto T2: o controlador da edição pelo teclado, a curva da seta segurada e a espera entre comandos no modelo (versão 25.8, em aberto)

Frente de funções, 09 e 10/11/2026. Ramo `funcoes/teclado-edicao`, empilhado sobre `funcoes/teclado-atalhos` (980c4cc, o T1). É o segundo dos seis pontos em que `md/ESPEC_TECLADO_25_9.md` divide o pedido do dono de 07/11 ("usar o programa todo pelo teclado"). É **lógica pura, sem janela: nada muda na tela e o programa se comporta exatamente como na 25.8**. O que entra é o que o T3 vai ligar na tabela de comandos: (1) a **espera** entre comandos como operação do modelo, (2) a **curva** da seta segurada e (3) o **controlador** que diz, para cada tecla apertada em cada estado da edição, o que fazer. **O T3 não foi construído e nada aqui o apresenta como disponível**: Enter, setas, `'`, o bip da captura, o seletor de programa e o ajuste do tempo continuam, na janela, como eram.

Marcação de versão: os três commits são `Versão: 25.8 (em aberto)`. Nenhum muda o que o usuário vê (o modelo ganha três métodos que nada na janela chama ainda; o controlador não tem quem o chame; o resto é teste e documento). `APP_VERSION` continua `"25.6"`: só o dono fecha versão.

## 1. O que muda para quem usa

**Nada, ainda.** O que fica pronto é o comportamento que o T3 vai pôr na janela. Está aqui para você poder vetar uma decisão **antes** de ela virar tela (as decisões estão na seção 5, e a ficha `md/FICHA_TECLADO_T2_25_9.md` tem a tabela completa):

| Estado | Teclas | O que fazem |
|---|---|---|
| Navegando (nada em edição) | `Enter` | Edita o conteúdo do comando da linha: tecla → captura; texto → editor; programa → seletor; botão do mouse → troca com ← →; mover, rolar e esperar não têm conteúdo simples: o Enter só mostra a dica de que os detalhes estão na barra lateral (`Shift+Enter`). |
| | `'` (o apóstrofo, pelo caractere digitado: vale em qualquer layout) | Edita a **espera** antes do comando. |
| | `F2` e `Shift+Enter` | Edita a célula da linha; abre os detalhes na barra lateral. |
| | `Enter`, `Enter` (em até 0,4 s) | Edita o **tempo apertado** (só tecla e botão do mouse de apertar e soltar; nos outros diz por que não). |
| Captura de tecla | qualquer tecla | A primeira vira **proposta** (com o bip); a **mesma** de novo confirma; outra troca a proposta. `Esc` cancela; `Shift+Esc` grava a própria Esc. |
| Texto | `Enter` / `Esc` | Confirma (texto vazio é recusado) / cancela. O resto é do editor. |
| Botão do mouse | `←` `→` / `Enter` / `Esc` | Percorrem os botões do modelo e param nas pontas / confirma / cancela. |
| Tempo apertado e espera | `←` `→` | **Um toque muda 0,01 s.** Segurando: os 3 primeiros segundos são lentos (0,1 s de valor por segundo), depois a velocidade dobra a cada 2 s até 60 s por segundo. |
| | `Enter` / `Esc` | Aceita (só aqui o valor vai para o mapa) / descarta. |

Cada estado tem uma **dica** didática (a frase que diz o que as teclas fazem agora) e um teste confere que toda tecla que o estado trata aparece nela.

## 2. Como cada ponto foi provado

**2.1. A espera no modelo.** A espera de um comando é a lacuna **com sinal** entre o fim programado do anterior (início + duração + atraso, o `computed_delay_after`) e o início dele: a mesma lacuna que o `reflow_timeline` já preserva quando se mexe numa duração. Medida nos três mapas reais (o primeiro comando conta a partir do instante 0):

| Mapa real | Comandos | Esperas negativas | Zero | Positivas | Menor / maior | 1º começa em |
|---|---|---|---|---|---|---|
| Click genshin | 8 | 0 | 1 | 7 | 0 / 0,018 s | 0 |
| Exemplo — Primeira automação | 2 | 1 | 1 | 0 | −1,2 s / 0 | 0 |
| Flins combo | 933 | 444 | 0 | 489 | −0,148 s / 1,928 s | 0,7014 s |

Os testes percorrem **cada comando dos três mapas**, e não só amostras: a espera de cada um bate com a conta feita à parte; pôr a espera que ele já tem não muda nada; somar 0,5 s move o comando e **todos os seguintes** exatamente 0,5 s e não toca nos anteriores; o piso (`min_gap_before`) é exatamente o valor em que o comando, ou um seguinte que já começa antes dele, chegaria ao instante 0; abaixo do piso é recusado (`ValueError`) e o mapa fica como estava; `NaN`, infinito e índice fora do mapa (inclusive o negativo, que o Python contaria de trás para frente) são recusados. Um achado do próprio teste: depois de somar 0,5 s e voltar, o início **não volta bit a bit** (ruído de ~5·10⁻¹⁷ do ponto flutuante: o teste compara com tolerância de 10⁻⁹ e o registra; não é defeito do modelo).

**2.2. A curva.** A mudança do valor em função do tempo com a seta apertada (`mudanca_acumulada`) é a integral da velocidade (`velocidade`), e o teste confere isso numericamente em 7 instantes. Pontos da tabela (a ficha, seção 5, tem todos):

| Seta apertada por | 0,3 s ou menos | 1 s | 3 s | 5 s | 7 s | 9 s | 11 s | 15 s | 21,5 s (teto de velocidade) | 30 s | 60 s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| O valor mudou | 0,01 s (um toque) | 0,08 s | 0,28 s | 0,57 s | 1,15 s | 2,30 s | 4,61 s | 18,5 s | 173 s | 686 s | 2486 s |

Sem salto nas emendas (0,3 s, 3 s e 21,5 s); a velocidade só cresce; o valor é arredondado ao milissegundo e preso entre o mínimo (0,01 s no tempo apertado, o piso do modelo na espera) e o teto de uma hora. A curva toda sai de **seis constantes** no topo do módulo (`PASSO_TOQUE`, `LIMITE_TOQUE`, `VELOCIDADE_INICIAL`, `SEGUNDOS_LENTOS`, `DOBRA_A_CADA`, `VELOCIDADE_MAXIMA`), então mudar a sensação é mudar números, sem mexer na lógica.

**2.3. O controlador.** É uma máquina de estados pura: recebe uma tecla abstrata (`Tecla`: nome do Studio, caractere digitado e Ctrl, Shift, Alt) e o instante (`agora`, um argumento: nada aqui dorme nem lê a hora), e devolve uma `Resposta` (se a tecla foi consumida e a lista de efeitos que a janela executa: marcar a linha, abrir o editor, tocar o bip, mostrar o valor, aplicar). Provas que vão além de "o caso feliz funciona":

- **A tabela de teclas de cada estado é exatamente o que o estado faz.** Um teste aperta 396 teclas e combinações (A a Z, 0 a 9, F1 a F24, as teclas de navegação, os modificadores sozinhos, cada uma com Shift, Ctrl, Alt e Ctrl+Shift, mais o apóstrofo e outros sinais) em cada estado e confere que o conjunto das que têm efeito é o declarado em `TECLAS_DO_ESTADO`, nem uma a mais, nem uma a menos; outro confere que cada tecla declarada está escrita na dica do estado.
- **O módulo é puro**: um teste lê a árvore sintática e falha se ele importar Qt, relógio, thread, aleatório, sistema ou subprocesso.
- **Nos três mapas reais**: a ficha de cada comando bate com o modelo; segurar ← na espera de cada comando nunca passa do piso e o modelo **aceita** o valor (`set_gap_before` sem erro); segurar → para no teto de uma hora; segurar ← no tempo de cada tecla ou botão para em 0,01 s.
- **Nada vai para o mapa sem o Enter**, e o Enter sem mudança não grava nada (voltar ao valor do início também conta como não mudar); `Esc`, o foco que sai, a linha que muda ou o mapa que muda por outro caminho descartam (`descartar`).
- **Relógio e seta**: os "tiques" da janela levam ao mesmo valor que soltar de uma vez; a repetição de tecla do sistema é ignorada (a contagem é a do primeiro aperto); trocar de direção conta o que a primeira seta já andou, mesmo sem tique no meio; relógio que anda para trás vale zero segundo.
- **Enter, Enter**: a janela é de 0,4 s **inclusive**; Enter depois de qualquer outra tecla nunca é "duplo"; só vale sem modificadores; só conta a partir do Enter que abriu **esta** edição.
- **Varredura com teclas ao acaso** (a que a especificação prometeu para o T2): em cada um dos três mapas reais (120 sementes nos dois pequenos, 40 no `Flins combo`, 70 passos cada, semente fixa) sorteia teclas que o controlador usa, que engole e que deixa passar, setas soltas, tiques, o seletor de programa respondendo, o foco saindo e a linha mudando, com instantes que só andam para a frente. A cada passo confere que a resposta é bem formada, que estado, linha e valor em edição são coerentes, que o que mexe no mapa só aparece com o Enter, com a mesma tecla de novo na captura ou com a resposta do seletor, e sempre fecha a edição, que o valor nunca sai de [mínimo, máximo] e **que o que o controlador aplica nunca invalida o mapa** (nenhum erro novo em `validate()`, `set_gap_before` aceita a espera, nenhum início cortado no zero). Outro teste confere que a varredura chega aos 7 estados e produz os 17 efeitos, senão ela seria mais fraca do que parece. Ela não achou defeito no controlador; achou um erro do meu teste (esperava valor em milissegundo também no piso do modelo, que é exato, e o ajuste alcança o piso sem arredondar). Com 4 defeitos feitos à mão contra ela sozinha (aceitar sempre aplicar, cancelar sem limpar, ajuste sem piso, aplicar o alvo sem fechar a edição) ela pegou os 4.
- **Defeitos plantados** (seção 4): 102 novos, os 102 pegos, nenhum sobrevivente.

## 3. O que mudou no código

- `automationstudio/core.py` (**arquivo compartilhado**, só acréscimo: 44 linhas depois de `reflow_timeline`, nenhuma linha existente mudou): `AutomationMap.gap_before(i)`, `min_gap_before(i)` e `set_gap_before(i, valor)`, mais o conferidor de índice. Reaproveitam `_gaps_before` e `_retime`, que já existiam, então a espera nova é **a mesma conta** do reflow.
- `automationstudio/teclado_edicao.py` (**novo**, lógica sem janelas e sem Qt): a curva (`velocidade`, `mudanca_acumulada`, `valor_apos`, `formatar_segundos`), a entrada (`Tecla`, `LinhaInfo`, `linha_info_de`), a saída (os efeitos e `Resposta`), as dicas e `EdicaoPorTeclado` (`pressionar`, `soltar`, `tique`, `conteudo_resolvido`, `descartar`).
- `tests/testsupport/catraca_cobertura.py`: grupo novo `teclado` (todo módulo do pacote tem de pertencer a um grupo da catraca de cobertura).
- `md/FICHA_TECLADO_T2_25_9.md` (a ficha de refinamento, escrita antes do código, com a seção 9 "o que mudou da ficha na construção") e este documento.

## 4. Testes e números

Medido em cópia limpa de cada commit (o `pytest` de verdade e o executor mínimo do projeto dão os mesmos números; o dublê de lógica pula os testes que precisam de widgets e o de widgets os roda):

| Árvore | Dublê de lógica | Dublê de widgets | Pulados (lógica e widgets) | Defeitos no catálogo |
|---|---|---|---|---|
| Base: `funcoes/teclado-atalhos` (980c4cc) | 2111 passam | 2384 | 362 e 89 | 478 |
| Commit 1: a espera no modelo | 2167 (+56) | 2440 (+56) | 362 e 89 | 491 |
| Commit 2: o controlador e a curva | 2445 (+334 sobre a base) | 2718 (+334) | 362 e 89 | 580 |
| Commit 3: documentos | 2445 | 2718 | 362 e 89 | 580 |

0 falham em todas, 2 xfail (os de sempre). Os 334 testes novos: 56 do modelo (`test_espera_entre_comandos.py`), 52 da curva (`test_teclado_curva.py`), 222 do controlador (`test_teclado_edicao.py`) e 4 da varredura (`test_teclado_varredura.py`: um por mapa real e o que confere que ela chega a todos os estados e efeitos). São todos de lógica: rodam nos dois dublês e nenhum é pulado. `mutacoes.py --validar`: os 491 do commit 1 e os 580 do commit 2 se aplicam.

**Defeitos plantados: 102 novos, 102 mortos, 0 sobreviventes, 0 inválidos.** `ESP01` a `ESP13` (o modelo: o primeiro comando conta do instante 0, o atraso do anterior entra no fim programado, o sinal, o piso olhando os seguintes e não os anteriores, a recusa de NaN, infinito, índice fora e valor abaixo do piso, o que anda junto) e `TKE01` a `TKE89` (a curva, a ficha da linha, cada estado, as dicas, a chave da tecla). Os 13 do modelo também rodaram sozinhos na árvore do commit 1: 13 de 13 mortos em 2,6 min. Os 102 rodaram numa cópia da árvore final: os 13 do modelo em 2,9 min e os 89 do controlador e da curva em 14,3 min, depois de o ambiente reiniciar no meio e a rodada ser retomada com `--retomar`. Entre essa cópia e a árvore final só mudam texto de docstring e o arquivo novo da varredura, que só acrescenta testes. Antes da rodada, a leitura do catálogo apontou três defeitos que podiam sobreviver (trocar de direção sem tique no meio, o apóstrofo com a seta apertada no valor de hoje, a edição nova começar limpa depois de digitar) e eles ganharam teste; a rodada não teve sobrevivente. **Não refeitos: os 478 anteriores.** Nenhuma linha existente mudou e nenhum teste antigo chama o código novo, então o resultado deles não pode ter mudado; a rodada inteira dos 580 fica para a próxima vez que o catálogo for refeito.

## 5. Decisões (você pode vetar qualquer uma)

1. **O tempo apertado não empurra os comandos seguintes** (D4 da especificação, mantida; T2-12). É o que a célula "Duração" da tabela faz hoje. Consequência: encurtar o tempo de uma tecla aumenta a espera depois dela (os seguintes ficam onde estavam) e alongar pode fazê-la ficar negativa (sobreposição, que o modelo já aceita: 444 dos 933 comandos do `Flins combo` são assim). **Só a espera empurra** (`set_gap_before`).
2. **A espera pode ser negativa e tem piso** (**refina a D4**, que dizia "mínimo 0"; T2-5). `'` edita quanto se espera antes do comando, contado do fim do anterior; negativa quer dizer que ele começa antes do fim do anterior, que é o normal num mapa gravado (no `Flins combo`, 444 dos 933 comandos). Com mínimo 0, a primeira seta apagaria a sobreposição de um comando gravado. O piso é o valor em que o comando, ou um dos seguintes, chegaria ao instante 0: abaixo disso o modelo **recusa**, em vez de cortar o início em silêncio.
3. **`'` no tempo apertado** (refina a D3; T2-1): vale para ir à espera se o valor ainda não mudou e nenhuma seta está apertada; senão é recusado com a dica "aceite com Enter (ou descarte com Esc) o que mudou antes de editar a espera". Nunca se perde nem se grava nada sem o Enter.
4. **Enter, Enter em até 0,4 s edita o tempo** (D1, T2-3). Consequência a conhecer: para gravar a própria tecla Enter num comando, a captura exige esperar 0,4 s antes de apertá-la (antes disso ela é o segundo Enter). O número é uma constante (`JANELA_ENTER_DUPLO`).
5. **`Esc` cancela e `Shift+Esc` grava a Esc** (T2-11). A captura grava qualquer tecla com nome; sem essa exceção a automação nunca poderia apertar Esc pela captura. A dica da captura diz isso.
6. **A curva** (D5, com os números da especificação): um toque 0,01 s; 3 s lentos; dobra a cada 2 s; teto de 60 s por segundo. É a leitura que fiz de "os 3 primeiros segundos bem lentos, depois cada vez mais rápido". **Só a mão diz se está boa** (T3 mais Windows); as seis constantes da curva ficam numa tabela.
7. **Limites** (T2-6): tempo apertado de 0,01 s (o modelo recusa duração 0) a 3600 s; a espera, do piso do modelo a 3600 s; se o comando já passa de uma hora, vale o valor de hoje como teto, para a primeira seta não encolher um valor legítimo. A resolução é de 1 ms. **A hora de teto é minha**: o modelo não tem teto.
8. **Em ajuste, o que o controlador não usa é engolido** (T2-9), menos Ctrl e Alt (que seguem para os atalhos da janela). Sem isso a tabela abriria um editor de célula a cada letra digitada no meio de um ajuste.
9. **A edição usa a ficha da linha de quando abriu** (T2-13): se a tabela atualizar no meio, o que está em edição não muda sozinho.
10. **Texto vazio é recusado** com a dica, e a edição continua; texto igual ao de hoje só desmarca.

## 6. Por que o ramo está empilhado

Como os da rodada anterior: o catálogo de defeitos (`mutacoes.py`) e a contagem do `tests/README.md` mudam em todos os ramos, e este ramo precisa do T1 por baixo (a mesma tabela de nomes de tecla, `atalhos_reservados.py`). Na `main` entra depois do `funcoes/teclado-atalhos`, que já contém, nesta ordem, `funcoes/pausar-continuar-teclas`, `funcoes/validacao-lacunas`, `funcoes/robustez-modelo` e `funcoes/robustez-motor`. Entre os ramos empilhados, os conflitos esperados são só do catálogo de defeitos e do README (trechos de contagem). O único arquivo compartilhado que este ramo toca é o `core.py`, só com acréscimo.

## 7. O que ainda aguarda o Windows do dono

Nada que esta entrega faça é visível, então nada precisa ser testado à mão agora. O que vai depender do Windows quando o T3 ligar o controlador (anotado aqui para não se perder):

- **A sensação da curva** (seção 5, item 6): se a rampa está lenta ou rápida demais só se vê com a seta de verdade na mão.
- **A tecla chegar ao controlador do jeito que ele espera**: o T3 traduz o evento do Qt em `Tecla` e filtra a repetição do sistema; o que o Qt entrega para `Shift`, `Ctrl` e `Alt` sozinhos, para a tecla apóstrofo no ABNT2 e para a repetição se confere com o Qt de verdade e depois no seu teclado. O T2 prova o controlador; não prova a janela.
- **O bip** da captura (o som que o Windows toca) e o aspecto das dicas na barra de status.

## 8. Resultado do Actions

Execução 42927030585 (disparada por `gh workflow run tests.yml` em 10/11/2026) no commit 391aa1e, o commit 2 (o 3 só tem documentos): **verde nos dois trabalhos**.

| Trabalho | Testes comuns | Janela principal, um processo por teste |
|---|---|---|
| Linux (Python 3.14.10, PySide6 6.12.0 de verdade, display virtual) | 2747 passam, 11 pulados, 3 xfail, 0 falham | 48 OK de 48 |
| Windows (informativo) | 2746 passam, 12 pulados, 3 xfail, 0 falham | 48 OK de 48 |

Em relação ao T1 (execução 42528564756: 2413 e 2412 passam), são os 334 testes novos a mais; os pulados não mudaram (11 e 12) e os 3 xfail são os conhecidos (achados 2.03 e 2.04 e o F4 da visão). Esta entrega não tem teste de janela novo: o que o resultado confirma é que o `core.py` acrescentado e o módulo novo não quebram a importação nem a abertura da janela com o Qt de verdade, no Linux e no Windows.

## 9. Para a integração

- **Arquivo compartilhado tocado**: `automationstudio/core.py`, só acréscimo de 44 linhas depois de `reflow_timeline` (três métodos e um conferidor). Nada de `main_window.py`, nada de visual. Se a frente visual ou outra sessão mexeu em `reflow_timeline` e no que vem logo depois, a resolução é manter as duas mudanças.
- Arquivos: `automationstudio/teclado_edicao.py` (novo), `core.py`; `tests/unit/test_espera_entre_comandos.py`, `tests/unit/test_teclado_curva.py`, `tests/unit/test_teclado_edicao.py` e `tests/unit/test_teclado_varredura.py` (novos), `tests/unit/test_mutacoes.py`, `tests/testsupport/catraca_cobertura.py`, `tests/testsupport/mutacoes.py`, `tests/README.md`; `md/ESPEC_TECLADO_25_9.md` (o estado e as refinações da D3 e da D4), `md/FICHA_TECLADO_T2_25_9.md` e este documento.
- **Comandos desativados (F49, ramo `funcoes/desativar-comandos`)**: pelo que a mensagem do commit dele diz, desativar um comando o mantém na lista, no mesmo lugar e com o mesmo horário, e os horários dos outros não mudam. Então a espera daqui continua sendo contada a partir do comando anterior **da lista**, esteja ele desativado ou não (os horários são absolutos). Se for melhor contá-la a partir do anterior **ativado**, é uma decisão do T3, depois que o F49 entrar na `main`.
- O catálogo de funções do usuário (`tests/testsupport/funcoes_do_usuario.py`) **não mudou**: nenhum controle foi criado, movido ou removido (não há controle novo; as teclas só entram com o T3).
- Para o changelog: nada para o usuário nesta entrega. Para o desenvolvimento: "o modelo ganha `gap_before`, `min_gap_before` e `set_gap_before` (a espera entre comandos) e há um controlador da edição pelo teclado sem janela (`teclado_edicao.py`), que o T3 liga à tabela".
- **Para o T3** (o próximo): ele vai mexer em `main_window.py` e na tabela de comandos, e a frente visual e os ramos `funcoes/desativar-comandos` e `funcoes/executar-a-partir-daqui` mexem em arquivos vizinhos; o conflito ali é provável e eu o meço por `git merge-tree` antes de publicar. O T3 também acrescenta um teste estático de ligação (como o `tests/static/test_ligacao_ativacao.py` do T1), porque a catraca de "código sem referência" é textual e o controlador **hoje não tem nenhum chamador**: o que prova que ele está ligado é o teste do T3, não esta entrega.
