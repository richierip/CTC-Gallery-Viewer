# Utility file to return custom colormaps
import numpy as np

def create_red_cm():
    colors = np.linspace(
        start=[0, 0, 0, 1],
        stop=[1, 0, 0, 1],
        num=256,
        endpoint=True)

    red_colormap = {
        'colors': colors,
        'name': 'Red',
        'interpolation': 'linear'}
    return red_colormap

def create_red_lut():
    colors = np.linspace(
        start=[0, 0, 0, 1],
        stop=[1, 0, 0, 1],
        num=256,
        endpoint=True)
    return colors

def create_green_cm():
    colors = np.linspace(
        start=[0, 0, 0, 1],
        stop=[0, 1, 0, 1],
        num=256,
        endpoint=True)

    green_colormap = {
        'colors': colors,
        'name': 'Green',
        'interpolation': 'linear'}
    return green_colormap

def create_green_lut():
    colors = np.linspace(
        start=[0, 0, 0, 1],
        stop=[0, 1, 0, 1],
        num=256,
        endpoint=True)

    return colors

def create_blue_cm():
    colors = np.linspace(
        start=[0, 0, 0, 1],
        stop=[0, 0, 1, 1],
        num=256,
        endpoint=True)

    blue_colormap = {
        'colors': colors,
        'name': 'Blue',
        'interpolation': 'linear'}
    return blue_colormap

def create_blue_lut():
    colors = np.linspace(
        start=[0, 0, 0, 1],
        stop=[0, 0, 1, 1],
        num=256,
        endpoint=True)

    return colors

def create_Pink_cm():
    colors = np.linspace(
        start=[0, 0, 0, 1],
        stop=[1, 0, 1, 1],
        num=256,
        endpoint=True)

    pink_colormap = {
        'colors': colors,
        'name': 'Pink',
        'interpolation': 'linear'}
    return pink_colormap

def create_Pink_lut():
    colors = np.linspace(
        start=[0, 0, 0, 1],
        stop=[1, 0, 1, 1],
        num=256,
        endpoint=True)

    return colors

def create_yellow_cm():
    colors = np.linspace(
        start=[0, 0, 0, 1],
        stop=[1, 1, 0, 1],
        num=256,
        endpoint=True)

    yellow_colormap = {
        'colors': colors,
        'name': 'Yellow',
        'interpolation': 'linear'}
    return yellow_colormap

def create_yellow_lut():
    colors = np.linspace(
        start=[0, 0, 0, 1],
        stop=[1, 1, 0, 1],
        num=256,
        endpoint=True)

    return colors

def create_cyan_cm():
    colors = np.linspace(
        start=[0, 0, 0, 1],
        stop=[0, 1, 1, 1],
        num=256,
        endpoint=True)

    cyan_colormap = {
        'colors': colors,
        'name': 'Cyan',
        'interpolation': 'linear'}
    return cyan_colormap

def create_cyan_lut():
    colors = np.linspace(
        start=[0, 0, 0, 1],
        stop=[0, 1, 1, 1],
        num=256,
        endpoint=True)

    return colors

def create_orange_cm():
    colors = np.linspace(
        start=[0, 0, 0, 1],
        stop=[1, 0.647, 0, 1],
        num=256,
        endpoint=True)

    orange_colormap = {
        'colors': colors,
        'name': 'Orange',
        'interpolation': 'linear'}
    return orange_colormap

def create_orange_lut():
    colors = np.linspace(
        start=[0, 0, 0, 1],
        stop=[1, 0.647, 0, 1],
        num=256,
        endpoint=True)

    return colors

def create_purple_cm():
    colors = np.linspace(
        start=[0, 0, 0, 1],
        stop=[0.627, 0.125, 0.941, 1],
        num=256,
        endpoint=True)

    purple_colormap = {
        'colors': colors,
        'name': 'Purple',
        'interpolation': 'linear'}
    return purple_colormap

def create_purple_lut():
    colors = np.linspace(
        start=[0, 0, 0, 1],
        stop=[0.627, 0.125, 0.941, 1],
        num=256,
        endpoint=True)

    return colors

def create_gray_cm():
    colors = np.linspace(
        start=[0, 0, 0, 1],
        stop=[1, 0.647, 1, 1],
        num=256,
        endpoint=True)

    gray_colormap = {
        'colors': colors,
        'name': 'Gray',
        'interpolation': 'linear'}
    return gray_colormap

def create_gray_lut():
    colors = np.linspace(
        start=[0, 0, 0, 1],
        stop=[1, 0.647, 1, 1],
        num=256,
        endpoint=True)

    return colors
