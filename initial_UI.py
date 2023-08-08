#############################################################################

from PyQt5.QtCore import QDateTime, Qt
from PyQt5.QtGui import QIcon, QPixmap,QColor,QFont
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QDateTimeEdit,
        QDial, QDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
        QProgressBar, QPushButton, QRadioButton, QScrollBar, QSizePolicy,
        QSlider, QSpinBox, QTableWidget, QTabWidget, QTextEdit,
        QVBoxLayout, QWidget)

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
from random import choice

import tifffile
import xml.etree.ElementTree as ET

VERSION_NUMBER = '1.1.0'
FONT_SIZE = 12
#DAPI = 0; OPAL570 = 1; OPAL690 = 2; OPAL480 = 3; OPAL620 = 4; OPAL780 = 5; OPAL520 = 6; AF=7
CHANNELS_STR = ["DAPI", "OPAL570", "OPAL690", "OPAL480", "OPAL620", "OPAL780", "OPAL520", "AF"]
AVAILABLE_COLORS = ['gray', 'purple' , 'blue', 'green', 'orange','red', 'yellow', 'pink', 'cyan']
COLOR_TO_RGB = {'gray': '(170,170,170, 255)', 'purple':'(160,32,240, 255)', 'blue':'(100,100,255, 255)',
                    'green':'(60,179,113, 255)', 'orange':'(255,127,80, 255)', 'red': '(215,40,40, 255)',
                    'yellow': '(255,215,0, 255)', 'pink': '(255,105,180, 255)', 'cyan' : '(0,220,255, 255)'}
WIDGET_SELECTED = None
ANNOTATION_LAYERS = ['All'] 

