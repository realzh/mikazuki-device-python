import asyncio

from as7341 import AS7341
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
                ws2812_light = WS2812Light(client)
                as7341 = AS7341(client)
                ws2812 = WS2812(client)
                ds18b20_desktop_light = DS18B20(
                    client,
                    esp32c3_id="desktop-control",
                    device_id="desktop_light_temperature",
                    ds18b20_id="0x0800000075660628",
                )
                asyncio.create_task(ws2812_light.on_connected())
                asyncio.create_task(as7341.on_connected())
                asyncio.create_task(ws2812.on_connected())
                asyncio.create_task(ds18b20_desktop_light.on_connected())

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

                        asyncio.create_task(ws2812_light.on_all_message(message))
                        asyncio.create_task(as7341.on_all_message(message))
                        asyncio.create_task(ws2812.on_message(message))
                        asyncio.create_task(ds18b20_desktop_light.on_message(message))
                    except Exception as e:
                        print(f"Message processing error {e}. Continue to receive.")

        except Exception as e:
            print(f"连接失败: {e}")

        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
