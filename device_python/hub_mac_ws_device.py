from device_python.ws_connection import WSConnection
from device_python.ws_device import WSDevice, action
from device_python.esp32_ws_device_usb import ESP32WSDeviceUSB
from device_python.esp32_device_usb import ESP32DeviceUSB


class MacHubWSDevice(WSDevice):
    def __init__(self, *, ws_connection: WSConnection):
        super().__init__(ws_connection=ws_connection, device_id="hub-mac")
        self.esp32_ws_devices = set[ESP32WSDeviceUSB]()

    async def esp32_on_close(self, esp32_ws_device: ESP32WSDeviceUSB):
        if esp32_ws_device in self.esp32_ws_devices:
            self.esp32_ws_devices.remove(esp32_ws_device)

    async def on_open(self):
        await super().on_open()
        await self.esp32_enumerate_devices()

    async def on_close(self):
        await super().on_close()
        for esp32_ws_device in self.esp32_ws_devices.copy():
            await esp32_ws_device.close()

    @action
    async def esp32_enumerate_devices(self):
        for esp32_ws_device in self.esp32_ws_devices.copy():
            await esp32_ws_device.close()
        ports = await ESP32DeviceUSB.enumerate_device_ports()

        for port in ports:
            esp32_device = ESP32DeviceUSB(port)
            esp32_ws_device = ESP32WSDeviceUSB(
                ws_connection=self.ws_connection,
                esp32_device=esp32_device,
            )
            self.esp32_ws_devices.add(esp32_ws_device)
            esp32_ws_device.on_close_callbacks.add(self.esp32_on_close)
            await esp32_ws_device.open()
