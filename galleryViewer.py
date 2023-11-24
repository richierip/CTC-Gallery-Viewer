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
from re import sub
import os
import dask.array as da
import zarr
import scipy.spatial as spatial
# from initial_UI import VERSION_NUMBER


######-------------------- Globals, will be loaded through pre-processing QT gui #TODO -------------######
VERSION_NUMBER = '1.2.1'
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
OBJECT_DATA_PATH = r"C:\Users\prich\Desktop\Projects\MGH\CTC_Example\ctc_example_data.csv" # path to halo export
PAGE_SIZE = 15 # How many cells will be shown in next page
CELLS_PER_ROW = 8
SPECIFIC_CELL = None # Dictionary with the format {'ID': (int),'Annotation Layer': (str) }
PHENOTYPES = ['Tumor'] #'CTC 488pos'
ANNOTATIONS = []
GLOBAL_SORT = None
DAPI = 0; OPAL480 = 3; OPAL520 = 6; OPAL570 = 1; OPAL620 = 4; OPAL690 = 2; OPAL780 = 5; AF=7; Composite = 8

userInfo = store_and_load.loadObject('data/presets')
SESSION = userInfo.session # will store non-persistent global variables that need to be accessible

# CHANNELS = [DAPI, OPAL480, OPAL520, OPAL570, OPAL620, OPAL690,OPAL780,AF,Composite] # Default. Not really that useful info since channel order was added.
CHANNELS = [DAPI, OPAL520,OPAL690, Composite] # for local execution / debugging
CHANNEL_ORDER = {'DAPI':'blue', 'OPAL570':'blue', 'OPAL690':'blue', 'OPAL480':'blue', 'OPAL620':'blue', 
                 'OPAL780':'blue', 'OPAL520':'blue', 'AF':'blue', 'Composite':'None'} # to save variable position data for channels (they can be in any order...)
CHANNELS_STR = list(userInfo.channelOrder.keys()) #["DAPI", "OPAL520", "OPAL690", "Composite"] # for local execution / debugging
CHANNELS_STR.append("Composite") # Seems like this has to happen on a separate line
ADJUSTED = copy.copy(CHANNELS_STR)
VIEWER = None
ADJUSTMENT_SETTINGS={"DAPI gamma": 0.5}; ORIGINAL_ADJUSTMENT_SETTINGS = {}
SAVED_INTENSITIES={}; 
RAW_PYRAMID=None
ALL_CUSTOM_WIDGETS = {}
RASTERS = None
NO_LABEL_BOX = False
STATUS_COLORS = {"Unseen":"gray", "Needs review":"bop orange", "Confirmed":"green", "Rejected":"red" }
STATUSES_TO_HEX = store_and_load.STATUSES_HEX
STATUSES_RGBA = {}
UPDATED_CHECKBOXES = []
ANNOTATIONS_PRESENT = False # Track whether there is an 'Analysis Regions' field in the data (duplicate CIDs possible)


######------------------------- MagicGUI Widgets, Functions, and accessories ---------------------######
#TODO merge some of the GUI elements into the same container to prevent strange spacing issues

## --- Composite functions 
def adjust_composite_gamma(layer, gamma):
    layer.gamma = 2-(2*gamma) + 0.001 # avoid gamma = 0 which causes an exception

def adjust_composite_limits(layer, limits):
    layer.contrast_limits = limits

def reuse_gamma():
    # Make everything silent
    for layer in VIEWER.layers:
        layer.visible = False
    for fluor in CHANNELS_STR:
        if fluor == 'Composite':
            continue
        if "Composite" in ADJUSTED or fluor in ADJUSTED: 
            VIEWER.layers[f"{SESSION.mode} {fluor}"].visible = True
        # Now change settings for both, whether or not they are displayed right now.
        adjust_composite_gamma(VIEWER.layers["Gallery "+fluor],ADJUSTMENT_SETTINGS[fluor+" gamma"])
        adjust_composite_gamma(VIEWER.layers["Multichannel "+fluor],ADJUSTMENT_SETTINGS[fluor+" gamma"])
        adjust_composite_gamma(VIEWER.layers["Context "+fluor],ADJUSTMENT_SETTINGS[fluor+" gamma"])

    if SESSION.mode != "Context":
        VIEWER.layers[f"{SESSION.mode} Status Layer"].visible = SESSION.status_layer_vis
        VIEWER.layers[f"{SESSION.mode} Absorption"].visible = SESSION.absorption_mode
    try:
        VIEWER.layers[f"{SESSION.mode} Nuclei Boxes"].visible = SESSION.nuclei_boxes_vis
    except KeyError:
        pass
    


def reuse_contrast_limits():
        # Make everything silent
    for layer in VIEWER.layers:
        layer.visible = False
    for fluor in CHANNELS_STR:
        if fluor == 'Composite':
            continue
        if "Composite" in ADJUSTED or fluor in ADJUSTED: 
            VIEWER.layers[f"{SESSION.mode} {fluor}"].visible = True
        # Now change settings for both, whether or not they are displayed right now.
        adjust_composite_limits(VIEWER.layers["Gallery "+fluor], [ADJUSTMENT_SETTINGS[fluor+" black-in"],ADJUSTMENT_SETTINGS[fluor+" white-in"]])
        adjust_composite_limits(VIEWER.layers["Multichannel "+fluor], [ADJUSTMENT_SETTINGS[fluor+" black-in"],ADJUSTMENT_SETTINGS[fluor+" white-in"]])
        adjust_composite_limits(VIEWER.layers["Context "+fluor], [ADJUSTMENT_SETTINGS[fluor+" black-in"],ADJUSTMENT_SETTINGS[fluor+" white-in"]])

    if SESSION.mode != "Context":
        VIEWER.layers[f"{SESSION.mode} Status Layer"].visible = SESSION.status_layer_vis
        VIEWER.layers[f"{SESSION.mode} Absorption"].visible = SESSION.absorption_mode
    try:
        VIEWER.layers[f"{SESSION.mode} Nuclei Boxes"].visible = SESSION.nuclei_boxes_vis
    except KeyError:
        pass

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
        for m in ["Gallery", "Multichannel", "Context"]:
            adjust_composite_gamma(VIEWER.layers[f"{m} "+fluor],Gamma)

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
        for m in ["Gallery", "Multichannel", "Context"]:
            adjust_composite_limits(VIEWER.layers[f"{m} {fluor}"], [ADJUSTMENT_SETTINGS[fluor+" black-in"],white_in])


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
        for m in ["Gallery", "Multichannel", "Context"]:
            adjust_composite_limits(VIEWER.layers[f"{m} {fluor}"], [black_in,ADJUSTMENT_SETTINGS[fluor+" white-in"]])

def toggle_absorption():
    #TODO make absorption work for context more?
    if SESSION.mode == "Context": return None
    if SESSION.absorption_mode ==True:
        SESSION.absorption_mode = False
        for layer in VIEWER.layers:
            
            if 'Status Layer' in layer.name or "Context" in layer.name:
                continue
            elif "Nuclei Boxes" in layer.name:
                layer.edge_color = '#ffffff'
                layer.text = {'string':'{cid}', 'anchor':'upper_left', 'size' : 8, 'color':"white"}
                continue
            elif "Absorption" in layer.name:
                layer.visible = False
                continue
            layer.colormap = custom_maps.retrieve_cm(CHANNEL_ORDER[layer.name.split()[1]])
            layer.blending = 'Additive'
    else:
        SESSION.absorption_mode = True
        for layer in VIEWER.layers:
            
            if 'Status Layer' in layer.name or "Context" in layer.name:
                continue
            elif "Nuclei Boxes" in layer.name:
                layer.edge_color="#000000"
                layer.text = {'string':'{cid}', 'anchor':'upper_left', 'size' : 8, 'color':"black"}
                continue
            elif "Absorption" in layer.name:
                if SESSION.mode == layer.name.split()[0]:
                    layer.visible = True
                    im = layer.data
                    im[:,:] = [255,255,255,255]
                    layer.data = im.astype(np.uint8)
                continue
            layer.colormap = custom_maps.retrieve_cm(CHANNEL_ORDER[layer.name.split()[1]]+' inverse')
            layer.blending = 'Minimum'
    change_statuslayer_color(copy.copy(SESSION.current_cells))

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
        # Different set of layers if we are in context mode
        lname = f'{SESSION.mode} {fluor}'
        if fluor == "Composite":
            continue
        if "Composite" in ADJUSTED or fluor in ADJUSTED:
            VIEWER.layers[lname].visible = True
        else:
            VIEWER.layers[lname].visible = False  
    # return myfunc

def check_creator2(list_of_names):
    all_boxes = []
    for name in list_of_names:
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
def toggle_session_mode(target_mode):
    def _save_validation(VIEWER, Mode):
        VIEWER.status = 'Saving ...'
        res = userInfo._save_validation(to_disk=False)
        if res:
            VIEWER.status = f'{Mode} Mode enabled. Decisions loaded successfully.'
            return True
        else:
            #TODO Maybe it's an excel sheet?
            VIEWER.status = f'{Mode} Mode enabled. But, there was a problem saving your decisions. Close your data file?'
            return False
    
    # Do nothing in these cases
    if target_mode==SESSION.mode: return None
    SESSION.last_mode = SESSION.mode # save for later

    if target_mode=="Context":
                
        target_cell_info = SESSION.cell_under_mouse
        SESSION.context_target = target_cell_info
        cell_num = str(target_cell_info["cid"])
        print(cell_num)
        
        # save current coordinates
        if SESSION.mode=="Gallery": 
            SESSION.last_gallery_camera_coordinates["center"] = VIEWER.camera.center
            SESSION.last_gallery_camera_coordinates["z"] = VIEWER.camera.zoom

        elif SESSION.mode=="Multichannel": 
            SESSION.last_multichannel_camera_coordinates["center"] = VIEWER.camera.center
            SESSION.last_multichannel_camera_coordinates["z"] = VIEWER.camera.zoom

        # Move to cell location on the global image
        sc = 1 if SESSION.image_scale is None else SESSION.image_scale # Scale factor necessary.
        VIEWER.camera.center = (target_cell_info["center_y"]*sc,target_cell_info["center_x"]*sc) # these values seem to work best
        # viewer.camera.zoom = 1.2 / sc

        # try to remove any previous box layers if there are any
        try:
            VIEWER.layers.selection.active = VIEWER.layers["Context Nuclei Boxes"]
            VIEWER.layers.remove_selected()
        except KeyError:
            pass

        # Find cells in session table near target
        nearby_inds = SESSION.kdtree.query_ball_point([target_cell_info["center_x"],target_cell_info["center_y"]], 500) # [x,y], dist -> indices in table
        nearby_cells = SESSION.session_cells.iloc[nearby_inds]

        # Add box around cells
        nuclei_box_coords = []
        cids = []
        for index, cell in nearby_cells.iterrows():
            x1 = int(cell["XMin"]); x2 = int(cell["XMax"])
            y1 = int(cell["YMin"]); y2 = int(cell["YMax"])
            nuclei_box_coords.append([[y1,x1] , [y2,x2]])
            cids.append(str(cell["Object Id"]))

        features = {'cid': cids}
        nb_color_str = 'black' if SESSION.absorption_mode else 'white' 
        nb_color_hex = '#000000' if SESSION.absorption_mode else '#ffffff'
        nb_text = {'string':'{cid}', 'anchor':'upper_left', 'size' : 8, 'color':nb_color_str}
        sc = (SESSION.image_scale, SESSION.image_scale) if SESSION.image_scale is not None else None
        VIEWER.add_shapes(nuclei_box_coords, name="Context Nuclei Boxes", shape_type="rectangle", edge_width=1, edge_color=nb_color_hex, 
                                            face_color='#00000000', scale=sc, features=features, text = nb_text )
        VIEWER.layers.selection.active = VIEWER.layers["Gallery Status Layer"]  
        # finally, set mode
        SESSION.mode = target_mode
        # Turn on / off the correct layers
        reuse_gamma()
        # Done. Leave function, no need to save cells
        return True 
    
    # Now, we must be changing to Gallery OR Multichannel
    if SESSION.mode == "Context":
        # If we are coming from Context Mode, just change coordinates back and restore visibility
        if target_mode == "Gallery":
            VIEWER.camera.center = SESSION.last_gallery_camera_coordinates["center"]
            VIEWER.camera.zoom = SESSION.last_gallery_camera_coordinates["z"]
        elif target_mode == "Multichannel":
            VIEWER.camera.center = SESSION.last_multichannel_camera_coordinates["center"]
            VIEWER.camera.zoom = SESSION.last_multichannel_camera_coordinates["z"]

        
        # VIEWER.layers.selection.active = VIEWER.layers["Status Layer"]
    
        SESSION.mode = target_mode
        # Change visibilities of the correct layers
        reuse_gamma()
        return True
    else:
        # Now, we are switching between Gallery and Multichannel mode. We might want to save. 
        # Save data to file from current set
        VIEWER.status = 'Saving data to file...'
        _save_validation(VIEWER, target_mode)


        print(f"Number of cells in current page is {len(SESSION.current_cells)} and type is {type(SESSION.current_cells)}")
        if target_mode == "Multichannel": # change to Show All
            VIEWER.camera.center = SESSION.last_multichannel_camera_coordinates["center"]
            VIEWER.camera.zoom = SESSION.last_multichannel_camera_coordinates["z"]
            SESSION.mode = target_mode

        elif target_mode == "Gallery": # change to composite only
            VIEWER.camera.center = SESSION.last_gallery_camera_coordinates["center"]
            VIEWER.camera.zoom = SESSION.last_gallery_camera_coordinates["z"]
            SESSION.mode = target_mode

        else:
            raise Exception(f"Invalid parameter passed to toggle_session_mode: {target_mode}. Must be 'Gallery' or 'Multichannel'.")
            # Perform adjustments before exiting function
        reuse_contrast_limits() # Only checked fluors will be visible
        reuse_gamma() 

        # set_viewer_to_neutral_zoom(VIEWER) # Fix zoomed out issue
        return True


