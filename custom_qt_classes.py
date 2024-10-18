
from qtpy.QtCore import Qt, QTimer
from qtpy.QtGui import QIcon, QColor, QLinearGradient, QFont
from qtpy.QtWidgets import (QApplication, QComboBox, QDialog, QGridLayout, QLayout, QSlider, QDoubleSpinBox, QFileDialog,
                            QRadioButton, QGroupBox, QLabel, QLineEdit,QPushButton, QSpinBox, QHBoxLayout)
from qtpy import QtGui, QtCore
from napari import Viewer
import os
import pandas as pd
# import warnings
# warnings.filterwarnings("ignore")
# warnings.catch_warnings
import copy
# Used in fetching and processing metadata
from random import choice
from typing import Callable
from itertools import product

from storage_classes import SessionVariables, GVData
import custom_color_functions
from custom_color_functions import colormap_titled as hexcd


VERSION_NUMBER = '1.3.5'
FONT_SIZE = 12


''' This class will be used for the dropdown menu that can assign a scoring decision to every cell 
    from an annotation layer or phenotype'''
class StatusCombo(QComboBox):
    def __init__(self, parent, gvdata, color_mode = "light"):
        super(QComboBox, self).__init__(parent)
        self.gvdata = gvdata
        self.color_mode = color_mode
        # self.setVisible(False)
        
        if color_mode == 'light':
            self.setStyleSheet(f"background-color: rgba(255,255,255,255);color: rgba(0,0,0,255); selection-background-color: rgba(255,255,255,255);")
            self.addItem("Don't assign") 
            self.setItemData(0,QColor(255,255,255,255),Qt.BackgroundRole)
            self.setItemData(0,QColor(0,0,0,255),Qt.ForegroundRole)
        elif color_mode == 'dark':
            self.setStyleSheet(f"background-color: rgba{self.gvdata.statuses_rgba['Unseen']};color: white; selection-background-color: rgba(0,0,0,20);")
        else:
            raise ValueError("Expected the 'color' parameter to be 'light' or 'dark' ")
        self.add_scoring_decisions()
        self.activated.connect(self.set_bg)

    def add_scoring_decisions(self):
        for pos,status in enumerate(list(self.gvdata.statuses.keys())):
            if self.color_mode == 'light':
                pos = pos+1
            elif self.color_mode == 'dark':
                pass
            else:
                raise ValueError("Expected the 'color' parameter to be 'light' or 'dark' ")
            self.addItem(status)
            self.setItemData(pos,QColor(*self.gvdata.statuses_rgba[status]),Qt.BackgroundRole)
            self.setItemData(pos,QColor(255,255,255,255),Qt.ForegroundRole)
    
    def reset_items(self):
        for i in range(1,self.count()):
            self.removeItem(1)
        self.add_scoring_decisions()

    def set_bg(self):
        status = self.currentText()
        if self.color_mode == 'light':
            if status not in self.gvdata.statuses_rgba.keys():
                self.setStyleSheet(f"background-color: rgba(255,255,255,255);color: rgb(0,0,0); selection-background-color: rgba(255,255,255,140);")
            else:
                self.setStyleSheet(f"background-color: rgba{self.gvdata.statuses_rgba[status]};color: rgb(0,0,0);selection-background-color: rgba(255,255,255,140);")
        elif self.color_mode =='dark':
            self.setStyleSheet(f"background-color: rgba{self.gvdata.statuses_rgba[status]}; selection-background-color: rgba(0,0,0,30);")
        else:
            raise ValueError("Expected the 'color' parameter to be 'light' or 'dark' ")

''' A QDialog that the user can interact with to select scoring decision names, color values,
    and keybindings. Loads with defaults initialized in the user data class'''
