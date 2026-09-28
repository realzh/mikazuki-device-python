from device_python.esp32_device import ESP32Device
from device_python.esp32_ws_device import ESP32WSDevice
from device_python.ws_connection import WSConnection
from device_python.ws_device import WSDevice, action


class MacHubWSDevice(WSDevice):
    def __init__(self, *, ws_connection: WSConnection):
        super().__init__(ws_connection=ws_connection, device_id="hub-mac")
        self.esp32_ws_devices = set[ESP32WSDevice]()

    async def esp32_on_close(self, esp32_ws_device: ESP32WSDevice):
        if esp32_ws_device in self.esp32_ws_devices:
            self.esp32_ws_devices.remove(esp32_ws_device)

    async def on_open(self):
        await super().on_open()
        await self.enumerate_esp32_devices()

    async def on_close(self):
        await super().on_close()
        await self.close_all_esp32_devices()

    @action
    async def enumerate_esp32_devices(self):
        await self.close_all_esp32_devices()
        ports = await ESP32Device.enumerate_device_ports()

        for port in ports:
            esp32_device = ESP32Device(port)
            esp32_ws_device = ESP32WSDevice(
                ws_connection=self.ws_connection,
                esp32_device=esp32_device,
            )
            self.esp32_ws_devices.add(esp32_ws_device)
            esp32_ws_device.on_close_callbacks.add(self.esp32_on_close)
            await esp32_ws_device.open()

    @action
    async def close_all_esp32_devices(self):
        for esp32_ws_device in self.esp32_ws_devices.copy():
            await esp32_ws_device.close()