def show_next_cell_group(page_cb_widget, single_cell_lineEdit,single_cell_combo, intensity_sort_widget):
    def _save_validation(VIEWER,numcells):
        res = userInfo._save_validation(to_disk=False)
        if res:
            VIEWER.status = f'Next {numcells} cells loaded.'
            return True
        else:
            VIEWER.status = 'There was a problem saving, so the next set of cells was not loaded. Close your data file?'
            return False
    if SESSION.mode == "Context":
        toggle_session_mode("Gallery")
        # return None # Don't allow loading of new cells when in context mode.
    # Take note of new starting point
    global PAGE_SIZE
    page_number = int(page_cb_widget.currentText().split()[-1])
    cell_choice = single_cell_lineEdit.text()

    # Ignore annotation if not in data
    if single_cell_combo:
        cell_annotation = single_cell_combo.currentText()
    else:
        cell_annotation = ''

    # Assemble dict from cell choice if needed
    if cell_choice == '': 
        cell_choice = None
    else:
        cell_choice = {"ID": cell_choice, "Annotation Layer": cell_annotation}

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


    # Load into same mode as the current
    xydata = extract_phenotype_xldata(page_number=page_number, specific_cell=cell_choice, sort_by_intensity=sort_option)
    if xydata is False:
        VIEWER.status="Can't load cells: out of bounds error."
    else:
        for layer in VIEWER.layers:
            if "Context" not in layer.name:
                VIEWER.layers.selection.add(layer)
        VIEWER.layers.remove_selected()
        # VIEWER.layers.clear()
        add_layers(VIEWER,RAW_PYRAMID, xydata, int(userInfo.imageSize/2))
    
    single_cell_lineEdit.clear() # reset the widgets
    if single_cell_combo: single_cell_combo.setCurrentIndex(0) # reset the widgets
    # Perform adjustments before exiting function
    #TODO
    reuse_contrast_limits()# Only checked fluors will be visible
    reuse_gamma() 
    set_viewer_to_neutral_zoom(VIEWER, reset_session=True) # Fix zoomed out issue
    VIEWER.layers.selection.active = VIEWER.layers["Gallery Status Layer"]  

    return None
    
# @magicgui(auto_call=True,
#         Status_Bar_Visibility={"widget_type": "RadioButtons","orientation": "vertical",
#         "choices": [("Show", 1), ("Hide", 2)]})
# def toggle_statusbar_visibility(Status_Bar_Visibility: int=1):
def toggle_statuslayer_visibility(show_widget):
    if SESSION.mode == "Context": return False
    if show_widget.isChecked(): SESSION.status_layer_vis = True
    else: SESSION.status_layer_vis = False
    # Find status layers and toggle visibility
    VIEWER.layers[f"{SESSION.mode} Status Layer"].visible = SESSION.status_layer_vis
    return True

def toggle_statusbox_visibility(show_widget):
    if SESSION.mode == "Context": return False
    if show_widget.isChecked(): SESSION.status_box_vis = True
    else: SESSION.status_box_vis = False
    # Find status layers and toggle visibility
    if SESSION.status_box_vis:
        for layer in VIEWER.layers:
            if layer.name == f'{SESSION.mode} Status Layer':
                im = layer.data
                if SESSION.mode=="Gallery":
                    mult = 1
                elif SESSION.mode=="Multichannel":
                    mult = 4
                for j in range(0,((userInfo.imageSize+2)*CELLS_PER_ROW), (userInfo.imageSize+2)):#rows
                    for i in range(0,(ceil((PAGE_SIZE*mult)/CELLS_PER_ROW)*(userInfo.imageSize+2))+1, (userInfo.imageSize+2)):#cols
                        im[i:i+1, j:j+userInfo.imageSize+2, 3] = 255 # top
                        im[i:i+userInfo.imageSize+2,j:j+1, 3] = 255 # left
                        im[i+userInfo.imageSize+1:i+userInfo.imageSize+2, j:j+userInfo.imageSize+2, 3] = 255 # right
                        im[i:i+userInfo.imageSize+2,j+userInfo.imageSize+1:j+userInfo.imageSize+2, 3] = 255 # bottom
                        if j == 0 or SESSION.mode=="Gallery":
                            im[i:i+16, j:j+16, 3] = 255

                layer.data = im
                # for col in range(1,CELLS_PER_ROW,1):
                    
    else: # Don't show box
        for layer in VIEWER.layers:
            if layer.name == f'{SESSION.mode} Status Layer':
                im = layer.data
                if SESSION.mode=="Gallery":
                    mult = 1
                elif SESSION.mode=="Multichannel":
                    mult = 4
                for j in range(0,((userInfo.imageSize+2)*CELLS_PER_ROW), (userInfo.imageSize+2)):
                    for i in range(0,(ceil((PAGE_SIZE*mult)/CELLS_PER_ROW)*(userInfo.imageSize+2))+1, (userInfo.imageSize+2)):
                        im[i:i+1, j:j+userInfo.imageSize+2, 3] = 0 # top
                        im[i:i+userInfo.imageSize+2,j:j+1, 3] = 0 # left
                        im[i+userInfo.imageSize+1:i+userInfo.imageSize+2, j:j+userInfo.imageSize+2, 3] = 0 # right
                        im[i:i+userInfo.imageSize+2,j+userInfo.imageSize+1:j+userInfo.imageSize+2, 3] = 0 # bottom
                        im[i:i+16, j:j+16, 3] = 0 # box
                layer.data = im
                # print(im.shape)
    return True

def set_notes_label(display_note_widget, ID):
    cell_num = ID.split()[-1]; cell_anno = ID.replace(' '+cell_num,'')
    if cell_anno == 'All':
        image_name = f'Cell {cell_num}'
    else:
        image_name = f'Cell {cell_num} from {cell_anno}'
    try:
        note = str(SESSION.saved_notes[ID])
    except KeyError: # in case the name was off
        return False
    status = SESSION.status_list[str(ID)]
    prefix = f'{SESSION.saved_notes["page"]}<br><font color="{STATUSES_TO_HEX[status]}">{image_name}</font>'

    # Add intensities
    intensity_series = SAVED_INTENSITIES[ID]
    names = list(intensity_series.index)
    intensity_str = ''
    for pos in CHANNELS:
        fluor = list(CHANNEL_ORDER.keys())[pos]
        if fluor == 'Composite':
            continue
        # fluor = str(cell).replace(" Cell Intensity","")
        fluor = str(fluor)
        intensity_str += f'<br><font color="{CHANNEL_ORDER[fluor].replace("blue","#0462d4")}">{fluor.replace("OPAL","Opal ")}'
        def add_values(intensity_str, fluor, intensity_lookup):
            flag = True
            name = intensity_lookup.replace("OPAL","Opal ") + ': No data'
            try:
                cyto = intensity_lookup.replace("OPAL","Opal ")
                cyto = [x for x in names if (cyto in x and 'Cytoplasm Intensity' in x)][0]
                val = round(float(intensity_series[cyto]),1)
                intensity_str += f'<font color="{CHANNEL_ORDER[fluor].replace("blue","#0462d4")}"> cyto: {val}</font>'
                flag = False
                name = cyto.replace(' Cytoplasm Intensity','')
            except (KeyError, IndexError): pass
            try:
                nuc = intensity_lookup.replace("OPAL","Opal ")
                nuc = [x for x in names if (nuc in x and 'Nucleus Intensity' in x)][0]
                val = round(float(intensity_series[nuc]),1)
                intensity_str += f'<font color="{CHANNEL_ORDER[fluor].replace("blue","#0462d4")}"> nuc: {val}</font>'
                flag = False
                name = nuc.replace(' Nucleus Intensity','')
            except (KeyError, IndexError): pass
            try:
                cell = intensity_lookup.replace("OPAL","Opal ")
                cell = [x for x in names if (cell in x and 'Cell Intensity' in x)][0]
                val = round(float(intensity_series[cell]),1)
                intensity_str += f'<font color="{CHANNEL_ORDER[fluor].replace("blue","#0462d4")}"> cell: {val}</font>'
                flag = False
                name = cell.replace(' Cell Intensity','')
            except (KeyError, IndexError): pass
            return intensity_str.replace(intensity_lookup.replace("OPAL","Opal "),name), flag
        intensity_str, error = add_values(intensity_str, fluor,fluor)
        possible_af_strings = ['AF', 'Autofluorescence', 'Sample AF']
        if error and fluor in possible_af_strings:
            possible_af_strings.remove(fluor)
            while possible_af_strings:
                new = possible_af_strings.pop()
                intensity_str, error = add_values(intensity_str,"AF", new)
                if not error: 
                    break
        # Should have something from the fluorescence column if it's there


        # intensity_str += f'<br><font color="{CHANNEL_ORDER[fluor.replace(" ","").upper()].replace("blue","#0462d4")}">{fluor} cyto: {round(float(intensity_series[cyto]),1)} nuc: {round(float(intensity_series[nuc]),1)} cell: {round(float(intensity_series[cell]),1)}</font>'
    # Add note if it exists
    if note == '-' or note == '' or note is None: 
        note = prefix + intensity_str
    else:
        note = prefix + intensity_str + f'<br><font size="5pt" color="white">{note}</font>'
    display_note_widget.setText(note)
    return True
######------------------------- Image loading and processing functions ---------------------######

def retrieve_status(cell_id, status, new_page):
    ''' Kind of an anachronistic function at this point.'''
    # print(f'Getting status for {cell_id}')
    if new_page:
        if type(status) is not str or status not in STATUS_COLORS.keys():
            status = "Unseen"
        # Save to dict to make next retrieval faster
        # If there are annotations, need to track a separate list for each one
        SESSION.status_list[str(cell_id)] = status
        return status
    else:
        # Just grab it because it's there already
        try:
            return SESSION.status_list[str(cell_id)]
        except:
            raise Exception(f"Looking for {cell_id} in the Status list dict but can't find it. List here:\n {SESSION.status_list}")

