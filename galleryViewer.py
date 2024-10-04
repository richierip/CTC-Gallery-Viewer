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
from qtpy.QtWidgets import (QLabel, QLineEdit, QPushButton, QRadioButton, QCheckBox, QButtonGroup, QSizePolicy, QFileDialog, QSpinBox,
                        QComboBox, QHBoxLayout,QVBoxLayout, QGroupBox, QLayout, QAbstractButton, QScrollArea, QDockWidget, QToolTip)
from qtpy.QtCore import Qt,QPoint, QRect
from qtpy.QtGui import QFont #, QImage, QGuiApplication, QPixmap
import numpy as np
import pandas as pd
# import openpyxl # necessary, do not remove
from matplotlib import cm, ticker # necessary, do not remove
from matplotlib import colors as mplcolors # Necessary, do not remove
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.lines as lines

import copy
import time
import custom_color_functions # Necessary, do not remove
from math import ceil
from re import sub
import os
import dask.array as da
# import zarr
import scipy.spatial as spatial
from seaborn import histplot, violinplot, FacetGrid
from itertools import chain

# For clipboard
from io import BytesIO
import win32clipboard
from PIL import Image
import pathlib
from datetime import datetime

# These files were created as part of the GalleryViewer Project
import store_and_load
from custom_qt_classes import StatusCombo, ViewSettingsDialog, make_fluor_toggleButton_stylesheet
# from initial_UI import VERSION_NUMBER


######-------------------- Globals, will be loaded through pre-processing QT gui #TODO -------------######
VERSION_NUMBER = '1.3.5'
QPTIFF_LAYER_TO_RIP = 0 # 0 is high quality. Can use 1 for testing (BF only, loads faster)
cell_colors = store_and_load.CELL_COLORS
print('\n--------------- adding custom cmaps\n')

for colormap in custom_color_functions.rgb_color_dict.keys():
    # print(f'registering cmap: {colormap}')
    if colormap in cm.__dict__.keys(): continue
    current_map = custom_color_functions.create_dynamic_lut(colormap)
    custom = mplcolors.LinearSegmentedColormap.from_list(colormap, current_map)
    cm.register_cmap(name = colormap, cmap = custom)
    # Add inverse 
    imap = custom_color_functions.create_dynamic_lut(colormap, inverse = True)
    icustom = mplcolors.LinearSegmentedColormap.from_list(colormap+ " inverse", imap)
    cm.register_cmap(name = colormap+ " inverse", cmap = icustom)
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
    try:
        layer.gamma = 2-(2*gamma) + 0.001 # avoid gamma = 0 which causes an exception
    except ValueError as e:
        userInfo.log_exception(e, error_type="adjust-gamma-slider-exception")

def adjust_composite_limits(layer, limits):
    try:
        layer.contrast_limits = limits
    except ValueError as e:
        userInfo.log_exception(e, error_type="adjust-composite-limits-slider-exception")

def hide_invisible_multichannel_fluors():
    
    all_fluors = [x for x in userInfo.channels if x != "Composite"]
    active_fluors_only = all_fluors if "Composite" in userInfo.active_channels else [x for x in userInfo.active_channels]

    if "Composite" in userInfo.active_channels or len(active_fluors_only) == len(userInfo.channels): # Reference list has 'Composite' in it
        # Want to show everything in this case. Use the full image.
        for fluor in userInfo.channels:
            if fluor == "Composite": continue
            VIEWER.layers[f"Multichannel {fluor}"].data = copy.copy(SESSION.multichannel_page_images[fluor])
            VIEWER.layers[f"Multichannel Nuclei Boxes"].data = copy.copy(SESSION.multichannel_nuclei_box_coords)
        return True

    # Something is missing. need to remake images
    num_active_channels = len(active_fluors_only)
    SESSION.cells_per_row['Multichannel'] = num_active_channels + 1
    num_channels = len(all_fluors)
    imsize = userInfo.imageSize+2
    page_shape = (PAGE_SIZE*(userInfo.imageSize+2),(userInfo.imageSize+2) * (num_active_channels+1)) 
    if num_active_channels ==1 : 
        page_shape = (PAGE_SIZE*(userInfo.imageSize+2),(userInfo.imageSize+2) * (num_active_channels)) 

    fullpage_col = 1
    collapsed_col = 1
    for fluor in userInfo.channels:
        if fluor not in all_fluors: continue
        # print(f"looping on {fluor},{pos}  ||| {fullpage_col} {collapsed_col}")
        if fluor in active_fluors_only:
            collapsed_image = np.zeros(page_shape)
            fluor_im = copy.copy(SESSION.multichannel_page_images[fluor][:,((fullpage_col-1)*imsize)+1 : (fullpage_col*imsize)-1])
            # Set individual column
            collapsed_image[:,((collapsed_col-1)*imsize)+1 : (collapsed_col*imsize)-1] = fluor_im
            if num_active_channels >1:
                # Set composite column
                collapsed_image[:,(num_active_channels*imsize)+1 : ((num_active_channels+1)*imsize)-1] = fluor_im
            collapsed_col +=1
            VIEWER.layers[f"Multichannel {fluor}"].data = collapsed_image
        fullpage_col +=1

        # x1 = int(cell["XMin"] + offset - cell_x) ; x2 = int(cell["XMax"] + offset - cell_x)
        # y1 = int(cell["YMin"] + offset - cell_y) ; y2 = int(cell["YMax"] + offset - cell_y)
        # cXg = (row_g-1)*(userInfo.imageSize+2) ; cYg = (col_g-1)*(userInfo.imageSize+2)
        # cXm = (row_m-1)*(userInfo.imageSize+2) ; cYm = len(userInfo.channels)*(userInfo.imageSize+2)

        # nuclei_box_coords_g.append([[cXg+y1, cYg+x1], [cXg+y2, cYg+x2]]) # x and y are actually flipped between napari and the object data
        # nuclei_box_coords_m.append([[cXm+y1, cYm+x1], [cXm+y2, cYm+x2]]) 
    
    # Horizontally adjust nuclei boxes 
    adjust_amount = num_channels - num_active_channels
    if num_active_channels == 1:
        adjust_amount +=1
    hdist = adjust_amount * imsize
    mbc = copy.copy(SESSION.multichannel_nuclei_box_coords)
    mbc = [ [[x[0][0], x[0][1]-hdist], [x[1][0], x[1][1]-hdist]]  for x in mbc]
    VIEWER.layers[f"Multichannel Nuclei Boxes"].data = mbc

def restore_viewsettings_from_cache(arrange_multichannel = False, viewer = VIEWER, session=SESSION, single_setting_change = False):
    vs = SESSION.view_settings
    '''Change settings for all modes, whether or not they are displayed right now.'''
    def _modify_images_in_modes(f, setting = "both"):
        for mode in ("Gallery ", "Multichannel ", "Context "):
            match setting:
                case "both":
                    adjust_composite_gamma(viewer.layers[mode+f],vs[f+" gamma"])
                    adjust_composite_limits(viewer.layers[mode+f], (vs[f+" black-in"],vs[f+" white-in"]))
                case "gamma":
                    adjust_composite_gamma(viewer.layers[mode+f],vs[f+" gamma"])
                case "white-in" | "black-in":
                    adjust_composite_limits(viewer.layers[mode+f], (vs[f+" black-in"],vs[f+" white-in"]))
                case _:
                    raise ValueError("Bad input to restore_viewsettings_from_cache - _modify_images_in_modes")
               
    if single_setting_change:
        print(f'\nSingle setting change - will exit function')
        spl = single_setting_change.split()
        caller_fluor, s = " ".join(spl[:-1]), spl[-1]
        _modify_images_in_modes(caller_fluor,s)
        return True
    # Cut out the multichannel fluors that are not visible
    if arrange_multichannel:
        hide_invisible_multichannel_fluors()

    # Make everything silent
    for layer in viewer.layers:
        layer.visible = False
    # Toggle back on overlays if applicable
    if session.mode != "Context":
        # viewer.layers[f"{session.mode} Status Edges"].visible = session.status_layer_vis
        viewer.layers[f"{session.mode} Status Squares"].visible = session.status_layer_vis
        viewer.layers[f"{session.mode} Status Numbers"].visible = session.status_layer_vis
        # viewer.layers[f"{session.mode} Absorption"].visible = session.absorption_mode
    try:
        if session.mode == "Context":
            show_boxes = True if session.nuclei_boxes_vis["Context"] =="Show" else False
        else:
            show_boxes = session.nuclei_boxes_vis["Gallery/Multichannel"]
        viewer.layers[f"{session.mode} Nuclei Boxes"].visible = show_boxes
    except KeyError:
        pass


    print(f"Mode is {session.mode} and active fluors are {userInfo.active_channels}")
    # Loop through channels and adjust
    for fluor in userInfo.channels:
        if fluor == 'Composite':
            continue
        # Turn on appropriate layers. Turn on all if "Composite" button is checked
        if "Composite" in userInfo.active_channels or fluor in userInfo.active_channels: 
            viewer.layers[f"{session.mode} {fluor}"].visible = True
        # call worker func
        _modify_images_in_modes(fluor)

def set_layer_colors():
    for mode in ("Gallery ", "Multichannel ", "Context "):
        for fluor, color in userInfo.channelColors.items():
            if fluor not in userInfo.active_channels: continue
            cm_name = color if not SESSION.absorption_mode else color+' inverse'
            VIEWER.layers[mode+fluor].colormap = custom_color_functions.retrieve_cm(cm_name)
## --- Bottom bar functions and GUI elements 

''' DEPRECATED -- replaced by a button that summons a ViewSettingsDialog'''
# @magicgui(auto_call=True,
#         Gamma={"widget_type": "FloatSlider", "max":1.0, "min":0.01},
#         layout = 'horizontal')
# def adjust_gamma_widget(Gamma: float = 0.5) -> ImageData: 
#     def _update_dictionary(name, val):
#         SESSION.view_settings[name+' gamma'] = val
#     for fluor in userInfo.active_channels:
#         if fluor == 'Composite':
#             continue
#         _update_dictionary(fluor,Gamma)
#         for m in ["Gallery", "Multichannel", "Context"]:
#             # VIEWER.layers[f"{m} "+fluor].visible = True
#             adjust_composite_gamma(VIEWER.layers[f"{m} "+fluor],Gamma)
#             # if ("Composite" not in userInfo.active_channels or fluor not in userInfo.active_channels) or SESSION.mode !=m: 
#             #     VIEWER.layers[f"{m} "+fluor].visible = False
#     VIEWER.window._qt_viewer.setFocus()
#     SESSION.widget_dictionary["reset_vs_button"].setDisabled(False)

''' DEPRECATED -- replaced by a button that summons a ViewSettingsDialog'''
# # @magicgui(auto_call=True,
# #         white_in={"widget_type": "FloatSlider", "max":255,"min":1.0, "label": "White-in"},
# #         layout = 'horizontal')
# def adjust_whitein(white_in: float = 255) -> ImageData:
#     def _update_dictionary(name, val):
#         SESSION.view_settings[name+' white-in'] = val
#     for fluor in userInfo.active_channels:
#         if fluor == 'Composite':
#             continue
#         _update_dictionary(fluor,white_in)
#         for m in ["Gallery", "Multichannel", "Context"]:
#             adjust_composite_limits(VIEWER.layers[f"{m} {fluor}"], [SESSION.view_settings[fluor+" black-in"],white_in])
#     VIEWER.window._qt_viewer.setFocus()
#     SESSION.widget_dictionary["reset_vs_button"].setDisabled(False)

''' DEPRECATED -- replaced by a button that summons a ViewSettingsDialog'''
# @magicgui(auto_call=True,
#         black_in={"widget_type": "FloatSlider", "max":255, "label":"Black-in"},
#         layout = 'horizontal')
# def adjust_blackin(black_in: float = 0) -> ImageData:
#     def _update_dictionary(name, val):
#         SESSION.view_settings[name+' black-in'] = val
    
#     for fluor in userInfo.active_channels:
#         if fluor == 'Composite':
#             continue
#         _update_dictionary(fluor,black_in)
#         for m in ["Gallery", "Multichannel", "Context"]:
#             adjust_composite_limits(VIEWER.layers[f"{m} {fluor}"], [black_in,SESSION.view_settings[fluor+" white-in"]])
#     VIEWER.window._qt_viewer.setFocus()
#     SESSION.widget_dictionary["reset_vs_button"].setDisabled(False)

