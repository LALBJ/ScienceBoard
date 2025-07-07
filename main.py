import sys
import os

sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding="utf-8")
from sci import Automata, Tester, OBS
from sci import AllInOne, AIOAgent
from sci import SeeAct, PlannerAgent, GrounderAgent
from sci import Disentangled, CoderAgent, ActorAgent

# commercial models
gpt_4o = lambda cls: Automata(
    model_style="openai",
    base_url="https://api.openai.com/v1/chat/completions",
    model_name="gpt-4o-2024-08-06",
    api_key=os.environ["OPENAI_API_KEY"],
    proxy=os.environ["HTTPX_PROXY"],
    overflow_style="openai_gpt"
)(cls)

gpt_o3 = lambda cls: Automata(
    model_style="openai",
    base_url="https://api.openai.com/v1/chat/completions",
    model_name="o3-mini-2025-01-31",
    api_key=os.environ["OPENAI_API_KEY"],
    proxy=os.environ["HTTPX_PROXY"],
    overflow_style="openai_gpt",
    max_tokens=None,
    top_p=None
)(cls)

gemini_2 = lambda cls: Automata(
    model_style="openai",
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
    model_name="gemini-2.0-flash-exp",
    api_key=os.environ["GOOGLE_API_KEY"],
    proxy=os.environ["HTTPX_PROXY"],
    overflow_style="openai_gpt"
)(cls)

claude_3 = lambda cls: Automata(
    model_style="anthropic",
    base_url="https://api.anthropic.com/v1/messages",
    model_name="claude-3-7-sonnet-20250219",
    api_key=os.environ["ANTHROPIC_API_KEY"],
    proxy=os.environ["HTTPX_PROXY"],
    overflow_style="anthropic"
)(cls)

# open-source models
qwen25_vl = lambda cls: Automata(
    model_style="openai",
    base_url=os.environ["QWEN_VL_URL"],
    model_name=os.environ["QWEN_VL_NAME"],
    overflow_style="openai_lmdeploy",
    hide_text=True
)(cls)

intern_vl = lambda cls: Automata(
    model_style="openai",
    base_url=os.environ["INTERN_VL_URL"],
    model_name=os.environ["INTERN_VL_NAME"],
    overflow_style="openai_lmdeploy",
    hide_text=True
)(cls)

qvq = lambda cls: Automata(
    model_style="openai",
    base_url=os.environ["QVQ_VL_URL"],
    model_name=os.environ["QVQ_VL_NAME"],
    overflow_style="openai_lmdeploy",
    hide_text=True
)(cls)

# grounding models
os_atlas = lambda cls: Automata(
    model_style="openai",
    base_url=os.environ["OS_ACT_URL"],
    model_name=os.environ["OS_ACT_NAME"],
    overflow_style="openai_lmdeploy",
    code_style="atlas"
)(cls)

gui_actor = lambda cls: Automata(
    model_style="gui_actor",
    base_url=os.environ["GUI_ACTOR_URL"],
    model_name=os.environ["GUI_ACTOR_NAME"],
    code_style="gui_actor"
)(cls)

uground = lambda cls: Automata(
    model_style="openai",
    base_url=os.environ["UGROUND_URL"],
    model_name=os.environ["UGROUND_NAME"],
    overflow_style="openai_lmdeploy",
    code_style="uground"
)(cls)

tars_dpo = lambda cls: Automata(
    model_style="openai",
    base_url="http://10.140.60.177:30009/v1/chat/completions",#os.environ["TARS_DPO_URL"],
    model_name="ui-tars",#os.environ["TARS_DPO_NAME"],
    overflow_style="openai_lmdeploy",
    code_style="uitars1_5"
)(cls)


# this file somehow acts as a config file
# with some sensitive contents hidden in env
if __name__ == "__main__":
    AIO_NAME = "tars_dpo"
    AIO_GROUP = AllInOne(tars_dpo(AIOAgent))

    SA_NAME = "tars_dpo->tars_dpo"
    SA_GROUP = SeeAct(tars_dpo(PlannerAgent), tars_dpo(GrounderAgent))

    # Disentangled for screenshot setting
    DT_NAME = "gpt_4o->gui-actor"
    DT_GROUP = Disentangled(gpt_4o(CoderAgent), gui_actor(ActorAgent))

    # register a tester and execute it
    # Tester(
    #     tasks_path="./tasks/VM",
    #     logs_path=f"./logs/{AIO_NAME}-raw-textual",
    #     community=AIO_GROUP,
    #     vm_path=os.environ["VM_PATH"],
    # )()

    # alternative for Tester.__call__()
    # execute tasks one by one immediately
    Tester.plan([
        {
            "tasks_path": "./tasks/VM_with_info",
            "logs_path": f"./logs/{AIO_NAME}-vm-screenshot",
            "community": AIO_GROUP,
            "vm_path": os.environ["VM_PATH"],
            "obs_types": {OBS.screenshot},
            "headless": True
        },
        # {
        #     "tasks_path": "./tasks/VM",
        #     "logs_path": f"./logs/{SA_NAME}-vm-screenshot",
        #     "community": SA_GROUP,
        #     "vm_path": os.environ["VM_PATH"],
        #     "obs_types": {OBS.screenshot},
        #     "headless": True
        # },
        # {
        #     "tasks_path": "./tasks/VM",
        #     "logs_path": f"./logs/{AIO_NAME}-vm-a11y_tree",
        #     "community": AIO_GROUP,
        #     "vm_path": os.environ["VM_PATH"],
        #     "obs_types": {OBS.a11y_tree},
        #     "headless": True
        # },
        # {
        #     "tasks_path": "./tasks/VM",
        #     "logs_path": f"./logs/{AIO_NAME}-vm-screenshot+a11y_tree",
        #     "community": AIO_GROUP,
        #     "vm_path": os.environ["VM_PATH"],
        #     "obs_types": {OBS.screenshot, OBS.a11y_tree},
        #     "headless": True
        # },
        # {
        #     "tasks_path": "./tasks/VM",
        #     "logs_path": f"./logs/{AIO_NAME}-vm-set_of_marks",
        #     "community": AIO_GROUP,
        #     "vm_path": os.environ["VM_PATH"],
        #     "obs_types": {OBS.set_of_marks},
        #     "headless": True
        # }
    ])
