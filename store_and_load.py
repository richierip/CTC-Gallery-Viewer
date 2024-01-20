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
import pandas as pd
from typing import Callable
from PIL import ImageColor
from itertools import product
from PyQt5.QtGui import QFont
from dataclasses import dataclass
import logging
import os
from datetime import datetime

CELL_COLORS = ['gray', 'purple' , 'blue', 'green', 'orange','red', 'yellow', 'cyan', 'pink'] # List of colors available to use as colormaps
CHANNELS_STR = ["DAPI", "Opal 570", "Opal 690", "Opal 480","Opal 620","Opal 780", "Opal 520", "AF"] # List of String names for fluors the user wants to display  

# Currently in the default Opal Motif order. Maybe could change in the future? So use this
#   variably to determine the order of filters so the software knows which columns in the data
#   to use. 
# CHANNEL_ORDER = {'DAPI': 'gray', 'OPAL570': 'purple', 'OPAL690': 'blue', 'OPAL480': 'green', 'OPAL620': 'orange',
#   'OPAL780': 'red', 'OPAL520': 'yellow', 'AF': 'cyan'} # mappings of fluors to user selected colors. Order is also significant, represents image data channel order
STATUSES = {"Unseen":"c", "Needs review":"v", "Confirmed":"b", "Rejected":"n", "Interesting": "m"}
STATUSES_HEX = {"Unseen":'#787878', 'Needs review':'#ffa000', 'Confirmed':'#00ff00', 'Rejected':'#ff0000',  "Interesting":"#be7ddb"} # A mapping of statuses to the color used to represent them


vs_list = [f"{x[0]} {x[1]}" for x in product(CHANNELS_STR, ['Gamma', 'white-in', 'black-in'])]
VIEW_SETTINGS = {v:[0.5, 255, 0][i%3] for i,v in enumerate(vs_list)}
# VIEW_SETTINGS = {"DAPI gamma": 0.5, "OPAL570 gamma": 0.5, "OPAL690 gamma": 0.5, "OPAL480 gamma": 0.5,
#                   "OPAL620 gamma": 0.5, "OPAL780 gamma": 0.5, "OPAL520 gamma": 0.5, 
#                   "AF gamma": 0.5,"Sample AF gamma": 0.5,"Autofluorescence gamma": 0.5,
#                   "DAPI black-in": 0, "OPAL570 black-in": 0, "OPAL690 black-in": 0, "OPAL480 black-in": 0,
#                   "OPAL620 black-in": 0, "OPAL780 black-in": 0, "OPAL520 black-in": 0, 
#                   "AF black-in": 0,"Sample AF black-in": 0,"Autofluorescence black-in": 0,
#                   "DAPI white-in": 255, "OPAL570 white-in": 255, "OPAL690 white-in": 255, "OPAL480 white-in": 255,
#                   "OPAL620 white-in": 255, "OPAL780 white-in": 255, "OPAL520 white-in": 255, 
#                   "AF white-in": 255,"Sample AF white-in": 255,"Autofluorescence white-in": 255}

