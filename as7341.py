import asyncio
from json import loads
from math import floor
from uuid import uuid4

from command import send_command
from device import Device

max_int_time = 0.1
adc_resolution_error_tolerance = 0.004

gain_map = [0.5, 1, 2, 4, 8, 16, 32, 64, 128, 256, 512]

center_wave_length = [415, 445, 480, 515, 555, 590, 630, 680]


def get_max_visible(measure_data):
    return max(
        measure_data["F1"],
        measure_data["F2"],
        measure_data["F3"],
        measure_data["F4"],
        measure_data["F5"],
        measure_data["F6"],
        measure_data["F7"],
        measure_data["F8"],
    )


async def measure_once():
    config = await read_config()
    rsp = await send_command("as7341_measure_once")
    assert rsp.startswith("OK")
    data_json = rsp.split("Measurement data: ")[1]
    data = loads(data_json)
    adc_value_visible_light_max = get_max_visible(data)
    adc_fullscale = min((config["atime"] + 1) * (config["astep"] + 1), 65535)
    sensitivity = (
        gain_map[config["gain"]]
        * (config["atime"] + 1)
        * (config["astep"] + 1)
        * 2.78e-6
    )
    visible_light_power = [
        data["F1"] / sensitivity,
        data["F2"] / sensitivity,
        data["F3"] / sensitivity,
        data["F4"] / sensitivity,
        data["F5"] / sensitivity,
        data["F6"] / sensitivity,
        data["F7"] / sensitivity,
        data["F8"] / sensitivity,
    ]
    return {
        "data": data,
        "config": config,
        "adc_value_visible_light_max": adc_value_visible_light_max,
        "sensitivity": sensitivity,
        "adc_fullscale": adc_fullscale,
        "visible_light_saturation": adc_value_visible_light_max == adc_fullscale,
        "visible_light_power": visible_light_power,
        "center_wave_length": center_wave_length,
        "adc_resolution_error": 1 / (adc_value_visible_light_max + 1),
    }


async def read_config():
    rsp = await send_command("as7341_read_config")
    assert rsp.startswith("OK")
    config_json = rsp.split("Config: ")[1]
    config = loads(config_json)
    config["int_time"] = (config["atime"] + 1) * (config["astep"] + 1) * 2.78e-6
    return config


async def estimate_max_visible_light_power():
    """
    Light power unit adc_value / (gain * integration_time (s))
    """

    print("Estimating max visible light power ", end="")
    atime = 30
    astep = 10
    await send_command(f"as7341_config_integration_time {atime - 1} {astep - 1}")
    await send_command("as7341_config_gain 0")
    result = await measure_once()
    if result["adc_value_visible_light_max"] == result["adc_fullscale"]:
        print(" 720000(overflow)")
        return 720000

    # 优先使用小积分时间，改变gain，最小化测量时间
    for i in [0, 3, 6, 8, 10]:
        await send_command(f"as7341_config_gain {i}")
        print(".", end="", flush=True)
        result = await measure_once()
        # 当 adc_value 达到 100 后，认为已经具备足够精度进行估算
        if result["adc_value_visible_light_max"] > 100:
            sensitivity = gain_map[i] * atime * astep * 2.78e-6
            power = (result["adc_value_visible_light_max"] + 1) / sensitivity
            print(f" {power:.2f}")
            return power

    # gain 达到最大值后，逐步增加积分时间，最大积分时间 2s
    await send_command("as7341_config_gain 10")
    while True:
        await send_command(f"as7341_config_integration_time {atime - 1} {astep - 1}")
        print(".", end="", flush=True)
        result = await measure_once()

        # 当 int_time 达到 max_int_time 后，不再延长积分时间，即使 adc_value 小于 100 也直接进行估算
        if (
            result["adc_value_visible_light_max"] > 100
            or atime * astep * 2.78e-6 >= max_int_time
        ):
            sensitivity = gain_map[i] * atime * astep * 2.78e-6
            power = (result["adc_value_visible_light_max"] + 1) / sensitivity
            print(f" {power:.2f}")
            return power
        astep = floor(astep * 10)
        if atime * astep * 2.78e-6 > max_int_time:
            astep = floor(max_int_time / (atime * 2.78e-6)) + 2


def find_config_for_light_power(light_power: float):
    # light_power = adc_value / (gain * int_time)
    # adc_value = light_power * (gain * int_time)
    # max_adc_value = min(atime * astep, 65535) = light_power * max_gain * int_time
    # max_gain = min(atime * astep, 65535) / (light_power * int_time)
    atime = 60
    astep = 300
    max_gain = min(atime * astep, 65535) / (light_power * 1.1 * atime * astep * 2.78e-6)

    # 如果 max_gain 足够小，说明光强相对比较大，不需要很长的积分时间
    if max_gain < 1024:
        for i in range(10, -1, -1):
            if gain_map[i] < max_gain:
                return {"gain": i, "atime": atime - 1, "astep": astep - 1}

        # 此时最小的 gain 也不足以满足 max_gain  的要求，也就是必然饱和
        return None

    # 如果 max_gain 很大，说明光强很小，最大的 gain 也不足以充分利用 adc_max，所以需要延长积分时间
    while atime * astep * 2.78e-6 < max_int_time:
        max_gain = min(atime * astep, 65535) / (
            light_power * 1.1 * atime * astep * 2.78e-6
        )
        # 如果此时 max_gain 足够小，说明积分时间已经够了
        if max_gain < 1024:
            # 因为对增长速度的控制，max_gain 不可能一次缩小 1/2 以上
            assert max_gain >= 512, max_gain
            return {"gain": 10, "atime": atime - 1, "astep": astep - 1}

        # 以 1.41 倍增长积分时间
        astep = floor(astep * 1.41)

    # 如果 max_int_time 积分时间也不足以获得足够大的 adc_value，则直接返回最大 gain 与 2s 积分时间
    astep = floor(max_int_time / (atime * 2.78e-6))
    max_gain = min(atime * astep, 65535) / (light_power * 1.1 * atime * astep * 2.78e-6)
    assert max_gain >= 512
    return {"gain": 10, "atime": atime - 1, "astep": astep - 1}


async def optimize_sensitivity():

    max_visible_light_power = await estimate_max_visible_light_power()
    if max_visible_light_power is None:
        return None
    config = find_config_for_light_power(max_visible_light_power)
    if config is None:
        return None

    await send_command(
        f"as7341_config_integration_time {config['atime']} {config['astep']}"
    )

    await send_command(f"as7341_config_gain {config['gain']}")


async def measure_with_sensitivity_optimization():
    print(f"Measuring... {(await read_config())['int_time'] * 2:.0f}s")
    result = await measure_once()
    if (
        not result["visible_light_saturation"]
        and result["adc_resolution_error"] < adc_resolution_error_tolerance
    ):
        return result
    print("Optimizing sensitivity...")
    await optimize_sensitivity()

    print(f"Measuring... {(await read_config())['int_time'] * 2:.0f}s")
    return await measure_once()


class AS7341(Device):
    type = "as7341"

    id = "as7341"

    async def on_connected(self):
        await super().on_connected()
        await send_command("as7341_init")

    async def on_message(self, message: dict):

        action = message.get("action")
        if action == "measure-once":
            measurement_id = message.get("measurement_id", uuid4())
            print("measuring")
            result = await measure_with_sensitivity_optimization()
            await self.send(
                {
                    "action": "measure-result",
                    "measurement_id": measurement_id,
                    "result": result,
                }
            )