def open_vs_popup():
    if SESSION.VSDialog is None:
        vs = ViewSettingsDialog(userInfo, VIEWER, SESSION.view_settings, restore_viewsettings_from_cache, set_layer_colors) # TODO make a function here that works
        SESSION.VSDialog = vs
        vs.exec()
        SESSION.VSDialog = None
    else:
        SESSION.VSDialog.setWindowState(SESSION.VSDialog.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        # this will activate the window
        SESSION.VSDialog.activateWindow()

def toggle_absorption():
    #TODO make absorption work for context more?
    # if SESSION.mode == "Context": return None
    if SESSION.absorption_mode ==True:
        SESSION.absorption_mode = False
        for layer in VIEWER.layers:
            
            if 'Status' in layer.name or layer.name == "Context Nuclei Boxes":
                # Don't want to change the color of the context mode boxes
                #   those colors are used to indicate status
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
        SESSION.widget_dictionary['imsave_cell_borders'].setCurrentText("White borders")
        SESSION.widget_dictionary['imsave_page_borders'].setCurrentText("White borders")
    else:
        SESSION.absorption_mode = True
        for layer in VIEWER.layers:
            
            if 'Status' in layer.name or layer.name == "Context Nuclei Boxes":
                # Don't want to change the color of the context mode boxes
                #   those colors are used to indicate status
                continue 
            elif "Nuclei Boxes" in layer.name or layer.name == "Context Closest Cell Box":
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
        SESSION.widget_dictionary['imsave_cell_borders'].setCurrentText("Black borders")
        SESSION.widget_dictionary['imsave_page_borders'].setCurrentText("Black borders")
    if not SESSION.mode == "Context":
        #TODO
        pass
        # change_statuslayer_color(copy.copy(SESSION.current_cells))
    
    # Change colors and widget styles
    for toggle in UPDATED_CHECKBOXES:
        name = str(toggle.objectName())
        toggle.setStyleSheet(make_fluor_toggleButton_stylesheet(userInfo.channelColors[name] if name != "Composite" else "None", toggle.isChecked(), SESSION.absorption_mode))
        
    newmode = "light" if SESSION.absorption_mode else "dark"
    oldmode = "dark" if SESSION.absorption_mode else "light"
    aw = SESSION.widget_dictionary["absorption_widget"]
    aw.setText("Apsorption on") if SESSION.absorption_mode else aw.setText("Apsorption off")
    for name, bg in SESSION.side_dock_groupboxes.items():
        bg.setStyleSheet(open(f"data/docked_group_box_border_{oldmode}.css").read())
    VIEWER.theme = newmode

def fluor_button_toggled():
    # keep track of visible channels in global list and then toggle layer visibility
    userInfo.active_channels = []
    for toggle in UPDATED_CHECKBOXES:
        name = str(toggle.objectName())
        print(f"{name}  is checked? {toggle.isChecked()}")
    # print(f"{checkbox_name} has been clicked and will try to remove from {userInfo.active_channels}")
        if not toggle.isChecked():
            userInfo.active_channels.append(name)
        
        toggle.setStyleSheet(make_fluor_toggleButton_stylesheet(userInfo.channelColors[name] if name != "Composite" else "None", toggle.isChecked(), SESSION.absorption_mode))
        
        
    print(userInfo.active_channels)
    # Make visible all channels according to rules
    restore_viewsettings_from_cache(arrange_multichannel=True if SESSION.mode == "Multichannel" else False, viewer = VIEWER, session=SESSION,)
    # for fluor in userInfo.channels:
    #     # Different set of layers if we are in context mode
    #     lname = f'{SESSION.mode} {fluor}'
    #     if fluor == "Composite":
    #         continue
    #     if "Composite" in userInfo.active_channels or fluor in userInfo.active_channels:
    #         VIEWER.layers[lname].visible = True
    #     else:
    #         VIEWER.layers[lname].visible = False  
    VIEWER.window._qt_viewer.setFocus()
    # return myfunc

def check_creator2(list_of_names):
    all_boxes = []
    for name in list_of_names:
        tb = QPushButton(name); tb.setObjectName(name)
        tb.setCheckable(True)
        tb.setStyleSheet(make_fluor_toggleButton_stylesheet(userInfo.channelColors[name] if name != "Composite" else "None") )
        all_boxes.append(tb)
        # f = dynamic_checkbox_creator()
        tb.clicked.connect(fluor_button_toggled)
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
            VIEWER.status = f'{Mode} Mode enabled. But, there was a problem saving your scoring     decisions. Close your data file?'
            return False

    if SESSION.mode != "Context" and from_mouse:
        _, coords, _ = SESSION.find_mouse_func(VIEWER.cursor.position)
        if coords is None: # User has clicked outside the grid area with the chage mode hotkey pressed. Alert and do nothing.
            if target_mode == "Context" and SESSION.mode == "Multichannel" and from_mouse:
                pass #TODO
            VIEWER.status = f"Invalid cell selection: cannot change mode to {target_mode}"
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
                # print(target_cell_info)
            except KeyError:
                VIEWER.status = f"Can't find cell [{cid}] in the current page. Staying in {SESSION.mode} mode"
                return False
        else:
            target_cell_info = SESSION.cell_under_mouse
            # print(target_cell_info)

        SESSION.context_target = target_cell_info
        cell_num = str(target_cell_info["cid"])
        sc = 1 if SESSION.image_scale is None else SESSION.image_scale # Scale factor necessary.

        # Find offset coordinates
        if SESSION.mode=="Gallery": 
            cname = f"{target_cell_info['Layer']} {cell_num}" if ANNOTATIONS_PRESENT else str(cell_num)
            row, col = list(SESSION.grid_to_ID["Gallery"].keys())[list(SESSION.grid_to_ID["Gallery"].values()).index(cname)].split(",")
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
        SESSION.widget_dictionary['mouse boxes'].setVisible(True) # Enable these widget
        SESSION.widget_dictionary["marker combo"].setVisible(True)
        SESSION.widget_dictionary["marker button"].setVisible(True)
        SESSION.widget_dictionary['show status layer radio'].setVisible(False) # Disable these widget
        SESSION.widget_dictionary['hide status layer radio'].setVisible(False) 
        

        if from_mouse:
            _, (mX,mY), _ = SESSION.find_mouse_func(VIEWER.cursor.position, scope="local")
            # Change cursor value
            sc = 1 if SESSION.image_scale is None else SESSION.image_scale # Scale factor necessary.
            class dummyCursor:
                def __init__(self, y, x) -> None:
                    self.position = (y,x)
            p = dummyCursor((target_cell_info["center_y"]+mY-(userInfo.imageSize+2)/2)*sc,(target_cell_info["center_x"]+mX-(userInfo.imageSize+2)/2)*sc)
            # Used to have the following line to try to show pixel val right away
            #SESSION.display_intensity_func(VIEWER, p)
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

        print(f"target mode is {target_mode} but actual mode is {SESSION.mode}")
        # Turn on / off the correct layers
        restore_viewsettings_from_cache(arrange_multichannel=True if target_mode=="Multichannel" else False, viewer = VIEWER, session=SESSION,)

        if from_mouse: # Go get pixel values now that proper image layers are visible.
            # Not working right now but it's a minor issue #TODO
            SESSION.display_intensity_func(VIEWER,p)

        VIEWER.window._qt_viewer.setFocus() # return focus
        # Done. Leave function, no need to save cells
        return True 
    
    elif target_mode == "Multichannel" or target_mode =="Gallery":
        
        SESSION.widget_dictionary['mouse boxes'].setVisible(False) # Disable these widget
        SESSION.widget_dictionary["marker combo"].setVisible(False)
        SESSION.widget_dictionary["marker button"].setVisible(False)
        SESSION.widget_dictionary['show status layer radio'].setVisible(True) # Enable these widget
        SESSION.widget_dictionary['hide status layer radio'].setVisible(True) 

        if SESSION.mode != "Context": # Now, we must be changing to Gallery OR Multichannel. Want to save to DataFrame, not disk
            _save_validation(VIEWER, target_mode)

        if target_mode == "Multichannel":
            if not from_mouse:
                try:
                    cid = SESSION.widget_dictionary['switch mode cell'].text()
                    if cid == '':
                        target_cell_info = SESSION.page_cells[SESSION.grid_to_ID["Multichannel"]["1,1"]] # get first
                        target_cell_name = f"{target_cell_info['Layer']} {target_cell_info['cid']}" if ANNOTATIONS_PRESENT else str(target_cell_info['cid'])
                    elif ANNOTATIONS_PRESENT:
                        layer = SESSION.widget_dictionary['switch mode annotation'].currentText()
                        target_cell_name = f"{layer} {cid}"
                        target_cell_info = SESSION.current_cells[target_cell_name]
                    else:
                        target_cell_name = str(cid)
                        target_cell_info = SESSION.current_cells[target_cell_name]
                    SESSION.cell_under_mouse = target_cell_info
                except KeyError:
                    VIEWER.status = f"Can't find cell [{cid}] in the current page. Staying in {SESSION.mode} mode"
                    return False
            else:
                match bool(ANNOTATIONS_PRESENT): # variable will be False, or a List of String names of annotations present in data
                
                    case True:
                        target_cell_name = f"{SESSION.cell_under_mouse['Layer']} {str(SESSION.cell_under_mouse['cid'])}"
                    case False: # Will match 
                        target_cell_name = str(SESSION.cell_under_mouse['cid'])
                    case _:
                        # Placeholder. Should never get here at the moment.
                        raise Exception("Something very wrong has happened")

            sc = 1 if SESSION.image_scale is None else SESSION.image_scale # Scale factor necessary
            row, col = list(SESSION.grid_to_ID["Multichannel"].keys())[list(SESSION.grid_to_ID["Multichannel"].values()).index(target_cell_name)].split(",")
            row= int(row) #find the row for multichannel cell. Col should be irrelevant
            cellCanvasY = ((row-1)*(userInfo.imageSize+2)) + ((userInfo.imageSize+2)/2)
            cellCanvasX = (len(userInfo.channels)+1)*(userInfo.imageSize+2) /2 # Add 1 to channels to account for merged image
            SESSION.last_multichannel_camera_coordinates["center"] = (cellCanvasY*sc, cellCanvasX*sc)
            
            VIEWER.camera.center = SESSION.last_multichannel_camera_coordinates["center"]
            VIEWER.camera.zoom = SESSION.last_multichannel_camera_coordinates["z"]


        elif target_mode == "Gallery":
            VIEWER.camera.center = SESSION.last_gallery_camera_coordinates["center"]
            VIEWER.camera.zoom = SESSION.last_gallery_camera_coordinates["z"]

        else:
            raise Exception(f"Invalid parameter passed to toggle_session_mode: {target_mode}. Must be 'Gallery' or 'Multichannel'.")
        

        SESSION.mode = target_mode
        # Change visibilities of the correct layers
        restore_viewsettings_from_cache(arrange_multichannel=True if target_mode =="Multichannel" else False, viewer = VIEWER, session=SESSION,)
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
        SESSION.page = page
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

    # Update scoring tally for this page
    set_initial_scoring_tally(userInfo.objectDataFrame, SESSION.session_cells)
    # Perform adjustments before exiting function
    #TODO
    # Only checked fluors will be visible
    restore_viewsettings_from_cache(arrange_multichannel= True if SESSION.mode == "Multichannel" else False, viewer = VIEWER, session=SESSION,) 
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
    if not checked:
        # This function gets called twice, since when one radio button in the group is toggle on, the other is toggled off. 
        #   We only want to run this function once so the other call can be discarded
        return False
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
        SESSION.nuclei_boxes_vis["Context"] = selected_mode
        SESSION.nuclei_boxes_vis["Gallery/Multichannel"] = True if selected_mode == "Show" else False

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
        
        # Find cells in session table near target
        z,y,x = VIEWER.camera.center
        # nearby_inds = SESSION.kdtree.query_ball_point([x/sc,y/sc], 550) # [x,y], dist -> indices in table
        if distanceSearchCenter:
            dists, nearby_inds = SESSION.kdtree.query(distanceSearchCenter, k=200) # [x,y], dist -> indices in table
        else:
            dists, nearby_inds = SESSION.kdtree.query([x/sc,y/sc], k=200) # [x,y], dist -> indices in table

        # if there are fewer than k cells, there will be occurences of length of data +1 in the data. Remove these
        #   so we can get real indices from the table
         
        nearby_cells = SESSION.session_cells.iloc[nearby_inds[nearby_inds!=SESSION.session_cells.shape[0]] ] 

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
            page = cell['Page']
            x1 = int(cell["XMin"]); x2 = int(cell["XMax"])
            y1 = int(cell["YMin"]); y2 = int(cell["YMax"])
            nuclei_box_coords.append([[y1,x1] , [y2,x2]])
            cids.append(str(cell["Object Id"]))
            vals = cell[SESSION.validation_columns]
            try:

                validation_call = SESSION.current_cells[ckey]['validation_call']
            except KeyError:
                try:
                    validation_call = str(vals[vals == 1].index.values[0]).replace(f"Validation | ", "")
                except IndexError:
                    # row has no validation call (all zeroes). Assign to Unseen
                    validation_call = "Unseen"
                SESSION.current_cells[ckey] = {'Layer':layer,"cid": cid,"center_x": (x1+x2)//2,'center_y': (y1+y2)//2,
                                'validation_call': validation_call, 'XMax' : x2,'XMin':x1,
                                'YMax' : y2,'YMin':y1, "Page":page}
                SESSION.saved_notes[ckey] = "-"
                record_notes_and_intensities(cell, SESSION.intensity_columns)
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

def toggle_marker_button(marker_button: QPushButton):
    current_marker_mode = SESSION.context_marker_mode
    if current_marker_mode == "Disabled":
        next_marker_mode = "Enabled"
    elif current_marker_mode == "Enabled":
        next_marker_mode = "Disabled"
    else:
        raise ValueError(f"Unexpected value {current_marker_mode} encountered for 'context_marker_mode'. Need 'Enabled' or 'Disabled'")
    
    SESSION.context_marker_mode = next_marker_mode
    display_text = {"Disabled":"Enable marker tool", "Enabled":"Disable marker tool"}[next_marker_mode]
    marker_button.setText(display_text)
    SESSION.widget_dictionary["marker combo"].setDisabled({"Enabled":False, "Disabled":True}[next_marker_mode])




def set_initial_scoring_tally(df, session_df, page_only = True):

    if not page_only:
        cols = [x for x in session_df.columns if "Validation" in x]
        zeroes_dict = dict(zip(list(userInfo.statuses.keys()) , [0 for i in range(len(userInfo.statuses))]))
        SESSION.scoring_tally =  {"Session":copy.copy(zeroes_dict), "Data":copy.copy(zeroes_dict), "Page":copy.copy(zeroes_dict)}

        # Counts for the whole cell set
        melted = df[cols].melt()
        scoring_tally_series = melted.loc[melted["value"] == 1].value_counts()
        for ind in scoring_tally_series.index:
            score = ind[0].replace("Validation | ",'')
            SESSION.scoring_tally["Data"][score] = scoring_tally_series[ind]
        
        # Counts for just the cells in this session
        melted = session_df[cols].melt()
        scoring_tally_series = melted.loc[melted["value"] == 1].value_counts()
        for ind in scoring_tally_series.index:
            score = ind[0].replace("Validation | ",'')
            SESSION.scoring_tally["Session"][score] = scoring_tally_series[ind]
    
    # Counts for the page
    for score in [x["validation_call"] for i,x in SESSION.current_cells.items()]:
        try:
            SESSION.scoring_tally["Page"][score] = SESSION.scoring_tally["Page"][score] + 1
        except KeyError:
            SESSION.scoring_tally["Page"][score] = 1

def update_scoring_tally(old_score, new_score, in_page = True):
    SESSION.scoring_tally["Session"][new_score] = SESSION.scoring_tally["Session"][new_score] +1
    SESSION.scoring_tally["Session"][old_score] = SESSION.scoring_tally["Session"][old_score] -1

    SESSION.scoring_tally["Data"][new_score] = SESSION.scoring_tally["Data"][new_score] +1
    SESSION.scoring_tally["Data"][old_score] = SESSION.scoring_tally["Data"][old_score] -1

    if in_page:
        SESSION.scoring_tally["Page"][new_score] = SESSION.scoring_tally["Page"][new_score] +1
        SESSION.scoring_tally["Page"][old_score] = SESSION.scoring_tally["Page"][old_score] -1

def update_scoring_tally_all(new_score):
    for score, key in userInfo.statuses.items():
        
        page_size = len(SESSION.page_cells)
        if score == new_score:
            difference = page_size - SESSION.scoring_tally["Page"][score]
            SESSION.scoring_tally["Session"][score] = SESSION.scoring_tally["Session"][score] + difference
            SESSION.scoring_tally["Data"][score] = SESSION.scoring_tally["Data"][score] + difference
            SESSION.scoring_tally["Page"][score] = page_size
        else:    
            SESSION.scoring_tally["Session"][score] = SESSION.scoring_tally["Session"][score] - SESSION.scoring_tally["Page"][score]
            SESSION.scoring_tally["Data"][score] = SESSION.scoring_tally["Data"][score] - SESSION.scoring_tally["Page"][score]
            SESSION.scoring_tally["Page"][score] = 0

def set_scoring_label(scoring_label):
    display_string = "Page / Session / Full object data count"
    count = 0
    for score, tally in SESSION.scoring_tally["Data"].items():
        try:
            page_tally = SESSION.scoring_tally["Page"][score]
        except KeyError: # Could trigger when the page has no cells of this scoring type
            page_tally = 0
            SESSION.scoring_tally["Page"][score] = 0
        
        session_tally = SESSION.scoring_tally["Session"][score]
        if count % 2 == 0: 
            display_string+="<br>"
            display_string += f'<font color="{userInfo.statuses_hex[score]}">{score}: {page_tally}/{session_tally}/{tally}</font>'
        else:
            display_string += f' | <font color="{userInfo.statuses_hex[score]}">{score}: {page_tally}/{session_tally}/{tally}</font>'
        # Add a new line for every other score
        count+=1
    scoring_label.setText(display_string)
    return True

def set_cell_description_label(ID, display_text_override = None):
    # Instead of showing a cell's info, display this text
    if display_text_override is not None:
        description = f'{SESSION.saved_notes["page"]}<br>' + display_text_override
        SESSION.widget_dictionary['cell description label'].setText(description)
        SESSION.widget_dictionary['notes label'].setVisible(False)
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
    status = SESSION.current_cells[str(ID)]['validation_call']
    if STATUSES_TO_HEX[status] != "#ffffff":
        prefix = f'Page {SESSION.current_cells[ID]["Page"]}<br><font color="{STATUSES_TO_HEX[status]}">{cell_name}</font>'
    else:
        prefix = f'Page {SESSION.current_cells[ID]["Page"]}<br>{cell_name}' 

    # Add intensities
    intensity_series = SAVED_INTENSITIES[ID]
    # intensity_series = SESSION.session_cells[ID]['intensities']
    names = list(intensity_series.index)
    intensity_str = ''
    for fluor in userInfo.channels:
        if fluor == 'Composite':
            continue
        # fluor = str(cell).replace(" Cell Intensity","")
        fluor = str(fluor)
        intensity_str += f'<br><font color="{userInfo.channelColors[fluor].replace("blue","blue")}">{fluor}</font>'
        def add_values(intensity_str, fluor, intensity_lookup):
            flag = True
            name = intensity_lookup + ': No data'
            try:
                cyto = intensity_lookup
                cyto = [x for x in names if (cyto in x and 'Cytoplasm Intensity' in x)][0]
                val = round(float(intensity_series[cyto]),1)
                intensity_str += f'<font color="{userInfo.channelColors[fluor].replace("blue","blue")}"> cyto: {val}</font>'
                flag = False
                name = cyto.replace(' Cytoplasm Intensity','')
            except (KeyError, IndexError): pass
            try:
                nuc = intensity_lookup
                nuc = [x for x in names if (nuc in x and 'Nucleus Intensity' in x)][0]
                val = round(float(intensity_series[nuc]),1)
                intensity_str += f'<font color="{userInfo.channelColors[fluor].replace("blue","blue")}"> nuc: {val}</font>'
                flag = False
                name = nuc.replace(' Nucleus Intensity','')
            except (KeyError, IndexError): pass
            try:
                cell = intensity_lookup
                cell = [x for x in names if (cell in x and 'Cell Intensity' in x)][0]
                val = round(float(intensity_series[cell]),1)
                intensity_str += f'<font color="{userInfo.channelColors[fluor].replace("blue","blue")}"> cell: {val}</font>'
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
    
    SESSION.widget_dictionary['cell description label'].setText(prefix + intensity_str)
    if note == '-' or note == '' or note is None: 
        note = ''
        SESSION.widget_dictionary['notes label'].setVisible(False)
    else:
        note = f'<font size="5pt">{note}</font>'
        SESSION.widget_dictionary['notes label'].setVisible(True)
    SESSION.widget_dictionary['notes label'].setText(note)
    VIEWER.window._qt_viewer.setFocus()
    return True
######------------------------- Image loading and processing functions ---------------------######

def retrieve_status(cell_id, status, new_page):
    ''' Kind of an anachronistic function at this point.'''
    
    if new_page:
        if type(status) is not str or status not in STATUS_COLORS.keys():
            status = "Unseen"
        # Save to dict to make next retrieval faster
        # If there are annotations, need to track a separate list for each one
        SESSION.current_cells[str(cell_id)]['validation_call'] = status
        return status
    else:
        # Just grab it because it's there already
        try:
            return SESSION.current_cells[str(cell_id)]['validation_call']
        except:
            raise Exception(f"Looking for {cell_id} in the Status list dict but can't find it. List here:\n {SESSION.current_cells.keys()}")


def black_background(color_space, mult, CPR):
    if color_space == 'RGB':
        return np.zeros((ceil((PAGE_SIZE*mult)/CPR)*(userInfo.imageSize+2),(userInfo.imageSize+2) * CPR, 4))
    elif color_space == 'Luminescence':
        return np.zeros((ceil((PAGE_SIZE*mult)/CPR)*(userInfo.imageSize+2),(userInfo.imageSize+2) * CPR))


''' Add images layers for Gallery and Multichannel modes. Only make visible the layers for the active mode'''
def add_layers(viewer: napari.Viewer, pyramid, cells, offset: int, new_page=True):
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
        for fluor in userInfo.channels: # loop through channels
            if fluor in userInfo.channels and fluor != 'Composite':
                positions.append(userInfo.channelOrder[fluor]) # channelOrder dict holds mappings of fluors to position in image data

        if RAW_PYRAMID is None:
            # print("Using zarr/dask")
            cell_punchout = SESSION.dask_array[positions,cell_y-offset:cell_y+offset, cell_x-offset:cell_x+offset].compute() # 0 is the largest pyramid layer         
        else:
            print("Using full size (raw) image. DANGER. DEPRECATED!")
            # dask / zarr lazy reading didn't work, so entire image should be in memory as np array
            # This method is deprecated at this point. Probably won't work.
            # cell_punchout = pyramid[cell_x-offset:cell_x+offset,cell_y-offset:cell_y+offset,pos].astype(np.uint8)

        fluor_index = 0
        for fluor in userInfo.channels: # loop through channels
            if fluor != 'Composite':
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
        SESSION.multichannel_page_images = copy.copy(page_image_multichannel)


    print(f"\nMy scale is {SESSION.image_scale}")
    sc = (SESSION.image_scale, SESSION.image_scale) if SESSION.image_scale is not None else None

    for fluor in list(page_image_gallery.keys()):
        # Passing gamma is currently bugged. Suggested change is to remove the validation in the _on_gamma_change 
        #   (now located at napari/_vispy/layers/image.py
        # See https://github.com/napari/napari/issues/1866
        fluor_gamma = SESSION.view_settings[fluor+" gamma"]
        fluor_contrast = [SESSION.view_settings[fluor+" black-in"],SESSION.view_settings[fluor+" white-in"]]
        print(f"Adding layers now. fluor is {fluor}, view settings are gamma {fluor_gamma}, contrast {fluor_contrast}")
        if fluor == 'Composite':
            continue # The merged composite consists of each layer's pixels blended together, so there is no composite layer itself
        if SESSION.absorption_mode:
            viewer.add_image(page_image_gallery[fluor], name = f"Gallery {fluor}", blending = 'minimum',
                colormap = custom_color_functions.retrieve_cm(userInfo.channelColors[fluor]+' inverse'), scale = sc, interpolation="linear",
                gamma=fluor_gamma, contrast_limits=fluor_contrast)
            viewer.add_image(page_image_multichannel[fluor], name = f"Multichannel {fluor}", blending = 'minimum',
                colormap = custom_color_functions.retrieve_cm(userInfo.channelColors[fluor]+' inverse'), scale = sc, interpolation="linear",
                gamma=fluor_gamma, contrast_limits=fluor_contrast)
            
        else:
            viewer.add_image(page_image_gallery[fluor], name = f"Gallery {fluor}", blending = 'additive',
                colormap = custom_color_functions.retrieve_cm(userInfo.channelColors[fluor]), scale = sc, interpolation="linear",
                gamma=fluor_gamma, contrast_limits=fluor_contrast)
            viewer.add_image(page_image_multichannel[fluor], name = f"Multichannel {fluor}", blending = 'additive',
                colormap = custom_color_functions.retrieve_cm(userInfo.channelColors[fluor]), scale = sc, interpolation="linear",
                gamma=fluor_gamma, contrast_limits=fluor_contrast)
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
                                        face_color='#00000000', scale=sc)
    viewer.add_shapes(nuclei_box_coords_m, name="Multichannel Nuclei Boxes", shape_type="rectangle", edge_width=1, edge_color=nb_color_hex, 
                                        face_color='#00000000', scale=sc)
    SESSION.multichannel_nuclei_box_coords = nuclei_box_coords_m

    # Defunct borders around each cell image. Don't think it's necessary, and definitely adds more visual clutter
    # viewer.add_shapes(status_box_coords_g, name="Gallery Status Edges", shape_type="rectangle", edge_width=1, edge_color=edge_col_list, 
    #                                     face_color='#00000000', scale=sc, visible=False, opacity=1)
    # viewer.add_shapes(status_box_coords_m, name="Multichannel Status Edges", shape_type="rectangle", edge_width=1, edge_color=edge_col_list, 
    #                                     face_color='#00000000', scale=sc, visible=False, opacity=1)
    viewer.add_shapes(status_box_flags_g, name="Gallery Status Squares", shape_type="rectangle", edge_width=1, edge_color=edge_col_list, 
                                        face_color=edge_col_list, scale=sc, opacity=1)
    viewer.add_shapes(status_box_flags_m, name="Multichannel Status Squares", shape_type="rectangle", edge_width=1, edge_color=edge_col_list, 
                                        face_color=edge_col_list, scale=sc, opacity=1)
    viewer.add_shapes(status_box_coords_g, name="Gallery Status Numbers", shape_type="rectangle", edge_width=0, face_color='#00000000',
                                            features=features, text = nb_text,
                                            scale=sc,  opacity=1)
    viewer.add_shapes(status_box_coords_m, name="Multichannel Status Numbers", shape_type="rectangle", edge_width=0, 
                                            features=features, text = nb_text, face_color = "#00000000",
                                            scale=sc, opacity=1)
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
        if "Composite" in userInfo.active_channels: 
            offset_x = (userInfo.imageSize+2) * list([x for x in userInfo.channels if x!="Composite"]).index(fluor)
            return (global_y, offset_x+local_x)
        elif fluor in userInfo.active_channels:
            offset_x = (userInfo.imageSize+2) * list([x for x in userInfo.active_channels if x!="Composite"]).index(fluor)
            return (global_y, offset_x+local_x)
        else:
            return (-10,-10) # will result in a None from layer.data.get_value

    

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
        if SESSION.mode == "Multichannel": 
            # Bail if in multichannel mode and mouse is off to the right. Hard coding this since the grid to id dict
            #   has the full multichannel grid shape, but now I am allowing users to shrink the grid when toggling channels.

            if coords[1] > (len([x for x in userInfo.active_channels if x !="Composite"])+1)*(userInfo.imageSize+2) and "Composite" not in userInfo.active_channels:
                
                return "None" , None, None
            
        if SESSION.mode == "Context":
            for fluor in userInfo.channels:
                if fluor == "Composite": continue

                # Requesting single pixel value from Dask array layer 0
                try:

                    v = str(int(viewer.layers["Context "+fluor].get_value(data_coordinates)[1])) 
                    # get_value returns a tuple from the dask array like (0,25). First number indicates the pyramid layer, second is the value.
                    # Seems to default to returning the current layer shown to the user which is acceptable.
                    # v = str(int(viewer.layers["Context "+fluor].data[0][coords]))
                except (IndexError, TypeError):
                    v = None # If you are very far off the canvas, get_value returns None. Also if the channel is not visible
                vals[fluor] =  v if v is not None else "-"
            
            # Now find the name of the closest cell 
            # curY, curX = SESSION.mouse_coords
            # print(SESSION.session_cells.loc[SESSION.session_cells['center_x'] < ])
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
                VIEWER.layers["Context Closest Cell Box"].visible = False
            except KeyError:
                pass
            return False
        try:
            VIEWER.layers["Context Closest Cell Box"].visible = True
            layer_present = True
        except KeyError:
            layer_present = False
        

        layer = cell["Layer"]; cid = cell["cid"]
        cname = str(cid) if layer is None else f"{layer} {cid}"
        features = {'cid_feat': [cid]}
        cell_bbox = [[cell["YMin"],cell["XMin"]] , [cell["YMax"],cell["XMax"]] ]

        sc = (SESSION.image_scale, SESSION.image_scale) if SESSION.image_scale is not None else None
        
        nb_color_hex = userInfo.statuses_hex[SESSION.current_cells[cname]['validation_call']] #'#000000' if SESSION.absorption_mode else '#ffffff'
        nb_text = {'string':'{cid_feat}', 'anchor':'upper_left', 'size' : 8, 'color':nb_color_hex}
        SESSION.context_closest_cell_text_object = nb_text
        if layer_present:
            VIEWER.layers["Context Closest Cell Box"].data = [cell_bbox]   
            VIEWER.layers["Context Closest Cell Box"].edge_color = nb_color_hex  
            VIEWER.layers["Context Closest Cell Box"].features = features   
            VIEWER.layers["Context Closest Cell Box"].text = nb_text   
        else:
            VIEWER.add_shapes([cell_bbox], name="Context Closest Cell Box", shape_type="rectangle", edge_width=2, edge_color=nb_color_hex, 
                            opacity=0.9, face_color='#00000000', scale=sc, text = nb_text, features=features)
        VIEWER.layers.selection.active = VIEWER.layers[f"Gallery {userInfo.channels[0]}"] 

    ''' You need to disable napari's native mouse callback that displays the status first.
            This function is in napari.components.viewer_model.py ViewerModel._update_status_bar_from_cursor''' 
    @viewer.mouse_move_callbacks.append
    def mouse_movement_wrapper(viewer, event):
        # The 'event' here is from vispy.app.canvas.MouseEvent
        SESSION.mouse_coords_world = event._pos # Store this 
        display_intensity(viewer,event)
        label_cells_mouseover(viewer,event)
        #Reset flag each cycle, so this signal can only last for one. Important to stop lagginess!!!
        SESSION.cell_under_mouse_changed = False
        pass

    ''' When in context mode, if radio toggle is enabled, user can move the mouse over a cell to relabel it
      as a certain scoring decision. Will need to implement this in the GUI as a dropdown menu'''
    @catch_exceptions_to_log_file("runtime_mouse-movement-over-context-cell")
    def label_cells_mouseover(viewer,event):
        if SESSION.mode != "Context" or SESSION.context_marker_mode == "Disabled":
            return False # Leave if not in context mode
        
        scoring_target = SESSION.widget_dictionary["marker combo"].currentText()
        if SESSION.cell_under_mouse_changed and scoring_target is not None:
            # print("\n%%%")
            # print(f"Modifier is {SESSION.last_score_used}")
            exec("globals()[f'{scoring_target}_func'](VIEWER)")
            
            # from qtpy.QtGui import QMouseEvent
            # x = QMouseEvent()
            #TODO


    @catch_exceptions_to_log_file("runtime_process-cell-under-mouse")
    def display_intensity(viewer, event): 
        if SESSION.mode == "Context":
            kw_res = find_mouse(event.position)
            cell = kw_res["cell"]
            coords = kw_res["coords"]
            vals = kw_res["vals"]

            if (vals is None) or (next(iter(vals.values())) is None):
                # Don't do anything else - the cursor is out of bounds of the image
                VIEWER.status = 'Out of bounds context'
                SESSION.cell_under_mouse = None
                return False 
            
            if cell is not None:
                cid = cell["Object Id"]
                layer = cell["Analysis Region"] if ANNOTATIONS_PRESENT else None
                ckey = f'{layer} {cid}' if ANNOTATIONS_PRESENT else str(cid)
                try:
                    cell_dict = SESSION.current_cells[ckey]
                    if cell_dict != SESSION.cell_under_mouse: SESSION.cell_under_mouse_changed = True
                except KeyError:
                    center_x = int((cell['XMax']+cell['XMin'])/2)
                    center_y = int((cell['YMax']+cell['YMin'])/2)
                    vcs = cell[SESSION.validation_columns]
                    validation_call = str(vcs[vcs == 1].index.values[0]).replace(f"Validation | ", "")

                    cell_dict = {'Layer':layer,"cid": cid,"center_x": center_x,'center_y': center_y,
                                            'validation_call': validation_call, 'XMax' : cell['XMax'],'XMin':cell['XMin'],
                                            'YMax' : cell['YMax'],'YMin':cell['YMin'], 'Page':cell["Page"]}
                    
                    SESSION.current_cells[ckey] = cell_dict
                    record_notes_and_intensities(cell, SESSION.intensity_columns)
                    SESSION.cell_under_mouse_changed = True # If we haven' seen this cell before, it has definitely changed.
                # Now that we have the cell dict, proceed to display
                SESSION.cell_under_mouse =  cell_dict # save info
                set_cell_description_label(ckey)
                # Draw box around closest cell
                box_closest_context_mode_cell(cell_dict)

            else: # Not near a cell
                set_cell_description_label(None, display_text_override="No cell nearby to show!")
                try:
                    VIEWER.layers.selection.active = VIEWER.layers["Context Closest Cell Box"]
                    VIEWER.layers.remove_selected()
                except KeyError:
                    pass
                # reset active layer to an image
                viewer.layers.selection.active = viewer.layers[f"Gallery {userInfo.channels[0]}"] 

    
            # Deal with pixel intensities
            output_str = ''
            for fluor, val in vals.items():
                if val != "-": val = int(val)
                output_str+= f'<font color="{userInfo.channelColors[fluor].replace("blue","blue")}">    {val}   </font>' # "#0462d4"
            
            if ANNOTATIONS_PRESENT:
                cname = f'Cell {cid} from {layer}' if cell is not None else "Context Mode" # default display name is the mouse is not under a cell
            else:
                cname = f'Cell {cid}' if cell is not None else "Context Mode" # default display name is the mouse is not under a cell
            
            sc = STATUSES_TO_HEX[SESSION.current_cells[str(ckey)]['validation_call']] if cell is not None else '' # 
            if not sc == "#ffffff":
                VIEWER.status = f'<font color="{sc}">{cname}</font> pixel intensities at {coords}: {output_str}'
            else:
                VIEWER.status = f'{cname} pixel intensities at {coords}: {output_str}'

        elif SESSION.mode == "Gallery" or SESSION.mode == "Multichannel":
            try:
                cell_name,coords,vals = find_mouse(event.position, scope = 'grid') 
            except TypeError:
                # find_mouse seems to be returning NoneType sometimes (no idea why) which can't be unpacked
                return False
            
            if vals is None:
                # Don't do anything else
                VIEWER.status = 'Out of bounds gallery / multichannel'
                SESSION.cell_under_mouse = None
                return True
            
            SESSION.cell_under_mouse = SESSION.current_cells[cell_name] # save info
            cell_num = cell_name.split()[-1]; cell_anno = cell_name.replace(' '+cell_num,'')

            if ANNOTATIONS_PRESENT:
                image_name = f'Cell {cell_num} from {cell_anno}'
            else:
                image_name = f'Cell {cell_num}'

            set_cell_description_label(str(cell_name))
            output_str = ''

            for fluor, val in vals.items():
                if val != "-": val = int(val)
                output_str+= f'<font color="{userInfo.channelColors[fluor].replace("blue","blue")}">    {val}   </font>'
        
            sc = STATUSES_TO_HEX[SESSION.current_cells[str(cell_name)]['validation_call']]
            if sc != "#ffffff":
                VIEWER.status = f'<font color="{sc}">{image_name}</font> intensities at {coords}: {output_str}'
            else:
                VIEWER.status = f'{image_name} intensities at {coords}: {output_str}'

        #TODO decide on tooltip behavior. Could change appearance by making 
        # To make this work in napari version 0.4.18, made a change in napari.components.viewer_model.py
            # In ViewerModel._update_status_bar_from_cursor , commented out lines 483 to 489
        if SESSION.tooltip_visible:
            # napari.Viewer._window._qt_window
            
            # Gets mouse position at event._pos, maps to
            pos = viewer._window._qt_window.mapToGlobal(QPoint(*event._pos).__add__(QPoint(12,-33)))
            # print(f'{QPoint(*event._pos)} || {pos}')
            QToolTip.showText(pos, 
                              f'<p style="font-size: 20px;">{output_str}</p>', 
                              viewer._window._qt_window)
            # viewer.tooltip.text = f'<p style="font-size: 20px;">{output_str}</p>' 

    SESSION.display_intensity_func = display_intensity
    SESSION.find_mouse_func = find_mouse

    def change_status_display(cell_name, next_status):
        next_color_txt = userInfo.statuses_rgba[next_status]
        next_color_txt = list(x/255 if next_color_txt.index(x)!=3 else 1 for x in next_color_txt)

        SESSION.current_cells[str(cell_name)]['validation_call'] = next_status
        try:
            SESSION.page_cells[str(cell_name)]['validation_call'] = next_status
        except (KeyError, ValueError) as e:
            pass # Cell not in page. Should still be marked in SESSION.current_cells list

        set_cell_description_label(str(cell_name)) 
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
        
        # print(f"!!! {SESSION.mode} {SESSION.context_nuclei_boxes_text_object} {SESSION.context_nuclei_boxes_map_to_ind}")
        if SESSION.mode =="Context" and SESSION.context_nuclei_boxes_text_object is not None and SESSION.context_nuclei_boxes_map_to_ind:
            try:
                ind_target = SESSION.context_nuclei_boxes_map_to_ind[str(cell_name)]
                x = viewer.layers["Context Nuclei Boxes"].edge_color # List of colors
                x[ind_target] = next_color_txt # Change only the color of this cell
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
        for coords, cname in SESSION.grid_to_ID[SESSION.mode].items():
            SESSION.current_cells[str(cname)]['validation_call'] = next_status
            try:
                SESSION.page_cells[str(cname)]['validation_call'] = next_status
            except (KeyError, ValueError) as e:
                pass # Cell not in page. Should still be marked in SESSION.current_cells list
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
    
    @viewer.bind_key('Space', overwrite = True)
    @catch_exceptions_to_log_file("runtime_assign-next-status")
    def toggle_status(viewer):
        # Allows us to get the cell that is actually under the mouse. If we used the viewer's coordinates, it would show the coords on last
        #   mouse move. Since the user can move around with the arrow keys as well this does not suffice 
        cell = SESSION.cell_under_mouse
        if cell is None:
            return False # leave if the mouse is not near a cell (not sure that this could even happen)
        cell_name = f"{cell['Layer']} {cell['cid']}" if ANNOTATIONS_PRESENT else str(cell['cid'])  

            

        cur_status = SESSION.current_cells[str(cell_name)]['validation_call']
        cur_index = list(status_colors.keys()).index(cur_status)
        next_status = list(status_colors.keys())[(cur_index+1)%len(status_colors)]

        if SESSION.mode == "Context" and SESSION.nuclei_boxes_vis["Context"] == "Mouse":
            # Change Context boxes and mouse only box colors
            VIEWER.layers["Context Closest Cell Box"].edge_color = userInfo.statuses_hex[next_status]
            SESSION.context_closest_cell_text_object["color"] = userInfo.statuses_hex[next_status]
            viewer.layers["Context Closest Cell Box"].text = SESSION.context_closest_cell_text_object
        change_status_display(cell_name, next_status)

        # Update scoring tally
        update_scoring_tally(cur_status, next_status, cell_name in SESSION.page_cells.keys())
        set_scoring_label(SESSION.widget_dictionary["scoring label"])
        # change color of viewer status
        vstatus_list = copy.copy(VIEWER.status).split('>')
        vstatus_list[0] = sub(r'#.{6}',STATUSES_TO_HEX[SESSION.current_cells[str(cell_name)]['validation_call']], vstatus_list[0])
        VIEWER.status = ">".join(vstatus_list)

    @viewer.mouse_drag_callbacks.append
    @catch_exceptions_to_log_file("runtime_left-click-cell")
    def user_clicked(viewer, event):
        #TODO decide on the behavior for clicking on a cell
        if SESSION.cell_under_mouse is None:
            return None # Nothing to do if no cell under mouse
        layer = SESSION.cell_under_mouse['Layer']
        cid = str(SESSION.cell_under_mouse['cid'])
        # Allow user to click on a cell to get it's name into the entry box  
        if ANNOTATIONS_PRESENT:
            SESSION.widget_dictionary['notes annotation combo'].setCurrentText(layer)
            if SESSION.mode == "Context":
                SESSION.widget_dictionary['page cell layer'].setCurrentText(layer)
            SESSION.widget_dictionary['switch mode annotation'].setCurrentText(layer)
            SESSION.widget_dictionary["image_save_target_annotation"].setCurrentText(layer)
            SESSION.widget_dictionary["hist_annotations"].setCurrentText(layer)
            SESSION.widget_dictionary["violin_annotations"].setCurrentText(layer)
        
        SESSION.widget_dictionary["image_save_target_entry"].setText(cid)
        SESSION.widget_dictionary['notes cell entry'].setText(cid)
        if SESSION.mode == "Context":
            SESSION.widget_dictionary['page cell id'].setText(cid)
        SESSION.widget_dictionary['switch mode cell'].setText(cid)
        SESSION.widget_dictionary["hist_target_entry"].setText(cid)
        SESSION.widget_dictionary["violin_target_entry"].setText(cid)
        


    ''' Dynamically make new functions that can change scoring decisions with a custom keypress. This
        will allow the user to choose their own scoring decisions, colors, and keybinds'''
    def create_score_funcs(scoring_decision, keybind):
        @viewer.bind_key(keybind)
        @catch_exceptions_to_log_file("runtime_change-status")
        def set_score(viewer):

            # Allows us to get the cell that is actually under the mouse. If we used the viewer's coordinates, it would show the coords on last
            #   mouse move. Since the user can move around with the arrow keys as well this does not suffice 
            cell = SESSION.cell_under_mouse 
            if cell is None:
                return False # leave if the mouse is not near a cell (not sure that this could even happen)
            cell_name = f"{cell['Layer']} {cell['cid']}" if ANNOTATIONS_PRESENT else str(cell['cid'])    
            
            
            if SESSION.mode == "Context" and SESSION.nuclei_boxes_vis["Context"] == "Mouse":
                # Change Context boxes and mouse only box colors
                VIEWER.layers["Context Closest Cell Box"].edge_color = userInfo.statuses_hex[scoring_decision]
                SESSION.context_closest_cell_text_object["color"] = userInfo.statuses_hex[scoring_decision]
                viewer.layers["Context Closest Cell Box"].text = SESSION.context_closest_cell_text_object
            
            # Update scoring tally BEFORE changing status 
            update_scoring_tally(SESSION.current_cells[str(cell_name)]['validation_call'], scoring_decision, cell_name in SESSION.page_cells.keys())
            set_scoring_label(SESSION.widget_dictionary["scoring label"])

            change_status_display(cell_name, scoring_decision)
            SESSION.last_score_used = scoring_decision

            # change color of viewer status
            vstatus_list = copy.copy(VIEWER.status).split('>')
            vstatus_list[0] = sub(r'#.{6}',STATUSES_TO_HEX[SESSION.current_cells[str(cell_name)]['validation_call']], vstatus_list[0])
            VIEWER.status = ">".join(vstatus_list)

        @viewer.bind_key(f'Control-{keybind}')
        @viewer.bind_key(f'Shift-{keybind}')
        @catch_exceptions_to_log_file("runtime_change-status-all")
        def set_scoring_all(viewer):
            if SESSION.mode == "Context": 
                # set up for marker tool   
                toggle_marker_button(SESSION.widget_dictionary["marker button"])
                SESSION.widget_dictionary["marker combo"].setCurrentText(scoring_decision)
                SESSION.widget_dictionary["marker combo"].setStyleSheet(f"background-color: rgba{userInfo.statuses_rgba[scoring_decision]}; selection-background-color: rgba(0,0,0,30);")
                if SESSION.context_marker_mode == "Enabled":
                    set_score(viewer)
                return True
            
            # Update scoring tally BEFORE changing status 
            update_scoring_tally_all(scoring_decision)
            set_scoring_label(SESSION.widget_dictionary["scoring label"])

            change_status_display_forAll(scoring_decision)

            cell_name,data_coordinates,val = find_mouse(viewer.cursor.position)
            if val is None:
                return None
            set_cell_description_label(str(cell_name))
            vstatus_list = copy.copy(VIEWER.status).split('>')
            vstatus_list[0] = sub(r'#.{6}',STATUSES_TO_HEX[SESSION.current_cells[str(cell_name)]['validation_call']], vstatus_list[0])
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
        if ("Control" in event.modifiers) and ("Shift" in event.modifiers):
            pass
        elif "Shift" in event.modifiers:
            if SESSION.mode == "Multichannel":
                toggle_session_mode_catch_exceptions(SESSION.last_mode)
            else:
                if SESSION.cell_under_mouse is None: 
                    return False # Can't do anything without a target cell
                layer = SESSION.cell_under_mouse["Layer"]
                cid = str(SESSION.cell_under_mouse["cid"])
                if ANNOTATIONS_PRESENT:
                    SESSION.widget_dictionary['switch mode annotation'].setCurrentText(layer)
                SESSION.widget_dictionary['switch mode cell'].setText(cid)
                toggle_session_mode_catch_exceptions("Multichannel")
        elif "Control" in event.modifiers:
            # Go to context or go back to last mode
            if SESSION.mode == "Context":
                toggle_session_mode_catch_exceptions(SESSION.last_mode)
            else:
                if SESSION.cell_under_mouse is None: 
                    return False # Can't do anything without a target cell
                layer =SESSION.cell_under_mouse["Layer"]
                cid = str(SESSION.cell_under_mouse["cid"])
                if ANNOTATIONS_PRESENT:
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
            toggle_boxes(viewer) # Allow 'h' to trigger cell box toggle when in context mode
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
    def toggle_boxes(viewer):
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
        def __init__(self, y, x, world_coords) -> None:
            self.position = (y,x)
            self._pos = world_coords

    @viewer.bind_key('Up')
    @catch_exceptions_to_log_file("runtime_arrow-pan")
    def scroll_up(viewer):
        z,y,x = viewer.camera.center
        sc = 1 if SESSION.image_scale is None else SESSION.image_scale
        step_size = ((userInfo.imageSize+2)*sc)
        if SESSION.mode == "Context":
            fluor = userInfo.channels[0]
            if fluor == "Composite":
                fluor = userInfo.channels[1] # Make sure to get an actual channel. Doesn't matter which one
            mult =  int(viewer.layers["Context "+fluor].get_value((1,1))[0]) + 1.5 # This returns a number corresponding to the current pyramid layer. Biggest is 0
            step_size *= (mult**2)

        viewer.camera.center = (y-int(step_size),x)

        curY, curX = SESSION.mouse_coords
        SESSION.cell_under_mouse_changed = True
        display_intensity(viewer, dummyCursor(curY-step_size, curX, SESSION.mouse_coords_world))

    @viewer.bind_key('Down')
    @catch_exceptions_to_log_file("runtime_arrow-pan")
    def scroll_down(viewer):
        z,y,x = viewer.camera.center
        sc = 1 if SESSION.image_scale is None else SESSION.image_scale
        step_size = ((userInfo.imageSize+2)*sc) 
        if SESSION.mode == "Context":
            fluor = userInfo.channels[0]
            if fluor == "Composite":
                fluor = userInfo.channels[1] # Make sure to get an actual channel. Doesn't matter which one
            mult =  int(viewer.layers["Context "+fluor].get_value((1,1))[0]) + 1.5 # This returns a number corresponding to the current pyramid layer. Biggest is 0
            step_size *= (mult**2)
        viewer.camera.center = (y+int(step_size),x)

        curY, curX = SESSION.mouse_coords
        SESSION.cell_under_mouse_changed = True
        display_intensity(viewer, dummyCursor(curY+step_size, curX, SESSION.mouse_coords_world))
    
    @viewer.bind_key('Left')
    @catch_exceptions_to_log_file("runtime_arrow-pan")
    def scroll_left(viewer):
        z,y,x = viewer.camera.center
        sc = 1 if SESSION.image_scale is None else SESSION.image_scale
        step_size = ((userInfo.imageSize+2)*sc)
        if SESSION.mode == "Context":
            fluor = userInfo.channels[0]
            if fluor == "Composite":
                fluor = userInfo.channels[1] # Make sure to get an actual channel. Doesn't matter which one
            mult =  int(viewer.layers["Context "+fluor].get_value((1,1))[0]) + 1.5 # This returns a number corresponding to the current pyramid layer. Biggest is 0
            step_size *= (mult**2)

        viewer.camera.center = (y,x-int(step_size))
        curY, curX = SESSION.mouse_coords
        SESSION.cell_under_mouse_changed = True
        display_intensity(viewer, dummyCursor(curY,curX-step_size, SESSION.mouse_coords_world))

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
        if SESSION.mode == "Context":
            fluor = userInfo.channels[0]
            if fluor == "Composite":
                fluor = userInfo.channels[1] # Make sure to get an actual channel. Doesn't matter which one
            mult =  int(viewer.layers["Context "+fluor].get_value((1,1))[0]) + 1.5 # This returns a number corresponding to the current pyramid layer. Biggest is 0
            step_size *= (mult**2)

        viewer.camera.center = (y,x+int(step_size))
        curY, curX = SESSION.mouse_coords
        SESSION.cell_under_mouse_changed = True
        display_intensity(viewer, dummyCursor(curY, curX+step_size, SESSION.mouse_coords_world))


    # On Macs, ctrl-arrow key is taken by something else.
    @viewer.bind_key('Shift-Right')  
    @viewer.bind_key('Shift-Up') 
    @viewer.bind_key('Control-Right')  
    @viewer.bind_key('Control-Up')   
    @catch_exceptions_to_log_file("runtime_arrow-zoom")
    def zoom_in(viewer: napari.Viewer):
        step_size = 1.15 if SESSION.mode !="Context" else 1.4
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
        step_size = 1.15 if SESSION.mode !="Context" else 1.4
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

    @viewer.bind_key('Ctrl-i')
    @catch_exceptions_to_log_file("runtime_toggle-tooltip")
    def toggle_tooltip(viewer: napari.Viewer):
        current = SESSION.tooltip_visible
        SESSION.tooltip_visible = not current
        # viewer.tooltip.visible = not current
        s = {True:"enabled",False:"disabled"}[not current]
        viewer.status = f"Tooltip {s}!"
        
    @viewer.bind_key('Alt-m')
    @catch_exceptions_to_log_file("runtime_open-manual")
    def open_guide(viewer):
        os.startfile(os.path.normpath(os.curdir+ r"/data/GalleryViewer v{x} User Guide.pdf".format(x=VERSION_NUMBER)))

