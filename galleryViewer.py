'''
CTC viewer for Napari
Started on 6/7/22
Peter Richieri
'''

import tifffile
import rasterio
from rasterio.windows import Window
import napari
from napari.types import ImageData
# from napari.qt.threading import thread_worker # Needed to add / remove a lot of layers without freezing
from magicgui import magicgui, magic_factory
from PyQt5.QtWidgets import QLabel, QLineEdit, QPushButton, QRadioButton, QSpinBox, QButtonGroup, QSizePolicy
from PyQt5.QtCore import Qt
import numpy as np
import pandas as pd
import openpyxl # necessary, do not remove
# import skimage.filters
# import gc # might garbage collect later
# import math
# import vispy.color as vpc
import matplotlib
from matplotlib import cm
from matplotlib import colors as mplcolors
from matplotlib import pyplot as plt
import custom_maps
# norm = plt.Normalize()
import copy
import time
import warnings
warnings.filterwarnings("ignore")

######-------------------- Globals, will be loaded through pre-processing QT gui #TODO -------------######
QPTIFF_LAYER_TO_RIP = 0 # 0 is high quality. Can use 1 for testing (BF only, loads faster)
cell_colors = ['gray', 'purple' , 'blue', 'green', 'orange','red', 'yellow', 'Pink', 'cyan']
print('\n--------------- adding custom cmaps\n')

for colormap in cell_colors:
    # print(f'cmap: {colormap}')
    if colormap == 'gray': continue
    exec(f'my_map = custom_maps.create_{colormap}_lut()')
    exec(f'custom = mplcolors.LinearSegmentedColormap.from_list("{colormap}", my_map)')
    exec(f'cm.register_cmap(name = "{colormap}", cmap = custom)')
# print(f'\n---------My colormaps are now {plt.colormaps()}--------\n')

cell_colors = ['blue', 'purple' , 'red', 'green', 'orange','red', 'green', 'Pink', 'cyan'] # for local execution
fluor_to_color = {}
# qptiff = r"N:\CNY_Polaris\2021-11(Nov)\Haber Lab\Leukopak_Liver_NegDep_Slide1\Scan1\memmap_test.tif"
qptiff = r"C:\Users\prich\Desktop\Projects\MGH\CTC-Gallery-Viewer\auto_test.tif"
OBJECT_DATA = r"C:\Users\prich\Desktop\Projects\MGH\CTC_Example\ctc_example_data.csv"
# OBJECT_DATA = r"N:\CNY_Polaris\2021-11(Nov)\Haber Lab\Leukopak_Liver_NegDep_Slide1\Scan1\PMR_test_Results.csv"
PUNCHOUT_SIZE = 90 # microns or pixels? Probably pixels
CELL_OFFSET= 0 # Saves the current number of cells shown. Useful when pulling 'next 10 cells' 
CELL_LIMIT = 5 # How many cells will be shown in next batch
PHENOTYPE = 'Tumor' #'CTC 488pos'
CELL_ID_START = 550 # debug?
DAPI = 0; OPAL480 = 3; OPAL520 = 6; OPAL570 = 1; OPAL620 = 4; OPAL690 = 2; OPAL780 = 5; AF=7; Composite = 8
# CHANNELS_STR = ["DAPI", "OPAL480", "OPAL520", "OPAL570", "OPAL620", "OPAL690", "OPAL780", "AF", "Composite"]
CHANNELS_STR = ["DAPI", "OPAL520", "OPAL690", "Composite"] # for local execution / debugging
# CHANNELS = [DAPI, OPAL480, OPAL520, OPAL570, OPAL620, OPAL690,OPAL780,AF,Composite] # Default. Not really that useful info since channel order was added.
CHANNELS = [DAPI, OPAL520,OPAL690, Composite] # for local execution / debugging
ADJUSTED = copy.copy(CHANNELS)
CHANNEL_ORDER = ['DAPI', 'OPAL570', 'OPAL690', 'OPAL480', 'OPAL620', 'OPAL780', 'OPAL520', 'AF', 'Composite'] # to save variable position data for channels (they can be in any order...)
VIEWER = None
SC_DATA = None # Using this to store data to coerce the exec function into doing what I want
TEMP = None
IMAGE_DATA_ORIGINAL = {}; IMAGE_DATA_ADJUSTED = {}; ADJUSTMENT_SETTINGS={}; 
SAVED_NOTES={} ; STATUS_LIST={}; XY_STORE = [1,2,3]
RAW_PYRAMID=None
NOTES_WIDGET = None; ALL_CUSTOM_WIDGETS = {}
COMPOSITE_MODE = True # Start in composite mode
RASTERS = None


######------------------------- MagicGUI Widgets, Functions, and accessories ---------------------######
#TODO merge some of the GUI elements into the same container to prevent strange spacing issues

def validate_adjustment(layer):
    layer_name = layer.name.split()[2] # grab last part of label
    if layer_name == 'DAPI' and DAPI in ADJUSTED:
        return True
    elif layer_name == '480' and OPAL480 in ADJUSTED:
        return True
    elif layer_name == '520'and OPAL520 in ADJUSTED:
        return True
    elif layer_name == '570' and OPAL570 in ADJUSTED:
        return True
    elif layer_name == '620'and OPAL620 in ADJUSTED:
        return True
    elif layer_name == '690'and OPAL690 in ADJUSTED:
        return True
    elif layer_name == '780'and OPAL780 in ADJUSTED:
        return True
    elif layer_name == 'AF'and AF in ADJUSTED:
        return True
    else:
        return False

# @magicgui(auto_call=True,
#             datapoint={"label":"N/A"})
# def show_intensity(datapoint: str):
#     datapoint = str(VIEWER.Layers.Image.get_value() )
#     show_intensity.show()

## --- Composite functions 
def adjust_composite_gamma(layer, gamma, keepSettingsTheSame = False):
    def _convert_to_rgb(data, colormap, divisor):
        # You have to do it like this. Seriously. 
        global SC_DATA, TEMP
        SC_DATA = data /divisor
        loc = {}
        exec(f'TEMP = cm.get_cmap("{colormap}")', globals())
        exec(f'rgb = TEMP(SC_DATA)', globals(), loc)
        return loc['rgb']

    # print(f'Checking keys of outer dict: {IMAGE_DATA_ORIGINAL.keys()}')
    # print(f'My name is {layer.name}')
    # composite = copy.copy(IMAGE_DATA_STORE[layer.name])
    # print(f'Checking keys of inner dict: {color_dict.keys()}')
    # print(type(layer.colormap))
    # print(f'{layer.colormap} vs str() {str(layer.colormap)}')
    stripped_name = layer.name.rstrip('Composite') # Format is 'Cell 271'

    # for chn in ADJUSTED:
    #     print(f'to be adjusted: {chn}')
    # print(f'\n DICT: {ADJUSTMENT_SETTINGS}')

    composite = []
    # get data from other CHECKED channels, not including Composite (always 8)
    need_gamma_adjustment = copy.copy(ADJUSTED)
    if Composite in ADJUSTED: need_gamma_adjustment.remove(Composite)
    fluors_only = copy.copy(CHANNELS)
    fluors_only.remove(Composite)
    # print(f'\n dumping ADJUSTED needed: {ADJUSTED}\n and CHANNELS: {CHANNELS}\n and CHANNELS_STR {CHANNELS_STR}\n and CHANNEL_ORDER {CHANNEL_ORDER}\n and something?? {CHANNELS}')
    # print(f'\n dumping adjustment needed: {need_gamma_adjustment}')
    for chn_pos in fluors_only:
        chn_str = CHANNEL_ORDER[chn_pos]
        chn_str = chn_str.lstrip('OPAL') # OPAL is not in the name of the data key
        # gamma adjust
        
        # In this certain case, don't show anything for this channel
        if Composite not in ADJUSTED and chn_pos not in need_gamma_adjustment:
            # print(f'Conditions satisfied!\n')
            chn_data = copy.copy(IMAGE_DATA_ADJUSTED[stripped_name+chn_str])
            chn_data.fill(0)
            chn_data = _convert_to_rgb(np.asarray(chn_data), fluor_to_color[chn_str], divisor=1)
            composite.append([chn_data])
            continue

        if chn_pos in need_gamma_adjustment:
            # print(f'Will gamma adjust {chn_str}')
            chn_data = copy.copy(IMAGE_DATA_ORIGINAL[stripped_name+chn_str])

            low = ADJUSTMENT_SETTINGS[chn_str+' black-in'] / 255.0
            high = ADJUSTMENT_SETTINGS[chn_str+' white-in'] / 255.0
            chn_data = np.clip(chn_data,low,high)
            color_range = high - low
            if color_range != 0:
                chn_data = (chn_data - low) / color_range
            #TODO determine whether gamma gets changed before or after color mapping
            # chn_data = _convert_to_rgb(chn_data, fluor_to_color[chn_str], divisor=1) # can do this at the end?
            if keepSettingsTheSame:
                gamma_correct = np.vectorize(lambda x:x**ADJUSTMENT_SETTINGS[chn_str+' gamma'])
            else:
                gamma_correct = np.vectorize(lambda x:x**gamma)
            chn_data = gamma_correct(chn_data)
            # print(f'Checking dimensions of chn_data: {np.asarray(chn_data).shape}')
            IMAGE_DATA_ADJUSTED[stripped_name+chn_str] = chn_data # store adjustments
        else:
            chn_data = np.asarray(copy.copy(IMAGE_DATA_ADJUSTED[stripped_name+chn_str]))
        chn_data = _convert_to_rgb(chn_data, fluor_to_color[chn_str], divisor=1)#len(CHANNELS)-1) # subtract one bc it contains the composite
        composite.append([chn_data])


    # print(f'Checking dimensions of composite: {np.asarray(composite).shape}')
    composite = np.asarray(composite)[:,0,:,:] # it's nested right now, so extract the values. Shape after this should be (#channels, pixelwidth, pixelheight, 4) 4 for rgba
    # print(f'Checking dimensions of composite after extract: {np.asarray(composite).shape}')
    composite = np.sum(composite, axis=0) 
    composite=np.clip(composite,0,np.max(composite))
    # print(f'Checking dimensions of composite after sum: {np.asarray(composite).shape}')
    composite[:,:,3] = 1.0

    rgb_mins = [] ## Axis here?
    rgb_maxes = []
    for i in range(3):
        temp = np.ndarray.flatten(composite[:,:,i])
        
        rgb_mins.append(np.min(temp))
        rgb_maxes.append(np.max(temp))
    
    for i in range(3):
        # print(f'Current max is {rgb_maxes[i]} and type is {type(rgb_maxes[i])}\n')
        composite[:,:,i] = composite[:,:,i] - float(rgb_mins[i])
        # the 1.0 value on the next line represents the 'max' value in a given channel. Really not sure if it should stay 1 or not.
        #TODO
        composite[:,:,i] = composite[:,:,i] /(float(1.0) - float(rgb_mins[i]))
        composite[:,:,i] = composite[:,:,i] * 255.0

    IMAGE_DATA_ADJUSTED[layer.name] = composite.astype('int')
    # print(f'Final check of dimensions of composite before setting data: {np.asarray(composite).shape}')
    layer.data = composite.astype('int') # casting is crucial


