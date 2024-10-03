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


def slice_fov(dask_list, fov):
        top_origin_px = min(fov_offsets['Y_mm'])*px_per_mm - cmeta['fov_height']
        left_origin_px = max(fov_offsets['X_mm'])*px_per_mm
        y = round((fov_offsets[fov_offsets['FOV'] == fov].iloc[0, ]["Y_mm"]*px_per_mm - cmeta['fov_height']) - top_origin_px)
        x = round(left_origin_px - fov_offsets[fov_offsets['FOV'] == fov].iloc[0, ]["X_mm"]*px_per_mm)
        fov_shrink_factors = [2**i for i in range(len(dask_list))]
        return [layer[y//sf:(y//sf) + (cmeta['fov_height']//sf), x//sf:(x//sf) + (cmeta['fov_width'] // sf)] for sf, layer in zip(fov_shrink_factors,dask_list) ]

def add_zarr_labels(view:napari.Viewer, layername = "outlines", cm = "gray", fov = None):
    metadata = zarr.open(zfolder, mode = 'r+',)["labels"].attrs
    datasets = metadata["multiscales"][0]["datasets"]
    im = [da.from_zarr(os.path.join(zfolder,"labels"), component=d["path"]).map_blocks(find_boundaries)
        for d in datasets]
    if fov is not None:
        im = slice_fov(im, fov)
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
        return add_zarr_labels(view,layername, cm,fov)
    metadata = zarr.open(zfolder, mode = 'r+',)[name].attrs
    # track updates to contrast limits and colormap
    sync_metadata = 'omero' in metadata

    datasets = metadata["multiscales"][0]["datasets"]
    im = [da.from_zarr(os.path.join(zfolder,name), component=d["path"]) for d in datasets]
    
    if fov is not None:
        im = slice_fov(im, fov)

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

''''''
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

IPython.embed()
exit()

viewer = napari.Viewer(title = "Zarr cosmx test")
npr_params = [("U","DAPI", "gray"), ("B","PanCK","green"), 
              ("Y","Membrane","bop purple"), ("R", "CD45", "red"),
              ("labels","outlines","gray"), ("G", "Not sure", "yellow")]

FOV = 126 #126 #136
layers = update_viewer(viewer, npr_params, fov = FOV)
RNA = "LINE1_ORF1"
l1 = add_tx(viewer, RNA,col="white", psize = 35, fov  =FOV)
l1c = add_tx_heatmap(viewer, RNA, (cmeta['fov_width'], cmeta['fov_height']), fov  = FOV, kind=["kde","contour","vector"], scale_kde=False)

                    #  contourkws = {"colormap":"blue","blending":"additive", "linewidth":5, "pcts" : [0.25,0.5,0.6,0.7,0.8,0.9]}) 

RNA = "B2M"
l1 = add_tx(viewer, RNA,col="white", psize = 35, fov  =FOV)
l1c = add_tx_heatmap(viewer, RNA, (cmeta['fov_width'], cmeta['fov_height']), fov  = FOV, kind=["kde","contour","vector"], scale_kde=False,
                     contourkws = {"colormap":"red","blending":"additive", "linewidth":5, "pcts" : [0.25,0.5,0.6,0.7,0.8,0.9]}) 



