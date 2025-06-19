import os
import numpy as np

Apps = ["Celestia", "ChimeraX"]
root_dir = "/data/code/ScienceBoard/logs/tars_dpo-vm-screenshot"
preds = []
app_preds = {"Celestia": [], "ChimeraX": [], "GrassGIS": [], "KAlgebra": [], "Lean": []}
for app in Apps:
    task_dirs = os.listdir(os.path.join(root_dir, app))
    
    for task_dir in task_dirs:
        result_dir = os.path.join(root_dir, app, task_dir, "result.out")
        try:
            with open(result_dir) as f:
                data = float(f.read().strip())
                preds.append(data)
                app_preds[app].append(data) 
        except FileNotFoundError:
            print(f"{result_dir} not found")
            preds.append(0)
            app_preds[app].append(0) 
import ipdb; ipdb.set_trace()