#############################################################################

import typing
from PyQt5.QtCore import QObject, Qt, QThread
from PyQt5.QtGui import QIcon, QPixmap,QColor,QFont
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,QMainWindow, QGridLayout, QDesktopWidget, 
                             QGroupBox, QLabel, QLineEdit,QPushButton, QSpinBox, QMenuBar, QAction)

import sys
import os
import time
import store_and_load
from galleryViewer import GUI_execute
import ctypes
import logging
from datetime import datetime
import os
import warnings
warnings.filterwarnings("ignore")
import pandas as pd
import copy

# Used in fetching and processing metadata
from random import choice
import tifffile
import xml.etree.ElementTree as ET
from re import sub
import webbrowser # for opening github
import warnings
warnings.catch_warnings

VERSION_NUMBER = '1.2.1'
FONT_SIZE = 12
#DAPI = 0; OPAL570 = 1; OPAL690 = 2; OPAL480 = 3; OPAL620 = 4; OPAL780 = 5; OPAL520 = 6; AF=7
CHANNELS_STR = ["DAPI", "OPAL570", "OPAL690", "OPAL480", "OPAL620", "OPAL780", "OPAL520", "AF"]
AVAILABLE_COLORS = ['gray', 'purple' , 'blue', 'green', 'orange','red', 'yellow', 'pink', 'cyan']
COLOR_TO_RGB = {'gray': '(170,170,170, 255)', 'purple':'(160,32,240, 255)', 'blue':'(100,100,255, 255)',
                    'green':'(60,179,113, 255)', 'orange':'(255,127,80, 255)', 'red': '(215,40,40, 255)',
                    'yellow': '(255,215,0, 255)', 'pink': '(255,105,180, 255)', 'cyan' : '(0,220,255, 255)'}
WIDGET_SELECTED = None

''' This class will be used for the dropdown menu that can assign a scoring decision to every cell 
    from an annotation layer or phenotype'''
class StatusCombo(QComboBox):
    def __init__(self, parent, userInfo):
        super(QComboBox, self).__init__(parent)
        # self.setVisible(False)
        self.addItem("Don't assign")
        self.setItemData(0,QColor(255,255,255,255),Qt.BackgroundRole)
        self.setItemData(0,QColor(0,0,0,255),Qt.ForegroundRole)
        for pos,status in enumerate(list(store_and_load.STATUSES.keys())):
            self.addItem(status)
            self.setItemData(pos+1,QColor(*userInfo.statuses_rgba[status]),Qt.BackgroundRole)
            self.setItemData(pos+1,QColor(0,0,0,255),Qt.ForegroundRole)
        self.setStyleSheet(f"background-color: rgba(255,255,255,255);color: rgb(0,0,0); selection-background-color: rgba(255,255,255,140);")
        self.activated.connect(lambda: self.set_bg(userInfo))
    
    def set_bg(self, userInfo):
        status = self.currentText()
        if status not in userInfo.statuses_rgba.keys():
            self.setStyleSheet(f"background-color: rgba(255,255,255,255);color: rgb(0,0,0); selection-background-color: rgba(255,255,255,140);")
        else:
            self.setStyleSheet(f"background-color: rgba{userInfo.statuses_rgba[status]};color: rgb(0,0,0);selection-background-color: rgba(255,255,255,140);")

''' This class contains the whole dialog box that the user interacts with and all it's widgets. Also contains
    an instance of the userPresets class, which will be passed to the viewer code. '''
