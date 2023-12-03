# Utility file to return custom colormaps
# Each look-up table will be used to convert one intensity (luminescence) value 
#   to the RGB value of the corresponding color.
import numpy as np
import matplotlib
import re
from PIL import Image

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


def isColor(color):
    toColor = []
    if isinstance(color, tuple):
        for element in color:
            toColor.append(isInt(element, 0))
            
        if len(toColor) > 3:
            toColor = [toColor[0], toColor[1], toColor[2]]
        if len(toColor) == 3:
            test = True
            for element in toColor:
                if element >= 0 and element < 256:
                    pass
                else:
                    test = False
            if test == True:
                color = True
            else:
                color = False
        else:
            color = False
    else:
        color = getcolori(color, 'RGB')
    return color
    
def isInt(value, remplacement=0):
    if value != 0:
        if isinstance(value, int):
            pass
        else:
            if isinstance(value, str):
                if value.isnumeric():
                    value = int(value)
                else:
                    value = remplacement
            else:
                value = remplacement
    else:
        value = remplacement
    return value
    
def getrgbi(color):
    """
        Convert a color string to an RGB or RGBA tuple.
    .. versionadded:: 1.1.4
    :param color: A color string
    :return: ``(red, green, blue[, alpha])``
    """
    if len(color) > 100:
        return False
    color = color.lower()

    rgb = colormap.get(color, None)
    if rgb:
        if isinstance(rgb, tuple):
            return rgb
        colormap[color] = rgb = getrgbi(rgb)
        return True

    # check for known string formats
    if re.match("#[a-f0-9]{3}$", color):
        return (int(color[1] * 2, 16), int(color[2] * 2, 16), int(color[3] * 2, 16))

    if re.match("#[a-f0-9]{4}$", color):
        return (
            int(color[1] * 2, 16),
            int(color[2] * 2, 16),
            int(color[3] * 2, 16),
            int(color[4] * 2, 16),
        )

    if re.match("#[a-f0-9]{6}$", color):
        return (int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16))

    if re.match("#[a-f0-9]{8}$", color):
        return (
            int(color[1:3], 16),
            int(color[3:5], 16),
            int(color[5:7], 16),
            int(color[7:9], 16),
        )

    m = re.match(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)$", color)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))

    m = re.match(r"rgb\(\s*(\d+)%\s*,\s*(\d+)%\s*,\s*(\d+)%\s*\)$", color)
    if m:
        return (
            int((int(m.group(1)) * 255) / 100.0 + 0.5),
            int((int(m.group(2)) * 255) / 100.0 + 0.5),
            int((int(m.group(3)) * 255) / 100.0 + 0.5),
        )

    m = re.match(
        r"hsl\(\s*(\d+\.?\d*)\s*,\s*(\d+\.?\d*)%\s*,\s*(\d+\.?\d*)%\s*\)$", color
    )
    if m:
        from colorsys import hls_to_rgb

        rgb = hls_to_rgb(
            float(m.group(1)) / 360.0,
            float(m.group(3)) / 100.0,
            float(m.group(2)) / 100.0,
        )
        return (
            int(rgb[0] * 255 + 0.5),
            int(rgb[1] * 255 + 0.5),
            int(rgb[2] * 255 + 0.5),
        )

    m = re.match(
        r"hs[bv]\(\s*(\d+\.?\d*)\s*,\s*(\d+\.?\d*)%\s*,\s*(\d+\.?\d*)%\s*\)$", color
    )
    if m:
        from colorsys import hsv_to_rgb

        rgb = hsv_to_rgb(
            float(m.group(1)) / 360.0,
            float(m.group(2)) / 100.0,
            float(m.group(3)) / 100.0,
        )
        return (
            int(rgb[0] * 255 + 0.5),
            int(rgb[1] * 255 + 0.5),
            int(rgb[2] * 255 + 0.5),
        )

    m = re.match(r"rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)$", color)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))
    return False


def getcolori(color, mode):
    """
    Same as :py:func:`~PIL.ImageColor.getrgb`, but converts the RGB value to a
    greyscale value if the mode is not color or a palette image. If the string
    cannot be parsed, this function raises a :py:exc:`ValueError` exception.
    .. versionadded:: 1.1.4
    :param color: A color string
    :return: ``(graylevel [, alpha]) or (red, green, blue[, alpha])``
    """
    # same as getrgb, but converts the result to the given mode
    color, alpha = getrgbi(color), 255
    if isinstance(color, bool):
        return color
    else:
        if len(color) == 4:
            color, alpha = color[0:3], color[3]

        if Image.getmodebase(mode) == "L":
            r, g, b = color
            # ITU-R Recommendation 601-2 for nonlinear RGB
            # scaled to 24 bits to match the convert's implementation.
            color = (r * 19595 + g * 38470 + b * 7471 + 0x8000) >> 16
            if mode[-1] == "A":
                return True
        else:
            if mode[-1] == "A":
                return True
    return True


