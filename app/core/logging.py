from contextvars import ContextVar
from contextvars import Token
import logging
import time

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="-")


class TraceIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = trace_id_var.get()
        return True


def configure_logging(level: str) -> None:
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    handler = logging.StreamHandler()
    handler.addFilter(TraceIdFilter())
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s trace_id=%(trace_id)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )
    )
    logging.Formatter.converter = time.gmtime
    root_logger.addHandler(handler)
    root_logger.setLevel(level)


def bind_trace_id(trace_id: str) -> Token[str]:
    return trace_id_var.set(trace_id)


def reset_trace_id(token: Token[str]) -> None:
    trace_id_var.reset(token)
