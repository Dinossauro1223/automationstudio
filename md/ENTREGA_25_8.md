# Entrega: ativação por mapa e conflito de atalhos (função da 25.8)

Registro de entrega (etapa 8 do processo). Itens do plano 25.7 cobertos: **MAP-01 a MAP-04** e **HK-01** (item 2.3), mais os critérios ATV-01 a ATV-05 da ficha (`md/ESPEC_ATIVACAO_25_8.md`).

**Onde está:** ramo `funcoes/ativacao-mapas`, a partir da `main` (`e2fec5f`, "Versão base AS 25.5"). A `main`, o ramo `visual/novo-tema` e a versão (`APP_VERSION = "25.6"`) **não foram tocados**. Nenhum formato de arquivo mudou.

## 1. O que muda para quem usa

- Cada automação tem um estado: **Ativo nesta sessão**, **Sempre ativo ao iniciar** ou **Desativado**. Desativado só tira a tecla: o botão ▶ Executar e a "próxima automação" continuam funcionando.
- As automações que você já tem **abrem "Sempre ativo"**, com as mesmas teclas de hoje. Automação nova nasce "Ativo nesta sessão" (e volta desativada na próxima abertura), ou desativada se a tecla já for de outra.
- **Conflito de tecla:** o aviso diz de quem é a tecla, por exemplo: A tecla “=” de “Novo” já é usada pela automação ativa “Exemplo”. Ativar ou trocar para uma tecla ocupada é **recusado**, nunca rouba. As teclas de controle (parar tudo, gravar...) **nunca perdem a tecla para uma automação**: antes, uma automação com `F12` engolia a parada de emergência.
- A tela: uma faixa **"Ativação"** no editor da automação (logo abaixo da frase de instrução), a dica de cada item da lista com o estado e a tecla, e o rótulo da tecla no editor com "(desativada)" ou "(em conflito)" quando for o caso.

## 2. Conferência rápida no Windows (uns 5 minutos)

Os testes de janela real foram escritos sem poder rodar o Qt; esta conferência à mão cobre o essencial enquanto a rodada completa não acontece.

| # | Faça | Deve acontecer |
|---|---|---|
| 1 | Abra o programa com as automações que já tinha | Todas na lista; a dica de cada uma diz "Sempre ativo ao iniciar" e a tecla |
| 2 | Abra uma automação | Abaixo da frase de instrução aparece "Ativação: [Sempre ativo ao iniciar]" e a frase da tecla; a linha de baixo mostra "Tecla para iniciar/parar: X" |
| 3 | Troque para **Desativado** | A linha de baixo ganha "(desativada)"; apertar a tecla (fora do programa) não inicia mais; ▶ Executar continua funcionando |
| 4 | Crie uma automação nova (a tecla padrão é `=`) | Se outra ativa já usa `=`: aviso "Atalho em conflito" e ela nasce desativada. Se não: nasce "Ativo nesta sessão" |
| 5 | Em ⚙ Configurações, digite a tecla de outra automação ativa | Aviso "Tecla não alterada" e a tecla anterior continua; as demais perguntas seguem |
| 6 | Feche e abra o programa | "Ativo nesta sessão" volta **desativada**; "Sempre ativo" continua ativa |
| 7 | Passe o mouse sobre um item da lista | A dica traz a frase de abrir, o estado e a situação da tecla |

Se algo não bater, o mais útil é `logs\AutomationStudio.log` (se a faixa não puder ser montada, o motivo está lá) e a descrição do que viu.

## 3. Números

| | Base (`e2fec5f`) | Esta função |
|---|---|---|
| Testes, dublê de lógica (`AS_TEST_QT_STUB=1`) | 1264 passam, 3 falham | **1403** passam, 3 falham, 6 xfail |
| Testes, dublê de widgets (`AS_TEST_QT_STUB=widgets`) | 1475 passam, 3 falham | **1630** passam, 3 falham, 6 xfail |
| Árvore **juntada** com `visual/novo-tema` (6e42294), lógica / widgets | — | 1418 / 1645 passam, **as mesmas 3 falham**, zero conflitos de junção |
| Defeitos plantados (verificador de mutações) | 292, todos pegos | **355** (63 novos), **todos pegos** (seção 4) |

- **Testes novos: 168** (155 rodam aqui; 12 só rodam com o Qt de verdade; 1 é o `xfail` do achado 2.11): `unit/test_ativacao.py` (92, a lógica), `unit/test_ativacao_controlador.py` (24), `gui/test_ativacao_painel.py` (16, com o dublê de widgets), `gui/test_ativacao_janela.py` (12, janela real), `static/test_ligacao_ativacao.py` (10), `static/test_lacunas_de_ligacao.py` (4), e 10 em `persistence/test_app_settings.py`.
- **As 3 falhas** são as de antes e **não são desta função**: dois testes de fim de linha dos `.bat` e a validação do catálogo de defeitos (NET10 e NET83, que plantam defeito em CRLF). Aparecem porque o repositório guarda os `.bat` com LF; no seu Windows (com `core.autocrlf`) não aparecem. Conferi na base limpa: as mesmas 3. A correção é um `.gitattributes` (ver `md/DIVISAO_DE_TRABALHO.md`).
- **Cobertura do `coverage.py`:** não medida (não há `coverage` no ambiente de desenvolvimento, e sem rede não consegui instalar). A catraca de cobertura ganhou o grupo `ativacao` para o seu baseline.

