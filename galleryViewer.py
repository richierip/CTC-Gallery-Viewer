'''
CTC viewer for Napari
Started on 6/7/22
Peter Richieri
'''

# import IPython
import tifffile
import rasterio
from rasterio.windows import Window
import napari
from napari.types import ImageData
from magicgui import magicgui #, magic_factory
from PyQt5.QtWidgets import QLabel, QLineEdit, QPushButton, QRadioButton, QCheckBox, QButtonGroup, QSizePolicy, QComboBox
from PyQt5.QtCore import Qt
import numpy as np
import pandas as pd
import openpyxl # necessary, do not remove
from matplotlib import cm # necessary, do not remove
from matplotlib import colors as mplcolors # Necessary, do not remove
import copy
import time
import store_and_load
import custom_maps # Necessary, do not remove
from math import ceil
from PIL import Image, ImageFont, ImageDraw

######-------------------- Globals, will be loaded through pre-processing QT gui #TODO -------------######
QPTIFF_LAYER_TO_RIP = 0 # 0 is high quality. Can use 1 for testing (BF only, loads faster)
cell_colors = store_and_load.CELL_COLORS
print('\n--------------- adding custom cmaps\n')

for colormap in cell_colors:
    # print(f'cmap: {colormap}')
    if colormap == 'gray': continue
    if colormap == 'pink': colormap = 'Pink'
    exec(f'my_map = custom_maps.create_{colormap}_lut()')
    exec(f'custom = mplcolors.LinearSegmentedColormap.from_list("{colormap}", my_map)')
    exec(f'cm.register_cmap(name = "{colormap}", cmap = custom)')
# print(f'\n---------My colormaps are now {plt.colormaps()}--------\n')

cell_colors = ['blue', 'purple' , 'red', 'green', 'orange','red', 'green', 'Pink', 'cyan'] # for local execution
CHANNEL_ORDER = {}
qptiff = r"C:\Users\prich\Desktop\Projects\MGH\CTC_Example\Exp02a01_02_Scan1.qptiff"
OBJECT_DATA = r"C:\Users\prich\Desktop\Projects\MGH\CTC_Example\ctc_example_data.csv"
# OBJECT_DATA = r"N:\CNY_Polaris\2021-11(Nov)\Haber Lab\Leukopak_Liver_NegDep_Slide1\Scan1\PMR_test_Results.csv"
PUNCHOUT_SIZE = 90 # microns or pixels? Probably pixels
PAGE_SIZE = 15 # How many cells will be shown in next page
CELLS_PER_ROW = 8
SPECIFIC_CELL = None # Will be an int if the user wants to load the page with that cell
PHENOTYPE = 'Tumor' #'CTC 488pos'
GLOBAL_SORT = None
DAPI = 0; OPAL480 = 3; OPAL520 = 6; OPAL570 = 1; OPAL620 = 4; OPAL690 = 2; OPAL780 = 5; AF=7; Composite = 8

userInfo = store_and_load.loadObject('data/presets')

# CHANNELS = [DAPI, OPAL480, OPAL520, OPAL570, OPAL620, OPAL690,OPAL780,AF,Composite] # Default. Not really that useful info since channel order was added.
CHANNELS = [DAPI, OPAL520,OPAL690, Composite] # for local execution / debugging
CHANNEL_ORDER = {'DAPI':'blue', 'OPAL570':'blue', 'OPAL690':'blue', 'OPAL480':'blue', 'OPAL620':'blue', 
                 'OPAL780':'blue', 'OPAL520':'blue', 'AF':'blue', 'Composite':'None'} # to save variable position data for channels (they can be in any order...)
CHANNELS_STR = list(userInfo.channelOrder.keys()) #["DAPI", "OPAL520", "OPAL690", "Composite"] # for local execution / debugging
CHANNELS_STR.append("Composite") # Seems like this has to happen on a separate line
ADJUSTED = copy.copy(CHANNELS_STR)
VIEWER = None
SC_DATA = None # Using this to store data to coerce the exec function into doing what I want
TEMP = None
ADJUSTMENT_SETTINGS={"DAPI gamma": 0.5}; 
SAVED_NOTES={} ; STATUS_LIST={}; SAVED_INTENSITIES={}; XY_STORE = [1,2,3]
RAW_PYRAMID=None
NOTES_WIDGET = None; ALL_CUSTOM_WIDGETS = {}
COMPOSITE_MODE = True # Start in composite mode
RASTERS = None
NO_LABEL_BOX = False
GRID_TO_ID = {}
STATUS_COLORS = {"Unseen":"gray", "Needs review":"bop orange", "Confirmed":"green", "Rejected":"red" }
STATUS_TO_HEX = {'Confirmed':'#00ff00', 'Rejected':'#ff0000', 'Needs review':'#ffa000', "Unseen":'#ffffff'}
IMAGE_LAYERS = {}
UPDATED_CHECKBOXES = []

######------------------------- MagicGUI Widgets, Functions, and accessories ---------------------######
#TODO merge some of the GUI elements into the same container to prevent strange spacing issues

def validate_adjustment(chn): # grab last part of label
    if chn in ADJUSTED:
        return True
    else:
        return False

# @magicgui(auto_call=True,
#             datapoint={"label":"N/A"})
# def show_intensity(datapoint: str):
#     datapoint = str(VIEWER.Layers.Image.get_value() )
#     show_intensity.show()

## --- Composite functions 
def adjust_composite_gamma(layer, gamma):
    # print(f'\nin fuxn adjustment settings are {ADJUSTMENT_SETTINGS}')
    # print(f'My datatype is {type(ADJUSTMENT_SETTINGS["DAPI gamma"])} while my value is {ADJUSTMENT_SETTINGS["DAPI gamma"]} and the value of\
    #       gamma is {gamma} and the image current gamma for {layer.name} is {layer.gamma}')
    layer.gamma = gamma
    # print(f'The new gamma is now {layer.gamma}')

def adjust_composite_limits(layer, limits):
    layer.contrast_limits = limits

def reuse_gamma():
    # print(f'\nREUSE adjustment settings are {ADJUSTMENT_SETTINGS}')
    for fluor in ADJUSTED:
        if fluor == 'Composite':
            continue
        adjust_composite_gamma(IMAGE_LAYERS[fluor],ADJUSTMENT_SETTINGS[fluor+" gamma"])

def reuse_contrast_limits():
    for fluor in ADJUSTED:
        if fluor == 'Composite':
            continue
        adjust_composite_limits(IMAGE_LAYERS[fluor], [ADJUSTMENT_SETTINGS[fluor+" black-in"],ADJUSTMENT_SETTINGS[fluor+" white-in"]])

## --- Bottom bar functions and GUI elements 

@magicgui(auto_call=True,
        Gamma={"widget_type": "FloatSlider", "max":1.0, "min":0.01},
        layout = 'horizontal')
def adjust_gamma_widget(Gamma: float = 0.5) -> ImageData: 
    def _update_dictionary(name, val):
        global ADJUSTMENT_SETTINGS
        ADJUSTMENT_SETTINGS[name+' gamma'] = val
    for fluor in ADJUSTED:
        if fluor == 'Composite':
            continue
        _update_dictionary(fluor,Gamma)
        adjust_composite_gamma(IMAGE_LAYERS[fluor],Gamma)
adjust_gamma_widget.visible=False

@magicgui(auto_call=True,
        white_in={"widget_type": "FloatSlider", "max":255,"min":1.0, "label": "White-in"},
        layout = 'horizontal')
def adjust_whitein(white_in: float = 255) -> ImageData:
    def _update_dictionary(name, val):
        global ADJUSTMENT_SETTINGS
        ADJUSTMENT_SETTINGS[name+' white-in'] = val
    for fluor in ADJUSTED:
        if fluor == 'Composite':
            continue
        _update_dictionary(fluor,white_in)
        adjust_composite_limits(IMAGE_LAYERS[fluor], [ADJUSTMENT_SETTINGS[fluor+" black-in"],white_in])

@magicgui(auto_call=True,
        black_in={"widget_type": "FloatSlider", "max":255, "label":"Black-in"},
        layout = 'horizontal')
