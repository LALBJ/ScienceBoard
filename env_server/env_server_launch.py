import importlib
import os
import sys
import json
import base64
import logging
import asyncio
import datetime
from desktop_env.desktop_env import DesktopEnv
from env_server.env import SciEnv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


#  Logger Configs {{{ #
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
stdout_handler = logging.StreamHandler(sys.stdout)
# stdout_handler.setLevel(logging.INFO)
stdout_handler.setLevel(logging.DEBUG)
stdout_handler.addFilter(logging.Filter("vm"))
logger.addHandler(stdout_handler)


CONFIG_BASE_DIR = "/data/code/ScienceBoard/tasks/VM"
VM_DIR = "/nvme/sushiqian/osworld-codebase/docker_vm_data"
INIT_NAME = 'sci_bench'
env = None


def byte_to_b64(byte_data) -> str:
    img_b64 = base64.b64encode(byte_data).decode("utf-8")
    return img_b64

def get_json_data(request: Request):
    return asyncio.run(request.json())

def get_time():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


app = FastAPI()

@app.get("/")
def read_root():
    return {"info": "ScienceBench env api"}


@app.post("/start")
def start(request: Request):
    try:
        data = get_json_data(request)
        vm_path = data.get("vm_path", "/data/code/VM/Ubuntu.vmx")
        print(f"[{get_time()}] [env api] vitual machine starting...")
        global env
        env = DesktopEnv(
            provider_name="vmware",
            region=None,
            path_to_vm=vm_path,
            snapshot_name=INIT_NAME,
            action_space="pyautogui",
            headless=True
        )


        print(f"[{get_time()}] [env api] vitual machine done.")
        return JSONResponse({"success": True})

    except Exception as e:
        print(f"[{get_time()}] [env api] start failed:", e)
        return JSONResponse({"success": False, "message": str(e)})

@app.post("/get_task_config")
def get_task_config(request: Request):
    try:
        data = get_json_data(request)
        domain = data.get("domain")
        example_id = data.get("example_id")
        config_file = os.path.join(CONFIG_BASE_DIR, f"{domain}/{example_id}.json")
        with open(config_file, "r", encoding="utf-8") as f:
            task_config = json.load(f)
        return JSONResponse({"task_config": task_config, "success": True})
    except Exception as e:
        print(f"[{get_time()}] [env api] get task_config failed:", e)
        return JSONResponse({"success": False, "message": str(e)})

@app.post("/reset")
def reset(request: Request):
    # try:
        data = get_json_data(request)
        task_config = data.get("task_config", None)
        if task_config is None:
            if 'domain' in data and 'example_id' in data:
                domain = data.get("domain")
                example_id = data.get("example_id")
                config_file = os.path.join(CONFIG_BASE_DIR, f"{domain}/{example_id}.json")
                with open(config_file, "r", encoding="utf-8") as f:
                    task_config = json.load(f)

        print(f"[{get_time()}] [env api] env reset starting...")
        module = importlib.import_module('env_server.manager')
        global manager
        manager = module.function_map[task_config["type"]](env)
        obs = manager.reset(task_config=task_config)
        print(f"[{get_time()}] [env api] env reset done...")
        screenshot = obs['screenshot']
        screenshot_b64 = byte_to_b64(screenshot)
        obs['screenshot'] = screenshot_b64
        return JSONResponse({"obs": obs, "success": True})

    # except Exception as e:
    #     print(f"[{get_time()}] [env api] reset failed:", e)
    #     return JSONResponse({"success": False, "message": str(e)})


@app.get("/evaluate")
def evaluate():
    try:
        metric = manager.evaluate()
        return JSONResponse({"metric": metric, "success": True})
    except Exception as e:
        print(f"[{get_time()}] [env api] evaluate failed:", e)
        import traceback; traceback.print_exc()
        return JSONResponse({"success": False, "message": str(e)})

@app.post("/close")
def close():
    if manager is None:
        print(f"[{get_time()}] [env api] No env to close.")
        return JSONResponse({"success": True})
    try:
        manager.close()
        print(f"[{get_time()}] [env api] vitual machine close.")
        return JSONResponse({"success": True})
    except Exception as e:
        print(f"[{get_time()}] [env api] closing vitual machine failed:", e)
        return JSONResponse({"success": False, "message": str(e)})
