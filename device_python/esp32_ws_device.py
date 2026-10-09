from device_python import ws_device
from device_python.esp32_device_base import ESP32DeviceBase
from device_python.esp32_device_usb import ESP32DeviceUSB
from device_python.ws_connection import WSConnection

from .ws_device import WSDevice


class ESP32WSDevice(WSDevice):

    def __init__(
        self,
        *,
        ws_connection: WSConnection,
        esp32_device: ESP32DeviceBase,
    ) -> None:
        super().__init__(
            ws_connection=ws_connection,
            device_id=None,
        )
        self.esp32_device = esp32_device
        # self.sub_devices = set[Device]()
        # self.feature_configs = {
        #     "ws2812": {
        #         "gpio_num": 38,
        #     }
        # }

    async def on_esp32_event(self, event: dict):
        name = event.get("name")
        value = event.get("value")
        if isinstance(name, str):
            await self.send_event(name, value)

    async def on_esp32_close(self, esp32_device: ESP32DeviceBase):
        await self.close()

    async def on_open(self):
        self.esp32_device.on_event_callbacks.add(self.on_esp32_event)
        self.esp32_device.on_close_callbacks.add(self.on_esp32_close)
        await self.esp32_device.open()
        self.device_id = f"esp32-{self.esp32_device.serial_number}"
        if self.esp32_device.channel is not None:
            self.device_id = self.device_id + "-" + self.esp32_device.channel
        await super().on_open()
        for k, v in self.esp32_device.system_info.items():
            await self.set_state(k, v)
        actions_from_commands = await self.generate_actions_from_commands()
        self.actions.extend(actions_from_commands)
        await self.send_action_definitions()
        # await self.create_devices_from_features()

    async def on_close(self):
        await super().on_close()
        await self.esp32_device.close()
        # while self.sub_devices:
        #     sub_device = self.sub_devices.pop()
        #     await sub_device.close()

    async def generate_action_handler_from_command(self, command: dict):

        async def handler(**kwargs):

            response = await self.esp32_device.send_command(command["name"], kwargs)
            return response

        return handler

    async def generate_actions_from_commands(self):
        commands = (await self.esp32_device.send_command("command_defs_get"))["result"][
            "command_defs"
        ]

        actions: list[ws_device.Action] = []
        for command in commands:
            esp32_param_defs: list[dict] = command["parameters"]
            action_param_defs: list[ws_device.Parameter] = []
            for param_def in esp32_param_defs:
                action_param_defs.append(
                    ws_device.Parameter(
                        name=param_def["name"],
                        type=param_def["type"],
                        optional=param_def["optional"],
                        description=param_def.get("description"),
                    )
                )
            action = ws_device.Action(
                f"esp32_{command['name']}",
                action_param_defs,
                None,
                await self.generate_action_handler_from_command(command),
            )

            actions.append(action)
        return actions

    # @action
    # async def create_devices_from_features(self):
    #     while self.sub_devices:
    #         sub_device = self.sub_devices.pop()
    #         await sub_device.close()
    #     esp32_states: dict[str, bool] = (
    #         await self.esp32_device.send_command("state_get_all")
    #     )["result"]["states"]
    #     features: list[str] = []
    #     for key, value in esp32_states.items():
    #         if key.startswith("feature_") and value == "true":
    #             features.append(key[8:])

    #     await self.set_state("features", features)

    #     for feature in features:
    #         if feature == "ws2812":
    #             sub_device = WS2812(
    #                 ws_connection=self.ws_connection,
    #                 device_id=f"ws2812-{self.esp32_device.serial_number}",
    #                 esp32_device=self.esp32_device,
    #                 gpio_num=self.feature_configs["ws2812"]["gpio_num"],
    #             )
    #             await sub_device.open()
    #             self.sub_devices.add(sub_device)

    # @action
    # async def feature_configs_get(self):
    #     return self.feature_configs

    # @action
    # async def feature_configs_set(self, config: str):
    #     self.feature_configs = json.loads(config)
