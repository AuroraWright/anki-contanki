from functools import partial

from aqt import mw, qconnect 
from aqt.qt import QTableWidget, QTableWidgetItem, QComboBox, QFormLayout, QHeaderView
from aqt.qt import QAction, QDialog, QWidget, QPushButton, QCheckBox, QHBoxLayout, QVBoxLayout, QTabWidget, QIcon
from aqt.qt import QKeySequenceEdit, QSpinBox, QLabel, QGridLayout, QGroupBox, Qt, QKeySequence, QLayout, QShortcut
from aqt.theme import theme_manager
from aqt.utils import showInfo, getText, openLink

from .funcs import get_button_icon
from .consts import BUTTON_NAMES, AXES_NAMES
from .profile import *
from .actions import state_actions
from .components import ControlButton


class ContankiConfig(QDialog):
    def __init__(self, parent: QWidget, profile: Profile) -> None:
        if profile is None:
            showInfo("Controller not detected. Connect your controller using Bluetooth or USB, and press any button to initialise.")
            return
        super().__init__(parent)
        self.setWindowTitle("Contanki Options")
        self.setObjectName("Contanki Options")
        self.setFixedWidth(800)
        self.setMinimumHeight(660)

        self.profile = profile.copy()
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.tabBar = QTabWidget()
        self.tabs = dict()
        self.setup_options()
        self.setup_bindings()
        
        self.saveButton = QPushButton(self)
        self.cancelButton = QPushButton(self)
        self.helpButton = QPushButton(self)

        self.saveButton.setText('Save')
        self.cancelButton.setText('Cancel')
        self.helpButton.setText('Help')
        
        self.saveButton.clicked.connect(self.save)
        self.cancelButton.clicked.connect(self.close)
        self.helpButton.clicked.connect(self.help)

        self.buttons = QWidget()
        self.buttons.layout = QHBoxLayout()

        self.buttons.layout.addWidget(self.helpButton)
        self.buttons.layout.addWidget(self.cancelButton)
        self.buttons.layout.addWidget(self.saveButton)
        
        self.buttons.layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)
        self.buttons.setLayout(self.buttons.layout)
        
        self.layout.addWidget(self.tabBar)
        self.layout.addWidget(self.buttons)

        self.to_delete = list()

        self.setLayout(self.layout)
        self.open()

    def save(self) -> None:
        for key in self.options.keys():
            if 'mod' in key:continue
            if type(self._options[key]) == int:
                self._options[key] = self.options[key].value()
            elif type(self._options[key]) == bool:
                self._options[key] = self.options[key].isChecked()
            elif key == "Custom Actions":
                for row in range(self.options[key].rowCount()):
                    self._options[key][self.options[key].item(row, 0).text()] = self.options[key].cellWidget(row, 1).keySequence().toString()
            elif key == "Flags":
                self._options["Flags"] = []
                for flag in self.options[key].findChildren(QCheckBox):
                    if flag.isChecked():
                        self._options["Flags"].append(int(flag.objectName()))

        mw.addonManager.writeConfig(__name__, self._options)
        self.profile.move_mouse = move_mouse_build()
        self.profile.scroll = scroll_build()

        for profile in self.to_delete:
            deleteProfile(profile, False)

        states = [
            "all",
            "deckBrowser",
            "overview",
            "review",
            "question",
            "answer",
            "dialog",
        ]

        mods = {0:"No Modifier"}
        for i, mod in enumerate(self.profile.mods):
            if mod in BUTTON_NAMES[self.controller]:
                mods[i+1] = BUTTON_NAMES[self.controller][mod]
            else:
                mods[i+1] = "Modifier Unassigned"

        controls = self.tabs['bindings']

        for i, combo in enumerate(self.axes_bindings):
            self.profile.axes_bindings[i] = combo.currentText()

        for state in states:
            for mod, title in mods.items():
                for button in range(self.profile.len_buttons):
                    if button in self.profile.mods or button not in controls.stateTabs[state].modTabs[mod].controls:
                        continue
                    action = controls.stateTabs[state].modTabs[mod].controls[button].currentText()
                    if 'inherit' in action:
                        action = ""
                    self.profile.updateBinding(state, mod, button, action, build_actions=False)

        self.profile.buildActions()
        self.profile.controller = self.corner.currentText()
        mw.contanki.update_profile(self.profile)
        updateControllers(self.controller, self.profile.name)
        self.profile.save()
        self.close()

    def help(self) -> None:
        openLink("https://github.com/roxgib/anki-contanki")

    def changeProfile(self, profile: Profile = None) -> None:
        if type(profile) == str:
            profile = getProfile(profile)
        elif not profile or type(profile) != Profile:
            profile = getProfile(self._profile.currentText())
        if not profile:
            return
        self.profile = profile.copy()
        self.refresh_bindings()

    def addProfile(self) -> None:
        new_profile = createProfile()
        if not new_profile: return
        self._profile.addItem(new_profile.name)
        self._profile.setCurrentText(new_profile.name)

    def delete_profile(self) -> None:
        if len(self._profile) == 1:
            showInfo("You can't delete the last profile")
            return
        self.to_delete.append(self.profile.name)
        self._profile.removeItem(self._profile.currentIndex())

    def rename_profile(self) -> None:
        old_name = self.profile.name
        new_name, success = getText("Please enter a new profile name", self, title = "New Name")
        if not success:
            return
        self._profile.setItemText(self._profile.currentIndex(), new_name)
        self.profile.name = new_name
        self.to_delete.append(old_name)

    def findCustomActions(self) -> None:
        shortcuts = [shortcut for name, shortcut in self._options["Custom Actions"].items()]
        for action in mw.findChildren(QAction):
            if (scut := action.shortcut().toString()) != "" and scut not in shortcuts:
                if action.objectName() != "":
                    self._options["Custom Actions"][action.objectName()] = scut
                else:
                    self._options["Custom Actions"][scut] = scut

        for scut in mw.findChildren(QShortcut):
            if scut.key().toString() != "":
                self._options["Custom Actions"][scut.key().toString()] = scut.key().toString()


    def setup_options(self) -> None:
        tab = QWidget()
        self.tabs['main'] = tab
        tab.layout = QGridLayout(tab)
        tab.layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)

        main                    = QWidget()
        mouse                   = QWidget()
        flags                   = QGroupBox('Flags', self.tabs['main'])
        form                    = QWidget()
        axes                    = QWidget()
        axes_buttons            = QWidget()

        main.layout             = QVBoxLayout()
        mouse.layout            = QGridLayout()
        flags.layout            = QFormLayout()
        form.layout             = QFormLayout()
        axes.layout             = QFormLayout()
        axes_buttons.layout     = QFormLayout()
        
        profileBar = QWidget()
        profileBar.layout = QHBoxLayout()
        profileBar.layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)
        self._profile = profileCombo = QComboBox(tab)
        profileCombo.addItems(p_list := getProfileList(include_defaults=False))
        profileCombo.setCurrentIndex(p_list.index(self.profile.name))
        profileCombo.currentIndexChanged.connect(self.changeProfile)
        profileBar.layout.addWidget(QLabel("Profile", tab))
        profileBar.layout.addWidget(profileCombo)
        
        add_button = QPushButton('Add Profile', tab)
        delete_button = QPushButton('Delete Profile', tab)
        rename_button = QPushButton('Rename Profile', tab)
        
        add_button.clicked.connect(self.addProfile)
        delete_button.clicked.connect(self.delete_profile)
        rename_button.clicked.connect(self.rename_profile)
        
        profileBar.layout.addWidget(add_button)
        profileBar.layout.addWidget(delete_button)
        profileBar.layout.addWidget(rename_button)
        
        profileBar.setLayout(profileBar.layout)

        self._options = mw.addonManager.getConfig(__name__)
        self.options = dict()

        flags.layout.setVerticalSpacing(20)
        form.layout.setVerticalSpacing(20)

        for key, value in self._options.items():
            if type(value) == int:
                self.options[key] = QSpinBox(tab)
                self.options[key].setMinimumWidth(70)
                self.options[key].setValue(value)
                form.layout.addRow(key, self.options[key])

            elif type(value) == bool:
                self.options[key] = QCheckBox(key, tab)
                self.options[key].setChecked(self._options[key])
                form.layout.addRow(self.options[key])
            elif key == "Custom Actions":
                container = QWidget()
                container.layout = QGridLayout()
                container.layout.addWidget(QLabel("Custom Actions"), 0, 0, 1, 2)
                self.options[key] = QTableWidget(len(value),2,tab)
                self.options[key].setHorizontalHeaderLabels(["Name", "Shortcut"])
                for row, (_key, _value) in enumerate(value.items()):
                    self.options[key].setItem(row, 0, QTableWidgetItem(_key,0))
                    self.options[key].setCellWidget(row, 1, QKeySequenceEdit(QKeySequence(_value)))
                self.options[key].horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
                self.options[key].setColumnWidth(1, 70)
                container.layout.addWidget(self.options[key], 1, 0, 1, 2)
                add_button = QPushButton("Add")
                delete_button = QPushButton("Delete")
                
                def add_row():
                    if self.options[key].selectedIndexes():
                        current_row = self.options[key].currentRow() + 1
                    else:
                        current_row = self.options[key].rowCount()
                    self.options[key].insertRow(current_row)
                    self.options[key].setItem(current_row, 0, QTableWidgetItem("New Action",0))
                    self.options[key].setCellWidget(current_row, 1, QKeySequenceEdit(QKeySequence("")))
                    self.options[key].setCurrentCell(current_row, 0)

                def remove_row():
                    if self.options[key].selectedIndexes():
                        current_row = self.options[key].currentRow()
                    else:
                        current_row = self.options[key].rowCount() - 1
                    self.options[key].removeRow(current_row)

                qconnect(add_button.pressed, add_row)
                qconnect(delete_button.pressed, remove_row)
                qconnect(self.options[key].itemChanged, self.refresh_bindings)

                container.layout.addWidget(add_button, 2, 0)
                container.layout.addWidget(delete_button, 2, 1)
                container.setLayout(container.layout)
                tab.layout.addWidget(container,1,2,2,1)
            elif key == "Flags":
                self.options[key] = flags
                for flag in mw.flags.all():
                    check = QCheckBox(flag.label, tab)
                    check.setIcon(theme_manager.icon_from_resources(flag.icon))
                    check.setObjectName(str(flag.index))
                    if flag.index in self._options["Flags"]:
                        check.setChecked(True)
                    flags.layout.addWidget(check)
                flags.setLayout(flags.layout)
                tab.layout.addWidget(self.options[key],2,1)
            else: continue

        _, cbuttons = zip(*BUTTON_NAMES[self.profile.controller].items())

        label = QLabel("Modifiers")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        form.layout.setWidget(form.layout.rowCount(), QFormLayout.ItemRole.SpanningRole, label)

        self.options['mod0'] = QComboBox()
        for cbutton in cbuttons:
            self.options['mod0'].addItem(QIcon(get_button_icon(self.profile.controller, cbutton)),cbutton)
        self.options['mod0'].setCurrentIndex(self.profile.mods[0])
        qconnect(self.options['mod0'].currentIndexChanged, self.update_modifiers)
        form.layout.setWidget(form.layout.rowCount(), QFormLayout.ItemRole.SpanningRole, self.options['mod0'])

        self.options['mod1'] = QComboBox()
        for cbutton in cbuttons:
            self.options['mod1'].addItem(QIcon(get_button_icon(self.profile.controller, cbutton)),cbutton)
        self.options['mod1'].setCurrentIndex(self.profile.mods[1])
        qconnect(self.options['mod1'].currentIndexChanged, self.update_modifiers)
        form.layout.setWidget(form.layout.rowCount(), QFormLayout.ItemRole.SpanningRole, self.options['mod1'])

        form.setLayout(form.layout)
        tab.layout.addWidget(form,1,0,2,1)

        # Axes
        
        self.axes_bindings = list()
        self.axes_button_bindings = list()
        for axis, name in AXES_NAMES[self.profile.controller].items():
            button = QComboBox()
            button.addItems([
                "Unassigned", 
                "Buttons",
                "Cursor Horizontal",
                "Cursor Vertical",
                "Scroll Horizontal",
                "Scroll Vertical",
            ])
            button.setCurrentText(self.profile.axes_bindings[axis])
            self.axes_bindings.append(button)
            label = QLabel()
            pixmap = get_button_icon(self.profile.controller, name)
            label.setPixmap(pixmap.scaled(40, 40, aspectRatioMode=Qt.AspectRatioMode.KeepAspectRatio))
            qconnect(button.currentIndexChanged, self.refresh_bindings)
            axes.layout.addRow(label, button)
            
        axes.setLayout(axes.layout)
        tab.layout.addWidget(axes,1,1)

        # Finish

        tab.layout.addWidget(profileBar,0,0,1,3)
        tab.setLayout(tab.layout)
        self.tabBar.addTab(tab, "Options")

    def get_custom_actions(self):
        table = self.options["Custom Actions"]
        return [table.item(row, 0).text() for row in range(table.rowCount())]

    def update_modifiers(self) -> None:
        _, cbuttons = zip(*BUTTON_NAMES[self.profile.controller].items())
        self.profile.changeMod(self.profile.mods[0], self.options['mod0'].currentIndex())
        self.profile.changeMod(self.profile.mods[1], self.options['mod1'].currentIndex())
        self.refresh_bindings()

    def setup_bindings(self):
        tab = self.tabs['bindings'] = QTabWidget()
        
        corner = self.corner = QComboBox()
        controllers = getControllerList()
        for controller in controllers:
            corner.addItem(controller)
        controller = self.profile.controller
        corner.setCurrentIndex(controllers.index(controller))
        self.controller = controller = corner.currentText()
        corner.currentIndexChanged.connect(self.refresh_bindings)
        self.tabs['bindings'].setCornerWidget(corner)

        mods = {0:"Default"}
        for i, mod in enumerate(self.profile.mods):
            if mod in BUTTON_NAMES[self.controller]:
                mods[i+1] = BUTTON_NAMES[self.controller][mod]
            else:
                mods[i+1] = "Modifier Unassigned"

        tab.stateTabs = dict()
        for state, title in states.items():
            tab.stateTabs[state] = QTabWidget()
            tab.stateTabs[state].setObjectName(state)
            tab.stateTabs[state].modTabs = dict()
            for mod, mTitle in mods.items():
                tab.stateTabs[state].modTabs[mod] = widget = QWidget()
                widget.setObjectName(str(mod))
                widget.layout = QGridLayout()
                widget.controls = {
                    control: ControlButton(button, self.profile.controller, actions = state_actions[state])
                    for control, button 
                    in BUTTON_NAMES[self.profile.controller].items()
                }
                row = col = 0
                for button, control in widget.controls.items():
                    control.action.addItems(self.get_custom_actions())
                    mw.contanki.register_icon(button, control.show_pressed, control.show_not_pressed)
                    if button in self.profile.bindings[state][mod]:
                        if (text := self.profile.bindings[state][mod][button]):
                            control.action.setCurrentText(text)
                    control.update = partial(self.updateBinding, state, mod, button)
                    qconnect(control.action.currentIndexChanged, control.update)
                    if button in self.profile.mods: continue
                    if button >= 100:
                        if not ((button - 100) // 2) < len(self.axes_bindings):
                            continue
                        if self.axes_bindings[(button - 100) // 2].currentText() != "Buttons":
                            continue
                    widget.layout.addWidget(control, row, col)
                    if col == 2:
                        row += 1
                        col = 0
                    else:
                        col += 1
                widget.setLayout(widget.layout)
                if mod == 0:
                    tab.stateTabs[state].addTab(widget, "No Modifier")
                else:
                    tab.stateTabs[state].addTab(widget, QIcon(get_button_icon(controller, mods[mod])), mTitle)
            tab.stateTabs[state].setTabPosition(QTabWidget.TabPosition.South)
            tab.addTab(tab.stateTabs[state], title)
        self.updateInheritance()
        self.tabBar.addTab(tab, "Controls")

    def refresh_bindings(self) -> None:
        current_tab = self.tabBar.currentIndex()
        self.controller = self.profile.controller = self.corner.currentText()
        self.tabBar.removeTab(1)
        self.setup_bindings()
        self.tabBar.setCurrentIndex(current_tab)
        self.resize(self.sizeHint())

    def updateBinding(self, state, mod, button):
        action = self.tabs['bindings'].stateTabs[state].modTabs[mod].controls[button].currentText()
        self.profile.updateBinding(state, mod, button, action)
        self.updateInheritance()

    def updateInheritance(self):
        for state in states:
            for mod in range(len(self.profile.mods) + 1):
                for button, control in self.tabs['bindings'].stateTabs[state].modTabs[mod].controls.items():
                    if button in self.profile.mods:
                        continue
                    inherited = None
                    if state != 'all' and button in (b := self.profile.bindings["all"][mod]):
                        inherited = b[button]
                    if (state == "question" or state == "answer") and button in self.profile.bindings["review"][mod]:
                        if action := self.profile.bindings["review"][mod][button]:
                            inherited = action
                    if inherited:
                        control.action.setItemText(0, inherited + " (inherit)")
                    else:
                        control.action.setItemText(0, "")


states = {
    "all": "Default",
    "deckBrowser": "Deck Browser", 
    "overview": "Deck Overview", 
    "review": "Review",
    "question": "Question", 
    "answer": "Answer",
    "dialog": "Dialogs",
}