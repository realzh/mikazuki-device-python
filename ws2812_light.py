import asyncio

from command import assert_connection, send_command
from device import Device
from web_socket import WebSocketClient


status = "unknown"


async def switch_on():
    global status
    await send_command("ws2812_set warm 1.0 0 144 0")
    status = "on"


async def switch_off():
    global status
    await send_command("ws2812_set warm 0.0 0 144 0")
    status = "off"


class WS2812Light(Device):
    type = "ws2812-light"

    id = "ws2812-light-desktop"

    async def send_status(self):
        await self.send({"action": "status", "status": status})

    async def on_connected(self):
        await super().on_connected()
        await send_command("ws2812_init")
        await self.send({"action": "name", "name": "Desktop"})
        await self.send_status()

    async def on_message(self, message: dict):
        action = message.get("action")
        if action == "on":
            await switch_on()
            await self.send_status()
        elif action == "off":
            await switch_off()
            await self.send_status()
