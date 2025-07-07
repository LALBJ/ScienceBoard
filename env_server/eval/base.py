class TaskEval:
    def __init__(
        self,
        manager
    ) -> None:
        # to enable Pylance type checker
        self.manager = manager

    def general_eval(self) -> bool:
        return False
