import logging
import structlog
import datetime
import atexit

start_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

log_file = open(f"log/mika_log_{start_time}.jsonl", "a", encoding="utf-8")
atexit.register(log_file.close)

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S.%f", utc=False),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(ensure_ascii=False),
    ],
    logger_factory=structlog.WriteLoggerFactory(file=log_file),
    wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
)


def get_logger(module: str = "no_module"):
    return structlog.get_logger(module=module)


def bytes_to_str(b):
    return str(bytes(b), encoding="utf8", errors="backslashreplace")
