import esp32_command
from device import Device, action
from web_socket import WebSocketClient


class WS2812(Device):

    def __init__(
        self,
        ws: WebSocketClient,
        device_id: str,
        esp32_send_command: esp32_command.AsyncSendCommand,
    ) -> None:
        super().__init__(ws, device_id)
        self.esp32_send_command = esp32_send_command

    async def on_connected(self):
        await super().on_connected()
        await self.set_state("state", "ready")

    @action(method="post")
    async def set(self, *, color: str, offset: int = 0, count: int):
        """Set the color of ws2812"""
        esp32_response = await self.esp32_send_command(
            f"ws2812_set {color} {offset} {count}"
        )
        await self.set_state("tag", color)
        await self.set_state("tag_color", color)
        return {"esp32_response": esp32_response}

    @action(method="post")
    async def on(self):
        """Switch on ws2812, color is #FF9038"""
        esp32_response = await self.esp32_send_command(f"ws2812_set #FF9038 0 144")
        await self.set_state("tag", "on")
        await self.set_state("tag_color", "green")
        return {"esp32_response": esp32_response}

    @action(method="post")
    async def off(self):
        """Switch off ws2812"""
        esp32_response = await self.esp32_send_command(f"ws2812_set #000000 0 144")
        await self.set_state("tag", "off")
        await self.set_state("tag_color", "gray")
        return {"esp32_response": esp32_response}
