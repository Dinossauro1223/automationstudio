# Roadmap do Automation Studio (revisado em 30/10/2026, na integração das frentes visual e de funções)

Este documento diz **onde estamos, o que vem e em que ordem**. Os planos detalhados de cada ponto são feitos um de cada vez, quando chega a vez dele. Aqui ficam o rumo, o que cada ponto traz e o que um ponto exige dos que vêm antes.

## Onde estamos

| # | Ponto | Situação | Versão |
|---|---|---|---|
| 1 | Estabilização | Concluído | 25.4 |
| 2 | Infraestrutura permanente de testes | Entregue na 25.5 e corrigida na 25.6. **Falta a sua rodada no Windows** (a primeira, de 18/10/2026, travou num teste da janela principal; a 25.6 trata disso) | 25.5, 25.6 |
| 3 | Formato de mapa legível e editável (TOML v2) e exportar/importar | Próximo | — |
| 4 | Arquitetura | Planejado | — |
| 5 | Motor e barreiras | Planejado | — |
| 6 | Persistência restante e visão (captura de tela) | Planejado | — |
| 7 | **Esperar por imagem e reagir ao que aparece** (pedido seu de 18/10/2026) | Planejado, é a próxima **versão grande** depois dos pontos acima | — |

**Ordem recomendada: 3 → 4 → 5 → 6 → 7.** O Ponto 7 só fica bem feito em cima dos outros: ele precisa do formato novo (3), de uma visão que rode sem o Qt (4 e 6) e de um motor que saiba esperar, desistir e voltar atrás sem prender teclas (5). Fazê-lo antes custaria refazer. A seção "O que o Ponto 7 exige dos Pontos 3 a 6" diz exatamente o quê.

Antes do Ponto 3 o certo é você rodar a 25.6 (`Rodar_Testes.bat`) e me enviar o resultado: o Ponto 3 vai apoiar os cenários de teste no formato novo, e eu prefiro apoiá-los numa suíte que já rodou inteira no seu computador.

### O que entrou na `main` fora da numeração dos pontos (30/10/2026)

Duas frentes trabalharam em paralelo, cada uma no seu ramo, e foram juntadas e testadas pela conta de integração (`md/DELEGACAO.md`):

| Frente | O que entrou | Situação |
|---|---|---|
| Visual: `visual/novo-tema` | Tema novo: tokens de cor, folha de estilo global, hierarquia de botões (`md/REDESIGN_VISUAL.md`) | Na `main`. Falta a conferência visual no Windows (checklist do `REDESIGN_VISUAL.md`) |
| Funções: `funcoes/ativacao-mapas` ("25.8") | Ativação por mapa (ativo só nesta sessão, sempre ativo ou desativado) e conflito de atalhos, itens MAP-01 a MAP-04 e HK-01 (`md/ENTREGA_25_8.md`) | Na `main`. Falta a conferência de 5 minutos no Windows (seção 2 do `ENTREGA_25_8.md`) |
| Infraestrutura | `.gitattributes` (CRLF nos `.bat`), testes de comportamento do `vision.py` (cobertura do módulo de 18% para 85%), testes automáticos no GitHub Actions, **catálogo de 45 funções do usuário com testes que impedem função perdida ou inacessível** (`md/FUNCOES_DO_USUARIO.md`) e script de medição de desempenho (`md/DESEMPENHO.md`) | Na `main`. O GitHub Actions ainda não foi executado pelo GitHub |

`APP_VERSION` continua `25.6`: fechar a versão e o changelog é do dono.

**Evidência de teste fora do Windows.** Em 30/10/2026 a suíte completa rodou no Linux, com Python 3.14.4 e PySide6 6.12.0 (Qt de verdade, sem janela visível, display virtual): 1680 testes comuns e 36 de janela passaram, nenhum falhou e 7 são `xfail` estritos (lacunas conhecidas). Isso confirma o Qt real e o Python 3.14 para o código da `main`. **Não** substitui a rodada no Windows: os atalhos globais com o `pynput`, o `SendInput`, os `.bat` e o travamento do 22º teste da janela principal seguem sem prova.

