# CHANGELOG V25

## 25.6 — correção da primeira rodada de testes no Windows

O programa não mudou: em `automationstudio/` só o número da versão. A 25.6 responde à primeira rodada completa que você fez
(18/10/2026, Windows, Python 3.14, PySide6 de verdade), que mostrou três problemas, todos da infraestrutura de testes e dos
`.bat`, e nenhum do programa em si. As provas, os níveis de confiança e o que **não** foi verificado estão em
`md/PONTO2_REVISAO_25_6.md`; o planejamento das próximas versões, com a espera por imagem, em `md/ROADMAP.md`.

### Correções
- **`Iniciar.bat` com a pasta de usuário acentuada.** O seu log mostrava o caminho do Python com a letra errada e o aviso de que o
  `pythonw.exe` não existia, embora existisse. O `.bat` copiava o texto que o Python imprimia (`for /f`) para uma variável, e o
  cmd o lia na página de código errada. O programa agora abre direto por `pyw.exe -3.14` (o mesmo Python do `py.exe`, sem janela de
  terminal), sem copiar caminho nenhum; sem o `pyw.exe` usa o `py.exe`. Os Pythons auxiliares que escrevem no log rodam em modo
  UTF-8 (`PYTHONUTF8=1`), e a variável é limpa antes de abrir o programa, que roda como antes. Causa **altamente provável**: decorre
  do funcionamento do cmd, mas o `cmd.exe` não roda no ambiente de desenvolvimento. Os `.bat` têm só ASCII e um teste estático
  passa a exigir isso, e também o modo UTF-8 e a ausência de `for /f` sobre a saída do Python.
- **O `F` da rodada era erro do teste, não do programa.** O primeiro teste da janela principal esperava a versão no título da
  janela. O título nunca mostrou a versão: o `__init__` a coloca, mas `_build_status_bar()` o troca em seguida por
  "Automation Studio — ● PARADO". O teste agora confere o título que o programa de fato mostra. Confirmada pela leitura do código;
  a sua próxima rodada confirma no Qt de verdade. (Se você quiser a versão no título, é uma mudança do programa, para decidir à parte.)

### O travamento do 22º teste da janela principal: causa ainda desconhecida
O teste ficou 180 s parado dentro de `QApplication.processEvents()` e o pytest-timeout encerrou a rodada inteira, sem dizer o que
o Qt fazia. **Não sei a causa, e não consegui reproduzir aqui** (sem Windows e sem o PySide6 de verdade). O que o seu log prova: o teste
parou dentro do `processEvents()`, só havia duas threads do Python vivas e a pilha do Python não tem nenhum slot em execução
acima da linha do teste, o que aponta para código nativo do Qt. As hipóteses, todas **não confirmadas**: acúmulo do que os 21
testes anteriores deixaram na fila (eles nunca processaram eventos nem destruíram as suas janelas, e o `processEvents()` fora de
um laço de eventos não executa os `deleteLater()`), o custo do primeiro `show()`, um temporizador que se reagenda sem parar e
um problema nativo do Qt `offscreen` no Windows com o Python 3.14. Em vez de adivinhar, a 25.6 faz o próximo travamento deixar
provas e impede que ele derrube a rodada:
- cada teste da janela principal roda num **processo próprio**, com tempo limite (marcador `isolado`): um travamento ou uma queda
  do Qt reprova só aquele teste e a rodada continua;
- nada de um teste sobra para o seguinte: as janelas são fechadas e destruídas e a fila de eventos é esvaziada ao fim de cada teste;
  `processar_eventos` (passadas mínimas e limite de tempo) substitui o `processEvents()` solto;
- um **vigia** em cada teste de janela: aos 60 s grava `logs\travamento_qt.txt` (últimos eventos do Qt, mensagens do Qt, pilhas
  das threads e um diagnóstico: Qt bloqueado ou em laço de eventos) e encerra o processo com o código 86; um alarme nativo de
  reserva dispara 15 s depois se a thread do Python não conseguir rodar;
- se um teste travar fora do isolamento, o passo roda de novo sem ele (até 3 vezes) e a rodada termina com o código 86: ela
  **não** conta como limpa;
