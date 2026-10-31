# Especificação: ativação por mapa (item 2.3 do plano 25.7, função da 25.8)

Etapa 1 do processo de 8 etapas. A ficha vem antes do código: os testes (etapa 2) saíram dela, com os IDs do plano.
**Estado: implementada.** Esta edição descreve o que foi **construído**. Onde o desenho mudou durante a construção, a seção 7 diz o que mudou e por quê.

## 1. Problema

Hoje **todo mapa que tem tecla é registrado** ao abrir o programa e a cada alteração (`_register_all_hotkeys`). Não existe o estado "desativado", e nada diz ao usuário de quem é uma tecla:

- Quem chega depois perde a tecla em silêncio, e a mensagem repete a tecla sem dizer de quem ela é (`O atalho '=' usa a(s) mesma(s) tecla(s) que '=', já em uso.`). O aviso ainda reaparece a cada novo registro, mesmo sem nada ter mudado.
- Todo mapa novo nasce com a tecla `=`, que já é a do exemplo: criar um segundo mapa já conflita.
- Os mapas são registrados **antes** dos atalhos de controle. Um mapa com a tecla `F12` fica com ela, e a **parada de emergência** perde a tecla (o aviso cita só "já em uso"). É uma falha de segurança latente, confirmada pela leitura do código.
- Uma tecla inválida (por exemplo só `+`) lança exceção no registro.

## 2. Comportamento

### 2.1 Os três estados (exclusivos)

| Estado | Rótulo na tela | O que significa |
|---|---|---|
| `sessao` | Ativo nesta sessão | A tecla funciona agora. Ao reabrir o programa, o mapa volta **desativado**. |
| `sempre` | Sempre ativo ao iniciar | A tecla funciona agora e em toda abertura. |
| `desativado` | Desativado | A tecla **não** inicia o mapa. O botão ▶ Executar e a "próxima automação" continuam funcionando. |

Só dois valores são gravados (a **preferência**): `sempre` e `desativado`. "Ativo nesta sessão" existe só na memória e **nunca é gravado**.

### 2.2 Transições (decisão D26)

| De → Para | Preferência gravada | Aviso |
|---|---|---|
| qualquer → `sempre` | `sempre` | — |
| qualquer → `desativado` | `desativado` | — |
| `desativado` → `sessao` | continua `desativado` | — |
| `sempre` → `sessao` | **muda** para `desativado` | "Na próxima abertura do programa esta automação ficará desativada." (barra de status, 8 s) |

Os estados são exclusivos; por isso "Sempre ativo" → "Ativo nesta sessão" necessariamente abre mão do "sempre".

### 2.3 Onde fica a preferência

No banco de **configurações** (`AppSettings`, chave `map_activation`, valor `{"migrated": true, "prefs": {"<nome do mapa>": "sempre" | "desativado"}}`), por **nome do mapa**. **Não entra no mapa**: o formato dos mapas continua intacto (bloqueado até o marco). Excluir um mapa apaga a preferência dele; **recarregar a lista nunca apaga** preferências (um mapa que não carregou desta vez continua no banco).

### 2.4 Mapas que já existem, mapas novos

- **Primeira abertura da 25.8:** todo mapa existente é gravado como `sempre` (é o comportamento de hoje: nada deixa de funcionar) e a migração fica marcada como feita.
- **Mapa novo ou importado** (criado, importado de JSON, de banco externo, ou o exemplo do tutorial): nasce `sessao` (preferência gravada `desativado`), **exceto** se a tecla dele já estiver em uso por um mapa ativo ou por um atalho de controle: então nasce `desativado` e o usuário é avisado com a mensagem de conflito.
- Vários mapas novos de uma vez com a mesma tecla: o primeiro pelo nome fica com ela.
- Importar **substituindo** um mapa de mesmo nome mantém a preferência dele.
- Dado corrompido no banco (`map_activation` que não é um dicionário, preferência desconhecida): ignorado, sem erro; o programa abre.

