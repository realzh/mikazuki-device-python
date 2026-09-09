from device_python.device import Device
from device_python.device import action as device_action

from . import action


class Flameeye(Device):

    @device_action
    async def measure(self):
        return await action.measure()
