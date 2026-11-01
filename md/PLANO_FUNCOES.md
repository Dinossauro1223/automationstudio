# Plano da frente de funções: versões, achado 2.11, preparação para o Android e otimização

Escrito pela conta de integração em 31/10/2026, a pedido do dono. Vale para a frente de funções e para qualquer conta que trabalhe em comportamento (lógica, motor, formato, banco, atalhos, visão). A política de versões da seção 1 vale para **todas** as frentes.

## 1. Mesma versão ou próxima

Uma versão é **fechada pelo dono**, depois que ele roda a suíte no Windows e dá o OK (é quando `APP_VERSION` e `md/CHANGELOG_V25.md` mudam). Até lá a versão está **em aberto**. Hoje, a em aberto é a **25.8** (tema novo e ativação por mapa, já na `main`; `APP_VERSION` ainda diz 25.6).

- **Entra na mesma versão (a em aberto)**: correção de defeito do que já está nela; correção achada na conferência no Windows; testes, documentos e otimização que não mudam o comportamento.
- **Abre a próxima versão (25.9, 25.10...)**: função nova; qualquer mudança no formato do arquivo de mapa ou do banco (pede migração e nota de migração); mudança que o usuário perceba como diferente do que usava (a interface nova do `PLANO_VISUAL.md`, por exemplo).
- Em caso de dúvida: **próxima versão**. É mais fácil juntar duas versões depois do que separá-las.
- Toda entrega diz na última linha da mensagem do commit: `Versão: 25.8 (em aberto)` ou `Versão: 25.9 (nova)`.
- A integração prepara o texto do changelog a partir dessas linhas; quem fecha é o dono.

## 2. Achado 2.11 (F9 e F10): já está com outra frente

O dono informou em 31/10/2026 que outra frente já trabalha nele. **Não duplicar**: as demais frentes não tocam `_on_hotkey_triggered` (`main_window.py`). Para quem está com ele, o roteiro até a entrega, que cabe na **mesma versão (25.8)**, por ser correção de um defeito achado na conferência:

1. Ligar `control:pause` e `control:resume` ao motor (`engine.pause()` e `engine.resume()`, que já existem e são testados) em `_on_hotkey_triggered`, e fazer a barra de estado dizer "Pausado" e "Em execução". Só texto: nada de aparência nova (a frente visual cuida do desenho).
2. A pausa durante uma espera por aplicativo (`md/ENTREGA_25_8.md`, seção 7) é decisão do dono. Se a resposta não chegar antes da entrega, escolha o comportamento mais conservador (a pausa atua entre comandos; nada que já foi enviado é desfeito), **registre a escolha no commit** e deixe o dono vetar.
3. Tirar o `xfail` estrito de `tests/static/test_lacunas_de_ligacao.py`: ao corrigir, o teste passa e o executor reclama enquanto o marcador existir.
4. Teste de janela real (`tests/gui`, com o backend de mentira): F9 com um mapa rodando pausa; F10 continua; **a tecla de parada continua funcionando durante a pausa** (segurança); a pausa não deixa tecla ou botão preso (`pressed_balance` em `tests/testsupport/helpers.py`).
5. Atualizar `md/ENTREGA_25_8.md` (seção 7) e o item F9/F10 dos "Itens menores" do `md/ROADMAP.md`; publicar em `funcoes/<assunto>` e avisar a integração.

## 3. O que vem depois (nesta ordem)

| # | Tarefa | Versão | Observação |
|---|---|---|---|
| 1 | F2 do `DELEGACAO.md`: os 3 `xfail` de `tests/unit/test_validation_gaps.py` (botão de mouse desconhecido, "abrir aplicativo" sem alvo, `repeat_count` menor que -1) | próxima | Validar mais pode recusar um mapa que antes abria: os cenários dos 3 mapas reais precisam continuar verdes |
| 2 | Pontos 3 e 4 do roadmap (formato v2 e arquitetura) | próxima | Exigem a rodada do dono no Windows antes e uma janela combinada para `core.py` e `project.py` (as outras frentes só fazem mudança pequena nesses arquivos enquanto durar) |
| 3 | Itens menores do roadmap | mesma, se for correção | Um por commit |
| 4 | Otimizações da seção 5 | mesma (não muda comportamento) | Ciclo de `md/DESEMPENHO.md`, seção 7 |

