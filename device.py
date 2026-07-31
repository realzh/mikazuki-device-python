from web_socket import WebSocketClient


class Device:
    type = "generic-device"
    id = ""

    def __init__(self, client: WebSocketClient) -> None:
        self.ws = client

    async def send(self, message: dict):
        message["type"] = self.type
        message["id"] = self.id
        await self.ws.send(message)

    async def on_connected(self):
        await self.send({"action": "register"})

    async def on_message(self, message: dict):
        raise NotImplementedError()

    async def on_all_message(self, message: dict):
        type = message.get("type")
        id = message.get("id")
        if type != self.type or id != self.id:
            return
        await self.on_message(message)
