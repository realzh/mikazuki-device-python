import inspect
import traceback
from typing import Awaitable, Callable, Literal

AsyncSend = Callable[[dict], Awaitable[None]]

action_index = 0


def action(method: Literal["get"] | Literal["post"]):
    def decorator(func):
        global action_index
        action_index += 1
        func.is_action = True
        func.http_method = method
        func.action_index = action_index
        return func

    return decorator


def type_to_string(type):
    if type == str:
        return "string"
    if type == int:
        return "integer"
    if type == bool:
        return "boolean"
    if type == float:
        return "float"
    return str(type)


def string_to_type(type):
    if type == "string":
        return str
    if type == "integer":
        return int
    if type == "boolean":
        return bool
    if type == "float":
        return float
    return


class Device:

    def __init__(self, *, socket_send: AsyncSend, device_id: str) -> None:
        self.socket_send = socket_send
        self.device_id = device_id
        self.actions = []
        self.collect_actions()

    def collect_actions(self):
        for python_method_name in dir(self):
            python_method = getattr(self, python_method_name)
            if hasattr(python_method, "is_action") and python_method.is_action:
                action_name = python_method_name
                http_method = getattr(python_method, "http_method")
                sig = inspect.signature(python_method)
                parameters = [
                    {
                        "name": param_name,
                        "type": param_def.annotation,
                        "type_str": type_to_string(param_def.annotation),
                        "optional": param_def.default is not inspect.Parameter.empty,
                    }
                    for param_name, param_def in sig.parameters.items()
                ]

                self.actions.append(
                    {
                        "action": action_name,
                        "method": http_method,
                        "handler": python_method,
                        "parameters": parameters,
                        "description": python_method.__doc__,
                        "action_index": python_method.action_index,
                    }
                )
        self.actions.sort(key=lambda x: x["action_index"])

    async def send(self, message: dict):
        message["type"] = "device"
        message["device_id"] = self.device_id
        await self.socket_send(message)

    async def send_action_definitions(self):
        actions = []
        for action in self.actions:
            actions.append(
                {
                    "name": action["action"],
                    "method": action["method"],
                    "parameters": [
                        {
                            "name": x["name"],
                            "type": x["type_str"],
                            "optional": x["optional"],
                        }
                        for x in action.get("parameters", [])
                    ],
                    "description": action.get("description"),
                }
            )
        await self.send({"action": "set-actions", "actions": actions})

    async def on_connected(self):
        print(f"Device {self.device_id} connected")
        await self.send({"action": "register"})
        await self.send_action_definitions()

    async def on_disconnected(self):
        print(f"Device {self.device_id} disconnected")

    async def on_message(self, message: dict):
        type = message.get("type")
        device_id = message.get("device_id")

        if type != "device" or device_id != self.device_id:
            return

        request_id = message.get("request_id")
        action = message.get("action")
        method = message.get("method")

        if request_id and action and method:
            try:
                result = await self.on_request(action, method, message)
                await self.send(
                    {"request_id": request_id, "success": True, "result": result}
                )
            except Exception as e:
                stacktrace = traceback.format_exc()

                await self.send(
                    {
                        "request_id": request_id,
                        "success": False,
                        "reason": str(e),
                        "stacktrace": str(stacktrace),
                    }
                )

    async def on_request(self, action: str, method: str, message: dict):
        fount_action = None
        for action_def in self.actions:
            if action == action_def["action"] and method == action_def["method"]:
                fount_action = action_def
        if not fount_action:
            raise Exception(f"action {action} {method} not found")

        handler = fount_action["handler"]
        params = {}
        for param_def in fount_action["parameters"]:
            if param_def["name"] not in message and not param_def["optional"]:
                raise Exception(f"param {param_def['name']} not found")
            if param_def["name"] not in message and param_def["optional"]:
                continue
            param_value = message[param_def["name"]]
            if not isinstance(param_value, param_def["type"]):
                raise Exception(
                    f"param {param_def['name']} is not type {param_def['type_str']}"
                )
            params[param_def["name"]] = param_value
        result = await handler(**params)
        return result

    async def set_state(self, key: str, value):
        await self.send({"action": "set-state", "key": key, "value": value})
