import pandas as pd
import numpy as np
import napari
import IPython
import pyarrow.dataset as ds
import pyarrow.parquet as pq
import pyarrow as pa
import dask.array as da
import zarr
import os
from skimage.segmentation import find_boundaries
from skimage.morphology import binary_dilation, disk
from skimage.transform import resize
from skimage.exposure import rescale_intensity
from vispy.color.colormap import Colormap
import scipy.stats as st
import matplotlib.pyplot as plt
import copy

# Single cell processing
import scanpy as sc
import anndata as ad
from scipy.sparse import csr_matrix
from pathlib import Path
import re
from scanpy import logging as logg
import seaborn as sns
from napari.utils.color import transform_color
from napari.utils.colormaps import AVAILABLE_COLORMAPS, label_colormap, color_dict_to_colormap

txpath = r"C:\Users\prich\Desktop\pdac_tma_targets.csv"
pqpath = r'C:\Users\prich\Desktop\pdac_tma_targets.parquet'

# convert CSV to pandas to parquet
# tx = pd.read_csv(txpath)
# table = pa.Table.from_pandas(tx)
# pq.write_table(table, pqpath)

pqds = ds.dataset(pqpath)
slow_ds = ds.dataset(txpath, format = "csv")

# test queries to get one target / one FOV or something like that
# Timed using parquet: 50ms       ||       Timed using csv: 6.5s !!
# pqds.to_table(filter= (ds.field('target') == "CD74") & (ds.field("fov") == 10) ).to_pandas().head
# slow_ds.to_table(filter= (ds.field('target') == "CD74") & (ds.field("fov") == 10) ).to_pandas().head

zfolder = r"C:\Users\prich\Desktop\GalleryViewer-stitched\images"
cmeta = zarr.open(zfolder, mode = 'r+',).attrs['CosMx']
mm_per_px = cmeta['scale_um'] / 1000
px_per_mm = 1 / mm_per_px
fov_offsets = pd.DataFrame.from_dict(cmeta['fov_offsets'])

''' FOV stuff '''
def get_offsets(fov):
    """Get offsets for given FOV

    Args:
        fov (int): FOV number

    Returns:
        tuple: x and y offsets in mm
    """
    offset = fov_offsets[fov_offsets['FOV'] == fov]
    if offset.empty:
        raise ValueError(f"FOV {fov} is not in the data")
    x_offset = offset.iloc[0, ]["Y_mm"]
    y_offset = -offset.iloc[0, ]["X_mm"]
    return (x_offset, y_offset)

def rect_for_fov(fov):
    fov_height = cmeta['fov_height']* mm_per_px
    fov_width = cmeta['fov_width']* mm_per_px
    rect = np.array([
        list(get_offsets(fov)),
        list(map(sum, zip(get_offsets(fov), (fov_height, 0)))),
        list(map(sum, zip(get_offsets(fov), (fov_height, fov_width)))),
        list(map(sum, zip(get_offsets(fov), (0, fov_width))))
    ])
    topleft = (min(fov_offsets['Y_mm']), -max(fov_offsets['X_mm']))
    y_offset = topleft[0]
    x_offset = topleft[1]
    return [[i[0] - y_offset, i[1] - x_offset] for i in rect]

def add_fov_labels(view: napari.Viewer, tx_names = [], limits:tuple | None = None, cm = "inferno"):
    topleft = (min(fov_offsets['Y_mm']), -max(fov_offsets['X_mm']))
    rects = [rect_for_fov(i) for i in fov_offsets['FOV']]

    text_parameters = {
        'text': 'label',
        'size': 12,
        'color': 'white'
    }

    if tx_names != []:
        pts = pqds.to_table(filter= (ds.field('target').isin(tx_names)), columns=['fov']).to_pandas()
        values = pts.fov.value_counts().sort_index().to_numpy()
        if limits is not None:
            if len(limits) != 2:
                raise ValueError("Limits should be a tuple of two numbers")
            values = np.clip(values,*limits)

        shape_properties = {
            'label': fov_offsets['FOV'].to_numpy(),
            'n_transcripts' : values
        }
        shapes_layer = view.add_shapes(rects,
            face_color='n_transcripts',
            face_colormap= cm,
            edge_color='white',
            edge_width=0.02,
            properties=shape_properties,
            text = text_parameters,
            name = 'FOV labels',
            # translate=self._top_left_mm(),
            # rotate=self.rotate
        )
    else:
        shape_properties = {
            'label': fov_offsets['FOV'].to_numpy()
        }
        shapes_layer = view.add_shapes(rects,
            face_color='#90ee90',
            edge_color='white',
            edge_width=0.02,
            properties=shape_properties,
            text = text_parameters,
            name = 'FOV labels',
            # translate=self._top_left_mm(),
            # rotate=self.rotate
        )
    shapes_layer.opacity = 0.5
    shapes_layer.editable = False
    return shapes_layer

