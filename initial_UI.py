#############################################################################

from PyQt5.QtCore import (QDateTime, Qt, QTimer, QThread, 
        pyqtSignal, QObject, QRunnable, QThreadPool, pyqtSlot)
from PyQt5.QtGui import QIcon, QPixmap,QColor
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QDateTimeEdit,
        QDial, QDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
        QProgressBar, QPushButton, QRadioButton, QScrollBar, QSizePolicy,
        QSlider, QSpinBox, QTableWidget, QTabWidget, QTextEdit,
        QVBoxLayout, QWidget)

import sys
import os
import time
import store_and_load
from galleryViewer import GUI_execute, GUI_execute_cheat
import ctypes
import threading
import logging
from datetime import datetime
import os

VERSION_NUMBER = '1.0'
FONT_SIZE = 12
#DAPI = 0; OPAL570 = 1; OPAL690 = 2; OPAL480 = 3; OPAL620 = 4; OPAL780 = 5; OPAL520 = 6; AF=7
CHANNELS_STR = ["DAPI", "OPAL570", "OPAL690", "OPAL480", "OPAL620", "OPAL780", "OPAL520", "AF"]
AVAILABLE_COLORS = ['gray', 'purple' , 'blue', 'green', 'orange','red', 'yellow', 'pink', 'cyan']
WIDGET_SELECTED = None

# class ExternalCounter(QThread):
#     """
#     Runs a counter thread.
#     """
#     countChanged = pyqtSignal(int)
#     def __init__(self, time_limit):
#         super(ExternalCounter, self).__init__()
#         self.time_limit = time_limit

