
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QColor
from PyQt5.QtWidgets import (QApplication, QComboBox, QDialog, QGridLayout, QLayout,
                            QRadioButton, QGroupBox, QLabel, QLineEdit,QPushButton, QSpinBox, QHBoxLayout)

import store_and_load
import os
# import warnings
# warnings.filterwarnings("ignore")
# warnings.catch_warnings
import copy
import custom_color_functions

# Used in fetching and processing metadata
from random import choice
from typing import Callable

VERSION_NUMBER = '1.2.1'
FONT_SIZE = 12

COLOR_TO_RGB = {'gray': '(170,170,170, 255)', 'purple':'(160,32,240, 255)', 'blue':'(100,100,255, 255)',
                    'green':'(60,179,113, 255)', 'orange':'(255,127,80, 255)', 'red': '(215,40,40, 255)',
                    'yellow': '(255,215,0, 255)', 'pink': '(255,105,180, 255)', 'cyan' : '(0,220,255, 255)'}
WIDGET_SELECTED = None


''' This class will be used for the dropdown menu that can assign a scoring decision to every cell 
    from an annotation layer or phenotype'''
class StatusCombo(QComboBox):
    def __init__(self, parent, userInfo, color_mode = "light"):
        super(QComboBox, self).__init__(parent)
        self.user_data = userInfo
        self.color_mode = color_mode
        # self.setVisible(False)
        
        if color_mode == 'light':
            self.setStyleSheet(f"background-color: rgba(255,255,255,255);color: rgba(0,0,0,255); selection-background-color: rgba(255,255,255,255);")
            self.addItem("Don't assign") 
            self.setItemData(0,QColor(255,255,255,255),Qt.BackgroundRole)
            self.setItemData(0,QColor(0,0,0,255),Qt.ForegroundRole)
        elif color_mode == 'dark':
            self.setStyleSheet(f"background-color: rgba{self.user_data.statuses_rgba['Unseen']};color: white; selection-background-color: rgba(0,0,0,20);")
        else:
            raise ValueError("Expected the 'color' parameter to be 'light' or 'dark' ")
        self.add_scoring_decisions()
        self.activated.connect(self.set_bg)

    def add_scoring_decisions(self):
        for pos,status in enumerate(list(self.user_data.statuses.keys())):
            if self.color_mode == 'light':
                pos = pos+1
            elif self.color_mode == 'dark':
                pass
            else:
                raise ValueError("Expected the 'color' parameter to be 'light' or 'dark' ")
            self.addItem(status)
            self.setItemData(pos,QColor(*self.user_data.statuses_rgba[status]),Qt.BackgroundRole)
            self.setItemData(pos,QColor(255,255,255,255),Qt.ForegroundRole)
    
    def reset_items(self):
        for i in range(1,self.count()):
            self.removeItem(1)
        self.add_scoring_decisions()

    def set_bg(self):
        status = self.currentText()
        if self.color_mode == 'light':
            if status not in self.user_data.statuses_rgba.keys():
                self.setStyleSheet(f"background-color: rgba(255,255,255,255);color: rgb(0,0,0); selection-background-color: rgba(255,255,255,140);")
            else:
                self.setStyleSheet(f"background-color: rgba{self.user_data.statuses_rgba[status]};color: rgb(0,0,0);selection-background-color: rgba(255,255,255,140);")
        elif self.color_mode =='dark':
            self.setStyleSheet(f"background-color: rgba{self.user_data.statuses_rgba[status]}; selection-background-color: rgba(0,0,0,30);")
        else:
            raise ValueError("Expected the 'color' parameter to be 'light' or 'dark' ")

''' A QDialog that the user can interact with to select scoring decision names, color values,
    and keybindings. Loads with defaults initialized in the user data class'''
