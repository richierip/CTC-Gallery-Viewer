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
# import skimage.filters
# import gc # might garbage collect later
# import math
# import copy
# import vispy.color as vpc
import matplotlib
from matplotlib import cm
from matplotlib import pyplot as plt
# norm = plt.Normalize()
import copy

from zmq import CHANNEL

#-------------------- Globals, will be loaded through pre-processing QT gui #TODO -------------#
QPTIFF_LAYER_TO_RIP = 0 # 0 is high quality. Can use 1 for testing (BF only, loads faster)
cell_colors = ['Greys', 'Purples' , 'Blues', 'Greens', 'Oranges','Reds', 'copper', 'twilight']
qptiff = r"C:\Users\prich\Desktop\Projects\MGH\CTC_Example\Exp02a01_02_Scan1.qptiff"
OBJECT_DATA = r"C:\Users\prich\Desktop\Projects\MGH\CTC_Example\ctc_example_data.csv"
OFFSET = 200 # microns or pixels? Probably pixels
# CELL_START = 100
CELL_LIMIT = 15
PHENOTYPE = 'Tumor'
CELL_ID_START = 1
DAPI = 0; OPAL480 = 1; OPAL520 = 2; OPAL570 = 3; OPAL620 = 4; OPAL690 = 5; OPAL780 = 6; AF=7; Composite = 8
CHANNELS_STR = ["DAPI", "OPAL480", "OPAL520", "OPAL570", "OPAL620", "OPAL690", "OPAL780", "AF", "Composite"]
# CHANNELS_STR = ["DAPI", "OPAL520", "OPAL690", "AF"]
CHANNELS = [DAPI, OPAL480, OPAL520, OPAL570, OPAL620, OPAL690, OPAL780, AF, Composite] # Default. Not really that useful info since channel order was added.
# CHANNELS = [DAPI, OPAL520,OPAL690, AF]
ADJUSTED = copy.copy(CHANNELS)
CHANNEL_ORDER = None # to save variable position data for channels (they can be in any order...)
VIEWER = None
SC_DATA = None # Using this to store data to coerce the exec function into doing what I want
IMAGE_DATA_ORIGINAL = {}; IMAGE_DATA_ADJUSTED = {}
# CHANNEL_ORDER[CHANNELS.index(chn_pos)]
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
    elif layer_name == 'Composite' and Composite in ADJUSTED:
        return True
    else:
        return False

# @magicgui(auto_call=True,
#             datapoint={"label":"N/A"})
# def show_intensity(datapoint: str):
#     datapoint = str(VIEWER.Layers.Image.get_value() )
#     show_intensity.show()

def adjust_composite(layer, gamma):

    print(f'Checking keys of outer dict: {IMAGE_DATA_ORIGINAL.keys()}')
    print(f'My name is {layer.name}')
    # composite = copy.copy(IMAGE_DATA_STORE[layer.name])
    # print(f'Checking keys of inner dict: {color_dict.keys()}')
    # print(type(layer.colormap))
    # print(f'{layer.colormap} vs str() {str(layer.colormap)}')
    stripped_name = layer.name.rstrip('Composite')

    for chn in ADJUSTED:
        print(f'to be adjusted: {chn}')


    composite = []
    # get data from other CHECKED channels
    need_gamma_adjustment = copy.copy(ADJUSTED)
    need_gamma_adjustment.remove(8)
    fluors_only = copy.copy(CHANNELS)
    fluors_only.remove(8)
    print(f'\n dumping ADJUSTED needed: {ADJUSTED}\n and CHANNELS: {CHANNELS}\n and CHANNELS_STR {CHANNELS_STR}\n and CHANNEL_ORDER {CHANNEL_ORDER}\n and something?? {CHANNEL}')
    print(f'\n dumping adjustment needed: {need_gamma_adjustment}')
    for chn_pos in fluors_only:
        chn_str = CHANNEL_ORDER[chn_pos]
        chn_str = chn_str.lstrip('OPAL') # OPAL is not in the name of the data key
        # gamma adjust
        if chn_pos in need_gamma_adjustment:
            print(f'Will gamma adjust {chn_str}')
            chn_data = copy.copy(IMAGE_DATA_ORIGINAL[stripped_name+chn_str])
            chn_data = [ x**gamma for x in chn_data]
            IMAGE_DATA_ADJUSTED[stripped_name+chn_str] = chn_data # store adjustments
        else:
            chn_data = copy.copy(IMAGE_DATA_ADJUSTED[stripped_name+chn_str])
        composite.append([chn_data])


    

    print(f'Checking dimensions of composite: {np.asarray(composite).shape}')
    composite = np.asarray(composite)[:,0,:,:] # it's nested right now, so extract the values. Shape after this should be (#channels, pixelwidth, pixelheight, 4) 4 for rgba
    print(f'Checking dimensions of composite after extract: {np.asarray(composite).shape}')
    composite = np.sum(composite, axis=0) 
    print(f'Checking dimensions of composite after sum: {np.asarray(composite).shape}')
    composite[:,:,3] /= 3.0

    rgb_mins = [] ## Axis here?
    rgb_maxes = []
    for i in range(3):
        temp = np.ndarray.flatten(composite[:,:,i])
        
        rgb_mins.append(np.min(temp))
        rgb_maxes.append(np.max(temp))
    
    for i in range(3):
        composite[:,:,i] = composite[:,:,i] - float(rgb_mins[i])
        composite[:,:,i] = composite[:,:,i] /(float(rgb_maxes[i]) - float(rgb_mins[i]))
        composite[:,:,i] = composite[:,:,i] * 255.0

    print(f'Final check of dimensions of composite before setting data: {np.asarray(composite).shape}')

    layer.data = composite.astype('int') # casting is crucial
    # layer.events.set_data()