class sessionVariables:
    ''' Stores variables that will only last for the duration of a single session'''
    def __init__(self) -> None:
        self.viewer = None # napari.Viewer()
        self.saving_required = False
        self.status_list = {} # mapping for cell names to statuses for the current page, eg {"Cell 2" : "Unseen"} 
        self.saved_notes = {} # mapping for cell names to notes for the current page, eg {"Cell 2" : "note"} 
        self.image_display_name = "" # Name of image file to display in the viewer banner
        self.image_scale = None # None, or float representing pixels per micron
        self.zarr_store = None
        self.dask_array = {} # full [Channel,Y,X] dask array, not yet loaded
        self.mode = "Gallery" # ['Gallery', 'Multichannel', 'Context']
        self.last_mode = "Gallery" # The previous mode of the viewer
        self.last_gallery_camera_coordinates = {"center":(0,0),"z":1} # store the last place the user was looking in the gallery
        self.last_multichannel_camera_coordinates = {"center":(0,0),"z":1} # store the last place the user was looking in multichannel mode
        self.last_context_camera_coordinates = {"center":(0,0),"z":1} # store the last place the user was looking in context mode
        self.grid_to_ID = {"Gallery":{}, "Multichannel":{}}
        self.page_status_layers = {"Gallery": [], "Multichannel": []}
        self.session_cells = pd.DataFrame() # all cells in all pages
        self.cell_under_mouse = {} # Will update with below info for one cell
        self.cell_under_mouse_changed = False # Stores a flag to signal this event
        self.context_target = {} # Saves information for the cell of interest in Context Mode
        self.current_cells =  {'Layer':str,"cid": int,"center_x": int,'center_y': int,
                                'validation_call': str, 'XMax' : float,'XMin':float,
                                'YMax' : float,'YMin':float} # Holds dict of dict for the cells that are loaded on the current page in the viewer
        self.cells_per_row = {"Gallery" : 8, "Multichannel" : 4} # replaced with real numbers
        self.status_text_object = None
        self.context_nuclei_boxes_text_object = None
        self.context_nuclei_boxes_map_to_ind = {} # Save position in list for each cell
        self.context_closest_cell_text_object = None # {'string':'{cid}', 'anchor':'upper_left', 'size' : 8, 'color':validation_colors_hex}
        self.absorption_mode = False # True = light mode, False = Dark mode
        self.nuclei_boxes_vis = {"Gallery/Multichannel":False, "Context": "Hide"} # {"Gallery/Multichannel":True|False, "Context": "Show"|"Hide"|"Mouse"}
        self.status_layer_vis = True
        self.status_box_vis = True
        self.kdtree = None # Will hold scipy.spatial.cKDTree data structure, for use in finding nearest neighbors
        self.intensity_columns = []
        self.validation_columns = []
        self.mouse_coords = (0,0) # (y,x)
        self.display_intensity_func = Callable
        self.find_mouse_func = Callable
        self.side_dock_groupboxes = {}
        self.widget_dictionary = {}
        self.scoring_tally = {"Page":{},"Session":{}, "Data":{}} # {"Session" : {"Unseen" : 1000, "Confirmed": 25 , ... }}, "Data":{"Unseen":2000, ...} }
        self.page_cells = {} # same structure as current_cells, but will not add cells as the user moves around in context mode
        self.radiogroups = {}
        self.last_score_used = None
        self.context_marker_mode = "Disabled"
        self.context_marker_score = None
        self.scoring_function_called_by_mouse_move = False

@dataclass
class ViewerFonts:
    """Hold various fonts to be used in the GUI and Viewer sidebar widget area"""
    small :QFont = QFont("Verdana", 6, weight=QFont.Normal)


