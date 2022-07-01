#############################################################################

from collections import UserString
from PyQt5.QtCore import QDateTime, Qt, QTimer
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QDateTimeEdit,
        QDial, QDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
        QProgressBar, QPushButton, QRadioButton, QScrollBar, QSizePolicy,
        QSlider, QSpinBox, QTableWidget, QTabWidget, QTextEdit,
        QVBoxLayout, QWidget)

import sys
import os
import store_and_load
from galleryViewer import GUI_execute, GUI_execute_cheat
import ctypes


FONT_SIZE = 12
DAPI = 0; OPAL570 = 1; OPAL690 = 2; OPAL480 = 3; OPAL620 = 4; OPAL780 = 5; OPAL520 = 6; AF=7
CHANNELS_STR = ["DAPI", "OPAL570", "OPAL690", "OPAL480", "OPAL620", "OPAL780", "OPAL520", "AF"]
AVAILABLE_COLORS = ['Greys', 'Purples' , 'Blues', 'Greens', 'Oranges','Reds', 'copper', 'twilight']

class ViewerPresets(QDialog):
    def __init__(self, app, parent=None):
        super(ViewerPresets, self).__init__(parent)

        self.app = app
        # Arrange title bar buttons
        self.setWindowFlag(Qt.WindowMinimizeButtonHint, True)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        self.setWindowFlag(Qt.WindowTitleHint,False)

        self.userInfo = store_and_load.loadObject('data/presets')
        self.checkUser()
        self.myColors = []
        # print(f'SP\pinning up ... preset colors are {self.userInfo.cell_colors}')
        self.originalPalette = QApplication.palette()
        self.setWindowIcon(QIcon('data/mghiconwhite.png'))

        cc_logo = QLabel()
        pixmap = QPixmap('data/mgh-mgb-cc-logo2 (Custom).png')
        cc_logo.setPixmap(pixmap)
        titleLabel = QLabel(f"Cool App Name {chr(8482)} TBD")
        titleLabel.setAlignment(Qt.AlignCenter)

        self.qptiffEntry = QLineEdit()  # Put retrieved previous answer here
        if self.userInfo.qptiff is not None:
            self.qptiffEntry.insert(self.userInfo.qptiff)
        else:
            self.qptiffEntry.setPlaceholderText('Enter path to .qptiff')

        self.qptiffEntry.setFixedWidth(600)
        # qptiffEntry.setAlignment(Qt.AlignLeft)
        entryLabel = QLabel("Raw Image: ")
        entryLabel.setBuddy(self.qptiffEntry)
        entryLabel.setAlignment(Qt.AlignCenter)
        entryLabel.setMaximumWidth(600)

        self.dataEntry = QLineEdit()  # Put retrieved previous answer here
        if self.userInfo.objectData is not None:
            self.dataEntry.insert(self.userInfo.objectData)
        else:
            self.dataEntry.setPlaceholderText('Enter path to .csv')
        self.dataEntry.setFixedWidth(600)
        # dataEntry.setAlignment(Qt.AlignLeft)
        dataEntryLabel = QLabel("Object Data: ")
        dataEntryLabel.setBuddy(self.dataEntry)
        dataEntryLabel.setAlignment(Qt.AlignCenter)
        dataEntryLabel.setMaximumWidth(600)

        findDataButton = QPushButton("Load Gallery Images")
        findDataButton.setDefault(False)

        self.createTopLeftGroupBox()
        self.createTopRightGroupBox()
        # self.createProgressBar()

        findDataButton.pressed.connect(self.loadGallery)
        self.qptiffEntry.textEdited.connect(self.saveQptiff)
        self.dataEntry.textEdited.connect(self.saveObjectData)

        topLayout = QGridLayout()
        # topLayout.addStretch(1)
        topLayout.addWidget(cc_logo,0,0)
        topLayout.addWidget(titleLabel,0,1)
        topLayout.setSpacing(20)
        topLayout.addWidget(entryLabel,1,0,1,0)
        topLayout.addWidget(self.qptiffEntry,1,1)
        topLayout.addWidget(dataEntryLabel,2,0,1,0)
        topLayout.addWidget(self.dataEntry,2,1)
        # topLayout.addWidget(findDataButton,2,1)

        self.mainLayout = QGridLayout()
        self.mainLayout.addLayout(topLayout, 0, 0, 1, 2)
        self.mainLayout.addWidget(self.topLeftGroupBox, 1, 0)
        self.mainLayout.addWidget(self.topRightGroupBox, 1, 1)
        # mainLayout.addWidget(self.bottomLeftTabWidget, 2, 0)
        # mainLayout.addWidget(self.bottomRightGroupBox, 2, 1)
        self.mainLayout.addWidget(findDataButton,2,0,1,0)
        
        self.mainLayout.setRowStretch(1, 1)
        self.mainLayout.setRowStretch(2, 1)
        self.mainLayout.setColumnStretch(0, 1)
        self.mainLayout.setColumnStretch(1, 1)
        self.setLayout(self.mainLayout)

        self.setWindowTitle("Pre-processing Info")

    # If no data yet (first time running the viewer), load up defaults
    def checkUser(self):
        if self.userInfo == None:
            self.userInfo = store_and_load.userPresets()
        else:
            pass

    def loadGallery(self):
        store_and_load.storeObject(self.userInfo, 'data/presets')
        # print(f'QPTIFF: {self.userInfo.qptiff}')
        # print(f'OBJECTDATA : {self.userInfo.objectData}')
        print(f'CHANNELS : {self.userInfo.channels}')
        # self.app.run(max_loop_level=2) # This isn't a thing apparently
        # self.app.processEvents()
        self.createProgressBar()
        self.mainLayout.addWidget(self.progressBar, 3, 0, 1, 2)
        GUI_execute(self.userInfo)
        # exit(0)

    def saveQptiff(self):
        self.userInfo.qptiff = os.path.normpath(self.qptiffEntry.text().strip('"'))
    def saveObjectData(self):
        self.userInfo.objectData = os.path.normpath(self.dataEntry.text().strip('"'))
    def savePhenotype(self):
        self.userInfo.phenotype = self.phenotypeToGrab.text()
    def saveNumCells(self):
        self.userInfo.cell_count = self.numCellsToRead.value()
    def saveOffset(self):
        self.userInfo.offset = self.imageSize.value()

    def saveChannel(self):
        for button in self.mycheckbuttons:
            channelName = button.objectName()
            # print(f"{channelName} and {self.userInfo.channels}")
            if button.isChecked() and channelName not in self.userInfo.channels:
                self.userInfo.channels.append(channelName)
                self.userInfo.channels = list(set(self.userInfo.channels))
            elif not button.isChecked() and channelName in self.userInfo.channels:
                self.userInfo.channels.remove(channelName)
                self.userInfo.channels = list(set(self.userInfo.channels))

    def saveColors(self):
        for colorWidget in self.myColors:
            colorChannel = colorWidget.objectName()
            # print(f'#### Anything? {colorChannel} and {store_and_load.CHANNEL_ORDER}')
            colorPos = store_and_load.CHANNEL_ORDER.index(colorChannel)
            self.userInfo.cell_colors.pop(colorPos)
            self.userInfo.cell_colors.insert(colorPos, colorWidget.currentText())
            

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
        
        # Space / time saving way to create 16 widgets and change their parameters
        for pos,button in enumerate(self.mycheckbuttons):
            colorComboName = button.objectName() + "_colors"
            exec(f'{colorComboName} = QComboBox()')
            exec(f'{colorComboName}.addItems(AVAILABLE_COLORS)')
            exec(f'{colorComboName}.setCurrentText("{AVAILABLE_COLORS[pos]}")')
            exec(f'{colorComboName}.setObjectName("{button.objectName()}")')
            if button.objectName() in self.userInfo.channels:
                button.setChecked(True)
            else:
                button.setChecked(False)
            button.toggled.connect(self.saveChannel) #IMPORTANT that this comes after setting check values
            exec(f'self.myColors.append({colorComboName})')
            exec(f'{colorComboName}.currentTextChanged.connect(self.saveColors)')
            col = [0,0,0,0,2,2,2,2][pos]
            layout.addWidget(button, pos%4,col)
            exec(f'layout.addWidget({colorComboName},{pos%4}, {col+1})')



            
        self.topLeftGroupBox.setLayout(layout)    

    def createTopRightGroupBox(self):
        self.topRightGroupBox = QGroupBox("Cells to Read")

        #TODO attach previous choice here
        self.phenotypeToGrab = QLineEdit(self.topRightGroupBox)
        if self.userInfo.phenotype is None:
            self.phenotypeToGrab.setPlaceholderText('Phenotype of Interest')
        else:
            self.phenotypeToGrab.insert(self.userInfo.phenotype)
        self.phenotypeToGrab.setFixedWidth(220)
        self.phenotypeToGrab.textEdited.connect(self.savePhenotype)
        # phenotypeToGrab.set
     
        explanationLabel1 = QLabel("Grab an image of size")
        explanationLabel2 = QLabel("for the first")
        explanationLabel3 = QLabel("cells")

        self.imageSize = QSpinBox(self.topRightGroupBox)
        self.imageSize.setRange(50,150)
        self.imageSize.setValue(self.userInfo.offset) # Misbehaving?
        self.imageSize.editingFinished.connect(self.saveOffset)

        # explanationLabel2.setFixedWidth(20)
        self.numCellsToRead = QSpinBox(self.topRightGroupBox)
        self.numCellsToRead.setValue(self.userInfo.cell_count)
        self.numCellsToRead.setRange(0,10000)
        self.numCellsToRead.editingFinished.connect(self.saveNumCells)
        # numCellsToRead.setFixedWidth(50)


        layout = QGridLayout()
        layout.addWidget(self.phenotypeToGrab,0,0,1,1)
        layout.addWidget(explanationLabel1,1,0)
        layout.addWidget(self.imageSize,1,1)
        layout.addWidget(explanationLabel2,2,0)
        layout.addWidget(self.numCellsToRead,2,1)
        layout.addWidget(explanationLabel3,2,2)

        # layout.addWidget(findDataButton)
        layout.rowStretch(-100)
        self.topRightGroupBox.setLayout(layout)

    def advanceProgressBar(self):
        curVal = self.progressBar.value()
        self.progressBar.setValue(int(curVal + 1))
        # QApplication.processEvents()

    def createProgressBar(self):
        size_of_image = os.path.getsize(self.userInfo.qptiff) / 100000000
        eta = int(size_of_image * 5) # about 5s per gb? This is in # of 10 ms periods to be done

        self.progressBar = QProgressBar()
        self.progressBar.setRange(0, eta)
        self.progressBar.setValue(0)
        timer = QTimer(self)
        timer.timeout.connect(self.advanceProgressBar)
        timer.start(100)


if __name__ == '__main__':
    # This gets python to tell Windows it is merely hosting another app
    #   Therefore, the icon I've attached to the app before is displayed in the taskbar, instead of the python default icon. 
    myappid = 'MGH.CellGalleryViewer.v1.0' # arbitrary string
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    app = QApplication([])
    customStyle = ""
    for elem in ["QLabel","QComboBox","QLineEdit","QPushButton","QCheckBox", "QSpinBox", "QGroupBox"]:
        if elem == "QGroupBox" or elem == "QPushButton":
            exec(f'customStyle += "{elem}{{font-size: {FONT_SIZE+2}pt;}}"')
        elif elem == QSpinBox:
            exec(f'customStyle += "{elem}{{font-size: {FONT_SIZE-2}pt;}}"')
        else:
            exec(f'customStyle += "{elem}{{font-size: {FONT_SIZE}pt;}}"')
    app.setStyleSheet(customStyle)
    # app.setStyle('Fusion')
    gallery = ViewerPresets(app)
    gallery.show()
    app.processEvents()
    sys.exit(app.exec())