from web_socket import WebSocketClient


class Device:
    type = "generic-device"
    device_id = ""

    def __init__(self, client: WebSocketClient) -> None:
        self.ws = client

    async def send(self, message: dict):
        message["type"] = self.type
        message["device_id"] = self.device_id
        await self.ws.send(message)

    async def on_connected(self):
        await self.send({"action": "register"})

    async def on_message(self, message: dict):
        raise NotImplementedError()

    async def on_all_message(self, message: dict):
        type = message.get("type")
        device_id = message.get("device_id")
        if type != self.type or device_id != self.device_id:
            return
        await self.on_message(message)
