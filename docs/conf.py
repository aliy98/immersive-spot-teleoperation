# Configuration file for the Sphinx documentation of immersive-spot-teleoperation.
# https://github.com/aliy98/immersive-spot-teleoperation

import os
import sys

sys.path.insert(0, os.path.abspath(".."))
sys.path.insert(0, os.path.abspath("../scripts"))
sys.path.insert(0, os.path.abspath("../scripts/spot_client"))

project = "immersive-spot-teleoperation"
copyright = "2025, RICE Lab — DIBRIS, University of Genova"
author = "Ali Yousefi, Carmine Tommaso Recchiuto, Antonio Sgorbissa"
release = "1.0.0"
version = "1.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.mathjax",
    "sphinx.ext.intersphinx",
    "sphinx.ext.todo",
    "sphinx.ext.githubpages",
    "myst_parser",
    "sphinx_copybutton",
    "sphinx_rtd_theme",
]

myst_enable_extensions = [
    "dollarmath",
    "amsmath",
    "colon_fence",
    "deflist",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_theme_options = {
    "navigation_depth": 4,
    "collapse_navigation": False,
    "sticky_navigation": True,
    "style_external_links": True,
}
html_title = "Immersive Spot Teleoperation"
html_short_title = "Spot Teleop"
html_logo = None
html_favicon = None

mathjax3_config = {
    "tex": {
        "macros": {
            "ROB": r"{\mathrm{ROB}}",
            "HMD": r"{\mathrm{HMD}}",
        }
    }
}

todo_include_todos = False
napoleon_google_docstring = True
napoleon_numpy_docstring = True
autodoc_mock_imports = [
    "bosdyn",
    "cv2",
    "paho",
    "do_mpc",
    "casadi",
    "matplotlib",
    "scipy",
    "numpy",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}