######------------------------- Misc + Viewer keybindings ---------------------######

@catch_exceptions_to_log_file("runtime_save-page-image")
def save_page_image(viewer:napari.Viewer, mode_choice:str = "Gallery", clipboard :bool = True, separate = False, borders="Black borders"):

    restore_viewsettings_from_cache(arrange_multichannel=True if mode_choice == 'Multichannel' else False, viewer = VIEWER, session=SESSION,) # Resets visible layers
    # Set only chosen mode's layers visible so they will be processed by the blending function
    page_shape = None
    for layer in viewer.layers:
        layer.visible = False
        for fluor in userInfo.channels:
            if "Composite" not in userInfo.active_channels and fluor not in userInfo.active_channels:
                continue
            layer = VIEWER.layers[f"{mode_choice} {fluor}"]
            page_shape = layer.data.shape
            layer.visible = True

    blended = _blend_visible_layers(viewer, page_shape, mode_choice, page_image = True)

    ##-------------------- add contrasting borders to page image if desired
    if (borders =="Black borders" and SESSION.absorption_mode) or (borders =="White borders" and not SESSION.absorption_mode):
        row,col = 0,0
        fill = 0 if SESSION.absorption_mode else 1
        lim = userInfo.page_size if mode_choice == 'Gallery' else userInfo.page_size * SESSION.cells_per_row[mode_choice]
        print(f"Image shape is {blended.shape}")
        for _ in range(lim):
            if col == SESSION.cells_per_row[mode_choice]:
                col = 0
                row = row+1
            
            x1 = (row*(userInfo.imageSize+2)) ; x2 = x1 + userInfo.imageSize + 2
            y1 = (col*(userInfo.imageSize+2)) ; y2 = y1 + userInfo.imageSize + 2

            print(f"My Xs are {x1} {x2} and my Ys are {y1} {y2}")
            if (x2,y2) == blended.shape[:2]:
                blended[x1:,y1] = fill
                blended[x1:,-1] = fill
                blended[x1,y1:] = fill
                blended[-1,y1:] = fill
            elif x2 == blended.shape[0]:
                blended[x1:,y1] = fill
                blended[x1:,y2] = fill
                blended[x1,y1:y2] = fill
                blended[-1,y1:y2] = fill
            elif y2 == blended.shape[1]:
                blended[x1:x2,y1] = fill
                blended[x1:x2,-1] = fill
                blended[x1,y1:] = fill
                blended[x2,y1:] = fill
            else:
                blended[x1:x2,y1] = fill
                blended[x1:x2,y2] = fill
                blended[x1,y1:y2] = fill
                blended[x2,y1:y2] = fill
            col +=1


    viewer.layers.selection.active = VIEWER.layers[f"Gallery {userInfo.channels[0]}"] 
    if separate:
        _slice_page_image(viewer, mode_choice, blended)
    else:
        _send_image_to_user(viewer, blended, clipboard)
    restore_viewsettings_from_cache(viewer = VIEWER, session=SESSION,)
    viewer.window._qt_viewer.setFocus() # restore focus
    # Done!