class ChannelDialog(QDialog):
    def __init__(self, parent, app: QApplication, gvdata: GVData, 
                 check_layout : QGridLayout, check_group : QGroupBox, check_group_create: Callable):
        super().__init__(parent)
        self.app = app
        self.gvdata = gvdata
        self.channelColors = copy.copy(gvdata.channelColors)
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
        
        unused_colors = copy.copy(self.gvdata.available_colors)
        for col in self.channelColors.values():
            if col in unused_colors:
                unused_colors.remove(col)

        # For this new fluor, give it a color
        if len(unused_colors) < 1:
            random_color = choice(self.gvdata.available_colors)
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
        self.gvdata.channelColors = self.channelColors
        self.gvdata.channels = list(self.channelColors.keys())
        self.gvdata.channelOrder = dict(zip(self.gvdata.channels,range(len(self.gvdata.channels))))
        self.gvdata.remake_viewsettings()

        # self.gvdata.remake_channelOrder()
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
    def __init__(self, parent, app: QApplication, gvdata: GVData, widget_dict: dict[str:QComboBox]):
        super().__init__(parent)
        self.app = app
        self.gvdata = gvdata
        self.statuses_hex = copy.copy(gvdata.statuses_hex)
        self.statuses = copy.copy(gvdata.statuses)
        self.available_statuses_keybinds = copy.copy(gvdata.available_statuses_keybinds)
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
        self.app.processEvents()

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
        # self.app.processEvents()

    def add_label(self):

        new_color = self.color_entry.text().replace(" ","").strip('"')
        new_scoring_decision = self.decision_entry.text()

        if custom_color_functions.isColor(new_color) and len(new_scoring_decision) >=1:
            try:
                new_color = custom_color_functions.colormap[new_color] # in case the user passed a string name for a color
            except KeyError:
                pass
            try:
                new_color = '#%02x%02x%02x' % new_color # Hex conversion
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
        self.gvdata.statuses = self.statuses
        self.gvdata.statuses_hex = self.statuses_hex
        self.gvdata.available_statuses_keybinds = [self.keybind_widget.itemText(i) for i in range(self.keybind_widget.count())]
        self.gvdata.remake_rgba()
        self.pheno_widget.reset_items()
        self.anno_widget.reset_items()
        self.close()

'''
    https://stackoverflow.com/questions/42820380/use-float-for-qslider
'''
class DoubleSlider(QSlider):

    def __init__(self, smin=0, smax = 255, *args, **kargs):
        super(DoubleSlider, self).__init__( *args, **kargs)
        self._min = smin
        self._max = smax
        self.interval = 0.01
        self._range_adjusted()

    def setValue(self, value):
        index = round((value - self._min) / self.interval)
        return super(DoubleSlider, self).setValue(index)

    def value(self):
        return self.index * self.interval + self._min

    @property
    def index(self):
        return super(DoubleSlider, self).value()

    def setIndex(self, index):
        return super(DoubleSlider, self).setValue(index)

    def setMinimum(self, value):
        self._min = value
        self._range_adjusted()

    def setMaximum(self, value):
        self._max = value
        self._range_adjusted()

    def setInterval(self, value):
        # To avoid division by zero
        if not value:
            raise ValueError('Interval of zero specified')
        self.interval = value
        self._range_adjusted()

    def _range_adjusted(self):
        number_of_steps = int((self._max - self._min) / self.interval)
        super(DoubleSlider, self).setMaximum(number_of_steps)