def adjust_blackin(black_in: float = 0) -> ImageData:
    def _update_dictionary(name, val):
        global ADJUSTMENT_SETTINGS
        ADJUSTMENT_SETTINGS[name+' black-in'] = val
    
    for fluor in ADJUSTED:
        if fluor == 'Composite':
            continue
        _update_dictionary(fluor,black_in)
        adjust_composite_limits(IMAGE_LAYERS[fluor], [black_in,ADJUSTMENT_SETTINGS[fluor+" white-in"]])

def tally_checked_widgets():
    # keep track of visible channels in global list and then toggle layer visibility
    global ADJUSTED
    ADJUSTED = []
    for checkbox in UPDATED_CHECKBOXES:
        check = checkbox.isChecked()
        checkbox_name = checkbox.objectName()
    # print(f"{checkbox_name} has been clicked and will try to remove from {ADJUSTED}")
        if check:
            ADJUSTED.append(str(checkbox_name))

    # Make visible all channels according to rules
    for fluor in CHANNELS_STR:
        if fluor == "Composite":
            continue
        if "Composite" in ADJUSTED or fluor in ADJUSTED:
            IMAGE_LAYERS[fluor].visible = True
        else:
            IMAGE_LAYERS[fluor].visible = False  
    # return myfunc

def check_creator2(list_of_names):
    all_boxes = []
    for name in list_of_names:
        print(f"Creating checkbox {name}")
        cb = QCheckBox(name); cb.setObjectName(name)
        cb.setChecked(True)
        # cb.setStyleSheet("QCheckBox { color: blue }")
        all_boxes.append(cb)
        # f = dynamic_checkbox_creator()
        cb.toggled.connect(tally_checked_widgets)
    return all_boxes

all_boxes = check_creator2(CHANNELS_STR)

# This is called in GUI_execute, because the global 'ADJUSTED' variable will be changed at that time. 
# We want to make sure that the backend bookkeeping is congruent with the front-end checkbox, which is 
#   unchecked by now.  
def fix_default_composite_adj():
    global ADJUSTED
    ADJUSTED = list(filter(lambda a: a != "Composite", ADJUSTED))

## --- Side bar functions and GUI elements 

### --- 
# @magicgui(call_button='Change Mode',
#         Mode={"widget_type": "RadioButtons","orientation": "vertical",
#         "choices": [("Multichannel Mode", 1), ("Composite Mode", 2)]})#,layout = 'horizontal')
def toggle_composite_viewstatus(all_channels_rb,composite_only_rb):
    def _save_validation(VIEWER, Mode):
        print(f'reading from {OBJECT_DATA}')
        hdata = pd.read_csv(OBJECT_DATA)
        try:
            hdata.loc[2,f"Validation - {PHENOTYPE} - Unseen"]
        except KeyError:
            for call_type in reversed(STATUS_COLORS.keys()):
                if call_type == 'Unseen':
                    hdata.insert(8,f"Validation - {PHENOTYPE} - {call_type}", 1)
                else:
                    hdata.insert(8,f"Validation - {PHENOTYPE} - {call_type}", 0) 
        try:
            hdata.loc[2,"Notes"]
        except KeyError:
            hdata.insert(8,"Notes","-")
            hdata.fillna("")
        global XY_STORE, STATUS_LIST
        for cell_id in STATUS_LIST.keys():
            status = STATUS_LIST[cell_id]
            
            try:
                # reset all validation cols to zero before assigning a 1 to the appropriate status col
                for call_type in STATUS_COLORS.keys():
                    hdata.loc[hdata["Object Id"]==int(cell_id),f"Validation - {PHENOTYPE} - {call_type}"] = 0
                hdata.loc[hdata["Object Id"]==int(cell_id),f"Validation - {PHENOTYPE} - {status}"] = 1
                hdata.loc[hdata["Object Id"]==int(cell_id),"Notes"] = SAVED_NOTES[str(cell_id)]
            except:
                print("There's an issue... ")
            # Now do it for the saved cache
            try:
                for i,row in enumerate(XY_STORE):
                    if str(row[2]) == cell_id: 
                        XY_STORE[i][3] = status # I don't think this value will be shown but it's not hurting anyone here, just in case.
                        STATUS_LIST[str(cell_id)] = status
            except:
                print("XY_Store saving issue.")
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
    # print(f'Mode {Mode} and Composite? {COMPOSITE_MODE}')
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
        VIEWER.layers.clear()
        # data = extract_phenotype_xldata() # Don't need this since it is saved now
        add_layers(VIEWER,RAW_PYRAMID, copy.copy(XY_STORE), int(PUNCHOUT_SIZE/2), composite_only=False, new_page=False)
    elif Mode ==2: # change to composite only
        COMPOSITE_MODE = True
        print(f'\nAttempting to clear')
        VIEWER.layers.clear()
        #data = extract_phenotype_xldata() # Don't need this since it is saved now
        add_layers(VIEWER,RAW_PYRAMID, copy.copy(XY_STORE), int(PUNCHOUT_SIZE/2), composite_only=True, new_page=False)
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
def show_next_cell_group(page_cb_widget, single_cell_lineEdit, intensity_sort_widget):
    def _save_validation(VIEWER,numcells):
        print(f'reading from {OBJECT_DATA}')
        hdata = pd.read_csv(OBJECT_DATA)
        try:
            hdata.loc[2,f"Validation - {PHENOTYPE} - Unseen"]
        except KeyError:
            for call_type in reversed(STATUS_COLORS.keys()):
                if call_type == 'Unseen':
                    hdata.insert(8,f"Validation - {PHENOTYPE} - {call_type}", 1)
                else:
                    hdata.insert(8,f"Validation - {PHENOTYPE} - {call_type}", 0) 
        try:
            hdata.loc[2,"Notes"]
        except KeyError:
            hdata.insert(8,"Notes","-")
            hdata.fillna("")

        for cell_id in STATUS_LIST.keys():
            status = STATUS_LIST[cell_id]
            try:
                # reset all validation cols to zero before assigning a 1 to the appropriate status col
                for call_type in STATUS_COLORS.keys():
                    hdata.loc[hdata["Object Id"]==int(cell_id),f"Validation - {PHENOTYPE} - {call_type}"] = 0
                hdata.loc[hdata["Object Id"]==int(cell_id),f"Validation - {PHENOTYPE} - {status}"] = 1
                hdata.loc[hdata["Object Id"]==int(cell_id),"Notes"] = SAVED_NOTES[str(cell_id)]
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
    global PAGE_SIZE
    page_number = int(page_cb_widget.currentText().split()[-1])
    cell_choice = single_cell_lineEdit.text()
    if cell_choice == '': cell_choice = None
    print(f"CURRENT WIDG POSITION IS {intensity_sort_widget.currentIndex()} and type is {type(intensity_sort_widget.currentIndex())}")
    if intensity_sort_widget.currentIndex() == 0:
        sort_option = None
    else:
        sort_option = intensity_sort_widget.currentText().split()[3]


    # Save data to file from current set
    #TODO Fix amount field
    if not _save_validation(VIEWER, PAGE_SIZE):
        print(f'Could not save...')
        return None
    
    # might not be necessary. Was put here in an attempt to avoid weird GUI element deletion glitch
    # Must come after attempting to save, otherwise widgets vanish when an error occurs...
    for widg in ALL_CUSTOM_WIDGETS.values():
        widg.setVisible(False)


    # Load into same mode as the current
    if COMPOSITE_MODE:
        xydata = extract_phenotype_xldata(page_number=page_number, specific_cell=cell_choice, sort_by_intensity=sort_option)
        if xydata is False:
            VIEWER.status="Can't load cells: out of bounds error."
        else:
            VIEWER.layers.clear()
            add_layers(VIEWER,RAW_PYRAMID, xydata, int(PUNCHOUT_SIZE/2), composite_only=True)
            
    else:
        xydata = extract_phenotype_xldata(page_number=page_number, specific_cell=cell_choice, sort_by_intensity=sort_option)
        if xydata is False:
            VIEWER.status="Can't load cells: out of bounds error."
        else:
            VIEWER.layers.clear()
            add_layers(VIEWER,RAW_PYRAMID, xydata, int(PUNCHOUT_SIZE/2), composite_only=False)
    
    single_cell_lineEdit.clear() # reset the widget
    # Perform adjustments before exiting function
    #TODO
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
def toggle_statuslayer_visibility(show_widget):
    if show_widget.isChecked(): Status_Bar_Visibility = 1
    else: Status_Bar_Visibility = 2
    # Find status layers and toggle visibility
    if Status_Bar_Visibility==1:
        for layer in VIEWER.layers:
            if layer.name == 'Status Layer':
                layer.visible = True
    elif Status_Bar_Visibility==2:
        for layer in VIEWER.layers:
            if layer.name == 'Status Layer':
                layer.visible = False
    else:
        raise Exception(f"Invalid parameter passed to toggle_statusbar_visibility: {Status_Bar_Visibility}. Must be 1 or 2.")
    return None

