'''
CTC viewer for Napari
Started on 6/7/22
Peter Richieri
'''

# import IPython
import tifffile
import napari
from napari.types import ImageData
from napari.settings import get_settings
from magicgui import magicgui #, magic_factory
from PyQt5.QtWidgets import (QLabel, QLineEdit, QPushButton, QRadioButton, QCheckBox, QButtonGroup, QSizePolicy, 
                        QComboBox, QHBoxLayout,QVBoxLayout, QGroupBox, QLayout, QAbstractButton)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
import numpy as np
import pandas as pd
# import openpyxl # necessary, do not remove
from matplotlib import cm # necessary, do not remove
from matplotlib import colors as mplcolors # Necessary, do not remove
import copy
import time
import store_and_load
import custom_color_functions # Necessary, do not remove
from math import ceil
from re import sub
import os
import dask.array as da
# import zarr
import scipy.spatial as spatial
from random import randint

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
    exec(f'my_map = custom_color_functions.create_{colormap}_lut()')
    exec(f'custom = mplcolors.LinearSegmentedColormap.from_list("{colormap}", my_map)')
    exec(f'cm.register_cmap(name = "{colormap}", cmap = custom)')
# print(f'\n---------My colormaps are now {plt.colormaps()}--------\n')

# cell_colors = ['blue', 'purple' , 'red', 'green', 'orange','red', 'green', 'Pink', 'cyan'] # for local execution
qptiff = r"C:\Users\prich\Desktop\Projects\MGH\CTC_Example\Exp02a01_02_Scan1.qptiff"
OBJECT_DATA_PATH = r"C:\Users\prich\Desktop\Projects\MGH\CTC_Example\ctc_example_data.csv" # path to halo export
PAGE_SIZE = 15 # How many cells will be shown in next page
CELLS_PER_ROW = 8
SPECIFIC_CELL = None # Dictionary with the format {'ID': (int),'Annotation Layer': (str) }
PHENOTYPES = ['Tumor'] #'CTC 488pos'
ANNOTATIONS = []
GLOBAL_SORT = None

userInfo = store_and_load.loadObject('data/presets')
SESSION = userInfo.session # will store non-persistent global variables that need to be accessible

VIEWER = None
ADJUSTMENT_SETTINGS={"DAPI gamma": 0.5}; ORIGINAL_ADJUSTMENT_SETTINGS = {}
SAVED_INTENSITIES={}; 
RAW_PYRAMID=None
SESSION.widget_dictionary = {}
NO_LABEL_BOX = False
STATUS_COLORS = {}
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
    for fluor in userInfo.channels:
        if fluor == 'Composite':
            continue
        if "Composite" in userInfo.active_channels or fluor in userInfo.active_channels: 
            VIEWER.layers[f"{SESSION.mode} {fluor}"].visible = True
        # Now change settings for both, whether or not they are displayed right now.
        adjust_composite_gamma(VIEWER.layers["Gallery "+fluor],ADJUSTMENT_SETTINGS[fluor+" gamma"])
        adjust_composite_gamma(VIEWER.layers["Multichannel "+fluor],ADJUSTMENT_SETTINGS[fluor+" gamma"])
        adjust_composite_gamma(VIEWER.layers["Context "+fluor],ADJUSTMENT_SETTINGS[fluor+" gamma"])

    if SESSION.mode != "Context":
        # VIEWER.layers[f"{SESSION.mode} Status Edges"].visible = SESSION.status_layer_vis
        VIEWER.layers[f"{SESSION.mode} Status Squares"].visible = SESSION.status_layer_vis
        VIEWER.layers[f"{SESSION.mode} Status Numbers"].visible = SESSION.status_layer_vis

        # VIEWER.layers[f"{SESSION.mode} Absorption"].visible = SESSION.absorption_mode
    try:
        print(SESSION.nuclei_boxes_vis)
        print(SESSION.mode)
        if SESSION.mode == "Context":
            show_boxes = True if SESSION.nuclei_boxes_vis["Context"] =="Show" else False
        else:
            show_boxes = SESSION.nuclei_boxes_vis["Gallery/Multichannel"]
        VIEWER.layers[f"{SESSION.mode} Nuclei Boxes"].visible = show_boxes
    except KeyError:
        pass
    


def reuse_contrast_limits():
        # Make everything silent
    for layer in VIEWER.layers:
        layer.visible = False
    for fluor in userInfo.channels:
        if fluor == 'Composite':
            continue
        if "Composite" in userInfo.active_channels or fluor in userInfo.active_channels: 
            VIEWER.layers[f"{SESSION.mode} {fluor}"].visible = True
        # Now change settings for both, whether or not they are displayed right now.
        adjust_composite_limits(VIEWER.layers["Gallery "+fluor], [ADJUSTMENT_SETTINGS[fluor+" black-in"],ADJUSTMENT_SETTINGS[fluor+" white-in"]])
        adjust_composite_limits(VIEWER.layers["Multichannel "+fluor], [ADJUSTMENT_SETTINGS[fluor+" black-in"],ADJUSTMENT_SETTINGS[fluor+" white-in"]])
        adjust_composite_limits(VIEWER.layers["Context "+fluor], [ADJUSTMENT_SETTINGS[fluor+" black-in"],ADJUSTMENT_SETTINGS[fluor+" white-in"]])

    if SESSION.mode != "Context":
        # VIEWER.layers[f"{SESSION.mode} Status Edges"].visible = SESSION.status_layer_vis
        VIEWER.layers[f"{SESSION.mode} Status Squares"].visible = SESSION.status_layer_vis
        VIEWER.layers[f"{SESSION.mode} Status Numbers"].visible = SESSION.status_layer_vis
        # VIEWER.layers[f"{SESSION.mode} Absorption"].visible = SESSION.absorption_mode
    try:
        show_boxes = SESSION.nuclei_boxes_vis[SESSION.mode]
        show_boxes = True if show_boxes =="Show" else False
        VIEWER.layers[f"{SESSION.mode} Nuclei Boxes"].visible = show_boxes
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
    for fluor in userInfo.active_channels:
        if fluor == 'Composite':
            continue
        _update_dictionary(fluor,Gamma)
        for m in ["Gallery", "Multichannel", "Context"]:
            adjust_composite_gamma(VIEWER.layers[f"{m} "+fluor],Gamma)
    VIEWER.window._qt_viewer.setFocus()

adjust_gamma_widget.visible=False

@magicgui(auto_call=True,
        white_in={"widget_type": "FloatSlider", "max":255,"min":1.0, "label": "White-in"},
        layout = 'horizontal')
def adjust_whitein(white_in: float = 255) -> ImageData:
    def _update_dictionary(name, val):
        global ADJUSTMENT_SETTINGS
        ADJUSTMENT_SETTINGS[name+' white-in'] = val
    for fluor in userInfo.active_channels:
        if fluor == 'Composite':
            continue
        _update_dictionary(fluor,white_in)
        for m in ["Gallery", "Multichannel", "Context"]:
            adjust_composite_limits(VIEWER.layers[f"{m} {fluor}"], [ADJUSTMENT_SETTINGS[fluor+" black-in"],white_in])
    VIEWER.window._qt_viewer.setFocus()


@magicgui(auto_call=True,
        black_in={"widget_type": "FloatSlider", "max":255, "label":"Black-in"},
        layout = 'horizontal')
def adjust_blackin(black_in: float = 0) -> ImageData:
    def _update_dictionary(name, val):
        global ADJUSTMENT_SETTINGS
        ADJUSTMENT_SETTINGS[name+' black-in'] = val
    
    for fluor in userInfo.active_channels:
        if fluor == 'Composite':
            continue
        _update_dictionary(fluor,black_in)
        for m in ["Gallery", "Multichannel", "Context"]:
            adjust_composite_limits(VIEWER.layers[f"{m} {fluor}"], [black_in,ADJUSTMENT_SETTINGS[fluor+" white-in"]])
    VIEWER.window._qt_viewer.setFocus()

def toggle_absorption():
    #TODO make absorption work for context more?
    # if SESSION.mode == "Context": return None
    if SESSION.absorption_mode ==True:
        SESSION.absorption_mode = False
        for layer in VIEWER.layers:
            
            if 'Status' in layer.name:
                continue
            elif "Nuclei Boxes" in layer.name or layer.name == "Context Closest Cell Box":
                layer.edge_color = '#ffffff'
                continue
            # elif "Absorption" in layer.name:
            #     layer.visible = False
            #     continue
            sess = layer.name.split()[0] + " "
            layer.colormap = custom_color_functions.retrieve_cm(userInfo.channelColors[layer.name.replace(sess,"")])
            layer.blending = 'Additive'
    else:
        SESSION.absorption_mode = True
        for layer in VIEWER.layers:
            
            if 'Status' in layer.name:
                continue
            elif "Nuclei Boxes"  in layer.name or layer.name == "Context Closest Cell Box":
                layer.edge_color="#000000"
                continue
            # elif "Absorption" in layer.name:
            #     if SESSION.mode == layer.name.split()[0]:
            #         layer.visible = True
            #         im = layer.data
            #         im[:,:] = [255,255,255,255]
            #         layer.data = im.astype(np.uint8)
            #     continue
            sess = layer.name.split()[0] + " "
            layer.colormap = custom_color_functions.retrieve_cm(userInfo.channelColors[layer.name.replace(sess,"")]+' inverse')
            layer.blending = 'Minimum'
    if not SESSION.mode == "Context":
        #TODO
        pass
        # change_statuslayer_color(copy.copy(SESSION.current_cells))
    
    # Change colors
    newmode = "light" if SESSION.absorption_mode else "dark"
    oldmode = "dark" if SESSION.absorption_mode else "light"
    for name, bg in SESSION.side_dock_groupboxes.items():
        bg.setStyleSheet(open(f"data/docked_group_box_border_{oldmode}.css").read())
    VIEWER.theme = newmode

def tally_checked_widgets():
    # keep track of visible channels in global list and then toggle layer visibility
    userInfo.active_channels = []
    for checkbox in UPDATED_CHECKBOXES:
        check = checkbox.isChecked()
        checkbox_name = checkbox.objectName()
    # print(f"{checkbox_name} has been clicked and will try to remove from {userInfo.active_channels}")
        if check:
            userInfo.active_channels.append(str(checkbox_name))

    # Make visible all channels according to rules
    for fluor in userInfo.channels:
        # Different set of layers if we are in context mode
        lname = f'{SESSION.mode} {fluor}'
        if fluor == "Composite":
            continue
        if "Composite" in userInfo.active_channels or fluor in userInfo.active_channels:
            VIEWER.layers[lname].visible = True
        else:
            VIEWER.layers[lname].visible = False  
    VIEWER.window._qt_viewer.setFocus()
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

# all_boxes = check_creator2(userInfo.channels)


## --- Side bar functions and GUI elements 

### --- 
# @magicgui(call_button='Change Mode',
#         Mode={"widget_type": "RadioButtons","orientation": "vertical",
#         "choices": [("Multichannel Mode", 1), ("Composite Mode", 2)]})#,layout = 'horizontal')
def toggle_session_mode_catch_exceptions(target_mode, from_mouse = True):
    # try:
    toggle_session_mode(target_mode, from_mouse)
    # except (ValueError,TypeError) as e:
    #     print(e)
    #     # Might trigger when SESSION.cell_under_mouse holds information on a cell from context mode
    #     VIEWER.status = f"Can't enter {target_mode} Mode right now. Move your mouse around a bit first please"


