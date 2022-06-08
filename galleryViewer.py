'''
6/7/22
Peter Richieri
'''
import tifffile
import napari
import numpy as np
import pandas as pd
import skimage
import gc # might garbage collect later
import math

# 0 is high quality. Can use 1 for testing (BF only, loads faster)
QPTIFF_LAYER_TO_RIP = 0
cell_colors = ['bop orange', 'bop purple' , 'green', 'blue', 'yellow','cyan', 'red', 'twilight']
qptiff = r"C:\Users\prich\Desktop\Projects\MGH\CTC_Example\Exp02a01_02_Scan1.qptiff"
OFFSET = 100

def get_crop(page, i0, j0, h, w):
    """Extract a crop from a TIFF image file directory (IFD).
    
    Only the tiles englobing the crop area are loaded and not the whole page.
    This is usefull for large Whole slide images that can't fit int RAM.
    Parameters
    ----------
    page : TiffPage
        TIFF image file directory (IFD) from which the crop must be extracted.
    i0, j0: int
        Coordinates of the top left corner of the desired crop.
    h: int
        Desired crop height.
    w: int
        Desired crop width.
    Returns
    -------
    out : ndarray of shape (imagedepth, h, w, sampleperpixel)
        Extracted crop.
    """

    if not page.is_tiled:
        raise ValueError("Input page must be tiled.")

    im_width = page.imagewidth
    im_height = page.imagelength

    if h < 1 or w < 1:
        raise ValueError("h and w must be strictly positive.")

    if i0 < 0 or j0 < 0 or i0 + h >= im_height or j0 + w >= im_width:
        raise ValueError("Requested crop area is out of image bounds.")

    tile_width, tile_height = page.tilewidth, page.tilelength
    i1, j1 = i0 + h, j0 + w

    tile_i0, tile_j0 = i0 // tile_height, j0 // tile_width
    tile_i1, tile_j1 = np.ceil([i1 / tile_height, j1 / tile_width]).astype(int)

    tile_per_line = int(np.ceil(im_width / tile_width))

    out = np.empty((page.imagedepth,
                    (tile_i1 - tile_i0) * tile_height,
                    (tile_j1 - tile_j0) * tile_width,
                    page.samplesperpixel), dtype=page.dtype)

    fh = page.parent.filehandle

    jpegtables = page.tags.get('JPEGTables', None)
    if jpegtables is not None:
        jpegtables = jpegtables.value

    for i in range(tile_i0, tile_i1):
        for j in range(tile_j0, tile_j1):
            index = int(i * tile_per_line + j)

            offset = page.dataoffsets[index]
            bytecount = page.databytecounts[index]

            fh.seek(offset)
            data = fh.read(bytecount)
            tile, indices, shape = page.decode(data, index, jpegtables)

            im_i = (i - tile_i0) * tile_height
            im_j = (j - tile_j0) * tile_width
            out[:, im_i: im_i + tile_height, im_j: im_j + tile_width, :] = tile

    im_i0 = i0 - tile_i0 * tile_height
    im_j0 = j0 - tile_j0 * tile_width

    return out[:, im_i0: im_i0 + h, im_j0: im_j0 + w, :]

def map_coords(array_shape, cellx,celly):
    array_x_length = array_shape[0]
    array_y_length = array_shape[1]

def add_layers(viewer,pyramid, cells, offset):
    def add_layer(viewer, layer, name, colormap):
        viewer.add_image(layer, name = name, colormap=colormap)
    
    while bool(cells): # coords left
        cell = cells.pop(); cell_x = cell[0]; cell_y = cell[1]
    # add the rest of the layers to the viewer
        for i in range(pyramid.shape[2]):
            print(f'addLayer loop, round {i}')
            if i in [0,2,7]:
                add_layer(viewer,pyramid[cell_x-offset:cell_x+offset,cell_y-offset:cell_y+offset,i], 'CTCLayer '+str(i), cell_colors[i])
    return True

def main():
    with tifffile.Timer('Loading pyramid ...\n'):
        with tifffile.TiffFile(qptiff) as ctcimg:
            # Sort layers by size
            pyramid = list(reversed(sorted(ctcimg.series, key = lambda p:p.size)))
            print(f'Initial pyramid levels: {[p.shape for p in pyramid]}')
            size = pyramid[0].size
            # pyramid = [p for p in pyramid if size % p.size == 0]
            pyramid = pyramid[QPTIFF_LAYER_TO_RIP] #TODO should be 0 which signifies the highest quality layer

            # Convert to np array. This seems to be pretty damn slow. 
            # Roughly doubles the load time from <20s to >45s
            pyramid = [p.asarray() for p in pyramid]

            pyramid = np.array(pyramid)
            print(f'QPTiff shape before removing nesting {pyramid.shape}. Just so we know, the length of the array is {len(pyramid)}\n')
            if len(pyramid) == 1:
                pyramid = pyramid[0] # It was nested, might as well take it out
            else:
                #for now, reduce the freaking input size so it doesn't mess up my computer
                # pyramid = pyramid[0:1,:,:]
                pass
            print('... completed in ', end='')
    # print(f'\nFinal pyramid levels: {[p.shape for p in pyramid]}\n')

    # Find location of channels in np array. Save that value, and subset the rest (one nparray per channel)
    print(f'pyramid array as np array shape is {pyramid.shape}\n')
    arr = np.array(pyramid.shape)
    channels = min(arr)
    channel_index = np.where(arr == channels)[0][0]
    print(f'least is {channels}, type is {type(channels)} and its at {channel_index}, test is {channel_index==0}')

    # have to grab the first to instantiate napari viewer
    if channel_index == 0:
        # Added this because the high quality layer of my sample data seemed to be flipped
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
    cell1 = [16690, 868]
    cell2 = [4050, 1081]

    viewer = napari.Viewer(title='CTC Gallery')
    sample_cell_dict = {}
    sample_cell_dict['cell_x'] = cell1[0] ; sample_cell_dict['cell_y'] = cell1[1]
    sample_cell_dict['slidewidth'] = pyramid.shape[0]
    sample_cell_dict['slidelength'] = pyramid.shape[1]
    
    add_layers(viewer,pyramid,[cell1, cell2], OFFSET)


    viewer.grid.enabled = True
    napari.run()



if __name__ == '__main__':
    main()


