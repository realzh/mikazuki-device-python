import asyncio

import serial.tools.list_ports

from device_python.esp32_device_base import ESP32DeviceBase


class ESP32DeviceUSB(ESP32DeviceBase):

    @classmethod
    async def scan_devices(cls):
        ports: list[str] = []
        for p in serial.tools.list_ports.comports():
            if p.product == "mikatsuki":
                ports.append(p.device)
        return ports

    def __init__(self, port: str):
        super().__init__()
        self.port = port
        self.channel = "usb"

    async def on_open(self):
        self.serial = serial.Serial(self.port)
        await super().on_open()

    async def on_close(self):
        await super().on_close()
        self.serial.close()

    async def esp32_readline(self) -> bytes:
        return await asyncio.to_thread(self.serial.readline)

    async def esp32_write(self, data: bytes):
        await asyncio.to_thread(self.serial.write, data)
