# Utility file to return custom colormaps
# Each look-up table will be used to convert one intensity (luminescence) value 
#   to the RGB value of the corresponding color.
import numpy as np
import matplotlib

def create_red_lut(inverse = False):
    # numpy will interpolate between these endpoint values to create 
    # all 256 rows of the LUT
    if inverse: 
        colors = np.linspace(start=[1, 1, 1, 1],stop=[1, 0, 0, 1], num=256,endpoint=True)
    else:
        colors = np.linspace(start=[0, 0, 0, 1],stop=[1, 0, 0, 1],num=256,endpoint=True)
    return colors

def create_red_cm(inverse = False):
    colors = create_red_lut(inverse)
    if inverse: name = 'Red inverse'
    else: name = 'Red'
    red_colormap = {
        'colors': colors,
        'name': name,
        'interpolation': 'linear'}
    return red_colormap

def create_green_lut(inverse = False):
    if inverse:
        colors = np.linspace(start=[1, 1, 1, 1],stop=[0, 1, 0, 1],num=256,endpoint=True)
    else:
        colors = np.linspace(start=[0, 0, 0, 1],stop=[0, 1, 0, 1],num=256,endpoint=True)
    return colors

def create_green_cm(inverse = False):
    colors = create_green_lut(inverse)
    if inverse: name = 'Green inverse'
    else: name = 'Green'
    green_colormap = {
        'colors': colors,
        'name': name,
        'interpolation': 'linear'}
    return green_colormap

def create_blue_lut(inverse = False):
    if inverse:
        colors = np.linspace(start=[1, 1, 1, 1],stop=[0, 0, 1, 1],num=256,endpoint=True)
    else:
        colors = np.linspace(start=[0, 0, 0, 1],stop=[0, 0, 1, 1],num=256,endpoint=True)
    return colors

def create_blue_cm(inverse=False):
    colors = create_blue_lut(inverse)
    if inverse:name = 'Blue inverse'
    else: name = 'Blue'
    blue_colormap = {
        'colors': colors,
        'name': name,
        'interpolation': 'linear'}
    return blue_colormap

# matplotlib has a 'pink' already, and won't allow one to be registered with the same
#   name. To keep it straight this one will be capitalized
def create_Pink_lut(inverse=False):
    if inverse:
        colors = np.linspace(start=[1, 1, 1, 1],stop=[1, 0, 1, 1],num=256,endpoint=True)
    else:
        colors = np.linspace(start=[0, 0, 0, 1],stop=[1, 0, 1, 1],num=256,endpoint=True)
    return colors

def create_Pink_cm(inverse=False):
    colors = create_Pink_lut(inverse)
    if inverse:name = 'Pink inverse'
    else: name = 'Pink'
    pink_colormap = {
        'colors': colors,
        'name': name,
        'interpolation': 'linear'}
    return pink_colormap

def create_yellow_lut(inverse=False):
    if inverse:
        colors = np.linspace(start=[1, 1, 1, 1],stop=[1, 1, 0, 1],num=256,endpoint=True)
    else:
        colors = np.linspace(start=[0, 0, 0, 1],stop=[1, 1, 0, 1],num=256,endpoint=True)
    return colors

def create_yellow_cm(inverse = False):
    colors = create_yellow_lut(inverse)
    if inverse: name = 'Yellow inverse'
    else: name='Yellow'
    yellow_colormap = {
        'colors': colors,
        'name': name,
        'interpolation': 'linear'}
    return yellow_colormap

def create_cyan_lut(inverse=False):
    if inverse:
        colors = np.linspace(start=[1, 1, 1, 1],stop=[0, 1, 1, 1],num=256,endpoint=True)
    else:
        colors = np.linspace(start=[0, 0, 0, 1],stop=[0, 1, 1, 1],num=256,endpoint=True)
    return colors
    
def create_cyan_cm(inverse=False):
    colors = create_cyan_lut(inverse)
    if inverse: name = 'Cyan inverse'
    else: name = 'Cyan'
    cyan_colormap = {
        'colors': colors,
        'name': name,
        'interpolation': 'linear'}
    return cyan_colormap

def create_orange_lut(inverse=False):
    if inverse:
        colors = np.linspace(start=[1, 1, 1, 1],stop=[1, 0.647, 0, 1],num=256,endpoint=True)
    else:
        colors = np.linspace(start=[0, 0, 0, 1],stop=[1, 0.647, 0, 1],num=256,endpoint=True)
    return colors

def create_orange_cm(inverse=False):
    colors = create_orange_lut(inverse)
    if inverse: name = 'Orange inverse'
    else: name = 'Orange'
    orange_colormap = {
        'colors': colors,
        'name': name,
        'interpolation': 'linear'}
    return orange_colormap

def create_purple_lut(inverse = False):
    if inverse:
        colors = np.linspace(start=[1, 1, 1, 1],stop=[0.627, 0.125, 0.941, 1],num=256,endpoint=True)
    else:
        colors = np.linspace(start=[0, 0, 0, 1],stop=[0.627, 0.125, 0.941, 1],num=256,endpoint=True)
    return colors

def create_purple_cm(inverse=False):
    colors = create_purple_lut(inverse)
    if inverse: name = 'Purple inverse'
    else: name='Purple'
    purple_colormap = {
        'colors': colors,
        'name': name,
        'interpolation': 'linear'}
    return purple_colormap

def create_gray_lut(inverse=False):
    if inverse:
        colors = np.linspace(start=[1, 1, 1, 1],stop=[1, 1, 1, 1],num=256,endpoint=True)
    else:
        colors = np.linspace(start=[0, 0, 0, 1],stop=[1, 1, 1, 1],num=256,endpoint=True)
    return colors

def create_gray_cm(inverse=False):
    colors = create_gray_lut(inverse)
    if inverse: name = 'Gray inverse'
    else: name = 'Gray'
    gray_colormap = {
        'colors': colors,
        'name': name,
        'interpolation': 'linear'}
    return gray_colormap

red = create_red_cm()
cyan = create_cyan_cm()
green = create_green_cm()
gray = create_gray_cm()
orange = create_orange_cm()
purple = create_purple_cm()
pink = create_Pink_cm()
blue = create_blue_cm()
yellow = create_yellow_cm()

redI = create_red_cm(inverse=True)
cyanI = create_cyan_cm(inverse=True)
greenI = create_green_cm(inverse=True)
grayI = create_gray_cm(inverse=True)
orangeI = create_orange_cm(inverse=True)
purpleI = create_purple_cm(inverse=True)
pinkI = create_Pink_cm(inverse=True)
blueI = create_blue_cm(inverse=True)
yellowI = create_yellow_cm(inverse=True)

cm_dict = {'red':red,"cyan":cyan,"green":green,"gray":gray,"orange":orange,
            "purple":purple,"pink":pink,"Pink":pink,"blue":blue,"yellow":yellow,
            'red inverse':redI,"cyan inverse":cyanI,"green inverse":greenI,"gray inverse":grayI,"orange inverse":orangeI,
            "purple inverse":purpleI,"pink inverse":pinkI,"Pink inverse":pinkI,"blue inverse":blueI,"yellow inverse":yellowI}

def retrieve_cm(cm_name):
    return cm_dict[cm_name]
