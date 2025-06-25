import sys
import json
import inspect

sys.dont_write_bytecode = True
from .utils import TypeSort

import sys
import re
import functools
import traceback

from dataclasses import dataclass

from typing import List, Set, FrozenSet, Optional
from typing import Callable, Self, NoReturn

sys.dont_write_bytecode = True
from .. import Prompts
from .override import *
from .manager import OBS, Manager
from .model import Content, TextContent
from .utils import TypeSort, relative_py
from .log import GLOBAL_VLOG

import ast

RAW = TypeSort.Sort.Raw
VM = TypeSort.Sort.VM

IMAGE_FACTOR = 28
MIN_PIXELS = 100 * 28 * 28
MAX_PIXELS = 16384 * 28 * 28
MAX_RATIO = 200

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

def round_by_factor(number: int, factor: int) -> int:
    """Returns the closest integer to 'number' that is divisible by 'factor'."""
    return round(number / factor) * factor


def ceil_by_factor(number: int, factor: int) -> int:
    """Returns the smallest integer greater than or equal to 'number' that is divisible by 'factor'."""
    return math.ceil(number / factor) * factor


def floor_by_factor(number: int, factor: int) -> int:
    """Returns the largest integer less than or equal to 'number' that is divisible by 'factor'."""
    return math.floor(number / factor) * factor

def convert_point_to_coordinates(text, is_answer=False):
    # 匹配 <bbox> 后面的四个数字
    pattern = r"<point>(\d+)\s+(\d+)</point>"

    def replace_match(match):
        x1, y1 = map(int, match.groups())
        x = (x1 + x1) // 2  # 使用截断取整
        y = (y1 + y1) // 2  # 使用截断取整
        if is_answer:
            return f"({x},{y})"  # 只返回 (x, y) 格式
        return f"({x},{y})"  # 返回带标签的格式

    # 去掉 [EOS] 并替换 <bbox> 坐标
    text = re.sub(r"\[EOS\]", "", text)
    return re.sub(pattern, replace_match, text).strip()


def linear_resize(
    height: int, width: int, factor: int = IMAGE_FACTOR, min_pixels: int = MIN_PIXELS, max_pixels: int = MAX_PIXELS
) -> tuple[int, int]:
    if width * height > max_pixels:
        """
        如果图片超过/低于像素限制，则计算一个缩放因子resize_factor，使图片的像素数缩小到等于或小于max_pixels。这个缩放因子是通过开平方根计算的，确保纵横比保持不变,这样原始的相对坐标可以不经转换直接复用
        """
        resize_factor = math.sqrt(max_pixels / (width * height))
        width, height = int(width * resize_factor), int(height * resize_factor)
    if width * height < min_pixels:
        resize_factor = math.sqrt(min_pixels / (width * height))
        width, height = math.ceil(width * resize_factor), math.ceil(height * resize_factor)

    return height, width 

def smart_resize(
    height: int, width: int, factor: int = IMAGE_FACTOR, min_pixels: int = MIN_PIXELS, max_pixels: int = MAX_PIXELS
) -> tuple[int, int]:
    """
    Rescales the image so that the following conditions are met:

    1. Both dimensions (height and width) are divisible by 'factor'.

    2. The total number of pixels is within the range ['min_pixels', 'max_pixels'].

    3. The aspect ratio of the image is maintained as closely as possible.
    """
    if max(height, width) / min(height, width) > MAX_RATIO:
        raise ValueError(
            f"absolute aspect ratio must be smaller than {MAX_RATIO}, got {max(height, width) / min(height, width)}"
        )
    h_bar = max(factor, round_by_factor(height, factor))
    w_bar = max(factor, round_by_factor(width, factor))
    if h_bar * w_bar > max_pixels:
        beta = math.sqrt((height * width) / max_pixels)
        h_bar = floor_by_factor(height / beta, factor)
        w_bar = floor_by_factor(width / beta, factor)
    elif h_bar * w_bar < min_pixels:
        beta = math.sqrt(min_pixels / (height * width))
        h_bar = ceil_by_factor(height * beta, factor)
        w_bar = ceil_by_factor(width * beta, factor)
    return h_bar, w_bar

