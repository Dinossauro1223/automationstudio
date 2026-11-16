# Robustez do motor: o Parar que chega no fim do mapa, o Executar logo depois do Parar e a varredura dos mapas reais (versão 25.8, em aberto)

Frente de funções, 04 a 06/11/2026. Ramo `funcoes/robustez-motor`, empilhado sobre `funcoes/robustez-modelo` (5b84ed2). O motor (`ExecutionEngine`) toca o mapa numa thread própria, e a janela, os atalhos e o botão Parar chamam `run()`, `stop()`, `pause()` e `resume()` de outras threads. Os testes provavam cada chamada isolada e, desde a pausa, a corrida entre `pause()`/`resume()` e o fim da execução. Esta rodada foi atrás do que sobrava nos cruzamentos entre **Parar** e **o fim da execução** e achou três defeitos reais de corrida, todos raríssimos, todos reproduzidos antes de corrigir, mais uma rede de segurança permanente: a **varredura dos mapas reais**, que para, pausa e retoma o motor depois de cada um dos eventos dos mapas reais.

Marcado `Versão: 25.8 (em aberto)` em todos os commits: são correções de defeito do que já está na versão (política da seção 1 de `md/PLANO_FUNCOES.md`), sem função nova e sem mudança de formato. Nada de interface mudou.

## 1. O que muda para quem usa

Na prática, quase nada: os três defeitos só aparecem quando duas coisas acontecem com poucos milissegundos (ou microssegundos) de diferença. O que muda é que o Parar, que é a função de segurança do programa, deixa de ter um modo de falha.

| Situação | Antes | Agora |
|---|---|---|
| "■ Parar" e logo "▶ Executar" (poucos milissegundos depois), com o mapa antigo dentro de uma tecla segurada ou de uma espera | a thread antiga ainda não tinha saído; como o pedido de parada é um `Event` compartilhado e o `run()` o limpa, ela seguia tocando o mapa antigo ao lado do novo: a tecla do mapa antigo só era solta no fim planejado dela e, num mapa que repete sem parar, o mapa antigo nunca parava | o Executar espera até 1 s a thread antiga sair (ela sai em milissegundos, soltando o que segurava) e só então começa o mapa novo |
| Parar (botão, F12, tecla de ativação) apertado no instante em que o mapa termina sozinho | o Parar levantava `InvalidStateTransition` ("idle -> stopping") para quem o chamou, e a parada de emergência, que promete nunca levantar, também; ou a thread do motor morria com a exceção e o aviso de "terminou" não saía | nenhum erro; o fim é avisado uma vez; se o mapa tinha um mapa seguinte (encadeamento), a parada pedida nesse instante o cancela |
| O backend recusa uma tecla (erro de execução) no instante em que a parada termina | a thread do motor morria com `InvalidStateTransition` ("idle -> error") e o erro nunca chegava a quem o escuta | o erro é avisado como sempre; a thread não morre |

## 2. Como cada defeito foi achado e provado

**2.1. Parar sem esperar e logo Executar (commit 1).** O botão "■ Parar" chama `stop()` sem esperar (para a janela não travar), e `run()` só parava a execução anterior se o estado ainda fosse RUNNING ou PAUSED. Logo depois do Parar o estado já é IDLE, mas a thread antiga ainda pode estar viva. Reprodução com o gancho do `HookBackend` (roda na thread do motor, no instante exato): a thread antiga fica parada depois do `key_down` de A, o teste chama `stop()` e `run()` com o mapa B em seguida; sem a correção, o mapa antigo continuava tocando ao lado do novo. Vermelho: 2 dos 4 testes novos falham (uma passada e repete sem parar); os outros 2 guardam o custo da correção (a espera tem prazo; quando o `run()` é chamado de dentro da própria thread do motor, como no encadeamento, ele não espera por si mesmo) e são mortos pelos defeitos plantados `MOT37` e `MOT38`.

