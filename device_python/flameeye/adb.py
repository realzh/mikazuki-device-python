import asyncio
import pathlib
import sys
from datetime import datetime
import tempfile
from uuid import uuid4

from device_python.device import Device, action


async def run_command(cmd: str, raise_on_fail=True):
    print(f"adb > {cmd}")
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    print(f"adb | {stdout}, {stderr}")
    returncode = proc.returncode
    if returncode != 0 and raise_on_fail:
        raise Exception(f"adb command failed '{cmd}'，{returncode}, {stderr}")
    return stdout.decode().strip()


async def connected():
    return (
        await run_command(
            "adb shell settings get global device_name", raise_on_fail=False
        )
    ) == "Xiaomi 14"


async def generate_temp_file_path(ext: str = ""):
    folder_path = tempfile.gettempdir() + "/device-flameeye"
    await run_command(f"mkdir -p {folder_path}")
    return (
        folder_path
        + "/"
        + datetime.now().strftime("%Y%m%d-%H%M%S")
        + "-"
        + str(uuid4())
        + ext
    )


async def get_screenshot():
    image_file_path = await generate_temp_file_path(".png")
    await run_command(f"adb exec-out screencap -p > {image_file_path}")
    return image_file_path


async def click(pos: list[int]):
    await run_command(f"adb shell input tap {pos[0]} {pos[1]}")


async def pull_file(android_file_path: str):
    ext = pathlib.Path(android_file_path).suffix
    file_path = await generate_temp_file_path(ext)
    await run_command(f"adb pull {android_file_path} {file_path}")
    return file_path


class ADB(Device):

    async def on_connected(self):
        await super().on_connected()
        try:
            device_name = await run_command("adb shell settings get global device_name")
            await self.set_state("device_name", device_name)
        except:
            pass

    @action("get")
    async def get_device_name(self):

        device_name = await run_command("adb shell settings get global device_name")
        await self.set_state("device_name", device_name)
        return device_name

    @action("post")
    async def connect_to_device(self, pair_code: str, ip: str, port: str):
        return await run_command(f'echo "{pair_code}" | adb pair {ip}:{port}')