''' Expects a numpy array of shape userInfo.imageSize x 16, with a 16x16 box taking up the left-hand side'''    
def write_cid_text_to_array(cb_size, im_length, upsample, color, cid):
    if SESSION.absorption_mode: bg_color = (255,255,255,255)
    else: bg_color = (0,0,0,255)
    new = Image.new("RGBA", (int(upsample*im_length),int(upsample*cb_size)), bg_color)
    font = ImageFont.truetype("arial.ttf",48)
    editable_image = ImageDraw.Draw(new)

    # switch CID order
    i = cid.split()[-1]; anno = cid.replace(' '+i,'')
    cid = i + " " + anno
    editable_image.text((60,1), str(cid), color, font = font)
    resized = np.array(new.resize((im_length,cb_size), Image.Resampling.LANCZOS))
    # np.save("lanczos", resized)
    if SESSION.absorption_mode:
        resized[:,:,0]
        resized[:,:,3] = (255* (resized[:,:,:3] <200).any(axis=2)).astype(np.uint8)
        # resized[fade]
    else:
        resized[:,:,3] = (255* (resized[:,:,:3] >50).any(axis=2)).astype(np.uint8)
    return resized

def generate_status_box(status, cid, kind = "Gallery"):

    color_tuple = STATUSES_RGBA[status]
    # print(f'STATUSES {STATUSES_RGBA} \n status {status}, color tup {color_tuple}')
    cpr_m = SESSION.cells_per_row["Multichannel"]
    upsample = {"Multichannel" : 3.5, "Gallery": 3.5 }

    corner_box_size = 16
    edge_width = 1
    if kind=="Gallery":
        layer_length = (userInfo.imageSize+(edge_width*2))
    elif kind=="Multichannel":
        layer_length = (userInfo.imageSize+(edge_width*2)) * cpr_m
    else:
        return np.array()

    if NO_LABEL_BOX:
        number_only = write_cid_text_to_array(userInfo.imageSize+(edge_width*2), layer_length, upsample[kind], color_tuple, cid)
        return number_only

    top_or_bottom = [color_tuple, ] *layer_length
    # top_or_bottom = np.append([top_or_bottom],[top_or_bottom],axis = 0)
    x = np.array([[color_tuple, (0,0,0,0), color_tuple]])
    y = np.repeat(x,[edge_width,layer_length - (2*edge_width),edge_width],axis=1)
    mid = np.repeat(y,userInfo.imageSize+edge_width-(corner_box_size), axis=0)

    z = np.repeat(x,[corner_box_size,(layer_length-(2*edge_width))+edge_width-(corner_box_size),edge_width],axis=1)
    # above_mid = np.repeat(z,corner_box_size-edge_width, axis=0)

    top = write_cid_text_to_array(corner_box_size, layer_length, upsample[kind], color_tuple, cid)
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

def black_background(color_space, mult, CPR):
    if color_space == 'RGB':
        return np.zeros((ceil((PAGE_SIZE*mult)/CPR)*(userInfo.imageSize+2),(userInfo.imageSize+2) * CPR, 4))
    elif color_space == 'Luminescence':
        return np.zeros((ceil((PAGE_SIZE*mult)/CPR)*(userInfo.imageSize+2),(userInfo.imageSize+2) * CPR))
    
def white_background(mult, CPR): 
    a = np.tile([255,255,255,255] , (ceil((PAGE_SIZE*mult)/CPR)*(userInfo.imageSize+2),(userInfo.imageSize+2) * CPR,1))
    return a

def change_statuslayer_color(cells):
    def retrieve_status(cell_id):
        try:
            return SESSION.status_list[str(cell_id)]
        except:
            raise Exception(f"Looking for {cell_id} in the Status list dict but can't find it. List here:\n {SESSION.status_list}")


    # Starting to add
    if SESSION.mode=="Gallery": 
        page_status_layer = black_background('RGB',1, userInfo.cells_per_row)
    elif SESSION.mode=="Multichannel": 
        page_status_layer = black_background('RGB',SESSION.cells_per_row["Multichannel"],SESSION.cells_per_row["Multichannel"])
        
    

    col = 0
    row = 0
    cells = list(cells.values())
    while bool(cells): # coords left
        col = (col%CELLS_PER_ROW)+1
        if col ==1: row+=1 
        cell = cells.pop(); 
        cell_anno = cell['Layer']; cell_id = cell['cid']
        cell_status = retrieve_status(cell_anno +' '+ str(cell_id))
        for pos, fluor in enumerate(CHANNEL_ORDER): # loop through channels
            if pos in CHANNELS and fluor != 'Composite':
                if SESSION.mode=="Multichannel": # Only add channels if we are in 'show all' mode. Otherwise only composite will show up
                    if col ==1:
                        page_status_layer[(row-1)*(userInfo.imageSize+2):row*(userInfo.imageSize+2),:] = generate_status_box(cell_status, cell_anno +' '+ str(cell_id), "Multichannel")
                    col+=1 # so that next luminescence image is tiled 
                    continue
                elif SESSION.mode=="Gallery": # This stuff is only necessary in composite mode 
                   page_status_layer[(row-1)*(userInfo.imageSize+2):row*(userInfo.imageSize+2), (col-1)*(userInfo.imageSize+2):col*(userInfo.imageSize+2)] = generate_status_box(cell_status, cell_anno +' '+ str(cell_id))
    
    # if composite_only:
    VIEWER.layers[f'{SESSION.mode} Status Layer'].data = page_status_layer.astype(np.uint8)

''' Add images layers for Gallery and Multichannel modes. Only make visible the layers for the active mode'''
def add_layers(viewer,pyramid, cells, offset, new_page=True):
    print(f'\n---------\n \n Entering the add_layers function')
    print(f"pyramid shape is {pyramid.shape}")
    # Make the color bar that appears to the left of the composite image
    status_colors = STATUS_COLORS
  
    SESSION.cells_per_row["Multichannel"] = len(userInfo.channels) + 1
    SESSION.cells_per_row["Gallery"] = userInfo.cells_per_row
    cpr_g = SESSION.cells_per_row["Gallery"]
    cpr_m = SESSION.cells_per_row["Multichannel"]


    # Starting to add
    SESSION.page_status_layers["Gallery"] = black_background('RGB', 1, userInfo.cells_per_row)
    SESSION.page_status_layers["Multichannel"] = black_background('RGB',cpr_m, cpr_m)

    print(f"Shapes are {SESSION.page_status_layers['Multichannel'].shape}  || {SESSION.page_status_layers['Gallery'].shape}")
    page_image_multichannel = {} ; page_image_gallery = {}
    for chn in CHANNELS_STR:
        if chn == 'Composite':
            pass
        else:
            page_image_gallery[chn] = black_background('Luminescence', 1, userInfo.cells_per_row)
            page_image_multichannel[chn] = black_background('Luminescence', cpr_m, cpr_m)

    # page_image = black_background('RGB',size_multiplier)

    nuclei_box_coords_g = []
    nuclei_box_coords_m = []
    print(f'Adding {len(cells)} cells to viewer... Channels are {CHANNELS} // {CHANNELS_STR}')
    col_g = 0 
    row_g = 0 ; row_m = 0
    SESSION.grid_to_ID = {"Gallery":{}, "Multichannel":{}} # Reset this since we could be changing to multichannel mode
    cells = list(cells.values())
    cid_list = []
    while bool(cells): # coords left
        col_g = (col_g%cpr_g)+1 
        if col_g ==1: row_g+=1
        col_m = 1 ;  row_m+=1 

        # print(f'Next round of while. Still {len(cells)} cells left. G Row {row_g}, Col {col_g} || M Row {row_m}, Col {col_m}')
        cell = cells.pop(); 
        cell_anno = cell["Layer"]; cell_id = cell['cid']; cell_x = cell['center_x']; cell_y = cell['center_y']
        cell_status = retrieve_status(cell_anno +' '+ str(cell_id),cell['validation_call'], new_page)
        cid_list.append(cell_id)
        # add the rest of the layers to the viewer
        if RASTERS is not None:
            # Raster channels for qptiffs are saved as subdatasets of the opened raster object
            num_channels = len(RASTERS) 
        else:
            num_channels = pyramid.shape[2] # Data is [X,Y,C]

        x1 = int(cell["XMin"] + offset - cell_x) ; x2 = int(cell["XMax"] + offset - cell_x)
        y1 = int(cell["YMin"] + offset - cell_y) ; y2 = int(cell["YMax"] + offset - cell_y)
        cXg = (row_g-1)*(userInfo.imageSize+2) ; cYg = (col_g-1)*(userInfo.imageSize+2)
        cXm = (row_m-1)*(userInfo.imageSize+2) ; cYm = len(userInfo.channels)*(userInfo.imageSize+2)

        nuclei_box_coords_g.append([[cXg+y1, cYg+x1], [cXg+y2, cYg+x2]]) # x and y are actually flipped between napari and the object data
        nuclei_box_coords_m.append([[cXm+y1, cYm+x1], [cXm+y2, cYm+x2]]) 

        for pos, fluor in enumerate(CHANNEL_ORDER): # loop through channels
            if pos in CHANNELS and fluor != 'Composite':
                # name cell layer
                cell_name = f'Cell {cell_id} {fluor}'

                # print(f'Testing if raster used: {RASTERS}') # YES can see subdatasets.
                if RASTERS is not None:
                    with rasterio.open(RASTERS[pos]) as channel:
                        cell_punchout = channel.read(1,window=Window(cell_x-offset,cell_y-offset, offset*2,offset*2)).astype(np.uint8)
                else:
                    # rasterio reading didn't work, so entire image should be in memory as np array
                    cell_punchout = pyramid[cell_x-offset:cell_x+offset,cell_y-offset:cell_y+offset,pos].astype(np.uint8)
                # print(f'Trying to add {cell_name} layer with fluor-color(cm):{fluor}-{CHANNEL_ORDER[fluor]}')

                
                # multichannel mode: individual image
                page_image_multichannel[fluor][(row_m-1)*(userInfo.imageSize+2)+1:row_m*(userInfo.imageSize+2)-1,
                            (col_m-1)*(userInfo.imageSize+2)+1:col_m*(userInfo.imageSize+2)-1] = cell_punchout
                # multichannel mode: composite image
                page_image_multichannel[fluor][(row_m-1)*(userInfo.imageSize+2)+1:row_m*(userInfo.imageSize+2)-1,
                            (cpr_m-1)*(userInfo.imageSize+2)+1:cpr_m*(userInfo.imageSize+2)-1] = cell_punchout
                SESSION.grid_to_ID["Multichannel"][f'{row_m},{col_m}'] = cell_anno + ' ' + str(cell_id)
                SESSION.grid_to_ID["Multichannel"][f'{row_m},{cpr_m}'] = cell_anno + ' ' + str(cell_id)
                if col_m ==1:
                    SESSION.page_status_layers["Multichannel"][(row_m-1)*(userInfo.imageSize+2):row_m*(userInfo.imageSize+2),:] = generate_status_box(cell_status, cell_anno +' '+ str(cell_id), "Multichannel")
                col_m+=1 # so that next luminescence image is tiled 
                

                # Gallery images 
                SESSION.grid_to_ID["Gallery"][f'{row_g},{col_g}'] = cell_anno + ' ' + str(cell_id)
                page_image_gallery[fluor][(row_g-1)*(userInfo.imageSize+2)+1:row_g*(userInfo.imageSize+2)-1, (col_g-1)*(userInfo.imageSize+2)+1:col_g*(userInfo.imageSize+2)-1] = cell_punchout
                SESSION.page_status_layers["Gallery"][(row_g-1)*(userInfo.imageSize+2):row_g*(userInfo.imageSize+2), (col_g-1)*(userInfo.imageSize+2):col_g*(userInfo.imageSize+2)] = generate_status_box(cell_status, cell_anno +' '+ str(cell_id), "Gallery")
    

    gal_vis = True if SESSION.mode == "Gallery" else False
    mult_vis = not gal_vis
    print(f"\nMy scale is {SESSION.image_scale}")
    sc = (SESSION.image_scale, SESSION.image_scale) if SESSION.image_scale is not None else None
    viewer.add_image(white_background(1, userInfo.cells_per_row).astype(np.uint8), name = "Gallery Absorption", 
                                                  blending = 'translucent', visible = SESSION.absorption_mode and gal_vis, scale =sc )
    viewer.add_image(white_background(cpr_m, cpr_m).astype(np.uint8), name = "Multichannel Absorption", 
                                                  blending = 'translucent', visible = SESSION.absorption_mode and mult_vis, scale =sc )
    for fluor in list(page_image_gallery.keys()):
        print(f"Adding layers now. fluor is {fluor}")
        if fluor == 'Composite':
            continue # The merged composite consists of each layer's pixels blended together, so there is no composite layer itself
        if SESSION.absorption_mode:
            viewer.add_image(page_image_gallery[fluor], name = f"Gallery {fluor}", blending = 'minimum',
                 colormap = custom_maps.retrieve_cm(CHANNEL_ORDER[fluor]+' inverse'), scale = sc, interpolation="linear", visible =gal_vis)
            viewer.add_image(page_image_multichannel[fluor], name = f"Multichannel {fluor}", blending = 'minimum',
                 colormap = custom_maps.retrieve_cm(CHANNEL_ORDER[fluor]+' inverse'), scale = sc, interpolation="linear", visible=mult_vis)
            
        else:
            viewer.add_image(page_image_gallery[fluor], name = f"Gallery {fluor}", blending = 'additive',
                 colormap = custom_maps.retrieve_cm(CHANNEL_ORDER[fluor]), scale = sc, interpolation="linear", visible=gal_vis)
            viewer.add_image(page_image_multichannel[fluor], name = f"Multichannel {fluor}", blending = 'additive',
                 colormap = custom_maps.retrieve_cm(CHANNEL_ORDER[fluor]), scale = sc, interpolation="linear", visible=mult_vis)
    # if composite_only:

    features = {'cid': cid_list}
    nb_color_str = 'black' if SESSION.absorption_mode else 'white' 
    nb_color_hex = '#000000' if SESSION.absorption_mode else '#ffffff'
    nb_text = {'string':'{cid}', 'anchor':'upper_left', 'size' : 8, 'color':nb_color_str}
    viewer.add_shapes(nuclei_box_coords_g, name="Gallery Nuclei Boxes", shape_type="rectangle", edge_width=1, edge_color=nb_color_hex, 
                                        face_color='#00000000', scale=sc, features=features, text = nb_text, visible=False)
    viewer.add_shapes(nuclei_box_coords_m, name="Multichannel Nuclei Boxes", shape_type="rectangle", edge_width=1, edge_color=nb_color_hex, 
                                        face_color='#00000000', scale=sc, features=features, text = nb_text, visible = False)
    viewer.add_image(SESSION.page_status_layers["Gallery"].astype(np.uint8), name='Gallery Status Layer', interpolation='linear', scale = sc, visible=gal_vis)
    viewer.add_image(SESSION.page_status_layers["Multichannel"].astype(np.uint8), name='Multichannel Status Layer', interpolation='linear', scale = sc, visible=mult_vis)
    # viewer.layers.selection.active = viewer.layers["Status Layer"]

    VIEWER.layers.selection.active = VIEWER.layers["Gallery Status Layer"]  
    

    #TODO make a page label... 

    # Exiting add_layers function

    return True

