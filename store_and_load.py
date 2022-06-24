''' 
Project - CTC Gallery viewer with Napari

Class for data storage

This file holds the user controlled information and methods to store that info persistently using the Pickle framework. '''

import pickle

# QPTIFF_LAYER_TO_RIP = 0 # 0 is high quality. Can use 1 for testing (BF only, loads faster)
CELL_COLORS = ['bop orange', 'bop purple' , 'green', 'blue', 'yellow','cyan', 'red', 'twilight']
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
    def __init__(self, channels = CHANNELS_STR, cell_colors = CELL_COLORS, qptiff = None, objectData = None, phenotype = None, offset = 100, cell_count = 10, channelOrder = CHANNEL_ORDER):
        self.qptiff = qptiff
        self.objectData = objectData
        self.offset = offset
        self.channels = channels
        self.cell_colors = cell_colors
        self.cell_count = cell_count
        self.phenotype = phenotype
        self.channelOrder = channelOrder

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