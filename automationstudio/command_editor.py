from __future__ import annotations



import shutil
from pathlib import PureWindowsPath
from . import core
from .core import *
from .input_system import *
from .project import *
from .overlays import *
from .vision import *
from PySide6.QtWidgets import (
    QAbstractButton, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFrame,
    QGroupBox, QInputDialog, QFileDialog, QLineEdit, QPlainTextEdit, QPushButton,
    QSizePolicy, QSlider, QSpinBox, QStyleOptionViewItem, QStyle,
    QTableWidget, QTextEdit, QWidget, QHBoxLayout, QLabel, QVBoxLayout, QListWidget, QListWidgetItem
)
from PySide6.QtGui import QPalette, QBrush
from PySide6.QtCore import QEventLoop, QTimer, QPoint, QRect, Qt, QEvent, QByteArray, QMimeData
from PySide6.QtGui import QCursor, QDrag, QPixmap


_ADV_WAIT_TIP = (
    "Sincronização de abertura: depois de iniciar um aplicativo, o Automation Studio "
    "aguarda o processo aparecer, permanecer estável e aplica o atraso de segurança "
    "antes de liberar o próximo comando."
)


class SelectionRubberBand(QWidget):
    """Área de seleção visual da tabela, desenhada dentro do viewport."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.hide()
        self._rect = QRect()
        self._color = QColor("#2F6FED")

    def set_theme(self, dark: bool, accent: str = "#2F6FED") -> None:
        # A seleção segue a regra de UX definida para o editor: azul no tema
        # claro e amarelo no tema escuro. O accent do tema escuro pode ser
        # personalizado, mas o padrão permanece o amarelo institucional.
        self._color = _normalized_color("#FFC53D" if dark else accent or "#2F6FED")
        self.update()

    def set_rect(self, rect: QRect) -> None:
        """Atualiza simultaneamente a geometria e o retângulo desenhado."""
        self._rect = rect.normalized()
        self.setGeometry(self._rect)
        self.update()

    def paintEvent(self, _event):
        # O widget é filho direto do viewport/canvas. A geometria já foi
        # normalizada pelo chamador, portanto o desenho deve usar o próprio
        # retângulo local do widget. A versão anterior mantinha `_rect` nulo
        # porque alguns caminhos chamavam `setGeometry()` diretamente; isso
        # fazia o widget existir e receber `show()`, mas pintar absolutamente
        # nada. Usar `self.rect()` torna a camada visual independente desse
        # detalhe de implementação.
        if self.rect().isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        c = QColor(self._color)
        fill = QColor(c); fill.setAlpha(24)
        border = QColor(c); border.setAlpha(170)
        painter.fillRect(self.rect(), fill)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(border, 2))
        painter.drawRect(self.rect().adjusted(1, 1, -1, -1))


class CommandDialog(QDialog):
    """Editor simples com telas específicas para teclado, mouse, movimento e scroll.

    Regra central (achado 2.07 da auditoria): abrir um comando e salvar sem mexer em nada não pode alterá-lo. O
    `result_command` reescreve o comando inteiro a partir dos campos da tela, então todo campo precisa ser carregado
    do comando na abertura E na troca de comando (`load_command`). As duas passam por `_load_fields`, a única fonte
    dos valores iniciais.
    """
    # Enquanto os campos são carregados, as caixas disparam sinais que recalculariam a sugestão de atraso com o
    # formulário pela metade. `_reload_from_command` calcula a sugestão uma vez, com tudo carregado.
    _loading = False
    _NO_PROCESS_LABEL = 'Nenhum aplicativo selecionado'  # item-guia dos combos de aplicativo: nunca é um valor
    _NO_POSITION_LABEL = 'Nenhuma posição escolhida.'

    def __init__(self,command=None,parent=None):
        super().__init__(parent); self.setWindowTitle('Adicionar ação' if command is None else 'Editar ação'); self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding); self.setMinimumWidth(0); self.setMinimumHeight(0)
        self._command=command or Command(); self._move_pos=None
        self.type_combo=QComboBox(); self.type_combo.addItem('⌨ Pressionar uma tecla',InputType.KEY); self.type_combo.addItem('🖱 Clicar / segurar o mouse',InputType.MOUSE_BUTTON); self.type_combo.addItem('🖱 Mover o mouse para uma posição',InputType.MOUSE_MOVE); self.type_combo.addItem('↕ Rolar a roda do mouse',InputType.MOUSE_SCROLL); self.type_combo.addItem('⌨ Digitar um texto',InputType.TEXT); self.type_combo.addItem('▣ Abrir aplicativo',InputType.APP_OPEN); self.type_combo.addItem('⏳ Esperar',InputType.WAIT); self.type_combo.currentIndexChanged.connect(self._update_form)
        self.target_combo=QComboBox(); self.target_combo.setEditable(False)
        self.app_browse=QPushButton('Procurar executável…')
        self.app_browse.clicked.connect(self._browse_app_executable)
        self.app_target_row=QWidget(); self.app_target_layout=QHBoxLayout(self.app_target_row); self.app_target_layout.setContentsMargins(0,0,0,0); self.app_target_layout.addWidget(self.target_combo,1); self.app_target_layout.addWidget(self.app_browse)
        self.text_edit=QTextEdit(); self.text_edit.setPlaceholderText('Digite aqui o texto que a automação deverá escrever…'); self.text_edit.setMinimumHeight(90)
        self.text_timing_label=QLabel('Tempo calculado: 0,000 s · atraso determinístico: 0,000 s')
        self.text_timing_label.setWordWrap(True); self.text_timing_label.setStyleSheet('color:#8f96a3;font-size:12px')
        self.text_edit.textChanged.connect(self._refresh_text_timing)
        self.action_combo=QComboBox(); self.action_combo.addItem('Pressionar e soltar',ActionType.PRESS_AND_RELEASE); self.action_combo.addItem('Manter pressionado',ActionType.PRESS); self.action_combo.addItem('Soltar',ActionType.RELEASE)
        self.duration=self._spin(.1)
        self.delay=self._spin(0.0); self.start=self._spin(0.0)
        self.wait_process_edit=QComboBox(); self.wait_process_edit.setEditable(True)
        self.wait_process_edit.setInsertPolicy(QComboBox.NoInsert)
        self.wait_process_edit.setPlaceholderText('Selecione um aplicativo ou informe o .exe')
        self._process_presets=[
            ('Microsoft Edge', 'msedge.exe'),
            ('Bloco de Notas', 'notepad.exe'),
            ('Explorador de Arquivos', 'explorer.exe'),
            ('Calculadora', 'CalculatorApp.exe;calc.exe'),
            ('Outlook (clássico)', 'outlook.exe'),
            ('Outlook (novo)', 'olk.exe'),
        ]
        # A lista inicial combina aplicativos Windows comuns com executáveis
        # encontrados no PATH. O botão de arquivo continua disponível para
        # qualquer programa fora dessa lista.
        self._app_presets = list(self._process_presets)
        for candidate in ('python.exe','cmd.exe','powershell.exe','wt.exe'):
            resolved = shutil.which(candidate)
            if resolved and not any(exe == resolved for _, exe in self._app_presets):
                self._app_presets.append((Path(resolved).stem, resolved))
        self.wait_process_edit.addItem(self._NO_PROCESS_LABEL, '')
        for label,exe in self._process_presets:
            self.wait_process_edit.addItem(f'{label} — {exe}', exe)
        self.wait_timeout=self._spin(0.0); self.wait_timeout.setRange(0,3600); self.wait_timeout.setSingleStep(1.0)
        self.wait_stable=QSpinBox(); self.wait_stable.setRange(0,10000); self.wait_stable.setSingleStep(25); self.wait_stable.setSuffix(' ms'); self.wait_stable.setValue(core.APP_STABLE_DEFAULT_MS)
        self.wait_after=self._spin(core.APP_AFTER_OPEN_DEFAULT)
        self.wait_help=QLabel('Após esta ação, aguarde o aplicativo aparecer no Windows, permanecer presente pelo tempo de estabilidade e então aguarde o atraso adicional. Não é necessário informar RAM.'); self.wait_help.setWordWrap(True); self.wait_help.setStyleSheet('color:#8f96a3;font-size:12px'); self.wait_help.hide()
        self.scroll_direction=QComboBox(); self.scroll_direction.addItem('Para cima', 'up'); self.scroll_direction.addItem('Para baixo','down'); self.scroll_direction.addItem('Para a esquerda','left'); self.scroll_direction.addItem('Para a direita','right')
        self.scroll_lines=QSpinBox(); self.scroll_lines.setRange(1,1000); self.scroll_lines.setValue(1); self.scroll_lines.setSuffix(' linha(s)')
        self.choose_position=QPushButton('📍 Escolher posição na tela')
        self.position_label=QLabel(self._NO_POSITION_LABEL)
        self.position_label.setStyleSheet('color:#9aa0aa')
        self.choose_position.clicked.connect(self._pick_position)
        self.help=QLabel(); self.help.setWordWrap(True); self.help.setStyleSheet('color:#9aa0aa'); self.help.hide()
        self.same_time=QCheckBox('Começar junto com a ação anterior'); self.same_time.setToolTip('Faz este comando iniciar no mesmo instante do comando anterior.')
        # Descrição e grupo são metadados opcionais: ficam exclusivamente
        # nas opções avançadas para não parecerem campos obrigatórios.
        self.description=QLineEdit()
        self.description.setPlaceholderText('Opcional — ex.: Ataque inicial')
        self.group_combo=QComboBox()  # os itens (e a escolha) vêm de `_select_group`, chamado por `_load_fields`
        self.advanced=QCheckBox('⚙ Opções avançadas'); self.advanced.setToolTip('Mostra somente configurações complementares: descrição, grupo, timeline e sincronização de abertura. Passe o mouse sobre os rótulos para ver a explicação de cada opção.'); self.advanced.setChecked(True); self.advanced.toggled.connect(self._toggle_advanced)
        self.advanced_box=QWidget()
        adv=QVBoxLayout(self.advanced_box)

        self.condition_section=QGroupBox('Condições antes desta ação')
        cond_layout=QVBoxLayout(self.condition_section); cond_layout.setContentsMargins(8,8,8,8); cond_layout.setSpacing(6)
        cond_help=QLabel('As condições são verificadas antes da ação. Elas não alteram o tempo planejado da Timeline; o executor pode aguardar tempo real adicional.')
        cond_help.setWordWrap(True); cond_help.setStyleSheet('color:#8f96a3;font-size:12px')
        cond_layout.addWidget(cond_help)
        self.condition_list=QListWidget(); self.condition_list.setMaximumHeight(100); cond_layout.addWidget(self.condition_list)
        cond_form=QFormLayout(); cond_form.setContentsMargins(0,0,0,0); cond_form.setHorizontalSpacing(8); cond_form.setVerticalSpacing(5)
        self.condition_type=QComboBox(); self.condition_type.addItem('Esperar pelo aplicativo de um comando', WaitConditionType.PROCESS); self.condition_type.addItem('Aguardar um tempo', WaitConditionType.DELAY); self.condition_type.addItem('Esperar por imagem', WaitConditionType.IMAGE)
        self.condition_command=QComboBox(); self.condition_command.setPlaceholderText('Selecione o número do comando-alvo')
        parent_map=getattr(parent,'_automation_map',None)
        self._condition_parent_map=parent_map
        self.condition_command.addItem('Selecione o comando…', '')
        if parent_map:
            for idx, command in enumerate(parent_map.commands, 1):
                desc=(getattr(command,'description','') or getattr(command,'target','') or getattr(command,'text','') or command.type.value).replace('\n',' ')[:48]
                self.condition_command.addItem(f'Comando {idx} — {desc}', command.id)
        self.condition_target=QLineEdit(); self.condition_target.setPlaceholderText('Compatibilidade: nome do processo')
        self.condition_image_path=QLineEdit(); self.condition_image_path.setPlaceholderText('Selecione uma imagem…')
        self.condition_image_browse=QPushButton('Procurar…'); self.condition_image_browse.clicked.connect(self._browse_condition_image)
        self.condition_image_row=QWidget(); _ir=QHBoxLayout(self.condition_image_row); _ir.setContentsMargins(0,0,0,0); _ir.addWidget(self.condition_image_path,1); _ir.addWidget(self.condition_image_browse)
        self.condition_confidence=QDoubleSpinBox(); self.condition_confidence.setRange(0.50,1.00); self.condition_confidence.setDecimals(3); self.condition_confidence.setSingleStep(0.01); self.condition_confidence.setValue(0.95)
        self.condition_interval=QDoubleSpinBox(); self.condition_interval.setRange(0.05,60); self.condition_interval.setDecimals(3); self.condition_interval.setSingleStep(0.05); self.condition_interval.setValue(0.5); self.condition_interval.setSuffix(' s')
        self.condition_search=QCheckBox('Procurar a imagem dentro da região')
        self.condition_search.setToolTip('Quando disponível, usa correspondência espacial via OpenCV. Sem OpenCV, o modo básico de comparação continua disponível.')
        self.condition_image_preview=QLabel('Nenhuma imagem selecionada'); self.condition_image_preview.setAlignment(Qt.AlignCenter); self.condition_image_preview.setMinimumHeight(72); self.condition_image_preview.setMaximumHeight(120); self.condition_image_preview.setStyleSheet('border:1px solid palette(mid); color:#8f96a3')
        self.condition_region_x=QSpinBox(); self.condition_region_y=QSpinBox(); self.condition_region_w=QSpinBox(); self.condition_region_h=QSpinBox()
        for widget in (self.condition_region_x,self.condition_region_y): widget.setRange(-10000,10000)
        for widget in (self.condition_region_w,self.condition_region_h): widget.setRange(0,20000)
        self.condition_timeout=QDoubleSpinBox(); self.condition_timeout.setRange(0,3600); self.condition_timeout.setDecimals(3); self.condition_timeout.setSingleStep(0.5); self.condition_timeout.setSuffix(' s')
        self.condition_stable=QSpinBox(); self.condition_stable.setRange(0,10000); self.condition_stable.setSingleStep(50); self.condition_stable.setSuffix(' ms'); self.condition_stable.setValue(1000)
        self.condition_after=QDoubleSpinBox(); self.condition_after.setRange(0,3600); self.condition_after.setDecimals(3); self.condition_after.setSingleStep(0.1); self.condition_after.setSuffix(' s')
        cond_form.addRow('Tipo:', self.condition_type); cond_form.addRow('Comando-alvo:', self.condition_command); cond_form.addRow('Processo:', self.condition_target); cond_form.addRow('Imagem:', self.condition_image_row); cond_form.addRow('', self.condition_image_preview); cond_form.addRow('', self.condition_search); cond_form.addRow('Precisão:', self.condition_confidence); cond_form.addRow('Verificar a cada:', self.condition_interval); cond_form.addRow('Região X:', self.condition_region_x); cond_form.addRow('Região Y:', self.condition_region_y); cond_form.addRow('Largura:', self.condition_region_w); cond_form.addRow('Altura:', self.condition_region_h); cond_form.addRow('Tempo:', self.condition_timeout); cond_form.addRow('Estabilidade:', self.condition_stable); cond_form.addRow('Atraso após:', self.condition_after)
        cond_layout.addLayout(cond_form)
        cond_buttons=QHBoxLayout(); self.condition_add=QPushButton('Adicionar condição'); self.condition_edit=QPushButton('Editar selecionada'); self.condition_remove=QPushButton('Remover selecionada'); cond_buttons.addWidget(self.condition_add); cond_buttons.addWidget(self.condition_edit); cond_buttons.addWidget(self.condition_remove); cond_layout.addLayout(cond_buttons)
        self.condition_type.currentIndexChanged.connect(self._update_condition_form)
        self.condition_command.currentIndexChanged.connect(self._condition_command_changed)
        self.condition_add.clicked.connect(self._add_condition)
        self.condition_edit.clicked.connect(self._edit_condition)
        self.condition_remove.clicked.connect(self._remove_condition)
        self._update_condition_form()
        adv.addWidget(self.condition_section)
        adv.setContentsMargins(0,0,0,0)
        adv.setSpacing(7)
        self._advanced_labels=[]
        self._advanced_form=QFormLayout()
        self._advanced_form.setContentsMargins(0,0,0,0)
        self._advanced_form.setHorizontalSpacing(8); self._advanced_form.setVerticalSpacing(5)
        self._advanced_form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._advanced_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        def _adv_row(text, widget, tip):
            lab=QLabel(text); lab.setMinimumWidth(0); lab.setMaximumWidth(180); lab.setWordWrap(True); lab.setToolTip(tip)
            widget.setToolTip(tip)
            self._advanced_form.addRow(lab, widget); self._standardize_field(widget)
            self._advanced_labels.append(lab)
        _adv_row('Descrição (opcional):',self.description,'Nome ou observação para identificar este comando. Não altera a execução.')
        _adv_row('Grupo (opcional):',self.group_combo,'Organiza comandos relacionados em um grupo visual.')
        _adv_row('Começar em:',self.start,'Momento em que o comando começa na timeline. O valor sugerido considera o término dos comandos anteriores.')
        _adv_row('Atraso sugerido:',self.delay,'Margem adicional entre este comando e o anterior. É uma referência e não altera automaticamente o início real.')
        adv.addLayout(self._advanced_form)

        # Sincronização é uma seção própria: o título fica acima dos campos,
        # evitando a antiga coluna aninhada que comprimía rótulos e controles.
        self.sync_section=QWidget()
        sync_layout=QVBoxLayout(self.sync_section); sync_layout.setContentsMargins(0,4,0,0); sync_layout.setSpacing(5)
        sync_title=QLabel('Sincronização de abertura')
        sync_title.setStyleSheet('font-weight:700;font-size:13px;')
        sync_title.setToolTip('Controla a espera automática depois de abrir um aplicativo antes de liberar os comandos seguintes.')
        sync_layout.addWidget(sync_title)
        wait_form=QFormLayout(); wait_form.setContentsMargins(0,0,0,0); wait_form.setHorizontalSpacing(8); wait_form.setVerticalSpacing(5)
        wait_form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        for lab_text, widget, tip in [
            ('Aplicativo:',self.wait_process_edit,'Processo que deve aparecer antes de continuar.'),
            ('Tempo limite:',self.wait_timeout,'Tempo máximo de espera. Zero significa sem limite.'),
            ('Estabilidade:',self.wait_stable,'Tempo durante o qual o processo deve permanecer presente/estável antes de continuar.'),
            ('Atraso de segurança:',self.wait_after,'Margem de segurança aplicada depois de o aplicativo ser considerado pronto.')]:
            lab=QLabel(lab_text); lab.setMinimumWidth(115); lab.setMaximumWidth(145); lab.setToolTip(tip); widget.setToolTip(tip)
            wait_form.addRow(lab,widget); self._standardize_field(widget)
        sync_layout.addLayout(wait_form)
        self.wait_help.setToolTip(_ADV_WAIT_TIP)
        sync_layout.addWidget(self.wait_help)
        adv.addWidget(self.sync_section)
        self.suggestion_label=QLabel('O início sugerido usa o término mais recente dos comandos existentes.')
        self.suggestion_label.setWordWrap(True); self.suggestion_label.setStyleSheet('color:#8f96a3;font-size:12px'); self.suggestion_label.hide()
        adv.addWidget(self.suggestion_label)
        self.description.textChanged.connect(lambda _=None: self._refresh_delay_suggestion())
        self.group_combo.currentIndexChanged.connect(lambda _=None: self._refresh_delay_suggestion())
        self.delay.valueChanged.connect(lambda _=None: self._refresh_delay_suggestion())
        buttons=QDialogButtonBox(QDialogButtonBox.Cancel|QDialogButtonBox.Ok); buttons.button(QDialogButtonBox.Ok).setText('Adicionar' if command is None else 'Salvar'); buttons.button(QDialogButtonBox.Cancel).setText('Cancelar'); buttons.accepted.connect(self._accept); buttons.rejected.connect(self.reject); self.buttons=buttons
        lay=QVBoxLayout(self); lay.setContentsMargins(10,10,10,10); lay.setSpacing(7); title=QLabel('O que você quer que o programa faça?'); title.setStyleSheet('font-size:18px;font-weight:700'); lay.addWidget(title); lay.addWidget(self.help)
        form=QFormLayout(); form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow); form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter); form.setHorizontalSpacing(8); form.setVerticalSpacing(4)
        self._form_rows={}
        self._form_labels={}
        self._add_form_row(form,'action','Ação:',self.type_combo,'Escolha o tipo de ação que será executada.')
        self._add_form_row(form,'target','Tecla:',self.app_target_row,'Selecione somente o recurso necessário para esta ação.')
        self._add_form_row(form,'text','Texto:',self.text_edit,'Digite o texto que será enviado ao aplicativo ativo.')
        self._add_form_row(form,'text_timing','',self.text_timing_label,None)
        self._add_form_row(form,'behavior','Comportamento:',self.action_combo,'Define se a tecla será pressionada e solta, mantida pressionada ou apenas solta.')
        self._add_form_row(form,'duration','Tempo:',self.duration,'Duração da tecla ou do botão do mouse.')
        self._add_form_row(form,'direction','Direção:',self.scroll_direction,'Direção da rolagem do mouse.')
        self._add_form_row(form,'quantity','Quantidade:',self.scroll_lines,'Quantidade de linhas/etapas da rolagem.')
        self._add_form_row(form,'position',self.choose_position,self.position_label,'Escolha a posição exata do cursor na tela.')
        self._main_form=form
        lay.addLayout(form); lay.addWidget(self.same_time); lay.addWidget(self.advanced); lay.addWidget(self.advanced_box);
        # Os botões são hospedados pelo rodapé fixo da sidebar principal.
        buttons.hide();
        lay.addStretch(1); self._reload_from_command()
    def _add_form_row(self, form, key, label, widget, tooltip=None):
        if isinstance(label, str):
            label_widget=QLabel(label)
        else:
            label_widget=label
        if isinstance(label_widget, QLabel):
            label_widget.setMinimumWidth(92)
            label_widget.setMaximumWidth(135)
            label_widget.setToolTip(tooltip or '')
        if tooltip:
            widget.setToolTip(tooltip)
        row=form.rowCount()
        form.addRow(label_widget, widget)
        self._form_rows[key]=row
        self._form_labels[key]=label_widget
        self._standardize_field(widget)

    @staticmethod
    def _standardize_field(widget):
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        if isinstance(widget, QTextEdit):
            widget.setMinimumWidth(0); widget.setMinimumHeight(72); widget.setMaximumHeight(110)
        elif isinstance(widget, QWidget):
            widget.setMinimumWidth(160)
            widget.setMaximumWidth(380)
            if isinstance(widget, QComboBox): widget.setMinimumHeight(28); widget.setMaximumHeight(30)
            elif isinstance(widget, (QLineEdit,QSpinBox,QDoubleSpinBox)): widget.setMinimumHeight(28); widget.setMaximumHeight(30)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_responsive_forms()

    def _apply_responsive_forms(self):
        # Em larguras estreitas, todas as relações label→campo passam para
        # duas linhas. Isso evita sobreposição em qualquer ponto da sidebar.
        narrow = self.width() < 390
        policy = QFormLayout.WrapAllRows if narrow else QFormLayout.WrapLongRows
        for form in (getattr(self, '_main_form', None), getattr(self, '_advanced_form', None)):
            if form is not None:
                form.setRowWrapPolicy(policy)
        for child in self.findChildren(QFormLayout):
            child.setRowWrapPolicy(policy)

    def _set_form_row_visible(self, key, visible):
        row=self._form_rows.get(key)
        if row is None: return
        try:
            self._main_form.setRowVisible(row, bool(visible))
        except Exception:
            item=self._main_form.itemAt(row,QFormLayout.LabelRole)
            if item and item.widget(): item.widget().setVisible(bool(visible))
            item=self._main_form.itemAt(row,QFormLayout.FieldRole)
            if item and item.widget(): item.widget().setVisible(bool(visible))

    def load_command(self, command: Command) -> None:
        """Recarrega o editor existente sem fechar/reabrir a Sidebar.

        Relê TODOS os campos: o que ficasse do comando anterior seria gravado no novo ao salvar (início, atraso,
        duração, rolagem, grupo, condições, processo, posição).
        """
        self._command = copy.deepcopy(command)
        self._reload_from_command()

    def _reload_from_command(self) -> None:
        self._loading = True
        try:
            self._load_fields()
        finally:
            self._loading = False
        self._set_type_from_command(); self._update_form()

    def _load_fields(self) -> None:
        """Copia o comando para todos os campos da tela, exceto o tipo e o alvo (ver `_set_type_from_command` e `_update_form`)."""
        c = self._command
        self._move_pos = QPoint(int(c.x), int(c.y)) if c.x is not None and c.y is not None else None
        self._refresh_position_label()
        self.text_edit.setPlainText(str(getattr(c, 'text', '') or ''))
        self.description.setText(str(getattr(c, 'description', '') or ''))
        self._load_number(self.start, float(c.start))
        self._load_number(self.delay, float(c.delay))
        self._load_number(self.duration, float(c.duration or .1))
        self._load_scroll_widgets()
        self._select_group()
        self._show_wait_process(getattr(c, 'wait_process', ''))
        self._load_number(self.wait_timeout, float(getattr(c, 'wait_timeout', 0.0)))
        self._load_number(self.wait_stable, int(getattr(c, 'wait_stable_ms', core.APP_STABLE_DEFAULT_MS)))
        self._load_number(self.wait_after, float(getattr(c, 'wait_after_open', core.APP_AFTER_OPEN_DEFAULT)))
        self.condition_list.clear()
        for existing in getattr(c, 'conditions', []) or []:
            self._append_condition_item(existing)

    @staticmethod
    def _load_number(spin, value) -> None:
        """Coloca no campo o valor que o comando JÁ tem, sem cortá-lo no limite da caixa (o limite vale para quem digita)."""
        value = max(0, value)
        if value > spin.maximum():
            spin.setMaximum(value)
        spin.setValue(value)

    def _load_scroll_widgets(self) -> None:
        dx, dy = int(self._command.scroll_dx or 0), int(self._command.scroll_dy or 0)
        self.scroll_lines.setValue(max(1, abs(dy or dx or 1)))
        direction = 0 if dy > 0 else 1 if dy < 0 else 2 if dx < 0 else 3 if dx > 0 else 0
        self.scroll_direction.setCurrentIndex(direction)

    def _select_group(self) -> None:
        """Monta a lista de grupos e escolhe o do comando.

        O painel lateral não entrega o mapa ao editor (`parent._automation_map` não existe), então os grupos do mapa
        não estão na lista. Um grupo que o comando tem mas a lista não conhece entra como item extra: sem isso o
        combo cairia em "Sem grupo" e o grupo seria apagado ao salvar.
        """
        combo = self.group_combo
        combo.clear()
        combo.addItem('Sem grupo', '')
        parent_map = getattr(self.parent(), '_automation_map', None)
        if parent_map:
            for gid, g in parent_map.groups.items():
                combo.addItem(g.name, gid)
        gid = str(getattr(self._command, 'group_id', '') or '')
        name = str(getattr(self._command, 'group', '') or '')
        index = 0
        if gid:
            index = combo.findData(gid)
            if index < 0:
                combo.addItem(name or gid, gid)
                index = combo.count() - 1
        elif name:
            index = combo.findText(name)
            if index < 0:
                combo.addItem(name, '')
                index = combo.count() - 1
        combo.setCurrentIndex(index)

    def _show_wait_process(self, process) -> None:
        """Mostra o processo a esperar: o item da lista, o texto digitado, ou o item-guia quando não há processo."""
        process = str(process or '').strip()
        combo = self.wait_process_edit
        if not process:
            combo.setCurrentIndex(0)
            return
        index = combo.findData(process)
        if index >= 0:
            combo.setCurrentIndex(index)
        else:
            combo.setCurrentText(process)  # combo editável: só o texto do campo muda

    def _wait_process_value(self) -> str:
        """O processo a esperar: o executável do item escolhido, ou o texto digitado.

        O texto do campo manda: num combo editável o índice atual não acompanha o que a pessoa digita. O item-guia
        "Nenhum aplicativo selecionado" vale ''. Antes, `currentData() or currentText()` gravava o texto-guia como
        processo de todo comando novo, e o motor esperaria para sempre por um processo com esse nome.
        """
        combo = self.wait_process_edit
        text = combo.currentText().strip()
        for i in range(combo.count()):
            if combo.itemText(i) == text:
                return str(combo.itemData(i) or '')
        return text

    def _refresh_position_label(self) -> None:
        if self._move_pos is None:
            self.position_label.setText(self._NO_POSITION_LABEL)
        else:
            self.position_label.setText(f'Posição definida: X={self._move_pos.x()}, Y={self._move_pos.y()}')

    def _set_type_from_command(self):
        c = self._command
        idx=self.type_combo.findData(c.type); self.type_combo.setCurrentIndex(max(0,idx))
        # "Comportamento" só existe para tecla; nos demais tipos o editor grava sempre "pressionar e soltar".
        action = c.action if c.type == InputType.KEY else ActionType.PRESS_AND_RELEASE
        self.action_combo.setCurrentIndex(max(0, self.action_combo.findData(action)))
    def _spin(self,v):
        s=QDoubleSpinBox(); s.setRange(0,3600); s.setDecimals(3); s.setSingleStep(.05); s.setSuffix(' s'); s.setValue(max(0,float(v))); return s
    @staticmethod
    def _key_options():
        return list('ABCDEFGHIJKLMNOPQRSTUVWXYZÇ')+list('0123456789')+[f'F{i}' for i in range(1,13)]+['ESC','TAB','CAPSLOCK','SHIFT','CTRL','ALT','ALTGR','ENTER','BACKSPACE','SPACE','WIN','MENU','FN','INSERT','HOME','PAGEUP','DELETE','END','PAGEDOWN','UP','DOWN','LEFT','RIGHT','PRINTSCREEN','SCROLLLOCK','PAUSE','NUMLOCK','NUM/','NUM*','NUM-','NUM+','NUM7','NUM8','NUM9','NUM4','NUM5','NUM6','NUM1','NUM2','NUM3','NUM0','NUM.','NUMENTER']
    def _toggle_advanced(self,c): self.advanced_box.setVisible(c); self.updateGeometry()
    def _update_condition_form(self):
        typ=self.condition_type.currentData(); process=typ==WaitConditionType.PROCESS; image=typ==WaitConditionType.IMAGE
        for widget, visible in ((self.condition_command,process),(self.condition_target,process),(self.condition_image_row,image),(self.condition_confidence,image),(self.condition_interval,image),(self.condition_region_x,image),(self.condition_region_y,image),(self.condition_region_w,image),(self.condition_region_h,image),(self.condition_stable,process)):
            widget.setVisible(visible)
        # O rótulo da primeira coluna é mantido simples; os campos são ocultados
        # sem remover o layout para preservar a geometria estável da sidebar.
        self.condition_timeout.setToolTip('Tempo máximo da espera. Zero significa sem limite.')
        self.condition_after.setToolTip('Atraso adicional depois que a condição for satisfeita.')
        self.condition_target.setToolTip('Compatibilidade com mapas antigos. Para novos comandos, selecione o número do comando-alvo acima.')
        self.condition_command.setToolTip('Escolha pelo número o comando que abre ou representa o aplicativo que deve estar pronto.')

    def _append_condition_item(self, condition: WaitCondition):
        item = QListWidgetItem()
        item.setData(Qt.UserRole, copy.deepcopy(condition))
        if condition.type == WaitConditionType.PROCESS:
            cid=str(condition.parameters.get('command_id','')).strip()
            row=next((i+1 for i,c in enumerate(getattr(self._condition_parent_map,'commands',[])) if c.id==cid), None)
            label=f'Comando {row} — aplicativo' if row else f'Processo: {condition.target or "(não definido)"}'
            text = f'{label} · limite {condition.timeout:g}s · estabilidade {condition.stable_ms}ms · após {condition.after:g}s'
        elif condition.type == WaitConditionType.DELAY:
            text = f'Aguardar {float(condition.timeout or condition.after):g}s'
        elif condition.type == WaitConditionType.IMAGE:
            text = f'Imagem: {Path(str(condition.parameters.get("image_path",""))).name or "(não definida)"} · precisão {float(condition.parameters.get("confidence",0.95)):.0%}'
        else:
            text = f'Condição: {condition.type.value}'
        item.setText(text); self.condition_list.addItem(item)

    def _add_condition(self):
        typ=self.condition_type.currentData()
        command_id=self.condition_command.currentData() if typ == WaitConditionType.PROCESS else ''
        if typ == WaitConditionType.PROCESS and not command_id and not self.condition_target.text().strip():
            QMessageBox.warning(self, 'Condição incompleta', 'Selecione o número do comando que deve ser aguardado.')
            return
        if typ == WaitConditionType.IMAGE and not self.condition_image_path.text().strip():
            QMessageBox.warning(self, 'Condição incompleta', 'Selecione a imagem que deve ser encontrada.')
            return
        if typ == WaitConditionType.DELAY and self.condition_timeout.value() <= 0 and self.condition_after.value() <= 0:
            QMessageBox.warning(self, 'Condição incompleta', 'Defina um tempo maior que zero.')
            return
        condition=WaitCondition(
            type=typ, target=self.condition_target.text().strip(), timeout=self.condition_timeout.value(),
            stable_ms=self.condition_stable.value(), after=self.condition_after.value(),
            parameters=({'command_id': str(command_id)} if command_id else {}) | ({'image_path': self.condition_image_path.text().strip(), 'confidence': self.condition_confidence.value(), 'interval': self.condition_interval.value(), 'search': self.condition_search.isChecked(), 'region': {'x': self.condition_region_x.value(),'y': self.condition_region_y.value(),'w': self.condition_region_w.value(),'h': self.condition_region_h.value()}} if typ == WaitConditionType.IMAGE else {})
        )
        errors=condition.validate()
        if errors:
            QMessageBox.warning(self, 'Condição inválida', '\n'.join(errors)); return
        self._append_condition_item(condition)
        self.condition_target.clear(); self.condition_timeout.setValue(0.0); self.condition_after.setValue(0.0)

    def _edit_condition(self):
        row=self.condition_list.currentRow()
        if row < 0:
            return
        item=self.condition_list.item(row); condition=item.data(Qt.UserRole)
        if not isinstance(condition, WaitCondition):
            return
        self.condition_type.setCurrentIndex(max(0, self.condition_type.findData(condition.type)))
        self.condition_target.setText(condition.target)
        cid=str(condition.parameters.get('command_id',''))
        idx=self.condition_command.findData(cid); self.condition_command.setCurrentIndex(max(0,idx))
        self.condition_timeout.setValue(float(condition.timeout))
        self.condition_stable.setValue(int(condition.stable_ms))
        self.condition_after.setValue(float(condition.after))
        p=condition.parameters or {}
        self.condition_search.setChecked(bool(p.get('search',False)))
        image_path=str(p.get('image_path','')); self.condition_image_path.setText(image_path); self._update_condition_preview(image_path)
        self.condition_confidence.setValue(float(p.get('confidence',0.95) or 0.95))
        self.condition_interval.setValue(float(p.get('interval',0.5) or 0.5))
        region=p.get('region',{}) or {}
        self.condition_region_x.setValue(int(region.get('x',0) or 0)); self.condition_region_y.setValue(int(region.get('y',0) or 0)); self.condition_region_w.setValue(int(region.get('w',0) or 0)); self.condition_region_h.setValue(int(region.get('h',0) or 0))
        self.condition_list.takeItem(row)

    def _update_condition_preview(self, path: str) -> None:
        """Mostra a miniatura da imagem de referência, ou o motivo de não haver miniatura."""
        label = self.condition_image_preview
        text = str(path or '').strip()
        label.setPixmap(QPixmap())
        if not text:
            label.setText('Nenhuma imagem selecionada')
            return
        pixmap = QPixmap(text)
        if pixmap.isNull():
            label.setText('Não foi possível abrir a imagem:\n' + os.path.basename(text))
            return
        label.setText('')
        label.setPixmap(pixmap.scaled(max(96, label.width() - 8), 112, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _browse_condition_image(self):
        path,_=QFileDialog.getOpenFileName(self,'Selecionar imagem para aguardar','','Imagens (*.png *.jpg *.jpeg *.bmp *.webp)')
        if path: self.condition_image_path.setText(path); self._update_condition_preview(path)

    def _condition_command_changed(self, _index=0):
        cid=self.condition_command.currentData()
        if not cid: return
        mp=self._condition_parent_map
        cmd=next((c for c in getattr(mp,'commands',[]) if c.id==cid),None) if mp else None
        if cmd is not None:
            process=str(getattr(cmd,'wait_process','') or '').strip()
            if not process:
                process=str(getattr(cmd,'target','') or '').strip()
            if process:
                self.condition_target.setText(process)

    def _remove_condition(self):
        row=self.condition_list.currentRow()
        if row >= 0:
            self.condition_list.takeItem(row)

    def _current_conditions(self) -> list[WaitCondition]:
        result=[]
        for i in range(self.condition_list.count()):
            item=self.condition_list.item(i); data=item.data(Qt.UserRole)
            if isinstance(data, WaitCondition): result.append(copy.deepcopy(data))
        return result

    def _update_form(self):
        t=self.type_combo.currentData()
        key=t==InputType.KEY; mouse=t==InputType.MOUSE_BUTTON; move=t==InputType.MOUSE_MOVE; scroll=t==InputType.MOUSE_SCROLL; text_type=t==InputType.TEXT; app=t==InputType.APP_OPEN; wait_cmd=t==InputType.WAIT
        self.app_target_row.setVisible(app); self.app_browse.setVisible(app)
        if hasattr(self, '_form_labels'):
            self._form_labels.get('target', QLabel()).setText('Tecla:' if key else 'Botão:' if mouse else 'Aplicativo:' if app else 'Opção:')
        self.target_combo.clear()
        if wait_cmd:
            self.help.setText('Crie uma ou mais condições. A execução só continua quando todas forem satisfeitas.')
        elif key:
            vals=self._key_options()
            # Uma tecla que a lista fixa não tem (as que o gravador produz, por exemplo ";") entra como item extra.
            # Antes o combo caía em "A" e o comando passava a apertar outra tecla ao ser salvo. Só vale para comando
            # do tipo tecla: o alvo de um botão do mouse ou de um aplicativo não é uma tecla.
            wanted=str(self._command.target or '').strip().upper() if self._command.type == InputType.KEY else ''
            if wanted and wanted not in vals: vals.append(wanted)
            self.target_combo.addItems(vals)
            if wanted: self.target_combo.setCurrentIndex(max(0, self.target_combo.findText(wanted)))
            self.target_combo.setEnabled(True)
            self.action_combo.setVisible(True); self.duration.setVisible(True)
            self.help.setText('Escolha uma tecla do teclado brasileiro e por quanto tempo ela ficará pressionada.')
        elif app:
            self.target_combo.addItem(self._NO_PROCESS_LABEL, '')
            for label,exe in self._app_presets: self.target_combo.addItem(f'{label} — {exe}', exe)
            current=str(self._command.target or '') if self._command.type == InputType.APP_OPEN else ''; idx=self.target_combo.findData(current)
            if current and idx < 0:
                # Executável que a lista não tem (escolhido em "Procurar executável…"): entra como item extra. Antes o
                # combo caía em "Nenhum aplicativo selecionado" e esse texto-guia era gravado como o aplicativo a abrir.
                self.target_combo.addItem(f'{PureWindowsPath(current).stem} — {current}', current); idx=self.target_combo.count()-1
            self.target_combo.setCurrentIndex(idx if idx >= 0 else 0); self.target_combo.setEnabled(True)
            self.help.setText('Escolha um aplicativo da lista ou procure um .exe. A sincronização aguarda o processo estar pronto antes do próximo comando.')
        elif mouse:
            for text,data in [('Botão esquerdo','left'),('Botão direito','right'),('Botão do meio','middle'),('Botão lateral 1','x1'),('Botão lateral 2','x2')]: self.target_combo.addItem(text,data)
            idx=self.target_combo.findData(self._command.target or 'left'); self.target_combo.setCurrentIndex(max(0,idx)); self.target_combo.setEnabled(True)
            self.help.setText('Escolha o botão do mouse e a duração do clique.')
        elif move:
            self.help.setText('Escolha a posição exata do cursor na tela.')
        elif scroll:
            self.help.setText('Escolha a direção e a quantidade da rolagem.')
        else:
            self.help.setText('Digite o texto. A duração é calculada automaticamente pela quantidade de caracteres e pelo intervalo configurado.')
            self._refresh_text_timing()
        self._set_form_row_visible('target', key or mouse or app)
        self.sync_section.setVisible(app)
        self.condition_section.setVisible(True)
        self._set_form_row_visible('text', text_type)
        self._set_form_row_visible('text_timing', text_type)
        self._set_form_row_visible('behavior', key)
        self._set_form_row_visible('duration', key or mouse)
        self._set_form_row_visible('direction', scroll)
        self._set_form_row_visible('quantity', scroll)
        self._set_form_row_visible('position', move)
        self._refresh_delay_suggestion(); self.updateGeometry()

    def _refresh_text_timing(self) -> None:
        text = self.text_edit.toPlainText()
        duration = calculate_text_duration(text)
        # O intervalo entre caracteres já é o mecanismo de cadência; o atraso
        # determinístico para a próxima ação inclui a janela ocupada pelo texto.
        self.text_timing_label.setText(
            f'Tempo calculado: {duration:.3f} s · atraso determinístico: {duration:.3f} s · '
            f'{len(text)} caractere(s) × {core.TEXT_CHAR_INTERVAL:.3f} s'
        )

    def _browse_app_executable(self):
        start = str(Path(self._command.target).parent) if self._command.target and Path(str(self._command.target)).exists() else str(Path.home())
        path, _ = QFileDialog.getOpenFileName(self, 'Selecionar executável do aplicativo', start, 'Executáveis (*.exe);;Todos os arquivos (*.*)')
        if not path:
            return
        path = str(Path(path).resolve())
        idx = self.target_combo.findData(path)
        if idx < 0:
            self.target_combo.addItem(f'{Path(path).stem} — {path}', path)
            idx = self.target_combo.findData(path)
        self.target_combo.setCurrentIndex(idx)
        # A sincronização deve acompanhar o executável escolhido.
        self.wait_process_edit.setCurrentText(Path(path).name)

    def _pick_position(self):
        picker=MousePositionPicker(self)
        if picker.exec()==QDialog.Accepted:
            # A posição já vem em coordenadas globais do Windows.
            # O sinal não é necessário aqui; recuperamos pela propriedade abaixo.
            # Como o diálogo foi aceito, guardamos a posição via atributo criado no mousePressEvent.
            self._move_pos=getattr(picker,'_selected_position',None)
            self._refresh_position_label()
    def _suggested_start(self) -> float:
        parent_map = getattr(self.parent(), '_automation_map', None)
        if not parent_map:
            return max(0.0, self.start.value())
        return parent_map.latest_end(exclude_ids={getattr(self._command, 'id', '')})

    def _refresh_delay_suggestion(self) -> None:
        """Atualiza a ajuda contextual sem alterar silenciosamente o tempo real."""
        if self._loading:
            return  # os campos estão sendo carregados: `_reload_from_command` calcula a sugestão ao final
        suggested = self._suggested_start()
        delay = self.delay.value()
        group_id = self.group_combo.currentData() or ''
        target = self.target_combo.currentText().strip().upper() if self.type_combo.currentData() == InputType.KEY else str(self.target_combo.currentData() or '')
        parent_map = getattr(self.parent(), '_automation_map', None)
        profile = None
        if parent_map and group_id in parent_map.groups:
            g = parent_map.groups[group_id]
            keys = [target, f'{target}|{self.description.text().strip()}', self.description.text().strip()]
            profile = next((g.delay_profiles[k] for k in keys if k and k in g.delay_profiles), None)
        if profile is not None:
            self.delay.setValue(float(profile))
            delay = float(profile)
        if self.type_combo.currentData() == InputType.TEXT:
            calculated = calculate_text_duration(self.text_edit.toPlainText())
            self.suggestion_label.setText(
                f'Início sugerido: {suggested:.2f} s. Tempo calculado: {calculated:.3f} s. '
                f'O próximo comando só poderá avançar após o texto ser entregue; o tempo real pode ser ligeiramente maior que a previsão.'
            )
        elif self.type_combo.currentData() == InputType.APP_OPEN:
            base = calculate_app_readiness_base(self._command)
            self.suggestion_label.setText(
                f'Início sugerido: {suggested:.2f} s. Atraso mínimo conhecido: {base:.3f} s. '
                'Além disso, a execução espera o processo aparecer e ficar estável; esse tempo variável não pode ser previsto antes de abrir o aplicativo.'
            )
        else:
            self.suggestion_label.setText(
                f'Início sugerido: {suggested:.2f} s. Atraso sugerido: {delay:.2f} s. '
                'O atraso é apenas uma referência visual e não muda o início real automaticamente.'
            )

    def _accept(self):
        t=self.type_combo.currentData()
        if t==InputType.KEY:
            if not self.target_combo.currentText().strip(): QMessageBox.warning(self,'Ação incompleta','Escolha uma tecla.'); return
            if self.action_combo.currentData()==ActionType.PRESS_AND_RELEASE and self.duration.value()<=0: QMessageBox.warning(self,'Tempo inválido','Defina um tempo maior que zero.'); return
        elif t==InputType.APP_OPEN:
            if not self.target_combo.currentData(): QMessageBox.warning(self,'Ação incompleta','Escolha um aplicativo.'); return
        elif t==InputType.MOUSE_BUTTON:
            if self.target_combo.currentData() is None: QMessageBox.warning(self,'Ação incompleta','Escolha o botão do mouse.'); return
            if self.duration.value()<=0: QMessageBox.warning(self,'Tempo inválido','Defina por quantos segundos o botão ficará pressionado.'); return
        elif t==InputType.TEXT:
            if not self.text_edit.toPlainText(): QMessageBox.warning(self,'Texto vazio','Digite o texto que será escrito.'); return
        elif t==InputType.WAIT:
            if not self._current_conditions(): QMessageBox.warning(self,'Espera incompleta','Adicione pelo menos uma condição antes de salvar.'); return
        elif t==InputType.MOUSE_MOVE and self._move_pos is None:
            QMessageBox.warning(self,'Posição não definida','Escolha a posição do mouse antes de adicionar a ação.'); return
        self.accept()
    def result_command(self):
        c=self._command; t=self.type_combo.currentData(); c.type=t; c.start=self.start.value(); c.delay=self.delay.value(); c.delay_suggested=self.delay.value(); c.description=self.description.text().strip()
        # O grupo pode ser um item que só o comando conhece (ver `_select_group`): então o nome vem do combo mesmo sem id.
        c.group_id=self.group_combo.currentData() or ''; c.group=self.group_combo.currentText() if (c.group_id or self.group_combo.currentIndex() > 0) else ''
        # `enabled` não é tocado: editar um comando desativado não pode reativá-lo (o comando novo já nasce ativado).
        c.wait_process=self._wait_process_value()
        c.wait_timeout=self.wait_timeout.value(); c.wait_min_ram_mb=0.0; c.wait_stable_ms=self.wait_stable.value(); c.wait_after_open=self.wait_after.value()
        c.conditions=self._current_conditions()
        if t==InputType.KEY:
            c.target=self.target_combo.currentText().strip().upper()
            c.action=self.action_combo.currentData(); c.duration=self.duration.value(); c.x=c.y=None; c.scroll_dx=c.scroll_dy=0
        elif t==InputType.APP_OPEN:
            c.target=self.target_combo.currentData() or ''; c.text=''; c.action=ActionType.PRESS_AND_RELEASE; c.duration=0; c.x=c.y=None; c.scroll_dx=c.scroll_dy=0
        elif t==InputType.MOUSE_BUTTON:
            c.target=self.target_combo.currentData(); c.action=ActionType.PRESS_AND_RELEASE; c.duration=self.duration.value(); c.x=c.y=None; c.scroll_dx=c.scroll_dy=0
        elif t==InputType.TEXT:
            c.target=''; c.text=self.text_edit.toPlainText(); c.action=ActionType.PRESS_AND_RELEASE
            c.duration=calculate_text_duration(c.text)
            # A duração calculada ocupa a própria faixa temporal do comando.
            # Não criamos um atraso adicional artificial: qualquer atraso
            # extra continua sendo o campo `Atraso sugerido` configurado pelo
            # usuário.
            c.delay_suggested=c.delay
            c.x=c.y=None; c.scroll_dx=c.scroll_dy=0
        elif t==InputType.WAIT:
            c.target=''; c.text=''; c.action=ActionType.PRESS_AND_RELEASE; c.duration=0; c.x=c.y=None; c.scroll_dx=c.scroll_dy=0
        elif t==InputType.MOUSE_MOVE:
            c.target=''; c.action=ActionType.PRESS_AND_RELEASE
            # Movimento mesclado (o que o gravador cria): a duração é o tempo do trajeto gravado e o editor não tem campo
            # para ela. Zerá-la faria o trajeto inteiro ser executado de uma vez só.
            if not (c.merged_move and c.mouse_path): c.duration=0
            c.x=self._move_pos.x(); c.y=self._move_pos.y(); c.relative=False; c.scroll_dx=c.scroll_dy=0
        else:
            direction=self.scroll_direction.currentData(); lines=self.scroll_lines.value(); c.target=direction; c.action=ActionType.PRESS_AND_RELEASE; c.duration=0; c.x=c.y=None; c.relative=False; c.scroll_dx=(-lines if direction=='left' else lines if direction=='right' else 0); c.scroll_dy=(lines if direction=='up' else -lines if direction=='down' else 0)
        return c

class HotkeySettingsDialog(QDialog):
    def __init__(self,current=None,parent=None):
        super().__init__(parent); self.setWindowTitle('Atalhos para controlar o programa'); current=current or {}
        self.pause=QLineEdit(current.get('pause','')); self.resume=QLineEdit(current.get('resume','')); self.emergency=QLineEdit(current.get('emergency',''))
        self.pause.setPlaceholderText('Ex.: F9'); self.resume.setPlaceholderText('Ex.: F10'); self.emergency.setPlaceholderText('Ex.: F12')
        b=QDialogButtonBox(QDialogButtonBox.Cancel|QDialogButtonBox.Ok); b.button(QDialogButtonBox.Ok).setText('Salvar'); b.button(QDialogButtonBox.Cancel).setText('Cancelar'); b.accepted.connect(self.accept); b.rejected.connect(self.reject)
        f=QFormLayout(); f.addRow('Pausar automação:',self.pause); f.addRow('Continuar automação:',self.resume); f.addRow('Parar tudo agora:',self.emergency)
        l=QVBoxLayout(self); l.addWidget(QLabel('<b>Esses atalhos funcionam mesmo com o programa minimizado.</b><br>Use uma tecla ou combinação como CTRL+F9.')); l.addLayout(f); l.addWidget(b)
    def values(self): return {k:v.text().strip() for k,v in [('pause',self.pause),('resume',self.resume),('emergency',self.emergency)] if v.text().strip()}

class RecorderSettingsDialog(QDialog):
    def __init__(self, current: RecorderFilters | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Filtros de gravação")
        current = current or RecorderFilters()

        self.keyboard_check = QCheckBox("Gravar teclado")
        self.keyboard_check.setChecked(current.capture_keyboard)

        self.mouse_buttons_check = QCheckBox("Gravar cliques do mouse")
        self.mouse_buttons_check.setChecked(current.capture_mouse_buttons)

        self.mouse_move_check = QCheckBox("Gravar movimento do mouse")
        self.mouse_move_check.setChecked(current.capture_mouse_move)

        self.mouse_scroll_check = QCheckBox("Gravar scroll")
        self.mouse_scroll_check.setChecked(current.capture_mouse_scroll)

        self.duration_check = QCheckBox("Gravar duração real (senão, zera tudo)")
        self.duration_check.setChecked(current.record_key_duration)

        self.ignored_keys_edit = QLineEdit(", ".join(sorted(current.ignored_keys)))
        self.ignored_keys_edit.setPlaceholderText("ex.: F8, F12 (separadas por vírgula)")

        self.ignored_mouse_edit = QLineEdit(", ".join(sorted(current.ignored_mouse_buttons)))
        self.ignored_mouse_edit.setPlaceholderText("ex.: middle (separados por vírgula)")

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        form = QFormLayout(self)
        form.addRow(self.keyboard_check)
        form.addRow(self.mouse_buttons_check)
        form.addRow(self.mouse_move_check)
        form.addRow(self.mouse_scroll_check)
        form.addRow(self.duration_check)
        form.addRow("Ignorar teclas:", self.ignored_keys_edit)
        form.addRow("Ignorar botões do mouse:", self.ignored_mouse_edit)
        form.addRow(buttons)

    @staticmethod
    def _parse_list(text: str) -> frozenset[str]:
        return frozenset(
            part.strip().upper() for part in text.split(",") if part.strip()
        )

    def filters(self) -> RecorderFilters:
        """Devolve um novo RecorderFilters com os valores escolhidos --
        pronto para MainWindow atribuir a Recorder.filters."""
        return RecorderFilters(
            capture_keyboard=self.keyboard_check.isChecked(),
            capture_mouse_buttons=self.mouse_buttons_check.isChecked(),
            capture_mouse_move=self.mouse_move_check.isChecked(),
            capture_mouse_scroll=self.mouse_scroll_check.isChecked(),
            record_key_duration=self.duration_check.isChecked(),
            ignored_keys=self._parse_list(self.ignored_keys_edit.text()),
            ignored_mouse_buttons=self._parse_list(self.ignored_mouse_edit.text()),
        )

class VisualSettingsDialog(QDialog):
    def __init__(self,current,parent=None):
        super().__init__(parent); self.setWindowTitle('Configurar teclado e mouse virtuais'); self.current=current
        self.mode=QComboBox(); self.mode.addItem('Somente teclas usadas (recomendado)','compact'); self.mode.addItem('Teclado completo','full'); self.mode.setCurrentIndex(max(0,self.mode.findData(current.get('keyboard_mode','compact'))))
        self.kt=self._spin(current.get('keyboard_timeout',3)); self.mt=self._spin(current.get('mouse_timeout',3)); self.ko=self._spin(current.get('keyboard_opacity',1),1); self.mo=self._spin(current.get('mouse_opacity',1),1)
        self.show_min=QCheckBox('Mostrar guia quando o programa estiver minimizado'); self.show_min.setChecked(current.get('show_on_minimize',True)); self.click=QCheckBox('Permitir clicar nas teclas do teclado completo'); self.click.setChecked(current.get('click_virtual_keyboard',True)); self.top=QCheckBox('Manter guia sobre outras janelas'); self.top.setChecked(current.get('always_on_top',True))
        f=QFormLayout(); f.addRow('Modo do teclado:',self.mode); f.addRow('Tempo visível após soltar:',self.kt); f.addRow('Tempo visível do mouse:',self.mt); f.addRow('Opacidade do teclado:',self.ko); f.addRow('Opacidade do mouse:',self.mo)
        b=QDialogButtonBox(QDialogButtonBox.Cancel|QDialogButtonBox.Ok); b.button(QDialogButtonBox.Ok).setText('Salvar'); b.button(QDialogButtonBox.Cancel).setText('Cancelar'); b.accepted.connect(self.accept); b.rejected.connect(self.reject)
        l=QVBoxLayout(self); l.addWidget(QLabel('<b>Guia visual</b><br>O modo compacto mostra apenas as teclas usadas recentemente, ocupando muito menos espaço.')); l.addLayout(f); l.addWidget(self.show_min); l.addWidget(self.click); l.addWidget(self.top); l.addWidget(b)
    def _spin(self,v,maxv=60):
        s=QDoubleSpinBox(); s.setRange(0.2 if maxv==60 else .05,maxv); s.setDecimals(1); s.setSingleStep(.5 if maxv==60 else .05); s.setValue(float(v)); return s
    def values(self):
        d=dict(self.current); d.update({'keyboard_mode':self.mode.currentData(),'keyboard_timeout':self.kt.value(),'mouse_timeout':self.mt.value(),'keyboard_opacity':self.ko.value(),'mouse_opacity':self.mo.value(),'show_on_minimize':self.show_min.isChecked(),'click_virtual_keyboard':self.click.isChecked(),'always_on_top':self.top.isChecked()}); return d

class ExecutionSettingsSidebar(QFrame):
    """Painel interno para tempos globais de execução; nunca abre uma janela externa."""
    saved = Signal()
    cancelled = Signal()
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main = main_window
        self.setObjectName("ExecutionSettingsSidebar")
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("#ExecutionSettingsSidebar { background: palette(window); border: 1px solid palette(mid); }")
        v = dict(main_window.visual_settings)
        self.text_interval=QDoubleSpinBox(); self.text_interval.setRange(0.001,0.5); self.text_interval.setDecimals(3); self.text_interval.setSingleStep(0.001); self.text_interval.setSuffix(' s'); self.text_interval.setValue(float(v.get('text_char_interval', core.TEXT_CHAR_INTERVAL)))
        self.app_stable=QSpinBox(); self.app_stable.setRange(0,10000); self.app_stable.setSingleStep(25); self.app_stable.setSuffix(' ms'); self.app_stable.setValue(int(v.get('app_stable_ms', core.APP_STABLE_DEFAULT_MS)))
        self.app_after=QDoubleSpinBox(); self.app_after.setRange(0,10); self.app_after.setDecimals(3); self.app_after.setSingleStep(.025); self.app_after.setSuffix(' s'); self.app_after.setValue(float(v.get('app_after_open', core.APP_AFTER_OPEN_DEFAULT)))
        title=QLabel("Configurações de execução")
        title.setStyleSheet("font-size:18px;font-weight:700;")
        info=QLabel("Ajuste os tempos globais usados pela automação. Intervalos menores deixam a digitação mais rápida; valores maiores dão mais margem para aplicativos lentos iniciarem. Essas opções não exigem configuração de RAM.")
        info.setWordWrap(True); info.setStyleSheet('color:#8f96a3;font-size:12px')
        form=QFormLayout(); form.addRow('Intervalo entre caracteres:',self.text_interval); form.addRow('Estabilidade do aplicativo:',self.app_stable); form.addRow('Atraso após aplicativo pronto:',self.app_after)
        self.status=QLabel('')
        self.status.setWordWrap(True); self.status.setStyleSheet('color:#8f96a3;font-size:12px')
        buttons=QHBoxLayout(); back=QPushButton('← Voltar às configurações'); save=QPushButton('Salvar')
        back.clicked.connect(self.cancelled.emit); save.clicked.connect(self._save); buttons.addWidget(back); buttons.addStretch(); buttons.addWidget(save)
        lay=QVBoxLayout(self); lay.setContentsMargins(12,12,12,12); lay.addWidget(title); lay.addWidget(info); lay.addSpacing(8); lay.addLayout(form); lay.addStretch(); lay.addWidget(self.status); lay.addLayout(buttons)
    def _save(self):
        visual=dict(self.main.visual_settings)
        visual.update({'text_char_interval':self.text_interval.value(),'app_stable_ms':self.app_stable.value(),'app_after_open':self.app_after.value()})
        core.set_runtime_defaults(visual['text_char_interval'], visual['app_stable_ms'], visual['app_after_open'])
        self.main.visual_settings=visual; self.main.settings.set_visual_settings(visual)
        self.status.setText('Configurações de execução salvas.')
        self.saved.emit()

class DragScrollArea(QScrollArea):
    """Rolagem com comportamento de superfície arrastável, sem setas.

    A rolagem horizontal pode ser feita com roda/Shift+roda e por arraste
    direto sobre áreas não interativas do conteúdo, aproximando-se do
    comportamento de uma faixa horizontal de navegador. Controles como
    botões, campos e combos continuam recebendo o clique normalmente.
    """
    def __init__(self, parent=None, horizontal_drag=True, vertical_scroll=False):
        super().__init__(parent)
        self._horizontal_drag = bool(horizontal_drag)
        self._vertical_scroll = bool(vertical_scroll)
        self._dragging = False
        self._drag_start = QPoint()
        self._drag_h = 0
        self._drag_v = 0
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded if vertical_scroll else Qt.ScrollBarAlwaysOff)
        self.setStyleSheet("""
            QScrollBar:horizontal { height: 6px; margin: 0; background: transparent; }
            QScrollBar:vertical { width: 6px; margin: 0; background: transparent; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal,
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                width: 0px; height: 0px; background: transparent; border: 0;
            }
            QScrollBar::handle:horizontal, QScrollBar::handle:vertical {
                border-radius: 4px; background: palette(mid); min-width: 42px; min-height: 42px;
            }
        """)
        self._update_cursor()

    def _update_cursor(self):
        overflow = self.horizontalScrollBar().maximum() > 0
        self.viewport().setCursor(Qt.OpenHandCursor if self._horizontal_drag and overflow else Qt.ArrowCursor)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._update_cursor)

    def _interactive_ancestor(self, widget):
        interactive = (QAbstractButton, QLineEdit, QTextEdit, QPlainTextEdit,
                       QComboBox, QSpinBox, QDoubleSpinBox, QSlider, QCheckBox)
        while widget is not None and widget is not self.viewport():
            if isinstance(widget, interactive):
                return True
            widget = widget.parentWidget()
        return False

    def wheelEvent(self, event):
        hdelta = event.angleDelta().x()
        vdelta = event.angleDelta().y()
        hbar = self.horizontalScrollBar(); vbar = self.verticalScrollBar()
        if hbar.maximum() > 0 and ((event.modifiers() & Qt.ShiftModifier) or vbar.maximum() == 0):
            delta = hdelta or vdelta
            if delta:
                hbar.setValue(hbar.value() - delta)
                event.accept(); return
        if vbar.maximum() > 0 and vdelta:
            vbar.setValue(vbar.value() - vdelta)
            event.accept(); return
        super().wheelEvent(event)

    def mousePressEvent(self, event):
        if self._horizontal_drag and event.button() == Qt.LeftButton and self.horizontalScrollBar().maximum() > 0:
            child = self.childAt(event.position().toPoint())
            if not self._interactive_ancestor(child):
                self._dragging = True
                self._drag_start = event.position().toPoint()
                self._drag_h = self.horizontalScrollBar().value()
                self._drag_v = self.verticalScrollBar().value()
                self.viewport().setCursor(Qt.ClosedHandCursor)
                event.accept(); return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging:
            delta = event.position().toPoint() - self._drag_start
            self.horizontalScrollBar().setValue(self._drag_h - delta.x())
            if self._vertical_scroll and self.verticalScrollBar().maximum() > 0:
                self.verticalScrollBar().setValue(self._drag_v - delta.y())
            event.accept(); return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._dragging and event.button() == Qt.LeftButton:
            self._dragging = False
            self._update_cursor()
            event.accept(); return
        super().mouseReleaseEvent(event)


class ScrollableTabWidget(QWidget):
    """Abas horizontais sem setas: rolagem/arraste no cabeçalho, conteúdo abaixo."""
    currentChanged = Signal(int)
    def __init__(self, parent=None):
        super().__init__(parent)
        self._stack = QStackedWidget()
        self._bar_scroll = DragScrollArea(horizontal_drag=True)
        self._bar_scroll.setFixedHeight(36)
        self._bar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._bar_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._bar = QWidget()
        self._bar_layout = QHBoxLayout(self._bar)
        self._bar_layout.setContentsMargins(0,0,0,0); self._bar_layout.setSpacing(1)
        self._bar_scroll.setWidget(self._bar); self._bar_scroll.setWidgetResizable(False)
        self._bar_scroll.setToolTip("Arraste o cabeçalho horizontalmente para acessar as outras guias.")
        lay=QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)
        lay.addWidget(self._bar_scroll); lay.addWidget(self._stack,1)

    def addTab(self, widget, label):
        index=self._stack.addWidget(widget)
        b=QPushButton(label); b.setCheckable(True); b.setAutoExclusive(True); b.setMinimumHeight(32); b.setSizePolicy(QSizePolicy.Fixed,QSizePolicy.Fixed)
        b.setStyleSheet("QPushButton { padding: 6px 14px; background: transparent; border: 0; border-radius: 0; border-bottom: 2px solid transparent; } QPushButton:checked { border-bottom: 2px solid palette(highlight); font-weight: 600; }")
        b.clicked.connect(lambda checked=False, i=index: self.setCurrentIndex(i))
        self._bar_layout.addWidget(b); self._bar_layout.invalidate(); self._bar.adjustSize()
        if index == 0: self.setCurrentIndex(0)
        return index

    def setCurrentIndex(self,index):
        if 0 <= index < self._stack.count():
            self._stack.setCurrentIndex(index)
            for i in range(self._bar_layout.count()):
                w=self._bar_layout.itemAt(i).widget()
                if w: w.setChecked(i == index)
            self.currentChanged.emit(index)

    def currentIndex(self): return self._stack.currentIndex()

class AppSettingsDialog(QDialog):
    """Central de configurações; também pode ser hospedada como painel lateral."""
    saved = Signal()
    cancelled = Signal()
    execution_requested = Signal()
    def __init__(self, main_window, parent=None, embedded=False):
        super().__init__(parent)
        self.embedded = bool(embedded)
        self.main = main_window
        self.setWindowTitle("Configurações")
        if self.embedded:
            self.setMinimumSize(0, 0)
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        else:
            self.resize(620, 480)
        tabs = ScrollableTabWidget()

        # Aparência — as cores do programa e dos guias virtuais ficam juntas,
        # organizadas pelo tema ativo. Isso evita repetir "modo claro/escuro"
        # em cada campo e deixa claro que a aparência é uma configuração única.
        visual = QWidget()
        v = dict(main_window.visual_settings)
        vbox = QVBoxLayout(visual); vbox.setContentsMargins(8,8,8,8); vbox.setSpacing(8)

        self.theme_mode = QComboBox()
        self.theme_mode.addItem("Seguir o Windows (recomendado)", "system")
        self.theme_mode.addItem("Claro", "light")
        self.theme_mode.addItem("Escuro", "dark")
        self.theme_mode.setCurrentIndex(max(0, self.theme_mode.findData(v.get("theme_mode","system"))))

        self.accent_dark = QLineEdit(v.get("accent_dark","#FFC53D"))
        self.accent_light = QLineEdit(v.get("accent_light","#2F6FED"))
        self.light_surface = QLineEdit(v.get("light_surface","#FFFFFF"))
        self.light_contrast = QLineEdit(v.get("light_contrast","#2F343B"))
        self.virtual_surface_dark = QLineEdit(v.get("virtual_surface_dark","#4A4F57"))
        self.virtual_surface_light = QLineEdit(v.get("virtual_surface_light","#5A6068"))
        self.virtual_text_dark = QLineEdit(v.get("virtual_text_dark","#FFC53D"))
        self.virtual_text_light = QLineEdit(v.get("virtual_text_light","#FFC53D"))
        self.virtual_accent = QLineEdit(v.get("virtual_accent","#FFC53D"))
        for w in (self.accent_dark,self.accent_light,self.light_surface,self.light_contrast,self.virtual_surface_dark,self.virtual_surface_light,self.virtual_text_dark,self.virtual_text_light,self.virtual_accent):
            w.setPlaceholderText("#RRGGBB")

        def group(title, tip=None):
            box=QGroupBox(title)
            if tip: box.setToolTip(tip)
            box.setLayout(QVBoxLayout())
            box.layout().setContentsMargins(10,10,10,10); box.layout().setSpacing(6)
            return box, box.layout()

        def row(layout, label, widget, tip):
            r=QHBoxLayout(); r.setContentsMargins(0,0,0,0); r.setSpacing(8)
            lab=QLabel(label); lab.setMinimumWidth(150); lab.setWordWrap(True); lab.setToolTip(tip)
            widget.setToolTip(tip)
            r.addWidget(lab, 0); r.addWidget(widget, 1); layout.addLayout(r)

        # O tema é geral; abaixo dele, todas as cores ficam agrupadas por
        # aparência, incluindo o programa e teclado/mouse virtuais.
        theme_box, theme_layout = group("Tema", "Define se a aparência acompanha o Windows ou usa sempre o modo claro/escuro.")
        row(theme_layout, "Tema:", self.theme_mode, "Escolhe se o Automation Studio acompanha o Windows ou usa sempre o modo claro/escuro.")
        vbox.addWidget(theme_box)

        dark_box, dark_layout = group("Modo escuro", "Cores usadas quando o Automation Studio está no modo escuro. O grupo inclui a interface e os guias virtuais para manter a aparência coerente.")
        row(dark_layout, "Destaque:", self.accent_dark, "Cor principal usada para seleções, destaques e elementos de interação no modo escuro.")
        row(dark_layout, "Fundo das teclas e mouse:", self.virtual_surface_dark, "Fundo dos guias de teclado e mouse virtuais no modo escuro.")
        row(dark_layout, "Texto e símbolos das teclas:", self.virtual_text_dark, "Cor dos textos e símbolos dos guias virtuais no modo escuro.")
        vbox.addWidget(dark_box)

        light_box, light_layout = group("Modo claro", "Cores usadas quando o Automation Studio está no modo claro. O grupo inclui a interface e os guias virtuais para manter a aparência coerente.")
        row(light_layout, "Destaque:", self.accent_light, "Cor principal usada para seleções, destaques e elementos de interação no modo claro.")
        row(light_layout, "Fundo da interface:", self.light_surface, "Cor de fundo principal da interface no modo claro.")
        row(light_layout, "Texto e contraste:", self.light_contrast, "Cor base dos textos e do contraste da interface no modo claro.")
        row(light_layout, "Fundo das teclas e mouse:", self.virtual_surface_light, "Fundo dos guias de teclado e mouse virtuais no modo claro.")
        row(light_layout, "Texto e símbolos das teclas:", self.virtual_text_light, "Cor dos textos e símbolos dos guias virtuais no modo claro.")
        vbox.addWidget(light_box)

        shared_box, shared_layout = group("Guias virtuais", "Configuração compartilhada pelos guias de teclado e mouse, independentemente do tema.")
        row(shared_layout, "Destaque dos guias:", self.virtual_accent, "Cor das bordas e dos estados de destaque dos guias virtuais.")
        vbox.addWidget(shared_box)
        vbox.addStretch(1)
        tabs.addTab(visual,"Aparência")

        # Teclado e mouse virtuais — somente comportamento e exibição.
        # As cores permanecem na aba Aparência, agrupadas por tema.
        self.mode = QComboBox(); self.mode.addItem("Somente teclas usadas (compacto)", "compact"); self.mode.addItem("Teclado completo", "full")
        self.mode.setCurrentIndex(max(0,self.mode.findData(v.get("keyboard_mode","compact"))))
        self.kt = QDoubleSpinBox(); self.kt.setRange(.2,60); self.kt.setValue(float(v.get("keyboard_timeout",3)))
        self.mt = QDoubleSpinBox(); self.mt.setRange(.2,60); self.mt.setValue(float(v.get("mouse_timeout",3)))
        self.ko = QDoubleSpinBox(); self.ko.setRange(.05,1); self.ko.setSingleStep(.05); self.ko.setValue(float(v.get("keyboard_opacity",1)))
        self.mo = QDoubleSpinBox(); self.mo.setRange(.05,1); self.mo.setSingleStep(.05); self.mo.setValue(float(v.get("mouse_opacity",1)))
        self.show_min = QCheckBox("Mostrar automaticamente ao minimizar"); self.show_min.setChecked(v.get("show_on_minimize",True))
        self.show_keyboard = QCheckBox("Mostrar teclado virtual ao abrir o programa"); self.show_keyboard.setChecked(v.get("show_keyboard",False))
        self.show_mouse = QCheckBox("Mostrar mouse virtual ao abrir o programa"); self.show_mouse.setChecked(v.get("show_mouse",False))
        self.click = QCheckBox("Permitir clicar nas teclas do teclado completo"); self.click.setChecked(v.get("click_virtual_keyboard",True))
        self.top = QCheckBox("Manter teclado e mouse acima de outras janelas"); self.top.setChecked(v.get("always_on_top",True))
        virtual = QWidget()
        virtual_layout = QVBoxLayout(virtual); virtual_layout.setContentsMargins(8,8,8,8); virtual_layout.setSpacing(8)

        behavior_box, behavior_layout = group("Exibição", "Controla como os guias virtuais aparecem e por quanto tempo permanecem visíveis.")
        row(behavior_layout, "Modo do teclado:", self.mode, "Define se o teclado virtual mostra somente as teclas usadas ou o teclado completo.")
        row(behavior_layout, "Tempo da última tecla visível:", self.kt, "Tempo que a última tecla permanece destacada no guia do teclado.")
        row(behavior_layout, "Tempo do mouse visível:", self.mt, "Tempo que o último evento do mouse permanece visível.")
        row(behavior_layout, "Opacidade do teclado:", self.ko, "Opacidade do guia visual do teclado.")
        row(behavior_layout, "Opacidade do mouse:", self.mo, "Opacidade do guia visual do mouse.")
        virtual_layout.addWidget(behavior_box)

        behavior2_box, behavior2_layout = group("Comportamento", "Define quando os guias virtuais aparecem e como permanecem sobre outras janelas.")
        for check in (self.show_min,self.show_keyboard,self.show_mouse,self.click,self.top):
            behavior2_layout.addWidget(check)
        virtual_layout.addWidget(behavior2_box)
        virtual_layout.addStretch(1)
        tabs.addTab(virtual,"Teclado e mouse virtuais")

        # Gravação
        rec = QWidget(); rf=QFormLayout(rec); f=main_window.recorder.filters
        self.rk=QCheckBox("Gravar teclado"); self.rk.setChecked(f.capture_keyboard)
        self.rb=QCheckBox("Gravar cliques do mouse"); self.rb.setChecked(f.capture_mouse_buttons)
        self.rm=QCheckBox("Gravar movimentos do mouse"); self.rm.setChecked(f.capture_mouse_move)
        self.rs=QCheckBox("Gravar scroll do mouse"); self.rs.setChecked(f.capture_mouse_scroll)
        self.rd=QCheckBox("Gravar duração real das teclas e botões"); self.rd.setChecked(f.record_key_duration)
        self.rmerge=QCheckBox("Mesclar movimentos contínuos do mouse em um único bloco"); self.rmerge.setToolTip("Reduz o número de comandos gerados sem eliminar trajetórias reais."); self.rmerge.setChecked(getattr(f, "merge_mouse_moves", True))
        self.rj=QSpinBox(); self.rj.setRange(0,30); self.rj.setSuffix(" px"); self.rj.setValue(int(getattr(f, "mouse_jitter_px", 3)))
        self.rsamp=QSpinBox(); self.rsamp.setRange(1,100); self.rsamp.setSuffix(" ms"); self.rsamp.setValue(int(getattr(f, "mouse_sample_interval_ms", 8)))
        self.ik=QLineEdit(", ".join(sorted(f.ignored_keys))); self.im=QLineEdit(", ".join(sorted(f.ignored_mouse_buttons)))
        self.ik.setPlaceholderText("Ex.: F8, F12"); self.im.setPlaceholderText("Ex.: x1, x2")
        rf.addRow(self.rk); rf.addRow(self.rb); rf.addRow(self.rm); rf.addRow(self.rs); rf.addRow(self.rd); rf.addRow(self.rmerge)
        self.rj.setToolTip("Movimentos menores que esta distância podem ser tratados como tremor e ignorados."); self.rsamp.setToolTip("Intervalo mínimo entre amostras do movimento do mouse."); rf.addRow("Ignorar tremores menores que:",self.rj); rf.addRow("Amostragem mínima do mouse:",self.rsamp)
        rf.addRow("Teclas ignoradas:",self.ik); rf.addRow("Botões do mouse ignorados:",self.im)
        tabs.addTab(rec,"Gravação")

        # Mapas
        maps=QWidget(); mf=QFormLayout(maps)
        mf.setRowWrapPolicy(QFormLayout.WrapLongRows)
        mf.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.maps_path=QLineEdit(str(main_window.project_manager.project_dir))
        self.maps_path.setMinimumWidth(0)
        browse=QPushButton("Escolher pasta…"); browse.clicked.connect(self._browse_maps)
        browse.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        row=QHBoxLayout(); row.setContentsMargins(0,0,0,0); row.setSpacing(6); row.addWidget(self.maps_path,1); row.addWidget(browse,0)
        self.maps_path.setToolTip("As automações salvas nesta pasta são carregadas automaticamente pelo programa.")
        mf.addRow("Pasta onde salvar e procurar automações:",row)
        tabs.addTab(maps,"Mapas")

        # Controles
        ctrl=QWidget(); cf=QFormLayout(ctrl); c=main_window.settings.get_control_hotkeys()
        self.pause=QLineEdit(c.get("pause","F9")); self.resume=QLineEdit(c.get("resume","F10")); self.emergency=QLineEdit(c.get("emergency","F12"))
        self.record_toggle=QLineEdit(c.get("record_toggle","F8")); self.record_cancel=QLineEdit(c.get("record_cancel","F11"))
        self.undo_ram=QSpinBox(); self.undo_ram.setRange(MapHistory.MIN_RAM_MB, MapHistory.MAX_RAM_MB); self.undo_ram.setSingleStep(16); self.undo_ram.setSuffix(" MB"); self.undo_ram.setValue(int(main_window.settings.get_visual_settings().get("undo_ram_mb",256)))
        self.pause.setPlaceholderText("Ex.: F9"); self.resume.setPlaceholderText("Ex.: F10"); self.emergency.setPlaceholderText("Ex.: F12")
        self.record_toggle.setPlaceholderText("Ex.: F8"); self.record_cancel.setPlaceholderText("Ex.: F11")
        cf.addRow("Tecla para pausar execução:",self.pause); cf.addRow("Tecla para continuar execução:",self.resume); cf.addRow("Tecla para parar tudo:",self.emergency)
        cf.addRow("Tecla para iniciar/finalizar gravação:",self.record_toggle); cf.addRow("Tecla para cancelar gravação:",self.record_cancel)
        self.undo_ram.setToolTip("Limite aproximado de memória reservado ao histórico de Undo/Redo."); cf.addRow("Memória RAM para Undo/Redo:",self.undo_ram)
        tabs.addTab(ctrl,"Controles")

        # Execução: os tempos globais ficam como uma aba própria das configurações.
        # Assim o usuário consegue voltar às demais opções sem abrir popup ou
        # outra janela e os valores permanecem acessíveis mesmo em telas estreitas.
        execution = QWidget(); exf = QFormLayout(execution)
        exf.setContentsMargins(12,12,12,12)
        exec_title=QLabel("<b>Tempos globais de execução</b>"); exec_title.setToolTip("Controla a cadência da digitação e a sincronização após abrir aplicativos."); exf.addRow(exec_title)
        v = dict(main_window.visual_settings)
        self.text_interval=QDoubleSpinBox(); self.text_interval.setRange(0.001,0.5); self.text_interval.setDecimals(3); self.text_interval.setSingleStep(0.001); self.text_interval.setSuffix(" s"); self.text_interval.setValue(float(v.get("text_char_interval", core.TEXT_CHAR_INTERVAL)))
        self.app_stable=QSpinBox(); self.app_stable.setRange(0,10000); self.app_stable.setSingleStep(25); self.app_stable.setSuffix(" ms"); self.app_stable.setValue(int(v.get("app_stable_ms", core.APP_STABLE_DEFAULT_MS)))
        self.app_after=QDoubleSpinBox(); self.app_after.setRange(0,10); self.app_after.setDecimals(3); self.app_after.setSingleStep(.025); self.app_after.setSuffix(" s"); self.app_after.setValue(float(v.get("app_after_open", core.APP_AFTER_OPEN_DEFAULT)))
        self.app_wait_timeout=QDoubleSpinBox(); self.app_wait_timeout.setRange(0,3600); self.app_wait_timeout.setDecimals(1); self.app_wait_timeout.setSingleStep(1.0); self.app_wait_timeout.setSuffix(" s"); self.app_wait_timeout.setValue(float(v.get("app_wait_timeout",0.0) or 0.0))
        self.app_learning=QCheckBox("Aprender o tempo de inicialização de cada aplicativo"); self.app_learning.setChecked(bool(v.get("app_adaptive_learning",True)))
        exf.addRow("Intervalo entre caracteres:", self.text_interval)
        exf.addRow("Estabilidade do aplicativo:", self.app_stable)
        exf.addRow("Atraso após aplicativo pronto:", self.app_after)
        exf.addRow("Tempo máximo de espera (0 = sem limite):", self.app_wait_timeout)
        exf.addRow(self.app_learning)
        help_exec="Após abrir um aplicativo, a automação aguarda o processo aparecer, permanecer estável pelo tempo definido e então espera o atraso adicional. O intervalo de caracteres é aplicado entre teclas de texto."
        self.text_interval.setToolTip("" + "Intervalo aplicado entre caracteres durante a digitação. " + "O tempo total do texto é calculado automaticamente pela quantidade de caracteres.")
        self.app_stable.setToolTip("Tempo durante o qual o aplicativo deve permanecer pronto/estável antes de liberar o próximo comando.")
        self.app_after.setToolTip("Atraso de segurança aplicado depois que o aplicativo é considerado pronto.")
        self.app_wait_timeout.setToolTip("Tempo máximo de espera pelo aplicativo. Zero significa sem limite.")
        self.app_learning.setToolTip(help_exec + " O aprendizado adapta a espera futura ao histórico do aplicativo.")
        tabs.addTab(execution,"Execução")

        # Formulários se reorganizam verticalmente quando a sidebar fica estreita.
        # O rótulo nunca fica sobre o campo: quando não houver espaço, o campo
        # é empurrado para a linha de baixo e as linhas seguintes acompanham.
        for _form in (mf, rf, cf, exf):
            _form.setRowWrapPolicy(QFormLayout.WrapLongRows)
            _form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        # Campos de configuração seguem a mesma métrica visual da sidebar de comandos.
        _settings_fields = (self.theme_mode,self.accent_dark,self.accent_light,self.light_surface,self.light_contrast,
                            self.virtual_surface_dark,self.virtual_surface_light,self.virtual_text_dark,self.virtual_text_light,self.virtual_accent,
                            self.mode,self.kt,self.mt,self.ko,self.mo,self.rj,self.rsamp,self.ik,self.im,self.pause,self.resume,self.emergency,
                            self.record_toggle,self.record_cancel,self.undo_ram,self.maps_path,self.text_interval,self.app_stable,self.app_after,
                            self.app_wait_timeout)
        for _field in _settings_fields:
            _field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            _field.setMinimumWidth(0); _field.setMaximumWidth(380)
            if isinstance(_field, QComboBox): _field.setMinimumHeight(32)
            elif isinstance(_field, (QLineEdit,QSpinBox,QDoubleSpinBox)): _field.setMinimumHeight(30)

        buttons=QDialogButtonBox(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)
        self.buttons = buttons
        buttons.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        buttons.setMinimumHeight(38)
        buttons.button(QDialogButtonBox.Ok).setText("Salvar configurações"); buttons.button(QDialogButtonBox.Cancel).setText("Cancelar")
        if self.embedded:
            buttons.accepted.connect(self._embedded_save); buttons.rejected.connect(self._embedded_cancel)
        else:
            buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        lay=QVBoxLayout(self); lay.setContentsMargins(8,8,8,8); settings_title=QLabel("Configurações do Automation Studio"); settings_title.setStyleSheet("font-size:16px;font-weight:700;"); settings_title.setToolTip("As opções estão separadas por função para manter a interface compacta. Passe o mouse sobre os rótulos para ver explicações sem ocupar espaço permanente."); lay.addWidget(settings_title); lay.addWidget(tabs,1); lay.addWidget(buttons)


        self._color_fields = (self.accent_dark,self.accent_light,self.light_surface,self.light_contrast,
                              self.virtual_surface_dark,self.virtual_surface_light,self.virtual_text_dark,
                              self.virtual_text_light,self.virtual_accent)
        for field in self._color_fields:
            field.textChanged.connect(lambda _=None, w=field: self._update_color_field(w))
            field.installEventFilter(self)
            field.setCursor(Qt.PointingHandCursor)
            self._update_color_field(field)
        # O tema é pré-visualizado imediatamente ao trocar a opção.
        # O valor só é persistido quando o usuário salva; cancelar restaura
        # integralmente o tema que estava ativo antes de abrir a sidebar.
        self.theme_mode.currentIndexChanged.connect(self._preview_theme)
        for field in (self.accent_dark,self.accent_light,self.light_surface,self.light_contrast,
                      self.virtual_surface_dark,self.virtual_surface_light,self.virtual_text_dark,
                      self.virtual_text_light,self.virtual_accent):
            field.textChanged.connect(lambda _=None: self._preview_theme())

    def eventFilter(self, obj, event):
        # Campos de cor funcionam como controles visuais: um clique abre a
        # paleta nativa do Windows/Qt, sem exigir que o usuário conheça o
        # formato hexadecimal. O código continua editável por teclado.
        if obj in getattr(self, "_color_fields", ()) and event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            current = QColor(obj.text().strip())
            if not current.isValid():
                current = QColor("#FFC53D")
            chosen = QColorDialog.getColor(current, self, "Escolher cor", QColorDialog.ShowAlphaChannel)
            if chosen.isValid():
                obj.setText(chosen.name(QColor.HexRgb).upper())
            return True
        return super().eventFilter(obj, event)

    def _preview_theme(self, _index=0) -> None:
        try:
            visual = dict(self.main.visual_settings)
            visual["theme_mode"] = self.theme_mode.currentData() or "system"
            # As cores de destaque digitadas na sidebar também participam da
            # pré-visualização, sem gravar nada ainda.
            visual["accent_dark"] = self.accent_dark.text().strip() or "#FFC53D"
            visual["accent_light"] = self.accent_light.text().strip() or "#2F6FED"
            visual["virtual_surface_dark"] = self.virtual_surface_dark.text().strip() or "#4A4F57"
            visual["virtual_surface_light"] = self.virtual_surface_light.text().strip() or "#5A6068"
            visual["virtual_text_dark"] = self.virtual_text_dark.text().strip() or "#FFC53D"
            visual["virtual_text_light"] = self.virtual_text_light.text().strip() or "#FFC53D"
            visual["virtual_accent"] = self.virtual_accent.text().strip() or "#FFC53D"
            self.main._apply_visual_settings(visual)
            QApplication.processEvents()
        except Exception:
            pass

    def _update_color_field(self, field: QLineEdit) -> None:
        c = QColor(field.text().strip())
        if c.isValid():
            # O próprio campo funciona como amostra: o código continua legível
            # e recebe um fundo suave derivado da cor informada.
            luminance = (0.299*c.red() + 0.587*c.green() + 0.114*c.blue()) / 255.0
            fg = '#111111' if luminance > 0.62 else '#FFFFFF'
            field.setStyleSheet(f"QLineEdit {{ color: {fg}; background: {c.name()}; font-weight: 700; border: 1px solid palette(mid); border-radius: 4px; padding: 4px 6px; }}")
        else:
            field.setStyleSheet('')

    def _embedded_save(self) -> None:
        try:
            self.apply()
            self.saved.emit()
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao salvar", str(exc))

    def _embedded_cancel(self) -> None:
        # A pré-visualização de tema não é persistente. Ao cancelar,
        # restauramos imediatamente as configurações salvas.
        try:
            self.main._apply_visual_settings()
        except Exception:
            pass
        self.cancelled.emit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        narrow = self.width() < 430
        policy = QFormLayout.WrapAllRows if narrow else QFormLayout.WrapLongRows
        for form in self.findChildren(QFormLayout):
            form.setRowWrapPolicy(policy)

    def _browse_maps(self):
        folder=QFileDialog.getExistingDirectory(self,"Escolher pasta das automações",self.maps_path.text())
        if folder:self.maps_path.setText(folder)

    @staticmethod
    def _set_parts(text):
        return frozenset(x.strip().upper() for x in text.split(",") if x.strip())

    def apply(self):
        main=self.main
        visual=dict(main.visual_settings)
        visual.update({
            "keyboard_mode":self.mode.currentData(),"keyboard_timeout":self.kt.value(),"mouse_timeout":self.mt.value(),
            "keyboard_opacity":self.ko.value(),"mouse_opacity":self.mo.value(),
            "show_on_minimize":self.show_min.isChecked(),"show_keyboard":self.show_keyboard.isChecked(),"show_mouse":self.show_mouse.isChecked(),"click_virtual_keyboard":self.click.isChecked(),
            "always_on_top":self.top.isChecked(),
            "theme_mode":self.theme_mode.currentData(),
            "accent_dark":self.accent_dark.text().strip() or "#FFC53D",
            "accent_light":self.accent_light.text().strip() or "#2F6FED",
            "light_surface":self.light_surface.text().strip() or "#FFFFFF",
            "light_contrast":self.light_contrast.text().strip() or "#2F343B",
            "virtual_surface_dark":self.virtual_surface_dark.text().strip() or "#4A4F57",
            "virtual_surface_light":self.virtual_surface_light.text().strip() or "#5A6068",
            "virtual_text_dark":self.virtual_text_dark.text().strip() or "#FFC53D",
            "virtual_text_light":self.virtual_text_light.text().strip() or "#FFC53D",
            "virtual_accent":self.virtual_accent.text().strip() or "#FFC53D",
            "text_char_interval":self.text_interval.value(), "app_stable_ms":self.app_stable.value(), "app_after_open":self.app_after.value(), "app_wait_timeout":self.app_wait_timeout.value(), "app_adaptive_learning":self.app_learning.isChecked()
        })
        core.set_runtime_defaults(visual.get("text_char_interval"), visual.get("app_stable_ms"), visual.get("app_after_open"))
        main.visual_settings=visual; main.settings.set_visual_settings(visual); main.engine.configure_readiness(history=visual.get("app_readiness_history", {}), default_timeout=float(visual.get("app_wait_timeout", 0.0) or 0.0), adaptive_learning=bool(visual.get("app_adaptive_learning", True)), save_callback=main._save_readiness_history); main._apply_visual_settings()
        main.btn_toggle_keyboard.setChecked(self.show_keyboard.isChecked())
        main.btn_toggle_mouse.setChecked(self.show_mouse.isChecked())
        filters=RecorderFilters(
            capture_keyboard=self.rk.isChecked(), capture_mouse_buttons=self.rb.isChecked(),
            capture_mouse_move=self.rm.isChecked(), capture_mouse_scroll=self.rs.isChecked(),
            record_key_duration=self.rd.isChecked(), merge_mouse_moves=self.rmerge.isChecked(),
            mouse_jitter_px=self.rj.value(), mouse_sample_interval_ms=self.rsamp.value(),
            ignored_keys=self._set_parts(self.ik.text()), ignored_mouse_buttons=self._set_parts(self.im.text())
        )
        main.recorder.filters=filters
        main.settings.set_recording_settings({
            "capture_keyboard":filters.capture_keyboard,"capture_mouse_buttons":filters.capture_mouse_buttons,
            "capture_mouse_move":filters.capture_mouse_move,"capture_mouse_scroll":filters.capture_mouse_scroll,
            "record_key_duration":filters.record_key_duration,"merge_mouse_moves":filters.merge_mouse_moves,
            "mouse_jitter_px":filters.mouse_jitter_px,"mouse_sample_interval_ms":filters.mouse_sample_interval_ms,
            "ignored_keys":sorted(filters.ignored_keys),
            "ignored_mouse_buttons":sorted(filters.ignored_mouse_buttons)
        })
        folder=Path(self.maps_path.text()).expanduser()
        if not folder.is_absolute(): folder=Path(main._default_maps_folder)/folder
        folder.mkdir(parents=True,exist_ok=True)
        if folder.resolve()!=main.project_manager.project_dir.resolve():
            main.project_manager=ProjectManager(folder)
            main.settings=AppSettings(folder)
            main.settings.set_maps_folder(folder)
            _set_registered_data_dir(folder)
            main._default_maps_folder=folder
            main._reload_map_list()
            main._current_map=None
        main.settings.set_control_hotkeys({k:v for k,v in [
            ("pause",self.pause.text().strip()),("resume",self.resume.text().strip()),("emergency",self.emergency.text().strip()),
            ("record_toggle",self.record_toggle.text().strip()),("record_cancel",self.record_cancel.text().strip())
        ] if v})
        main._register_all_hotkeys()
        visual["undo_ram_mb"] = self.undo_ram.value()
        main.settings.set_visual_settings(visual)
        main.history.set_ram_mb(self.undo_ram.value())
        main._update_history_actions()

class ExcelLikeDelegate(QStyledItemDelegate):
    """Edição protegida: Enter abre a célula; Enter/Tab dentro do editor confirma e navega."""
    navigation = Signal(str)
    def createEditor(self, parent, option, index):
        editor=super().createEditor(parent, option, index)
        editor.installEventFilter(self)
        return editor
    def eventFilter(self, obj, event):
        if event.type()==QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self.commitData.emit(obj); self.closeEditor.emit(obj, QStyledItemDelegate.NoHint)
                self.navigation.emit("enter")
                return True
            if event.key()==Qt.Key_Tab:
                self.commitData.emit(obj); self.closeEditor.emit(obj, QStyledItemDelegate.NoHint)
                self.navigation.emit("tab")
                return True
        return super().eventFilter(obj,event)

class CommandSelectionDelegate(ExcelLikeDelegate):
    """Desenha a seleção do editor somente como contorno da linha.

    A seleção lógica continua pertencendo ao QItemSelectionModel, mas a
    aparência da seleção não usa o destaque nativo do Qt. Isso evita que o
    tema do Windows/Fusion pinte toda a linha de azul e garante que o conteúdo
    permaneça legível.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._selection_color = QColor("#2F6FED")
        self._drag_color = QColor("#3A78D6")

    def set_drag_color(self, color: str) -> None:
        self._drag_color = _normalized_color(color)
        if self.parent():
            self.parent().viewport().update()

    def set_selection_color(self, color: str) -> None:
        self._selection_color = _normalized_color(color)
        if self.parent():
            self.parent().viewport().update()

    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        opt.state &= ~QStyle.State_Selected
        pal = opt.palette
        normal_fg = pal.brush(QPalette.Active, QPalette.Text)
        pal.setBrush(QPalette.Active, QPalette.Highlight, QBrush(Qt.NoBrush))
        pal.setBrush(QPalette.Inactive, QPalette.Highlight, QBrush(Qt.NoBrush))
        pal.setBrush(QPalette.Active, QPalette.HighlightedText, normal_fg)
        pal.setBrush(QPalette.Inactive, QPalette.HighlightedText, normal_fg)
        opt.palette = pal
        opt.backgroundBrush = QBrush(Qt.NoBrush)

        table = self.parent() if isinstance(self.parent(), QTableWidget) else None
        host = table.parentWidget() if table is not None else None
        dragging = False
        if table is not None and host is not None and getattr(host, '_row_reorder_dragging', False):
            try:
                ids = getattr(host, '_row_reorder_ids', set()) or set()
                # Durante a reordenação, a tabela pode estar em uma ordem
                # visual diferente da ordem atual do modelo. A identidade da
                # linha precisa vir da própria célula (#), que acompanha o
                # item quando fazemos as trocas visuais.
                item = table.item(index.row(), 0)
                item_id = item.data(Qt.UserRole) if item is not None else None
                if item_id is not None:
                    dragging = item_id in ids
            except Exception:
                dragging = False

        if dragging:
            # Durante o arraste a linha continua visível: somente seu fundo muda.
            # Isso substitui ghost/máscara e evita repaints e estados invisíveis.
            painter.save()
            painter.fillRect(option.rect, self._drag_color)
            painter.restore()
            opt.palette.setBrush(QPalette.Active, QPalette.Text, QBrush(Qt.white))
            opt.palette.setBrush(QPalette.Inactive, QPalette.Text, QBrush(Qt.white))
            opt.palette.setBrush(QPalette.Active, QPalette.WindowText, QBrush(Qt.white))
            opt.palette.setBrush(QPalette.Inactive, QPalette.WindowText, QBrush(Qt.white))
            opt.backgroundBrush = QBrush(Qt.NoBrush)

        super().paint(painter, opt, index)