### 2.5 Conflito de tecla (decisão D27)

1. Só mapas **ativos** e atalhos de controle ocupam teclas. Mapa desativado nunca conflita.
2. **Os atalhos de controle têm prioridade** e nunca perdem a tecla para um mapa. Entre eles, a ordem é: parada de emergência, pausar, continuar, iniciar/finalizar gravação, cancelar gravação.
3. Duas teclas são a mesma se a combinação normalizada for igual (`ctrl+f6`, `CTRL+F6` e `F6+Ctrl` são a mesma; `X1` e `MOUSE_X1` também), a mesma regra de `GlobalHotkeyManager`.
4. **Ativar** um mapa cuja tecla está ocupada é **recusado**: o estado não muda e a mensagem nomeia a tecla, o mapa e quem a usa. Quem já usa a tecla nunca a perde para quem chega depois, mesmo que o nome de quem chega venha antes na ordem alfabética.
5. **Mudar a tecla** de um mapa ativo para uma tecla ocupada é **recusado** do mesmo jeito (a tecla anterior permanece). Mapa desativado pode receber qualquer tecla **que exista**: o conflito é checado quando for ativado. Uma tecla que não existe (vazia, só `+`) é recusada em qualquer estado.
6. **Dados antigos com conflito** (dois mapas ativos com a mesma tecla, vindos de versões anteriores): vale a ordem do nome como o banco a faz (`COLLATE NOCASE`, só A-Z igualados), como hoje: o primeiro registra. O outro continua **ativo, sem a tecla** ("sem a tecla: conflito"), sem que a preferência gravada seja alterada, e a tela diz isso. O aviso aparece **uma vez por conflito** (de novo se o conflito sumir e voltar). Se quem tinha a tecla for desativado, a tecla passa sozinha ao outro no registro seguinte.
7. Mapa **sem tecla** ou com tecla **inválida** não ocupa nada, não conflita e não derruba o programa.

### 2.6 Mensagens (HK-01)

Sempre com aspas curvas e o nome das duas partes:

- Mapa × mapa: `A tecla “=” de “Novo” já é usada pela automação ativa “Exemplo”.`
- Mapa × controle: `A tecla “F12” de “Novo” é a do atalho de controle “Parar tudo agora”.`
- Controle × controle: `Os atalhos de controle “Pausar automação” e “Parar tudo agora” usam a mesma tecla “F9”; só “Parar tudo agora” foi ativado.`
- Tecla inválida: `A tecla “+” de “Novo” não é válida; a automação ficou sem atalho.`

Quem pediu a ação recebe, além disso, o que fazer (desativar o outro mapa ou mudar a tecla em ⚙ Configurações da automação) e, ao mudar a tecla, qual tecla continua valendo.

## 3. Interface (como foi construída)

A frente visual redesenha a tela. Aqui só entra o **controle necessário para a função existir**, com widgets padrão (herdam o tema). Tudo mora em `automationstudio/ativacao_ui.py`; a janela principal ganhou só ganchos.

### 3.1 A faixa "Ativação" (no editor)

Uma caixa com os três estados e, embaixo, uma frase com a situação da automação aberta (por exemplo `A tecla “=” inicia e para esta automação.`). Fica **no editor da automação, logo abaixo da frase de instrução**, e só aparece quando há uma automação aberta. A dica da caixa explica o estado. Escolha recusada por conflito: aviso "Não foi possível ativar" e a caixa **volta ao estado verdadeiro**. `objectName`: `PainelAtivacao`.

Por que no editor e não debaixo da lista: um clique na lista já abre o editor (`_on_map_selected`), então um painel debaixo da lista nunca seria visto com uma automação selecionada.

### 3.2 A lista de automações