#     def run(self):
#         count = 0
#         while count < self.time_limit:
#             count +=1
#             time.sleep(1)
#             self.countChanged.emit(count)

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
        titleLabel = QLabel(f"Pre-Release v"+VERSION_NUMBER)#{chr(8482)} TBD
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

        topLayout = QGridLayout()
        # topLayout.addStretch(1)
        topLayout.addWidget(cc_logo,0,0)
        topLayout.addWidget(titleLabel,0,1)
        topLayout.setSpacing(20)
        topLayout.addWidget(entryLabel,1,0,1,0)
        topLayout.addWidget(self.qptiffEntry,1,1)
        topLayout.addWidget(dataEntryLabel,2,0,1,0)
        topLayout.addWidget(self.dataEntry,2,1)
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

        self.setWindowTitle("Pre-processing Info")

    # If no data yet (first time running the viewer), load up defaults
    def checkUser(self):
        if self.userInfo == None:
            self.userInfo = store_and_load.userPresets()
        else:
            pass

    def saveQptiff(self):
        self.userInfo.qptiff = os.path.normpath(self.qptiffEntry.text().strip('"'))
    def saveObjectData(self):
        self.userInfo.objectData = os.path.normpath(self.dataEntry.text().strip('"'))
    def savePhenotype(self):
        self.userInfo.phenotype = self.phenotypeToGrab.text()
    def saveNumCells(self):
        self.userInfo.cell_count = self.numCellsToRead.value()
    def saveImageSize(self):
        self.userInfo.imageSize = self.imageSize.value()
    def saveCellOffset(self):
        self.userInfo.cell_ID_start = self.cellOffset.value()

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
            # Set each the color of each QSpin
            if colorWidget.currentText() == 'gray': # gray
                    colorWidget.setStyleSheet("background-color: rgba(170,170,170, 255);color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
            elif colorWidget.currentText() == 'purple': # purple
                colorWidget.setStyleSheet("background-color: rgba(160,32,240, 255);color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
            elif colorWidget.currentText() == 'blue': # blue
                colorWidget.setStyleSheet("background-color: rgba(100,100,255, 255);color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
            elif colorWidget.currentText() == 'green': # green
                colorWidget.setStyleSheet("background-color: rgba(60,179,113, 255);color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
            elif colorWidget.currentText() == 'orange': # orange
                colorWidget.setStyleSheet("background-color: rgba(255,127,80, 255);color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
            elif colorWidget.currentText() == 'red': # red
                colorWidget.setStyleSheet("background-color: rgba(215,40,40, 255);color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
            elif colorWidget.currentText() == 'yellow': # yellow
                colorWidget.setStyleSheet("background-color: rgba(255,215,0, 255);color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
            elif colorWidget.currentText() == 'pink': # pink
                colorWidget.setStyleSheet("background-color: rgba(255,105,180, 255);color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
            elif colorWidget.currentText() == 'cyan': # cyan
                colorWidget.setStyleSheet("background-color: rgba(0,220,255, 255);selection-color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")

            # colorWidget.setItemData(0,QColor("red"),Qt.BackgroundRole)
            # print(f'My trigger was {colorWidget.objectName()}')
            colorChannel = colorWidget.objectName()
            # print(f'#### Channel order fsr: {store_and_load.CHANNELS_STR} \n 1. also userinfo.cell_colors before change: {self.userInfo.cell_colors}')
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
                print(f" index is {index} and widget is {colorWidget}, type is {type(colorWidget)}")
                # return None
                # for colorWidget in self.myColors:
                if index ==0: # gray
                    colorWidget.setStyleSheet("selection-background-color: rgba(170,170,170, 255);selection-color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
                elif index ==1: # purple
                    colorWidget.setStyleSheet("selection-background-color: rgba(160,32,240, 255);selection-color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
                elif index ==2: # blue
                    colorWidget.setStyleSheet("selection-background-color: rgba(100,100,255, 255);selection-color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
                elif index ==3: # green
                    colorWidget.setStyleSheet("selection-background-color: rgba(60,179,113, 255);selection-color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
                elif index ==4: # orange
                    colorWidget.setStyleSheet("selection-background-color: rgba(255,127,80, 255);selection-color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
                elif index ==5: # red
                    colorWidget.setStyleSheet("selection-background-color: rgba(215,40,40, 255);selection-color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
                elif index ==6: # yellow
                    colorWidget.setStyleSheet("selection-background-color: rgba(255,215,0, 255);selection-color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
                elif index ==7: # pink
                    colorWidget.setStyleSheet("selection-background-color: rgba(255,105,180, 255);selection-color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
                elif index ==8: # cyan
                    colorWidget.setStyleSheet("selection-background-color: rgba(0,220,255, 255);selection-color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
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
            if colorWidget.currentText() == 'gray': # gray
                    colorWidget.setStyleSheet("background-color: rgba(170,170,170, 255);color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
            elif colorWidget.currentText() == 'purple': # purple
                colorWidget.setStyleSheet("background-color: rgba(160,32,240, 255);color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
            elif colorWidget.currentText() == 'blue': # blue
                colorWidget.setStyleSheet("background-color: rgba(100,100,255, 255);color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
            elif colorWidget.currentText() == 'green': # green
                colorWidget.setStyleSheet("background-color: rgba(60,179,113, 255);color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
            elif colorWidget.currentText() == 'orange': # orange
                colorWidget.setStyleSheet("background-color: rgba(255,127,80, 255);color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
            elif colorWidget.currentText() == 'red': # red
                colorWidget.setStyleSheet("background-color: rgba(215,40,40, 255);color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
            elif colorWidget.currentText() == 'yellow': # yellow
                colorWidget.setStyleSheet("background-color: rgba(255,215,0, 255);color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
            elif colorWidget.currentText() == 'pink': # pink
                colorWidget.setStyleSheet("background-color: rgba(255,105,180, 255);color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")
            elif colorWidget.currentText() == 'cyan': # cyan
                colorWidget.setStyleSheet("background-color: rgba(0,220,255, 255);selection-color: rgb(0,0,0); font-size:{FONT_SIZE}pt;")

        
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
     
        explanationLabel1 = QLabel("Cell image size in <b>pixels</b>")
        explanationLabel2 = QLabel("Exclude cells with a <i>Cell ID</i> <b>&lt;</b> ")
        explanationLabel3 = QLabel("Limit the display to the first ")

        self.imageSize = QSpinBox(self.topRightGroupBox)
        self.imageSize.setRange(50,200)
        self.imageSize.setValue(self.userInfo.imageSize) # Misbehaving?
        self.imageSize.editingFinished.connect(self.saveImageSize)

        # explanationLabel2.setFixedWidth(20)
        self.numCellsToRead = QSpinBox(self.topRightGroupBox)
        self.numCellsToRead.setValue(self.userInfo.cell_count)
        self.numCellsToRead.setRange(0,1000)
        self.numCellsToRead.editingFinished.connect(self.saveNumCells)
        # numCellsToRead.setFixedWidth(50)

        self.cellOffset = QSpinBox(self.topRightGroupBox)
        self.cellOffset.setRange(0,10000000)
        self.cellOffset.setValue(self.userInfo.cell_ID_start)
        self.cellOffset.editingFinished.connect(self.saveCellOffset)


        layout = QGridLayout()
        layout.addWidget(self.phenotypeToGrab,0,0,1,1)
        layout.addWidget(explanationLabel1,1,0)
        layout.addWidget(self.imageSize,1,1)
        layout.addWidget(explanationLabel2,2,0)
        layout.addWidget(self.cellOffset,2,1)
        layout.addWidget(explanationLabel3,3,0)
        layout.addWidget(self.numCellsToRead,3,1)

        # layout.addWidget(self.findDataButton)
        layout.rowStretch(-100)
        self.topRightGroupBox.setLayout(layout)

    def createProgressBar(self):
        size_of_image = os.path.getsize(self.userInfo.qptiff) / 100000000
        eta = int(size_of_image * 5) # about 5s per gb? This is in # of 10 ms periods to be done

        self.progressBar = QProgressBar()
        self.progressBar.setRange(0, eta)
        self.progressBar.setValue(0)

        # self.timer = ExternalCounter(time_limit=eta)
        # self.timer.countChanged.connect(self.advanceProgressBar)
        # self.timer.start()

    #     # self.timer = ExternalCounter(time_limit=eta)
    #     # self.timer.countChanged.connect(self.advanceProgressBar)
    #     # self.timer.start()

    # def startProgressBar(self):
    #     size_of_image = os.path.getsize(self.userInfo.qptiff) / 100000000
    #     eta = int(size_of_image * 5) # about 5s per gb? This is in # of 10 ms periods to be done
    #     self.timer = ExternalCounter(time_limit = eta)
    #     self.timer.countChanged.connect(self.advanceProgressBar)
    #     self.timer.start()

    # def advanceProgressBar(self, value):
    #     self.progressBar.setValue(value)
    #     # self.progressBar.setValue(int(curVal + 1))
    #     QApplication.processEvents()

    def loadGallery(self):
        # self.status_label.setVisible(True)
        # self.app.processEvents()

        self.findDataButton.setEnabled(False) # disable load button after click
        store_and_load.storeObject(self.userInfo, 'data/presets')
        # Correct color order
        self.userInfo._correct_color_order()

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

        #TODO make this relative with the os package
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
            logging.basicConfig(filename=logpath, encoding='utf-8', level=logging.DEBUG)
            logging.exception("Napari crashed after trying to load QPTiff with GUI load button. Error: %s", e)

        # GUI_execute(self.userInfo)
        # exit(0)


if __name__ == '__main__':
    # This gets python to tell Windows it is merely hosting another app
    #   Therefore, the icon I've attached to the app before is displayed in the taskbar, instead of the python default icon. 
    myappid = 'MGH.CellGalleryViewer.v'+VERSION_NUMBER # arbitrary string
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    app = QApplication([])
    customStyle = ""
    for elem in ["QLabel","QLineEdit","QPushButton","QCheckBox", "QSpinBox", "QGroupBox"]:
        if elem == "QGroupBox" or elem == "QPushButton":
            exec(f'customStyle += "{elem}{{font-size: {FONT_SIZE+2}pt;}}"')
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