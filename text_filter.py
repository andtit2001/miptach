# -*- coding: utf-8 -*-
"""
This module currently contains the only text filter.
"""
from copy import copy

from bs4 import BeautifulSoup
import bleach
from bleach_whitelist import markdown_attrs, markdown_tags, standard_styles
from markdown import markdown
from mdx_math import MathExtension

ALLOWED_TAGS = copy(markdown_tags)
ALLOWED_TAGS.remove("img")
ALLOWED_TAGS.append("script")
ALLOWED_ATTRS = copy(markdown_attrs)
ALLOWED_ATTRS["script"] = ["type"]
ALLOWED_ATTRS["span"] = ["class"]


def markdown_to_html(text):
    """
    Text filter which does the following:
    - Process text with Markdown
    - Process result with Bleach
    - Delete all non-MathJax scripts
    """
    html_text = markdown(text,
                         extensions=[MathExtension(
                             enable_dollar_delimiter=True,
                             add_preview=True)],
                         output_format="html5")
    clean_text = bleach.clean(html_text,
                              ALLOWED_TAGS, ALLOWED_ATTRS, standard_styles)
    soup = BeautifulSoup(clean_text, "html5lib")
    for script_tag in soup.find_all("script"):
        if script_tag.attrs.get("type", False) != "math/tex":
            script_tag.extract()
    for span_tag in soup.find_all("span"):
        if span_tag.attrs.get("class", False)\
                and "MathJax_Preview" not in span_tag.attrs["class"]:
            span_tag.extract()
    return str(soup)
