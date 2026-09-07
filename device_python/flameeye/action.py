import json
import time

import numpy as np
from . import adb, templates
import aiosqlite

android_db_path = "/storage/emulated/0/Android/data/tech.torchbearer.flameeye/apps/__UNI__AC0AA31/doc/spectrometer.db"


async def match_condition(condition: str):
    print(f"match_condition {condition} ... ", end="", flush=True)
    try:
        screen = await adb.get_screenshot()
        result = templates.match_condition(screen, condition)
        print("OK" if result else "ERROR")
        return result
    except Exception as e:
        print("ERROR")
        raise e


async def assert_condition(condition: str, error_message: str | None = None):
    matched = await match_condition(condition)
    if not matched:
        if error_message:
            raise Exception(error_message)
        else:
            raise Exception(f"condition {condition} not matched")


async def click_button(button_template_name: str):
    print(f"click_button {button_template_name} ... ", end="", flush=True)
    screen = await adb.get_screenshot()
    pos = await templates.get_button_pos(screen, button_template_name)
    await adb.click(pos)
    print("OK")


async def wait_for_condition(condition: str, timeout_s=5, raise_on_timeout=True):
    print(f"wait_for_condition {condition} ... ", end="", flush=True)
    start_time = time.time()
    while True:
        screen = await adb.get_screenshot()
        if templates.match_condition(screen, condition):
            print("OK")
            return "ok"
        if time.time() - start_time > timeout_s:
            if raise_on_timeout:
                raise Exception(f"timeout for condition {condition}")
            else:
                print("ERROR")
                return "timeoue"


async def android_app_measure_once():
    await assert_condition("in-measure-page", "Android APP not opened")
    if not await match_condition("measure-status-idle"):
        await click_button("init--pause-button")
        await wait_for_condition("measure-status-idle")
    if not await match_condition("auto-exposure-switch-on"):
        await click_button("auto-exposure-switch-off--auto-exposure-switch")
        await wait_for_condition("auto-exposure-switch-on")

    await click_button("init--single-frame-button")
    ok = await wait_for_condition(
        "measure-status-idle", timeout_s=20, raise_on_timeout=False
    )
    if ok == "ok":
        return
    assert ok == "timeoue"
    assert await match_condition(
        "under-exposure-adjustifying"
    ) or await match_condition("over-exposure-adjustifying")
    await click_button("init--pause-button")
    await wait_for_condition("measure-status-idle")


async def save():
    await assert_condition("in-measure-page")
    await assert_condition("measure-status-idle")
    exposure_status = "unknown"
    if await match_condition("exposure-normal"):
        exposure_status = "normal"
    elif await match_condition("under-exposure-adjustifying"):
        exposure_status = "under"
    elif await match_condition("over-exposure-adjustifying"):
        exposure_status = "over"
    await click_button("init--save-button")
    await wait_for_condition("input-file-name-page-title")
    await click_button("input-save-name--title")
    await wait_for_condition("input-file-name-page-confirm-button")
    await click_button("input-save-name--confirm-button")
    await wait_for_condition("in-measure-page")
    return {"exposure_status": exposure_status}


async def get_last_record_from_db(db_path):
    async with aiosqlite.connect(db_path) as db:
        # 获取列名
        async with db.execute("SELECT * FROM historyData LIMIT 1") as cursor:
            columns = (
                [description[0] for description in cursor.description]
                if cursor.description
                else []
            )

        # 获取最后一条数据
        async with db.execute(
            "SELECT * FROM historyData ORDER BY id DESC LIMIT 1"
        ) as cursor:
            row = await cursor.fetchone()
            if row and columns:
                return dict(zip(columns, row))
    raise Exception(f"No record found from databse {db_path}")


async def measure():
    assert await adb.connected(), "Android device not connected"
    await android_app_measure_once()
    extra_info = await save()
    db_path = await adb.pull_file(android_db_path)
    record = await get_last_record_from_db(db_path)
    record_data = json.loads(record["data"])
    beginWl = int(record["beginWl"])
    endWl = int(record["endWl"])

    spectrum = record_data["data"]

    wavelength = list(np.linspace(beginWl, endWl, len(spectrum)))
    return {
        "time": record["createTime"],
        "exposure_time": float(record["exposureTime"]),
        **extra_info,
        "wavelength": wavelength,
        "spectrum": spectrum,
    }