def toggle_session_mode(target_mode, from_mouse: bool):
    def _save_validation(VIEWER, Mode):
        res = userInfo._save_validation(to_disk=False)
        if res:
            VIEWER.status = f'{Mode} Mode enabled. Scoring decisions loaded successfully.'
            return True
        else:
            #TODO Maybe it's an excel sheet?
            VIEWER.status = f'{Mode} Mode enabled. But, there was a problem saving your decisions. Close your data file?'
            return False
    
    # Change widget display
    SESSION.widget_dictionary['switch mode combo'].setCurrentText(target_mode)
    if SESSION.nuclei_boxes_vis["Context"]=="Mouse": SESSION.widget_dictionary['hide boxes'].setChecked(True)
    SESSION.widget_dictionary['page cell id'].clear() #This can only cause issues if not cleared.
    # Do nothing in these cases
    if target_mode==SESSION.mode: return None
    SESSION.last_mode = SESSION.mode # save for later

    # Save last coordinates
    if SESSION.mode == "Gallery":
        SESSION.last_gallery_camera_coordinates["center"] = VIEWER.camera.center
        SESSION.last_gallery_camera_coordinates["z"] = VIEWER.camera.zoom
    elif SESSION.mode == "Multichannel":
        SESSION.last_multichannel_camera_coordinates["center"] = VIEWER.camera.center
        SESSION.last_multichannel_camera_coordinates["z"] = VIEWER.camera.zoom
    
    if target_mode=="Context":
        if not from_mouse:
            try:
                cid = SESSION.widget_dictionary['switch mode cell'].text()
                if ANNOTATIONS_PRESENT:
                    layer = SESSION.widget_dictionary['switch mode annotation'].currentText()
                    cname = f"{layer} {cid}"
                else:
                    cname = str(cid)
                target_cell_info = SESSION.current_cells[cname]
                SESSION.cell_under_mouse = target_cell_info
                print(target_cell_info)
            except KeyError:
                VIEWER.status = f"Can't find cell [{cid}] in the current page. Staying in {SESSION.mode} mode"
                return False
        else:
            target_cell_info = SESSION.cell_under_mouse
            print(target_cell_info)

        SESSION.context_target = target_cell_info
        cell_num = str(target_cell_info["cid"])
        # print(cell_num)
        sc = 1 if SESSION.image_scale is None else SESSION.image_scale # Scale factor necessary.

        # Find offset coordinates
        if SESSION.mode=="Gallery": 
            row, col = list(SESSION.grid_to_ID["Gallery"].keys())[list(SESSION.grid_to_ID["Gallery"].values()).index(f"{target_cell_info['Layer']} {cell_num}")].split(",")
            row, col = (int(row),int(col))
            cellCanvasY = ((row-1)*(userInfo.imageSize+2)) + ((userInfo.imageSize+2)/2)
            cellCanvasX = ((col-1)*(userInfo.imageSize+2)) + ((userInfo.imageSize+2)/2)
            z,y,x = VIEWER.camera.center
            offsetX = (x/sc) - cellCanvasX 
            offsetY = (y/sc) - cellCanvasY 

        elif SESSION.mode=="Multichannel": 
            # Could do it here, but not certain that it's preferable over centering the cell.
            offsetX = 0
            offsetY = 0
        
        # Move to cell location on the global image
        VIEWER.camera.center = ((target_cell_info["center_y"]+offsetY)*sc,(target_cell_info["center_x"]+offsetX)*sc) # these values seem to work best
        # viewer.camera.zoom = 1.2 / sc

        # try to remove any previous box layers if there are any
        try:
            VIEWER.layers.selection.active = VIEWER.layers["Context Nuclei Boxes"]
            VIEWER.layers.remove_selected()
        except KeyError:
            pass
        SESSION.widget_dictionary['mouse boxes'].setVisible(True) # Enable this widget

        if from_mouse:
            _, (mX,mY), _ = SESSION.find_mouse_func(VIEWER.cursor.position, scope="local")
            # print(f"mx {mX} and mY {mY}")
            # Change cursor value
            sc = 1 if SESSION.image_scale is None else SESSION.image_scale # Scale factor necessary.
            class dummyCursor:
                def __init__(self, y, x) -> None:
                    self.position = (y,x)
            SESSION.display_intensity_func(VIEWER, dummyCursor((target_cell_info["center_y"]+mY-(userInfo.imageSize+2)/2)*sc,(target_cell_info["center_x"]+mX-(userInfo.imageSize+2)/2)*sc))

        
        # finally, set mode
        SESSION.mode = target_mode

        # Will trigger this function with the appropriate input to box and color the nearest
        #   100 cells around the target cell 
        if SESSION.nuclei_boxes_vis["Gallery/Multichannel"]:
            radio = SESSION.widget_dictionary['show boxes']
        else:
            radio = SESSION.widget_dictionary['hide boxes']
        toggle_nuclei_boxes(radio, True, 
            [target_cell_info["center_x"],target_cell_info["center_y"]])

        # Turn on / off the correct layers
        reuse_gamma()

        VIEWER.window._qt_viewer.setFocus() # return focus
        # Done. Leave function, no need to save cells
        return True 
    
    elif target_mode == "Multichannel" or target_mode =="Gallery":
        
        SESSION.widget_dictionary['mouse boxes'].setVisible(False) # Disable this widget
        if SESSION.mode != "Context": # Now, we must be changing to Gallery OR Multichannel. Want to save to DataFrame, not disk
            _save_validation(VIEWER, target_mode)
            print(f"Number of cells in current page is {len(SESSION.current_cells)} and type is {type(SESSION.current_cells)}")
            

        if target_mode == "Multichannel":
            if not from_mouse:
                try:
                    cid = SESSION.widget_dictionary['switch mode cell'].text()
                    if ANNOTATIONS_PRESENT:
                        layer = SESSION.widget_dictionary['switch mode annotation'].currentText()
                        target_cell_name = f"{layer} {cid}"
                    else:
                        target_cell_name = str(cid)
                    target_cell_info = SESSION.current_cells[cname]
                    SESSION.cell_under_mouse = target_cell_info
                    print(target_cell_info)
                except KeyError:
                    VIEWER.status = f"Can't find cell [{cid}] in the current page. Staying in {SESSION.mode} mode"
                    return False
            else:
                target_cell_name = f"{SESSION.cell_under_mouse['Layer']} {str(SESSION.cell_under_mouse['cid'])}"

            sc = 1 if SESSION.image_scale is None else SESSION.image_scale # Scale factor necessary
            row, col = list(SESSION.grid_to_ID["Multichannel"].keys())[list(SESSION.grid_to_ID["Multichannel"].values()).index(target_cell_name)].split(",")
            row= int(row) #find the row for multichannel cell. Col should be irrelevant
            cellCanvasY = ((row-1)*(userInfo.imageSize+2)) + ((userInfo.imageSize+2)/2)
            cellCanvasX = (len(userInfo.channels)+1)*(userInfo.imageSize+2) /2 # Add 1 to channels to account for merged image
            SESSION.last_multichannel_camera_coordinates["center"] = (cellCanvasY*sc, cellCanvasX*sc)
            # print(f"Targeting {cellCanvasY,cellCanvasX}")
            VIEWER.camera.center = SESSION.last_multichannel_camera_coordinates["center"]
            VIEWER.camera.zoom = SESSION.last_multichannel_camera_coordinates["z"]
        
        elif target_mode == "Gallery":
            VIEWER.camera.center = SESSION.last_gallery_camera_coordinates["center"]
            VIEWER.camera.zoom = SESSION.last_gallery_camera_coordinates["z"]
        else:
            raise Exception(f"Invalid parameter passed to toggle_session_mode: {target_mode}. Must be 'Gallery' or 'Multichannel'.")
        

        SESSION.mode = target_mode
        # Change visibilities of the correct layers
        reuse_gamma()
        VIEWER.window._qt_viewer.setFocus()
        return True


def show_next_cell_group():
    def _save_validation(VIEWER,numcells):

        res = userInfo._save_validation(to_disk=False)
        if res:
            VIEWER.status = f'Next {numcells} cells loaded.'
            return True
        else:
            VIEWER.status = 'There was a problem saving, so the next set of cells was not loaded. Close your data file?'
            return False
    
    def _get_widgets():
        widgets = SESSION.widget_dictionary
        intensity_sort_widget = widgets["page intensity sort"]
        if intensity_sort_widget.currentIndex() == 0:
            sort_option = None
        else:
            sort_option = intensity_sort_widget.currentText().replace("Sort page by ","")

        cid = widgets["page cell id"].text()
        page_widget = widgets["page combobox"]
        page = int(page_widget.currentText().split()[-1])
        if ANNOTATIONS_PRESENT:
            ann_layer = widgets["page cell layer"].currentText()
        else:
            ann_layer = ""
        return page, sort_option, cid, ann_layer

    page_number,sort_option, cell_choice, cell_annotation = _get_widgets()
    if SESSION.mode == "Context":
        toggle_session_mode_catch_exceptions("Gallery", from_mouse=False)
        # return None # Don't allow loading of new cells when in context mode.

    # Assemble dict from cell choice if needed
    if cell_choice == '': 
        cell_choice = None
    else:
        cell_choice = {"ID": cell_choice, "Annotation Layer": cell_annotation}

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

    # Perform adjustments before exiting function
    #TODO
    reuse_contrast_limits()# Only checked fluors will be visible
    reuse_gamma() 
    set_viewer_to_neutral_zoom(VIEWER, reset_session=True) # Fix zoomed out issue
    VIEWER.layers.selection.active = VIEWER.layers[f"Gallery {userInfo.channels[0]}"]  
    VIEWER.window._qt_viewer.setFocus()
    return True
    
# @magicgui(auto_call=True,
#         Status_Bar_Visibility={"widget_type": "RadioButtons","orientation": "vertical",
#         "choices": [("Show", 1), ("Hide", 2)]})
# def toggle_statusbar_visibility(Status_Bar_Visibility: int=1):
def toggle_statuslayer_visibility(show_widget):
    if SESSION.mode == "Context": return False
    if show_widget.isChecked(): SESSION.status_layer_vis = True
    else: SESSION.status_layer_vis = False
    # Find status layers and toggle visibility
    # VIEWER.layers[f"{SESSION.mode} Status Edges"].visible = SESSION.status_layer_vis
    VIEWER.layers[f"{SESSION.mode} Status Squares"].visible = SESSION.status_layer_vis
    VIEWER.layers[f"{SESSION.mode} Status Numbers"].visible = SESSION.status_layer_vis


    VIEWER.window._qt_viewer.setFocus()
    return True