def adjust_composite_limits(layer):

    def _convert_to_rgb(data, colormap, divisor):
        # You have to do it like this. Seriously. 
        global SC_DATA, TEMP
        SC_DATA = data /divisor
        loc = {}
        exec(f'TEMP = cm.get_cmap("{colormap}")', globals())
        exec(f'rgb = TEMP(SC_DATA)', globals(), loc)
        return loc['rgb']

    # print(f'Checking keys of outer dict: {IMAGE_DATA_ORIGINAL.keys()}')
    # print(f'My name is {layer.name}')
    # composite = copy.copy(IMAGE_DATA_STORE[layer.name])
    # print(f'Checking keys of inner dict: {color_dict.keys()}')
    # print(type(layer.colormap))
    # print(f'{layer.colormap} vs str() {str(layer.colormap)}')
    stripped_name = layer.name.rstrip('Composite') # Format is 'Cell 271'

    # for chn in ADJUSTED:
    #     print(f'to be adjusted: {chn}')

    # print(f'\n DICT: {ADJUSTMENT_SETTINGS}')
    composite = []
    # get data from other CHECKED channels, not including Composite (always 8)
    need_contrast_adjustment = copy.copy(ADJUSTED)
    if Composite in ADJUSTED: need_contrast_adjustment.remove(Composite) # nervous about hard-coding this...
    fluors_only = copy.copy(CHANNELS)
    fluors_only.remove(Composite)
    # print(f'\n dumping ADJUSTED needed: {ADJUSTED}\n and CHANNELS: {CHANNELS}\n and CHANNELS_STR {CHANNELS_STR}\n and CHANNEL_ORDER {CHANNEL_ORDER}\n and something?? {CHANNELS}')
    # print(f'\n dumping contrast adjustment needed: {need_contrast_adjustment}')
    for chn_pos in fluors_only:
        chn_str = CHANNEL_ORDER[chn_pos]
        chn_str = chn_str.lstrip('OPAL') # OPAL is not in the name of the data key
        # gamma adjust

        # In this certain case, don't show anything for this channel
        if Composite not in ADJUSTED and chn_pos not in need_contrast_adjustment:
            chn_data = copy.copy(IMAGE_DATA_ADJUSTED[stripped_name+chn_str])
            chn_data.fill(0)
            chn_data = _convert_to_rgb(np.asarray(chn_data), fluor_to_color[chn_str], divisor=1)
            composite.append([chn_data])
            continue

        if chn_pos in need_contrast_adjustment:
            # print(f'Will contrast adjust {chn_str}')
            chn_data = copy.copy(IMAGE_DATA_ORIGINAL[stripped_name+chn_str])

            low = ADJUSTMENT_SETTINGS[chn_str+' black-in'] / 255.0
            high = ADJUSTMENT_SETTINGS[chn_str+' white-in'] / 255.0
            chn_data = np.clip(chn_data,low,high)
            color_range = high - low
            if color_range != 0:
                chn_data = (chn_data - low) / color_range
            gamma_correct = np.vectorize(lambda x:x**ADJUSTMENT_SETTINGS[chn_str+' gamma'])
            chn_data = gamma_correct(chn_data)
            # chn_data = _convert_to_rgb(chn_data, fluor_to_color[chn_str], divisor=1) # can do this at the end?
            # print(f'Checking dimensions of chn_data: {np.asarray(chn_data).shape}')
            IMAGE_DATA_ADJUSTED[stripped_name+chn_str] = chn_data # store adjustments
        else:
            print(f'Just fetching {chn_str} data...')
            chn_data = copy.copy(IMAGE_DATA_ADJUSTED[stripped_name+chn_str])
        # print(f'Converting back to rgb, using the {fluor_to_color[chn_str]} palette ...')
        chn_data = _convert_to_rgb(np.asarray(chn_data), fluor_to_color[chn_str], divisor=1)#len(CHANNELS)-1) # subtract one bc it contains the composite
        composite.append([chn_data])


    # print(f'Checking dimensions of composite: {np.asarray(composite).shape}')
    composite = np.asarray(composite)[:,0,:,:] # it's nested right now, so extract the values. Shape after this should be (#channels, pixelwidth, pixelheight, 4) 4 for rgba
    # print(f'Checking dimensions of composite after extract: {np.asarray(composite).shape}')
    composite = np.sum(composite, axis=0) 
    # print(f'Checking dimensions of composite after sum: {np.asarray(composite).shape}')
    composite[:,:,3] = 1.0 # restore alpha value.

    rgb_mins = [] ## Axis here?
    rgb_maxes = []
    for i in range(3):
        temp = np.ndarray.flatten(composite[:,:,i])
        
        rgb_mins.append(np.min(temp))
        rgb_maxes.append(np.max(temp))
    
    for i in range(3):
        # print(f'Current max is {rgb_maxes[i]} and type is {type(rgb_maxes[i])}\n')
        composite[:,:,i] = composite[:,:,i] - float(rgb_mins[i])
        composite[:,:,i] = composite[:,:,i] /(float(1.0) - float(rgb_mins[i]))
        composite[:,:,i] = composite[:,:,i] * 255.0

    # Save result
    IMAGE_DATA_ADJUSTED[layer.name] = composite.astype('int')
    # print(f'Final check of dimensions of composite before setting data: {np.asarray(composite).shape}')
    layer.data = composite.astype('int') # casting is crucial

def reuse_gamma():
    # print(f'\nDumping adjustment dict... \n {ADJUSTMENT_SETTINGS}\n')
    # print(f'ADJUSTED is {ADJUSTED}')
    for ctclayer in VIEWER.layers:
        if ctclayer.name == 'Batch Name': continue
        # print(f'layername is {ctclayer}')
        # no longer elif: want to do composite and all checked channels at the same time
        if validate_adjustment(ctclayer):
            # print(f"Validated! Searching dict for {ctclayer.name.split()[2]+' gamma'}")
            # print(f"Result is {ADJUSTMENT_SETTINGS[ctclayer.name.split()[2]+' gamma']}")
            # print(f"Result type is {type(ADJUSTMENT_SETTINGS[ctclayer.name.split()[2]+' gamma'])}")
            ctclayer.gamma = ADJUSTMENT_SETTINGS[ctclayer.name.split()[2]+' gamma']
        elif ctclayer.name.split()[2] == 'Composite' and len(ADJUSTED)>0:
            # this gamma doesn't matter since it won't be considered - The final parameter
            #   tells the function to skip it
            adjust_composite_gamma(ctclayer,gamma = 1.0, keepSettingsTheSame=True)

def reuse_contrast_limits():
    for layer in VIEWER.layers:
        if layer.name == 'Batch Name': continue
        if validate_adjustment(layer):
            name = layer.name.split()[2]
            layer.contrast_limits = (ADJUSTMENT_SETTINGS[name+' black-in'], ADJUSTMENT_SETTINGS[name+' white-in'])
        elif layer.name.split()[2] == 'Composite' and len(ADJUSTED)>0: 
            adjust_composite_limits(layer)

## --- Bottom bar functions and GUI elements 
def adjust_gamma(viewer, gamma):
    def _update_dictionary(name, val):
        global ADJUSTMENT_SETTINGS
        ADJUSTMENT_SETTINGS[name+' gamma'] = val
    # This allows the function to be called to reuse the same settings instead of updating them
    #   useful for keeping settings when loading next batch or switching modes. 
    for fluor in ADJUSTED:
        fluorname = CHANNEL_ORDER[fluor].lstrip('OPAL')
        _update_dictionary(fluorname,gamma)

    for ctclayer in viewer.layers:
        if ctclayer.name == 'Batch Name': continue
        # no longer elif: want to do composite and all checked channels at the same time
        if validate_adjustment(ctclayer):
            ctclayer.gamma = gamma
        elif ctclayer.name.split()[2] == 'Composite' and len(ADJUSTED)>0:
            adjust_composite_gamma(ctclayer, gamma)

@magicgui(auto_call=True,
        gamma={"widget_type": "FloatSlider", "max":1.0, "min":0.01},
        layout = 'horizontal')
def adjust_gamma_widget(gamma: float = 1.0) -> ImageData: 
    adjust_gamma(VIEWER,gamma)
adjust_gamma_widget.visible=False

@magicgui(auto_call=True,
        white_in={"widget_type": "FloatSlider", "max":255,"min":1.0, "label": "White-in"},
        layout = 'horizontal')
def adjust_whitein(white_in: float = 255) -> ImageData:
    def _update_dictionary(name, val):
        global ADJUSTMENT_SETTINGS
        ADJUSTMENT_SETTINGS[name+' white-in'] = val
    for fluor in ADJUSTED:
        fluorname = CHANNEL_ORDER[fluor].lstrip('OPAL')
        _update_dictionary(fluorname,white_in)
    
    for ctclayer in VIEWER.layers:
        if ctclayer.name == 'Batch Name': continue
        # no longer elif: want to do composite and all checked channels at the same time
        if validate_adjustment(ctclayer):
            ctclayer.contrast_limits = (ctclayer.contrast_limits[0], white_in)
        elif ctclayer.name.split()[2] == 'Composite' and len(ADJUSTED)>0:
            # Works in both cases
            adjust_composite_limits(ctclayer)

