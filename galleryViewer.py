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
import skimage
import gc # might garbage collect later
import math


QPTIFF_LAYER_TO_RIP = 0 # 0 is high quality. Can use 1 for testing (BF only, loads faster)
cell_colors = ['bop orange', 'bop purple' , 'green', 'blue', 'yellow','cyan', 'red', 'twilight']
qptiff = r"C:\Users\prich\Desktop\Projects\MGH\CTC_Example\Exp02a01_02_Scan1.qptiff"
OFFSET = 100 # microns or pixels?
CELL_START = 100
CELL_LIMIT = 150
CHANNELS = [0,1,2,3,4,5,6,7]

# Probably won't be used - both image and object data use same units in my example
def map_coords(array_shape, cellx,celly):
    array_x_length = array_shape[0]
    array_y_length = array_shape[1]

# @magicgui(auto_call=True,
#         sigma={"widget_type": "FloatSlider", "max":255},
#         layout = 'horizontal')
# def adjust_gamma(layer: ImageData) -> ImageData:
#     pass

def add_layers(viewer,pyramid, cells, offset):
    def add_layer(viewer, layer, name, colormap):
        # Napari bug: setting gamma here doesn't update what is seen, 
        # even thought the slider gui shows the change
        #   Will have to do something else.
        viewer.add_image(layer, name = name, colormap=colormap, gamma=0.5)
        return True
    # def add_layer_rgb(viewer, layer, name):
    #     viewer.add_image(layer, name = name, rgb=True)
    #     return True
    
    while bool(cells): # coords left
        cell = cells.pop(); cell_x = cell[0]; cell_y = cell[1]; cell_id = cell[2]

        # add the rest of the layers to the viewer
        for i in range(pyramid.shape[2]): # loop through channels
            if i in CHANNELS:
                # name cell layer
                if i==0: fluor='DAPI?'
                elif i==1: fluor='570'
                elif i==2: fluor='690' 
                elif i==3: fluor='480'
                elif i==4: fluor='620' 
                if i==5: fluor='780'
                elif i==6: fluor='520'
                elif i==7: fluor='AF' 
                cell_name = f'Cell {cell_id} {fluor}'
                print(f'Adding cell {cell_x},{cell_y} - layer {i}')
                add_layer(viewer,pyramid[cell_x-offset:cell_x+offset,cell_y-offset:cell_y+offset,i], cell_name, cell_colors[i])
    return True

def main():
    with tifffile.Timer(f'\nLoading pyramid from {qptiff}...\n'):
        pyramid = tifffile.imread(qptiff)
        # can pick select pages
        # image = imread('temp.tif', key=0)
        # images = imread('temp.tif', key=range(4, 40, 2))

        print('... completed in ', end='')
    print(f'\nFinal pyramid levels: {[p.shape for p in pyramid]}\n')

    # Find location of channels in np array. Save that value, and subset the rest (one nparray per channel)
    print(f'pyramid array as np array shape is {pyramid.shape}\n')
    arr = np.array(pyramid.shape)
    channels = min(arr)
    channel_index = np.where(arr == channels)[0][0]
    print(f'least is {channels}, type is {type(channels)} and its at {channel_index}, test is {channel_index==0}')

    # have to grab the first to instantiate napari viewer
    if channel_index == 0:
        # Added this because the high quality layer of my sample QPTIFF data seemed to be flipped
        # i.e. array looks like (channels, y, x)
        # to be seen if this actually works
        #TODO
        pyramid = np.transpose(pyramid,(2,1,0))
        print(f'FLIPPED SHAPE is {pyramid.shape}\n')
        firstLayer = pyramid[:,:,0]
    else:
        firstLayer = pyramid[:,:,0]
    print(f'Single layer shape is {firstLayer.shape}\n')

    # pyramid = skimage.io.imread(qptiff)
    # pyramid = pyramid[0][10000:11000, 100:1000]
    # pyramid = get_crop(pyramid, 10800, 900, 100, 100)

    # pyramidXC = int(pyramid.shape[0]/2)
    # pyramidYC = int(pyramid.shape[1]/2)
    
    halo_export = pd.read_csv(r"C:\Users\prich\Desktop\Projects\MGH\CTC_Example\ctc_example_data.csv")
    halo_export = halo_export.loc[CELL_START:CELL_LIMIT, ["Object Id", "XMin","XMax","YMin", "YMax", "Tumor"]]
    halo_export = halo_export[halo_export['Tumor']==1]
    tumor_cell_XYs = []
    for index,row in halo_export.iterrows():
        center_x = int((row['XMax']+row['XMin'])/2)
        center_y = int((row['YMax']+row['YMin'])/2)
        tumor_cell_XYs.append([center_x, center_y, row["Object Id"]])

    cell1 = [16690, 868]
    cell2 = [4050, 1081]

    viewer = napari.Viewer(title='CTC Gallery')
    sample_cell_dict = {}
    sample_cell_dict['cell_x'] = cell1[0] ; sample_cell_dict['cell_y'] = cell1[1]
    sample_cell_dict['slidewidth'] = pyramid.shape[0]
    sample_cell_dict['slidelength'] = pyramid.shape[1]
    
    add_layers(viewer,pyramid,tumor_cell_XYs, int(OFFSET/2))


    viewer.grid.enabled = True
    # viewer.window.add_dock_widget(adjust_gamma)

    napari.run()



if __name__ == '__main__':
    main()