@catch_exceptions_to_log_file("runtime_save-cell-image")
def save_cell_image(viewer: napari.Viewer, cell_id : str, layer_name = None, clipboard :bool = True, borders = 'No borders' ):

    # Silence all layers
    for layer in viewer.layers:
        layer.visible = False
    
    df = SESSION.session_cells
    try:
        if ANNOTATIONS_PRESENT:
            singlecell_df = df[(df['Object Id']==int(cell_id)) & (df['Analysis Region']==str(layer_name))]
        else:
            singlecell_df = df[df['Object Id']==int(cell_id)]
    except (ValueError, TypeError, IndexError):
        # Cell doesn't exist
        if ANNOTATIONS_PRESENT:
            viewer.status = f"Unable to screenshot cell '{layer_name} {cell_id}'. This ID was not found in my table."
        else:
            viewer.status = f"Unable to screenshot cell '{cell_id}'. This ID was not found in my table."
        return False
    
    # print(f"Trying to take screenshot for the following frame: {singlecell_df}")
    cell_x = singlecell_df.iloc[0]["center_x"]
    cell_y = singlecell_df.iloc[0]["center_y"]
    # Get images from dask in chosen channels

    # if RAW_PYRAMID is None:
    #     # print("Using zarr/dask")

    sc = (SESSION.image_scale, SESSION.image_scale) if SESSION.image_scale is not None else None
    # Need to know this for multichannel mode
    num_channels = len(userInfo.active_channels) if "Composite" not in userInfo.active_channels else len(userInfo.channels)
    pos = 0
    for fluor in list(userInfo.channels):

        # Passing gamma is currently bugged. Suggested change is to remove the validation in the _on_gamma_change 
        #   (now located at napari/_vispy/layers/image.py
        # See https://github.com/napari/napari/issues/1866
        if (fluor == 'Composite') or (fluor not in userInfo.active_channels and "Composite" not in userInfo.active_channels):
            continue # The merged composite consists of each layer's pixels blended together, so there is no composite layer itself
        

        fluor_gamma = 2-(2*SESSION.view_settings[fluor+" gamma"]) + 0.001
        fluor_contrast = [SESSION.view_settings[fluor+" black-in"],SESSION.view_settings[fluor+" white-in"]]
        position = userInfo.channelOrder[fluor]
        if SESSION.mode in ("Gallery","Context"):
            offset = userInfo.imageSize // 2
            cell_image = SESSION.dask_array[position,cell_y-offset:cell_y+offset, cell_x-offset:cell_x+offset].compute() # 0 is the largest pyramid layer         
            imsize = userInfo.imageSize
        elif SESSION.mode == "Multichannel":
            if borders != "No borders":
                imsize = userInfo.imageSize + 2
            else:
                imsize = userInfo.imageSize
            offset = imsize // 2
            cell_image = np.zeros((imsize, imsize*(num_channels+1)))
            cell_punchout = SESSION.dask_array[position,cell_y-offset:cell_y+offset, cell_x-offset:cell_x+offset].compute()
            # if borders != "No borders":
            start = pos * imsize
            end = (pos+1) * imsize
            cell_image[0:imsize, start:end] = cell_punchout
            cell_image[-imsize:,-imsize:] = cell_punchout
            # else:
            #     start = (pos * imsize)+1
            #     end = ((pos+1) * imsize) -1
            #     cell_image[1:imsize-1, start:end] = cell_punchout
            #     cell_image[-(imsize-1):-1,-(imsize-1):-1] = cell_punchout
            pos +=1
        else:
            viewer.status = "Ran into a problem: unexpected viewer mode"
            raise ValueError(f"Unexpected session mode given: {SESSION.mode}")

        # SESSION.dask_array[positions,cell_y-offset:cell_y+offset, cell_x-offset:cell_x+offset].compute() # 0 is the largest pyramid layer         
        if SESSION.absorption_mode:
            viewer.add_image(cell_image, name = f"Screenshot {fluor}", blending = 'minimum',
                colormap = custom_color_functions.retrieve_cm(userInfo.channelColors[fluor]+' inverse'), scale = sc, interpolation="linear",
                gamma=fluor_gamma, contrast_limits=fluor_contrast)
            
        else:
            viewer.add_image(cell_image, name = f"Screenshot {fluor}", blending = 'additive',
                colormap = custom_color_functions.retrieve_cm(userInfo.channelColors[fluor]), scale = sc, interpolation="linear",
                gamma=fluor_gamma, contrast_limits=fluor_contrast)
 
    blended = _blend_visible_layers(viewer, (imsize, imsize))

    # Add line separations if desired
    if borders != 'No borders':
        fill = 0 if borders == 'Black borders' else 1
        if SESSION.mode == "Multichannel": 
            blended[0,:] = fill
            blended[-1,:] = fill
            for i in range(SESSION.cells_per_row['Multichannel']):
                y1 = i* imsize
                y2 = y1 + imsize
                blended[:,y1] = fill
                try:
                    blended[:,y2] = fill
                except IndexError:
                    blended[:,-1] = fill
        else:
            blended[0,:] = fill
            blended[-1,:] = fill
            blended[:,0] = fill
            blended[:,-1] = fill

    # Delete layers and resume
    viewer.layers.selection.clear()
    for layer in viewer.layers:
        if "Screenshot" in layer.name:
            viewer.layers.selection.add(layer)
    viewer.layers.remove_selected()
    viewer.layers.selection.active = VIEWER.layers[f"Gallery {userInfo.channels[0]}"]
    # Resets visible layers 
    restore_viewsettings_from_cache(viewer = VIEWER, session=SESSION,)
    _send_image_to_user(viewer, blended, clipboard)
    viewer.window._qt_viewer.setFocus() # restore focus
    # Done!