def toggle_nuclei_boxes(btn, checked, distanceSearchCenter = None):

    # Always reset the user's input selection
    VIEWER.layers.selection.active = VIEWER.layers[f"Gallery {userInfo.channels[0]}"]  
    print("\nEntered function")
    if not checked:
        # This function gets called twice, since when one radio button in the group is toggle on, the other is toggled off. 
        #   We only want to run this function once so the other call can be discarded
        return False
    print("\nPassed Check") 
    if SESSION.mode in ["Gallery","Multichannel"]:
        SESSION.nuclei_boxes_vis["Gallery/Multichannel"] = not SESSION.nuclei_boxes_vis["Gallery/Multichannel"]
        SESSION.nuclei_boxes_vis["Context"] = "Show" if SESSION.nuclei_boxes_vis["Gallery/Multichannel"] else "Hide"
        try:
            VIEWER.layers[f'{SESSION.mode} Nuclei Boxes'].visible = SESSION.nuclei_boxes_vis["Gallery/Multichannel"]
        except KeyError:
            pass

    if SESSION.mode == "Context":
        match btn.text():
            case str(x) if 'mouse' in x.lower():
                selected_mode = "Mouse"
            case str(x) if 'hide' in x.lower():
                selected_mode = "Hide"
            case _:
                selected_mode = "Show"
        print(f"BEFORE toggle, mode is {SESSION.nuclei_boxes_vis['Context']}")
        SESSION.nuclei_boxes_vis["Context"] = selected_mode
        SESSION.nuclei_boxes_vis["Gallery/Multichannel"] = True if selected_mode == "Show" else False
        print(f"After toggle, mode is {SESSION.nuclei_boxes_vis['Context']}")

        # try to remove any previous box layers if there are any
        try:
            VIEWER.layers.selection.active = VIEWER.layers["Context Nuclei Boxes"]
            VIEWER.layers.remove_selected()
        except KeyError:
            pass

        try:
            VIEWER.layers.selection.active = VIEWER.layers["Context Closest Cell Box"]
            VIEWER.layers.remove_selected()
        except KeyError:
            pass
        # Always reset the user's input selection
        VIEWER.layers.selection.active = VIEWER.layers[f"Gallery {userInfo.channels[0]}"]

        if SESSION.nuclei_boxes_vis["Context"] != "Show":
            return False # Leave! Nothing more to do since the user does not want to see these boxes
        vy, vx = VIEWER.cursor.position
        sc = 1 if SESSION.image_scale is None else SESSION.image_scale
        print(f"{vx, vy}")
        # Find cells in session table near target
        z,y,x = VIEWER.camera.center
        # nearby_inds = SESSION.kdtree.query_ball_point([x/sc,y/sc], 550) # [x,y], dist -> indices in table
        if distanceSearchCenter:
            dists, nearby_inds = SESSION.kdtree.query(distanceSearchCenter, k=100) # [x,y], dist -> indices in table
            print("\nHere!")
        else:
            dists, nearby_inds = SESSION.kdtree.query([x/sc,y/sc], k=100) # [x,y], dist -> indices in table

        nearby_cells = SESSION.session_cells.iloc[nearby_inds] 

        # Add box around cells
        nuclei_box_coords = []
        cids = []
        validation_colors_hex = []
        count = 0
        SESSION.context_nuclei_boxes_map_to_ind = {} # reset this, will be different
        for index, cell in nearby_cells.iterrows():
            cid = cell["Object Id"]
            layer = cell["Analysis Region"] if ANNOTATIONS_PRESENT else None
            ckey = f'{layer} {cid}' if ANNOTATIONS_PRESENT else str(cid)
            x1 = int(cell["XMin"]); x2 = int(cell["XMax"])
            y1 = int(cell["YMin"]); y2 = int(cell["YMax"])
            nuclei_box_coords.append([[y1,x1] , [y2,x2]])
            cids.append(str(cell["Object Id"]))
            vals = cell[SESSION.validation_columns]
            try:
                validation_call = SESSION.status_list[ckey]
            except KeyError:
                try:
                    validation_call = str(vals[vals == 1].index.values[0]).replace(f"Validation | ", "")
                except IndexError:
                    # row has no validation call (all zeroes). Assign to Unseen
                    validation_call = "Unseen"
                SESSION.status_list[ckey] = validation_call #TODO this causes issues
                SESSION.saved_notes[ckey] = "-"
            validation_colors_hex.append(userInfo.statuses_hex[validation_call])
            SESSION.context_nuclei_boxes_map_to_ind[ckey] = count
            count+=1

        if nuclei_box_coords: # We have cells to box
            features = {'cid': cids}
            nb_color_str = 'black' if SESSION.absorption_mode else 'white' 
            nb_color_hex = '#000000' if SESSION.absorption_mode else '#ffffff'
            
            nb_text = {'string':'{cid}', 'anchor':'upper_left', 'size' : 8, 'color':validation_colors_hex}
            SESSION.context_nuclei_boxes_text_object = nb_text
            sc = (SESSION.image_scale, SESSION.image_scale) if SESSION.image_scale is not None else None
            VIEWER.add_shapes(nuclei_box_coords, name="Context Nuclei Boxes", shape_type="rectangle", edge_width=1, edge_color=validation_colors_hex, 
                                                face_color='#00000000', scale=sc, features=features,text=nb_text,opacity=0.9 )
        # Always reset the user's input selection
        VIEWER.layers.selection.active = VIEWER.layers[f"Gallery {userInfo.channels[0]}"]



def set_notes_label(ID, display_text_override = None):
    # Instead of showing a cell's info, display this text
    if display_text_override is not None:
        note = f'{SESSION.saved_notes["page"]}<br><br>' + display_text_override
        SESSION.widget_dictionary['notes label'].setText(note)
        VIEWER.window._qt_viewer.setFocus()
        return True
    cell_num = ID.split()[-1]; cell_anno = ID.replace(' '+cell_num,'')
    if ANNOTATIONS_PRESENT:
        cell_name = f'Cell {cell_num} from {cell_anno}'
    else:
        cell_name = f'Cell {cell_num}'
    try:
        note = str(SESSION.saved_notes[ID])
    except KeyError: # in case the name was off
        return False
    status = SESSION.status_list[str(ID)]
    if STATUSES_TO_HEX[status] != "#ffffff":
        prefix = f'{SESSION.saved_notes["page"]}<br><font color="{STATUSES_TO_HEX[status]}">{cell_name}</font>'
    else:
        prefix = f'{SESSION.saved_notes["page"]}<br>{cell_name}'


    # Add intensities
    intensity_series = SAVED_INTENSITIES[ID]
    names = list(intensity_series.index)
    intensity_str = ''
    for fluor in userInfo.channels:
        if fluor == 'Composite':
            continue
        # fluor = str(cell).replace(" Cell Intensity","")
        fluor = str(fluor)
        intensity_str += f'<br><font color="{userInfo.channelColors[fluor].replace("blue","#0462d4")}">{fluor}</font>'
        def add_values(intensity_str, fluor, intensity_lookup):
            flag = True
            name = intensity_lookup + ': No data'
            try:
                cyto = intensity_lookup
                cyto = [x for x in names if (cyto in x and 'Cytoplasm Intensity' in x)][0]
                val = round(float(intensity_series[cyto]),1)
                intensity_str += f'<font color="{userInfo.channelColors[fluor].replace("blue","#0462d4")}"> cyto: {val}</font>'
                flag = False
                name = cyto.replace(' Cytoplasm Intensity','')
            except (KeyError, IndexError): pass
            try:
                nuc = intensity_lookup
                nuc = [x for x in names if (nuc in x and 'Nucleus Intensity' in x)][0]
                val = round(float(intensity_series[nuc]),1)
                intensity_str += f'<font color="{userInfo.channelColors[fluor].replace("blue","#0462d4")}"> nuc: {val}</font>'
                flag = False
                name = nuc.replace(' Nucleus Intensity','')
            except (KeyError, IndexError): pass
            try:
                cell = intensity_lookup
                cell = [x for x in names if (cell in x and 'Cell Intensity' in x)][0]
                val = round(float(intensity_series[cell]),1)
                intensity_str += f'<font color="{userInfo.channelColors[fluor].replace("blue","#0462d4")}"> cell: {val}</font>'
                flag = False
                name = cell.replace(' Cell Intensity','')
            except (KeyError, IndexError): pass
            return intensity_str.replace(intensity_lookup,name), flag
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


        # intensity_str += f'<br><font color="{userInfo.channelColors[fluor.replace(" ","").upper()].replace("blue","#0462d4")}">{fluor} cyto: {round(float(intensity_series[cyto]),1)} nuc: {round(float(intensity_series[nuc]),1)} cell: {round(float(intensity_series[cell]),1)}</font>'
    # Add note if it exists
    if note == '-' or note == '' or note is None: 
        note = prefix + intensity_str
    else:
        note = prefix + intensity_str + f'<br><font size="5pt">{note}</font>'
    SESSION.widget_dictionary['notes label'].setText(note)
    VIEWER.window._qt_viewer.setFocus()
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


def black_background(color_space, mult, CPR):
    if color_space == 'RGB':
        return np.zeros((ceil((PAGE_SIZE*mult)/CPR)*(userInfo.imageSize+2),(userInfo.imageSize+2) * CPR, 4))
    elif color_space == 'Luminescence':
        return np.zeros((ceil((PAGE_SIZE*mult)/CPR)*(userInfo.imageSize+2),(userInfo.imageSize+2) * CPR))


