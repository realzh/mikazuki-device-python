import asyncio
import traceback

from device_python.esp32_device_ble import ESP32DeviceBLE
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
        await self.set_state(
            "esp32_devices", [x.device_id for x in self.esp32_ws_devices]
        )

    async def on_open(self):
        await super().on_open()
        await self.open_esp32_devices()
        self.tasks.add(asyncio.create_task(self.task_watch_connected_devices())
)
    async def on_close(self):
        await super().on_close()
        await self.close_all_esp32_devices()

    @action
    async def open_esp32_devices(self):
        connected_devices = []
        connected_devices.extend(await ESP32DeviceUSB.scan_devices())
        connected_devices.extend(await ESP32DeviceBLE.scan_devices())
        device_serial_numbers = set[str]()
        for dev in connected_devices:
            device_serial_numbers.add(dev["serial_number"])

        channel_priority = {
            "usb": 0,
            "ble": 1,
        }
        selected_devices = []
        for sn in device_serial_numbers:
            selected_device = None
            for dev in connected_devices:
                if dev["serial_number"] == sn:
                    if selected_device == None:
                        selected_device = dev
                    elif (
                        channel_priority[dev["channel"]]
                        < channel_priority[selected_device["channel"]]
                    ):
                        selected_device = dev
            if selected_device:
                selected_devices.append(selected_device)
        opened_devices = []

        for selected_dev in selected_devices:
            if any(
                [
                    x.serial_number == selected_dev["serial_number"]
                    for x in self.esp32_ws_devices
                ]
            ):
                continue
            if selected_dev["channel"] == "usb":
                esp32_device = ESP32DeviceUSB(selected_dev["device_address"])

            elif selected_dev["channel"] == "ble":
                esp32_device = ESP32DeviceBLE(selected_dev["device_address"])
            else:
                raise NotImplementedError(
                    f"Channel {selected_dev['channel']} not implemented"
                )
            self.esp32_ws_devices.add(
                ESP32WSDevice(
                    ws_connection=self.ws_connection,
                    esp32_device=esp32_device,
                    serial_number=selected_dev["serial_number"],
                )
            )
            opened_devices.append(selected_dev)

        opened_tasks = []
        for esp32_ws_device in self.esp32_ws_devices:
            esp32_ws_device.on_close_callbacks.add(self.esp32_on_close)
            opened_tasks.append(asyncio.create_task(esp32_ws_device.open()))
        results = await asyncio.gather(*opened_tasks, return_exceptions=True)
        errors = [r for r in results if isinstance(r, Exception)]
        return opened_devices

    async def task_watch_connected_devices(self):
        while True:
            try:
                await self.open_esp32_devices()
            except:
                traceback.print_exc()
            await asyncio.sleep(1)

    @action
    async def close_all_esp32_devices(self):
        async with asyncio.TaskGroup() as tg:
            for esp32_ws_device in self.esp32_ws_devices.copy():
                tg.create_task(esp32_ws_device.close())
