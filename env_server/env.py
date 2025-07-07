import importlib
import logging
import re
import time
import os
import functools

from typing import Callable, Any, Optional, Tuple
from typing import List, Dict, Union

import requests

from desktop_env.desktop_env  import DesktopEnv

from sci.base import init
from sci.base.utils import TypeSort

logger = logging.getLogger("desktopenv.env")

INIT_NAME = 'sci_bench'
PATH_LIKE = "«PORTLIKE»"
SERVER_PORT = 5000
HOMO_TIMEOUT = 240
EARLY_STOP = "stop"
class SciEnv:
    def __init__(self, vm_path, headless=True):
        self.path = vm_path
        self.env = DesktopEnv(
            provider_name="vmware",
            region=None,
            path_to_vm=self.path,
            snapshot_name=INIT_NAME,
            action_space="pyautogui",
            headless=headless
        )

    #     self.snapshot_name = INIT_NAME
        
    #     self._traj_no: int = -1
    #     self._step_no: int = 0
    #     self.action_history: List[Dict[str, any]] = []

    #     ## TODO: make this configurable
    #     self.port = 8000

    # def reset(self, task_config: Optional[Dict[str, Any]] = None, seed=None, options=None) -> Dict[str, Any]:
    #     # Reset to certain task in OSWorld
    #     logger.info("Resetting environment...")
    #     logger.info("Switching task...")
    #     logger.info("Setting counters...")
    #     self._traj_no += 1
    #     self._step_no = 0
    #     self.action_history.clear()

    #     logger.info("Reverting to snapshot to {}...".format(self.snapshot_name))
    #     self.env.snapshot_name = self.snapshot_name
    #     self.env._revert_to_snapshot()
    #     logger.info("Starting emulator...")
    #     self.env._start_emulator()
    #     logger.info("Emulator started.")
    #     self.controller = self.env.controller
    #     logger.info("Reset API Server in the virtual machine...")
    #     response = self._execute(
    #         command="/bin/bash /home/user/server/reset.sh",
    #         shell=True
    #     )
    #     print("API server reset response:", response)

    #     local_name = lambda func: f"_{func}"
    #     global_name = lambda func: f"{self.sort.lower()}_{func}"

    #     def func(func: str, wait: int = 0, **kwargs):
    #         handler = getattr(self, local_name(func)) \
    #             if hasattr(self, local_name(func)) \
    #             else getattr(init, global_name(func))

    #         # if handler.__name__.startswith(TypeSort.Sort.VM.name.lower()):
    #         #     kwargs["manager"] = self.manager

    #         result = handler(**kwargs)
    #         time.sleep(2)
    #         return result
        
    #     initialize = task_config.get("initialize", [])
    #     for init_item in initialize:
    #             succeed = False
    #             succeed = func(**init_item)
        
    #     print("logging succeed", succeed)
    #     time.sleep(2)
    #     observation = self._get_obs()

    #     module = importlib.import_module('env_server.eval')
    #     self.metric = module.function_map[task_config["type"]](self, task_config)

    #     return observation
    
    # def step(self, action, pause=0.5):
    #     self._step_no += 1
    #     self.action_history.append(action)

    #     reward = 0  # todo: Define reward calculation for each example
    #     done = False  # todo: Define episode termination condition for each example
    #     info = {}

    #     # handle the special actions
    #     if action in ['WAIT', 'FAIL', 'DONE'] or (type(action) == dict and action['action_type'] in ['WAIT', 'FAIL', 'DONE']):
    #         if action == 'WAIT':
    #             time.sleep(pause)
    #         elif action == 'FAIL':
    #             done = True
    #             info = {"fail": True}
    #         elif action == 'DONE':
    #             done = True
    #             info = {"done": True}

    #     if action in ['WAIT', 'FAIL', 'DONE']:
    #         self.controller.execute_action(action)
    #     else:
    #         # the set of all possible python commands insides `pyautogui`
    #         self.controller.execute_python_command(action)

    #     observation = self._get_obs()

    #     return observation, reward, done, info
    
    # def evaluate(self):
    #     # eval_index = 0

    #     # while eval_index < len(self.evaluate):
    #     #     eval_item = self.evaluate[eval_index]
    #     #     if eval_item["type"] != EARLY_STOP:
    #     #         eval_index += 1
    #     #     elif eval_item["value"] != stop_type.__name__:
    #     #         self.vlog.info(f"Evaluation failed at stop type.")
    #     #         return False
    #     #     elif eval_item["value"] == Primitive.ANS.__name__ \
    #     #         and eval_item["args"] != stop_args:
    #     #         self.vlog.info(f"Evaluation failed at ANS.")
    #     #         return False
    #     #     else:
    #     #         del self.evaluate[eval_index]

    #     # if len(self.evaluate) > 0:
    #     #     raise Task.PlannedNotImplemented()
    #     # else:
    #     result = self.metric.eval()
    #     return result

    # def _get_obs(self):
    #     # We provide screenshot, accessibility_tree (optional), terminal (optional), and instruction.
    #     # can be customized and scaled
        
    #     ## TODO: make this configurable
    #     self.require_a11y_tree = False
    #     self.require_terminal = False
    #     self.instruction = ""
    #     return {
    #         "screenshot": self.controller.get_screenshot(),
    #         "accessibility_tree": self.controller.get_accessibility_tree() if self.require_a11y_tree else None,
    #         "terminal": self.controller.get_terminal_output() if self.require_terminal else None,
    #         "instruction": self.instruction
    #     }

    # # def step(self, action):
    # #     return self.env.step(action)

    # # requires VMManager to possess "port" attribute
    # def __fill_port(self, command: str) -> str:
    #     assert isinstance(command, str)
    #     return command.replace(PATH_LIKE, str(self.port)) \
    #         if hasattr(self, "port") else command
    
    # def _request(self, query: str, param: Dict["str", Any]) -> requests.Response:
    #     # query string example: "POST:8080/api/version"
    #     # correspond to request.post(f"http://{base}:{port}{path}")
    #     reg_exp = r'(GET|POST)(:\d+)?(.+)'
    #     request_method, port, pathname = re.search(reg_exp, query).groups()
    #     if port is None:
    #         port = f":{SERVER_PORT}"

    #     request = getattr(requests, request_method.lower())
    #     base = f"http://{self.controller.vm_ip}"

    #     if request_method == "POST":
    #         if "headers" not in param:
    #             param["headers"] = {}
    #         if "Content-Type" not in param["headers"]:
    #             param["headers"]["Content-Type"] = "application/json"

    #     print("base url", base + port + pathname)
    #     print("request payload", param)
    #     return request(
    #         base + port + pathname,
    #         timeout=HOMO_TIMEOUT,
    #         **param
    #     )
            
    # # OSWorld's request does not check success
    # # rewrite requests to make up this flaw
    # @staticmethod
    # def _request_factory(query: str):
    #     def _request_decorator(method: Callable) -> Callable:
    #         @functools.wraps(method)
    #         def _request_wrapper(self: "SciEnv", **kwargs) -> bool:
    #             param: Dict["str", Any] = method(self, **kwargs)
    #             try:
    #                 response = self._request(query, param)
    #                 succeed = response.status_code == 200
    #                 if not succeed:
    #                     print(f"Failed when requesting {query}: {response.status_code}")
    #                     print(response.json())
    #                 return succeed
    #             except Exception as err:
    #                 print(f"Error when requesting {query}: {err}")
    #                 return False
    #         return _request_wrapper
    #     return _request_decorator

    # @_request_factory("POST/setup/execute")
    # def _execute(self, command: Union[str, List[str]], shell: bool = False) -> Dict:
    #     assert isinstance(shell, bool)
    #     if isinstance(command, list):
    #         for index, part in enumerate(command):
    #             command[index] = self.__fill_port(part)
    #     else:
    #         command = self.__fill_port(command)

    #     print("execute payload", command, shell)
    #     return {
    #         "json": {
    #             "command": command,
    #             "shell": shell
    #         }
    #     }

    # @_request_factory("POST/setup/launch")
    # def _launch(self, command: Union[str, List[str]], shell: bool = False) -> Dict:
    #     return self._execute.__wrapped__(self, command, shell)

    # @_request_factory("POST/opt")
    # def _opt(self, depth: int) -> Dict:
    #     return {
    #         "json": {
    #             "depth": depth
    #         }
    #     }

    # @_request_factory("POST/append")
    # def _append(self, path: str, content: str) -> Dict:
    #     return {
    #         "json": {
    #             "path": path,
    #             "content": content
    #         }
    #     }