class ChannelDialog(QDialog):
    def __init__(self, app: QApplication, user_data: store_and_load.userPresets, 
                 check_layout : QGridLayout, check_group : QGroupBox, check_group_create: Callable):
        super(ChannelDialog, self).__init__()
        self.app = app
        self.user_data = user_data
        self.channelColors = copy.copy(user_data.channelColors)
        self.check_layout = check_layout
        self.check_group = check_group
        self.check_group_create = check_group_create
       
        # Arrange title bar buttons
        self.setWindowFlag(Qt.WindowMinimizeButtonHint, True)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        self.setWindowFlag(Qt.WindowTitleHint,False)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint,False)
        self.setWindowTitle('Select Channels')
        self.setWindowIcon(QIcon('data/mghiconwhite.png'))   
        # self.setStyleSheet("background-color: '#daeef0'")     

        self.save_button = QPushButton("Save and exit")
        self.add_button = QPushButton("Add new")
        self.remove_button = QPushButton("Remove last")
        self.add_button.pressed.connect(self.add_channel)
        self.remove_button.pressed.connect(self.remove_channel)
        self.save_button.pressed.connect(self.save)
        self.channel_entry = QLineEdit(); self.channel_entry.setPlaceholderText("Channel name")
        self.position_spin = QSpinBox(); self.position_spin.setRange(0,len(self.channelColors))
        self.position_spin.setValue(len(self.channelColors))


        self.buttonGroup = QGroupBox()
        # self.buttonGroup.setStyleSheet("background-color: '#ededed'")
        self.buttonBoxLayout = QGridLayout()
        self.buttonBoxLayout.addWidget(self.channel_entry,0,0)
        self.buttonBoxLayout.addWidget(self.position_spin,1,0)
        self.buttonBoxLayout.addWidget(self.add_button, 0,1)
        self.buttonBoxLayout.addWidget(self.remove_button, 1,1)
        self.buttonBoxLayout.addWidget(self.save_button, 2,0,1,2)
        self.buttonGroup.setLayout(self.buttonBoxLayout)

        
        # Dynamically assemble channel names labels
        self.channelGroup = QGroupBox("Channel names and order in the image data")
        # self.channelGroup.setStyleSheet("background-color: '#ededed'")
        self.channelBoxLayout = QGridLayout()
        self.make_labels()

        # Make top area
        self.overrideGroup = QGroupBox("Override Viewer detected metadata?")
        # self.overrideGroup.setStyleSheet("background-color: '#ededed'")
        self.radio1 = QRadioButton("Yes, use the selections below")
        self.radio2 = QRadioButton("No, let the Viewer pick")

        # self.radio1.setStyleSheet(open("data/style.css").read())
        self.overrideLayout = QHBoxLayout()
        self.overrideLayout.addWidget(self.radio1)
        self.overrideLayout.addWidget(self.radio2)
        self.overrideGroup.setLayout(self.overrideLayout)
        self.radio2.setChecked(True)
        
        self.layout = QGridLayout()
        self.layout.addWidget(self.overrideGroup,0,0)
        self.layout.addWidget(self.channelGroup, 1,0)
        self.layout.addWidget(self.buttonGroup, 2,0)
        self.layout.setSizeConstraint(QLayout.SetFixedSize) # Allows window to resize to shrink when widgets are removed
        self.setLayout(self.layout)
        self.show()
    
    def make_labels(self):
        for i in reversed(range(self.channelBoxLayout.count())): 
            self.channelBoxLayout.itemAt(i).widget().setParent(None)
        row=0
        for pos, chn in enumerate(list((self.channelColors.keys()))):
            c = QLabel(str(chn))
            n = QLabel(str(pos))
            self.channelBoxLayout.addWidget(c,row,0 )
            self.channelBoxLayout.addWidget(n,row,1 )
            row+=1
        # self.decision_label.setText(display_str)
        self.channelGroup.setLayout(self.channelBoxLayout)
        self.channelBoxLayout.update()
        self.app.processEvents()
    
    def add_channel(self):
        def _setWidgetColorBackground(widg, color):
            widg.setStyleSheet(f"background-color: {color}")

        new_chn = self.channel_entry.text()
        self.channel_entry.clear()
        new_pos = self.position_spin.value()

        if len(new_chn) <1:
            return None

        if new_chn in self.channelColors.keys():
            _setWidgetColorBackground(self.channel_entry, "#ff5555")
            QTimer.singleShot(800, lambda:_setWidgetColorBackground(self.channel_entry, ""))
            
            for i in range(self.channelBoxLayout.count()):
                widg = self.channelBoxLayout.itemAt(i).widget()
                if widg.text() == new_chn:
                    _setWidgetColorBackground(widg, "#ff5555")
                    QTimer.singleShot(800, lambda: _setWidgetColorBackground(widg, ""))
                    widg2 = self.channelBoxLayout.itemAt(i+1).widget()
                    _setWidgetColorBackground(widg2, "#ff5555")
                    QTimer.singleShot(800, lambda: _setWidgetColorBackground(widg2, ""))
                    break
            return None
        
        unused_colors = copy.copy(self.user_data.available_colors)
        for col in self.channelColors.values():
            if col in unused_colors:
                unused_colors.remove(col)

        # For this new fluor, give it a color
        if len(unused_colors) < 1:
            random_color = choice(self.user_data.available_colors)
        else:
            random_color = choice(unused_colors)

        # Add new channel to dictionary
        self.channelColors[new_chn] = random_color
        self.make_labels()
        self.position_spin.setRange(0,len(self.channelColors))
        self.position_spin.setValue(new_pos+1)

    def remove_channel(self):
        if len(self.channelColors) <=1:
            return False
        
        x = self.channelColors.popitem()
        self.make_labels()
        self.position_spin.setRange(0,len(self.channelColors))
        self.position_spin.setValue(len(self.channelColors))

    def save(self):
        self.user_data.channelColors = self.channelColors
        self.user_data.channels = list(self.channelColors.keys())
        self.user_data.channelOrder = dict(zip(self.user_data.channels,range(len(self.user_data.channels))))
        self.user_data.remake_viewsettings()

        # self.user_data.remake_channelOrder()
        #TODO set channel widgets in main UI

        for i in reversed(range(self.check_layout.count())): 
            self.check_layout.itemAt(i).widget().setParent(None)
        self.check_layout, self.check_group = self.check_group_create(self.check_layout, self.check_group)
        self.check_group.update()
        self.app.processEvents()
        self.close()


