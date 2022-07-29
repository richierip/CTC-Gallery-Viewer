''' 
Project - CTC Gallery viewer with Napari

Class for data storage

This file holds the user controlled information and methods to store that info persistently using the Pickle framework. '''

import pickle
import copy

CELL_COLORS = ['Greys', 'Purples' , 'Blues', 'Greens', 'Oranges','Reds', 'copper', 'twilight']
# qptiff = r"C:\Users\prich\Desktop\Projects\MGH\CTC_Example\Exp02a01_02_Scan1.qptiff"
# OFFSET = 100 # pixels?
# CELL_START = 100
# CELL_LIMIT = 150
DAPI = 0; OPAL570 = 1; OPAL690 = 2; OPAL480 = 3; OPAL620 = 4; OPAL780 = 5; OPAL520 = 6; AF=7
CHANNELS_STR = ["DAPI", "OPAL480", "OPAL520", "OPAL570", "OPAL620", "OPAL690", "OPAL780", "AF"]
CHANNELS = [DAPI, OPAL570, OPAL690, OPAL480, OPAL620, OPAL780, OPAL520, AF]
CHANNEL_ORDER = ["DAPI", "OPAL570", "OPAL690", "OPAL480", "OPAL620", "OPAL780", "OPAL520", "AF"]
# ADJUSTED = CHANNELS

class userPresets:
    def __init__(self, channels = copy.copy(CHANNELS_STR), cell_colors = [], qptiff = None, 
                objectData = None, phenotype = None, imageSize = 100, cell_count = 25, 
                channelOrder = CHANNEL_ORDER, cell_ID_start = 0):
        self.qptiff = qptiff
        self.objectData = objectData
        self.imageSize = imageSize
        self.channels = channels
        self.cell_colors = cell_colors
        self.UI_color_display = copy.copy(CELL_COLORS)
        self.cell_count = cell_count
        self.phenotype = phenotype
        self.channelOrder = channelOrder
        self.cell_ID_start = cell_ID_start

        # for chnl in CHANNELS_STR:
        #     # this inserts colors into backend ordered array in the right place off the bat. 
        #     self.cell_colors.append(CELL_COLORS[globals()[chnl]])

    def _correct_color_order(self):
        self.cell_colors = []
        # print(f'\n \n GETTING TO THE BOTTOM OF THS SHIT')
        print(f'CHANNELS_STR {CHANNELS_STR}')
        print(f'CHANNEL_ORDER {CHANNEL_ORDER}')
        print(f'self.cell_colors {self.cell_colors}')
        print(f'self.UI_color_display {self.UI_color_display}')
        for chnl in CHANNEL_ORDER:
                print(f'current var is {chnl} and the global value is {globals()[chnl]}')
                # this inserts colors into backend ordered array in the right place off the bat. 
                pos = CHANNELS_STR.index(chnl)
                self.cell_colors.append(self.UI_color_display[pos])
        print(f'DONE CORRECTING. colors to be passed are {self.cell_colors}')

def storeObject(obj, filename):
    try:
        outfile = open(filename, 'wb' )
        pickle.dump(obj, outfile)
        outfile.close()
        return True
    except:
        return False
        
def loadObject(filename):
    try:
        infile = open(filename,'rb')
        new_obj = pickle.load(infile)
        infile.close()
        return new_obj
    except:
        return None 