@magicgui(auto_call=True,
        black_in={"widget_type": "FloatSlider", "max":255, "label":"Black-in"},
        layout = 'horizontal')
def adjust_blackin(black_in: float = 0) -> ImageData:
    def _update_dictionary(name, val):
        global ADJUSTMENT_SETTINGS
        ADJUSTMENT_SETTINGS[name+' black-in'] = val
    
    for fluor in ADJUSTED:
        fluorname = CHANNEL_ORDER[fluor].lstrip('OPAL')
        _update_dictionary(fluorname,black_in)

    for ctclayer in VIEWER.layers:
        if ctclayer.name == 'Batch Name': continue
        # no longer elif: want to do composite and all checked channels at the same time
        if validate_adjustment(ctclayer):
            ctclayer.contrast_limits = (black_in, ctclayer.contrast_limits[1])
        elif ctclayer.name.split()[2] == 'Composite' and len(ADJUSTED)>0:
            adjust_composite_limits(ctclayer)

# Called in a loop to create as many GUI elements as needed
#TODO use magicfactory decorator to do this. It probably is better practice, and surely looks nicer
def dynamic_checkbox_creator(checkbox_name, setChecked = True):

    @magicgui(auto_call=True,
            check={"widget_type": "CheckBox", "text": checkbox_name, "value": setChecked},
            layout = 'horizontal')
    def myfunc(check: bool = setChecked):
        # print(f'in myfunc backend CHANNELS are {CHANNELS}, and {CHANNELS_STR}. Trying to remove {checkbox_name}, whose global value is {globals()[checkbox_name]}, from {ADJUSTED}')
        if not COMPOSITE_MODE:
            if check:
                ADJUSTED.append(globals()[checkbox_name])
                # ADJUSTMENT_SETTINGS[checkbox_name+' box'] = True
                # print(f'In check function. Current state, about to return and ADJUSTED is {ADJUSTED}, just added {checkbox_name}')
            else:
                ADJUSTED.remove(globals()[checkbox_name])
                # ADJUSTMENT_SETTINGS[checkbox_name+' box'] = False
                # print(f'In check function. Current state, about to return and ADJUSTED is {ADJUSTED}, just removed {checkbox_name}')
        else: # In composite mode 
            if check:
                ADJUSTED.append(globals()[checkbox_name])
            else:
                ADJUSTED.remove(globals()[checkbox_name])
            # now remake composite images with the channels listed in ADJUSTED
            #   But only if the "Composite" check is active, otherwise show all channels in the image
            # if Composite not in ADJUSTED:
        
        # This will show/hide the appropriate layers in the composite image when checking the box
        for layer in VIEWER.layers:
            if layer.name == 'Batch Name': continue
            if layer.name.split()[2] == 'Composite' and len(ADJUSTED)>0:
                adjust_composite_gamma(layer, gamma=0.5, keepSettingsTheSame = True)
            
    return myfunc

# print(f'dir is {dir()}')
def checkbox_setup():
    all_boxes = []
    for checkbox_name in CHANNELS_STR:   
        #Turn off composite by default.
        print(f'creating checkbox func for {checkbox_name}')
        if False: #checkbox_name == 'Composite':
            ADJUSTMENT_SETTINGS[checkbox_name+' box'] = False
            exec(f"globals()[\'{checkbox_name+'_box'}\'] = globals()[\'dynamic_checkbox_creator\'](checkbox_name, setChecked=False)") # If doing this is wrong I don't want to be right
        else:
            # ADJUSTMENT_SETTINGS[checkbox_name+' box'] = True
            exec(f"globals()[\'{checkbox_name+'_box'}\'] = globals()[\'dynamic_checkbox_creator\'](checkbox_name)")
        all_boxes.append(globals()[f'{checkbox_name}_box'])
        # exec(f"viewer.window.add_dock_widget({marker_function+'_box'}, area='bottom')")
    return all_boxes
checkbox_setup()

# This is called in GUI_execute, because the global 'ADJUSTED' variable will be changed at that time. 
# We want to make sure that the backend bookkeeping is congruent with the front-end checkbox, which is 
#   unchecked by now.  
def fix_default_composite_adj():
    global ADJUSTED
    ADJUSTED = list(filter(lambda a: a != globals()["Composite"], ADJUSTED))

## --- Side bar functions and GUI elements 

### --- The following attempts at removing layers with a separate thread are deprecated
def threading_remove_layer(layer):
    try:
        VIEWER.layers.remove(layer)
    except KeyError:
        # Just in case something goes wrong here.
        pass

def threading_add_layer(layer):
    try:
        VIEWER.add_image(layer)
    except KeyError:
        # Just in case something goes wrong here.
        pass

def one_by_one_layers(viewer):
    for layer in list(viewer.layers):
        # time.sleep(0.5) # wtf
        yield layer
# @thread_worker(connect={'yielded': threading_remove_layer})
def concurrent_clear(viewer):
    layers = one_by_one_layers(viewer)
    for layer in layers:
        # viewer.processEvents()
        viewer.layers.remove(layer)

### --- 
# @magicgui(call_button='Change Mode',
#         Mode={"widget_type": "RadioButtons","orientation": "vertical",
#         "choices": [("Show all channels", 1), ("Composite Only", 2)]})#,layout = 'horizontal')
def toggle_composite_viewstatus(all_channels_rb,composite_only_rb):
    def _save_validation(VIEWER, Mode):
        print(f'reading from {OBJECT_DATA}')
        hdata = pd.read_csv(OBJECT_DATA)
        try:
            hdata.loc[2,"Validation"]
        except KeyError:
            hdata.insert(4,"Validation", "unseen")
            hdata.loc[hdata[PHENOTYPE]==0,"Validation"] = ""
        try:
            hdata.loc[2,"Notes"]
        except KeyError:
            hdata.insert(5,"Notes","-")
            hdata.fillna("")

        for layer in VIEWER.layers:
            if 'status' in layer.name:
                status = layer.name.split('_')[1]
                cell_id = layer.name.split()[1]
            else:
                continue
            
            print(f"LName: {layer.name} , status {status}, cid {cell_id}")
            try:
                hdata.loc[hdata["Object Id"]==int(cell_id),"Validation"] = status
                hdata.loc[hdata["Object Id"]==int(cell_id),"Notes"] = SAVED_NOTES[cell_id]
            except:
                print("There's an issue... ")
        try:
            VIEWER.status = 'Saving ...'
            hdata.to_csv(OBJECT_DATA, index=False)
            if Mode == 1:
                VIEWER.status = 'Channels Mode enabled. Decisions loaded successfully.'
            elif Mode ==2:
                VIEWER.status = 'Composite Mode enabled. Decisions loaded successfully.'
            return True
        except:
            #TODO Maybe it's an excel sheet?
            if Mode == 1:
                VIEWER.status = 'Channels Mode enabled. But, there was a problem saving your decisions. Close your data file?'
            elif Mode ==2:
                VIEWER.status = 'Composite Mode enabled. But, there was a problem saving your decisions. Close your data file?'
            return False
            # hdata.loc[:,1:].to_excel(
            # OBJECT_DATA,sheet_name='Exported from gallery viewer')
        VIEWER.status = 'Done saving!'
    
    if all_channels_rb.isChecked(): Mode = 1
    else: Mode=2

    # Do nothing in these cases
    global COMPOSITE_MODE # needed for changes later 
    if Mode==1 and COMPOSITE_MODE==False: return None
    elif Mode==2 and COMPOSITE_MODE==True: return None

    # Save data to file from current set
    VIEWER.status = 'Saving data to file...'
    _save_validation(VIEWER, Mode)

    # Hide the widgets to avoid crashing?
    for widg in ALL_CUSTOM_WIDGETS.values():
        widg.setVisible(False)

    print("|||| XY STORE INFO ||||")
    print(f"length is {len(XY_STORE)} and type is {type(XY_STORE)}")
    if Mode == 1: # change to Show All
        COMPOSITE_MODE = False
        print(f'\nAttempting to clear')
        # VIEWER.layers.clear()
        concurrent_clear(VIEWER)
        #data = extract_phenotype_xldata() # Don't need this since it is saved now
        add_layers(VIEWER,RAW_PYRAMID, copy.copy(XY_STORE), int(PUNCHOUT_SIZE/2), composite_enabled=False, new_batch=False)
    elif Mode ==2: # change to composite only
        COMPOSITE_MODE = True
        print(f'\nAttempting to clear')
        # VIEWER.layers.clear()
        concurrent_clear(VIEWER)
        #data = extract_phenotype_xldata() # Don't need this since it is saved now
        add_layers(VIEWER,RAW_PYRAMID, copy.copy(XY_STORE), int(PUNCHOUT_SIZE/2), composite_enabled=True, new_batch=False)
    else:
        raise Exception(f"Invalid parameter passed to toggle_composite_viewstatus: {Mode}. Must be 1 or 2.")
        # Perform adjustments before exiting function
    reuse_contrast_limits()
    reuse_gamma() # might not need to do both of these... One is enough?
    for widg in ALL_CUSTOM_WIDGETS.values(): # restore widgets
        widg.setVisible(True)

    set_viewer_to_neutral_zoom(VIEWER) # Fix zoomed out issue
    return None