class userPresets:
    ''' This class is used to store user-selected parameters on disk persistently,
    and to pass the information to the main script to interpret. The class will initialize
    with values I have chosen (can modify these in the init below, or with certain global 
    variables above.) '''

    def __init__(self, channels = copy.copy(CHANNELS_STR), qptiff_path = None, 
                phenotype = None, imageSize = 100, specific_cell = None, page_size = 56, global_sort = "Sort object table by Cell Id",
                cells_per_row = 8, statuses = None, ):
        self.qptiff_path = qptiff_path # String - image path
        self.last_system_folder_visited = "C:/"
        self.objectDataPath = '' # String - object data path
        self.objectDataFrame = None # Pandas DataFrame created using read_csv. Storing this saves time when wanting the df later
        self.imageSize = imageSize # Int - size of EACH punchout around a cell
        self.channels = channels # String array - user choice for channels to read and display
        self.active_channels = channels
        self.specific_cell = specific_cell # Dictionary of the format {'ID': (int),'Annotation Layer': (str)}, or None 
        self.available_colors = copy.copy(CELL_COLORS)
        self.channelColors = dict(zip(channels,CELL_COLORS)) #String array - Order of multichannel data found in the image
        self.channelOrder = dict(zip(channels,range(len(channels))))
        self.page_size = page_size # Integer - How many cells should be displayed per page
        self.global_sort = global_sort # String - Header to use to sort the object data. Default is cell ID (sheet is usually pre-sorted like this)
        self.cells_per_row = cells_per_row # Int - how many cells should be placed in a row before wrapping to the next (multichannel mode only)
        self.statuses = copy.copy(STATUSES) # Dict of statuses and string keybinds, e.g. {'status A':'a'}
        self.statuses_hex = copy.copy(STATUSES_HEX) # Dict of statuses and HEX codes of color mappings, e.g. {'status A':'#ff0000'}
        self.statuses_rgba = {key: ImageColor.getcolor(val, "RGBA") for key,val in self.statuses_hex.items()} # Dict of statuses and RGBA tuples color mappings, e.g. {'status A':(255,0,0,255)}
        self.available_statuses_keybinds = ["q","w","e","t","y","u","o","d","f","j","k","l","z","x",",",".","/","[","]",";","'"]
        self.view_settings = self.remake_viewsettings(pass_value=True) # Dict of view settings. Can change after reading from file. ex: {fluor A gamma: 0.5}
        self.view_settings_path = '' # Path to .viewsettings file. The file is a type of HALO export and will use XML formatting
        self.phenotype_mappings = {} # Dict of user selected phenotypes and their status mappings. Cells in the data of these phenotypes will be kept for viewing and assigned the given status 
        self.phenotype_mappings_label = '<u>Phenotypes</u><br>All' # String representation of the above info for displaying in a QLabel
        self.annotation_mappings = {} # Dict of user selected annotations and their status mappings. Cells in the data of these annotations will be kept for viewing and assigned the given status 
        self.annotation_mappings_label = '<u>Annotations</u><br>All'# String representation of the above info for displaying in a QLabel
        self.analysisRegionsInData = False # Bool that tracks whether the object data has an 'Analysis Region' field with multiple annotations. Useful later
        self.filters = []
        self.filters_label = '<u>Filters</u><br>None'
        self.session = sessionVariables()
        self.possible_fluors_in_data = ['DAPI','Opal 480','Opal 520', 'Opal 570', 'Opal 620','Opal 690', 'Opal 720', 'AF', 'Sample AF', 'Autofluorescence']
        self.non_phenotype_fluor_suffixes_in_data = ['Positive Classification', 'Positive Nucleus Classification','Positive Cytoplasm Classification',
                    'Cell Intensity','Nucleus Intensity', 'Cytoplasm Intensity', '% Nucleus Completeness', '% Cytoplasm Completeness',
                    '% Cell Completeness', '% Completeness']
        self.non_phenotype_fluor_cols_in_data = ['Cell Area (µm²)', 'Cytoplasm Area (µm²)', 'Nucleus Area (µm²)', 'Nucleus Perimeter (µm)', 'Nucleus Roundness',
                  'Image Location','Image File Name', 'Analysis Region', 'Algorithm Name', 'Object Id', 'XMin', 'XMax', 'YMin', 'YMax', 'Notes']
        self.fonts = ViewerFonts()


    ''' Restore viewsettings to [chn] gamma : 0.5, [chn] whitein:255, [chn] blackin:0
        for all channels in the data'''
    def remake_viewsettings(self, pass_value = False):
        vs_list = [f"{x[0]} {x[1]}" for x in product(list(self.channelOrder.keys()), ['gamma', 'white-in', 'black-in'])]
        self.view_settings = {v:[0.5, 255, 0][i%3] for i,v in enumerate(vs_list)}
        if pass_value:
            return {v:[0.5, 255, 0][i%3] for i,v in enumerate(vs_list)}
    
    # def remake_channelColors(self):
    #     self.channelColors = dict(zip(self.channels,CELL_COLORS))

    def remake_rgba(self):
        self.statuses_rgba = {key: ImageColor.getcolor(val, "RGBA") for key,val in self.statuses_hex.items()} # Dict of statuses and RGBA tuples color mappings, e.g. {'status A':(255,0,0,255)}

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

    def _save_validation(self, to_disk = False):
        '''Save new calls to the session's Pandas DataFrame, and optionally save that frame to disk'''
        for call_type in reversed(self.statuses.keys()):
            try:
                self.objectDataFrame[f"Validation | {call_type}"]
            except KeyError:
                if call_type == 'Unseen':
                    self.objectDataFrame.insert(8,f"Validation | {call_type}", 1)
                else:
                    self.objectDataFrame.insert(8,f"Validation | {call_type}", 0)  
        try:
            self.objectDataFrame["Notes"]
        except KeyError:
            self.objectDataFrame.insert(8,"Notes","-")
            self.objectDataFrame.fillna("")
        
        status_copy = copy.copy(self.session.status_list)
        for key, status in status_copy.items():
            cid = key.split()[-1]
            vals = [1 if x == status else 0 for x in list(self.statuses.keys())]
            status_copy[key] = [key.replace(f' {cid}',''), int(cid),self.session.saved_notes[key], *vals]

        # Create dataframe from stored dictionary and join with original df by assigning them the same kind of index
        calls = [f"Validation | {status}" for status in list(self.statuses.keys())]
        df = pd.DataFrame.from_dict(status_copy, orient = 'index', columns = ["Analysis Region", "Object Id",'Notes', *calls] )
        if self.analysisRegionsInData:
            self.objectDataFrame['new_index'] = self.objectDataFrame['Analysis Region'] +' '+ self.objectDataFrame['Object Id'].astype(str)
        else:
            df = df.drop(columns=['Analysis Region'])
            self.objectDataFrame['new_index'] = 'All '+ self.objectDataFrame['Object Id'].astype(str)
        self.objectDataFrame = self.objectDataFrame.set_index('new_index')
        # Drop analysis region if it does not belong

        self.objectDataFrame.update(df) # overwrite data with new cols
        self.objectDataFrame[calls + ['Object Id']] = self.objectDataFrame[calls + ['Object Id']].astype(int)
        # print(self.objectDataFrame.columns)
        # print(self.objectDataFrame[calls].head(15))

        if to_disk:
            try:
                self.objectDataFrame.to_csv(self.objectDataPath, index=False)
                self.objectDataFrame.reset_index(drop=True,inplace=True)
            except PermissionError: # file in use
                self.objectDataFrame.reset_index(drop=True,inplace=True)
                return False
        
            # hdata.loc[:,1:].to_excel(
            # OBJECT_DATA,sheet_name='Exported from gallery viewer')
        return True
    
            # Log the crash and report key variables
    def log_exception(self, e, logpath = None, error_type = None):
        if logpath is None:
            folder = os.path.normpath(os.path.join(os.getcwd(), 'runtime logs/'))
            if not os.path.exists(folder):
                os.makedirs(folder)
            if error_type is None:
                error_type = "unspecified-issue" # default naming for an exception
            
            print(f"Caught {error_type} exception in viewer runtime. Will write to file")
            logpath = os.path.normpath(os.path.join(folder, datetime.today().strftime(f'%Y-%m-%d_{error_type}_%H%M%S.txt')))
        
        params = f"\nImage path: {self.qptiff_path} \nData path: {self.objectDataPath}\n"
        params += f"Punchout size: {self.imageSize} \nUser selected channels: {self.channels}\n"
        params += f"Available colors: {self.available_colors} \n"
        params += f"Batch/page size: {self.page_size} \nSort: {self.global_sort}\n"
        params += f"Specific cell chosen?: {self.specific_cell} \nExpected order of multichannel data: {self.channelOrder}\n"
        params += f"Color mappings: {self.channelColors}\n"
        params += f"Phenotype mappings: {self.phenotype_mappings}\n"
        params += f"Annotation mappings: {self.annotation_mappings}\n"
        params += f"View settings path: {self.view_settings_path}\n"
        params += f"View settings: {self.view_settings}\n"
        params += f"Available statuses: {self.statuses}"
        logging.basicConfig(filename=logpath, encoding='utf-8', level=logging.DEBUG)
        spacer = "        -----------------------------        "
        logging.exception(f"{params}\n{spacer}\n ------ Autogenerated crash report ------ {spacer}\n{e}")

def storeObject(obj : userPresets, filename : str):
    ''' Write the class object to a file. Default location is data/presets'''
    try:
        obj.session = sessionVariables() # reset per-session variables to save space
        obj.fonts = None
        outfile = open(filename, 'wb' )
        pickle.dump(obj, outfile)
        outfile.close()
        obj.fonts = ViewerFonts()
        return True
    except Exception as e:
        print(e)
        return False
        
def loadObject(filename):
    ''' Read the class object from a file. Default location is data/presets'''
    try:
        infile = open(filename,'rb')
        new_obj = pickle.load(infile)
        infile.close()

        new_obj.session = sessionVariables() # just make sure nothing happened here
        new_obj.fonts = ViewerFonts()
        return new_obj
    except Exception as e:
        print(e)
        # If no data yet (first time running the viewer), load up defaults
        return userPresets()