**Paralelismo entre as contas.** Aparência e comportamento andam juntos sem problema: a junção de 30/10/2026 deu zero conflitos. Os **Pontos 3 e 4 são diferentes**: mexem nos mesmos arquivos que as duas frentes (`core.py`, `project.py`, `input_system.py`, `main_window.py`, `command_editor.py`). Enquanto um deles estiver em andamento, as outras frentes só fazem mudanças pequenas e localizadas nesses arquivos, e a integração marca uma janela antes. O Ponto 6 (visão) é o mais independente: `vision.py` não é tocado por nenhuma outra frente e já tem testes de comportamento, então pode ser entregue a uma terceira conta. As tarefas de cada conta estão em `md/DELEGACAO.md`; o plano da frente visual (simplificar a interface e preparar o Android) em `md/PLANO_VISUAL.md`; o das funções (versões, achado 2.11, preparação para o Android) em `md/PLANO_FUNCOES.md`; os custos medidos e como otimizar em `md/DESEMPENHO.md`.

## O que cada ponto traz

**Ponto 3 — formato v2.** O mapa passa a poder ser escrito em texto (TOML, um comando por linha), exportado, editado à mão (ou com ajuda do Claude), comparado e importado de volta. "Flins combo" tem hoje cerca de 1,15 MB e a meta é no máximo 100 KB. O leitor deixa de adivinhar: erro de digitação vira aviso com linha e dica, e nenhum registro some em silêncio. Também resolve os achados 2.03 (mapa apagado que ressuscita), 2.04 (`load_map` com ponto no nome), 2.05 (atalho sem tecla) e as 3 lacunas de validação, todos já com teste `xfail` esperando. Decisões D11 a D15: as recomendações do planejamento continuam valendo (TOML; banco mantido com exportar e importar; milissegundos adaptativos; grupos regenerados na leitura; tempo absoluto como hoje).

**Ponto 4 — arquitetura.** Tirar o `import *`, separar o modelo do Qt (o que permite rodar toda a lógica sem PySide6), dividir o `input_system.py` (backends, monitor, motor, gravador), quebrar `MainWindow` e o editor de comandos (2.998 linhas num arquivo só) e ter um lugar só para a configuração de execução.

**Ponto 5 — motor e barreiras.** Uma semântica única para toda espera (processo, tempo, imagem), cancelamento cooperativo em todos os backends, `stop()` sem bloquear, e as hipóteses abertas do Ponto 2: `VkKeyScanW` sem `restype`, `mouse_up` repetido na parada, teste da espera de processo no Windows (`WindowsProcessReadiness`).

**Ponto 6 — persistência restante e visão.** Transações, quarentena de registro inválido, migração versionada, excluir mapa. Na visão: captura de tela segura entre threads, DPI, região e referência, desempenho e testes (hoje `vision.py` tem 24% de cobertura e nenhum teste de comportamento).

## Ponto 7 — esperar por imagem e reagir ao que aparece

### O que você pediu

Em resumo, nas suas palavras de 18/10/2026: usar **imagens como fator de espera até a automação continuar**, para ter automações mais precisas e **respostas diferentes para situações diferentes**. Os três casos que você deu, com o exemplo "abrir o navegador, pesquisar no YouTube e abrir um vídeo":

1. **Computador lento.** Processos em segundo plano atrasam o navegador e a automação digita a pesquisa antes de a tela mudar, e a automação inteira se perde logo no começo. Solução pedida: usar a imagem da tela já carregada, **ou de uma zona específica** (a barra de busca), como espera, sem depender da tela exatamente igual.
2. **Janela que atrapalha.** O YouTube carrega, mas uma atualização abre um pop-up que impede de continuar. Solução pedida: uma **imagem condicional que se espera ver**; se **não aparecer em algum lugar da tela**, executar um comando (apertar F5 para recarregar, ou **uma sequência de comandos**), o que **permite repetir a tentativa e limitar o número de tentativas**.
3. **Para onde voltar.** Depois da tentativa, **repetir a partir do último comando (a quantidade de comandos configurável) ou do início**, conforme o usuário.