class ViewerPresets(QDialog):
    def __init__(self, app, parent=None):
        super(ViewerPresets, self).__init__(parent)

        self.app = app
        # Arrange title bar buttons
        self.setWindowFlag(Qt.WindowMinimizeButtonHint, True)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        self.setWindowFlag(Qt.WindowTitleHint,False)
        # self.setWindowFlag(Qt.WindowContextHelpButtonHint,False)


        self.userInfo = store_and_load.loadObject('data/presets')

        # For TESTING
        print(f'Initial test print for colors: {self.userInfo.UI_color_display}')

        self.myColors = []
        self.setWindowIcon(QIcon('data/mghiconwhite.png'))

        # Set title area / logo
        cc_logo = QLabel()
        pixmap = QPixmap('data/mgh-mgb-cc-logo2 (Custom).png')
        cc_logo.setPixmap(pixmap)
        # f'<br><font color="{idcolor}">CID: {ID}</font>'
        titleLabel = QLabel(f'TCC Imaging Core <font color="#033b96">Gallery</font><font color="#009ca6">Viewer</font> <font size=12pt>v{VERSION_NUMBER}</font>')
        # custom_font = QFont(); custom_font.setFamily('Metropolis Black'); custom_font.setPointSize(39)
        titleLabel.setStyleSheet('font-family: Metropolis ; font-size: 25pt')
        # titleLabel.setFont(QFont('MS Gothic',38))
        titleLabel.setAlignment(Qt.AlignCenter)


        # reset status mappings for selected annotations and phenotypes
        new_pheno_label = '<u>Phenotype</u><br>'
        if not self.userInfo.phenotype_mappings.keys(): new_pheno_label +='All'
        for key in self.userInfo.phenotype_mappings:
            self.userInfo.phenotype_mappings[key] = "Don't assign"
            new_pheno_label += f'{key}<br>'
        self.userInfo.phenotype_mappings_label = new_pheno_label

        new_anno_label = '<u>Annotation Layer</u><br>'
        if not self.userInfo.annotation_mappings.keys(): new_anno_label +='All'
        for key in self.userInfo.annotation_mappings:
            self.userInfo.annotation_mappings[key] = "Don't assign"
            new_anno_label += f'{key}<br>'
        self.userInfo.annotation_mappings_label = new_anno_label


        # entry box for .qptiff        
        self.qptiffEntry = QLineEdit()  # Put retrieved previous answer here
        if self.userInfo.qptiff is not None:
            self.qptiffEntry.insert(self.userInfo.qptiff)
        # Want to do this in any case
        self.qptiffEntry.setPlaceholderText('Enter path to .qptiff')

        self.qptiffEntry.setFixedWidth(800)
        # qptiffEntry.setAlignment(Qt.AlignLeft)
        entryLabel = QLabel("Image: ")
        entryLabel.setBuddy(self.qptiffEntry)
        entryLabel.setAlignment(Qt.AlignCenter)
        entryLabel.setMaximumWidth(600)

        self.dataEntry = QLineEdit()  # Put retrieved previous answer here
        if self.userInfo.objectDataPath is not None:
            self.dataEntry.insert(self.userInfo.objectDataPath)
        self.dataEntry.setPlaceholderText('Enter path to .csv')
        self.dataEntry.setFixedWidth(800)
        # dataEntry.setAlignment(Qt.AlignLeft)
        dataEntryLabel = QLabel("Object Data: ")
        dataEntryLabel.setBuddy(self.dataEntry)
        dataEntryLabel.setAlignment(Qt.AlignCenter)
        dataEntryLabel.setMaximumWidth(600)

        self.previewObjectDataButton = QPushButton("Fetch CSV metadata")
        if "csv" not in self.dataEntry.text() :
            self.previewObjectDataButton.setEnabled(False)

        self.previewImageDataButton = QPushButton("Fetch image metadata")
        self.previewObjectDataButton.setDefault(True)
        if (".qptiff" not in self.qptiffEntry.text()) and (".tif" not in self.qptiffEntry.text()):
            self.previewImageDataButton.setEnabled(False)

        
        self.viewSettingsEntry = QLineEdit()
        self.viewSettingsEntry.insert(self.userInfo.view_settings_path)
        self.viewSettingsEntry.setPlaceholderText('Enter path to a .viewsettings file (optional)')
        self.viewSettingsEntry.setFixedWidth(800)

        viewSettingsLabel = QLabel("View Settings: ")
        viewSettingsLabel.setBuddy(self.viewSettingsEntry)
        viewSettingsLabel.setAlignment(Qt.AlignCenter)
        viewSettingsLabel.setMaximumWidth(600)

        # Push button to start reading image data and start up napari by remotely executing main method of main script
        self.findDataButton = QPushButton("Load images into viewer")
        self.findDataButton.setDefault(False)

        self.status_label = QLabel("init")
        self.status_label.setStyleSheet('color:#075cbf ; font-size: 15pt')
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setVisible(False)

        self.createTopLeftGroupBox()
        self.createTopRightGroupBox()
        # self.createProgressBar()

        self.findDataButton.pressed.connect(self.loadGallery)
        self.qptiffEntry.textEdited.connect(self.saveQptiff)
        self.dataEntry.textEdited.connect(self.saveObjectData)
        # self.viewSettingsEntry.textEdited.connect(self.saveViewSettings)
        self.previewObjectDataButton.pressed.connect(self.prefillObjectData)
        self.previewImageDataButton.pressed.connect(self.prefillImageData)

        # Menu bar
        self.menubar = QMenuBar()
        pref = self.menubar.addMenu('Preferences')
        manual = QAction("Open the manual", self)
        manual.setShortcut("Ctrl+M")
        reset = QAction("Reset GUI to defaults", self)
        reset.setShortcut("Ctrl+R")
        github = QAction("View source code",self)
        errors = QAction("Check error logs",self)
        errors.setShortcut("Ctrl+E")
        pref.addActions((manual,reset, errors, github))
        pref.triggered[QAction].connect(self.process_menu_action)

        topLayout = QGridLayout()
        # topLayout.addStretch(1)
        topLayout.addWidget(cc_logo,0,0)
        topLayout.addWidget(titleLabel,0,1)
        topLayout.setSpacing(20)
        topLayout.addWidget(entryLabel,1,0,1,0)
        topLayout.addWidget(self.qptiffEntry,1,1)
        topLayout.addWidget(self.previewImageDataButton,1,2)
        topLayout.addWidget(dataEntryLabel,2,0,1,0)
        topLayout.addWidget(self.dataEntry,2,1)
        topLayout.addWidget(viewSettingsLabel,3,0,1,0)
        topLayout.addWidget(self.previewObjectDataButton,2,2)
        topLayout.addWidget(self.viewSettingsEntry,3,1)
        # topLayout.addWidget(self.findDataButton,2,1)

        self.mainLayout = QGridLayout()
        self.mainLayout.setMenuBar(self.menubar)
        self.mainLayout.addLayout(topLayout, 0, 0, 1, 2)
        self.mainLayout.addWidget(self.topLeftGroupBox, 1, 0)
        self.mainLayout.addWidget(self.topRightGroupBox, 1, 1)
        # mainLayout.addWidget(self.bottomLeftTabWidget, 2, 0)
        # mainLayout.addWidget(self.bottomRightGroupBox, 2, 1)
        self.mainLayout.addWidget(self.findDataButton,2,0,1,0)
        self.mainLayout.addWidget(self.status_label,3,0,1,0)
        
        self.mainLayout.setRowStretch(1, 1)
        self.mainLayout.setRowStretch(2, 1)
        self.mainLayout.setColumnStretch(0, 1)
        self.mainLayout.setColumnStretch(1, 1)
        self.setLayout(self.mainLayout)

        self.setWindowTitle(f"GalleryViewer v{VERSION_NUMBER}")

    def process_menu_action(self,q):
        if 'manual' in q.text().lower():
            try:
                # print(os.path.normpath(os.curdir+ r"/data/GalleryViewer v{x} User Guide.pdf".format(x=VERSION_NUMBER)))
                os.startfile(os.path.normpath(os.curdir+ r"/data/GalleryViewer v{x} User Guide.pdf".format(x=VERSION_NUMBER)))
            except FileNotFoundError:
                self.status_label.setVisible(True)
                status ='<font color="#ffa000">Can\'t find a guide for this version!</font><br>Check for old versions in the server\'s Imagers/ImageProcessing/GalleryViewer/ folder.'
                self.status_label.setText(status)
        elif 'reset' in q.text().lower():
            os.remove(os.path.normpath(r'./data/presets'))
            self.status_label.setVisible(True)
            status ='<br><font color="#ffa000">Cleared all saved metadata!</font> Close this window to allow the changes to take effect'
            self.status_label.setText(status)
        elif 'source code' in q.text().lower():
            webbrowser.open("https://github.com/richierip/CTC-Gallery-Viewer", new = 2)
        elif "error logs" in q.text().lower():
            os.startfile(os.path.normpath(r"./runtime logs"))
            errors = 0
            for root, cur, files in os.walk(os.path.normpath(r"./runtime logs")):
                errors += len(files)
            self.status_label.setVisible(True)
            status =f'Found {errors} error logs! If you are having trouble, try resetting the viewer\'s saved preferences (ctrl+R) and restarting the program.<br> '
            status += 'Previewing image and object csv metadata can fix issues too.<br> If problems persist, share these logs with Peter at prichieri@mgh.harvard.edu.'
            self.status_label.setText(status)


    def saveQptiff(self):
        self.userInfo.qptiff = os.path.normpath(self.qptiffEntry.text().strip('"')).strip('.')
        if (".qptiff" in self.qptiffEntry.text()) or (".tif" in self.qptiffEntry.text()):
            self.previewImageDataButton.setEnabled(True)
        else:
            self.previewImageDataButton.setEnabled(False)
    def saveObjectData(self):
        self.userInfo.objectDataPath = os.path.normpath(self.dataEntry.text().strip('"')).strip('.')
        if ".csv" in self.dataEntry.text():
            self.previewObjectDataButton.setEnabled(True)
        else:
            self.previewObjectDataButton.setEnabled(False)

    def saveViewSettings(self):
        self.userInfo.view_settings_path = os.path.normpath(self.viewSettingsEntry.text().strip('"')).strip('.')
        try:
            if self.userInfo.view_settings_path:
                df = pd.read_xml(self.userInfo.view_settings_path)
                self.userInfo.transfer_view_settings(df)
            # print("Success!")
            # print(self.userInfo.view_settings)
        except Exception as e:
            folder = os.path.normpath(os.path.join(os.getcwd(), 'runtime logs/'))
            if not os.path.exists(folder):
                os.makedirs(folder)
            logpath = os.path.normpath(os.path.join(folder, datetime.today().strftime('%Y-%m-%d_silent_viewsettings_issue_%H%M%S.txt')))
            self.userInfo.view_settings = store_and_load.VIEW_SETTINGS # use defaults
            self._log_problem(logpath,e)

    def saveSpecificCell(self):
        try:
            if self.specificCellChoice.text() == '':
                self.userInfo.specific_cell = None
            elif self.specificCellAnnotationCombo.isVisible():
                self.userInfo.specific_cell = {'ID': str(int(self.specificCellChoice.text())),
                                            'Annotation Layer': self.specificCellAnnotationCombo.currentText()}
            else:
                self.userInfo.specific_cell = {'ID': str(int(self.specificCellChoice.text())),
                                           'Annotation Layer': self.specificCellAnnotationEdit.text()}
        except:
            print('Bad input to "Specific Cell" widget. Saving as NoneType')
            self.userInfo.specific_cell = None
    def saveImageSize(self):
        self.userInfo.imageSize = self.imageSize.value()
    def savePageSize(self):
        self.userInfo.page_size = self.page_size_widget.value()
        self.row_size_widget.setRange(2,self.userInfo.page_size)
    def saveRowSize(self):
        self.userInfo.cells_per_row = self.row_size_widget.value()
        print(f"Row size is now {self.userInfo.cells_per_row}")
    def saveGlobalSort(self):
        print("Saving global sort")
        self.userInfo.global_sort = self.global_sort_widget.currentText()

    def saveChannel(self):
        print(f'\nTrying to save the channel')
        for button in self.mycheckbuttons:
            channelName = button.objectName()
            print(f"{channelName} and {self.userInfo.channels}")
            if button.isChecked():
                self.userInfo.attempt_channel_add(channelName)
            elif not button.isChecked():
                self.userInfo.attempt_channel_remove(channelName)

    def saveColors(self):
        for colorWidget in self.myColors:
            # Set each the color of each QSpin
            colorWidget.setStyleSheet(f"background-color: rgba{COLOR_TO_RGB[colorWidget.currentText()]};color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
            

            # print(f'My trigger was {colorWidget.objectName()}')
            colorChannel = colorWidget.objectName()
            # print(f'#### Channel order fsr: {store_and_load.CHANNELS_STR} \n')
            colorPos = store_and_load.CHANNELS_STR.index(colorChannel)
            # print(f'2. Position of {colorChannel} in CHANNEL_ORDER is {colorPos}')
            self.userInfo.UI_color_display.pop(colorPos)
            # print(f'3. Our intermediate step is this: {self.userInfo.UI_color_display}')
            self.userInfo.UI_color_display.insert(colorPos, colorWidget.currentText())
            # print(f'4. Now color should be in right spot. Here is the thing {self.userInfo.UI_color_display}')

            # # Now do it for visual display:
            # colorPos = CHANNELS_STR.index(colorChannel)
            # self.userInfo.UI_color_display.pop(colorPos)
            # self.userInfo.UI_color_display.insert(colorPos, colorWidget.currentText())
            # Save info to channelOrder
            self.userInfo.channelOrder[colorChannel] = colorWidget.currentText()

    def addAnnotation(self):
        # Get status and color from combobox
        status = self.annotationStatuses.currentText()
        if status in self.userInfo.statuses_rgba.keys():
            status_color = self.userInfo.statuses_rgba[status][:-1]
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
        self.userInfo.annotation_mappings_label = self.annotationDisplay.text()
        self.userInfo.annotation_mappings[anno] = status
    
    def addPheno(self):
        # Get status and color from combobox
        status = self.phenotypeStatuses.currentText()
        print(f'Status is {status}')
        if status in self.userInfo.statuses_rgba.keys():
            status_color = self.userInfo.statuses_rgba[status][:-1]
        else: status_color = (0,0,0)
        # convert to hex
        status_color = '#%02x%02x%02x' % status_color
        print(status_color)

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
        self.userInfo.phenotype_mappings_label = self.phenoDisplay.text()
        self.userInfo.phenotype_mappings[pheno] = status

    def reset_mappings(self):
        self.userInfo.phenotype_mappings = {}
        self.userInfo.phenotype_mappings_label = '<u>Phenotype</u><br>All'
        self.phenoDisplay.setText('<u>Phenotype</u><br>All')
        self.userInfo.annotation_mappings = {}
        self.userInfo.annotation_mappings_label = '<u>Annotation Layer</u><br>All'
        self.annotationDisplay.setText('<u>Annotation Layer</u><br>All')

        # Refresh comboboxes
        if self.phenotypeCombo.isVisible() or self.annotationCombo.isVisible():
            self.phenotypeCombo.clear()
            self.annotationCombo.clear()
            self.prefillObjectData()

    def _log_problem(self, logpath, e):
        # Log the crash and report key variables

        params = f"\nImage path: {self.userInfo.qptiff} \nData path: {self.userInfo.objectDataPath}\n"
        params += f"Punchout size: {self.userInfo.imageSize} \nUser selected channels: {self.userInfo.channels}\n"
        params += f"Available colors: {store_and_load.CELL_COLORS} \n"
        params += f"Batch/page size: {self.userInfo.page_size} \nSort: {self.userInfo.global_sort}\n"
        params += f"Specific cell chosen?: {self.userInfo.specific_cell} \nExpected order of multichannel data: {self.userInfo.channelOrder}\n"
        params += f"Phenotype mappings: {self.userInfo.phenotype_mappings}\n"
        params += f"Annotation mappings: {self.userInfo.annotation_mappings}\n"
        params += f"View settings path: {self.userInfo.view_settings_path}\n"
        params += f"View settings: {self.userInfo.view_settings}\n"
        params += f"Available statuses: {self.userInfo.statuses}"
        logging.basicConfig(filename=logpath, encoding='utf-8', level=logging.DEBUG)
        logging.exception(f"{params}\n ------ Autogenerated crash report ------ \n{e}")

    def prefillObjectData(self):
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
            res = self._prefillObjectData()
            annos = self.annotationCombo.count()
            phenos = self.phenotypeCombo.count()
            self.previewObjectDataButton.setEnabled(False)
            self.status_label.setVisible(True)


            if res == 'no annotations':
                status = _generate_no_anno_string(phenos)
                self.status_label.setText(status)
                self.previewObjectDataButton.setStyleSheet(f"color: #4c9b8f") 
            elif res == 'passed':
                status = _generate_typical_string(annos,phenos)
                self.status_label.setText(status)
                self.previewObjectDataButton.setStyleSheet(f"color: #4c9b8f")
            elif res == 'name conflict':
                if annos == 0:
                    status = _generate_no_anno_string(phenos)
                else: status = _generate_typical_string(annos,phenos)
                status +='<br><font color="#ffa000">Warning - the image given has a different name than what was used to generate the object data</font>'
                self.status_label.setText(status)
                self.previewObjectDataButton.setStyleSheet(f"color: #ffa000")
        except Exception as e:
            folder = os.path.normpath(os.path.join(os.getcwd(), 'runtime logs/'))
            if not os.path.exists(folder):
                os.makedirs(folder)
            logpath = os.path.normpath(os.path.join(folder, datetime.today().strftime('%Y-%m-%d_csv_metadata_warning_%H%M%S.txt')))
            self._log_problem(logpath,e)
            # Inform user of possible issue
            self.status_label.setVisible(True)
            status = '<font color="#ffa000">Warning: Failed to properly ingest the file\'s metadata.\
              The viewer expects a QPTIFF from an Akoya Polaris,<br> and an object data <i>.csv</i> generated by a Halo analysis app. It might have problems with this data.</font>'
            self.status_label.setText(status)
            self.previewObjectDataButton.setEnabled(False)
            self.previewObjectDataButton.setStyleSheet(f"color: #ffa000")
    
    def _prefillObjectData(self):
        path = self.dataEntry.text().strip('"')
        if ".csv" not in path:
            return None
        headers = pd.read_csv(path, index_col=False, nrows=0).columns.tolist() 
        possible_fluors = ['DAPI','Opal 480','Opal 520', 'Opal 570', 'Opal 620','Opal 690', 'Opal 720', 'AF', 'Sample AF', 'Autofluorescence']
        suffixes = ['Positive Classification', 'Positive Nucleus Classification','Positive Cytoplasm Classification',
                    'Cell Intensity','Nucleus Intensity', 'Cytoplasm Intensity', '% Nucleus Completeness', '% Cytoplasm Completeness',
                    '% Cell Completeness', '% Completeness']
        exclude = ['Cell Area (µm²)', 'Cytoplasm Area (µm²)', 'Nucleus Area (µm²)', 'Nucleus Perimeter (µm)', 'Nucleus Roundness',
                  'Image Location','Image File Name', 'Analysis Region', 'Algorithm Name', 'Object Id', 'XMin', 'XMax', 'YMin', 'YMax', 'Notes']

        for fl in possible_fluors:
            for sf in suffixes:
                exclude.append(f'{fl} {sf}')
        include = [x for x in headers if ((x not in exclude) and not (any(f in x for f in possible_fluors)))]
        
        self.phenotypeToGrab.setVisible(False) #
        self.phenotypeCombo.setVisible(True) 
        self.phenotypeCombo.addItems(include)
        # Assess annotation regions in csv
        try:
            regions = list(pd.read_csv(path, index_col=False, usecols=['Analysis Region'])['Analysis Region'].unique()) 
            print(regions)
            self.annotationCombo.setVisible(True); self.annotationEdit.setVisible(False)
            self.annotationCombo.addItems(regions)
            self.specificCellAnnotationCombo.setVisible(True); self.specificCellAnnotationEdit.setVisible(False)
            self.specificCellAnnotationCombo.addItems(regions)
            if self.userInfo.specific_cell is not None:
                try:
                    self.specificCellAnnotationCombo.setCurrentText(self.userInfo.specific_cell['Annotation Layer'])
                except:
                    pass # If the user misspelled and annotation then just do nothing, it's fine
        except Exception as e:
            return 'no annotations'
        # Check if image location in CSV matches with image given to viewer
        try:
            im_location_csv = pd.read_csv(path, index_col=False, nrows=1, usecols=['Image Location']).iloc[0,0]
            # get everything after the last / , i.e. the image name.
            # Do it this way since some people use a mapped drive path, some use CIFS, some use UNC path with IP address
            im_name_csv = sub(r'.*?\\',"", im_location_csv) 
            path = self.userInfo.qptiff
            if im_name_csv != sub(r'.*?\\',"", path):
                return 'name conflict'
        except ValueError: 
            try: # Attempt to check the alternative column name that might be present
                im_location_csv = pd.read_csv(path, index_col=False, nrows=1, usecols=['Image File Name']).iloc[0,0]
                path = self.userInfo.qptiff
                if im_name_csv != sub(r'.*?\\',"", path):
                    return 'name conflict'
            except ValueError:
                pass 
            pass # No name columns that I know of, move on.
        return 'passed'

    def prefillImageData(self):
        try:
            res = self._prefillImageData()
            if res == 'passed':
                self.status_label.setVisible(True)
                status = f'<font color="#4c9b8f">Successfully processed image metadata! {len(self.userInfo.channelOrder)} channel image is ready for viewing. </font>'
                self.status_label.setText(status)
                self.previewImageDataButton.setEnabled(False)
                self.previewImageDataButton.setStyleSheet(f"color: #4c9b8f")
            elif res == 'name conflict':
                pass #TODO something here
        except Exception as e:
            folder = os.path.normpath(os.path.join(os.getcwd(), 'runtime logs/'))
            if not os.path.exists(folder):
                os.makedirs(folder)
            logpath = os.path.normpath(os.path.join(folder, datetime.today().strftime('%Y-%m-%d_image_metadata_warning_%H%M%S.txt')))
            self._log_problem(logpath,e)
            # Inform user of possible issue
            self.status_label.setVisible(True)
            status = '<font color="#ffa000">Warning: Failed to properly ingest the files\' metadata.\
              The viewer expects a QPTIFF from an Akoya Polaris,<br> and an object data <i>.csv</i> generated by a Halo analysis app</font>'
            self.status_label.setText(status)
            self.previewImageDataButton.setEnabled(False)
            self.previewImageDataButton.setStyleSheet(f"color: #ffa000")

    def _retrieve_image_scale(self):
        ''' Get pixel per um value for the image'''
        try:
        #     return None
            path = self.userInfo.qptiff
            with tifffile.TiffFile(path) as tif:
                description = tif.pages[0].tags['ImageDescription'].value
            root = ET.fromstring(description)
            # QPTIFF only
            raw = [x.text.split("_")[0] for x in root.findall(".//PixelSizeMicrons")]
            val = min([float(x) for x in raw])
            return val
        except Exception as e:
            folder = os.path.normpath(os.path.join(os.getcwd(), 'runtime logs/'))
            if not os.path.exists(folder):
                os.makedirs(folder)
            logpath = os.path.normpath(os.path.join(folder, datetime.today().strftime('%Y-%m-%d_scale_retrieve_failure_%H%M%S.txt')))
            self._log_problem(logpath,e)
            # exit()
            return None



    def _prefillImageData(self):
        path = self.userInfo.qptiff
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
        
        def rename_key(key):
            af_possibilities = ["SampleAF", 'Sample AF', 'Autofluorescence']
            if key in af_possibilities: key = 'AF'
            return key.replace(" ", '').upper()
        # rename keys 
        for key in list(fluors.keys()):
            fluors[rename_key(key)] = fluors.pop(key).lower().replace('white', 'gray').replace('lime','green').replace('pink','Pink')
        print(fluors)
        unused_colors = copy.copy(AVAILABLE_COLORS)
        for col in fluors.values():
            if col in unused_colors:
                unused_colors.remove(col)
        
        for key, value in fluors.items():
            if value in AVAILABLE_COLORS: 
                continue
            else:
                if len(unused_colors) < 1:
                    random_color = choice(AVAILABLE_COLORS)
                else:
                    random_color = choice(unused_colors)
                    unused_colors.remove(random_color)
                fluors[key] = random_color
        print(fluors)

        # Change display widgets to reflect change
        for pos,combo in enumerate(self.myColors):
            widget_name = combo.objectName()
            widget_color = fluors[widget_name]
            # print(widget_name +  "  |  " + widget_color)
            # colorComboName = button.objectName() + "_colors"
            combo.setCurrentText(widget_color)
            combo.setStyleSheet(f"background-color: rgba{COLOR_TO_RGB[widget_color]};color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
        for button in self.mycheckbuttons:
            button.setChecked(False)
            widget_name = button.objectName()
            if widget_name in list(fluors.keys()):
                button.setChecked(True)
        
        # Save info to class
        self.userInfo.channelOrder = fluors
        display_list =  sorted(fluors.items())
        display_list = [x[1] for x in display_list]
        display_list.append(display_list.pop(0))
        self.userInfo.UI_color_display = display_list
        self.saveChannel()
        # self.saveColors()
        return 'passed'

            
    def createTopLeftGroupBox(self):
        self.topLeftGroupBox = QGroupBox("Channels and Colors")

        self.dapiCheck = QCheckBox("DAPI"); self.dapiCheck.setObjectName('DAPI')
        self._480Check = QCheckBox("Opal 480"); self._480Check.setObjectName('OPAL480')
        self._520Check = QCheckBox("Opal 520"); self._520Check.setObjectName('OPAL520')
        self._570Check = QCheckBox("Opal 570"); self._570Check.setObjectName('OPAL570')
        self._620Check = QCheckBox("Opal 620"); self._620Check.setObjectName('OPAL620')
        self._690Check = QCheckBox("Opal 690"); self._690Check.setObjectName('OPAL690')
        self._780Check = QCheckBox("Opal 780"); self._780Check.setObjectName('OPAL780')
        self.autofluorescenceCheck = QCheckBox("AF"); self.autofluorescenceCheck.setObjectName('AF')
        self.mycheckbuttons= [self.dapiCheck, self._480Check, self._520Check, self._570Check,self._620Check, self._690Check, self._780Check, self.autofluorescenceCheck]
        
        layout = QGridLayout()
        
        def create_func(colorWidget):
            def set_color_index(index):
                # return None
                # for colorWidget in self.myColors:
                if index ==0: # gray
                    colorWidget.setStyleSheet(f"selection-background-color: rgba(170,170,170, 255);selection-color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
                elif index ==1: # purple
                    colorWidget.setStyleSheet(f"selection-background-color: rgba(160,32,240, 255);selection-color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
                elif index ==2: # blue
                    colorWidget.setStyleSheet(f"selection-background-color: rgba(100,100,255, 255);selection-color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
                elif index ==3: # green
                    colorWidget.setStyleSheet(f"selection-background-color: rgba(60,179,113, 255);selection-color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
                elif index ==4: # orange
                    colorWidget.setStyleSheet(f"selection-background-color: rgba(255,127,80, 255);selection-color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
                elif index ==5: # red
                    colorWidget.setStyleSheet(f"selection-background-color: rgba(215,40,40, 255);selection-color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
                elif index ==6: # yellow
                    colorWidget.setStyleSheet(f"selection-background-color: rgba(255,215,0, 255);selection-color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
                elif index ==7: # cyan
                    colorWidget.setStyleSheet(f"selection-background-color: rgba(0,220,255, 255);selection-color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
                elif index ==8: # pink
                    colorWidget.setStyleSheet(f"selection-background-color: rgba(255,105,180, 255);selection-color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
                
                # colorWidget.setStyleSheet(f"color: {colorWidget.currentText()}; font-size: {FONT_SIZE}pt;")
            return set_color_index 
        # Space / time saving way to create 16 widgets and change their parameters
        for pos,button in enumerate(self.mycheckbuttons):
            colorComboName = button.objectName() + "_colors"
            exec(f'{colorComboName} = QComboBox()')
            colored_items = [f'<font color="{item}">{item}</font>' for item in store_and_load.CELL_COLORS]
            exec(f'{colorComboName}.addItems(store_and_load.CELL_COLORS)')
            exec(f'{colorComboName}.setCurrentText("{self.userInfo.UI_color_display[pos]}")')

            # exec(f'{colorComboName}.setItemData(0,QColor("red"),Qt.ForegroundRole)')
            # test = QComboBox()
            # test.setItemData(0,value=QColor('red'))

            # colorWidget.setItemData(0,QColor("red"),Qt.BackgroundRole)

            exec(f'{colorComboName}.setItemData(1,QColor(100,100,100,0),Qt.BackgroundRole)') # gray
            exec(f'{colorComboName}.setItemData(1,QColor(0,0,0,255),Qt.ForegroundRole)')
            exec(f'{colorComboName}.setItemData(1,QColor(160,32,240,0),Qt.BackgroundRole)') # purple
            exec(f'{colorComboName}.setItemData(1,QColor(0,0,0,255),Qt.ForegroundRole)')
            exec(f'{colorComboName}.setItemData(2,QColor(20,20,255,0),Qt.BackgroundRole)') # blue
            exec(f'{colorComboName}.setItemData(2,QColor(0,0,0,255),Qt.ForegroundRole)')
            exec(f'{colorComboName}.setItemData(3,QColor(0,255,0,0),Qt.BackgroundRole)') # green
            exec(f'{colorComboName}.setItemData(3,QColor(0,0,0,255),Qt.ForegroundRole)')
            exec(f'{colorComboName}.setItemData(4,QColor(255,0,0,0),Qt.BackgroundRole)') # red
            exec(f'{colorComboName}.setItemData(4,QColor(0,0,0,255),Qt.ForegroundRole)') 
            exec(f'{colorComboName}.setItemData(5,QColor(255,165,0,0),Qt.BackgroundRole)') # orange
            exec(f'{colorComboName}.setItemData(5,QColor(0,0,0,255),Qt.ForegroundRole)')
            exec(f'{colorComboName}.setItemData(6,QColor(255,255,0,0),Qt.BackgroundRole)')# yellow
            exec(f'{colorComboName}.setItemData(6,QColor(0,0,0,255),Qt.ForegroundRole)')
            exec(f'{colorComboName}.setItemData(7,QColor(0,255,255,0),Qt.BackgroundRole)') # cyan
            exec(f'{colorComboName}.setItemData(7,QColor(0,0,0,255),Qt.ForegroundRole)')
            exec(f'{colorComboName}.setItemData(8,QColor(255,0,255,0),Qt.BackgroundRole)') # pink
            exec(f'{colorComboName}.setItemData(8,QColor(0,0,0,255),Qt.ForegroundRole)')

            
            # exec(f'{colorComboName}.setStyleSheet("background-color: rgb(0,0,0); selection-background-color: rgba(255,255,255,1);selection-color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")')
            # exec(f'{colorComboName}.setStyleSheet("selection-background-color: rgba(255,0,0,255);selection-color: rgb(255,255,255); font-size:{FONT_SIZE}pt;")')
            # exec(f'{colorComboName}.setStyleSheet("color:{self.userInfo.UI_color_display[pos]};font-size:{FONT_SIZE}pt;")')

            # create function that will be attached to this ComboBox only
            exec(f'combo_highlighted = create_func({colorComboName})')
            
            exec(f'{colorComboName}.highlighted[int].connect(combo_highlighted)')
            # exec(f'{colorComboName}.highlighted[int].connect(helper_exec)')
            # src = f'{colorComboName}.highlighted[int].connect(lambda x: print(dir()) )'
             
            # exec(f'{colorComboName}.highlighted.connect(change_color)')
            exec(f'{colorComboName}.setObjectName("{button.objectName()}")')
            if button.objectName() in self.userInfo.channels and button.objectName != 'AF':
                button.setChecked(True)
            else:
                button.setChecked(False)
            button.toggled.connect(self.saveChannel) #IMPORTANT that this comes after setting check values
            exec(f'self.myColors.append({colorComboName})')
            exec(f'{colorComboName}.activated.connect(self.saveColors)')
            col = [0,0,0,0,2,2,2,2][pos]
            layout.addWidget(button, pos%4,col)
            exec(f'layout.addWidget({colorComboName},{pos%4}, {col+1})')

            
        for colorWidget in self.myColors:
            # Set each the color of each QSpin
            colorWidget.setStyleSheet(f"background-color: rgba{COLOR_TO_RGB[colorWidget.currentText()]};color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")

        self.topLeftGroupBox.setLayout(layout)    
    
    def createTopRightGroupBox(self):
        self.topRightGroupBox = QGroupBox("Cells to Read")

        # self.explanationLabel0 = QLabel("Custom object data <b>phenotype<b>")
        # self.explanationLabel1 = QLabel("Pull from an <b>annotation layer<b>")
        explanationLabel2 = QLabel("Cell image size in <b>pixels</b>")
        explanationLabel3 = QLabel("Number of cells <b>per page<b>")
        explanationLabel4 = QLabel("Number of cells <b>per row<b>")
        explanationLabel5 = QLabel("Load the page with this <b>Cell ID<b>")
        # self.explanationLabel0.setAlignment(Qt.AlignRight)
        # self.explanationLabel1.setAlignment(Qt.AlignRight)
        # explanationLabel2.setAlignment(Qt.AlignRight)
        # explanationLabel3.setAlignment(Qt.AlignRight)
        # explanationLabel4.setAlignment(Qt.AlignRight)
        # explanationLabel5.setAlignment(Qt.AlignRight)
        # explanationLabel5 = QLabel("Number of cells <b>per row<b>")
        self.phenotypeButton = QPushButton("Add Phenotype")
        self.phenotypeButton.setStyleSheet(f"QPushButton {{ font-size: 22px}}")
        self.phenotypeButton.pressed.connect(self.addPheno)
        self.annotationButton = QPushButton("Add Annotation Layer")
        self.annotationButton.setStyleSheet(f"QPushButton {{ font-size: 22px}}")
        self.annotationButton.pressed.connect(self.addAnnotation)

        #TODO attach previous choice here
        self.phenotypeToGrab = QLineEdit(self.topRightGroupBox)
        self.phenotypeToGrab.setPlaceholderText('Phenotype of Interest')
        self.phenotypeToGrab.setFixedWidth(220)
        self.phenotypeCombo = QComboBox(self.topRightGroupBox)
        self.phenotypeCombo.setVisible(False)
        self.phenotypeStatuses = StatusCombo(self.topRightGroupBox, self.userInfo)
        

        # Annotation layer select
        self.annotationEdit = QLineEdit(self.topRightGroupBox)
        self.annotationEdit.setPlaceholderText('Single layer only')
        self.annotationEdit.setFixedWidth(220)
        self.annotationCombo = QComboBox(self.topRightGroupBox)
        self.annotationCombo.setVisible(False)
        self.annotationStatuses = StatusCombo(self.topRightGroupBox, self.userInfo)

        # Pheno / annotation selection display label
        self.phenoDisplay = QLabel(self.topRightGroupBox)
        self.phenoDisplay.setText(self.userInfo.phenotype_mappings_label)
        self.phenoDisplay.setAlignment(Qt.AlignTop)

        self.annotationDisplay = QLabel(self.topRightGroupBox)
        self.annotationDisplay.setText(self.userInfo.annotation_mappings_label)
        self.annotationDisplay.setAlignment(Qt.AlignTop)

        # Reset button 
        self.resetButton = QPushButton('Reset choices',self.topRightGroupBox)
        self.resetButton.pressed.connect(self.reset_mappings)
        self.resetButton.setStyleSheet(f"QPushButton {{ font-size: 14px}}")


        self.imageSize = QSpinBox(self.topRightGroupBox)
        self.imageSize.setRange(50,1000)
        self.imageSize.setValue(self.userInfo.imageSize) # Misbehaving?
        self.imageSize.editingFinished.connect(self.saveImageSize)
        self.imageSize.setFixedWidth(100)

        self.specificCellChoice = QLineEdit(self.topRightGroupBox)
        self.specificCellChoice.setPlaceholderText('Leave blank for page 1')
        if self.userInfo.specific_cell is not None:
            self.specificCellChoice.insert(self.userInfo.specific_cell['ID'])
        self.specificCellChoice.setFixedWidth(220)
        self.specificCellChoice.textEdited.connect(self.saveSpecificCell)

        # Widgets to select annotation layer
        self.specificCellAnnotationEdit = QLineEdit(self.topRightGroupBox)
        self.specificCellAnnotationEdit.setPlaceholderText('Annotation layer')
        if self.userInfo.specific_cell is not None:
            self.specificCellAnnotationEdit.insert(self.userInfo.specific_cell['Annotation Layer'])
        self.specificCellAnnotationEdit.setFixedWidth(220)
        self.specificCellAnnotationEdit.textEdited.connect(self.saveSpecificCell)

        self.specificCellAnnotationCombo = QComboBox(self.topRightGroupBox)
        self.specificCellAnnotationCombo.setVisible(False)
        self.specificCellAnnotationCombo.activated.connect(self.saveSpecificCell)

        self.page_size_widget = QSpinBox(self.topRightGroupBox)
        self.page_size_widget.setRange(5,4000)
        self.page_size_widget.setValue(self.userInfo.page_size)
        self.page_size_widget.editingFinished.connect(self.savePageSize)
        self.page_size_widget.setFixedWidth(100)

        self.row_size_widget = QSpinBox(self.topRightGroupBox)
        self.row_size_widget.setRange(2,self.userInfo.page_size)
        self.row_size_widget.setValue(self.userInfo.cells_per_row)
        self.row_size_widget.editingFinished.connect(self.saveRowSize)
        self.row_size_widget.setFixedWidth(100)

        self.global_sort_widget = QComboBox(self.topRightGroupBox)
        self.global_sort_widget.addItem("Sort object table by Cell Id")
        print(f"setting widget to be {self.userInfo.global_sort}")
        for i, chn in enumerate(CHANNELS_STR):
            self.global_sort_widget.addItem(f"Sort object table by {chn} Intensity")
        self.global_sort_widget.setCurrentText(self.userInfo.global_sort)
        self.global_sort_widget.currentTextChanged.connect(self.saveGlobalSort)


        layout = QGridLayout()
        layout.addWidget(self.phenotypeButton,0,0,Qt.AlignTop)#;layout.addWidget(self.explanationLabel0,0,0)
        layout.addWidget(self.phenotypeToGrab,0,1,Qt.AlignTop) ; layout.addWidget(self.phenotypeCombo,0,1,Qt.AlignTop)
        layout.addWidget(self.phenotypeStatuses,0,2,Qt.AlignTop)
        layout.addWidget(self.annotationButton,1,0,Qt.AlignTop)#;layout.addWidget(self.explanationLabel1,1,0)
        layout.addWidget(self.annotationEdit,1,1,Qt.AlignTop); layout.addWidget(self.annotationCombo,1,1,Qt.AlignTop)
        layout.addWidget(self.annotationStatuses,1,2,Qt.AlignTop)
        layout.addWidget(explanationLabel2,2,0,Qt.AlignTop)
        layout.addWidget(self.imageSize,2,1,Qt.AlignTop)
        layout.addWidget(self.resetButton,2,2,Qt.AlignTop)
        layout.addWidget(explanationLabel3,3,0,Qt.AlignTop)
        layout.addWidget(self.page_size_widget,3,1,Qt.AlignTop)
        layout.addWidget(explanationLabel4,4,0,Qt.AlignTop)
        layout.addWidget(self.row_size_widget,4,1,Qt.AlignTop)
        layout.addWidget(explanationLabel5,5,0,Qt.AlignTop)
        layout.addWidget(self.specificCellChoice,5,1,Qt.AlignTop)
        layout.addWidget(self.specificCellAnnotationEdit,5,2,Qt.AlignTop)
        layout.addWidget(self.specificCellAnnotationCombo,5,2,Qt.AlignTop)
        layout.addWidget(self.global_sort_widget,6,0,1,2)
        layout.addWidget(self.phenoDisplay,0,3,7,1)
        layout.addWidget(self.annotationDisplay,0,4,7,1)
        # layout.setColumnStretch(3,6)
        # layout.setColumnStretch(4,6)


        # layout.addWidget(self.findDataButton)
        layout.rowStretch(-100)
        self.topRightGroupBox.setLayout(layout)

    def _check_validation_cols(self,df):
        # Check to see if validation columns are in the data (won't be on first run)
        #   Put them in place if needed
        try:
            for status in list(self.userInfo.statuses.keys()):
                df.loc[2,f"Validation | {status}"]
        except KeyError:
            for call_type in reversed(list(self.userInfo.statuses.keys())):
                try:
                    if call_type == 'Unseen':
                        df.insert(8,f"Validation | {call_type}", 1)
                    else:
                        df.insert(8,f"Validation | {call_type}", 0) 
                except ValueError:
                    pass # triggered when trying to insert column that already exists
    
    ''' Iterate through annotation mappings collected from user and assign new statuses to cells if needed'''
    def assign_annotation_statuses_to_sheet(self,df):
        l = list(set(self.userInfo.annotation_mappings.keys()))
        if (not self.userInfo.annotation_mappings):
            print("No annotation assignments")
            return df # break if user wants "All" for each

        elif (len(l) == 1) and (l[0] == "Don't assign"):
            print("Annotation(s) but no assignment")
            return df # Also break if there are no status mappings for any annotation
        
        print("Assignments to complete")
        self._append_status('Assigning decisions to annotations...')
        self._check_validation_cols(df)
        sk = list(self.userInfo.statuses.keys())
        validation_cols = [f"Validation | " + s for s in sk]
        for annotation in self.userInfo.annotation_mappings.keys():
            status = self.userInfo.annotation_mappings[annotation]
            if status == "Don't assign":
                continue
            for call_type in sk:
                df.loc[df["Analysis Region"]==annotation,f"Validation | {call_type}"] = 0
            df.loc[df["Analysis Region"]==annotation,f"Validation | {status}"] = 1
        self._append_status('<font color="#7dbc39">  Done. </font>') 
        return df

    def assign_phenotype_statuses_to_sheet(self,df):
        l = list(set(self.userInfo.phenotype_mappings.keys()))
        if (not self.userInfo.phenotype_mappings):
            return df # break if user wants "All" 
        
        elif (len(l) == 1) and (l[0] == "Don't assign"):
            return df # Also break if there are no status mappings for any annotation
        
        self._append_status('Assigning decisions to phenotypes...')
        self._check_validation_cols(df)
        sk = list(self.userInfo.statuses.keys())
        validation_cols = [f"Validation | " + s for s in sk]
        for phenotype in self.userInfo.phenotype_mappings.keys():
            status = self.userInfo.phenotype_mappings[phenotype]
            if status == "Don't assign":
                continue
            for call_type in sk:
                df.loc[df[phenotype]==1,f"Validation | {call_type}"] = 0
            df.loc[df[phenotype]==1,f"Validation | {status}"] = 1
        self._append_status('<font color="#7dbc39">  Done. </font>')
        return df

    '''Find all unique annotation layer names, if the column exists in the data, and return the results'''
    def _locate_annotations_col(self, path):
        try:
            true_annotations = list(pd.read_csv(path, index_col=False, usecols=['Analysis Region'])['Analysis Region'].unique()) 
            self.userInfo.analysisRegionsInData = true_annotations
            return true_annotations
        except (KeyError, ValueError):
            print("No Analysis regions column in data")
            self.userInfo.analysisRegionsInData = False
            return None

    '''Check that annotations and phenotypes chosen by the user match the data. Return False if there is a mismatch. 
            Allowed to procees if the annotations column does not exist at all in the data.'''
    def _validate_names(self):
        # Get headers and unique annotations
        path = self.userInfo.objectDataPath
        headers = pd.read_csv(path, index_col=False, nrows=0).columns.tolist() 
        true_annotations = self._locate_annotations_col(path) # Find out if the data have multiple analysis regions (duplicate Cell IDs as well)
        if true_annotations is None: 
            self.annotationButton.setEnabled(False)
            self.annotationDisplay.setText('<u>Annotation Layer</u><br>All')
            self.userInfo.annotation_mappings_label = '<u>Annotation Layer</u><br>All'
            self.userInfo.annotation_mappings = {}
            self.specificCellAnnotationEdit.setVisible(False)
            self.specificCellAnnotationCombo.setVisible(False)
        
            return True # It's ok to have no annotation layer
        annotations = list(self.userInfo.annotation_mappings.keys())
        phenotypes = list(self.userInfo.phenotype_mappings.keys())
        # perform checks
        for anno in annotations:
            if anno not in true_annotations: return False
        for pheno in phenotypes:
            if pheno not in headers: return False
        return True
         
    '''Read in the object data file and assign user chosen validation calls to the data, if needed'''
    def assign_statuses_to_sheet(self):
        self._replace_status('Reading object data... ')
        df = pd.read_csv(self.userInfo.objectDataPath)
        self._append_status('<font color="#7dbc39">  Done. </font>')
        self._append_status_br('Validating chosen annotations and phenotypes...')
        if self._validate_names():
            self._append_status('<font color="#7dbc39">  Done. </font>')
            df = self.assign_phenotype_statuses_to_sheet(df)
            df = self.assign_annotation_statuses_to_sheet(df)
            try:
                # self._append_status_br('Saving data back to file...')
                # df.to_csv(self.userInfo.objectDataPath,index=False)
                # self._append_status('<font color="#7dbc39">  Done. </font>')
                self.userInfo.objectDataFrame = df

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

    def loadGallery(self):
        # self.status_label.setVisible(True)
        # self.app.processEvents()
        self.findDataButton.setEnabled(False) # disable load button after click
        res = self.assign_statuses_to_sheet()
        if res == 'Bad input':
            # Will execute if the phenotypes / annotations given do not match to object data
            self.status_label.setVisible(True)
            status = '<font color="#f5551a">  Failed to assign status mappings</font><br>Check your annotations and phenotypes before trying again'
            self.status_label.setText(status)
            return None
        elif res == 'PermissionError':
             self.status_label.setVisible(True)
             self.status_label.setText('<font color="#f5551a">Access to object data file was denied</font><br>Close the sheet before trying again')
             return None

        self.saveViewSettings()
        store_and_load.storeObject(self.userInfo, 'data/presets')
        self.userInfo.session.image_display_name = sub(r'.*?\\',"", self.userInfo.qptiff) # save name of image for display later
        self.userInfo.session.image_scale = self._retrieve_image_scale()
        # If user fetched metadata, save changes to color mappings
        # self.saveColors()


        # print(f'QPTIFF: {self.userInfo.qptiff}')
        # print(f'OBJECTDATA : {self.userInfo.objectData}')
        print(f'CHANNELS : {self.userInfo.channels}')

        # self.app.setStyleSheet('')
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
            GUI_execute(self)
        except Exception as e:
            folder = os.path.normpath(os.path.join(os.getcwd(), 'runtime logs/'))
            if not os.path.exists(folder):
                os.makedirs(folder)
            logpath = os.path.normpath(os.path.join(folder, datetime.today().strftime('%Y-%m-%d_runtime_crash_%H%M%S.txt')))
            self._log_problem(logpath,e)
        
class ThreadSave(QThread):
    def __init__(self, gallery:ViewerPresets, target=None) -> None:
        super().__init__()
        self.target=target
        self.gallery=gallery
    def run(self):
        if self.target:
            self.target(self.gallery)



def ensure_saving(gallery : ViewerPresets, app, window = QDialog(), 
                  notice = QLabel(),button = QPushButton()) -> None:
    app.exec()
    # old app has exited now
    if gallery.userInfo.session.saving_required:
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
        def begin_save(g):
            g.save_result = g.userInfo._save_validation(to_disk=True)
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
                    if gallery.userInfo._save_validation(to_disk=True): 
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
            folder = os.path.normpath(os.path.join(os.getcwd(), 'runtime logs/'))
            if not os.path.exists(folder):
                os.makedirs(folder)
            logpath = os.path.normpath(os.path.join(folder, datetime.today().strftime('%Y-%m-%d_SavingError_%H%M%S.txt')))
            gallery._log_problem(logpath,e)
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
    gallery = ViewerPresets(app)
    gallery.show()
    sys.exit(ensure_saving(gallery,app))
    print("\nI should only see this after I close the viewer")
