import command
from device import Device


async def send_command(command_str: str):
    return await command.send_command("spectrum-test", command_str)


status = "unknown"


class WS2812(Device):
    type = "ws2812"

    device_id = "spectrum-test"

    async def on_connected(self):
        await super().on_connected()
        await send_command("ws2812_init")

    async def on_message(self, message: dict):
        action = message.get("action")
        if action == "set":
            color = message.get("color", "#000000")
            offset = message.get("offset", 0)
            count = message.get("count", 0)
            await send_command(f"ws2812_set {color} {offset} {count}")
