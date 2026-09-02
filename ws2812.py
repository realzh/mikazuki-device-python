import command
from device import Device, action
from web_socket import WebSocketClient


class WS2812(Device):

    def __init__(self, ws: WebSocketClient, device_id: str, esp32c3_id: str) -> None:
        super().__init__(ws, device_id)
        self.esp32c3_id = esp32c3_id

    async def on_connected(self):
        await super().on_connected()
        await self.set_state("state", "ready")

    @action(method="post")
    async def set(self, *, color: str, offset: int = 0, count: int):
        """Set the color of ws2812"""
        esp32_response = await command.send_command(
            self.esp32c3_id, f"ws2812_set {color} {offset} {count}", assert_success=True
        )
        await self.set_state("tag", color)
        await self.set_state("tag_color", color)
        return {"esp32_response": esp32_response}

    @action(method="post")
    async def on(self):
        """Switch on ws2812, color is #FF9038"""
        esp32_response = await command.send_command(
            self.esp32c3_id, f"ws2812_set #FF9038 0 144", assert_success=True
        )
        await self.set_state("tag", "on")
        await self.set_state("tag_color", "green")
        return {"esp32_response": esp32_response}

    @action(method="post")
    async def off(self):
        """Switch off ws2812"""
        esp32_response = await command.send_command(
            self.esp32c3_id, f"ws2812_set #000000 0 144", assert_success=True
        )
        await self.set_state("tag", "off")
        await self.set_state("tag_color", "gray")
        return {"esp32_response": esp32_response}
