#############################################################################

from qtpy.QtCore import QObject, Qt, QThread, QTimer
from qtpy.QtGui import QIcon, QPixmap,QColor,QFont
from qtpy.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,QMainWindow, QGridLayout, QDesktopWidget, QSizePolicy,QLayout,
                            QRadioButton, QGroupBox, QLabel, QLineEdit,QPushButton, QSpinBox,QDoubleSpinBox, QMenuBar, QAction, QFileDialog,
                            QHBoxLayout, QVBoxLayout)

import sys
import os
import time
import storage_classes
from galleryViewer import gui_execute
import ctypes
import os
import warnings
warnings.filterwarnings("ignore")
import pandas as pd
import numpy as np
import anndata as ad
import pyarrow.dataset as ds
import zarr
import copy
import pathlib

# Used in fetching and processing metadata
from random import choice
import tifffile
import xml.etree.ElementTree as ET
import webbrowser # for opening github
import warnings
warnings.catch_warnings

from custom_qt_classes import ScoringDialog, HaloChannelDialog,CosMxChannelDialog, StatusCombo, ColorfulComboBox, ModeCombo
from custom_color_functions import colormap_titled as rgbcd

VERSION_NUMBER = '1.3.5'
FONT_SIZE = 12

''' Keeps a reference to the open QDialog, so that when a new one is created, it can destroy the old one. 
        Responsible for instantiating the new dialog and updating it's style. Requires the old GVData class as input'''
class WindowTracker():
    def __init__(self):
        self.windows = []
    
    def _lighten_color(self,hexstr):
        hexstr = hexstr.strip('#')
        factor = 2.5
        r, g, b = int(hexstr[:2], 16), int(hexstr[2:4], 16), int(hexstr[4:], 16)
        r = min(int(r * factor), 255)
        g = min(int(g * factor), 255)
        b = min(int(b * factor), 255)
        return "#%02x%02x%02x" % (r, g, b)
    
    def _updateStyleSheet(self, dialog, ui_mode):
        '''                 main dark (button), main border + menubar, lineEdit, Qlabel '''
        colors = {"HALO": ["#0b2636", "#5e8e92", "#5e8e92", "#333333"],
                  "HALO Multi-Image" : ["#0b2636", "#5e8e92", "#5e8e92", "#333333"],
                  "CosMx" : ["#2d5b71", "#b0ce4c", "#545659", "#545659"],
                  "Xenium" : ["#1f1f1f", "#8a3634", "#545659", "#545659"]}
    
        accent_colors = colors[ui_mode]
    
        style_sheet = f"""
            
            QCheckBox {{
                color: {accent_colors[3]};
            }}
            QCheckBox::indicator {{ 
                background: none;
                border: 2px solid {accent_colors[0]};
            }}
            QCheckBox::indicator:checked {{ 
                background-color: {accent_colors[1]};
                image-position: center center;
                image: url('./data/Plus-Symbol.png');
                border: 2px solid {accent_colors[1]};
            }}
            QLabel {{
                color: {accent_colors[3]};
            }}
            QPushButton {{
                background-color: {accent_colors[0]};
                color: white;
            }}
            QGroupBox {{
                border: 2px solid {accent_colors[1]};
                border-radius: 5px;
                padding-top: 1em;
                padding-bottom: 0.5em;
                padding-left: 0.5em;
                padding-right: 0.5em;
                margin-top: 2ex; /* leave space at the top for the title */
                margin-bottom: 2ex;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 3px;
                color: {accent_colors[3]};
            }}
            QSpinBox, QDoubleSpinBox {{
                border: 2px solid {accent_colors[0]};
                color: {accent_colors[3]};
                background: white;
            }}
            QLineEdit {{
                border: 2px solid {accent_colors[0]};
                color: {accent_colors[2]};
                background: white;
            }}
            QMenuBar {{
                background-color: {accent_colors[1]};
                color:  white; /* {accent_colors[3]}*/
            }}
        """
        dialog.setStyleSheet(style_sheet)

    def start_application(self, app: QApplication, gvdata:storage_classes.GVData | None= None):
        # Read stored class data
        if gvdata is None:
            user = storage_classes.loadObject('profiles/active.gvconfig')
        else:
            user = gvdata.user
        gvdata = user.current_data
        print(gvdata.user.UI_mode)
        match gvdata.user.UI_mode:
            case "HALO":
                new_window = GVUI_Halo(app, tracker=self, gvdata=gvdata)
                self._updateStyleSheet(new_window, "HALO")
            case "HALO Multi-Image":
                new_window = GVUI_Halo_MI(app, tracker=self, gvdata=gvdata)
                self._updateStyleSheet(new_window, "HALO Multi-Image")
            case "CosMx":
                new_window = GVUI_CosMx(app, tracker=self, gvdata=gvdata)
                self._updateStyleSheet(new_window, "CosMx")
            case "Xenium":
                new_window = GVUI_Xenium(app, tracker=self, gvdata=gvdata)
                self._updateStyleSheet(new_window, "Xenium")
            case _:
                raise ValueError("Unkown UI mode given by user data class")
        self.windows.append(new_window)

        return new_window

''' This class contains the whole dialog box that the user interacts with and all it's widgets. Also contains
    an instance of the GVData class, which will be passed to the viewer code. '''