class ReorderableCommandTable(QTableWidget):
    """Tabela com arrastar-e-soltar para reordenar comandos.

    A ordem visual é sincronizada com automation_map.commands. O arraste é
    iniciado pela linha, não por um botão separado, e o drop acontece na
    posição indicada pelo cursor.
    """
    rows_reordered = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(False)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSupportedDragActions(Qt.MoveAction)
        self.setDragDropOverwriteMode(False)
        self.setAutoScroll(True)
        self.setAutoScrollMargin(44)

    def start_multi_row_drag(self, host, press_pos: QPoint) -> None:
        """Inicia um QDrag nativo para aproveitar autoscroll do Qt.

        O ghost é uma única imagem capturada no início; durante o gesto o Qt
        movimenta essa imagem e trata o autoscroll sem reconstruir a tabela.
        """
        if host is None or host._automation_map is None:
            return
        rows = sorted({idx.row() for idx in self.selectionModel().selectedRows()})
        if not rows:
            rows = sorted({idx.row() for idx in self.selectedIndexes()})
        if not rows:
            return
        rows = [r for r in rows if 0 <= r < self.rowCount()]
        if not rows:
            return

        ids = {host._automation_map.commands[r].id for r in rows
               if 0 <= r < len(host._automation_map.commands)}
        if not ids:
            return

        # Captura uma única vez, antes da máscara esconder as linhas.
        width = max(1, self.viewport().width())
        pixmaps = []
        total_h = 0
        for r in rows:
            vr = self.visualRect(self.model().index(r, 0))
            if not vr.isValid() or vr.height() <= 0:
                continue
            pm = self.viewport().grab(QRect(0, vr.top(), width, vr.height()))
            if not pm.isNull():
                pixmaps.append(pm)
                total_h += pm.height()
        if not pixmaps:
            return
        canvas = QPixmap(width, max(1, total_h))
        canvas.fill(Qt.transparent)
        qp = QPainter(canvas)
        y = 0
        for pm in pixmaps:
            qp.drawPixmap(0, y, pm)
            y += pm.height()
        qp.end()

        host._native_drag_ids = set(ids)
        host._native_drag_rows = set(rows)
        host._row_reorder_dragging = True
        host._row_reorder_ids = set(ids)
        host._reorder_drag_mask.setGeometry(self.viewport().rect())
        host._reorder_drag_mask.set_rows(rows)
        host._reorder_drag_mask.show()
        host._reorder_drag_mask.raise_()
        host._selection_outline.hide()
        host._selection_band.hide()

        mime = QMimeData()
        mime.setData('application/x-automationstudio-command-drag', QByteArray(b'1'))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(canvas)
        offset = self.visualRect(self.model().index(rows[0], 0)).top()
        hot_y = max(0, min(canvas.height() - 1, int(press_pos.y() - offset)))
        drag.setHotSpot(QPoint(max(0, min(canvas.width() - 1, press_pos.x())), hot_y))
        self._native_drag_active = True
        try:
            drag.exec(Qt.MoveAction)
        finally:
            self._native_drag_active = False
            host._native_drag_ids = set()
            host._native_drag_rows = set()
            host._row_reorder_dragging = False
            host._row_reorder_ids = set()
            host._end_reorder_ghost()

    def dragEnterEvent(self, event):  # noqa: N802
        # Aceita explicitamente o MIME interno do editor. Sem isso, o QDrag
        # pode mostrar o cursor proibido (X) e o drop volta para a posição inicial.
        if event.mimeData().hasFormat('application/x-automationstudio-command-drag'):
            event.setDropAction(Qt.MoveAction)
            event.accept()
            self._last_drag_pos = event.position().toPoint()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):  # noqa: N802
        # Mantém o destino aceito enquanto o cursor está dentro do viewport e
        # implementa autoscroll graduado, como no Excel: ~10% inicia devagar,
        # ~5% acelera. O QTableWidget não é reconstruído durante o gesto.
        if event.mimeData().hasFormat('application/x-automationstudio-command-drag'):
            pos = event.position().toPoint()
            self._last_drag_pos = pos
            h = max(1, self.viewport().height())
            margin_slow = max(24, int(h * 0.10))
            margin_fast = max(12, int(h * 0.05))
            sb = self.verticalScrollBar()
            value = sb.value()
            delta = 0
            if pos.y() <= margin_slow:
                depth = max(0, margin_slow - pos.y())
                if pos.y() <= margin_fast:
                    # Região mais próxima da borda: acelera progressivamente.
                    ratio = min(1.0, max(0.0, (margin_fast - pos.y()) / margin_fast))
                    delta = -max(4, int(8 + 22 * ratio))
                else:
                    ratio = min(1.0, depth / max(1, margin_slow - margin_fast))
                    delta = -max(1, int(2 + 8 * ratio))
            elif pos.y() >= h - margin_slow:
                depth = max(0, pos.y() - (h - margin_slow))
                if pos.y() >= h - margin_fast:
                    ratio = min(1.0, max(0.0, (pos.y() - (h - margin_fast)) / margin_fast))
                    delta = max(4, int(8 + 22 * ratio))
                else:
                    ratio = min(1.0, depth / max(1, margin_slow - margin_fast))
                    delta = max(1, int(2 + 8 * ratio))
            if delta:
                sb.setValue(max(sb.minimum(), min(sb.maximum(), value + delta)))
            event.setDropAction(Qt.MoveAction)
            event.accept()
            return
        super().dragMoveEvent(event)

    def dragLeaveEvent(self, event):  # noqa: N802
        # Não cancela o estado do host aqui: o QDrag continua ativo até o drop
        # ou cancelamento; apenas devolvemos o evento ao mecanismo do Qt.
        super().dragLeaveEvent(event)

    def dropEvent(self, event):  # noqa: N802
        # A CommandTableWidget controla o modelo real; não deixe o Qt mover
        # somente as células e dessincronizar a lista de comandos.
        host = self.parentWidget()
        while host is not None and not isinstance(host, CommandTableWidget):
            host = host.parentWidget()
        if host is None or host._automation_map is None:
            event.ignore()
            return

        if event.mimeData().hasFormat('application/x-automationstudio-command-drag'):
            selected_rows = sorted(host._native_drag_rows or {idx.row() for idx in self.selectionModel().selectedRows()})
        else:
            selected_rows = sorted({idx.row() for idx in self.selectionModel().selectedRows()})
            if not selected_rows:
                selected_rows = sorted({idx.row() for idx in self.selectedIndexes()})
        if not selected_rows:
            event.ignore()
            return

        # Determina a linha de destino a partir do indicador de drop.
        pos = event.position().toPoint()
        target = self.indexAt(pos).row()
        if target < 0:
            target = self.rowCount()
        elif pos.y() > self.visualRect(self.model().index(target, 0)).center().y():
            target += 1

        commands = host._automation_map.commands
        moving = [commands[i] for i in selected_rows if 0 <= i < len(commands)]
        if not moving:
            event.ignore()
            return

        result = host._automation_map.move_commands({c.id for c in moving}, target)
        if result is None:
            event.ignore()
            return
        first, last = result
        host.refresh()
        self.clearSelection()
        for row in range(first, last + 1):
            self.selectRow(row)
        self.setCurrentCell(first, 0)
        host.map_changed.emit("Reordenar comandos")
        event.acceptProposedAction()
        self.rows_reordered.emit()

