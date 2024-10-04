#############################################################################

from qtpy.QtCore import QObject, Qt, QThread, QTimer
from qtpy.QtGui import QIcon, QPixmap,QColor,QFont
from qtpy.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,QMainWindow, QGridLayout, QDesktopWidget, QSizePolicy,QLayout,
                            QRadioButton, QGroupBox, QLabel, QLineEdit,QPushButton, QSpinBox,QDoubleSpinBox, QMenuBar, QAction, QFileDialog,
                            QHBoxLayout, QVBoxLayout)

import sys
import os
import time
import store_and_load
from galleryViewer import GUI_execute
import ctypes
import os
import warnings
warnings.filterwarnings("ignore")
import pandas as pd
import copy
import pathlib

# Used in fetching and processing metadata
from random import choice
import tifffile
import xml.etree.ElementTree as ET
import webbrowser # for opening github
import warnings
warnings.catch_warnings

from custom_qt_classes import ScoringDialog, ChannelDialog, StatusCombo, ColorfulComboBox
from custom_color_functions import colormap_titled as rgbcd

VERSION_NUMBER = '1.3.5'
FONT_SIZE = 12

COLOR_TO_RGB = {'gray': '(170,170,170, 255)', 'purple':'(160,32,240, 255)', 'blue':'(100,100,255, 255)',
                    'green':'(60,179,113, 255)', 'orange':'(255,127,80, 255)', 'red': '(215,40,40, 255)',
                    'yellow': '(255,215,0, 255)', 'pink': '(255,105,180, 255)', 'cyan' : '(0,220,255, 255)'}
