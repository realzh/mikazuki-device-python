from dataclasses import dataclass
import inspect
import traceback
from typing import Any, Awaitable, Callable, Literal, Optional

from bidict import bidict

AsyncSend = Callable[[dict], Awaitable[None]]

action_index = 0


def action(func):

    func.is_action = True

    return func


parameter_types = bidict(
    {
        "string": str,
        "integer": int,
        "boolean": bool,
        "float": float,
    }
)


@dataclass
class Parameter:
    name: str
    type: str
    optional: bool


@dataclass
class Action:
    name: str
    parameters: list[Parameter]
    description: Optional[str]
    handler: Callable[..., Awaitable[Any]]


class Device:

    def __init__(self, *, socket_send: AsyncSend, device_id: str | None = None) -> None:
        self.socket_send = socket_send
        self.device_id = device_id
        self.actions: list[Action] = []

    async def open(self):
        assert self.device_id is not None
        print(f"Device {self.device_id} open")
        self.generate_actions_from_decorators()
        await self.send({"action": "register"})
        self.actions.extend(self.generate_actions_from_decorators())
        await self.send_action_definitions()

    async def close(self):
        print(f"Device {self.device_id} close")

    async def __aenter__(self):
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    def generate_actions_from_decorators(self):
        actions: list[Action] = []
        for python_method_name in dir(self):
            python_method = getattr(self, python_method_name)
            if hasattr(python_method, "is_action") and python_method.is_action:
                assert inspect.iscoroutinefunction(python_method)
                action_name = python_method_name
                sig = inspect.signature(python_method)
                parameters = [
                    Parameter(
                        param_name,
                        parameter_types.inverse[param_def.annotation],
                        param_def.default is not inspect.Parameter.empty,
                    )
                    for param_name, param_def in sig.parameters.items()
                ]

                actions.append(
                    Action(
                        action_name,
                        parameters,
                        python_method.__doc__,
                        python_method,
                    )
                )
        return actions

    async def send(self, message: dict):
        message["type"] = "device"
        message["device_id"] = self.device_id
        await self.socket_send(message)

    async def send_action_definitions(self):
        actions_dict = []
        for action in self.actions:
            actions_dict.append(
                {
                    "name": action.name,
                    "parameters": [
                        {
                            "name": x.name,
                            "type": x.type,
                            "optional": x.optional,
                        }
                        for x in action.parameters
                    ],
                    "description": action.description,
                }
            )
        actions_dict.sort(key=lambda x: x["name"])
        await self.send({"action": "set-actions", "actions": actions_dict})

    async def on_message(self, message: dict):
        if not isinstance(message, dict):
            print(f"message {message} is not dict")
            return

        type = message.get("type")
        device_id = message.get("device_id")

        if type != "device" or device_id != self.device_id:
            return

        action = message.get("action")
        name = message.get("name")
        request_id = message.get("request_id")

        if request_id and action == "request" and name:
            try:
                result = await self.on_request(name, message)
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

    async def on_request(self, name: str, message: dict):
        action_def = None
        for iter_action in self.actions:
            if name == iter_action.name:
                action_def = iter_action
        if not action_def:
            raise Exception(f"action {name} not found")

        parameters = message.get("parameters")
        if not isinstance(parameters, dict):
            raise Exception(f"parameters is not dict")

        params = {}
        for param_def in action_def.parameters:
            if param_def.name not in parameters:
                if not param_def.optional:
                    raise Exception(f"param {param_def.name} not found")
                else:
                    continue
            param_value = parameters[param_def.name]
            if not isinstance(param_value, parameter_types[param_def.type]):
                raise Exception(f"param {param_def.name} is not type {param_def.type}")
            params[param_def.name] = param_value
        result = await action_def.handler(**params)
        return result

    async def set_state(self, key: str, value):
        await self.send({"action": "set-state", "key": key, "value": value})
