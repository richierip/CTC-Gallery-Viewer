# Utility file to return custom colormaps
# Each look-up table will be used to convert one intensity (luminescence) value 
#   to the RGB value of the corresponding color.
import numpy as np
import matplotlib

def create_red_lut():
    # numpy will interpolate between these endpoint values to create 
    # all 256 rows of the LUT
    colors = np.linspace(
        start=[0, 0, 0, 1],
        stop=[1, 0, 0, 1],
        num=256,
        endpoint=True)
    return colors

def create_red_cm():
    colors = create_red_lut()

    red_colormap = {
        'colors': colors,
        'name': 'Red',
        'interpolation': 'linear'}
    return red_colormap

def create_green_lut():
    colors = np.linspace(
        start=[0, 0, 0, 1],
        stop=[0, 1, 0, 1],
        num=256,
        endpoint=True)
    return colors

def create_green_cm():
    colors = create_green_lut()

    green_colormap = {
        'colors': colors,
        'name': 'Green',
        'interpolation': 'linear'}
    return green_colormap

def create_blue_lut():
    colors = np.linspace(
        start=[0, 0, 0, 1],
        stop=[0, 0, 1, 1],
        num=256,
        endpoint=True)
    return colors

def create_blue_cm():
    colors = create_blue_lut()

    blue_colormap = {
        'colors': colors,
        'name': 'Blue',
        'interpolation': 'linear'}
    return blue_colormap

# matplotlib has a 'pink' already, and won't allow one to be registered with the same
#   name. To keep it straight this one will be capitalized
def create_Pink_lut():
    colors = np.linspace(
        start=[0, 0, 0, 1],
        stop=[1, 0, 1, 1],
        num=256,
        endpoint=True)
    return colors

def create_Pink_cm():
    colors = create_Pink_lut()

    pink_colormap = {
        'colors': colors,
        'name': 'Pink',
        'interpolation': 'linear'}
    return pink_colormap

def create_yellow_lut():
    colors = np.linspace(
        start=[0, 0, 0, 1],
        stop=[1, 1, 0, 1],
        num=256,
        endpoint=True)
    return colors

def create_yellow_cm():
    colors = create_yellow_lut()

    yellow_colormap = {
        'colors': colors,
        'name': 'Yellow',
        'interpolation': 'linear'}
    return yellow_colormap

def create_cyan_lut():
    colors = np.linspace(
        start=[0, 0, 0, 1],
        stop=[0, 1, 1, 1],
        num=256,
        endpoint=True)
    return colors
    
def create_cyan_cm():
    colors = create_cyan_lut()

    cyan_colormap = {
        'colors': colors,
        'name': 'Cyan',
        'interpolation': 'linear'}
    return cyan_colormap

def create_orange_lut():
    colors = np.linspace(
        start=[0, 0, 0, 1],
        stop=[1, 0.647, 0, 1],
        num=256,
        endpoint=True)
    return colors

def create_orange_cm():
    colors = create_orange_lut()

    orange_colormap = {
        'colors': colors,
        'name': 'Orange',
        'interpolation': 'linear'}
    return orange_colormap

def create_purple_lut():
    colors = np.linspace(
        start=[0, 0, 0, 1],
        stop=[0.627, 0.125, 0.941, 1],
        num=256,
        endpoint=True)
    return colors

def create_purple_cm():
    colors = create_purple_lut()

    purple_colormap = {
        'colors': colors,
        'name': 'Purple',
        'interpolation': 'linear'}
    return purple_colormap

def create_gray_lut():
    colors = np.linspace(
        start=[0, 0, 0, 1],
        stop=[1, 0.647, 1, 1],
        num=256,
        endpoint=True)
    return colors

def create_gray_cm():
    colors = create_gray_lut()

    gray_colormap = {
        'colors': colors,
        'name': 'Gray',
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

cm_dict = {'red':red,"cyan":cyan,"green":green,"gray":gray,"orange":orange,
            "purple":purple,"pink":pink,"blue":blue,"yellow":yellow}

def retrieve_lut(cmstr):
    return cm_dict[cmstr]