# @magicgui(call_button='Load Cells',
#         Direction={"widget_type": "RadioButtons","orientation": "horizontal",
#         "choices": [("Next", 'fwd'), ("Previous", 'bkwd')]},
#         Amount={"widget_type": "SpinBox", "value":15,
#         "max":1000,"min":5})
def show_next_cell_group(next_cell_rb, previous_cell_rb, amount_sp):
    def _save_validation(VIEWER,numcells):
        print(f'reading from {OBJECT_DATA}')
        hdata = pd.read_csv(OBJECT_DATA)
        try:
            hdata.loc[2,"Validation"]
        except KeyError:
            hdata.insert(4,"Validation", "unseen")
            hdata.loc[hdata[PHENOTYPE]==0,"Validation"] = ""
        try:
            hdata.loc[2,"Notes"]
        except KeyError:
            hdata.insert(5,"Notes","-")
            hdata.fillna("")

        for layer in VIEWER.layers:
            if 'status' in layer.name:
                status = layer.name.split('_')[1]
                cell_id = layer.name.split()[1]
            else:
                continue
            
            print(f"LName: {layer.name} , status {status}, cid {cell_id}")
            try:
                hdata.loc[hdata["Object Id"]==int(cell_id),"Validation"] = status
                hdata.loc[hdata["Object Id"]==int(cell_id),"Notes"] = SAVED_NOTES[cell_id]
            except:
                print("There's an issue... ")
        try:
            VIEWER.status = 'Saving ...'
            hdata.to_csv(OBJECT_DATA, index=False)
            VIEWER.status = f'Saved to file! Next {numcells} cells loaded.'
            return True
        except:
            # Maybe it's an excel sheet?
            VIEWER.status = 'There was a problem saving, so the next set of cells was not loaded. Close your data file?'
            return False
            # hdata.loc[:,1:].to_excel(
            # OBJECT_DATA,sheet_name='Exported from gallery viewer')
        VIEWER.status = 'Done saving!'
    # Take note of new starting point
    global CELL_ID_START, CELL_LIMIT, CELL_OFFSET
    if next_cell_rb.isChecked(): Direction = 'fwd'
    else: Direction = 'bkwd'
    Amount = amount_sp.value()
    print(f'\nDebug prints. Spinbox reads {Amount}, type {type(Amount)}')

    # Save data to file from current set
    if not _save_validation(VIEWER, Amount):
        print(f'Could not save...')
        return None
    
    # might not be necessary. Was put here in an attempt to avoid weird GUI element deletion glitch
    # Must come after attempting to save, otherwise widgets vanish when an error occurs...
    for widg in ALL_CUSTOM_WIDGETS.values():
        widg.setVisible(False)

    CELL_OFFSET = CELL_LIMIT 
    CELL_LIMIT = int(Amount)
    VIEWER.grid.shape = (CELL_LIMIT, len(CHANNELS)+1)
    # Load into same mode as the current
    if COMPOSITE_MODE:
        xydata = extract_phenotype_xldata(change_startID=True,direction=Direction)
        if xydata is False:
            VIEWER.status="Can't load cells: out of bounds error."
        else:
            VIEWER.layers.clear()
            add_layers(VIEWER,RAW_PYRAMID, xydata, int(PUNCHOUT_SIZE/2), composite_enabled=True)
    else:
        xydata = extract_phenotype_xldata(change_startID=True,direction=Direction)
        if xydata is False:
            VIEWER.status="Can't load cells: out of bounds error."
        else:
            VIEWER.layers.clear()
            add_layers(VIEWER,RAW_PYRAMID, xydata, int(PUNCHOUT_SIZE/2), composite_enabled=False)
        # Perform adjustments before exiting function
    reuse_contrast_limits()
    reuse_gamma() # might not need to do both of these... One is enough?
    set_viewer_to_neutral_zoom(VIEWER) # Fix zoomed out issue
    for widg in ALL_CUSTOM_WIDGETS.values():
        widg.setVisible(True)
    return None
    
# @magicgui(auto_call=True,
#         Status_Bar_Visibility={"widget_type": "RadioButtons","orientation": "vertical",
#         "choices": [("Show", 1), ("Hide", 2)]})
# def toggle_statusbar_visibility(Status_Bar_Visibility: int=1):
def toggle_statusbar_visibility(show_widget):
    if show_widget.isChecked(): Status_Bar_Visibility = 1
    else: Status_Bar_Visibility = 2
    # Find status layers and toggle visibility
    if Status_Bar_Visibility==1:
        for layer in VIEWER.layers:
            layername = layer.name
            if 'status' in layername:
                layer.visible = True
    elif Status_Bar_Visibility==2:
        for layer in VIEWER.layers:
            layername = layer.name
            if 'status' in layername:
                layer.visible = False
    else:
        raise Exception(f"Invalid parameter passed to toggle_statusbar_visibility: {Status_Bar_Visibility}. Must be 1 or 2.")
    return None

def sort_by_intensity():
    pass

def set_notes_label(display_note_widget, ID):
    try:
        note = str(SAVED_NOTES[ID])
    except KeyError: # in case the name was off
        return False
    prefix = f'CID: <font color="#f5551a">{ID}</font>'
    if note == '-' or note == '' or note is None: 
        note = prefix
    else:
        note = prefix +'<br>'+ f'<font size="5pt">{note}</font>'
    display_note_widget.setText(note)
    return True
######------------------------- Image loading and processing functions ---------------------######