''' A QDialog that the user can interact with to select scoring decision names, color values,
    and keybindings. Loads with defaults initialized in the user data class'''
class ScoringDialog(QDialog):
    def __init__(self, app: QApplication, user_data: store_and_load.userPresets, widget_dict: dict[str:QComboBox]):
        super(ScoringDialog, self).__init__()
        self.app = app
        self.user_data = user_data
        self.statuses_hex = copy.copy(user_data.statuses_hex)
        self.statuses = copy.copy(user_data.statuses)
        self.available_statuses_keybinds = copy.copy(user_data.available_statuses_keybinds)
        self.pheno_widget = widget_dict["pheno_widget"]
        self.anno_widget = widget_dict["anno_widget"]


        # Arrange title bar buttons
        self.setWindowFlag(Qt.WindowMinimizeButtonHint, True)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        self.setWindowFlag(Qt.WindowTitleHint,False)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint,False)
        self.setWindowTitle('Scoring preferences')
        self.setWindowIcon(QIcon('data/mghiconwhite.png'))        

        self.decisionBox = QGroupBox("Scoring decisions, colors, and keybinds")
        self.buttonBox = QGroupBox()
        self.save_button = QPushButton("Save and exit")
        self.add_button = QPushButton("Add new")
        self.remove_button = QPushButton("Remove last")
        self.add_button.pressed.connect(self.add_label)
        self.remove_button.pressed.connect(self.remove_label)
        self.save_button.pressed.connect(self.save)
        self.decision_entry = QLineEdit(); self.decision_entry.setPlaceholderText("Scoring decision")
        self.color_entry = QLineEdit(); self.color_entry.setPlaceholderText("Color")
        self.keybind_widget = QComboBox()
        self.keybind_widget.addItems([x.upper() for x in self.available_statuses_keybinds])


        self.saveBoxLayout = QGridLayout()
        self.saveBoxLayout.addWidget(self.decision_entry,0,0)
        self.saveBoxLayout.addWidget(self.color_entry,1,0)
        self.saveBoxLayout.addWidget(self.keybind_widget,2,0)

        self.saveBoxLayout.addWidget(self.add_button, 0,1)
        self.saveBoxLayout.addWidget(self.remove_button, 1,1)
        self.saveBoxLayout.addWidget(self.save_button, 2,1)
        # self.saveBox.setLayout(self.saveBoxLayout)

        self.decisionBoxLayout = QGridLayout()
        # self.decision_label = QLabel("")
        self.make_labels()
        # self.decisionBoxLayout.addWidget(self.decision_label)

        # self.decisionBox.setLayout(self.decisionBoxLayout)
        
        self.buttonBox.setLayout(self.saveBoxLayout)
        self.layout = QGridLayout()
        self.layout.addWidget(self.decisionBox, 0 ,0)
        self.layout.addWidget(self.buttonBox, 1,0)
        self.layout.setSizeConstraint(QLayout.SetFixedSize) # Allows window to resize to shrink when widgets are removed
        self.setLayout(self.layout)
        self.show()

    def make_labels(self):

        for i in reversed(range(self.decisionBoxLayout.count())): 
            self.decisionBoxLayout.itemAt(i).widget().setParent(None)
        row=0
        for decision, color in self.statuses_hex.items():
            keybind = self.statuses[decision]
            d = QLabel(decision)
            c = QLabel(f"<font color='{color}'>{color}</font>")
            k = QLabel(f'{keybind.upper()}')
            self.decisionBoxLayout.addWidget(d,row,0 )
            self.decisionBoxLayout.addWidget(c,row,1 )
            self.decisionBoxLayout.addWidget(k,row,2 )
            row+=1
        # self.decision_label.setText(display_str)
        self.decisionBox.setLayout(self.decisionBoxLayout)
        self.decisionBoxLayout.update()
        self.app.processEvents()

    def add_label(self):

        new_color = self.color_entry.text().replace(" ","").strip('"')
        new_scoring_decision = self.decision_entry.text()

        if custom_color_functions.isColor(new_color) and len(new_scoring_decision) >=1:
            try:
                new_color = custom_color_functions.colormap[new_color] # in case the user passed a string name for a color
            except KeyError:
                pass
            try:
                new_color = '#%02x%02x%02x' % new_color
                if not custom_color_functions.isColor(new_color):
                    raise TypeError
            except TypeError:
                pass
            
            # now we should have a hex value

            # self.available_statuses_keybinds.remove(new_keybind)
            self.statuses_hex[new_scoring_decision] = new_color
            try:
                # If there is already a color and keybind for the scoring decision, need to add the keybind back to the list of available
                # The rest will update in place
                self.keybind_widget.addItem(self.statuses[new_scoring_decision].upper())
            except KeyError:
                pass
            self.statuses[new_scoring_decision] = self.keybind_widget.currentText()
            self.keybind_widget.removeItem(self.keybind_widget.currentIndex())
            self.decision_entry.clear()
            self.color_entry.clear()
            self.make_labels()
        
    def remove_label(self):
        if len(self.statuses) <=1:
            return False
        
        x = self.statuses.popitem()
        self.keybind_widget.insertItem(0, x[1].upper())
        self.statuses_hex.popitem()
        self.make_labels()

    def save(self):
        self.user_data.statuses = self.statuses
        self.user_data.statuses_hex = self.statuses_hex
        self.user_data.available_statuses_keybinds = [self.keybind_widget.itemText(i) for i in range(self.keybind_widget.count())]
        self.user_data.remake_rgba()
        self.pheno_widget.reset_items()
        self.anno_widget.reset_items()
        self.close()
