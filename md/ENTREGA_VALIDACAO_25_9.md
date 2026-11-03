# F2: a validação recusa o que o executor recusaria (versão 25.9)

Frente de funções, 03/11/2026. Fecha os 3 testes `xfail` de `tests/unit/test_validation_gaps.py` (tarefa F2 do `DELEGACAO.md`, "O que vem depois", item 1 do `PLANO_FUNCOES.md`). Ramo `funcoes/validacao-lacunas`, **empilhado** sobre `funcoes/pausar-continuar-teclas` (seção 4). Marcado `Versão: 25.9 (nova)`: nada daqui entra na 25.8.

## 1. O que muda para quem usa

Antes, três erros só apareciam com o mapa já rodando, ou nem apareciam. Agora o mapa **não começa** e a mensagem aponta o comando:

| Situação | Antes | Agora |
|---|---|---|
| Botão do mouse com nome que não existe (por exemplo `lefft`) | o mapa começava, enviava as entradas anteriores e falhava no meio, com o erro do backend | recusado ao iniciar: `[cmd_...] botão do mouse desconhecido: 'lefft' (use left, right, middle, x1, x2).` |
| "Abrir aplicativo" sem programa (vazio, só espaços ou só aspas) | falhava no meio, com "Nenhum aplicativo foi definido para abrir." | recusado ao iniciar: `[cmd_...] abrir aplicativo sem o programa a abrir (caminho ou comando) definido.` |
| `repeat_count` menor que -1 | **rodava uma vez, em silêncio** | recusado ao iniciar: `Mapa 'X': repeat_count -2 é inválido (use 1, N ou -1 para infinito).` |

**O que não muda.** Os mapas continuam abrindo e podem ser editados: só a execução é recusada. `Left`, `RIGHT` e `X1` continuam valendo (o executor compara em minúsculas). `repeat_count` -1 (infinito) e os positivos continuam valendo. Os 3 mapas reais e o seu `AutomationStudio.db` de 08/10 (3 mapas, 943 comandos: só botão esquerdo, `repeat_count` -1, -1 e 1, nenhum alvo vazio) passam sem nenhum erro novo.

**Quem pode notar.** Só quem tiver um mapa com um desses três defeitos. A interface não os produz (a caixa de repetições vai de -1 a 9999 e o editor só oferece os 5 botões válidos): eles só aparecem em arquivo ou banco editado à mão, ou vindo de uma versão antiga. O caso que muda de "funcionava" para "recusado" é o `repeat_count` menor que -1, que antes rodava uma vez.

## 2. Como foi feito

- **`core.MOUSE_BUTTON_NAMES`** (`left`, `right`, `middle`, `x1`, `x2`): a fonte única dos nomes de botão. É lida pela validação do comando e pelo resolvedor do backend pynput (que tinha a lista escrita no código); o teste de contrato confere que os dois backends estritos (pynput e Win32) aceitam todos e recusam o resto (o Mock, que é o dublê dos testes, aceita tudo), e um teste da janela confere que o editor oferece exatamente estes.
- **`core.normalized_app_target()`**: o programa que "abrir aplicativo" abre, sem espaços nas pontas e sem aspas externas, que é a conta que o executor já fazia em `_launch_application`. Agora o executor e a validação chamam a mesma função.
- **`Command.validate()`**: duas regras novas (botão desconhecido; abrir aplicativo sem programa). **`AutomationMap.validate()`**: uma (`repeat_count` menor que -1).
- O executor **não mudou de comportamento**: `_resolve_mouse_button` e `_launch_application` só passaram a ler a fonte única e o normalizador.

## 3. Decisões (você pode vetar qualquer uma)

1. **A validação copia o executor, não o contrário.** Recusa exatamente o que o executor recusaria, nem mais nem menos: nomes de botão sem diferenciar maiúsculas (como os backends), **sem** aparar espaços (os backends não aparam: `" left"` falharia na execução), e o mesmo critério de "vazio" para o programa.
2. **A leitura não corrige nada.** Um mapa com `repeat_count` -5 carrega como -5 (hoje também) e a validação o recusa na hora de executar. Descartei normalizá-lo na leitura, como o 0 vira 1: mudaria o dado do usuário em silêncio, e a F2 não mexe no leitor (o formato v2 do Ponto 3 decide isso).
3. **Comando desativado também é validado**, como já era para as outras regras (alvo vazio, duração negativa...): um comando desativado volta a valer quando reativado. Se preferir que o desativado não bloqueie o mapa, é uma mudança à parte, para todas as regras de uma vez.
4. **Sem limite superior para `repeat_count`.** A interface limita a 9999, mas o motor aceita mais; recusar seria inventar regra.
5. **A validação não confere se o programa existe.** Só diz se há algo para abrir; um caminho que não existe continua falhando na execução, com a mensagem do executor.

## 4. Por que o ramo está empilhado

