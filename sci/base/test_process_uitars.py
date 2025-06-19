import sys
import json
import inspect

sys.dont_write_bytecode = True

import sys
import re
import functools
import traceback

from dataclasses import dataclass

from typing import List, Set, FrozenSet, Optional
from typing import Callable, Self, NoReturn

sys.dont_write_bytecode = True

import ast


FINISH_WORD = "finished"
WAIT_WORD = "wait"
ENV_FAIL_WORD = "error_env"
CALL_USER = "call_user"
UITARS_USR_PROMPT_THOUGHT = """You are a GUI agent. You are given a task and your action history, with screenshots. You need to perform the next action to complete the task. 

## Output Format
```
Thought: ...
Action: ...
```

## Action Space
click(start_box='<|box_start|>(x1,y1)<|box_end|>')
left_double(start_box='<|box_start|>(x1,y1)<|box_end|>')
right_single(start_box='<|box_start|>(x1,y1)<|box_end|>')
drag(start_box='<|box_start|>(x1,y1)<|box_end|>', end_box='<|box_start|>(x3,y3)<|box_end|>')
hotkey(key='')
type(content='') #If you want to submit your input, use "\\n" at the end of `content`.
scroll(start_box='<|box_start|>(x1,y1)<|box_end|>', direction='down or up or right or left')
wait() #Sleep for 5s and take a screenshot to check for any changes.
finished()

## Note
- Use English in `Thought` part.
- Write a small plan and finally summarize your next action (with its target element) in one sentence in `Thought` part.

"""