## 4. Verificador de mutações (a prova de que os testes pegam defeito)

Planta-se um defeito de cada vez numa cópia e roda-se a suíte inteira; "morto" é um teste que passava e passou a falhar.

- **Área nova `ativacao`: 62 de 62 mortos** (a primeira rodada deixou 2 sobreviverem: um buraco de teste e uma decisão dentro da janela que o teste não alcançava; a decisão foi para `ControladorAtivacao.mudar_tecla`, que se testa sem Qt, e a segunda rodada pegou os 62).
- **`EST13`** (a emergência perde o ramo em `_on_hotkey_triggered`): morto, pelo controle do verificador das lacunas de ligação.
- **Rodada completa do catálogo, refeita inteira com o código e os testes desta função, numa cópia com os `.bat` em CRLF (como no seu Windows): 354 de 354 mortos, nenhum sobrevivente, nenhum inválido** (os 292 da base e os 62 da ativação), cerca de 57 minutos com duas cópias por vez. O ambiente interrompeu o processo duas vezes e o `--retomar` continuou dali (ele só aceita retomar se o código e os testes são os mesmos). Somado ao `EST13`: **355 de 355**. Ou seja, nada do que a suíte já pegava deixou de ser pego.

## 5. O que **não** foi verificado

1. **Qt de verdade.** O ambiente de desenvolvimento não tem PySide6. Os 12 testes de `gui/test_ativacao_janela.py` e o encaixe da faixa no editor (`insertWidget`), a dica dos itens sob o tema novo e a largura da linha de baixo do editor **só se confirmam na sua máquina** (ou no CI do GitHub). A faixa foi construída para falhar sem derrubar o programa (se o encaixe falhar, a janela abre sem ela e o log diz por quê).
2. **Windows de verdade:** os atalhos globais com o `pynput` e o clique físico nunca rodaram aqui. A lógica é testada com um gerente de atalhos e um monitor falsos.
3. **Python 3.14:** o ambiente tem o 3.13. Os módulos novos não usam nada específico do 3.14 e passam nas checagens estáticas (módulos removidos, escapes, `return` em `finally`).
4. **A rodada de testes da 25.6 no Windows ainda não chegou** (`logs\tests_last_run.txt`, `logs\travamento_qt.txt`, `logs\AutomationStudio.log`). Esta função foi construída sobre uma base que o seu Windows ainda não confirmou. Pode esperar: a rodada com as duas frentes vale para tudo.

## 6. Decisões que tomei (você pode vetar qualquer uma)

Do plano 25.7, adotei como recomendadas: **D26** (a preferência "sempre"/"desativado" gravada nas configurações, a ativação temporária só na memória, e o aviso de "sempre" para "só nesta sessão") e **D27** (só mapas ativos contam; ativar em conflito é recusado e a mensagem nomeia as duas partes). **D24, D25 e D34** (a prévia da 25.7, o painel único de configurações, a ordem das versões) seguem como recomendadas no roadmap; nada nesta função depende delas, e a prévia e o painel único são da frente visual.

Decisões **minhas** desta construção, que o plano não cobria:

| Decisão | Por quê | Se você discordar |
|---|---|---|
| A faixa fica **no editor**, não debaixo da lista | Clicar na lista já abre o editor | A frente visual pode mudar a âncora (uma linha) |
| **Sem cinza** na lista; estado e conflito nos papéis 257 e 258 | Cor é da frente visual | Aplicar uma cor é uma linha em `decorar_lista` |
| Rótulo da tecla **curto** com o motivo entre parênteses | A linha de baixo do editor é estreita | O texto longo está na faixa |
| Quem **perdeu** a tecla num conflito antigo continua **ativo, sem tecla**, com a situação na tela (em vez de ser desativado) | Não altero a preferência gravada por conta própria; se quem tinha a tecla for desativado, a tecla passa sozinha ao outro | Desativar o perdedor é uma linha |
| **Desativar** um mapa que está executando **não** o interrompe | Desativar só mexe na tecla | Interromper é uma linha na faixa |
| Uma tecla **inexistente** (vazia, só `+`) é recusada em qualquer estado; uma tecla ocupada só é recusada se o mapa está ativo | Mapa desativado pode ser configurado à vontade; o conflito é conferido ao ativar | — |
| O aviso de conflito aparece **uma vez por conflito** | Antes reaparecia a cada alteração de mapa | — |
| O exemplo do tutorial nasce "Ativo nesta sessão" | É um mapa novo como outro qualquer | — |

