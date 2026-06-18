# -*- coding: utf-8 -*-
"""Sphinx 配置 — StockQuant 项目文档"""
import os
import sys

# 项目根目录加入 sys.path（autodoc 需要）
sys.path.insert(0, os.path.abspath("../.."))

project = "StockQuant"
copyright = "2026, StockQuant Team"
author = "StockQuant Team"

# 短版本
version = "1.0"
release = "1.0.0"

# 扩展
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
]

# 主题
html_theme = "alabaster"
html_static_path = ["_static"]

# autodoc 配置
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
}

# Napoleon 配置（支持 Google/NumPy 风格 docstring）
napoleon_google_docstring = True
napoleon_numpy_docstring = True

# intersphinx
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

# 中文支持
language = "zh_CN"
html_encoding = "utf-8"
