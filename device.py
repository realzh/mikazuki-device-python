import inspect

from web_socket import WebSocketClient


def action(method="get"):
    def decorator(func):
        func.is_action = True
        func.http_method = method
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


class Device:

    def __init__(self, ws: WebSocketClient, device_id: str) -> None:
        self.ws = ws
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
                    }
                )

    async def send(self, message: dict):
        message["type"] = "device"
        message["device_id"] = self.device_id
        await self.ws.send(message)

    async def on_connected(self):
        await self.send({"action": "register"})
        for action in self.actions:
            await self.send(
                {
                    "action": "register-action",
                    "name": action["action"],
                    "method": action["method"],
                    "parameters": [
                        {
                            "name": x["name"],
                            "type": x["type_str"],
                            "optional": x["optional"],
                        }
                        for x in action["parameters"]
                    ],
                }
            )

    async def on_all_message(self, message: dict):
        type = message.get("type")
        device_id = message.get("device_id")
        if type != "device" or device_id != self.device_id:
            return
        await self.on_message(message)

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
                await self.send({"request_id": request_id, "success": True, **result})
            except Exception as e:
                await self.send(
                    {"request_id": request_id, "success": False, "reason": str(e)}
                )

    async def on_request(self, action: str, method: str, message: dict) -> dict:
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
        return result or {}
