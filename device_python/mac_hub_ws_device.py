from device_python.esp32_device_bt import ESP32DeviceBT
from device_python.esp32_device_usb import ESP32DeviceUSB
from device_python.esp32_ws_device import ESP32WSDevice
from device_python.ws_connection import WSConnection
from device_python.ws_device import WSDevice, action


class MacHubWSDevice(WSDevice):
    def __init__(self, *, ws_connection: WSConnection):
        super().__init__(ws_connection=ws_connection, device_id="mac-hub")
        self.esp32_ws_devices = set[ESP32WSDevice]()

    async def esp32_on_close(self, esp32_ws_device: ESP32WSDevice):
        if esp32_ws_device in self.esp32_ws_devices:
            self.esp32_ws_devices.remove(esp32_ws_device)

    async def on_open(self):
        await super().on_open()
        await self.open_esp32_devices()

    async def on_close(self):
        await super().on_close()
        await self.close_all_esp32_devices()

    @action
    async def open_esp32_devices(self):
        await self.close_all_esp32_devices()

        usb_ports = await ESP32DeviceUSB.scan_devices()
        await self.set_state("esp32_usb_ports", usb_ports)

        bt_addresses = await ESP32DeviceBT.scan_devices()
        await self.set_state("esp32_bt_addresses", bt_addresses)

        for port in usb_ports:
            esp32_device = ESP32DeviceUSB(port)
            esp32_ws_device = ESP32WSDevice(
                ws_connection=self.ws_connection,
                esp32_device=esp32_device,
                channel="usb",
            )
            self.esp32_ws_devices.add(esp32_ws_device)

        for address in bt_addresses:
            esp32_device = ESP32DeviceBT(address)
            esp32_ws_device = ESP32WSDevice(
                ws_connection=self.ws_connection,
                esp32_device=esp32_device,
                channel="bt",
            )
            self.esp32_ws_devices.add(esp32_ws_device)

        for esp32_ws_device in self.esp32_ws_devices:
            esp32_ws_device.on_close_callbacks.add(self.esp32_on_close)
            await esp32_ws_device.open()

    @action
    async def close_all_esp32_devices(self):
        for esp32_ws_device in self.esp32_ws_devices.copy():
            await esp32_ws_device.close()