WIDGET_SELECTED = None


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
        # self.setSizePolicy(QSizePolicy.MinimumExpanding,QSizePolicy.MinimumExpanding)

        self.userInfo = store_and_load.loadObject('data/presets')

        # For TESTING
        print(f'Initial test print for colors: {self.userInfo.channelColors}')

        self.myColors = [] # Holds color selection comboboxes for the channel selection widgets
        self.setWindowIcon(QIcon('data/mghiconwhite.png'))

        # Set title area / logo
        cc_logo = QLabel()
        pixmap = QPixmap('data/mgh-mgb-cc-logo2 (Custom).png')
        cc_logo.setPixmap(pixmap)
        # f'<br><font color="{idcolor}">CID: {ID}</font>'
        titleLabel = QLabel(f'Tumor Cartography Core <font color="#033b96">Gallery</font><font color="#009ca6">Viewer</font> <font size=12pt>v{VERSION_NUMBER}</font>')
        # custom_font = QFont(); custom_font.setFamily('Metropolis Black'); custom_font.setPointSize(39)
        titleLabel.setStyleSheet('font-family: Metropolis ; font-size: 25pt')
        # titleLabel.setFont(QFont('MS Gothic',38))
        titleLabel.setAlignment(Qt.AlignCenter)


        # reset status mappings for selected annotations and phenotypes
        new_pheno_label = '<u>Phenotypes</u><br>'
        if not self.userInfo.phenotype_mappings.keys(): new_pheno_label +='All'
        for key in self.userInfo.phenotype_mappings:
            self.userInfo.phenotype_mappings[key] = "Don't assign"
            new_pheno_label += f'{key}<br>'
        self.userInfo.phenotype_mappings_label = new_pheno_label

        new_anno_label = '<u>Annotations</u><br>'
        if not self.userInfo.annotation_mappings.keys(): new_anno_label +='All'
        for key in self.userInfo.annotation_mappings:
            self.userInfo.annotation_mappings[key] = "Don't assign"
            new_anno_label += f'{key}<br>'
        self.userInfo.annotation_mappings_label = new_anno_label

        self.status_label = QLabel()
        self.status_label.setStyleSheet('color:#075cbf ; font-size: 15pt')
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setVisible(False)

        self.createTopLeftGroupBox()
        self.createTopRightGroupBox()
        # self.createProgressBar()

        # entry box for .qptiff        
        self.qptiffEntry = QLineEdit()  # Put retrieved previous answer here
        # Want to do this in any case
        self.qptiffEntry.setPlaceholderText('Enter path to .qptiff')

        self.qptiffEntry.setFixedWidth(800)
        # qptiffEntry.setAlignment(Qt.AlignLeft)
        # entryLabel = QLabel("Image: ")
        # entryLabel.setBuddy(self.qptiffEntry)
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
        self.previewImageDataButton = QPushButton("Choose Image")
        self.previewObjectDataButton.setDefault(True)

        
        self.viewSettingsEntry = QLineEdit()
        self.viewSettingsEntry.insert(pathlib.Path(self.userInfo.view_settings_path).name)
        self.viewSettingsEntry.setPlaceholderText('Enter path to a .viewsettings file (optional)')
        self.viewSettingsEntry.setFixedWidth(800)

        self.getViewsettingsPathButton = QPushButton("Set default view settings")

        # viewSettingsLabel = QLabel("View Settings: ")
        # viewSettingsLabel.setBuddy(self.viewSettingsEntry)
        # viewSettingsLabel.setAlignment(Qt.AlignCenter)
        # viewSettingsLabel.setMaximumWidth(600)

        # Push button to start reading image data and start up napari by remotely executing main method of main script
        self.findDataButton = QPushButton("Load images into viewer")
        self.findDataButton.setDefault(False)


        self.findDataButton.pressed.connect(self.loadGallery)
        self.qptiffEntry.textEdited.connect(self.saveQptiff)
        self.dataEntry.textEdited.connect(self.saveObjectData)
        self.getViewsettingsPathButton.pressed.connect(self.fetchViewsettingsPath)
        self.previewObjectDataButton.pressed.connect(self.prefillObjectData)
        self.previewImageDataButton.pressed.connect(self.prefillImageData)

        # Menu bar
        self.menubar = QMenuBar()
        pref = self.menubar.addMenu('Preferences')
        scoring = QAction("Modify scoring decisions and colors", self)
        scoring.setShortcut("Ctrl+P")
        import_gvs = QAction("Import configuration file", self)
        import_gvs.setShortcut("Shift+S")
        export_gvs = QAction("Export configuration file", self)
        export_gvs.setShortcut("Ctrl+S")
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

        topLayout = QGridLayout()
        # topLayout.addStretch(1)
        topLayout.addWidget(cc_logo,0,0)
        topLayout.addWidget(titleLabel,0,1, 1,2, Qt.AlignLeft)
        topLayout.setSpacing(20)
        # topLayout.addWidget(entryLabel,1,0,1,0)
        topLayout.addWidget(self.qptiffEntry,1,1)
        topLayout.addWidget(self.previewImageDataButton,1,2)
        # topLayout.addWidget(dataEntryLabel,2,0,1,0)
        topLayout.addWidget(self.dataEntry,2,1)
        # topLayout.addWidget(viewSettingsLabel,3,0,1,0)
        topLayout.addWidget(self.previewObjectDataButton,2,2)
        topLayout.addWidget(self.viewSettingsEntry,3,1)
        topLayout.addWidget(self.getViewsettingsPathButton,3,2)
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
        self.mainLayout.setSizeConstraint(QLayout.SetFixedSize)
        self.setLayout(self.mainLayout)

        self.setWindowTitle(f"GalleryViewer v{VERSION_NUMBER}")

        # preprocess things if user has entered paths in a previous session
        if self.userInfo.qptiff_path is not None:
            self.qptiffEntry.insert(pathlib.Path(self.userInfo.qptiff_path).name)
            # self.prefillImageData(fetch=False)
        if self.userInfo.objectDataPath is not None and  self.userInfo.qptiff_path is not None:
            self.dataEntry.insert(pathlib.Path(self.userInfo.objectDataPath).name)
            self.prefillObjectData(fetch=False)
        if self.userInfo.view_settings_path is not None:
            self.saveViewSettings()
        self.clearFocus()


    def change_scoring_decisions(self):
        scoring = ScoringDialog(self.app, self.userInfo, {"pheno_widget":self.phenotypeStatuses,"anno_widget": self.annotationStatuses})
        scoring.exec()

    def change_channels(self):
        channels = ChannelDialog(self.app, self.userInfo, self.topLeftGroupLayout, self.topLeftGroupBox , self.createTopLeftGroupBox)
        channels.exec()

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
                    os.remove(os.path.normpath(r'./data/presets'))
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
                self.status_label.setText("Coming soon")
            case "export configuration":
                self.status_label.setText("Coming soon")
            case _:
                raise ValueError("Bad input to process_menu_action")


    def saveQptiff(self):
        cleanpath = os.path.normpath(self.qptiffEntry.text().strip('"')).strip('.')
        if os.path.exists(cleanpath):
            pass
            # self.userInfo.qptiff_path = cleanpath
        # if (".qptiff" in self.qptiffEntry.text()) or (".tif" in self.qptiffEntry.text()):
        #     self.previewImageDataButton.setEnabled(True)
        # else:
        #     self.previewImageDataButton.setEnabled(False)
    def saveObjectData(self):
        cleanpath = os.path.normpath(self.dataEntry.text().strip('"')).strip('.')
        if os.path.exists(cleanpath):
            pass
            # self.userInfo.objectDataPath = cleanpath
        # if ".csv" in self.dataEntry.text():
        #     self.previewObjectDataButton.setEnabled(True)
        # else:
        #     self.previewObjectDataButton.setEnabled(False)

    def saveViewSettings(self):
        import lxml
        try:
            df = pd.read_xml(self.userInfo.view_settings_path)
            self.userInfo.transfer_view_settings(df)
            self._append_status_br('<font color="#4c9b8f">Successfully imported .viewsettings file!</font>')
            self.userInfo.imported_view_settings = df
            self.setWidgetColorBackground(self.viewSettingsEntry, "#55ff55")
            QTimer.singleShot(800, lambda:self.setWidgetColorBackground(self.viewSettingsEntry, "#ffffff"))

        except lxml.etree.XMLSyntaxError as e:
            self.userInfo.remake_viewsettings() # use defaults
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
        val = self.imageSize.value()
        # Make sure it's an even number. Odd number causes an off by one issue that I don't want to track down.
        self.userInfo.imageSize = val if val%2==0 else val+1
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
        for button in self.mycheckbuttons:
            channelName = button.objectName().replace("_"," ")
            if button.isChecked():
                self.userInfo.attempt_channel_add(channelName)
            elif not button.isChecked():
                self.userInfo.attempt_channel_remove(channelName)

    def saveColors(self):
        for colorWidget in self.myColors:
            channelName = colorWidget.objectName().replace("_"," ")
            # print(f'#### Channel order fsr: {store_and_load.CHANNELS_STR} \n')
            print(self.userInfo.channels)
            
            self.userInfo.channelColors[channelName] = colorWidget.currentText()
        print(f"Current mapping is {self.userInfo.channelColors}")

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
        self.userInfo.phenotype_mappings_label = self.phenoDisplay.text()
        self.userInfo.phenotype_mappings[pheno] = status

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
        self.userInfo.filters_label = self.filterDisplay.text()
        self.userInfo.filters.append(f"{fil} {fil_compare_query} {fil_number}")   

    def reset_mappings(self, examine_object_data = True):
        #phenotype
        self.userInfo.phenotype_mappings = {}
        self.userInfo.phenotype_mappings_label = '<u>Phenotypes</u><br>All'
        self.phenoDisplay.setText('<u>Phenotypes</u><br>All')
        #Annotations
        self.userInfo.annotation_mappings = {}
        self.userInfo.annotation_mappings_label = '<u>Annotations</u><br>All'
        self.annotationDisplay.setText('<u>Annotations</u><br>All')
        #Filters
        self.userInfo.filters = []
        self.userInfo.filters_label = '<u>Filters</u><br>None'
        self.filterDisplay.setText('<u>Filters</u><br>None')

        # Refresh comboboxes
        if self.phenotypeCombo.isVisible() or self.annotationCombo.isVisible():
            self.phenotypeCombo.clear() 
            self.annotationCombo.clear() 
            self.filterMarkerCombo.clear()
            self.specificCellAnnotationCombo.clear()
        if examine_object_data:
            self.prefillObjectData(fetch=False)

    def _log_problem(self, e, logpath= None, error_type = None):
        # Log the crash and report key variables
        self.userInfo.log_exception(e, logpath, error_type)

    def fetchViewsettingsPath(self):
        path = self.userInfo.last_system_folder_visited

        print(f"path {path}")
        current_entry = self.viewSettingsEntry.text().strip('"').strip("' ")
        if os.path.exists(current_entry) and (current_entry.lower().endswith(".viewsettings") ):
            fileName = current_entry
        else:
            fileName, _ = QFileDialog.getOpenFileName(self,"Select a HALO viewsettings file", path,"HALO viewsettigs (*.viewsettings)")
        # self.userInfo.last_system_folder_visited = os.path.normpath(pathlib.Path(fileName).parent)
        self.userInfo.view_settings_path = os.path.normpath(fileName)
        self.saveViewSettings() # Try to import
        self.viewSettingsEntry.clear()
        self.viewSettingsEntry.insert(pathlib.Path(fileName).name)

    def fetchObjectDataPath(self):
        path = self.userInfo.last_system_folder_visited

        print(f"path {path}")
        current_entry = self.dataEntry.text().strip('"').strip("' ")
        if os.path.exists(current_entry) and (current_entry.lower().endswith(".qptiff") or current_entry.lower().endswith(".tif")):
            fileName = current_entry
        else:
            fileName, _ = QFileDialog.getOpenFileName(self,"Select a HALO Object Data file", path,"HALO Object Data (*.csv)")
        self.userInfo.last_system_folder_visited = os.path.normpath(pathlib.Path(fileName).parent)
        self.userInfo.objectDataPath = os.path.normpath(fileName)
        self.dataEntry.clear()
        self.dataEntry.insert(pathlib.Path(fileName).name)

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
                # self.previewObjectDataButton.setStyleSheet(f"color: #4c9b8f") 
            elif res == 'passed':
                status = _generate_typical_string(annos,phenos)
                self.status_label.setText(status)
                # self.previewObjectDataButton.setStyleSheet(f"color: #4c9b8f")
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
                # self.previewObjectDataButton.setStyleSheet(f"color: #ffa000")
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
    
    def _prefillObjectData(self):
        headers = pd.read_csv(self.userInfo.objectDataPath, index_col=False, nrows=0).columns.tolist() 
        possible_fluors = self.userInfo.possible_fluors_in_data
        suffixes = self.userInfo.non_phenotype_fluor_suffixes_in_data
        exclude = self.userInfo.other_cols_in_data
        
        intens_ = ['Cell Intensity','Nucleus Intensity', 'Cytoplasm Intensity']

        include = [x for x in headers if any(f in x for f in intens_)]
        self.filterMarker.setVisible(False)
        self.filterMarkerCombo.setVisible(True)
        self.filterMarkerCombo.addItems(include)

        for fl in possible_fluors:
            for sf in suffixes:
                exclude.append(f'{fl} {sf}')
        include = [x for x in headers if ((x not in exclude) and not (any(f in x for f in possible_fluors)))]
        self.userInfo.phenotypes = include
        self.phenotypeToGrab.setVisible(False) #
        self.phenotypeCombo.setVisible(True) 
        self.phenotypeCombo.addItems(include)
        # Assess annotation regions in csv
        try:
            regions = list(pd.read_csv(self.userInfo.objectDataPath, index_col=False, usecols=['Analysis Region'])['Analysis Region'].unique()) 
            
            print(f"{self.userInfo.objectDataPath}   {regions}")
            self.annotationCombo.setVisible(True); self.annotationEdit.setVisible(False)
            self.annotationCombo.clear() ;  self.annotationEdit.clear() # Remove anything that's already there
            self.annotationCombo.addItems(regions)
            self.specificCellAnnotationCombo.setVisible(True); self.specificCellAnnotationEdit.setVisible(False)
            self.specificCellAnnotationCombo.clear() ; self.specificCellAnnotationEdit.clear() # Remove anything that is there
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
            im_location_csv = pd.read_csv(self.userInfo.objectDataPath, index_col=False, nrows=1, usecols=['Image Location']).iloc[0,0]
            # get everything after the last / , i.e. the image name.
            # Do it this way since some people use a mapped drive path, some use CIFS, some use UNC path with IP address
            im_name_csv = pathlib.Path(im_location_csv).name
        
            if im_name_csv != pathlib.Path(self.userInfo.qptiff_path).name:
                return 'name conflict'
        except ValueError: 
            try: # Attempt to check the alternative column name that might be present
                im_location_csv = pd.read_csv(self.userInfo.objectDataPath, index_col=False, nrows=1, usecols=['Image File Name']).iloc[0,0]
                im_name_csv = pathlib.Path(im_location_csv).name
                
                if im_name_csv != pathlib.Path(self.userInfo.qptiff_path).name:
                    return 'name conflict'
            except ValueError:
                pass 
            pass # No name columns that I know of, move on.
        return 'passed'

    def setWidgetColorBackground(self, widg, color):
        widg.setStyleSheet(f"background: {color}")

    # def flashCorrect(self):
    #     self.textInput.configure(bg = 'green')
    #     self.window.after(150, self.resetInputColor)

    def fetchImagePath(self):
        path = self.userInfo.last_system_folder_visited
        current_entry = self.qptiffEntry.text().strip('"').strip("' ")
        if os.path.exists(current_entry) and (current_entry.lower().endswith(".qptiff") or current_entry.lower().endswith(".tif")):
            fileName = current_entry
        else:
            fileName, _ = QFileDialog.getOpenFileName(self,"Select an image to load", path,"Akoya QPTIFF (*.qptiff);;Akoya QPTIFF (*.QPTIFF)")  
        
        self.userInfo.last_system_folder_visited = os.path.normpath(pathlib.Path(fileName).parent)
        self.userInfo.qptiff_path = os.path.normpath(fileName)
        self.qptiffEntry.clear()
        self.qptiffEntry.insert(pathlib.Path(fileName).name)

    def prefillImageData(self, fetch = True):
        try:
            if fetch:
                self.fetchImagePath()
            res = self._prefillImageData()
            if res == 'passed':
                self.status_label.setVisible(True)
                status = f'<font color="#4c9b8f">Successfully processed image metadata! {len(self.userInfo.channelOrder)} channel image is ready for viewing. </font>'
                self.status_label.setText(status)
                # self.previewImageDataButton.setEnabled(False)
                # self.previewImageDataButton.setStyleSheet(f"color: #4c9b8f")
                self.setWidgetColorBackground(self.qptiffEntry, "#55ff55")
                QTimer.singleShot(800, lambda:self.setWidgetColorBackground(self.qptiffEntry, "#ffffff"))
            elif res == 'name conflict':
                #TODO something here
                self.setWidgetColorBackground(self.qptiffEntry, "#ef881a")
                QTimer.singleShot(800, lambda:self.setWidgetColorBackground(self.qptiffEntry, "#ffffff"))
        except Exception as e:
            print(e)
            self.setWidgetColorBackground(self.qptiffEntry, "#ff5555")
            QTimer.singleShot(800, lambda:self.setWidgetColorBackground(self.qptiffEntry, "#ffffff"))

            self._log_problem(e, error_type="image-metadata-warning")
            # Inform user of possible issue
            self.status_label.setVisible(True)
            status = '<font color="#ffa000">Warning: Failed to properly ingest the files\' metadata.\
              The viewer expects a QPTIFF from an Akoya Polaris,<br> and an object data <i>.csv</i> generated by a Halo analysis app</font>'
            self.status_label.setText(status)
            # self.previewImageDataButton.setEnabled(False)
            # self.previewImageDataButton.setStyleSheet(f"color: #ffa000")
        
    def _retrieve_image_scale(self):
        ''' Get pixel per um value for the image'''
        try:
            # return None
            path = self.userInfo.qptiff_path
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

    def _prefillImageData(self):
        path = self.userInfo.qptiff_path
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
            return key
        
        # rename keys to ensure channels are mapped to a color we have a colormap for  
        for key in list(fluors.keys()):
            fluors[rename_key(key)] = fluors.pop(key).lower().replace('white', 'gray')
        unused_colors = copy.copy(self.userInfo.available_colors)
        for col in fluors.values():
            if col in unused_colors:
                unused_colors.remove(col)
        for key, value in fluors.items():
            if value in self.userInfo.available_colors: 
                continue
            else:
                if len(unused_colors) < 1:
                    random_color = choice(self.userInfo.available_colors)
                else:
                    random_color = choice(unused_colors)
                    unused_colors.remove(random_color)
                fluors[key] = random_color

        for button in self.mycheckbuttons:
            button.setChecked(False)
            widget_name = button.objectName().replace("_"," ")
            print(f"WIDGET NAME IS {widget_name}")

            if widget_name in list(fluors.keys()):
                button.setChecked(True)
        # Save info to class
        self.userInfo.channelColors = fluors
        self.userInfo.channels = []
        for pos, fluor in enumerate(list(fluors.keys())):
            self.userInfo.channels.append(fluor)
            self.userInfo.channelOrder[fluor] = int(pos)
        
        self.saveChannel()
        # self.saveColors()
        return 'passed'
    
    def createTopLeftGroupBox(self, layout: None|QGridLayout = None, groupbox: None|QGroupBox = None ):
        self.topLeftGroupBox = groupbox if groupbox is not None else QGroupBox("Channels and Colors")
        
        self.mycheckbuttons = []
        for chn, pos in self.userInfo.channelOrder.items():
            check = QCheckBox(chn)
            check.setObjectName(chn.replace(" ","_"))
            self.mycheckbuttons.append(check)
        self.topLeftGroupLayout = layout if layout is not None else QGridLayout()
        
        row = 0 ; col = 0
        for pos,button in enumerate(self.mycheckbuttons):
            colorComboName = button.objectName()
            colorCombo = ColorfulComboBox(self, rgbcd, self.userInfo.channelColors[button.objectName().replace("_"," ")].title() )
            colorCombo.setObjectName(colorComboName)
            if button.objectName().replace("_"," ") in self.userInfo.channels:
                button.setChecked(True)
            else:
                button.setChecked(False)
            button.toggled.connect(self.saveChannel) #IMPORTANT that this comes after setting check values
            self.myColors.append(colorCombo)
            colorCombo.activated.connect(self.saveColors)
            
            self.topLeftGroupLayout.addWidget(button, row//4,col%4)
            self.topLeftGroupLayout.addWidget(colorCombo, row//4 ,  (col%4)+1 )
            row+=2; col+=2

        self.topLeftGroupBox.setLayout(self.topLeftGroupLayout)    
        return self.topLeftGroupLayout, self.topLeftGroupBox
    
    def createTopRightGroupBox(self):
        self.topRightGroupBox = QGroupBox("Cells to Read")

        # self.explanationLabel0 = QLabel("Custom object data <b>phenotype<b>")
        # self.explanationLabel1 = QLabel("Pull from an <b>annotation layer<b>")
        explanationLabel2 = QLabel("Cell image size in <b>pixels</b>")
        explanationLabel3 = QLabel("Number of cells <b>per page<b>")
        explanationLabel4 = QLabel("Number of cells <b>per row<b>")
        explanationLabel5 = QLabel("Load page with <b>Cell ID<b>")
        # self.explanationLabel0.setAlignment(Qt.AlignRight)
        # self.explanationLabel1.setAlignment(Qt.AlignRight)
        # explanationLabel2.setAlignment(Qt.AlignRight)
        # explanationLabel3.setAlignment(Qt.AlignRight)
        # explanationLabel4.setAlignment(Qt.AlignRight)
        # explanationLabel5.setAlignment(Qt.AlignRight)
        # explanationLabel5 = QLabel("Number of cells <b>per row<b>")
        
        #------------------ Annotation widgets
        self.annotationButton = QPushButton("Add Annotation")
        self.annotationButton.setStyleSheet(f"QPushButton {{ font-size: 22px}}")
        self.annotationButton.pressed.connect(self.addAnnotation)

         # Annotation layer select
        self.annotationEdit = QLineEdit(self.topRightGroupBox)
        self.annotationEdit.setPlaceholderText('Single layer only')
        self.annotationEdit.setFixedWidth(220)
        self.annotationCombo = QComboBox(self.topRightGroupBox)
        self.annotationCombo.setVisible(False)
        self.annotationStatuses = StatusCombo(self.topRightGroupBox, self.userInfo)

        # Pheno selection display label
        self.annotationDisplay = QLabel(self.topRightGroupBox)
        self.annotationDisplay.setText(self.userInfo.annotation_mappings_label)
        self.annotationDisplay.setAlignment(Qt.AlignTop)
        # self.annotationDisplay.setStyleSheet("line-height:1.5; padding-left:15px; padding-right:15px; padding-top:0px")
        self.annotationDisplay.setContentsMargins(15,0,15,0)

        #---------- Phenotype widgets
        self.phenotypeButton = QPushButton("Add Phenotype")
        self.phenotypeButton.setStyleSheet(f"QPushButton {{ font-size: 22px}}")
        self.phenotypeButton.pressed.connect(self.addPheno)

        # LineEdit / ComboBox
        self.phenotypeToGrab = QLineEdit(self.topRightGroupBox)
        self.phenotypeToGrab.setPlaceholderText('Phenotype of Interest')
        self.phenotypeToGrab.setFixedWidth(220)
        self.phenotypeCombo = QComboBox(self.topRightGroupBox)
        self.phenotypeCombo.setVisible(False)
        self.phenotypeStatuses = StatusCombo(self.topRightGroupBox, self.userInfo)
       

        # Pheno selection display label
        self.phenoDisplay = QLabel(self.topRightGroupBox)
        self.phenoDisplay.setText(self.userInfo.phenotype_mappings_label)
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
        self.filterDisplay.setText(self.userInfo.filters_label)
        self.filterDisplay.setAlignment(Qt.AlignTop)
        self.filterDisplay.setStyleSheet("line-height:1.5")


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
        for i, chn in enumerate(self.userInfo.channels):
            self.global_sort_widget.addItem(f"Sort object table by {chn} Cell Intensity")
        self.global_sort_widget.setCurrentText(self.userInfo.global_sort)
        self.global_sort_widget.currentTextChanged.connect(self.saveGlobalSort)


        layout = QGridLayout()
        layout.addWidget(self.filterButton,0,0,Qt.AlignTop)#;layout.addWidget(self.explanationLabel0,0,0)
        layout.addWidget(self.filterMarker,0,1,Qt.AlignTop) ; layout.addWidget(self.filterMarkerCombo,0,1,Qt.AlignTop)
        layout.addWidget(self.filterFunctionChoice,0,2,Qt.AlignTop)
        layout.addWidget(self.filterNumber,0,3,Qt.AlignTop)

        layout.addWidget(self.phenotypeButton,1,0,Qt.AlignTop)#;layout.addWidget(self.explanationLabel0,0,0)
        layout.addWidget(self.phenotypeToGrab,1,1,Qt.AlignTop) ; layout.addWidget(self.phenotypeCombo,1,1,Qt.AlignTop)
        layout.addWidget(self.phenotypeStatuses,1,2,1,2,Qt.AlignTop)
        layout.addWidget(self.annotationButton,2,0,Qt.AlignTop)#;layout.addWidget(self.explanationLabel1,1,0)
        layout.addWidget(self.annotationEdit,2,1,Qt.AlignTop); layout.addWidget(self.annotationCombo,2,1,Qt.AlignTop)
        layout.addWidget(self.annotationStatuses,2,2,1,2,Qt.AlignTop)
        layout.addWidget(explanationLabel2,3,0,Qt.AlignTop)
        layout.addWidget(self.imageSize,3,1,Qt.AlignTop)
        layout.addWidget(self.resetButton,3,2,1,2,Qt.AlignTop)
        layout.addWidget(explanationLabel3,4,0,Qt.AlignTop)
        layout.addWidget(self.page_size_widget,4,1,Qt.AlignTop)
        layout.addWidget(explanationLabel4,5,0,Qt.AlignTop)
        layout.addWidget(self.row_size_widget,5,1,Qt.AlignTop)
        layout.addWidget(explanationLabel5,6,0,Qt.AlignTop)
        layout.addWidget(self.specificCellChoice,6,1,Qt.AlignTop)
        layout.addWidget(self.specificCellAnnotationEdit,6,2,1,2,Qt.AlignTop)
        layout.addWidget(self.specificCellAnnotationCombo,6,2,1,2,Qt.AlignTop)
        layout.addWidget(self.global_sort_widget,7,0,1,2)
        layout.addWidget(self.phenoDisplay,0,4,7,1)
        layout.addWidget(self.annotationDisplay,0,5,7,1)
        layout.addWidget(self.filterDisplay,0,6,7,1)
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
            self.annotationDisplay.setText('<u>Annotations</u><br>All')
            self.userInfo.annotation_mappings_label = '<u>Annotations</u><br>All'
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
        try:
            df = pd.read_csv(self.userInfo.objectDataPath)
        except FileNotFoundError:
            return "No file"
        self._append_status('<font color="#7dbc39">  Done. </font>')
        self._append_status_br('Validating chosen annotations and phenotypes...')
        if self._validate_names():
            try:
                # self._append_status_br('Saving data back to file...')
                # df.to_csv(self.userInfo.objectDataPath,index=False)
                # self._append_status('<font color="#7dbc39">  Done. </font>')
                for call_type in reversed(self.userInfo.statuses.keys()):
                    try:
                        df[f"Validation | {call_type}"]
                    except KeyError:
                        if call_type == 'Unseen':
                            df.insert(8,f"Validation | {call_type}", 1)
                        else:
                            df.insert(8,f"Validation | {call_type}", 0)  
                df = self.assign_phenotype_statuses_to_sheet(df)
                df = self.assign_annotation_statuses_to_sheet(df)
                self._append_status('<font color="#7dbc39">  Done. </font>')
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

        store_and_load.storeObject(self.userInfo, 'data/presets')
        self.userInfo.session.image_display_name = pathlib.Path(self.userInfo.qptiff_path).name # save name of image for display later
        self.userInfo.session.image_scale = self._retrieve_image_scale()
        # If user fetched metadata, save changes to color mappings
        # self.saveColors()

        # self.userInfo.channels.append("Composite")
        print(f'CHANNELS : {self.userInfo.channels}')
        print(f'CHANNELS ORDER : {self.userInfo.channelOrder}')
        print(f'CHANNELS colors : {self.userInfo.channelColors}')
        # print(f'View Settings : {self.userInfo.view_settings}')

        # self.app.setStyleSheet('')
        # Now the galleryViewer file loads the presets 

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
            # self.userInfo.session.zarr_store.close() # close zarr file??
            self._log_problem(e, error_type="runtime-crash")

class ThreadSave(QThread):
    def __init__(self, gallery:ViewerPresets, target=None) -> None:
        super().__init__()
        self.target=target
        self.gallery=gallery
    def run(self):
        if self.target:
            self.target(self.gallery)

def ensure_saving(gallery : ViewerPresets, app) -> None:
    app.exec()
    window = QDialog()
    notice = QLabel()
    button = QPushButton()
    # gallery.userInfo.session.zarr_store.close() # close zarr file??
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
    gallery = ViewerPresets(app)

    gallery.show()
    sys.exit(ensure_saving(gallery,app))
    print("\nI should never see this.")
