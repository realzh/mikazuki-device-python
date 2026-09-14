from device_python.connection import Connection

# from device_python.esp32 import ESP32Device

from .device import Device, action


class WS2812(Device):

    def __init__(
        self,
        *,
        ws_connection: Connection,
        device_id: str | None = None,
        esp32_device,
        gpio_num: int,
    ) -> None:
        super().__init__(ws_connection=ws_connection, device_id=device_id)
        self.esp32_device = esp32_device
        self.gpio_num = gpio_num

    async def open(self):
        await super().open()
        await self.set_state("gpio_num", self.gpio_num)

    @action
    async def set_gpio_num(self, gpio_num: int):
        self.gpio_num = gpio_num
        await self.set_state("gpio_num", self.gpio_num)

    @action
    async def set(self, *, color: str, count: int):
        """Set the color of ws2812"""
        return await self.esp32_device.send_command(
            "ws2812_set_single_color",
            {"gpio_num": self.gpio_num, "color": color, "count": count},
        )

    @action
    async def on(self):
        """Switch on ws2812, color is #FF9038"""
        return await self.esp32_device.send_command(
            "ws2812_set_single_color",
            {"gpio_num": self.gpio_num, "color": "#FF9038", "count": 144},
        )

    @action
    async def off(self):
        """Switch off ws2812"""
        return await self.esp32_device.send_command(
            "ws2812_set_single_color",
            {"gpio_num": self.gpio_num, "color": "#000000", "count": 144},
        )
