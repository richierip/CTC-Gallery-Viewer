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
import numpy as np
from typing import Callable
from PIL import ImageColor
from itertools import product
from qtpy.QtGui import QFont
from dataclasses import dataclass
import logging
import os
from datetime import datetime
from qtpy.QtWidgets import QToolTip
from custom_color_functions import colormap, hex_color_from_decimal, decimal_color_from_hex
import pathlib

CELL_COLORS = ['gray', 'purple' , 'blue', 'green', 'orange','red', 'yellow', 'cyan', 'pink'] # List of colors available to use as colormaps
CHANNELS_STR = ["DAPI", "Opal 570", "Opal 690", "Opal 480","Opal 620","Opal 780", "Opal 520", "AF"] # List of String names for fluors the user wants to display  

# Currently in the default Opal Motif order. Maybe could change in the future? So use this
#   variably to determine the order of filters so the software knows which columns in the data
#   to use. 
# CHANNEL_ORDER = {'DAPI': 'gray', 'OPAL570': 'purple', 'OPAL690': 'blue', 'OPAL480': 'green', 'OPAL620': 'orange',
#   'OPAL780': 'red', 'OPAL520': 'yellow', 'AF': 'cyan'} # mappings of fluors to user selected colors. Order is also significant, represents image data channel order
HALO_STATUSES = {"Unseen":"c", "Needs review":"v", "Confirmed":"b", "Rejected":"n", "Interesting": "m"}
HALO_STATUSES_HEX = {"Unseen":'#787878', 'Needs review':'#ffa000', 'Confirmed':'#00ff00', 'Rejected':'#ff0000',  "Interesting":"#be7ddb"} # A mapping of statuses to the color used to represent them


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

