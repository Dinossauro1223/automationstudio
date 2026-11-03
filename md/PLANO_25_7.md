# Plano 25.7: o roadmap que incorpora o "Planejamento de desenvolvimento da versão 25.7" do dono

> **Origem.** Este é o roadmap que a frente de funções entregou ao dono em 26/10/2026, escrito a partir do "Planejamento de desenvolvimento da versão 25.7" (24/10/2026) depois de conferir cada apontamento contra o código (`md/CONFIRMACAO_APONTAMENTOS_25_7.md`, entregue junto e commitado junto). O texto original do plano do dono não está em nenhum arquivo do repositório: o que existe é este documento, que o incorpora, e o relatório de confirmação, que repete cada apontamento com o veredito. Foi commitado a pedido da integração (`md/DELEGACAO.md`, seção 5, item 5), porque as entregas das duas frentes citam dele os itens MAP-01 a MAP-04 e HK-01, o "item 2.3" e as decisões D24 a D34, e elas não estavam em `md/`. O texto abaixo é o da entrega de 26/10, com uma única atualização, de 31/10/2026: o achado 2.11 (F9 e F10), corrigido no ramo `funcoes/pausar-continuar-teclas` (as referências a esse ramo e aos documentos dele valem depois da junção do ramo na `main`).
>
> **Como ler junto com o resto de `md/`.** O `ROADMAP.md` (revisado pela integração em 30/10/2026) descreve o que está na `main`; o `PLANO_FUNCOES.md` e o `PLANO_VISUAL.md` dizem o que cada frente faz agora. Este documento vale como **fonte do plano do dono**: a numeração dele (2.1 a 2.4, 3.1, 3.2, 4 a 8), a ordem das versões (seção 5), as telas da 25.7 (seção 4.2), os IDs de teste (seção 12) e as decisões D24 a D34 (seção 13).
>
> **Divergência que o dono precisa decidir.** Depois da 25.8, este documento põe como próxima função a **timeline avançada (2.4, versão 25.9)**, seguida da espera por imagem (25.10) e dos grupos (25.11), e deixa o **formato v2 para a 25.12** (decisão D34). O `ROADMAP.md` e o `PLANO_FUNCOES.md` seguem a ordem dos Pontos 3, 4, 5, 6 e 7 da auditoria (formato v2 primeiro). Os dois foram escritos sem este documento. Até o dono dizer qual vale, as frentes não devem tratar nenhuma das duas ordens como definitiva.
>
> **O que está desatualizado.** A seção 2 ("Onde estamos") e a 14 ("O que preciso de você") são de 26/10, antes da integração de 30/10; os "itens menores" (seção 15) foram superados pelos do `ROADMAP.md`. As linhas de código citadas aqui e no relatório de confirmação são as da 25.6.

---

Este documento diz **onde estamos, o que vem e em que ordem**. Ele incorpora o seu "Planejamento de desenvolvimento da versão 25.7" (24/10/2026), depois de conferido contra o código (`md/CONFIRMACAO_APONTAMENTOS_25_7.md`), e a sua instrução de que **a próxima versão traga todo o visual do roadmap e que, nas versões seguintes, as funções passem a funcionar uma a uma**. Os planos detalhados de cada função são feitos um de cada vez, quando chega a vez dela.

## 1. Regras que valem para tudo

1. **Visual primeiro, funções depois.** A 25.7 entrega todo o visual do roadmap; cada função passa a funcionar na sua versão, uma por vez (seção 5).
2. **Previsto não é disponível.** Nada planejado aparece como se funcionasse: nem na tela, nem no tutorial, nem nos textos (seção 4.3).
3. **O formato dos mapas continua bloqueado** até os itens 2.1 a 2.4 estarem implementados e aprovados nos testes de regressão (seção 6 diz o que conta como "alterar o formato").
4. **Processo de 8 etapas** para toda função nova, mudança de comportamento e correção de defeito (seção 11).
5. **Versão estável intacta.** A 25.6 não é sobrescrita; a 25.7 sai como **candidata**, com número e arquivo próprios.
6. **Uma função por vez.** Não avanço enquanto a anterior estiver parcial, quebrada ou sem validação suficiente.
7. **Decido e aviso.** Continuo autorizado a decidir os pontos pendentes, dizendo o que escolhi e por quê; as escolhas desta edição estão na seção 13 e você pode vetar qualquer uma.
8. Prioridade de sempre: precisão, segurança da implementação, testabilidade, organização e, por último, velocidade. Sem inventar defeitos; cada achado com a sua confiança.

## 2. Onde estamos

**Pontos da auditoria** (os nomes se mantêm; outros documentos os citam):

| # | Ponto | Situação | Versão |
|---|---|---|---|
| 1 | Estabilização | Concluído | 25.4 |
| 2 | Infraestrutura permanente de testes | Entregue na 25.5, corrigida na 25.6. **Falta a sua rodada no Windows** (a de 18/10/2026 travou num teste da janela principal; a 25.6 trata disso) | 25.5, 25.6 |
| 3 | Formato de mapa legível (TOML v2) e exportar/importar | **Bloqueado** pelo seu plano até 2.1 a 2.4 aprovados; entra na 25.12 | — |
| 4 | Arquitetura | Planejado. Os componentes novos já nascem separados desde a 25.7 | — |
| 5 | Motor e barreiras | Planejado; entra na 25.13 | — |
| 6 | Persistência restante e visão (captura de tela) | Planejado; a parte de visão entra na 25.10 | — |
| 7 | Esperar por imagem e reagir ao que aparece (pedido de 18/10/2026) | Planejado: fase 7.A na 25.10, 7.B e 7.C na 25.14, 7.D na 25.15 | — |

**Como a numeração do seu plano 25.7 se encaixa aqui:**

| Plano 25.7 | Neste roadmap |
|---|---|
| 2.1 Tutorial | Seção 4: corrigido **de verdade** na 25.7 |
| 2.2 Sidebar | Seção 4: corrigida **de verdade** na 25.7 |
| 2.3 Ativação de mapas | Prévia na 25.7; funciona na **25.8** |
| 2.4 Timeline avançada | Prévia na 25.7; funciona na **25.9** |
| 3.1 Espera por imagem | É o **Ponto 7** (seção 8); funciona a partir da **25.10** |
| 3.2 Grupos, repetições e condições | Seção 9; funciona na **25.11** |
| 4 IA por API | Seção 10: só documentada |
| 5 Processo, 6 Testes, 7 Ordem | Seções 11, 12 e 5 |
| 8 Condições para iniciar | Seção 3 |

## 3. Base conferida (item 8 do plano)

A base é a **árvore da 25.6**. O código do programa é o da 25.5; só a string de versão difere. Não usei versão antiga como substituta. Módulos responsáveis (linhas aproximadas):

| Área | Onde |
|---|---|
| Tutorial | `tutorial.py` (253 linhas) e o roteiro em `main_window.py` 916-1120 |
| Sidebar | principal: `main_window.py` 543-600 e 611-870; formulários e rolagem: `command_editor.py` 270-293, 843-934, 1262; da timeline: `timeline.py` 819-881 |
| Mapas e atalhos | `main_window.py` 1241-1330, 1418-1560, 1630-1680; `input_system.py` 589-704 (`GlobalHotkeyManager`); `project.py` |
| Timeline | `timeline.py` (1.005 linhas) |
| Execução | `input_system.py` 1040-1470 (`ExecutionEngine`); `core.py` 1189-1275 (`build_timeline`) |
| Gravador | `input_system.py` 1470-1920; `core.py` 646 (`key_to_name`) |
| Visão e condições | `vision.py` (133 linhas), `conditions.py` (95 linhas) |

**Testes que já existem, por área** (a regressão da etapa 6 cobre todas): janela e inicialização (`gui/test_main_window_smoke.py`), editor de comandos (`gui/test_command_dialog.py`), edição e salvamento (`persistence/`, `unit/test_map_operations.py`), reprodução (`engine/`, `scenarios/` com os 3 mapas reais), atalhos (`engine/test_hotkeys.py`), gravação (`engine/test_recorder.py`), timeline (`unit/test_timeline_build.py` e a abertura com os 3 mapas reais). **Sem teste de comportamento hoje:** tutorial, sidebar (corte e sobreposição), overlays (teclado e mouse virtuais), visão (`vision.py`). A 25.7 mexe no tutorial e na sidebar e cria os testes deles; nos overlays e na visão, só mexe se for necessário, e então cria o teste junto.