def center_fov(view: napari.Viewer, fov:int, buffer:float=1.0):
    """Center FOV in canvas and zoom to fill

    Args:
        fov (int): FOV number
        buffer (float): Buffer size for zoom. < 1 equals zoom out.
    """        
    # topleft = (min(fov_offsets['Y_mm']), -max(fov_offsets['X_mm'])) This is dumb???
    topleft = 0
    extent = [np.min(rect_for_fov(fov), axis=0) + topleft,
        np.max(rect_for_fov(fov), axis=0) + topleft]
    size = extent[1] - extent[0]
    view.camera.center = np.add(extent[0], np.divide(size, 2))
    view.camera.zoom = np.min(np.array(view._canvas_size) / size) * buffer

''' Image functions '''

# def slice_fov_single(layer, fov, shrink_factor):
#     sf = shrink_factor
#     top_origin_px = min(fov_offsets['Y_mm'])*px_per_mm - cmeta['fov_height']
#     left_origin_px = max(fov_offsets['X_mm'])*px_per_mm
#     y = round((fov_offsets[fov_offsets['FOV'] == fov].iloc[0, ]["Y_mm"]*px_per_mm - cmeta['fov_height']) - top_origin_px)
#     x = round(left_origin_px - fov_offsets[fov_offsets['FOV'] == fov].iloc[0, ]["X_mm"]*px_per_mm)
#     return layer[y//sf:(y//sf) + (cmeta['fov_height']//sf), x//sf:(x//sf) + (cmeta['fov_width'] // sf) ]