#TODO consider combining numpy arrays before adding layers? So that we create ONE image, and have ONE layer
#   for the ctc cells. Gallery mode might end up being a pain for downstream.
#   Counterpoint - how to apply filters to only some channels if they are in same image?
#   Counterpoint to counterpoint - never get rid of numpy arrays and remake whole image as needed. 
def add_layers(viewer,pyramid, cells, offset, composite_enabled=COMPOSITE_MODE, new_batch=True):
    print(f'\n---------\n \n Entering the add_layers function')
    print(f"pyramid shape is {pyramid.shape}")
    # Make the color bar that appears to the left of the composite image
    status_colors = {"unseen":"gray", "needs review":"bop orange", "confirmed":"green", "rejected":"red" }

    # Choice depends on whether we want to be in composite only mode or not
    if not composite_enabled:
        viewer.grid.stride = 1
    else:
        viewer.grid.stride = 2

    def retrieve_status(cell_id, cell):
        ''' Kind of an anachronistic function at this point.'''
        # print(f'Getting status for {cell_id}')
        if new_batch:
            try:
                status = cell[3]
                # print(f'Got it. Status is .{status}.')
            except:
                # Column doesn't exist, use default
                status = "unseen"
                # print(f'exception. Could not grab status')
            if type(status) is not str or status not in status_colors.keys():
                status = "unseen"
            # Save to dict to make next retrieval faster
            STATUS_LIST[cell_id] = status
            return status
        else:
            return STATUS_LIST[cell_id]

    def generate_status_box(color):
        if color == 'red':
            color_tuple = (255,0,0,255)
        elif color == 'green':
            color_tuple = (0,255,0,255)
        elif color =='bop orange':
            color_tuple = (255,160,0,255)
        else: # assume 'gray'
            color_tuple = (150,150,150,255)

        corner_box_size = 8

        top_or_bottom = [color_tuple, ] *(PUNCHOUT_SIZE+1)
        x = np.array([[color_tuple, (0,0,0,0), color_tuple]])
        y = np.repeat(x,[1,PUNCHOUT_SIZE-1,1],axis=1)
        mid = np.repeat(y,PUNCHOUT_SIZE-(corner_box_size), axis=0)

        z = np.repeat(x,[corner_box_size,PUNCHOUT_SIZE-(corner_box_size),1],axis=1)
        above_mid = np.repeat(z,corner_box_size-1, axis=0)
        top = np.append([top_or_bottom],above_mid,axis=0)
        # z = np.repeat([np.repeat([0],12)],2,axis=0)
        xy = np.append(top,mid, axis=0)
        return np.append(xy,[top_or_bottom],axis=0)

    def add_status_bar(viewer, name, status = 'unseen'):
        if not composite_enabled:
            # Make a strip - will display at the left of each row of channels (one row per cell)
            x = np.array([[0,255,0]])
            y = np.repeat(x,[PUNCHOUT_SIZE-8,7,1],axis=1)
            overlay = np.repeat(y,PUNCHOUT_SIZE,axis=0)
            status_layer = viewer.add_image(overlay, name = f'{name}_{status}', colormap = status_colors[status])
        else:
            # Create a small box - will display in the top left corner above each composite image
            overlay = generate_status_box(status_colors[status])
            status_layer = viewer.add_image(overlay, name = f'{name}_{status}')#, colormap = status_colors[status])

        def find_mouse(shape_layer, pos):
            data_coordinates = shape_layer.world_to_data(pos)
            coords = np.round(data_coordinates).astype(int)
            val = None
            for img in VIEWER.layers:
                if img.name == 'Batch Name': continue
                data_coordinates = img.world_to_data(pos)
                val = img.get_value(data_coordinates)
                if val is not None:
                    shape_layer = img
                    break
            # val = shape_layer.get_value(data_coordinates)
            # print(f'val is {val} and type is {type(val)}')
            coords = np.round(data_coordinates).astype(int)
            return shape_layer, coords, val

        @status_layer.mouse_move_callbacks.append
        def display_intensity(shape_layer, event):
            
            shape_layer,coords,val = find_mouse(shape_layer, event.position) 
            set_notes_label(NOTES_WIDGET, shape_layer.name.split()[1])
            if val is None:
                # print('none')
                VIEWER.status = f'{shape_layer.name} intensity at {coords}: N/A'
            else:
                # print('else')
                VIEWER.status = f'{shape_layer.name} intensity at {coords}: {val}'

        def get_layer_name(shape_layer):
            # Find details for the layer under the mouse
            status_layer,coords,val = find_mouse(shape_layer, VIEWER.cursor.position) 
            # Find this layers corresponding status layer
            for candidate in VIEWER.layers:
                if candidate.name == 'Batch Name': continue
                cellnum = candidate.name.split()[1]
                if cellnum == status_layer.name.split()[1] and ('status' in candidate.name.split()[-1] or 'status' in candidate.name.split()[-2]):
                    status_layer = candidate
                    break
                else:
                    continue
            return status_layer.name,status_layer
            
        @status_layer.bind_key('Space')
        def toggle_status(shape_layer):
            name,status_layer = get_layer_name(shape_layer)
            # Rename the status layer and change the color
            if 'status' in name:
                cur_status = name.split('_')[1] 
                cur_index = list(status_colors.keys()).index(cur_status)
                next_status = list(status_colors.keys())[(cur_index+1)%len(status_colors)]
                print(f'next status (shape_layer) is {next_status}')
                status_layer.name = name.split('_')[0] +'_'+next_status
                if COMPOSITE_MODE: 
                    status_layer.data = generate_status_box(status_colors[next_status])
                else:
                    status_layer.colormap = status_colors[next_status]

            else:
                pass
        
        @status_layer.bind_key('c')
        def set_unseen(shape_layer):
            next_status = 'unseen'

            name,status_layer = get_layer_name(shape_layer)
            # Rename the status layer and change the color
            if 'status' in name:
                status_layer.name = name.split('_')[0] +'_'+next_status
                if COMPOSITE_MODE: 
                    status_layer.data = generate_status_box(status_colors[next_status])
                else:
                    status_layer.colormap = status_colors[next_status] 
            else:
                pass

        @status_layer.bind_key('v')
        def set_nr(shape_layer):
            next_status = 'needs review'

            name,status_layer = get_layer_name(shape_layer)
            # Rename the status layer and change the color
            if 'status' in name:
                status_layer.name = name.split('_')[0] +'_'+next_status 
                if COMPOSITE_MODE: 
                    status_layer.data = generate_status_box(status_colors[next_status])
                else:
                    status_layer.colormap = status_colors[next_status]
            else:
                pass
        @status_layer.bind_key('b')
        def set_confirmed(shape_layer):
            next_status = 'confirmed'

            name,status_layer = get_layer_name(shape_layer)
            # Rename the status layer and change the color
            if 'status' in name:
                status_layer.name = name.split('_')[0] +'_'+next_status
                if COMPOSITE_MODE: 
                    status_layer.data = generate_status_box(status_colors[next_status])
                else:
                    status_layer.colormap = status_colors[next_status]
            else:
                pass

        @status_layer.bind_key('n')
        def set_rejected(shape_layer):
            next_status = 'rejected'

            name,status_layer = get_layer_name(shape_layer)
            # Rename the status layer and change the color
            if 'status' in name:
                status_layer.name = name.split('_')[0] +'_'+next_status 
                if COMPOSITE_MODE: 
                    status_layer.data = generate_status_box(status_colors[next_status])
                else:
                    status_layer.colormap = status_colors[next_status]
            else:
                pass

    def add_layer(viewer, layer, name, colormap = None, contr = [0,255] ):

        #TODO Decide: here or later (After RGB color mapping?)
        # Store image data in global dict
        # IMAGE_DATA_STORE[name+CHANNEL_ORDER[cell_colors.index(colormap)]] = layer
        # IMAGE_DATA_STORE[name] = layer
        # if name not in IMAGE_DATA_STORE.keys():
        #     inner_dict = {} #initialize
        #     inner_dict[colormap] = layer
        #     IMAGE_DATA_STORE[name] = inner_dict
        # else:
        #     inner_dict[colormap] = layer

        # colors = np.linspace(
        #     start=[0, 0, 0, 1],
        #     stop=[1, 0, 1, 1],
        #     num=256,
        #     endpoint=True
        # )

        # new_colormap = {
        #     'colors': colors,
        #     'name': 'test_green',
        #     'interpolation': 'linear'
        # }

        # Napari bug: setting gamma here doesn't update what is seen, 
        # even thought the slider gui shows the change
        #   Will have to do something else.
        if colormap is not None: # Luminescence image
            shape_layer = viewer.add_image(layer, name = name, contrast_limits = contr)
            shape_layer.colormap = custom_maps.retrieve_cm(colormap)
        elif contr is not None: # RBG image
            print(f'\n ~~~ Adding RGB Image ~~~ \n')
            shape_layer = viewer.add_image(layer, name = name, contrast_limits = contr)
        else:
            print(f'\n ~~~ Adding RGB Image auto contrast limit ~~~ \n')
            shape_layer = viewer.add_image(layer, name = name, gamma = 0.5)

        def find_mouse(shape_layer, pos):
            data_coordinates = shape_layer.world_to_data(pos)
            coords = np.round(data_coordinates).astype(int)
            val = None
            for img in VIEWER.layers:
                if img.name == 'Batch Name': continue

                data_coordinates = img.world_to_data(pos)
                val = img.get_value(data_coordinates)
                if val is not None:
                    shape_layer = img
                    break
            # val = shape_layer.get_value(data_coordinates)
            # print(f'val is {val} and type is {type(val)}')
            coords = np.round(data_coordinates).astype(int)
            return shape_layer, coords, val

        @shape_layer.mouse_move_callbacks.append
        def display_intensity(shape_layer, event):
            
            shape_layer,coords,val = find_mouse(shape_layer, event.position) 
            set_notes_label(NOTES_WIDGET, shape_layer.name.split()[1])
            if val is None:
                # print('none')
                VIEWER.status = f'{shape_layer.name} intensity at {coords}: N/A'
            else:
                # print('else')
                VIEWER.status = f'{shape_layer.name} intensity at {coords}: {val}'

        def get_layer_name(shape_layer):
            # Find details for the layer under the mouse
            status_layer,coords,val = find_mouse(shape_layer, VIEWER.cursor.position) 
            # Find this layers corresponding status layer
            for candidate in VIEWER.layers:
                if candidate.name == 'Batch Name': continue

                cellnum = candidate.name.split()[1]
                if cellnum == status_layer.name.split()[1] and ('status' in candidate.name.split()[-1] or 'status' in candidate.name.split()[-2]):
                    status_layer = candidate
                    break
                else:
                    continue
            return status_layer.name,status_layer
            
        @shape_layer.bind_key('Space')
        def toggle_status(shape_layer):
            name,status_layer = get_layer_name(shape_layer)
            # Rename the status layer and change the color
            if 'status' in name:
                cur_status = name.split('_')[1] 
                cur_index = list(status_colors.keys()).index(cur_status)
                next_status = list(status_colors.keys())[(cur_index+1)%len(status_colors)]
                print(f'next status (shape_layer) is {next_status}')
                status_layer.name = name.split('_')[0] +'_'+next_status 
                if COMPOSITE_MODE: 
                    status_layer.data = generate_status_box(status_colors[next_status])
                else:
                    status_layer.colormap = status_colors[next_status]
            else:
                pass
        
        @shape_layer.bind_key('c')
        def set_unseen(shape_layer):
            next_status = 'unseen'

            name,status_layer = get_layer_name(shape_layer)
            # Rename the status layer and change the color
            if 'status' in name:
                status_layer.name = name.split('_')[0] +'_'+next_status 
                if COMPOSITE_MODE: 
                    status_layer.data = generate_status_box(status_colors[next_status])
                else:
                    status_layer.colormap = status_colors[next_status]
            else:
                pass

        @shape_layer.bind_key('v')
        def set_nr(shape_layer):
            next_status = 'needs review'

            name,status_layer = get_layer_name(shape_layer)
            # Rename the status layer and change the color
            if 'status' in name:
                status_layer.name = name.split('_')[0] +'_'+next_status 
                if COMPOSITE_MODE: 
                    status_layer.data = generate_status_box(status_colors[next_status])
                else:
                    status_layer.colormap = status_colors[next_status]
            else:
                pass
        @shape_layer.bind_key('b')
        def set_confirmed(shape_layer):
            next_status = 'confirmed'

            name,status_layer = get_layer_name(shape_layer)
            # Rename the status layer and change the color
            if 'status' in name:
                status_layer.name = name.split('_')[0] +'_'+next_status 
                if COMPOSITE_MODE: 
                    status_layer.data = generate_status_box(status_colors[next_status])
                else:
                    status_layer.colormap = status_colors[next_status]
            else:
                pass

        @shape_layer.bind_key('n')
        def set_rejected(shape_layer):
            next_status = 'rejected'

            name,status_layer = get_layer_name(shape_layer)
            # Rename the status layer and change the color
            if 'status' in name:
                status_layer.name = name.split('_')[0] +'_'+next_status 
                if COMPOSITE_MODE: 
                    status_layer.data = generate_status_box(status_colors[next_status])
                else:
                    status_layer.colormap = status_colors[next_status]
            else:
                pass

        return True
    # def add_layer_rgb(viewer, layer, name):
    #     viewer.add_image(layer, name = name, rgb=True)
    #     return True

    def _convert_to_rgb(data, colormap, divisor):
        # You have to do it like this. Seriously. 
        # print(f'CONVERTING to {colormap}... \n')
        global SC_DATA, TEMP
        SC_DATA = data / divisor
        # SC_DATA /= divisor
        loc = {}
        
        # exec(f'rgb = cm.{colormap}(norm(SC_DATA))', globals(), loc)
        exec(f'TEMP = cm.get_cmap("{colormap}")', globals())
        exec(f'rgb = TEMP(SC_DATA)', globals(), loc)
        return loc['rgb']
    
    print(f'Adding {len(cells)} cells to viewer... Channels are {CHANNELS} // {CHANNELS_STR}')
    while bool(cells): # coords left
        print(f'Next round of while. Still {len(cells)} cells left')
        cell = cells.pop(); cell_x = cell[0]; cell_y = cell[1]; cell_id = cell[2]; cell_status = retrieve_status(cell_id,cell)
        composite = []
        # add the rest of the layers to the viewer
        if RASTERS is not None:
            # Raster channels for qptiffs are saved as subdatasets of the opened raster object
            num_channels = len(RASTERS) 
        else:
            num_channels = pyramid.shape[2] # Data is [X,Y,C]
        for i in range(num_channels): # loop through channels
            if i in CHANNELS:
                # name cell layer
                #TODO this should REALLY be a dictionary lookup...
                if i==DAPI: fluor='DAPI'
                elif i==OPAL570: fluor='570'
                elif i==OPAL690: fluor='690' 
                elif i==OPAL480: fluor='480'
                elif i==OPAL620: fluor='620' 
                elif i==OPAL780: fluor='780'
                elif i==OPAL520: fluor='520'
                elif i==AF: continue #fluor='AF' 
                cell_name = f'Cell {cell_id} {fluor}'

                # Shortcut if we have seen the cell before and done the work
                if not composite_enabled and cell_name in IMAGE_DATA_ADJUSTED:
                    # Have to apply a 255 multiplier since it's saved with a range of 0-1 (used for the composite calculations)
                    add_layer(viewer,IMAGE_DATA_ADJUSTED[cell_name]*255, cell_name, colormap= cell_colors[i])
                    continue # go on to the next

                # print(f'Adding cell {cell_x},{cell_y} - layer {i}')
                # Save record of what colormap is chosen for what fluor. Useful for 
                #   altering the composite image later (white-in / black-in). 
                # This is dumb - do it somewhere else
                if cell_colors[i] == 'pink': cell_colors[i] = 'Pink'
                global fluor_to_color; fluor_to_color[fluor] = cell_colors[i]
                # print(f'Testing if raster used: {RASTERS}') # YES can see subdatasets.
                if RASTERS is not None:
                    with rasterio.open(RASTERS[i]) as channel:
                        cell_punchout_raw = channel.read(1,window=Window(cell_x-offset,cell_y-offset, offset*2,offset*2)).astype('float64')
                else:
                    cell_punchout_raw = pyramid[cell_x-offset:cell_x+offset,cell_y-offset:cell_y+offset,i].astype('float64')
                print(f'Trying to add {cell_name} layer with fluor-color(cm):{fluor}-{cell_colors[i]}')

                if not composite_enabled: # Only add channels if we are in 'show all' mode. Otherwise only composite will show up
                    add_layer(viewer,cell_punchout_raw, cell_name, colormap= cell_colors[i])
                
                # normalize to 1.0

                # print(f'My types are as follows: \n cell raw {cell_punchout_raw.dtype}\n min {type(cell_punchout_raw.min())}\n max {type(cell_punchout_raw.max())}')
                # should be floats now
                # Normalize to range of 0.0 , 1.0 BEFORE passing through color map

                # print(f' MIN / MAX output {np.min(cell_punchout_raw)} / {np.max(cell_punchout_raw)}')
                cell_punchout_raw = cell_punchout_raw #- cell_punchout_raw.min()
                cell_punchout_raw = cell_punchout_raw / 255.0 #cell_punchout_raw.max()

                # custom_map = vpc.get_colormap('single_hue',hue=40, saturation_range=[0.1,0.8], value=0.5)
                # cell_punchout = custom_map(cell_punchout_raw)*255
                # print(f'color chosen is |{cell_colors[i]}|')

                # print(f'len of channels is {len(CHANNELS)}')
                # STORING in global dicts
                #TODO should be pre-RGB mapping intensities so that white-in / black-in threshold
                #   can be properly applied. Need to copy that code again somewhere I guess

                cp_save = cell_punchout_raw 
                IMAGE_DATA_ORIGINAL[cell_name] = cp_save; IMAGE_DATA_ADJUSTED[cell_name] = cp_save

                # #TODO Gamma correct right here since there's a bug that doesn't allow passing to the viewer
                # cell_punchout_raw = np.asarray([x**0.5 for x in cell_punchout_raw])
                cell_punchout = _convert_to_rgb(cell_punchout_raw, cell_colors[i], divisor=1)#len(CHANNELS)-1) # subtract one bc it contains the composite


                # print(f'raw np shape is {cell_punchout_raw.shape}') # (100,100)
                # print(f'colormapped np shape is {cell_punchout.shape}') # (100,100,4)
                # composite = np.vstack([composite, cell_punchout]')
                composite.append([cell_punchout])

                if len(cells) == 5 and cell_colors[i] == 'Reds':
                    pass
                    # print(f'Colormapped shape is {cell_punchout.shape}')
                    # print(f'Colormapped RAW shape is {cell_punchout_raw.shape}')
                    # print(f' our min and max in the raw file is {np.min(cell_punchout_raw)} and {np.max(cell_punchout_raw)}')
                    # np.savetxt(r"C:\Users\prich\Desktop\Projects\MGH\CTC-Gallery-Viewer\data\cell_punch.txt", cell_punchout[:,:,0])
                    # np.savetxt(r"C:\Users\prich\Desktop\Projects\MGH\CTC-Gallery-Viewer\data\normed.txt", cm.Reds(norm(cell_punchout_raw))[:,:,0])
                    # np.savetxt(r"C:\Users\prich\Desktop\Projects\MGH\CTC-Gallery-Viewer\data\cell_punch_raw.txt", cell_punchout_raw)

                
                # Confirmation that values are 0-255
                # mymax = np.max(pyramid[cell_x-offset:cell_x+offset,cell_y-offset:cell_y+offset,i])
                # print(f'For cell number {cell_id}, channel {i}, the max value is {mymax}')
        # add composite
        cell_name = f'Cell {cell_id} Composite'
        if cell_name in IMAGE_DATA_ADJUSTED:
            add_layer(viewer, IMAGE_DATA_ADJUSTED[cell_name], cell_name, colormap=None) #!!! NEEDS TO BE AN INT ARRAY!
            add_status_bar(viewer, f'Cell {cell_id} status', cell_status)
            continue
        composite = np.asarray(composite)[:,0,:,:] # it's nested right now, so extract the values. Shape after this should be (#channels, pixelwidth, pixelheight, 4) 4 for rgba
        # print(f'shape before summing is {composite.shape}')
        # print(f'trying to pull out some rgba data: black {composite[0,45,45,:]}\n blue {composite[1,45,45,:]}\n red {composite[2,45,45,:]}')

        composite = np.sum(composite, axis=0)
        composite = np.clip(composite,0,np.max(composite)) # ensures 0-1 scaling 
        # print(f'\n!!! Shape after summing is {composite.shape}')
        # print(f'same pixel added: {composite [45,45,:]}')
        composite[:,:,3] = 1.0 # Restore Alpha value to 1.0 (possibly redundant)
        # print(f'same pixel averaged by 3: {composite [45,45,:]}')


        rgb_mins = [] ## Axis here?
        rgb_maxes = []
        for i in range(3):
            temp = np.ndarray.flatten(composite[:,:,i])
            # print(f'Shape of intermediate is {temp.shape}')
            rgb_mins.append(np.min(temp))
            rgb_maxes.append(np.max(temp))
        # print(f'Using axis {1}, here are the mins: {rgb_mins}')
        # print(f'Here are the maxes: {rgb_maxes}')

        # rgb_mins = np.amin(composite, axis=2) ## Axis here?
        # rgb_maxes = np.amax(composite, axis = 2)
        # print(f'\n \nUsing axis {2}, here are the mins: {rgb_mins}')
        # print(f'\n Here are the maxes: {rgb_maxes}')
        # for j in range(3):
        #     print(f'My j is {j}. 0 should be black channel, one is blue, 2 is red ')
        # print(f'\n \n Beginning the min/max normalization loop.')
        for i in range(3):
            # Map values back to normal range of 0, 255.0 before passing as RGB. Napari does a shitty job of displaying without this.
            # print(f'My i is {i}. RGB maps to 012 min/max is {rgb_mins[i]}/{rgb_maxes[i]}')
            # continue
            #TODO decide what to do here
            ##### try to colormap a 255 and use that as a max ... It's 1 

            composite[:,:,i] = composite[:,:,i] - float(rgb_mins[i])
                                                    #rgb_maxes[i]
            composite[:,:,i] = composite[:,:,i] /(float(1.0) - float(rgb_mins[i]))
            composite[:,:,i] = composite[:,:,i] * 255.0

            # composite[:,:,i] -= np.min(composite[:,:,i])
            # composite[:,:,i] *= 255.0/np.max(composite[:,:,i])
        # print(f'same pixel multiplied / normalized to 0,255 range: {composite [45,45,:]}')
        # print(f'For cell number {cell_id} the datatype is {composite.dtype}, max value is {np.max(composite[:,:,0])} and the min is {np.min(composite[:,:,0])}')
        # print(f'also the shape is {composite.shape}') # (100,100,4)
        
        IMAGE_DATA_ADJUSTED[cell_name] = composite.astype('int')
        add_layer(viewer, composite.astype('int'), cell_name, colormap=None) #!!! NEEDS TO BE AN INT ARRAY!
        add_status_bar(viewer, f'Cell {cell_id} status', cell_status)
        # if len(cells) == 5:
        #     np.savetxt(r"C:\Users\prich\Desktop\Projects\MGH\CTC-Gallery-Viewer\data\composite.txt", composite[:,:,0])
    
    #TODO make a batch label... 
    # add polygon (just for text label)
    # text = {'string': 'Batch name goes here', 'anchor': 'center', 'size': 8,'color': 'white'}
    # shapes_layer1 = viewer.add_shapes([[0,0], [40,0], [40,40],[0,40]], shape_type = 'polygon',
    #                 edge_color = 'green', face_color='transparent',text=text, name='Batch Name') 
    # shapes_layer2 = viewer.add_shapes([[0,0], [40,0], [40,40],[0,40]], shape_type = 'polygon',
    #                 edge_color = 'green', face_color='transparent',text=text, name='Batch Name') 

    return True