**Testes de referência.** No ambiente de desenvolvimento (sem o PySide6 de verdade), a suíte da 25.6 tem 1.514 testes: no modo lógica, **1.267 passam, 5 são `xfail` esperados e 242 são pulados** (exigem o Qt de verdade), com 0 falhas (conferido de novo nesta edição); com o dublê de widgets, 1.478 passam e 31 são pulados. O verificador de defeitos plantados detectou **292 de 292** na rodada completa da 25.6 (não repetida nesta edição, que só mexeu em documentos). **A rodada com o Qt de verdade, no Windows, é a sua e ainda não chegou.**

## 4. Versão 25.7: o visual completo

### 4.1 Como entendi o seu pedido

Três tipos de entrega, e cada item do roadmap cai em um deles:

- **Real (R).** O que já existe e está errado ou incompleto é corrigido de verdade: o **tutorial** (2.1) e a **sidebar** (2.2). Eles são a própria interface; deixá-los para depois não faria sentido.
- **Prévia (P).** Tudo o que o roadmap ainda vai trazer ganha, na 25.7, a **tela e os controles definitivos**, com os textos reais e o selo "Prévia · chega na 25.x". A prévia pode ser aberta, percorrida e clicada para avaliar layout, textos e larguras, mas **não grava nada, não executa nada, não altera mapas nem configurações e não envia entrada ao teclado ou ao mouse**.
- **Existente intacto (E).** O que funciona hoje continua igual. A prévia nunca substitui um controle que já funciona: por exemplo, os campos reais da espera por imagem continuam onde estão e a prévia entra num bloco separado, ao lado.

**O que você pode vetar:** (a) prévia clicável ou só desenhada (recomendo clicável, sem efeito); (b) o cartão informativo da IA (recomendo só um cartão, sem campo de chave); (c) o painel único "Configurações da automação" da linha 4 da tabela: é proposta minha, não do seu plano.

### 4.2 O que a 25.7 entrega, tela a tela

| # | Tela ou controle | Hoje | Na 25.7 | Tipo | Funciona de verdade em |
|---|---|---|---|---|---|
| 1 | **Tutorial** | Qualquer clique ou tecla avança; o exemplo é executado sozinho no fim; sem animação; textos de até 828 caracteres | Reescrito conforme 2.1 (detalhes abaixo da tabela) | R | 25.7 |
| 2 | **Sidebar**: principal, da timeline e Configurações | Linhas montadas à mão não quebram; mínimos de 160 px; a da timeline tem 340 px fixos | Reorganização automática: controles vão para a linha de baixo, o rótulo fica junto do campo, sem corte nem sobreposição; a largura que você definiu é preservada | R | 25.7 |
| 3 | **Seleção de mapas** | Lista de nomes | Cada mapa mostra a tecla, o estado e um aviso de conflito. Seletor com os 3 estados (Ativo nesta sessão · Sempre ativo ao iniciar · Desativado), distinguindo o temporário do permanente | P | 25.8 |
| 4 | **Configurações da automação** | 6 caixas de diálogo em sequência | **Proposta:** painel lateral único com tecla de início (com aviso de conflito), ativação, repetição, intervalo, velocidade, próxima automação e conflito. Os valores que existem hoje funcionam de verdade (é só uma casa nova, com os mesmos testes); a ativação e o aviso de conflito são prévia | R + P | 25.7 (o que existe) e 25.8 (o novo) |
| 5 | **Timeline, modo Avançada** | Só muda o rótulo da linha | Barra própria do modo avançado ("Teclas → Texto…", "Mesclar…"), alvo de soltar com a indicação "será combinado com…" e painel de prévia da conversão (tecla por tecla, texto resultante, tempo gravado × tempo do texto, avisos). Mostrado com **dados de exemplo**, não com o seu mapa | P | 25.9 |
| 6 | **Comando "Esperar", condição de imagem** | Campos reais: arquivo, precisão, verificar a cada, região, procurar dentro da região, tempo limite | Os campos reais ficam intactos. Abaixo, um bloco "Em breve": capturar imagem e região, tempo máximo e intervalo (valores sugeridos de 60 s e 1 s), "se não aparecer…" (parar · reiniciar com limite), tentativas e "Testar agora" | P | 25.10 |
| 7 | **Monitor e timeline durante a execução** | Estado, automação, último evento, progresso | Faixas de estado da espera ("procurando", "imagem encontrada", "tempo esgotado", "interrompida", "nova tentativa n de m") e do grupo ("Grupo B — etapa 2 de 3"), com exemplo | P | 25.10 e 25.11 |
| 8 | **Grupos** | Nome e cor; os automáticos do gravador ("A", "B", "C"…) | Cabeçalho de grupo com repetição (×N), condição de continuação e limite; "Executar só este grupo" e "Executar trecho"; exemplo das três guias | P | 25.11 |
| 9 | **Exportar e importar** | JSON | Opção "Texto legível (TOML)" desabilitada, com selo | P | 25.12 |
| 10 | **IA** | — | Cartão informativo "Planejado para uma versão futura", sem campo de chave e sem botão que chame algo (opcional) | P | futura |

**O tutorial novo (linha 1)**, item por item do seu plano:

- Cada passo **destaca um controle** e só avança quando você faz a ação indicada, ou aperta o botão de navegação previsto para aquele passo ("Entendi", nos passos só informativos). Clique fora do alvo e teclas **não avançam**. Maximizar, restaurar, minimizar e redimensionar apenas reposicionam o destaque.
- A camada do tutorial passa a **deixar o clique chegar ao controle destacado** (hoje ela cobre a janela inteira e engole todo clique), e observa a ação real do controle antes de liberar o passo seguinte.
- O anel e o balão **acompanham a janela** e são recalculados a cada mudança de tamanho, posição ou estado; pulsação discreta no alvo atual e transições suaves entre os destaques; o balão **nunca cobre** o alvo, a área de edição nem o próximo controle.
- "Pular tutorial" vira um **botão próprio, afastado do "Próximo", com confirmação** ("Pular todo o tutorial?"), e não um link de 9 pt.
- **Passos curtos** (o texto de 828 caracteres vira vários passos) e conteúdo atualizado: cobre o que existe e mostra o planejado com o selo "Em breve", lendo o registro de recursos (4.3).
- O tutorial **nunca exige uma ação que crie, altere ou apague dado real** seu; nos passos "experimente", a ação é segura e reversível.
- No fim, **nada é executado sozinho**: o exemplo fica disponível num botão "Executar o exemplo" e a decisão é sua.
- Ao terminar, pular ou fechar a janela, **nada do tutorial permanece ativo** (camada, animação, temporizador).

### 4.3 Como a prévia não engana

1. **Registro de recursos** (`recursos.py`, lógica pura, sem Qt): cada recurso tem identificador, nome, estado (`ativo`, `previa`, `planejado`) e a versão em que passa a funcionar. A interface lê dele o selo e a dica; o tutorial lê dele o que pode chamar de disponível; os testes leem dele quais controles são prévia. **Ligar uma função é mudar o estado dela no registro**, e isso é um passo do aceite da versão que a liga.
2. **Três testes mecânicos novos:** PRE-01, interagir com qualquer controle de prévia não muda `mapa.to_dict()`, nem as configurações gravadas, nem envia entrada ao backend; PRE-02, todo controle de prévia mostra o selo; PRE-03, nenhum passo do tutorial chama de disponível um recurso que não esteja `ativo`.
3. **Componentes próprios.** Os painéis novos nascem em arquivos novos, e não dentro do `command_editor.py` (2.998 linhas) nem do `main_window.py` (2.288). Quando a função for ligada, ela entra num componente que já tem o seu lugar e os seus testes.

### 4.4 O que a 25.7 não faz

- Não altera o formato dos mapas: **nenhum campo novo é gravado** em mapa algum.
- Não muda padrões de execução: os 60 s e 1 s da espera por imagem só valem para condições novas, quando a função for ligada.
- Não liga a ativação por mapa: as teclas continuam registradas como hoje.
- Não converte teclas em texto, não executa grupos, não reinicia a automação, não chama IA.
- Não mexe no motor, no gravador nem nos backends.

Mudam de comportamento: o tutorial, a sidebar e, se você aprovar, a "casa" das configurações da automação.