**2.2. Parar no instante do fim (commit 2).** Veio de uma medição, não de uma suspeita. Ao medir quantos defeitos plantados de motor e pausa a varredura pegava, o teste de "pausar e depois parar" apareceu entre os que "matavam" defeitos que nada tinham a ver com ele (por exemplo `MOT26`, mapa sem comandos; `MOT28`, erro num observador de progresso; `MOT34`, aspas do alvo; `PAU18` a `PAU20`, a ligação da janela com o motor): um teste meu estava instável. Sob carga de CPU (três laços ocupados em duas CPUs) ele falhou em 21 de 25 execuções. A causa estava no teste: pausado no último evento, o mapa termina sozinho no mesmo instante em que a parada chega; se o fim natural vence, `stop()` encontra o motor em IDLE e volta sem esperar, e a thread ainda está nos últimos passos (os observadores de fim) quando o teste olhava se ela estava viva. Consertei o teste (no último evento ele espera a thread antes de olhar): 30 execuções sob a mesma carga, 0 falhas.

Mas o que o teste instável mostrou é que existe um instante em que a parada e o fim natural se cruzam, e o código do motor lê o estado e só depois muda o estado, sem nada que impeça a outra ponta de mudá-lo no intervalo (o docstring do `StateManager` avisa: quem chama `transition_to` de threads diferentes deve estar ciente disso). Medi se isso acontece de verdade, com o motor real, uma thread real e um mapa de 1 ms, com o Parar chegando em instantes aleatórios (de 0 a 4 ms) ao redor do fim. Sem nenhum artifício no código do motor:

| Experimento (descartável, fora do projeto) | Antes da correção | Depois |
|---|---|---|
| 40 000 execuções, intervalo padrão de troca de threads do Python (5 ms) | **1** thread do motor morta, com `InvalidStateTransition` ("idle -> stopping" no `_finish`, depois "idle -> error" no tratador) | 0 |
| 20 000 execuções, intervalo reduzido a 1 µs (amplia a janela) | **7** `stop()` que levantaram `InvalidStateTransition` (6 "idle -> stopping", 1 "idle -> idle") e **4** threads do motor mortas | 0 e 0 |

As três janelas (a troca para "parando" e a troca final para "ocioso" em `stop()`, e as duas trocas de `_finish()`) viraram testes determinísticos: `_EstadoComGancho` (em `tests/engine/test_engine_parada_no_fim.py`) é um `StateManager` que roda uma função exatamente antes da troca escolhida, e a função faz a outra ponta terminar o trabalho nesse ponto (a execução acaba, ou uma parada completa roda em outra thread). Nada depende de tempo. Vermelho: 7 dos 8 testes dessa parte falham sem a correção, com as mesmas exceções do experimento; o oitavo é o controle (sem parada, o encadeamento continua acontecendo).

**2.3. Erro de execução no instante da parada (commit 2).** Achado pelo passo seguinte: um estresse com operações de controle aleatórias (executar, pausar, continuar, parar, parar esperando, parar de emergência), intervalo de 1 µs e um backend que falha em 15% das teclas, para exercitar o caminho de erro. Sem falhas do backend, 30 000 execuções sem nenhuma anomalia (a pausa, o Executar e o Parar entre si estão bem). Com falhas, 20 000 execuções deram **7** threads do motor mortas com `InvalidStateTransition` ("idle -> error", no `except` de `_run_loop`): a parada terminava entre o erro do backend e a troca do motor para ERROR. É a mesma classe de defeito, nos dois tratadores de erro (o genérico e o da espera por aplicativo). Teste determinístico com os dois tipos de erro; vermelho: 2 de 2 falham sem a correção.

Depois das correções, o mesmo estresse com falhas do backend, 60 000 execuções: 0 threads mortas, 0 exceções vindas das chamadas de controle, 0 tecla presa no fim, 0 estado final diferente de IDLE, 0 thread viva (os erros do backend, 19 639, continuaram sendo avisados).

## 3. O que mudou no código (`automationstudio/input_system.py`)