######------------------------- Misc + Viewer keybindings ---------------------######

#TODO make a button to do this as well?
def set_viewer_to_neutral_zoom(viewer):
    viewer.camera.center = (300,250) # these values seem to work best
    viewer.camera.zoom = 1.3


def add_custom_colors():
    for colormap in cell_colors:
        if colormap == 'gray': continue
        elif colormap =='pink': colormap='Pink'
        exec(f'my_map = custom_maps.create_{colormap}_lut()')
        exec(f'custom = mplcolors.LinearSegmentedColormap.from_list("{colormap}", my_map)')
        exec(f'cm.register_cmap(name = "{colormap}", cmap = custom)')
    return True

def sv_wrapper(viewer):
    @viewer.bind_key('s')
    def save_validation(viewer):
        print(f'reading from {OBJECT_DATA}')
        viewer.status = 'Saving ...'
        hdata = pd.read_csv(OBJECT_DATA)

        try:
            hdata.loc[2,"Validation"]
        except KeyError:
            hdata.insert(4,"Validation", "unseen")
            hdata.loc[hdata[PHENOTYPE]==0,"Validation"] = ""
        try:
            hdata.loc[2,"Notes"]
        except KeyError:
            hdata.insert(5,"Notes","-")
            hdata.fillna("")

        for layer in viewer.layers:
            if 'status' in layer.name:
                status = layer.name.split('_')[1]
                cell_id = layer.name.split()[1]
            else:
                continue
            
            print(f"LName: {layer.name} , status {status}, cid {cell_id}")
            try:
                hdata.loc[hdata["Object Id"]==int(cell_id),"Validation"] = status
                hdata.loc[hdata["Object Id"]==int(cell_id),"Notes"] = SAVED_NOTES[cell_id]
            except:
                print("There's an issue... ")
        try:
            hdata.to_csv(OBJECT_DATA, index=False)
            viewer.status = 'Done saving!'
            return None
        except:
            # Maybe it's an excel sheet?
            viewer.status = 'There was a problem. Close your data file?'
            return None
            # hdata.loc[:,1:].to_excel(
            # OBJECT_DATA,sheet_name='Exported from gallery viewer')
        viewer.status = 'Done saving!'