- se **3 testes da janela principal travarem em sequência**, o passo isolado desiste dos que faltam e diz quantos não rodaram
  (estado "NÃO RODOU" no resumo, e a rodada também não conta como limpa; o código de saída é 86, ou 1 se algum teste também falhou). Três travamentos seguidos indicam um problema do
  ambiente e não de um teste, e continuar gastaria cerca de 1 minuto por teste só para repetir o mesmo relatório. Para rodar um dos
  que faltam: `Rodar_Testes.bat completo -k <parte do nome>`.

### Projeto e testes
- `Rodar_Testes.bat`: o passo comum roda `-m "not isolado"` e o passo isolado roda um teste por processo; cada falha é impressa
  **na hora** (e não só no fim, que a rodada de 18/10 nunca alcançou); o fim traz um RESUMO (OK, FALHOU, TRAVOU, QUEDA) e diz quais
  arquivos enviar. O modo `cobertura` mede também os processos isolados (`coverage run -p` e `combine`).
- O verificador de defeitos plantados roda por padrão com o dublê de widgets, e só usa o PySide6 de verdade com
  `AS_MUTACOES_QT_REAL=1` (ele não isola testes um por processo). O catálogo passou de 225 para 292 defeitos: os novos cobrem o
  lançador (inclusive a parada depois de 3 travamentos seguidos), o diagnóstico, a higiene das janelas, o relato das falhas e os `.bat`.
- Verificação estática nova: todo teste que abre a janela principal precisa ser marcado `isolado`.
- Com o pytest real: 1267 passam, 242 pulados (precisam do Qt), 5 xfail (modo lógica, `rapido`) e 1478 passam, 31 pulados, 5 xfail (dublê de widgets); 0 falhas nos dois. O executor mínimo dá o
  mesmo resultado, teste a teste.
- **Não verificado** (precisa da sua máquina): o `.bat` no `cmd.exe`, o comportamento dos fixtures, do filtro de eventos e do
  tratador de mensagens no PySide6 de verdade, a medição de cobertura com o `coverage.py`, e a causa do travamento.

## 25.5 — infraestrutura de testes (Ponto 2 da auditoria)

A parte principal da versão é a infraestrutura permanente de testes (`tests/`, `Rodar_Testes.bat`). Medir a cobertura mostrou
trechos que nenhum teste executava, e escrever os testes desses trechos revelou os defeitos abaixo. Os níveis de confiança e as
provas estão em `md/PONTO2_IMPLEMENTACAO_25_5.md`.

### Correções
- **Editor de comandos: abrir um comando e salvar sem mexer em nada não o altera mais (2.07).** O diálogo reescreve o comando
  inteiro a partir dos campos da tela, e vários campos não eram carregados. Na 25.4, abrir e salvar sem mexer:
  - gravava o item-guia "Nenhum aplicativo selecionado" como processo a esperar em todo comando (o motor esperaria um processo
    com esse nome; leitura do código, não reproduzido no Windows);
  - trocava "Manter pressionado" e "Soltar" por "Pressionar e soltar";
  - trocava teclas que a lista fixa não tem (as que o gravador produz, como ";") e a tecla Espaço por "A";
  - gravava o item-guia como aplicativo a abrir quando o executável não estava na lista;
  - reativava um comando desativado;
  - apagava o grupo quando o painel lateral não conhece o mapa;
  - zerava a duração do trajeto de um movimento mesclado;
  - cortava em 3600 s um início ou tempo de espera maior que 1 hora;
  - e, ao trocar de comando com o painel aberto, deixava campos do comando anterior (início, atraso, duração, rolagem, grupo,
    condições, processo) para serem gravados no novo.
  Hipótese (depende do PySide6 real): `QPoint` não aceita `ponto[0]`, e então abrir o editor de um "Mover o mouse" falhava; a
  correção (`x()` e `y()`) vale nos dois casos.
- **A pré-visualização não altera mais o mapa (2.09).** `timeline_rows` reencadeava os inícios do mapa aberto antes de montar as
  linhas. Medido na 25.4: no "Flins combo", só abrir a pré-visualização mudava o início de 932 dos 933 comandos e a duração de
  64,871 s para 94,307 s; no "Exemplo — Primeira automação", de 1,960 s para 3,160 s. Na 25.5, nenhum início muda.
