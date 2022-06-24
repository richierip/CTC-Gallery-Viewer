'''
CTC viewer for Napari
Started on 6/7/22
Peter Richieri
'''

import tifffile
import napari
from napari.types import ImageData
from magicgui import magicgui
import numpy as np
import pandas as pd
import skimage.filters
import gc # might garbage collect later
import math

#-------------------- Globals, will be loaded through pre-processing QT gui #TODO -------------#
QPTIFF_LAYER_TO_RIP = 0 # 0 is high quality. Can use 1 for testing (BF only, loads faster)
cell_colors = ['bop orange', 'bop purple' , 'green', 'blue', 'yellow','cyan', 'red', 'twilight']
qptiff = r"C:\Users\prich\Desktop\Projects\MGH\CTC_Example\Exp02a01_02_Scan1.qptiff"
OBJECT_DATA = r"C:\Users\prich\Desktop\Projects\MGH\CTC_Example\ctc_example_data.csv"
OFFSET = 100 # microns or pixels?
# CELL_START = 100
CELL_LIMIT = 15
PHENOTYPE = 'Tumor'
DAPI = 0; OPAL480 = 1; OPAL520 = 2; OPAL570 = 3; OPAL620 = 4; OPAL690 = 5; OPAL780 = 6; AF=7
# DAPI = None; OPAL480 = None; OPAL520 = None; OPAL570 = None; OPAL620 = None; OPAL690 = None; OPAL780 = None; AF=None
CHANNELS_STR = ["DAPI", "OPAL480", "OPAL520", "OPAL570", "OPAL620", "OPAL690", "OPAL780", "AF"]
# CHANNELS_STR = ["DAPI", "OPAL520", "OPAL690", "AF"]
CHANNELS = [DAPI, OPAL480, OPAL520, OPAL570, OPAL620, OPAL690, OPAL780, AF]
# CHANNELS = [DAPI, OPAL520,OPAL690, AF]
ADJUSTED = CHANNELS
CHANNEL_ORDER = None # to save variable position data for channels (they can be in any order...)
VIEWER = None

# Probably won't be used - both image and object data use same units in my example
def map_coords(array_shape, cellx,celly):
    array_x_length = array_shape[0]
    array_y_length = array_shape[1]


#------------------------- MagicGUI Widgets, Functions, and accessories ---------------------#

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

def adjust_gamma(viewer, gamma):
    for ctclayer in viewer.layers:
        if validate_adjustment(ctclayer):
            ctclayer.gamma = gamma


@magicgui(auto_call=True,
        gamma={"widget_type": "FloatSlider", "max":1.0},
        layout = 'horizontal')
def adjust_gamma_widget(gamma: float = 0.5) -> ImageData:
    adjust_gamma(VIEWER,gamma)

@magicgui(auto_call=True,
        white_in={"widget_type": "FloatSlider", "max":255, "label": "White-in"},
        layout = 'horizontal')
def adjust_whitein(white_in: float = 255) -> ImageData:
    for ctclayer in VIEWER.layers:
        if validate_adjustment(ctclayer):
            ctclayer.contrast_limits = (ctclayer.contrast_limits[0], white_in)

@magicgui(auto_call=True,
        black_in={"widget_type": "FloatSlider", "max":255, "label":"Black-in"},
        layout = 'horizontal')
def adjust_blackin(black_in: float = 0) -> ImageData:
    for ctclayer in VIEWER.layers:
        if validate_adjustment(ctclayer):
            print(ctclayer.contrast_limits)
            ctclayer.contrast_limits = (black_in, ctclayer.contrast_limits[1])

# Called in a loop to create as many GUI elements as needed
def dynamic_checkbox_creator(checkbox_name):
    @magicgui(auto_call=True,
            check={"widget_type": "CheckBox", "text": checkbox_name},
            layout = 'horizontal')
    def myfunc(check: bool = True):
        print(f'In check function. ADJUSTED is {ADJUSTED}, checkbox name is {checkbox_name}')
        if check:
            ADJUSTED.append(globals()[checkbox_name])
        else:
            ADJUSTED.remove(globals()[checkbox_name])
    return myfunc

# Execution loop - need to call it here to get the names into the namespace
for checkbox_name in CHANNELS_STR:   
    exec(f'{checkbox_name+"_box"} = dynamic_checkbox_creator(checkbox_name)') # If doing this is wrong I don't want to be right
# print(f'dir is {dir()}')

#------------------------- Image loading and processing functions ---------------------#

#TODO consider combining numpy arrays before adding layers? So that we create ONE image, and have ONE layer
#   for the ctc cells. Gallery mode might end up being a pain for downstream.
#   Counterpoint - how to apply filters to only some channels if they are in same image?
#   Counterpoint to counterpoint - never get rid of numpy arrays and remake whole image as needed. 
def add_layers(viewer,pyramid, cells, offset):
    def add_layer(viewer, layer, name, colormap):
        # Napari bug: setting gamma here doesn't update what is seen, 
        # even thought the slider gui shows the change
        #   Will have to do something else.
        viewer.add_image(layer, name = name, colormap=colormap)
        return True
    # def add_layer_rgb(viewer, layer, name):
    #     viewer.add_image(layer, name = name, rgb=True)
    #     return True
    
    print(f'Adding {len(cells)} cells to viewer...')
    while bool(cells): # coords left
        cell = cells.pop(); cell_x = cell[0]; cell_y = cell[1]; cell_id = cell[2]

        # add the rest of the layers to the viewer
        for i in range(pyramid.shape[2]): # loop through channels
            if i in CHANNELS:
                # name cell layer
                if i==DAPI: fluor='DAPI'
                elif i==OPAL570: fluor='570'
                elif i==OPAL690: fluor='690' 
                elif i==OPAL480: fluor='480'
                elif i==OPAL620: fluor='620' 
                elif i==OPAL780: fluor='780'
                elif i==OPAL520: fluor='520'
                elif i==AF: fluor='AF' 
                cell_name = f'Cell {cell_id} {fluor}'
                # print(f'Adding cell {cell_x},{cell_y} - layer {i}')
                add_layer(viewer,pyramid[cell_x-offset:cell_x+offset,cell_y-offset:cell_y+offset,i], cell_name, cell_colors[i])
                # if len(cells) == 5 and i ==0 :
                #     np.savetxt(r"C:\Users\prich\Desktop\Projects\MGH\CTC_Example\np_array_for_dapi.txt", pyramid[cell_x-offset:cell_x+offset,cell_y-offset:cell_y+offset,i])
                #     # print(pyramid[cell_x-offset:cell_x+offset,cell_y-offset:cell_y+offset,i][0])
    return True