def tsv_wrapper(viewer):
    @viewer.bind_key('h')
    def toggle_statusbar_visibility(viewer):
        show_vis_radio = ALL_CUSTOM_WIDGETS['show visibility radio']
        hide_vis_radio = ALL_CUSTOM_WIDGETS['hide visibility radio']
        if show_vis_radio.isChecked():
            show_vis_radio.setChecked(False)
            hide_vis_radio.setChecked(True)
        else:
            show_vis_radio.setChecked(True)
            hide_vis_radio.setChecked(False)

def chn_key_wrapper(viewer):
    def create_fun(position,channel):
        @viewer.bind_key(str(position+1))
        def toggle_channel_visibility(viewer,pos=position,chn=channel):
            widget_name = chn+'_box'
            # print(f'You are trying to toggle {widget_name} with pos {pos}')
            widget_obj = globals()[widget_name]
            if widget_obj.check.value:
                widget_obj.check.value =False
            else:
                widget_obj.check.value=True
        return toggle_channel_visibility

    for pos, chn in enumerate(CHANNELS_STR):
        binding_func_name = f'{chn}_box_func'
        exec(f'globals()["{binding_func_name}"] = create_fun({pos},"{chn}")')
        

def set_initial_adjustment_parameters():
    for fluor in CHANNELS_STR:
        fluor = fluor.lstrip("OPAL")
        ADJUSTMENT_SETTINGS[fluor+ ' black-in']=0
        ADJUSTMENT_SETTINGS[fluor+ ' white-in']=255
        ADJUSTMENT_SETTINGS[fluor+ ' gamma']= 1.0

def fetch_notes(cell_set):
    '''Grab notes for each cell in the list and save to global dict'''
    for index,row in cell_set.iterrows():
        ID = str(row['Object Id'])
        SAVED_NOTES[ID] = row['Notes']
    print(f'dumping dict {SAVED_NOTES}')

'''Get object data from csv and parse.''' 
def extract_phenotype_xldata(change_startID = False ,direction = 'fwd', new_batch = True, cell_id_start=None, cell_limit=None, phenotype=None):
    
    sort_by_intensity = None# 'OPAL520' # None means 'don't do it', while a channel name means 'put highest at the top'
    if sort_by_intensity is not None:
        sort_by_intensity = sort_by_intensity.replace('OPAL','Opal ') + ' Cell Intensity'

    # get defaults from global space
    global CELL_ID_START
    if cell_id_start is None: cell_id_start = CELL_ID_START # ID of first cell in the set (smallest) 
    if cell_limit is None: cell_limit=CELL_LIMIT # Number of cells to be shown
    if phenotype is None: phenotype=PHENOTYPE # Name of phenotype of interest
    # Also using CELL_OFFSET to know how big the current set size is
    print(f'ORDERING PARAMS: id start: {cell_id_start}, limit: {cell_limit}, direction: {direction}, change?: {change_startID}')
    halo_export = pd.read_csv(OBJECT_DATA)

    # Add columns w/defaults if they aren't there to avoid runtime issues
    try:
        halo_export.loc[2,"Validation"]
    except KeyError:
        halo_export.insert(4,"Validation", "unseen")
        halo_export.loc[halo_export[PHENOTYPE]==0,"Validation"] = ""
    try:
        halo_export.loc[2,"Notes"]
    except KeyError:
        halo_export.insert(5,"Notes","-")
        halo_export.fillna("")
    try:
        halo_export.to_csv(OBJECT_DATA, index=False)
    except:
        pass

    # Get relevant columns
    all_possible_intensities = ['DAPI Cell Intensity', 'Opal 480 Cell Intensity','Opal 520 Cell Intensity',
            'Opal 570 Cell Intensity', 'Opal 620 Cell Intensity', 'Opal 690 Cell Intensity','Opal 780 Cell Intensity',
            'AF Cell Intensity','Autofluorescence Cell Intensity'] # not sure what the correct nomenclature is here
    cols_to_keep = ["Object Id","Validation","Notes", "XMin","XMax","YMin", "YMax", phenotype] + all_possible_intensities
    cols_to_keep = halo_export.columns.intersection(cols_to_keep)
    halo_export = halo_export.loc[:, cols_to_keep]
    
    if cell_id_start < len(halo_export) and cell_id_start > 0:
        if direction =='fwd':     
            cell_set = halo_export[cell_id_start:] # Exclude cells prior to target ID
            cell_set = cell_set[cell_set[phenotype]==1]
            if CELL_OFFSET > len(cell_set.index):
                return False
            new_CID = int(cell_set.iloc[CELL_OFFSET]['Object Id'])
        elif direction=='bkwd':
            # In this case we have a negative offset, meaning we want to check out cells with
            #   a target ID of LESS than the start ID
            # Use cell_limit here, NOT CELL_OFFSET because we want to use the new set size to determine the smallest ID  
            cell_set = halo_export[:cell_id_start]
            cell_set = cell_set[cell_set[phenotype]==1]
            if cell_limit > len(cell_set.index):
                return False
            new_CID = int(cell_set.iloc[len(cell_set.index)-cell_limit]['Object Id'])
        else:
            raise Exception(f"Invalid parameter 'direction' in extract_phenotype_xldata: {direction}. Expecting 'fwd' or 'bkwd'")

    if change_startID:
        CELL_ID_START = new_CID
        print(f'\nThe new CID you requested is {new_CID}\n')

        cell_set = halo_export[new_CID:]
        cell_set = cell_set[cell_set[phenotype]==1] # pare down cell list (now containing only phenotype of interest) to desired length
        if cell_limit < len(cell_set.index) and cell_limit > 0: 
            cell_set = cell_set[:cell_limit]
    else:
        # Likely changing composite modes, so don't do any manipulations
        cell_set = cell_set[:cell_limit]
    
    if sort_by_intensity is not None:
        cell_set = cell_set.sort_values(by = sort_by_intensity, ascending = False, kind = 'mergesort')
    fetch_notes(cell_set)

    tumor_cell_XYs = []
    for index,row in cell_set.iterrows():
        center_x = int((row['XMax']+row['XMin'])/2)
        center_y = int((row['YMax']+row['YMin'])/2)
        tumor_cell_XYs.append([center_x, center_y, row["Object Id"], row["Validation"]])
    global XY_STORE
    XY_STORE = copy.copy(tumor_cell_XYs)
    return tumor_cell_XYs

def replace_note(cell_widget, note_widget):
    global SAVED_NOTES
    cellID = cell_widget.text(); note = note_widget.text()
    try: 
        cellID = int(cellID)
    except ValueError:
        VIEWER.status = 'Error recording note: non-numeric Cell Id given'
        return None 
    try:
        SAVED_NOTES[str(cellID)] # to trigger exception
        SAVED_NOTES[str(cellID)] = note
        cell_widget.clear(); note_widget.clear()
        VIEWER.status = "Note recorded! Press 's' to save to file."
    except KeyError as e:
        print(f'\n{e}\n')
        VIEWER.status = 'Error recording note: Cell Id not found in list'

######------------------------- Remote Execution + Main ---------------------######

''' Reset globals and proceed to main '''
def GUI_execute(preprocess_class):
    userInfo = preprocess_class.userInfo ; status_label = preprocess_class.status_label
    global cell_colors, qptiff, PUNCHOUT_SIZE, CELL_LIMIT, CHANNELS_STR, CHANNEL_ORDER
    global CHANNELS, ADJUSTED, OBJECT_DATA, PHENOTYPE, CELL_ID_START

    cell_colors = userInfo.cell_colors
    qptiff = userInfo.qptiff
    PUNCHOUT_SIZE = userInfo.imageSize
    PHENOTYPE = userInfo.phenotype
    CELL_ID_START = userInfo.cell_ID_start
    CELL_LIMIT = userInfo.cell_count
    OBJECT_DATA = userInfo.objectData
    CHANNELS_STR = userInfo.channels
    if "Composite" not in CHANNELS_STR: CHANNELS_STR.append("Composite")
    CHANNEL_ORDER = userInfo.channelOrder
    if "Composite" not in CHANNEL_ORDER: CHANNEL_ORDER.append("Composite")
    CHANNELS = []
    for pos,chn in enumerate(CHANNEL_ORDER):
        # print(f'enumerating {chn} and {pos} for {CHANNELS_STR}')
        exec(f"globals()['{chn}'] = {pos}") # Important to do this for ALL channels
        if chn in CHANNELS_STR:
            # print(f'IF triggered with {chn} and {pos}')
            exec(f"globals()['CHANNELS'].append({chn})")
    # print(f'GUI execute channels are {CHANNELS}')
    ADJUSTED = copy.copy(CHANNELS)

    # fix_default_composite_adj()

    # for checkbox_name in CHANNELS_STR:   
    #     print(f'checkbox name is {checkbox_name} and type is {type(checkbox_name)}')
    #     exec(f"globals()[\'{checkbox_name+'_box'}\'].show()") # If doing this is wrong I don't want to be right
    main(preprocess_class)