class SessionVariables:
    ''' Stores variables that will only last for the duration of a single session'''
    def __init__(self) -> None:
        self.viewer = None # napari.Viewer()
        self.saving_required = False
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
        self.cell_under_mouse = {} # Will update with 'current cells' info for one cell
        self.cell_under_mouse_changed = False # Stores a flag to signal this event
        self.context_target = {} # Saves information for the cell of interest in Context Mode
        self.current_cells =  {'Layer':str|None,"cid": int,"center_x": int,'center_y': int,
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
        self.mouse_coords_world = (0,0) # Used in dummyCoords class to preserve the world coordinates when user moves with arrow keys
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
        self.tooltip_visible = False
        self.multichannel_page_images = {} # {"DAPI" : np.Array ...}
        self.multichannel_nuclei_box_coords = None
        self.page = 1
        self.view_settings = {}
        self.VSDialog = None

@dataclass
class ViewerFonts:
    """Hold various fonts to be used in the GUI and Viewer sidebar widget area"""
    small :QFont = QFont("Verdana", 6, weight=QFont.Normal)
    medium :QFont = QFont("Calibri", 15, weight=QFont.Normal)
    button_small = QFont("Calibri", 6, weight=QFont.Normal)

@dataclass
class UserData:
    def __init__(self):
        self.fonts = ViewerFonts()
        self.session = SessionVariables()
        self.halo = HaloData(self)
        self.cosmx = CosMxData(self)
        self.xenium = XeniumData(self)
        self._UI_mode = "HALO" # Needs to come last
        self.current_data = self.halo
    
    def __switch_current_data(self, new_mode):
        match new_mode:
            case "HALO" | "HALO Multi-Image":
                self.current_data = self.halo
            case "CosMx":
                self.current_data = self.cosmx
            case "Xenium":
                self.current_data = self.xenium
            case _:
                raise ValueError("This mode isn't accounted for.")
        self._UI_mode = new_mode
            
    @property
    def UI_mode(self):
        return self._UI_mode
    
    @UI_mode.setter
    def UI_mode(self, new_mode):
        self.__switch_current_data(new_mode)

class GVData:
    ''' This class is used to store user-selected parameters on disk persistently,
    and to pass the information to the main script to interpret. The class will initialize
    with values I have chosen (can modify these in the init below, or with certain global 
    variables above.) '''

    def __init__(self, user_data: UserData, channels = copy.copy(CHANNELS_STR), qptiff_path = None, 
                imageSize = 100, specific_cell = None, page_size = 56, global_sort = "Sort object table by Cell Id",
                cells_per_row = 8):
        self.user = user_data
        self.imageSize = imageSize # Int - size of EACH punchout around a cell
        self.channels = channels # String array - user choice for channels to read and display
        self.active_channels = channels
        self.specific_cell = specific_cell # Dictionary of the format {'ID': (int),'Annotation Layer': (str)}, or None 
        self.page_size = page_size # Integer - How many cells should be displayed per page
        self.global_sort = global_sort # String - Header to use to sort the object data. Default is cell ID (sheet is usually pre-sorted like this)
        self.cells_per_row = cells_per_row # Int - how many cells should be placed in a row before wrapping to the next (multichannel mode only)
        self.statuses = copy.copy(HALO_STATUSES) # Dict of statuses and string keybinds, e.g. {'status A':'a'}
        self.statuses_hex = copy.copy(HALO_STATUSES_HEX) # Dict of statuses and HEX codes of color mappings, e.g. {'status A':'#ff0000'}
        self.phenotype_mappings = {} # Dict of user selected phenotypes and their status mappings. Cells in the data of these phenotypes will be kept for viewing and assigned the given status 
        self.phenotype_mappings_label = '<u>Phenotypes</u><br>All' # String representation of the above info for displaying in a QLabel
        self.annotation_mappings = {} # Dict of user selected annotations and their status mappings. Cells in the data of these annotations will be kept for viewing and assigned the given status 
        self.annotation_mappings_label = '<u>Annotations</u><br>All'# String representation of the above info for displaying in a QLabel
        self.analysisRegionsInData = False # Bool that tracks whether the object data has an 'Analysis Region' field with multiple annotations. Useful later
        self.filters = []
        self.filters_label = '<u>Filters</u><br>None'
        self.possible_fluors_in_data = ['DAPI','Opal 480','Opal 520', 'Opal 570', 'Opal 620','Opal 690', 'Opal 720', 'AF', 'Sample AF', 'Autofluorescence']
        self.non_phenotype_fluor_suffixes_in_data = ['Positive Classification', 'Positive Nucleus Classification','Positive Cytoplasm Classification',
                    'Cell Intensity','Nucleus Intensity', 'Cytoplasm Intensity', '% Nucleus Completeness', '% Cytoplasm Completeness',
                    '% Cell Completeness', '% Completeness']
        self.other_cols_in_data = ['Cell Area (µm²)', 'Cytoplasm Area (µm²)', 'Nucleus Area (µm²)', 'Nucleus Perimeter (µm)', 'Nucleus Roundness',
                  'Image Location','Image File Name', 'Analysis Region', 'Algorithm Name', 'Object Id', 'XMin', 'XMax', 'YMin', 'YMax', 'Notes']
        self.phenotypes = []
        self.qptiff_path = qptiff_path # String - image path

        self.last_system_folder_visited = "C:/"
        self.last_image_save_folder = "C:/"
        self.objectDataPath = '' # String - object data path
        self.objectDataFrame = None # Pandas DataFrame created using read_csv. Storing this saves time when wanting the df later
        self.available_colors = list(colormap.keys())
        self.channelColors = dict(zip(channels, list(colormap.keys())[:len(channels)] )) #String array - Order of multichannel data found in the image
        self.channelOrder = dict(zip(channels,range(len(channels))))
        self.statuses_rgba = {key: ImageColor.getcolor(val, "RGBA") for key,val in self.statuses_hex.items()} # Dict of statuses and RGBA tuples color mappings, e.g. {'status A':(255,0,0,255)}
        self.available_statuses_keybinds = ["q","w","e","t","y","u","o","p","d","f","g","j","l","z","x",",",".","/","[","]",";","'"]
        self.view_settings = self.remake_viewsettings(pass_value=True) # Dict of view settings. Will NOT change after reading from file. ex: {fluor A gamma: 0.5}
        self.view_settings_path = '' # Path to .viewsettings file. The file is a type of HALO export and will use XML formatting
        self.imported_view_settings = None


    ''' Restore viewsettings to [chn] gamma : 0.5, [chn] whitein:255, [chn] blackin:0
        for all channels in the data'''
    def remake_viewsettings(self, pass_value = False):
        vs_list = [f"{x[0]} {x[1]}" for x in product(list(self.channelOrder.keys()), ['gamma', 'white-in', 'black-in'])]
        if pass_value:
            return {v:[0.5, 255, 0][i%3] for i,v in enumerate(vs_list)}
        else:
            self.view_settings = {v:[0.5, 255, 0][i%3] for i,v in enumerate(vs_list)}
    
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
        
        cname_dict = {code : cname for cname, code in colormap.items()}
        
        issues = []
        def _catch_problems(self_param, pos, table_column, inform_index_error = False):
            try:
                self.view_settings[f'{fluor} {self_param}'] = vs_table.iloc[pos][table_column]
                return []
            except KeyError:
                return [f"Could not find {table_column} in the viewsettings file"]
            except IndexError:
                if not inform_index_error:
                    return [f"Viewsettings file contains data for channel {pos}, but the loaded image only has {len(self.channels)} channels"]
                else:
                    return []

        #TODO what if there's a miss for a code? Need to create a new color and add it to the table
        for pos, fluor in enumerate(self.channelOrder):
            if fluor == "Composite": continue
            
            issues += _catch_problems('gamma',pos,'Gamma', inform_index_error= True)
            issues += _catch_problems('black-in',pos,'BlackInAbsolute')
            issues += _catch_problems('white-in',pos,'WhiteInAbsolute')
            try:
                hc = hex_color_from_decimal(vs_table.iloc[pos]['ColorCode'])
                self.channelColors[fluor] = cname_dict[hc]
            except IndexError:
                pass # Already would have informed user about this above
            except KeyError:
                #TODO add automatically?
                issues += [f"The color {hc} does not currently exist in my table. Please add it and try again"]
            except (ValueError, TypeError):
                issues += [f"Cannot parse the color passed for channel {pos} ({fluor}). HALO format viewsettings use decimal color codes"]
            
        return issues
    
    ''' Create a .viewsettings file compatible with HALO from the current view settings
        If the user imported a view settings file at the start, we will work from that. '''
    def write_view_settings(self, destination_path):
        print(self.channelColors)
        user_colors_hex = {fluor : colormap[clr] for fluor, clr in self.channelColors.items()}
        print(user_colors_hex)

        if self.imported_view_settings is not None:
            # User import view settings. Modify this table in place and write somewhere
            df = self.imported_view_settings
            # Set color codes, 
            for i, (fluor, color_hex) in enumerate(user_colors_hex.items()):
                color_dec = decimal_color_from_hex(color_hex)
                df.loc[df["Id"] == i, "ColorCode"] = color_dec
                df.loc[df["Id"] == i, "BlackInAbsolute"] = int(self.user.session.view_settings[f'{fluor} black-in'])
                df.loc[df["Id"] == i, "BlackIn"] = self.user.session.view_settings[f'{fluor} black-in'] / 255
                df.loc[df["Id"] == i, "WhiteInAbsolute"] = int(self.user.session.view_settings[f'{fluor} white-in'])
                df.loc[df["Id"] == i, "WhiteIn"] = self.user.session.view_settings[f'{fluor} white-in'] / 255
                df.loc[df["Id"] == i, "Gamma"] = self.user.session.view_settings[f'{fluor} gamma'] 
                df.loc[df["Id"] == i, "Visible"] = True if fluor in self.active_channels else False
                df.loc[df["Id"] == i, "Absorption"] = 1 if self.user.session.absorption_mode else 0
        else: 
            # Make table from scratch
            vscols = ['Id', 'ColorCode', 'Brightness', 'Contrast', 'Gamma', 'Absorption',
                    'BlackIn', 'WhiteIn', 'Visible', 'BlackInAbsolute', 'WhiteInAbsolute'] # No need to add any CustomName tags
            df = pd.DataFrame([], columns = vscols)
            for i, (fluor, color_hex) in enumerate(user_colors_hex.items()):
                row = { 'Id' : i, 
                        'ColorCode': [ decimal_color_from_hex(color_hex) ], 
                        'Brightness': [1], 'Contrast':[1], 
                        'Gamma':[ self.user.session.view_settings[f'{fluor} gamma'] ], 
                        'Absorption': [1 if self.user.session.absorption_mode else 0],
                        'BlackIn': [self.user.session.view_settings[f'{fluor} black-in'] / 255], 
                        'WhiteIn': [self.user.session.view_settings[f'{fluor} white-in'] / 255], 
                        'Visible': [True if fluor in self.active_channels else False], 
                        'BlackInAbsolute': [int(self.user.session.view_settings[f'{fluor} black-in'])], 
                        'WhiteInAbsolute':[int(self.user.session.view_settings[f'{fluor} white-in'])]}
                df = pd.concat([df, pd.DataFrame.from_dict(row)])

        #TODO Check if the unpaired </CustomName> tags don't actually work on import with HALO
        df.reset_index(drop=True).to_xml(destination_path, index=False, root_name="ViewSettings", row_name="Channel", xml_declaration=False)


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

        df = self.user.session.current_cells.copy()
        self.objectDataFrame.update(df) # overwrite data with new cols


        vcols = [f'Validation | {s}' for s in self.statuses]
        for status, vcol in zip(self.statuses, vcols):
            self.objectDataFrame[vcol] = np.where(self.objectDataFrame["Validation"] == status,1,0)
        self.objectDataFrame[vcols + ['Object Id']] = self.objectDataFrame[vcols + ['Object Id']].astype(int)
        
        if to_disk:
            try:
                self.objectDataFrame.to_csv(self.objectDataPath, index=False)
                # self.objectDataFrame.reset_index(drop=True,inplace=True)
            except PermissionError: # file in use
                # self.objectDataFrame.reset_index(drop=True,inplace=True)
                return False
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


class HaloData(GVData):
    def __init__(self, parent):
        super().__init__(parent)
        # self.user = parent

class CosMxData(GVData):
    def __init__(self, parent):
        super().__init__(parent)
        # self.user = parent

class XeniumData(GVData):
    def __init__(self, parent):
        super().__init__(parent)
        # self.user = parent

def storeObject(obj : UserData, filename : str):
    ''' Write the class object to a file. Default location is data/presets'''
    try:
        if not pathlib.Path(filename).parent.exists(): # Create the profiles/ folder
            pathlib.Path(filename).parent.mkdir()
        obj.session = SessionVariables() # reset per-session variables to save space
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
    ''' Read the class object from a file. Default location is profiles/active.gvconfig'''
    try:
        if not pathlib.Path(filename).parent.exists(): # Create the profiles/ folder
            pathlib.Path(filename).parent.mkdir()
        infile = open(filename,'rb')
        new_obj = pickle.load(infile)
        infile.close()

        new_obj.session = SessionVariables() # just make sure nothing happened here
        new_obj.fonts = ViewerFonts()
        return new_obj
    except Exception as e:
        print(e)
        # If no data yet (first time running the viewer), load up defaults
        return UserData()