''' Reset globals and proceed to main '''
def GUI_execute(userInfo):
    global cell_colors; global qptiff; global OFFSET; global CELL_LIMIT; global CHANNELS_STR
    global CHANNELS; global ADJUSTED; global DAPI; global OPAL480; global OPAL520; global OPAL570
    global OPAL620; global OPAL690; global OPAL780; global AF; global OBJECT_DATA; global PHENOTYPE

    cell_colors = userInfo.cell_colors
    qptiff = userInfo.qptiff
    OFFSET = userInfo.offset
    PHENOTYPE = userInfo.phenotype
    CELL_LIMIT = userInfo.cell_count
    OBJECT_DATA = userInfo.objectData
    CHANNELS_STR = userInfo.channels
    CHANNEL_ORDER = userInfo.channelOrder
    CHANNELS = []
    for pos,chn in enumerate(CHANNEL_ORDER):
        if chn in CHANNELS_STR:
            exec(f'{chn} = {pos}')
            exec(f'CHANNELS.append({chn})')
    print(f'backend channels are : {CHANNELS}')
    ADJUSTED = CHANNELS
    main()

def GUI_execute_cheat(userInfo):
    main()

def main():
    with tifffile.Timer(f'\nLoading pyramid from {qptiff}...\n'):
        pyramid = tifffile.imread(qptiff)
        # can pick select pages
        # image = imread('temp.tif', key=0)
        # images = imread('temp.tif', key=range(4, 40, 2))
        print('... completed in ', end='')
    # print(f'\nFinal pyramid levels: {[p.shape for p in pyramid]}\n')

    # Find location of channels in np array. Save that value, and subset the rest (one nparray per channel)
    print(f'pyramid array as np array shape is {pyramid.shape}\n')
    arr = np.array(pyramid.shape)
    channels = min(arr)
    channel_index = np.where(arr == channels)[0][0]
    # print(f'least is {channels}, type is {type(channels)} and its at {channel_index}, test is {channel_index==0}')

    # have to grab the first to instantiate napari viewer
    if channel_index == 0:
        # Added this because the high quality layer of my sample QPTIFF data seemed to be flipped
        # i.e. array looks like (channels, y, x)
        # to be seen if this actually works
        pyramid = np.transpose(pyramid,(2,1,0))
        # print(f'FLIPPED SHAPE is {pyramid.shape}\n')
        firstLayer = pyramid[:,:,0]
    else:
        firstLayer = pyramid[:,:,0]
    print(f'Single layer shape is {firstLayer.shape}\n')

    # Get object data from csv and parse.
    halo_export = pd.read_csv(OBJECT_DATA)
    halo_export = halo_export.loc[:, ["Object Id", "XMin","XMax","YMin", "YMax", PHENOTYPE]]
    halo_export = halo_export[halo_export[PHENOTYPE]==1]
    halo_export = halo_export[:CELL_LIMIT] # pare down cell list to desired length
    tumor_cell_XYs = []
    for index,row in halo_export.iterrows():
        center_x = int((row['XMax']+row['XMin'])/2)
        center_y = int((row['YMax']+row['YMin'])/2)
        tumor_cell_XYs.append([center_x, center_y, row["Object Id"]])

    cell1 = [16690, 868]
    cell2 = [4050, 1081]

    sample_cell_dict = {}
    sample_cell_dict['cell_x'] = cell1[0] ; sample_cell_dict['cell_y'] = cell1[1]
    sample_cell_dict['slidewidth'] = pyramid.shape[0]
    sample_cell_dict['slidelength'] = pyramid.shape[1]
    
    viewer = napari.Viewer(title='CTC Gallery')
    add_layers(viewer,pyramid,tumor_cell_XYs, int(OFFSET/2))
    global VIEWER
    VIEWER = viewer
    viewer.grid.enabled = True
    viewer.grid.shape = (CELL_LIMIT, len(CHANNELS))
    viewer.window.add_dock_widget(adjust_gamma_widget, area = 'bottom')
    viewer.window.add_dock_widget(adjust_whitein, area = 'bottom')
    viewer.window.add_dock_widget(adjust_blackin, area = 'bottom')
    
    # print(f'\n {dir()}')
    # viewer.window.add_dock_widget(check_test, area = 'bottom')
    for marker_function in CHANNELS_STR:
        exec(f"viewer.window.add_dock_widget({marker_function+'_box'}, area='bottom')")
    #adjust_gamma(viewer,0.5)

    napari.run()



if __name__ == '__main__':
    main()