def main(preprocess_class = None):
    #TODO do this in a function because this is ugly
    # Status update helper
    def _update_status(status):
        if preprocess_class is not None:
            preprocess_class.status_label.setText(status)
            preprocess_class.app.processEvents()
    global RAW_PYRAMID, RASTERS, VIEWER,NOTES_WIDGET, ALL_CUSTOM_WIDGETS
    if preprocess_class is not None: preprocess_class.status_label.setVisible(True)
    status = "Loading image as raster..."
    _update_status(status)

    start_time = time.time()

    print(f'\nLoading pyramid from {qptiff}...\n')
    try:
        print("Try using rasterio first.")
        with rasterio.open(qptiff) as src:
            pyramid = src
            raw_subdata = copy.copy(src.subdatasets)
        # Remove overview pic and label pic from subdataset. Some other crap at the end too?  
        #   They happen to be in the middle of the set, and aren't really well labelled.
        to_remove = []
        for i,sds in enumerate(raw_subdata):
            # These are the IDS of the crap data.
            if sds.lstrip('GTIFF_DIR:').startswith('50') or sds.lstrip('GTIFF_DIR:').startswith('51') or sds.lstrip('GTIFF_DIR:').startswith('9'):  
                to_remove.append(sds)  
        for sds in to_remove:
            raw_subdata.remove(sds)
        RASTERS = raw_subdata

        status+='<font color="#7dbc39">  Done.</font><br> Parsing object data...'
        _update_status(status)
    except:
        status+='<font color="#f5551a">  Failed.</font><br> Attempting to load memory-mapped object...'
        _update_status(status)
        try:
            pyramid = tifffile.memmap(qptiff)
            status+='<font color="#7dbc39">  Done.</font><br> Parsing object data...'
            _update_status(status)
        except:
            status+='<font color="#f5551a">  Failed.</font><br> Attempting to load raw image, this will take a while ...'
            _update_status(status)
            try:
                pyramid = tifffile.imread(qptiff) # print(f'\nFinal pyramid levels: {[p.shape for p in pyramid]}\n')
                # Find location of channels in np array. Save that value, and subset the rest (one nparray per channel)
                print(f'pyramid array as np array shape is {pyramid.shape}\n')
                arr = np.array(pyramid.shape)
                channels = min(arr)
                channel_index = np.where(arr == channels)[0][0]
                # have to grab the first to instantiate napari viewer
                if channel_index == 0:
                    # Added this because the high quality layer of my sample QPTIFF data seemed to be flipped
                    # i.e. array looks like (channels, y, x)
                    pyramid = np.transpose(pyramid,(2,1,0))
                    # firstLayer = pyramid[:,:,0]
                else:
                    pass #firstLayer = pyramid[:,:,0]
                status+='<font color="#7dbc39">  Done.</font><br> Parsing object data...'
                _update_status(status)
            except:
                status+='<font color="#f5551a">  Failed.</font><br> Aborting startup, please contact Peter.'
                _update_status(status)
                raise Exception("There was a problem reading the image data. Expecting a regular or memory-mapped tif/qptiff. Got something else.")
    finally:
        end_time = time.time()
        print(f'... completed in {end_time-start_time} seconds')

    # #TODO think of something better than this. It tanks RAM usage to store this thing
    # #       Literally  ~ 10GB difference
    
    RAW_PYRAMID=pyramid
    
    tumor_cell_XYs = extract_phenotype_xldata()
    status+='<font color="#7dbc39">  Done.</font><br> Initializing Napari session...'
    _update_status(status)

    set_initial_adjustment_parameters() # set defaults: 1.0 gamma, 0 black in, 255 white in
    
    viewer = napari.Viewer(title='CTC Gallery')
    VIEWER = viewer
    NOTES_WIDGET = QLabel('Placeholder note'); NOTES_WIDGET.setAlignment(Qt.AlignCenter)
    print(f'Notes widget is {NOTES_WIDGET}\n type is {type(NOTES_WIDGET)}')
    add_layers(viewer,pyramid,tumor_cell_XYs, int(PUNCHOUT_SIZE/2))
        # Perform adjustments before exiting function
    reuse_contrast_limits()
    reuse_gamma() # might not need to do both of these... One is enough?
    viewer.grid.enabled = True
    viewer.grid.shape = (CELL_LIMIT, len(CHANNELS)+1) # +1 because of the status layer.

    #TODO arrange these more neatly
    #TODO these dock widgets cause VERY strange behavior when trying to clear all layers / load more
    note_text_entry = QLineEdit()
    note_cell_entry = QLineEdit()
    note_button = QPushButton("Replace note for cell")
    note_text_entry.setPlaceholderText('Enter new note')
    note_text_entry.setFixedWidth(200)
    note_cell_entry.setPlaceholderText("Cell Id")
    note_cell_entry.setFixedWidth(100)
    # Pass pointer to widgets to function on button press
    note_button.pressed.connect(lambda: replace_note(note_cell_entry, note_text_entry))

    next_cell_rb = QRadioButton("Next") ; next_cell_rb.setChecked(True)
    previous_cell_rb = QRadioButton("Previous")
    batch_group = QButtonGroup(); batch_group.addButton(next_cell_rb); batch_group.addButton(previous_cell_rb)
    next_batch_amt = QSpinBox(); next_batch_amt.setRange(5,150); next_batch_amt.setValue(15)
    next_batch_button = QPushButton("Go")
    next_batch_button.pressed.connect(lambda: show_next_cell_group(next_cell_rb, previous_cell_rb, next_batch_amt))
    notes_container = viewer.window.add_dock_widget([NOTES_WIDGET,note_text_entry, note_cell_entry, note_button], name = 'Take notes', area = 'right')
    batch_container = viewer.window.add_dock_widget([next_cell_rb,previous_cell_rb, next_batch_amt, next_batch_button], name = 'Change Batch', area = 'right')

    all_channels_rb = QRadioButton("Show All Channels")
    composite_only_rb = QRadioButton("Composite Mode"); composite_only_rb.setChecked(True) # Start in composite mode
    comp_group = QButtonGroup(); comp_group.addButton(composite_only_rb); comp_group.addButton(all_channels_rb)
    switch_mode_button = QPushButton("Change Mode")
    switch_mode_button.pressed.connect(lambda: toggle_composite_viewstatus(all_channels_rb,composite_only_rb))
    mode_container = viewer.window.add_dock_widget([all_channels_rb,composite_only_rb,switch_mode_button],name ="Mode",area="right")
    
    visibility_show = QRadioButton("Show label overlay"); visibility_show.setChecked(True)
    visibility_hide = QRadioButton("Hide label overlay"); visibility_hide.setChecked(False)
    vis_group = QButtonGroup(); vis_group.addButton(visibility_show);vis_group.addButton(visibility_hide)
    visibility_hide.toggled.connect(lambda: toggle_statusbar_visibility(visibility_show))
    visibility_show.toggled.connect(lambda: toggle_statusbar_visibility(visibility_show))
    vis_container = viewer.window.add_dock_widget([visibility_show,visibility_hide],name ="Label Opacity",area="right")

    viewer.window.add_dock_widget(adjust_gamma_widget, area = 'bottom')
    viewer.window.add_dock_widget(adjust_whitein, area = 'bottom')
    viewer.window.add_dock_widget(adjust_blackin, area = 'bottom')
    # viewer.window.add_dock_widget(toggle_composite_viewstatus,name = 'Test', area = 'right')
    # viewer.window.add_dock_widget(show_next_cell_group,name = 'Test2', area = 'right')
    # viewer.window.add_dock_widget(toggle_statusbar_visibility,name = 'Test3', area = 'right')
    # print(f'\n {dir()}') # prints out the namespace variables 
    ALL_CUSTOM_WIDGETS['notes label']=NOTES_WIDGET; ALL_CUSTOM_WIDGETS['notes text entry']=note_text_entry
    ALL_CUSTOM_WIDGETS['notes cell entry']= note_cell_entry;ALL_CUSTOM_WIDGETS['notes button']=note_button
    ALL_CUSTOM_WIDGETS['next cell radio']=next_cell_rb;ALL_CUSTOM_WIDGETS['previous cell radio']=previous_cell_rb
    ALL_CUSTOM_WIDGETS['next batch amount']=next_batch_amt;ALL_CUSTOM_WIDGETS['next batch button']=next_batch_button
    ALL_CUSTOM_WIDGETS['channels mode radio']=all_channels_rb; ALL_CUSTOM_WIDGETS['composite mode radio']=composite_only_rb
    ALL_CUSTOM_WIDGETS['switch mode buton']=switch_mode_button; 
    ALL_CUSTOM_WIDGETS['show visibility radio']=visibility_show; ALL_CUSTOM_WIDGETS['hide visibility radio']=visibility_hide
    notes_container.setSizePolicy(QSizePolicy.MinimumExpanding,QSizePolicy.MinimumExpanding)
    batch_container.setSizePolicy(QSizePolicy.MinimumExpanding,QSizePolicy.MinimumExpanding)
    mode_container.setSizePolicy(QSizePolicy.MinimumExpanding,QSizePolicy.MinimumExpanding)
    vis_container.setSizePolicy(QSizePolicy.MinimumExpanding,QSizePolicy.MinimumExpanding)

    # for widg in ALL_CUSTOM_WIDGETS.values():
    #     widg.setSizePolicy(QSizePolicy.MinimumExpanding,QSizePolicy.MinimumExpanding)

    # Get rid of the crap on the left sidebar for a cleaner screen
    viewer.window._qt_viewer.dockLayerList.toggleViewAction().trigger()
    viewer.window._qt_viewer.dockLayerControls.toggleViewAction().trigger()

    print('Before')
    print(type(viewer.window))

    all_boxes = []
    for marker_function in CHANNELS_STR:
        # Only make visible the chosen markers
        all_boxes.append(globals()[f'{marker_function}_box'])
        # exec(f"viewer.window.add_dock_widget({marker_function+'_box'}, area='bottom')")

    status+='<font color="#7dbc39">  Done.</font><br> Goodbye' ;_update_status(status)
    sv_wrapper(viewer)
    tsv_wrapper(viewer)
    chn_key_wrapper(viewer)
    print('After')
    print(type(viewer.window))
    viewer.grid.stride = 2 # start in composite mode
    set_viewer_to_neutral_zoom(viewer) # Fix zoomed out issue

    viewer.window.add_dock_widget(all_boxes,area='bottom')
    if preprocess_class is not None: preprocess_class.close() # close other window
    napari.run()
    # close image file
    if RASTERS is not None:
        print('Not sure if we have to close this file... the "with" statement should handle it.')
        RAW_PYRAMID.close()
# Main should work now using the defaults specified at the top of this script in the global variable space
if __name__ == '__main__':
    main()