def _blend_visible_layers(viewer, blended_image_shape, mode_choice = None, page_image = False):
    print(f"incoming image shape: {blended_image_shape}")
    num_channels = len(userInfo.active_channels) if "Composite" not in userInfo.active_channels else len(userInfo.channels)
    # num_channels = num_channels - 1 if "Composite" in userInfo.active_channels else num_channels
    print(userInfo.active_channels)
    print(userInfo.channels)
    print(num_channels)
    if SESSION.absorption_mode: # Light mode. Subtractive color space
        if page_image: 
            blended = np.ones(blended_image_shape + (4,))
        elif SESSION.mode in ("Gallery","Context"):
            blended = np.ones(blended_image_shape + (4,))
        elif SESSION.mode == "Multichannel":
            blended_image_shape = (blended_image_shape[0], blended_image_shape[1]*(num_channels+1))
            blended = np.ones(blended_image_shape + (4,))
        else:
            viewer.status = "Ran into a problem: unexpected viewer mode"
            raise ValueError(f"Unexpected session mode given: {SESSION.mode}")
        
        for layer in viewer.layers:
            if layer.visible == False:
                continue # pass over everything except the screenshot layers
            # Subtract min or assign zero if value would be negative. subtracting would actually result in an overflow error since
            #   this data type is apparently unsigned ints. 
            normalized_data = np.where(layer.data <= layer.contrast_limits[0], 0, layer.data-layer.contrast_limits[0])
            # normalized to 0-1 range and apply gamma correction
            normalized_data = (normalized_data / (layer.contrast_limits[1] - layer.contrast_limits[0])) ** layer.gamma

            # Map to color
            colormapped_data = 1- layer.colormap.map(normalized_data.flatten())
            colormapped_data = colormapped_data.reshape(normalized_data.shape + (4,))

            # Blend in to composite image
            blended = blended-colormapped_data
            
    else: # Dark mode. Additive color space
        if page_image:
            blended = np.zeros(blended_image_shape + (4,))
        elif SESSION.mode in ("Gallery","Context"):
            blended = np.zeros(blended_image_shape + (4,))
        elif SESSION.mode == "Multichannel":
            blended_image_shape = (blended_image_shape[0], blended_image_shape[1]*(num_channels+1))
            blended = np.zeros(blended_image_shape + (4,))
        else:
            viewer.status = "Ran into a problem: unexpected viewer mode"
            raise ValueError(f"Unexpected session mode given: {SESSION.mode}")
        for layer in viewer.layers:
            if layer.visible == False:
                continue
            
            # Subtract min or assign zero if value would be negative. subtracting would actually result in an overflow error since
            #   this data type is apparently unsigned ints. 
            normalized_data = np.where(layer.data <= layer.contrast_limits[0], 0, layer.data-layer.contrast_limits[0])
            # normalized to 0-1 range and apply gamma correction
            normalized_data = (normalized_data / (layer.contrast_limits[1] - layer.contrast_limits[0])) ** layer.gamma
            
            # Map to color
            colormapped_data = layer.colormap.map(normalized_data.flatten())
            colormapped_data = colormapped_data.reshape(normalized_data.shape + (4,))

            # blend in to composite image
            blended = blended + colormapped_data

    # Clipping mostly to avoid negative numbers that might be present from a light mode cell image
    blended = blended.clip(min=0, max = 1)
    blended[..., 3] = 1 # set alpha channel to 1

    return blended

