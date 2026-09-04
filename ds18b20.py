import json
from uuid import uuid4

import esp32
from device import Device
from web_socket import WebSocketClient


class DS18B20(Device):
    type = "ds18b20"

    def __init__(
        self, client: WebSocketClient, esp32c3_id: str, device_id: str, ds18b20_id: str
    ) -> None:
        super().__init__(client)
        self.esp32c3_id = esp32c3_id
        self.device_id = device_id
        self.ds18b20_id = ds18b20_id

    async def send_command(self, command_str: str):
        return await esp32.send_command(self.esp32c3_id, command_str)

    async def measure(self):
        result = json.loads(await self.send_command("ds18b20_measure"))
        for dev_temp in result:
            if dev_temp.get("address") == self.ds18b20_id:
                return dev_temp.get("temperature")

    async def on_message(self, message: dict):
        action = message.get("action")
        if action == "measure":
            request_id = message.get("request_id", uuid4())
            temperature = await self.measure()
            if temperature is not None:
                await self.send(
                    {
                        "action": "measure-result",
                        "request_id": request_id,
                        "success": True,
                        "temperature": temperature,
                    }
                )
            else:
                await self.send(
                    {
                        "action": "measure-result",
                        "request_id": request_id,
                        "success": False,
                    }
                )