def attach_functions_to_viewer(viewer):

    ##----------------- Live functions that control mouseover behavior on images 
    status_colors = STATUS_COLORS

    '''Take a pixel coordinate (y,x) and return an (x,y) position for the image that contains the pixel in the image grid'''
    def pixel_coord_to_grid(coords):
        x = coords[0]; y = coords[1]
        # sc = 1 if SESSION.image_scale is None else SESSION.image_scale
        # Cannot return 0 this way, since there is no 0 row or col
        row_num = max(ceil((x+1)/(userInfo.imageSize+2)),1)
        col_num = max(ceil((y+1)/(userInfo.imageSize+2)),1)
        return row_num, col_num
    
    def multichannel_fetch_val(local_x,global_y, fluor):
        offset_x = (userInfo.imageSize+2) * list(CHANNELS_STR).index(fluor)
        return (global_y, offset_x+local_x)
    

    '''Locate mouse on the canvas. Returns the name of the cell under the mouse, current mouse 
        coordinates, and pixel values for each channel in a dict'''
    def find_mouse(data_coordinates, scope = 'world'):
   
                # retrieve cell ID name
        # Scale data coordinates to image. Then round to nearest int, representing the coord or the image pixel under the mouse
        sc = 1.0 if SESSION.image_scale is None else SESSION.image_scale
        data_coordinates = tuple([x/sc for x in data_coordinates])
        coords = np.round(data_coordinates).astype(int)
        vals = {} # will hold fluor : pixel intensity pairs 

        if coords[0] < 0 or coords[1]<0:
            if SESSION.mode == "Context": return {"cell":None,"coords": None,"vals": None}
            return "None" , None, None
        if SESSION.mode == "Context":
            for fluor in CHANNELS_STR:
                if fluor == "Composite": continue
                # get_value returns a tuple here, where the first number is the image layer in the pyramid. Discard that
                v = VIEWER.layers["Context "+fluor].get_value(data_coordinates)
                vals[fluor] =  v[1] if v is not None else "-"
            
            # Now find the name of the closest cell 
            dist, closest_ind = SESSION.kdtree.query([data_coordinates[1],data_coordinates[0]])
            if dist < 1.5*userInfo.imageSize:
                closest_cell = SESSION.session_cells.iloc[closest_ind]
            else:
                closest_cell = None
            return {"cell":closest_cell,"coords": (coords[1],coords[0]),"vals": vals} # flips axes of coordinates
        else: # Gallery mode or Multichannel mode    
            row,col = pixel_coord_to_grid(coords)
            try:
                image_name = SESSION.grid_to_ID[SESSION.mode][f'{row},{col}']
            except KeyError as e:
                return "None" , None, None
            
            local_x = coords[1] - (userInfo.imageSize+2)*(col-1)
            local_y = coords[0] - (userInfo.imageSize+2)*(row-1)
            for fluor in CHANNELS_STR:
                if fluor == "Composite": continue
                # Context mode already taken care of. Need to handle Gallery / Multichannel 
                if SESSION.mode=="Multichannel":
                    # print(f"data coords: {data_coordinates}  | vs assumed coords for {fluor}: {multichannel_fetch_val(local_x, data_coordinates[0], fluor)}")
                    vals[fluor] = VIEWER.layers[f"Multichannel {fluor}"].get_value(multichannel_fetch_val(local_x, data_coordinates[0], fluor))
                elif SESSION.mode=="Gallery":
                    vals[fluor] = VIEWER.layers[f"Gallery {fluor}"].get_value(data_coordinates)
                if vals[fluor] is None:
                    vals[fluor] = "-"

            # return either global or local (relative to punchout) coordinates
            if scope == 'world':
                return str(image_name), coords, vals
            else:
                return str(image_name), (local_x,local_y), vals

    @viewer.mouse_move_callbacks.append
    def display_intensity(viewer, event):
        
        if SESSION.mode == "Context":
            kw_res = find_mouse(event.position)
            cell = kw_res["cell"]
            coords = kw_res["coords"]
            vals = kw_res["vals"]
            # import pickle
            # with open("cell_tup.pkl","wb") as f:
            #     pickle.dump(cell_tup,f)
            # exit()
            if (vals is None) or (next(iter(vals.values())) is None):
                # Don't do anything else - the cursor is out of bounds of the image
                VIEWER.status = 'Out of bounds'
                return True 
            
            if cell is not None:
                cid = cell["Object Id"]
                layer = cell["Analysis Region"] if ANNOTATIONS_PRESENT else "All"
                ckey = f'{layer} {cid}'
                try:
                    cell_dict = SESSION.current_cells[ckey]
                except KeyError:
                    fetch_notes(cell, SESSION.intensity_columns)
                    center_x = int((cell['XMax']+cell['XMin'])/2)
                    center_y = int((cell['YMax']+cell['YMin'])/2)
                    vcs = cell[SESSION.validation_columns]
                    validation_call = str(vcs[vcs == 1].index.values[0]).replace(f"Validation | ", "")

                    cell_dict = {'Layer':layer,"cid": cid,"center_x": center_x,'center_y': center_y,
                                            'validation_call': validation_call, 'XMax' : cell['XMax'],'XMin':cell['XMin'],
                                            'YMax' : cell['YMax'],'YMin':cell['YMin']}
                    
                    SESSION.current_cells[ckey] = cell_dict
                    SESSION.status_list[ckey] = validation_call
                    fetch_notes(cell, SESSION.intensity_columns)
                # Now that we have the cell dict, proceed to display
                SESSION.cell_under_mouse =  cell_dict # save info
                set_notes_label(ALL_CUSTOM_WIDGETS['notes label'], ckey)
                

            # print(f"Vals is type {type(vals)} and content is {vals}")
            # exit()
            # Deal with pixel intensities
            
            output_str = ''
            for fluor, val in vals.items():
                if val != "-": val = int(val)
                output_str+= f'<font color="{CHANNEL_ORDER[fluor].replace("blue","#0462d4")}">    {val}   </font>'
            sc = STATUSES_TO_HEX[SESSION.status_list[str(ckey)]] if cell is not None else "#ffffff"
            VIEWER.status = f'<font color="{sc}">Context Mode</font> pixel intensities at {coords}: {output_str}'
        elif SESSION.mode == "Gallery" or SESSION.mode == "Multichannel":
            cell_name,coords,vals = find_mouse(event.position, scope = 'grid') 
            if vals is None:
                # Don't do anything else
                VIEWER.status = 'Out of bounds'
                return True
            SESSION.cell_under_mouse = SESSION.current_cells[cell_name] # save info
            cell_num = cell_name.split()[-1]; cell_anno = cell_name.replace(' '+cell_num,'')

            if cell_anno == 'All':
                image_name = f'Cell {cell_num}'
            else:
                image_name = f'Cell {cell_num} from {cell_anno}'

            set_notes_label(ALL_CUSTOM_WIDGETS['notes label'], str(cell_name))
            output_str = ''

            for fluor, val in vals.items():
                if val != "-": val = int(val)
                output_str+= f'<font color="{CHANNEL_ORDER[fluor].replace("blue","#0462d4")}">    {val}   </font>'
        
            sc = STATUSES_TO_HEX[SESSION.status_list[str(cell_name)]]
            VIEWER.status = f'<font color="{sc}">{image_name}</font> intensities at {coords}: {output_str}'

    @viewer.bind_key('j')
    @viewer.bind_key('Space', overwrite = True)
    @viewer.bind_key('Ctrl-Space', overwrite = True)
    def toggle_status(viewer):
        
        if SESSION.mode == "Context": 
            cell = SESSION.cell_under_mouse
            if cell is None:
                return False # leave if the mouse is not near a cell (not sure that this could even happen)
            cell_name = f"{cell['Layer']} {cell['cid']}"
            
        else:
            cell_name,data_coordinates,val = find_mouse(viewer.cursor.position)
            if val is None:
                return None

        cur_status = SESSION.status_list[str(cell_name)]
        cur_index = list(status_colors.keys()).index(cur_status)
        next_status = list(status_colors.keys())[(cur_index+1)%len(status_colors)]
        SESSION.status_list[str(cell_name)] = next_status
        set_notes_label(ALL_CUSTOM_WIDGETS['notes label'], str(cell_name)) 

        # Change gallery mode status layer
        try:
            row, col = list(SESSION.grid_to_ID["Gallery"].keys())[list(SESSION.grid_to_ID["Gallery"].values()).index(cell_name)].split(",")
            row, col = (int(row),int(col))
            imdata = viewer.layers["Gallery Status Layer"].data
            imdata[(row-1)*(userInfo.imageSize+2):row*(userInfo.imageSize+2), 
                            (col-1)*(userInfo.imageSize+2):col*(userInfo.imageSize+2)] = generate_status_box(next_status,str(cell_name), "Gallery")
            viewer.layers["Gallery Status Layer"].data = imdata.astype('int')

            # Change multichannel mode status layer
            row, col = list(SESSION.grid_to_ID["Multichannel"].keys())[list(SESSION.grid_to_ID["Multichannel"].values()).index(cell_name)].split(",")
            row, col = (int(row),int(col))
            imdata = viewer.layers["Multichannel Status Layer"].data
            imdata[(row-1)*(userInfo.imageSize+2):row*(userInfo.imageSize+2),
                :] = generate_status_box(next_status,str(cell_name), "Multichannel")
            viewer.layers["Multichannel Status Layer"].data = imdata.astype('int')
        except (KeyError, ValueError):
            # Changing a cell status that isn't in the current page using Context Mode.
            pass 
        # change color of viewer status
        vstatus_list = copy.copy(VIEWER.status).split('>')
        vstatus_list[0] = sub(r'#.{6}',STATUSES_TO_HEX[SESSION.status_list[str(cell_name)]], vstatus_list[0])
        VIEWER.status = ">".join(vstatus_list)

    @viewer.mouse_drag_callbacks.append
    def trigger_toggle_status(viewer, event):
        #TODO decide on the behavior for clicking on a cell
        
        # Allow user to click on a cell to get it's name into the entry box  
        widget = ALL_CUSTOM_WIDGETS['notes cell entry']
        # cell_name,data_coordinates,val = find_mouse(viewer.cursor.position)
        widget.setText(f"{SESSION.cell_under_mouse['Layer']} {SESSION.cell_under_mouse['cid']}")

        if SESSION.mode == "Context":
            pgc = ALL_CUSTOM_WIDGETS['page cell layer']
            pgc.setCurrentText(SESSION.cell_under_mouse['Layer'])
            pge = ALL_CUSTOM_WIDGETS['page cell id']
            pge.setText(str(SESSION.cell_under_mouse['cid']))



    @viewer.bind_key('Control-c')
    @viewer.bind_key('Shift-c')
    def set_all_unseen(viewer):
        if SESSION.mode == "Context": return None
        next_status = 'Unseen'

        # set all cells to status
        for coords, cell_id in SESSION.grid_to_ID[SESSION.mode].items():
            SESSION.status_list[str(cell_id)] = next_status
            row = int(coords.split(',')[0])
            col = int(coords.split(',')[1])

            if SESSION.mode=="Gallery": 
                imdata = viewer.layers["Gallery Status Layer"].data
                imdata[(row-1)*(userInfo.imageSize+2):row*(userInfo.imageSize+2), 
                                (col-1)*(userInfo.imageSize+2):col*(userInfo.imageSize+2)] = generate_status_box(next_status,str(cell_id), SESSION.mode)
                viewer.layers["Gallery Status Layer"].data = imdata.astype('int')
            elif SESSION.mode=="Multichannel":
                imdata = viewer.layers["Multichannel Status Layer"].data
                imdata[(row-1)*(userInfo.imageSize+2):row*(userInfo.imageSize+2),
                    :] = generate_status_box(next_status,str(cell_id), SESSION.mode)
                viewer.layers["Multichannel Status Layer"].data = imdata.astype('int')

        cell_name,data_coordinates,val = find_mouse(viewer.cursor.position)
        if val is None:
            return None
        set_notes_label(ALL_CUSTOM_WIDGETS['notes label'], str(cell_name))
        vstatus_list = copy.copy(VIEWER.status).split('>')
        vstatus_list[0] = sub(r'#.{6}',STATUSES_TO_HEX[SESSION.status_list[str(cell_name)]], vstatus_list[0])
        VIEWER.status = ">".join(vstatus_list)
 
    @viewer.bind_key('c')
    def set_unseen(viewer):
        if SESSION.mode == "Context": return None
        next_status = 'Unseen'
        cell_name,data_coordinates,val = find_mouse(viewer.cursor.position)
        if val is None:
            return None
        coords = np.round(data_coordinates).astype(int)
        row,col = pixel_coord_to_grid(coords)
        SESSION.status_list[str(cell_name)] = next_status
        set_notes_label(ALL_CUSTOM_WIDGETS['notes label'], str(cell_name)) 


        if SESSION.mode=="Gallery": 
            imdata = viewer.layers["Gallery Status Layer"].data
            imdata[(row-1)*(userInfo.imageSize+2):row*(userInfo.imageSize+2), 
                              (col-1)*(userInfo.imageSize+2):col*(userInfo.imageSize+2)] = generate_status_box(next_status,str(cell_name), SESSION.mode)
            viewer.layers["Gallery Status Layer"].data = imdata.astype('int')
        elif SESSION.mode=="Multichannel":
            imdata = viewer.layers["Multichannel Status Layer"].data
            imdata[(row-1)*(userInfo.imageSize+2):row*(userInfo.imageSize+2),
                :] = generate_status_box(next_status,str(cell_name), SESSION.mode)
            viewer.layers["Multichannel Status Layer"].data = imdata.astype('int')
        # change color of viewer status
        vstatus_list = copy.copy(VIEWER.status).split('>')
        vstatus_list[0] = sub(r'#.{6}',STATUSES_TO_HEX[SESSION.status_list[str(cell_name)]], vstatus_list[0])
        VIEWER.status = ">".join(vstatus_list)

    @viewer.bind_key('Control-v')
    @viewer.bind_key('Shift-v')
    def set_all_nr(viewer):
        if SESSION.mode == "Context": return None
        next_status = 'Needs review'

        # set all cells to status
        for coords, cell_id in SESSION.grid_to_ID[SESSION.mode].items():
            SESSION.status_list[str(cell_id)] = next_status
            row = int(coords.split(',')[0])
            col = int(coords.split(',')[1])

            if SESSION.mode=="Gallery": 
                imdata = viewer.layers["Gallery Status Layer"].data
                imdata[(row-1)*(userInfo.imageSize+2):row*(userInfo.imageSize+2), 
                                (col-1)*(userInfo.imageSize+2):col*(userInfo.imageSize+2)] = generate_status_box(next_status,str(cell_id), SESSION.mode)
                viewer.layers["Gallery Status Layer"].data = imdata.astype('int')
            elif SESSION.mode=="Multichannel":
                imdata = viewer.layers["Multichannel Status Layer"].data
                imdata[(row-1)*(userInfo.imageSize+2):row*(userInfo.imageSize+2),
                    :] = generate_status_box(next_status,str(cell_id), SESSION.mode)
                viewer.layers["Multichannel Status Layer"].data = imdata.astype('int')

        cell_name,data_coordinates,val = find_mouse(viewer.cursor.position)
        if val is None:
            return None
        set_notes_label(ALL_CUSTOM_WIDGETS['notes label'], str(cell_name))
        vstatus_list = copy.copy(VIEWER.status).split('>')
        vstatus_list[0] = sub(r'#.{6}',STATUSES_TO_HEX[SESSION.status_list[str(cell_name)]], vstatus_list[0])
        VIEWER.status = ">".join(vstatus_list)

    @viewer.bind_key('v')
    def set_nr(viewer):
        if SESSION.mode == "Context": return None
        next_status = 'Needs review'
        cell_name,data_coordinates,val = find_mouse(viewer.cursor.position)
        if val is None:
            return None
        coords = np.round(data_coordinates).astype(int)
        row,col = pixel_coord_to_grid(coords)
        SESSION.status_list[str(cell_name)] = next_status
        set_notes_label(ALL_CUSTOM_WIDGETS['notes label'], str(cell_name)) 

        if SESSION.mode=="Gallery": 
            imdata = viewer.layers["Gallery Status Layer"].data
            imdata[(row-1)*(userInfo.imageSize+2):row*(userInfo.imageSize+2), 
                              (col-1)*(userInfo.imageSize+2):col*(userInfo.imageSize+2)] = generate_status_box(next_status,str(cell_name), SESSION.mode)
            viewer.layers["Gallery Status Layer"].data = imdata.astype('int')

        elif SESSION.mode=="Multichannel":
            imdata = viewer.layers["Multichannel Status Layer"].data
            imdata[(row-1)*(userInfo.imageSize+2):row*(userInfo.imageSize+2),
                :] = generate_status_box(next_status,str(cell_name), SESSION.mode)
            viewer.layers["Multichannel Status Layer"].data = imdata.astype('int')

        # change color of viewer status
        vstatus_list = copy.copy(VIEWER.status).split('>')
        vstatus_list[0] = sub(r'#.{6}',STATUSES_TO_HEX[SESSION.status_list[str(cell_name)]], vstatus_list[0])
        VIEWER.status = ">".join(vstatus_list)

    @viewer.bind_key('Control-b')
    @viewer.bind_key('Shift-b')
    def set_all_confirmed(viewer):
        if SESSION.mode == "Context": return None
        next_status = 'Confirmed'

        # set all cells to status
        for coords, cell_id in SESSION.grid_to_ID[SESSION.mode].items():
            SESSION.status_list[str(cell_id)] = next_status
            row = int(coords.split(',')[0])
            col = int(coords.split(',')[1])

            if SESSION.mode=="Gallery": 
                imdata = viewer.layers["Gallery Status Layer"].data
                imdata[(row-1)*(userInfo.imageSize+2):row*(userInfo.imageSize+2), 
                                (col-1)*(userInfo.imageSize+2):col*(userInfo.imageSize+2)] = generate_status_box(next_status,str(cell_id), SESSION.mode)
                viewer.layers["Gallery Status Layer"].data = imdata.astype('int')

            elif SESSION.mode=="Multichannel":
                imdata = viewer.layers["Multichannel Status Layer"].data
                imdata[(row-1)*(userInfo.imageSize+2):row*(userInfo.imageSize+2),
                    :] = generate_status_box(next_status,str(cell_id), SESSION.mode)
                viewer.layers["Multichannel Status Layer"].data = imdata.astype('int')

        cell_name,data_coordinates,val = find_mouse(viewer.cursor.position)
        if val is None:
            return None
        set_notes_label(ALL_CUSTOM_WIDGETS['notes label'], str(cell_name))
        vstatus_list = copy.copy(VIEWER.status).split('>')
        vstatus_list[0] = sub(r'#.{6}',STATUSES_TO_HEX[SESSION.status_list[str(cell_name)]], vstatus_list[0])
        VIEWER.status = ">".join(vstatus_list)

    @viewer.bind_key('b')
    def set_confirmed(viewer):
        if SESSION.mode == "Context": return None
        next_status = 'Confirmed'
        cell_name,data_coordinates,val = find_mouse(viewer.cursor.position)
        if val is None:
            return None
        coords = np.round(data_coordinates).astype(int)
        row,col = pixel_coord_to_grid(coords)
        SESSION.status_list[str(cell_name)] = next_status
        set_notes_label(ALL_CUSTOM_WIDGETS['notes label'], str(cell_name)) 

        if SESSION.mode=="Gallery": 
            imdata = viewer.layers["Gallery Status Layer"].data
            imdata[(row-1)*(userInfo.imageSize+2):row*(userInfo.imageSize+2), 
                              (col-1)*(userInfo.imageSize+2):col*(userInfo.imageSize+2)] = generate_status_box(next_status,str(cell_name), SESSION.mode)
            viewer.layers["Gallery Status Layer"].data = imdata.astype('int')

        elif SESSION.mode=="Multichannel":
            imdata = viewer.layers["Multichannel Status Layer"].data
            imdata[(row-1)*(userInfo.imageSize+2):row*(userInfo.imageSize+2),
                :] = generate_status_box(next_status,str(cell_name), SESSION.mode)
            viewer.layers["Multichannel Status Layer"].data = imdata.astype('int')
        # change color of viewer status
        vstatus_list = copy.copy(VIEWER.status).split('>')
        vstatus_list[0] = sub(r'#.{6}',STATUSES_TO_HEX[SESSION.status_list[str(cell_name)]], vstatus_list[0])
        VIEWER.status = ">".join(vstatus_list)

    @viewer.bind_key('Control-n')
    @viewer.bind_key('Shift-n')
    def set_all_rejected(viewer):
        if SESSION.mode == "Context": return None
        next_status = 'Rejected'

        # set all cells to status
        for coords, cell_id in SESSION.grid_to_ID[SESSION.mode].items():
            SESSION.status_list[str(cell_id)] = next_status
            row = int(coords.split(',')[0])
            col = int(coords.split(',')[1])

            if SESSION.mode=="Gallery": 
                imdata = viewer.layers["Gallery Status Layer"].data
                imdata[(row-1)*(userInfo.imageSize+2):row*(userInfo.imageSize+2), 
                                (col-1)*(userInfo.imageSize+2):col*(userInfo.imageSize+2)] = generate_status_box(next_status,str(cell_id), SESSION.mode)
                viewer.layers["Gallery Status Layer"].data = imdata.astype('int')
            elif SESSION.mode=="Multichannel":
                imdata = viewer.layers["Multichannel Status Layer"].data
                imdata[(row-1)*(userInfo.imageSize+2):row*(userInfo.imageSize+2),
                    :] = generate_status_box(next_status,str(cell_id), SESSION.mode)
            viewer.layers["Multichannel Status Layer"].data = imdata.astype('int')

        cell_name,data_coordinates,val = find_mouse(viewer.cursor.position)
        if val is None:
            return None
        set_notes_label(ALL_CUSTOM_WIDGETS['notes label'], str(cell_name))
        vstatus_list = copy.copy(VIEWER.status).split('>')
        vstatus_list[0] = sub(r'#.{6}',STATUSES_TO_HEX[SESSION.status_list[str(cell_name)]], vstatus_list[0])
        VIEWER.status = ">".join(vstatus_list)

    @viewer.bind_key('n')
    def set_rejected(viewer):
        if SESSION.mode == "Context": return None
        next_status = 'Rejected'
        cell_name,data_coordinates,val = find_mouse(viewer.cursor.position)
        if val is None:
            return None
        coords = np.round(data_coordinates).astype(int)
        row,col = pixel_coord_to_grid(coords)
        SESSION.status_list[str(cell_name)] = next_status
        set_notes_label(ALL_CUSTOM_WIDGETS['notes label'], str(cell_name)) 

        if SESSION.mode=="Gallery": 
            imdata = viewer.layers["Gallery Status Layer"].data
            imdata[(row-1)*(userInfo.imageSize+2):row*(userInfo.imageSize+2), 
                              (col-1)*(userInfo.imageSize+2):col*(userInfo.imageSize+2)] = generate_status_box(next_status,str(cell_name), SESSION.mode)
            viewer.layers["Gallery Status Layer"].data = imdata.astype('int')

        elif SESSION.mode=="Multichannel":
            imdata = viewer.layers["Multichannel Status Layer"].data
            imdata[(row-1)*(userInfo.imageSize+2):row*(userInfo.imageSize+2),
                :] = generate_status_box(next_status,str(cell_name), SESSION.mode)
            viewer.layers["Multichannel Status Layer"].data = imdata.astype('int')
        # change color of viewer status
        vstatus_list = copy.copy(VIEWER.status).split('>')
        vstatus_list[0] = sub(r'#.{6}',STATUSES_TO_HEX[SESSION.status_list[str(cell_name)]], vstatus_list[0])
        VIEWER.status = ">".join(vstatus_list)

    @viewer.bind_key('Control-m')
    @viewer.bind_key('Shift-m')
    def set_all_interesting(viewer):
        if SESSION.mode == "Context": return None
        next_status = 'Interesting'

        # set all cells to status
        for coords, cell_id in SESSION.grid_to_ID[SESSION.mode].items():
            SESSION.status_list[str(cell_id)] = next_status
            row = int(coords.split(',')[0])
            col = int(coords.split(',')[1])

            if SESSION.mode=="Gallery": 
                imdata = viewer.layers["Gallery Status Layer"].data
                imdata[(row-1)*(userInfo.imageSize+2):row*(userInfo.imageSize+2), 
                                (col-1)*(userInfo.imageSize+2):col*(userInfo.imageSize+2)] = generate_status_box(next_status,str(cell_id), SESSION.mode)
                viewer.layers["Gallery Status Layer"].data = imdata.astype('int')

            elif SESSION.mode=="Multichannel":
                imdata = viewer.layers["Multichannel Status Layer"].data
                imdata[(row-1)*(userInfo.imageSize+2):row*(userInfo.imageSize+2),
                    :] = generate_status_box(next_status,str(cell_id), SESSION.mode)
                viewer.layers["Multichannel Status Layer"].data = imdata.astype('int')

        cell_name,data_coordinates,val = find_mouse(viewer.cursor.position)
        if val is None:
            return None
        set_notes_label(ALL_CUSTOM_WIDGETS['notes label'], str(cell_name))
        vstatus_list = copy.copy(VIEWER.status).split('>')
        vstatus_list[0] = sub(r'#.{6}',STATUSES_TO_HEX[SESSION.status_list[str(cell_name)]], vstatus_list[0])
        VIEWER.status = ">".join(vstatus_list)


    @viewer.bind_key('m')
    def set_interesting(viewer):
        if SESSION.mode == "Context": return None
        next_status = 'Interesting'
        cell_name,data_coordinates,val = find_mouse(viewer.cursor.position)
        if val is None:
            return None
        coords = np.round(data_coordinates).astype(int)
        row,col = pixel_coord_to_grid(coords)
        SESSION.status_list[str(cell_name)] = next_status
        set_notes_label(ALL_CUSTOM_WIDGETS['notes label'], str(cell_name)) 

        if SESSION.mode=="Gallery": 
            imdata = viewer.layers["Gallery Status Layer"].data
            imdata[(row-1)*(userInfo.imageSize+2):row*(userInfo.imageSize+2), 
                              (col-1)*(userInfo.imageSize+2):col*(userInfo.imageSize+2)] = generate_status_box(next_status,str(cell_name), SESSION.mode)
            viewer.layers["Gallery Status Layer"].data = imdata.astype('int')

        elif SESSION.mode=="Multichannel":
            imdata = viewer.layers["Multichannel Status Layer"].data
            imdata[(row-1)*(userInfo.imageSize+2):row*(userInfo.imageSize+2),
                :] = generate_status_box(next_status,str(cell_name), SESSION.mode)
            viewer.layers["Multichannel Status Layer"].data = imdata.astype('int')
        # change color of viewer status
        vstatus_list = copy.copy(VIEWER.status).split('>')
        vstatus_list[0] = sub(r'#.{6}',STATUSES_TO_HEX[SESSION.status_list[str(cell_name)]], vstatus_list[0])
        VIEWER.status = ">".join(vstatus_list)

    @viewer.bind_key('l')
    def load_context_mode(viewer):
        print("\nIn context mode fxn")
        if SESSION.mode == "Context":
            toggle_session_mode(SESSION.last_mode)
        else:
            toggle_session_mode("Context")

    return True