### O que o programa já faz hoje (lido do código na 25.6; nada disso foi executado no Windows)

| # | Achado | Confiança |
|---|---|---|
| F1 | **Já existe** "Esperar por imagem" (`WaitConditionType.IMAGE`): arquivo da imagem, precisão (padrão 95%), "verificar a cada" (0,5 s), região (X, Y, largura, altura), "procurar a imagem dentro da região" e tempo limite (0 = esperar para sempre). Roda **uma vez**, antes do primeiro evento do comando, e a espera desloca o relógio da linha do tempo (os comandos seguintes mantêm as lacunas planejadas). | Confirmada (leitura de `conditions.py`, `core.py`, `input_system.py`, `command_editor.py`) |
| F2 | Só há **um desfecho**. Achou: segue. Não achou no tempo limite: `ProcessReadinessError`, estado ERRO, e a automação inteira para. Não existe "tentar de novo", "executar outra coisa", "pular" nem imagem opcional. É exatamente o que acontece no seu caso 2. | Confirmada |
| F3 | No editor, "Atraso após" aparece também para a imagem, mas o motor o **ignora** nesse tipo (só o tipo "processo" e o "tempo" o usam). | Confirmada |
| F4 | A "similaridade" é `1 − média(|diferença|) / 255` sobre uma amostra dos pixels (`compare_images`), com mínimo de 95%. Pela própria fórmula, uma diferença que ocupe até 5% da área comparada (no contraste máximo, preto sobre branco) **não derruba** o 0,95: um pop-up pequeno sobre uma região grande pode passar despercebido, e a "tela carregada" pode ser reconhecida antes da hora. O efeito em telas reais não foi medido. | Confirmada (a fórmula); efeito real, hipótese |
| F5 | O modo "procurar dentro da região" usa `cv2.matchTemplate` e **só funciona com OpenCV**. O OpenCV e o NumPy **não estão** no `requirements.txt` nem no instalador, e a verificação de dependências do `Iniciar.bat` só confere PySide6 e pynput. Sem o OpenCV a função cai para a comparação de tamanho igual, que devolve 0,0 quando a região é maior que a imagem: o "procurar" **nunca encontra** e o programa não avisa. Se o OpenCV existe no seu Python 3.14 é uma **pergunta aberta** (veja "Verificação opcional"). | Confirmada (o código); a instalação no seu computador, desconhecida |
| F6 | `vision.py` importa o PySide6 no topo (sem Qt não há como testar a lógica de visão) e captura a tela **pela thread do motor** (`QGuiApplication.primaryScreen().grabWindow`). Só a tela primária é usada. Se a chamada fora da thread da interface é segura não foi verificado. | Confirmada (o código); a segurança da chamada, hipótese |
| F7 | Com a escala do Windows diferente de 100% (125%, 150%), a captura pode vir em pixels físicos enquanto a região e a imagem de referência estão em outras unidades; como a comparação exige tamanho igual, o resultado seria 0,0. | **Hipótese** (precisa do Windows com escala) |
| F8 | O editor **não captura** a imagem nem a região: você precisa ter o arquivo pronto e digitar X, Y, largura e altura. O único seletor de tela é o de posição do mouse. | Confirmada |
| F9 | O custo de cada verificação é Python puro. Um laço equivalente, medido aqui (Python 3.13, este ambiente), leva cerca de 8 ms para 200×100 e **150 a 200 ms** para regiões de 800×600 a 2560×1440, sem contar a captura nem as conversões do Qt. Com "verificar a cada 0,5 s" são até 30–40% de um núcleo, justamente no computador lento que o caso 1 quer ajudar. | Medida aqui; na sua máquina, a conferir |

**Leitura:** a base existe, mas ela cobre só o começo do caso 1 e, mesmo assim, com três armadilhas silenciosas (F4, F5, F7). Os casos 2 e 3 não existem.

### O que falta, caso a caso

