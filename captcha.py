# -*- coding: utf-8 -*-
"""This module provides function for generating arithmetic CAPTCHA."""
import io
import math
import random
import subprocess
from uuid import uuid4

from bs4 import BeautifulSoup
from cairosvg import svg2png
import matplotlib
from matplotlib.backends.backend_svg import FigureCanvasSVG
from matplotlib.figure import Figure

DEFAULT_FONT_SIZE_PT = 12
MATHJAX_FONT_SIZE_MULTIPLIER = 1.24
matplotlib.rcParams.update(
    {'font.size': DEFAULT_FONT_SIZE_PT * MATHJAX_FONT_SIZE_MULTIPLIER})
matplotlib.rcParams["mathtext.fontset"] = "cm"

DEFAULT_DPI = 96
SPOT_RELATIVE_SIZE = 0.025


def is_prime(num):
    """Check if `num` is prime number (trial division)."""
    if num < 2:
        return False
    for div in range(2, int(math.sqrt(num)) + 1):
        if num % div == 0:
            return False
    return True


class ArithmeticTree:
    """Class that represents trees for arithmetical expressions."""
    value = 0
    children = None

    def __init__(self, value=None):
        if value:
            self.value = value

    def add_new_nodes(self):
        """
        Try to add new nodes in tree;
        return `True` if successful,
        otherwise `False`.
        """
        choice = random.randrange(3)
        if not isinstance(self.value, int):
            checked = set()
            child_num = len(self.children)
            while len(checked) != child_num:
                index = random.randrange(child_num)
                checked.add(index)
                if random.choice(self.children).add_new_nodes():
                    return True
            return False
        if choice == 1 and self.value >= 2:
            num = self.value
            addendum = random.randrange(1, num)
            self.children = [ArithmeticTree(addendum),
                             ArithmeticTree(num - addendum)]
            self.value = '+'
            return True
        if choice == 2 and self.value >= 4 and not is_prime(self.value):
            num = self.value
            divisor = num - 1
            while num % divisor != 0:
                divisor = random.randrange(2, num)
            self.children = [ArithmeticTree(divisor),
                             ArithmeticTree(num // divisor)]
            self.value = '*'
            return True
        return False

    @staticmethod
    def generate(num, max_operands):
        """
        Generate tree for expression
        which contains `max_operands` operands
        and whose value is equal to `num`.
        """
        tree = ArithmeticTree()
        tree.children = []
        tree.value = num
        cur_operands = 1
        while cur_operands < max_operands:
            if tree.add_new_nodes():
                cur_operands += 1
        return tree

    def __str__(self):
        if isinstance(self.value, int):
            return str(self.value)
        str_list = []
        for child in self.children:
            if self.value == '*' and child.value == '+':
                str_list.append("({})".format(str(child)))
            else:
                str_list.append(str(child))
        return " {} ".format(self.value.replace('*', "\\cdot")).join(str_list)


def transform_image(svg_text):
    """Apply transformation to the given SVG image."""
    soup = BeautifulSoup(svg_text, "html5lib")
    svg_elem = soup.find("svg")

    figure_elem = svg_elem.find(id="figure_1")
    # Strip "pt" from the end
    img_width = float(svg_elem["width"][:-2])
    img_height = float(svg_elem["height"][:-2])

    spot_absolute_size = SPOT_RELATIVE_SIZE * img_width
    # Add some random colored circle spots
    for _ in range(5):
        circle = soup.new_tag(
            "circle",
            cx=str(random.uniform(
                spot_absolute_size, img_width - spot_absolute_size)),
            cy=str(random.uniform(
                spot_absolute_size, img_height - spot_absolute_size)),
            r=str(spot_absolute_size),
            fill="#{0:06X}".format(random.randrange(2 ** 24)))
        circle["fill-opacity"] = str(random.uniform(0.5, 1))
        figure_elem.append(circle)

    # Skew that!
    skews = (random.randint(-20, 20), random.randint(-20, 20),)
    figure_elem["transform"] = "skewX({})skewY({})".format(*skews)

    basis = [
        [1, 0],
        [0, 1]
    ]
    basis[1][0] += math.tan(math.radians(skews[0])) * basis[0][0]
    basis[1][1] += math.tan(math.radians(skews[0])) * basis[0][1]
    basis[0][0] += math.tan(math.radians(skews[1])) * basis[1][0]
    basis[0][1] += math.tan(math.radians(skews[1])) * basis[1][1]

    # "BP" means "bounding parallelogram"
    bp_vertices = [
        (0, 0),
        (basis[0][0] * img_width, basis[0][1] * img_width),
        (basis[0][0] * img_width + basis[1][0] * img_height,
         basis[0][1] * img_width + basis[1][1] * img_height),
        (basis[1][0] * img_height, basis[1][1] * img_height),
    ]
    coords = tuple(zip(*bp_vertices))
    viewbox = [
        min(*coords[0]),
        min(*coords[1]),
        max(*coords[0]),
        max(*coords[1]),
    ]
    viewbox[2] -= viewbox[0]
    viewbox[3] -= viewbox[1]
    svg_elem["width"] = str(viewbox[2]) + "pt"
    svg_elem["height"] = str(viewbox[3]) + "pt"
    svg_elem["viewBox"] = ' '.join(map(str, viewbox))

    return (str(svg_elem), svg_elem["width"], svg_elem["height"],)


def generate_captcha(webp=False, uuid_set=None, img_dir="."):
    """Generate arithmetic CAPTCHA."""
    result = random.randrange(5, 100)
    tree = ArithmeticTree.generate(result, 5)

    fig = Figure()
    # pylint: disable=unused-variable
    canvas = FigureCanvasSVG(fig)
    fig.text(.5, .5, '$' + str(tree) + '$')
    stream = io.StringIO()
    fig.savefig(stream, transparent=True, bbox_inches="tight", pad_inches=0)
    svg_text, img_width, img_height = transform_image(stream.getvalue())

    filename = uuid4().hex
    if uuid_set:
        while filename in uuid_set:
            filename = uuid4().hex
    # Picture is upscaled to prevent blur
    svg2png(bytestring=svg_text,
            write_to=img_dir + '/' + filename + ".png",
            dpi=DEFAULT_DPI * 2)
    if webp:
        subprocess.run(["cwebp",
                        "-quiet",
                        "-z", "9",
                        img_dir + '/' + filename + ".png",
                        "-o", img_dir + '/' + filename + ".webp"])

    html_text = """
                    <picture>
                        {}<img src="/captcha/{}.png" style="vertical-align: middle; width: {};">
                    </picture>
                """.format("""\
<source srcset="/captcha/{}.webp" type="image/webp">
                        """.format(filename) if webp else "",
                           filename, img_width)

    return (html_text, result, filename,)


random.seed()