''' Add images layers for Gallery and Multichannel modes. Only make visible the layers for the active mode'''
def add_layers(viewer,pyramid, cells, offset, new_page=True):
    print(f'\n---------\n \n Entering the add_layers function')
    if pyramid is not None: print(f"pyramid shape is {pyramid.shape}")
  
    SESSION.cells_per_row["Multichannel"] = len(userInfo.channels) + 1
    SESSION.cells_per_row["Gallery"] = userInfo.cells_per_row
    cpr_g = SESSION.cells_per_row["Gallery"]
    cpr_m = SESSION.cells_per_row["Multichannel"]


    # Starting to add
    # SESSION.page_status_layers["Gallery"] = black_background('RGB', 1, userInfo.cells_per_row)
    # SESSION.page_status_layers["Multichannel"] = black_background('RGB',cpr_m, cpr_m)

    # print(f"Shapes are {SESSION.page_status_layers['Multichannel'].shape}  || {SESSION.page_status_layers['Gallery'].shape}")
    page_image_multichannel = {} ; page_image_gallery = {}
    for chn in userInfo.channels:
        if chn == 'Composite': continue
        page_image_gallery[chn] = black_background('Luminescence', 1, userInfo.cells_per_row)
        page_image_multichannel[chn] = black_background('Luminescence', cpr_m, cpr_m)

    # page_image = black_background('RGB',size_multiplier)

    nuclei_box_coords_g = []
    nuclei_box_coords_m = []
    print(f'Adding {len(cells)} cells to viewer... Channels are{userInfo.channels}')
    col_g = 0 
    row_g = 0 ; row_m = 0
    SESSION.grid_to_ID = {"Gallery":{}, "Multichannel":{}} # Reset this since we could be changing to multichannel mode
    cells = list(cells.values())
    cid_list = []
    edge_col_list = []
    status_box_coords_g = [] ; status_box_flags_g = []
    status_box_coords_m = [] ; status_box_flags_m = []

    while bool(cells): # coords left
        col_g = (col_g%cpr_g)+1 
        if col_g ==1: row_g+=1
        col_m = 1 ;  row_m+=1 

        # print(f'Next round of while. Still {len(cells)} cells left. G Row {row_g}, Col {col_g} || M Row {row_m}, Col {col_m}')
        cell = cells.pop(); 
        cell_anno = cell["Layer"]; cell_id = cell['cid']; cell_x = cell['center_x']; cell_y = cell['center_y']
        cname = str(cell_id) if cell_anno is None else f"{cell_anno} {cell_id}"
        cell_status = retrieve_status(cname,cell['validation_call'], new_page)
        cid_list.append(cell_id)
        edge_col_list.append(userInfo.statuses_hex[cell_status])


        x1 = int(cell["XMin"] + offset - cell_x) ; x2 = int(cell["XMax"] + offset - cell_x)
        y1 = int(cell["YMin"] + offset - cell_y) ; y2 = int(cell["YMax"] + offset - cell_y)
        cXg = (row_g-1)*(userInfo.imageSize+2) ; cYg = (col_g-1)*(userInfo.imageSize+2)
        cXm = (row_m-1)*(userInfo.imageSize+2) ; cYm = len(userInfo.channels)*(userInfo.imageSize+2)

        nuclei_box_coords_g.append([[cXg+y1, cYg+x1], [cXg+y2, cYg+x2]]) # x and y are actually flipped between napari and the object data
        nuclei_box_coords_m.append([[cXm+y1, cYm+x1], [cXm+y2, cYm+x2]]) 

        status_box_coords_g.append([[cXg, cYg], [cXg+(userInfo.imageSize+1), cYg+(userInfo.imageSize+1)]]) 
        status_box_coords_m.append([[cXm, 0], [cXm+(userInfo.imageSize+1), cYm+(userInfo.imageSize+1)]]) 
        status_box_flags_g.append([[cXg, cYg], [cXg+int(userInfo.imageSize/8), cYg+int(userInfo.imageSize/8)]]) 
        status_box_flags_m.append([[cXm, 0], [cXm+int(userInfo.imageSize/8), int(userInfo.imageSize/8)]]) 


        # Create array of channel indices in image data. Will use to fetch from the dask array
        positions = []
        for fluor, pos in userInfo.channelOrder.items(): # loop through channels
            if fluor in userInfo.channels and fluor != 'Composite':
                positions.append(pos)

        if RAW_PYRAMID is None:
            # print("Using zarr/dask")
            cell_punchout = SESSION.dask_array[positions,cell_y-offset:cell_y+offset, cell_x-offset:cell_x+offset].compute() # 0 is the largest pyramid layer         
        else:
            print("Using full size (raw) image. DANGER")
            # dask / zarr lazy reading didn't work, so entire image should be in memory as np array
            # This method is deprecated at this point. Probably won't work.
            cell_punchout = pyramid[cell_x-offset:cell_x+offset,cell_y-offset:cell_y+offset,pos].astype(np.uint8)
        # print(f'Trying to add {cell_name} layer with fluor-color(cm):{fluor}-{userInfo.channelColors[fluor]}')
        
        fluor_index = 0
        for fluor, pos in userInfo.channelOrder.items(): # loop through channels
            if fluor in userInfo.channels and fluor != 'Composite':
                # multichannel mode: individual image
                page_image_multichannel[fluor][(row_m-1)*(userInfo.imageSize+2)+1:row_m*(userInfo.imageSize+2)-1,
                            (col_m-1)*(userInfo.imageSize+2)+1:col_m*(userInfo.imageSize+2)-1] = cell_punchout[fluor_index,:,:]
                # multichannel mode: composite image
                page_image_multichannel[fluor][(row_m-1)*(userInfo.imageSize+2)+1:row_m*(userInfo.imageSize+2)-1,
                            (cpr_m-1)*(userInfo.imageSize+2)+1:cpr_m*(userInfo.imageSize+2)-1] = cell_punchout[fluor_index,:,:]
                SESSION.grid_to_ID["Multichannel"][f'{row_m},{col_m}'] = cname
                SESSION.grid_to_ID["Multichannel"][f'{row_m},{cpr_m}'] = cname
                # if col_m ==1:
                #     SESSION.page_status_layers["Multichannel"][(row_m-1)*(userInfo.imageSize+2):row_m*(userInfo.imageSize+2),:] = generate_status_box(cell_status, cell_anno +' '+ str(cell_id), "Multichannel")
                col_m+=1 # so that next luminescence image is tiled 
                
                # Gallery images 
                SESSION.grid_to_ID["Gallery"][f'{row_g},{col_g}'] = cname
                page_image_gallery[fluor][(row_g-1)*(userInfo.imageSize+2)+1:row_g*(userInfo.imageSize+2)-1, (col_g-1)*(userInfo.imageSize+2)+1:col_g*(userInfo.imageSize+2)-1] = cell_punchout[fluor_index,:,:]
                # SESSION.page_status_layers["Gallery"][(row_g-1)*(userInfo.imageSize+2):row_g*(userInfo.imageSize+2), (col_g-1)*(userInfo.imageSize+2):col_g*(userInfo.imageSize+2)] = generate_status_box(cell_status, cell_anno +' '+ str(cell_id), "Gallery")
                fluor_index+=1

    gal_vis = True if SESSION.mode == "Gallery" else False
    mult_vis = not gal_vis
    print(f"\nMy scale is {SESSION.image_scale}")
    sc = (SESSION.image_scale, SESSION.image_scale) if SESSION.image_scale is not None else None
    # viewer.add_image(white_background(1, userInfo.cells_per_row).astype(np.uint8), name = "Gallery Absorption", 
    #                                               blending = 'translucent', visible = SESSION.absorption_mode and gal_vis, scale =sc )
    # viewer.add_image(white_background(cpr_m, cpr_m).astype(np.uint8), name = "Multichannel Absorption", 
    #                                               blending = 'translucent', visible = SESSION.absorption_mode and mult_vis, scale =sc )
    for fluor in list(page_image_gallery.keys()):
        print(f"Adding layers now. fluor is {fluor}")
        if fluor == 'Composite':
            continue # The merged composite consists of each layer's pixels blended together, so there is no composite layer itself
        if SESSION.absorption_mode:
            viewer.add_image(page_image_gallery[fluor], name = f"Gallery {fluor}", blending = 'minimum',
                 colormap = custom_color_functions.retrieve_cm(userInfo.channelColors[fluor]+' inverse'), scale = sc, interpolation="linear", visible =gal_vis)
            viewer.add_image(page_image_multichannel[fluor], name = f"Multichannel {fluor}", blending = 'minimum',
                 colormap = custom_color_functions.retrieve_cm(userInfo.channelColors[fluor]+' inverse'), scale = sc, interpolation="linear", visible=mult_vis)
            
        else:
            viewer.add_image(page_image_gallery[fluor], name = f"Gallery {fluor}", blending = 'additive',
                 colormap = custom_color_functions.retrieve_cm(userInfo.channelColors[fluor]), scale = sc, interpolation="linear", visible=gal_vis)
            viewer.add_image(page_image_multichannel[fluor], name = f"Multichannel {fluor}", blending = 'additive',
                 colormap = custom_color_functions.retrieve_cm(userInfo.channelColors[fluor]), scale = sc, interpolation="linear", visible=mult_vis)
    # if composite_only:

    features = {'cid': cid_list}
    nb_color_str = edge_col_list #'black' if SESSION.absorption_mode else 'white'
    # nb_color_str = ['#000000' for x in nb_color_str if SESSION.absorption_mode and (x == '#ffffff')]
    # nb_color_str = ['#ffffff' for x in nb_color_str if (not SESSION.absorption_mode) and (x == '#000000')] 

    nb_color_hex = '#000000' if SESSION.absorption_mode else '#ffffff'
    tl = int(userInfo.imageSize/8)#* (1 if SESSION.image_scale is None else SESSION.image_scale)
    nb_text = {'string':'{cid}', 'anchor':'lower_left', 'size' : 8,'translation':[-(userInfo.imageSize),int(tl*1.3)], 'color':nb_color_str}
    SESSION.status_text_object = nb_text
    viewer.add_shapes(nuclei_box_coords_g, name="Gallery Nuclei Boxes", shape_type="rectangle", edge_width=1, edge_color=nb_color_hex, 
                                        face_color='#00000000', scale=sc, visible=False)
    viewer.add_shapes(nuclei_box_coords_m, name="Multichannel Nuclei Boxes", shape_type="rectangle", edge_width=1, edge_color=nb_color_hex, 
                                        face_color='#00000000', scale=sc, visible = False)
    
    # print(status_box_coords_g)
    # print(edge_col_list)

    viewer.add_shapes(status_box_coords_g, name="Gallery Status Edges", shape_type="rectangle", edge_width=1, edge_color=edge_col_list, 
                                        face_color='#00000000', scale=sc, visible=False, opacity=1)
    viewer.add_shapes(status_box_coords_m, name="Multichannel Status Edges", shape_type="rectangle", edge_width=1, edge_color=edge_col_list, 
                                        face_color='#00000000', scale=sc, visible=False, opacity=1)
    viewer.add_shapes(status_box_flags_g, name="Gallery Status Squares", shape_type="rectangle", edge_width=1, edge_color=edge_col_list, 
                                        face_color=edge_col_list, scale=sc, visible=gal_vis, opacity=1)
    viewer.add_shapes(status_box_flags_m, name="Multichannel Status Squares", shape_type="rectangle", edge_width=1, edge_color=edge_col_list, 
                                        face_color=edge_col_list, scale=sc, visible=mult_vis, opacity=1)
    viewer.add_shapes(status_box_coords_g, name="Gallery Status Numbers", shape_type="rectangle", edge_width=0, face_color='#00000000',
                                            features=features, text = nb_text,
                                            scale=sc, visible=gal_vis, opacity=1)
    viewer.add_shapes(status_box_coords_m, name="Multichannel Status Numbers", shape_type="rectangle", edge_width=0, 
                                            features=features, text = nb_text, face_color = "#00000000",
                                            scale=sc, visible=mult_vis, opacity=1)
    # viewer.add_image(SESSION.page_status_layers["Gallery"].astype(np.uint8), name='Gallery Status Layer', interpolation='linear', scale = sc, visible=gal_vis)
    # viewer.add_image(SESSION.page_status_layers["Multichannel"].astype(np.uint8), name='Multichannel Status Layer', interpolation='linear', scale = sc, visible=mult_vis)
    # viewer.layers.selection.active = viewer.layers["Status Layer"]
    
    VIEWER.layers.selection.active = VIEWER.layers[f"Gallery {userInfo.channels[0]}"]  
    

    #TODO make a page label... 

    # Exiting add_layers function

    return True

###################################################################
######---------------- Viewer Key Bindings, -----------------######
###################################################################

def catch_exceptions_to_log_file(error_type="runtime-exception"):
    def custom_error(func):
        def wrapper(*args, **kwargs):
            try:
                func(*args, **kwargs)
            except Exception as e:
                userInfo.log_exception(e, error_type=error_type)
                VIEWER.status = f"Encountered a non-critical error when attempting to '{func.__name__}'. Please forward the error log to the developer"
        return wrapper
    return custom_error

