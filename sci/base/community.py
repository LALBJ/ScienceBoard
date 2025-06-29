import json
import sys

import os

from typing import List, Tuple, Dict
from typing import Optional, Any, Self
from dataclasses import dataclass

from .model import Message, TextContent

sys.dont_write_bytecode = True
from .manager import OBS
from .log import VirtualLog
from .agent import Agent, AIOAgent
from .agent import PlannerAgent, GrounderAgent
from .prompt import TypeSort, CodeLike


@dataclass
class Community:
    def __post_init__(self):
        self.vlog = VirtualLog()

    @property
    def agents(self) -> List[Tuple[str, Agent]]:
        return [
            (key, getattr(self, key))
            for key in self.__dataclass_fields__.keys()
            if isinstance(getattr(self, key), Agent)
        ]

    def __iter__(self) -> Self:
        self.iter_pointer = 0
        return self

    def __next__(self):
        if self.iter_pointer < len(self.agents):
            self.iter_pointer += 1
            return self.agents[self.iter_pointer - 1]
        else:
            raise StopIteration

    def __call__(
        self,
        steps: Tuple[int, int],
        inst: str,
        obs: Dict[str, Any],
        code_info: tuple[set[str], Optional[List[List[int]]]],
        type_sort: TypeSort,
        timeout: int
    ) -> List[CodeLike]:
        raise NotImplementedError


@dataclass
class AllInOne(Community):
    mono: AIOAgent

    def __call__(
        self,
        steps: Tuple[int, int],
        inst: str,
        obs: Dict[str, Any],
        code_info: tuple[set[str], Optional[List[List[int]]]],
        type_sort: TypeSort,
        timeout: int
    ) -> List[CodeLike]:
        step_index, total_steps = steps
        init_kwargs = {
            "inst": inst,
            "type_sort": type_sort
        } if step_index == 0 else None

        user_content = self.mono._step(obs, init_kwargs)

        DEBUG_MODE = os.environ.get("DEBUG_MODE", "False").lower() == "true"
        if DEBUG_MODE:
            # for debugging purpose, 直接加载 debug 文件
            ACTION_PATH = os.environ.get("ACTION_PATH", None)
            with open(ACTION_PATH, "r") as f:
                history = json.loads(f.read())
                assistant_content = [content for content in history if content["role"] == "assistant"]
                response_message = Message(
                    style="openai",
                    role="assistant",
                    content=[TextContent(assistant_content[step_index]["content"][0]["text"])],
                )
        else:
            response_message = self.mono(user_content, timeout=timeout)

        assert len(response_message.content) == 1
        response_content = response_message.content[0]

        self.vlog.info(
            f"Response {step_index + 1}/{total_steps}: \n" \
                + response_content.text
        )
        return self.mono.code_handler(response_content, *code_info)


@dataclass
class SeeAct(Community):
    planner: PlannerAgent
    grounder: GrounderAgent

    def __call__(
        self,
        steps: Tuple[int, int],
        inst: str,
        obs: Dict[str, Any],
        code_info: tuple[set[str], Optional[List[List[int]]]],
        type_sort: TypeSort,
        timeout: int
    ) -> List[CodeLike]:
        step_index, total_steps = steps
        first_step = step_index == 0

        init_kwargs = {
            "inst": inst,
            "type_sort": type_sort
        } if first_step else None

        planner_content = self.planner._step(obs, init_kwargs)
        planner_reponse_message = self.planner(planner_content, timeout=timeout)

        assert len(planner_reponse_message.content) == 1
        planner_response_content = planner_reponse_message.content[0]

        self.vlog.info(
            f"Response of planner {step_index + 1}/{total_steps}: \n" \
                + planner_response_content.text
        )

        codes = self.planner.code_handler(planner_response_content, *code_info)

        if first_step:
            self.grounder._init(obs.keys(), **init_kwargs)

        # to intercept special codes
        if codes[0].desc is False:
            return codes

        obs[OBS.schedule] = codes[0].code
        grounder_content = self.grounder._step(obs)
        grounder_response_message = self.grounder(grounder_content, timeout=timeout)

        assert len(grounder_response_message.content) == 1
        grounder_response_content = grounder_response_message.content[0]

        self.vlog.info(
            f"Response of grounder {step_index + 1}/{total_steps}: \n" \
                + grounder_response_content.text
        )
        return self.grounder.code_handler(grounder_response_content, *code_info)
