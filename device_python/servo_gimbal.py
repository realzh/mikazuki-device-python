import asyncio
import math

import serial

from device_python import config
from device_python.log import get_logger
from device_python.ws_connection import WSConnection
from device_python.ws_device import WSDevice, action

logger = get_logger("servo_gimbal")


class ServoGimBalWSDevice(WSDevice):
    def __init__(self, *, ws_connection: WSConnection):
        super().__init__(ws_connection=ws_connection, device_id="servo-gimbal")
        self.serial: serial.Serial | None = None
        self.timeout = 1
        self.command_lock = asyncio.Lock()

    @action
    async def serial_port_open(self, serial_port: str, baudrate: int = 115200):
        self.serial = await asyncio.to_thread(
            serial.Serial, serial_port, baudrate=baudrate
        )
        logger.info("open_serial", port=serial_port)
        await self.set_state("serial", serial_port)
        config.write("servo_gimbal.serial_port", serial_port)

    @action
    async def serial_port_close(self):
        if self.serial:
            self.serial.close()
            logger.info("close_serial", port=self.serial.portstr)
            self.serial = None
            await self.set_state("serial", None)

    async def on_open(self):
        await super().on_open()
        try:
            config_serial_port = config.read("servo_gimbal.serial_port")
            assert isinstance(config_serial_port, str)
            await self.serial_port_open(config_serial_port)
        except:
            pass
        self.tasks.add(asyncio.create_task(self.task_update_state()))

    async def on_close(self):
        await super().on_close()
        await self.serial_port_close()

    async def servo_readline(self) -> str:
        assert self.serial
        line_bytes = await asyncio.to_thread(self.serial.readline)
        line = line_bytes.decode().strip()
        logger.debug("read_line", line=line)
        return line

    async def servo_writeline(self, line: str):
        assert self.serial
        logger.debug("write_line", line=line)
        data = line.encode() + b"\n"
        await asyncio.to_thread(self.serial.write, data)

    @action
    async def send_servo_command(self, command: str, receive_response: str = "true"):
        async with self.command_lock:
            await self.servo_writeline(command)
            if receive_response == "true":
                return await asyncio.wait_for(self.servo_readline(), self.timeout)
            return ""

    @action
    async def get_position(self):
        pan = (int((await self.send_servo_command("#001PRAD"))[5:]) - 1500) / 2000 * 360
        tilt = (
            (int((await self.send_servo_command("#002PRAD"))[5:]) - 1500) / 2000 * 270
        )
        return {"pan": pan, "tilt": tilt}

    async def update_position(self):
        pos = await self.get_position()
        for k, v in pos.items():
            await self.set_state(k, v)

    async def task_update_state(self):
        while True:
            try:
                if self.serial and self.serial.is_open:
                    await self.update_position()
            except:
                pass
            await asyncio.sleep(0.2)

    @action
    async def move(self, pan: float, tilt: float):
        pan_pos = math.floor(pan / 360 * 2000 + 1500)
        tilt_pos = math.floor(tilt / 270 * 2000 + 1500)
        await self.send_servo_command(f"#001P{pan_pos}", receive_response="false")
        await self.send_servo_command(f"#002P{tilt_pos}", receive_response="false")
