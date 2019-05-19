"""This module provides function for generating arithmetic CAPTCHA."""
from math import sqrt
import io
import random

import matplotlib
from matplotlib.backends.backend_svg import FigureCanvasSVG
from matplotlib.figure import Figure
# from matplotlib import font_manager

DEFAULT_FONT_SIZE_PT = 12
MATHJAX_FONT_SIZE_MULTIPLIER = 1.24
matplotlib.rcParams.update(
    {'font.size': DEFAULT_FONT_SIZE_PT * MATHJAX_FONT_SIZE_MULTIPLIER})
matplotlib.rcParams["mathtext.fontset"] = "cm"
# FONTPROP = font_manager.FontProperties(
#     fname="site/static/js/MathJax/fonts/HTML-CSS/TeX/\
# otf/MathJax_Main-Regular.otf")


def is_prime(num):
    """Check if `num` is prime number (trial division)."""
    if num < 2:
        return False
    for div in range(2, int(sqrt(num)) + 1):
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


def generate_captcha():
    """Generate arithmetic CAPTCHA."""
    result = random.randrange(5, 100)
    tree = ArithmeticTree.generate(result, 5)

    fig = Figure()
    # pylint: disable=unused-variable
    canvas = FigureCanvasSVG(fig)
    fig.text(.5, .5, '$' + str(tree) + '$')
    # fig.text(.5, .5, '$' + str(tree) + '$', fontproperties=FONTPROP)
    stream = io.StringIO()
    fig.savefig(stream, transparent=True, bbox_inches="tight", pad_inches=0)

    return (stream.getvalue(), result,)


random.seed()