- **`run()`** (commit 1): depois de parar a execução anterior, chama `_wait_previous_thread()`, que espera até 1 s a thread antiga sair e não espera por si mesma quando o `run()` vem de dentro da thread do motor (o encadeamento). Se a thread antiga não sair no prazo, o `run()` segue como antes e registra `ENGINE_RUN` no log de execução.
- **`_transition_if_possible(destino)`** (commit 2): muda o estado aceitando perder a corrida; devolve `False`, sem levantar, se o estado já mudou para onde o destino não é mais permitido. Usada em `stop()` (a troca para "parando" e a final para "ocioso"), em `_finish()` (as duas trocas) e nos dois tratadores de erro de `_run_loop` (a troca para ERROR). `emergency_stop()` não mudou: como `stop()` deixou de levantar, o que o docstring dela promete passou a valer.
- **Encadeamento**: `_finish()` só pede o mapa seguinte se nenhuma parada foi pedida (`not self._stop_requested.is_set()`). Antes, quando a parada vencia a corrida dentro do `_finish`, o encadeamento só deixava de acontecer porque a thread do motor morria antes; com a thread viva, o cancelamento passou a ser deliberado.
- Não mudaram: `core.py` e o `StateManager` (arquivo compartilhado, fora do escopo), `pause()` e `resume()` (já tolerantes desde a pausa), a assinatura de `stop()` (sem esperar por padrão).

## 4. A varredura dos mapas reais

O que o motor promete vale em qualquer evento da execução, e não só nos pontos que um teste escolhido à mão lembraria de visitar. `tests/scenarios/test_varredura_motor_mapas_reais.py` interrompe o motor logo depois de cada evento (o gancho roda na thread do motor, no instante exato) e confere, nos dois mapas reais com teclas e mouse (`Click genshin`, 16 eventos por passada, repete sem parar; `Flins combo`, 2073 eventos por passada, com teclas e botões segurados ao mesmo tempo):

1. **parado** (F12, botão Parar, tecla de ativação): nenhuma tecla ou botão fica preso, o motor volta a IDLE, não avisa "terminou" e depois da parada só se enviam soltura;
2. **pausado e retomado**: os mesmos eventos, na mesma ordem, e cada evento seguinte deslocado exatamente pelo tempo da pausa (nada é pulado, repetido ou reordenado);
3. **pausado e depois parado**: nada preso, a thread sai, IDLE.

Por padrão cada teste visita uma amostra (todos os eventos do `Click genshin`; do `Flins combo`, os 8 primeiros, os 8 últimos e um a cada 61, mais o começo da passada seguinte): cerca de 1,6 s no total. `AS_VARREDURA_COMPLETA=1` visita todos: 6297 execuções do motor (2119 paradas, 2089 pausas com retomada, 2089 pausas com parada), 90 s; **0 problemas**, no código da 25.8 com as correções deste ramo. Rode a completa antes de mexer na parada, na pausa ou na divisão do motor (Ponto 4).

**O quanto ela pega.** Rodada sozinha contra os 68 defeitos plantados de motor e pausa que existiam na hora (`MOT01` a `MOT45` e `PAU01` a `PAU23`): pega 15 (`MOT01`, `MOT02`, `MOT07` a `MOT13`, `MOT15`, `MOT30`, `PAU02`, `PAU06`, `PAU07`, `PAU08`), todos do tipo para o qual foi feita (a parada que não solta o registrado, a pausa que não congela o relógio ou não solta as teclas, a repetição com uma passada a mais, a parada que não acorda a thread pausada, o estado que não volta a IDLE). Os outros 53 são de partes que os dois mapas não exercitam (digitar texto, barreiras, condições, validação, velocidade, progresso, encadeamento) ou de corridas que só um intercalamento forçado enxerga (seção 2). A suíte inteira, com a varredura, matou os 62 de motor e pausa que o catálogo tinha antes dos novos: 62 mortos, 0 sobreviveram (15,8 min); e, no código final deste ramo, os 70 (os 62 mais `MOT40` a `MOT47`): 70 mortos, 0 sobreviveram, 0 inválidos (19,4 min).

**Cuidado do teste de pausa.** A pausa só vale quando o motor a percebe (no próximo ponto de verificação). Avançar o relógio virtual antes disso é "dormir" sem o motor saber: ele trata os 7 s como atraso a recuperar e toca eventos adiantados. Um teste meu errou nisso (Flins, evento 141) e pensei que era defeito do motor; era a condição do teste. Agora o `_pause_event` do motor é trocado por um evento que avisa quando a thread entra na espera (`_PausaObservavel`), em vez de um `sleep`.