# from galleryViewer import GView
''' A QDialog that the user can interact with to adjust the Napari view settings while running the app.'''
class ViewSettingsDialog(QDialog):
    def __init__(self, parent, gview):
        super().__init__(parent)
        self.gview = gview # galleryViewer.py GView -- can't import here for typing due to circular import
        self.gvdata = gview.data
        self.session = gview.session # 
        self.viewer = gview.viewer
        self.viewsettings = gview.session.view_settings # Dictionary of viewsettings. E.g., for each chn,  '[chn] gamma' : 0.5, '[chn] whitein':255, '[chn] blackin':0
        self.original_viewsettings = copy.deepcopy(self.viewsettings)
        self.last_adjustment = None
        self.target_override = False # Used in restore function to one by one trigger the appropriate fluors to re-adjust
        self.sliders = {}
        self.spin_boxes = {}
        self.labels = {}
        self.create_color_combos()

        # Arrange title bar buttons
        self.setWindowFlag(Qt.WindowMinimizeButtonHint, True)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        self.setWindowFlag(Qt.WindowTitleHint,False)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint,False)
        self.setWindowTitle('Edit view settings')
        self.setWindowIcon(QIcon('data/mghiconwhite.png')) 

        # Create gamma and contrast sliders for each fluor in the user data
        #TODO Consider importing a custom double-slider to get two values at once. Would make this much easier.
        # Not built in though, but there's a class posted somewhere on StackOverflow. I forget why I didn't try to do this already
        self.vsBox = QGroupBox()
        self.vsLayout = QGridLayout()
        row = -1 ; col=0
        for fluor, setting in product(self.gvdata.channels, ("gamma","black-in", "white-in")):
            
            d = QDoubleSpinBox(self) 
            match setting:
                case "gamma":
                    s = DoubleSlider(0.01,1)
                    d.setRange(0.01,1)
                    d.setSingleStep(0.01)
                    row+=1
                    col=0
                    l = QLabel(fluor)
                    l.setFont(self.gvdata.user.fonts.medium)
                    l.setAlignment(Qt.AlignRight)
                    l.setStyleSheet(f"QLabel{{ color : {self.ccbs[fluor].text_color}; \
                                              font-size: 18pt; \
                                              background-color: {self.gvdata.channelColors[fluor]} ; \
                                              }}")
                    self.labels[fluor] = l
                    self.vsLayout.addWidget(l, row, col)
                    self.vsLayout.addWidget(self.ccbs[fluor], row, col+1)
                    col+=2
                case "black-in" | "white-in":
                    s = DoubleSlider(0,255)
                    d.setRange(0,255)
            sname = f'{fluor} {setting}'
            
            self.spin_boxes[sname] = d
            d.setValue(self.viewsettings[sname])
            d.setObjectName(sname)
            d.valueChanged.connect(self.spin_edited)
            self.sliders[sname] = s
            s.setValue(self.viewsettings[sname])
            s.setObjectName(sname)
            s.valueChanged.connect(self.slider_moved)
            s.setOrientation(Qt.Horizontal)
            s.setStyleSheet(
                f"""QSlider::groove:horizontal {{background-color : {self.gvdata.channelColors[fluor]};\
                                                border: 1px solid #999999 ; 
                                                height: 20px; 
                                                margin: 0px;}}
                QSlider::handle:horizontal{{background-color: white; 
                                            border: 2px solid black; 
                                            border-radius: 4px; 
                                            border-color: black; 
                                            height:20px; 
                                            width: 14px }}""")
            # QSlider().set
            self.vsLayout.addWidget(QLabel(setting.title()), row, col)
            self.vsLayout.addWidget(s, row, col+1) 
            self.vsLayout.addWidget(d, row, col+2) 
            col+=3
        
        # Create buttons and layout
        self.buttonBox = QGroupBox()
        self.restore_button = QPushButton("Undo changes")
        self.restore_button.pressed.connect(lambda: self.wipe_viewsettings('Restore'))

            # Reset viewsettings button
        self.reset_button = QPushButton("Reload defaults")
        self.reset_button.pressed.connect(lambda: self.wipe_viewsettings('Reset'))
        # self.reset_vs.setFont(self.gvdata.user.fonts.button_small)

        self.export_button = QPushButton("Export viewsettings")
        self.export_button.pressed.connect(lambda: self.export_viewsettings())

        self.import_button = QPushButton("Import viewsettings")
        self.import_button.pressed.connect(lambda: self.import_viewsettings())

        self.buttonLayout = QGridLayout()
        self.buttonLayout.addWidget(self.restore_button, 0,0)
        self.buttonLayout.addWidget(self.reset_button, 0,1)
        self.buttonLayout.addWidget(self.import_button, 1,0)
        self.buttonLayout.addWidget(self.export_button, 1,1)

        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFont(self.gvdata.user.fonts.medium)

        # Set Group layouts and main layout
        self.vsBox.setLayout(self.vsLayout)
        self.buttonBox.setLayout(self.buttonLayout)
        self.layout = QGridLayout()
        self.layout.addWidget(self.vsBox, 0,0)
        self.layout.addWidget(self.buttonBox, 0,1)
        self.layout.addWidget(self.status_label,1,0,1,2)
        self.layout.setSizeConstraint(QLayout.SetFixedSize) # Allows window to resize to shrink when widgets are removed
        self.setLayout(self.layout)    
        # Display and finish up
        self.show()
    
    def create_color_combos(self):
        self.ccbs = {}
        for fluor in self.gvdata.channels:
            ccb = ColorfulComboBox(self, color_dict=hexcd, selection = self.gvdata.channelColors[fluor].capitalize())
            ccb.currentIndexChanged.connect(self.update_colors)
            self.ccbs[fluor] = ccb

    def update_widget_colors(self):
        for fluor, setting in product(self.gvdata.channels, ("label", "gamma","black-in", "white-in")):
            c = self.ccbs[fluor].color_name
            tc = self.ccbs[fluor].text_color
            if setting == "label":
                self.labels[fluor].setStyleSheet(f"""QLabel{{ color : {tc}; font-size: 18pt; background-color: {c}; }}""")
            else:
                slider = self.sliders[f'{fluor} {setting}']
                slider.setStyleSheet(f"""QSlider::groove:horizontal {{background-color : {c};
                                            border: 1px solid #999999 ; height: 20px; margin: 0px;}}
                                    QSlider::handle:horizontal{{background-color: white; 
                                            border: 2px solid black; border-radius: 4px; 
                                            border-color: black; height:20px; width: 14px }}""")

    ''' Get color mappings from dialog widgets and read to user data'''
    def update_colors(self):
        changed = []
        for fluor, ccb in self.ccbs.items():
            if self.gvdata.channelColors[fluor] != ccb.color_name.lower():
                changed.append(fluor)
                self.gvdata.channelColors[fluor] = ccb.color_name.lower()
        self.gview.set_layer_colors(changed)
        self.update_widget_colors()
    
    ''' Get color mappings from user data and set widgets'''
    def set_colors(self):
        print("Showing full dict")
        new_colors = copy.copy(self.gvdata.channelColors) 
        print("-------")
        for fluor, ccb in self.ccbs.items():
            print(f"Setting {fluor} ccb to the following color {new_colors[fluor].capitalize()} ")
            ccb.setCurrentText(new_colors[fluor].capitalize())
        self.gview.set_layer_colors(list(self.ccbs.keys()))
        self.update_widget_colors()

    '''Called upon widget value change. Couldn't get it to update just the value changed, so this just overwrites every value.
        There will never be more than 8 fluors so this is not a concern, just bad design.'''
    def update_settings(self, source_widgets, target_widgets):
        # If there is a value here, the restore button was clicked. Calling function wants to trigger a specific dial to move back
        if self.target_override:
            self.change_viewsettings(self.target_override)
            return None
        for setting, w in source_widgets.items():
            spl = setting.split()
            fluor, key_type = " ".join(spl[:-1]), spl[-1]
            new, old = w.value(), self.viewsettings[setting]
            if new != old:
                target_widgets[setting].setValue(new)
                self.last_adjustment = setting
                self.viewsettings[setting] = new
        self.change_viewsettings(self.last_adjustment)
        return None

    '''Helper that passes on signal to update function with proper params'''
    def slider_moved(self):
        # self.update_needed = "Spin"
        self.update_settings(self.sliders, self.spin_boxes)
        # self.update_needed = False

    '''Helper that passes on signal to update function with proper params'''
    def spin_edited(self):
        # self.update_needed = "Slider"
        self.update_settings(self.spin_boxes, self.sliders)
        # self.update_needed = False
        
    ''' Run function to make visual changes in Napari given user-selected viewsettings'''
    def change_viewsettings(self, caller_setting = False):
        self.session.view_settings = self.viewsettings
        self.gview.restore_viewsettings_from_cache(arrange_multichannel = False, single_setting_change = caller_setting)

    ''' Bring viewsettings back to a previous state. Either original (what was loaded at the start) or
            to the settings from when the Dialog opened.'''
    def wipe_viewsettings(self, mode = 'Restore'):
        template = {'Reset':self.gvdata.view_settings, 'Restore':self.original_viewsettings}[mode]
        self.viewsettings = copy.deepcopy(template)
        self.session.view_settings = copy.deepcopy(template)
        for setting, w in self.sliders.items():
            self.target_override = setting
            w.setValue(template[setting])
            self.spin_boxes[setting].setValue(template[setting])
        self.target_override = False
    
    ''' Write a HALO-compatible viewsettings file to disk. Calls a worker function in the user class'''
    def export_viewsettings(self):
        parent_folder = self.gvdata.last_image_save_folder 
        file_name, _ = QFileDialog.getSaveFileName(None,"Export viewsettings",parent_folder,"VIEWSETTINGS file (*.viewsettings)")
        if os.path.exists(file_name):
            self.gvdata.write_view_settings(file_name)
            self.status_label.setText('<font color="#4c9b8f">Export successful</font>')
    
    def import_viewsettings(self):
        import lxml
        try:
            parent_folder = self.gvdata.last_image_save_folder
            file_name, _ = QFileDialog.getOpenFileName(None,"Import viewsettings",parent_folder,"VIEWSETTINGS file (*.viewsettings)")
            df = pd.read_xml(file_name)
            errors = self.gvdata.transfer_view_settings(df)
            self.gvdata.imported_view_settings = df
            self.wipe_viewsettings(mode="Reset") # Change dialog sliders and numbers to match
            self.change_viewsettings() # Change viewer settings
            self.set_colors()
            if errors != []:
                self.status_label.setText('<font color="#4c9b8f">Import successful</font>')
            else:
                status = ''
                for e in errors:
                    status += f'{e}\n'
                self.status_label.setText(f'<font color="#bd4545"{status}</font>')

        except lxml.etree.XMLSyntaxError as e:
                print("xml")
                # self._append_status_br('<font color="#ffa000"> Unable to read .viewsettings file, will use defaults instead</font>')  
                # self._log_problem(e, error_type= 'viewsettings-parse-issue')
                # self.setWidgetColorBackground(self.viewSettingsEntry, "#4c9b8f")
                # QTimer.singleShot(800, lambda:self.setWidgetColorBackground(self.viewSettingsEntry, "#ffffff"))
                self.status_label.setText('<font color="#bd4545">Import error: bad XML syntax in viewsettings file</font>')
        
        except Exception as e:
                print("other")
                # self._append_status_br('<font color="#ffa000"> Unable to read .viewsettings file, will use defaults instead</font>')  
                # self._log_problem(e, error_type= 'unspecified-viewsettings-issue')
                # self.setWidgetColorBackground(self.viewSettingsEntry, "#4c9b8f")
                # QTimer.singleShot(800, lambda:self.setWidgetColorBackground(self.viewSettingsEntry, "#ffffff"))
                self.status_label.setText('<font color ="#bd4545">Import error: unknown</font>')
        

