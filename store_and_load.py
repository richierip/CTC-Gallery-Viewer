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
STATUSES = {"Unseen":"gray", "Needs review":"bop orange", "Confirmed":"green", "Rejected":"red" } # A mapping of statuses to the color used to represent them

class userPresets:
    ''' This class is used to store user-selected parameters on disk persistently,
    and to pass the information to the main script to interpret. The class will initialize
    with values I have chosen (can modify these in the init below, or with certain global 
    variables above.) '''

    def __init__(self, channels = copy.copy(CHANNELS_STR), qptiff = None, 
                objectData = None, phenotype = None, imageSize = 100, specific_cell = None, 
                channelOrder = CHANNEL_ORDER, page_size = 56, global_sort = "Sort object table by Cell Id",
                cells_per_row = 8, statuses = None):
        self.qptiff = qptiff #String - image path
        self.objectData = objectData # String - object data path
        self.imageSize = imageSize # Int - size of EACH punchout around a cell
        self.channels = channels # String array - user choice for channels to read and display
        self.UI_color_display = copy.copy(CELL_COLORS) # keep track of user selected colors for fluors
        self.specific_cell = specific_cell # Int if USER wants to load the page containing this cell, None otherwise
        self.phenotype = phenotype # String - Label for the column name of interest in the object data file
        self.channelOrder = channelOrder #String array - Order of multichannel data found in the image
        self.page_size = page_size # Integer - How many cells should be displayed per page
        self.global_sort = global_sort # String - Header to use to sort the object data. Default is cell ID (sheet is usually pre-sorted like this)
        self.cells_per_row = cells_per_row
        self.statuses = copy.copy(STATUSES)


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