- **Mover, reordenar e reencadear (reflow) não desfazem mais as sobreposições (2.10).** A distância entre dois comandos era cortada
  em zero, mas num mapa gravado a sobreposição é o normal (o mouse se move com uma tecla pressionada). Medido na 25.4, no
  "Flins combo": arrastar uma linha (do comando 300 para o 305) mudava o início de 932 comandos e a duração de 64,871 s para
  94,307 s, e soltar uma linha no mesmo lugar também mudava 932. Na 25.5 mudam só os 5 comandos do trecho que trocou de lugar, a
  duração se mantém, e soltar no mesmo lugar não muda nada. A distância passa a ter sinal e `reflow_timeline(preserve_gaps=True)`
  é a identidade (D6).
- **Parada durante o envio de uma tecla: a tecla não fica mais presa (2.01).** Se a parada chegasse depois de a tecla ser enviada e
  antes de ser registrada como pressionada, `stop()` não a soltava. A thread do motor agora solta o que sobrou ao sair por parada.
- **Fallback do pynput:** PRINTSCREEN, SCROLLLOCK e NUMLOCK passam a ser reconhecidos (2.06).
- **Gravador (D3):** o intervalo de amostragem do mouse passa a valer, e a última amostra descartada pelo intervalo é mantida, então
  o cursor não para antes do lugar onde o movimento terminou.
- **Botões laterais (D1):** nenhuma mudança visível. A gravação e os atalhos já usavam os nomes do sistema, porque a troca X1↔X2 era
  aplicada duas vezes e uma desfazia a outra, e só o mouse virtual mostrava o par trocado. Agora há uma única troca, só na
  exibição (`display_mouse_button_name`), controlada por `DISPLAY_SWAPS_SIDE_BUTTONS`.

### Projeto e testes
- Relógio injetável (`core.SystemClock`) no motor, no gravador e no backend Mock, e backend Win32 com `user32` injetável: os testes
  rodam em tempo virtual (`FakeClock`), sem esperar e sem enviar input real.
- Suíte nova em `tests/`, dividida em `unit`, `engine`, `contract` (os 3 backends contra o mesmo contrato), `persistence`, `static`,
  `gui`, `scenarios`, `regression` e `e2e_windows`. Com o pytest real: 1156 testes passam, 241 são pulados (precisam do Qt real) e
  5 são xfail de defeitos conhecidos; com o dublê funcional de widgets, 1366 passam, 31 são pulados e 5 xfail; 0 falhas nos dois.
- Os 3 mapas reais (`tests/data/legacy_maps.json.gz`) e 8 arquivos golden são fixtures permanentes.
- `Rodar_Testes.bat` com os modos `rapido`, `completo`, `windows`, `repetir`, `cobertura`, `mutacoes` e `instalar`; o log fica em
  `logs\tests_last_run.txt`. Nenhum modo envia input real, exceto `windows`, que pede a confirmação digitada "SIM".
- Verificador de defeitos plantados (`tests/testsupport/mutacoes.py`): 225 defeitos introduzidos um de cada vez numa cópia do projeto;
  a suíte inteira precisa reprovar cada um. Retomável (`--retomar`).
- Catraca de cobertura por grupo de módulos (`tests/testsupport/catraca_cobertura.py`): a primeira execução de `cobertura` registra a
  linha de base na sua máquina; uma queda maior que 1 ponto reprova.
- Verificações estáticas permanentes do código e dos testes: nomes indefinidos, métodos duplicados, sinais sem `connect`, constantes
  copiadas fora do `core`, `\n` literal, `import *` e código sem referência (com catraca), `py -3` e fim de linha nos `.bat`, versão
  igual em todo lugar, módulos removidos do Python, `return`/`break`/`continue` dentro de `finally` (PEP 765, aviso de sintaxe no
  Python 3.14), caminhos de usuário escritos no código, uso do input real fora dos módulos permitidos, esperas reais nos testes,
  golden órfão e o subconjunto do pytest que o executor mínimo e o pytest estrito entendem.