######------------------------- Misc + Viewer keybindings ---------------------######

#TODO make a button to do this as well?
def set_viewer_to_neutral_zoom(viewer, reset_session = False):
    sc = 1 if SESSION.image_scale is None else SESSION.image_scale
    viewer.camera.zoom = 1.2 / sc
    if SESSION.mode=="Gallery":
        viewer.camera.center = (350*sc,450*sc) # these values seem to work best
        SESSION.last_gallery_camera_coordinates["center"] = viewer.camera.center
        SESSION.last_gallery_camera_coordinates["z"] = viewer.camera.zoom
    elif SESSION.mode=="Multichannel":
        viewer.camera.center = (350*sc, 300*sc)
        SESSION.last_multichannel_camera_coordinates["center"] = viewer.camera.center
        SESSION.last_multichannel_camera_coordinates["z"] = viewer.camera.zoom
    elif SESSION.mode=="Context":
        # Move to cell location on the global image
        VIEWER.camera.center = (SESSION.context_target["center_y"]*sc,SESSION.context_target["center_x"]*sc)
    if reset_session:
        SESSION.last_gallery_camera_coordinates["center"] = (350*sc,450*sc)
        SESSION.last_multichannel_camera_coordinates["center"] = (350*sc, 300*sc)
        SESSION.last_gallery_camera_coordinates["z"] = viewer.camera.zoom = 1.2/sc
        SESSION.last_multichannel_camera_coordinates["z"] = viewer.camera.zoom = 1.2/sc

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
        print(f'Using stored dataframe')
        viewer.status = 'Saving ...'
        # try:
        res = userInfo._save_validation(to_disk=True)
        
        if res: 
            viewer.status = 'Done saving!'
        else:
            viewer.status = 'There was a problem. Close your data file?'
        return None

