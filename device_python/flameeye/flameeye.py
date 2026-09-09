from device_python.device import Device, action as device_action
from . import action


class Flameeye(Device):

    @device_action
    async def measure(self):
        return await action.measure()
