from typing import Dict
import requests
from env_server.manager.base import BaseManager

HOMO_TIMEOUT = 240
class GrassGISManager(BaseManager):
    STARTUP_WAIT_TIME = 5

    def __init__(
        self,
        *args,
        port: int = 8000,
        **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)

        assert port in range(1024, 65536)
        self.port = port
        ip = self.env.controller.vm_ip
        # legality is not checked due to inner usage
        self.base_url = f"http://{ip}:{port}"
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
        return self._get("version").text

    def operate_cmd(self) -> bool:
        return self._get("/init/cmd").text == "OK"

    def operate_map(self, grassdb: str, location: str, mapset: str) -> bool:
        return self._post("/init/map", json={
            "grassdb": grassdb,
            "location": location,
            "mapset": mapset
        }).text == "OK"

    def operate_layer(self, query: Dict[str, str]) -> bool:
        return self._post("/init/layer", json={"query": query}).text == "OK"

    def operate_scale(self, scale: int) -> bool:
        return self._post("/init/scale", json={"scale": scale}).text == "OK"

    def status_dump(self) -> Dict[str, str]:
        return self._get("/dump").json()

    def operate_gcmd(self, cmd: str, kwargs: Dict[str, str]) -> Dict:
        return self._post(
            "/gcmd",
            json={"cmd": cmd, "kwargs": kwargs}
        ).json()

    def operate_quit(self) -> bool:
        return self._post("/quit").status_code == 500

    # def _post__enter__(self) -> None:
    #     # MRO: VMManager -> VManager -> Manager -> ManagerMixin -> object
    #     super(Manager, self).__init__(self.controller.vm_ip, self.port)

    # def __enter__(self) -> Self:
    #     self = super().__enter__()
    #     self._post__enter__()
    #     return self
    def _cmd(self) -> bool:
        return self.operate_cmd()

    def _map(
        self,
        grassdb: str,
        location: str,
        mapset: str
    ) -> bool:
        return self.operate_map(grassdb, location, mapset)

    def _layer(
        self,
        query: Dict[str, str]
    ) -> bool:
        return self.operate_layer(query)

    def _scale(
        self,
        scale: int
    ) -> bool:
        return self.operate_scale(scale)