def tsv_wrapper(viewer):
    @viewer.bind_key('h')
    def toggle_statuslayer_visibility(viewer):
        if SESSION.mode == "Context":
            toggle_nuclei_boxes(viewer)
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
    
    @viewer.bind_key('Shift-h')
    def toggle_nuclei_boxes(viewer):
        SESSION.nuclei_boxes_vis = not SESSION.nuclei_boxes_vis
        try:
            VIEWER.layers[f'{SESSION.mode} Nuclei Boxes'].visible = not VIEWER.layers[f'{SESSION.mode} Nuclei Boxes'].visible
        except KeyError:
            pass

        if SESSION.mode == "Context" and SESSION.nuclei_boxes_vis:
            # try to remove any previous box layers if there are any
            try:
                VIEWER.layers.selection.active = VIEWER.layers["Context Nuclei Boxes"]
                VIEWER.layers.remove_selected()
            except KeyError:
                pass
            
            vy, vx = viewer.cursor.position
            sc = 1 if SESSION.image_scale is None else SESSION.image_scale
            print(f"{vx, vy}")
            # Find cells in session table near target
            nearby_inds = SESSION.kdtree.query_ball_point([vx/sc,vy/sc], 125) # [x,y], dist -> indices in table
            nearby_cells = SESSION.session_cells.iloc[nearby_inds]

            # Add box around cells
            nuclei_box_coords = []
            cids = []
            for index, cell in nearby_cells.iterrows():
                x1 = int(cell["XMin"]); x2 = int(cell["XMax"])
                y1 = int(cell["YMin"]); y2 = int(cell["YMax"])
                nuclei_box_coords.append([[y1,x1] , [y2,x2]])
                cids.append(str(cell["Object Id"]))

            if nuclei_box_coords:
                features = {'cid': cids}
                nb_color_str = 'black' if SESSION.absorption_mode else 'white' 
                nb_color_hex = '#000000' if SESSION.absorption_mode else '#ffffff'
                nb_text = {'string':'{cid}', 'anchor':'upper_left', 'size' : 8, 'color':nb_color_str}
                sc = (SESSION.image_scale, SESSION.image_scale) if SESSION.image_scale is not None else None
                VIEWER.add_shapes(nuclei_box_coords, name="Context Nuclei Boxes", shape_type="rectangle", edge_width=1, edge_color=nb_color_hex, 
                                                    face_color='#00000000', scale=sc, features=features, text = nb_text )
                VIEWER.layers.selection.active = VIEWER.layers["Gallery Status Layer"]  



    @viewer.bind_key('Control-k')
    def restore_canvas(viewer):
        set_viewer_to_neutral_zoom(viewer)

    @viewer.bind_key('k')
    def recenter_canvas(viewer):
        set_viewer_to_neutral_zoom(viewer)

    @viewer.bind_key('Up')
    def scroll_up(viewer):
        z,y,x = viewer.camera.center
        sc = 1 if SESSION.image_scale is None else SESSION.image_scale
        viewer.camera.center = (y-((userInfo.imageSize+2)*sc),x)

    @viewer.bind_key('Down')
    def scroll_down(viewer):
        z,y,x = viewer.camera.center
        sc = 1 if SESSION.image_scale is None else SESSION.image_scale
        viewer.camera.center = (y+((userInfo.imageSize+2)*sc),x)
    
    @viewer.bind_key('Left')
    def scroll_left(viewer):
        z,y,x = viewer.camera.center
        sc = 1 if SESSION.image_scale is None else SESSION.image_scale
        viewer.camera.center = (y,x-((userInfo.imageSize+2)*sc))
        #TODO trigger mouse update here
        # napari.Viewer.window.qt_viewer._process_mouse_event
        # viewer.window.qt_viewer.canvas.events.mouse_press(pos=(x, y), modifiers=(), button=0)
        # viewer.cursor.position = viewer.window.qt_viewer._map_canvas2world([x,y])

    @viewer.bind_key('Right')   
    def scroll_right(viewer):
        z,y,x = viewer.camera.center
        sc = 1 if SESSION.image_scale is None else SESSION.image_scale
        viewer.camera.center = (y,x+((userInfo.imageSize+2)*sc))

    # On Macs, ctrl-arrow key is taken by something else.
    @viewer.bind_key('Shift-Right')  
    @viewer.bind_key('Shift-Up') 
    @viewer.bind_key('Control-Right')  
    @viewer.bind_key('Control-Up')   
    def zoom_in(viewer):
        viewer.camera.zoom *= 1.15

    @viewer.bind_key('Shift-Left')  
    @viewer.bind_key('Shift-Down') 
    @viewer.bind_key('Control-Left')  
    @viewer.bind_key('Control-Down')   
    def zoom_out(viewer):
        viewer.camera.zoom /= 1.15  
    
    @viewer.bind_key('a')
    def trigger_absorption(viewer):
        toggle_absorption()
    
    @viewer.bind_key('r')
    def reset_viewsettings(viewer):
        global ADJUSTMENT_SETTINGS
        ADJUSTMENT_SETTINGS = copy.copy(ORIGINAL_ADJUSTMENT_SETTINGS)
        reuse_gamma()
        reuse_contrast_limits()
    
    @viewer.bind_key('i')
    def toggle_interpolation(viewer):
        current = VIEWER.layers[f"Gallery {CHANNELS_STR[0]}"].interpolation
        if current == 'nearest':
            new = 'linear'
        else:
            new = 'nearest' 
        for fluor in CHANNELS_STR:
            if fluor =='Composite': continue
            VIEWER.layers["Gallery " +fluor].interpolation = new
            VIEWER.layers["Multichannel "+fluor].interpolation = new
            VIEWER.layers["Context "+fluor].interpolation = new

    @viewer.bind_key('Alt-m')
    def open_guide(viewer):
        os.startfile(os.path.normpath(os.curdir+ r"/data/GalleryViewer v{x} User Guide.pdf".format(x=VERSION_NUMBER)))
        



