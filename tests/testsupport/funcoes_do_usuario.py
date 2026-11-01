"""Catálogo das FUNÇÕES que o usuário do Automation Studio pode fazer, e de onde ele as aciona hoje.

Por que existe: a frente visual vai simplificar a interface (menos botões, mais interação) e, depois, levar o programa ao
Android com a mesma cara. Simplificar só é seguro se nenhuma função se perder pelo caminho. Este catálogo é a lista
do que o programa faz; `tests/gui/test_funcoes_acessiveis.py` abre a janela de verdade e confere que TODA função daqui
ainda tem pelo menos um jeito de ser acionada. Quem muda um controle de lugar (ou de nome) muda a linha da função no mesmo
commit: o teste só quer que a função continue tendo um endereço.

Cada função tem um ID que NÃO muda (nem quando o nome ou o botão mudam) e que será o mesmo no app Android.

Tipos de endereço (o segundo item de cada tupla é o que se procura):
    ("acao",   "texto")                  ação da barra ou de menu da janela principal, pelo texto visível
    ("botao",  "texto")                  botão da janela principal (ou de uma das telas dela), pelo texto visível
    ("painel", "nomeDoObjeto", "sempre")           widget com esse objectName na janela principal
    ("fonte",  "arquivo.py", "texto")    texto que só existe em menu de contexto ou diálogo (que não abre sozinho no
                                         teste): conferido no código-fonte do pacote
    ("teste",  "caminho::nome")          função que se aciona só por tecla: o endereço é o teste que a exercita

Para regenerar o documento depois de mudar o catálogo:
    python tests/testsupport/funcoes_do_usuario.py > md/FUNCOES_DO_USUARIO.md
"""
from collections import namedtuple

Funcao = namedtuple("Funcao", "id grupo nome atalho acessos")

