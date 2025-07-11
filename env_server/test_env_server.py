import requests
import json
import time

# BASE_URL = "http://localhost:10010"

def test_root():
    response = requests.get(f"{BASE_URL}/")
    assert response.status_code == 200
    print("Root endpoint test passed")

def test_create_env_api():
    response = requests.post(f"http://localhost:10001/create_env_api", json={})
    print(response)
    global BASE_URL
    BASE_URL = f"http://localhost:{response.json()['port']}"
    assert response.status_code == 200
    assert response.json().get("success") == True
    print("Start endpoint test passed")


def test_start():
    # payload = {
    #     "vm_name": "Ubuntu.qcow2",
    #     "action_space": "pyautogui",
    #     "screen_width": 1920,
    #     "screen_height": 1080,
    #     "headless": True,
    #     "require_a11y_tree": False,
    #     "os_type": "Ubuntu"
    # }
    response = requests.post(f"{BASE_URL}/start", json={})
    print(response)
    assert response.status_code == 200
    assert response.json().get("success") == True
    print("Start endpoint test passed")

def test_get_task_config():
    payload = {
        "domain": "TeXstudio",
        "example_id": "A-01"
    }
    response = requests.post(f"{BASE_URL}/get_task_config", json=payload)
    print("Task config response:", response.json())
    print("Get task config endpoint test completed")

def test_reset():
    payload = {
        "domain": "TeXstudio",
        "example_id": "A-01"
    }
    response = requests.post(f"{BASE_URL}/reset", json=payload)
    print("Reset response:", response)
    print("Reset endpoint test completed")

def test_step():
    payload = {
        "action": "do(action=\"Tap\", element=[0.856, 0.916])",
        "pause": 2
    }
    response = requests.post(f"{BASE_URL}/step", json=payload)
    # print("Step response:", response.json())
    print("Step endpoint test completed")

def test_evaluate():
    response = requests.get(f"{BASE_URL}/evaluate")
    print("Evaluate response:", response.json())
    print("Evaluate endpoint test completed")

def test_vm_platform():
    response = requests.get(f"{BASE_URL}/vm_platform")
    assert response.status_code == 200
    print("VM platform response:", response.json())
    print("VM platform endpoint test passed")

def test_vm_screen_size():
    response = requests.get(f"{BASE_URL}/vm_screen_size")
    assert response.status_code == 200
    print("VM screen size response:", response.json())
    print("VM screen size endpoint test passed")

def test_close():
    response = requests.post(f"{BASE_URL}/close")
    assert response.status_code == 200
    assert response.json().get("success") == True
    print("Close endpoint test passed")

if __name__ == "__main__":
    print("Starting API tests...")
    
    # Test sequence
    test_create_env_api()
    time.sleep(10)
    test_root()
    time.sleep(1)
    test_start()
    time.sleep(1)
    test_get_task_config()
    time.sleep(1)
    test_reset()
    # time.sleep(1)
    # test_step()
    # time.sleep(10)
    # test_evaluate()
    # time.sleep(1)
    # # test_vm_platform()
    # # time.sleep(1)
    # test_vm_screen_size()
    # time.sleep(1)
    # test_close()
    
    print("All tests completed successfully!")
        