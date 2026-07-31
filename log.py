from datetime import datetime
from json import dumps
from pathlib import Path


log_file = Path("log.jsonl").open("a", encoding="utf8", buffering=1)


def log(data: dict | str):
    if isinstance(data, str):
        data = {"text": data}
    log_file.write(
        dumps({"time": datetime.now().isoformat(), **data}, ensure_ascii=False) + "\n"
    )
    log_file.flush()