#TODO
'''Used to prompt the user for a selection of a color. Should hold every color in a reference dictionary, 
    but only show maybe 10-15 at a time. Some CSS needed to make it feel more responsive. '''

class ColorfulComboBox(QComboBox):
    def __init__(self, parent, color_dict: dict, selection:str = 'Grey', text_size = "10pt"):
        super(ColorfulComboBox, self).__init__(parent)
        super().setMaxVisibleItems(10)
        self.color_dict = color_dict
        self.init_color_backgrounds()
        self.currentIndexChanged.connect(self.change_active_item_color)
        self.highlighted[int].connect(self.item_highlighted)
        self.text_size = text_size
        self.setStyleSheet(f"""
            QComboBox {{ combobox-popup: 0; 
                        color: white;  
                        font-size: {self.text_size};         
                        background-color: {self.color_dict[selection]};
                        border: 1px solid gray;}}
            QComboBox::drop-down {{ background: none; }}
            """)
        self.setCurrentText(selection.capitalize()) # Start with chosen color
        self.update_stored_color(selection.capitalize())

    def update_stored_color(self, cn):
        self.color_name = cn
        self.color_value = self.color_dict[cn]     
        self.text_color = "white" if self.is_dark_color(QtGui.QColor(self.color_dict[cn])) else "black" 

    def lighten_color(self,color):
        factor = 1.3
        r, g, b, a = color.getRgb()
        r = min(int(r * factor), 255)
        g = min(int(g * factor), 255)
        b = min(int(b * factor), 255)
        return QtGui.QColor(r, g, b, a).toRgb()
                        
    def is_dark_color(self, color):
        if not color.isValid():
            return False
        r, g, b, _ = color.getRgb()
        luminance = 0.299 * r + 0.587 * g + 0.114 * b
        return luminance < 128

    def init_color_backgrounds(self):
        model = self.model()
        for row, (color_name, color_value) in enumerate(self.color_dict.items()):
            self.addItem(color_name.title())
            color = QtGui.QColor(color_value)
            model.setData(model.index(row, 0), color, QtCore.Qt.BackgroundRole)
            text_color = QtGui.QColor('white') if self.is_dark_color(color) else QtGui.QColor('black')
            model.setData(model.index(row, 0), text_color, QtCore.Qt.ForegroundRole)

    def item_highlighted(self, pos):
        highlight_color_value = self.color_dict[self.itemText(pos)].lower()
        lightened_highlight = self.lighten_color(QtGui.QColor(highlight_color_value))
        # print(lightened_highlight.name())

        highlight_color = 'white' if self.is_dark_color(QtGui.QColor(lightened_highlight.name())) else "black"
        active_bg_color = self.color_dict[self.currentText()].lower()       
        active_text_color = 'white'if self.is_dark_color(QtGui.QColor(active_bg_color)) else "black"

        self.setStyleSheet(f"""
            QWidget {{ 
                        selection-background-color:{lightened_highlight.name()}; 
                        selection-color: {highlight_color};
                    }}
            QComboBox {{
                combobox-popup: 0;
                font-size: {self.text_size};
                color: {active_text_color};           
                background-color: {active_bg_color};
                border: 1px solid gray;
            }}
            QComboBox::drop-down {{ background: none; }}
            """)

    def change_active_item_color(self):
        self.update_stored_color(self.currentText())
        current_color_value = self.color_dict[self.currentText()]
        print(f"Startup = {self.currentText()} - {current_color_value}")
                    
        text_color = 'white' if self.is_dark_color(QtGui.QColor(current_color_value)) else 'black'
        self.setStyleSheet(f"""
            QComboBox {{
                combobox-popup: 0;
                font-size: {self.text_size};
                color: {text_color};           
                background-color: {current_color_value};
                border: 1px solid gray;
            }}

            QComboBox::drop-down {{
                background: none;
            }}
        """)



