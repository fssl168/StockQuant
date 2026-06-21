project = 'StockQuant'
copyright = '2026, StockQuant'
author = 'StockQuant Team'
release = '2.0.0'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

import os
import sys
sys.path.insert(0, os.path.abspath('../..'))