O texto do item continua sendo o **nome do mapa** (a janela o usa como chave). Cada item ganha: a dica (a frase "Abrir esta automação…", uma linha em branco, a situação e o resumo) e dois papéis de dados para a frente visual desenhar como quiser: `257` (estado: `sessao`, `sempre` ou `desativado`) e `258` (o texto do conflito, vazio se não há). **Nenhuma cor, ícone ou cinza é aplicado:** isso é da frente visual.

### 3.3 O rótulo "Tecla para iniciar/parar" (linha de baixo do editor)

Curto, porque a linha é estreita: `Tecla para iniciar/parar: =`, e só quando algo impede a tecla de iniciar a automação, o motivo entre parênteses: ` (desativada)`, ` (em conflito)` ou ` (inválida)`. O detalhe está na faixa.

### 3.4 ⚙ Configurações da automação

A tecla digitada é conferida. Recusada (ocupada por mapa ativo ou por atalho de controle, ou inexistente): aviso **"Tecla não alterada"** com o motivo e a tecla que continua; a tecla anterior permanece e as **demais perguntas seguem** (para não perder o resto da configuração).

### 3.5 Os avisos

| Título | Quando | Conteúdo |
|---|---|---|
| Atalho em conflito | Um mapa novo ou importado nasceu desativado porque a tecla dele estava ocupada | A mensagem de conflito + "Por isso “X” começou desativada." |
| Conflito de atalhos | No registro: conflito antigo, tecla inválida, ou o gerente recusou uma tecla | Uma vez por conflito enquanto durar |
| Não foi possível ativar | Ativar pela faixa com a tecla ocupada | A mensagem + o que fazer |
| Tecla não alterada | Mudar a tecla para uma ocupada ou inexistente | A mensagem + a tecla que continua + o que fazer |

## 4. Funções afetadas

`MainWindow.__init__` (cria `self.ativacao` e monta a faixa), `_reload_map_list` (sincroniza o estado e decora a lista), `_register_all_hotkeys` (passa a seguir o plano), `_on_hotkey_triggered` (ignora `map:X` com `X` desativado, mesmo que o disparo já estivesse na fila do Qt), `_delete_current_map` (esquece a preferência), `_configure_current_map` (valida a tecla), `_refresh_map_config_labels` (rótulo compacto e faixa). `AppSettings` ganha `get_map_activation` e `set_map_activation`. Módulos novos: `ativacao.py` (lógica pura, sem Qt) e `ativacao_ui.py` (controlador e faixa).

**Não muda:** o motor, o gravador, os backends, o formato dos mapas, a versão (`APP_VERSION`) e o tema.

## 5. Critérios objetivos e onde estão os testes

| ID | Critério | Nível | Onde |
|---|---|---|---|
| MAP-01 | Ativar nesta sessão não altera a preferência gravada (exceto vindo de "Sempre ativo", e então avisa) | L | `unit/test_ativacao.py`, `unit/test_ativacao_controlador.py`, `gui/test_ativacao_painel.py` |
| MAP-02 | "Sempre ativo" e "Desativado" voltam iguais na próxima abertura; "Ativo nesta sessão" volta desativado | L | `unit/test_ativacao.py`, `unit/test_ativacao_controlador.py` |
| MAP-03 | Mapa desativado não executa ao acionar a tecla (backend e monitor falsos; nenhum evento) | L + Q | `unit/test_ativacao_controlador.py`; `gui/test_ativacao_janela.py` (motor de verdade) |
| MAP-04 | Os 3 mapas reais abrem "Sempre ativos" e registram **os mesmos atalhos de hoje** | L + Q | `unit/test_ativacao.py`, `unit/test_ativacao_controlador.py`; `gui/test_ativacao_janela.py` |
| HK-01 | A mensagem de conflito nomeia as duas automações (ou o atalho de controle) e a tecla | L + Q | `unit/test_ativacao.py`, `unit/test_ativacao_controlador.py`; `gui/test_ativacao_janela.py` |
| ATV-01 | O atalho de controle nunca perde a tecla para um mapa; a parada de emergência vem primeiro | L + Q | `unit/test_ativacao.py`; `gui/test_ativacao_janela.py` |
| ATV-02 | Tecla vazia, inválida ou equivalente (ordem e caixa) é tratada sem exceção | L | `unit/test_ativacao.py` |
| ATV-03 | Mapa novo ou importado nasce conforme 2.4; excluir apaga a preferência | L + Q | `unit/test_ativacao.py`, `unit/test_ativacao_controlador.py`; `gui/test_ativacao_janela.py` |
| ATV-04 | Preferência corrompida no banco é ignorada (leitor tolerante) | L + Q | `unit/test_ativacao.py`, `persistence/test_app_settings.py`; `gui/test_ativacao_janela.py` |
| ATV-05 | A faixa e o controlador atualizam lista, faixa e rótulo e recusam a ativação em conflito | L (dublê) + Q | `gui/test_ativacao_painel.py`; `gui/test_ativacao_janela.py` |
| LIG | A janela está ligada ao controlador nos 7 pontos (ganchos) | L | `static/test_ligacao_ativacao.py` |

