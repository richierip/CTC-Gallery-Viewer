''' 
Project - CTC Gallery viewer with Napari

Description - class for data storage
    This file holds the user controlled information and methods to store that info persistently. 

Peter Richieri
Ting Lab
2023
'''

import pickle
import copy

CELL_COLORS = ['gray', 'purple' , 'blue', 'green', 'orange','red', 'yellow', 'cyan', 'pink'] # List of colors available to use as colormaps
DAPI = 0; OPAL570 = 1; OPAL690 = 2; OPAL480 = 3; OPAL620 = 4; OPAL780 = 5; OPAL520 = 6; AF=7 # Each fluor will be assigned a number that is used to represent it's position in the image array
CHANNELS_STR = ["DAPI", "OPAL480", "OPAL520", "OPAL570", "OPAL620", "OPAL690", "OPAL780", "AF"] # List of String names for fluors the user wants to display  
CHANNELS = [DAPI, OPAL570, OPAL690, OPAL480, OPAL620, OPAL780, OPAL520, AF] # List of int variables (same information as above)

# Currently in the default Opal Motif order. Maybe could change in the future? So use this
#   variably to determine the order of filters so the software knows which columns in the data
#   to use. 
# CHANNEL_ORDER = ["DAPI", "OPAL570", "OPAL690", "OPAL480", "OPAL620", "OPAL780", "OPAL520", "AF"]
CHANNEL_ORDER = {'DAPI': 'gray', 'OPAL570': 'purple', 'OPAL690': 'blue', 'OPAL480': 'green', 'OPAL620': 'orange',
  'OPAL780': 'red', 'OPAL520': 'yellow', 'AF': 'cyan'} # mappings of fluors to user selected colors. Order is also significant, represents image data channel order
STATUSES = {"Unseen":"gray", "Needs review":"bop orange", "Confirmed":"green", "Rejected":"red", "Interesting": "lavender" }
STATUSES_RGBA = {"Unseen":(120,120,120,255), "Needs review":(255,127,80,255), "Confirmed":(60,179,113, 255), "Rejected":(215,40,40, 255), "Interesting": (190, 125, 219, 255) }
STATUSES_HEX = {'Confirmed':'#00ff00', 'Rejected':'#ff0000', 'Needs review':'#ffa000', "Interesting":"#be7ddb", "Unseen":'#ffffff'} # A mapping of statuses to the color used to represent them
VIEW_SETTINGS = {"DAPI gamma": 0.5, "OPAL570 gamma": 0.5, "OPAL690 gamma": 0.5, "OPAL480 gamma": 0.5,
                  "OPAL620 gamma": 0.5, "OPAL780 gamma": 0.5, "OPAL520 gamma": 0.5, 
                  "AF gamma": 0.5,"Sample AF gamma": 0.5,"Autofluorescence gamma": 0.5,
                  "DAPI black-in": 0, "OPAL570 black-in": 0, "OPAL690 black-in": 0, "OPAL480 black-in": 0,
                  "OPAL620 black-in": 0, "OPAL780 black-in": 0, "OPAL520 black-in": 0, 
                  "AF black-in": 0,"Sample AF black-in": 0,"Autofluorescence black-in": 0,
                  "DAPI white-in": 255, "OPAL570 white-in": 255, "OPAL690 white-in": 255, "OPAL480 white-in": 255,
                  "OPAL620 white-in": 255, "OPAL780 white-in": 255, "OPAL520 white-in": 255, 
                  "AF white-in": 255,"Sample AF white-in": 255,"Autofluorescence white-in": 255}