def chn_key_wrapper(viewer):
    def create_fun(position,channel):
        @viewer.bind_key(str(position+1))
        def toggle_channel_visibility(viewer,pos=position,chn=channel):
            
            widget_obj = UPDATED_CHECKBOXES[pos]
            if widget_obj.isChecked():
                widget_obj.setChecked(False)
            else:
                widget_obj.setChecked(True)

        return toggle_channel_visibility

    for pos, chn in enumerate(UPDATED_CHECKBOXES):
        binding_func_name = f'{chn}_box_func'
        exec(f'globals()["{binding_func_name}"] = create_fun({pos},"{chn}")')
        

def set_initial_adjustment_parameters(viewsettings):
    for key in list(viewsettings.keys()):
        # print(f'\n key is {key}')
        ADJUSTMENT_SETTINGS[key] = viewsettings[key]
    global ORIGINAL_ADJUSTMENT_SETTINGS
    ORIGINAL_ADJUSTMENT_SETTINGS = copy.copy(ADJUSTMENT_SETTINGS) # save a snapshot in case things get messed up

    return True

def fetch_notes(cell_row, intensity_col_names):
    '''Grab notes and intensities for each cell in the list and save to global dicts'''
    if not ANNOTATIONS_PRESENT:
        ID = "All " + str(cell_row['Object Id'])
    else:
        ID = str(cell_row['Analysis Region']) + ' ' + str(cell_row['Object Id'])
    SESSION.saved_notes[ID] = cell_row['Notes']
    # Find out which columns are present in the Series and subset to those
    present_intensities = sorted(list(set(list(cell_row.index)).intersection(set(intensity_col_names))))
    cell_row = cell_row.loc[present_intensities]
    SAVED_INTENSITIES[ID] = cell_row
    # print(f'dumping dict {SESSION.saved_notes}')