| Caso | O que já ajuda | O que falta |
|---|---|---|
| 1. Computador lento | F1: esperar por imagem, com região | Capturar imagem e região na tela (F8); casar a imagem de verdade, sem as armadilhas F4, F5, F7; custo baixo (F9); opcionalmente **esperar a região parar de mudar** (não exige imagem de referência, e é a forma mais simples de "esperar carregar") |
| 2. Janela que atrapalha | Nada: o único desfecho é parar (F2) | **Desfechos**: o que fazer se achar e o que fazer se não achar; **sequência de recuperação** (F5, ou vários comandos); **limite de tentativas**; o que fazer quando as tentativas acabam |
| 3. Para onde voltar | Nada: a linha do tempo só anda para frente | **Voltar** N comandos ou ao início, soltando antes tudo o que estiver pressionado; contar as tentativas; mostrar tudo isso na interface e no log |

### Proposta: uma espera com vários desfechos

Em vez de acrescentar mais campos soltos à condição atual, a espera passa a ter a forma abaixo (nomes provisórios, em linguagem de usuário):

```
Esperar por imagem
  Procurar:       a imagem [arquivo] [onde: tela inteira | região | janela do aplicativo] [precisão]
  Por quanto tempo:  [tempo limite] [verificar a cada]
  Se aparecer:    continuar (opção: só depois de ficar visível por N ms)
  Se não aparecer até o tempo limite:
      parar com erro                      (padrão: o comportamento de hoje)
    | continuar mesmo assim
    | pular este comando
    | executar o bloco [Recarregar a página]  e depois  tentar de novo
  Tentativas:     até [N]; esgotadas: [parar com erro | continuar | pular]
  Tentar de novo:  [só esta espera | voltar K comandos | voltar ao início]
```

- **Bloco de recuperação**: uma sequência de comandos com nome ("Recarregar a página" = F5; "Fechar o aviso" = Esc, Enter…), guardada no mapa **fora da linha do tempo principal** e executada só quando um desfecho a chamar.
- Os três casos ficam assim: o caso 1 é uma espera por imagem (ou por "região parada") com "parar com erro" como padrão; o caso 2 é a mesma espera com o desfecho "executar o bloco F5 e tentar de novo, até 3 vezes"; o caso 3 é o "tentar de novo: voltar K comandos / ao início".
- Imagem que **pode aparecer sem aviso** (o pop-up): a primeira versão a trata como **uma verificação nos pontos de espera** ("se esta imagem estiver na tela agora, execute o bloco X antes de seguir"), e não como uma thread que vigia a tela o tempo todo. A verificação nos pontos de espera é previsível e testável com o relógio virtual; um vigia em segundo plano concorreria com o envio de teclado e mouse e é tema da fase 7.D.

### Fases (cada uma vira uma versão e fecha com o critério dela)

**7.A — Esperar a tela ficar pronta (caso 1).**
Capturar imagem e região na própria tela (seletor de região com o mouse, imagem gravada junto do mapa). Casamento de imagem de verdade, que não deixa passar um elemento pequeno (F4) e que avisa se faltar a dependência (F5). Região parada ("esperar a tela parar de mudar") como alternativa. Resolver a escala do Windows (F7) e a captura fora da thread da interface (F6). Custo baixo por verificação (F9).
*Critério:* num cenário simulado de "máquina lenta", a imagem aparece em 7 s virtuais e a automação segue **no instante em que ela aparece**; um elemento de 4% da região é distinguido; o teste real no Windows (Tk com padrão conhecido, em 100%, 125% e 150%) captura a região certa.

**7.B — Desfechos e tentativas (caso 2).**
O painel "Se não aparecer…", os blocos de recuperação, o limite de tentativas e o que fazer quando acabam; tudo aparece no log ("tentativa 2 de 3: executando Recarregar a página").
*Critério:* cenário simulado "pop-up": a imagem só aparece depois de 2 recargas, e a automação segue na 3ª tentativa; com a imagem nunca aparecendo, a automação para com erro **depois de exatamente N tentativas**, com o teclado solto.