def parse_action_to_structure_output(text,
                                     factor,
                                     origin_resized_height,
                                     origin_resized_width,
                                     model_type="qwen25vl",
                                     max_pixels=16384 * 28 * 28,
                                     min_pixels=100 * 28 * 28):
    text = text.strip()

    if "<point>" in text:
        text = convert_point_to_coordinates(text)
    if "start_point=" in text:
        text = text.replace("start_point=", "start_box=")
    if "end_point=" in text:
        text = text.replace("end_point=", "end_box=")
    if "point=" in text:
        text = text.replace("point=", "start_box=")

    if model_type == "qwen25vl":
        smart_resize_height, smart_resize_width = smart_resize(
            origin_resized_height,
            origin_resized_width,
            factor=IMAGE_FACTOR,
            min_pixels=min_pixels,
            max_pixels=max_pixels)

    # 正则表达式匹配 Action 字符串
    if text.startswith("Thought:"):
        thought_pattern = r"Thought: (.+?)(?=\s*Action: |$)"
        thought_hint = "Thought: "
    elif text.startswith("Reflection:"):
        thought_pattern = r"Reflection: (.+?)Action_Summary: (.+?)(?=\s*Action: |$)"
        thought_hint = "Reflection: "
    elif text.startswith("Action_Summary:"):
        thought_pattern = r"Action_Summary: (.+?)(?=\s*Action: |$)"
        thought_hint = "Action_Summary: "
    else:
        thought_pattern = r"Thought: (.+?)(?=\s*Action: |$)"
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
    action_str = text.split("Action: ")[-1]

    tmp_all_action = action_str.split(")\n\n")
    all_action = []
    for action_str in tmp_all_action:
        if "type(content" in action_str:
            if not action_str.strip().endswith(")"):
                action_str = action_str.strip() + ")"
            # 正则表达式匹配 content 中的字符串并转义单引号
            def escape_quotes(match):
                content = match.group(1)  # 获取 content 的值
                return content

            # 使用正则表达式进行替换
            pattern = r"type\(content='(.*?)'\)"  # 匹配 type(content='...')
            if re.search(pattern, action_str):  # 检查是否有匹配项
                content = re.sub(pattern, escape_quotes, action_str)
            else:
                raise ValueError("Pattern not found in the input string.")

            # 处理字符串
            action_str = escape_single_quotes(content)
            action_str = "type(content='" + action_str + "')"
        if not action_str.strip().endswith(")"):
            action_str = action_str.strip() + ")"
        all_action.append(action_str)

    parsed_actions = [
        parse_action(action.replace("\n", "\\n").lstrip())
        for action in all_action
    ]
    actions = []
    for action_instance, raw_str in zip(parsed_actions, all_action):
        if action_instance == None:
            print(f"Action can't parse: {raw_str}")
            raise ValueError(f"Action can't parse: {raw_str}")
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
                numbers = ori_box.replace("(", "").replace(")", "").split(",")

                # Convert to float and scale by 1000
                # Qwen2.5vl output absolute coordinates, qwen2vl output relative coordinates
                if model_type == "qwen25vl":
                    float_numbers = []
                    for num_idx, num in enumerate(numbers):
                        num = float(num)
                        if (num_idx + 1) % 2 == 0:
                            float_numbers.append(
                                float(num / smart_resize_height))
                        else:
                            float_numbers.append(
                                float(num / smart_resize_width))
                else:
                    float_numbers = [float(num) / factor for num in numbers]

                if len(float_numbers) == 2:
                    float_numbers = [
                        float_numbers[0], float_numbers[1], float_numbers[0],
                        float_numbers[1]
                    ]
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
                sx = round(float((x1 + x2) / 2), 3)
                sy = round(float((y1 + y2) / 2), 3)
                x1, y1, x2, y2 = eval(end_box)  # Assuming box is in [x1, y1, x2, y2]
                ex = round(float((x1 + x2) / 2), 3)
                ey = round(float((y1 + y2) / 2), 3)
                pyautogui_code += (
                    f"\npyautogui.moveTo({sx}, {sy})\n"
                    f"\npyautogui.dragTo({ex}, {ey}, duration=1.0)\n"
                )

        elif action_type == "scroll":
            # Parsing scroll action
            start_box = action_inputs.get("start_box")
            if start_box:
                x1, y1, x2, y2 = eval(start_box)  # Assuming box is in [x1, y1, x2, y2]
                x = round(float((x1 + x2) / 2), 3)
                y = round(float((y1 + y2) / 2), 3)

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


