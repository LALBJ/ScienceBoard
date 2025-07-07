from env_server.eval.base import TaskEval


class CelestiaEval(TaskEval):
    def __init__(self, manager, task_config) -> None:
        super().__init__(manager)

        self.query = task_config.get("query", [])
        self.evaluate = task_config["evaluate"]

    def eval(self) -> bool:
        if self.general_eval():
            return True
        else:
            info = self.manager.status_dump(self.query)
            for eval_item in self.evaluate:
                hkey: Callable = lambda info: info[eval_item["key"]]
                pred: Callable = lambda left, right: left == right

                if hasattr(key_eval := eval(eval_item["key"]), "__call__"):
                    hkey = key_eval
                if "pred" in eval_item:
                    pred = eval(eval_item["pred"])
                if not pred(hkey(info), eval_item["value"]):
                    print(f"Evaluation failed at {eval_item['type']} of {eval_item['key']}.")
                    return False
        return True