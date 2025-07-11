import json
import os
import time
from typing import Dict, List, Tuple, Union
from env_server.manager.base import BaseManager

SERVER_PORT=5000
class ChimeraXManager(BaseManager):
    def __init__(
        self,
        *args,
        port: int = 8000,
        **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)

        assert port in range(1024, 65536)
        self.port = port

    def chimerax_execute(self, command: str) -> Dict:
        # return self._request(
        #     f"POST:{SERVER_PORT}/chimerax/run",
        #     param={"json": {"command": command}}
        # ).json()
        # ToDO: 有没有必要加上时间间隔？
        time.sleep(1)
        res = self._request(
            f"POST:{SERVER_PORT}/chimerax/run",
            param={"json": {"command": command}}
        )
        return res.json()

    def states_dump(self) -> dict:
        timestamp = str(int(time.time() * 1000))
        guest_dir = "/home/user/Downloads"
        guest_file = os.path.join(guest_dir, f"{timestamp}.json")

        assert self._call(f"states {guest_dir} {timestamp}")[1]
        return json.loads(self.read_file(guest_file))

    def _call(
        self,
        command: str
    ) -> Tuple[List[str], bool]:
        response = self.chimerax_execute(command)
        return (
            response["log messages"]["note"],
            response["error"] is None
        )
    
    def _destroy(self) -> bool:
        _, code = self._call(f"destroy")
        return code

    def _open(self, name: str) -> bool:
        _, code = self._call(f"open {name}")
        return code

    def _turn(self, axis: str, angle: int) -> bool:
        _, code = self._call(f"turn {axis} {angle}")
        return code

    def _alphafold_match(self, name: str) -> bool:
        _, code = self._call(f"alphafold match {name}")
        return code

    def _color(self, style: str) -> bool:
        command = f"color {style}" if style != "rainbow" else style
        _, code = self._call(command)
        return code

    def _clear_log(self) -> bool:
        _, code = self._call(f"log clear")
        return code