class SelectionOutlineOverlay(QWidget):
    """Desenha o destaque das linhas selecionadas como contorno único por linha."""
    def __init__(self, table, parent=None):
        super().__init__(parent or table.viewport())
        self.table = table
        self.color = QColor("#2F6FED")
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.hide()

    def set_color(self, color: str):
        self.color = _normalized_color(color)
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        c = QColor(self.color)
        c.setAlpha(155)
        pen = QPen(c, 1)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        selected = sorted({i.row() for i in self.table.selectedIndexes()})
        for row in selected:
            if row < 0 or row >= self.table.rowCount():
                continue
            vr = self.table.visualRect(self.table.model().index(row, 0))
            if not vr.isValid() or vr.height() <= 0:
                continue
            r = QRect(0, vr.top(), self.width()-1, vr.height()-1)
            painter.drawRect(r.adjusted(1, 1, -1, -1))

class ReorderDragMaskOverlay(QWidget):
    """Cobre visualmente apenas as linhas em arraste, sem alterar geometria.

    A tabela continua intacta enquanto o usuário arrasta. O overlay apenas
    pinta o fundo original sobre as linhas que estão sendo carregadas,
    permitindo que o ghost seja a única representação do bloco em movimento.
    """
    def __init__(self, table, parent=None):
        super().__init__(parent or table.viewport())
        self.table = table
        self.rows = set()
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.hide()

    def set_rows(self, rows) -> None:
        self.rows = set(rows or ())
        self.update()

    def clear_rows(self) -> None:
        self.rows.clear()
        self.hide()
        self.update()

    def paintEvent(self, _event):
        if not self.rows:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        palette = self.table.palette()
        for row in sorted(self.rows):
            if row < 0 or row >= self.table.rowCount():
                continue
            vr = self.table.visualRect(self.table.model().index(row, 0))
            if not vr.isValid() or vr.height() <= 0:
                continue
            r = QRect(0, max(0, vr.top()), self.width(), vr.height())
            # Usa o fundo da viewport/tabela; o objetivo é apagar somente o
            # conteúdo da linha, preservando exatamente sua geometria.
            brush = palette.brush(QPalette.Base)
            if getattr(self.table, 'alternatingRowColors', lambda: False)():
                if row % 2:
                    brush = palette.brush(QPalette.AlternateBase)
            painter.fillRect(r, brush)