colormap = {
    # X11 colour table from https://drafts.csswg.org/css-color-4/, with
    # gray/grey spelling issues fixed.  This is a superset of HTML 4.0
    # colour names used in CSS 1.
    "aliceblue": "#f0f8ff",
    "antiquewhite": "#faebd7",
    "aqua": "#00ffff",
    "aquamarine": "#7fffd4",
    "azure": "#f0ffff",
    "beige": "#f5f5dc",
    "bisque": "#ffe4c4",
    "black": "#000000",
    "blanchedalmond": "#ffebcd",
    "blue": "#0000ff",
    "blueviolet": "#8a2be2",
    "brown": "#a52a2a",
    "burlywood": "#deb887",
    "cadetblue": "#5f9ea0",
    "chartreuse": "#7fff00",
    "chocolate": "#d2691e",
    "coral": "#ff7f50",
    "cornflowerblue": "#6495ed",
    "cornsilk": "#fff8dc",
    "crimson": "#dc143c",
    "cyan": "#00ffff",
    "darkblue": "#00008b",
    "darkcyan": "#008b8b",
    "darkgoldenrod": "#b8860b",
    "darkgray": "#a9a9a9",
    "darkgrey": "#a9a9a9",
    "darkgreen": "#006400",
    "darkkhaki": "#bdb76b",
    "darkmagenta": "#8b008b",
    "darkolivegreen": "#556b2f",
    "darkorange": "#ff8c00",
    "darkorchid": "#9932cc",
    "darkred": "#8b0000",
    "darksalmon": "#e9967a",
    "darkseagreen": "#8fbc8f",
    "darkslateblue": "#483d8b",
    "darkslategray": "#2f4f4f",
    "darkslategrey": "#2f4f4f",
    "darkturquoise": "#00ced1",
    "darkviolet": "#9400d3",
    "deeppink": "#ff1493",
    "deepskyblue": "#00bfff",
    "dimgray": "#696969",
    "dimgrey": "#696969",
    "dodgerblue": "#1e90ff",
    "firebrick": "#b22222",
    "floralwhite": "#fffaf0",
    "forestgreen": "#228b22",
    "fuchsia": "#ff00ff",
    "gainsboro": "#dcdcdc",
    "ghostwhite": "#f8f8ff",
    "gold": "#ffd700",
    "goldenrod": "#daa520",
    "gray": "#808080",
    "grey": "#808080",
    "green": "#008000",
    "greenyellow": "#adff2f",
    "honeydew": "#f0fff0",
    "hotpink": "#ff69b4",
    "indianred": "#cd5c5c",
    "indigo": "#4b0082",
    "ivory": "#fffff0",
    "khaki": "#f0e68c",
    "lavender": "#e6e6fa",
    "lavenderblush": "#fff0f5",
    "lawngreen": "#7cfc00",
    "lemonchiffon": "#fffacd",
    "lightblue": "#add8e6",
    "lightcoral": "#f08080",
    "lightcyan": "#e0ffff",
    "lightgoldenrodyellow": "#fafad2",
    "lightgreen": "#90ee90",
    "lightgray": "#d3d3d3",
    "lightgrey": "#d3d3d3",
    "lightpink": "#ffb6c1",
    "lightsalmon": "#ffa07a",
    "lightseagreen": "#20b2aa",
    "lightskyblue": "#87cefa",
    "lightslategray": "#778899",
    "lightslategrey": "#778899",
    "lightsteelblue": "#b0c4de",
    "lightyellow": "#ffffe0",
    "lime": "#00ff00",
    "limegreen": "#32cd32",
    "linen": "#faf0e6",
    "magenta": "#ff00ff",
    "maroon": "#800000",
    "mediumaquamarine": "#66cdaa",
    "mediumblue": "#0000cd",
    "mediumorchid": "#ba55d3",
    "mediumpurple": "#9370db",
    "mediumseagreen": "#3cb371",
    "mediumslateblue": "#7b68ee",
    "mediumspringgreen": "#00fa9a",
    "mediumturquoise": "#48d1cc",
    "mediumvioletred": "#c71585",
    "midnightblue": "#191970",
    "mintcream": "#f5fffa",
    "mistyrose": "#ffe4e1",
    "moccasin": "#ffe4b5",
    "navajowhite": "#ffdead",
    "navy": "#000080",
    "oldlace": "#fdf5e6",
    "olive": "#808000",
    "olivedrab": "#6b8e23",
    "orange": "#ffa500",
    "orangered": "#ff4500",
    "orchid": "#da70d6",
    "palegoldenrod": "#eee8aa",
    "palegreen": "#98fb98",
    "paleturquoise": "#afeeee",
    "palevioletred": "#db7093",
    "papayawhip": "#ffefd5",
    "peachpuff": "#ffdab9",
    "peru": "#cd853f",
    "pink": "#ffc0cb",
    "plum": "#dda0dd",
    "powderblue": "#b0e0e6",
    "purple": "#800080",
    "rebeccapurple": "#663399",
    "red": "#ff0000",
    "rosybrown": "#bc8f8f",
    "royalblue": "#4169e1",
    "saddlebrown": "#8b4513",
    "salmon": "#fa8072",
    "sandybrown": "#f4a460",
    "seagreen": "#2e8b57",
    "seashell": "#fff5ee",
    "sienna": "#a0522d",
    "silver": "#c0c0c0",
    "skyblue": "#87ceeb",
    "slateblue": "#6a5acd",
    "slategray": "#708090",
    "slategrey": "#708090",
    "snow": "#fffafa",
    "springgreen": "#00ff7f",
    "steelblue": "#4682b4",
    "tan": "#d2b48c",
    "teal": "#008080",
    "thistle": "#d8bfd8",
    "tomato": "#ff6347",
    "turquoise": "#40e0d0",
    "violet": "#ee82ee",
    "wheat": "#f5deb3",
    "white": "#ffffff",
    "whitesmoke": "#f5f5f5",
    "yellow": "#ffff00",
    "yellowgreen": "#9acd32",
}
colormap["blue"] = "#0000ff"