L = lógica pura ou dublê de widgets (roda sem Qt); Q = janela com o Qt de verdade (só roda na sua máquina ou no CI do GitHub). Os testes Q foram escritos **sem poder rodar o Qt**: ver `md/ENTREGA_25_8.md`.

## 6. O que fica de fora

- O desenho final da seleção de mapas (colunas, selos, cores): é da frente visual. O contrato dela com esta função está em `md/DIVISAO_DE_TRABALHO.md` (`ControladorAtivacao.descrever`, os papéis 257 e 258, a faixa `PainelAtivacao`).
- Os atalhos de **Pausar** e **Continuar** (F9 e F10) **não fazem nada hoje** (achado 2.11, confirmado pela leitura do código: nenhum ramo em `_on_hotkey_triggered` e nenhuma chamada a `engine.pause()`/`resume()`). Não entram aqui; ficam registrados como teste de defeito conhecido (`static/test_lacunas_de_ligacao.py`).
- Conflito entre uma tecla simples e uma combinação que a contém (`F8` e `CTRL+F8` disparam juntas): hoje já é assim, e nenhum pedido do plano cobre isso. Registrado como observação.
- Desativar um mapa **que está executando** não o interrompe: só tira a tecla dele, e a tecla era também a de parar. Para pará-lo, o botão de parar ou a emergência. É uma escolha minha, pela regra de que desativar só mexe na tecla; se preferir que desativar também pare a execução, é uma linha na faixa.

## 7. O que mudou desde a ficha original

| Na ficha | Como ficou | Por quê |
|---|---|---|
| Painel "Ativação da automação selecionada" debaixo da lista | Faixa no editor, logo abaixo da instrução | Clicar na lista já abre o editor; debaixo da lista o painel nunca seria visto |
| Mapa sem tecla ativa em cinza na lista | Sem cinza; estado e conflito nos papéis 257 e 258 e na dica | Cor é da frente visual; um cinza meu brigaria com o tema |
| Rótulo do editor "…: = · Ativo nesta sessão" | Rótulo curto com o motivo entre parênteses só quando a tecla não funciona | A linha de baixo do editor é estreita e já tem três rótulos |
| Decisão de recusar a tecla dentro da janela | `ControladorAtivacao.mudar_tecla` (a janela só chama) | A decisão ficou testável sem Qt (o verificador de defeitos achou um buraco aqui) |
| — | Guarda `acao_permitida` em `_on_hotkey_triggered` | Um disparo que já estava na fila do Qt quando o usuário desativou o mapa ainda o executaria |
| — | Aviso de conflito uma vez por conflito (e não a cada registro) | Antes o mesmo aviso reaparecia a cada alteração de mapa |