## 4. Preparação para o Android, pelo lado das funções

O Android não vai rodar os widgets do PySide6. O que se reaproveita é o **contrato**: formato, regras e testes. O que fazer:

1. **Formato v2 como contrato (Ponto 3)**: escrever `md/FORMATO_V2.md` (especificação, versão do formato, regras de migração) e criar **vetores de conformidade**: os 3 mapas reais e os cenários de `tests/scenarios` viram arquivos de exemplo com a leitura esperada. Quem implementar o Android prova que lê e grava igual.
2. **Núcleo sem Qt.** Hoje `ativacao.py`, `project.py`, `conditions.py` e `input_system.py` não importam o PySide6 no topo; `core.py` e `vision.py` importam. Em `core.py` o Qt serve ao tema, às cores e à animação, misturados com o modelo (`Command`, `AutomationMap`), o formato, a validação e a linha do tempo. Separar o modelo, o formato, a validação e a linha do tempo (sem Qt) do tema (com Qt) é o passo que libera o núcleo: é o Ponto 4, e vale por si só (testes mais rápidos, menos acoplamento).
3. **Entrada por plataforma.** `InputBackend` (`input_system.py`) já é a interface; o Android a implementa com um serviço de acessibilidade. Manter a interface pequena e documentada.
4. **Gatilho abstrato.** Hoje o que dispara uma automação é uma "tecla". No Android será um toque, um botão flutuante ou outro gesto. Tratar o **gatilho** como conceito (tipo e valor) no formato v2 e em `ativacao.py`, em vez de uma tecla fixa: o desktop usa tecla, o Android o que for definido.
5. **Dependem do dono**: nativo (Kotlin e Compose) ou reaproveitando Python (Kivy, BeeWare). Nativo: a especificação e os vetores do item 1 são tudo o que se leva. Python: o núcleo sem Qt do item 2 vira dependência direta. A decisão também aparece em `md/PLANO_VISUAL.md`, seção 8.

## 5. Otimização (o que a frente de funções faz)

O plano completo, com números medidos, está em `md/DESEMPENHO.md`. Do lado das funções:

- **F-O1** `vision.compare_images` (211 ms em 1080p): atalho para imagens iguais, `math.ceil` no passo e, com a decisão D19, OpenCV (3,9 ms medidos).
- **F-O2** banco (~22 ms por gravação): `journal_mode=WAL` uma vez só; `synchronous=NORMAL` **somente depois** de existir o teste de queda no meio da gravação.
- **F-O3** núcleo e motor: já estão bons; **não mexer**.
- **F-O4** importação (~330 ms): medir com `-X importtime` e adiar o que só serve a diálogos raros.
- **F-O5** `PySide6-Essentials` no lugar de `PySide6` (673 MB em disco no ambiente de testes), verificando com a suíte e com o `.exe`.

Regra de ouro: medir antes e depois, uma mudança por commit, suíte completa e catálogo de funções verdes. Nunca remover verificação de segurança para ganhar tempo.

## 6. Quando não houver tarefa atribuída

Em ordem, uma coisa por rodada:

1. Pendências abertas: `xfail` estritos que sejam da sua frente (`pytest -rx`), e itens menores do roadmap.
2. Lacunas de teste na sua área. Cobertura medida no Linux em 30/10/2026: `input_system` 77% (o que falta é, em boa parte, o código do Windows de verdade, que só o dono cobre), `vision` 85% depois dos testes novos.
3. Otimizações (`md/DESEMPENHO.md`, seção 7).
4. O próximo ponto do roadmap, se estiver liberado.

No fim de cada rodada: suíte completa verde, uma linha no registro de `md/DELEGACAO.md` e o ramo publicado.
