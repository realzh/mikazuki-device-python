import asyncio
import traceback
import serial
import serial.tools.list_ports


from device_python.esp32_device_ble import ESP32DeviceBLE
from device_python.esp32_device_usb import ESP32DeviceUSB
from device_python.esp32_ws_device import ESP32WSDevice
from device_python.log import get_logger
from device_python.ws_connection import WSConnection
from device_python.ws_device import WSDevice, action

logger = get_logger("mac_hub_ws_device")


class MacHubWSDevice(WSDevice):
    def __init__(self, *, ws_connection: WSConnection):
        super().__init__(ws_connection=ws_connection, device_id="mac-hub")
        self.esp32_ws_devices = set[ESP32WSDevice]()

    async def esp32_on_close(self, esp32_ws_device: ESP32WSDevice):
        if esp32_ws_device in self.esp32_ws_devices:
            self.esp32_ws_devices.remove(esp32_ws_device)
        await self.set_state(
            "esp32_devices_opened", [x.device_id for x in self.esp32_ws_devices]
        )

    async def on_open(self):
        await super().on_open()
        await self.esp32_device_open()
        self.tasks.add(asyncio.create_task(self.task_watch_connected_devices()))

    async def on_close(self):
        await super().on_close()
        await self.esp32_device_close_all()

    @action
    async def esp32_device_open(self):
        discovered_devices = []
        discovered_devices.extend(await ESP32DeviceUSB.scan_devices())
        discovered_devices.extend(await ESP32DeviceBLE.scan_devices())
        await self.set_state("esp32_devices_discovered", discovered_devices)
        device_serial_numbers = set[str]()
        for dev in discovered_devices:
            device_serial_numbers.add(dev["serial_number"])

        channel_priority = {
            "usb": 0,
            "ble": 1,
        }
        selected_devices = []
        for sn in device_serial_numbers:
            selected_device = None
            for dev in discovered_devices:
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
        await self.set_state(
            "esp32_devices_opened", [x.device_id for x in self.esp32_ws_devices]
        )
        return opened_devices

    async def task_watch_connected_devices(self):
        while True:
            try:
                await self.esp32_device_open()
            except:
                logger.exception()
            await asyncio.sleep(1)

    @action
    async def esp32_device_close_all(self):
        async with asyncio.TaskGroup() as tg:
            for esp32_ws_device in self.esp32_ws_devices.copy():
                tg.create_task(esp32_ws_device.close())

    @action
    async def serial_port_get_connected_devices(self):
        ports = list(serial.tools.list_ports.comports())
        devices = []
        for p in ports:
            dev = {}
            dev["device"] = p.device
            dev["name"] = p.name
            dev["description"] = p.description
            dev["hwid"] = p.hwid
            dev["vid"] = p.vid
            dev["pid"] = p.pid
            dev["serial_number"] = p.serial_number
            dev["location"] = p.location
            dev["manufacturer"] = p.manufacturer
            dev["product"] = p.product
            dev["interface"] = p.interface
            dev["usb_description"] = p.usb_description()
            dev["usb_info"] = p.usb_info()
            devices.append(dev)
        return devices