def slice_fov_dask(dask_list, fov):
    top_origin_px = min(fov_offsets['Y_mm'])*px_per_mm - cmeta['fov_height']
    left_origin_px = max(fov_offsets['X_mm'])*px_per_mm
    y = round((fov_offsets[fov_offsets['FOV'] == fov].iloc[0, ]["Y_mm"]*px_per_mm - cmeta['fov_height']) - top_origin_px)
    x = round(left_origin_px - fov_offsets[fov_offsets['FOV'] == fov].iloc[0, ]["X_mm"]*px_per_mm)
    fov_shrink_factors = [2**i for i in range(len(dask_list))]
    return [layer[y//sf:(y//sf) + (cmeta['fov_height']//sf), x//sf:(x//sf) + (cmeta['fov_width'] // sf)] for sf, layer in zip(fov_shrink_factors,dask_list) ]

def add_cell_leiden(view:napari.Viewer,adata: ad.AnnData, layername = "leiden",colname = "Selected",colvalues = [True], filled = True, fov = None):
    
    leiden_color = {k:transform_color(v).ravel().tolist() for k,v in enumerate(adata.uns['leiden_colors'])}
    cell_colors = {cid: leiden_color[l] for cid, l in zip(adata.obs.global_ID.tolist(), adata.obs.leiden.astype(int).tolist())}
    background =  {0:[0,0,0,0]}
    background.update(cell_colors)
    cell_colors = background
    if colname is not None:
        assert(colname in adata.obs.columns)
        exclude = {cid: [0,0,0,0] for cid in adata.obs.loc[~adata.obs["Selected"].isin(colvalues), "global_ID"].tolist()}
        cell_colors.update(exclude)

    metadata = zarr.open(zfolder, mode = 'r+',)["labels"].attrs
    datasets = metadata["multiscales"][0]["datasets"]
    im = [da.from_zarr(os.path.join(zfolder,"labels"), component=d["path"]) for d in datasets]
    if fov is not None:
        im = slice_fov_dask(im, fov)
    if not filled:
        def _keep_labels_erosion(labels):
            borders = find_boundaries(labels)
            return borders * labels
        im = [x.map_blocks(_keep_labels_erosion) for x in im]
    return view.add_labels(im,name=layername, color = cell_colors, scale = (mm_per_px, mm_per_px), metadata=metadata)

''' Method in gemini.py, designed by nanostring'''
def add_cell_leiden2(view:napari.Viewer,adata: ad.AnnData, layername = "leiden",colname = "Selected",colvalues = [True], filled = True, fov = None):
    
    leiden_color = {k:transform_color(v).ravel().tolist() for k,v in enumerate(adata.uns['leiden_colors'])}
    cell_colors = {cid: leiden_color[l] for cid, l in zip(adata.obs.global_ID.tolist(), adata.obs.leiden.astype(int).tolist())}
    # cell_leiden = cell_colors = {cid: l for cid, l in zip(adata.obs.global_ID.tolist(), adata.obs.leiden.astype(int).tolist())}
    background =  {0:[0,0,0,0]}
    background.update(cell_colors)
    cell_colors = background
    if colname is not None:
        assert(colname in adata.obs.columns)
        exclude = {cid: [0,0,0,0] for cid in adata.obs.loc[~adata.obs["Selected"].isin(colvalues), "global_ID"].tolist()}
        cell_colors.update(exclude)

    metadata = zarr.open(zfolder, mode = 'r+',)["labels"].attrs
    datasets = metadata["multiscales"][0]["datasets"]
    im = [da.from_zarr(os.path.join(zfolder,"labels"), component=d["path"]) for d in datasets]


    def color_labels(labels, cell_dict, fill):

        if not fill:
            borders = find_boundaries(labels)
            labels = borders * labels

        u, inv = np.unique(labels, return_inverse = True)
        image = np.array(
         [cell_dict[x] if x in cell_dict else 0 for x in u
         ])[inv].reshape(labels.shape)
        
        return image
    

    if fov is not None:
        im = slice_fov_dask(im, fov)

    custom_colormap, color_mappings = color_dict_to_colormap(cell_colors)

    im = [x.map_blocks(lambda x: color_labels(x, color_mappings, filled)) for x in im]
    return  view.add_image(im, name = layername,
            blending="translucent",
            opacity = 0.75,
            contrast_limits=(0,1),
            colormap=custom_colormap,
            cache=True,
            scale = (mm_per_px, mm_per_px),
            rgb=False)

def add_cell_leiden3(view:napari.Viewer,adata: ad.AnnData, layername = "leiden",colname = "Selected",colvalues = [True], filled = True, fov = None):

    metadata = zarr.open(zfolder, mode = 'r+',)["labels"].attrs
    datasets = metadata["multiscales"][0]["datasets"]
    im = [da.from_zarr(os.path.join(zfolder,"labels"), component=d["path"]) for d in datasets]

    def _remove_bg_cells_and_fill(_labels, _population, _filled ):
        _labels[~np.isin(_labels, _population)] = 0 # Cells not in population will be treated as background and not colored
        if not _filled:
            borders = find_boundaries(_labels)
            return borders * _labels
        else:
            return _labels

    if fov is not None:
        im = slice_fov_dask(im, fov)
        population = adata.obs.loc[(adata.obs[colname].isin(colvalues)) & (adata.obs['fov'] == str(fov)), "global_ID"].to_numpy() 
    else:
        population = adata.obs.loc[adata.obs[colname].isin(colvalues), "global_ID"].to_numpy() 

        leiden_color = {k:transform_color(v).ravel().tolist() for k,v in enumerate(adata.uns['leiden_colors'])}
    if colname is not None:
        assert colname in adata.obs.columns, f"Column {colname} not in adata"
        cell_colors = {cid: leiden_color[l] for cid, l in zip(adata.obs.loc[adata.obs[colname].isin(colvalues), "global_ID"].tolist(), adata.obs.leiden.astype(int).tolist())}
    else:
        pass
    cell_colors = {cid: leiden_color[l] for cid, l in zip(population, adata.obs.leiden.astype(int).tolist())}
    cell_colors = {cid: leiden_color[l] for cid, l in zip(population, adata.obs.leiden.astype(int).tolist())}
    # Add bg color 
    background =  {0:[0,0,0,0]}
    background.update(cell_colors)
    cell_colors = background

    im = [x.map_blocks(lambda: _remove_bg_cells_and_fill(x, population, filled)) for x in im]
    return view.add_labels(im,name=layername, color = cell_colors, scale = (mm_per_px, mm_per_px), metadata=metadata)

def add_cell_metadata_labels(view:napari.Viewer,meta: pd.DataFrame,colname = "Selected",colvalues = [True], layername = "Custom", cm = "gray", filled = True, fov = None):
    metadata = zarr.open(zfolder, mode = 'r+',)["labels"].attrs
    datasets = metadata["multiscales"][0]["datasets"]

    def _filter_labels(labels, _population, _filled):
        labels[~np.isin(labels, _population)] = 0
        if _filled:
            return rescale_intensity(labels, out_range = (0,(2**8)-1)).astype(np.uint8)
        else:
            return find_boundaries(labels)
        
    im = [da.from_zarr(os.path.join(zfolder,"labels"), component=d["path"]) for d in datasets]
    # im = da.from_zarr(os.path.join(zfolder,"labels"), 
    #     component=datasets[0]["path"])
    
    # fov_im = slice_fov_dask(im,fov)
    if fov is not None:
        im = slice_fov_dask(im, fov)
        population = meta.loc[(meta[colname].isin(colvalues)) & (meta['fov'] == str(fov)), "global_ID"].to_numpy() 
    else:
        population = meta.loc[meta[colname].isin(colvalues), "global_ID"].to_numpy() 
    
    im = [x.map_blocks(lambda x: _filter_labels(x, population, filled)) for x in im]
    # cm = Colormap(['transparent', cm], controls = [0.0, 1.0])
    # scaled = rescale_intensity(im, out_range = (0,(2**8)-1)).astype(np.uint8)
    layer = view.add_image(im, name=layername, multiscale=True,
        colormap=cm, 
        blending="additive",
        opacity = 0.5,
        scale = (mm_per_px,mm_per_px),
        rgb=False,
        metadata=metadata)
    return layer

def add_cell_labels(view:napari.Viewer, layername = "outlines", cm = "gray", fov = None):
    metadata = zarr.open(zfolder, mode = 'r+',)["labels"].attrs
    datasets = metadata["multiscales"][0]["datasets"]
    im = [da.from_zarr(os.path.join(zfolder,"labels"), component=d["path"]).map_blocks(find_boundaries)
        for d in datasets]
    if fov is not None:
        im = slice_fov_dask(im, fov)
    cm = Colormap(['transparent', cm], controls = [0.0, 1.0])
    layer = view.add_image(im, name=layername, multiscale=True,
        colormap=cm, 
        blending="translucent",
        opacity = 0.5,
        scale = (mm_per_px,mm_per_px),
        rgb=False,
        metadata=metadata)
    return layer

def add_zarr_layer(view: napari.Viewer,name = 'U', layername = "DAPI", cm = "blue", fov = None):
    if(name == "labels"):
        return add_cell_labels(view,layername, cm,fov)
    metadata = zarr.open(zfolder, mode = 'r+',)[name].attrs
    # track updates to contrast limits and colormap
    sync_metadata = 'omero' in metadata

    datasets = metadata["multiscales"][0]["datasets"]
    im = [da.from_zarr(os.path.join(zfolder,name), component=d["path"]) for d in datasets]
    
    if fov is not None:
        im = slice_fov_dask(im, fov)

    window = metadata['omero']['channels'][0]['window']
    layer = view.add_image(im, name=layername, multiscale=True,
        colormap=cm, blending="additive",
        contrast_limits = (window['start'],window['end']),
        scale = (mm_per_px,mm_per_px),
        # translate=self._top_left_mm(), 
        # rotate=self.rotate,
        rgb=False,
        metadata=metadata)
    layer.contrast_limits_range = window['min'],window['max']
    return layer

def update_viewer(view, lparams, fov = None):
    layers = [add_zarr_layer(view, *args, fov = fov) for args in lparams]
    return layers

''' Transcript functions '''
def get_tx(tx_name, fov = None, extra_columns = []):
    topleft = (min(fov_offsets['Y_mm']), -max(fov_offsets['X_mm']))
    if fov:
        ec = [col for col in extra_columns if col not in ['x','y']]
        pts = pqds.to_table(filter= (ds.field('target') == tx_name) & (ds.field('fov') == fov), columns=['x','y']+ec ).to_pandas()
        yx = np.array([pts.y.to_numpy(), pts.x.to_numpy()]).transpose()
    else:
        ec = [col for col in extra_columns if col not in ['fov','x','y']]  
        pts = pqds.to_table(filter= (ds.field('target') == tx_name), columns=['fov','x', 'y'] + ec ).to_pandas()
        pts = pd.merge(pts, fov_offsets[["FOV","X_mm","Y_mm"]], left_on='fov',right_on='FOV', how='left')
        yx = np.array([pts.y.to_numpy() + pts.Y_mm.to_numpy()*(1/mm_per_px) - topleft[0]*(1/mm_per_px),
                   pts.x.to_numpy() - pts.X_mm.to_numpy()*(1/mm_per_px) - topleft[1]*(1/mm_per_px)]).transpose()
    if extra_columns:
        return yx, pts[extra_columns]
    else:
        return yx

def add_tx(view: napari.Viewer, tx_name, fov = None, col = 'white',cm = 'viridis', psize = 20):
    if col in pqds.schema.names:
       pts, feat = get_tx(tx_name, fov, extra_columns=[col])
       if feat[col].dtype == "object":
           feat = feat.transform(lambda x: pd.CategoricalIndex(x).codes + 1)
       feat = feat[[col]].to_numpy().ravel() # Flatten to 1D
                                    
       ptprops = {col : rescale_intensity(feat, out_range = (0,1.0))} # Scale 0 to 1 is expected for colors.
       return view.add_points(pts, name=f'{tx_name} {col}', face_color=col, face_colormap= cm, properties=ptprops,  edge_color="white",
                size = psize, scale= (mm_per_px,mm_per_px)) 
    
    else:
        return view.add_points(get_tx(tx_name, fov),
                name=tx_name, face_color= col, size = psize, scale= (mm_per_px,mm_per_px))

def add_tx_heatmap(view: napari.Viewer, tx_name, imshape, fov=None, kind = ["contour"], scale_kde = True,
                   scale_kde_limits = (25, 500),
                   kdekws = {"colormap" : "magma", "blending":"translucent", "opacity" : 0.4}, 
                   contourkws = {"colormap":"magma","blending":"additive", "linewidth":5, "pcts" : [0.25,0.5,0.6,0.7,0.8,0.9]}, 
                   vectorkws = {"edge_colormap":"turbo", "vector_style":"arrow","edge_width":10,"blending":"translucent","opacity":0.85,
                                "step_size" : 20, "magnitude_scalar" : 0.85}):
    if fov == None:
        print("Can't do a kde for the full CosMx stitched image")
        return None

    return_layers = tuple() # add pointers to layers created and return to caller
    # Peform the kernel density estimate
    pts = get_tx(tx_name, fov)
    x = pts[:,0]
    y = pts[:,1]
    xmin, xmax = 0, imshape[0]
    ymin, ymax = 0, imshape[1]

    xx, yy = np.mgrid[xmin:xmax:100j, ymin:ymax:100j]
    positions = np.vstack([xx.ravel(), yy.ravel()])
    values = np.vstack([x, y])
    kernel = st.gaussian_kde(values)
    f = np.reshape(kernel(positions).T, xx.shape)

    scaled = resize(f,(imshape[0]//2, imshape[1]//2) )
    kde = rescale_intensity(scaled, out_range = (0,(2**16)-1)).astype(np.uint16)
    grad = np.gradient(kde)
    # Method: scale the KDE image to a range where the highest value represents the number of transcripts that you would find in 
    #   the FOV if the whole FOV had the density of the top 90%
    #   Then, set contrast limits equal to the user defined transcripts per FOV density. 
    if scale_kde:
        thresh = 0.9 * ((2**16)-1)
        lbl = kde.copy()
        lbl[lbl < thresh] = 0
        lbl[lbl >=thresh] = 1
        coords_int = np.round(pts/2).astype(int)
        tx_by_containing_region = lbl[tuple(coords_int.T)]
        region_tx = np.unique(tx_by_containing_region, return_counts = True)[1][1]
        region_size_px = np.unique(lbl, return_counts = True)[1][1]
        region_size_um = region_size_px * mm_per_px * 1_000
        tx_per_um = region_tx / region_size_um
        tx_per_fov = region_tx * (kde.shape[0]*kde.shape[1] /region_size_px)
        # 0.0015 tx per pixel is high? number for Line1 in FOV 127 
        # 0.00013 is low? FOXP3 in 127
        low = scale_kde_limits[0]
        high = scale_kde_limits[1]
        # kde = (kde * min(1, max(tx_per_um,low) / high)).astype(np.uint16)
        kde_range = (0,tx_per_fov)
        kde = rescale_intensity(kde, out_range = kde_range).astype(np.uint16)
        tx_name = f'{tx_name} scaled'
        cl = scale_kde_limits
        magnitude_scalar = min(1, tx_per_fov/scale_kde_limits[1]) 
    else:
        kde_range = (0, (2**16)-1)
        cl = None

    if "kde" in kind:
        kdekws = copy.copy(kdekws)
        out = view.add_image(kde, name = f"{tx_name} kde",scale = (mm_per_px*2,mm_per_px*2),contrast_limits=cl, **kdekws)
        return_layers += tuple([out])

    if "contour" in kind:
        contourkws = copy.copy(contourkws)
        pcts = contourkws.pop("pcts")
        linewidth = contourkws.pop("linewidth")
        contours = np.zeros(kde.shape, kde.dtype)
        for thresh in pcts:
            thresh = thresh * kde.max()
            lbl = kde.copy()
            lbl[lbl < thresh] = 0
            lbl[lbl >=thresh] = 1
            bord = find_boundaries(lbl).astype(kde.dtype)
            contours = np.bitwise_or(contours,kde * binary_dilation(bord, footprint = disk(linewidth)))
        out = view.add_image(contours, name = f"{tx_name} contour", scale = (mm_per_px*2,mm_per_px*2),contrast_limits=cl, **contourkws)
        return_layers += tuple([out])
    
    if "vector" in kind:
        vectorkws = copy.copy(vectorkws)
        step_size = vectorkws.pop("step_size")
        if scale_kde:
            magnitude_scalar = magnitude_scalar 
            vectorkws.pop("magnitude_scalar")
        else:
            magnitude_scalar = vectorkws.pop("magnitude_scalar")
        
        mgrad  =  np.stack((grad[0],grad[1]),axis=2) * -1 * magnitude_scalar
        step = mgrad.shape[0] // step_size
        vector_grid = mgrad[step:-step:step, step:-step:step] # samples points in a step x step grid. Don't include the border samples (prevent edge effects)
        distances = vector_grid.reshape(vector_grid.shape[0]**2, 2)
        grid_coords = []
        steps = range(step,len(mgrad)-step, step)
        for x in steps:
            for y in steps:
                grid_coords.append([x,y])
        grid_coords = np.array(grid_coords)
        #loop
        # grid_coords = np.array([[x,y] for x in steps for y in steps])
        vectors = np.stack((grid_coords,distances),axis=1)
        vprops = {"magnitude" : np.linalg.norm(distances, axis = 1)}
        cl = (0,step) if scale_kde else None # Color scale the vectors if needed. KDE scaling already controls the magnitudes.
        out = view.add_vectors(vectors,name = f"{tx_name} vectors",properties = vprops, 
                edge_contrast_limits= cl, scale = (mm_per_px*2,mm_per_px*2), **vectorkws)
        return_layers += tuple([out])
    
    if not return_layers:
        # Caller did not specify a valid kind of plot
        raise ValueError("Argument 'kind' needs to be one of ['kde','contour', 'vector']")
    else:
        return return_layers

''' Scanpy stuff for cell level data'''

def read_nanostring(
    path: str | Path,
    *,
    counts_file: str,
    meta_file: str
) -> ad.AnnData:
    """
    Read *Nanostring* formatted dataset.

    In addition to reading the regular *Nanostring* output, it loads the metadata file, if present *CellComposite* and *CellLabels*
    directories containing the images and optionally the field of view file.

    .. seealso::

        - `Nanostring Spatial Molecular Imager <https://nanostring.com/products/cosmx-spatial-molecular-imager/>`_.
        - :func:`squidpy.pl.spatial_scatter` on how to plot spatial data.

    Parameters
    ----------
    path
        Path to the root directory containing *Nanostring* files.
    counts_file
        File containing the counts. Typically ends with *_exprMat_file.csv*.
    meta_file
        File containing the spatial coordinates and additional cell-level metadata.
        Typically ends with *_metadata_file.csv*.\

    Returns
    -------
    Annotated data object with the following keys:

        - :attr:`anndata.AnnData.obsm` ``['spatial_fov']`` -  local coordinates of the centers of cells.
        - :attr:`anndata.AnnData.obsm` ``['spatial']`` - global coordinates of the centers of cells in the
          field of view.
    """  # noqa: E501
    path, fov_key = Path(path), "fov"
    cell_id_key = "cell_ID"
    if counts_file.endswith('.gz'):
        print("Unzipping, reading compressed counts ... ")
        counts = pd.read_csv(path / counts_file, header=0, index_col=cell_id_key, compression = 'infer')
    else:
        print("Reading counts ... ", end='')
        counts = pd.read_csv(path / counts_file, header=0, index_col=cell_id_key)
    print("Done")
    counts.index = counts.index.astype(str).str.cat(counts.pop(fov_key).astype(str).values, sep="_")

    print("Reading cell metadata ... ", end='')
    def _meta_filter(colname):
        first = not colname.startswith("i.")
        second = not colname.startswith("RNA_")
        third = not colname.startswith("nn_")
        return first and second and third
    
    obs = pd.read_csv(path / meta_file, header=0, index_col=cell_id_key, usecols= _meta_filter)
    obs[fov_key] = pd.Categorical(obs[fov_key].astype(str))
    obs[cell_id_key] = obs.index.astype(np.int64)
    obs.rename_axis(None, inplace=True)
    obs.index = obs.index.astype(str).str.cat(obs[fov_key].values, sep="_")
    common_index = obs.index.intersection(counts.index)
    print("Done")
    #TODO do something with QC?
    #meta.loc[meta["qcFlagsFOV"] == "Fail", "fov"].unique() 

    print("Creating AnnData ... ", end='')
    adata = ad.AnnData(
        csr_matrix(counts.loc[common_index, :].values),
        dtype=counts.values.dtype,
        obs=obs.loc[common_index, :]
    )
    adata.var_names = counts.columns
    adata.obsm["spatial_fov"] = adata.obs[["CenterX_local_px", "CenterY_local_px"]].values
    adata.obsm["spatial"] = adata.obs[["CenterX_global_px", "CenterY_global_px"]].values
    adata.obs.drop(columns=["CenterX_local_px", "CenterY_local_px"], inplace=True)
    print('Done')
    return adata

from matplotlib.widgets import LassoSelector
from matplotlib.path import Path

class SelectFromCollection:
    """
    Select indices from a matplotlib collection using `LassoSelector`.

    Selected indices are saved in the `ind` attribute. This tool fades out the
    points that are not part of the selection (i.e., reduces their alpha
    values). If your collection has alpha < 1, this tool will permanently
    alter the alpha values.

    Note that this tool selects collection objects based on their *origins*
    (i.e., `offsets`).

    Parameters
    ----------
    ax : `~matplotlib.axes.Axes`
        Axes to interact with.
    collection : `matplotlib.collections.Collection` subclass
        Collection you want to select from.
    alpha_other : 0 <= float <= 1
        To highlight a selection, this tool sets all selected points to an
        alpha value of 1 and non-selected points to *alpha_other*.
    """

    def __init__(self, ax, collection, alpha_other=0.3):
        self.canvas = ax.figure.canvas
        self.collection = collection
        self.alpha_other = alpha_other

        self.xys = collection.get_offsets()
        self.Npts = len(self.xys)

        # Ensure that we have separate colors for each object
        self.fc = collection.get_facecolors()
        if len(self.fc) == 0:
            raise ValueError('Collection must have a facecolor')
        elif len(self.fc) == 1:
            self.fc = np.tile(self.fc, (self.Npts, 1))

        self.lasso = LassoSelector(ax, onselect=self.onselect)
        self.ind = []

    def onselect(self, verts):
        path = Path(verts)
        self.ind = np.nonzero(path.contains_points(self.xys))[0]
        self.fc[:, -1] = self.alpha_other
        self.fc[self.ind, -1] = 1
        self.collection.set_facecolors(self.fc)
        self.canvas.draw_idle()

    def disconnect(self):
        self.lasso.disconnect_events()
        self.fc[:, -1] = 1
        self.collection.set_facecolors(self.fc)
        self.canvas.draw_idle()

def interactive_umap(adata, figure_color = "leiden", alpha_for_nonselected = 0.3):
    fig = sc.pl.umap(adata,color=figure_color,wspace=0.4,legend_loc = 'on data',legend_fontoutline = 2, size = 15,return_fig = True )
    ax = fig.get_axes()[0]

    selector = SelectFromCollection(ax, ax.collections[0], alpha_other = alpha_for_nonselected)

    def accept(event):
        if event.key == "enter":
            print("Selection made.")
            adata.obs["Selected"] =  False
            adata.obs.iloc[selector.ind, adata.obs.columns.get_loc("Selected")] = True
            # selector.disconnect() # Not doing this allows for re-selection
            ax.set_title(f"Selected {len(selector.ind)} cells.")
            fig.canvas.draw()
    fig.canvas.mpl_connect("key_press_event", accept)
    ax.set_title("Press enter to accept selected points.")
    plt.show()

def auto_interactive_umap(view: napari.Viewer, adata: ad.AnnData, fov = 1, figure_color = "leiden", labels_color = 'cyan', alpha_for_nonselected = 0.1, borders_only = False,psize = 15, method = 1):
    if isinstance(adata.obs.dtypes.loc[figure_color] , pd.CategoricalDtype):
        fig = sc.pl.umap(adata,color=figure_color,wspace=0.4,legend_loc = 'on data',legend_fontoutline = 2, size = psize,return_fig = True )
    else:
        fig = sc.pl.umap(adata,color=figure_color,wspace=0.4, size = psize,return_fig = True ) # Can't get opacity to work for non-categorical data
    ax = fig.get_axes()[0]
    selector = SelectFromCollection(ax, ax.collections[0], alpha_other = alpha_for_nonselected)

    def accept(event):
        if event.key == "enter":
            print("Selection made.")
            adata.obs["Selected"] =  False
            adata.obs.iloc[selector.ind, adata.obs.columns.get_loc("Selected")] = True
            # selector.disconnect() # Not doing this allows for re-selection

            # If layer is already here, delete

            if labels_color == 'leiden':
                try:
                    view.layers.remove(view.layers["leiden"])
                except KeyError:
                   pass
                if method ==2:
                    add_cell_leiden2(view, adata, fov=fov, filled = not borders_only)
                else:
                    add_cell_leiden(view, adata, fov=fov, filled = not borders_only)
            else:
                try:
                    view.layers.remove(view.layers["Custom"])
                except KeyError:
                   pass
                add_cell_metadata_labels(view, adata.obs, cm = labels_color, fov = fov, filled = not borders_only)
            
            ax.set_title(f"Selected {len(selector.ind)} cells.")
            fig.canvas.draw()
    fig.canvas.mpl_connect("key_press_event", accept)
    ax.set_title("Press enter to accept selected points.")
    plt.show()


adata = ad.read_h5ad(r"C:\Users\prich\Desktop\GalleryViewer-stitched\counts.h5ad")
# Make global_ID that is unique to a cell across FOVs and interpretable for the mask stitched for the viewer.
adata.obs["global_ID"] = adata.obs['cell_ID'].astype(int) + (adata.obs['fov'].astype(int) * 25_000)

leiden_color = {k:transform_color(v).ravel().tolist() for k,v in enumerate(adata.uns['leiden_colors'])}
cell_colors = {cid: leiden_color[l] for cid, l in zip(adata.obs.global_ID.tolist(), adata.obs.leiden.astype(int).tolist())}
background =  {0:[0,0,0,0]}
background.update(cell_colors)
cell_colors = background
# I do this and paste all the other code in the embedded terminal. Allows you to continue to enter code in the terminal and have napari work. If you start the viewer BEFORE IPython, the terminal
#   is hung. Has to do with Napari's event loop.
IPython.embed()
exit()

viewer = napari.Viewer(title = "Zarr cosmx test")

# Edit to contain ( *name of image folder under ./images*, *semantic name you want to display in the viewer*, *a valid colormap*)
npr_params = [("U","DAPI", "gray"), ("B","PanCK","green"), 
              ("Y","Membrane","bop purple"), ("R", "CD45", "red"),
              ("labels","outlines","gray"), ("G", "Not sure", "yellow")]


FOV = None #126 #126 #136
layers = update_viewer(viewer, npr_params, fov = FOV) # fov = None will add a full image
RNA = "LINE1_ORF1"
l1 = add_tx(viewer, RNA, col="white", psize = 35, fov =FOV)

fov_labels = add_fov_labels(viewer, tx_names=[RNA])
# l1c = add_tx_heatmap(viewer, RNA, (cmeta['fov_width'], cmeta['fov_height']), fov  = FOV, kind=["kde","contour","vector"], scale_kde=False)

#                     #  contourkws = {"colormap":"blue","blending":"additive", "linewidth":5, "pcts" : [0.25,0.5,0.6,0.7,0.8,0.9]}) 

# RNA = "B2M"
# l1 = add_tx(viewer, RNA,col="white", psize = 35, fov  =FOV)
# l1c = add_tx_heatmap(viewer, RNA, (cmeta['fov_width'], cmeta['fov_height']), fov  = FOV, kind=["kde","contour","vector"], scale_kde=False,
#                      contourkws = {"colormap":"red","blending":"additive", "linewidth":5, "pcts" : [0.25,0.5,0.6,0.7,0.8,0.9]}) 

# sc.logging.print_header()

# adata = read_nanostring(r"C:\Users\prich\Desktop\GalleryViewer-stitched", counts_file="S1_exprMat_file.csv.gz", meta_file= "S1_metadata_file.csv")
# # sc.pp.calculate_qc_metrics(adata, qc_vars=["NegPrb"], inplace=True)
# pd.set_option("display.max_columns", None)
# adata.obs["nCount_negprobes"].sum() / adata.obs["nCount_RNA"].sum() * 100


# ## Transcripts per cell, unique transcripts per cell, transcripts per FOV
# fig, axs = plt.subplots(1, 3, figsize=(15, 4))

# axs[0].set_title("Total transcripts per cell")
# sns.histplot(
#     adata.obs["nCount_RNA"],
#     kde=False,
#     ax=axs[0],)

# axs[1].set_title("Unique transcripts per cell")
# sns.histplot(
#     adata.obs["nFeature_RNA"],
#     kde=False,
#     ax=axs[1],)

# axs[2].set_title("Transcripts per FOV")
# sns.histplot(
#     adata.obs.groupby("fov").sum()["nCount_RNA"],
#     kde=False,
#     ax=axs[2],)
# plt.show()



# ## Immunofluorescence data
# fig, axs = plt.subplots(1, 4, figsize=(15, 4))

# axs[0].set_title("Membrane Stain")
# sns.histplot(
#     adata.obs["Mean.Membrane"],
#     kde=False,
#     ax=axs[0],)

# axs[1].set_title("PanCK")
# sns.histplot(
#     adata.obs["Mean.PanCK"],
#     kde=False,
#     ax=axs[1],)

# axs[2].set_title("CD45")
# sns.histplot(
#     adata.obs["Mean.CD45"],
#     kde=False,
#     ax=axs[2],)

# axs[3].set_title("DAPI")
# sns.histplot(
#     adata.obs["Mean.DAPI"],
#     kde=False,
#     ax=axs[3],)
# plt.show()

# Gene level data
# fig, axs = plt.subplots(1, 2)
# ax=axs[0].set_title("Mean counts per cell by gene")
# sns.histplot(adata.var["mean_counts"],ax=axs[0])

# ax=axs[1].set_title("Unique cells containing at least 1 copy of gene")
# sns.histplot(adata.var["n_cells_by_counts"],ax=axs[1])
# plt.show()


## Filter cells by min transcripts, filter genes by min cells
# sc.pp.filter_cells(adata, min_counts=20)
# sc.pp.filter_genes(adata, min_cells=500)

# ## Dimensionality reduction and clustering
# adata.layers["counts"] = adata.X.copy() # save raw counts before normalizing
# sc.pp.normalize_total(adata, inplace=True)
# sc.pp.log1p(adata)
# sc.pp.pca(adata)
# sc.pp.neighbors(adata)
# sc.tl.umap(adata)
# sc.tl.leiden(adata)
#The warning suggests doing this but it throws continuos error messages. Exception ignored in: <class 'ValueError'>
'''Traceback (most recent call last):
  File "numpy\\random\\mtrand.pyx", line 779, in numpy.random.mtrand.RandomState.randint
  File "numpy\\random\\_bounded_integers.pyx", line 2881, in numpy.random._bounded_integers._rand_int32
ValueError: high is out of bounds for int32 '''
# sc.tl.leiden(adata, flavor="igraph", n_iterations=2, directed=False)

# adata.write(r"C:\Users\prich\Desktop\GalleryViewer-stitched\counts.h5ad")
# adata = ad.read_h5ad(r"C:\Users\prich\Desktop\GalleryViewer-stitched\counts.h5ad")
# adata.obs["global_ID"] = adata.obs['cell_ID'].astype(int) + (adata.obs['fov'].astype(int) * 25_000)

# interactive_umap(adata)

# add_cell_metadata_labels(viewer, adata.obs, "leiden", ['1','11'], 'leiden 1 and 11', cm = 'bop purple', fov = FOV)
# add_cell_metadata_labels(viewer, adata.obs, "leiden", ['12','13','14','15','16','17','18'], 
#     'leiden 12+', cm = 'bop orange', fov = FOV, rip_layer=0)

add_cell_leiden(viewer, adata, colname = None, filled = False)
auto_interactive_umap(viewer, adata, fov = FOV, labels_color='cyan', borders_only=False)