def parsing_response_to_pyautogui_code(responses, image_height: int, image_width:int, input_swap:bool=True) -> str:
    '''
    将M模型的输出解析为OSWorld中的action，生成pyautogui代码字符串
    参数:
        response: 包含模型输出的字典，结构类似于：
        {
            "action_type": "hotkey",
            "action_inputs": {
                "hotkey": "v ctrl",
                "start_box": None,
                "end_box": None
            }
        }
    返回:
        生成的pyautogui代码字符串
    '''

    # pyautogui_code = f"import pyautogui\nimport time\n"
    pyautogui_code = ""
    if isinstance(responses, dict):
        responses = [responses]
    for response_id, response in enumerate(responses):
        if "observation" in response:
            observation = response["observation"]
        else:
            observation = ""

        if "thought" in response:
            thought = response["thought"]
        else:
            thought = ""

        if response_id == 0:
            pass
            # pyautogui_code += f"'''\nObservation:\n{observation}\n\nThought:\n{thought}\n'''\n"
        else:
            pyautogui_code += f"\ntime.sleep(3)\n"

        action_dict = response
        action_type = action_dict.get("action_type")
        action_inputs = action_dict.get("action_inputs", {})

        if action_type == "hotkey":
            # Parsing hotkey action
            if "key" in action_inputs:
                hotkey = action_inputs.get("key", "")
            else:
                hotkey = action_inputs.get("hotkey", "")

            if hotkey == "arrowleft":
                hotkey = "left"

            elif hotkey == "arrowright":
                hotkey = "right"
            
            elif hotkey == "arrowup":
                hotkey = "up"
            
            elif hotkey == "arrowdown":
                hotkey = "down"

            if hotkey:
                # Handle other hotkeys
                keys = hotkey.split()  # Split the keys by space
                convert_keys = []
                for key in keys:
                    if key == "space":
                        key = ' '
                    convert_keys.append(key)
                pyautogui_code += f"\npyautogui.hotkey({', '.join([repr(k) for k in convert_keys])})"

        elif action_type == "press":
            # Parsing press action
            if "key" in action_inputs:
                key_to_press = action_inputs.get("key", "")
            else:
                key_to_press = action_inputs.get("press", "")

            if hotkey == "arrowleft":
                hotkey = "left"

            elif hotkey == "arrowright":
                hotkey = "right"
            
            elif hotkey == "arrowup":
                hotkey = "up"
            
            elif hotkey == "arrowdown":
                hotkey = "down"
            
            elif hotkey == "space":
                hotkey = " "
                
            if key_to_press:
                # Simulate pressing a single key
                pyautogui_code += f"\npyautogui.press({repr(key_to_press)})"
            
        elif action_type == "keyup":
            key_to_up = action_inputs.get("key", "")
            pyautogui_code += f"\npyautogui.keyUp({repr(key_to_up)})"
        
        elif action_type == "keydown":
            key_to_down = action_inputs.get("key", "")
            pyautogui_code += f"\npyautogui.keyDown({repr(key_to_down)})"

        elif action_type == "type":
            # Parsing typing action using clipboard
            content = action_inputs.get("content", "")
            content = escape_single_quotes(content)
            stripped_content = content
            if content.endswith("\n") or content.endswith("\\n"):
                stripped_content = stripped_content.rstrip("\\n").rstrip("\n")
            if content:
                if input_swap:
                    pyautogui_code += f"\nimport pyperclip"
                    pyautogui_code += f"\npyperclip.copy('{stripped_content}')"
                    pyautogui_code += f"\npyautogui.hotkey('ctrl', 'v')"
                    pyautogui_code += f"\ntime.sleep(0.5)\n"
                    if content.endswith("\n") or content.endswith("\\n"):
                        pyautogui_code += f"\npyautogui.press('enter')"
                else:
                    pyautogui_code += f"\npyautogui.write('{stripped_content}', interval=0.1)"
                    pyautogui_code += f"\ntime.sleep(0.5)\n"
                    if content.endswith("\n") or content.endswith("\\n"):
                        pyautogui_code += f"\npyautogui.press('enter')"


        elif action_type in ["drag", "select"]:
            # Parsing drag or select action based on start and end_boxes
            start_box = action_inputs.get("start_box")
            end_box = action_inputs.get("end_box")
            if start_box and end_box:
                x1, y1, x2, y2 = eval(start_box)  # Assuming box is in [x1, y1, x2, y2]
                sx = round(float((x1 + x2) / 2) * image_width, 3)
                sy = round(float((y1 + y2) / 2) * image_height, 3)
                x1, y1, x2, y2 = eval(end_box)  # Assuming box is in [x1, y1, x2, y2]
                ex = round(float((x1 + x2) / 2) * image_width, 3)
                ey = round(float((y1 + y2) / 2) * image_height, 3)
                pyautogui_code += (
                    f"\npyautogui.moveTo({sx}, {sy})\n"
                    f"\npyautogui.dragTo({ex}, {ey}, duration=1.0)\n"
                )

        elif action_type == "scroll":
            # Parsing scroll action
            start_box = action_inputs.get("start_box")
            if start_box:
                x1, y1, x2, y2 = eval(start_box)  # Assuming box is in [x1, y1, x2, y2]
                x = round(float((x1 + x2) / 2) * image_width, 3)
                y = round(float((y1 + y2) / 2) * image_height, 3)

                # # 先点对应区域，再滚动
                # pyautogui_code += f"\npyautogui.click({x}, {y}, button='left')"
            else:
                x = None
                y = None
            direction = action_inputs.get("direction", "")

            if x == None:
                if "up" in direction.lower():
                    pyautogui_code += f"\npyautogui.scroll(5)"
                elif "down" in direction.lower():
                    pyautogui_code += f"\npyautogui.scroll(-5)"
            else:
                if "up" in direction.lower():
                    pyautogui_code += f"\npyautogui.scroll(5, x={x}, y={y})"
                elif "down" in direction.lower():
                    pyautogui_code += f"\npyautogui.scroll(-5, x={x}, y={y})"

        elif action_type in ["click", "left_single", "left_double", "right_single", "hover"]:
            # Parsing mouse click actions
            start_box = action_inputs.get("start_box")
            start_box = str(start_box)
            if start_box:
                start_box = eval(start_box)
                if len(start_box) == 4:
                    x1, y1, x2, y2 = start_box  # Assuming box is in [x1, y1, x2, y2]
                elif len(start_box) == 2:
                    x1, y1 = start_box
                    x2 = x1
                    y2 = y1
                x = round(float((x1 + x2) / 2), 3)
                y = round(float((y1 + y2) / 2), 3)
                if action_type == "left_single" or action_type == "click":
                    pyautogui_code += f"\npyautogui.click({x}, {y}, button='left')"
                elif action_type == "left_double":
                    pyautogui_code += f"\npyautogui.doubleClick({x}, {y}, button='left')"
                elif action_type == "right_single":
                    pyautogui_code += f"\npyautogui.click({x}, {y}, button='right')"
                elif action_type == "hover":
                    pyautogui_code += f"\npyautogui.moveTo({x}, {y})"

        elif action_type in ["finished"]:
            pyautogui_code = f"DONE"

        else:
            pyautogui_code += f"\n# Unrecognized action type: {action_type}"

    return pyautogui_code