## 5. Testes e números

Cada número abaixo vem de uma cópia limpa do próprio commit.

| Commit | Dublê de lógica | Dublê de widgets | Defeitos plantados |
|---|---|---|---|
| base (`5b84ed2`, robustez do modelo) | 1710 passam | 1969 passam | 414 |
| 1: o Executar espera a thread anterior | 1714 | 1973 | 418 |
| 2: a parada no instante do fim e o erro no instante da parada | 1724 | 1983 | 426 |
| 3: a varredura dos mapas reais | 1730 | 1989 | 426 |

Nos três: 0 falham, 344 e 85 pulados, 2 xfail, como na base. `tests/testsupport/mutacoes.py --validar`: os 418, 426 e 426 se aplicam.

- `tests/engine/test_engine_control.py` (+4): executar logo depois de parar sem esperar a thread antiga (uma passada, repete sem parar), o prazo da espera, e o `run()` de dentro do motor.
- `tests/engine/test_engine_parada_no_fim.py` (novo, 10): parar no instante do fim (`stop`, `stop(wait=True)`, `emergency_stop`), duas paradas ao mesmo tempo, o fim natural que perde para a parada (as duas trocas), o erro de execução e o erro da espera por aplicativo no instante da parada, a parada que cancela o encadeamento e o controle sem parada.
- `tests/scenarios/test_varredura_motor_mapas_reais.py` (novo, 6): seção 4.
- Defeitos plantados novos (12, catálogo 414 para 426): `MOT36` a `MOT39` (sem a espera, a espera por si mesma, sem prazo, prazo zero) e `MOT40` a `MOT47` (cada uma das trocas tolerantes desfeita: em `stop()` duas, em `_finish()` duas, a troca em si, os dois tratadores de erro, e o encadeamento com parada pedida). Ajustados porque o trecho mudou: `MOT16`, `MOT24`, `MOT30`. Os 12 novos e os 3 ajustados: 100% mortos, cada um pelo teste que o mira.
- Não foi refeita a rodada inteira dos 426 (leva cerca de uma hora). Foram refeitos, contra a suíte completa e o código final, os 70 de motor e pausa (`MOT01` a `MOT47` e `PAU01` a `PAU23`, que incluem os 12 novos e os 3 ajustados): 70 mortos, 0 sobreviveram, 19,4 min.

## 6. Decisões (você pode vetar qualquer uma)

1. **Prazo de 1 s na espera do `run()`.** A thread antiga sai em milissegundos; 1 s cobre qualquer escalonamento razoável sem deixar o Executar travado se a thread estiver presa numa chamada do backend. Se estourar, o `run()` segue como antes e deixa uma linha `ENGINE_RUN` no log.
2. **A correção do Parar+Executar fica no `run()`, não no `stop()`.** `stop()` continua sem esperar por padrão, para o botão da janela não travar.
3. **Troca tolerante em vez de trava.** Uma trava própria do motor em volta de "ler o estado e trocar" também resolveria, mas obrigaria todos os caminhos (`stop`, `_finish`, os tratadores, `pause`, `resume`) a segui-la e abre a possibilidade de impasse com os observadores que chamam `stop()` de dentro da thread do motor. A troca tolerante é local, não mexe no `StateManager` (do `core.py`, arquivo compartilhado) e já é o padrão de `pause()` e `resume()`.
4. **`stop()` que perde a corrida segue o caminho normal** (marca o pedido, espera a thread se `wait=True`, solta o que sobrou) em vez de sair cedo: o `stop(wait=True)` continua garantindo que a thread acabou quando volta.
5. **O fim natural que perde a corrida ainda avisa "terminou"** (o mapa de fato terminou); só o encadeamento é cancelado, porque quem apertou o Parar não quer o mapa seguinte.
6. **O erro de execução que chega junto com a parada continua sendo avisado** (a política de antes: erros são avisados). Mudar para "erro durante uma parada pedida não é mostrado" seria política nova e esconderia falha de verdade; não fiz.
7. **Versão 25.8 (em aberto)**: correções de defeito e testes. Se preferir contar o `run()` que espera como mudança perceptível, é trocar a linha `Versão:` da mensagem do commit 1.
8. **Amostra por padrão, completa por variável**: a amostra custa 1,6 s por rodada; a completa (90 s) é para antes de mexer na parada, na pausa ou na divisão do motor.