class userPresets:
    ''' This class is used to store user-selected parameters on disk persistently,
    and to pass the information to the main script to interpret. The class will initialize
    with values I have chosen (can modify these in the init below, or with certain global 
    variables above.) '''

    def __init__(self, channels = copy.copy(CHANNELS_STR), qptiff = None, 
                objectData = None, phenotype = None, imageSize = 100, specific_cell = None, 
                channelOrder = CHANNEL_ORDER, page_size = 56, global_sort = "Sort object table by Cell Id",
                cells_per_row = 8, statuses = None, view_settings = copy.copy(VIEW_SETTINGS)):
        self.qptiff = qptiff #String - image path
        self.objectData = objectData # String - object data path
        self.imageSize = imageSize # Int - size of EACH punchout around a cell
        self.channels = channels # String array - user choice for channels to read and display
        self.UI_color_display = copy.copy(CELL_COLORS) # keep track of user selected colors for fluors
        self.specific_cell = specific_cell # Int if USER wants to load the page containing this cell, None otherwise
        self.channelOrder = channelOrder #String array - Order of multichannel data found in the image
        self.page_size = page_size # Integer - How many cells should be displayed per page
        self.global_sort = global_sort # String - Header to use to sort the object data. Default is cell ID (sheet is usually pre-sorted like this)
        self.cells_per_row = cells_per_row
        self.statuses = copy.copy(STATUSES)
        self.statuses_rgba = copy.copy(STATUSES_RGBA)
        self.statuses_hex = copy.copy(STATUSES_HEX)
        self.view_settings = view_settings
        self.view_settings_path = ''
        self.phenotype_mappings = {}
        self.phenotype_mappings_label = '<u>Phenotype</u><br>All'
        self.annotation_mappings = {}
        self.annotation_mappings_label = '<u>Annotation Layer</u><br>All'
        self.analysisRegionsInData = False


    '''
    Input: table generated from reading an xml into a dataframe with pandas
    vs_table example:
    Id  ColorCode  Brightness  Contrast  Gamma  ...   BlackIn   WhiteIn  Visible  BlackInAbsolute  WhiteInAbsolute
    0   0        255           1         1    0.5  ...  0.019608  0.588235     True                5              150
    1   1   16776960           1         1    0.5  ...  0.019608  0.588235     True                5              150'''
    def transfer_view_settings(self, vs_table):
        for pos, fluor in enumerate(self.channelOrder):
            if fluor == "Composite": continue
            self.view_settings[f'{fluor} gamma'] = vs_table.iloc[pos]['Gamma']
            self.view_settings[f'{fluor} black-in'] = vs_table.iloc[pos]['BlackInAbsolute']
            self.view_settings[f'{fluor} white-in'] = vs_table.iloc[pos]['WhiteInAbsolute']
        return True


    def attempt_channel_add(self, channelName):
        ''' Adds a channel name to the class variable. Ensures that the list is sorted, and that
        there are no duplicates. Should be triggered by GUI checkboxes. '''
        if channelName not in self.channels:
            self.channels.append(channelName)
            self.channels = sorted(list(set(self.channels)))
            if "AF" in self.channels:
                self.channels.remove("AF")
                self.channels.append("AF")

    def attempt_channel_remove(self, channelName):
        ''' Removes a channel name from the class variable. Ensures that the list is sorted, and that
        there are no duplicates. Should be triggered by GUI checkboxes. '''
        if channelName in self.channels:
            self.channels.remove(channelName)
            self.channels = sorted(list(set(self.channels)))
            if "AF" in self.channels:
                self.channels.remove("AF")
                self.channels.append("AF")

def storeObject(obj, filename):
    ''' Write the class object to a file. Default location is data/presets'''
    try:
        outfile = open(filename, 'wb' )
        pickle.dump(obj, outfile)
        outfile.close()
        return True
    except:
        return False
        
def loadObject(filename):
    ''' Read the class object from a file. Default location is data/presets'''
    try:
        infile = open(filename,'rb')
        new_obj = pickle.load(infile)
        infile.close()
        return new_obj
    except:
        # If no data yet (first time running the viewer), load up defaults
        return userPresets()

# If no data yet (first time running the viewer), load up defaults
# def checkObject(presets_object):
#     if presets_object == None:
#         return userPresets()
#     else:
#         return presets_object