**7.C — Voltar atrás (caso 3).**
Voltar K comandos ou ao início, com K configurável. O motor passa a andar por posição na linha do tempo (hoje é um `for` que só avança), solta tudo o que está pressionado antes de voltar e reposiciona o relógio. As sobreposições do mapa gravado (um comando que começa antes de o anterior terminar) precisam de regra explícita: ao voltar K comandos, o ponto de retorno é o **início do comando** K posições antes, e o que estava em andamento é encerrado.
*Critério:* nenhuma tecla ou botão preso em nenhuma saída (fim, parada, erro, esgotar tentativas), provado com os 3 mapas reais e com mapas sintéticos com sobreposição.

**7.D — Imagens que surgem sem aviso e diagnóstico.**
Verificação "se esta imagem estiver na tela, execute o bloco X" numa faixa de comandos; botão "Testar agora" no editor; quando uma espera falha, gravar a captura de tela final e a melhor correspondência em `logs\` para entender o porquê.
*Critério:* cenário simulado "pop-up no meio da faixa" tratado sem parar a automação.

### Como será testado (sem tela de verdade, com o que a 25.5 e a 25.6 já deixaram)

- Uma **fonte de tela** como interface (a real usa o Qt; a de teste, `FakeScreen`, entrega quadros previstos por instante do **relógio virtual**: "a imagem aparece em t = 7 s"). Isso permite testar o motor inteiro sem monitor, em milissegundos, como já se faz com as esperas por tempo.
- O casamento de imagem é uma função pura (matriz de pixels → pontuação), testada com imagens sintéticas: elemento pequeno, ruído, deslocamento, escala, imagem maior que a região, região vazia.
- Cenários de ponta a ponta com resultado de referência (golden), como os de hoje: "máquina lenta", "pop-up", "F5 em laço", "tentativas esgotadas", "parada no meio de uma tentativa solta tudo", "voltar K comandos nos 3 mapas reais".
- O verificador de defeitos plantados ganha defeitos novos para cada regra (contagem de tentativas, soltar antes de voltar, K comandos para trás etc.).
- No Windows de verdade, em modo opt-in como o `windows` atual: uma janela de teste com padrão conhecido para conferir captura, coordenadas e escala. O seletor de região com o mouse não dá para automatizar: entra no roteiro manual.

### Riscos e limites (conhecidos desde já)

- **Captura**: jogos em tela cheia exclusiva e conteúdo protegido podem sair pretos; a captura de vários monitores hoje não existe (só a tela primária); a própria janela do Automation Studio pode estar na frente da região. Nada disso foi medido: entra na verificação da fase 7.A.
- **Dependência**: o casamento de imagem rápido pede OpenCV (que traz o NumPy). Eu **não confirmei** que haja pacote para o Python 3.14 no Windows (tentei consultar o PyPI daqui, sem acesso à rede; só tenho uma página de terceiros). Se não houver, a alternativa é um casamento próprio mais limitado. Fica na decisão D19, depois da verificação opcional abaixo.
- **Sobreposição de comandos**: voltar "K comandos" num mapa gravado, onde 568 dos 932 pares consecutivos de "Flins combo" se sobrepõem, exige a regra descrita em 7.C. Sem ela, "voltar" geraria teclas presas ou repetidas.
- **Laços sem fim**: toda repetição precisa de limite; o padrão deve ser **finito** e o "ilimitado" uma escolha explícita (e sempre interrompível pela parada de emergência).
- **Falso positivo × falso negativo**: uma precisão alta demais faz a automação desistir à toa; uma baixa demais faz continuar cedo. Por isso o "Testar agora" e o registro da melhor correspondência (7.D) valem tanto quanto o casamento.

### O que o Ponto 7 exige dos Pontos 3 a 6

| Ponto | O que precisa estar lá |
|---|---|
| **3 — formato** | Reservar no esquema v2, desde a primeira versão do formato: condições **com desfechos** (`se_aparecer`, `se_nao_aparecer`, `tentativas`, `voltar`), **blocos nomeados** de comandos fora da linha do tempo e **referência a imagens** (caminho relativo à pasta do mapa; exportar e importar levam as imagens junto, em pasta ou pacote). Hoje o caminho da imagem é absoluto e se perde ao levar o mapa para outro computador. Campos desconhecidos de versões futuras devem gerar **aviso**, não erro. |
| **4 — arquitetura** | `vision.py` sem PySide6 no topo: a captura vira uma interface (`FonteDeTela`) com a implementação do Qt isolada; o casamento de imagem em módulo puro. O painel de condições do editor (hoje dentro de um arquivo de 2.998 linhas) sai para um componente próprio **antes** de ganhar desfechos e blocos. |
| **5 — motor e barreiras** | Toda espera devolve um **resultado** (satisfeita, estourou o tempo, interrompida) em vez de lançar `ProcessReadinessError`; uma política por espera decide o que fazer com cada resultado. O laço de execução anda por posição (para poder voltar), soltar tudo é uma operação única e testada, e a contagem de tentativas vive no motor. Sem isto a 7.B e a 7.C viram remendo. |
| **6 — persistência e visão** | Imagens de referência guardadas junto do mapa (e levadas por exportar/importar, com transação); captura segura entre threads, escala do Windows, região e desempenho resolvidos e **testados** (a base da 7.A); `FonteDeTela` falsa pronta para os testes. |

### Decisões que o Ponto 7 vai pedir (as recomendações estão em negrito)

| # | Decisão | Recomendado |
|---|---|---|
| D17 | Onde moram as sequências de recuperação | **Blocos nomeados dentro do mapa, fora da linha do tempo** (alternativas: comandos marcados "só para recuperação" na própria lista; um mapa à parte) |
| D18 | "Voltar K comandos": como contar | **K comandos na ordem de início, voltando ao começo do comando** (como você descreveu); um "ponto de retomada" marcado pelo usuário fica como evolução |
| D19 | Casamento de imagem e dependência | **OpenCV (`opencv-python-headless`) como dependência obrigatória, se houver pacote para o 3.14**, com aviso claro na verificação de dependências; senão, um casamento próprio mais limitado, assumido como tal *Verificado em 30/10/2026: há pacote para o 3.14 no Windows, `opencv-python-headless` 5.0.0.93 (`cp37-abi3`) e `numpy` 2.5.4 (`cp314`); instalar é possível, mas não foi testado em execução no Windows.* |
| D20 | Como capturar a tela | **Manter o Qt, mas fora da thread do motor (a captura é pedida à thread da interface)**, depois de medir no Windows com escala 100%, 125% e 150% (alternativa: GDI via ctypes) |
| D21 | Quando as tentativas se esgotam | **Parar com erro** (o comportamento de hoje), configurável por espera para "continuar" ou "pular" |
| D22 | Pop-ups sem aviso | **Verificação nos pontos de espera na primeira versão** (fase 7.D), sem vigia em segundo plano |
| D23 | Onde ficam as imagens | **Junto do mapa, com caminho relativo e cópia ao adicionar** (junto com o exportar/importar do Ponto 3) |

Não preciso delas agora. Elas só entram na pauta quando o Ponto 5 estiver fechado, e continuo sob a sua autorização para decidir e avisar o que escolhi e por quê.

### Verificação opcional na sua máquina (cerca de 10 minutos, sem pressa)

Só para eu chegar ao Ponto 7 com dados em vez de suposições (F5, F7, F9). **Não é necessária para a 25.6.**

1. Abra um terminal e rode `py -3.14 -c "import cv2, numpy; print(cv2.__version__)"`. Se aparecer um número, o OpenCV já existe; se der erro de módulo, não existe (e isso responde a parte de F5).
2. Anote a **escala do Windows** (Configurações → Sistema → Tela → Dimensionar: 100%, 125%, 150%…).
3. No programa, faça um mapa de 1 comando de espera: "Esperar por imagem", com uma imagem pequena que **esteja visível na tela** (um recorte seu, em PNG), com e sem "procurar a imagem dentro da região", deixando a região em 0, 0, 0, 0 e depois com a região do recorte. Diga em cada caso se **achou ou ficou esperando** (ponha tempo limite de 10 s para não ficar preso).
4. Me conte o resultado. Com ele eu sei se F5 e F7 acontecem de verdade no seu computador.

## Itens menores (fora dos pontos)

- O título da janela **nunca mostrou a versão** (o `__init__` a coloca, mas `_update_status_label` a troca por "Automation Studio — ● PARADO" na construção). Se você quiser a versão no título, é uma mudança do programa a decidir à parte; hoje ela só aparece nos arquivos e no README.
- `main_window.py` tem uma função interna `size_toolbar` que nunca é chamada (e que, se fosse, se reagendaria sozinha com `QTimer.singleShot(0, ...)`) e um `toolbar_hint` que nunca é criado. Código morto; limpar no Ponto 4.
- **F9 e F10 pausam e continuam (achado 2.11, corrigido em 1/11/2026).** Ramo `funcoes/pausar-continuar-teclas`, na mesma versão (25.8); aguarda a integração e a conferência do dono no Windows (`md/ESPEC_PAUSA_TECLAS.md`, `md/ENTREGA_PAUSA_TECLAS.md`). O defeito era que o motor tinha `pause()` e `resume()`, mas nada na janela os chamava: as teclas eram registradas e o disparo sumia em `_on_hotkey_triggered` (achado em `md/ENTREGA_25_8.md`, seção 7). O `xfail` estrito saiu: `tests/static/test_lacunas_de_ligacao.py` virou o guarda permanente `tests/static/test_ligacao_controle.py`, que falha se uma tecla de controle registrada ficar sem ramo na janela.
- **Teclas de controle: apagar o campo devolve o padrão.** Em Configurações, esvaziar o campo de uma tecla de controle (pausar, continuar, parar tudo) não a desativa: o diálogo e `set_control_hotkeys` descartam campos vazios e `get_control_hotkeys` preenche com o padrão (F9, F10, F12). Se for intencional, vale um texto no diálogo; se não, é um ponto à parte. O diálogo também não tem campos para as teclas de gravar (F8) e cancelar gravação (F11). Achado ao corrigir o 2.11; não mexido.
- **O "plano 25.7" não está no repositório.** As entregas das duas frentes citam um plano 25.7 (itens MAP-01 a MAP-04, HK-01, decisões D24 a D34) que não está em `md/`; este roadmap vai até D23. Ele precisa ser commitado para que todas as contas trabalhem da mesma fonte.
- **Lacuna F4 com teste.** A comparação de imagens do `vision.py` é uma média: um elemento de 4% da região que falta na tela dá 0,96, acima da confiança padrão (0,95), e a espera termina como se ele estivesse lá. Está guardada como `xfail` estrito em `tests/unit/test_vision_comportamento.py`; sai quando a fase 7.A trocar o casamento. **Custo medido** (Linux, Python 3.14, uma verificação de `compare_images`): cerca de 22 ms numa região de 400x300, 46 ms em 1000x1000 e 113 ms em 1920x1080. O passo da amostragem usa `int(...)` e dá 518 mil amostras em 1080p, o dobro do alvo de 250 mil que o próprio código descreve; com o intervalo mínimo de 50 ms a verificação passa a durar mais que a pausa. Não foi mexido, porque a 7.A troca o casamento por inteiro; se a 7.A demorar, trocar `int` por `math.ceil` no passo é a correção de uma linha.
- Arquivos duplicados na raiz (`ROADMAP.md`, `PONTO2_REVISAO_25_6.md`) eram cópias idênticas dos de `md/` e foram removidos; `ALTERACOES_25_5_para_25_6.diff` (230 KB) segue na raiz, à espera de decisão do dono.
- **Código morto na interface.** A página do tutorial antigo (índice 0 da pilha de páginas) e o botão "Começar a usar" nunca são exibidos por nenhum código; sair junto com `size_toolbar` e `toolbar_hint` (P1 do `md/PLANO_VISUAL.md`).
- **Custos medidos na interface** (31/10/2026, Linux): pintar a timeline 117 ms por quadro, abrir uma automação de 933 comandos no editor 243 ms, reaplicar o tema 281 ms. Causas e o que fazer em `md/DESEMPENHO.md`, seção 5.
- Quando o programa é aberto como administrador, o diretório atual é `C:\Windows\System32` (visto no seu log). Não faz diferença: o programa só usa o diretório atual para escrever diagnósticos, e os caminhos dele partem da pasta do script.
