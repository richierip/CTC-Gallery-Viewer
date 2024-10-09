# Utility file to return custom colormaps
# Each look-up table will be used to convert one intensity (luminescence) value 
#   to the RGB value of the corresponding color.
import numpy as np
import matplotlib
import re
from skimage.color import color_dict as rgb_color_dict
# from PIL import Image

''' Accepts a decimal number and returns a hex value'''
def hex_color_from_decimal(code):
    return f"{code:#0{8}x}".replace('0x','#')

def decimal_color_from_hex(code):
    return int(code.strip('#'), 16)

''' Either use the RGB named color dictionary or use a passed tuple of values'''
def create_dynamic_lut(cn, rgb_override: tuple | None = None, inverse = False):
    color_rgb = rgb_color_dict[cn.lower()] if rgb_override is None else rgb_override
    if inverse:
        colors = np.linspace(start=[1, 1, 1, 1],stop=list(color_rgb)+[1],num=256,endpoint=True)
    else:
        colors = np.linspace(start=[0, 0, 0, 1],stop=list(color_rgb)+[1],num=256,endpoint=True)
    return colors

def create_dynamic_cm(cn, inverse=False, rgb_override = None):
    colors = create_dynamic_lut(cn,rgb_override, inverse)
    if inverse:name = f'{cn} inverse'
    else: name = cn
    dcm = {
        'colors': colors,
        'name': name,
        'interpolation': 'linear'}
    return dcm

cm_dict = {name : create_dynamic_cm(name) for name in rgb_color_dict.keys()}
cm_dict.update({name+" inverse" : create_dynamic_cm(name, inverse = True) for name in rgb_color_dict.keys()})
cm_dict.update({name.capitalize() : val for name, val in cm_dict.items()})

def retrieve_cm(cm_name):
    return cm_dict[cm_name]

# X11 colour table from https://drafts.csswg.org/css-color-4/, with
# gray/grey spelling issues fixed.  This is a superset of HTML 4.0
# colour names used in CSS 1.
colormap = {
    # "none": "#000000",
    "gray": "#808080",
    "purple": "#800080",
    "blue": "#0000ff",
    "green": "#008000",
    "orange": "#ffa500",
    "red": "#ff0000",
    "yellow": "#ffff00",
    "cyan": "#00ffff",
    "pink": "#ffc0cb",
    "aliceblue": "#f0f8ff",
    "antiquewhite": "#faebd7",
    "aqua": "#00ffff",
    "aquamarine": "#7fffd4",
    "azure": "#f0ffff",
    "beige": "#f5f5dc",
    "bisque": "#ffe4c4",
    "black": "#000000",
    "blanchedalmond": "#ffebcd",
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
    "grey": "#808080",
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
    "orangered": "#ff4500",
    "orchid": "#da70d6",
    "palegoldenrod": "#eee8aa",
    "palegreen": "#98fb98",
    # "paleturquoise": "#afeeee", # Not in skimage rgb2color
    "palevioletred": "#db7093",
    "papayawhip": "#ffefd5",
    "peachpuff": "#ffdab9",
    "peru": "#cd853f",
    "plum": "#dda0dd",
    "powderblue": "#b0e0e6",
    # "rebeccapurple": "#663399", # Not in skimage rgb2color
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
    "yellowgreen": "#9acd32",
}
colormap["blue"] = "#0000ff" # Why?
colormap_titled = {name.title(): val for name, val in colormap.items()}
colormap.update( {name.title(): val for name, val in colormap.items()} ) # Avoid capitalization issues
colormap_decimal = {name : decimal_color_from_hex(val) for name,val in colormap.items() }


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

        if getmodebase(mode) == "L":
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

def getmodebase(mode):
    """
    Gets the "base" mode for given mode.  This function returns "L" for
    images that contain grayscale data, and "RGB" for images that
    contain color data.

    :param mode: Input mode.
    :returns: "L" or "RGB".
    :exception KeyError: If the input mode was not a standard mode.
    """
    return getmode(mode).basemode


# PIL functions needed for the above code

#
# The Python Imaging Library.
# $Id$
#
# standard mode descriptors
#
# History:
# 2006-03-20 fl   Added
#
# Copyright (c) 2006 by Secret Labs AB.
# Copyright (c) 2006 by Fredrik Lundh.
#
# See the README file for information on usage and redistribution.
#

import sys

# mode descriptor cache
_modes = None


class ModeDescriptor:
    """Wrapper for mode strings."""

    def __init__(self, mode, bands, basemode, basetype, typestr):
        self.mode = mode
        self.bands = bands
        self.basemode = basemode
        self.basetype = basetype
        self.typestr = typestr

    def __str__(self):
        return self.mode


def getmode(mode):
    """Gets a mode descriptor for the given mode."""
    global _modes
    if not _modes:
        # initialize mode cache
        modes = {}
        endian = "<" if sys.byteorder == "little" else ">"
        for m, (basemode, basetype, bands, typestr) in {
            # core modes
            # Bits need to be extended to bytes
            "1": ("L", "L", ("1",), "|b1"),
            "L": ("L", "L", ("L",), "|u1"),
            "I": ("L", "I", ("I",), endian + "i4"),
            "F": ("L", "F", ("F",), endian + "f4"),
            "P": ("P", "L", ("P",), "|u1"),
            "RGB": ("RGB", "L", ("R", "G", "B"), "|u1"),
            "RGBX": ("RGB", "L", ("R", "G", "B", "X"), "|u1"),
            "RGBA": ("RGB", "L", ("R", "G", "B", "A"), "|u1"),
            "CMYK": ("RGB", "L", ("C", "M", "Y", "K"), "|u1"),
            "YCbCr": ("RGB", "L", ("Y", "Cb", "Cr"), "|u1"),
            # UNDONE - unsigned |u1i1i1
            "LAB": ("RGB", "L", ("L", "A", "B"), "|u1"),
            "HSV": ("RGB", "L", ("H", "S", "V"), "|u1"),
            # extra experimental modes
            "RGBa": ("RGB", "L", ("R", "G", "B", "a"), "|u1"),
            "BGR;15": ("RGB", "L", ("B", "G", "R"), endian + "u2"),
            "BGR;16": ("RGB", "L", ("B", "G", "R"), endian + "u2"),
            "BGR;24": ("RGB", "L", ("B", "G", "R"), endian + "u3"),
            "BGR;32": ("RGB", "L", ("B", "G", "R"), endian + "u4"),
            "LA": ("L", "L", ("L", "A"), "|u1"),
            "La": ("L", "L", ("L", "a"), "|u1"),
            "PA": ("RGB", "L", ("P", "A"), "|u1"),
        }.items():
            modes[m] = ModeDescriptor(m, bands, basemode, basetype, typestr)
        # mapping modes
        for i16mode, typestr in {
            # I;16 == I;16L, and I;32 == I;32L
            "I;16": "<u2",
            "I;16S": "<i2",
            "I;16L": "<u2",
            "I;16LS": "<i2",
            "I;16B": ">u2",
            "I;16BS": ">i2",
            "I;16N": endian + "u2",
            "I;16NS": endian + "i2",
            "I;32": "<u4",
            "I;32B": ">u4",
            "I;32L": "<u4",
            "I;32S": "<i4",
            "I;32BS": ">i4",
            "I;32LS": "<i4",
        }.items():
            modes[i16mode] = ModeDescriptor(i16mode, ("I",), "L", "L", typestr)
        # set global mode cache atomically
        _modes = modes
    return _modes[mode]