Você autorizou ramos abertos sobre os meus. Este nasce de `funcoes/pausar-continuar-teclas` (`b755b9a`) e não da `main`, por três razões: (a) os dois ramos alteram as mesmas linhas do `tests/README.md` (a lista de defeitos conhecidos) e a contagem do catálogo de defeitos plantados, e separados dariam conflito na junção; (b) a correção do abort do Windows no Actions (commit `Infra:` da pausa) já vem junto, e sem ela qualquer teste novo pode derrubar o job do Windows de novo (`md/ENTREGA_PAUSA_TECLAS.md`, seção 10); (c) a F2 é da 25.9 e a pausa é da 25.8, então a ordem natural de junção é essa. **Consequência:** este ramo só pode entrar na `main` depois do da pausa. Se a pausa for vetada, ele precisa ser refeito sobre a `main` (são poucas linhas).

## 5. Testes e números

**Reproduzir e falhar antes de corrigir.** Com os testes escritos e o código ainda sem a correção, 30 dos 55 testes que o arquivo tinha nessa hora falharam: os 3 antigos, sem o marcador, e 27 novos. Os outros 25 (nomes válidos, regra que não vale para outros tipos de comando, `repeat_count` válido) passavam e continuam passando, como guarda contra regra a mais. O 56º, o do executor, entrou depois dessa rodada.

**Árvore final** (dublê de lógica / dublê de widgets, `.bat` em CRLF): **1548 passam, 0 falham, 313 pulados, 2 xfail** / **1776 passam, 0 falham, 85 pulados, 2 xfail** (a pausa tinha 1460 / 1687, com 5 xfail; os 2 que restam são os de persistência, achados 2.03 e 2.04, do Ponto 3).

**Testes novos.** `unit/test_validation_gaps.py` passa de 3 testes `xfail` para 56 (limites de cada regra, maiúsculas, espaços, tipos de comando que não são alvo da regra, mensagem com o valor, `repeat_count` na leitura e na validação, o motor recusando o mapa antes de enviar qualquer entrada, e o executor abrindo o programa já normalizado). Em `contract/test_backend_contract.py`: os botões válidos agora vêm da fonte única e um teste de **paridade** confere, para cada backend estrito e 16 nomes (válidos, em outra caixa, com espaço, inventados e vazio), que a validação recusa exatamente o que o backend recusa. Em `gui/test_command_dialog.py`: o editor oferece exatamente os botões da fonte única e cada um valida.

**Defeitos plantados** (`tests/testsupport/mutacoes.py`): o catálogo vai de 381 para **391**. Os 10 novos (`MOD51` a `MOD56`, `MOT34`, `MOT35`, `W3222`, `EDI31`: cada regra sem efeito, a regra que diferencia maiúsculas, o `<= -1` que recusaria o infinito, o normalizador sem o `strip`, o executor com outra conta, o Win32 aceitando um terceiro botão lateral, o editor oferecendo um sexto botão) foram **10 de 10 mortos** na rodada à parte (2,2 min). Rodada completa dos 391: **391 de 391 mortos, 0 sobreviventes, 0 inválidos**, em perto de 60 min (duas cópias ao mesmo tempo). Foi feita numa cópia da árvore tirada antes de eu reescrever o texto de um comentário de `core.py`: é a única diferença de código ou de teste para o que foi commitado, e não muda comportamento (conferi com `diff`). O ambiente interrompeu a rodada uma vez, no 28º defeito; ela foi retomada com `--retomar`, que só aceita o mesmo projeto (impressão digital), e os 28 primeiros resultados vieram do progresso gravado.

**Dados reais.** `test_legacy_maps.py` (os 3 mapas reais, `validate()` e `validate_structure()` sem erro) segue verde. Além disso, o seu `AutomationStudio.db` de 08/10, numa cópia: 3 mapas, 943 comandos, nenhum erro de validação, nenhum recusado pelas regras novas.

**GitHub Actions** (Qt de verdade, Python 3.14.x, PySide6 6.12.0): ainda não rodou neste ramo no momento deste commit; o resultado entra no commit seguinte, que atualiza esta linha.

## 6. O que não foi verificado

- **Windows de verdade.** A F2 não toca em entrada real (nenhum `SendInput` novo), mas a conferência dos backends com o teclado e o mouse do seu Windows continua sendo a da rodada normal.
- **Python 3.14 aqui.** O ambiente onde rodei os dublês tem o Python 3.13.16; quem roda o 3.14 é o Actions (resultado na seção 5).
- **Mapas seus que eu não tenho.** Só vi os 3 que estão no `AutomationStudio.db` de 08/10. Se houver outros no seu banco de hoje com um dos três defeitos, o primeiro sinal é a mensagem ao executar, que diz o comando e o motivo.
- **O leitor v2** (Ponto 3) é quem decide, no futuro, se estes casos passam a ser tratados já na leitura.

## 7. Para a integração

Esta entrega fecha a F2 do quadro de tarefas e deixa a lista de `xfail` com 2 itens; o `ROADMAP.md` e o `DELEGACAO.md` não foram alterados por mim. `md/FUNCOES_DO_USUARIO.md` não muda: nenhum controle foi alterado.