def _send_image_to_user(viewer, blended, clipboard, image_name_override = False , silence_animation = False):

    # Save image. Can leave if failure
    if not clipboard:
        # Need to save image only
        from matplotlib.image import imsave

        try:
            if not image_name_override:
                parent_folder = userInfo.last_image_save_folder 
                file_name, _ = QFileDialog.getSaveFileName(None,"Save single cell image",parent_folder,"PNG file (*.png);;All Files(*)")
                userInfo.last_image_save_folder = os.path.normpath(pathlib.Path(file_name).parent)
                imsave(file_name, blended)
            else:
                imsave(image_name_override, blended)
        except ValueError as e:
            # User closed save window?
            print(f"You just closed the save dialog!! {e} \n")
            return False

    else:
        im = (blended*255).astype(np.uint8)

        # Copy the image to the system clipboard
        output = BytesIO()
        Image.fromarray(im).convert("RGB").save(output, "BMP")
        im_data = output.getvalue()[14:] # not entirely sure about the mechanics here but we need to cut off the first couple bits
        output.close()

        def send_to_clipboard(clip_type, data):
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(clip_type, data)
            win32clipboard.CloseClipboard()
        send_to_clipboard(win32clipboard.CF_DIB, im_data)

    # Show flash to user, if desired
    if not silence_animation:
        from napari._qt.utils import add_flash_animation
        # Here we are actually applying the effect to the `_welcome_widget` and not # the `native` widget because it does
        #  not work on the `native` widget. It's probably because the widget is in a stack with the `QtWelcomeWidget`.
        add_flash_animation(viewer._window._qt_viewer._welcome_widget)
    return True

def _slice_page_image(viewer, page_mode, blended_image ):

    try:
        parent_folder = userInfo.last_image_save_folder 
        folder = str(QFileDialog.getExistingDirectory(None, "Select Directory", parent_folder))
        userInfo.last_image_save_folder = os.path.normpath(pathlib.Path(folder).parent)
        # save_folder_name = datetime.today().strftime(f'{}_%H%M%S.txt')
    except ValueError as e:
        # User closed save window?
        print(f"You just closed the save dialog (maybe?) {e} \n")
        return False

    im_size = userInfo.imageSize + 2
    if page_mode == "Gallery":
        for cell_dict in SESSION.page_cells.values():
            cname = f"{cell_dict['Layer']} {cell_dict['cid']}" if ANNOTATIONS_PRESENT else str(cell_dict['cid'])
            cname_display = f"{cell_dict['Layer']}- cell {cell_dict['cid']}" if ANNOTATIONS_PRESENT else f"cell {cell_dict['cid']}"
            row, col = list(SESSION.grid_to_ID[page_mode].keys())[list(SESSION.grid_to_ID[page_mode].values()).index(cname)].split(",")
            col, row = (int(row),int(col))
            col_start = (col-1)*(im_size)+1
            row_start = (row-1)*(im_size)+1
            blended_cell = blended_image[col_start : col_start + (im_size-2), row_start : row_start + (im_size-2), :]
            ab = "_light" if SESSION.absorption_mode else ''
            image_path = pathlib.Path(folder).joinpath(f'{cname_display}{ab}.png')
            _send_image_to_user(viewer, blended_cell, clipboard=False, image_name_override= image_path, silence_animation=True)

    elif page_mode == "Multichannel":
        for cell_dict in SESSION.page_cells.values():
            cname = f"{cell_dict['Layer']} {cell_dict['cid']}" if ANNOTATIONS_PRESENT else str(cell_dict['cid'])
            cname_display = f"{cell_dict['Layer']}- cell {cell_dict['cid']}" if ANNOTATIONS_PRESENT else f"cell {cell_dict['cid']}"
            row, col = list(SESSION.grid_to_ID[page_mode].keys())[list(SESSION.grid_to_ID[page_mode].values()).index(cname)].split(",")
            row, col = (int(row),int(col))
            col_start = ((row-1)*(im_size))
            blended_cell = blended_image[ col_start : col_start + im_size, :, :]
            ab = "_light" if SESSION.absorption_mode else ''
            image_path = pathlib.Path(folder).joinpath(f'{cname_display}_splitChannel{ab}.png')
            _send_image_to_user(viewer, blended_cell, clipboard=False, image_name_override= image_path, silence_animation=True)
    else:
        raise ValueError(f"Expected 'Gallery' or Multichannel', got {page_mode}")
    
    from napari._qt.utils import add_flash_animation
    # Here we are actually applying the effect to the `_welcome_widget` and not # the `native` widget because it does
    #  not work on the `native` widget. It's probably because the widget is in a stack with the `QtWelcomeWidget`.
    add_flash_animation(viewer._window._qt_viewer._welcome_widget)
    return True

@catch_exceptions_to_log_file("runtime_plot-histogram")
def generate_intensity_hist(viewer :napari.Viewer, cell_id : str , layer_name : str | None, 
                            bins:int, include_all:bool, normalize:bool):
    
    cells = SESSION.page_cells
    try:
        if ANNOTATIONS_PRESENT:
            singlecell = cells[f"{layer_name} {cell_id}"]
        else:
            singlecell = cells[str(cell_id)]
    except (ValueError, TypeError, IndexError):
        # Cell doesn't exist
        if ANNOTATIONS_PRESENT:
            viewer.status = f"Unable to plot histogram for cell '{layer_name} {cell_id}'. This ID was not found in my table."
        else:
            viewer.status = f"Unable to plot histogram for cell '{cell_id}'. This ID was not found in my table."
        return False

    viewer.status = "Analyzing object data..."
    # Create array of channel indices in image data. Will use to fetch from the dask array
    positions = []
    for fluor in userInfo.channels: # loop through channels
        if fluor != 'Composite': positions.append(userInfo.channelOrder[fluor]) # channelOrder dict holds mappings of fluors to position in image data
    # Get data for reference cell
    xmin = singlecell['XMin'] ; xmax = singlecell['XMax'] 
    ymin = singlecell['YMin'] ; ymax = singlecell['YMax'] 
    cname = f"Cell {cell_id}" if not ANNOTATIONS_PRESENT else f"{layer_name} - cell {cell_id}"
    
    if RAW_PYRAMID is None:
        reference_pixels = SESSION.dask_array[positions,ymin:ymax, xmin:xmax].compute() # 0 is the largest pyramid layer         
   
    plt.close() # Close a plot if it was there already
    # Assemble kwargs conditionally to pass to plotting function
    new_legend = [mpatches.Patch(color=userInfo.channelColors[fluor], label=fluor) for fluor in userInfo.channels if fluor!='Composite']
    pal = [userInfo.channelColors[fluor] for fluor in userInfo.channels if fluor!='Composite']
    mult = "fill" if normalize else 'layer'
    fill = True if normalize else False
    e = 'bars' if normalize else 'step'
    l = 1 if normalize else 3
    b = 'auto' if bins<2 else bins
    kwargs = {'palette':pal,'multiple':mult,'fill':fill,'bins':b,'element':e,'linewidth':l }

    if include_all: # User wants to plot current cell against all. Fetch pixels
        
        # Get data for all cells
        collected = np.array([])
        count = 0
        for _, cell in cells.items():
            # Get data for single cell
            xmin = cell['XMin'] ; xmax = cell['XMax'] 
            ymin = cell['YMin'] ; ymax = cell['YMax']
            
            if RAW_PYRAMID is None:
                cell_punchout = SESSION.dask_array[positions,ymin:ymax, xmin:xmax].compute() # 0 is the largest pyramid layer         
            cflat = [cell_punchout[x,:,:].flatten() for x in tuple(range(len(userInfo.channels)))]
            collected = np.concatenate((collected,cflat),axis=1) if count !=0 else cflat
            count +=1
        
        # Now plot
        viewer.status = "Done - displaying plot in live viewer"
        fig, axs = plt.subplots(nrows=2, sharey=True, )
        fig.suptitle(SESSION.image_display_name, fontsize='20')
        histplot([reference_pixels[x,:,:].flatten() for x in tuple(range(len(userInfo.channels)))], ax=axs[0], legend=False, **kwargs)
        
        if not normalize: 
            axs[0].set_yscale('log')
        else:
            ticks = ticker.FuncFormatter(lambda y, pos: '{0:g}'.format(y*100))
            axs[0].yaxis.set_major_formatter(ticks)
            axs[0].set_ylabel("Percentage of counts in bin")
        axs[0].set_title(f"{cname} pixel intensities")

        histplot(list(collected), ax=axs[1], legend=False, **kwargs)
        axs[1].set_title(f"Page {SESSION.page} cells combined pixel intensities")
        axs[1].set_xlabel("Pixel intensity")
        if normalize: axs[1].set_ylabel("Percentage of counts in bin")
        
        fig.legend(handles=new_legend, fontsize = '14')
    else: # Only plot cell histogram by itself
        viewer.status = "Done - displaying histogram in live viewer"
        p = histplot([reference_pixels[x,:,:].flatten() for x in tuple(range(len(userInfo.channels)))], **kwargs)
        # plt.gcf().get_axes()[0].set_yscale('log')
        if not normalize: 
            p.set_yscale('log')
        else:
            # Rescale to represent a percentage (0-100) instead of a ratio (0-1)
            ticks = ticker.FuncFormatter(lambda y, _: '{0:g}'.format(y*100))
            p.yaxis.set_major_formatter(ticks)
            p.set_ylabel("Percentage of counts in bin")
        p.set_title(f"{SESSION.image_display_name} | {cname} pixel intensities", fontsize='20')
        p.set_xlabel("Pixel intensity")
        plt.legend(handles=new_legend, fontsize='14')
    plt.show()