def toggle_statusbox_visibility(show_widget):
    if show_widget.isChecked(): Status_Box_Visibility = 1
    else: Status_Box_Visibility = 2
    # Find status layers and toggle visibility
    if Status_Box_Visibility==1:
        for layer in VIEWER.layers:
            if layer.name == 'Status Layer':
                im = layer.data
                if COMPOSITE_MODE:
                    mult = 1
                else:
                    mult = 4
                for j in range(0,((PUNCHOUT_SIZE+2)*CELLS_PER_ROW), (PUNCHOUT_SIZE+2)):#rows
                    for i in range(0,(ceil((PAGE_SIZE*mult)/CELLS_PER_ROW)*(PUNCHOUT_SIZE+2))+1, (PUNCHOUT_SIZE+2)):#cols
                        im[i:i+1, j:j+PUNCHOUT_SIZE+2, 3] = 255 # top
                        im[i:i+PUNCHOUT_SIZE+2,j:j+1, 3] = 255 # left
                        im[i+PUNCHOUT_SIZE+1:i+PUNCHOUT_SIZE+2, j:j+PUNCHOUT_SIZE+2, 3] = 255 # right
                        im[i:i+PUNCHOUT_SIZE+2,j+PUNCHOUT_SIZE+1:j+PUNCHOUT_SIZE+2, 3] = 255 # bottom
                        if j == 0 or COMPOSITE_MODE:
                            im[i:i+16, j:j+16, 3] = 255

                layer.data = im
                # for col in range(1,CELLS_PER_ROW,1):
                    
    elif Status_Box_Visibility==2:
        for layer in VIEWER.layers:
            if layer.name == 'Status Layer':
                im = layer.data
                if COMPOSITE_MODE:
                    mult = 1
                else:
                    mult = 4
                for j in range(0,((PUNCHOUT_SIZE+2)*CELLS_PER_ROW), (PUNCHOUT_SIZE+2)):
                    for i in range(0,(ceil((PAGE_SIZE*mult)/CELLS_PER_ROW)*(PUNCHOUT_SIZE+2))+1, (PUNCHOUT_SIZE+2)):
                        im[i:i+1, j:j+PUNCHOUT_SIZE+2, 3] = 0 # top
                        im[i:i+PUNCHOUT_SIZE+2,j:j+1, 3] = 0 # left
                        im[i+PUNCHOUT_SIZE+1:i+PUNCHOUT_SIZE+2, j:j+PUNCHOUT_SIZE+2, 3] = 0 # right
                        im[i:i+PUNCHOUT_SIZE+2,j+PUNCHOUT_SIZE+1:j+PUNCHOUT_SIZE+2, 3] = 0 # bottom
                        im[i:i+16, j:j+16, 3] = 0 # box
                layer.data = im
                # print(im.shape)
    else:
        raise Exception(f"Invalid parameter passed to toggle_statusbox_visibility: {Status_Box_Visibility}. Must be 1 or 2.")
    return None

def sort_by_intensity():
    pass

def set_notes_label(display_note_widget, ID):
    try:
        note = str(SAVED_NOTES[ID])
    except KeyError: # in case the name was off
        return False
    status = STATUS_LIST[str(ID)]
    prefix = f'{SAVED_NOTES["page"]}<br><font color="{STATUS_TO_HEX[status]}">CID: {ID}</font>'

    # Add intensities
    intensity_series = SAVED_INTENSITIES[ID]
    intensity_str = ''
    for pos in CHANNELS:
        fluor = list(CHANNEL_ORDER.keys())[pos]
        if fluor == 'Composite':
            continue
        # fluor = str(cell).replace(" Cell Intensity","")
        fluor = str(fluor)
        intensity_str += f'<br><font color="{CHANNEL_ORDER[fluor].replace("blue","#0462d4")}">{fluor.replace("OPAL","Opal ")}'
        try:
            # cyto = fluor.replace("OPAL","Opal ")
            cyto = round(float(intensity_series[f'{fluor.replace("OPAL","Opal ")} Cytoplasm Intensity']),1)
            intensity_str += f'<font color="{CHANNEL_ORDER[fluor].replace("blue","#0462d4")}"> cyto: {cyto}</font>'
        except KeyError:
            pass
        try:
            # nuc = fluor.replace("OPAL","Opal ")
            nuc = round(float(intensity_series[f'{fluor.replace("OPAL","Opal ")} Nucleus Intensity']),1)
            intensity_str += f'<font color="{CHANNEL_ORDER[fluor].replace("blue","#0462d4")}"> nuc: {nuc}</font>'
        except KeyError:
            pass
        try:
            # cell = fluor.replace("OPAL","Opal ")
            cell = round(float(intensity_series[f'{fluor.replace("OPAL","Opal ")} Cell Intensity']),1)
            intensity_str += f'<font color="{CHANNEL_ORDER[fluor].replace("blue","#0462d4")}"> cell: {cell}</font>'
        except KeyError:
            pass
        # intensity_str += f'<br><font color="{CHANNEL_ORDER[fluor.replace(" ","").upper()].replace("blue","#0462d4")}">{fluor} cyto: {round(float(intensity_series[cyto]),1)} nuc: {round(float(intensity_series[nuc]),1)} cell: {round(float(intensity_series[cell]),1)}</font>'
    # Add note if it exists
    if note == '-' or note == '' or note is None: 
        note = prefix + intensity_str
    else:
        note = prefix + intensity_str + f'<br><font size="5pt" color="white">{note}</font>'
    display_note_widget.setText(note)
    return True
######------------------------- Image loading and processing functions ---------------------######