@dataclass
class CodeLike:
    code: str
    desc: bool = False
    prefix: str = ""

    @staticmethod
    def parse_tags(tags):
        tag_prefix = ""
        for index, tag in enumerate(tags):
            cord_x, cord_y, width, height = tag
            tag_prefix += "tag_" \
                + str(index + 1) \
                + "=" \
                + f"({cord_x + width // 2}, {cord_y + height // 2})"
            tag_prefix += "\n"
        return tag_prefix.strip()

    def is_primitive(self, primitives: List[str]) -> bool:
        return any([self.code.strip().startswith(prim) for prim in primitives])

    @staticmethod
    def _tag_handler(method: Callable[[Content], List[Self]]) -> Callable:
        def _tag_wrapper(
            content: Content,
            primitives: Set[str],
            tags: List[List[int]]
        ) -> List[Self]:
            for code in (codes := method(content)):
                if tags is not None and not code.is_primitive(primitives):
                    code.push_prefix(CodeLike.parse_tags(tags))
            return codes
        return _tag_wrapper

    @staticmethod
    def match(pattern: str, content: TextContent, index: int = 1) -> List[Self]:
        occurence = [
            match.group(index).strip()
            for match in re.finditer(pattern, content.text)
        ]
        return [CodeLike(code=code) for code in occurence]

    @_tag_handler
    @staticmethod
    def extract_antiquot(content: TextContent) -> List[Self]:
        return CodeLike.match(r'```(?:\w*\s+)?([\w\W]*?)```', content)

    @staticmethod
    def wrap_antiquot(doc_str: str) -> str:
        return doc_str.replace("«", "```").replace("»", "```")

    @staticmethod
    def extract_planner(
        content: TextContent,
        primitives: Set[str],
        *args,
        **kwargs
    ) -> List[Self]:
        codes = [
            code for code in CodeLike.match(
                r'```(?:\w*\s+)?([\w\W]*?)```',
                content
            ) if code.is_primitive(primitives)
        ]
        return codes if len(codes) > 0 \
            else [CodeLike(code=content.text, desc=True)]

    @staticmethod
    def wrap_planner(doc_str: str) -> str:
        return doc_str.replace("«", "```").replace("»", "```")

    @staticmethod
    def extract_atlas(content: TextContent, *args, **kwargs) -> List[Self]:
        pat_click = r'CLICK <point>\[\[(\d+), ?(\d+)\]\]</point>'
        pat_type = r'TYPE \[(.+?)\]'
        pat_scroll = r'SCROLL \[(UP|DOWN|LEFT|RIGHT)\]'
        pat_atlas = fr'({pat_click}|{pat_type}|{pat_scroll})'

        def parse(code: str) -> str:
            match_obj = None
            if (match_obj := re.match(pat_click, code)) is not None:
                x = int(match_obj[1]) / 1000
                y = int(match_obj[2]) / 1000
                return f"pyautogui.click({x}, {y})"
            elif (match_obj := re.match(pat_type, code)) is not None:
                text = json.dumps(match_obj[1])
                return f"pyautogui.typewrite({text}, interval=0.1)"
            elif (match_obj := re.match(pat_scroll, code)) is not None:
                direction = match_obj[1]
                return {
                    "UP": "pyautogui.scroll(10)",
                    "DOWN": "pyautogui.scroll(-10)",
                    "LEFT": "pyautogui.hscroll(-10)",
                    "RIGHT": "pyautogui.hscroll(10)"
                }[direction]

        return [
            CodeLike(code=parse(code.code), prefix=relative_py)
            for code in CodeLike.match(pat_atlas, content)
        ]

    @staticmethod
    def wrap_atlas(doc_str: str) -> str:
        # this function will not be called
        return doc_str

    @staticmethod
    def extract_uground(content: TextContent, *args, **kwargs) -> List[Self]:
        def parse(code: str) -> str:
            match_obj = re.match(r'\((\d+), ?(\d+)\)', code)
            x = int(match_obj[1]) / 1000
            y = int(match_obj[2]) / 1000
            return f"pyautogui.click({x}, {y})"
        return [
            CodeLike(code=parse(code.code), prefix=relative_py)
            for code in CodeLike.match(r'(\(\d+, ?\d+\))', content)
        ]
    
    @staticmethod
    def extract_uitars(content: TextContent, *args, **kwargs) -> List[Self]:
        parsed_responses = parse_action_qwen2vl(
            content.text,
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

            try:
                pyautogui_code = parsing_response_to_pyautogui_code(
                    parsed_response,
                    1000, #action_parse_res_factor,
                    800, #screen_size[1],
                    1280, #screen_size[0]
                )
                action_codes.append(pyautogui_code)
            except Exception as e:
                print(f"Parsing pyautogui code error: {parsed_response}, with error:\n{e}")
        return [
            CodeLike(code=code, prefix=relative_py)
            for code in action_codes
        ]
    
    @staticmethod
    def extract_uitars1_5(content: TextContent, *args, **kwargs) -> List[Self]:
        parsed_responses = parse_action_to_structure_output(
            content.text,
            IMAGE_FACTOR, #action_parse_res_factor,
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

            try:
                pyautogui_code = parsing_response_to_pyautogui_code(
                    parsed_response,
                    1000, #action_parse_res_factor,
                    800, #screen_size[1],
                    1280, #screen_size[0]
                )
                action_codes.append(pyautogui_code)
            except Exception as e:
                print(f"Parsing pyautogui code error: {parsed_response}, with error:\n{e}")
        return [
            CodeLike(code=code, prefix=relative_py)
            for code in action_codes
        ]

    @staticmethod
    def wrap_uground(doc_str: str) -> str:
        # this function will not be called
        return doc_str
    
    @staticmethod
    def wrap_uitars(doc_str: str) -> str:
        # this function will not be called
        return doc_str
    
    @staticmethod
    def wrap_uitars1_5(doc_str: str) -> str:
        # this function will not be called
        return doc_str

    def push_prefix(self, prefix: str, back: bool = True) -> None:
        new_prefix = [self.prefix, prefix.strip()] if back \
            else [prefix.strip(), self.prefix]
        self.prefix = "\n\n".join(PromptFactory.filter(new_prefix))

    def __call__(
        self,
        manager: Manager,
        primitives: List[str]
    ) -> Optional[bool]:
        assert self.desc is False

        if self.is_primitive(primitives):
            splits = self.code.split(" ")
            try:
                getattr(Primitive, splits[0])(*splits[1:])
            except Primitive.PlannedTermination as early_stop:
                # pass planned exception
                raise early_stop
            except:
                # catch unexpected exception
                GLOBAL_VLOG.error(
                    f"Error calling primitive. \n" \
                        + traceback.format_exc()
                )
        else:
            return manager("\n\n".join(PromptFactory.filter([
                "" if self.prefix is None else self.prefix.strip(),
                self.code
            ])))


class PromptFactory:
    def __init__(self, code_style: str) -> None:
        assert hasattr(CodeLike, func_name:=f"wrap_{code_style}")
        self.code_style = code_style
        self.code_handler: Callable[[str], str] = getattr(CodeLike, func_name)

    @staticmethod
    def option(item: Optional[str]) -> List[str]:
        # usage: [..., *PromptFactory.option("..."), ...]
        return PromptFactory.filter([item])

    @staticmethod
    def filter(inputs: List[str]) -> List[str]:
        return [
            item for item in inputs
            if isinstance(item, str) and len(item) > 0
        ]


class AIOPromptFactory(PromptFactory):
    # first section: _intro
    GENERAL_INTRO = "You are an agent which follow my instruction and perform desktop computer tasks as instructed."
    APP_GENERAL = "an application available on Ubuntu"
    APP_INCENTIVE = {
        RAW: lambda type, intro: f"You have good knowledge of {type}, {intro}; and assume that your code will run directly in the CLI/REPL of {type}.",
        VM: lambda type, intro: f"You have good knowledge of {type}, {intro}; and assume your code will run on a computer controlling the mouse and keyboard."
    }
    OBS_INCENTIVE = lambda obs_descr: f"For each step, you will get an observation of the desktop by {obs_descr}, and you will predict actions of next steps based on that."

    # second section: _command = _general_command + _general_usage + _special_command
    # second #1: _general_command
    RETURN_OVERVIEW_RAW = staticmethod(lambda type, media: f"You are required to use {media} to perform the action grounded to the observation. DO NOT use the bash commands or and other codes that {type} itself does not support.")
    RETURN_OVERVIEW_VM = {
        "antiquot": "You are required to use `pyautogui` to perform the action grounded to the observation, but DO NOT use the `pyautogui.locateCenterOnScreen` function to locate the element you want to operate with since we have no image of the element you want to operate with. DO NOT USE `pyautogui.screenshot()` to make screenshot.",
        "uground": "You are required to use `pyautogui` to perform the action grounded to the observation, but DO NOT use the `pyautogui.locateCenterOnScreen` function to locate the element you want to operate with since we have no image of the element you want to operate with. DO NOT USE `pyautogui.screenshot()` to make screenshot."
    }
    RETURN_REGULATION = {
        "antiquot": "You ONLY need to return the code inside a code block, like this:\n```\n# your code here\n```",
        "uground": "You ONLY need to return the code inside a code block, like this:\n```\n# your code here\n```"
    }
    RETURN_SUPPLEMENT_RAW = "Return exact one line of commands to perform the action in each code block."
    RETURN_SUPPLEMENT_VM = {
        "antiquot": "Return one line or multiple lines of python code to perform the action each time, and be time efficient. When predicting multiple lines of code, make some small sleep like `time.sleep(0.5);` interval so that the machine could take breaks. Each time you need to predict a complete code, and no variables or function can be shared from history.",
        "uground": "Return one line or multiple lines of python code to perform the action each time, and be time efficient. When predicting multiple lines of code, make some small sleep like `time.sleep(0.5);` interval so that the machine could take breaks. Each time you need to predict a complete code, and no variables or function can be shared from history."
    }

    # second #1.5: supplementary instruction for set of marks
    SOM_SUPPLEMENT = [
        "You can replace x, y in the code with the tag of elements you want to operate with, such as:",
        "«\npyautogui.moveTo(tag_3)\npyautogui.click(tag_2)\npyautogui.dragTo(tag_1, button='left')\n»",
        "When you think you can directly output precise x and y coordinates or there is no tag on which you want to interact, you can also use them directly; but you should be careful to ensure the correct of coordinates."
    ]

    # second #3: _general_command
    SPECIAL_OVERVIEW = "Specially, it is also allowed to return the following special code:"

    # third section: _warning
    VM_GENERAL = f"My computer's password is '{Prompts.VM_PASSWORD}', feel free to use it when you need sudo rights."

    # fourth section: _ending
    ENDING_ULTIMATUM = "First give the current observation and previous things we did a short reflection, then RETURN ME THE CODE OR SPECIAL CODE I ASKED FOR. NEVER EVER RETURN ME ANYTHING ELSE."
    # SYSTEM_INSTRUCTION = lambda inst: f"You are asked to complete the following task: {inst}"
    SYSTEM_INSTRUCTION = lambda inst: f"## User Instruction:\n{inst}"

    def getattr(self, type_sort: TypeSort, name: str, default: Any) -> Any:
        assert type(default) == type(results := getattr(
            Prompts,
            str(type_sort).upper() + "_" + name,
            getattr(
                Prompts,
                type_sort.type.upper() + "_" + name,
                default
            )
        ))
        return results

    def _unfold(self, obs: FrozenSet[str]) -> str:
        get_descr = lambda obs_name: getattr(Manager, obs_name).__doc__
        obs = list(obs)

        if len(obs) == 1:
            return get_descr(obs[0])
        else:
            return "; ".join([
                f"{index + 1}) {get_descr(item)}"
                for index, item in enumerate(obs[:-1])
            ]) + f"; and {len(obs)}) " + get_descr(obs[-1])

    def _intro(self, obs: FrozenSet[str], type_sort: TypeSort) -> str:
        brief_intro = self.getattr(type_sort, "IS", self.APP_GENERAL)
        return "\n".join([
            self.GENERAL_INTRO,
            self.APP_INCENTIVE[type_sort.sort](type_sort.type, brief_intro),
            self.OBS_INCENTIVE.__func__(self._unfold(obs))
        ])

    def _general_command(self, obs: FrozenSet[str], type_sort: TypeSort) -> str:
        media = self.getattr(type_sort, "NEED", type_sort.type + " commands")
        set_of_marks = self.SOM_SUPPLEMENT if OBS.set_of_marks in obs else []

        return_overview = self.RETURN_OVERVIEW_RAW(type_sort.type, media) \
            if type_sort.sort == RAW \
            else self.RETURN_OVERVIEW_VM[self.code_style]
        return_regulation = self.RETURN_REGULATION[self.code_style]
        return_supplement = self.RETURN_SUPPLEMENT_RAW \
            if type_sort.sort == RAW \
            else self.RETURN_SUPPLEMENT_VM[self.code_style]

        return "\n\n".join(PromptFactory.filter([
            "\n".join(PromptFactory.filter([
                return_overview,
                return_regulation,
                return_supplement,
            ])),
            "\n".join([self.code_handler(item) for item in set_of_marks]),
        ]))

    def _general_usage(self, type_sort: TypeSort) -> str:
        return "\n".join(self.getattr(type_sort, "USAGE", []))

    def _special_command(self) -> str:
        docs = [
            self.code_handler(getattr(Primitive, item).__doc__)
            for item in Primitive.PRIMITIVES
        ]

        return "\n".join([self.SPECIAL_OVERVIEW, *[
            item + ("." if index + 1 == len(docs) else ";")
            for index, item in enumerate(docs)
        ]])

    def _command(self, obs: FrozenSet[str], type_sort: TypeSort) -> str:
        import ipdb; ipdb.set_trace()
        return "\n\n".join(PromptFactory.filter([
            self._general_command(obs, type_sort),
            self._general_usage(type_sort),
            self._special_command()
        ]))

    def _warning(self, type_sort: TypeSort) -> str:
        vm_tip = self.VM_GENERAL if type_sort == TypeSort.VM else None
        extra_tips = self.getattr(type_sort, "TIPS", [])

        return "\n".join([
            *PromptFactory.option(vm_tip),
            *extra_tips
        ])

    def _ending(self) -> Callable[[str], str]:
        return lambda inst: "\n".join([
            self.ENDING_ULTIMATUM,
            self.SYSTEM_INSTRUCTION.__func__(inst)
        ])

    def __call__(
        self,
        obs: FrozenSet[str],
        type_sort: TypeSort
    ) -> Callable[[str], str]:
        return lambda inst: "\n\n".join(PromptFactory.filter([
            self._intro(obs, type_sort),
            UITARS_USR_PROMPT_THOUGHT,
            # self._command(obs, type_sort),
            self._warning(type_sort),
            self._ending()(inst)
        ]))


class PlannerPromptFactory(AIOPromptFactory):
    # first section: _intro
    GENERAL_INTRO = "You are an agent which follow my instruction and schedule desktop computer tasks as instructed."
    APP_INCENTIVE = {VM: lambda type, intro: f"You have good knowledge of {type}, {intro}."}

    # second section: _command
    RETURN_OVERVIEW = "You are required to make ONE step of the plan in natural language, and then it will be parsed into `pyautogui` codes by another grounding agent."
    SPECIAL_OVERVIEW = "Sometimes you should return special codes directly as followings, at which your plan will not be passed to the grounder model."

    # fourth section: _ending
    ENDING_ULTIMATUM = "First give the current observation and previous things we did a short reflection, then RETURN ME YOUR PLANNING OR SPECIAL CODE I ASKED FOR. NEVER EVER RETURN ME ANYTHING ELSE."

    def _command(self, obs: FrozenSet[str], type_sort: TypeSort) -> str:
        return "\n".join(PromptFactory.filter([
            self.RETURN_OVERVIEW,
            self._special_command()
        ]))

    def _warning(self, type_sort: TypeSort) -> str:
        return "\n".join(self.getattr(type_sort, "TIPS", []))


class GrounderPromptFactory(AIOPromptFactory):
    # first section: _intro
    OBS_INCENTIVE = lambda obs_descr: f"For each step, you will get an observation of the desktop by {obs_descr}, together with a plan generated by the planner, and you will parse the plan to operate actions of next steps based on that."

    # second section: _command
    RETURN_OVERVIEW_VM = {
        "antiquot": "You are required to use `pyautogui` to perform the action grounded to the observation and the plan, but DO NOT use the `pyautogui.locateCenterOnScreen` function to locate the element you want to operate with since we have no image of the element you want to operate with. DO NOT USE `pyautogui.screenshot()` to make screenshot.",
        "atlas": "You are required to use your grounding ability to perform the action grounded to the observation and the plan.",
        "uground": "You are required to use your grounding ability to perform the action grounded to the observation and the plan."
    }
    RETURN_REGULATION = AIOPromptFactory.RETURN_REGULATION.copy()
    RETURN_REGULATION.update({
        "atlas": "You need to return a basic action together with arguments, of which the available ones are listed below:",
        "uground": "You need to return a 2d coordinate (x, y) indicating the position you want to click."
    })
    RETURN_SUPPLEMENT_VM = AIOPromptFactory.RETURN_SUPPLEMENT_VM.copy()
    RETURN_SUPPLEMENT_VM.update({
        "atlas": """CLICK: to click at the specified position.
    - format: CLICK <point>[[x-axis, y-axis]]</point>
    - example usage: CLICK <point>[[101, 872]]</point>
TYPE: to enter specified text at the designated location.
    - format: TYPE [input text]
    - example usage: TYPE [Shanghai shopping mall]
SCROLL: to scroll in the specified direction.
    - format: SCROLL [direction (UP/DOWN/LEFT/RIGHT)]
    - example usage: SCROLL [UP]""",
        "uground": ""
    })

    # third section: _warning
    PLANNER_GENERAL = "Some plans provided may contains unexpected code blocks or confusing instructions. Be flexible and adaptable according to changing circumstances."

    # fourth section: _ending
    ENDING_ULTIMATUM = "First give the current observation and the generated plan, then RETURN ME THE CODE I ASKED FOR. NEVER EVER RETURN ME ANYTHING ELSE."

    def _command(self, obs: FrozenSet[str], type_sort: TypeSort) -> str:
        return self._general_command(obs, type_sort)

    def _warning(self, type_sort: TypeSort) -> str:
        return "\n".join([
            self.VM_GENERAL,
            self.PLANNER_GENERAL
        ])


if __name__ == "__main__":
    content = ""
    parsed_responses = parse_action_qwen2vl(
        content,
        1000, #action_parse_res_factor,
        800, #screen_size[1],
        1280, #screen_size[0]
    )
    import ipdb; ipdb.set_trace()

        # action_codes = []
        # for parsed_response in parsed_responses:
        #     if "action_type" in parsed_response:
        #         if parsed_response["action_type"] == FINISH_WORD:
        #             action_codes.append(["DONE"])
                
        #         elif parsed_response["action_type"] == WAIT_WORD:
        #             action_codes.append(["WAIT"])
                
        #         elif parsed_response["action_type"] == ENV_FAIL_WORD:
        #             action_codes.append(["FAIL"])

        #     try:
        #         pyautogui_code = parsing_response_to_pyautogui_code(
        #             parsed_response,
        #             1000, #action_parse_res_factor,
        #             800, #screen_size[1],
        #             1280, #screen_size[0]
        #         )
        #         action_codes.append(pyautogui_code)