@catch_exceptions_to_log_file("runtime_plot-violins")
def generate_intensity_violins(viewer:napari.Viewer, cell_id : str|None, layer_name : str|None, refdataset:str="Full dataset",
                               col_choice:str='Cell', pheno_choice:str='All custom'):
    
    match refdataset:
        case "Full dataset":
            df = userInfo.objectDataFrame
        case "All pages in session":
            df = SESSION.session_cells

            print(df.columns)
            print(userInfo.objectDataFrame.columns)
            print('------------------------')
            # exit()
        case "This page only":
            df = SESSION.session_cells
            df = df[df["Page"] == SESSION.page]

    # If the user has passed a value here, they want to show the position of a reference cell
    cell_id = None if cell_id == '' else cell_id # Let's consider passing a blank as wanting to NOT plot a reference cell, so let's continue
    if cell_id is not None:
        try:
            if ANNOTATIONS_PRESENT:
                singlecell_df = df[(df['Object Id']==int(cell_id)) & (df['Analysis Region']==str(layer_name))]
            else:
                singlecell_df = df[df['Object Id']==int(cell_id)]
        except (ValueError, TypeError, IndexError):
            # Cell doesn't exist
            if ANNOTATIONS_PRESENT:
                viewer.status = f"Unable to plot reference cell '{layer_name} {cell_id}'. This ID was not found in my table."
            else:
                viewer.status = f"Unable to plot reference cell '{cell_id}'. This ID was not found in my table."
            return False
    viewer.status = 'Analyzing object data...'
    
    match col_choice: #'Cell' 'Nucleus' 'Cytoplasm' 'All'

        case 'All':      
            selection = SESSION.intensity_columns
        case 'Cell':
            selection = [x for x in SESSION.intensity_columns if 'Cell Intensity' in x]
        case 'Nucleus':
            selection = [x for x in SESSION.intensity_columns if 'Nucleus Intensity' in x]
        case 'Cytoplasm':
            selection = [x for x in SESSION.intensity_columns if 'Cytoplasm Intensity' in x]
        case _:
            viewer.status = 'Issue.'
            return None

    pal = selection.copy()
    for chn in userInfo.channels:
        pal = [userInfo.channelColors[chn] if chn in x else x for x in pal]

    print(f'Palette is {list(zip(selection,pal))}')
    print(f"Phenotypes are {userInfo.phenotypes}")
    match pheno_choice:
        case "All custom":
            pheno_selection = [x for x in userInfo.phenotypes if (not x.startswith("Validation |")) and x in list(df.columns)]
        case "All validation":
            pheno_selection = [x for x in userInfo.phenotypes if x.startswith("Validation |") and x in list(df.columns)]
        case _:
            pheno_selection = [pheno_choice]
    df.to_csv('mdf.csv',index=False)
    print(selection)
    print(pheno_selection)
    mdf = df.melt(id_vars=['Object Id', *pheno_selection ], value_vars=selection).rename(columns={'variable':'Intensity Type','value':'Intensity Value'})
    mdf = mdf.melt(id_vars = ['Object Id','Intensity Type','Intensity Value'], 
                  value_vars= pheno_selection).rename(columns={'variable':'Phenotype'})
    # Only keep cells positive for the chosen phenotypes. Cells with multiple phenotypes are split into different rows here (this is fine)
    mdf = mdf.loc[mdf['value'] ==1].drop(columns=['value'])
    print("\nmelted data here\n")
    print(mdf)
    # kwargs = {'palette':pal,'multiple':mult,'fill':fill,'bins':b,'element':e,'linewidth':l }
    viewer.status = "Done - displaying violinplot in live viewer"

    if pheno_choice not in ("All custom", "All validation"):
    # Just one phenotype, no need to facet
        p = violinplot(mdf, x='Intensity Type',y='Intensity Value',hue='Intensity Type', palette=pal,cut=0.1)
        
        p.set_title(f"{SESSION.image_display_name} fluorescent intensity distribution with reference to cell {cell_id}",fontsize='20')
        
        ax = plt.gca()
        labs = ax.get_xticklabels()
        ax.set_xticks(ax.get_xticks(),labs, rotation=45, ha='right')
        current_title = ax.title._text
        sc_phen = current_title.replace('Phenotype = ','')
        c = 'black' if sc_phen.replace("Validation | ",'') not in userInfo.statuses_hex.keys() else userInfo.statuses_hex[sc_phen.replace("Validation | ",'')]
        
        # Only do the following if the user wants to plot the position of a single reference cell on a violin
        if cell_id is not None:
            for tick, lab in enumerate(labs):
                y = singlecell_df.iloc[0][lab._text]
                ax.add_line(lines.Line2D([tick-.46, tick+.46], [y, y],lw=2, color='white'))
                ax.add_line(lines.Line2D([tick-.46, tick+.46], [y, y],lw=2, color='black', ls= (0,(5,5)) ))
                # ax.axhline(y=y,xmin=tick-(1/len(pal)),xmax=tick+(1/len(pal)), linewidth=2, color='white')
                # ax.axhline(y=y,xmin=tick-(1/len(pal)),xmax=tick+(1/len(pal)), linewidth=2, color='black', ls=":")
                
            # for tick, lab in enumerate(labs):
            #     y = singlecell_df.iloc[0][lab._text]
                # ax.text(tick-0.45, y-2, f">", fontsize=18,horizontalalignment='center',verticalalignment='center')
                ax.text(tick+0.4, y+1, f"{round(y,1)}", fontsize=12,horizontalalignment='left')
                                #bbox=dict(facecolor='white', alpha=0.8, edgecolor=None, boxstyle='round,pad=0.08'))

    else: 
        # Need to facet on multiple phenotypes
        g = FacetGrid(mdf, col ='Phenotype', col_wrap=3)
        g.map_dataframe(violinplot, x='Intensity Type',y='Intensity Value',hue='Intensity Type',palette=pal, cut=0.1)
        g.figure.suptitle(f"{SESSION.image_display_name} fluorescent intensity distribution with reference to cell {cell_id}",fontsize='20')

        for ax in g.axes:
            # For each subplot, want to adjust title color / add n, and optionally plot a reference line
            labs = g.axes[-1].get_xticklabels() # Get labels and rotate for visibility
            ax.set_xticks(ax.get_xticks(),labs, rotation=45, ha='right')
            # Redo title to include n and color with validation call color if plotting a validation phenotype
            current_title = ax.title._text
            sc_phen = current_title.replace('Phenotype = ','')
            c = 'black' if sc_phen.replace("Validation | ",'') not in userInfo.statuses_hex.keys() else userInfo.statuses_hex[sc_phen.replace("Validation | ",'')]
            n = mdf.Phenotype.value_counts()[sc_phen] // len(labs)
            new_title = current_title+f'\nn = {n}'
            ax.set_title(new_title, color=c)

            # Only do the following if the user wants to plot the position of a single reference cell on a violin
            if cell_id is not None:
                cname = f'{singlecell_df.iloc[0]["Analysis Region"]} {singlecell_df.iloc[0]["Object Id"]}' if ANNOTATIONS_PRESENT else str(singlecell_df.iloc[0]["Object Id"])
                if cname in SESSION.current_cells.keys():
                    print(SESSION.current_cells[cname])
                    print(sc_phen)
                    try:
                        if pheno_choice == 'All validation':
                            val = SESSION.current_cells[cname]['validation_call']
                            facet = sc_phen.replace("Validation | ",'')
                            on_phenotype_facet = True if val == facet else False
                        elif pheno_choice =='All custom':
                            on_phenotype_facet = bool(singlecell_df.iloc[0][sc_phen])
                        else: #Unreachable case? Should'nt be faceting if user chose single column
                            raise Exception("Executing faceted violinplot code even though user requested a single column")
                    except KeyError: # Probably triggered
                        on_phenotype_facet = False
                    print(f"on_phenotype_facet = {on_phenotype_facet}")
                else:
                    on_phenotype_facet = bool(singlecell_df.iloc[0][sc_phen])
                    print(f"Not in current cells. on_phenotype_facet = {on_phenotype_facet}")
                for tick, lab in enumerate(labs):
                    y = singlecell_df.iloc[0][lab._text]

                    ax.add_line(lines.Line2D([tick-.46, tick+.46], [y, y],lw=2, color='white'))
                    ax.add_line(lines.Line2D([tick-.46, tick+.46], [y, y],lw=2, color='black', ls= (0,(5,5)) ))
                    ax.text(tick+0.4, y+1, f"{round(y,1)}", fontsize=12,horizontalalignment='left')
                    # Add a visual indicator of the reference cell's expression for a given marker
                    # if not on_phenotype_facet:
                    #     ax.text(tick+0.15, y, f"<", fontsize=12,horizontalalignment='center',verticalalignment='center',
                    #             bbox=dict(facecolor='white', alpha=0.8, edgecolor=None, boxstyle='round,pad=0.08'))
                    # else:
                    #     ax.text(tick+0.15, y, f"<",color='white',fontsize=16,horizontalalignment='center',verticalalignment='center',
                    #             bbox=dict(facecolor=c , alpha=1, edgecolor=None, boxstyle='round,pad=0.08'))
    plt.tight_layout()
    plt.show()


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
            fluor_button_toggled() 
            viewer.window._qt_viewer.setFocus()
        return toggle_channel_visibility

    for pos, chn in enumerate(UPDATED_CHECKBOXES):
        binding_func_name = f'{chn}_box_func'
        exec(f'globals()["{binding_func_name}"] = create_fun({pos},"{chn}")')
        

def set_initial_adjustment_parameters(viewsettings):
    for key in list(viewsettings.keys()):
        # print(f'\n key is {key}')
        SESSION.view_settings[key] = viewsettings[key]
    return True