#TODO consider combining numpy arrays before adding layers? So that we create ONE image, and have ONE layer
#   for the ctc cells. Gallery mode might end up being a pain for downstream.
#   Counterpoint - how to apply filters to only some channels if they are in same image?
#   Counterpoint to counterpoint - never get rid of numpy arrays and remake whole image as needed. 
def add_layers(viewer,pyramid, cells, offset, composite_only=COMPOSITE_MODE, new_page=True):
    print(f'\n---------\n \n Entering the add_layers function')
    print(f"pyramid shape is {pyramid.shape}")
    # Make the color bar that appears to the left of the composite image
    status_colors = {"Unseen":"gray", "Needs review":"bop orange", "Confirmed":"green", "Rejected":"red" }
    global CELLS_PER_ROW
    if not composite_only:
        CELLS_PER_ROW = len(CHANNELS_STR) #+1
        # print(f"$$$$$$$ ROW SIZE VS CHANSTR: {CELLS_PER_ROW} vs {len(CHANNELS_STR)}")
    else: # composite_only = True
        CELLS_PER_ROW = userInfo.cells_per_row

    def retrieve_status(cell_id, cell):
        ''' Kind of an anachronistic function at this point.'''
        # print(f'Getting status for {cell_id}')
        if new_page:
            try:
                status = cell[3]
                # print(f'Got it. Status is .{status}.')
            except:
                # Column doesn't exist, use default
                status = "Unseen"
                # print(f'exception. Could not grab status')
            if type(status) is not str or status not in status_colors.keys():
                status = "Unseen"
            # Save to dict to make next retrieval faster
            STATUS_LIST[str(cell_id)] = status
            return status
        else:
            # Just grab it because it's there already
            try:
                return STATUS_LIST[str(cell_id)]
            except:
                raise Exception(f"Looking for {cell_id} in the Status list dict but can't find it. List here:\n {STATUS_LIST}")

    ''' Expects a numpy array of shape PUNCHOUT_SIZE x 16, with a 16x16 box taking up the left-hand side'''    
    def write_cid_text_to_array(cb_size, im_length, edge_width, color, cid):
        new = Image.new("RGBA", (3*im_length,3*cb_size), (0,0,0,255))
        font = ImageFont.truetype("arial.ttf",48)
        editable_image = ImageDraw.Draw(new)
        editable_image.text((70,1), str(cid), color, font = font)
        resized = np.array(new.resize((im_length,cb_size), Image.Resampling.LANCZOS))
        resized[:,:,3] = (255* (resized[:,:,:3] >15).any(axis=2)).astype(np.uint8)
        return resized

    def generate_status_box(color, cid, composite_only):
        if color == 'red':
            color_tuple = (255,0,0,255)
        elif color == 'green':
            color_tuple = (0,255,0,255)
        elif color =='bop orange':
            color_tuple = (255,160,0,255)
        else: # assume 'gray'
            color_tuple = (180,180,180,255)

        corner_box_size = 16
        edge_width = 1
        if composite_only:
            layer_length = (PUNCHOUT_SIZE+(edge_width*2))
        else:
            layer_length = (PUNCHOUT_SIZE+(edge_width*2)) * CELLS_PER_ROW

        if NO_LABEL_BOX:
            number_only = write_cid_text_to_array(PUNCHOUT_SIZE+(edge_width*2), layer_length, edge_width, color_tuple, cid)
            return number_only

        top_or_bottom = [color_tuple, ] *layer_length
        # top_or_bottom = np.append([top_or_bottom],[top_or_bottom],axis = 0)
        x = np.array([[color_tuple, (0,0,0,0), color_tuple]])
        y = np.repeat(x,[edge_width,layer_length - (2*edge_width),edge_width],axis=1)
        mid = np.repeat(y,PUNCHOUT_SIZE+edge_width-(corner_box_size), axis=0)

        z = np.repeat(x,[corner_box_size,(layer_length-(2*edge_width))+edge_width-(corner_box_size),edge_width],axis=1)
        # above_mid = np.repeat(z,corner_box_size-edge_width, axis=0)

        top = write_cid_text_to_array(corner_box_size, layer_length, edge_width, color_tuple, cid)
        # text_added = text_added | above_mid
        # top = np.append([top_or_bottom],above_mid,axis=0)
        # print(f"SHAPES: tob {np.array([top_or_bottom]).shape} and text_added {text_added.shape}")
        # exit()
        top[0:corner_box_size,0:corner_box_size,:] = color_tuple
        top[0,:,:] = color_tuple
        top[:,-1,:] = color_tuple

        # top = np.append([top_or_bottom],text_added,axis=0)
        # z = np.repeat([np.repeat([0],12)],2,axis=0)z
        tm = np.append(top,mid, axis=0)
        return np.append(tm,[top_or_bottom],axis=0)

    def black_background(color_space, mult):
        if color_space == 'RGB':
            return np.zeros((ceil((PAGE_SIZE*mult)/CELLS_PER_ROW)*(PUNCHOUT_SIZE+2),(PUNCHOUT_SIZE+2) * CELLS_PER_ROW, 4))
        elif color_space == 'Luminescence':
            return np.zeros((ceil((PAGE_SIZE*mult)/CELLS_PER_ROW)*(PUNCHOUT_SIZE+2),(PUNCHOUT_SIZE+2) * CELLS_PER_ROW))


    # Starting to add
    if composite_only: size_multiplier = 1
    else: size_multiplier = len(CHANNELS)
    page_image = {}
    for chn in CHANNELS_STR:
        if chn == 'Composite':
            pass
        else:
            page_image[chn] = black_background('Luminescence', size_multiplier)

    # page_image = black_background('RGB',size_multiplier)
    page_status_layer = black_background('RGB',size_multiplier)
    print(f'Adding {len(cells)} cells to viewer... Channels are {CHANNELS} // {CHANNELS_STR}')
    col = 0
    row = 0
    GRID_TO_ID = {} # Reset this since we could be changing to multichannel mode
    while bool(cells): # coords left
        col = (col%CELLS_PER_ROW)+1
        if col ==1: row+=1 
        # print(f'Next round of while. Still {len(cells)} cells left. Row {row}, Col {col}')
        cell = cells.pop(); cell_x = cell[0]; cell_y = cell[1]; cell_id = cell[2]; cell_status = retrieve_status(cell_id,cell)
        # add the rest of the layers to the viewer
        if RASTERS is not None:
            # Raster channels for qptiffs are saved as subdatasets of the opened raster object
            num_channels = len(RASTERS) 
        else:
            num_channels = pyramid.shape[2] # Data is [X,Y,C]
        for pos, fluor in enumerate(CHANNEL_ORDER): # loop through channels
            if pos in CHANNELS and fluor != 'Composite':
                # name cell layer
                cell_name = f'Cell {cell_id} {fluor}'

                # print(f'Adding cell {cell_x},{cell_y} - layer {i}')
                # Save record of what colormap is chosen for what fluor. Useful for 
                #   altering the composite image later (white-in / black-in). 
                # This is dumb - do it somewhere else
                # print(f'Testing if raster used: {RASTERS}') # YES can see subdatasets.
                if RASTERS is not None:
                    with rasterio.open(RASTERS[pos]) as channel:
                        cell_punchout = channel.read(1,window=Window(cell_x-offset,cell_y-offset, offset*2,offset*2)).astype(np.uint8)
                else:
                    # rasterio reading didn't work, so entire image should be in memory as np array
                    cell_punchout = pyramid[cell_x-offset:cell_x+offset,cell_y-offset:cell_y+offset,pos].astype(np.uint8)
                # print(f'Trying to add {cell_name} layer with fluor-color(cm):{fluor}-{CHANNEL_ORDER[fluor]}')

                # print(f'fluor {fluor} pageimage shape: {pageimage.shape} | row {row}, col {col} | cpsave shape {cp_save.shape}')
                if not composite_only: # Only add channels if we are in 'show all' mode. Otherwise only composite will show up
                    if col ==1:
                        page_status_layer[(row-1)*(PUNCHOUT_SIZE+2):row*(PUNCHOUT_SIZE+2), 
                                          (col-1)*(PUNCHOUT_SIZE+2):] = generate_status_box(status_colors[cell_status], cell_id, composite_only)
                    # multichannel mode: individual image
                    page_image[fluor][(row-1)*(PUNCHOUT_SIZE+2)+1:row*(PUNCHOUT_SIZE+2)-1,
                                (col-1)*(PUNCHOUT_SIZE+2)+1:col*(PUNCHOUT_SIZE+2)-1] = cell_punchout
                    # multichannel mode: composite image
                    page_image[fluor][(row-1)*(PUNCHOUT_SIZE+2)+1:row*(PUNCHOUT_SIZE+2)-1,
                                (CELLS_PER_ROW-1)*(PUNCHOUT_SIZE+2)+1:CELLS_PER_ROW*(PUNCHOUT_SIZE+2)-1] = cell_punchout
                    GRID_TO_ID[f'{row},{col}'] = cell_id
                    GRID_TO_ID[f'{row},{CELLS_PER_ROW}'] = cell_id

                    col+=1 # so that next luminescence image is tiled 
                    continue

                if composite_only: # This stuff is only necessary in composite mode 
                    GRID_TO_ID[f'{row},{col}'] = cell_id
                    page_image[fluor][(row-1)*(PUNCHOUT_SIZE+2)+1:row*(PUNCHOUT_SIZE+2)-1, (col-1)*(PUNCHOUT_SIZE+2)+1:col*(PUNCHOUT_SIZE+2)-1] = cell_punchout
                    page_status_layer[(row-1)*(PUNCHOUT_SIZE+2):row*(PUNCHOUT_SIZE+2), (col-1)*(PUNCHOUT_SIZE+2):col*(PUNCHOUT_SIZE+2)] = generate_status_box(status_colors[cell_status], cell_id, composite_only)
    
    for fluor in list(page_image.keys()):
        print(f"Adding layers now. fluor is {fluor}")
        if fluor == 'Composite':
            continue
        IMAGE_LAYERS[fluor] = viewer.add_image(page_image[fluor], name = fluor, 
                                               blending = 'additive', colormap = custom_maps.retrieve_cm(CHANNEL_ORDER[fluor]) )
    # if composite_only:
    status_layer = viewer.add_image(page_status_layer.astype('int'), name='Status Layer')

    ##----------------- Live functions that control mouseover behavior on images 

    '''Take a pixel coordinate (y,x) and return an (x,y) position for the image that contains the pixel in the image grid'''
    def pixel_coord_to_grid(coords):
        x = coords[0]; y = coords[1]
        # Cannot return 0 this way, since there is no 0 row or col
        row_num = max(ceil((x+1)/(PUNCHOUT_SIZE+2)),1)
        col_num = max(ceil((y+1)/(PUNCHOUT_SIZE+2)),1)
        return row_num, col_num
    
    def multichannel_fetch_val(local_x,global_y, fluor):
        offset_x = (PUNCHOUT_SIZE+2) * list(CHANNELS_STR).index(fluor)
        return (global_y, offset_x+local_x)
    

    def find_mouse(image_layer, data_coordinates, scope = 'world'):
        
                # retrieve cell ID name
        coords = np.round(data_coordinates).astype(int)
        row,col = pixel_coord_to_grid(coords)
        try:
            image_name = GRID_TO_ID[f'{row},{col}']
        except KeyError as e:
            return "None" , None, None
        
        vals = {}
        local_x = coords[1] - (PUNCHOUT_SIZE+2)*(col-1)
        local_y = coords[0] - (PUNCHOUT_SIZE+2)*(row-1)
        for fluor in CHANNELS_STR:
            if fluor == "Composite": continue
            img_layer = IMAGE_LAYERS[fluor]
            if not COMPOSITE_MODE:
                # print(f"data coords: {data_coordinates}  | vs assumed coords for {fluor}: {multichannel_fetch_val(local_x, data_coordinates[0], fluor)}")
                vals[fluor] = img_layer.get_value(multichannel_fetch_val(local_x, data_coordinates[0], fluor))
            else:
                vals[fluor] = img_layer.get_value(data_coordinates)
            if vals[fluor] is None:
                return "None" , None, None

        # return either global or local (relative to punchout) coordinates
        if scope == 'world':
            return str(image_name), coords, vals
        else:
            return str(image_name), (local_x,local_y), vals

    @viewer.mouse_move_callbacks.append
    def display_intensity(image_layer, event):
        
        cell_num,coords,vals = find_mouse(image_layer, event.position, scope = 'grid') 
        image_name = f'Cell {cell_num}'
        set_notes_label(NOTES_WIDGET, str(cell_num))

        if (not vals) or (vals is None):
            # Don't do anything else
            VIEWER.status = 'Out of bounds'
            return True
        output_str = ''
        for fluor in vals.keys():
            output_str+= f'<font color="{CHANNEL_ORDER[fluor].replace("blue","#0462d4")}">    {vals[fluor]}   </font>'
        else:
            # print('else')
            sc = STATUS_TO_HEX[STATUS_LIST[str(cell_num)]]
            VIEWER.status = f'<font color="{sc}">{image_name}</font> intensities at {coords}: {output_str}'

    @status_layer.bind_key('Space')
    def toggle_status(image_layer):
        
        cell_num,data_coordinates,val = find_mouse(image_layer, viewer.cursor.position) 
        if val is None:
            return None
        coords = np.round(data_coordinates).astype(int)
        row,col = pixel_coord_to_grid(coords)

        cur_status = STATUS_LIST[str(cell_num)]
        cur_index = list(status_colors.keys()).index(cur_status)
        next_status = list(status_colors.keys())[(cur_index+1)%len(status_colors)]
        STATUS_LIST[str(cell_num)] = next_status

        imdata = image_layer.data
        if COMPOSITE_MODE: 
            imdata[(row-1)*(PUNCHOUT_SIZE+2):row*(PUNCHOUT_SIZE+2), 
                              (col-1)*(PUNCHOUT_SIZE+2):col*(PUNCHOUT_SIZE+2)] = generate_status_box(status_colors[next_status],str(cell_num), True)
        else:
            imdata[(row-1)*(PUNCHOUT_SIZE+2):row*(PUNCHOUT_SIZE+2),
                :] = generate_status_box(status_colors[next_status],str(cell_num), False)
        image_layer.data = imdata.astype('int')

    @status_layer.mouse_drag_callbacks.append
    def trigger_toggle_status(image_layer, event):
        toggle_status(image_layer)

    @status_layer.bind_key('c')
    def set_unseen(image_layer):
        next_status = 'Unseen'
        cell_num,data_coordinates,val = find_mouse(image_layer, viewer.cursor.position) 
        if val is None:
            return None
        coords = np.round(data_coordinates).astype(int)
        row,col = pixel_coord_to_grid(coords)
        STATUS_LIST[str(cell_num)] = next_status

        imdata = image_layer.data
        if COMPOSITE_MODE: 
            imdata[(row-1)*(PUNCHOUT_SIZE+2):row*(PUNCHOUT_SIZE+2), 
                              (col-1)*(PUNCHOUT_SIZE+2):col*(PUNCHOUT_SIZE+2)] = generate_status_box(status_colors[next_status],str(cell_num), True)
        else:
            imdata[(row-1)*(PUNCHOUT_SIZE+2):row*(PUNCHOUT_SIZE+2),
                :] = generate_status_box(status_colors[next_status],str(cell_num), False)
        image_layer.data = imdata.astype('int')

    @status_layer.bind_key('v')
    def set_nr(image_layer):
        next_status = 'Needs review'
        cell_num,data_coordinates,val = find_mouse(image_layer, viewer.cursor.position) 
        if val is None:
            return None
        coords = np.round(data_coordinates).astype(int)
        row,col = pixel_coord_to_grid(coords)
        STATUS_LIST[str(cell_num)] = next_status

        imdata = image_layer.data
        if COMPOSITE_MODE: 
            imdata[(row-1)*(PUNCHOUT_SIZE+2):row*(PUNCHOUT_SIZE+2), 
                              (col-1)*(PUNCHOUT_SIZE+2):col*(PUNCHOUT_SIZE+2)] = generate_status_box(status_colors[next_status],str(cell_num), True)
        else:
            imdata[(row-1)*(PUNCHOUT_SIZE+2):row*(PUNCHOUT_SIZE+2), 
                :] = generate_status_box(status_colors[next_status],str(cell_num), False)
        image_layer.data = imdata.astype('int')

    @status_layer.bind_key('b')
    def set_confirmed(image_layer):
        next_status = 'Confirmed'
        cell_num,data_coordinates,val = find_mouse(image_layer, viewer.cursor.position) 
        if val is None:
            return None
        coords = np.round(data_coordinates).astype(int)
        row,col = pixel_coord_to_grid(coords)
        STATUS_LIST[str(cell_num)] = next_status

        imdata = image_layer.data   
        if COMPOSITE_MODE: 
            imdata[(row-1)*(PUNCHOUT_SIZE+2):row*(PUNCHOUT_SIZE+2), 
                              (col-1)*(PUNCHOUT_SIZE+2):col*(PUNCHOUT_SIZE+2)] = generate_status_box(status_colors[next_status],str(cell_num), True)
        else:
            imdata[(row-1)*(PUNCHOUT_SIZE+2):row*(PUNCHOUT_SIZE+2), 
                :] = generate_status_box(status_colors[next_status],str(cell_num), False)
        image_layer.data = imdata.astype('int')
    
    @status_layer.bind_key('n')
    def set_rejected(image_layer):
        next_status = 'Rejected'
        cell_num,data_coordinates,val = find_mouse(image_layer, viewer.cursor.position) 
        if val is None:
            return None
        coords = np.round(data_coordinates).astype(int)
        row,col = pixel_coord_to_grid(coords)
        STATUS_LIST[str(cell_num)] = next_status

        imdata = image_layer.data   
        if COMPOSITE_MODE: 
            imdata[(row-1)*(PUNCHOUT_SIZE+2):row*(PUNCHOUT_SIZE+2), 
                              (col-1)*(PUNCHOUT_SIZE+2):col*(PUNCHOUT_SIZE+2)] = generate_status_box(status_colors[next_status],str(cell_num), True)
        else:
            imdata[(row-1)*(PUNCHOUT_SIZE+2):row*(PUNCHOUT_SIZE+2), 
                :] = generate_status_box(status_colors[next_status],str(cell_num), False)
        image_layer.data = imdata.astype('int')

    #TODO make a page label... 
    # add polygon (just for text label)
    # text = {'string': 'Page name goes here', 'anchor': 'center', 'size': 8,'color': 'white'}
    # shapes_layer1 = viewer.add_shapes([[0,0], [40,0], [40,40],[0,40]], shape_type = 'polygon',
    #                 edge_color = 'green', face_color='transparent',text=text, name='Page Name') 
    # shapes_layer2 = viewer.add_shapes([[0,0], [40,0], [40,40],[0,40]], shape_type = 'polygon',
    #                 edge_color = 'green', face_color='transparent',text=text, name='Page Name') 

    return True