## 7. Por que o ramo está empilhado

Como os da rodada anterior, este ramo sai de `funcoes/robustez-modelo`: os dois alteram o catálogo de defeitos plantados (`mutacoes.py`) e a contagem do `tests/README.md`. Ordem de entrada na `main`: `funcoes/pausar-continuar-teclas`, `funcoes/plano-25-7`, `funcoes/validacao-lacunas`, `funcoes/robustez-modelo` e este. Os conflitos esperados são só do catálogo e do README (trechos de contagem).

## 8. O que não foi verificado

- **O Windows do dono.** As janelas de corrida estão no código Python (não dependem do sistema), mas o escalonamento de threads do Windows e o prazo de 1 s da espera não foram medidos lá. O Actions roda a suíte no Windows (informativo) e passou com os testes novos (seção 9), mas isso é uma máquina do GitHub e não mede a frequência da corrida nem o tempo real da espera.
- **Os experimentos de estresse rodaram no ambiente de desenvolvimento** (Linux, Python 3.13.16, 2 CPUs). O intervalo de 1 µs é um artifício para ampliar a janela; o número com o intervalo padrão (1 em 40 000 paradas num intervalo de 4 ms ao redor do fim) mostra que acontece sem ele, mas a probabilidade por uso real é muito menor.
- **Thread presa numa chamada do backend por mais de 1 s** continua possível (e o `run()` segue, como antes). Não reproduzi e não há o que testar sem o backend de verdade.
- **Não toquei**: o `except` genérico do `_run_loop` continua reportando o erro mesmo quando a parada foi pedida (decisão 6); `VkKeyScan` sem `restype` (Windows) segue para o Ponto 5, sem como verificar fora do Windows.

## 9. Resultado do Actions

**GitHub Actions** (Qt de verdade, PySide6 6.12.0), execução 42322092748, disparada à mão no commit `2578019` (a ponta do ramo na hora: a árvore de código é a dos commits 1 a 3, e os outros dois só alteram documentos) em 06/11/2026:
- **Linux** (Python 3.14.10, pytest 9.2.0): passo comum com **2018 passam, 11 pulados, 3 xfail** (51 s); janela principal, um processo por teste, **44 de 44**; sucesso.
- **Windows** (Python 3.14.10, informativo): passo comum com **2017 passam, 12 pulados, 3 xfail** (71 s); janela principal **44 de 44**; sucesso.
- Em relação à execução do ramo anterior (`funcoes/robustez-modelo`: Linux 1998, Windows 1997, 3 xfail nas duas), os passam sobem **20 nos dois**, que é exatamente a conta dos testes novos (4 + 10 + 6), e os **pulados não mudaram** (11 e 12): nenhum teste novo foi pulado, nem o das corridas nem os da varredura, que aqui rodaram com o Python 3.14 e com o escalonador de threads do Linux e do Windows. Os 3 xfail são os mesmos de antes (achados 2.03 e 2.04 da persistência e a F4 da visão, fase 7.A).
- A diferença de um teste entre Linux e Windows (2018 contra 2017, 11 contra 12 pulados) já existia: é `tests/unit/test_e2e_ambientes.py`, que só vale fora do Windows.

## 10. Para a integração

- Nada em `main_window.py`, `core.py`, `project.py` ou na documentação das outras frentes foi tocado.
- Arquivos: `automationstudio/input_system.py`; `tests/engine/test_engine_control.py`, `tests/engine/test_engine_parada_no_fim.py` (novo), `tests/scenarios/test_varredura_motor_mapas_reais.py` (novo), `tests/testsupport/mutacoes.py`, `tests/README.md`, este documento.
- Para o changelog da 25.8: "o Parar que chega no instante em que o mapa termina, ou em que o backend recusa uma tecla, não gera mais erro nem mata a thread do motor; o Executar logo depois do Parar espera a execução anterior sair".
