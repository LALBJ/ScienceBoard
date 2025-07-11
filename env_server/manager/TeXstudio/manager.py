
from time import sleep
from env_server.manager.base import BaseManager

SERVER_PORT = 5000
class TeXstudioManager(BaseManager):
    def __init__(
        self,
        *args,
        port: int = 8000,
        **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)

        assert port in range(1024, 65536)
        self.port = port

    def _chimerax_execute(self, command: str):
        sleep(1)
        return self._request(
            f"POST:{SERVER_PORT}/chimerax/run",
            param={"json": {"command": command}}
        ).json()["error"] is None

    def _chimerax_open(self, name: str) -> bool:
        return self._chimerax_execute(f"open {name}")

    def _chimerax_turn(self, axis: str, angle: int) -> bool:
        return self._chimerax_execute(f"turn {axis} {angle}")

    def _chimerax_clear_log(self) -> bool:
        return self._chimerax_execute(f"log clear")