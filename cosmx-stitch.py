'''
Scavenging the necessary code to stich CosMx files and make a zarr that will be readable for napari as one plane. 
'''

from tqdm.auto import tqdm
from importlib.metadata import version
import argparse
import os
import sys
import re
import sys
import math
import numpy as np
import pandas as pd
import tifffile
import zarr
import dask.array as da
import json
from skimage.transform import resize
from numcodecs import Zlib
from functools import partial
from tqdm.auto import tqdm as std_tqdm
import re
from pathlib import Path

## From _patterns.py
timestamp_pattern = re.compile("^(?P<timestamp>[0-9]{8}_[0-9]{6})_")
slide_pattern = re.compile("(?:^|_)S(?P<slide>[0-9])(?:_|$)")
cycle_pattern = re.compile("(?:^|_)C(?P<cycle>[0-9]+)(?:_|[.]|$)")
pool_pattern = re.compile("(?:^|_)P(?P<pool>[0-9]+)(?:_|[.]|$)")
spot_pattern = re.compile("(?:^|_)N(?P<spot>[0-9]+)(?:_|[.]|$)")
fov_pattern = re.compile("(?:^|_)F(?:OV)?(?P<fov>[0-9]+)(?:_|[.]|$)")
zslice_pattern = re.compile("(?:^|_)Z(?P<zslice>[0-9]+)(?:_|[.]|$)")
## From _patterns.py
def get_fov_number(filepath):
    filename = Path(filepath).name
    m = fov_pattern.search(filename)
    return int(m['fov']) if m else None


BETA_UM_PER_PX = 0.1203
BETA_MM_PER_PX = BETA_UM_PER_PX/1000
BETA_PX_PER_MM = 1/BETA_MM_PER_PX

ALPHA_UM_PER_PX = 0.1681
ALPHA_MM_PER_PX = ALPHA_UM_PER_PX/1000
ALPHA_PX_PER_MM = 1/ALPHA_MM_PER_PX

DASH_UM_PER_PX = 0.18
DASH_MM_PER_PX = DASH_UM_PER_PX/1000
DASH_PX_PER_MM = 1/DASH_MM_PER_PX

DEFAULT_COLORMAPS = {
    'DAPI': 'blue',
    'DNA': 'blue',
    'PanCK': 'green',
    'U': 'blue',
    'G': 'green',
    None: 'gray'
}

OTHER_KEYS = ['labels', 'protein', 'composite', 'targets', 'fovgrid']


zarr.storage.default_compressor = Zlib()
# CHUNKS = (8192, 8192)  # 'auto' or tuple
CHUNKS = (2**14,2**14) # 2x above

fov_tqdm = partial(
        std_tqdm, desc='Added FOV', unit=" FOVs", ncols=40, mininterval=1.2,
        bar_format="{desc} {n_fmt}/{total_fmt}|{bar}|{percentage:3.0f}%")

## From _stitch.py
def offsets(offsetsdir):
    df = pd.read_csv(os.path.join(offsetsdir, "latest.fovs.csv"), header=None)
    cols = {k: v for k, v in enumerate(
        ["Slide", "X_mm", "Y_mm", "Z_mm", "ZOffset_mm", "ROI", "FOV", "Order"]
        )}
    return df.rename(columns=cols)
