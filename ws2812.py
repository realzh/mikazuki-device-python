import esp32
from device import AsyncSend, Device, action


class WS2812(Device):

    def __init__(
        self,
        *,
        esp32_send_command: esp32.AsyncSendCommand,
        gpio_num: int,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.esp32_send_command = esp32_send_command
        self.gpio_num = gpio_num

    async def on_connected(self):
        await super().on_connected()

    @action(method="post")
    async def set(self, *, color: str, count: int):
        """Set the color of ws2812"""
        esp32_response = await self.esp32_send_command(
            f"ws2812_set_single_color {self.gpio_num} {color} {count}"
        )
        await self.set_state("color", color)
        return {"esp32_response": esp32_response}

    @action(method="post")
    async def on(self):
        """Switch on ws2812, color is #FF9038"""
        esp32_response = await self.esp32_send_command(
            f"ws2812_set_single_color {self.gpio_num} #FF9038 144"
        )
        await self.set_state("color", "#FF9038")
        return {"esp32_response": esp32_response}

    @action(method="post")
    async def off(self):
        """Switch off ws2812"""
        esp32_response = await self.esp32_send_command(
            f"ws2812_set_single_color {self.gpio_num} #000000 144"
        )
        await self.set_state("color", "#000000")
        return {"esp32_response": esp32_response}