class ReorderGhostOverlay(QWidget):
    """Ghost leve e estático do bloco sendo arrastado.

    O conteúdo é capturado uma única vez no início do gesto. Durante o arraste
    apenas a geometria muda; não há reconstrução de widgets nem repintura das
    células, mantendo o custo do gesto baixo mesmo com várias linhas.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap = QPixmap()
        self._offset = QPoint()
        self._opacity = 0.88
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.hide()

    def set_snapshot(self, pixmap: QPixmap, offset: QPoint) -> None:
        self._pixmap = pixmap
        self._offset = QPoint(offset)
        self.setFixedSize(pixmap.size())
        self.update()

    def move_for_cursor(self, pos: QPoint) -> None:
        self.move(pos - self._offset)
        self.show()
        self.raise_()

    def clear(self) -> None:
        self._pixmap = QPixmap()
        self.hide()

    def paintEvent(self, _event):
        if self._pixmap.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.setOpacity(self._opacity)
        painter.drawPixmap(0, 0, self._pixmap)

class CommandTableWidget(QWidget):
    """Editor central da V23: seleção, edição, clipboard e operações do mapa."""
    map_changed = Signal(str)
    command_editor_requested = Signal(object, int)
    test_requested = Signal(object)
    preview_requested = Signal(object)
    validate_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._automation_map: AutomationMap | None = None
        self._clipboard_commands: list[Command] = []
        self._loading = False

        self.table = ReorderableCommandTable(self)
        self.table.setColumnCount(7)
        # A tabela usa um gesto próprio para reordenar linhas. O drag/drop
        # genérico do QTableWidget ficava disputando o mesmo gesto com a
        # seleção por área e, em algumas situações, movia apenas as células.
        self.table.setDragEnabled(False)
        self._selection_dragging = False
        self._selection_drag_modifiers = Qt.NoModifier
        self._selection_band_selected_rows = []
        self._selection_press_pos = QPoint()
        self._selection_press_index = None
        self._selection_candidate_row = None
        self._selection_press_was_selected = False
        self._selection_press_had_any_selection = False
        self._selection_hold_timer = QTimer(self)
        self._selection_hold_timer.setSingleShot(True)
        self._selection_hold_timer.setInterval(180)
        self._selection_hold_timer.timeout.connect(self._activate_hold_selection)
        self._selection_anchor_row = None
        self._selection_anchor_id = None
        self._context_selection_ids: set[str] = set()
        self._context_press_row: int | None = None
        self._native_drag_active = False
        self._native_drag_ids: set[str] = set()
        self._native_drag_rows: set[int] = set()
        self._native_drag_last_pos = QPoint()
        self._row_reorder_dragging = False
        self._row_reorder_start_row = None
        self._row_reorder_target_row = None
        self._row_reorder_ids = set()
        self._drag_mask_rows = set()
        self._drag_hidden_ids: set[str] = set()
        self._drag_capture_in_progress = False
        self._reorder_ghost = ReorderGhostOverlay(self.table.viewport())
        self._reorder_drag_mask = ReorderDragMaskOverlay(self.table, self.table.viewport())
        self._reorder_drag_mask.hide()
        self._reorder_autoscroll = QTimer(self)
        self._reorder_autoscroll.setInterval(16)
        self._reorder_autoscroll.timeout.connect(self._reorder_autoscroll_tick)
        self._reorder_autoscroll_margin = 42
        self._reorder_autoscroll_step = 26
        self._reorder_indicator = QFrame(self.table.viewport())
        self._reorder_indicator.setObjectName("CommandReorderIndicator")
        self._reorder_indicator.setFixedHeight(3)
        self._reorder_indicator.setStyleSheet("QFrame#CommandReorderIndicator { background: #2F6FED; border: none; }")
        self._reorder_indicator.hide()
        self._selection_band = SelectionRubberBand(self.table.viewport())
        self._selection_band.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._selection_band.set_theme(False, "#2F6FED")
        # Estes estados precisam existir antes de qualquer chamada Qt que
        # possa emitir eventos (setPalette/setStyleSheet podem fazê-lo).
        # Caso contrário o eventFilter pode ser acionado durante a construção
        # do widget e acessar um atributo ainda não inicializado.
        self._editing_cell = False
        self._edit_origin = None
        self.table.viewport().setMouseTracking(True)
        self.table.viewport().setAcceptDrops(True)
        self.table.viewport().installEventFilter(self)
        self._delegate=CommandSelectionDelegate(self.table)
        self._delegate.navigation.connect(self._delegate_navigation)
        self.table.setItemDelegate(self._delegate)
        self._selection_outline = SelectionOutlineOverlay(self.table, self.table.viewport())
        self._selection_outline.raise_()
        self._selection_outline.hide()
        self.table.setHorizontalHeaderLabels(["#", "Ordem dos comandos", "Tipo", "Tecla / botão", "Começa em", "Duração", "Grupo"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        for col, width in enumerate((48, 220, 150, 240, 105, 105, 150)):
            header.resizeSection(col, width)
            header.setMinimumSectionSize(70)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        # O destaque nativo do QTableWidget é desativado visualmente. A
        # seleção lógica continua ativa no selectionModel; o delegate desenha
        # somente o contorno. O uso conjunto de palette + stylesheet impede
        # que estilos do Windows/Fusion reintroduzam o preenchimento azul.
        pal = self.table.palette()
        pal.setBrush(QPalette.Active, QPalette.Highlight, QBrush(Qt.NoBrush))
        pal.setBrush(QPalette.Inactive, QPalette.Highlight, QBrush(Qt.NoBrush))
        pal.setBrush(QPalette.Active, QPalette.HighlightedText, pal.brush(QPalette.Active, QPalette.Text))
        pal.setBrush(QPalette.Inactive, QPalette.HighlightedText, pal.brush(QPalette.Inactive, QPalette.Text))
        self.table.setPalette(pal)
        self.table.setObjectName("CommandEditorTable")
        self.table.setStyleSheet("QTableWidget#CommandEditorTable::item:selected { background: transparent; color: palette(text); }")
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setToolTip("")
        self.table.itemChanged.connect(self._cell_changed)
        self.table.itemSelectionChanged.connect(self._update_selection_summary)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)
        self.table.setAlternatingRowColors(True)
        self.table.installEventFilter(self)

        self.btn_add = QPushButton("＋ ADICIONAR COMANDO")
        self.btn_edit = QPushButton("Editar comando")
        self.btn_remove = QPushButton("Excluir selecionados")
        self.btn_up = QPushButton("▲ Subir")
        self.btn_down = QPushButton("▼ Descer")
        self.btn_groups = QPushButton("● Grupos")
        self.btn_more = QPushButton("Mais…")
        self.btn_add.clicked.connect(self._add_command)
        self.btn_edit.clicked.connect(self._edit_selected)
        self.btn_remove.clicked.connect(self._remove_selected)
        self.btn_up.clicked.connect(lambda: self._move_selected(-1))
        self.btn_down.clicked.connect(lambda: self._move_selected(1))
        self.btn_groups.clicked.connect(self._manage_groups)
        self.btn_more.clicked.connect(self._show_more_actions)

        buttons_row = QHBoxLayout()
        for b in (self.btn_add, self.btn_edit, self.btn_remove, self.btn_up, self.btn_down, self.btn_groups, self.btn_more):
            buttons_row.addWidget(b)
        self.selection_summary = QLabel('Nenhum comando selecionado')
        self.selection_summary.setObjectName('CommandSelectionSummary')
        self.selection_summary.setStyleSheet('color:#8f96a3;font-size:12px;padding-left:4px;')
        buttons_row.addStretch(1)
        buttons_row.addWidget(self.selection_summary)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(6)
        layout.addLayout(buttons_row)
        layout.addWidget(self.table)
        self._set_buttons_enabled(False)

    def set_theme(self, dark: bool, accent: str = "#2F6FED") -> None:
        """Atualiza a linguagem visual da seleção sem alterar a seleção atual."""
        selection_color = "#FFC53D" if dark else (accent or "#2F6FED")
        self._selection_band.set_theme(bool(dark), accent)
        if isinstance(self._delegate, CommandSelectionDelegate):
            self._delegate.set_selection_color(selection_color)
            self._delegate.set_drag_color("#4A78B8" if dark else "#6B9FE8")
        if hasattr(self, "_selection_outline"):
            self._selection_outline.set_color(selection_color)
            self._selection_outline.raise_()
        self.table.viewport().update()

    def _selection_range_from_points(self, start: QPoint, end: QPoint):
        a = self.table.indexAt(start)
        b = self.table.indexAt(end)
        if not a.isValid():
            # Mantém a seleção dentro da última célula visível quando o mouse
            # ultrapassa o viewport durante o arraste.
            a = self.table.model().index(max(0, min(self.table.rowCount()-1, 0)), 0) if self.table.rowCount() else a
        if not b.isValid():
            x = max(0, min(self.table.viewport().width()-1, end.x()))
            y = max(0, min(self.table.viewport().height()-1, end.y()))
            b = self.table.indexAt(QPoint(x, y))
        if not a.isValid() or not b.isValid():
            return None
        top = min(a.row(), b.row()); bottom = max(a.row(), b.row())
        left = min(a.column(), b.column()); right = max(a.column(), b.column())
        return top, left, bottom, right

    def _apply_selection_band(self, current: QPoint) -> None:
        """Seleciona todas as linhas cujo retângulo intersecta a área do arraste."""
        if not self._selection_dragging or not self.table.rowCount():
            return
        rect = QRect(self._selection_press_pos, current).normalized()
        if not rect.isValid() or rect.width() < 1 and rect.height() < 1:
            return
        model = self.table.selectionModel()
        from PySide6.QtCore import QItemSelection, QItemSelectionModel
        model.blockSignals(True)
        try:
            model.clearSelection()
            selected_rows = []
            for row in range(self.table.rowCount()):
                first = self.table.visualRect(self.table.model().index(row, 0))
                if not first.isValid():
                    continue
                row_rect = QRect(0, first.y(), self.table.viewport().width(), first.height())
                # Basta a área de seleção tocar a faixa útil da linha.
                # Não exigimos que o cursor chegue ao centro da linha: isso
                # deixa a seleção muito mais natural e responsiva.
                if row_rect.intersects(rect):
                    selected_rows.append(row)

            if selected_rows:
                # O retângulo produz sempre uma faixa contínua de linhas.
                # Selecionamos explicitamente da primeira à última coluna, em
                # vez de selecionar células isoladas. Isso torna o resultado
                # independente da coluna em que o arraste começou.
                model.clearSelection()
                top = selected_rows[0]
                bottom = selected_rows[-1]
                top_left = self.table.model().index(top, 0)
                bottom_right = self.table.model().index(bottom, self.table.columnCount() - 1)
                model.select(
                    QItemSelection(top_left, bottom_right),
                    QItemSelectionModel.Select | QItemSelectionModel.Rows,
                )
                self._selection_band_selected_rows = list(selected_rows)
            else:
                model.clearSelection()
                self._selection_band_selected_rows = []
        finally:
            model.blockSignals(False)

        if selected_rows:
            # O índice atual é independente da seleção; não o alteramos aqui para
            # evitar que o QTableWidget faça uma seleção nativa concorrente.
            self._update_selection_summary()
        else:
            self.table.viewport().update()

    def _finish_selection_drag(self) -> None:
        if not self._selection_dragging:
            return
        self._update_selection_band(self._selection_current_pos)
        self._apply_selection_band(self._selection_current_pos)
        self._selection_dragging = False
        self._selection_band.hide()
        self._selection_press_index = None

    def _update_selection_band(self, current: QPoint) -> None:
        self._selection_current_pos = current
        r = QRect(self._selection_press_pos, current).normalized()
        self._selection_band.set_rect(r)
        self._selection_band.show()
        self._selection_band.raise_()

    def _select_clicked_row(self, row: int, modifiers) -> None:
        if row < 0 or row >= self.table.rowCount():
            return
        model = self.table.selectionModel()
        from PySide6.QtCore import QItemSelection, QItemSelectionModel

        # A âncora de Shift pertence ao comando (ID), e nao ao indice da tabela.
        # Isso evita que filtros/reordenações visuais façam o intervalo começar
        # em uma linha diferente da que o usuário clicou originalmente.
        clicked_item = self.table.item(row, 0)
        clicked_id = clicked_item.data(Qt.UserRole) if clicked_item else None

        if modifiers & Qt.ShiftModifier and self._selection_anchor_id is not None:
            anchor_row = next(
                (r for r in range(self.table.rowCount())
                 if (self.table.item(r, 0) is not None and
                     self.table.item(r, 0).data(Qt.UserRole) == self._selection_anchor_id)),
                None,
            )
            if anchor_row is not None:
                lo, hi = sorted((int(anchor_row), int(row)))
                model.clearSelection()
                # Seleção explícita por linha. Isso evita a ambiguidade do
                # QItemSelectionModel.Rows em QTableWidget e garante que todo
                # o intervalo seja realmente selecionado.
                for r in range(lo, hi + 1):
                    model.select(
                        self.table.model().index(r, 0),
                        QItemSelectionModel.Select | QItemSelectionModel.Rows,
                    )
                self._selection_anchor_row = anchor_row
            else:
                model.clearSelection()
                self.table.selectRow(row)
                self._selection_anchor_row = row
                self._selection_anchor_id = clicked_id
        elif modifiers & Qt.ControlModifier:
            top_left = self.table.model().index(row, 0)
            bottom_right = self.table.model().index(row, self.table.columnCount() - 1)
            model.select(QItemSelection(top_left, bottom_right), QItemSelectionModel.Toggle | QItemSelectionModel.Rows)
            self._selection_anchor_row = row
            self._selection_anchor_id = clicked_id
        else:
            model.clearSelection()
            self.table.selectRow(row)
            self._selection_anchor_row = row
            self._selection_anchor_id = clicked_id
        self.table.setCurrentCell(row, 0)

    def _activate_hold_selection(self) -> None:
        """Após manter o botão esquerdo pressionado, habilita a seleção por área.

        O clique só é confirmado no release. Enquanto não houver uma seleção
        prévia, o gesto de pressionar e segurar passa a usar o retângulo de
        seleção a partir exatamente do ponto inicial.
        """
        if self._selection_press_index is None:
            return
        if self._selection_press_had_any_selection:
            return
        self._selection_dragging = True
        self._selection_current_pos = self._selection_press_pos
        self._update_selection_band(self._selection_current_pos)
        self._apply_selection_band(self._selection_current_pos)

    def _handle_viewport_selection_event(self, event):
        """Controla clique, seleção por área e reordenação com gesto explícito.

        Regras UX:
        - clique simples: seleção só é aplicada no release;
        - seleção existente + arraste iniciado sobre uma linha selecionada:
          reordena o conjunto selecionado;
        - nenhuma seleção + botão esquerdo mantido por 220 ms: inicia seleção
          por área no ponto exato do press;
        - a caixa de seleção nunca substitui a reordenação de uma seleção já
          existente.
        """
        if self._editing_cell:
            return False

        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.RightButton:
            # Preserve the complete multi-selection before Qt processes the
            # context-click. QTableWidget normally makes the row under the
            # cursor current/selected, which used to collapse a multi-selection
            # to a single row before the group menu was invoked.
            pos = event.position().toPoint()
            idx = self.table.indexAt(pos)
            self._context_press_row = idx.row() if idx.isValid() else None
            if idx.isValid() and idx.row() in set(self._selected_rows()):
                self._context_selection_ids = {
                    self._automation_map.commands[r].id
                    for r in self._selected_rows()
                    if self._automation_map and 0 <= r < len(self._automation_map.commands)
                }
            else:
                self._context_selection_ids = set()
            # Do not consume: the native context-menu event still needs to be
            # delivered, but the selection snapshot above survives it.
            return False

        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self._selection_hold_timer.stop()
            self._selection_band.hide()
            pos = event.position().toPoint()
            idx = self.table.indexAt(pos)
            current_rows = set(self._selected_rows())
            self._selection_press_pos = pos
            self._selection_current_pos = pos
            self._selection_press_index = idx
            self._selection_press_had_any_selection = bool(current_rows)
            self._selection_press_was_selected = bool(idx.isValid() and idx.row() in current_rows)
            self._selection_drag_modifiers = event.modifiers()
            self._selection_dragging = False
            self._row_reorder_dragging = False
            self._row_reorder_start_row = idx.row() if idx.isValid() else None
            self._row_reorder_target_row = idx.row() if idx.isValid() else None
            self._row_reorder_ids = {
                self._automation_map.commands[r].id
                for r in current_rows
                if self._automation_map and 0 <= r < len(self._automation_map.commands)
            }
            self._selection_candidate_row = idx.row() if idx.isValid() else None

            # Só há espera para o gesto de seleção por área quando não existe
            # nenhuma seleção. Com seleção existente, o arraste de uma linha
            # selecionada é reservado à reordenação.
            if not current_rows:
                self._selection_hold_timer.start()
            return True

        if event.type() == QEvent.MouseMove:
            if not (event.buttons() & Qt.LeftButton):
                self._selection_hold_timer.stop()
                if self._selection_dragging or not self._selection_band.isHidden():
                    self._selection_dragging = False
                    self._selection_band.hide()
                self._row_reorder_dragging = False
                return False

            pos = event.position().toPoint()
            self._selection_current_pos = pos
            delta = pos - self._selection_press_pos

            # Se o gesto partiu de uma seleção já existente e da linha
            # selecionada, o arraste vertical é exclusivamente reordenação.
            if (self._selection_press_had_any_selection and
                    self._selection_press_was_selected and
                    not self._selection_dragging):
                if abs(delta.y()) >= max(3, QApplication.startDragDistance() // 2):
                    self._selection_hold_timer.stop()
                    self._selection_hold_timer.stop()
                    self._selection_band.hide()
                    self._reorder_indicator.hide()
                    # Arraste manual leve: captura um único ghost e prende
                    # o mouse ao viewport. Não usamos QDrag do Qt, pois ele
                    # perde o controle do destino quando o cursor alcança
                    # regiões sem células e introduz o cursor de proibido.
                    self._row_reorder_dragging = True
                    self._row_reorder_target_row = self._reorder_target_from_cursor(pos)
                    self._begin_reorder_ghost(pos)
                    self.table.viewport().grabMouse()
                    # O acompanhamento passa a ser dirigido por um único
                    # timer leve de 60 FPS, além do MouseMove. Isso garante
                    # continuidade mesmo quando o cursor fica em áreas sem
                    # células (espaço vazio/limites do viewport) ou durante
                    # o autoscroll.
                    self._reorder_autoscroll.start()
                    self._live_reorder_at(pos)
                    return True

            if self._selection_dragging:
                self._update_selection_band(pos)
                self._apply_selection_band(pos)
                return True

            if self._row_reorder_dragging:
                # Durante o arraste, apenas o ghost acompanha o cursor e o
                # slot de destino é recalculado. A tabela real permanece
                # estável até o release, evitando repaints e deslocamentos.
                self._live_reorder_at(pos)
                return True

            return True

        if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            self._selection_hold_timer.stop()
            pos = event.position().toPoint()
            try:
                if self._selection_dragging:
                    self._update_selection_band(pos)
                    self._finish_selection_drag()
                    return True
                if self._row_reorder_dragging:
                    try:
                        self._finish_row_reorder(pos)
                    finally:
                        try:
                            self.table.viewport().releaseMouse()
                        except Exception:
                            pass
                    return True
                idx = self.table.indexAt(pos)
                if idx.isValid():
                    self._select_clicked_row(idx.row(), self._selection_drag_modifiers)
                else:
                    # Clique em área vazia do viewport desfaz a seleção. Isso é
                    # especialmente importante agora que o viewport captura o gesto
                    # manualmente e, portanto, não deixa o QTableWidget limpar a seleção
                    # por conta própria.
                    self.table.clearSelection()
                    self.table.setCurrentItem(None)
                    self._selection_anchor_row = None
                    self._selection_anchor_id = None
                    self._update_selection_summary()
                return True
            finally:
                self._selection_press_index = None
                self._selection_candidate_row = None
                self._selection_press_was_selected = False
                self._selection_press_had_any_selection = False
                self._selection_dragging = False
                self._row_reorder_dragging = False
                self._row_reorder_target_row = None
                self._reorder_indicator.hide()
                self._selection_band.hide()
                if not self._row_reorder_dragging:
                    self._end_reorder_ghost()
        return False

    def _current_visual_command_ids(self) -> list:
        ids = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None:
                cid = item.data(Qt.UserRole)
                if cid is not None:
                    ids.append(cid)
        return ids

    def _reorder_target_from_cursor(self, pos: QPoint) -> int:
        """Calcula o slot de inserção usando a ordem VISUAL atual da tabela.

        Isso é deliberadamente independente do índice original do modelo: durante
        o arraste a própria tabela se move em tempo real, então o cursor deve ser
        comparado com as linhas que estão realmente na tela naquele instante.
        """
        moving = set(self._row_reorder_ids or ())
        current_ids = self._current_visual_command_ids()
        remaining_ids = [cid for cid in current_ids if cid not in moving]
        if not remaining_ids:
            return 0
        y = int(pos.y())
        first = None
        last = None
        for visual_row, cid in enumerate(current_ids):
            if cid in moving:
                continue
            vr = self.table.visualRect(self.table.model().index(visual_row, 0))
            if not vr.isValid() or vr.height() <= 0:
                continue
            if first is None:
                first = vr
            last = vr
            slot = remaining_ids.index(cid)
            if y < vr.center().y():
                return slot
        if last is None:
            return 0
        return len(remaining_ids)

    def _move_visual_block_to_slot(self, slot: int) -> None:
        """Move o bloco visual por trocas de linhas, sem reconstruir a tabela.

        O método anterior removia/insiria linhas inteiras. Isso fazia o viewport
        recalcular geometria e, em algumas combinações de seleção/scroll, a
        movimentação parecia não acontecer. Aqui movemos apenas as linhas que
        precisam atravessar o bloco, mantendo a tabela estável e atualizando
        apenas os QTableWidgetItems envolvidos.
        """
        moving = set(self._row_reorder_ids or ())
        current_ids = self._current_visual_command_ids()
        if not moving or not current_ids:
            return
        remaining_ids = [cid for cid in current_ids if cid not in moving]
        slot = max(0, min(int(slot), len(remaining_ids)))
        moving_ids = [cid for cid in current_ids if cid in moving]
        desired_ids = remaining_ids[:slot] + moving_ids + remaining_ids[slot:]
        if desired_ids == current_ids:
            return

        # Fazemos somente as trocas necessárias entre linhas adjacentes.
        # Para cada posição, encontramos o ID que deve ocupá-la e deslocamos
        # a linha atual com takeItem/setItem. Isso evita setRowCount/refresh.
        self.table.blockSignals(True)
        try:
            max_steps = self.table.rowCount() + 2
            steps = 0
            while self._current_visual_command_ids() != desired_ids and steps < max_steps:
                steps += 1
                live_ids = self._current_visual_command_ids()
                # Primeiro ponto de divergência.
                pivot = next((i for i,(a,b) in enumerate(zip(live_ids, desired_ids)) if a != b), None)
                if pivot is None:
                    break
                wanted = desired_ids[pivot]
                found = live_ids.index(wanted, pivot)
                if found == pivot:
                    continue
                # Desloca a linha desejada para o pivot por swaps adjacentes.
                direction = -1
                while found > pivot:
                    self._swap_visual_rows(found, found - 1)
                    found -= 1
                if direction:
                    pass
        finally:
            self.table.blockSignals(False)

        # Reaplica a seleção por ID sem disparar sinais durante a atualização.
        self.table.blockSignals(True)
        try:
            self.table.clearSelection()
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if item is not None and item.data(Qt.UserRole) in moving:
                    self.table.selectRow(row)
        finally:
            self.table.blockSignals(False)
        self.table.viewport().update()

    def _swap_visual_rows(self, a: int, b: int) -> None:
        if a == b or not (0 <= a < self.table.rowCount()) or not (0 <= b < self.table.rowCount()):
            return
        if abs(a - b) != 1:
            return
        left, right = (a, b) if a < b else (b, a)
        for col in range(self.table.columnCount()):
            first = self.table.takeItem(left, col)
            second = self.table.takeItem(right, col)
            self.table.setItem(left, col, second)
            self.table.setItem(right, col, first)

    def _begin_reorder_ghost(self, pos: QPoint) -> None:
        """Inicia o arraste visual sem ghost e sem ocultar as linhas.

        O destaque é feito diretamente pelo delegate. A ordem visual da tabela
        passa a acompanhar o cursor em tempo real; o modelo só é confirmado no release.
        """
        if not self._row_reorder_ids:
            return
        self._selection_outline.hide()
        self._selection_band.hide()
        self._reorder_indicator.hide()
        self._drag_hidden_ids = set()
        self._drag_mask_rows = set()
        self._reorder_ghost.clear()
        if hasattr(self, '_reorder_drag_mask'):
            self._reorder_drag_mask.clear_rows()
        self.table.viewport().update()

    def _end_reorder_ghost(self) -> None:
        self._reorder_autoscroll.stop()
        self._drag_mask_rows = set()
        self._drag_hidden_ids = set()
        self._reorder_ghost.clear()
        if hasattr(self, '_reorder_drag_mask'):
            self._reorder_drag_mask.clear_rows()
        self.table.viewport().update()
        self._refresh_selection_outline()

    def _reorder_autoscroll_tick(self) -> None:
        """Autoscroll suave + acompanhamento do ghost, sem reconstruir a tabela."""
        if not self._row_reorder_dragging:
            self._reorder_autoscroll.stop()
            return
        vp = self.table.viewport()
        global_pos = QCursor.pos()
        pos = vp.mapFromGlobal(global_pos)
        self._native_drag_last_pos = pos

        h = max(1, vp.height())
        # Zonas proporcionais ao viewport: 10% inicia; 5% acelera.
        slow = max(28, int(h * 0.10))
        fast = max(14, int(h * 0.05))
        sb = self.table.verticalScrollBar()
        value = sb.value()
        delta = 0
        if pos.y() < 0 or pos.y() <= slow:
            y = max(0, pos.y())
            if y <= fast:
                ratio = 1.0 if y < 0 else min(1.0, (fast - y) / max(1, fast))
                delta = -max(5, int(8 + 24 * ratio))
            else:
                ratio = min(1.0, (slow - y) / max(1, slow - fast))
                delta = -max(1, int(2 + 8 * ratio))
        elif pos.y() > h or pos.y() >= h - slow:
            y = pos.y()
            if y >= h or y >= h - fast:
                ratio = 1.0 if y > h else min(1.0, (y - (h - fast)) / max(1, fast))
                delta = max(5, int(8 + 24 * ratio))
            else:
                ratio = min(1.0, (y - (h - slow)) / max(1, slow - fast))
                delta = max(1, int(2 + 8 * ratio))
        if delta:
            new_value = max(sb.minimum(), min(sb.maximum(), value + delta))
            if new_value != value:
                sb.setValue(new_value)

        self._live_reorder_at(pos)
        self.table.viewport().update()

    def _live_reorder_at(self, pos: QPoint) -> None:
        """Move a representação real das linhas em tempo real, sem alterar o modelo."""
        if not self._automation_map or not self._row_reorder_ids:
            return
        slot = max(0, int(self._reorder_target_from_cursor(pos)))
        self._row_reorder_target_row = slot
        self._move_visual_block_to_slot(slot)

    def _show_reorder_indicator(self, pos: QPoint) -> None:
        """Mostra a linha de inserção em tempo real, acima da posição de destino."""
        if not self._row_reorder_dragging:
            self._reorder_indicator.hide()
            return
        idx = self.table.indexAt(pos)
        if idx.isValid():
            vr = self.table.visualRect(idx)
            y = vr.top() if pos.y() <= vr.center().y() else vr.bottom() + 1
        else:
            y = self.table.viewport().height() - 1
        y = max(0, min(y, self.table.viewport().height() - 3))
        self._reorder_indicator.setGeometry(0, y, self.table.viewport().width(), 3)
        self._reorder_indicator.show()
        self._reorder_indicator.raise_()

    def _update_row_reorder_target(self, pos: QPoint) -> None:
        if not self._automation_map or not self._automation_map.commands:
            return
        self._row_reorder_target_row = self._reorder_target_from_cursor(pos)

    def _finish_row_reorder(self, pos: QPoint) -> None:
        if not self._automation_map or not self._row_reorder_ids:
            self._row_reorder_dragging = False
            self._row_reorder_ids = set()
            self._end_reorder_ghost()
            return

        # A tabela pode ter sido reorganizada apenas visualmente durante o gesto.
        # A ordem final desejada é convertida em um único movimento do MODELO,
        # para que o mecanismo central também reconstrua os tempos.
        desired_ids = self._current_visual_command_ids()
        original_ids = [cmd.id for cmd in self._automation_map.commands]
        ids = set(self._row_reorder_ids)

        # A ordem visual atual da tabela é a fonte de verdade do drop.
        # Em vez de converter novamente para um índice potencialmente sujeito
        # a off-by-one, usamos a sequência visual completa diretamente.
        desired_moving = [cid for cid in desired_ids if cid in ids]
        visual_remaining = [cid for cid in desired_ids if cid not in ids]
        original_moving = [cid for cid in original_ids if cid in ids]
        if desired_moving != original_moving or desired_ids != original_ids:
            changed = True
        else:
            changed = False

        self._row_reorder_dragging = False
        self._row_reorder_target_row = None
        self._reorder_indicator.hide()
        self._row_reorder_ids = set()
        self._reorder_autoscroll.stop()
        self._end_reorder_ghost()

        if not changed:
            self.table.viewport().update()
            return

        result = self._automation_map.reorder_to_ids(desired_ids)
        if result is None:
            self.table.viewport().update()
            return

        self.refresh()
        self.table.clearSelection()
        for row, cmd in enumerate(self._automation_map.commands):
            if cmd.id in ids:
                self.table.selectRow(row)
        self._selection_anchor_row = next((row for row, cmd in enumerate(self._automation_map.commands) if cmd.id in ids), None)
        self._selection_anchor_id = next((cmd.id for cmd in self._automation_map.commands if cmd.id in ids), None)
        self.map_changed.emit("Alteração")
        self._update_selection_summary()

    def _refresh_selection_outline(self) -> None:
        if not hasattr(self, "_selection_outline"):
            return
        # Durante a reordenação, a borda de seleção não deve permanecer presa
        # na posição original. O destaque do arraste é desenhado pelo delegate
        # a partir do ID do comando, portanto ele acompanha a linha visualmente.
        if getattr(self, "_row_reorder_dragging", False):
            self._selection_outline.hide()
            return
        has = bool(self.table.selectedIndexes())
        self._selection_outline.setGeometry(self.table.viewport().rect())
        if has:
            self._selection_outline.show()
            self._selection_outline.raise_()
            self._selection_outline.update()
        else:
            self._selection_outline.hide()

    def _update_selection_summary(self) -> None:
        self._refresh_selection_outline()
        if self._automation_map is None:
            self.selection_summary.setText('Nenhum mapa selecionado')
            return
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()})
        if not rows:
            self.selection_summary.setText(f'{len(self._automation_map.commands)} comando(s)')
            return
        selected = [self._automation_map.commands[i] for i in rows if 0 <= i < len(self._automation_map.commands)]
        total = sum(c.computed_duration for c in selected)
        if len(selected) == 1:
            self.selection_summary.setText(f'1 comando selecionado • {total:.2f} s')
        else:
            self.selection_summary.setText(f'{len(selected)} comandos selecionados • {total:.2f} s')

    def _delegate_navigation(self, direction: str) -> None:
        item=self.table.currentItem()
        if item is None:
            self._editing_cell=False
            return
        r,c=item.row(),item.column()
        if direction=="enter":
            origin=self._edit_origin or (r,c)
            # Enter sempre conserva a coluna original e desce uma linha.
            nr=min(self.table.rowCount()-1, origin[0]+1)
            self.table.setCurrentCell(nr, origin[1])
            self._edit_origin=origin
        else:
            nc=min(self.table.columnCount()-1,c+1)
            self.table.setCurrentCell(r,nc)
            self._edit_origin=(r,nc)
        self._editing_cell=False

    def eventFilter(self, obj, event):
        if obj is self.table.viewport():
            # QDrag entrega DragEnter/DragMove/Drop ao viewport interno do
            # QTableWidget, não necessariamente ao QTableWidget em si.
            # Encaminhamos explicitamente esses eventos para manter o drop
            # aceito e permitir autoscroll dentro do quadro.
            if event.type() == QEvent.DragEnter and event.mimeData().hasFormat('application/x-automationstudio-command-drag'):
                event.setDropAction(Qt.MoveAction)
                event.accept()
                return True
            if event.type() == QEvent.DragMove and event.mimeData().hasFormat('application/x-automationstudio-command-drag'):
                pos = event.position().toPoint()
                self._selection_current_pos = pos
                self._native_drag_last_pos = pos
                event.setDropAction(Qt.MoveAction)
                event.accept()
                return True
            if event.type() == QEvent.Drop and event.mimeData().hasFormat('application/x-automationstudio-command-drag'):
                pos = event.position().toPoint()
                event.setDropAction(Qt.MoveAction)
                event.accept()
                self._finish_native_drop_from_viewport(pos)
                return True
            handled = self._handle_viewport_selection_event(event)
            if handled:
                return True
        if obj is self.table and event.type() == QEvent.KeyPress:
            key=event.key(); mods=event.modifiers()
            if key == Qt.Key_Delete:
                self._remove_selected(); return True
            if key == Qt.Key_A and mods & Qt.ControlModifier:
                self.table.selectAll(); return True
            if key == Qt.Key_C and mods & Qt.ControlModifier:
                self._copy_selected(); return True
            if key == Qt.Key_X and mods & Qt.ControlModifier:
                self._copy_selected(); self._remove_selected(); return True
            if key == Qt.Key_V and mods & Qt.ControlModifier:
                self._paste(); return True
            if key == Qt.Key_Z and mods & Qt.ControlModifier:
                host=self.window()
                if hasattr(host,'_undo_map'): host._undo_map()
                return True
            if key == Qt.Key_Y and mods & Qt.ControlModifier:
                host=self.window()
                if hasattr(host,'_redo_map'): host._redo_map()
                return True
            if key in (Qt.Key_Return, Qt.Key_Enter):
                item=self.table.currentItem()
                if item is None:
                    return True
                if not self._editing_cell:
                    self._editing_cell=True
                    self._edit_origin=(item.row(), item.column())
                    self.table.editItem(item)
                    return True
                self._editing_cell=False
                r,c=self._edit_origin or (item.row(),item.column())
                self.table.closePersistentEditor(item)
                nr=min(self.table.rowCount()-1,r+1)
                self.table.setCurrentCell(nr,c)
                self.table.editItem(self.table.currentItem())
                self._edit_origin=(r,c)
                self._editing_cell=True
                return True
            if key == Qt.Key_Tab:
                item=self.table.currentItem()
                if item is not None:
                    c=min(self.table.columnCount()-1,item.column()+1)
                    self.table.setCurrentCell(item.row(),c)
                return True
        return super().eventFilter(obj,event)

    def _finish_native_drop_from_viewport(self, pos: QPoint) -> None:
        """Finaliza o QDrag usando coordenadas do viewport.

        O viewport recebe o evento de drop; por isso calculamos o slot a partir
        da sua geometria sem depender de QTableWidget.dropEvent().
        """
        if not self._automation_map or not self._native_drag_ids:
            return
        self._row_reorder_target_row = self._reorder_target_from_cursor(pos)
        target = max(0, int(self._row_reorder_target_row or 0))
        ids = set(self._native_drag_ids)
        result = self._automation_map.move_commands(ids, target)
        if result is None:
            return
        self._row_reorder_target_row = target

    def set_map(self, automation_map: AutomationMap | None) -> None:
        self._automation_map = automation_map
        if automation_map:
            automation_map.ensure_legacy_groups()
        self._set_buttons_enabled(automation_map is not None)
        self.refresh()

    def refresh(self) -> None:
        self._loading = True
        self.table.setRowCount(0)
        if self._automation_map:
            for row, cmd in enumerate(self._automation_map.commands):
                self.table.insertRow(row)
                self._fill_row(row, cmd)
        self._loading = False

    def set_recording_preview(self, commands: list[Command]) -> None:
        self._loading = True
        self.table.setRowCount(0)
        if self._automation_map:
            base = list(self._automation_map.commands)
            for row, cmd in enumerate(base + commands):
                self.table.insertRow(row); self._fill_row(row, cmd)
                if row >= len(base):
                    for col in range(self.table.columnCount()):
                        item=self.table.item(row,col)
                        if item: item.setBackground(QColor(255,245,190,220))
        self._loading = False

    def clear_recording_preview(self) -> None:
        self.refresh()

        self._update_selection_summary()

    def _fill_row(self, row: int, cmd: Command) -> None:
        type_name = {InputType.KEY:"Teclado", InputType.MOUSE_BUTTON:"Botão do mouse", InputType.MOUSE_MOVE:"Mover mouse", InputType.MOUSE_SCROLL:"Rolar mouse", InputType.TEXT:"Digitar texto", InputType.APP_OPEN:"Abrir aplicativo"}.get(cmd.type, "Comando")
        group = self._automation_map.groups.get(cmd.group_id) if self._automation_map and cmd.group_id else None
        display_target = cmd.text if cmd.type == InputType.TEXT else cmd.target
        if len(display_target) > 70: display_target = display_target[:67] + "…"
        values = [str(row + 1), cmd.description or type_name, type_name, display_target, f"{cmd.start:.2f} s", f"{cmd.computed_duration:.2f} s", group.name if group else cmd.group]
        for col, text in enumerate(values):
            item = QTableWidgetItem(text)
            item.setData(Qt.UserRole, cmd.id)
            if col in (0,2,3): item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            if group:
                bg = _normalized_color(group.color)
                # A cor do grupo fica somente no # para preservar a
                # legibilidade do restante da linha. A seleção é desenhada
                # separadamente pelo delegate, como na Timeline.
                if col == 0:
                    item.setBackground(bg)
                    item.setForeground(_text_color_for_background(bg))
                item.setToolTip(group.description or group.name)
            self.table.setItem(row, col, item)

    def _selected_rows(self) -> list[int]:
        return sorted({i.row() for i in self.table.selectionModel().selectedIndexes()})

    def _selected_index(self) -> int | None:
        rows=self._selected_rows(); return rows[0] if rows else None

    def _add_command(self) -> None:
        if not self._automation_map: return
        rows = self._selected_rows()
        # O clique no botão pode tirar o foco da tabela, mas a última seleção
        # válida permanece registrada como âncora. Assim, em automações com
        # centenas de linhas, Adicionar comando não cai acidentalmente no fim.
        anchor = max(rows) if rows else self._selection_anchor_row
        if anchor is None:
            current = self.table.currentRow()
            anchor = current if current >= 0 else None
        insertion_index = (int(anchor) + 1) if anchor is not None else -1
        self.command_editor_requested.emit(None, insertion_index)

    def _edit_selected(self, *_args) -> None:
        index=self._selected_index()
        if index is None or not self._automation_map: return
        self.command_editor_requested.emit(self._automation_map.commands[index], index)

    def _begin_edit(self, item, *_args):
        if item.column() in (1,4,5,6): self.table.editItem(item)
        else: self.table.setCurrentItem(item)

    def _cell_changed(self, item: QTableWidgetItem) -> None:
        if self._loading or not self._automation_map: return
        row, col = item.row(), item.column()
        if row >= len(self._automation_map.commands): return
        cmd=self._automation_map.commands[row]
        text=item.text().strip()
        try:
            if col == 1:
                cmd.description=text
            elif col == 4:
                cmd.start=max(0.0,float(text.lower().replace('s','').strip().replace(',','.')))
            elif col == 5:
                cmd.duration=max(0.0,float(text.lower().replace('s','').strip().replace(',','.')))
            elif col == 6:
                match=next((g for g in self._automation_map.groups.values() if g.name.lower()==text.lower()),None)
                if text and match is None:
                    raise ValueError('grupo inexistente')
                cmd.group_id=match.id if match else ''
                cmd.group=match.name if match else ''
            else: return
        except ValueError:
            self.refresh(); return
        self.map_changed.emit("Editar comando")

    def _remove_selected(self) -> None:
        if not self._automation_map: return
        rows=self._selected_rows()
        if not rows: return
        first,last=rows[0]+1,rows[-1]+1
        if self._automation_map.confirm_delete_commands:
            box=QMessageBox(self)
            box.setWindowTitle('Excluir comandos')
            box.setText(f'Excluir linha {first} a {last}?')
            box.setInformativeText('Os comandos abaixo serão aproximados no tempo, preservando a distância existente após o bloco excluído.')
            box.setStandardButtons(QMessageBox.Cancel | QMessageBox.Yes)
            box.button(QMessageBox.Yes).setText('Confirmar')
            box.button(QMessageBox.Cancel).setText('Cancelar')
            dont=QCheckBox('Não perguntar novamente neste mapa')
            box.setCheckBox(dont)
            if box.exec() != QMessageBox.Yes: return
            if dont.isChecked(): self._automation_map.confirm_delete_commands=False
        selected={self._automation_map.commands[r].id for r in rows}
        self._compact_after_delete(selected)
        self.refresh(); self.map_changed.emit("Excluir comandos")

    def _compact_after_delete(self, selected: set[str]) -> None:
        """Compatibilidade com chamadas antigas; a V23 mantém a operação no modelo."""
        if self._automation_map:
            self._automation_map.remove_commands(set(selected), compact=True)

    def _move_selected(self,direction:int) -> None:
        if not self._automation_map:return
        rows=self._selected_rows()
        if len(rows)!=1:return
        i=rows[0]; j=i+direction
        if 0<=j<len(self._automation_map.commands):
            cmd_id=self._automation_map.commands[i].id
            self._automation_map.move_commands({cmd_id}, j + 1 if direction > 0 else j)
            self.refresh(); self.table.selectRow(j); self.table.setCurrentCell(j, 0); self.map_changed.emit("Mover comandos")

    def _context_menu(self,pos):
        if not self._automation_map:return
        menu=QMenu(self)
        # If the context click landed on an already-selected row, operate on
        # the selection that existed when the right button was pressed. This
        # prevents Qt's native right-click behavior from reducing it to the
        # row under the cursor.
        context_ids = set(self._context_selection_ids)
        if not context_ids:
            context_ids = {
                self._automation_map.commands[r].id
                for r in self._selected_rows()
                if self._automation_map and 0 <= r < len(self._automation_map.commands)
            }
        if self._context_press_row is not None and self._context_press_row not in self._selected_rows():
            context_ids = {self._automation_map.commands[self._context_press_row].id} if 0 <= self._context_press_row < len(self._automation_map.commands) else context_ids
        copy_a=menu.addAction('Copiar selecionados'); copy_a.triggered.connect(lambda: self._copy_ids(context_ids))
        paste_a=menu.addAction('Colar'); paste_a.triggered.connect(self._paste)
        dup_a=menu.addAction('Duplicar selecionados'); dup_a.triggered.connect(lambda: self._duplicate_ids(context_ids))
        menu.addSeparator(); delete_a=menu.addAction('Excluir selecionados'); delete_a.triggered.connect(lambda: self._remove_ids(context_ids))
        groups=menu.addMenu('Adicionar ao grupo')
        new_a=groups.addAction('＋ Criar novo grupo'); new_a.triggered.connect(lambda: self._create_group_for_ids(context_ids))
        if self._automation_map.groups:
            groups.addSeparator()
            for g in self._automation_map.groups.values():
                a=groups.addAction(f'● {g.name}'); a.triggered.connect(lambda checked=False,gid=g.id,ids=set(context_ids):self._assign_group_ids(gid, ids))
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _copy_selected(self):
        if not self._automation_map:return
        rows=self._selected_rows()
        if not rows:return
        base=min(self._automation_map.commands[r].start for r in rows)
        self._clipboard_commands=[]
        for r in rows:
            c=copy.deepcopy(self._automation_map.commands[r]); c.start=max(0.0,c.start-base); self._clipboard_commands.append(c)
        QApplication.clipboard().setText(json.dumps([c.to_dict() for c in self._clipboard_commands],ensure_ascii=False))

    def _paste(self):
        if not self._automation_map:return
        cmds=copy.deepcopy(self._clipboard_commands)
        if not cmds:
            try: cmds=[Command.from_dict(x) for x in json.loads(QApplication.clipboard().text())]
            except Exception:return
        rows=self._selected_rows()
        anchor_row=max(rows) if rows else self._selection_anchor_row
        insert_at=(int(anchor_row)+1) if anchor_row is not None else len(self._automation_map.commands)
        insert_at=max(0,min(insert_at,len(self._automation_map.commands)))
        base=self._automation_map.commands[insert_at-1].effective_end if insert_at > 0 else 0.0
        for c in cmds: c.id=_next_id(); c.start += base
        for offset,c in enumerate(cmds):
            self._automation_map.commands.insert(insert_at+offset,c)
        self.refresh(); self.map_changed.emit("Colar comandos")

    def _duplicate_selected(self): self._copy_selected(); self._paste()

    def _assign_group_ids(self, gid: str, ids: set[str]) -> None:
        if not self._automation_map or gid not in self._automation_map.groups:
            return
        g = self._automation_map.groups[gid]
        for c in self._automation_map.commands:
            if c.id in ids:
                c.group_id = gid
                c.group = g.name
        self.refresh(); self.map_changed.emit("Alteração")

    def _copy_ids(self, ids: set[str]) -> None:
        rows = [i for i,c in enumerate(self._automation_map.commands) if c.id in ids] if self._automation_map else []
        if not rows: return
        base=min(self._automation_map.commands[r].start for r in rows)
        self._clipboard_commands=[]
        for r in rows:
            c=copy.deepcopy(self._automation_map.commands[r]); c.start=max(0.0,c.start-base); self._clipboard_commands.append(c)
        QApplication.clipboard().setText(json.dumps([c.to_dict() for c in self._clipboard_commands],ensure_ascii=False))

    def _duplicate_ids(self, ids: set[str]) -> None:
        self._copy_ids(ids); self._paste()

    def _remove_ids(self, ids: set[str]) -> None:
        if not self._automation_map or not ids: return
        self._automation_map.remove_commands(set(ids), compact=True); self.refresh(); self.map_changed.emit("Excluir comandos")

    def _create_group_for_ids(self, ids: set[str]) -> None:
        if not self._automation_map or not ids: return
        name,ok=QInputDialog.getText(self,'Criar grupo','Nome do novo grupo:', QLineEdit.Normal, 'Novo grupo')
        if not ok or not name.strip(): return
        color=QColorDialog.getColor(QColor('#5B8DEF'),self,'Cor do grupo')
        if not color.isValid(): return
        gid=_next_id()
        g=CommandGroup(id=gid,name=name.strip(),color=color.name())
        self._automation_map.groups[gid]=g
        self._assign_group_ids(gid, ids)

    def _assign_group(self,gid:str):
        if not self._automation_map:return
        for r in self._selected_rows():
            c=self._automation_map.commands[r]; g=self._automation_map.groups[gid]; c.group_id=gid; c.group=g.name
        self.refresh(); self.map_changed.emit("Alteração")

    def _manage_groups(self):
        if not self._automation_map or not self._automation_map.groups:
            QMessageBox.information(self, 'Grupos', 'Este mapa ainda não possui grupos. Selecione comandos e use “Adicionar ao grupo” para criar o primeiro.')
            return
        dlg=QDialog(self); dlg.setWindowTitle('Gerenciar grupos'); dlg.resize(420,360)
        lay=QVBoxLayout(dlg); lst=QListWidget(); lay.addWidget(lst)
        for g in self._automation_map.groups.values():
            it=QListWidgetItem(g.name); it.setData(Qt.UserRole,g.id); bg=_normalized_color(g.color); it.setBackground(bg); it.setForeground(_text_color_for_background(bg)); lst.addItem(it)
        row=QHBoxLayout(); rename=QPushButton('Renomear'); color=QPushButton('Alterar cor'); details=QPushButton('Descrição / atrasos'); remove=QPushButton('Excluir grupo')
        for b in (rename,color,details,remove): row.addWidget(b)
        lay.addLayout(row); buttons=QDialogButtonBox(QDialogButtonBox.Close); buttons.rejected.connect(dlg.reject); buttons.accepted.connect(dlg.accept); lay.addWidget(buttons)
        def current():
            it=lst.currentItem(); return self._automation_map.groups.get(it.data(Qt.UserRole)) if it else None
        def refresh_list():
            lst.clear()
            for g in self._automation_map.groups.values():
                it=QListWidgetItem(g.name); it.setData(Qt.UserRole,g.id); bg=_normalized_color(g.color); it.setBackground(bg); it.setForeground(_text_color_for_background(bg)); lst.addItem(it)
            self.refresh()
        def do_rename():
            g=current()
            if not g:return
            name,ok=QInputDialog.getText(dlg,'Renomear grupo','Nome:',QLineEdit.Normal,g.name)
            if ok and name.strip():
                g.name=name.strip()
                for c in self._automation_map.commands:
                    if c.group_id==g.id:c.group=g.name
                refresh_list(); self.map_changed.emit("Alteração")
        def do_color():
            g=current()
            if not g:return
            c=QColorDialog.getColor(QColor(g.color),dlg,'Cor do grupo')
            if c.isValid(): g.color=c.name(); refresh_list(); self.map_changed.emit("Alteração")
        def do_details():
            g=current()
            if not g: return
            d=QDialog(dlg); d.setWindowTitle(f'Configurar grupo — {g.name}'); d.resize(520,420)
            form=QFormLayout(d)
            desc=QLineEdit(g.description); desc.setPlaceholderText('Ex.: preparação, rotação ofensiva...')
            use=QCheckBox('Usar este grupo para sugestões de atraso'); use.setChecked(g.use_for_delay_suggestions)
            form.addRow('Descrição:',desc); form.addRow('',use)
            form.addRow(QLabel('<b>Perfil de atrasos</b>'))
            lst=QListWidget()
            for key,val in g.delay_profiles.items():
                it=QListWidgetItem(f'{key}  →  {val:.2f} s'); it.setData(Qt.UserRole,key); lst.addItem(it)
            form.addRow(lst)
            br=QHBoxLayout(); add=QPushButton('Adicionar / alterar'); rem=QPushButton('Remover perfil'); br.addWidget(add); br.addWidget(rem); form.addRow(br)
            bb=QDialogButtonBox(QDialogButtonBox.Cancel|QDialogButtonBox.Ok); bb.button(QDialogButtonBox.Ok).setText('Salvar'); bb.button(QDialogButtonBox.Cancel).setText('Cancelar'); form.addRow(bb)
            def add_profile():
                key,ok=QInputDialog.getText(d,'Perfil de atraso','Chave ou descrição (ex.: Q, Ataque carregado):',QLineEdit.Normal,'')
                if not ok or not key.strip(): return
                val,ok=QInputDialog.getDouble(d,'Perfil de atraso','Atraso sugerido em segundos:',g.delay_profiles.get(key.strip(),0.0),0.0,3600.0,3)
                if not ok:return
                g.delay_profiles[key.strip()]=val
                lst.clear()
                for k,v in g.delay_profiles.items():
                    it=QListWidgetItem(f'{k}  →  {v:.2f} s'); it.setData(Qt.UserRole,k); lst.addItem(it)
            def remove_profile():
                it=lst.currentItem()
                if it: g.delay_profiles.pop(it.data(Qt.UserRole),None); lst.takeItem(lst.row(it))
            add.clicked.connect(add_profile); rem.clicked.connect(remove_profile); bb.accepted.connect(d.accept); bb.rejected.connect(d.reject)
            if d.exec()==QDialog.Accepted:
                g.description=desc.text().strip(); g.use_for_delay_suggestions=use.isChecked(); refresh_list(); self.map_changed.emit("Alteração")

        def do_remove():
            g=current()
            if not g:return
            if QMessageBox.question(dlg,'Excluir grupo',f'Excluir o grupo “{g.name}”? Os comandos não serão excluídos.',QMessageBox.Yes|QMessageBox.Cancel,QMessageBox.Cancel)==QMessageBox.Yes:
                for c in self._automation_map.commands:
                    if c.group_id==g.id:c.group_id=''; c.group=''
                self._automation_map.groups.pop(g.id,None); refresh_list(); self.map_changed.emit("Alteração")
        rename.clicked.connect(do_rename); color.clicked.connect(do_color); details.clicked.connect(do_details); remove.clicked.connect(do_remove); dlg.exec()

    def _create_group_from_selection(self):
        if not self._automation_map:return
        name,ok=QInputDialog.getText(self,'Criar grupo','Nome do novo grupo:', QLineEdit.Normal, 'Novo grupo')
        if not ok or not name.strip():return
        color=QColorDialog.getColor(QColor('#5B8DEF'),self,'Cor do grupo')
        if not color.isValid():return
        g=CommandGroup(name=name.strip(),color=color.name()); self._automation_map.groups[g.id]=g; self._assign_group(g.id)

    def _selection_ids(self) -> set[str]:
        if not self._automation_map:
            return set()
        return {self._automation_map.commands[r].id for r in self._selected_rows() if 0 <= r < len(self._automation_map.commands)}

    def _show_more_actions(self) -> None:
        if not self._automation_map:
            return
        menu=QMenu(self)
        ids=self._selection_ids()
        copy_a=menu.addAction('Copiar')
        copy_a.setEnabled(bool(ids))
        copy_a.triggered.connect(lambda: self._copy_ids(ids))
        cut_a=menu.addAction('Recortar')
        cut_a.setEnabled(bool(ids))
        cut_a.triggered.connect(lambda: (self._copy_ids(ids), self._remove_ids(ids)))
        paste_a=menu.addAction('Colar')
        paste_a.setEnabled(bool(self._clipboard_commands) or bool(QApplication.clipboard().text().strip()))
        paste_a.triggered.connect(self._paste)
        dup_a=menu.addAction('Duplicar')
        dup_a.setEnabled(bool(ids))
        dup_a.triggered.connect(lambda: self._duplicate_ids(ids))
        menu.addSeparator()
        export_a=menu.addAction('Exportar seleção (.ascommands)')
        export_a.setEnabled(bool(ids))
        export_a.triggered.connect(lambda: self._export_selected_commands(ids))
        import_a=menu.addAction('Importar comandos (.ascommands)')
        import_a.triggered.connect(self._import_commands)
        menu.addSeparator()
        val_a=menu.addAction('Validar automação')
        val_a.triggered.connect(lambda: self.validate_requested.emit())
        test_a=menu.addAction('▶ Testar selecionados')
        test_a.setEnabled(bool(ids))
        test_a.triggered.connect(lambda: self.test_requested.emit(set(ids)))
        prev_a=menu.addAction('▷ Pré-visualizar automação')
        prev_a.triggered.connect(lambda: self.preview_requested.emit(self._automation_map))
        menu.exec(self.btn_more.mapToGlobal(self.btn_more.rect().bottomLeft()))

    def _export_selected_commands(self, ids: set[str]) -> None:
        if not self._automation_map or not ids: return
        path,_=QFileDialog.getSaveFileName(self,'Exportar comandos','comandos.ascommands','Automation Studio Commands (*.ascommands)')
        if not path: return
        if not path.lower().endswith('.ascommands'): path += '.ascommands'
        payload=self._automation_map.export_commands(ids)
        Path(path).write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')

    def _import_commands(self) -> None:
        if not self._automation_map: return
        path,_=QFileDialog.getOpenFileName(self,'Importar comandos','','Automation Studio Commands (*.ascommands);;JSON (*.json)')
        if not path: return
        try:
            payload=json.loads(Path(path).read_text(encoding='utf-8'))
            commands,groups=AutomationMap.import_commands(payload)
            # Preserva grupos locais sem sobrescrever IDs já existentes.
            for gid,g in groups.items():
                if gid not in self._automation_map.groups:
                    self._automation_map.groups[gid]=g
            rows=self._selected_rows(); anchor=max(rows) if rows else self._selection_anchor_row
            index=int(anchor)+1 if anchor is not None else len(self._automation_map.commands)
            inserted=self._automation_map.insert_commands(commands,index)
            self.refresh()
            self.table.clearSelection()
            for c in inserted:
                row=self._automation_map.commands.index(c); self.table.selectRow(row)
            self.map_changed.emit('Importar comandos')
        except Exception as exc:
            QMessageBox.warning(self,'Importar comandos',f'Não foi possível importar o arquivo:\n\n{exc}')

    def _set_buttons_enabled(self,enabled:bool):
        for b in (self.btn_add,self.btn_edit,self.btn_remove,self.btn_up,self.btn_down,self.btn_groups,self.btn_more): b.setEnabled(enabled)


# Modular export contract: this project intentionally shares private helpers
# between UI modules via import *. Export them explicitly so runtime names
# such as _PYNPUT_AVAILABLE and _default_backend are not lost.
__all__ = [name for name in globals() if not name.startswith("__")]
