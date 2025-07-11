

from typing import Any, Dict, List, Union
import requests
from env_server.manager.base import BaseManager

HOMO_TIMEOUT = 240
class KAlgebraManager(BaseManager):
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

    # def _post__enter__(self) -> None:
    #     # MRO: VMManager -> VManager -> Manager -> ManagerMixin -> object
    #     super(Manager, self).__init__(self.controller.vm_ip, self.port)

    # def __enter__(self) -> Self:
    #     self = super().__enter__()
    #     self._post__enter__()
    #     return self

    def status_version(self) -> str:
        return self._get("/version").text

    def status_vars(self) -> Dict[str, str]:
        return self._get("/vars").json()

    def status_func(
        self,
        points: List[List[float]],
        dim: int = None
    ) -> List[Dict["str", Union[bool, str]]]:
        if dim is None:
            dim = len(points[0])

        result = self._post(f"/func/{dim}d", json=points).json()
        if isinstance(result, dict):
            result = [result]
        return result

    def operate_tab(self, index: int) -> bool:
        assert isinstance(index, int)
        assert index >= 0 and index < 4
        return self._post("/tab", json=index).text == "OK"

    def operate_func2d(self, expr: str) -> bool:
        return self._post("/add/2d", data=expr).text == "OK"

    def operate_func3d(self, expr: str) -> bool:
        return self._post("/add/3d", data=expr).text == "OK"
    
    def _tab(self, index: int) -> bool:
        return self.manager.operate_tab(index)

    def _func_2d(self, expr: str) -> bool:
        return self.manager.operate_func2d(expr)

    def _func_3d(self, expr: str) -> bool:
        return self.manager.operate_func3d(expr)

    @staticmethod
    def is_near(left: Any, right: Any) -> bool:
        return abs(float(left) - float(right)) <= 1e-6
