"""This module provides function for generating arithmetic CAPTCHA."""
from math import sqrt
import random

import inflect

ENGINE = inflect.engine()


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
            return ENGINE.number_to_words(self.value, andword='')
        str_list = []
        for child in self.children:
            if self.value == '*' and child.value == '+':
                str_list.append("({})".format(str(child)))
            else:
                str_list.append(str(child))
        return " {} ".format(self.value).join(str_list)


def generate_captcha():
    """Generate arithmetic CAPTCHA."""
    result = random.randrange(5, 100)
    return (str(ArithmeticTree.generate(result, 5)), result,)


random.seed()
