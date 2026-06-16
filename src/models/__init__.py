import os
import importlib

# Import dynamically model files as submodules and create a dictionary that points at them by name.

# Available models list.
available_models = {} 

for file in os.listdir(os.path.dirname(__file__)):
    mod_name = file.removesuffix(".py")
    if mod_name in ("__init__", "__pycache__"): continue
    if mod_name[0] == '.': continue

    cur_mod = importlib.import_module('.' + mod_name, package=__name__)

    available_models[cur_mod.name] = cur_mod