## From _stitch.py
def _resize(image):
    return resize(
        image,
        output_shape=(max(1, image.shape[0]//2), max(1, image.shape[1]//2)),
        order=0,
        preserve_range=True,
        anti_aliasing=False
    )
## From _stitch.py
def write_pyramid(image, scale_dict, store, path):
    PYRAMID_LEVELS = math.floor(math.log2(max(image.shape)/256))
    um_per_px = scale_dict["um_per_px"]
    pyramid_scale = 1
    dimensions = ['y','x']
    datasets = [{}]*PYRAMID_LEVELS
    print(f"Writing {path} multiscale output to zarr.")
    for i in range(PYRAMID_LEVELS):
        print(f"Writing level {i+1} of {PYRAMID_LEVELS}, shape: {image.shape}, chunksize: {image.chunksize}")
        image.to_zarr(store, component=path+f"/{i}", overwrite=True, write_empty_chunks=False, dimension_separator="/")
        new_chunks = tuple([
            tuple([max(1, i//2) for i in image.chunks[0]]),
            tuple([max(1, i//2) for i in image.chunks[1]])
        ])
        if path == "composite":
            new_chunks = new_chunks + (3,)
        image = image.map_blocks(_resize, dtype=image.dtype, chunks=new_chunks)
        datasets[i] = {'path': str(i), 
                       'coordinateTransformations':[{'type':'scale', 
                       'scale':[um_per_px*pyramid_scale]*len(dimensions)}]} 
        pyramid_scale *= 2
    grp = zarr.open(store, mode = 'r+')
    grp[path].attrs['multiscales'] = [{
        'axes':[{'name': dim, 'type': 'space', 'unit': 'micrometer'} for dim in dimensions],
        'datasets': datasets,
        'type': 'resize'
        }]
    channel_name = os.path.splitext(path)[0]
    # write image intensity stats as omero metadata
    if channel_name not in ['labels', 'composite']:
        window = {}
        print("Calculating contrast limits")
        window['min'], window['max'] = int(da.min(image)), int(da.max(image))
        window['start'],window['end'] = [int(x) for x in da.percentile(image.ravel()[image.ravel()!=0], (0.1, 99.9))]
        if window['start'] - window['end'] == 0:
            if window['end'] == 0:
                print(f"\nWARNING: {channel_name} image is empty!")
                window['end'] = 1000
            else:
                window['start'] = 0
        print(f"Writing omero metadata...\n{str(window)}")
        color = DEFAULT_COLORMAPS[channel_name] if channel_name in DEFAULT_COLORMAPS else DEFAULT_COLORMAPS[None]
        grp[path].attrs['omero'] = {'name':channel_name, 'channels': [{
            'label':channel_name,
            'window': window,
            'color': color
            }]}## From _stitch.py
## From _stitch.py
def base(fov_offsets, fov_height, fov_width, scale_dict, dash):
    px_per_mm = scale_dict["px_per_mm"]
    if dash:
        top_origin_px = max(fov_offsets['X_mm'])*px_per_mm + fov_height
        left_origin_px = min(fov_offsets['Y_mm'])*px_per_mm
        height = round(top_origin_px - min(fov_offsets['X_mm'])*px_per_mm)
        width = round((max(fov_offsets['Y_mm'])*px_per_mm + fov_width) - left_origin_px)
    else:
        top_origin_px = min(fov_offsets['Y_mm'])*px_per_mm - fov_height
        left_origin_px = max(fov_offsets['X_mm'])*px_per_mm
        height = round(max(fov_offsets['Y_mm'])*px_per_mm - top_origin_px)
        width = round((left_origin_px + fov_width) - min(fov_offsets['X_mm'])*px_per_mm)
    return top_origin_px, left_origin_px, height, width
 ## From _stitch.py
## From _stitch.py
def fov_origin(fov_offsets, fov, top_origin_px, left_origin_px, fov_height, scale_dict, dash):
    px_per_mm = scale_dict["px_per_mm"]
    if dash:
        y = round(top_origin_px - (fov_offsets[fov_offsets['FOV'] == fov].iloc[0, ]["X_mm"]*px_per_mm + fov_height))
        x = round(fov_offsets[fov_offsets['FOV'] == fov].iloc[0, ]["Y_mm"]*px_per_mm - left_origin_px)
    else:
        y = round((fov_offsets[fov_offsets['FOV'] == fov].iloc[0, ]["Y_mm"]*px_per_mm - fov_height) - top_origin_px)
        x = round(left_origin_px - fov_offsets[fov_offsets['FOV'] == fov].iloc[0, ]["X_mm"]*px_per_mm)
    return y, x
## From _stitch.py
def get_scales(tiff_path=None, um_per_px=None, scale=1):
    if um_per_px is None:
        with tifffile.TiffFile(tiff_path) as im:
            try:
                tif_tags = {}
                for tag in im.pages[0].tags.values():
                    tif_tags[tag.name] = tag.value
                j = json.loads(tif_tags['ImageDescription'])
                Magnification, PixelSize_um = j['Magnification'], j['PixelSize_um']
                um_per_px = round(PixelSize_um/Magnification, 4)
                print(f"Reading pixel size and magnification from metadata... scale = {um_per_px:.4f} um/px")
            except:
                im_shape = im.pages[0].shape
                fov_height,fov_width = im_shape[0],im_shape[1]
                dash = (fov_height/fov_width) != 1
                if dash:
                    instrument = 'DASH'
                    um_per_px = DASH_UM_PER_PX
                else:
                    beta = fov_height%133 == fov_width%133 == 0
                    if beta:
                        instrument = 'BETA'
                        um_per_px = BETA_UM_PER_PX
                    else:
                        instrument = 'ALPHA'
                        um_per_px = ALPHA_UM_PER_PX
                print(f"Pixel size and magnification not found in metadata, reverting to {instrument} default: {um_per_px:.4f} um/px.")
    um_per_px = round(um_per_px/scale, 4)
    mm_per_px = um_per_px/1000
    px_per_mm = 1/mm_per_px
    if scale != 1:
        print(f"Scaling by {scale} based on user input...")
        print(f"New scale = {um_per_px:.4f} um/px")
    return {"um_per_px":um_per_px, "mm_per_px":mm_per_px, "px_per_mm":px_per_mm}  

## From pairing.py
def pair_np(x, y):
    """Encode x to array of y

    Zero remains zero.

    Args:
        x (int): number
        y (ndarray): numpy array of int
    """    
    z = y != 0
    a = (x >= y) & z
    b = (x < y) & z
    np.putmask(y, a, x * x + x + y)
    np.putmask(y, b, y * y + x)

def main(args_list=None):
    parser = argparse.ArgumentParser(description='Tile CellLabels and morphology TIFFs.',
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("-i", "--inputdir",
        help="Required: Path to CellLabels and morphology images.",
        default=".")
    parser.add_argument("--imagesdir",
        help="Optional: Path to morphology images, if different than inputdir.",
        default=None)
    parser.add_argument("-o", "--outputdir",
        help="Required: Where to create zarr output.",
        default=".")
    parser.add_argument("-f", "--offsetsdir",
        help="Required: Path to latest.fovs.csv directory.",
        default=".")
    parser.add_argument("-l", "--labels",
        help="\nOptional: Only stitch labels.",
        action='store_true')
    parser.add_argument("-u", "--umperpx",
        help="Optional: Override image scale in um per pixel.\n"+
        "Instrument-specific values to use:\n-> beta04 = 0.1228",
        default=None,
        type=float)
    parser.add_argument("-z", "--zslice",
        help="Optional: Z slice to stitch.",
        default="0",
        type=int)
    parser.add_argument("--dotzarr",
        help="\nOptional: Add .zarr extension on multiscale pyramids.",
        action='store_true')
    args = parser.parse_args(args=args_list)

    # Check output directory
    if not os.path.exists(args.outputdir):
        print(f"Output path does not exist, creating {args.outputdir}")
        os.mkdir(args.outputdir)
    store = os.path.join(args.outputdir, "images")
    if not os.path.exists(store):
        os.mkdir(store)


    if args.imagesdir is None:
        args.imagesdir = args.inputdir

    # Read latest.fovs.csv file
    fov_offsets = offsets(args.offsetsdir)

    labels_res = []
    for root, dirs, files in os.walk(args.inputdir):
        labels_res += [os.path.join(root, f) for f in files 
            if re.match(r"CELLLABELS_F[0-9]+\.TIF", f.upper())]

    # Check input directory for images and get image dimensions
    im_shape = None
    if len(labels_res) == 0:
        print(f"No CellLabels_FXXX.tif files found at {args.inputdir}")
    else:
        ref_tif = labels_res[0]
        im_shape = tifffile.TiffFile(ref_tif).pages[0].shape

    ihc_res = []
    if not args.labels:
        z_string = f"_Z{args.zslice:03}" if args.zslice != 0 else "" 
        for root, dirs, files in os.walk(args.imagesdir):
            ihc_res += [os.path.join(root, f) for f in files 
                if re.match(r".*C902_P99_N99_F[0-9]+" + z_string + r"\.TIF", f.upper())]

        if len(ihc_res) == 0:
            print(f"No _FXXX{z_string}.TIF images found at {args.imagesdir}")
        else:
            ref_tif = ihc_res[0]
            with tifffile.TiffFile(ref_tif) as im:
                n = len(im.pages)
                if n <= 1:
                    sys.exit("Expecting multi-channel TIFFs")
                im_shape = im.pages[0].shape
                if im_shape is None:
                    sys.exit("No images found, exiting.")
            # get morphology kit metadata
                channels = markers = ['B','G','Y','R','U']
                tif_tags = {}
                try:
                    for tag in im.pages[0].tags.values():
                        tif_tags[tag.name] = tag.value
                    j = json.loads(tif_tags['ImageDescription'])
                    reagents = j['MorphologyKit']['MorphologyReagents']
                    mkit = {}
                    for r in reagents:
                        channel = r['Fluorophore']['ChannelId']
                        target = r['BiologicalTarget'].replace("/", "_")
                        mkit[channel] = target
                    markers = [mkit[c] for c in channels] 
                except:
                    pass # channel names left as default ['B','G','R','Y','U']
        
    fov_height = im_shape[0]
    fov_width = im_shape[1]
    dash = (fov_height/fov_width) != 1
    if args.umperpx == None:
        scale_dict = get_scales(tiff_path=ref_tif)
    else:
        scale_dict = get_scales(um_per_px=args.umperpx)
    
    top_origin_px, left_origin_px, height, width = base(
        fov_offsets, fov_height, fov_width, scale_dict, dash)
    
    if len(labels_res) != 0:
        im = da.zeros((height, width), dtype=np.uint32, chunks=CHUNKS)
        print("Stitching cell segmentation labels.")
        for fov in fov_tqdm(fov_offsets['FOV']):
            tile_path = [x for x in labels_res if get_fov_number(x) == int(fov)]
            if len(tile_path) == 0:
                tqdm.write(f"Could not find CellLabels image for FOV {fov}")
                continue
            elif len(tile_path) > 1:
                tqdm.write(f"Multiple CellLabels files found for FOV {fov}\nUsing {tile_path[0]}")
            tile = tifffile.imread(tile_path[0]).astype(np.uint32)
            pair_np(fov, tile)
            y, x = fov_origin(fov_offsets, fov, top_origin_px, left_origin_px, fov_height, scale_dict, dash)
            im[y:y+tile.shape[0], x:x+tile.shape[1]] = tile
        
        write_pyramid(im, scale_dict, store=store, path="labels")
        #TODO: Add .zarr extension to labels if --dotzarr is used. May not be recognized by previous reader versions.
             # Needs more work before readable by napari-ome-zarr anyway

    print("Saving metadata")
    grp = zarr.open(store, mode = 'a')
    grp.attrs['CosMx'] = {
        'fov_height': fov_height,
        'fov_width': fov_width,
        'fov_offsets': fov_offsets.to_dict(),
        'scale_um': scale_dict['um_per_px'],
        'version': '0.4.17.0' # manually entered from the .whl downloaded from napari-cosmx
    }

    if len(ihc_res) != 0:
        for i in range(n):
            im = da.zeros((height, width), dtype=np.uint16, chunks=CHUNKS)
            print(f"Stitching images for {markers[i]}.")
            for fov in fov_tqdm(fov_offsets['FOV']):
                tile_path = [x for x in ihc_res if get_fov_number(x) == int(fov)]
                if len(tile_path) == 0:
                    tqdm.write(f"Could not find image for FOV {fov}")
                    continue
                elif len(tile_path) > 1:
                    tqdm.write(f"Multiple image files found for FOV {fov}\nUsing {tile_path[0]}")
                with tifffile.TiffFile(tile_path[0]) as my_tiff:
                    tile = my_tiff.pages[i].asarray()
                y, x = fov_origin(fov_offsets, fov, top_origin_px, left_origin_px, fov_height, scale_dict, dash)
                im[y:y+tile.shape[0], x:x+tile.shape[1]] = tile
            if args.dotzarr:
                markers[i] += ".zarr"
            write_pyramid(im, scale_dict, store=store, path=f"{markers[i]}")

if __name__ == '__main__':
    sys.exit(main())