FUNCOES = [
    # ---- Automações
    Funcao("F01", "Automações", "Criar uma automação nova", "", [("acao", "＋ Nova automação", "sempre"), ("botao", "＋ CRIAR NOVA AUTOMAÇÃO", "lista")]),
    Funcao("F02", "Automações", "Abrir ou importar um mapa externo (.json ou banco)", "", [("botao", "📂 ABRIR / IMPORTAR MAPA EXTERNO", "lista")]),
    Funcao("F03", "Automações", "Abrir a automação selecionada no editor", "", [("botao", "ABRIR AUTOMAÇÃO SELECIONADA", "lista")]),
    Funcao("F04", "Automações", "Salvar a automação", "", [("acao", "💾 Salvar", "sempre")]),
    Funcao("F05", "Automações", "Escolher outra automação (voltar à lista)", "", [("botao", "← Escolher outra automação", "editor")]),
    Funcao("F06", "Automações", "Ajustar a automação (nome, tecla, repetição, velocidade)", "", [("botao", "⚙ Configurações da automação", "editor")]),
    Funcao("F07", "Automações", "Desfazer a última alteração", "Ctrl+Z", [("acao", "↶ Desfazer", "sempre")]),
    Funcao("F08", "Automações", "Refazer a alteração desfeita", "Ctrl+Y", [("acao", "↷ Refazer", "sempre")]),
    Funcao("F09", "Automações", "Escolher como a automação é ativada (sempre ativa, só nesta sessão, desativada)", "", [("painel", "PainelAtivacao", "editor")]),
    # ---- Execução
    Funcao("F10", "Execução", "Executar a automação", "", [("acao", "▶ Executar", "sempre")]),
    Funcao("F11", "Execução", "Parar a execução", "", [("acao", "■ Parar", "sempre")]),
    Funcao("F12", "Execução", "Parar tudo (emergência)", "tecla de parada", [("acao", "🛑 Parar tudo", "sempre")]),
    Funcao("F13", "Execução", "Ver o monitor de execução", "", [("acao", "▣ Monitor de execução", "sempre")]),
    Funcao("F14", "Execução", "Voltar ao editor (da timeline ou do monitor)", "", [("botao", "← Voltar ao editor", "timeline")]),
    Funcao("F15", "Execução", "Parar tudo pela tecla, mesmo que um mapa use a mesma tecla", "tecla de parada",
           [("teste", "tests/gui/test_ativacao_janela.py::test_a_parada_de_emergencia_continua_com_a_tecla_mesmo_que_um_mapa_use_a_mesma")]),
    Funcao("F16", "Execução", "Executar uma automação pela tecla dela (só se estiver ativa)", "tecla do mapa",
           [("teste", "tests/gui/test_ativacao_janela.py::test_mapa_desativado_nao_executa_pela_tecla_mas_o_botao_executar_continua_funcionando")]),
    Funcao("F47", "Execução", "Pausar a automação que está executando", "tecla de pausa",
           [("teste", "tests/gui/test_controle_janela.py::test_f9_pausa_a_automacao_executando_e_f10_termina_o_que_faltava")]),
    Funcao("F48", "Execução", "Continuar a automação pausada, do ponto onde parou", "tecla de continuar",
           [("teste", "tests/gui/test_controle_janela.py::test_o_callback_do_atalho_registrado_para_f9_e_f10_pausa_e_continua")]),
    # ---- Gravação
    Funcao("F17", "Gravação", "Iniciar a gravação", "tecla de gravação", [("acao", "● Iniciar gravação", "sempre")]),
    Funcao("F18", "Gravação", "Cancelar a gravação", "", [("acao", "✕ Cancelar gravação", "sempre")]),
    Funcao("F19", "Gravação", "Pré-visualizar a gravação", "", [("acao", "▶ Pré-visualizar gravação", "sempre")]),
    # ---- Comandos (editor)
    Funcao("F20", "Comandos", "Adicionar um comando", "", [("botao", "＋ ADICIONAR COMANDO", "editor"), ("botao", "＋ Adicionar comando", "timeline")]),
    Funcao("F21", "Comandos", "Editar um comando", "", [("botao", "Editar comando", "editor")]),
    Funcao("F22", "Comandos", "Excluir os comandos selecionados", "Delete", [("botao", "Excluir selecionados", "editor")]),
    Funcao("F23", "Comandos", "Mover um comando para cima", "", [("botao", "▲ Subir", "editor")]),
    Funcao("F24", "Comandos", "Mover um comando para baixo", "", [("botao", "▼ Descer", "editor")]),
    Funcao("F25", "Comandos", "Agrupar comandos e gerenciar grupos", "", [("botao", "● Grupos", "editor")]),
    Funcao("F26", "Comandos", "Outras ações sobre os comandos (menu \"Mais…\")", "", [("botao", "Mais…", "editor")]),
    # ---- Timeline
    Funcao("F27", "Timeline", "Abrir a timeline da automação", "", [("botao", "▣ Abrir Timeline", "editor")]),
    Funcao("F28", "Timeline", "Ver a timeline no modo simples", "", [("botao", "Simples", "timeline")]),
    Funcao("F46", "Timeline", "Ver a timeline no modo avançado", "", [("botao", "Avançada", "timeline")]),
    Funcao("F29", "Timeline", "Ajustar a timeline à janela", "", [("botao", "Ajustar", "timeline")]),
    Funcao("F44", "Timeline", "Aproximar a timeline (zoom +)", "", [("botao", "+", "timeline")]),
    Funcao("F45", "Timeline", "Afastar a timeline (zoom −)", "", [("botao", "−", "timeline")]),
    Funcao("F30", "Timeline", "Ligar ou desligar o encaixe (Snap)", "", [("botao", "Snap", "timeline")]),
    Funcao("F31", "Timeline", "Editar as linhas mescladas", "", [("fonte", "timeline.py", "✎ Editar linhas mescladas")]),
    Funcao("F32", "Timeline", "Criar um grupo pela timeline", "", [("fonte", "timeline.py", "＋ Criar novo grupo")]),
    # ---- Programa
    Funcao("F33", "Programa", "Abrir as configurações do programa", "", [("acao", "⚙ Configurações", "sempre")]),
    Funcao("F34", "Programa", "Abrir o tutorial", "", [("acao", "❔ Tutorial", "sempre")]),
    Funcao("F35", "Programa", "Mostrar ou ocultar o teclado virtual", "", [("acao", "⌨ Mostrar teclado", "sempre")]),
    Funcao("F36", "Programa", "Mostrar ou ocultar o mouse virtual", "", [("acao", "🖱 Mostrar mouse", "sempre")]),
    # ---- Configurações do programa (abas do diálogo)
    Funcao("F38", "Configurações do programa", "Aparência (tema e cores)", "", [("fonte", "command_editor.py", "Aparência")]),
    Funcao("F39", "Configurações do programa", "Teclado e mouse virtuais", "", [("fonte", "command_editor.py", "Teclado e mouse virtuais")]),
    Funcao("F40", "Configurações do programa", "Gravação", "", [("fonte", "command_editor.py", "Gravação")]),
    Funcao("F41", "Configurações do programa", "Pasta das automações", "", [("fonte", "command_editor.py", "Mapas")]),
    Funcao("F42", "Configurações do programa", "Teclas de controle", "", [("fonte", "command_editor.py", "Controles")]),
    Funcao("F43", "Configurações do programa", "Execução", "", [("fonte", "command_editor.py", "Execução")]),
]