# 定义一个函数来解析每个 action
def parse_action(action_str):
    try:
        # 解析字符串为 AST 节点
        node = ast.parse(action_str, mode='eval')

        # 确保节点是一个表达式
        if not isinstance(node, ast.Expression):
            raise ValueError("Not an expression")

        # 获取表达式的主体
        call = node.body

        # 确保主体是一个函数调用
        if not isinstance(call, ast.Call):
            raise ValueError("Not a function call")

        # 获取函数名
        if isinstance(call.func, ast.Name):
            func_name = call.func.id
        elif isinstance(call.func, ast.Attribute):
            func_name = call.func.attr
        else:
            func_name = None

        # 获取关键字参数
        kwargs = {}
        for kw in call.keywords:
            key = kw.arg
            # 处理不同类型的值，这里假设都是常量
            if isinstance(kw.value, ast.Constant):
                value = kw.value.value
            elif isinstance(kw.value, ast.Str):  # 兼容旧版本 Python
                value = kw.value.s
            else:
                value = None
            kwargs[key] = value

        return {
            'function': func_name,
            'args': kwargs
        }

    except Exception as e:
        print(f"Failed to parse action '{action_str}': {e}")
        return None


def escape_single_quotes(text):
    # 匹配未转义的单引号（不匹配 \\'）
    pattern = r"(?<!\\)'"
    return re.sub(pattern, r"\\'", text)

def fix_click_output(output: str) -> str:
    # 直接匹配两个逗号分隔的数字，不考虑括号
    matches = re.findall(r'(\d+)\s*,\s*(\d+)', output)

    if matches:
        # 取最后一个匹配到的坐标
        x, y = matches[-1]
        return f"click(start_box='({x},{y})')"
    else:
        return None  # 没有找到任何有效的坐标时返回

def fix_drag_output(output: str) -> str:
    # 直接匹配两个逗号分隔的数字，不考虑括号
    matches = re.findall(r'(\d+)\s*,\s*(\d+)', output)

    if matches and len(matches) >= 2:
        # 取最后一个匹配到的坐标
        x1, y1 = matches[-2]
        x2, y2 = matches[-1]
        return f"drag(start_box='({x1},{y1})', end_box='({x2},{y2})')"
    else:
        return None  # 没有找到任何有效的坐标时返回

def parse_action_qwen2vl(text, factor, image_height, image_width):
    text = text.strip()
    # 正则表达式匹配 Action 字符串
    if text.startswith("Thought:"):
        thought_pattern = r"Thought: (.+?)(?=\s*Action:|$)"
        thought_hint = "Thought: "
    elif text.startswith("Reflection:"):
        thought_pattern = r"Reflection: (.+?)Action_Summary: (.+?)(?=\s*Action:|$)"
        thought_hint = "Reflection: "
    elif text.startswith("Action_Summary:"):
        thought_pattern = r"Action_Summary: (.+?)(?=\s*Action:|$)"
        thought_hint = "Action_Summary: "
    else:
        thought_pattern = r"Thought: (.+?)(?=\s*Action:|$)"
        thought_hint = "Thought: "
    reflection, thought = None, None
    thought_match = re.search(thought_pattern, text, re.DOTALL)
    if thought_match:
        if len(thought_match.groups()) == 1:
            thought = thought_match.group(1).strip()
        elif len(thought_match.groups()) == 2:
            thought = thought_match.group(2).strip()
            reflection = thought_match.group(1).strip()
    assert "Action:" in text
    action_str = text.split("Action:")[-1]

    tmp_all_action = action_str.split("\n\n")
    all_action = []
    for action_str in tmp_all_action:
        if "type(content" in action_str:
            # 正则表达式匹配 content 中的字符串并转义单引号
            def escape_quotes(match):
                content = match.group(1)  # 获取 content 的值
                return content

            # 使用正则表达式进行替换
            pattern = r"type\(content='(.*?)'\)"  # 匹配 type(content='...')
            content = re.sub(pattern, escape_quotes, action_str)

            # 处理字符串
            action_str = escape_single_quotes(content)
            action_str = "type(content='" + action_str + "')"
        elif "click(start_box" in action_str:
            # - Failed to parse action 'click(start_box='='x(409,173)')'
            # - Failed to parse action 'click(start_box='='\nstart_box='(430,348)')'
            # - Failed to parse action 'click(start_box='='\n' Data')'
            # - Failed to parse action 'click(start_box='237,72)'
            # - Failed to parse action 'click(start_box='='(492,348)')'
            # - Failed to parse action 'click(start_box='='\n(493,350)')'
            action_str_fixed = fix_click_output(action_str)
            if (action_str_fixed is not None) and (action_str_fixed != action_str):
                print('[CLICK ACTION FIXED]', action_str, '->', action_str_fixed)
                action_str = action_str_fixed
        elif "drag(start_box" in action_str:
            action_str_fixed = fix_drag_output(action_str)
            if (action_str_fixed is not None) and (action_str_fixed != action_str):
                print('[DRAG ACTION FIXED]', action_str, '->', action_str_fixed)
                action_str = action_str_fixed
        all_action.append(action_str)

    parsed_actions = [parse_action(action.replace("\n","\\n").lstrip()) for action in all_action]
    actions = []
    for action_instance, raw_str in zip(parsed_actions, all_action):
        if action_instance == None:
            print(f"Action can't parse: {raw_str}")
            continue
        action_type = action_instance["function"]
        params = action_instance["args"]

        # import pdb; pdb.set_trace()
        action_inputs = {}
        for param_name, param in params.items():
            if param == "": continue
            param = param.lstrip()  # 去掉引号和多余的空格
            # 处理start_box或者end_box参数格式 '<bbox>x1 y1 x2 y2</bbox>'
            action_inputs[param_name.strip()] = param
            
            if "start_box" in param_name or "end_box" in param_name:
                ori_box = param
                # Remove parentheses and split the string by commas
                # if "[" in  ori_box:
                #     numbers = ori_box.replace("[", "").replace("]", "").split(",")
                # else:
                #     numbers = ori_box.replace("(", "").replace(")", "").split(",")
                numbers = ori_box.replace("(", "").replace(")", "").replace("[", "").replace("]", "").split(",")

                # Convert to float and scale by 1000
                float_numbers = [float(num) / factor for num in numbers]
                if len(float_numbers) == 2:
                    float_numbers = [float_numbers[0], float_numbers[1], float_numbers[0], float_numbers[1]]
                action_inputs[param_name.strip()] = str(float_numbers)

        # import pdb; pdb.set_trace()
        actions.append({
            "reflection": reflection,
            "thought": thought,
            "action_type": action_type,
            "action_inputs": action_inputs,
            "text": text
        })
    return actions


