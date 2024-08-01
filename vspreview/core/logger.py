from __future__ import annotations

import logging
import sys
from typing import Callable

from vapoursynth import MessageType

__all__ = [
    'setup_logger', 'set_log_level',

    'get_vs_logger',
]

_logger_setup = False


LOG_LEVEL = logging.INFO


_vsLogType_to_logging = {
    MessageType.MESSAGE_TYPE_DEBUG: logging.DEBUG,
    MessageType.MESSAGE_TYPE_INFORMATION: logging.INFO,
    MessageType.MESSAGE_TYPE_WARNING: logging.WARNING,
    MessageType.MESSAGE_TYPE_CRITICAL: logging.CRITICAL,
    MessageType.MESSAGE_TYPE_FATAL: logging.FATAL,
}


def setup_logger() -> None:
    global _logger_setup

    if not _logger_setup:
        try:
            from ctypes import windll

            windll.kernel32.SetConsoleMode(windll.kernel32.GetStdHandle(-11), 7)
        except ImportError:
            ...

        logging.basicConfig(format='{asctime}: {name}: {levelname}: {message}', style='{', level=LOG_LEVEL)
        logging.Formatter.default_msec_format = '%s.%03d'
        if sys.stdout.isatty():
            logging.addLevelName(
                logging.DEBUG, "\033[0;32m%s\033[0m" % logging.getLevelName(logging.DEBUG)
            )
            logging.addLevelName(
                logging.INFO, "\033[1;33m%s\033[0m" % logging.getLevelName(logging.INFO)
            )
            logging.addLevelName(
                logging.WARNING, "\033[1;35m%s\033[1;0m" % logging.getLevelName(logging.WARNING)
            )
            logging.addLevelName(
                logging.ERROR, "\033[1;41m%s\033[1;0m" % logging.getLevelName(logging.ERROR)
            )

        _logger_setup = True


def set_log_level(main: int = LOG_LEVEL, engine: int = logging.ERROR) -> None:
    from vsengine import _hospice  # type: ignore[import]
    from vsengine import policy

    policy.logger.addFilter(lambda record: 'dead environment' not in record.msg)
    _hospice.logger.setLevel(engine)
    logging.getLogger().level = main


def get_vs_logger() -> Callable[[MessageType, str], None]:
    setup_logger()

    def _logger(mType: MessageType, msg: str) -> None:
        import logging
        return logging.log(_vsLogType_to_logging[mType], msg)

    return _logger
