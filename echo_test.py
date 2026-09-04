import asyncio
import random
import string
from tqdm import tqdm

from esp32 import send_command


async def main():

    for i in tqdm(range(100000)):
        test_str = "S" + "".join(
            random.choices(
                string.ascii_letters + string.digits, k=random.randint(1, 200)
            )
        )
        rsp = await send_command("desktop-control", f"echo {test_str}")
        assert rsp == test_str, (rsp, test_str)


asyncio.run(main())