## 7. Achado novo: as teclas F9 e F10 (pausar e continuar) não fazem nada

**Problema.** Em Configurações aparecem "Pausar automação" e "Continuar automação", e as duas teclas são registradas. Mas apertar F9 ou F10 **não pausa nem continua** a execução.
**Evidência (leitura do código; a janela real não foi acionada aqui).** `MainWindow._on_hotkey_triggered` atende só `map:`, `control:emergency`, `record:toggle` e `record:cancel`; o disparo de `control:pause` e `control:resume` não casa com nenhum ramo e some. `ExecutionEngine.pause()` e `resume()` existem (e o motor pausa e continua, testado em `engine/test_engine_control.py`), mas **nada no programa chama `engine.pause()` nem `engine.resume()`**.
**Confiança.** Confirmada pela leitura (não executada).
**Correção proposta.** Dois ramos em `_on_hotkey_triggered` (`self.engine.pause()` e `self.engine.resume()`), mais o que a barra de estado mostra e o que acontece com uma pausa durante uma espera por aplicativo (decisão sua). Fica como **ponto à parte**, não nesta função.
**Teste.** `static/test_lacunas_de_ligacao.py` guarda o defeito como `xfail` estrito (falha pelo motivo certo hoje; quando alguém corrigir, o teste "passa", o executor reclama e o marcador sai). Conferi numa cópia que ele acusa a correção.
**Impacto no plano.** O roadmap diz, em D32(a), que a pausa "já funciona". **Isso está errado:** o motor pausa, a tecla não. Cópias corrigidas do roadmap vão junto.

## 8. Limitações conhecidas

- Uma tecla simples e uma combinação que a contém (`F8` e `CTRL+F8`) disparam juntas; já era assim e nenhum pedido do plano cobre.
- A migração da primeira abertura considera "existente" todo mapa que o banco já tinha. Quem voltar da 25.8 para a 25.6 e criar mapas lá terá esses mapas tratados como novos ao reabrir na 25.8.
- A preferência é por **nome** de mapa: renomear um mapa não leva a preferência junto (o mapa renomeado vira "novo"). Hoje o programa não tem renomear; se tiver, é preciso levar a preferência.

## 9. O processo de 8 etapas

| Etapa | Feito |
|---|---|
| 1. Especificação | `md/ESPEC_ATIVACAO_25_8.md` (atualizada ao que foi construído) |
| 2. Testes primeiro | os testes saíram da ficha, com os IDs do plano, antes do código |
| 3. Implementação isolada | `ativacao.py`: lógica pura, sem Qt e sem disco |
| 4. Testes isolados e regressão | `unit/test_ativacao.py`, `unit/test_ativacao_controlador.py`, `persistence/test_app_settings.py`; os 3 mapas reais como ficha permanente |
| 5. Integração no ramo de desenvolvimento, com a estável intacta | `ativacao_ui.py` + 7 ganchos em `main_window.py`, protegidos por `static/test_ligacao_ativacao.py`; ramo `funcoes/ativacao-mapas` |
| 6. Regressão | suíte inteira contra a base (seção 3); verificador de mutações (seção 4); ensaio de junção com o ramo visual |
| 7. Aprovação | **sua**: use a conferência da seção 2 e me diga |
| 8. Registro de entrega | este arquivo |

## 10. Sugestões (nada disso foi feito)

1. **`.gitattributes`** com `*.bat text eol=crlf` na `main` (corrige as 3 falhas em clone novo).
2. **GitHub Actions no Windows** (Python 3.14, PySide6 de verdade, janela invisível): rodaria a suíte inteira, inclusive os 12 testes de janela desta função, a cada pull request, e daria os dados para a dúvida do OpenCV (F5 do roadmap).
3. Os documentos da raiz (`ROADMAP.md`, `PONTO2_REVISAO_25_6.md`) são cópias dos de `md/`; manter só os de `md/` evita as duas versões divergirem.
4. Proteger a `main` no GitHub (exigir pull request).

## 11. O que preciso de você

1. **Criar o ramo `funcoes/ativacao-mapas` no GitHub** (passo a passo na mensagem da entrega) e me avisar; só então eu envio o código, e só para esse ramo.
2. **Aval ou veto** das decisões da seção 6.
3. **Decidir o achado 2.11** (F9 e F10): corrigir já, como a próxima função, ou deixar para a 25.11.
4. **A rodada de testes no Windows** (`Rodar_Testes.bat`, enviando `logs\tests_last_run.txt` e, se existirem, `logs\travamento_qt.txt` e `logs\AutomationStudio.log`). Como você junta várias versões antes de rodar, pode esperar as duas frentes.
5. Combinar com a frente visual quem faz o quê nas telas da 25.7 (`md/DIVISAO_DE_TRABALHO.md`, seção 7).
