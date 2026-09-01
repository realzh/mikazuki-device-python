import command
from device import Device, action
from web_socket import WebSocketClient


class WS2812(Device):

    def __init__(self, ws: WebSocketClient, device_id: str, esp32c3_id: str) -> None:
        super().__init__(ws, device_id)
        self.esp32c3_id = esp32c3_id

    @action(method="post")
    async def set(self, *, color: str, offset: int = 0, count: int):
        esp32_response = await command.send_command(
            self.esp32c3_id, f"ws2812_set {color} {offset} {count}", assert_success=True
        )
        return {"esp32_response": esp32_response}

    @action(method="post")
    async def on(self):
        esp32_response = await command.send_command(
            self.esp32c3_id, f"ws2812_set #FF9038 0 144", assert_success=True
        )
        return {"esp32_response": esp32_response}

    @action(method="post")
    async def off(self):
        esp32_response = await command.send_command(
            self.esp32c3_id, f"ws2812_set #000000 0 144", assert_success=True
        )
        return {"esp32_response": esp32_response}