'''Get object data from csv and parse.''' 
def extract_phenotype_xldata(page_size=None, phenotypes=None,annotations = None, page_number = 1, 
                            specific_cell = None, sort_by_intensity = None, combobox_widget = None):
    
    # 'OPAL520' # None means 'don't do it', while a channel name means 'put highest at the top'
    if sort_by_intensity is None:
        sort_by_intensity = "Object Id"
    elif "opal" in sort_by_intensity.lower() or "DAPI" == sort_by_intensity:
        sort_by_intensity = sort_by_intensity.replace('OPAL','Opal ') + ' Cell Intensity'
    else:
        sort_by_intensity = "Sample AF Cell Intensity"
    print(f"SORTBYINTENSITY IS {sort_by_intensity}")

    # get defaults from global space
    if page_size is None: page_size=PAGE_SIZE # Number of cells to be shown
    if phenotypes is None: phenotypes=PHENOTYPES
    if annotations is None: annotations=ANNOTATIONS  # Name of phenotype of interest
    # print(f'ORDERING PARAMS: id start: {cell_id_start}, page size: {page_size}, direction: {direction}, change?: {change_startID}')
    halo_export = userInfo.objectDataFrame.copy()

    # Check for errors:
    for ph in phenotypes:
        if ph not in list(halo_export.columns):
            raise KeyError
    if len(annotations) >0 and ('Analysis Region' not in list(halo_export.columns)):
        raise KeyError

    # Add columns w/defaults if they aren't there to avoid runtime issues
    if "Validation | Unseen" not in halo_export.columns:
        for call_type in reversed(STATUS_COLORS.keys()):
            if call_type == 'Unseen':
                halo_export.insert(8,f"Validation | {call_type}", 1)
            else:
                halo_export.insert(8,f"Validation | {call_type}", 0)     
    if "Notes" not in halo_export.columns:
        halo_export.insert(8,"Notes","-")
        halo_export.fillna("")

    # Get relevant columns for intensity sorting
    # TODO make this conditional, and in a try except format
    headers = pd.read_csv(OBJECT_DATA_PATH, index_col=False, nrows=0).columns.tolist() 
    possible_fluors = ['DAPI','Opal 480','Opal 520', 'Opal 570', 'Opal 620','Opal 690', 'Opal 720', 'AF', 'Sample AF', 'Autofluorescence']
    suffixes = ['Cell Intensity','Nucleus Intensity', 'Cytoplasm Intensity']
    all_possible_intensities = [x for x in headers if (any(s in x for s in suffixes) and (any(f in x for f in possible_fluors)))]
    SESSION.intensity_columns = all_possible_intensities
    # for fl in possible_fluors:
    #         for sf in suffixes:
    #             all_possible_intensities.append(f'{fl} {sf}')
    v = list(STATUS_COLORS.keys())
    validation_cols = [f"Validation | " + s for s in v]
    SESSION.validation_columns = validation_cols
    cols_to_keep = ["Object Id","Analysis Region", "Notes", "XMin","XMax","YMin", "YMax"] + phenotypes + all_possible_intensities + validation_cols
    cols_to_keep = halo_export.columns.intersection(cols_to_keep)
    halo_export = halo_export.loc[:, cols_to_keep]

    global GLOBAL_SORT
    global_sort_status = True
    if GLOBAL_SORT is not None:
        try:
            GLOBAL_SORT = [x for x in all_possible_intensities if all(y in x for y in GLOBAL_SORT.split(" "))][0]
            halo_export = halo_export.sort_values(by = GLOBAL_SORT, ascending = False, kind = 'mergesort')
        except:
            print('Global sort failed. Will sort by Cell Id instead.')
            GLOBAL_SORT = None
            global_sort_status = False
            VIEWER.status = 'Global sort failed. Will sort by Cell Id instead.'
            if annotations:
                halo_export = halo_export.sort_values(by = ["Analysis Region","Object Id"], ascending = True, kind = 'mergesort')
    else:
        if annotations:
            halo_export = halo_export.sort_values(by = ["Analysis Region","Object Id"], ascending = True, kind = 'mergesort')
    
    # Helper to construct query string that will subset dataframe down to cells that 
    #   are positive for a phenotype in the list, or a member of an annotation layer in the list
    def _create_anno_pheno_query(anno_list, pheno_list):
        query = ''
        for anno in anno_list:
            query += f"(`Analysis Region` == '{anno}') | "
        for pheno in pheno_list:
            query += f"(`{pheno}` == 1) |"
        print(query)
        return query.rstrip(" |")

    # #acquire 
    print('page code start')
    # Figure out which range of cells to get based on page number and size
    if annotations or phenotypes:
        phen_only_df = halo_export.query(_create_anno_pheno_query(annotations,phenotypes)).reset_index()
    else:
        phen_only_df = halo_export.reset_index()
    last_page = (len(phen_only_df.index) // page_size)+1
    print(f"last page is {last_page}")
    global ALL_CUSTOM_WIDGETS
    combobox_widget =  ALL_CUSTOM_WIDGETS['page combobox']
    # combobox_widget.addItem('Page 1')
    # If page numbers haven't been added to the widget, do it now   
    if combobox_widget.currentIndex() == -1: # This means it's empty
        for i in range(1,last_page+1):
            bname = f'Page {i}'
            combobox_widget.addItem(bname)

    # If a certain cell is desired, find its page
    print(f"testing if specific cell {specific_cell} and type {type(specific_cell)}")
    if specific_cell is not None:
        try:
            specific_cid = specific_cell['ID']
            specific_layer = specific_cell['Annotation Layer']
            
            #TODO fix this
            if ANNOTATIONS_PRESENT and specific_layer:
                singlecell_df = phen_only_df[(phen_only_df['Object Id']==int(specific_cid)) & (phen_only_df['Analysis Region']==str(specific_layer))]
            else:
                singlecell_df = phen_only_df[phen_only_df['Object Id']==int(specific_cid)]
            sc_index = singlecell_df.index[0]
            page_number = (sc_index//page_size) + 1
            #TODO set the combobox widget to the current page number
        except (KeyError,IndexError, ValueError):
            print(f'The cell ID {specific_layer} {specific_cid} is not in my list of cells. Loading default page instead')
            VIEWER.status = f'The cell ID {specific_layer} {specific_cid} is not in my list of cells. Loaded default page instead'

    # set widget to current page number 
    combobox_widget.setCurrentIndex(page_number-1)
    SESSION.saved_notes['page'] = combobox_widget.currentText()
    
    
    
    # Save cells that form ALL pages for this session. They could appear in Context Mode.
    SESSION.session_cells = phen_only_df
    SESSION.session_cells["center_x"] = ((SESSION.session_cells['XMax']+SESSION.session_cells['XMin'])/2).astype(int)
    SESSION.session_cells["center_y"] = ((SESSION.session_cells['YMax']+SESSION.session_cells['YMin'])/2).astype(int)
    points = SESSION.session_cells[["center_x","center_y"]].to_numpy()
    SESSION.kdtree = spatial.KDTree(points)
    #(SESSION.kdtree.query_ball_point([ 1366, 15053], 100)) # x,y, dist -> index in table of 


    # import pickle
    # with open("session_cells.pkl","wb") as out:
    #     pickle.dump(phen_only_df, out)
    # exit()

    # Get the appropriate set
    if page_number != last_page:
        cell_set = phen_only_df[(page_number-1)*page_size: page_number*page_size]
    else:
        cell_set = phen_only_df[(page_number-1)*page_size:]

    
    print(f"#$%#$% local sort is {sort_by_intensity}")

    # Reorder cells in the page according to user input
    if sort_by_intensity is not None: # should never be none
        try:    
            if sort_by_intensity == "Object Id":
                if ANNOTATIONS_PRESENT:
                    cell_set = cell_set.sort_values(by = ["Analysis Region", sort_by_intensity], ascending = False, kind = 'mergesort')
                else:
                    cell_set = cell_set.sort_values(by = sort_by_intensity, ascending = False, kind = 'mergesort')

            else:
                 # First, check if a custom name was used.
                sort_by_intensity = [x for x in all_possible_intensities if all(y in x for y in sort_by_intensity.split(" "))][0]
                cell_set = cell_set.sort_values(by = sort_by_intensity, ascending = True, kind = 'mergesort')
        except (KeyError, IndexError):
            #  
            if global_sort_status:
                VIEWER.status = f"Unable to sort this page by '{sort_by_intensity}', will use ID instead. Check your data headers."
            else:
                VIEWER.status = f"Unable to sort everything by '{sort_by_intensity}', will use ID instead. Check your data headers."
            if ANNOTATIONS_PRESENT:
                cell_set = cell_set.sort_values(by = ["Analysis Region",'Object Id'], ascending = False, kind = 'mergesort')
            else:
                cell_set = cell_set.sort_values(by = 'Object Id', ascending = False, kind = 'mergesort')
    tumor_cell_XYs = {}

    for index,row in cell_set.iterrows():
        cid = row["Object Id"]
        layer = row["Analysis Region"] if ANNOTATIONS_PRESENT else "All"
        ckey = f'{layer} {cid}'
        fetch_notes(row, all_possible_intensities)
        center_x = int((row['XMax']+row['XMin'])/2)
        center_y = int((row['YMax']+row['YMin'])/2)
        vals = row[validation_cols]
        validation_call = str(vals[vals == 1].index.values[0]).replace(f"Validation | ", "")

        tumor_cell_XYs[ckey] = {'Layer':layer,"cid": cid,"center_x": center_x,'center_y': center_y,
                                'validation_call': validation_call, 'XMax' : row['XMax'],'XMin':row['XMin'],
                                'YMax' : row['YMax'],'YMin':row['YMin']}

    SESSION.current_cells = copy.copy(tumor_cell_XYs)
    SESSION.cell_under_mouse = next(iter(tumor_cell_XYs.values())) # Set first cell in list as "current" to avoid exceptions
    return tumor_cell_XYs

def replace_note(cell_widget, note_widget):
    cellID = cell_widget.text(); note = note_widget.text()
    # try: 
    #     cellID = int(cellID)
    # except ValueError:
    #     VIEWER.status = 'Error recording note: non-numeric Cell Id given'
    #     return None 
    try:
        SESSION.saved_notes[str(cellID)] # to trigger exception
        SESSION.saved_notes[str(cellID)] = note
        cell_widget.clear(); note_widget.clear()
        VIEWER.status = "Note recorded! Press 's' to save to file."
    except KeyError as e:
        print(f'\n{e}\n')
        VIEWER.status = 'Error recording note: Cell Id not found in list'

######------------------------- Remote Execution + Main ---------------------######

''' Reset globals and proceed to main '''
def GUI_execute(preprocess_class):
    global userInfo, qptiff, PAGE_SIZE, CHANNELS_STR, CHANNEL_ORDER, STATUS_COLORS, STATUSES_TO_HEX, STATUSES_RGBA
    global CHANNELS, ADJUSTED, OBJECT_DATA_PATH, PHENOTYPES, ANNOTATIONS, SPECIFIC_CELL, GLOBAL_SORT, CELLS_PER_ROW
    global ANNOTATIONS_PRESENT, ORIGINAL_ADJUSTMENT_SETTINGS, SESSION
    userInfo = preprocess_class.userInfo ; status_label = preprocess_class.status_label
    SESSION = userInfo.session

    qptiff = userInfo.qptiff_path
    PHENOTYPES = list(userInfo.phenotype_mappings.keys())
    ANNOTATIONS = list(userInfo.annotation_mappings.keys())
    ANNOTATIONS_PRESENT = userInfo.analysisRegionsInData
    STATUS_COLORS = userInfo.statuses ; STATUSES_RGBA = userInfo.statuses_rgba ; STATUSES_TO_HEX = userInfo.statuses_hex
    PAGE_SIZE = userInfo.page_size
    SPECIFIC_CELL = userInfo.specific_cell
    OBJECT_DATA_PATH = userInfo.objectDataPath
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
    # set saving flag so that dataframe will be written upon exit
    userInfo.session.saving_required = True # make the app save it's data on closing
    main(preprocess_class)

def main(preprocess_class = None):
    #TODO do this in a function because this is ugly

    global RAW_PYRAMID, RASTERS, VIEWER, ALL_CUSTOM_WIDGETS
    if preprocess_class is not None: preprocess_class.status_label.setVisible(True)
    preprocess_class._append_status_br("Loading image as raster...")
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

        preprocess_class._append_status('<font color="#7dbc39">  Done.</font>')
        preprocess_class._append_status_br('Sorting object data...')
    except:
        preprocess_class._append_status('<font color="#f5551a">  Failed.</font> Attempting to load memory-mapped object...')
        try:
            pyramid = tifffile.memmap(qptiff)
            preprocess_class._append_status('<font color="#7dbc39">  Done. </font> Parsing object data...')
        except:
            preprocess_class._append_status('<font color="#f5551a">  Failed.</font> Attempting to load raw image, this will take a while ...')
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
                preprocess_class._append_status('<font color="#7dbc39">  Done.</font>')
                preprocess_class._append_status_br('Sorting object data...')
            except:
                preprocess_class._append_status('<font color="#f5551a">  Failed.</font><br> Aborting startup, please contact Peter.')
                raise Exception("There was a problem reading the image data. Expecting a regular or memory-mapped tif/qptiff. Got something else.")
    finally:
        end_time = time.time()
        print(f'... completed in {end_time-start_time} seconds')

    
    viewer = napari.Viewer(title=f'GalleryViewer v{VERSION_NUMBER} {SESSION.image_display_name}')
    VIEWER = viewer
    # Get rid of the crap on the left sidebar for a cleaner screen
    viewer.window._qt_viewer.dockLayerList.toggleViewAction().trigger()
    viewer.window._qt_viewer.dockLayerControls.toggleViewAction().trigger()

    notes_label = QLabel('Placeholder note'); notes_label.setAlignment(Qt.AlignCenter)

    #TODO arrange these more neatly
    #TODO these dock widgets cause VERY strange behavior when trying to clear all layers / load more
    note_text_entry = QLineEdit()
    note_cell_entry = QLineEdit()
    note_button = QPushButton("Add note for cell")
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

    notes_container = viewer.window.add_dock_widget([notes_label,note_text_entry, note_cell_entry, note_button], name = 'Annotation', area = 'right')
    # Don't include annotation combobox unless it is necessary
    if ANNOTATIONS_PRESENT:
        page_cell_combo = QComboBox(); page_cell_combo.addItems(ANNOTATIONS_PRESENT); page_cell_combo.setFixedWidth(200)
        next_page_button.pressed.connect(lambda: show_next_cell_group(page_combobox, page_cell_entry,page_cell_combo, intensity_sort_box))
        page_container = viewer.window.add_dock_widget([page_combobox,page_cell_entry, page_cell_combo, intensity_sort_box, next_page_button], name = 'Page selection', area = 'right')
        ALL_CUSTOM_WIDGETS["page cell layer"] = page_cell_combo
    else:
        next_page_button.pressed.connect(lambda: show_next_cell_group(page_combobox, page_cell_entry, None, intensity_sort_box))
        page_container = viewer.window.add_dock_widget([page_combobox,page_cell_entry, intensity_sort_box, next_page_button], name = 'Page selection', area = 'right')


    mode_switch_combo = QComboBox()
    mode_switch_combo.addItems(["Gallery","Multichannel","Context"])
    switch_mode_button = QPushButton("Change Mode")
    switch_mode_button.pressed.connect(lambda: toggle_session_mode(mode_switch_combo.currentText()))
    mode_container = viewer.window.add_dock_widget([mode_switch_combo,switch_mode_button],name ="Mode selection",area="right")
    
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
    absorption_widget = QPushButton("Absorption")
    absorption_widget.pressed.connect(toggle_absorption)
    viewer.window.add_dock_widget(absorption_widget,name ="Light/dark mode",area="right")


    viewer.window.add_dock_widget(adjust_gamma_widget, area = 'bottom')
    viewer.window.add_dock_widget(adjust_whitein, area = 'bottom')
    viewer.window.add_dock_widget(adjust_blackin, area = 'bottom')
    # viewer.window.add_dock_widget(toggle_session_mode,name = 'Test', area = 'right')
    # viewer.window.add_dock_widget(show_next_cell_group,name = 'Test2', area = 'right')
    # viewer.window.add_dock_widget(toggle_statusbar_visibility,name = 'Test3', area = 'right')
    # print(f'\n {dir()}') # prints out the namespace variables 
    ALL_CUSTOM_WIDGETS['notes label']=notes_label; ALL_CUSTOM_WIDGETS['notes text entry']=note_text_entry
    ALL_CUSTOM_WIDGETS['notes cell entry']= note_cell_entry;ALL_CUSTOM_WIDGETS['notes button']=note_button
    ALL_CUSTOM_WIDGETS['next page button']=next_page_button
    ALL_CUSTOM_WIDGETS['switch mode combo']=mode_switch_combo
    ALL_CUSTOM_WIDGETS['switch mode button']=switch_mode_button; 
    ALL_CUSTOM_WIDGETS['show status layer radio']=status_layer_show; ALL_CUSTOM_WIDGETS['hide status layer radio']=status_layer_hide
    ALL_CUSTOM_WIDGETS['show status box radio']=status_box_show; ALL_CUSTOM_WIDGETS['hide status box radio']=status_box_hide
    ALL_CUSTOM_WIDGETS['page combobox']=page_combobox
    ALL_CUSTOM_WIDGETS['page cell id'] = page_cell_entry
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
        preprocess_class._append_status('<font color="#f5551a">  Failed.</font>')
        if PHENOTYPES:
            status+=f'<br><font color="#f5551a">The phenotype(s) {", ".join(str(x) for x in PHENOTYPES)} might not exist in the data, or other column names may have changed!</font>'
        if ANNOTATIONS:
            status+=f'<br><font color="#f5551a">The annotations(s) {", ".join(str(x) for x in ANNOTATIONS)} might not exist in the data, or other column names may have changed!</font>'
        viewer.close()
        return None # allows the input GUI to continue running
    preprocess_class._append_status('<font color="#7dbc39">  Done.</font>')
    preprocess_class._append_status_br('Initializing Napari session...')

    set_initial_adjustment_parameters(preprocess_class.userInfo.view_settings) # set defaults: 1.0 gamma, 0 black in, 255 white in
    attach_functions_to_viewer(viewer)
    add_layers(viewer,pyramid,tumor_cell_XYs, int(userInfo.imageSize/2))
    #TODO
    #Enable scale bar
    if SESSION.image_scale:
        viewer.scale_bar.visible = True
        viewer.scale_bar.unit = "um"

    # Filter checkboxes down to relevant ones only and update color
    for i in range(len(all_boxes)):
        box = all_boxes[i]
        if box.objectName() in CHANNELS_STR:
            box.setStyleSheet(f"QCheckBox {{ color: {CHANNEL_ORDER[box.objectName()].replace('blue','#0462d4')} }}")
            UPDATED_CHECKBOXES.append(box)
    viewer.window.add_dock_widget(UPDATED_CHECKBOXES,area='bottom')

    # Finish up, and set keybindings
    preprocess_class._append_status('<font color="#7dbc39">  Done.</font><br> Goodbye')
    sv_wrapper(viewer)
    tsv_wrapper(viewer)
    chn_key_wrapper(viewer)
    set_viewer_to_neutral_zoom(viewer, reset_session=True) # Fix zoomed out issue
    if preprocess_class is not None: preprocess_class.close() # close other window
    with tifffile.imread(userInfo.qptiff_path, aszarr=True) as zs:
        SESSION.zarr_store = zs
        sc = (SESSION.image_scale, SESSION.image_scale) if SESSION.image_scale is not None else None
        for i, fluor in enumerate(userInfo.channelOrder):
            if i not in CHANNELS or fluor == 'Composite':
                continue
            print(f"\nAdding full size {fluor} image")
            pyramid = [da.from_zarr(zs, n)[i] for n in range(6) ] #TODO how to know how many pyramid layers?
            viewer.add_image(pyramid, name = f'Context {fluor}', 
                        blending = 'additive', colormap = custom_maps.retrieve_cm(CHANNEL_ORDER[fluor]),
                        interpolation = "linear", scale=sc, visible = False)
        
        # Set adjustment settings to their default now that all images are loaded
        reuse_contrast_limits()
        reuse_gamma()
        viewer.layers.selection.active = viewer.layers["Gallery Status Layer"]
        napari.run() # Start the event loop
        # zs.close()
    print('\n#Zarr object should be closed')
    # close image file
    if RASTERS is not None:
        print('Not sure if we have to close this file... the "with" statement should handle it.')
        RAW_PYRAMID.close()
# Main should work now using the defaults specified at the top of this script in the global variable space
if __name__ == '__main__':
    main()