# @catch_exceptions_to_log_file
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
        offset_x = (userInfo.imageSize+2) * list(userInfo.channels).index(fluor)
        return (global_y, offset_x+local_x)
    

    '''Locate mouse on the canvas. Returns the name of the cell under the mouse, current mouse 
        coordinates, and pixel values for each channel in a dict'''
    # @catch_exceptions_to_log_file("runtime_find-mouse")
    def find_mouse(data_coordinates, scope = 'world'):
        
        # print(f"{data_coordinates}")
        SESSION.mouse_coords = data_coordinates

                # retrieve cell ID name
        # Scale data coordinates to image. Then round to nearest int, representing the coord or the image pixel under the mouse
        sc = 1.0 if SESSION.image_scale is None else SESSION.image_scale
        data_coordinates = tuple([x/sc for x in data_coordinates])
        coords = tuple(np.round(data_coordinates).astype(int))
        vals = {} # will hold fluor : pixel intensity pairs 

        if coords[0] < 0 or coords[1]<0:
            if SESSION.mode == "Context": return {"cell":None,"coords": None,"vals": None}
            return "None" , None, None
        if SESSION.mode == "Context":
            for fluor in userInfo.channels:
                if fluor == "Composite": continue

                # Requesting single pixel value from Dask array layer 0
                try:
                    v = str(int(viewer.layers["Context "+fluor].data[0][coords]))
                except IndexError:
                    v = None # Seems like this exception can trigger sometimes if you are very far off the canvas maybe
                vals[fluor] =  v if v is not None else "-"
            
            # Now find the name of the closest cell 
            dist, closest_ind = SESSION.kdtree.query([data_coordinates[1],data_coordinates[0]])
            if dist < .6*userInfo.imageSize:
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
            for fluor in userInfo.channels:
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

    @catch_exceptions_to_log_file("runtime_box-cell-near-mouse")
    def box_closest_context_mode_cell(cell):
        if not SESSION.cell_under_mouse_changed:  # Save computation and don't do this unless needed
            return False 
        elif SESSION.nuclei_boxes_vis["Context"] != "Mouse": # Don't run the regular routine unless the "Show under mouse only" radio is toggled on
            try:
                VIEWER.layers.selection.active = VIEWER.layers["Context Closest Cell Box"]
                VIEWER.layers.remove_selected()
            except KeyError:
                pass
            return False
        try:
            VIEWER.layers.selection.active = VIEWER.layers["Context Closest Cell Box"]
            VIEWER.layers.remove_selected()
        except KeyError:
            pass
        
        #Reset flag. Important!!!
        SESSION.cell_under_mouse_changed = False
        layer = cell["Layer"]; cid = cell["cid"]
        cname = cid if layer is None else f"{layer} {cid}"
        features = {'cid_feat': [cid]}
        cell_bbox = [[cell["YMin"],cell["XMin"]] , [cell["YMax"],cell["XMax"]] ]

        sc = (SESSION.image_scale, SESSION.image_scale) if SESSION.image_scale is not None else None
        nb_color_hex = userInfo.statuses_hex[SESSION.status_list[cname]] #'#000000' if SESSION.absorption_mode else '#ffffff'
        nb_text = {'string':'{cid_feat}', 'anchor':'upper_left', 'size' : 8, 'color':nb_color_hex}
        SESSION.context_closest_cell_text_object = nb_text
        VIEWER.add_shapes([cell_bbox], name="Context Closest Cell Box", shape_type="rectangle", edge_width=2, edge_color=nb_color_hex, 
                        opacity=0.9, face_color='#00000000', scale=sc, text = nb_text, features=features)
        VIEWER.layers.selection.active = VIEWER.layers[f"Gallery {userInfo.channels[0]}"] 

    ''' You need to disable napari's native mouse callback that displays the status first.
            This function is in napari.components.viewer_model.py ViewerModel._update_status_bar_from_cursor''' 
    @viewer.mouse_move_callbacks.append
    def display_intensity_wrapper(viewer, event):
        display_intensity(viewer,event)

    @catch_exceptions_to_log_file("runtime_process-cell-under-mouse")
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
            # print(kw_res)
            if (vals is None) or (next(iter(vals.values())) is None):
                # Don't do anything else - the cursor is out of bounds of the image
                VIEWER.status = 'Out of bounds'
                return True 
            
            if cell is not None:
                cid = cell["Object Id"]
                layer = cell["Analysis Region"] if ANNOTATIONS_PRESENT else None
                ckey = f'{layer} {cid}' if ANNOTATIONS_PRESENT else str(cid)
                try:
                    cell_dict = SESSION.current_cells[ckey]
                    if cell_dict != SESSION.cell_under_mouse: SESSION.cell_under_mouse_changed = True
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
                    SESSION.cell_under_mouse_changed = True # If we haven't seen this cell before, it has definitely changed.
                # Now that we have the cell dict, proceed to display
                SESSION.cell_under_mouse =  cell_dict # save info
                set_notes_label(ckey)
                # Draw box around closest cell
                box_closest_context_mode_cell(cell_dict)
            else: # Not near a cell
                set_notes_label(None, display_text_override="No cell nearby to show!")
                try:
                    VIEWER.layers.selection.active = VIEWER.layers["Context Closest Cell Box"]
                    VIEWER.layers.remove_selected()
                except KeyError:
                    pass
                # reset active layer to an image
                viewer.layers.selection.active = viewer.layers[f"Gallery {userInfo.channels[0]}"] 

                

            # print(f"Vals is type {type(vals)} and content is {vals}")
            # exit()
            # Deal with pixel intensities
            
            output_str = ''
            for fluor, val in vals.items():
                if val != "-": val = int(val)
                output_str+= f'<font color="{userInfo.channelColors[fluor].replace("blue","#0462d4")}">    {val}   </font>'
            sc = STATUSES_TO_HEX[SESSION.status_list[str(ckey)]] if cell is not None else ''
            if not sc == "#ffffff":
                VIEWER.status = f'<font color="{sc}">Context Mode</font> pixel intensities at {coords}: {output_str}'
            else:
                VIEWER.status = f'Context Mode pixel intensities at {coords}: {output_str}'
        elif SESSION.mode == "Gallery" or SESSION.mode == "Multichannel":
            try:
                cell_name,coords,vals = find_mouse(event.position, scope = 'grid') 
            except TypeError:
                # find_mouse seems to be returning NoneType sometimes (no idea why) which can't be unpacked
                return False
            
            if vals is None:
                # Don't do anything else
                VIEWER.status = 'Out of bounds'
                return True
            SESSION.cell_under_mouse = SESSION.current_cells[cell_name] # save info
            cell_num = cell_name.split()[-1]; cell_anno = cell_name.replace(' '+cell_num,'')

            if ANNOTATIONS_PRESENT:
                image_name = f'Cell {cell_num} from {cell_anno}'
            else:
                image_name = f'Cell {cell_num}'

            set_notes_label(str(cell_name))
            output_str = ''

            for fluor, val in vals.items():
                if val != "-": val = int(val)
                output_str+= f'<font color="{userInfo.channelColors[fluor].replace("blue","#0462d4")}">    {val}   </font>'
        
            sc = STATUSES_TO_HEX[SESSION.status_list[str(cell_name)]]
            if sc != "#ffffff":
                VIEWER.status = f'<font color="{sc}">{image_name}</font> intensities at {coords}: {output_str}'
            else:
                VIEWER.status = f'{image_name} intensities at {coords}: {output_str}'


    SESSION.display_intensity_func = display_intensity
    SESSION.find_mouse_func = find_mouse
    #TODO trigger pixel readout update when pan or zoom occurs

    # viewer.camera.events.connect(display_intensity)
    # napari.Viewer.camera.zoom.

    def change_status_display(cell_name, next_status):
        next_color_txt = userInfo.statuses_rgba[next_status]
        next_color_txt = list(x/255 if next_color_txt.index(x)!=3 else 1 for x in next_color_txt)

        SESSION.status_list[str(cell_name)] = next_status
        set_notes_label(str(cell_name)) 
        # Change gallery mode status layer
        try:
            ind_target = list(SESSION.grid_to_ID["Gallery"].values()).index(str(cell_name))
            x = viewer.layers["Gallery Status Squares"].face_color
            x[ind_target] = next_color_txt
            viewer.layers["Gallery Status Squares"].face_color = x 
            viewer.layers["Multichannel Status Squares"].face_color = x

            viewer.layers["Gallery Status Squares"].edge_color = x
            viewer.layers["Multichannel Status Squares"].edge_color = x

            SESSION.status_text_object["color"][ind_target] = next_color_txt
            viewer.layers["Gallery Status Numbers"].text = SESSION.status_text_object
            viewer.layers["Multichannel Status Numbers"].text = SESSION.status_text_object
 
        except (KeyError, ValueError) as e:
            # Changing a cell status that isn't in the current page using Context Mode.
            print(e)
        
        print(f"!!! {SESSION.mode} {SESSION.context_nuclei_boxes_text_object} {SESSION.context_nuclei_boxes_map_to_ind}")
        if SESSION.mode =="Context" and SESSION.context_nuclei_boxes_text_object is not None and SESSION.context_nuclei_boxes_map_to_ind:
            try:
                print("In function")
                ind_target = SESSION.context_nuclei_boxes_map_to_ind[str(cell_name)]
                x = viewer.layers["Context Nuclei Boxes"].edge_color
                x[ind_target] = next_color_txt
                viewer.layers["Context Nuclei Boxes"].edge_color = x
                SESSION.context_nuclei_boxes_text_object["color"] = x
                viewer.layers["Context Nuclei Boxes"].text = SESSION.context_nuclei_boxes_text_object
            except (KeyError, ValueError) as e:
            # Changing a cell status that isn't in the current page using Context Mode.
                print(e)

    def change_status_display_forAll(next_status):
        next_color_txt = userInfo.statuses_rgba[next_status]
        next_color_txt = list(x/255 if next_color_txt.index(x)!=3 else 1 for x in next_color_txt)

        # set all cells to status
        for coords, cell_id in SESSION.grid_to_ID[SESSION.mode].items():
            SESSION.status_list[str(cell_id)] = next_status
        # Change gallery mode status layer
        try:
            x = viewer.layers["Gallery Status Squares"].face_color
            x = [next_color_txt for y in x]
            viewer.layers["Gallery Status Squares"].face_color = x 
            x = viewer.layers["Gallery Status Squares"].edge_color
            x = [next_color_txt for y in x]
            viewer.layers["Gallery Status Squares"].edge_color = x

            SESSION.status_text_object["color"] = [next_color_txt for y in SESSION.status_text_object["color"]]
            viewer.layers["Gallery Status Numbers"].text = SESSION.status_text_object

            x = viewer.layers["Multichannel Status Squares"].face_color
            x = [next_color_txt for y in x]
            viewer.layers["Multichannel Status Squares"].face_color = x 
            x = viewer.layers["Multichannel Status Squares"].edge_color
            x = [next_color_txt for y in x]
            viewer.layers["Multichannel Status Squares"].edge_color = x

            viewer.layers["Multichannel Status Numbers"].text = SESSION.status_text_object
            
        except (KeyError, ValueError):
            # Changing a cell status that isn't in the current page using Context Mode.
            pass 

    # @viewer.bind_key('j')
    @viewer.bind_key('Space', overwrite = True)
    @viewer.bind_key('Ctrl-Space', overwrite = True)
    @catch_exceptions_to_log_file("runtime_assign-next-status")
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

        if SESSION.mode == "Context" and SESSION.nuclei_boxes_vis["Context"] == "Mouse":
            # Change Context boxes and mouse only box colors
            VIEWER.layers["Context Closest Cell Box"].edge_color = userInfo.statuses_hex[next_status]
            SESSION.context_closest_cell_text_object["color"] = userInfo.statuses_hex[next_status]
            viewer.layers["Context Closest Cell Box"].text = SESSION.context_closest_cell_text_object
        change_status_display(cell_name, next_status)
        # change color of viewer status
        vstatus_list = copy.copy(VIEWER.status).split('>')
        vstatus_list[0] = sub(r'#.{6}',STATUSES_TO_HEX[SESSION.status_list[str(cell_name)]], vstatus_list[0])
        VIEWER.status = ">".join(vstatus_list)

    @viewer.mouse_drag_callbacks.append
    @catch_exceptions_to_log_file("runtime_left-click-cell")
    def user_clicked(viewer, event):
        #TODO decide on the behavior for clicking on a cell
        
        layer = SESSION.cell_under_mouse['Layer']
        cid = str(SESSION.cell_under_mouse['cid'])
        # Allow user to click on a cell to get it's name into the entry box  
        if ANNOTATIONS_PRESENT:
            SESSION.widget_dictionary['notes annotation combo'].setCurrentText(layer)
            if SESSION.mode == "Context":
                SESSION.widget_dictionary['page cell layer'].setCurrentText(layer)
            SESSION.widget_dictionary['switch mode annotation'].setCurrentText(layer)
        
        SESSION.widget_dictionary['notes cell entry'].setText(cid)
        if SESSION.mode == "Context":
            SESSION.widget_dictionary['page cell id'].setText(cid)
        SESSION.widget_dictionary['switch mode cell'].setText(cid)

    ''' Dynamically make new functions that can change scoring decisions with a custom keypress. This
        will allow the user to choose their own scoring decisions, colors, and keybinds'''
    def create_score_funcs(scoring_decision, keybind):
        @viewer.bind_key(keybind)
        @catch_exceptions_to_log_file("runtime_change-status")
        def set_score(viewer):
            if SESSION.mode == "Context": 
                cell = SESSION.cell_under_mouse
                if cell is None:
                    return False # leave if the mouse is not near a cell (not sure that this could even happen)
                cell_name = f"{cell['Layer']} {cell['cid']}"     
            else:
                cell_name,data_coordinates,val = find_mouse(viewer.cursor.position)
                if val is None:
                    return None
            
            if SESSION.mode == "Context" and SESSION.nuclei_boxes_vis["Context"] == "Mouse":
                # Change Context boxes and mouse only box colors
                VIEWER.layers["Context Closest Cell Box"].edge_color = userInfo.statuses_hex[scoring_decision]
                SESSION.context_closest_cell_text_object["color"] = userInfo.statuses_hex[scoring_decision]
                viewer.layers["Context Closest Cell Box"].text = SESSION.context_closest_cell_text_object
            change_status_display(cell_name, scoring_decision)

            # change color of viewer status
            vstatus_list = copy.copy(VIEWER.status).split('>')
            vstatus_list[0] = sub(r'#.{6}',STATUSES_TO_HEX[SESSION.status_list[str(cell_name)]], vstatus_list[0])
            VIEWER.status = ">".join(vstatus_list)

        @viewer.bind_key(f'Control-{keybind}')
        @viewer.bind_key(f'Shift-{keybind}')
        @catch_exceptions_to_log_file("runtime_change-status-all")
        def set_scoring_all(viewer):
            if SESSION.mode == "Context": return None
            
            change_status_display_forAll(scoring_decision)

            cell_name,data_coordinates,val = find_mouse(viewer.cursor.position)
            if val is None:
                return None
            set_notes_label(str(cell_name))
            vstatus_list = copy.copy(VIEWER.status).split('>')
            vstatus_list[0] = sub(r'#.{6}',STATUSES_TO_HEX[SESSION.status_list[str(cell_name)]], vstatus_list[0])
            VIEWER.status = ">".join(vstatus_list)
        return set_score, set_scoring_all

    for scoring_decision, keybind in userInfo.statuses.items():
        score_name = f'{scoring_decision}_func'
        score_all_name = f"{scoring_decision}_all_func"
        exec(f'globals()["{score_name}"], globals()["{score_all_name}"] = create_score_funcs("{scoring_decision}","{keybind}")')

    ''' This function is called on a Control+left click. USed currently to changee to context mode and back'''
    @viewer.mouse_drag_callbacks.append
    @catch_exceptions_to_log_file("runtime_change-session-mode-on-click")
    def load_context_mode(viewer, event):
        print(event.modifiers)
        if ("Control" in event.modifiers) and ("Shift" in event.modifiers):
            pass
        elif "Shift" in event.modifiers:
            if SESSION.mode == "Multichannel":
                toggle_session_mode_catch_exceptions(SESSION.last_mode)
            else:
                layer = SESSION.cell_under_mouse["Layer"]
                cid = str(SESSION.cell_under_mouse["cid"])
                SESSION.widget_dictionary['switch mode annotation'].setCurrentText(layer)
                SESSION.widget_dictionary['switch mode cell'].setText(cid)
                toggle_session_mode_catch_exceptions("Multichannel")
        elif "Control" in event.modifiers:
            # Go to context or go back to last mode
            if SESSION.mode == "Context":
                toggle_session_mode_catch_exceptions(SESSION.last_mode)
            else:
                layer =SESSION.cell_under_mouse["Layer"]
                cid = str(SESSION.cell_under_mouse["cid"])
                SESSION.widget_dictionary['switch mode annotation'].setCurrentText(layer)
                SESSION.widget_dictionary['switch mode cell'].setText(cid)
                toggle_session_mode_catch_exceptions("Context")

    #TODO catch exceptions here? Probably need to inform the user.
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

    @viewer.bind_key('h')
    @catch_exceptions_to_log_file("runtime_toggle-status")
    def toggle_statuslayer_visibility(viewer):
        # raise Exception(f"This should work!")
        if SESSION.mode == "Context":
            return False
        show_vis_radio = SESSION.widget_dictionary['show status layer radio']
        hide_vis_radio = SESSION.widget_dictionary['hide status layer radio']
        if show_vis_radio.isChecked():
            show_vis_radio.setChecked(False)
            hide_vis_radio.setChecked(True)
        else:
            show_vis_radio.setChecked(True)
            hide_vis_radio.setChecked(False)

    # @viewer.bind_key('Control-h')
    # def toggle_statusbox_visibility(viewer):
    #     show_box_radio = SESSION.widget_dictionary['show status box radio']
    #     hide_box_radio = SESSION.widget_dictionary['hide status box radio']
    #     if show_box_radio.isChecked():
    #         show_box_radio.setChecked(False)
    #         hide_box_radio.setChecked(True)
    #     else:
    #         show_box_radio.setChecked(True)
    #         hide_box_radio.setChecked(False)
    
    ''' Toggles to the next GUI radio button given the current session, and also changes the session variable to
        track the current state '''
    @viewer.bind_key('Shift-h')
    @catch_exceptions_to_log_file("runtime_toggle-cell-boxes")
    def toggle_boxes_wrapper(viewer):
        if SESSION.mode != "Context":
            if SESSION.nuclei_boxes_vis["Gallery/Multichannel"]:
                SESSION.widget_dictionary['hide boxes'].setChecked(True)
            else:
                SESSION.widget_dictionary['show boxes'].setChecked(True)
        else: # Context Mode
            cur = ["Show","Hide","Mouse"].index(SESSION.nuclei_boxes_vis["Context"])
            new = ["Show","Hide","Mouse"][(cur+1)%3]
            SESSION.widget_dictionary[f"{new.lower()} boxes"].setChecked(True)
    
    @viewer.bind_key('Control-k')
    def restore_canvas(viewer):
        set_viewer_to_neutral_zoom(viewer)

    @viewer.bind_key('k')
    def recenter_canvas(viewer):
        set_viewer_to_neutral_zoom(viewer)

    class dummyCursor:
        def __init__(self, y, x) -> None:
            self.position = (y,x)

    @viewer.bind_key('Up')
    @catch_exceptions_to_log_file("runtime_arrow-pan")
    def scroll_up(viewer):
        z,y,x = viewer.camera.center
        sc = 1 if SESSION.image_scale is None else SESSION.image_scale
        step_size = ((userInfo.imageSize+2)*sc)

        viewer.camera.center = (y-step_size,x)

        curY, curX = SESSION.mouse_coords
        display_intensity(viewer, dummyCursor(curY-step_size, curX))
        # SESSION.mouse_coords = (curX, curY-step_size)

    @viewer.bind_key('Down')
    @catch_exceptions_to_log_file("runtime_arrow-pan")
    def scroll_down(viewer):
        z,y,x = viewer.camera.center
        sc = 1 if SESSION.image_scale is None else SESSION.image_scale
        step_size = ((userInfo.imageSize+2)*sc)

        viewer.camera.center = (y+step_size,x)

        curY, curX = SESSION.mouse_coords
        display_intensity(viewer, dummyCursor(curY+step_size, curX))
        # SESSION.mouse_coords = (curX, curY+step_size)
    
    @viewer.bind_key('Left')
    @catch_exceptions_to_log_file("runtime_arrow-pan")
    def scroll_left(viewer):
        z,y,x = viewer.camera.center
        sc = 1 if SESSION.image_scale is None else SESSION.image_scale
        step_size = ((userInfo.imageSize+2)*sc)

        viewer.camera.center = (y,x-step_size)
        curY, curX = SESSION.mouse_coords
        display_intensity(viewer, dummyCursor(curY,curX-step_size))
        # SESSION.mouse_coords = (curX-step_size, curY)

        #TODO trigger mouse update here
        # napari.Viewer.window.qt_viewer._process_mouse_event
        # viewer.window.qt_viewer.canvas.events.mouse_press(pos=(x, y), modifiers=(), button=0)
        # viewer.cursor.position = viewer.window.qt_viewer._map_canvas2world([x,y])

    @viewer.bind_key('Right')   
    @catch_exceptions_to_log_file("runtime_arrow-pan")
    def scroll_right(viewer):
        z,y,x = viewer.camera.center
        sc = 1 if SESSION.image_scale is None else SESSION.image_scale
        step_size = ((userInfo.imageSize+2)*sc)
        viewer.camera.center = (y,x+step_size)
        curY, curX = SESSION.mouse_coords
        # SESSION.mouse_coords = (curX+step_size, curY)\
        display_intensity(viewer, dummyCursor(curY, curX+step_size))


    # On Macs, ctrl-arrow key is taken by something else.
    @viewer.bind_key('Shift-Right')  
    @viewer.bind_key('Shift-Up') 
    @viewer.bind_key('Control-Right')  
    @viewer.bind_key('Control-Up')   
    @catch_exceptions_to_log_file("runtime_arrow-zoom")
    def zoom_in(viewer):
        step_size = 1.15
        # _,y,x = viewer.camera.center
        # curY, curX = SESSION.mouse_coords
        # print(f"Before moving, camera coords are {viewer.camera.center}")
        # print(f"Mouse coords are z, {curY} {curX}")
        # print(f"Will move to {curY+(y-curY)*(step_size-1)} {curX+((x-curX)*(step_size-1))}")
        # print(f"Zoom level is {viewer.camera.zoom}\n")
        # display_intensity(viewer, dummyCursor(curY+((y-curY)*(step_size-1)), curX+((x-curX)*(step_size-1)) ))
        viewer.camera.zoom *= step_size


    # @viewer.mouse_move_callbacks.append
    # def zoom_out_wrapper(viewer, event):
    #     zoom_out(viewer, event)

    @viewer.bind_key('Shift-Left')  
    @viewer.bind_key('Shift-Down') 
    @viewer.bind_key('Control-Left')  
    @viewer.bind_key('Control-Down')  
    @catch_exceptions_to_log_file("runtime_arrow-zoom")
    def zoom_out(viewer):
        step_size = 1.15
        # _,y,x = viewer.camera.center
        # curY, curX = SESSION.mouse_coords
        # print(f"Before moving, camera coords are {viewer.camera.center}")
        # print(f"Mouse coords are z, {curY} {curX}")
        # print(f"Will move to {(curY - (y*(step_size-1))) / (2-step_size)} {(curX - (x*(step_size-1))) / (2-step_size)}")

        # print(f"Zoom level is {viewer.camera.zoom}\n")
        # # (step_size-1) + (1-step_size)
        # display_intensity(viewer, dummyCursor((curY - (y*(step_size-1))) / (2-step_size), (curX - (x*(step_size-1))) / (2-step_size) ))
        viewer.camera.zoom /= step_size  
        

    
    @viewer.bind_key('a', overwrite=True)
    @viewer.bind_key('Ctrl-a', overwrite=True)
    @catch_exceptions_to_log_file("runtime_toggle-absorption")
    def trigger_absorption(viewer):
        toggle_absorption()
    
    @viewer.bind_key('r')
    @catch_exceptions_to_log_file("runtime_reset-viewsettings")
    def reset_viewsettings(viewer):
        global ADJUSTMENT_SETTINGS
        ADJUSTMENT_SETTINGS = copy.copy(ORIGINAL_ADJUSTMENT_SETTINGS)
        reuse_gamma()
        reuse_contrast_limits()
    
    @viewer.bind_key('i')
    @catch_exceptions_to_log_file("runtime_switch-interpolation")
    def toggle_interpolation(viewer):
        current = VIEWER.layers[f"Gallery {userInfo.channels[0]}"].interpolation
        if current == 'nearest':
            new = 'linear'
        else:
            new = 'nearest' 
        for fluor in userInfo.channels:
            if fluor =='Composite': continue
            VIEWER.layers["Gallery " +fluor].interpolation = new
            VIEWER.layers["Multichannel "+fluor].interpolation = new
            VIEWER.layers["Context "+fluor].interpolation = new

    @viewer.bind_key('Alt-m')
    @catch_exceptions_to_log_file("runtime_open-manual")
    def open_guide(viewer):
        os.startfile(os.path.normpath(os.curdir+ r"/data/GalleryViewer v{x} User Guide.pdf".format(x=VERSION_NUMBER)))


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