- Testes ponta a ponta no Windows (`tests/e2e_windows`): sempre rodam simulados; os 9 testes reais só rodam com `Rodar_Testes.bat windows`.
- `tests/README.md` explica como rodar, como escrever um teste novo e o que a suíte não prova.

### Pendências que dependem de decisão
- Ponto 3 (formato TOML v2 do mapa): 2.03 (migração do JSON antigo ressuscita mapas excluídos), 2.04 (`load_map(nome)` perde o
  texto depois do último ponto do nome) e 3 lacunas de validação (botão de mouse desconhecido, "Abrir aplicativo" sem alvo,
  `repeat_count` menor que −1): são os 5 testes `xfail` (falha esperada) até lá. 2.05 (não há como desligar um atalho de controle)
  está registrado por um teste de caracterização.
- Ponto 5: a espera por processo (`WindowsProcessReadiness.wait`) não tem teste. Ponto 6: a captura e a comparação de imagens (`vision.py`).
- A suíte não foi executada no Windows, no Python 3.14 nem com o PySide6 real: veja `md/PONTO2_IMPLEMENTACAO_25_5.md`.

## 25.4 — estabilização (Ponto 1 da auditoria)

### Correções
- Mover o mouse, rolar e "Esperar" deixam de ser recusados pela validação: duração 0 só é erro em tecla e botão do mouse.
- IDs de comandos novos não colidem mais com os de mapas salvos antes; excluir um comando não remove outro.
- "Próxima automação" volta a funcionar (o sinal do motor não estava ligado ao slot da janela).
- Miniatura da condição de imagem implementada; antes, escolher ou editar a imagem gerava erro.
- A lista de aplicativos passa a incluir python, cmd, powershell e wt encontrados no PATH (faltava `import shutil`).
- Backend pynput de fallback corrigido; botão ou tecla desconhecida agora é erro, e não outra tecla.
- "Intervalo entre caracteres" e os padrões de espera de aplicativo passam a valer no motor (fonte única: `core.set_runtime_defaults`).
- A parada de emergência interrompe a digitação de textos longos e a janela não congela até o fim do texto.
- Pausar durante uma espera (imagem, processo, condições) não envia mais input enquanto pausado.
- A espera por condição desloca o relógio da timeline: o comando mantém a duração e os seguintes mantêm as lacunas.
- Proteção de instância única aplicada: a segunda janela avisa e fecha.
- A tecla AltGr pode ser enviada pelo backend Win32.
- `resizeEvent` duplicado unificado; o rótulo "Total" da Timeline passa a refletir a duração do mapa.
- Log de início sem "\n" literal; o log de falha de importação não apaga mais o log da sessão.
- Conexões SQLite fechadas ao fim de cada operação.
- Mapas gravados que não puderam ser lidos não somem mais em silêncio: aviso na janela e registro no log; nada é apagado do banco.
- `engine.run()` na janela trata também a transição de estado inválida.

### Projeto
- Python 3.14 definido em `python_version.txt`; scripts `.bat` com fim de linha do Windows e sem `py -3`.
- Versão única (`APP_VERSION`); título da janela e README em dia.
- Testes: 4 testes corrigidos, suíte de regressão do Ponto 1 (`tests/test_ponto1_reproducao.py`), `pytest.ini`, `requirements-dev.txt` e `tests/conftest.py`.

### Pendências que dependem de decisão
- Botões laterais X1/X2 (D1), intervalo de amostragem do mouse (D3), excluir e exportar mapa (D5) e o teste de reflow (D6).

## 25.3
- Nova camada de visão em memória para comparação de imagens.
- Condição “Esperar por imagem” com arquivo de referência, precisão, frequência e região de interesse fixa.
- Captura via QScreen, sem PNG temporário durante a verificação.
- Miniatura da imagem de referência na interface.
- Erros de captura e timeout são reportados explicitamente.
- OCR completo e template matching espacial ficam fora desta primeira consolidação para evitar introduzir dependências pesadas antes de estabilizar o backend básico.

- Busca espacial opcional com OpenCV quando instalado; o modo fixo continua funcionando sem essa dependência.
- Interrupção durante condições não permite que o evento protegido seja executado.
- Região de interesse e miniatura persistem na condição.