# Controles que existem na janela mas NÃO são funções do usuário: a alça da própria barra ("Principal"), fechar avisos,
# copiar o log de erro, e os botões de confirmar ou cancelar de diálogos. O teste que procura controles sem função no
# catálogo ignora estes textos.
CONTROLES_QUE_NAO_SAO_FUNCOES = {"Principal", "×", "Fechar", "📋 Copiar log completo", "Cancelar", "Adicionar", "Salvar",
                                  "Começar a usar"}  # este: página do tutorial antigo (índice 0), que nenhum código exibe mais


TELAS = ("sempre", "lista", "editor", "timeline")
_TELAS = {"sempre": "em todas as telas", "lista": "tela da lista", "editor": "tela do editor", "timeline": "tela da timeline"}


def descrever(acesso):
    tipo = acesso[0]
    if tipo == "acao":
        return f"Barra ({_TELAS[acesso[2]]}): {acesso[1]}"
    if tipo == "botao":
        return f"Botão ({_TELAS[acesso[2]]}): {acesso[1]}"
    if tipo == "painel":
        return f"Painel ({_TELAS[acesso[2]]}): {acesso[1]}"
    if tipo == "fonte":
        return f"Menu ou diálogo ({acesso[1]}): {acesso[2]}"
    return f"Tecla (teste: {acesso[1].split('::')[-1]})"


def markdown():
    linhas = [
        "# Funções do usuário",
        "",
        "Gerado de `tests/testsupport/funcoes_do_usuario.py`; não edite aqui. Para regenerar: "
        "`python tests/testsupport/funcoes_do_usuario.py > md/FUNCOES_DO_USUARIO.md`.",
        "",
        "Este é o catálogo do que o programa faz. O **ID não muda** (nem quando o botão muda de lugar ou de nome) e é o "
        "mesmo no app Android: cada função daqui precisa existir lá, com o mesmo nome. "
        "`tests/gui/test_funcoes_acessiveis.py` abre a janela e confere que toda função tem pelo menos um endereço; "
        "quem muda um controle muda a linha da função no mesmo commit (regras em `md/PLANO_VISUAL.md`).",
        "",
    ]
    grupo = None
    for f in FUNCOES:
        if f.grupo != grupo:
            grupo = f.grupo
            linhas += [f"## {grupo}", "", "| ID | Função | Onde está hoje | Atalho | Android |", "|---|---|---|---|---|"]
        onde = "<br>".join(descrever(a) for a in f.acessos).replace("|", "\\|")
        linhas.append(f"| {f.id} | {f.nome} | {onde} | {f.atalho or '—'} | a definir |")
        proxima = FUNCOES[FUNCOES.index(f) + 1] if FUNCOES.index(f) + 1 < len(FUNCOES) else None
        if proxima is None or proxima.grupo != grupo:
            linhas.append("")
    return "\n".join(linhas).rstrip() + "\n"


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdout.write(markdown())