# DO NOT DELETE DOCSTRINGS OF EACH PRIMITIVE!
class Primitive:
    class PrimitiveGetter:
        def __get__(self, obj, obj_type=None):
            return [
                item for item in Primitive.__dict__
                if isinstance(
                    inspect.getattr_static(Primitive, item),
                    staticmethod
                ) and getattr(Primitive, item).__doc__ is not None
            ]

    WAIT_TIME = 5
    PRIMITIVES = PrimitiveGetter()

    def option_handler(method: Callable) -> Callable:
        @functools.wraps(method)
        def option_wrapper(*args, **kwargs):
            return method(*args, **kwargs)
        return option_wrapper

    class PlannedTermination(Exception):
        def __init__(self, type: staticmethod, *args) -> None:
            self.type = type
            self.args = args

    @staticmethod
    def DONE() -> NoReturn:
        """When you think the task is done, return «DONE»"""
        raise Primitive.PlannedTermination(Primitive.DONE)

    @staticmethod
    def FAIL() -> NoReturn:
        """When you think the task can not be done, return «FAIL». Don't easily say «FAIL»; try your best to do the task"""
        raise Primitive.PlannedTermination(Primitive.FAIL)

    @staticmethod
    def WAIT(time_span: Optional[str] = None) -> None:
        """When you think you have to wait for some time, return «WAIT» or «WAIT n», in which n defaults to 5(s)"""
        time_span = Primitive.WAIT_TIME if time_span is None else int(time_span)
        Manager.pause(time_span)

    @staticmethod
    @option_handler
    def ANS(*args) -> None:
        """When you are asked to submit an answer, return «ANS s» without quotation marks surrounding s, and use «FAIL» if there is no answer to the question"""
        raise Primitive.PlannedTermination(Primitive.ANS, *args)

    @staticmethod
    def TIMEOUT() -> None:
        ...



if __name__ == "__main__":
    content = "Thought: The apparent magnitude of the Milky Way galaxy is already visible in the \"App. mag\" column of the table. Since the task is to find and submit this value, I can now proceed to copy the magnitude value, which is -5.95, to ensure it is recorded accurately for submission.\nUse the keyboard shortcut \"Ctrl + C\" to copy the apparent magnitude value of -5.95 from the \"App. mag\" column.\nAction: hotkey(key='ctrl c')\n\nfinished()"
    parsed_responses = parse_action_qwen2vl(
        content,
        1000, #action_parse_res_factor,
        800, #screen_size[1],
        1280, #screen_size[0]
    )

    action_codes = []
    for parsed_response in parsed_responses:
        if "action_type" in parsed_response:
            if parsed_response["action_type"] == FINISH_WORD:
                action_codes.append("DONE")
            
            elif parsed_response["action_type"] == WAIT_WORD:
                action_codes.append("WAIT")
            
            elif parsed_response["action_type"] == ENV_FAIL_WORD:
                action_codes.append("FAIL")

            pyautogui_code = parsing_response_to_pyautogui_code(
                parsed_response,
                1000, #action_parse_res_factor,
                800, #screen_size[1],
                1280, #screen_size[0]
            )
            import ipdb; ipdb.set_trace()
            action_codes.append(pyautogui_code)