import asyncio

from as7341 import AS7341
from device import Device
from ds18b20 import DS18B20
from web_socket import WebSocketClient
from ws2812 import WS2812
from ws2812_light import WS2812Light


async def main():
    uri = "ws://localhost:8000/api/ws"

    while True:
        try:
            async with WebSocketClient(uri) as client:
                print("客户端已启动")
                await client.send(
                    {
                        "type": "socket",
                        "action": "set-endpoint-name",
                        "name": "device-esp32c3",
                    }
                )

                devices: list[Device] = [
                    WS2812(client, "ws2812-desktop", "desktop-control"),
                ]
                for device in devices:
                    asyncio.create_task(device.on_connected())

                while True:
                    try:
                        message = await client.receive()
                        print(f"receive: {message}")
                    except Exception as e:
                        print(f"Receive error {e}. Break socket connection")
                        break

                    try:
                        type = message.get("type")

                        if type == "ping":
                            ping_id = message.get("ping_id")
                            await client.send({"type": "pong", "ping_id": ping_id})
                        for device in devices:
                            asyncio.create_task(device.on_all_message(message))

                    except Exception as e:
                        print(f"Message processing error {e}. Continue to receive.")

        except Exception as e:
            print(f"连接失败: {e}")

        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