class ViewerPresets(QDialog):
    def __init__(self, app, parent=None):
        super(ViewerPresets, self).__init__(parent)

        self.app = app
        # Arrange title bar buttons
        self.setWindowFlag(Qt.WindowMinimizeButtonHint, True)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        self.setWindowFlag(Qt.WindowTitleHint,False)

        self.userInfo = store_and_load.loadObject('data/presets')

        # For TESTING
        print(f'Initial test print for colors: {self.userInfo.UI_color_display}')

        self.combobox_index = 0 # for combobox color changing
        self.myColors = []
        # print(f'SP\pinning up ... preset colors are {self.userInfo.cell_colors}')
        self.originalPalette = QApplication.palette()
        self.setWindowIcon(QIcon('data/mghiconwhite.png'))

        cc_logo = QLabel()
        pixmap = QPixmap('data/mgh-mgb-cc-logo2 (Custom).png')
        cc_logo.setPixmap(pixmap)
        # f'<br><font color="{idcolor}">CID: {ID}</font>'
        titleLabel = QLabel(f'TCC Imaging Core <font color="#033b96">Gallery</font><font color="#009ca6">Viewer</font> <font size=12pt>v{VERSION_NUMBER}</font>')
        # custom_font = QFont(); custom_font.setFamily('Metropolis Black'); custom_font.setPointSize(39)
        titleLabel.setStyleSheet('font-family: Metropolis ; font-size: 25pt')
        # titleLabel.setFont(QFont('MS Gothic',38))
        titleLabel.setAlignment(Qt.AlignCenter)

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
        if self.userInfo.objectData is not None:
            self.dataEntry.insert(self.userInfo.objectData)
        self.dataEntry.setPlaceholderText('Enter path to .csv')
        self.dataEntry.setFixedWidth(800)
        # dataEntry.setAlignment(Qt.AlignLeft)
        dataEntryLabel = QLabel("Object Data: ")
        dataEntryLabel.setBuddy(self.dataEntry)
        dataEntryLabel.setAlignment(Qt.AlignCenter)
        dataEntryLabel.setMaximumWidth(600)

        self.previewDataButton = QPushButton("Fetch metadata")
        self.previewDataButton.setDefault(False)
        if "csv" not in self.dataEntry.text() and ((".qptiff" not in self.qptiffEntry.text()) or (".tif" not in self.qptiffEntry.text())):
            self.previewDataButton.setEnabled(False)


        # Push button to start reading image data and start up napari by remotely executing main method of main script
        self.findDataButton = QPushButton("Load Gallery Images")
        self.findDataButton.setDefault(False)

        self.status_label = QLabel("Test Status for Loading")
        self.status_label.setStyleSheet('color:#075cbf ; font-size: 15pt')
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setVisible(False)

        self.createTopLeftGroupBox()
        self.createTopRightGroupBox()
        # self.createProgressBar()

        self.findDataButton.pressed.connect(self.loadGallery)
        self.qptiffEntry.textEdited.connect(self.saveQptiff)
        self.dataEntry.textEdited.connect(self.saveObjectData)
        self.previewDataButton.pressed.connect(self.prefillData)

        topLayout = QGridLayout()
        # topLayout.addStretch(1)
        topLayout.addWidget(cc_logo,0,0)
        topLayout.addWidget(titleLabel,0,1)
        topLayout.setSpacing(20)
        topLayout.addWidget(entryLabel,1,0,1,0)
        topLayout.addWidget(self.qptiffEntry,1,1)
        topLayout.addWidget(dataEntryLabel,2,0,1,0)
        topLayout.addWidget(self.dataEntry,2,1)
        topLayout.addWidget(self.previewDataButton,2,2)
        # topLayout.addWidget(self.findDataButton,2,1)

        self.mainLayout = QGridLayout()
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

    def saveQptiff(self):
        self.userInfo.qptiff = os.path.normpath(self.qptiffEntry.text().strip('"'))
        if "csv" in self.dataEntry.text() and ((".qptiff" in self.qptiffEntry.text()) or (".tif" in self.qptiffEntry.text())):
            self.previewDataButton.setEnabled(True)
        else:
            self.previewDataButton.setEnabled(False)
    def saveObjectData(self):
        self.userInfo.objectData = os.path.normpath(self.dataEntry.text().strip('"'))
        if "csv" in self.dataEntry.text() and ((".qptiff" in self.qptiffEntry.text()) or (".tif" in self.qptiffEntry.text())):
            self.previewDataButton.setEnabled(True)
        else:
            self.previewDataButton.setEnabled(False)

    def savePhenotype(self):
        self.userInfo.phenotype = self.phenotypeToGrab.text()
    def saveSpecificCell(self):
        try:
            self.userInfo.specific_cell = int(self.specificCellChoice.text())
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
    def saveGlobalSort(self):
        print("Saving global sort")
        self.userInfo.global_sort = self.global_sort_widget.currentText()

    def saveChannel(self):
        for button in self.mycheckbuttons:
            channelName = button.objectName()
            # print(f"{channelName} and {self.userInfo.channels}")
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

    def prefillData(self):
        path = self.dataEntry.text().strip('"')
        if ".csv" not in path:
            return None
        headers = pd.read_csv(path, index_col=False, nrows=0).columns.tolist()  
        all_layers = list(pd.read_csv(path, usecols=['Analysis Region'])['Analysis Region'].unique())
        global ANNOTATION_LAYERS
        ANNOTATION_LAYERS = ['All'] + all_layers
        print(ANNOTATION_LAYERS)

        # Parse annoying TIF metadata
        # It seems to be stored in XML format under the 'ImageDescription' TIF tag. 
        path = self.qptiffEntry.text().strip('"')
        description = tifffile.TiffFile(path).pages[0].tags['ImageDescription'].value
        root = ET.fromstring(description)
        # QPTIFF only
        sc = root.find(".//ScanColorTable")
        raw = sc.findall(".//")
        raw = [x.text.split("_")[0] for x in raw]
        fluors = {}
        for i in range(0,len(raw),2):
            fluors[raw[i]] = raw[i+1]
        
        # rename keys 
        for key in list(fluors.keys()):
            fluors[key.replace(" ", '').replace('SampleAF','AF').upper()] = fluors.pop(key).lower().replace('white', 'gray').replace('lime','green').replace('pink','Pink')
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
        
        self.userInfo.channelOrder = fluors
        display_list =  sorted(fluors.items())
        display_list = [x[1] for x in display_list]
        display_list.append(display_list.pop(0))
        self.userInfo.UI_color_display = display_list
        self.saveChannel()
        self.saveColors()
        self.previewDataButton.setEnabled(False)
        self.previewDataButton.setStyleSheet(f"color: rgba(100,200,100,255)")

            
    def createTopLeftGroupBox(self):
        self.topLeftGroupBox = QGroupBox("Channels and Colors")

        self.dapiCheck = QCheckBox("DAPI"); self.dapiCheck.setObjectName('DAPI')
        self._480Check = QCheckBox("Opal 480"); self._480Check.setObjectName('OPAL480')
        self._520Check = QCheckBox("Opal 520"); self._520Check.setObjectName('OPAL520')
        self._570Check = QCheckBox("Opal 570"); self._570Check.setObjectName('OPAL570')
        self._620Check = QCheckBox("Opal 620"); self._620Check.setObjectName('OPAL620')
        self._690Check = QCheckBox("Opal 690"); self._690Check.setObjectName('OPAL690')
        self._780Check = QCheckBox("Opal 780"); self._780Check.setObjectName('OPAL780')
        self.autofluorescenceCheck = QCheckBox("Autofluorescence"); self.autofluorescenceCheck.setObjectName('AF')
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
                elif index ==7: # pink
                    colorWidget.setStyleSheet(f"selection-background-color: rgba(255,105,180, 255);selection-color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
                elif index ==8: # cyan
                    colorWidget.setStyleSheet(f"selection-background-color: rgba(0,220,255, 255);selection-color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
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
            exec(f'{colorComboName}.setItemData(7,QColor(255,0,255,0),Qt.BackgroundRole)') # pink
            exec(f'{colorComboName}.setItemData(7,QColor(0,0,0,255),Qt.ForegroundRole)')
            exec(f'{colorComboName}.setItemData(8,QColor(0,255,255,0),Qt.BackgroundRole)') # cyan
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

        explanationLabel0 = QLabel("Custom object data <b>phenotype<b>")
        explanationLabel1 = QLabel("Cell image size in <b>pixels</b>")
        explanationLabel2 = QLabel("Load the page with this <b>Cell ID<b>")
        explanationLabel3 = QLabel("Number of cells <b>per page<b>")
        explanationLabel4 = QLabel("Number of cells <b>per row<b>")
        # explanationLabel5 = QLabel("Number of cells <b>per row<b>")


        #TODO attach previous choice here
        self.phenotypeToGrab = QLineEdit(self.topRightGroupBox)
        self.phenotypeToGrab.setPlaceholderText('Phenotype of Interest')
        if self.userInfo.phenotype is not None:
            self.phenotypeToGrab.insert(self.userInfo.phenotype)
        self.phenotypeToGrab.setFixedWidth(220)
        self.phenotypeToGrab.textEdited.connect(self.savePhenotype)
        # phenotypeToGrab.set
        self.annotationLayers = QComboBox

        self.imageSize = QSpinBox(self.topRightGroupBox)
        self.imageSize.setRange(50,200)
        self.imageSize.setValue(self.userInfo.imageSize) # Misbehaving?
        self.imageSize.editingFinished.connect(self.saveImageSize)
        self.imageSize.setFixedWidth(100)

        self.specificCellChoice = QLineEdit(self.topRightGroupBox)
        self.specificCellChoice.setPlaceholderText('Leave blank for page 1')
        if self.userInfo.specific_cell is not None:
            self.specificCellChoice.insert(str(self.userInfo.specific_cell))
        self.specificCellChoice.setFixedWidth(220)
        self.specificCellChoice.textEdited.connect(self.saveSpecificCell)

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
        layout.addWidget(explanationLabel0,0,0)
        layout.addWidget(self.phenotypeToGrab,0,1)
        layout.addWidget(explanationLabel1,1,0)
        layout.addWidget(self.imageSize,1,1)
        layout.addWidget(explanationLabel2,2,0)
        layout.addWidget(self.specificCellChoice,2,1)
        layout.addWidget(explanationLabel3,3,0)
        layout.addWidget(self.page_size_widget,3,1)
        layout.addWidget(explanationLabel4,4,0)
        layout.addWidget(self.row_size_widget,4,1)
        layout.addWidget(self.global_sort_widget,5,0)

        # layout.addWidget(self.findDataButton)
        layout.rowStretch(-100)
        self.topRightGroupBox.setLayout(layout)

    def loadGallery(self):
        # self.status_label.setVisible(True)
        # self.app.processEvents()

        self.findDataButton.setEnabled(False) # disable load button after click
        store_and_load.storeObject(self.userInfo, 'data/presets')

        # If user fetched metadata, save changes to color mappings
        # self.saveColors()


        # print(f'QPTIFF: {self.userInfo.qptiff}')
        # print(f'OBJECTDATA : {self.userInfo.objectData}')
        print(f'CHANNELS : {self.userInfo.channels}')
        # self.app.run(max_loop_level=2) # This isn't a thing apparently
        # self.app.processEvents()

        # self.createProgressBar()
        # self.mainLayout.addWidget(self.progressBar, 3, 0, 1, 2)
        # self.startProgressBar()

        # t = threading.Thread(target = self.startProgressBar, name = "Testing thread capabilities")
        # t.daemon = True
        # t.start()
        # print(f'progress bar thread w/daemon should be started now...')

        folder = os.path.normpath(os.path.join(os.getcwd(), 'runtime logs/'))
        if not os.path.exists(folder):
            os.makedirs(folder)
        logpath = os.path.normpath(os.path.join(folder, datetime.today().strftime('%Y-%m-%d_crashlog_%H%M%S.txt')))

        # self.app.setStyleSheet('')
        try:
            # for i in range(15):
            #     time.sleep(1)
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
            # close this window
            # self.close()
            GUI_execute(self)
            # time.sleep(5)
            # print("done")
        except Exception as e:
            params = f"Image path: {self.userInfo.qptiff} \nData path: {self.userInfo.objectData}\n"
            params += f"Punchout size: {self.userInfo.imageSize} \nUser selected channels: {self.userInfo.channels}\n"
            params += f"Avaliable color: {store_and_load.CELL_COLORS} \nChosen phenotype: {self.userInfo.phenotype}\n"
            params += f"Batch/page size: {self.userInfo.page_size} \nSort: {self.userInfo.global_sort}\n"
            params += f"Specific cell chosen?: {self.userInfo.specific_cell} \nExpected order of multichannel data: {self.userInfo.channelOrder}\n"
            logging.basicConfig(filename=logpath, encoding='utf-8', level=logging.DEBUG)
            logging.exception(f"{params}\n ------ Crash report autogenerated after trying to load from GUI------ \n{e}")

        # GUI_execute(self.userInfo)
        # exit(0)


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
    sys.exit(app.exec())