######------------------------- Misc + Viewer keybindings ---------------------######

#TODO make a button to do this as well?
def set_viewer_to_neutral_zoom(viewer):
    if COMPOSITE_MODE:
        viewer.camera.center = (350,450) # these values seem to work best
    else:
        viewer.camera.center(350, 1000)
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
            hdata.loc[2,f"Validation - {PHENOTYPE} - Unseen"]
        except KeyError:
            for call_type in reversed(STATUS_COLORS.keys()):
                if call_type == 'Unseen':
                    hdata.insert(8,f"Validation - {PHENOTYPE} - {call_type}", 1)
                else:
                    hdata.insert(8,f"Validation - {PHENOTYPE} - {call_type}", 0) 
        try:
            hdata.loc[2,"Notes"]
        except KeyError:
            hdata.insert(8,"Notes","-")
            hdata.fillna("")

        for cell_id in STATUS_LIST.keys():
            status = STATUS_LIST[cell_id]
            # print(f"\nSave status {status}, cid {cell_id}")
            try:
                # reset all validation cols to zero before assigning a 1 to the appropriate status col
                for call_type in STATUS_COLORS.keys():
                    hdata.loc[hdata["Object Id"]==int(cell_id),f"Validation - {PHENOTYPE} - {call_type}"] = 0
                hdata.loc[hdata["Object Id"]==int(cell_id),f"Validation - {PHENOTYPE} - {status}"] = 1
                hdata.loc[hdata["Object Id"]==int(cell_id),"Notes"] = SAVED_NOTES[str(cell_id)]
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
    def toggle_statuslayer_visibility(viewer):
        show_vis_radio = ALL_CUSTOM_WIDGETS['show status layer radio']
        hide_vis_radio = ALL_CUSTOM_WIDGETS['hide status layer radio']
        if show_vis_radio.isChecked():
            show_vis_radio.setChecked(False)
            hide_vis_radio.setChecked(True)
        else:
            show_vis_radio.setChecked(True)
            hide_vis_radio.setChecked(False)

    @viewer.bind_key('Control-h')
    def toggle_statusbox_visibility(viewer):
        show_box_radio = ALL_CUSTOM_WIDGETS['show status box radio']
        hide_box_radio = ALL_CUSTOM_WIDGETS['hide status box radio']
        if show_box_radio.isChecked():
            show_box_radio.setChecked(False)
            hide_box_radio.setChecked(True)
        else:
            show_box_radio.setChecked(True)
            hide_box_radio.setChecked(False)

    @viewer.bind_key('Control-k')
    def restore_canvas(viewer):
        set_viewer_to_neutral_zoom(viewer)

    @viewer.bind_key('k')
    def recenter_canvas(viewer):
        set_viewer_to_neutral_zoom(viewer)

    @viewer.bind_key('Up')
    def scroll_up(viewer):
        z,y,x = viewer.camera.center
        viewer.camera.center = (y-50,x)

    @viewer.bind_key('Down')
    def scroll_down(viewer):
        z,y,x = viewer.camera.center
        viewer.camera.center = (y+50,x)
    
    @viewer.bind_key('Left')
    def scroll_left(viewer):
        z,y,x = viewer.camera.center
        viewer.camera.center = (y,x-50)
        #TODO trigger mouse update here
        # napari.Viewer.window.qt_viewer._process_mouse_event
        # viewer.window.qt_viewer.canvas.events.mouse_press(pos=(x, y), modifiers=(), button=0)
        # viewer.cursor.position = viewer.window.qt_viewer._map_canvas2world([x,y])

    @viewer.bind_key('Right')   
    def scroll_right(viewer):
        z,y,x = viewer.camera.center
        viewer.camera.center = (y,x+50)

    @viewer.bind_key('Control-Right')  
    @viewer.bind_key('Control-Up')   
    def zoom_in(viewer):
        viewer.camera.zoom *= 1.3

    @viewer.bind_key('Control-Left')  
    @viewer.bind_key('Control-Down')   
    def zoom_out(viewer):
        viewer.camera.zoom /= 1.3  

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
        # fluor = fluor.replace("OPAL",'')
        ADJUSTMENT_SETTINGS[fluor+ ' black-in']=0
        ADJUSTMENT_SETTINGS[fluor+ ' white-in']=255
        ADJUSTMENT_SETTINGS[fluor+ ' gamma']= 0.5