def chn_key_wrapper(viewer):
    def create_fun(position,channel):
        @viewer.bind_key(str(position+1), overwrite=True)
        def toggle_channel_visibility(viewer,pos=position,chn=channel):
            
            widget_obj = UPDATED_CHECKBOXES[pos]
            if widget_obj.isChecked():
                widget_obj.setChecked(False)
            else:
                widget_obj.setChecked(True)
            viewer.window._qt_viewer.setFocus()
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
    if ANNOTATIONS_PRESENT:
        ID = str(cell_row['Analysis Region']) + ' ' + str(cell_row['Object Id'])
    else:
        ID = str(cell_row['Object Id'])
    SESSION.saved_notes[ID] = cell_row['Notes']
    # Find out which columns are present in the Series and subset to those
    present_intensities = sorted(list(set(list(cell_row.index)).intersection(set(intensity_col_names))))
    cell_row = cell_row.loc[present_intensities]
    SAVED_INTENSITIES[ID] = cell_row
    # print(f'dumping dict {SESSION.saved_notes}')

'''Get object data from csv and parse.''' 
def extract_phenotype_xldata(page_size=None, phenotypes=None,annotations = None, page_number = 1, 
                            specific_cell = None, sort_by_intensity = None, combobox_widget = None):
    
    # None means 'don't do it', while a channel name means 'put highest at the top'
    if sort_by_intensity is None:
        sort_by_intensity = "Object Id"
    else:
        sort_by_intensity = sort_by_intensity
   
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
            GLOBAL_SORT = [x for x in all_possible_intensities if all(y in x for y in GLOBAL_SORT.replace("Cell Intensity",""))][0]
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
        # print(query)
        return query.rstrip(" |")
    ''' Helper function to create a query that will filter by intensity'''
    def _create_filter_query(filters):
        query = ''
        for fil in filters:
            if ">" in fil:
                intensity_column, fil = fil.split(">")
                compare = ">"
            elif "<" in fil:
                intensity_column, fil = fil.split("<")
                compare = "<"
            else:
                raise ValueError # Not the expected input
            
            query += f"(`{intensity_column.strip()}` {compare} {fil.strip()}) &"  
        # print(query)
        return query.rstrip(" &")

    # print('page code start')
    # Apply filters here
    if annotations or phenotypes:
        phen_only_df = halo_export.query(_create_anno_pheno_query(annotations,phenotypes)).reset_index()
    else:
        phen_only_df = halo_export.reset_index()
    if userInfo.filters:
        phen_only_df = phen_only_df.query(_create_filter_query(userInfo.filters)).reset_index()

    # Figure out which range of cells to get based on page number and size
    last_page = (len(phen_only_df.index) // page_size)+1
    combobox_widget =  SESSION.widget_dictionary['page combobox']
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
        layer = row["Analysis Region"] if ANNOTATIONS_PRESENT else None
        ckey = f'{layer} {cid}' if ANNOTATIONS_PRESENT else str(cid)
        fetch_notes(row, all_possible_intensities)
        center_x = int((row['XMax']+row['XMin'])/2)
        center_y = int((row['YMax']+row['YMin'])/2)
        vals = row[validation_cols]
        try:
            validation_call = str(vals[vals == 1].index.values[0]).replace(f"Validation | ", "")
        except IndexError:
            # row has no validation call (all zeroes). Assign to Unseen
            validation_call = "Unseen"

        tumor_cell_XYs[ckey] = {'Layer':layer,"cid": cid,"center_x": center_x,'center_y': center_y,
                                'validation_call': validation_call, 'XMax' : row['XMax'],'XMin':row['XMin'],
                                'YMax' : row['YMax'],'YMin':row['YMin']}

    SESSION.current_cells = copy.copy(tumor_cell_XYs)
    SESSION.cell_under_mouse = next(iter(tumor_cell_XYs.values())) # Set first cell in list as "current" to avoid exceptions
    return tumor_cell_XYs

def replace_note(cell_widget, note_widget):
    cellID = cell_widget.text(); note = note_widget.text()
    if ANNOTATIONS_PRESENT:
        annotation_layer = SESSION.widget_dictionary['notes annotation combo'].currentText()
        cellID = f"{annotation_layer} {cellID}"

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
    global userInfo, qptiff, PAGE_SIZE, STATUS_COLORS, STATUSES_TO_HEX, STATUSES_RGBA
    global  OBJECT_DATA_PATH, PHENOTYPES, ANNOTATIONS, SPECIFIC_CELL, GLOBAL_SORT, CELLS_PER_ROW
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
    
    if "Composite" not in list(userInfo.channelColors.keys()): userInfo.channelColors['Composite'] = 'None'
    

    userInfo.active_channels = copy.copy(userInfo.channels)
    userInfo.active_channels.append("Composite")
    if userInfo.global_sort == "Sort object table by Cell Id":
        GLOBAL_SORT = None
    else :
        chn = userInfo.global_sort.replace("Sort object table by ","")
        GLOBAL_SORT = chn

    # set saving flag so that dataframe will be written upon exit
    userInfo.session.saving_required = True # make the app save it's data on closing
    main(preprocess_class)

def main(preprocess_class = None):
    #TODO do this in a function because this is ugly

    global RAW_PYRAMID, VIEWER
    if preprocess_class is not None: preprocess_class.status_label.setVisible(True)
    preprocess_class._append_status_br("Checking data pipe to image...")
    start_time = time.time()

    print(f'\nChecking if image can be lazily loaded with dask / zarr {qptiff}...\n')
    try:
        with tifffile.imread(userInfo.qptiff_path, aszarr=True) as zs:
            SESSION.dask_array =  da.from_zarr(zs, 0) # Saves a path to the image data that can be used later

        
        pyramid = None
        preprocess_class._append_status('<font color="#7dbc39">  Done.</font>')
        preprocess_class._append_status_br('Sorting object data...')
    except:
        preprocess_class._append_status('<font color="#f5551a">  Failed.</font> Attempting to load image as memory-mapped object...')
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

    # Get rid of problematic bindings before starting napari viewer
    settings=get_settings()
    for binding in ["napari:hold_for_pan_zoom","napari:activate_image_pan_zoom_mode", "napari:activate_image_transform_mode"]:
        try:
            print(settings.shortcuts.shortcuts.pop(binding))
        except KeyError:
            print("Keyerror")
            pass
    
    viewer = napari.Viewer(title=f'GalleryViewer v{VERSION_NUMBER} {SESSION.image_display_name}')
    VIEWER = viewer
    # Get rid of the crap on the left sidebar for a cleaner screen
    viewer.window._qt_viewer.dockLayerList.toggleViewAction().trigger()
    viewer.window._qt_viewer.dockLayerControls.toggleViewAction().trigger()


    notes_label = QLabel('Placeholder note'); notes_label.setAlignment(Qt.AlignCenter)
    notes_label.setFont(userInfo.fonts.small)

    #TODO arrange these more neatly
    #TODO these dock widgets cause VERY strange behavior when trying to clear all layers / load more

    notes_entry_layout = QHBoxLayout()
    note_text_entry = QLineEdit()
    note_cell_entry = QLineEdit()
    notes_entry_layout.addWidget(note_text_entry) 
    notes_entry_layout.addWidget(note_cell_entry)
    if ANNOTATIONS_PRESENT:
        notes_annotation_combo = QComboBox()
        notes_annotation_combo.addItems(ANNOTATIONS_PRESENT)
        notes_entry_layout.addWidget(notes_annotation_combo)
        SESSION.widget_dictionary['notes annotation combo']=notes_annotation_combo
    note_button = QPushButton("Add note for cell")
    note_text_entry.setPlaceholderText('Enter new note')
    # note_text_entry.setFixedWidth(200)
    note_cell_entry.setPlaceholderText("Cell Id")
    # note_cell_entry.setFixedWidth(200)
    # Pass pointer to widgets to function on button press
    note_button.pressed.connect(lambda: replace_note(note_cell_entry, note_text_entry))

    notes_all_group = QGroupBox('Annotation')
    notes_all_group.setStyleSheet(open("data/docked_group_box_border_light.css").read())
    notes_all_layout = QVBoxLayout(notes_all_group)
    notes_all_layout.addWidget(notes_label)
    notes_all_layout.addLayout(notes_entry_layout)
    notes_all_layout.addWidget(note_button)
    SESSION.widget_dictionary['notes label']=notes_label; SESSION.widget_dictionary['notes text entry']=note_text_entry
    SESSION.widget_dictionary['notes cell entry']= note_cell_entry


    # Change page widgets
    page_combobox = QComboBox()
    page_cell_entry = QLineEdit(); 
    page_cell_entry.setPlaceholderText("Cell Id (optional)")#; page_cell_entry.setFixedWidth(200)
    intensity_sort_box = QComboBox()
    intensity_sort_box.addItem("Sort page by Cell Id")
    for i, chn in enumerate(userInfo.channels):
        intensity_sort_box.addItem(f"Sort page by {chn} Cell Intensity")
    local_sort = None
    if GLOBAL_SORT is None:
        intensity_sort_box.setCurrentIndex(0) # Set "sort by CID" to be the default
    else:
        local_sort = GLOBAL_SORT
        intensity_sort_box.setCurrentText(f"Sort page by {local_sort}")
    
    # Change page widgets entry
    next_page_button = QPushButton("Change Page")
    page_group = QGroupBox("Page selection")
    page_group.setStyleSheet(open("data/docked_group_box_border_light.css").read())
    page_group_layout = QVBoxLayout(page_group)

    page_entry_layout = QHBoxLayout()
    page_entry_layout.addWidget(page_combobox)
    page_entry_layout.addWidget(page_cell_entry)
    # Don't include annotation combobox unless it is necessary
    if ANNOTATIONS_PRESENT:
        page_cell_combo = QComboBox(); page_cell_combo.addItems(ANNOTATIONS_PRESENT)#; page_cell_combo.setFixedWidth(200)
        SESSION.widget_dictionary["page cell layer"] = page_cell_combo
        page_entry_layout.addWidget(page_cell_combo)

    next_page_button.pressed.connect(lambda: show_next_cell_group())
    
    page_group_layout.addLayout(page_entry_layout)
    page_group_layout.addWidget(intensity_sort_box)
    page_group_layout.addWidget(next_page_button)
    SESSION.widget_dictionary['page combobox']= page_combobox
    SESSION.widget_dictionary['page cell id'] = page_cell_entry
    SESSION.widget_dictionary['page intensity sort'] = intensity_sort_box

    # Mode toggle tools
    mode_group = QGroupBox("Mode")
    mode_group.setStyleSheet(open("data/docked_group_box_border_light.css").read())
    mode_layout = QVBoxLayout(mode_group)

    mode_entry_layout = QHBoxLayout()
    mode_switch_combo = QComboBox()
    mode_switch_combo.addItems(["Gallery","Multichannel","Context"])
    mode_switch_cell = QLineEdit() ; mode_switch_cell.setPlaceholderText("Cell ID (optional)")
    mode_entry_layout.addWidget(mode_switch_combo)
    mode_entry_layout.addWidget(mode_switch_cell)
    if ANNOTATIONS_PRESENT:
        mode_switch_annotations = QComboBox() ; mode_switch_annotations.addItems(ANNOTATIONS_PRESENT)
        SESSION.widget_dictionary["switch mode annotation"] = mode_switch_annotations
        mode_entry_layout.addWidget(mode_switch_annotations)
    else:
        pass
    SESSION.widget_dictionary['switch mode combo']=mode_switch_combo
    SESSION.widget_dictionary['switch mode cell']=mode_switch_cell
    mode_layout.addLayout(mode_entry_layout)
    switch_mode_button = QPushButton("Change Mode")
    switch_mode_button.pressed.connect(lambda: toggle_session_mode_catch_exceptions(mode_switch_combo.currentText(), from_mouse=False))
    mode_layout.addWidget(switch_mode_button)
    

    # Show / hide radio buttons
    show_hide_group = QGroupBox("Show/hide overlays")
    show_hide_group.setStyleSheet(open("data/docked_group_box_border_light.css").read())
    show_hide_layout = QVBoxLayout()
    show_hide_group.setLayout(show_hide_layout)
    status_layer_show = QRadioButton("Show labels"); status_layer_show.setChecked(True)
    status_layer_hide = QRadioButton("Hide labels"); status_layer_hide.setChecked(False) 
    
    status_layer_layout = QHBoxLayout(); status_layer_layout.addWidget(status_layer_show) ; status_layer_layout.addWidget(status_layer_hide)
    status_layer_group = QButtonGroup() ; status_layer_group.addButton(status_layer_show); status_layer_group.addButton(status_layer_hide)
    status_layer_show.setFont(userInfo.fonts.small); status_layer_hide.setFont(userInfo.fonts.small)
    
    status_layer_show.toggled.connect(lambda: toggle_statuslayer_visibility(status_layer_show))
    SESSION.widget_dictionary['show status layer radio']=status_layer_show
    SESSION.widget_dictionary['hide status layer radio']=status_layer_hide
    show_hide_layout.addLayout(status_layer_layout)

    nuc_boxes_show = QRadioButton("Show nuclei boxes"); nuc_boxes_show.setChecked(False)
    nuc_boxes_hide = QRadioButton("Hide nuclei boxes"); nuc_boxes_hide.setChecked(True)
    nuc_boxes_context = QRadioButton("Show box under mouse"); nuc_boxes_context.setChecked(False); nuc_boxes_context.setVisible(False)

    
    
    nuc_boxes_layout = QHBoxLayout(); nuc_boxes_layout.addWidget(nuc_boxes_show) ; nuc_boxes_layout.addWidget(nuc_boxes_hide); nuc_boxes_layout.addWidget(nuc_boxes_context)
    nuc_boxes_group = QButtonGroup(); nuc_boxes_group.addButton(nuc_boxes_show) ; nuc_boxes_group.addButton(nuc_boxes_hide) ; nuc_boxes_group.addButton(nuc_boxes_context)
    nuc_boxes_show.setFont(userInfo.fonts.small); nuc_boxes_hide.setFont(userInfo.fonts.small); nuc_boxes_context.setFont(userInfo.fonts.small)
   
    # nuc_boxes_show.tog
    nuc_boxes_group.buttonToggled[QAbstractButton, bool].connect(toggle_nuclei_boxes)
    SESSION.widget_dictionary['show boxes']=nuc_boxes_show
    SESSION.widget_dictionary['hide boxes']=nuc_boxes_hide
    SESSION.widget_dictionary['mouse boxes']=nuc_boxes_context
    show_hide_layout.addLayout(nuc_boxes_layout)

    absorption_widget = QPushButton("Absorption")
    absorption_widget.pressed.connect(toggle_absorption)

    # Create main group in a vertical stack, and add to side box
    # mode_group.setSizePolicy(QSizePolicy.MinimumExpanding,QSizePolicy.MinimumExpanding)
    side_dock_group = QGroupBox()
    side_dock_group.setStyleSheet(open("data/docked_group_box_noborder.css").read())
    side_dock_layout = QVBoxLayout(side_dock_group)
    side_dock_layout.addWidget(notes_all_group)
    side_dock_layout.addWidget(page_group)
    side_dock_layout.addWidget(mode_group)
    side_dock_layout.addWidget(show_hide_group)
    side_dock_layout.addWidget(absorption_widget)
    side_dock_group.setSizePolicy(QSizePolicy.MinimumExpanding,QSizePolicy.MinimumExpanding)
    viewer.window.add_dock_widget(side_dock_group,name ="User tools",area="right")

    # Create bottom bar widgets
    # bottom_dock_group = QGroupBox()
    # bottom_dock_group.setStyleSheet(open("data/docked_group_box_noborder.css").read())
    # bottom_dock_layout = QHBoxLayout(bottom_dock_group)
    viewer.window.add_dock_widget(adjust_gamma_widget, area = 'bottom')
    viewer.window.add_dock_widget(adjust_whitein, area = 'bottom')
    viewer.window.add_dock_widget(adjust_blackin, area = 'bottom')

    # print(f'\n {dir()}') # prints out the namespace variables 
    SESSION.side_dock_groupboxes = {"notes":notes_all_group, "page":page_group, "mode":mode_group, "hide": show_hide_group}
    SESSION.radiogroups = [status_layer_group, nuc_boxes_group]

    # Now process object data and fetch images
    RAW_PYRAMID=pyramid
    try:
        tumor_cell_XYs = extract_phenotype_xldata(specific_cell=SPECIFIC_CELL, sort_by_intensity=local_sort)
    except KeyError as e:
        print(e)
        # If the user has given bad input, the function will raise a KeyError. Fail gracefully and inform the user
        preprocess_class._append_status('<font color="#f5551a">  Failed.</font>')
        if PHENOTYPES:
            preprocess_class._append_status(f'<br><font color="#f5551a">The phenotype(s) {", ".join(str(x) for x in PHENOTYPES)} might not exist in the data, or other column names may have changed!</font>')
        if ANNOTATIONS:
            preprocess_class._append_status(f'<br><font color="#f5551a">The annotations(s) {", ".join(str(x) for x in ANNOTATIONS)} might not exist in the data, or other column names may have changed!</font>')
        viewer.close()
        return None # allows the input GUI to continue running
    
    except StopIteration as e:
        print("StopIteration raised in extract_phenotype_xldata")
        # Triggered by the next(cell_set.values()) call. If there are no cells to show, this happens
        preprocess_class._append_status('<font color="#f5551a">  Failed.</font>')
        preprocess_class._append_status(f'<br><font color="#f5551a">There are no cells to show. This could be a result of a phenotype with no positive calls, or a strict filter</font>')
        viewer.close()
        return None # allows the input GUI to continue running
    
    preprocess_class._append_status('<font color="#7dbc39">  Done.</font>')
    preprocess_class._append_status_br('Initializing Napari session...')

    set_initial_adjustment_parameters(preprocess_class.userInfo.view_settings) # set defaults: 1.0 gamma, 0 black in, 255 white in
    attach_functions_to_viewer(viewer)


    # try:
    add_layers(viewer,pyramid,tumor_cell_XYs, int(userInfo.imageSize/2))
    # except IndexError as e:
    #     preprocess_class._append_status('<font color="#f5551a">  Failed.<br>A requested image channel does not exist in the data!</font>')
    #     # preprocess_class.findDataButton.setEnabled(True)
    #     viewer.close()
    #     return False
    #TODO
    #Enable scale bar
    if SESSION.image_scale:
        viewer.scale_bar.visible = True
        viewer.scale_bar.unit = "um"

    # Filter checkboxes down to relevant ones only and update color
    # print("My active channels are\n")
    # print(userInfo.active_channels)
    # all_boxes = check_creator2(userInfo.active_channels)

    for box in check_creator2(userInfo.active_channels):
        box.setStyleSheet(f"QCheckBox {{ color: {userInfo.channelColors[box.objectName()].replace('blue','#0462d4')} }}")
        UPDATED_CHECKBOXES.append(box)
    viewer.window.add_dock_widget(UPDATED_CHECKBOXES,area='bottom')

    #TODO set theme
    VIEWER.theme = "dark"


    with tifffile.imread(userInfo.qptiff_path, aszarr=True) as zs:
        SESSION.zarr_store = zs
        sc = (SESSION.image_scale, SESSION.image_scale) if SESSION.image_scale is not None else None
        for fluor in userInfo.channels:
            if fluor == 'Composite':
                continue
            pos = userInfo.channelOrder[fluor]
            print(f"\nAdding full size {fluor} image")
            pyramid = [da.from_zarr(zs, n)[pos] for n in range(6) ] #TODO how to know how many pyramid layers?
            viewer.add_image(pyramid, name = f'Context {fluor}', 
                        blending = 'additive', colormap = custom_color_functions.retrieve_cm(userInfo.channelColors[fluor]),
                        interpolation = "linear", scale=sc, multiscale=True, visible = False)
        
    # Finish up, and set keybindings
    preprocess_class._append_status('<font color="#7dbc39">  Done.</font><br> Goodbye')
    chn_key_wrapper(viewer)
    set_viewer_to_neutral_zoom(viewer, reset_session=True) # Fix zoomed out issue
    if preprocess_class is not None: preprocess_class.close() # close other window
    # Set adjustment settings to their default now that all images are loaded
    reuse_contrast_limits()
    reuse_gamma()
    viewer.layers.selection.active = viewer.layers[f"Gallery {userInfo.channels[0]}"]  
    napari.run() # Start the event loop
    # zs.close()
    print('\n#Zarr object should be closed')

# Main Probably doesn't work as is right now. Will need to instantiate a new user class to run everything
if __name__ == '__main__':
    main()