class GVUI(QDialog):
    def __init__(self, app: QApplication, tracker: WindowTracker, gvdata: storage_classes.GVData | None = None, add_annotations = True):
        super().__init__()
        self.tracker = tracker
        self.app = app
        self.gvdata = gvdata
        self.add_annotations = add_annotations
        self.init_window_defaults()
        self.init_top_layout()
        self.createLeftGroupBox()
        self.createRightGroupBox(add_annotations)
        self.init_filter_readouts()
        self.init_status_load_area()
        self.connect_buttons()
        self.init_menu_bar()
        self.insert_previous_hints()
        self.set_top_layout()
        self.set_main_layout()
        print("End init\n")

    #################################
    #        Initialization functions          
    #################################

    def init_window_defaults(self):
        # Arrange title bar buttons
        self.setWindowFlag(Qt.WindowMinimizeButtonHint, True)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        self.setWindowFlag(Qt.WindowTitleHint,False)
        # self.setWindowFlag(Qt.WindowContextHelpButtonHint,False)
        # self.setSizePolicy(QSizePolicy.MinimumExpanding,QSizePolicy.MinimumExpanding)

        # For TESTING
        print(f"My class type is {type(self)} and || {self.gvdata}")
        print(f'Initial test print for colors: {self.gvdata.channelColors}')
        self.setWindowIcon(QIcon('data/mghiconwhite.png'))

        '''Set title area / logo'''
        self.cc_logo = QLabel()
        pixmap = QPixmap('data/mgh-mgb-cc-logo2 (Custom).png')
        self.cc_logo.setPixmap(pixmap)
        self.setWindowTitle(f"GalleryViewer v{VERSION_NUMBER}")

    def init_top_layout(self):
        # f'<br><font color="{idcolor}">CID: {ID}</font>'
        self.titleLabel = QLabel(f'Tumor Cartography Core <font color="#033b96">Gallery</font><font color="#009ca6">Viewer</font> <font size=12pt>v{VERSION_NUMBER}</font>')
        # custom_font = QFont(); custom_font.setFamily('Metropolis Black'); custom_font.setPointSize(39)
        self.titleLabel.setStyleSheet('font-family: Metropolis ; font-size: 25pt')
        # titleLabel.setFont(QFont('MS Gothic',38))
        self.titleLabel.setAlignment(Qt.AlignCenter)

        ''' ComboBox for UI Mode '''
        self.UI_combo = ModeCombo(self,self.gvdata)
        self.UI_combo.currentTextChanged.connect(self.change_UI_mode)
        # entry box for .qptiff        
        self.imageEntry = QLineEdit()  # Put retrieved previous answer here
        # Want to do this in any case
        self.imageEntry.setPlaceholderText('Enter path to .qptiff')
        self.imageEntry.setFixedWidth(800)
        # imageEntry.setAlignment(Qt.AlignLeft)
        # entryLabel = QLabel("Image: ")
        # entryLabel.setBuddy(self.imageEntry)
        # entryLabel.setAlignment(Qt.AlignCenter)
        # entryLabel.setMaximumWidth(600)

        self.dataEntry = QLineEdit()  # Put retrieved previous answer here
        self.dataEntry.setPlaceholderText('Enter path to .csv')
        self.dataEntry.setFixedWidth(800)
        # dataEntry.setAlignment(Qt.AlignLeft)
        # dataEntryLabel = QLabel("Object Data: ")
        # dataEntryLabel.setBuddy(self.dataEntry)
        # dataEntryLabel.setAlignment(Qt.AlignCenter)
        # dataEntryLabel.setMaximumWidth(600)

        self.previewObjectDataButton = QPushButton("Choose Data")
        self.previewObjectDataButton.setMaximumWidth(200)
        self.previewImageDataButton = QPushButton("Choose Image")
        self.previewImageDataButton.setMaximumWidth(200)
        self.previewObjectDataButton.setDefault(True)

        
        self.viewSettingsEntry = QLineEdit()
        self.viewSettingsEntry.insert(pathlib.Path(self.gvdata.view_settings_path).name)
        self.viewSettingsEntry.setPlaceholderText('Enter path to a .viewsettings file (optional)')
        self.viewSettingsEntry.setFixedWidth(800)

        self.getViewsettingsPathButton = QPushButton("Import viewsettings")
        # self.getViewsettingsPathButton.setMaximumWidth(220)


        # viewSettingsLabel = QLabel("View Settings: ")
        # viewSettingsLabel.setBuddy(self.viewSettingsEntry)
        # viewSettingsLabel.setAlignment(Qt.AlignCenter)
        # viewSettingsLabel.setMaximumWidth(600)

    def init_filter_readouts(self):
        # reset status mappings for selected annotations and phenotypes
        new_pheno_label = '<u>Phenotypes</u><br>'
        if not self.gvdata.phenotype_mappings.keys(): new_pheno_label +='All'
        for key in self.gvdata.phenotype_mappings:
            self.gvdata.phenotype_mappings[key] = "Don't assign"
            new_pheno_label += f'{key}<br>'
        self.gvdata.phenotype_mappings_label = new_pheno_label

        new_anno_label = '<u>Annotations</u><br>'
        if not self.gvdata.annotation_mappings.keys(): new_anno_label +='All'
        for key in self.gvdata.annotation_mappings:
            self.gvdata.annotation_mappings[key] = "Don't assign"
            new_anno_label += f'{key}<br>'
        self.gvdata.annotation_mappings_label = new_anno_label

    def init_status_load_area(self):
        self.status_label = QLabel()
        self.status_label.setStyleSheet('color:#075cbf ; font-size: 15pt')
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setVisible(False)

        # self.createProgressBar()
        # Push button to start reading image data and start up napari by remotely executing main method of main script
        self.findDataButton = QPushButton("Load images into viewer")
        self.findDataButton.setDefault(False)

    def connect_buttons(self):
        self.findDataButton.pressed.connect(self.loadGallery)
        self.imageEntry.textEdited.connect(self.saveQptiff)
        self.dataEntry.textEdited.connect(self.saveObjectData)
        self.getViewsettingsPathButton.pressed.connect(self.fetchViewsettingsPath)
        self.previewObjectDataButton.pressed.connect(self.prefillObjectData)
        self.previewImageDataButton.pressed.connect(self.prefillImageData)

    def init_menu_bar(self):
        # Menu bar
        self.menubar = QMenuBar()
        pref = self.menubar.addMenu('Preferences')
        scoring = QAction("Modify scoring decisions and colors", self)
        scoring.setShortcut("Ctrl+P")
        import_gvs = QAction("Import configuration file", self)
        import_gvs.setShortcut("Ctrl+I+C")
        export_gvs = QAction("Export configuration file", self)
        export_gvs.setShortcut("Ctrl+E+C")
        reset = QAction("Reset GUI to defaults", self)
        reset.setShortcut("Ctrl+R")
        channels = QAction("Select image channels", self)
        channels.setShortcut("Ctrl+i")
        
        pref.addActions((scoring,import_gvs, export_gvs, channels,reset))
        pref.triggered[QAction].connect(self.process_menu_action)

        about = self.menubar.addMenu('About')
        manual = QAction("Open the manual", self)
        manual.setShortcut("Ctrl+M")
        github = QAction("View source code",self)
        errors = QAction("Check error logs",self)
        errors.setShortcut("Ctrl+E")
        about.addActions((manual,errors, github))
        about.triggered[QAction].connect(self.process_menu_action)

    def set_top_layout(self):
        ''' Top layout'''
        self.topLayout = QGridLayout()
        # topLayout.addStretch(1)
        self.topLayout.addWidget(self.cc_logo,0,0)
        self.topLayout.addWidget(self.titleLabel,0,1, 1,3, Qt.AlignLeft)
        self.topLayout.addWidget(self.UI_combo, 0, 3,1,2,Qt.AlignRight)
        self.topLayout.setSpacing(20)
        self.topLayout.addWidget(self.imageEntry,1,1,)
        self.topLayout.addWidget(self.previewImageDataButton,1,2,1,2)
        self.topLayout.addWidget(self.dataEntry,2,1)
        self.topLayout.addWidget(self.previewObjectDataButton,2,2,1,2)
        self.topLayout.addWidget(self.viewSettingsEntry,3,1)
        self.topLayout.addWidget(self.getViewsettingsPathButton,3,2,1,2)

    def set_main_layout(self):  
        ''' Main layout '''
        self.mainLayout = QGridLayout()
        self.mainLayout.setMenuBar(self.menubar)
        self.mainLayout.addLayout(self.topLayout, 0, 0, 1, 2)
        self.mainLayout.addWidget(self.topLeftGroupBox, 1, 0)
        self.mainLayout.addWidget(self.topRightGroupBox, 1, 1)
        self.mainLayout.addWidget(self.findDataButton,2,0,1,0)
        self.mainLayout.addWidget(self.status_label,3,0,1,0)
        
        self.mainLayout.setRowStretch(1, 1)
        self.mainLayout.setRowStretch(2, 1)
        self.mainLayout.setColumnStretch(0, 1)
        self.mainLayout.setColumnStretch(1, 1)
        self.mainLayout.setSizeConstraint(QLayout.SetFixedSize)
        self.setLayout(self.mainLayout)

    def insert_previous_hints(self):
        # preprocess things if user has entered paths in a previous session
        if self.gvdata.image_path is not None:
            self.imageEntry.insert(pathlib.Path(self.gvdata.image_path).name)
            # self.prefillImageData(fetch=False)
        if self.gvdata.objectDataPath is not None and  self.gvdata.image_path is not None:
            self.dataEntry.insert(pathlib.Path(self.gvdata.objectDataPath).name)
            self.prefillObjectData(fetch=False)
        if self.gvdata.view_settings_path is not None:
            self.saveViewSettings()
        self.clearFocus()

    #################################
    #      Groupbox constructors
    #################################

    ''' Construct widgets for channel checkboxes and color dropdowns'''
    def createLeftGroupBox(self, layout: None|QGridLayout = None, groupbox: None|QGroupBox = None ):
        self.topLeftGroupBox = groupbox if groupbox is not None else QGroupBox("Channels and Colors")
        self.myColors = [] # Holds color selection comboboxes for the channel selection widgets
        self.mycheckbuttons = []
        for chn, pos in self.gvdata.channelOrder.items():
            check = QCheckBox(chn)
            check.setObjectName(chn.replace(" ","_"))
            self.mycheckbuttons.append(check)
        self.topLeftGroupLayout = layout if layout is not None else QGridLayout()
        
        row = 0 ; col = 0
        for pos,button in enumerate(self.mycheckbuttons):
            colorComboName = button.objectName()
            colorCombo = ColorfulComboBox(self, rgbcd, self.gvdata.channelColors[button.objectName().replace("_"," ")].title() )
            colorCombo.setObjectName(colorComboName)
            if button.objectName().replace("_"," ") in self.gvdata.channels:
                button.setChecked(True)
            else:
                button.setChecked(False)
            button.toggled.connect(self.saveChannel) #IMPORTANT that this comes after setting check values
            self.myColors.append(colorCombo)
            colorCombo.activated.connect(self.saveColors)
            
            button.setStyleSheet(f"""
                QCheckBox {{ font-size: 10pt;}}
            """)
            self.topLeftGroupLayout.addWidget(button, row//4,col%4)
            self.topLeftGroupLayout.addWidget(colorCombo, row//4 ,  (col%4)+1 )
            row+=2; col+=2

        self.topLeftGroupBox.setLayout(self.topLeftGroupLayout)    
        return self.topLeftGroupLayout, self.topLeftGroupBox
    
    ''' Construct widgets for cell filters area'''
    def createRightGroupBox(self, add_annotations = True):
        self.topRightGroupBox = QGroupBox("Cells to Read")

        explanationLabel2 = QLabel("Gallery image size <b>(px)</b>")
        explanationLabel3 = QLabel("Num. cells <b>per page<b>")
        explanationLabel4 = QLabel("Num. cells <b>per row<b>")
        explanationLabel5 = QLabel("Load page with <b>Cell ID<b>")
        
        #------------------ Annotation widgets
        if add_annotations:
            self.annotationButton = QPushButton("Add Annotation")
            self.annotationButton.setStyleSheet(f"QPushButton {{ font-size: 22px}}")
            self.annotationButton.pressed.connect(self.addAnnotation)

            # Annotation layer select
            self.annotationEdit = QLineEdit(self.topRightGroupBox)
            self.annotationEdit.setPlaceholderText('Single layer only')
            self.annotationEdit.setFixedWidth(220)
            self.annotationCombo = QComboBox(self.topRightGroupBox)
            self.annotationCombo.setVisible(False)
            self.annotationStatuses = StatusCombo(self.topRightGroupBox, self.gvdata)

            # Anno selection display label
            self.annotationDisplay = QLabel(self.topRightGroupBox)
            self.annotationDisplay.setText(self.gvdata.annotation_mappings_label)
            self.annotationDisplay.setAlignment(Qt.AlignTop)
            # self.annotationDisplay.setStyleSheet("line-height:1.5; padding-left:15px; padding-right:15px; padding-top:0px")
            self.annotationDisplay.setContentsMargins(15,0,15,0)

        #---------- Phenotype widgets
        self.phenotypeButton = QPushButton("Add Phenotype")
        self.phenotypeButton.setStyleSheet(f"QPushButton {{ font-size: 22px}}")
        self.phenotypeButton.pressed.connect(self.addPheno)

        # LineEdit / ComboBox
        self.phenotypeToGrab = QLineEdit(self.topRightGroupBox)
        self.phenotypeToGrab.setPlaceholderText('Phenotype of interest')
        self.phenotypeToGrab.setFixedWidth(220)
        self.phenotypeCombo = QComboBox(self.topRightGroupBox)
        self.phenotypeCombo.setVisible(False)
        self.phenotypeStatuses = StatusCombo(self.topRightGroupBox, self.gvdata)
       

        # Pheno selection display label
        self.phenoDisplay = QLabel(self.topRightGroupBox)
        self.phenoDisplay.setText(self.gvdata.phenotype_mappings_label)
        self.phenoDisplay.setAlignment(Qt.AlignTop)
        self.phenoDisplay.setStyleSheet("line-height:1.5")

        #---------- Filter widgets
        self.filterButton = QPushButton("Add Filter")
        self.filterButton.setStyleSheet(f"QPushButton {{ font-size: 22px}}")
        self.filterButton.pressed.connect(self.addFilter)

        self.filterMarker = QLineEdit(self.topRightGroupBox)
        self.filterMarker.setPlaceholderText('Marker')
        self.filterMarker.setFixedWidth(220)
        self.filterMarkerCombo = QComboBox(self.topRightGroupBox)
        self.filterMarkerCombo.setVisible(False)
        self.filterFunctionChoice = QComboBox(self.topRightGroupBox)
        self.filterFunctionChoice.addItems(["greater than", "less than"])
        self.filterNumber = QDoubleSpinBox(self.topRightGroupBox)
        self.filterNumber.setRange(0,1000)
       
        # Pheno / annotation selection display label
        self.filterDisplay = QLabel(self.topRightGroupBox)
        self.filterDisplay.setText(self.gvdata.filters_label)
        self.filterDisplay.setAlignment(Qt.AlignTop)
        self.filterDisplay.setStyleSheet("line-height:1.5")

        # Reset button 
        self.resetButton = QPushButton('Reset choices',self.topRightGroupBox)
        self.resetButton.pressed.connect(self.reset_mappings)
        self.resetButton.setStyleSheet(f"QPushButton {{ font-size: 14px}}")

        self.imageSize = QSpinBox(self.topRightGroupBox)
        self.imageSize.setRange(50,1000)
        self.imageSize.setValue(self.gvdata.imageSize) # Misbehaving?
        self.imageSize.editingFinished.connect(self.saveImageSize)
        self.imageSize.setFixedWidth(100)
        self.specificCellChoice = QLineEdit(self.topRightGroupBox)
        self.specificCellChoice.setPlaceholderText('Leave blank for page 1')
        if self.gvdata.specific_cell is not None:
            self.specificCellChoice.insert(self.gvdata.specific_cell['ID'])
        self.specificCellChoice.setFixedWidth(220)
        self.specificCellChoice.textEdited.connect(self.saveSpecificCell)

        # Widgets to select annotation layer
        if add_annotations:
            self.specificCellAnnotationEdit = QLineEdit(self.topRightGroupBox)
            self.specificCellAnnotationEdit.setPlaceholderText('Annotation layer')
            if self.gvdata.specific_cell is not None:
                self.specificCellAnnotationEdit.insert(self.gvdata.specific_cell['Annotation Layer'])
            self.specificCellAnnotationEdit.setFixedWidth(220)
            self.specificCellAnnotationEdit.textEdited.connect(self.saveSpecificCell)

            self.specificCellAnnotationCombo = QComboBox(self.topRightGroupBox)
            self.specificCellAnnotationCombo.setVisible(False)
            self.specificCellAnnotationCombo.activated.connect(self.saveSpecificCell)

        self.page_size_widget = QSpinBox(self.topRightGroupBox)
        self.page_size_widget.setRange(5,4000)
        self.page_size_widget.setValue(self.gvdata.page_size)
        self.page_size_widget.editingFinished.connect(self.savePageSize)
        self.page_size_widget.setFixedWidth(100)

        self.row_size_widget = QSpinBox(self.topRightGroupBox)
        self.row_size_widget.setRange(2,self.gvdata.page_size)
        self.row_size_widget.setValue(self.gvdata.cells_per_row)
        self.row_size_widget.editingFinished.connect(self.saveRowSize)
        self.row_size_widget.setFixedWidth(100)

        self.global_sort_widget = QComboBox(self.topRightGroupBox)
        self.global_sort_widget.addItem("Sort object table by Cell Id")
        print(f"setting widget to be {self.gvdata.global_sort}")
        for i, chn in enumerate(self.gvdata.channels):
            self.global_sort_widget.addItem(f"Sort object table by {chn} Cell Intensity")
        self.global_sort_widget.setCurrentText(self.gvdata.global_sort)
        self.global_sort_widget.currentTextChanged.connect(self.saveGlobalSort)

        layout = QGridLayout()
        layout.addWidget(self.filterButton,0,0,Qt.AlignTop)#;layout.addWidget(self.explanationLabel0,0,0)
        layout.addWidget(self.filterMarker,0,1,Qt.AlignTop) ; layout.addWidget(self.filterMarkerCombo,0,1,Qt.AlignTop)
        layout.addWidget(self.filterFunctionChoice,0,2,Qt.AlignTop)
        layout.addWidget(self.filterNumber,0,3,Qt.AlignTop)

        layout.addWidget(self.phenotypeButton,1,0,Qt.AlignTop)#;layout.addWidget(self.explanationLabel0,0,0)
        layout.addWidget(self.phenotypeToGrab,1,1,Qt.AlignTop) ; layout.addWidget(self.phenotypeCombo,1,1,Qt.AlignTop)
        layout.addWidget(self.phenotypeStatuses,1,2,1,2,Qt.AlignTop)
        if add_annotations: layout.addWidget(self.annotationButton,2,0,Qt.AlignTop)#;layout.addWidget(self.explanationLabel1,1,0)
        if add_annotations: layout.addWidget(self.annotationEdit,2,1,Qt.AlignTop); layout.addWidget(self.annotationCombo,2,1,Qt.AlignTop)
        if add_annotations: layout.addWidget(self.annotationStatuses,2,2,1,2,Qt.AlignTop)
        layout.addWidget(explanationLabel2,3,0,Qt.AlignTop)
        layout.addWidget(self.imageSize,3,1,Qt.AlignTop)
        layout.addWidget(self.resetButton,3,2,1,2,Qt.AlignTop)
        layout.addWidget(explanationLabel3,4,0,Qt.AlignTop)
        layout.addWidget(self.page_size_widget,4,1,Qt.AlignTop)
        layout.addWidget(explanationLabel4,5,0,Qt.AlignTop)
        layout.addWidget(self.row_size_widget,5,1,Qt.AlignTop)
        layout.addWidget(explanationLabel5,6,0,Qt.AlignTop)
        layout.addWidget(self.specificCellChoice,6,1,Qt.AlignTop)
        if add_annotations: layout.addWidget(self.specificCellAnnotationEdit,6,2,1,2,Qt.AlignTop)
        if add_annotations: layout.addWidget(self.specificCellAnnotationCombo,6,2,1,2,Qt.AlignTop)
        layout.addWidget(self.global_sort_widget,7,0,1,2)
        layout.addWidget(self.phenoDisplay,0,4,7,1)
        if add_annotations: layout.addWidget(self.annotationDisplay,0,5,7,1)
        layout.addWidget(self.filterDisplay,0,6,7,1)
        # layout.setColumnStretch(3,6)
        # layout.setColumnStretch(4,6)


        # layout.addWidget(self.findDataButton)
        layout.rowStretch(-100)
        self.topRightGroupBox.setLayout(layout)

    #################################
    #        Event functions          
    #################################

    ''' ui_mode variable tracks with the current display of the widget. Will have changed by now. '''
    def change_UI_mode(self, new_mode):
        def _open_new_mode(w):
            w.tracker.windows.pop(0) # remove reference to old dialog
            w.status_label.setText(f"Entering {w.UI_mode}")
            w.exec_()

        self.gvdata.user.UI_mode = new_mode
        tracker = self.tracker
        tracker.start_application(self.app, gvdata = self.gvdata )
        old, new = tracker.windows
        old.finished.connect(lambda: _open_new_mode(new))
        old.close()

    ''' Summon dialog box for changing scoring labels'''
    def change_scoring_decisions(self):
        scoring = ScoringDialog(self, self.app, self.gvdata, {"pheno_widget":self.phenotypeStatuses,"anno_widget": self.annotationStatuses})
        scoring.exec()

    ''' Called when a menu bar option is selected'''
    def process_menu_action(self,q):
        class partialMatch(str):
            def __eq__(self, other):
                return self.__contains__(other)
        match partialMatch(q.text().lower()):

            case "scoring decisions":
                self.change_scoring_decisions()
            case "channels":
                self.change_channels()
            case 'manual':
                try:
                    # print(os.path.normpath(os.curdir+ r"/data/GalleryViewer v{x} User Guide.pdf".format(x=VERSION_NUMBER)))
                    os.startfile(os.path.normpath(os.curdir+ r"/data/GalleryViewer v{x} User Guide.pdf".format(x=VERSION_NUMBER)))
                except FileNotFoundError:
                    self.status_label.setVisible(True)
                    status ='<font color="#ffa000">Can\'t find a guide for this version!</font><br>Check for old versions in the server\'s Imagers/ImageProcessing/GalleryViewer/ folder.'
                    self.status_label.setText(status)
            case 'reset':
                try:
                    os.remove(os.path.normpath('profiles/active.gvconfig'))
                    self.status_label.setVisible(True)
                    status ='<font color="#ffa000">Cleared all saved metadata!</font> Close this window to allow the changes to take effect'
                    self.status_label.setText(status)
                except FileNotFoundError:
                    self.status_label.setVisible(True)
                    status ='<font color="#ffa000">I haven\'t saved any data yet.</font>'
                    self.status_label.setText(status)
            case 'source code':
                webbrowser.open("https://github.com/richierip/CTC-Gallery-Viewer", new = 2)
            case "error logs":
                os.startfile(os.path.normpath(r"./runtime logs"))
                errors = 0
                for root, cur, files in os.walk(os.path.normpath(r"./runtime logs")):
                    errors += len(files)
                self.status_label.setVisible(True)
                status =f'Found {errors} error logs! If you are having trouble, try resetting the viewer\'s saved preferences (ctrl+R) and restarting the program.<br> '
                status += 'Double check that your image and object data file contents match what is listed in Preferences.<br> If problems persist, share the latest log with Peter at prichieri@mgh.harvard.edu.'
                self.status_label.setText(status)
            case "import configuration":
                def _open_new_mode(w):
                    w.tracker.windows.pop(0) # remove reference to old dialog
                    w.status_label.setText("Import successful")
                    w.exec_()

                parent_folder = "./profiles/" 
                file_name, _ = QFileDialog.getOpenFileName(self,"Import configuration",parent_folder,"GalleryViewer Configuration File (*.gvconfig)")
                if file_name == "": return None # User closed import window. Don't open up a new one...
                tracker = self.tracker
                user = storage_classes.loadObject(file_name)
                tracker.start_application(self.app, gvdata = user.current_data )
                old,new = tracker.windows
                old.finished.connect(lambda: _open_new_mode(new))
                old.close()
                self = new

                print("Import successful?")
            case "export configuration":
                parent_folder = "./profiles/" 
                file_name, _ = QFileDialog.getSaveFileName(self,"Export configuration",parent_folder,"GalleryViewer Configuration File (*.gvconfig)")
                
                if storage_classes.storeObject(self.gvdata.user, file_name):
                    self.status_label.setText("Export successful")
                else:
                    self.status_label.setText("Export canceled")
            case _:
                raise ValueError("Bad input to process_menu_action")

    ''' Anachronistic. Switched to only checking input when Preview button is clicked'''
    def saveQptiff(self):
        cleanpath = os.path.normpath(self.imageEntry.text().strip('"')).strip('.')
        if os.path.exists(cleanpath):
            pass
            # self.gvdata.image_path = cleanpath
        # if (".qptiff" in self.imageEntry.text()) or (".tif" in self.imageEntry.text()):
        #     self.previewImageDataButton.setEnabled(True)
        # else:
        #     self.previewImageDataButton.setEnabled(False)
    
    ''' Anachronistic. Switched to only checking input when Preview button is clicked'''
    def saveObjectData(self):
        cleanpath = os.path.normpath(self.dataEntry.text().strip('"')).strip('.')
        if os.path.exists(cleanpath):
            pass
            # self.gvdata.objectDataPath = cleanpath
        # if ".csv" in self.dataEntry.text():
        #     self.previewObjectDataButton.setEnabled(True)
        # else:
        #     self.previewObjectDataButton.setEnabled(False)

    ''' Called on viewer start if there's a path written and if the view settings button is clicked'''
    def saveViewSettings(self):
        import lxml
        try:
            df = pd.read_xml(self.gvdata.view_settings_path)
            self.gvdata.transfer_view_settings(df)
            self._append_status_br('<font color="#4c9b8f">Successfully imported .viewsettings file!</font>')
            self.gvdata.imported_view_settings = df
            self.setWidgetColorBackground(self.viewSettingsEntry, "#55ff55")
            QTimer.singleShot(800, lambda:self.setWidgetColorBackground(self.viewSettingsEntry, "#ffffff"))

        except lxml.etree.XMLSyntaxError as e:
            self.gvdata.remake_viewsettings() # use defaults
            if 'empty' in str(e):
                self._append_status_br('No .viewsettings file selected, using defaults')    
                print("Entry box is empty, user wants to use defaults")
            else:
                self._append_status_br('<font color="#ffa000"> Unable to read .viewsettings file, will use defaults instead</font>')  
                self._log_problem(e, error_type= 'viewsettings-parse-issue')
                self.setWidgetColorBackground(self.viewSettingsEntry, "#4c9b8f")
                QTimer.singleShot(800, lambda:self.setWidgetColorBackground(self.viewSettingsEntry, "#ffffff"))
        except Exception as e:
                self._append_status_br('<font color="#ffa000"> Unable to read .viewsettings file, will use defaults instead</font>')  
                self._log_problem(e, error_type= 'unspecified-viewsettings-issue')
                self.setWidgetColorBackground(self.viewSettingsEntry, "#4c9b8f")
                QTimer.singleShot(800, lambda:self.setWidgetColorBackground(self.viewSettingsEntry, "#ffffff"))
    
    ''' Internalize the ID of a cell that should be shown in the first open page of cells. Different for if the data has annotations or not.'''
    def saveSpecificCell(self):
        try:
            if self.specificCellChoice.text() == '':
                self.gvdata.specific_cell = None
            elif self.specificCellAnnotationCombo.isVisible():
                self.gvdata.specific_cell = {'ID': str(int(self.specificCellChoice.text())),
                                            'Annotation Layer': self.specificCellAnnotationCombo.currentText()}
            else:
                self.gvdata.specific_cell = {'ID': str(int(self.specificCellChoice.text())),
                                           'Annotation Layer': self.specificCellAnnotationEdit.text()}
        except:
            print('Bad input to "Specific Cell" widget. Saving as NoneType')
            self.gvdata.specific_cell = None
    
    ''' Internalize cutout size of cell images'''
    def saveImageSize(self):
        val = self.imageSize.value()
        # Make sure it's an even number. Odd number causes an off by one issue that I don't want to track down.
        self.gvdata.imageSize = val if val%2==0 else val+1
   
    ''' Internalize number of cells to show per page'''
    def savePageSize(self):
        self.gvdata.page_size = self.page_size_widget.value()
        self.row_size_widget.setRange(2,self.gvdata.page_size)
    
    ''' Internalize number of cells per row'''
    def saveRowSize(self):
        self.gvdata.cells_per_row = self.row_size_widget.value()
        print(f"Row size is now {self.gvdata.cells_per_row}")
    
    ''' Internalize channel to sort cells by'''
    def saveGlobalSort(self):
        print("Saving global sort")
        self.gvdata.global_sort = self.global_sort_widget.currentText()

    ''' Internalize channels to show in viewer'''
    def saveChannel(self):
        for button in self.mycheckbuttons:
            channelName = button.objectName().replace("_"," ")
            if button.isChecked():
                self.gvdata.attempt_channel_add(channelName)
            elif not button.isChecked():
                self.gvdata.attempt_channel_remove(channelName)

    ''' Set color widgets with the colors in the data'''
    def setColors(self):
        for colorWidget in self.myColors:
            channelName = colorWidget.objectName().replace("_"," ")
            colorWidget.setCurrentText(self.gvdata.channelColors[channelName].capitalize())

    ''' Internalize mappings of channel names to colors'''
    def saveColors(self):
        for colorWidget in self.myColors:
            channelName = colorWidget.objectName().replace("_"," ")
            # print(f'#### Channel order fsr: {storage_classes.CHANNELS_STR} \n')
            print(self.gvdata.channels)
            
            self.gvdata.channelColors[channelName] = colorWidget.currentText()
        print(f"Current mapping is {self.gvdata.channelColors}")

    ''' Internalize annotations to use as a filter'''
    def addAnnotation(self):
        # Get status and color from combobox
        status = self.annotationStatuses.currentText()
        if status in self.gvdata.statuses_rgba.keys():
            status_color = self.gvdata.statuses_rgba[status][:-1]
        else: status_color = (0,0,0)
        # convert to hex
        status_color = '#%02x%02x%02x' % status_color
        print(status_color)

        # get annotation layer from appropriate widget
        if self.annotationCombo.isVisible():
            anno = self.annotationCombo.currentText()
            if anno == '': return None
            self.annotationCombo.removeItem(self.annotationCombo.findText(anno))
        else:
            anno = self.annotationEdit.text()
            if anno == '': return None
            self.annotationEdit.clear()

        # Pass to label
        current = self.annotationDisplay.text()
        current = current.replace("All",'')
        self.annotationDisplay.setText(current + f'<font color="{status_color}">{anno}<br>')
        self.gvdata.annotation_mappings_label = self.annotationDisplay.text()
        self.gvdata.annotation_mappings[anno] = status
    
    ''' Internalize phenotypes to use a filter'''
    def addPheno(self):
        # Get status and color from combobox
        status = self.phenotypeStatuses.currentText()
        print(f'Status is {status}')
        if status in self.gvdata.statuses_rgba.keys():
            status_color = self.gvdata.statuses_rgba[status][:-1]
        else: status_color = (0,0,0)
        # convert to hex
        status_color = '#%02x%02x%02x' % status_color
        print(f"Status color: {status_color}")

        # get annotation layer from appropriate widget
        if self.phenotypeCombo.isVisible():
            pheno = self.phenotypeCombo.currentText()
            if pheno == '': return None
            self.phenotypeCombo.removeItem(self.phenotypeCombo.findText(pheno))
        else:
            pheno = self.phenotypeToGrab.text()
            if pheno == '': return None
            self.phenotypeToGrab.clear()

        # Pass to label
        current = self.phenoDisplay.text()
        current = current.replace("All",'')
        self.phenoDisplay.setText(current + f'<font color="{status_color}">{pheno}<br>')
        self.gvdata.phenotype_mappings_label = self.phenoDisplay.text()
        self.gvdata.phenotype_mappings[pheno] = status

    ''' Internalize intensity threshold filters to add to viewer query'''
    def addFilter(self):
        if self.filterMarkerCombo.isVisible():
            fil = self.filterMarkerCombo.currentText()
            if fil == '':return None
        else:
            fil = self.filterMarker.text()
            if fil == '':return None
            self.filterMarker.clear()
        
        fil_compare_display = {"greater than": "&gt;", "less than": "&lt;"}[self.filterFunctionChoice.currentText()]
        fil_compare_query= {"greater than": ">", "less than": "<"}[self.filterFunctionChoice.currentText()]
        fil_number = self.filterNumber.value()

        print(f'{fil} {fil_compare_display} {fil_number}<br>')
        # Pass to label
        current = self.filterDisplay.text()
        current = current.replace("None",'')
        self.filterDisplay.setText(current + f'{fil} {fil_compare_display} {fil_number}<br>')
        self.gvdata.filters_label = self.filterDisplay.text()
        self.gvdata.filters.append(f"{fil} {fil_compare_query} {fil_number}")   

    ''' Reset all annotations, filters, and phenotypes'''
    def reset_mappings(self, examine_object_data = True):
        #phenotype
        self.gvdata.phenotype_mappings = {}
        self.gvdata.phenotype_mappings_label = '<u>Phenotypes</u><br>All'
        self.phenoDisplay.setText('<u>Phenotypes</u><br>All')
        #Annotations
        if self.add_annotations:
            self.gvdata.annotation_mappings = {}
            self.gvdata.annotation_mappings_label = '<u>Annotations</u><br>All'
            self.annotationDisplay.setText('<u>Annotations</u><br>All')
        #Filters
        self.gvdata.filters = []
        self.gvdata.filters_label = '<u>Filters</u><br>None'
        self.filterDisplay.setText('<u>Filters</u><br>None')

        # Refresh comboboxes
        if self.phenotypeCombo.isVisible():
            self.phenotypeCombo.clear() 
            self.filterMarkerCombo.clear()
        if self.add_annotations:
            if self.annotationCombo.isVisible():
                self.specificCellAnnotationCombo.clear()
                self.annotationCombo.clear()

        if examine_object_data:
            self.prefillObjectData(fetch=False)

    ''' Call the logger'''
    def _log_problem(self, e, logpath= None, error_type = None):
        # Log the crash and report key variables
        self.gvdata.log_exception(e, logpath, error_type)

    ''' Add path to viewsettings on button click'''
    def fetchViewsettingsPath(self):
        path = self.gvdata.last_system_folder_visited

        print(f"path {path}")
        current_entry = self.viewSettingsEntry.text().strip('"').strip("' ")
        if os.path.exists(current_entry) and (current_entry.lower().endswith(".viewsettings") ):
            fileName = current_entry
        else:
            fileName, _ = QFileDialog.getOpenFileName(self,"Select a HALO viewsettings file", path,"HALO viewsettigs (*.viewsettings)")
        # self.gvdata.last_system_folder_visited = os.path.normpath(pathlib.Path(fileName).parent)
        self.gvdata.view_settings_path = os.path.normpath(fileName)
        self.saveViewSettings() # Try to import
        self.viewSettingsEntry.clear()
        self.viewSettingsEntry.insert(pathlib.Path(fileName).name)

    ''' Called on button click'''
    def fetchObjectDataPath(self):
        path = self.gvdata.last_system_folder_visited

        print(f"path {path}")
        current_entry = self.dataEntry.text().strip('"').strip("' ")
        if os.path.exists(current_entry) and (current_entry.lower().endswith(".csv")):
            fileName = current_entry
        else:
            fileName, _ = QFileDialog.getOpenFileName(self,"Select a HALO Object Data file", path,"HALO Object Data (*.csv)")
        self.gvdata.last_system_folder_visited = os.path.normpath(pathlib.Path(fileName).parent)
        self.gvdata.objectDataPath = os.path.normpath(fileName)
        self.dataEntry.clear()
        self.dataEntry.insert(pathlib.Path(fileName).name)

    ''' Called on button click. Read a valid object data file and inform the user of the results'''
    def prefillObjectData(self, fetch = True):
        def _generate_no_anno_string(phenos):
            status = ''
            if phenos == 0:
                    status = f'<font color="#4c9b8f">Successfully processed <i>.csv</i> metadata! No annotations or phenotypes found, check your headers.</font>'
            elif phenos ==1:
                status = f'<font color="#4c9b8f">Successfully processed <i>.csv</i> metadata! Found one phenotype</font>'
            else:
                status = f'<font color="#4c9b8f">Successfully processed <i>.csv</i> metadata! Found {phenos} phenotypes</font>'
            return status
        def _generate_typical_string(annos,phenos):
            status = ''
            if annos !=1 and phenos == 0:
                    status = f'<font color="#4c9b8f">Successfully processed <i>.csv</i> metadata! Found {annos} annotations</font>'
            elif annos ==1 and phenos ==0:
                status = f'<font color="#4c9b8f">Successfully processed <i>.csv</i> metadata! Found one annotation</font>'
            else:
                status = f'<font color="#4c9b8f">Successfully processed <i>.csv</i> metadata! Found {annos} annotations and {phenos} phenotypes</font>'
            return status
        
        try:
            if fetch: 
                self.fetchObjectDataPath()
                # Have to reset the widgets here since these widgets could be filled out already
                self.reset_mappings(examine_object_data=False)
            # Now get information and pass to widgets
            res = self._prefillObjectData()
            annos = self.annotationCombo.count()
            phenos = self.phenotypeCombo.count()
            self.status_label.setVisible(True)
            
            if res == 'no annotations':
                status = _generate_no_anno_string(phenos)
                self.status_label.setText(status)
                self.setWidgetColorBackground(self.dataEntry, "#55ff55")
                QTimer.singleShot(800, lambda:self.setWidgetColorBackground(self.dataEntry, "#ffffff"))
            elif res == 'passed':
                status = _generate_typical_string(annos,phenos)
                self.status_label.setText(status)
                self.setWidgetColorBackground(self.dataEntry, "#55ff55")
                QTimer.singleShot(800, lambda:self.setWidgetColorBackground(self.dataEntry, "#ffffff"))
            elif res == 'name conflict':
                if annos == 0:
                    status = _generate_no_anno_string(phenos)
                else: status = _generate_typical_string(annos,phenos)
                status +='<br><font color="#ffa000">Warning - the image given has a different name than the image that was used to generate the object data</font>'
                self.status_label.setText(status)
                self.setWidgetColorBackground(self.dataEntry, "#4c9b8f")
                QTimer.singleShot(800, lambda:self.setWidgetColorBackground(self.dataEntry, "#ffffff"))
        
        except Exception as e:
            self._log_problem(e, error_type="csv-metadata-warning")
            # Inform user of possible issue
            self.status_label.setVisible(True)
            status = '<font color="#ffa000">Warning: Failed to properly ingest the file\'s metadata.\
              The viewer expects a QPTIFF from an Akoya Polaris,<br> and an object data <i>.csv</i> generated by a Halo analysis app.\
                It might have problems with this data.<br> Check the error logs.</font>'
            self.status_label.setText(status)
            self.setWidgetColorBackground(self.dataEntry, "#ffa000")
            QTimer.singleShot(800, lambda:self.setWidgetColorBackground(self.dataEntry, "#ffffff"))
    
    ''' Worker function to read and object data file and check for compatibility. Dynamic columns names present a challenge. 
            Tries to only pull in column data that is relevant. 
            Sets widgets to visible -- dependent on the data
            Also check if the image location in the data matches the image given'''
    def _prefillObjectData(self):
        headers = pd.read_csv(self.gvdata.objectDataPath, index_col=False, nrows=0).columns.tolist() 
        possible_fluors = self.gvdata.possible_fluors_in_data
        suffixes = self.gvdata.non_phenotype_fluor_suffixes_in_data
        exclude = self.gvdata.other_cols_in_data
        
        intens_ = ['Cell Intensity','Nucleus Intensity', 'Cytoplasm Intensity']

        include = [x for x in headers if any(f in x for f in intens_)]
        self.filterMarker.setVisible(False)
        self.filterMarkerCombo.setVisible(True)
        self.filterMarkerCombo.addItems(include)

        for fl in possible_fluors:
            for sf in suffixes:
                exclude.append(f'{fl} {sf}')
        include = [x for x in headers if ((x not in exclude) and not (any(f in x for f in possible_fluors)))]
        self.gvdata.phenotypes = include
        self.phenotypeToGrab.setVisible(False) #
        self.phenotypeCombo.setVisible(True) 
        self.phenotypeCombo.addItems(include)
        # Assess annotation regions in csv
        try:
            regions = list(pd.read_csv(self.gvdata.objectDataPath, index_col=False, usecols=['Analysis Region'])['Analysis Region'].unique()) 
            
            print(f"{self.gvdata.objectDataPath}   {regions}")
            self.annotationCombo.setVisible(True); self.annotationEdit.setVisible(False)
            self.annotationCombo.clear() ;  self.annotationEdit.clear() # Remove anything that's already there
            self.annotationCombo.addItems(regions)
            self.specificCellAnnotationCombo.setVisible(True); self.specificCellAnnotationEdit.setVisible(False)
            self.specificCellAnnotationCombo.clear() ; self.specificCellAnnotationEdit.clear() # Remove anything that is there
            self.specificCellAnnotationCombo.addItems(regions)
            if self.gvdata.specific_cell is not None:
                try:
                    self.specificCellAnnotationCombo.setCurrentText(self.gvdata.specific_cell['Annotation Layer'])
                except:
                    pass # If the user misspelled and annotation then just do nothing, it's fine
        except Exception as e:
            return 'no annotations'
        # Check if image location in CSV matches with image given to viewer
        try:
            im_location_csv = pd.read_csv(self.gvdata.objectDataPath, index_col=False, nrows=1, usecols=['Image Location']).iloc[0,0]
            # get everything after the last / , i.e. the image name.
            # Do it this way since some people use a mapped drive path, some use CIFS, some use UNC path with IP address
            im_name_csv = pathlib.Path(im_location_csv).name
        
            if im_name_csv != pathlib.Path(self.gvdata.image_path).name:
                return 'name conflict'
        except ValueError: 
            try: # Attempt to check the alternative column name that might be present
                im_location_csv = pd.read_csv(self.gvdata.objectDataPath, index_col=False, nrows=1, usecols=['Image File Name']).iloc[0,0]
                im_name_csv = pathlib.Path(im_location_csv).name
                
                if im_name_csv != pathlib.Path(self.gvdata.image_path).name:
                    return 'name conflict'
            except ValueError:
                pass 
            pass # No name columns that I know of, move on.
        return 'passed'

    ''' Helper to change a stylesheet for a label widget'''
    def setWidgetColorBackground(self, widg, color):
        widg.setStyleSheet(f"background: {color}")

    # def flashCorrect(self):
    #     self.textInput.configure(bg = 'green')
    #     self.window.after(150, self.resetInputColor)

    ''' Called on UI init and button click. Saves contents of entry box if it appears to be a valid image, or prompts the user to select one through
            the OS file system.'''
    def fetchImagePath(self):
        path = self.gvdata.last_system_folder_visited
        current_entry = self.imageEntry.text().strip('"').strip("' ")
        if os.path.exists(current_entry) and (current_entry.lower().endswith(".qptiff") or current_entry.lower().endswith(".tif")):
            fileName = current_entry
        else:
            fileName, _ = QFileDialog.getOpenFileName(self,"Select an image to load", path,"Akoya QPTIFF (*.qptiff);;Akoya QPTIFF (*.QPTIFF)")  
        
        self.gvdata.last_system_folder_visited = os.path.normpath(pathlib.Path(fileName).parent)
        self.gvdata.image_path = os.path.normpath(fileName)
        self.imageEntry.clear()
        self.imageEntry.insert(pathlib.Path(fileName).name)

    ''' Called on UI init and button click. Read a valid image file to parse the metadata and inform the user of the results'''
    def prefillImageData(self, fetch = True):
        try:
            if fetch:
                self.fetchImagePath()
            res = self._prefillImageData()
            if res == 'passed':
                self.status_label.setVisible(True)
                status = f'<font color="#4c9b8f">Successfully processed image metadata! {len(self.gvdata.channelOrder)} channel image is ready for viewing. </font>'
                self.status_label.setText(status)
                # self.previewImageDataButton.setEnabled(False)
                # self.previewImageDataButton.setStyleSheet(f"color: #4c9b8f")
                self.setWidgetColorBackground(self.imageEntry, "#55ff55")
                QTimer.singleShot(800, lambda:self.setWidgetColorBackground(self.imageEntry, "#ffffff"))
            elif res == 'name conflict':
                #TODO something here
                self.setWidgetColorBackground(self.imageEntry, "#ef881a")
                QTimer.singleShot(800, lambda:self.setWidgetColorBackground(self.imageEntry, "#ffffff"))
        except Exception as e:
            print(e)
            self.setWidgetColorBackground(self.imageEntry, "#ff5555")
            QTimer.singleShot(800, lambda:self.setWidgetColorBackground(self.imageEntry, "#ffffff"))

            self._log_problem(e, error_type="image-metadata-warning")
            # Inform user of possible issue
            self.status_label.setVisible(True)
            status = '<font color="#ffa000">Warning: Failed to properly ingest the files\' metadata.\
              The viewer expects a QPTIFF from an Akoya Polaris,<br> and an object data <i>.csv</i> generated by a Halo analysis app</font>'
            self.status_label.setText(status)
            # self.previewImageDataButton.setEnabled(False)
            # self.previewImageDataButton.setStyleSheet(f"color: #ffa000")
    
    ''' Helper function to attempt to get the TIF tag for PixelSizeMicrons'''
    def _retrieve_image_scale(self):
        ''' Get pixel per um value for the image'''
        try:
            # return None
            path = self.gvdata.image_path
            with tifffile.TiffFile(path) as tif:
                description = tif.pages[0].tags['ImageDescription'].value
            root = ET.fromstring(description)
            # QPTIFF only
            raw = [x.text.split("_")[0] for x in root.findall(".//PixelSizeMicrons")]
            val = min([float(x) for x in raw])
            return val
        except Exception as e:
            self._log_problem(e, error_type="scale-retrieve-failure")
            # exit()
            return None

    ''' Worker function that parses QPTIFF metadata looking for a few key pieces of information
            Looking for channel names, order in multichannel image, and color mappings
            Also configure checkboxes and dropdowns to '''
    def _prefillImageData(self):
        path = self.gvdata.image_path
        # Parse annoying TIF metadata
        # It seems to be stored in XML format under the 'ImageDescription' TIF tag. 
        with tifffile.TiffFile(path) as tif:
            description = tif.pages[0].tags['ImageDescription'].value
        root = ET.fromstring(description)
        # QPTIFF only
        sc = root.find(".//ScanColorTable")
        raw = sc.findall(".//")
        raw = [x.text.split("_")[0] for x in raw]
        fluors = {}
        for i in range(0,len(raw),2):
            fluors[raw[i]] = raw[i+1]
        
        ''' Preempt possibility of differences here'''
        def rename_key(key):
            af_possibilities = ["SampleAF", 'Sample AF', 'Autofluorescence']
            if key in af_possibilities: key = 'AF'
            return key
    
        # rename keys to ensure channels are mapped to a color we have a colormap for  
        for key in list(fluors.keys()):
            fluors[rename_key(key)] = fluors.pop(key).lower().replace('white', 'gray')
        fluors = {key : val.lower() for key, val in fluors.items()}
        unused_colors = copy.copy(self.gvdata.available_colors)
        for col in fluors.values():
            if col in unused_colors:
                unused_colors.remove(col)
        for key, value in fluors.items():
            if value in self.gvdata.available_colors: 
                continue
            else:
                if len(unused_colors) < 1:
                    random_color = choice(self.gvdata.available_colors)
                else:
                    random_color = choice(unused_colors)
                    unused_colors.remove(random_color)
                fluors[key] = random_color

        ''' Set everything to checked?'''
        for button in self.mycheckbuttons:
            button.setChecked(False)
            widget_name = button.objectName().replace("_"," ")
            print(f"WIDGET NAME IS {widget_name}")

            if widget_name in list(fluors.keys()):
                button.setChecked(True)
        # Save info to class
        print(f"TESTING HERE")
        print('\n')
        print(fluors)
        print('\n')
        self.gvdata.channelColors = fluors
        self.gvdata.channels = []
        for pos, fluor in enumerate(list(fluors.keys())):
            self.gvdata.channels.append(fluor)
            self.gvdata.channelOrder[fluor] = int(pos)
        
        self.saveChannel()
        self.setColors()
        return 'passed'

    #################################
    #        Viewer input cleanup          
    #################################

    '''Check to see if validation columns are in the data (won't be on first run)
            Put them in place if needed'''
    def _check_halo_validation_cols(self,df):
        missing = False
        for call_type in reversed(self.gvdata.statuses.keys()):
            missing = (f"Validation | {call_type}" not in df.columns) or missing
            
        if missing:
            for call_type in reversed(self.gvdata.statuses.keys()):
                try:
                    if call_type == 'Unseen':
                        df.insert(8,f"Validation | {call_type}", 1)
                    else:
                        df.insert(8,f"Validation | {call_type}", 0)  
                except ValueError:
                    pass# triggered when trying to insert column that already exists
    
    ''' Iterate through annotation mappings collected from user and assign new statuses to cells if needed'''
    def assign_annotation_statuses_to_sheet(self,df):
        l = list(set(self.gvdata.annotation_mappings.keys()))
        if (not self.gvdata.annotation_mappings):
            print("No annotation assignments")
            return df # break if user wants "All" for each

        elif (len(l) == 1) and (l[0] == "Don't assign"):
            print("Annotation(s) but no assignment")
            return df # Also break if there are no status mappings for any annotation
        
        print("Assignments to complete")
        self._append_status('Assigning decisions to annotations...')
        self._check_halo_validation_cols(df)
        sk = list(self.gvdata.statuses.keys())
        validation_cols = [f"Validation | " + s for s in sk]
        for annotation in self.gvdata.annotation_mappings.keys():
            status = self.gvdata.annotation_mappings[annotation]
            if status == "Don't assign":
                continue
            df.loc[df["Analysis Region"]==annotation, "Validation"] = status
        self._append_status('<font color="#7dbc39">  Done. </font>') 
        return df

    ''' Iterate through phenotype mappings collected from user and assign new statuses to cells if needed'''
    def assign_phenotype_statuses_to_sheet(self,df):
        l = list(set(self.gvdata.phenotype_mappings.keys()))
        if (not self.gvdata.phenotype_mappings):
            return df # break if user wants "All" 
        
        elif (len(l) == 1) and (l[0] == "Don't assign"):
            return df # Also break if there are no status mappings for any annotation
        
        self._append_status('Assigning decisions to phenotypes...')
        self._check_halo_validation_cols(df)
        sk = list(self.gvdata.statuses.keys())
        validation_cols = [f"Validation | " + s for s in sk]
        for phenotype in self.gvdata.phenotype_mappings.keys():
            status = self.gvdata.phenotype_mappings[phenotype]
            if status == "Don't assign":
                continue
            df.loc[df[phenotype] == 1, 'Validation'] = status
        self._append_status('<font color="#7dbc39">  Done. </font>')
        return df

    '''Find all unique annotation layer names, if the column exists in the data, and return the results'''
    def _locate_annotations_col(self, path):
        try:
            true_annotations = list(pd.read_csv(path, index_col=False, usecols=['Analysis Region'])['Analysis Region'].unique()) 
            self.gvdata.analysisRegionsInData = true_annotations
            return true_annotations
        except (KeyError, ValueError):
            print("No Analysis regions column in data")
            self.gvdata.analysisRegionsInData = False
            return None

    '''Check that annotations and phenotypes chosen by the user match the data. Return False if there is a mismatch. 
            Allowed to procees if the annotations column does not exist at all in the data.'''
    def _validate_names(self):
        # Get headers and unique annotations
        path = self.gvdata.objectDataPath
        headers = pd.read_csv(path, index_col=False, nrows=0).columns.tolist() 
        true_annotations = self._locate_annotations_col(path) # Find out if the data have multiple analysis regions (duplicate Cell IDs as well)
        if true_annotations is None: 
            self.annotationButton.setEnabled(False)
            self.annotationDisplay.setText('<u>Annotations</u><br>All')
            self.gvdata.annotation_mappings_label = '<u>Annotations</u><br>All'
            self.gvdata.annotation_mappings = {}
            self.specificCellAnnotationEdit.setVisible(False)
            self.specificCellAnnotationCombo.setVisible(False)
        
            return True # It's ok to have no annotation layer
        annotations = list(self.gvdata.annotation_mappings.keys())
        phenotypes = list(self.gvdata.phenotype_mappings.keys())
        # perform checks
        for anno in annotations:
            if anno not in true_annotations: return False
        for pheno in phenotypes:
            if pheno not in headers: return False
        return True
    
    def convert_from_halo_phenotypes(self, df: pd.DataFrame):
        v = list(self.gvdata.statuses.keys())
        validation_cols = [f"Validation | " + s for s in v]
        conds = [df[c] ==1 for c in validation_cols]
        choices = list(self.gvdata.statuses.keys())
        df['Validation'] = np.select(conds, choices, 'Unseen')
        df.drop(columns=validation_cols)
        return df
    
    def add_global_id(self, df:pd.DataFrame):
        if self.gvdata.analysisRegionsInData:
            df['gvid'] = df['Analysis Region'].astype(str) +' '+ df[self.gvdata.idcol].astype(str)
        else:
            # df.drop(columns=['Analysis Region'], inplace=True)
            df['gvid'] = df[self.gvdata.idcol].astype(str)    
        return df.set_index('gvid', drop=True)

    '''Read in the object data file and assign user chosen validation calls to the data, if needed'''
    def process_cell_table(self):
        self._replace_status('Reading object data... ')
        try:
            df = pd.read_csv(self.gvdata.objectDataPath)
        except FileNotFoundError:
            return "No file"
        self._append_status('<font color="#7dbc39">  Done. </font>')
        self._append_status_br('Validating chosen annotations and phenotypes...')
        if self._validate_names():
            try:
                # self._append_status_br('Saving data back to file...')
                # df.to_csv(self.gvdata.objectDataPath,index=False)
                # self._append_status('<font color="#7dbc39">  Done. </font>')
                self._check_halo_validation_cols(df)
                df = self.convert_from_halo_phenotypes(df)
                df = self.assign_phenotype_statuses_to_sheet(df)
                df = self.assign_annotation_statuses_to_sheet(df)
                df = self.add_global_id(df)
                self._append_status('<font color="#7dbc39">  Done. </font>')
                self.gvdata.objectDataFrame = df

                return 'Passed'
            except PermissionError:
                return 'PermissionError'
        else:
            return 'Bad input'
    
    def _replace_status(self, status):
        self.status_label.setVisible(True)
        self.status_label.setText(status)
        self.app.processEvents()

    def _append_status_br(self, status):
        self.status_label.setVisible(True)
        current = self.status_label.text()
        self.status_label.setText(current +'<br>'+ status)
        self.app.processEvents()

    def _append_status(self, status):
        self.status_label.setVisible(True)
        current = self.status_label.text()
        self.status_label.setText(current + status)
        self.app.processEvents()
    
    ''' Attempt to start viewer. Stop if there's an issue. Alert user with status label
            Store .gvconfig object to disk
            Set some final session parameters
            Call GUI_execute '''
    def beforeLoad(self):
        pass

    def loadGallery(self):
        # self.status_label.setVisible(True)
        # self.app.processEvents()
        self.findDataButton.setEnabled(False) # disable load button after click
        res = self.process_cell_table()
        if res == 'Bad input':
            # Will execute if the phenotypes / annotations given do not match to object data
            self.status_label.setVisible(True)
            status = '<font color="#f5551a">  Failed to assign status mappings</font><br>Check your annotations and phenotypes before trying again'
            self.status_label.setText(status)
            self.findDataButton.setEnabled(True)
            return None
        elif res == 'PermissionError':
            self.status_label.setVisible(True)
            self.status_label.setText('<font color="#f5551a">Access to object data file was denied</font><br>Close the sheet before trying again')
            self.findDataButton.setEnabled(True)
            return None
        elif res == "No file":
            self.status_label.setVisible(True)
            self.status_label.setText('<font color="#f5551a">Can\'t find the object data file.</font><br>Check the filepath input')
            self.findDataButton.setEnabled(True)
            return None

        storage_classes.storeObject(self.gvdata.user, 'profiles/active.gvconfig')
        self.gvdata.user.session.image_scale = self._retrieve_image_scale()
        # If user fetched metadata, save changes to color mappings
        # self.saveColors()

        # self.gvdata.channels.append("Composite")
        print(f'CHANNELS : {self.gvdata.channels}')
        print(f'CHANNELS ORDER : {self.gvdata.channelOrder}')
        print(f'CHANNELS colors : {self.gvdata.channelColors}')


        self.beforeLoad() # class-specific extras. Empty in this parent class
        try:
            print('Calling GUI execute...')
            # Reset stylesheet
            newStyle = ''
            # for elem in ["QLabel","QComboBox","QLineEdit","QPushButton","QCheckBox", "QSpinBox", "QGroupBox"]:
            #     if elem == "QGroupBox" or elem == "QPushButton":
            #         exec(f'newStyle += "{elem}{{font-size: {FONT_SIZE-10}pt;}}"')
            #     elif elem == QSpinBox:
            #         exec(f'newStyle += "{elem}{{font-size: {FONT_SIZE-10}pt;}}"')
            #     else:
            #         exec(f'newStyle += "{elem}{{font-size: {FONT_SIZE-10}pt;}}"')
            # self.app.setStyleSheet(newStyle)
            # self.processEvents()
            gui_execute(self)
        except Exception as e:
            # self.gvdata.user.session.zarr_store.close() # close zarr file??
            self._log_problem(e, error_type="runtime-crash")

#################################
#        Subclasses          
#################################

class GVUI_Halo(GVUI):
    def __init__(self, app: QApplication, tracker = None, gvdata: storage_classes.GVData | None = None):
        super().__init__(app, tracker, gvdata)
        self.UI_mode = "HALO"

    ''' Summon dialog box for changing image data channel order / fluorophore names'''
    def change_channels(self):
        channels = HaloChannelDialog(self, self.app, self.gvdata, self.topLeftGroupLayout, self.topLeftGroupBox , self.createLeftGroupBox)
        channels.exec()

class GVUI_Halo_MI(GVUI):
    def __init__(self, app: QApplication, tracker = None, gvdata: storage_classes.GVData | None = None):
        super().__init__(app, tracker, gvdata)
        self.UI_mode = "HALO Multi-Image"

    def beforeLoad(self):
        self.gvdata.user.session.image_display_name = pathlib.Path(self.gvdata.image_path).name # save name of image for display later

class GVUI_CosMx(GVUI):
    def __init__(self, app: QApplication, tracker = None, gvdata: storage_classes.GVData | None = None):
        super().__init__(app, tracker, gvdata, add_annotations=False)
        self.UI_mode = "CosMx"
        # self.init_top_layout()

    ''' Summon dialog box for changing image data channel order / fluorophore names'''
    def change_channels(self):
        channels = CosMxChannelDialog(self, self.app, self.gvdata, self.topLeftGroupLayout, self.topLeftGroupBox , self.createLeftGroupBox)
        channels.exec()

    def init_top_layout(self):
        self.titleLabel = QLabel(f'Tumor Cartography Core <font color="#033b96">Gallery</font><font color="#009ca6">Viewer</font> <font size=12pt>v{VERSION_NUMBER}</font>')
        # custom_font = QFont(); custom_font.setFamily('Metropolis Black'); custom_font.setPointSize(39)
        self.titleLabel.setStyleSheet('font-family: Metropolis ; font-size: 25pt')
        # titleLabel.setFont(QFont('MS Gothic',38))
        self.titleLabel.setAlignment(Qt.AlignCenter)

        ''' ComboBox for UI Mode '''
        self.UI_combo = ModeCombo(self,self.gvdata)
        self.UI_combo.currentTextChanged.connect(self.change_UI_mode)
        # entry box for .qptiff        
        self.imageEntry = QLineEdit()  # Put retrieved previous answer here
        # Want to do this in any case
        self.imageEntry.setVisible(False)
        self.imageEntry.setEnabled(False)

        self.dataEntry = QLineEdit()  # Put retrieved previous answer here
        self.dataEntry.setPlaceholderText('Enter path to viewer-compatible folder')
        self.dataEntry.setFixedWidth(800)

        self.previewObjectDataButton = QPushButton("Choose Data")
        self.previewObjectDataButton.setMaximumWidth(200)
        self.previewObjectDataButton.setDefault(True)
        self.previewImageDataButton = QPushButton("Choose Image")
        self.previewImageDataButton.setVisible(False)
        self.previewImageDataButton.setEnabled(False)
        
        self.viewSettingsEntry = QLineEdit()
        self.viewSettingsEntry.insert(pathlib.Path(self.gvdata.view_settings_path).name)
        self.viewSettingsEntry.setPlaceholderText('Enter path to a .viewsettings file (optional)')
        self.viewSettingsEntry.setFixedWidth(800)

        self.getViewsettingsPathButton = QPushButton("Import viewsettings")
        # self.getViewsettingsPathButton.setMaximumWidth(220)


        ''' Called on button click. Read a valid object data file and inform the user of the results'''
    
        ''' Called on button click'''
    
    def fetchObjectDataPath(self):
        path = self.gvdata.last_system_folder_visited

        print(f"path {path}")
        current_entry = self.dataEntry.text().strip('"').strip("' ")
        if os.path.exists(current_entry) and os.path.isdir():
            folder = current_entry
        else:
            folder = QFileDialog.getExistingDirectory(self,"Select a folder containing formatted CosMx data", path)
        self.gvdata.last_system_folder_visited = os.path.normpath(pathlib.Path(folder).parent)
        self.gvdata.objectDataPath = pathlib.Path(os.path.normpath(folder))
        self.dataEntry.clear()
        self.dataEntry.insert(pathlib.Path(folder).name)

    

    def _prefillObjectData(self):
        self.status_label.setText("Checking compatibility...")
        self.gvdata.cosmx_folder = self.gvdata.objectDataPath
        contents = [c.name for c in list(self.gvdata.cosmx_folder.iterdir())]

        if ('counts.h5ad' not in contents) or ('transcripts.parquet' not in contents) or ('images' not in contents): 
            return 'missing'
        imagecontents = [c.name for c in self.gvdata.cosmx_folder.joinpath("images").iterdir()]

        if ('.zattrs' not in imagecontents) or ('.zgroup' not in imagecontents):
            return 'not zarr'
        if 'labels' not in imagecontents:
            return 'no mask'
        
        imagecontents.remove('.zattrs') ; imagecontents.remove('.zgroup') ; imagecontents.remove('labels') 
        if any([x not in self.gvdata.channelFolders.values() for x in imagecontents]):
            return 'request reconfigure'
        

        
        self.gvdata.adata_path = self.gvdata.cosmx_folder.joinpath('counts.h5ad')
        self.gvdata.pqds = ds.dataset(self.gvdata.cosmx_folder.joinpath('transcripts.parquet'))

        self.gvdata.image_path = self.gvdata.cosmx_folder.joinpath('images')
        self.gvdata.cmeta = zarr.open(self.gvdata.image_path, mode = 'r+',).attrs['CosMx']
        self.gvdata.mm_per_px = self.gvdata.cmeta['scale_um'] / 1000
        self.gvdata.px_per_mm = 1 / self.gvdata.mm_per_px
        self.gvdata.px_per_um = self.gvdata.cmeta['scale_um']
        self.gvdata.fov_offsets = pd.DataFrame.from_dict(self.gvdata.cmeta['fov_offsets'])
        
        return 'pass'

    def prefillObjectData(self, fetch = True):

        try:
            if fetch: 
                self.fetchObjectDataPath()
                # Have to reset the widgets here since these widgets could be filled out already
                self.reset_mappings(examine_object_data=False)
            # Now get information and pass to widgets
            res = self._prefillObjectData()
            phenos = self.phenotypeCombo.count()
            self.status_label.setVisible(True)
            
            if res != 'pass':
                match res:
                    case 'missing':
                        status = 'The folder is missing required components'
                    case 'not zarr':
                        status = 'The images folder does not appear to be zarr format'
                    case 'request reconfigure':
                        status = 'Detected unfamiliar names in the images folder. Will assume they are fluor names.'
                    case 'no mask':
                        status = 'The images folder is missing cell masks'
                self.status_label.setText(status)
                self.setWidgetColorBackground(self.dataEntry, "#4c9b8f")
                QTimer.singleShot(800, lambda:self.setWidgetColorBackground(self.dataEntry, "#ffffff"))
            else:
                status = 'Pass'
                self.status_label.setText(status)
                self.setWidgetColorBackground(self.dataEntry, "#55ff55")
                QTimer.singleShot(800, lambda:self.setWidgetColorBackground(self.dataEntry, "#ffffff"))

        
        except Exception as e:
            self._log_problem(e, error_type="cosmx-metadata-warning")
            # Inform user of possible issue
            self.status_label.setVisible(True)
            status = '<font color="#ffa000">Unknown issue -- failed to properly ingest the folder\'s data.\
              The viewer expects a folder called <br> \'images\' created by the stitching tool, a transcripts<i>.parquet</i> generated by the stitching tool,<br>\
              and a counts.h5ad file (AnnData format). It might have problems with this data.<br> Check the error logs.</font>'
            self.status_label.setText(status)
            self.setWidgetColorBackground(self.dataEntry, "#ffa000")
            QTimer.singleShot(800, lambda:self.setWidgetColorBackground(self.dataEntry, "#ffffff"))

        '''Read in the object data file and assign user chosen validation calls to the data, if needed'''
    
    def process_cell_table(self):
        self._replace_status('Reading AnnData... ')
        try:
            adata  = ad.read_h5ad(self.gvdata.adata_path)
        except FileNotFoundError:
            return "No file"
        self._append_status('<font color="#7dbc39">  Done. </font>')
        self._append_status_br('Validating chosen phenotypes...')
        
        try:
            adata.obs["gvid"] = (adata.obs['cell_ID'].astype(int) + (adata.obs['fov'].astype(int) * 25_000)).astype(str)
            adata.obs.set_index('gvid', inplace = True)
            df = adata.obs
            df = self.assign_phenotype_statuses_to_sheet(df)
            self._append_status('<font color="#7dbc39">  Done. </font>')

            def tryall(a,b,c, m='min'):
                import math
                r1 = (a + b+c).min()
                r2 = (a + b-c).min()
                r3 = (a - b+c).min()
                r4 = (a - b-c).min()
                r5 = (-a + b+c).min()
                r6 = (-a + b-c).min()
                r7 = (-a - b+c).min()
                r8 = (-a - b-c).min()
                if m =='min':
                    n = 1_000_000
                    p = 1
                    for i,e in enumerate([r1,r2,r3,r4,r5,r6,r7,r8]):
                        if e < 0: 
                            continue
                        if n <=e:
                            continue
                        n = e
                        p = i
                    return(n,p)
                else:
                    n = 0
                    p = 1
                    for i,e in enumerate([r1,r2,r3,r4,r5,r6,r7,r8]):
                        if e < 0: 
                            continue
                        if n >=e:
                            continue
                        n = e
                        p = i
                    return (n,p)

            
            # I hate them for making me do this.
            self.gvdata.fov_offsets = pd.DataFrame.from_dict(self.gvdata.cmeta['fov_offsets'])
            self.gvdata.fov_offsets['fov'] = self.gvdata.fov_offsets['FOV'].astype(str)
            topleft = (min(self.gvdata.fov_offsets['Y_mm']), -max(self.gvdata.fov_offsets['X_mm']))
            #TODO put this stuff where it belongs
            df = pd.merge(df.reset_index(), self.gvdata.fov_offsets[['fov',"X_mm","Y_mm"]], on='fov').set_index('gvid')

            df['Validation'] = 'Unseen'
            df['Notes'] = '-'
            df['center_x'] = df['CenterY_local_px'] - (df['X_mm']* self.gvdata.px_per_mm) - (topleft[1]*self.gvdata.px_per_mm)
            df['center_y'] = df['CenterX_local_px'] + (df['Y_mm']*self.gvdata.px_per_mm) - (topleft[0]*self.gvdata.px_per_mm)

            df['XMin'] = df['center_x'] - (df['Width'] //2)
            df['XMax'] = df['center_x'] + (df['Width'] //2)
            df['YMin'] = df['center_y'] - (df['Height'] //2)
            df['YMax'] = df['center_y'] + (df['Height'] //2)
            df.rename(columns = {'CenterX_local_px' : 'fovY', 'CenterY_local_px': 'fovX'}, inplace=True) # Coord flip again.
            adata.obs = df
            self.gvdata.objectDataFrame = df
            self.gvdata.adata = adata

            return 'Passed'
        except PermissionError:
            return 'PermissionError'
    
    def beforeLoad(self):
        if self.gvdata.view_settings_path:
            pass
        else:
            for chn, folder in self.gvdata.channelFolders.items():
                metadata = zarr.open(self.gvdata.image_path, mode = 'r+',)[folder].attrs
                limits = metadata['omero']['channels'][0]['window']
                self.gvdata.view_settings[f'{chn} black-in'] = limits['start']
                self.gvdata.view_settings[f'{chn} white-in'] = limits['end']
                self.gvdata.contrastRanges[chn] = limits['min'],limits['max']
        print("Contrast ranges")
        print(self.gvdata.view_settings)
                



    ''' Helper function to attempt to get the TIF tag for PixelSizeMicrons'''
    def _retrieve_image_scale(self):
        ''' Get pixel per um value for the image'''
        return self.gvdata.px_per_um

class GVUI_Xenium(GVUI):
    def __init__(self, app: QApplication, tracker = None, gvdata: storage_classes.GVData | None = None):
        super().__init__(app, tracker, gvdata)
        self.UI_mode = "Xenium"

#################################
#            On exit          
#################################

''' Helper class for ensure_saving'''
class ThreadSave(QThread):
    def __init__(self, gallery:GVUI, target=None) -> None:
        super().__init__()
        self.target=target
        self.gallery=gallery
    def run(self):
        if self.target:
            self.target(self.gallery)

''' Clean-up function called on viewer exit. Handles data saving with a feedback loop in case of error that gives the user
        another chance to save their data. '''
def ensure_saving(gallery : GVUI, app) -> None:
    app.exec()
    window = QDialog()
    notice = QLabel()
    button = QPushButton()
    # old app has exited now
    if gallery.gvdata.user.session.saving_required:
        app = QApplication([])
        button.setVisible(False)
        
        window.setWindowTitle('Save Data')
        window.setWindowIcon(QIcon('data/mghiconwhite.png'))
        window.setWindowFlag(Qt.WindowTitleHint,False)
        window.setWindowFlag(Qt.WindowContextHelpButtonHint,False)
        
        window.setGeometry(200,200,1400,300) # 3rd and 4th args are width and height
        window.frameGeometry().moveCenter(QDesktopWidget().availableGeometry().center()) # center this window
        window.setStyleSheet('color:#075cbf ; font-size: 25pt')
        notice.setText('Saving scoring decisions, <font color="#a05459">the file will be locked until the operation is complete!</font>')
        notice.setAlignment(Qt.AlignCenter)

        # set layout
        layout = QGridLayout()
        layout.addWidget(notice,0,0)
        layout.addWidget(button,1,0)
        window.setLayout(layout)
        window.show()
        ''' Called on exit'''
        def begin_save(g):
            g.save_result = g.gvdata._save_validation(to_disk=True)
        ''' Called on ThreadSave exit. A check in case things still were not properly saved.'''
        def goodbye(gallery,app,window,notice,button, save_result):
            if save_result:
                notice.setText(notice.text()+'<br><font color="#7dbc39">  Done. </font>')
                # notice.setText('<font color="#7dbc39">  Done. </font>')
                print('Done saving.')
            else:
                print('Error. Looping here until saving works.')
                notice.setText(notice.text()+'<br><font color="#a05459"> There was a permissions issue - close your file? </font>')
                button.setText("Try to save again")
                button.setVisible(True)
                def retry(gallery, notice, app):
                    if gallery.gvdata._save_validation(to_disk=True): 
                        notice.setText('<font color="#7dbc39"> Scoring results saved. </font>')
                        app.processEvents()
                        time.sleep(2)
                        window.close()
                button.pressed.connect(lambda: retry(gallery, notice, app))
                notice.setText('<font color="#a05459">Can\'t access the save file! </font><br>Close your file and hit the button below')
                app.processEvents()
                return None # needed?
            
            time.sleep(2)
            window.close()
        try:      
            t = ThreadSave(gallery, target = begin_save)
            t.start()
            print('\nShould be saving data now...')
            t.finished.connect(lambda: goodbye(gallery,app,window,notice,button, gallery.save_result))
            app.exec()

        except Exception as e:
            save = False
            print('save issue!')
            gallery._log_problem(e, error_type="saving-error")
            notice.setText('<font color="#a05459">There was an issue.</font><br>Send the error log to Peter.')
        app.processEvents() 
    return None

if __name__ == '__main__':
    ''' This file is run directly to start the GUI. The main method here needs to initialize
    the QApplication
    '''
    
    # This gets python to tell Windows it is merely hosting another app
    # Therefore, the icon I've attached to the app before is displayed in the taskbar, instead of the python default icon. 
    myappid = 'MGH.CellGalleryViewer.v'+VERSION_NUMBER # arbitrary string
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    app = QApplication([])
    customStyle = ""
    for elem in ["QLabel","QLineEdit","QPushButton","QCheckBox", "QSpinBox", "QGroupBox"]:
        if elem == "QGroupBox" or elem == "QPushButton":
            exec(f'customStyle += "{elem}{{font-size: {FONT_SIZE+2}pt;}} "')
        elif elem == QSpinBox:
            exec(f'customStyle += "{elem}{{font-size: {FONT_SIZE-2}pt;}}"')
        else:
            exec(f'customStyle += "{elem}{{font-size: {FONT_SIZE}pt;}}"')
    customStyle += f"QComboBox{{font-size: {FONT_SIZE}pt;}}"
    app.setStyleSheet(customStyle)
    app.setStyle('Fusion')
    print("Launching UI")
    main = WindowTracker()
    gallery = main.start_application(app)
    gallery.show()
    sys.exit(ensure_saving(gallery,app))
    # sys.exit(app.exec_())
    print("\nI should never see this.")
