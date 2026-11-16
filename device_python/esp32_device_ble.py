import asyncio
import traceback

import bleak
import bleak.exc

from device_python.esp32_device_base import ESP32DeviceBase
from device_python.log import bytes_to_str, get_logger

logger = get_logger("esp32_device_ble")


class ESP32DeviceBLE(ESP32DeviceBase):

    @classmethod
    async def scan_devices(cls):
        devices = []
        for device_addr, (device, adv) in (
            await bleak.BleakScanner.discover(timeout=0.5, return_adv=True)
        ).items():
            serial_number = adv.manufacturer_data.get(0xFFFF, b"").hex().upper()
            if adv.local_name == "MIKAZIIKI" and serial_number != "":
                devices.append(
                    {
                        "device_address": device_addr,
                        "serial_number": serial_number,
                        "channel": "ble",
                    }
                )

        return devices

    def __init__(self, address: str) -> None:
        super().__init__()
        self.address = address
        self.stream_reader = asyncio.StreamReader(limit=2**20)
        self.channel = "ble"

    async def on_ble_notify(self, sender, data: bytearray):
        try:
            self.stream_reader.feed_data(bytes(data))
            logger.debug("ble_notify", data=bytes_to_str(data))
        except:
            logger.exception()

    def on_ble_disconnected(self, bleak_client):
        self.stream_reader.feed_eof()

    async def on_open(self):
        self.ble_client = bleak.BleakClient(
            self.address, disconnected_callback=self.on_ble_disconnected
        )
        await self.ble_client.connect()
        self.ble_char = self.ble_client.services.get_characteristic("AB01")
        assert self.ble_char is not None
        assert "write" in self.ble_char.properties
        assert "indicate" in self.ble_char.properties
        await self.ble_client.start_notify(self.ble_char.uuid, self.on_ble_notify)
        await super().on_open()

    async def on_close(self):
        await super().on_close()
        await self.ble_client.disconnect()

    async def esp32_readline(self) -> bytes:
        line = await self.stream_reader.readline()
        if len(line) == 0:
            raise ConnectionError("Closed")
        return line

    async def esp32_write(self, data: bytes):
        logger.debug("esp32_write", data=bytes_to_str(data))
        assert self.ble_char is not None
        offset = 0
        retry = 0
        while offset < len(data):
            chunk = data[
                offset : offset + self.ble_char.max_write_without_response_size
            ]
            try:
                await self.ble_client.write_gatt_char(
                    self.ble_char.uuid, chunk, response=True
                )
                retry = 0
            except bleak.exc.BleakGATTProtocolError as e:
                if e.code == 0x84:
                    logger.warn(
                        "esp32_gatt_busy", retry=retry, chunk=bytes_to_str(chunk)
                    )
                    retry += 1
                    if retry >= 3:
                        raise
                    await asyncio.sleep(0.1)
                    continue
                else:
                    logger.warn('esp32_gatt_busy_max_retry')
                    raise
            offset += len(chunk)