def fetch_notes(cell_set, intensity_col_names):
    '''Grab notes and intensities for each cell in the list and save to global dicts'''
    for index,row in cell_set.iterrows():
        ID = str(row['Object Id'])
        SAVED_NOTES[ID] = row['Notes']
        # Find out which columns are present in the Series and subset to those
        present_intensities = sorted(list(set(list(row.index)).intersection(set(intensity_col_names))))
        row = row.loc[present_intensities]
        SAVED_INTENSITIES[ID] = row
    # print(f'dumping dict {SAVED_NOTES}')

'''Get object data from csv and parse.''' 
def extract_phenotype_xldata(page_size=None, phenotype=None, page_number = 1, 
                            specific_cell = None, sort_by_intensity = None, combobox_widget = None):
    
    # 'OPAL520' # None means 'don't do it', while a channel name means 'put highest at the top'
    if sort_by_intensity is None:
        sort_by_intensity = "Object Id"
    elif "opal" in sort_by_intensity.lower():
        sort_by_intensity = sort_by_intensity.replace('OPAL','Opal ') + ' Cell Intensity'
    else:
        sort_by_intensity = "Sample AF Cell Intensity"
    print(f"SORTBYINTENSITY IS {sort_by_intensity}")

    # get defaults from global space
    if page_size is None: page_size=PAGE_SIZE # Number of cells to be shown
    if phenotype is None: phenotype=PHENOTYPE # Name of phenotype of interest
    # print(f'ORDERING PARAMS: id start: {cell_id_start}, page size: {page_size}, direction: {direction}, change?: {change_startID}')
    halo_export = pd.read_csv(OBJECT_DATA)
    
    if phenotype not in list(halo_export.columns):
        raise KeyError
    # Add columns w/defaults if they aren't there to avoid runtime issues
    try:
        halo_export.loc[2,f"Validation - {phenotype} - Unseen"]
    except KeyError:
        for call_type in reversed(STATUS_COLORS.keys()):
            if call_type == 'Unseen':
                halo_export.insert(8,f"Validation - {phenotype} - {call_type}", 1)
            else:
                halo_export.insert(8,f"Validation - {phenotype} - {call_type}", 0) 
    try:
        halo_export.loc[2,"Notes"]
    except KeyError:
        halo_export.insert(8,"Notes","-")
        halo_export.fillna("")
    try:
        halo_export.to_csv(OBJECT_DATA, index=False)
    except:
        pass

    # Get relevant columns for intensity sorting
    # TODO make this conditional, and in a try except format
    all_possible_intensities = ['DAPI Nucleus Intensity','DAPI Cytoplasm Intensity','DAPI Cell Intensity', 
                                'Opal 480 Nucleus Intensity','Opal 480 Cytoplasm Intensity','Opal 480 Cell Intensity',
                                'Opal 520 Nucleus Intensity','Opal 520 Cytoplasm Intensity','Opal 520 Cell Intensity',
            'Opal 570 Nucleus Intensity','Opal 570 Cytoplasm Intensity','Opal 570 Cell Intensity',
              'Opal 620 Nucleus Intensity','Opal 620 Cytoplasm Intensity','Opal 620 Cell Intensity',
                'Opal 690 Nucleus Intensity','Opal 690 Cytoplasm Intensity','Opal 690 Cell Intensity',
                'Opal 780 Nucleus Intensity','Opal 780 Cytoplasm Intensity','Opal 780 Cell Intensity',
            'AF Nucleus Intensity','AF Cytoplasm Intensity','AF Cell Intensity',
            'Autofluorescence Nucleus Intensity','Autofluorescence Cytoplasm Intensity','Autofluorescence Cell Intensity',
            "Sample AF Nucleus Intensity", "Sample AF Cytoplasm Intensity", "Sample AF Cell Intensity"] # not sure what the correct nomenclature is here
    v = list(STATUS_COLORS.keys())
    validation_cols = [f"Validation - {PHENOTYPE} - " + s for s in v]
    cols_to_keep = ["Object Id", "Notes", "XMin","XMax","YMin", "YMax", phenotype] + all_possible_intensities + validation_cols
    cols_to_keep = halo_export.columns.intersection(cols_to_keep)
    halo_export = halo_export.loc[:, cols_to_keep]

    global GLOBAL_SORT
    global_sort_status = True
    if GLOBAL_SORT is not None:
        try:
            halo_export = halo_export.sort_values(by = GLOBAL_SORT, ascending = False, kind = 'mergesort')
        except:
            print('Global sort failed. Will sort by Cell Id instead.')
            GLOBAL_SORT = None
            global_sort_status = False
            VIEWER.status = 'Global sort failed. Will sort by Cell Id instead.'
    
    # #acquire 
    print('page code start')
    # Figure out which range of cells to get based on page number and size
    phen_only_df = halo_export[halo_export[phenotype]==1].reset_index()
    last_page = len(phen_only_df.index) // page_size
    print(f"last page is {last_page}")
    global ALL_CUSTOM_WIDGETS
    combobox_widget =  ALL_CUSTOM_WIDGETS['page combobox']
    # If page numbers haven't been added to the widget, do it now   
    if combobox_widget.currentIndex() == -1: # This means it's empty
        for i in range(1,last_page+1):
            bname = f'{phenotype} page {i}'
            combobox_widget.addItem(bname)

    # If a certain cell is desired, find its page
    print(f"testing if specific cell {specific_cell} and type {type(specific_cell)}")
    if specific_cell is not None:
        try:
            singlecell_df = phen_only_df[phen_only_df['Object Id']==int(specific_cell)]
            sc_index = singlecell_df.index[0]
            page_number = (sc_index//page_size)+1
            #TODO set the combobox widget to the current page number
        except (KeyError,IndexError, ValueError):
            print(f'The cell ID {specific_cell} is not in my list of {phenotype}. Loading default page instead ')
            VIEWER.status = f'The cell ID {specific_cell} is not in my list of {phenotype}. Loaded default page instead'

    # set widget to current page number 
    combobox_widget.setCurrentIndex(page_number-1)
    SAVED_NOTES['page'] = combobox_widget.currentText()
    # Get the appropriate set
    if page_number != last_page:
        cell_set = phen_only_df[(page_number-1)*page_size: page_number*page_size]
    else:
        cell_set = phen_only_df[(page_number)*page_size:]
    
    print(f"#$%#$% local sort is {sort_by_intensity}")

    # Reorder cells in the page according to user input
    if sort_by_intensity is not None:
        if sort_by_intensity == "Object Id": lsort = False
        else: lsort = True
        try:    
            cell_set = cell_set.sort_values(by = sort_by_intensity, ascending = lsort, kind = 'mergesort')
        except:
            if global_sort_status:
                VIEWER.status = f"Unable to sort this page by '{sort_by_intensity}', will use ID instead. Check your data headers."
            else:
                VIEWER.status = f"Unable to sort everything by '{sort_by_intensity}', will use ID instead. Check your data headers."
            cell_set = cell_set.sort_values(by = 'Object Id', ascending = False, kind = 'mergesort')
    fetch_notes(cell_set, all_possible_intensities)
    tumor_cell_XYs = []
    try:
        for index,row in cell_set.iterrows():
            center_x = int((row['XMax']+row['XMin'])/2)
            center_y = int((row['YMax']+row['YMin'])/2)
            vals = row[validation_cols]
            validation_call = str(vals[vals == 1].index.values[0]).replace(f"Validation - {phenotype} - ", "")
            tumor_cell_XYs.append([center_x, center_y, row["Object Id"], validation_call])
    except Exception as e:
        print(e)
        exit()
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
    global qptiff, PUNCHOUT_SIZE, PAGE_SIZE, CHANNELS_STR, CHANNEL_ORDER
    global CHANNELS, ADJUSTED, OBJECT_DATA, PHENOTYPE, SPECIFIC_CELL, GLOBAL_SORT, CELLS_PER_ROW

    qptiff = userInfo.qptiff
    PUNCHOUT_SIZE = userInfo.imageSize
    PHENOTYPE = userInfo.phenotype
    PAGE_SIZE = userInfo.page_size
    SPECIFIC_CELL = userInfo.specific_cell
    OBJECT_DATA = userInfo.objectData
    CELLS_PER_ROW = userInfo.cells_per_row
    CHANNEL_ORDER = userInfo.channelOrder
    if "Composite" not in list(CHANNEL_ORDER.keys()): CHANNEL_ORDER['Composite'] = 'None'
    CHANNELS = []
    CHANNELS_STR = []
    for pos,chn in enumerate(list(CHANNEL_ORDER.keys())):
        # print(f'enumerating {chn} and {pos} for {CHANNELS_STR}')
        exec(f"globals()['{chn}'] = {pos}") # Important to do this for ALL channels
        if chn in userInfo.channels:
            # print(f'IF triggered with {chn} and {pos}')
            exec(f"globals()['CHANNELS'].append({chn})")
            CHANNELS_STR.append(chn)
    # print(f'GUI execute channels are {CHANNELS}')
    CHANNELS.append(len(CHANNEL_ORDER)-1) ; CHANNELS_STR.append('Composite')
    ADJUSTED = copy.copy(CHANNELS_STR)
    if userInfo.global_sort == "Sort object table by Cell Id":
        GLOBAL_SORT = None
    elif "OPAL" in userInfo.global_sort:
        chn = userInfo.global_sort.split()[4].replace("OPAL","Opal ")
        GLOBAL_SORT = f"{chn} Cell Intensity"
    else:
        GLOBAL_SORT = f"Sample AF Cell Intensity"


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
            if sds.replace('GTIFF_DIR:','')[1].isdigit() or sds.replace('GTIFF_DIR:','').startswith('9'):  
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

    
    viewer = napari.Viewer(title='CTC Gallery')
    VIEWER = viewer
    # Get rid of the crap on the left sidebar for a cleaner screen
    viewer.window._qt_viewer.dockLayerList.toggleViewAction().trigger()
    viewer.window._qt_viewer.dockLayerControls.toggleViewAction().trigger()

    NOTES_WIDGET = QLabel('Placeholder note'); NOTES_WIDGET.setAlignment(Qt.AlignCenter)
    print(f'Notes widget is {NOTES_WIDGET}\n type is {type(NOTES_WIDGET)}')

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

    page_combobox = QComboBox()
    page_cell_entry = QLineEdit(); 
    page_cell_entry.setPlaceholderText("Cell Id (optional)"); page_cell_entry.setFixedWidth(200)
    intensity_sort_box = QComboBox()
    intensity_sort_box.addItem("Sort page by Cell Id")
    for i, chn in enumerate(CHANNELS_STR[:-1]):
        intensity_sort_box.addItem(f"Sort page by {chn} Intensity")
    local_sort = None
    if GLOBAL_SORT is None:
        intensity_sort_box.setCurrentIndex(0) # Set "sort by CID" to be the default
    elif "Opal" in GLOBAL_SORT:
        local_sort = f"OPAL{GLOBAL_SORT.split()[1]}"
        intensity_sort_box.setCurrentText(f"Sort page by {local_sort} Intensity")
    else:
        local_sort = "AF"
        intensity_sort_box.setCurrentText(f"Sort page by Sample {local_sort} Intensity")

    next_page_button = QPushButton("Change Page")
    next_page_button.pressed.connect(lambda: show_next_cell_group(page_combobox, page_cell_entry, intensity_sort_box))
    notes_container = viewer.window.add_dock_widget([NOTES_WIDGET,note_text_entry, note_cell_entry, note_button], name = 'Annotation', area = 'right')
    page_container = viewer.window.add_dock_widget([page_combobox,page_cell_entry, intensity_sort_box, next_page_button], name = 'Page selection', area = 'right')

    all_channels_rb = QRadioButton("Multichannel Mode")
    composite_only_rb = QRadioButton("Composite Mode"); composite_only_rb.setChecked(True) # Start in composite mode
    comp_group = QButtonGroup(); comp_group.addButton(composite_only_rb); comp_group.addButton(all_channels_rb)
    switch_mode_button = QPushButton("Change Mode")
    switch_mode_button.pressed.connect(lambda: toggle_composite_viewstatus(all_channels_rb,composite_only_rb))
    mode_container = viewer.window.add_dock_widget([all_channels_rb,composite_only_rb,switch_mode_button],name ="Mode selection",area="right")
    
    status_layer_show = QRadioButton("Show label overlay"); status_layer_show.setChecked(True)
    status_layer_hide = QRadioButton("Hide label overlay"); status_layer_hide.setChecked(False)
    vis_group = QButtonGroup(); vis_group.addButton(status_layer_show);vis_group.addButton(status_layer_hide)
    status_layer_hide.toggled.connect(lambda: toggle_statuslayer_visibility(status_layer_show))
    status_layer_show.toggled.connect(lambda: toggle_statuslayer_visibility(status_layer_show))

    # Label box
    status_box_show = QRadioButton("Show status box"); status_box_show.setChecked(True)
    status_box_hide = QRadioButton("Hide status box"); status_box_hide.setChecked(False)
    box_group = QButtonGroup(); box_group.addButton(status_box_show);box_group.addButton(status_box_hide)
    status_box_show.toggled.connect(lambda: toggle_statusbox_visibility(status_box_show))
    status_box_hide.toggled.connect(lambda: toggle_statusbox_visibility(status_box_show))
    vis_container = viewer.window.add_dock_widget([status_layer_show,status_layer_hide],name ="Show/hide overlay",area="right")
    box_container = viewer.window.add_dock_widget([status_box_show,status_box_hide],name ="Show/hide boxes",area="right")

    viewer.window.add_dock_widget(adjust_gamma_widget, area = 'bottom')
    viewer.window.add_dock_widget(adjust_whitein, area = 'bottom')
    viewer.window.add_dock_widget(adjust_blackin, area = 'bottom')
    # viewer.window.add_dock_widget(toggle_composite_viewstatus,name = 'Test', area = 'right')
    # viewer.window.add_dock_widget(show_next_cell_group,name = 'Test2', area = 'right')
    # viewer.window.add_dock_widget(toggle_statusbar_visibility,name = 'Test3', area = 'right')
    # print(f'\n {dir()}') # prints out the namespace variables 
    ALL_CUSTOM_WIDGETS['notes label']=NOTES_WIDGET; ALL_CUSTOM_WIDGETS['notes text entry']=note_text_entry
    ALL_CUSTOM_WIDGETS['notes cell entry']= note_cell_entry;ALL_CUSTOM_WIDGETS['notes button']=note_button
    ALL_CUSTOM_WIDGETS['next page button']=next_page_button
    ALL_CUSTOM_WIDGETS['channels mode radio']=all_channels_rb; ALL_CUSTOM_WIDGETS['composite mode radio']=composite_only_rb
    ALL_CUSTOM_WIDGETS['switch mode buton']=switch_mode_button; 
    ALL_CUSTOM_WIDGETS['show status layer radio']=status_layer_show; ALL_CUSTOM_WIDGETS['hide status layer radio']=status_layer_hide
    ALL_CUSTOM_WIDGETS['show status box radio']=status_box_show; ALL_CUSTOM_WIDGETS['hide status box radio']=status_box_hide
    ALL_CUSTOM_WIDGETS['page combobox']=page_combobox
    notes_container.setSizePolicy(QSizePolicy.MinimumExpanding,QSizePolicy.MinimumExpanding)
    page_container.setSizePolicy(QSizePolicy.MinimumExpanding,QSizePolicy.MinimumExpanding)
    mode_container.setSizePolicy(QSizePolicy.MinimumExpanding,QSizePolicy.MinimumExpanding)
    vis_container.setSizePolicy(QSizePolicy.MinimumExpanding,QSizePolicy.MinimumExpanding)

    # for widg in ALL_CUSTOM_WIDGETS.values():
    #     widg.setSizePolicy(QSizePolicy.MinimumExpanding,QSizePolicy.MinimumExpanding)

        
    RAW_PYRAMID=pyramid
    try:
        tumor_cell_XYs = extract_phenotype_xldata(specific_cell=SPECIFIC_CELL, sort_by_intensity=local_sort)
    except KeyError as e:
        print(e)
        # If the user has given bad input, the function will raise a KeyError. Fail gracefully and inform the user
        status+=f'<font color="#f5551a">  Failed.<br> The phenotype "{PHENOTYPE}" might not exist in the data, or other column names may have changed!</font>'
        _update_status(status)
        viewer.close()
        return None # allows the input GUI to continue running
    status+='<font color="#7dbc39">  Done.</font><br> Initializing Napari session...'
    _update_status(status)

    set_initial_adjustment_parameters() # set defaults: 1.0 gamma, 0 black in, 255 white in
    try:
        add_layers(viewer,pyramid,tumor_cell_XYs, int(PUNCHOUT_SIZE/2))
    except Exception as e:
        print(f'\n add layers segfault')
        print(e)
        exit()

    #TODO
    # Perform adjustments before exiting function
    reuse_contrast_limits()
    reuse_gamma() # might not need to do both of these... One is enough?

    # Filter checkboxes down to relevant ones only and update color
    for i in range(len(all_boxes)):
        box = all_boxes[i]
        if box.objectName() in CHANNELS_STR:
            print(f'going to add box {box.objectName()} to list')
            box.setStyleSheet(f"QCheckBox {{ color: {CHANNEL_ORDER[box.objectName()].replace('blue','#0462d4')} }}")
            UPDATED_CHECKBOXES.append(box)
    viewer.window.add_dock_widget(UPDATED_CHECKBOXES,area='bottom')

    # Finish up, and set keybindings
    status+='<font color="#7dbc39">  Done.</font><br> Goodbye' ;_update_status(status)
    sv_wrapper(viewer)
    tsv_wrapper(viewer)
    chn_key_wrapper(viewer)
    set_viewer_to_neutral_zoom(viewer) # Fix zoomed out issue

    if preprocess_class is not None: preprocess_class.close() # close other window
    napari.run()
    # close image file
    if RASTERS is not None:
        print('Not sure if we have to close this file... the "with" statement should handle it.')
        RAW_PYRAMID.close()
# Main should work now using the defaults specified at the top of this script in the global variable space
if __name__ == '__main__':
    main()