### 4.5 Aceite da 25.7

1. Os critérios de aceite do plano para 2.1 e 2.2.
2. TUT-01 a TUT-06, UI-01 a UI-03 e PRE-01 a PRE-03 (seção 12).
3. REG-01: a suíte completa verde na sua máquina, e os 3 mapas reais abrindo, rodando e salvando idênticos.
4. O roteiro visual no Windows (12.3), feito por você, com as capturas do modo `visual`.
5. A 25.6 estável intacta; a 25.7 entregue como candidata.

### 4.6 Como vou enxergar o visual

- **Modo `visual` do `Rodar_Testes.bat` (novo, proposta).** Abre a janela com a plataforma `offscreen`, percorre as telas (seleção, editor, sidebar em quatro larguras, timeline simples e avançada, configurações, monitor, o tutorial passo a passo) e grava imagens em `logs\visual\` mais um `index.html`. Você me envia a pasta, ou as imagens que quiser, e eu **confiro as telas de verdade**; hoje eu só leio código. Limites: a plataforma `offscreen` pode usar fonte e escala um pouco diferentes da janela real e **não reproduz maximizar e minimizar do sistema**; as capturas servem para ver layout, corte e sobreposição, e esses casos seguem no roteiro manual.
- **Desenhos antes do código.** Antes de programar o Qt das linhas 3 a 8 da tabela 4.2, posso desenhar cada tela em imagem (HTML) para você aprovar o layout. Recomendo, porque são telas novas e o visual é a prioridade.

## 5. As versões seguintes, uma função por vez

Ordem recomendada (você pode reordenar; cada versão só começa com a anterior aprovada):

| Versão | O que passa a funcionar | Testes que ficam verdes | Antes dela | Mexe no formato? |
|---|---|---|---|---|
| **25.7** | **Visual completo**; tutorial e sidebar corrigidos | TUT-01 a 06, UI-01 a 03, PRE-01 a 03, REG-01 | — | Não |
| **25.8** | **Ativação de mapas** (2.3) | MAP-01 a 04, HK-01 | 25.7 aprovada | Não: a preferência fica nas configurações |
| **25.9** | **Timeline avançada**: teclas → texto, prévia, desfazer (2.4) | TL-01 a 04 | 25.8 | Não: usa o comando Texto que já existe |
| — | **Marco:** 2.1 a 2.4 aprovados e estável preservada, **o bloqueio do formato é levantado** | | | |
| **25.10** | **Espera por imagem, fase A** (3.1 e 7.A): capturar imagem e região, casamento de verdade, padrões novos, indicadores, parar (padrão) ou reiniciar com limite | VIS-01 a 06 (o 03, só com o reinício do mapa inteiro) | Sua verificação opcional (OpenCV e escala); D19 e D20 | Não: campos novos dentro de `parameters`, que já é livre |
| **25.11** | **Grupos, repetição e condição** (3.2): escopo, repetição, condição entre grupos, "grupo e etapa" em execução | GRP-01 a 03 | D31 e D32 | Sim: campos opcionais do grupo, um por vez (seção 6) |
| **25.12** | **Formato v2** (Ponto 3): texto legível (TOML), exportar e importar, achados 2.03 a 2.05 | Testes do Ponto 3 | Marco; D11 a D15 | Sim: é o objeto da versão |
| **25.13** | **Motor por posição e resultado de espera** (Ponto 5) | Regressão do motor, mais os novos | 25.12 | Não |
| **25.14** | **Desfechos, tentativas e voltar atrás** (7.B e 7.C) | VIS-03 completo | 25.13 | Sim |
| **25.15** | **Imagens que surgem sem aviso e diagnóstico** (7.D) | — | 25.14 | Não |
| futura | **Assistência por IA** (seção 10) | — | Tudo acima | — |

**Por que o formato v2 vem depois da espera por imagem e dos grupos.** O seu item 7 põe a espera visual e os grupos antes de "retomar a alteração do formato"; e desenhar o v2 depois das funções que ele precisa carregar evita desenhá-lo no escuro, com campos reservados que depois mudam. Se você preferir o formato logo depois do marco (como estava no roadmap da 25.6), a 25.12 sobe para antes da 25.10, e a 25.10 e a 25.11 passam a gravar nos campos do v2; custa desenhar antes os campos de grupo e de espera. **Recomendo a ordem da tabela.**

**Arquitetura (Ponto 4)** não tem versão própria por enquanto: os componentes novos já nascem em arquivos separados, e a divisão dos arquivos grandes (`main_window.py`, `command_editor.py`) fica para quando uma função a exigir ou quando você decidir.

## 6. O que conta como "alterar o formato dos mapas"

Para não haver dúvida sobre o bloqueio:

- **Bloqueado até o marco (2.1 a 2.4 aprovados):** trocar a forma de gravar os mapas (TOML v2, novo exportar e importar), mexer em `format_version`, e mudar, renomear ou remover campos que existem.
- **Permitido depois do marco, um por vez:** acrescentar **campos opcionais com padrão seguro** (por exemplo, os do grupo executável). Cada campo exige: teste do leitor tolerante, teste de ida e volta, os 3 mapas reais abrindo idênticos e uma nota no "contrato de campos".
- **Nas versões 25.7 a 25.9, nenhum campo novo é gravado em mapa.** A preferência de ativação (25.8) vai para o banco de configurações, por nome de mapa.
- **Risco de descer de versão:** o leitor atual lê só os campos que conhece e descarta os outros (`AutomationMap.from_dict`, `core.py:1135-1148`). Uma versão antiga que abra e salve um mapa gravado por uma versão nova **perde os campos novos**. Por isso cada entrega que introduzir campos traz o aviso "não abra este mapa numa versão anterior".

## 7. O que cada ponto técnico traz

**Ponto 3, formato v2 (25.12).** O mapa passa a poder ser escrito em texto (TOML, um comando por linha), exportado, editado à mão (ou com ajuda do Claude), comparado e importado de volta. "Flins combo" tem hoje cerca de 1,15 MB e a meta é no máximo 100 KB. O leitor deixa de adivinhar: erro de digitação vira aviso com linha e dica, e nenhum registro some em silêncio. Também resolve os achados 2.03 (mapa apagado que ressuscita), 2.04 (`load_map` com ponto no nome), 2.05 (atalho sem tecla) e as 3 lacunas de validação, todos já com teste `xfail` esperando. Decisões D11 a D15: as recomendações do planejamento continuam valendo (TOML; banco mantido com exportar e importar; milissegundos adaptativos; grupos regenerados na leitura; tempo absoluto como hoje). **Novidade desta edição:** o v2 já nasce carregando os campos de espera e de grupo que a 25.10 e a 25.11 tiverem gravado.

**Ponto 4, arquitetura.** Tirar o `import *`, separar o modelo do Qt (o que permite rodar toda a lógica sem PySide6), dividir o `input_system.py` (backends, monitor, motor, gravador), quebrar `MainWindow` e o editor de comandos (2.998 linhas num arquivo só) e ter um lugar só para a configuração de execução.

**Ponto 5, motor e barreiras (25.13).** Uma semântica única para toda espera (processo, tempo, imagem), cancelamento cooperativo em todos os backends, `stop()` sem bloquear, e as hipóteses abertas do Ponto 2: `VkKeyScanW` sem `restype`, `mouse_up` repetido na parada, teste da espera de processo no Windows (`WindowsProcessReadiness`).

**Ponto 6, persistência restante e visão (a visão entra na 25.10).** Transações, quarentena de registro inválido, migração versionada, excluir mapa. Na visão: captura de tela segura entre threads, DPI, região e referência, desempenho e testes (hoje `vision.py` tem 24% de cobertura e nenhum teste de comportamento).

## 8. Ponto 7: esperar por imagem e reagir ao que aparece

### 8.1 O que você pediu

Em resumo, nas suas palavras de 18/10/2026: usar **imagens como fator de espera até a automação continuar**, para ter automações mais precisas e **respostas diferentes para situações diferentes**. Os três casos que você deu, com o exemplo "abrir o navegador, pesquisar no YouTube e abrir um vídeo":

1. **Computador lento.** Processos em segundo plano atrasam o navegador e a automação digita a pesquisa antes de a tela mudar, e a automação inteira se perde logo no começo. Solução pedida: usar a imagem da tela já carregada, **ou de uma zona específica** (a barra de busca), como espera, sem depender da tela exatamente igual.
2. **Janela que atrapalha.** O YouTube carrega, mas uma atualização abre um pop-up que impede de continuar. Solução pedida: uma **imagem condicional que se espera ver**; se **não aparecer em algum lugar da tela**, executar um comando (apertar F5 para recarregar, ou **uma sequência de comandos**), o que **permite repetir a tentativa e limitar o número de tentativas**.
3. **Para onde voltar.** Depois da tentativa, **repetir a partir do último comando (a quantidade de comandos configurável) ou do início**, conforme o usuário.

### 8.2 Como o item 3.1 do plano 25.7 encaixa aqui

O plano descreve o "comando de espera por imagem" como novo. **Ele já existe em parte** (o tipo "⏳ Esperar" com condição de imagem); o plano o **evolui**, e quase tudo o que ele pede é um recorte do Ponto 7:

| Plano 25.7, item 3.1 | Neste roadmap |
|---|---|
| Imagem de referência escolhida pelo usuário | 7.A; hoje há só o arquivo (sem captura) |
| Tempo máximo (exemplo de 60 s) e intervalo (padrão de 1 s) | 7.A; os padrões atuais são 0 (sem limite) e 0,5 s. **Só valem para condições novas**: as já gravadas guardam os seus valores e um mapa antigo abre idêntico |
| Comportamento ao esgotar; padrão: parar | **Já existe como único desfecho** (F2); 7.B acrescenta os outros |
| Reiniciar automaticamente, com limite de tentativas | É "tentar de novo: voltar ao início" (7.C) na forma mais simples: **reiniciar o mapa inteiro**, sem "voltar K comandos". Proponho entregar esta forma já na 25.10 (laço externo do motor) e deixar o "voltar K" para a 25.14 |
| Indicadores: procurando, encontrada, tempo esgotado, interrompida, nova tentativa | Novo, em 7.A: exige um canal novo do motor para a interface (hoje só o log registra o sucesso) |
| Módulo isolado de captura e comparação | 7.A: `vision.py` sem Qt no topo, captura como interface (`FonteDeTela`) e casamento como função pura |
| Temporários com ciclo de vida definido | **Hoje não há arquivo temporário nenhum.** Passam a existir se decidirmos guardar a imagem junto do mapa e a captura da falha em `logs\` (D23); o ciclo (criar ao adicionar ou ao falhar; remover ao excluir o comando ou o mapa, ao cancelar e na limpeza do início) vira teste |
| Compatibilidade validada tecnicamente | 7.A e a "verificação opcional" no fim desta seção (F5, F7, F9) |
| Encontrar libera o próximo comando uma única vez; parar interrompe a busca | VIS-01 e VIS-04; pela leitura do código já se comportam assim |

### 8.3 O que o programa já faz hoje (lido do código na 25.6; nada disso foi executado no Windows)

| # | Achado | Confiança |
|---|---|---|
| F1 | **Já existe** "Esperar por imagem" (`WaitConditionType.IMAGE`): arquivo da imagem, precisão (padrão 95%), "verificar a cada" (0,5 s), região (X, Y, largura, altura), "procurar a imagem dentro da região" e tempo limite (0 = esperar para sempre). Roda **uma vez**, antes do primeiro evento do comando, e a espera desloca o relógio da linha do tempo (os comandos seguintes mantêm as lacunas planejadas). | Confirmada (leitura de `conditions.py`, `core.py`, `input_system.py`, `command_editor.py`) |
| F2 | Só há **um desfecho**. Achou: segue. Não achou no tempo limite: `ProcessReadinessError`, estado ERRO, e a automação inteira para. Não existe "tentar de novo", "executar outra coisa", "pular" nem imagem opcional. É exatamente o que acontece no seu caso 2. | Confirmada |
| F3 | No editor, "Atraso após" aparece também para a imagem, mas o motor o **ignora** nesse tipo (só o tipo "processo" e o "tempo" o usam). | Confirmada |
| F4 | A "similaridade" é `1 − média(|diferença|) / 255` sobre uma amostra dos pixels (`compare_images`), com mínimo de 95%. Pela própria fórmula, uma diferença que ocupe até 5% da área comparada (no contraste máximo, preto sobre branco) **não derruba** o 0,95: um pop-up pequeno sobre uma região grande pode passar despercebido, e a "tela carregada" pode ser reconhecida antes da hora. O efeito em telas reais não foi medido. | Confirmada (a fórmula); efeito real, hipótese |
| F5 | O modo "procurar dentro da região" usa `cv2.matchTemplate` e **só funciona com OpenCV**. O OpenCV e o NumPy **não estão** no `requirements.txt` nem no instalador, e a verificação de dependências do `Iniciar.bat` só confere PySide6 e pynput. Sem o OpenCV a função cai para a comparação de tamanho igual, que devolve 0,0 quando a região é maior que a imagem: o "procurar" **nunca encontra** e o programa não avisa. Se o OpenCV existe no seu Python 3.14 é uma **pergunta aberta** (veja a verificação opcional). | Confirmada (o código); a instalação no seu computador, desconhecida |
| F6 | `vision.py` importa o PySide6 no topo (sem Qt não há como testar a lógica de visão) e captura a tela **pela thread do motor** (`QGuiApplication.primaryScreen().grabWindow`). Só a tela primária é usada. Se a chamada fora da thread da interface é segura não foi verificado. | Confirmada (o código); a segurança da chamada, hipótese |
| F7 | Com a escala do Windows diferente de 100% (125%, 150%), a captura pode vir em pixels físicos enquanto a região e a imagem de referência estão em outras unidades; como a comparação exige tamanho igual, o resultado seria 0,0. | **Hipótese** (precisa do Windows com escala) |
| F8 | O editor **não captura** a imagem nem a região: você precisa ter o arquivo pronto e digitar X, Y, largura e altura. O único seletor de tela é o de posição do mouse. | Confirmada |
| F9 | O custo de cada verificação é Python puro, sobre uma amostra de até cerca de 1 milhão de pixels: a subamostragem de `compare_images` (`vision.py:55`) só começa quando a região passa de 1 milhão de pixels. Um laço equivalente, medido aqui (Python 3.13, este ambiente, remedido nesta edição), leva cerca de 6 ms para 200×100 e **120 a 270 ms** para regiões de 800×600 a 2560×1440 (o pior caso é a faixa de 250 mil a 1 milhão de pixels, como 1280×720), sem contar a captura nem as conversões do Qt. Como a espera de "verificar a cada" (0,5 s) vem depois de cada verificação, são de 20% a 35% de um núcleo, justamente no computador lento que o caso 1 quer ajudar. | Medida aqui; na sua máquina, a conferir |

**Leitura:** a base existe, mas ela cobre só o começo do caso 1 e, mesmo assim, com três armadilhas silenciosas (F4, F5, F7). Os casos 2 e 3 não existem.

### 8.4 O que falta, caso a caso

| Caso | O que já ajuda | O que falta |
|---|---|---|
| 1. Computador lento | F1: esperar por imagem, com região | Capturar imagem e região na tela (F8); casar a imagem de verdade, sem as armadilhas F4, F5, F7; custo baixo (F9); opcionalmente **esperar a região parar de mudar** (não exige imagem de referência, e é a forma mais simples de "esperar carregar") |
| 2. Janela que atrapalha | Nada: o único desfecho é parar (F2) | **Desfechos**: o que fazer se achar e o que fazer se não achar; **sequência de recuperação** (F5, ou vários comandos); **limite de tentativas**; o que fazer quando as tentativas acabam |
| 3. Para onde voltar | Nada: a linha do tempo só anda para frente | **Voltar** N comandos ou ao início, soltando antes tudo o que estiver pressionado; contar as tentativas; mostrar tudo isso na interface e no log |

### 8.5 Proposta: uma espera com vários desfechos

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

- **Bloco de recuperação**: uma sequência de comandos com nome ("Recarregar a página" = F5; "Fechar o aviso" = Esc, Enter…), guardada no mapa **fora da linha do tempo principal** e executada só quando um desfecho a chamar. Na seção 9, o mesmo conceito de **bloco** serve aos grupos executáveis do item 3.2: um só mecanismo para os dois.
- Os três casos ficam assim: o caso 1 é uma espera por imagem (ou por "região parada") com "parar com erro" como padrão; o caso 2 é a mesma espera com o desfecho "executar o bloco F5 e tentar de novo, até 3 vezes"; o caso 3 é o "tentar de novo: voltar K comandos / ao início".
- Imagem que **pode aparecer sem aviso** (o pop-up): a primeira versão a trata como **uma verificação nos pontos de espera** ("se esta imagem estiver na tela agora, execute o bloco X antes de seguir"), e não como uma thread que vigia a tela o tempo todo. A verificação nos pontos de espera é previsível e testável com o relógio virtual; um vigia em segundo plano concorreria com o envio de teclado e mouse e é tema da fase 7.D.

### 8.6 Fases (cada uma vira uma versão e fecha com o critério dela)

**7.A, esperar a tela ficar pronta (caso 1), versão 25.10.**
Capturar imagem e região na própria tela (seletor de região com o mouse, imagem gravada junto do mapa). Casamento de imagem de verdade, que não deixa passar um elemento pequeno (F4) e que avisa se faltar a dependência (F5). Região parada ("esperar a tela parar de mudar") como alternativa. Resolver a escala do Windows (F7) e a captura fora da thread da interface (F6). Custo baixo por verificação (F9). Indicadores de estado da espera e o reinício do mapa inteiro com limite de tentativas (8.2).
*Critério:* num cenário simulado de "máquina lenta", a imagem aparece em 7 s virtuais e a automação segue **no instante em que ela aparece**; um elemento de 4% da região é distinguido; o teste real no Windows (Tk com padrão conhecido, em 100%, 125% e 150%) captura a região certa.

**7.B, desfechos e tentativas (caso 2), versão 25.14.**
O painel "Se não aparecer…", os blocos de recuperação, o limite de tentativas e o que fazer quando acabam; tudo aparece no log ("tentativa 2 de 3: executando Recarregar a página").
*Critério:* cenário simulado "pop-up": a imagem só aparece depois de 2 recargas, e a automação segue na 3ª tentativa; com a imagem nunca aparecendo, a automação para com erro **depois de exatamente N tentativas**, com o teclado solto.

**7.C, voltar atrás (caso 3), versão 25.14.**
Voltar K comandos ou ao início, com K configurável. O motor passa a andar por posição na linha do tempo (hoje é um `for` que só avança), solta tudo o que está pressionado antes de voltar e reposiciona o relógio. As sobreposições do mapa gravado (um comando que começa antes de o anterior terminar) precisam de regra explícita: ao voltar K comandos, o ponto de retorno é o **início do comando** K posições antes, e o que estava em andamento é encerrado.
*Critério:* nenhuma tecla ou botão preso em nenhuma saída (fim, parada, erro, esgotar tentativas), provado com os 3 mapas reais e com mapas sintéticos com sobreposição.

**7.D, imagens que surgem sem aviso e diagnóstico, versão 25.15.**
Verificação "se esta imagem estiver na tela, execute o bloco X" numa faixa de comandos; botão "Testar agora" no editor; quando uma espera falha, gravar a captura de tela final e a melhor correspondência em `logs\` para entender o porquê.
*Critério:* cenário simulado "pop-up no meio da faixa" tratado sem parar a automação.

### 8.7 Como será testado (sem tela de verdade, com o que a 25.5 e a 25.6 já deixaram)

- Uma **fonte de tela** como interface (a real usa o Qt; a de teste, `FakeScreen`, entrega quadros previstos por instante do **relógio virtual**: "a imagem aparece em t = 7 s"). Isso permite testar o motor inteiro sem monitor, em milissegundos, como já se faz com as esperas por tempo.
- O casamento de imagem é uma função pura (matriz de pixels → pontuação), testada com imagens sintéticas: elemento pequeno, ruído, deslocamento, escala, imagem maior que a região, região vazia.
- Cenários de ponta a ponta com resultado de referência (golden), como os de hoje: "máquina lenta", "pop-up", "F5 em laço", "tentativas esgotadas", "parada no meio de uma tentativa solta tudo", "voltar K comandos nos 3 mapas reais".
- O verificador de defeitos plantados ganha defeitos novos para cada regra (contagem de tentativas, soltar antes de voltar, K comandos para trás etc.).
- No Windows de verdade, em modo opt-in como o `windows` atual: uma janela de teste com padrão conhecido para conferir captura, coordenadas e escala. O seletor de região com o mouse não dá para automatizar: entra no roteiro manual.

### 8.8 Riscos e limites (conhecidos desde já)

- **Captura**: jogos em tela cheia exclusiva e conteúdo protegido podem sair pretos; a captura de vários monitores hoje não existe (só a tela primária); a própria janela do Automation Studio pode estar na frente da região. Nada disso foi medido: entra na verificação da fase 7.A.
- **Dependência**: o casamento de imagem rápido pede OpenCV (que traz o NumPy). Eu **não confirmei** que haja pacote para o Python 3.14 no Windows (tentei consultar o PyPI daqui, sem acesso à rede; só tenho uma página de terceiros). Se não houver, a alternativa é um casamento próprio mais limitado. Fica na decisão D19, depois da verificação opcional abaixo.
- **Sobreposição de comandos**: voltar "K comandos" num mapa gravado exige a regra descrita em 7.C. No "Flins combo", em **444 dos 932 pares consecutivos** o comando seguinte começa antes de o anterior terminar (conta feita aqui com a mesma definição de lacuna que o código usa para reencadear, `core.py:931-942`), e **568 pares** pertencem ao mesmo grupo de simultâneos. Sem a regra, "voltar" geraria teclas presas ou repetidas.
- **Laços sem fim**: toda repetição precisa de limite; o padrão deve ser **finito** e o "ilimitado" uma escolha explícita (e sempre interrompível pela parada de emergência).
- **Falso positivo × falso negativo**: uma precisão alta demais faz a automação desistir à toa; uma baixa demais faz continuar cedo. Por isso o "Testar agora" e o registro da melhor correspondência (7.D) valem tanto quanto o casamento.

### 8.9 O que o Ponto 7 exige dos outros pontos (ajustado à nova ordem)

| Ponto | O que precisa estar lá |
|---|---|
| **3, formato** | O v2 (25.12) nasce com os campos que a 25.10 e a 25.11 gravaram: condições **com desfechos**, **blocos nomeados** fora da linha do tempo e **referência a imagens** (caminho relativo à pasta do mapa; exportar e importar levam as imagens junto, em pasta ou pacote). Hoje o caminho da imagem é absoluto e se perde ao levar o mapa para outro computador. Campos desconhecidos de versões futuras devem gerar **aviso**, não erro. |
| **4, arquitetura** | `vision.py` sem PySide6 no topo: a captura vira uma interface (`FonteDeTela`) com a implementação do Qt isolada; o casamento de imagem em módulo puro. **Isso acontece dentro da 25.10**, como "implementação isolada". O painel de condições do editor sai para um componente próprio **antes** de ganhar desfechos e blocos; a prévia da 25.7 já o cria separado. |
| **5, motor e barreiras** | Toda espera devolve um **resultado** (satisfeita, estourou o tempo, interrompida) em vez de lançar `ProcessReadinessError`; uma política por espera decide o que fazer com cada resultado. O laço de execução anda por posição (para poder voltar), soltar tudo é uma operação única e testada, e a contagem de tentativas vive no motor. **Necessário para 7.B e 7.C (25.14)**; o reinício do mapa inteiro da 25.10 não depende dele. |
| **6, persistência e visão** | Captura segura entre threads, escala do Windows, região e desempenho resolvidos e **testados** (a base da 7.A, na 25.10); imagens de referência guardadas junto do mapa (cópia ao adicionar, na 25.10) e levadas por exportar e importar, com transação (25.12); `FonteDeTela` falsa pronta para os testes. |

### 8.10 Verificação opcional na sua máquina (cerca de 10 minutos, sem pressa)

Só para eu chegar à 25.10 com dados em vez de suposições (F5, F7, F9). **Não é necessária para a 25.7.**

1. Abra um terminal e rode `py -3.14 -c "import cv2, numpy; print(cv2.__version__)"`. Se aparecer um número, o OpenCV já existe; se der erro de módulo, não existe (e isso responde a parte de F5).
2. Anote a **escala do Windows** (Configurações → Sistema → Tela → Dimensionar: 100%, 125%, 150%…).
3. No programa, faça um mapa de 1 comando de espera: "Esperar por imagem", com uma imagem pequena que **esteja visível na tela** (um recorte seu, em PNG), com e sem "procurar a imagem dentro da região", deixando a região em 0, 0, 0, 0 e depois com a região do recorte. Diga em cada caso se **achou ou ficou esperando** (ponha tempo limite de 10 s para não ficar preso).
4. Me conte o resultado. Com ele eu sei se F5 e F7 acontecem de verdade no seu computador.

## 9. Grupos, repetições e condições (item 3.2, versão 25.11)

**Situação hoje** (detalhes em `md/CONFIRMACAO_APONTAMENTOS_25_7.md`): o grupo existente é visual (nome, cor, sugestão de atraso); a repetição existe só no mapa inteiro; as condições existem só por comando; não há como executar só um grupo ou trecho; o exemplo das três guias só se faz hoje com 4 mapas encadeados.

**Vocabulário (D31).** Nos mapas reais gravados, **todos** os grupos são os automáticos do gravador, com nome de letras ("A", "B", "C"…), e os dados não distinguem um grupo automático de um escolhido por você. Proponho: o que o plano chama de **Grupo** (conjunto nomeado de ações, com repetição, condição e limite) é marcado por um campo próprio (`executavel`, ou um tipo), e os automáticos do gravador passam a se chamar **"Simultâneos"** na interface (é o que eles são: comandos que se sobrepõem no tempo). A mudança de nome é só visual e já pode entrar na 25.7.

**Modelo proposto.**

- **Grupo executável** = o grupo que existe hoje, mais: repetição (N), **condição de continuação** (a mesma `WaitCondition` que já existe para os comandos), **política quando a condição falha** (parar, que é o padrão, continuar ou pular) e **papel** (principal ou de recuperação, que é o "bloco" da seção 8.5).
- **Limite de execução** (trecho): um parâmetro de **execução**, não do mapa: "executar só o grupo X", "executar do grupo X ao Y". Não é gravado.
- **Como executa.** A linha do tempo de eventos do mapa é montada por uma **função pura** (`build_timeline`, `core.py:1189`), e cada evento leva o `command_id`. É o ponto natural para o **escopo** e a **repetição**: expandir os eventos do grupo N vezes (cada repetição começa quando a anterior termina, mais o intervalo configurado) e filtrar o escopo, **sem mexer no laço do motor**. As condições entre grupos reutilizam as barreiras de espera que já existem. O que exige o motor novo (25.13) é a política "continuar ou pular" e o "voltar".
- **Indicação "grupo e etapa".** O motor já avisa cada evento com o `command_id`; a interface mapeia para o grupo e mostra "Grupo B — etapa 2 de 3".

**Exemplo obrigatório como teste de aceite (GRP-02 e GRP-03).** Mapa sintético com 4 grupos: A "Abrir guias" (Ctrl+T, repetição 3); B, C e D "Pesquisa 1, 2 e 3" (clique na barra de pesquisa, Texto com a informação, Ctrl+W). Resultado esperado no backend falso, com o relógio virtual: Ctrl+T três vezes; depois, em ordem, clique, texto 1 e Ctrl+W; clique, texto 2 e Ctrl+W; clique, texto 3 e Ctrl+W; nenhum evento repetido ou omitido; lacunas planejadas preservadas; parar no meio do grupo B não deixa tecla presa e o estado informa "interrompido no Grupo B, etapa 2". **O teste não prova o navegador** (qual guia fica ativa depois de fechar uma): isso é verificação manual.

**"A retomada ocorre no bloco correto" (D32).** O plano não diz o que é "retomada". Três leituras possíveis: (a) depois de uma **pausa** (F9 e F10): **o motor pausa e continua** (a pausa congela o relógio, e isso é testado), e **as teclas F9 e F10 agora o chamam** (achado 2.11, achado na 25.8 lendo `_on_hotkey_triggered`: nenhum ramo para elas e nenhuma chamada a `engine.pause()` ou `resume()`; corrigido no ramo `funcoes/pausar-continuar-teclas`, **aguardando a sua aprovação**: `md/ENTREGA_PAUSA_TECLAS.md`); (b) depois de um **bloco de recuperação**, voltar ao grupo que falhou; (c) depois de uma **parada**, "continuar de onde parou". Recomendo (a) (ligando as teclas) e (b) na 25.11 e a (c) só como opção explícita, depois.

## 10. Assistência por IA (versão futura, só documentada)

Nada da 25.7 chama IA, guarda chave ou apresenta a IA como disponível. Requisitos do plano, com o que cada um pede do programa:

| Requisito | Pré-requisito no programa | Hoje |
|---|---|---|
| Nunca editar o mapa original; trabalhar numa **cópia identificável** | Operação "criar cópia" com nome e marca ("cópia IA") | Duplicar existe para comandos, não para mapas |
| Apresentar plano e diferenças antes de efetivar | **Comparação (diff) pública de mapas** | Só existe nos testes (`differences`) |
| Só gerar ações suportadas; respostas inválidas não executam nada | A IA devolve uma **representação estruturada** que passa pelos **mesmos validadores** do editor (`Command.validate`, `AutomationMap.validate`, `validate_structure`) | Os validadores existem; falta cobrir grupos e condições novos |
| Chave de API segura, nunca em texto simples nos mapas, logs ou configurações | **Cofre fora do banco** (por exemplo, o Gerenciador de Credenciais do Windows) | `AppSettings` guarda tudo como JSON em texto no mesmo SQLite dos mapas: a chave **não pode** ir ali |
| Informar custo e consumo de créditos | Aviso por provedor antes de enviar | Não existe |
| Registrar erros e permitir voltar sem depender da IA | O original intacto + registro de cada tentativa | O desfazer existe por mapa |

O modelo de comandos já permite **validar** (`validate`), **duplicar** (`copy.deepcopy`, `duplicate_commands`) e **serializar** (`to_dict` e `from_dict`); falta **comparar** de forma pública. Esse diff e a validação estrutural dos novos campos entram no Ponto 4.

## 11. Processo obrigatório (8 etapas) e como a infraestrutura de testes o cumpre

| Etapa | O que exige | Como será feito |
|---|---|---|
| 1. Especificação | Problema, comportamento normal e extremo, alterações visuais, funções afetadas, critérios objetivos | Uma ficha curta por função, **antes** do código (`md/ESPEC_<função>.md`). Para a 25.7, a ficha é a seção 4 deste roadmap, mais uma ficha para o tutorial e outra para a sidebar |
| 2. Testes antes | Casos de teste a partir da especificação: positivos, negativos, limites, cancelamentos, falhas, persistência | Cada teste leva o **ID do plano** num marcador. Os de função ainda não implementada entram como `xfail` **estrito**: aparecem no resumo como "especificado, pendente" e, quando a função existir, o teste que passar sem querer reprova até o marcador ser removido |
| 3. Implementação isolada | Módulo ou componente próprio; testável sem abrir o programa inteiro | Lógica em módulos sem Qt (`recursos.py`, `ativacao.py`, `teclas_para_texto.py`, `blocos.py`; `vision` sem Qt no topo) e interface em arquivos próprios. Não altero várias funções não relacionadas ao mesmo tempo |
| 4. Testes isolados e regressão por erro | Para cada erro, um teste que o reproduza **antes** da correção | O teste é escrito, falha, o código é corrigido, o teste passa e fica em `tests/regression/`. Cada regra nova ganha defeitos plantados no verificador de mutações (hoje 292) |
| 5. Integração na versão de desenvolvimento | Cópia ou ramo de desenvolvimento; estável intacta; testes de integração | Árvore nova por versão; o `AS_25_6.zip` entregue **nunca é sobrescrito**; a candidata sai como `AS_25_7_candidata_N.zip` até ser aprovada |
| 6. Regressão | Bateria da versão atual e a das funções relacionadas, nas áreas listadas no plano | `Rodar_Testes.bat` completo, com as áreas da seção 3 (inicialização, tutorial, edição e salvamento, reprodução, atalhos, gravação, overlays, sidebar, timeline) |
| 7. Aprovação | Todos os obrigatórios passam; sem regressão conhecida sem decisão explícita; cada erro com o seu teste; resultados e limitações registrados. Se falhar, **fica isolada** | A entrega traz a tabela "o que rodou aqui" e "o que só você roda" (os testes que precisam do Qt de verdade só ficam verdes depois da sua rodada) |
| 8. Registro de entrega | Versão, arquivos, comportamento, testes, resultados, erros corrigidos, limitações | Modelo abaixo, em `md/ENTREGA_<versão>.md`, mais o `CHANGELOG` |

**Modelo do registro de entrega:**

```
Versão e função:
Arquivos alterados:
Comportamento implementado:
Testes executados (por ID):    [aqui]  [na sua máquina]
Resultados:
Erros corrigidos (com o teste de regressão de cada um):
Limitações conhecidas:
Versão estável anterior (preservada):
```

## 12. Plano de testes

Níveis: **L** lógica pura (roda aqui e no Windows, sem Qt) · **Q** interface com o Qt de verdade (roda na sua máquina em `Rodar_Testes.bat`, plataforma `offscreen`; aqui só com o dublê, que não cobre a janela principal) · **V** verificação visual (capturas do modo `visual` e roteiro manual) · **W** Windows real (`Rodar_Testes.bat windows` ou roteiro).

### 12.1 Os IDs do seu plano

| ID | Cenário | Resultado esperado | Como é testado | Nível | Ativo em |
|---|---|---|---|---|---|
| TUT-01 | Clicar fora do alvo | Etapa não avança | Clique e tecla qualquer na camada, fora do alvo: o passo atual não muda | Q (+V) | 25.7 |
| TUT-02 | Maximizar ou restaurar a janela | Etapa permanece; destaque recalculado | Redimensionar e maximizar por código: passo igual, camada do tamanho da janela, anel sobre o alvo; maximizar de verdade com o mouse e por teclado no roteiro | Q + V + W | 25.7 |
| TUT-03 | Interagir corretamente com o alvo | Avança após validar a ação | Validador do passo (função pura) e a ação real (clique no botão) avançando; ação errada não avança | L + Q | 25.7 |
| TUT-04 | Pular o tutorial ou fechar a janela | Nenhum balão ou destaque fica ativo | Depois de pular e de fechar: nenhuma camada, animação ou temporizador do tutorial vivo | Q | 25.7 |
| TUT-05 | Percorrer o tutorial completo | Instruções correspondem às funções presentes | Cada passo aponta para um recurso do registro e só diz "disponível" se estiver `ativo`; cada alvo existe e está visível; comprimento máximo; percurso manual | L + Q + V | 25.7 |
| UI-01 | Reduzir a largura | Controles reorganizados sem cortes | Larguras de 320 a 560 nas duas barras e nas Configurações: cada controle dentro da área visível, sem sobreposição, sem rolagem horizontal necessária; capturas | Q + V | 25.7 |
| UI-02 | Rótulos e campos longos | Controles associados e acessíveis | Textos longos em pt-BR e fonte maior: o rótulo fica acima ou ao lado do seu campo; capturas | Q + V | 25.7 |
| MAP-01 | Ativar mapa nesta sessão | Estado temporário não altera a preferência | Modelo `ativacao` com configurações em pasta temporária; depois, a interface | L + Q | 25.8 |
| MAP-02 | Ativação na inicialização | Estado recuperado na próxima abertura | Fechar e abrir de novo (novo gerenciador sobre a mesma pasta) | L + Q | 25.8 |
| MAP-03 | Desativar mapa e acionar o atalho | O mapa não executa | `_on_hotkey_triggered` com backend falso: nenhum evento | L + Q | 25.8 |
| TL-01 | Converter teclas imprimíveis em texto | Prévia correta; conversão reversível | Função pura de análise e operação do mapa; desfazer e refazer pelo `MapHistory` | L + Q | 25.9 |
| TL-02 | Mesclar sequência com tecla especial | Nenhuma conversão incorreta nem perda de dados | Teclas especiais, Ctrl/Alt/Win, CapsLock e tecla mantida encerram o trecho; mapa idêntico quando inválido | L | 25.9 |
| TL-03 | Mesclar, salvar, reabrir e desfazer | Conteúdo, ordem e reversibilidade preservados | `map_to_json` e `map_from_json`, mais desfazer e refazer; os 3 mapas reais | L + Q | 25.9 |
| VIS-01 | Imagem aparece no prazo | Próximo comando executa uma vez | `FakeScreen` com relógio virtual: a imagem aparece em t = 7 s | L | 25.10 |
| VIS-02 | Imagem não aparece no prazo | Automação para por padrão | Mesmo cenário, sem a imagem: estado de erro e teclado solto | L | 25.10 |
| VIS-03 | Reinício automático | Tentativas respeitam o limite | Exatamente N reinícios e nada além (25.10: reinício do mapa inteiro; 25.14: completo) | L | 25.10 / 25.14 |
| VIS-04 | Interromper durante a busca | Busca cancelada sem retomar a execução | Parada durante a espera: a busca termina e nenhum comando seguinte executa | L | 25.10 |
| GRP-01 | Executar grupo isolado | Só o trecho selecionado executa | `build_timeline` com escopo; backend falso | L | 25.11 |
| GRP-02 | Repetir abertura de guias três vezes | Três guias antes das pesquisas | O exemplo da seção 9 | L | 25.11 |
| GRP-03 | Executar as três pesquisas | Pesquisas e fechamentos na ordem | O mesmo mapa sintético, com a ordem exata dos eventos | L | 25.11 |
| REG-01 | Recursos existentes relacionados | Nenhuma regressão crítica | A suíte completa e os 3 mapas reais idênticos; as áreas do plano (seção 3) | L + Q | Toda versão |

Os testes de funções ainda não implementadas existem desde a 25.7 como `xfail` estrito com o ID (etapa 2 do processo), para que ninguém "esqueça" de ligá-los.

### 12.2 IDs novos que proponho

| ID | Cenário | Resultado esperado | Nível | Ativo em |
|---|---|---|---|---|
| TUT-06 | Terminar o tutorial | Nada é executado sozinho: o motor não roda e o backend não recebe entrada | Q | 25.7 |
| UI-03 | Largura salva do usuário | `sidebar_width`, `sidebar_last_manual_width` e `workspace_splitter_sizes` iguais antes e depois do reflow | L + Q | 25.7 |
| PRE-01 | Interagir com qualquer prévia | Mapa, configurações e backend inalterados | L + Q | 25.7 |
| PRE-02 | Controle de prévia | Todo controle de prévia mostra o selo | Q | 25.7 |
| PRE-03 | Texto do tutorial | Nenhum recurso não `ativo` é chamado de disponível | L | 25.7 |
| HK-01 | Conflito de tecla | A mensagem nomeia as duas automações (ou a ação de controle) e a tecla | L + Q | 25.8 |
| MAP-04 | Os 3 mapas reais "Sempre ativos" | Registram os mesmos atalhos de hoje | L | 25.8 |
| TL-04 | Pausa significativa, maiúsculas por Shift, repetição de tecla | Pausa maior que o limite divide ou avisa; maiúsculas só com Shift sobreposto; tecla mantida avisa | L | 25.9 |
| VIS-05 | Falha de captura | Registrada, sem ciclo silencioso | L | 25.10 |
| VIS-06 | Temporários | Removidos no fim, no cancelamento e na falha | L | 25.10 |

### 12.3 Roteiro visual manual no Windows (o que o teste automático não prova)

Você faz, e eu uso as capturas para conferir:

1. **Primeira abertura.** O tutorial aparece; clique fora do alvo e aperte uma tecla qualquer (não avança); maximize pelo botão, pelo duplo clique na barra de título e por Win+↑; restaure; minimize e restaure. O anel e o balão acompanham?
2. **Tutorial inteiro**, fazendo cada ação pedida; ao fim, nada é executado sozinho.
3. **Pular** o tutorial (com a confirmação); **fechar a janela** no meio e reabrir: nada preso.
4. **Sidebar** na largura mínima, em 320, em 400 e na máxima, em cada tipo de comando e nas Configurações; a barra da timeline; escalas do Windows de 100%, 125% e 150%.
5. **Prévias:** abrir cada uma, conferir o selo e conferir que nada muda (mapa e configurações).
6. Os **3 mapas reais** abrem e executam como antes.

## 13. Decisões

**Já tomadas, valendo (D11 a D15, formato v2):** TOML; banco mantido com exportar e importar; milissegundos adaptativos; grupos regenerados na leitura; tempo absoluto como hoje. **D16:** os 3 mapas reais são fixtures permanentes (`tests/data/legacy_maps.json.gz`) e fazem parte de toda regressão (REG-01).

**Do Ponto 7 (D17 a D23), com as recomendações em negrito:**

| # | Decisão | Recomendado |
|---|---|---|
| D17 | Onde moram as sequências de recuperação | **Blocos nomeados dentro do mapa, fora da linha do tempo** (alternativas: comandos marcados "só para recuperação" na própria lista; um mapa à parte). Casa com o item 3.2 (seção 9) |
| D18 | "Voltar K comandos": como contar | **K comandos na ordem de início, voltando ao começo do comando** (como você descreveu); um "ponto de retomada" marcado pelo usuário fica como evolução |
| D19 | Casamento de imagem e dependência | **OpenCV (`opencv-python-headless`) como dependência obrigatória, se houver pacote para o 3.14**, com aviso claro na verificação de dependências; senão, um casamento próprio mais limitado, assumido como tal |
| D20 | Como capturar a tela | **Manter o Qt, mas fora da thread do motor (a captura é pedida à thread da interface)**, depois de medir no Windows com escala 100%, 125% e 150% (alternativa: GDI via ctypes) |
| D21 | Quando as tentativas se esgotam | **Parar com erro** (o comportamento de hoje), configurável por espera para "continuar" ou "pular" |
| D22 | Pop-ups sem aviso | **Verificação nos pontos de espera na primeira versão** (fase 7.D), sem vigia em segundo plano |
| D23 | Onde ficam as imagens | **Junto do mapa, com caminho relativo e cópia ao adicionar** (a cópia na 25.10; exportar e importar levando as imagens, na 25.12) |

**Novas, desta edição.** Marquei **(!)** nas quatro que mudam o que eu construo a seguir; as outras eu apenas adotei:

| # | Decisão | Recomendado, e por quê |
|---|---|---|
| D24 (!) | O que é a "prévia" da 25.7 | **Tela definitiva, clicável e sem efeito, com selo, protegida por PRE-01 a PRE-03 e pelo registro de recursos.** Clicável, porque só assim se avaliam larguras e textos reais; sem efeito, para não haver função pela metade |
| D25 (!) | Painel único "Configurações da automação" já na 25.7 | **Sim.** Hoje são 6 diálogos em sequência e não há onde mostrar ativação nem conflito; o painel segue o padrão da sidebar. Se preferir, mantenho os diálogos até a 25.8 |
| D26 (!) | Modelo da ativação por mapa | **Duas coisas separadas:** a preferência permanente ("Sempre ativo" ou "Desativado"), gravada no banco de **configurações** por nome de mapa, e a ativação temporária, só em memória. Transições: de "Desativado" para "Ativo nesta sessão" não toca na preferência; de "Sempre ativo" para "Ativo nesta sessão" **muda a preferência** para "Desativado" (você está abrindo mão do "sempre"; a tela avisa "na próxima abertura ficará desativado"); "Sempre ativo" e "Desativado" gravam a preferência. **Mapas que já existem ficam "Sempre ativo"** (é o comportamento de hoje, nada deixa de funcionar); **mapa novo nasce "Ativo nesta sessão"**, ou "Desativado" se a tecla dele já estiver em uso por um mapa ativo |
| D27 | Conflito de tecla | Só mapas **ativos** entram na checagem. Ao ativar ou editar uma tecla, o conflito **impede a ativação** e a mensagem nomeia as duas automações (ou o atalho de controle) e a tecla. Mapa "Desativado" nunca conflita. Hoje quem chega depois perde em silêncio e a mensagem repete a tecla sem dizer de quem é |
| D28 | Teclas → texto: regras da primeira versão | **Subconjunto seguro:** letras, dígitos, Espaço e Ç, com Shift. Encerram o trecho: qualquer outra tecla nomeada (Backspace, Enter, setas…), Ctrl, Alt e Win, **CapsLock** (o estado inicial é desconhecido) e tecla mantida além do tempo de repetição. **Pausa significativa:** acima de 1 s por padrão, editável na prévia (divide em dois textos ou avisa). **Tempo:** o Texto assume o início da 1ª tecla e **os comandos seguintes não se movem**; a prévia mostra "gravado X s → texto Y s". **Intervalo entre caracteres:** o da configuração global (o comando Texto não tem intervalo próprio). **Desfazer:** uma transação. A prévia **avisa** que o gravador não captura pontuação |
| D29 | Gesto de mesclar | **Botão e menu "Teclas → Texto…" primeiro**, com prévia; arrastar e soltar depois, com alvo de soltar próprio (soltar sobre a barra de destino mescla; soltar entre linhas reordena) e a indicação "será combinado com…" antes de soltar. Hoje o arrasto vertical já significa reordenar (`timeline.py:502-506`) |
| D30 | O que conta como "alterar o formato" | A seção 6 |
| D31 | Vocabulário e modelo dos grupos | A seção 9: "Grupo" executável (campo próprio); os automáticos do gravador viram "Simultâneos" na interface; "bloco de recuperação" é um papel do mesmo grupo |
| D32 | O que é "retomada no bloco correto" | A seção 9: pausa (o motor pausa e **as teclas F9 e F10 agora o ligam**: achado 2.11, corrigido, aguardando a sua aprovação) e volta ao grupo que falhou na 25.11; "continuar de onde parou" só como opção explícita, depois |
| D33 | O gravador não captura pontuação nem acentos | **Fica como melhoria separada, fora da 25.7 a 25.9** (por exemplo, gravar o que foi digitado direto como comando Texto). A conversão só avisa. Peço sua decisão depois da 25.9, com a prévia na mão |
| D34 (!) | Ordem das versões | A tabela da seção 5 (formato v2 depois da espera por imagem e dos grupos) |

## 14. O que preciso de você

Nada disto é urgente: a 25.7 só começa quando você der o aval da seção 4.

1. **Seu aval ou veto** da interpretação da seção 4.1 e das decisões marcadas **(!)**: D24, D25, D26 e D34.
2. **A rodada de testes da 25.6** (`Rodar_Testes.bat`, enviando `logs\tests_last_run.txt` e, se existir, `logs\travamento_qt.txt` e `logs\AutomationStudio.log`). Como você roda a bateria quando várias versões se acumulam, **ela pode esperar a candidata 25.7 e valer para as duas**.
3. **Se quiser os desenhos antes do código** (4.6), diga e eu os preparo.
4. **A verificação opcional** da seção 8.10: só será necessária para a 25.10.

## 15. Itens menores (fora dos pontos)

- **Achado 2.11 (25.8): as teclas F9 e F10 (pausar e continuar) não faziam nada. CORRIGIDO** no ramo `funcoes/pausar-continuar-teclas` (`md/ESPEC_PAUSA_TECLAS.md`, `md/ENTREGA_PAUSA_TECLAS.md`), **aguardando a sua aprovação**. Aparecem em Configurações e eram registradas, mas a janela principal não tinha ramo para elas e nunca chamava `engine.pause()` nem `resume()`. O teste `xfail` do defeito virou o guarda permanente `tests/static/test_ligacao_controle.py`. Decisões tomadas por mim (vetáveis): a barra de status diz como continuar, e uma pausa durante a espera por um aplicativo vale a partir do ponto de controle seguinte (o motor já era assim).
- O título da janela **nunca mostrou a versão** (o `__init__` a coloca, mas `_update_status_label` a troca por "Automation Studio — ● PARADO" na construção). Se você quiser a versão no título, é uma mudança do programa a decidir à parte; hoje ela só aparece nos arquivos e no README.
- `main_window.py` tem uma função interna `size_toolbar` que nunca é chamada (e que, se fosse, se reagendaria sozinha com `QTimer.singleShot(0, ...)`) e um `toolbar_hint` que nunca é criado. Código morto; limpar no Ponto 4.
- Quando o programa é aberto como administrador, o diretório atual é `C:\Windows\System32` (visto no seu log). Não faz diferença: o programa só usa o diretório atual para escrever diagnósticos, e os caminhos dele partem da pasta do script.
- O botão "⚙ Configurações da automação" é uma variável local (`cfg`, `main_window.py:592`), sem atributo na janela. O tutorial novo (e qualquer teste) precisa de **nomes estáveis** nos controles que apontar: isso entra na 25.7 como parte do item 2.1.