''' Adjust the style of clickable QPushButtons that change the active channels of the image. These buttons act
    as on/off toggles for these channels and also allow for an easy way for the user to see which are enabled.'''
def make_fluor_toggleButton_stylesheet(clr: str = "gray" , toggled: bool = False, absorption = False):
    def _clamp(val, minimum=0, maximum=255):
        if val < minimum:
            return minimum
        if val > maximum:
            return maximum
        return int(val)

    def _colorscale(hexstr, scalefactor):
        ''' https://thadeusb.com/weblog/2010/10/10/python_scale_hex_color/
        Scales a hex string by ``scalefactor``. Returns scaled hex string.

        To darken the color, use a float value between 0 and 1.
        To brighten the color, use a float value greater than 1.
        '''

        hexstr = hexstr.strip('#')

        if scalefactor < 0 or len(hexstr) != 6:
            return hexstr

        r, g, b = int(hexstr[:2], 16), int(hexstr[2:4], 16), int(hexstr[4:], 16)

        r = _clamp(r * scalefactor)
        g = _clamp(g * scalefactor)
        b = _clamp(b * scalefactor)
        return "#%02x%02x%02x" % (r, g, b)
    
    ''' Takes QT Color'''
    def _is_dark_color(color):
        if not color.isValid():
            return False
        r, g, b, _ = color.getRgb()
        luminance = 0.299 * r + 0.587 * g + 0.114 * b
        return luminance < 128
    
    clr = custom_color_functions.colormap[clr] if clr !="None" else '#b6b6b6'
    dark_clr = _colorscale(clr, 0.6)

    darkgray = "#333333"

    text_color = 'white'if _is_dark_color(QtGui.QColor(clr)) else "black"

    if toggled: # Button is 'off'. Should be muted and indicate that the fluor is not being displayed
        style = f"""QPushButton {{background-color: {'white' if absorption else darkgray};
                            border-style: inset;
                            border-width: 2px;
                            border-radius: 10px;
                            border-color: {clr};
                            min-width: 5em;
                            padding: 2px;  }}
            QPushButton:pressed{{background-color: {clr};
                                border-style: outset; }}"""
    else: # Button is 'on'. should be colored and indicate that the fluor is active
        style = f"""QPushButton {{background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 {clr},stop: 0.4 {clr},  stop: 1 {dark_clr}); \
                            border-style: outset;
                            border-width: 2px;
                            border-radius: 10px;
                            border-color: {darkgray if absorption else 'white'};
                            color: {text_color};
                            min-width: 5em;
                            padding: 2px;  }}
            QPushButton:pressed{{background-color: {'white' if absorption else darkgray};
                                border-style: inset; }}"""
    return style

class ModeCombo(QComboBox):
    def __init__(self, parent, gvdata: GVData):
        super(ModeCombo, self).__init__(parent)
        self.gvdata = gvdata
        self.setMaximumWidth(180)
        self.addItems(["HALO", "HALO Multi-Image", "CosMx", "Xenium"])
        self.setCurrentText(self.gvdata.user.UI_mode)
        # self.highlighted.connect(lambda: self.showPopup())

        # Set some styles for a modern look
        self.setStyleSheet("""
            QWidget{
                selection-background-color: #f5f5f5;
                selection-color: #333;
            }
            QComboBox {
                combobox-popup: 0;
                border: 2px solid #555;
                border-radius: 5px;
                padding: 5px 15px;
                background: #fff;

            }
            QComboBox::drop-down {
                background: none;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #555;
                selection-background-color: #eee;
            }
        """)

        # Set font for a modern look
        font = QFont("Helvetica", 10)
        self.setFont(font)

        # Add a custom arrow icon
        # self.setEditable(True)
        # self.lineEdit().setReadOnly(True)
        # self.lineEdit().setAlignment(QtCore.Qt.AlignCenter)