def record_notes_and_intensities(cell_row, intensity_col_names):
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
    # SESSION.session_cells[ID]["intensities"] = cell_row

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
    possible_fluors = userInfo.possible_fluors_in_data
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

    #TODO Need to generalize this better. Should do the work to place candidate values in the dropdown menu in the user GUI
    #   Then, user can pick and we don't have to consider anything else here since we know that the sort column passed is valid and the user
    #   wants it.
    global GLOBAL_SORT
    global_sort_status = True
    if GLOBAL_SORT is not None:
        try:
            # Doing this temporarily to handle cases where there is a custom fluor name passed. Fluor needs to still contain the 'Opal'
            #   Label somewhere in the name.
            GLOBAL_SORT = [x for x in all_possible_intensities if all(y in x for y in GLOBAL_SORT.replace("Cell Intensity",""))]
            GLOBAL_SORT = [x for x in GLOBAL_SORT if "Cell Intensity" in x][0]
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


    # Assign page numbers to each cell in the table now. These cells can appear in the viewer during this session
    phen_only_df["Page"] = (phen_only_df.index // page_size)+1

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
            page_number = singlecell_df.iloc[0]["Page"] # Converts single row dataframe to series and fetches the page value

            print("I will now print the 'page number' which should be a number, not a series")
            print(page_number)
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
        cell_set = SESSION.session_cells[(page_number-1)*page_size: page_number*page_size]
    else:
        cell_set = SESSION.session_cells[(page_number-1)*page_size:]

    
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
    cell_information = {}

    # Iterate over rows to create dictionary entries for each cell.
    #TODO just keep the information in a pandas DataFrame. It will be faster and easier to work with than doing this.
    for index,row in cell_set.iterrows():
        cid = row["Object Id"]
        layer = row["Analysis Region"] if ANNOTATIONS_PRESENT else None
        ckey = f'{layer} {cid}' if ANNOTATIONS_PRESENT else str(cid)
        record_notes_and_intensities(row, all_possible_intensities)
        center_x = row['center_x']
        center_y = row['center_y']
        vals = row[validation_cols]
        try:
            validation_call = str(vals[vals == 1].index.values[0]).replace(f"Validation | ", "")
        except IndexError:
            # row has no validation call (all zeroes). Assign to Unseen
            validation_call = "Unseen"

        cell_information[ckey] = {'Layer':layer,"cid": cid,"center_x": center_x,'center_y': center_y,
                                'validation_call': validation_call, 'XMax' : row['XMax'],'XMin':row['XMin'],
                                'YMax' : row['YMax'],'YMin':row['YMin'], 'Page':row["Page"]}

    SESSION.current_cells = copy.copy(cell_information)
    SESSION.page_cells = copy.copy(cell_information)
    SESSION.cell_under_mouse = next(iter(cell_information.values())) # Set first cell in list as "current" to avoid exceptions
    return cell_information

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
    global ANNOTATIONS_PRESENT, SESSION
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
    
    # if "Composite" not in list(userInfo.channelColors.keys()): userInfo.channelColors['Composite'] = 'None'
    

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
            preprocess_class._append_status('<font color="#7dbc39">  Done. </font>')
            preprocess_class._append_status_br('Sorting object data...')
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
    RAW_PYRAMID=pyramid 


    # Get rid of problematic bindings before starting napari viewer
    # See file at napari\utils\shortcuts.py
    settings=get_settings()
    for binding in ["napari:hold_for_pan_zoom","napari:activate_image_pan_zoom_mode", "napari:activate_image_transform_mode",
                    "napari:toggle_grid", "napari:transpose_axes","napari:roll_axes", "napari:reset_view",
                    "napari:toggle_selected_visibility"]:
        try:
            settings.shortcuts.shortcuts.pop(binding)
            # print(settings.shortcuts.shortcuts.pop(binding))
        except KeyError as e:
            print(f"Can't find this binding: {e}")
            pass
    
    viewer = napari.Viewer(title=f'GalleryViewer v{VERSION_NUMBER} {SESSION.image_display_name}')
    VIEWER = viewer
    # Get rid of the crap on the left sidebar for a cleaner screen
    viewer.window._qt_viewer.dockLayerList.toggleViewAction().trigger()
    viewer.window._qt_viewer.dockLayerControls.toggleViewAction().trigger()


    # this will remove minimized status 
    # and restore window with keeping maximized/normal state
    preprocess_class.setWindowState(preprocess_class.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
    # this will activate the window
    preprocess_class.activateWindow()


    cell_description_label = QLabel(); cell_description_label.setAlignment(Qt.AlignCenter)
    cell_description_label.setFont(userInfo.fonts.small)
    cell_description_group = QGroupBox("Cell Attributes")
    cell_description_group.setStyleSheet(open("data/docked_group_box_border_light.css").read())
    cell_description_layout = QVBoxLayout(cell_description_group)
    cell_description_layout.addWidget(cell_description_label)
    SESSION.widget_dictionary["cell description label"] = cell_description_label

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

    # Label to show user how many cells have been assigned to each scoring decision bucket
    scoring_label = QLabel()
    scoring_label.setAlignment(Qt.AlignCenter)
    scoring_label.setFont(QFont("Verdana", 5, weight=QFont.Normal))

    scoring_group = QGroupBox("Scoring Information")
    scoring_group.setStyleSheet(open("data/docked_group_box_border_light.css").read())
    scoring_layout = QVBoxLayout(scoring_group)
    scoring_layout.addWidget(scoring_label)
    SESSION.widget_dictionary['scoring label'] = scoring_label

    # Change page widgets
    page_combobox = QComboBox()
    page_combobox.setStyleSheet("combobox-popup: 0;")
    page_combobox.setMaxVisibleItems(10)
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
    show_hide_group = QGroupBox("Scoring Tools")
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
    
    # Context mode marker tool group
    marker_layout = QHBoxLayout()
    # Create a combobox
    marker_combo = StatusCombo(show_hide_group ,userInfo, color_mode = 'dark')
    marker_combo.setVisible(False) # Will be shown when context mode is enabled
    marker_combo.setDisabled(True)
    SESSION.widget_dictionary["marker combo"] = marker_combo
    # Create a button
    marker_button = QPushButton("Enable marker tool")
    marker_button.setVisible(False)
    marker_button.released.connect(lambda: toggle_marker_button(marker_button))
    SESSION.widget_dictionary["marker button"] = marker_button
    # Add to layouts
    marker_layout.addWidget(marker_combo)
    marker_layout.addWidget(marker_button)
    show_hide_layout.addLayout(marker_layout)





    # nuc_boxes_show.tog
    nuc_boxes_group.buttonToggled[QAbstractButton, bool].connect(toggle_nuclei_boxes)
    SESSION.widget_dictionary['show boxes']=nuc_boxes_show
    SESSION.widget_dictionary['hide boxes']=nuc_boxes_hide
    SESSION.widget_dictionary['mouse boxes']=nuc_boxes_context
    show_hide_layout.addLayout(nuc_boxes_layout)

    

    # Create main group in a vertical stack, and add to side box
    # mode_group.setSizePolicy(QSizePolicy.MinimumExpanding,QSizePolicy.MinimumExpanding)

    side_dock_group = QGroupBox()
    side_dock_group.setStyleSheet(open("data/docked_group_box_noborder.css").read())
    side_dock_layout = QVBoxLayout(side_dock_group)
    side_dock_layout.addWidget(cell_description_group)
    side_dock_layout.addWidget(scoring_group)
    side_dock_layout.addWidget(notes_all_group)
    side_dock_layout.addWidget(page_group)
    side_dock_layout.addWidget(mode_group)
    side_dock_layout.addWidget(show_hide_group)
    # side_dock_group.setSizePolicy(QSizePolicy.MinimumExpanding,QSizePolicy.MinimumExpanding)


    # Start adding widgets for the next page. Will be accessible with a new tab
    im_save_cell_group = QGroupBox("Save a cell image")
    im_save_cell_group.setStyleSheet(open("data/docked_group_box_border_light.css").read())
    im_save_cell_layout = QVBoxLayout(im_save_cell_group)
    
    # LineEdit
    image_save_target_entry = QLineEdit()
    image_save_target_entry.setPlaceholderText("ID to save")
    SESSION.widget_dictionary["image_save_target_entry"] = image_save_target_entry
    
    # Layout 
    imsave_entry_layout = QHBoxLayout()
    imsave_entry_layout.addWidget(image_save_target_entry)
    # Annotation widget:
    if ANNOTATIONS_PRESENT:
        imsave_annotations = QComboBox() ; imsave_annotations.addItems(ANNOTATIONS_PRESENT)
        SESSION.widget_dictionary["image_save_target_annotation"] = imsave_annotations
        imsave_entry_layout.addWidget(imsave_annotations)

    imsave_cell_borders = QComboBox() ; imsave_cell_borders.addItems(["White borders","Black borders","No borders"])
    SESSION.widget_dictionary['imsave_cell_borders'] = imsave_cell_borders
    imsave_entry_layout.addWidget(imsave_cell_borders)
    im_save_cell_layout.addLayout(imsave_entry_layout) # Add H layout to main V layout
    
    # Buttons
    im_save_cell_buttons_layout = QHBoxLayout()
    # Save to clipboard
    imsave_cell_button_clipboard = QPushButton("Save image to clipboard")
    imsave_cell_button_clipboard.released.connect(lambda: save_cell_image(viewer, 
                image_save_target_entry.text(), imsave_annotations.currentText() if ANNOTATIONS_PRESENT else None,
                clipboard=True, borders=imsave_cell_borders.currentText()))
    # Save to file
    imsave_cell_button_file = QPushButton("Save image to file")

    imsave_cell_button_file.released.connect(lambda: save_cell_image(viewer, 
                image_save_target_entry.text(), imsave_annotations.currentText() if ANNOTATIONS_PRESENT else None,
                clipboard=False, borders=imsave_cell_borders.currentText()))
    im_save_cell_buttons_layout.addWidget(imsave_cell_button_clipboard)
    im_save_cell_buttons_layout.addWidget(imsave_cell_button_file)
    im_save_cell_layout.addLayout(im_save_cell_buttons_layout)

    # Group for saving image of all cells in the page
    im_save_page_group = QGroupBox("Save a page image")
    im_save_page_group.setStyleSheet(open("data/docked_group_box_border_light.css").read())
    im_save_page_layout = QVBoxLayout(im_save_page_group)

    # options Layout 
    im_save_page_options_layout = QHBoxLayout()
    # Annotation combo (for mode)
    im_save_mode_select = QComboBox()
    im_save_mode_select.addItems(["Gallery", "Multichannel"])
    SESSION.widget_dictionary["im_save_mode_select"] = im_save_mode_select
    im_save_page_options_layout.addWidget(im_save_mode_select)

    # Separate file combo option
    im_save_separate_files = QComboBox()
    im_save_separate_files.addItems(["Save full page image", "Save each cell separately"])
    SESSION.widget_dictionary["im_save_separate_files"] = im_save_separate_files
    im_save_page_options_layout.addWidget(im_save_separate_files)

    imsave_page_borders = QComboBox() ; imsave_page_borders.addItems(["White borders","Black borders"])
    SESSION.widget_dictionary['imsave_page_borders'] = imsave_page_borders
    im_save_page_options_layout.addWidget(imsave_page_borders)
    
    im_save_page_layout.addLayout(im_save_page_options_layout) # add to v layout
    # Buttons layout
    im_save_page_buttons_layout = QHBoxLayout()
        # Save to clipboard button
    imsave_page_button_clipboard = QPushButton("Save image to clipboard")
    imsave_page_button_clipboard.released.connect(lambda: save_page_image(viewer, im_save_mode_select.currentText(), clipboard=True, borders = imsave_page_borders.currentText()))
    # Don't allow the user to use the clipboard button if 'Save each cell separately' is selected
    im_save_separate_files.currentTextChanged.connect(lambda: imsave_page_button_clipboard.setDisabled({0:False, 1:True}[im_save_separate_files.currentIndex()]))
    # Save to file
    imsave_page_button_file = QPushButton("Save image(s) to file")
    imsave_page_button_file.released.connect(lambda: save_page_image(viewer, im_save_mode_select.currentText(), borders = imsave_page_borders.currentText(),
                                                                     clipboard=False, separate=True if 'separately' in im_save_separate_files.currentText() else False))
    im_save_page_buttons_layout.addWidget(imsave_page_button_clipboard)
    im_save_page_buttons_layout.addWidget(imsave_page_button_file)
    im_save_page_layout.addLayout(im_save_page_buttons_layout)

    overflow_page_dock_group = QGroupBox()
    overflow_page_dock_group.setStyleSheet(open("data/docked_group_box_noborder.css").read())
    overflow_page_dock_layout = QVBoxLayout(overflow_page_dock_group)
    overflow_page_dock_layout.addWidget(im_save_cell_group)
    overflow_page_dock_layout.addWidget(im_save_page_group)


    ###--------- Widgets on 'Plotting' tab
    ## Seaborn histplot widgets for cell intensities
    hist_group = QGroupBox("Intensity Histogram")
    hist_group.setStyleSheet(open("data/docked_group_box_border_light.css").read())
    hist_layout = QVBoxLayout(hist_group)
    
    # LineEdit
    hist_target_entry = QLineEdit()
    hist_target_entry.setPlaceholderText("ID to plot")
    SESSION.widget_dictionary["hist_target_entry"] = hist_target_entry
    
    # Layout 
    hist_entry_layout = QHBoxLayout()
    hist_entry_layout.addWidget(hist_target_entry)
    # Annotation widget:
    if ANNOTATIONS_PRESENT:
        hist_annotations = QComboBox() ; hist_annotations.addItems(ANNOTATIONS_PRESENT)
        SESSION.widget_dictionary["hist_annotations"] = hist_annotations
        hist_entry_layout.addWidget(hist_annotations)

    hist_subplots = QComboBox()
    hist_subplots.addItems(["Plot against page cells","Plot this cell only"])
    hist_entry_layout.addWidget(hist_subplots)
    hist_layout.addLayout(hist_entry_layout)


    hist_second_row_layout = QHBoxLayout()
    hist_norm = QComboBox()
    hist_norm.addItems(["Normalize bins","Plot raw counts"])
    hist_second_row_layout.addWidget(hist_norm)
    hist_bins = QSpinBox()
    hist_bins.setRange(0,255) ; hist_bins.setValue(25)
    hist_bins_label = QLabel("Bins:")
    hist_bins_label.setAlignment(Qt.AlignRight)
    hist_second_row_layout.addWidget(hist_bins_label)
    hist_second_row_layout.addWidget(hist_bins)


    hist_layout.addLayout(hist_second_row_layout)
    

    hist_button = QPushButton("Generate histogram")
    hist_button.released.connect(lambda: generate_intensity_hist(viewer,
                    hist_target_entry.text(), hist_annotations.currentText() if ANNOTATIONS_PRESENT else None,
                    hist_bins.value(), 
                    {"Plot against page cells":True,"Plot this cell only":False}[hist_subplots.currentText()],
                    {"Normalize bins":True,"Plot raw counts":False}[hist_norm.currentText()]))
    hist_layout.addWidget(hist_button)


    # Seaborn Violinplot widgets 
    violin_group = QGroupBox("Intensity Violins")
    violin_group.setStyleSheet(open("data/docked_group_box_border_light.css").read())
    violin_layout = QVBoxLayout(violin_group)

    # Layout 
    violin_entry_layout = QHBoxLayout()

    # Ref cell toggle:
    violin_use_refcell = QPushButton("Plot a reference cell")
    violin_use_refcell.setFont(userInfo.fonts.button_small)
    violin_entry_layout.addWidget(violin_use_refcell)

    # LineEdit
    violin_target_entry = QLineEdit()
    violin_target_entry.setPlaceholderText("ID to plot")
    SESSION.widget_dictionary["violin_target_entry"] = violin_target_entry


    violin_entry_layout.addWidget(violin_target_entry)
    # Annotation widget:
    if ANNOTATIONS_PRESENT:
        violin_annotations = QComboBox() ; violin_annotations.addItems(ANNOTATIONS_PRESENT)
        SESSION.widget_dictionary["violin_annotations"] = violin_annotations
        violin_entry_layout.addWidget(violin_annotations)
    violin_layout.addLayout(violin_entry_layout)

    def _change_reference_settings(button, entry, annot):
        if button.text() == "Plot a reference cell":
            button.setText("No reference")
            entry.setDisabled(True)
            if annot is not None:
                annot.setDisabled(True)

        elif button.text() == "No reference":
            button.setText("Plot a reference cell")
            entry.setEnabled(True)
            if annot is not None:
                annot.setEnabled(True)

    violin_use_refcell.released.connect(lambda: _change_reference_settings(violin_use_refcell,violin_target_entry, None if not ANNOTATIONS_PRESENT else violin_annotations))

    
    violin_second_row_layout = QHBoxLayout()
    vlabel = QLabel("Reference data")
    vlabel.setAlignment(Qt.AlignRight)
    violin_second_row_layout.addWidget(vlabel)
    violin_referencedata = QComboBox()
    violin_referencedata.addItems(["Full dataset","All pages in session","This page only"])
    violin_second_row_layout.addWidget(violin_referencedata)
    violin_layout.addLayout(violin_second_row_layout)


    violin_third_row_layout = QHBoxLayout()
    violin_phenotype = QComboBox()
    violin_phenotype.addItems(["All custom", "All validation", *userInfo.phenotypes])
    vlabel = QLabel("Phenotype(s)")
    vlabel.setAlignment(Qt.AlignRight)
    violin_third_row_layout.addWidget(vlabel)
    violin_third_row_layout.addWidget(violin_phenotype)
    violin_intensity = QComboBox()
    violin_intensity.addItems(["Cell","Nucleus","Cytoplasm","All"])
    vlabel = QLabel("Intensities")
    vlabel.setAlignment(Qt.AlignRight)
    violin_third_row_layout.addWidget(vlabel)
    violin_third_row_layout.addWidget(violin_intensity)
    violin_layout.addLayout(violin_third_row_layout)



    violin_button = QPushButton("Generate violins")
    violin_button.released.connect(lambda: generate_intensity_violins(viewer,
                                violin_target_entry.text() if violin_target_entry.isEnabled() else None, 
                                violin_annotations.currentText() if ANNOTATIONS_PRESENT and violin_annotations.isEnabled() else None,
                                violin_referencedata.currentText(),
                                violin_intensity.currentText(), violin_phenotype.currentText() ))
    violin_layout.addWidget(violin_button)


    plots_dock_group = QGroupBox()
    plots_dock_group.setStyleSheet(open("data/docked_group_box_noborder.css").read())
    plots_dock_layout = QVBoxLayout(plots_dock_group)
    plots_dock_layout.addWidget(hist_group)
    plots_dock_layout.addWidget(violin_group)



    # Open viewsettings popout
    open_vs = QPushButton("Modify view settings")
    open_vs.pressed.connect(open_vs_popup)
    open_vs.setFont(QFont("Calibri", 6, weight=QFont.Normal))
    SESSION.widget_dictionary["open_vs_button"] = open_vs


    absorption_widget = QPushButton("Absorption off")
    absorption_widget.pressed.connect(toggle_absorption)
    SESSION.widget_dictionary["absorption_widget"] = absorption_widget


    # Create bottom bar widgets
    for box in check_creator2(userInfo.active_channels):
        UPDATED_CHECKBOXES.append(box)
    viewer.window.add_dock_widget(UPDATED_CHECKBOXES + [absorption_widget, open_vs],area='bottom')
    # right_dock.adjustSize()

    # print(f'\n {dir()}') # prints out the namespace variables 
    SESSION.side_dock_groupboxes = {"notes":notes_all_group, "page":page_group, "mode":mode_group, "hide": show_hide_group, 
                                    "scoring":scoring_group, "cell description":cell_description_group, 
                                    "image cell group":im_save_cell_group, "image page group":im_save_page_group,
                                    "histogram":hist_group,"violin":violin_group}
    SESSION.radiogroups = {"Status layer group": status_layer_group, "Cell boxes group": nuc_boxes_group}
    
    
    
    # Now process object data and fetch images
    try:
        cell_information = extract_phenotype_xldata(specific_cell=SPECIFIC_CELL, sort_by_intensity=local_sort)
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
    preprocess_class._append_status(' Adding gallery images to viewer...')
    set_initial_adjustment_parameters(preprocess_class.userInfo.view_settings) # set defaults: 0.5 gamma, 0 black in, 255 white in
    attach_functions_to_viewer(viewer)


    # record initial counts for each scoring label
    set_initial_scoring_tally(userInfo.objectDataFrame, SESSION.session_cells, page_only=False)
    set_scoring_label(SESSION.widget_dictionary["scoring label"])

    # try:
    add_layers(viewer,pyramid,cell_information, int(userInfo.imageSize/2))
    # except IndexError as e:
    #     preprocess_class._append_status('<font color="#f5551a">  Failed.<br>A requested image channel does not exist in the data!</font>')
    #     # preprocess_class.findDataButton.setEnabled(True)
    #     viewer.close()
    #     return False
   
    #Enable scale bar
    if SESSION.image_scale:
        viewer.scale_bar.visible = True
        viewer.scale_bar.unit = "um"

    # Filter checkboxes down to relevant ones only and update color
    # print("My active channels are\n")
    # print(userInfo.active_channels)
    # all_boxes = check_creator2(userInfo.active_channels)
    

    #TODO set custom theme?
    VIEWER.theme = "dark"

    # Lazy load full size images as dask array
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
                        interpolation = "linear", scale=sc, multiscale=True, visible = True) 
            # Adding these images with visible = True allows viewsettings changes to be applied to them when the user loads into gallery mode at first.
            # Otherwise, it seems that they only display the changes after they have been visible for some small period of time in the viewer. 
        
    # Finish up, and set keybindings
    preprocess_class._append_status('<font color="#7dbc39">  Done.</font><br> Goodbye')
    chn_key_wrapper(viewer)
    if preprocess_class is not None: preprocess_class.close() # close other window
    # Set adjustment settings to their default now that all images are loaded
    restore_viewsettings_from_cache(False, viewer, userInfo.session)
    viewer.layers.selection.active = viewer.layers[f"Gallery {userInfo.channels[0]}"]  


    # Make sure user can scroll through tools if there are too many
    scroll_area = QScrollArea()
    scroll_area.setWidgetResizable(True)
    # scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    side_dock_group.setSizePolicy(QSizePolicy.MinimumExpanding,QSizePolicy.MinimumExpanding)
    scroll_area.setSizePolicy(QSizePolicy.MinimumExpanding,QSizePolicy.MinimumExpanding)
    scroll_area.setWidget(side_dock_group)
    side_dock_group.setAlignment(Qt.AlignHCenter)
    scroll_area.resize(side_dock_group.sizeHint())
    right_dock = viewer.window.add_dock_widget(scroll_area, name ="User tools",area="right", tabify = True)
    viewer.window.add_dock_widget(overflow_page_dock_group, name ="Export data",area="right", tabify = True)
    viewer.window.add_dock_widget(plots_dock_group, name ="Plotting",area="right", tabify = True)

    right_dock.show()
    right_dock.raise_() # Make the user tools dock come up first

    # right_dock.resize(side_dock_group.sizeHint())
    # print(side_dock_group.sizeHint())
    # print(scroll_area.sizeHint())
    # print(right_dock.sizeHint())
    
    set_viewer_to_neutral_zoom(viewer, reset_session=True) # Fix zoomed out issue
    napari.run() # Start the event loop

# Main Probably doesn't work as is right now. Will need to instantiate a new user class to run everything
if __name__ == '__main__':
    main()