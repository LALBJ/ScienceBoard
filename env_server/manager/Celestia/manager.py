import json
from typing import Any, Dict
import requests
from env_server.manager.base import BaseManager

HOMO_TIMEOUT = 240
class CelestiaManager(BaseManager):
    STARTUP_WAIT_TIME = 5

    def __init__(self, env):
        super().__init__(env)
        # legality is not checked due to inner usage
        ip = self.env.controller.vm_ip
        self.base_url = f"http://{ip}:{self.port}"
        self._get = lambda path: requests.get(
            self.base_url + path,
            timeout=HOMO_TIMEOUT
        )
        self._post = lambda path, **kwargs: requests.post(
            self.base_url + path,
            timeout=HOMO_TIMEOUT,
            **kwargs
        )

    def status_version(self) -> str:
        return self._get("/version").text

    def status_dump(self, query) -> Dict[str, Any]:
        return self._post("/dump", data=json.dumps(query)).json()