def adjust_gamma(viewer, gamma):
    for ctclayer in viewer.layers:
        if validate_adjustment(ctclayer):
            if ctclayer.name.split()[2] == 'Composite' and len(ADJUSTED)>1: # name looks like 'Cell 100 DAPI'
                print('About to enter adjust Composite func')
                adjust_composite(ctclayer, 1-gamma)
            else:
                ctclayer.gamma = gamma
            # print('Checking ', ctclayer.name)

@magicgui(auto_call=True,
        gamma={"widget_type": "FloatSlider", "max":1.0, "min":0.01},
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
            # print(f'blackin contrast limits: {ctclayer.contrast_limits}')
            ctclayer.contrast_limits = (black_in, ctclayer.contrast_limits[1])

# Called in a loop to create as many GUI elements as needed
def dynamic_checkbox_creator(checkbox_name):
    @magicgui(auto_call=True,
            check={"widget_type": "CheckBox", "text": checkbox_name},
            layout = 'horizontal')
    def myfunc(check: bool = True):
        # print(f'in myfunc backend CHANNELS are {CHANNELS}, and {CHANNELS_STR}. Trying to remove {checkbox_name}, whose global value is {globals()[checkbox_name]}, from {ADJUSTED}')
        if check:
            ADJUSTED.append(globals()[checkbox_name])
            # print(f'In check function. Current state, about to return and ADJUSTED is {ADJUSTED}, just added {checkbox_name}')
        else:
            ADJUSTED.remove(globals()[checkbox_name])
            # print(f'In check function. Current state, about to return and ADJUSTED is {ADJUSTED}, just removed {checkbox_name}')
    return myfunc

# print(f'dir is {dir()}')
def checkbox_setup():
    for checkbox_name in CHANNELS_STR:   
        exec(f"globals()[\'{checkbox_name+'_box'}\'] = globals()[\'dynamic_checkbox_creator\'](checkbox_name)") # If doing this is wrong I don't want to be right
    
checkbox_setup()
#------------------------- Image loading and processing functions ---------------------#

#TODO consider combining numpy arrays before adding layers? So that we create ONE image, and have ONE layer
#   for the ctc cells. Gallery mode might end up being a pain for downstream.
#   Counterpoint - how to apply filters to only some channels if they are in same image?
#   Counterpoint to counterpoint - never get rid of numpy arrays and remake whole image as needed. 
def add_layers(viewer,pyramid, cells, offset):
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

        # Napari bug: setting gamma here doesn't update what is seen, 
        # even thought the slider gui shows the change
        #   Will have to do something else.
        if colormap is not None: # Luminescence image
            shape_layer = viewer.add_image(layer, name = name, colormap = colormap, contrast_limits = contr, gamma = 0.5)
        elif contr is not None: # RBG image
            print(f'\n ~~~ Adding RGB Image ~~~ \n')
            shape_layer = viewer.add_image(layer, name = name, contrast_limits = contr, gamma = 0.5)
        else:
            print(f'\n ~~~ Adding RGB Image auto contrast limit ~~~ \n')
            shape_layer = viewer.add_image(layer, name = name, gamma = 0.5)

        @shape_layer.mouse_move_callbacks.append
        def display_intensity(shape_layer, event):
            data_coordinates = shape_layer.world_to_data(event.position)
            coords = np.round(data_coordinates).astype(int)
            val = None
            for img in VIEWER.layers:
                data_coordinates = img.world_to_data(event.position)
                val = img.get_value(data_coordinates)
                if val is not None:
                    shape_layer = img
                    break
            coords = np.round(data_coordinates).astype(int)
            # val = shape_layer.get_value(data_coordinates)
            # print(f'val is {val} and type is {type(val)}')
            if val is None:
                # print('none')
                VIEWER.status = f'{shape_layer.name} intensity at {coords}: N/A'
            else:
                # print('else')
                VIEWER.status = f'{shape_layer.name} intensity at {coords}: {val}'

        return True
    # def add_layer_rgb(viewer, layer, name):
    #     viewer.add_image(layer, name = name, rgb=True)
    #     return True

    def _convert_to_rgb(data, colormap, divisor):
        # You have to do it like this. Seriously. 
        global SC_DATA
        SC_DATA = data /divisor
        # SC_DATA /= divisor
        loc = {}
        # exec(f'rgb = cm.{colormap}(norm(SC_DATA))', globals(), loc)
        exec(f'rgb = cm.{colormap}(SC_DATA)', globals(), loc)
        return loc['rgb']
    
    print(f'Adding {len(cells)} cells to viewer...')
    while bool(cells): # coords left
        cell = cells.pop(); cell_x = cell[0]; cell_y = cell[1]; cell_id = cell[2]
        composite = []
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
                elif i==AF: continue #fluor='AF' 
                cell_name = f'Cell {cell_id} {fluor}'
                # print(f'Adding cell {cell_x},{cell_y} - layer {i}')
                cell_punchout_raw = pyramid[cell_x-offset:cell_x+offset,cell_y-offset:cell_y+offset,i].astype('float64')

                add_layer(viewer,cell_punchout_raw, cell_name, colormap= cell_colors[i])


                # normalize to 1.0

                # print(f'My types are as follows: \n cell raw {cell_punchout_raw.dtype}\n min {type(cell_punchout_raw.min())}\n max {type(cell_punchout_raw.max())}')
                # should be floats now
                # Normalize to range of 0.0 , 1.0 BEFORE passing through color map

                print(f' MIN / MAX output {np.min(cell_punchout_raw)} / {np.max(cell_punchout_raw)}')
                cell_punchout_raw = cell_punchout_raw #- cell_punchout_raw.min()
                cell_punchout_raw = cell_punchout_raw / 255.0 #cell_punchout_raw.max()

                # custom_map = vpc.get_colormap('single_hue',hue=40, saturation_range=[0.1,0.8], value=0.5)
                # cell_punchout = custom_map(cell_punchout_raw)*255
                print(f'color chosen is |{cell_colors[i]}|')

                cell_punchout = _convert_to_rgb(cell_punchout_raw, cell_colors[i], divisor= len(CHANNELS)-1) 

                # STORING in global dicts
                IMAGE_DATA_ORIGINAL[cell_name] = cell_punchout; IMAGE_DATA_ADJUSTED[cell_name] = cell_punchout

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
        composite = np.asarray(composite)[:,0,:,:] # it's nested right now, so extract the values. Shape after this should be (#channels, pixelwidth, pixelheight, 4) 4 for rgba
        # print(f'shape before summing is {composite.shape}')
        # print(f'trying to pull out some rgba data: black {composite[0,45,45,:]}\n blue {composite[1,45,45,:]}\n red {composite[2,45,45,:]}')
        composite = np.sum(composite, axis=0) 
        # print(f'\n!!! Shape after summing is {composite.shape}')
        # print(f'same pixel added: {composite [45,45,:]}')
        composite[:,:,3] /= 3.0
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
            composite[:,:,i] = composite[:,:,i] - float(rgb_mins[i])
            composite[:,:,i] = composite[:,:,i] /(float(rgb_maxes[i]) - float(rgb_mins[i]))
            composite[:,:,i] = composite[:,:,i] * 255.0

            # composite[:,:,i] -= np.min(composite[:,:,i])
            # composite[:,:,i] *= 255.0/np.max(composite[:,:,i])
        # print(f'same pixel multiplied / normalized to 0,255 range: {composite [45,45,:]}')
        # print(f'For cell number {cell_id} the datatype is {composite.dtype}, max value is {np.max(composite[:,:,0])} and the min is {np.min(composite[:,:,0])}')
        # print(f'also the shape is {composite.shape}') # (100,100,4)
        
        add_layer(viewer, composite.astype('int'), cell_name, colormap=None) #!!! NEEDS TO BE AN INT ARRAY!
        if len(cells) == 5:
            np.savetxt(r"C:\Users\prich\Desktop\Projects\MGH\CTC-Gallery-Viewer\data\composite.txt", composite[:,:,0])

    return True

''' Reset globals and proceed to main '''
def GUI_execute(userInfo):
    global cell_colors, qptiff, OFFSET, CELL_LIMIT, CHANNELS_STR, CHANNEL_ORDER
    global CHANNELS, ADJUSTED, OBJECT_DATA, PHENOTYPE, CELL_ID_START

    cell_colors = userInfo.cell_colors
    qptiff = userInfo.qptiff
    OFFSET = userInfo.imageSize
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
        print(f'enumerating {chn} and {pos} for {CHANNELS_STR}')
        exec(f"globals()['{chn}'] = {pos}") # Important to do this for ALL channels
        if chn in CHANNELS_STR:
            print(f'IF triggered with {chn} and {pos}')
            exec(f"globals()['CHANNELS'].append({chn})")
    print(f'GUI execute channels are {CHANNELS}')
    ADJUSTED = copy.copy(CHANNELS)

    # for checkbox_name in CHANNELS_STR:   
    #     print(f'checkbox name is {checkbox_name} and type is {type(checkbox_name)}')
    #     exec(f"globals()[\'{checkbox_name+'_box'}\'].show()") # If doing this is wrong I don't want to be right

    main()

def GUI_execute_cheat(userInfo):
    main()

def main():

    # print(f'dumping globals before checkbox\n {globals()}')
    #    # Execution loop - need to call it here to get the names into the namespace
    
    # print(f'dumping globals AFTER\n {globals()}')
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
    
    if CELL_ID_START < len(halo_export) and CELL_ID_START > 0:     
        halo_export = halo_export[CELL_ID_START:] # Exclude cells prior to target ID
    halo_export = halo_export[halo_export[PHENOTYPE]==1]
    if CELL_LIMIT < len(halo_export) and CELL_LIMIT > 0:
        halo_export = halo_export[:CELL_LIMIT] # pare down cell list (now containing only phenotype of interest) to desired length
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
    print(f'$$$$$$ OFFSET is {OFFSET}')
    add_layers(viewer,pyramid,tumor_cell_XYs, int(OFFSET/2))
    global VIEWER
    VIEWER = viewer
    viewer.grid.enabled = True
    viewer.grid.shape = (CELL_LIMIT, len(CHANNELS)) # +1 when plotting the shitty composite
    viewer.window.add_dock_widget(adjust_gamma_widget, area = 'bottom')
    viewer.window.add_dock_widget(adjust_whitein, area = 'bottom')
    viewer.window.add_dock_widget(adjust_blackin, area = 'bottom')

    # @VIEWER.bind_key('h')
    # def hello_world(viewer):
    #     # on key press
    #     VIEWER.status = 'hello world!'

    #     yield

    #     # on key release
    #     VIEWER.status = 'goodbye world :('
    
    # print(f'\n {dir()}') # prints out the namespace variables 
    # viewer.window.add_dock_widget(check_test, area = 'bottom')
    for marker_function in CHANNELS_STR:
        # Only make visible the chosen markers
        exec(f"viewer.window.add_dock_widget({marker_function+'_box'}, area='bottom')")
    #adjust_gamma(viewer,0.5)

    napari.run()



if __name__ == '__main__':
    main()



